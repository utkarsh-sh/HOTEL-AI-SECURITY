import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("configs/retention.json")
DEFAULT_EVIDENCE_DIRECTORY = Path("data/output/events")

TERMINAL_EVENT_STATUSES = {
    "RESOLVED",
    "FALSE_POSITIVE",
}


class RetentionConfigurationError(ValueError):
    """Raised when retention configuration is invalid."""


class UnsafeEvidencePathError(ValueError):
    """Raised when evidence is outside the managed directory."""


class RetentionCleanupResult:
    """Summary of a retention cleanup operation."""

    def __init__(
        self,
        events_considered=0,
        events_deleted=0,
        evidence_deleted=0,
        evidence_missing=0,
    ):
        self.events_considered = events_considered
        self.events_deleted = events_deleted
        self.evidence_deleted = evidence_deleted
        self.evidence_missing = evidence_missing

    def to_dict(self):
        return {
            "events_considered": self.events_considered,
            "events_deleted": self.events_deleted,
            "evidence_deleted": self.evidence_deleted,
            "evidence_missing": self.evidence_missing,
        }


class RetentionService:
    def __init__(
        self,
        database,
        config_path=DEFAULT_CONFIG_PATH,
        evidence_directory=DEFAULT_EVIDENCE_DIRECTORY,
    ):
        self.database = database
        self.config_path = Path(config_path)
        self.evidence_directory = Path(evidence_directory)

        self.event_retention_days, self.evidence_retention_days = (
            self._load_configuration()
        )

    def _load_configuration(self):
        if not self.config_path.exists():
            raise RetentionConfigurationError(
                f"Retention configuration not found: "
                f"{self.config_path}"
            )

        try:
            with self.config_path.open(
                "r",
                encoding="utf-8-sig",
            ) as file:
                configuration = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise RetentionConfigurationError(
                f"Invalid retention configuration: {error}"
            ) from error

        event_retention_days = configuration.get(
            "event_retention_days"
        )

        evidence_retention_days = configuration.get(
            "evidence_retention_days"
        )

        self._validate_days(
            "event_retention_days",
            event_retention_days,
        )

        self._validate_days(
            "evidence_retention_days",
            evidence_retention_days,
        )

        return (
            int(event_retention_days),
            int(evidence_retention_days),
        )

    @staticmethod
    def _validate_days(name, value):
        if isinstance(value, bool):
            raise RetentionConfigurationError(
                f"{name} must be a positive integer."
            )

        if not isinstance(value, int):
            raise RetentionConfigurationError(
                f"{name} must be a positive integer."
            )

        if value <= 0:
            raise RetentionConfigurationError(
                f"{name} must be a positive integer."
            )

    def cleanup(self, reference_time=None):
        """
        Remove eligible terminal events and their evidence.

        reference_time is injectable for deterministic testing.
        """

        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        if reference_time.tzinfo is None:
            raise ValueError(
                "reference_time must be timezone-aware."
            )

        event_cutoff = (
            reference_time
            - timedelta(days=self.event_retention_days)
        )

        evidence_cutoff = (
            reference_time
            - timedelta(days=self.evidence_retention_days)
        )

        terminal_statuses = tuple(TERMINAL_EVENT_STATUSES)

        rows = self.database.connection.execute(
            """
            SELECT
                id,
                status,
                created_at,
                evidence_path
            FROM events
            WHERE status IN (?, ?)
            """,
            terminal_statuses,
        ).fetchall()

        result = RetentionCleanupResult(
            events_considered=len(rows)
        )

        for event in rows:
            created_at = self._parse_timestamp(
                event["created_at"]
            )

            if created_at >= event_cutoff:
                continue

            evidence_path = event["evidence_path"]

            if evidence_path:
                try:
                    evidence_created_at = self._get_file_timestamp(
                        evidence_path
                    )
                except UnsafeEvidencePathError:
                    continue

                if (
                    evidence_created_at is not None
                    and evidence_created_at >= evidence_cutoff
                ):
                    continue

                if evidence_created_at is None:
                    result.evidence_missing += 1

                elif self._delete_evidence_file(
                    evidence_path
                ):
                    result.evidence_deleted += 1

            self.database.connection.execute(
                "DELETE FROM events WHERE id = ?",
                (event["id"],),
            )

            result.events_deleted += 1

        self.database.connection.commit()

        return result

    @staticmethod
    def _parse_timestamp(timestamp):
        try:
            parsed = datetime.fromisoformat(timestamp)

        except (TypeError, ValueError) as error:
            raise RetentionConfigurationError(
                f"Invalid event timestamp: {timestamp}"
            ) from error

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    def _get_file_timestamp(self, evidence_path):
        path = Path(evidence_path)

        if not path.is_file():
            return None

        try:
            resolved_path = path.resolve()
            resolved_directory = (
                self.evidence_directory.resolve()
            )

            resolved_path.relative_to(
                resolved_directory
            )

        except (OSError, ValueError) as error:
            raise UnsafeEvidencePathError(
                f"Evidence path is outside the managed directory: "
                f"{evidence_path}"
            ) from error

        modified_at = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        )

        return modified_at

    def _delete_evidence_file(self, evidence_path):
        path = Path(evidence_path)

        try:
            resolved_path = path.resolve()
            resolved_directory = (
                self.evidence_directory.resolve()
            )

            resolved_path.relative_to(
                resolved_directory
            )

        except (OSError, ValueError):
            return False

        if not path.is_file():
            return False

        path.unlink()

        return True




