import json
from dataclasses import dataclass
from pathlib import Path

from evaluation.video_runner import VideoPipelineResult


@dataclass(frozen=True)
class EvaluationArtifact:
    video: str
    camera_id: str
    source_fps: float
    ai_fps: float
    model_version: str
    result: VideoPipelineResult

    def __post_init__(self):
        if not isinstance(self.video, str) or not self.video.strip():
            raise ValueError("video must be a non-empty string")

        if not isinstance(self.camera_id, str) or not self.camera_id.strip():
            raise ValueError("camera_id must be a non-empty string")

        if not isinstance(self.source_fps, (int, float)) or self.source_fps <= 0:
            raise ValueError("source_fps must be > 0")

        if not isinstance(self.ai_fps, (int, float)) or self.ai_fps <= 0:
            raise ValueError("ai_fps must be > 0")

        if self.ai_fps > self.source_fps:
            raise ValueError("ai_fps must be <= source_fps")

        if not isinstance(self.model_version, str) or not self.model_version.strip():
            raise ValueError("model_version must be a non-empty string")

        if not isinstance(self.result, VideoPipelineResult):
            raise ValueError(
                "result must be a VideoPipelineResult"
            )

    def to_dict(self):
        return {
            "video": self.video,
            "camera_id": self.camera_id,
            "source_fps": self.source_fps,
            "ai_fps": self.ai_fps,
            "model_version": self.model_version,
            "result": {
                "total_frames": self.result.total_frames,
                "ai_frames": self.result.ai_frames,
                "predictions": self.result.predictions,
            },
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("artifact must be a dictionary")

        required = {
            "video",
            "camera_id",
            "source_fps",
            "ai_fps",
            "model_version",
            "result",
        }

        missing = required - data.keys()

        if missing:
            raise ValueError(
                f"missing artifact fields: {sorted(missing)}"
            )

        result_data = data["result"]

        if not isinstance(result_data, dict):
            raise ValueError("result must be a dictionary")

        result_required = {
            "total_frames",
            "ai_frames",
            "predictions",
        }

        missing_result = result_required - result_data.keys()

        if missing_result:
            raise ValueError(
                f"missing result fields: {sorted(missing_result)}"
            )

        predictions = result_data["predictions"]

        if not isinstance(predictions, list):
            raise ValueError("predictions must be a list")

        result = VideoPipelineResult(
            total_frames=result_data["total_frames"],
            ai_frames=result_data["ai_frames"],
            predictions=predictions,
        )

        return cls(
            video=data["video"],
            camera_id=data["camera_id"],
            source_fps=data["source_fps"],
            ai_fps=data["ai_fps"],
            model_version=data["model_version"],
            result=result,
        )


def save_evaluation_artifact(
    artifact: EvaluationArtifact,
    path,
):
    if not isinstance(artifact, EvaluationArtifact):
        raise ValueError(
            "artifact must be an EvaluationArtifact"
        )

    output_path = Path(path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            artifact.to_dict(),
            f,
            indent=2,
        )


def load_evaluation_artifact(path):
    input_path = Path(path)

    try:
        with open(
            input_path,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"unable to load evaluation artifact: {input_path}"
        ) from exc

    return EvaluationArtifact.from_dict(data)
