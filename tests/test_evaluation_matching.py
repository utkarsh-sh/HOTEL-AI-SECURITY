from evaluation.matching import (
    EventMatch,
    match_events,
)
from evaluation.schema import EvaluationEvent


def event(
    start_frame,
    end_frame,
    zone_id="ZONE-001",
    event_type="INTRUSION",
):
    return EvaluationEvent(
        event_type=event_type,
        zone_id=zone_id,
        start_frame=start_frame,
        end_frame=end_frame,
    )


def test_overlapping_same_event_is_match():
    truth = [event(100, 160)]
    predictions = [event(105, 165)]

    result = match_events(truth, predictions)

    assert result.true_positives == 1
    assert result.false_positives == 0
    assert result.false_negatives == 0


def test_non_overlapping_prediction_is_false_positive():
    truth = [event(100, 160)]
    predictions = [event(300, 360)]

    result = match_events(truth, predictions)

    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 1


def test_missing_prediction_is_false_negative():
    truth = [event(100, 160)]
    predictions = []

    result = match_events(truth, predictions)

    assert result.true_positives == 0
    assert result.false_positives == 0
    assert result.false_negatives == 1


def test_extra_prediction_is_false_positive():
    truth = []
    predictions = [event(100, 160)]

    result = match_events(truth, predictions)

    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 0


def test_different_zone_does_not_match():
    truth = [event(100, 160, zone_id="ZONE-001")]
    predictions = [event(105, 165, zone_id="ZONE-002")]

    result = match_events(truth, predictions)

    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 1


def test_different_event_type_does_not_match():
    truth = [event(100, 160, event_type="INTRUSION")]
    predictions = [event(105, 165, event_type="FALL")]

    result = match_events(truth, predictions)

    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 1


def test_one_prediction_matches_only_one_truth_event():
    truth = [
        event(100, 160),
        event(300, 360),
    ]

    predictions = [
        event(120, 170),
    ]

    result = match_events(truth, predictions)

    assert result.true_positives == 1
    assert result.false_positives == 0
    assert result.false_negatives == 1


def test_match_result_exposes_matches():
    truth = [event(100, 160)]
    predictions = [event(105, 165)]

    result = match_events(truth, predictions)

    assert len(result.matches) == 1
    assert isinstance(result.matches[0], EventMatch)
    assert result.matches[0].truth_index == 0
    assert result.matches[0].prediction_index == 0
