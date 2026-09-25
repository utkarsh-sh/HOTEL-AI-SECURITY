from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


AFTER_HOURS_MODEL_VERSION = "after-hours-rule-v1"
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class AfterHoursRule:
    """Raise one logical event for persistent presence outside work hours."""

    def __init__(
        self,
        camera_id: str,
        config: dict[str, Any],
        available_zone_ids: set[str] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(camera_id, str) or not camera_id.strip():
            raise ValueError("camera_id must be a non-empty string")
        if not isinstance(config, dict):
            raise ValueError("after-hours configuration must be an object")

        self.camera_id = camera_id
        self.enabled = bool(config.get("enabled", False))
        self.persistence_frames = self._validate_positive_int(
            config.get("persistence_frames", 3),
            "persistence_frames",
        )

        severity = str(config.get("severity", "HIGH")).strip().upper()
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                "severity must be one of "
                f"{sorted(VALID_SEVERITIES)}"
            )
        self.severity = severity

        self.timezone = self._load_timezone(
            config.get("timezone", "UTC")
        )
        self.now_provider = now_provider

        self.default_schedule = self._validate_schedule(
            config.get("default_schedule", {}),
            "default_schedule",
        )

        cameras = config.get("cameras", {})
        if not isinstance(cameras, dict):
            raise ValueError("'cameras' must be an object")

        camera_override = cameras.get(camera_id, {})
        self.camera_schedule = self._merge_schedule(
            self.default_schedule,
            camera_override,
        )

        available_zone_ids = available_zone_ids or set()
        for zone_id in self.camera_schedule["zone_ids"]:
            if available_zone_ids and zone_id not in available_zone_ids:
                raise ValueError(
                    f"Unknown after-hours zone_id: {zone_id}"
                )

        self._qualifying_frames: dict[str, int] = {}
        self._alert_active: dict[str, bool] = {}

    @staticmethod
    def _validate_positive_int(value: Any, field_name: str) -> int:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
        ):
            raise ValueError(f"{field_name} must be an integer > 0")
        return value

    @staticmethod
    def _load_timezone(value: Any) -> ZoneInfo:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "timezone must be a non-empty IANA timezone string"
            )
        try:
            return ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            if value == "Asia/Kolkata":
                return timezone(
                    timedelta(hours=5, minutes=30)
                )
            raise ValueError(f"Unknown timezone: {value}") from exc

    @staticmethod
    def _parse_time(value: Any, field_name: str) -> time:
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must use HH:MM format")
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError(f"{field_name} must use HH:MM format")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must use HH:MM format"
            ) from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"{field_name} must use HH:MM format")
        return time(hour=hour, minute=minute)

    @classmethod
    def _validate_schedule(
        cls,
        schedule: Any,
        field_name: str,
    ) -> dict[str, Any]:
        if not isinstance(schedule, dict):
            raise ValueError(f"{field_name} must be an object")

        working_days = schedule.get(
            "working_days",
            [0, 1, 2, 3, 4],
        )
        if (
            not isinstance(working_days, list)
            or any(
                not isinstance(day, int)
                or isinstance(day, bool)
                or day < 0
                or day > 6
                for day in working_days
            )
            or len(set(working_days)) != len(working_days)
        ):
            raise ValueError(
                f"{field_name}.working_days must contain "
                "unique integers from 0 to 6"
            )

        start = cls._parse_time(
            schedule.get("start"),
            f"{field_name}.start",
        )
        end = cls._parse_time(
            schedule.get("end"),
            f"{field_name}.end",
        )
        if start == end:
            raise ValueError(
                f"{field_name}.start and end must differ"
            )

        zone_ids = schedule.get("zone_ids", [])
        if (
            not isinstance(zone_ids, list)
            or any(
                not isinstance(zone_id, str)
                or not zone_id.strip()
                for zone_id in zone_ids
            )
            or len(set(zone_ids)) != len(zone_ids)
        ):
            raise ValueError(
                f"{field_name}.zone_ids must be a list "
                "of unique non-empty strings"
            )

        return {
            "working_days": list(working_days),
            "start": start,
            "end": end,
            "zone_ids": list(zone_ids),
        }

    @classmethod
    def _merge_schedule(
        cls,
        default_schedule: dict[str, Any],
        camera_override: Any,
    ) -> dict[str, Any]:
        if camera_override is None:
            camera_override = {}
        if not isinstance(camera_override, dict):
            raise ValueError(
                "Camera after-hours override must be an object"
            )

        merged = {
            "working_days": list(default_schedule["working_days"]),
            "start": (
                f"{default_schedule['start'].hour:02d}:"
                f"{default_schedule['start'].minute:02d}"
            ),
            "end": (
                f"{default_schedule['end'].hour:02d}:"
                f"{default_schedule['end'].minute:02d}"
            ),
            "zone_ids": list(default_schedule["zone_ids"]),
        }

        for key in ("working_days", "start", "end", "zone_ids"):
            if key in camera_override:
                merged[key] = camera_override[key]

        return cls._validate_schedule(
            merged,
            "camera schedule",
        )

    def _current_time(self) -> datetime:
        current = (
            self.now_provider()
            if self.now_provider is not None
            else datetime.now(self.timezone)
        )
        if current.tzinfo is None:
            current = current.replace(tzinfo=self.timezone)
        return current.astimezone(self.timezone)

    def _is_after_hours(self) -> bool:
        current = self._current_time()
        schedule = self.camera_schedule

        if current.weekday() not in schedule["working_days"]:
            return True

        current_time = current.time()
        # MVP deliberately supports same-day working windows only.
        return not (
            schedule["start"]
            <= current_time
            < schedule["end"]
        )

    @staticmethod
    def _active_track_ids(
        tracks: list[dict[str, Any]],
    ) -> set[int]:
        if not isinstance(tracks, list):
            raise ValueError("tracks must be a list")

        active_ids: set[int] = set()
        for track in tracks:
            if not isinstance(track, dict):
                raise ValueError("each track must be a dictionary")
            if "track_id" not in track:
                raise ValueError("track missing track_id")
            try:
                track_id = int(track["track_id"])
                missed = int(track.get("missed", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "track_id and missed must be integers"
                ) from exc
            if missed == 0:
                active_ids.add(track_id)
        return active_ids

    def _qualifying_scopes(
        self,
        active_track_ids: set[int],
        zone_results: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        target_zone_ids = self.camera_schedule["zone_ids"]

        if not target_zone_ids:
            if not active_track_ids:
                return {}
            return {
                "camera": {
                    "zone_id": None,
                    "zone_name": None,
                    "people_count": len(active_track_ids),
                }
            }

        if not isinstance(zone_results, list):
            raise ValueError("zone_results must be a list")

        occupants: dict[str, set[int]] = {}
        zone_names: dict[str, str] = {}

        for result in zone_results:
            if not isinstance(result, dict):
                raise ValueError(
                    "each zone result must be a dictionary"
                )

            zone_id = result.get("zone_id")
            if zone_id not in target_zone_ids:
                continue
            if not bool(result.get("inside", False)):
                continue

            try:
                track_id = int(result.get("track_id"))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "zone result track_id must be an integer"
                ) from exc

            if track_id not in active_track_ids:
                continue

            occupants.setdefault(zone_id, set()).add(track_id)
            zone_names[zone_id] = str(
                result.get("zone_name", zone_id)
            )

        return {
            f"zone:{zone_id}": {
                "zone_id": zone_id,
                "zone_name": zone_names[zone_id],
                "people_count": len(track_ids),
            }
            for zone_id, track_ids in occupants.items()
        }

    def evaluate(
        self,
        tracks: list[dict[str, Any]],
        zone_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        active_track_ids = self._active_track_ids(tracks)

        if not self._is_after_hours():
            self.reset()
            return []

        qualifying = self._qualifying_scopes(
            active_track_ids,
            zone_results,
        )

        for scope_id in list(self._qualifying_frames):
            if scope_id not in qualifying:
                self._qualifying_frames.pop(scope_id, None)
                self._alert_active.pop(scope_id, None)

        events: list[dict[str, Any]] = []
        for scope_id, details in qualifying.items():
            self._qualifying_frames[scope_id] = (
                self._qualifying_frames.get(scope_id, 0) + 1
            )

            if (
                self._qualifying_frames[scope_id]
                >= self.persistence_frames
                and not self._alert_active.get(scope_id, False)
            ):
                self._alert_active[scope_id] = True
                zone_name = details["zone_name"]
                count = int(details["people_count"])

                if zone_name is None:
                    message = (
                        "After-hours presence detected: "
                        f"{count} active people outside "
                        "configured working hours"
                    )
                else:
                    message = (
                        "After-hours presence detected in "
                        f"{zone_name}: {count} active people"
                    )

                events.append(
                    {
                        "event_type": "AFTER_HOURS",
                        "severity": self.severity,
                        "zone_id": details["zone_id"],
                        "zone_name": zone_name,
                        "track_id": None,
                        "message": message,
                        "people_count": count,
                    }
                )

        return events

    def reset(self) -> None:
        self._qualifying_frames.clear()
        self._alert_active.clear()
