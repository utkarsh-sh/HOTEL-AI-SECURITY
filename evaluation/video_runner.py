from dataclasses import dataclass
from typing import Any, Dict, List

import cv2


@dataclass(frozen=True)
class VideoPipelineResult:
    total_frames: int
    ai_frames: int
    predictions: List[Dict[str, Any]]


class OpenCVVideoSource:
    """Minimal read-only video source for evaluation."""

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.capture = cv2.VideoCapture(video_path)

        if not self.capture.isOpened():
            raise ValueError(
                f"Unable to open video: {video_path}"
            )

    def read(self):
        success, frame = self.capture.read()

        if not success:
            return None

        return frame

    def close(self):
        self.capture.release()


def prediction_from_event(
    event: Dict[str, Any],
    frame_index: int,
) -> Dict[str, Any]:

    if not isinstance(event, dict):
        raise ValueError("event must be a dictionary")

    if not isinstance(frame_index, int):
        raise ValueError("frame_index must be an integer")

    if frame_index < 0:
        raise ValueError("frame_index must be >= 0")

    event_type = event.get("event_type")
    zone_id = event.get("zone_id")

    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")

    if not isinstance(zone_id, str) or not zone_id.strip():
        raise ValueError("zone_id must be a non-empty string")

    return {
        "event_type": event_type,
        "zone_id": zone_id,
        "start_frame": frame_index,
        "end_frame": frame_index,
    }


def run_event_pipeline(
    source: Any,
    detector: Any,
    tracker: Any,
    zone_detector: Any,
    intrusion_rule: Any,
    source_fps: float,
    ai_fps: float,
) -> VideoPipelineResult:

    if not isinstance(source_fps, (int, float)) or source_fps <= 0:
        raise ValueError("source_fps must be > 0")

    if not isinstance(ai_fps, (int, float)) or ai_fps <= 0:
        raise ValueError("ai_fps must be > 0")

    if ai_fps > source_fps:
        raise ValueError("ai_fps must be <= source_fps")

    sample_interval = max(
        1,
        round(source_fps / ai_fps),
    )

    total_frames = 0
    ai_frames = 0
    predictions: List[Dict[str, Any]] = []

    try:
        while True:
            frame = source.read()

            if frame is None:
                break

            frame_index = total_frames
            total_frames += 1

            if frame_index % sample_interval != 0:
                continue

            ai_frames += 1

            detections = detector.detect(frame)
            tracks = tracker.update(detections)
            zone_results = zone_detector.check_tracks(tracks)
            events = intrusion_rule.evaluate(zone_results)

            for event in events:
                predictions.append(
                    prediction_from_event(
                        event,
                        frame_index,
                    )
                )

    finally:
        close_method = getattr(source, "close", None)

        if callable(close_method):
            close_method()

    return VideoPipelineResult(
        total_frames=total_frames,
        ai_frames=ai_frames,
        predictions=predictions,
    )
