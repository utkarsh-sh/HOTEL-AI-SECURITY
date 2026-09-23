import pytest

from evaluation.metrics import (
    calculate_evaluation_metrics,
)


def test_metrics_calculate_basic_values():
    artifact = {
        "video": "test.mp4",
        "camera_id": "CAM-001",
        "source_fps": 25.0,
        "ai_fps": 5.0,
        "model_version": "prototype-v1",
        "result": {
            "total_frames": 500,
            "ai_frames": 100,
            "predictions": [
                {
                    "event_type": "INTRUSION",
                    "zone_id": "restricted_01",
                    "start_frame": 10,
                    "end_frame": 10,
                },
                {
                    "event_type": "INTRUSION",
                    "zone_id": "restricted_01",
                    "start_frame": 50,
                    "end_frame": 50,
                },
            ],
        },
    }

    metrics = calculate_evaluation_metrics(artifact)

    assert metrics["total_frames"] == 500
    assert metrics["ai_frames"] == 100
    assert metrics["ai_frame_coverage_percent"] == 20.0
    assert metrics["prediction_count"] == 2
    assert metrics["predictions_per_ai_frame"] == 0.02


def test_metrics_calculate_prediction_timestamps():
    artifact = {
        "video": "test.mp4",
        "camera_id": "CAM-001",
        "source_fps": 25.0,
        "ai_fps": 5.0,
        "model_version": "prototype-v1",
        "result": {
            "total_frames": 250,
            "ai_frames": 50,
            "predictions": [
                {
                    "event_type": "INTRUSION",
                    "zone_id": "restricted_01",
                    "start_frame": 25,
                    "end_frame": 25,
                },
                {
                    "event_type": "INTRUSION",
                    "zone_id": "restricted_01",
                    "start_frame": 100,
                    "end_frame": 100,
                },
            ],
        },
    }

    metrics = calculate_evaluation_metrics(artifact)

    assert metrics["prediction_timestamps_seconds"] == [1.0, 4.0]


def test_metrics_require_independent_ground_truth_for_classification_metrics():
    artifact = {
        "video": "test.mp4",
        "camera_id": "CAM-001",
        "source_fps": 25.0,
        "ai_fps": 5.0,
        "model_version": "prototype-v1",
        "result": {
            "total_frames": 100,
            "ai_frames": 20,
            "predictions": [],
        },
    }

    metrics = calculate_evaluation_metrics(artifact)

    assert metrics["classification_metrics_available"] is False
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["f1"] is None
    assert metrics["false_positives"] is None
    assert metrics["false_negatives"] is None


def test_metrics_reject_invalid_frame_counts():
    artifact = {
        "video": "test.mp4",
        "camera_id": "CAM-001",
        "source_fps": 25.0,
        "ai_fps": 5.0,
        "model_version": "prototype-v1",
        "result": {
            "total_frames": 100,
            "ai_frames": 101,
            "predictions": [],
        },
    }

    with pytest.raises(ValueError):
        calculate_evaluation_metrics(artifact)
