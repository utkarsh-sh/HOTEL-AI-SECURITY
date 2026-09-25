from __future__ import annotations

from math import isfinite
from typing import Any


class WeaponEventProcessor:
    """Turn persistent gun/knife observations into camera-local WEAPON events."""

    VALID_CLASSES = {"gun", "knife"}

    def __init__(
        self,
        persistence_frames: int = 3,
        min_confidence: float = 0.50,
        region_tolerance: float = 75.0,
        track_association_tolerance: float = 100.0,
    ) -> None:
        if not isinstance(persistence_frames, int) or persistence_frames <= 0:
            raise ValueError("persistence_frames must be an integer > 0")
        if not isinstance(min_confidence, (int, float)) or not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not isinstance(region_tolerance, (int, float)) or float(region_tolerance) < 0:
            raise ValueError("region_tolerance must be >= 0")
        if not isinstance(track_association_tolerance, (int, float)) or float(track_association_tolerance) < 0:
            raise ValueError("track_association_tolerance must be >= 0")
        self.persistence_frames = persistence_frames
        self.min_confidence = float(min_confidence)
        self.region_tolerance = float(region_tolerance)
        self.track_association_tolerance = float(track_association_tolerance)
        self._states: dict[int, dict[str, Any]] = {}
        self._next_id = 1

    @staticmethod
    def _box(box: Any) -> list[float]:
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ValueError("box must contain four coordinates")
        try:
            values = [float(v) for v in box]
        except (TypeError, ValueError) as exc:
            raise ValueError("box coordinates must be numeric") from exc
        if not all(isfinite(v) for v in values):
            raise ValueError("box coordinates must be finite")
        if values[2] <= values[0] or values[3] <= values[1]:
            raise ValueError("invalid box coordinates")
        return values

    @staticmethod
    def _center(box: list[float]) -> tuple[float, float]:
        return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    @staticmethod
    def _inside(point: tuple[float, float], box: list[float]) -> bool:
        return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]

    @staticmethod
    def _distance_to_box(point: tuple[float, float], box: list[float]) -> float:
        dx = max(box[0] - point[0], 0.0, point[0] - box[2])
        dy = max(box[1] - point[1], 0.0, point[1] - box[3])
        return (dx * dx + dy * dy) ** 0.5

    def _track_id(self, box: list[float], tracks: list[dict[str, Any]]) -> int | None:
        center = self._center(box)
        candidates: list[tuple[bool, float, int]] = []
        for track in tracks:
            if not isinstance(track, dict) or "track_id" not in track or "box" not in track:
                continue
            try:
                track_box = self._box(track["box"])
                track_id = int(track["track_id"])
            except (TypeError, ValueError):
                continue
            inside = self._inside(center, track_box)
            distance = self._distance_to_box(center, track_box)
            if inside or distance <= self.track_association_tolerance:
                candidates.append((inside, distance, track_id))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (not x[0], x[1], x[2]))
        return candidates[0][2]

    def _match(self, class_name: str, center: tuple[float, float], track_id: int | None) -> int | None:
        matches = []
        for state_id, state in self._states.items():
            if state["class_name"] != class_name:
                continue
            if track_id is not None and state["track_id"] is not None and track_id != state["track_id"]:
                continue
            distance = self._distance(center, state["center"])
            if distance <= self.region_tolerance:
                matches.append((distance, state_id))
        return min(matches)[1] if matches else None

    def evaluate(self, detections: list[dict[str, Any]], tracks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not isinstance(detections, list):
            raise ValueError("detections must be a list")
        if tracks is None:
            tracks = []
        if not isinstance(tracks, list):
            raise ValueError("tracks must be a list")
        current: set[int] = set()
        events: list[dict[str, Any]] = []
        for detection in detections:
            if not isinstance(detection, dict):
                raise ValueError("each detection must be a dictionary")
            for field in ("class_name", "confidence", "box"):
                if field not in detection:
                    raise ValueError(f"detection missing {field}")
            class_name = str(detection["class_name"]).strip().lower()
            if class_name not in self.VALID_CLASSES:
                raise ValueError(f"unsupported weapon class: {class_name}")
            confidence = float(detection["confidence"])
            if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0 and 1")
            if confidence < self.min_confidence:
                continue
            box = self._box(detection["box"])
            track_id = self._track_id(box, tracks)
            center = self._center(box)
            state_id = self._match(class_name, center, track_id)
            if state_id is None:
                state_id = self._next_id
                self._next_id += 1
                self._states[state_id] = {
                    "class_name": class_name,
                    "track_id": track_id,
                    "center": center,
                    "count": 0,
                    "alerted": False,
                    "max_confidence": confidence,
                }
            state = self._states[state_id]
            if state["track_id"] is None and track_id is not None:
                state["track_id"] = track_id
            state["center"] = center
            state["count"] += 1
            state["max_confidence"] = max(state["max_confidence"], confidence)
            current.add(state_id)
            if state["count"] >= self.persistence_frames and not state["alerted"]:
                state["alerted"] = True
                events.append({
                    "event_type": "WEAPON",
                    "severity": "CRITICAL",
                    "zone_id": None,
                    "zone_name": None,
                    "track_id": state["track_id"],
                    "message": f"Potential weapon detected ({class_name.upper()}) by CCTV analysis",
                    "weapon_class": class_name,
                    "confidence": state["max_confidence"],
                    "box": box,
                })
        for stale in set(self._states) - current:
            del self._states[stale]
        return events

    def reset(self) -> None:
        self._states.clear()
        self._next_id = 1
