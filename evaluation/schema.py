import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class EvaluationEvent:
    """Ground-truth event annotation for a recorded evaluation video."""

    event_type: str
    zone_id: str
    start_frame: int
    end_frame: int

    def __post_init__(self):
        if not isinstance(self.event_type, str) or not self.event_type.strip():
            raise ValueError("event_type must be a non-empty string")

        if not isinstance(self.zone_id, str) or not self.zone_id.strip():
            raise ValueError("zone_id must be a non-empty string")

        if not isinstance(self.start_frame, int):
            raise ValueError("start_frame must be an integer")

        if not isinstance(self.end_frame, int):
            raise ValueError("end_frame must be an integer")

        if self.start_frame < 0:
            raise ValueError("start_frame must be >= 0")

        if self.end_frame < 0:
            raise ValueError("end_frame must be >= 0")

        if self.end_frame < self.start_frame:
            raise ValueError(
                "end_frame must be >= start_frame"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "zone_id": self.zone_id,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("event must be an object")

        required_fields = {
            "event_type",
            "zone_id",
            "start_frame",
            "end_frame",
        }

        missing = required_fields - payload.keys()

        if missing:
            raise ValueError(
                f"event is missing fields: {sorted(missing)}"
            )

        return cls(
            event_type=payload["event_type"],
            zone_id=payload["zone_id"],
            start_frame=payload["start_frame"],
            end_frame=payload["end_frame"],
        )


@dataclass(frozen=True)
class EvaluationVideo:
    """Ground-truth annotations associated with one video."""

    video: str
    camera_id: str
    events: List[EvaluationEvent]

    def __post_init__(self):
        if not isinstance(self.video, str) or not self.video.strip():
            raise ValueError("video must be a non-empty string")

        if (
            not isinstance(self.camera_id, str)
            or not self.camera_id.strip()
        ):
            raise ValueError(
                "camera_id must be a non-empty string"
            )

        if not isinstance(self.events, list):
            raise ValueError("events must be a list")

        if not all(
            isinstance(event, EvaluationEvent)
            for event in self.events
        ):
            raise ValueError(
                "events must contain EvaluationEvent objects"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video": self.video,
            "camera_id": self.camera_id,
            "events": [
                event.to_dict()
                for event in self.events
            ],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError(
                "ground-truth payload must be an object"
            )

        video = payload.get("video")
        camera_id = payload.get("camera_id")
        events = payload.get("events")

        if not isinstance(video, str) or not video.strip():
            raise ValueError(
                "video must be a non-empty string"
            )

        if (
            not isinstance(camera_id, str)
            or not camera_id.strip()
        ):
            raise ValueError(
                "camera_id must be a non-empty string"
            )

        if not isinstance(events, list):
            raise ValueError("events must be a list")

        return cls(
            video=video,
            camera_id=camera_id,
            events=[
                EvaluationEvent.from_dict(event)
                for event in events
            ],
        )


def save_ground_truth(
    evaluation_video: EvaluationVideo,
    path: Path,
) -> None:
    """Save ground-truth annotations as formatted JSON."""

    if not isinstance(
        evaluation_video,
        EvaluationVideo,
    ):
        raise ValueError(
            "evaluation_video must be an EvaluationVideo"
        )

    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            evaluation_video.to_dict(),
            indent=2,
        ),
        encoding="utf-8",
    )


def load_ground_truth(
    path: Path,
) -> EvaluationVideo:
    """Load and validate ground-truth annotations."""

    path = Path(path)

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Could not load ground truth: {exc}"
        ) from exc

    return EvaluationVideo.from_dict(payload)
