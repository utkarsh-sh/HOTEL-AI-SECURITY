from typing import Dict, List, Optional


class FallDetector:
    """
    Lightweight temporal heuristic for identifying a potential
    person-down/fall event from tracked person bounding boxes.

    This is an AI-assisted security signal, not a medical or
    clinical fall-detection system.
    """

    def __init__(
        self,
        persistence_frames: int = 3,
        min_horizontal_aspect_ratio: float = 1.5,
    ) -> None:
        if not isinstance(persistence_frames, int):
            raise ValueError(
                "persistence_frames must be an integer"
            )

        if persistence_frames <= 0:
            raise ValueError(
                "persistence_frames must be > 0"
            )

        if not isinstance(
            min_horizontal_aspect_ratio,
            (int, float),
        ):
            raise ValueError(
                "min_horizontal_aspect_ratio must be a number"
            )

        if min_horizontal_aspect_ratio <= 0:
            raise ValueError(
                "min_horizontal_aspect_ratio must be > 0"
            )

        self.persistence_frames = persistence_frames
        self.min_horizontal_aspect_ratio = float(
            min_horizontal_aspect_ratio
        )

        self._horizontal_counts: Dict[int, int] = {}
        self._alerted_tracks: set[int] = set()

    def _validate_box(self, box: List[int]) -> None:
        if not isinstance(box, (list, tuple)):
            raise ValueError("box must be a list or tuple")

        if len(box) != 4:
            raise ValueError(
                "box must contain four coordinates"
            )

        x1, y1, x2, y2 = box

        if not all(
            isinstance(value, (int, float))
            for value in box
        ):
            raise ValueError(
                "box coordinates must be numeric"
            )

        if x2 <= x1:
            raise ValueError(
                "box x2 must be greater than x1"
            )

        if y2 <= y1:
            raise ValueError(
                "box y2 must be greater than y1"
            )

    def _is_horizontal(self, box: List[int]) -> bool:
        x1, y1, x2, y2 = box

        width = float(x2 - x1)
        height = float(y2 - y1)

        aspect_ratio = width / height

        return (
            aspect_ratio
            >= self.min_horizontal_aspect_ratio
        )

    def evaluate(
        self,
        track_id: int,
        box: List[int],
    ) -> Optional[dict]:
        """
        Evaluate one tracked person.

        Returns a FALL event dictionary only when the horizontal
        posture persists for the configured number of frames and
        that track has not already generated an alert.
        """

        if not isinstance(track_id, int):
            raise ValueError(
                "track_id must be an integer"
            )

        if track_id < 0:
            raise ValueError(
                "track_id must be >= 0"
            )

        self._validate_box(box)

        if not self._is_horizontal(box):
            self._horizontal_counts.pop(track_id, None)
            self._alerted_tracks.discard(track_id)
            return None

        current_count = (
            self._horizontal_counts.get(track_id, 0)
            + 1
        )

        self._horizontal_counts[track_id] = current_count

        if (
            current_count >= self.persistence_frames
            and track_id not in self._alerted_tracks
        ):
            self._alerted_tracks.add(track_id)

            return {
                "event_type": "FALL",
                "severity": "HIGH",
                "track_id": track_id,
                "message": (
                    f"Potential person-down event "
                    f"detected for track {track_id}"
                ),
            }

        return None

    def reset_track(self, track_id: int) -> None:
        """Reset detector state for a specific track."""

        if not isinstance(track_id, int):
            raise ValueError(
                "track_id must be an integer"
            )

        self._horizontal_counts.pop(track_id, None)
        self._alerted_tracks.discard(track_id)

    def reset(self) -> None:
        """Reset all detector state."""

        self._horizontal_counts.clear()
        self._alerted_tracks.clear()
