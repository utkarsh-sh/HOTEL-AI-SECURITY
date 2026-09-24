from typing import List, Dict, Any

from ai.fire_smoke_detector import FireSmokeDetector


class FireSmokeEventProcessor:
    """
    Converts fire/smoke model detections into the common
    security-event contract.

    Database persistence and notification delivery remain
    outside this processor.
    """

    def __init__(
        self,
        persistence_frames: int = 3,
        min_confidence: float = 0.50,
        region_tolerance: float = 75.0,
    ) -> None:
        self.detector = FireSmokeDetector(
            persistence_frames=persistence_frames,
            min_confidence=min_confidence,
            region_tolerance=region_tolerance,
        )

    def evaluate(
        self,
        detections: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not isinstance(
            detections,
            list,
        ):
            raise ValueError(
                "detections must be a list"
            )

        return self.detector.evaluate(
            detections
        )

    def reset(self) -> None:
        self.detector.reset()
