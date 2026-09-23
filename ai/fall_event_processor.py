from typing import List, Dict, Any

from ai.fall_detector import FallDetector


class FallEventProcessor:
    """
    Converts active PersonTracker tracks into potential FALL events.

    Database persistence and notification delivery remain outside this
    processor so the existing event pipeline can be reused unchanged.
    """

    def __init__(
        self,
        persistence_frames: int = 3,
        min_horizontal_aspect_ratio: float = 1.5,
    ) -> None:
        self.detector = FallDetector(
            persistence_frames=persistence_frames,
            min_horizontal_aspect_ratio=min_horizontal_aspect_ratio,
        )

    def evaluate(
        self,
        tracks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not isinstance(tracks, list):
            raise ValueError("tracks must be a list")

        events: List[Dict[str, Any]] = []

        for track in tracks:
            if not isinstance(track, dict):
                raise ValueError(
                    "each track must be a dictionary"
                )

            if "track_id" not in track:
                raise ValueError(
                    "track missing track_id"
                )

            if "box" not in track:
                raise ValueError(
                    "track missing box"
                )

            event = self.detector.evaluate(
                track_id=track["track_id"],
                box=track["box"],
            )

            if event is not None:
                event["zone_id"] = None
                event["zone_name"] = None
                events.append(event)

        return events

    def reset_track(self, track_id: int) -> None:
        self.detector.reset_track(track_id)

    def reset(self) -> None:
        self.detector.reset()
