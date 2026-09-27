import json
from pathlib import Path

from evaluation.adapter import convert_prediction_events
from evaluation.evaluator import evaluate_events
from evaluation.metrics import calculate_evaluation_metrics
from evaluation.schema import load_ground_truth


def _serialize_metrics(metrics):
    return {
        "true_positives": metrics.true_positives,
        "false_positives": metrics.false_positives,
        "false_negatives": metrics.false_negatives,
        "precision": round(metrics.precision, 6),
        "recall": round(metrics.recall, 6),
        "f1": round(metrics.f1, 6),
    }


def generate_evaluation_report(
    artifact_path,
    report_path,
    ground_truth_path=None,
):
    """
    Load an evaluation artifact, calculate reproducible metrics,
    and save a JSON evaluation report.

    Without independent ground truth, only artifact-derived metrics
    are reported.

    With independent ground truth, event-level classification metrics,
    per-event-type metrics, and detection latency are reported.
    """

    artifact_path = Path(artifact_path)
    report_path = Path(report_path)

    if not artifact_path.exists():
        raise ValueError(
            f"Evaluation artifact not found: {artifact_path}"
        )

    try:
        with artifact_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            artifact = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Unable to load evaluation artifact: {artifact_path}"
        ) from exc

    metrics = calculate_evaluation_metrics(artifact)

    report = {
        "report_type": "evaluation",
        "evaluation_version": "1.1",
        "ground_truth_available": False,
        "ground_truth_note": (
            "Independent ground truth is required for "
            "precision, recall, F1, false-positive, "
            "and false-negative classification metrics."
        ),
        **metrics,
    }

    if ground_truth_path is not None:
        ground_truth_path = Path(ground_truth_path)

        if not ground_truth_path.exists():
            raise ValueError(
                f"Ground truth not found: {ground_truth_path}"
            )

        ground_truth = load_ground_truth(ground_truth_path)

        if ground_truth.camera_id != artifact["camera_id"]:
            raise ValueError(
                "ground truth camera_id does not match "
                "evaluation artifact camera_id"
            )

        if ground_truth.video != artifact["video"]:
            raise ValueError(
                "ground truth video does not match "
                "evaluation artifact video"
            )

        predictions = convert_prediction_events(
            artifact["result"]["predictions"]
        )

        evaluation = evaluate_events(
            ground_truth=ground_truth.events,
            predictions=predictions,
            fps=artifact["source_fps"],
        )

        report.update(
            {
                "ground_truth_available": True,
                "ground_truth_path": str(ground_truth_path),
                "ground_truth_event_count": len(
                    ground_truth.events
                ),
                "true_positives": (
                    evaluation.metrics.true_positives
                ),
                "false_positives": (
                    evaluation.metrics.false_positives
                ),
                "false_negatives": (
                    evaluation.metrics.false_negatives
                ),
                "precision": round(
                    evaluation.metrics.precision,
                    6,
                ),
                "recall": round(
                    evaluation.metrics.recall,
                    6,
                ),
                "f1": round(
                    evaluation.metrics.f1,
                    6,
                ),
                "metrics_by_event_type": {
                    event_type: _serialize_metrics(event_metrics)
                    for event_type, event_metrics
                    in evaluation.metrics_by_event_type.items()
                },
                "detection_latencies_seconds": [
                    round(latency, 6)
                    for latency
                    in evaluation.detection_latencies_seconds
                ],
                "mean_detection_latency_seconds": (
                    None
                    if evaluation.mean_detection_latency_seconds
                    is None
                    else round(
                        evaluation.mean_detection_latency_seconds,
                        6,
                    )
                ),
                "false_positive_rate": None,
                "false_positive_rate_available": False,
                "false_positive_rate_note": (
                    "A defined negative-exposure denominator "
                    "is required to calculate false-positive rate."
                ),
            }
        )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    return report
