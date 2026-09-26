import pytest

from evaluation.latency import (
    LatencyMeasurement,
    LatencySample,
    calculate_latency_metrics,
    percentile,
)


def test_percentile_empty_values():
    assert percentile([], 95) is None


def test_percentile_single_value():
    assert percentile([42.0], 95) == 42.0


def test_percentile_interpolates():
    assert percentile([10.0, 20.0, 30.0, 40.0], 95) == 38.5


def test_percentile_rejects_invalid_value():
    with pytest.raises(
        ValueError,
        match="percentile_value must be between 0 and 100.",
    ):
        percentile([10.0], 101)


def test_latency_metrics_empty():
    metrics = calculate_latency_metrics([])

    assert metrics.count == 0
    assert metrics.mean_ms is None
    assert metrics.median_ms is None
    assert metrics.p95_ms is None
    assert metrics.max_ms is None


def test_latency_measurement_records_stage_and_end_to_end_latency():
    measurement = LatencyMeasurement()

    sample = measurement.record(
        event_type="INTRUSION",
        frame_received_at=10.0,
        ai_completed_at=10.2,
        persisted_at=10.25,
        notification_queued_at=10.30,
    )

    assert sample.event_type == "INTRUSION"
    assert sample.frame_to_ai_ms == pytest.approx(200.0)
    assert sample.ai_to_persistence_ms == pytest.approx(50.0)
    assert sample.persistence_to_notification_ms == pytest.approx(50.0)
    assert sample.end_to_end_ms == pytest.approx(300.0)


def test_latency_metrics_group_by_event_type():
    measurement = LatencyMeasurement()

    measurement.record(
        event_type="INTRUSION",
        frame_received_at=0.0,
        ai_completed_at=0.1,
        persisted_at=0.2,
        notification_queued_at=0.3,
    )

    measurement.record(
        event_type="INTRUSION",
        frame_received_at=1.0,
        ai_completed_at=1.1,
        persisted_at=1.2,
        notification_queued_at=1.5,
    )

    measurement.record(
        event_type="FALL",
        frame_received_at=2.0,
        ai_completed_at=2.2,
        persisted_at=2.3,
        notification_queued_at=2.7,
    )

    metrics = measurement.metrics_by_event_type()

    assert set(metrics) == {"FALL", "INTRUSION"}

    assert metrics["INTRUSION"].count == 2
    assert metrics["INTRUSION"].mean_ms == pytest.approx(400.0)
    assert metrics["INTRUSION"].median_ms == pytest.approx(400.0)
    assert metrics["INTRUSION"].p95_ms == pytest.approx(490.0)
    assert metrics["INTRUSION"].max_ms == pytest.approx(500.0)

    assert metrics["FALL"].count == 1
    assert metrics["FALL"].mean_ms == pytest.approx(700.0)
    assert metrics["FALL"].median_ms == pytest.approx(700.0)
    assert metrics["FALL"].p95_ms == pytest.approx(700.0)
    assert metrics["FALL"].max_ms == pytest.approx(700.0)


def test_latency_measurement_overall_metrics():
    measurement = LatencyMeasurement()

    measurement.record(
        event_type="INTRUSION",
        frame_received_at=0.0,
        ai_completed_at=0.1,
        persisted_at=0.2,
        notification_queued_at=0.3,
    )

    measurement.record(
        event_type="FALL",
        frame_received_at=1.0,
        ai_completed_at=1.1,
        persisted_at=1.2,
        notification_queued_at=1.7,
    )

    metrics = measurement.overall_metrics()

    assert metrics.count == 2
    assert metrics.mean_ms == pytest.approx(500.0)
    assert metrics.median_ms == pytest.approx(500.0)
    assert metrics.p95_ms == pytest.approx(680.0)
    assert metrics.max_ms == pytest.approx(700.0)
