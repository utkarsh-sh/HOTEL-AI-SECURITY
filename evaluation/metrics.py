from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationMetrics:
    """Classification metrics for event-level evaluation."""

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def _validate_count(name: str, value: int) -> None:
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")

    if value < 0:
        raise ValueError(f"{name} must be >= 0")


def calculate_metrics(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> EvaluationMetrics:
    """Calculate precision, recall, and F1 from event counts."""

    _validate_count("true_positives", true_positives)
    _validate_count("false_positives", false_positives)
    _validate_count("false_negatives", false_negatives)

    precision_denominator = (
        true_positives + false_positives
    )

    recall_denominator = (
        true_positives + false_negatives
    )

    if precision_denominator == 0:
        precision = 0.0
    else:
        precision = (
            true_positives
            / precision_denominator
        )

    if recall_denominator == 0:
        recall = 0.0
    else:
        recall = (
            true_positives
            / recall_denominator
        )

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = (
            2.0
            * precision
            * recall
            / (precision + recall)
        )

    return EvaluationMetrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def calculate_detection_latency(
    ground_truth_start_frame: int,
    predicted_start_frame: int,
    fps: float,
) -> float:
    """
    Calculate detection latency in seconds.

    Positive latency means the prediction occurred after the
    ground-truth event started.

    Negative latency means the prediction occurred before the
    annotated ground-truth start.
    """

    if not isinstance(
        ground_truth_start_frame,
        int,
    ):
        raise ValueError(
            "ground_truth_start_frame must be an integer"
        )

    if not isinstance(
        predicted_start_frame,
        int,
    ):
        raise ValueError(
            "predicted_start_frame must be an integer"
        )

    if ground_truth_start_frame < 0:
        raise ValueError(
            "ground_truth_start_frame must be >= 0"
        )

    if predicted_start_frame < 0:
        raise ValueError(
            "predicted_start_frame must be >= 0"
        )

    if not isinstance(fps, (int, float)):
        raise ValueError("fps must be a number")

    if fps <= 0:
        raise ValueError("fps must be > 0")

    frame_difference = (
        predicted_start_frame
        - ground_truth_start_frame
    )

    return frame_difference / float(fps)


def calculate_evaluation_metrics(artifact: dict) -> dict:
    """
    Calculate metrics that can be derived from an evaluation artifact
    without independent ground truth.

    Precision, recall, F1, false positives, and false negatives are
    intentionally unavailable unless independently verified ground
    truth is supplied.
    """

    if not isinstance(artifact, dict):
        raise ValueError("artifact must be a dictionary")

    required_fields = {
        "video",
        "camera_id",
        "source_fps",
        "ai_fps",
        "model_version",
        "result",
    }

    missing_fields = required_fields.difference(artifact)

    if missing_fields:
        raise ValueError(
            "artifact missing required fields: "
            + ", ".join(sorted(missing_fields))
        )

    source_fps = artifact["source_fps"]
    ai_fps = artifact["ai_fps"]
    result = artifact["result"]

    if not isinstance(source_fps, (int, float)):
        raise ValueError("source_fps must be a number")

    if source_fps <= 0:
        raise ValueError("source_fps must be > 0")

    if not isinstance(ai_fps, (int, float)):
        raise ValueError("ai_fps must be a number")

    if ai_fps <= 0:
        raise ValueError("ai_fps must be > 0")

    if ai_fps > source_fps:
        raise ValueError(
            "ai_fps must be <= source_fps"
        )

    if not isinstance(result, dict):
        raise ValueError("artifact result must be a dictionary")

    if "total_frames" not in result:
        raise ValueError("result missing total_frames")

    if "ai_frames" not in result:
        raise ValueError("result missing ai_frames")

    if "predictions" not in result:
        raise ValueError("result missing predictions")

    total_frames = result["total_frames"]
    ai_frames = result["ai_frames"]
    predictions = result["predictions"]

    _validate_count("total_frames", total_frames)
    _validate_count("ai_frames", ai_frames)

    if ai_frames > total_frames:
        raise ValueError(
            "ai_frames must be <= total_frames"
        )

    if not isinstance(predictions, list):
        raise ValueError("predictions must be a list")

    for prediction in predictions:
        if not isinstance(prediction, dict):
            raise ValueError(
                "each prediction must be a dictionary"
            )

        if "start_frame" not in prediction:
            raise ValueError(
                "prediction missing start_frame"
            )

        if not isinstance(
            prediction["start_frame"],
            int,
        ):
            raise ValueError(
                "prediction start_frame must be an integer"
            )

        if prediction["start_frame"] < 0:
            raise ValueError(
                "prediction start_frame must be >= 0"
            )

    prediction_count = len(predictions)

    if total_frames == 0:
        ai_frame_coverage_percent = 0.0
    else:
        ai_frame_coverage_percent = (
            ai_frames / total_frames
        ) * 100.0

    if ai_frames == 0:
        predictions_per_ai_frame = 0.0
    else:
        predictions_per_ai_frame = (
            prediction_count / ai_frames
        )

    prediction_timestamps_seconds = [
        prediction["start_frame"] / float(source_fps)
        for prediction in predictions
    ]

    return {
        "video": artifact["video"],
        "camera_id": artifact["camera_id"],
        "model_version": artifact["model_version"],
        "source_fps": float(source_fps),
        "ai_fps": float(ai_fps),
        "total_frames": total_frames,
        "ai_frames": ai_frames,
        "ai_frame_coverage_percent": round(
            ai_frame_coverage_percent,
            6,
        ),
        "prediction_count": prediction_count,
        "predictions_per_ai_frame": round(
            predictions_per_ai_frame,
            6,
        ),
        "prediction_timestamps_seconds": (
            prediction_timestamps_seconds
        ),
        "classification_metrics_available": False,
        "precision": None,
        "recall": None,
        "f1": None,
        "false_positives": None,
        "false_negatives": None,
    }
