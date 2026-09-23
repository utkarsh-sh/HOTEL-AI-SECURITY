import pytest

from evaluation.evaluator import evaluate_events
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


def test_evaluator_combines_matching_and_metrics():
    truth = [
        event(100, 160),
        event(300, 360),
    ]

    predictions = [
        event(105, 165),
        event(500, 550),
    ]

    result = evaluate_events(
        ground_truth=truth,
        predictions=predictions,
        fps=5.0,
    )

    assert result.matching.true_positives == 1
    assert result.matching.false_positives == 1
    assert result.matching.false_negatives == 1

    assert result.metrics.precision == pytest.approx(0.5)
    assert result.metrics.recall == pytest.approx(0.5)
    assert result.metrics.f1 == pytest.approx(0.5)


def test_evaluator_reports_detection_latency():
    truth = [
        event(100, 160),
    ]

    predictions = [
        event(125, 165),
    ]

    result = evaluate_events(
        ground_truth=truth,
        predictions=predictions,
        fps=5.0,
    )

    assert result.detection_latencies_seconds == [5.0]
    assert result.mean_detection_latency_seconds == pytest.approx(5.0)


def test_evaluator_reports_multiple_latencies():
    truth = [
        event(100, 160),
        event(300, 360),
    ]

    predictions = [
        event(110, 165),
        event(320, 370),
    ]

    result = evaluate_events(
        ground_truth=truth,
        predictions=predictions,
        fps=10.0,
    )

    assert result.detection_latencies_seconds == [1.0, 2.0]
    assert result.mean_detection_latency_seconds == pytest.approx(1.5)


def test_unmatched_events_do_not_create_latency():
    truth = [
        event(100, 160),
    ]

    predictions = [
        event(500, 550),
    ]

    result = evaluate_events(
        ground_truth=truth,
        predictions=predictions,
        fps=5.0,
    )

    assert result.detection_latencies_seconds == []
    assert result.mean_detection_latency_seconds is None


def test_invalid_fps_is_rejected():
    with pytest.raises(ValueError):
        evaluate_events(
            ground_truth=[],
            predictions=[],
            fps=0,
        )
