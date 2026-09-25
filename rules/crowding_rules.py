from __future__ import annotations

from typing import Any


class CrowdingRule:
    """Generate one logical CROWDING event after persistent crowding."""

    def __init__(
        self,
        minimum_people: int = 5,
        persistence_frames: int = 3,
    ) -> None:
        if (
            not isinstance(minimum_people, int)
            or isinstance(minimum_people, bool)
            or minimum_people < 2
        ):
            raise ValueError("minimum_people must be an integer >= 2")

        if (
            not isinstance(persistence_frames, int)
            or isinstance(persistence_frames, bool)
            or persistence_frames <= 0
        ):
            raise ValueError("persistence_frames must be an integer > 0")

        self.minimum_people = minimum_people
        self.persistence_frames = persistence_frames
        self._qualifying_frames = 0
        self._alert_active = False

    @staticmethod
    def _active_track_ids(tracks: list[dict[str, Any]]) -> set[int]:
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

    def evaluate(self, tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(tracks, list):
            raise ValueError("tracks must be a list")

        people_count = len(self._active_track_ids(tracks))

        if people_count >= self.minimum_people:
            self._qualifying_frames += 1

            if (
                self._qualifying_frames >= self.persistence_frames
                and not self._alert_active
            ):
                self._alert_active = True
                return [{
                    "event_type": "CROWDING",
                    "severity": "HIGH",
                    "zone_id": None,
                    "zone_name": None,
                    "track_id": None,
                    "message": (
                        f"Crowding detected: {people_count} active people "
                        f"(threshold {self.minimum_people})"
                    ),
                    "people_count": people_count,
                    "threshold": self.minimum_people,
                }]
        else:
            self._qualifying_frames = 0
            self._alert_active = False

        return []

    def reset(self) -> None:
        self._qualifying_frames = 0
        self._alert_active = False
