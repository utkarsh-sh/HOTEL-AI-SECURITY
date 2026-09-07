import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")

CURRENT_WORKFLOW_VERSION = "workflow-v2"
LEGACY_WORKFLOW_VERSION = "legacy-v1"


class EventDatabase:

    def __init__(
        self,
        database_path=DATABASE_PATH
    ):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.connection = sqlite3.connect(
            self.database_path
        )

        self.connection.row_factory = sqlite3.Row

        self._create_tables()

    # ==========================================================
    # DATABASE SETUP
    # ==========================================================

    def _create_tables(self):

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NEW',

                camera_id TEXT NOT NULL,

                zone_id TEXT,
                zone_name TEXT,

                track_id INTEGER,

                message TEXT NOT NULL,

                timestamp TEXT NOT NULL,

                model_version TEXT,

                workflow_version TEXT NOT NULL
                    DEFAULT 'legacy-v1',

                evidence_path TEXT,

                created_at TEXT NOT NULL,

                acknowledged_at TEXT,
                dispatched_at TEXT,
                resolved_at TEXT,

                resolution TEXT
            )
            """
        )

        self.connection.commit()

        # ------------------------------------------------------
        # Migration: evidence_path
        # ------------------------------------------------------

        columns = self.connection.execute(
            "PRAGMA table_info(events)"
        ).fetchall()

        column_names = {
            column["name"]
            for column in columns
        }

        if "evidence_path" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE events
                ADD COLUMN evidence_path TEXT
                """
            )

            self.connection.commit()

        # ------------------------------------------------------
        # Migration: workflow_version
        #
        # Existing events are historical records, therefore
        # they receive legacy-v1.
        #
        # New events explicitly receive workflow-v2.
        # ------------------------------------------------------

        columns = self.connection.execute(
            "PRAGMA table_info(events)"
        ).fetchall()

        column_names = {
            column["name"]
            for column in columns
        }

        if "workflow_version" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE events
                ADD COLUMN workflow_version TEXT
                DEFAULT 'legacy-v1'
                """
            )

            self.connection.commit()

    # ==========================================================
    # CREATE EVENT
    # ==========================================================

    def create_event(
        self,
        event_type,
        severity,
        camera_id,
        zone_id,
        zone_name,
        track_id,
        message,
        model_version="prototype-v1",
        evidence_path=None,
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO events (
                event_type,
                severity,
                status,
                camera_id,
                zone_id,
                zone_name,
                track_id,
                message,
                timestamp,
                model_version,
                workflow_version,
                evidence_path,
                created_at,
                acknowledged_at,
                dispatched_at,
                resolved_at,
                resolution
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                event_type,
                severity,
                "NEW",
                camera_id,
                zone_id,
                zone_name,
                track_id,
                message,
                timestamp,
                model_version,
                CURRENT_WORKFLOW_VERSION,
                evidence_path,
                timestamp,
                None,
                None,
                None,
                None,
            )
        )

        self.connection.commit()

        return cursor.lastrowid

    # ==========================================================
    # EVIDENCE
    # ==========================================================

    def update_evidence_path(
        self,
        event_id,
        evidence_path,
    ):

        cursor = self.connection.execute(
            """
            UPDATE events
            SET evidence_path = ?
            WHERE id = ?
            """,
            (
                evidence_path,
                event_id,
            )
        )

        self.connection.commit()

        if cursor.rowcount != 1:

            raise ValueError(
                f"Event not found: {event_id}"
            )

    # ==========================================================
    # READ OPERATIONS
    # ==========================================================

    def get_event(
        self,
        event_id
    ):

        cursor = self.connection.execute(
            """
            SELECT *
            FROM events
            WHERE id = ?
            """,
            (event_id,)
        )

        return cursor.fetchone()

    def get_all_events(self):

        cursor = self.connection.execute(
            """
            SELECT *
            FROM events
            ORDER BY id DESC
            """
        )

        return cursor.fetchall()

    # ==========================================================
    # INTERNAL ATOMIC UPDATE
    # ==========================================================

    def _execute_atomic_transition(
        self,
        sql,
        parameters,
        event_id,
        expected_status,
        target_status,
    ):

        cursor = self.connection.execute(
            sql,
            parameters
        )

        if cursor.rowcount != 1:

            raise ValueError(
                "Atomic event transition failed: "
                f"event {event_id} was expected to be "
                f"{expected_status}, but its state changed "
                f"before transition to {target_status}."
            )

    # ==========================================================
    # EVENT LIFECYCLE
    # ==========================================================

    def update_status(
        self,
        event_id,
        status,
        resolution=None
    ):

        supported_statuses = {
            "ACKNOWLEDGED",
            "DISPATCHED",
            "RESOLVED",
            "FALSE_POSITIVE",
        }

        if status not in supported_statuses:

            raise ValueError(
                f"Unsupported event status: {status}"
            )

        if status in {
            "RESOLVED",
            "FALSE_POSITIVE",
        }:

            if (
                resolution is None
                or not str(resolution).strip()
            ):
                raise ValueError(
                    f"{status} requires a non-empty resolution"
                )

        self.connection.execute(
            "BEGIN IMMEDIATE"
        )

        try:

            event = self.get_event(event_id)

            if event is None:

                raise ValueError(
                    f"Event not found: {event_id}"
                )

            current_status = event["status"]

            now = datetime.now(
                timezone.utc
            ).isoformat()

            # --------------------------------------------------
            # NEW -> ACKNOWLEDGED
            # --------------------------------------------------

            if status == "ACKNOWLEDGED":

                expected_status = "NEW"

                if current_status != expected_status:

                    raise ValueError(
                        "Invalid event transition: "
                        f"{current_status} -> ACKNOWLEDGED"
                    )

                self._execute_atomic_transition(
                    """
                    UPDATE events
                    SET
                        status = ?,
                        acknowledged_at = ?,
                        dispatched_at = NULL,
                        resolved_at = NULL,
                        resolution = NULL
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        "ACKNOWLEDGED",
                        now,
                        event_id,
                        expected_status,
                    ),
                    event_id,
                    expected_status,
                    "ACKNOWLEDGED",
                )

            # --------------------------------------------------
            # ACKNOWLEDGED -> DISPATCHED
            # --------------------------------------------------

            elif status == "DISPATCHED":

                expected_status = "ACKNOWLEDGED"

                if current_status != expected_status:

                    raise ValueError(
                        "Invalid event transition: "
                        f"{current_status} -> DISPATCHED"
                    )

                if event["acknowledged_at"] is None:

                    raise ValueError(
                        "Cannot dispatch an event without "
                        "acknowledged_at"
                    )

                self._execute_atomic_transition(
                    """
                    UPDATE events
                    SET
                        status = ?,
                        dispatched_at = ?,
                        resolved_at = NULL,
                        resolution = NULL
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        "DISPATCHED",
                        now,
                        event_id,
                        expected_status,
                    ),
                    event_id,
                    expected_status,
                    "DISPATCHED",
                )

            # --------------------------------------------------
            # DISPATCHED -> RESOLVED
            # --------------------------------------------------

            elif status == "RESOLVED":

                expected_status = "DISPATCHED"

                if current_status != expected_status:

                    raise ValueError(
                        "Invalid event transition: "
                        f"{current_status} -> RESOLVED"
                    )

                if event["acknowledged_at"] is None:

                    raise ValueError(
                        "Cannot resolve an event without "
                        "acknowledged_at"
                    )

                if event["dispatched_at"] is None:

                    raise ValueError(
                        "Cannot resolve an event without "
                        "dispatched_at"
                    )

                self._execute_atomic_transition(
                    """
                    UPDATE events
                    SET
                        status = ?,
                        resolved_at = ?,
                        resolution = ?
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        "RESOLVED",
                        now,
                        str(resolution).strip(),
                        event_id,
                        expected_status,
                    ),
                    event_id,
                    expected_status,
                    "RESOLVED",
                )

            # --------------------------------------------------
            # NEW / ACKNOWLEDGED -> FALSE_POSITIVE
            # --------------------------------------------------

            elif status == "FALSE_POSITIVE":

                allowed_source_statuses = {
                    "NEW",
                    "ACKNOWLEDGED",
                }

                if current_status not in allowed_source_statuses:

                    raise ValueError(
                        "Invalid event transition: "
                        f"{current_status} -> FALSE_POSITIVE"
                    )

                expected_status = current_status

                self._execute_atomic_transition(
                    """
                    UPDATE events
                    SET
                        status = ?,
                        dispatched_at = NULL,
                        resolved_at = NULL,
                        resolution = ?
                    WHERE id = ?
                      AND status = ?
                    """,
                    (
                        "FALSE_POSITIVE",
                        str(resolution).strip(),
                        event_id,
                        expected_status,
                    ),
                    event_id,
                    expected_status,
                    "FALSE_POSITIVE",
                )

            self.connection.commit()

        except Exception:

            self.connection.rollback()

            raise

    # ==========================================================
    # CLOSE
    # ==========================================================

    def close(self):

        if self.connection:

            self.connection.close()

            self.connection = None