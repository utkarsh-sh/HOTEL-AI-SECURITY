from dataclasses import dataclass
from typing import List, Sequence

from evaluation.schema import EvaluationEvent


@dataclass(frozen=True)
class EventMatch:
    """A matched ground-truth event and prediction."""

    truth_index: int
    prediction_index: int


@dataclass(frozen=True)
class EventMatchingResult:
    """Result of matching predicted events against ground truth."""

    matches: List[EventMatch]
    true_positives: int
    false_positives: int
    false_negatives: int


def _events_overlap(
    truth: EvaluationEvent,
    prediction: EvaluationEvent,
) -> bool:
    """Return True when two event frame intervals overlap."""

    return (
        truth.start_frame <= prediction.end_frame
        and prediction.start_frame <= truth.end_frame
    )


def _events_compatible(
    truth: EvaluationEvent,
    prediction: EvaluationEvent,
) -> bool:
    """Return True when two events can represent the same incident."""

    if truth.event_type != prediction.event_type:
        return False

    if truth.zone_id != prediction.zone_id:
        return False

    return _events_overlap(truth, prediction)


def match_events(
    ground_truth: Sequence[EvaluationEvent],
    predictions: Sequence[EvaluationEvent],
) -> EventMatchingResult:
    """
    Match predicted events against ground-truth events.

    Matching requires:
    - same event type
    - same zone
    - overlapping frame intervals

    Each event can participate in at most one match.
    """

    if not isinstance(ground_truth, Sequence):
        raise ValueError("ground_truth must be a sequence")

    if not isinstance(predictions, Sequence):
        raise ValueError("predictions must be a sequence")

    for event in ground_truth:
        if not isinstance(event, EvaluationEvent):
            raise ValueError(
                "ground_truth must contain EvaluationEvent objects"
            )

    for event in predictions:
        if not isinstance(event, EvaluationEvent):
            raise ValueError(
                "predictions must contain EvaluationEvent objects"
            )

    matches: List[EventMatch] = []
    matched_truth = set()
    matched_predictions = set()

    for prediction_index, prediction in enumerate(predictions):
        for truth_index, truth in enumerate(ground_truth):
            if truth_index in matched_truth:
                continue

            if prediction_index in matched_predictions:
                continue

            if not _events_compatible(truth, prediction):
                continue

            matches.append(
                EventMatch(
                    truth_index=truth_index,
                    prediction_index=prediction_index,
                )
            )

            matched_truth.add(truth_index)
            matched_predictions.add(prediction_index)

            break

    true_positives = len(matches)
    false_positives = len(predictions) - len(matched_predictions)
    false_negatives = len(ground_truth) - len(matched_truth)

    return EventMatchingResult(
        matches=matches,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )
