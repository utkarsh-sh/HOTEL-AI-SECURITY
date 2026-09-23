from dataclasses import dataclass
from statistics import mean
from typing import List, Sequence

from evaluation.matching import (
    EventMatchingResult,
    match_events,
)
from evaluation.metrics import (
    EvaluationMetrics,
    calculate_detection_latency,
    calculate_metrics,
)
from evaluation.schema import EvaluationEvent


@dataclass(frozen=True)
class EventEvaluationResult:
    """Complete evaluation result for one set of events."""

    matching: EventMatchingResult
    metrics: EvaluationMetrics
    detection_latencies_seconds: List[float]
    mean_detection_latency_seconds: float | None


def _validate_fps(fps: float) -> None:
    if not isinstance(fps, (int, float)):
        raise ValueError("fps must be a number")

    if fps <= 0:
        raise ValueError("fps must be > 0")


def evaluate_events(
    ground_truth: Sequence[EvaluationEvent],
    predictions: Sequence[EvaluationEvent],
    fps: float,
) -> EventEvaluationResult:
    """
    Evaluate predicted events against ground truth.

    Matching determines TP, FP, and FN.

    Detection latency is calculated only for matched events and
    represents the time between the ground-truth start frame and
    the predicted start frame.
    """

    _validate_fps(fps)

    matching = match_events(
        ground_truth=ground_truth,
        predictions=predictions,
    )

    metrics = calculate_metrics(
        true_positives=matching.true_positives,
        false_positives=matching.false_positives,
        false_negatives=matching.false_negatives,
    )

    detection_latencies_seconds: List[float] = []

    for match in matching.matches:
        truth_event = ground_truth[match.truth_index]
        prediction_event = predictions[
            match.prediction_index
        ]

        latency = calculate_detection_latency(
            ground_truth_start_frame=truth_event.start_frame,
            predicted_start_frame=prediction_event.start_frame,
            fps=fps,
        )

        detection_latencies_seconds.append(latency)

    if detection_latencies_seconds:
        mean_detection_latency_seconds = mean(
            detection_latencies_seconds
        )
    else:
        mean_detection_latency_seconds = None

    return EventEvaluationResult(
        matching=matching,
        metrics=metrics,
        detection_latencies_seconds=(
            detection_latencies_seconds
        ),
        mean_detection_latency_seconds=(
            mean_detection_latency_seconds
        ),
    )
