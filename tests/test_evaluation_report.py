import pytest
from pathlib import Path
import json

from evaluation.report import generate_evaluation_report


def test_generate_evaluation_report(tmp_path):
    artifact_path = tmp_path / "evaluation.json"
    report_path = tmp_path / "report.json"

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

    artifact_path.write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )

    report = generate_evaluation_report(
        artifact_path,
        report_path,
    )

    assert report["camera_id"] == "CAM-001"
    assert report["prediction_count"] == 2
    assert report["ai_frames"] == 100
    assert report["classification_metrics_available"] is False

    assert report_path.exists()

    saved = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    assert saved["prediction_count"] == 2


def test_generate_report_rejects_missing_artifact(tmp_path):
    artifact_path = tmp_path / "missing.json"
    report_path = tmp_path / "report.json"

    try:
        generate_evaluation_report(
            artifact_path,
            report_path,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for missing artifact"
    )


def test_generate_evaluation_report_with_ground_truth(tmp_path):
    artifact_path = tmp_path / "evaluation_CAM-001.json"
    ground_truth_path = tmp_path / "ground_truth_ranges.json"
    report_path = tmp_path / "test_evaluation_report_with_ground_truth.json"

    artifact = {
        "video": "01_person_tracking_intrusion.mp4",
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
                    "start_frame": 20,
                    "end_frame": 30,
                },
                {
                    "event_type": "INTRUSION",
                    "zone_id": "restricted_01",
                    "start_frame": 40,
                    "end_frame": 50,
                },
                {
                    "event_type": "INTRUSION",
                    "zone_id": "restricted_01",
                    "start_frame": 70,
                    "end_frame": 80,
                },
            ],
        },
    }

    ground_truth = {
        "video": "01_person_tracking_intrusion.mp4",
        "camera_id": "CAM-001",
        "events": [
            {
                "event_type": "INTRUSION",
                "zone_id": "restricted_01",
                "start_frame": 10,
                "end_frame": 20,
            }
        ],
    }

    artifact_path.write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )
    ground_truth_path.write_text(
        json.dumps(ground_truth),
        encoding="utf-8",
    )

    report = generate_evaluation_report(
        artifact_path,
        report_path,
        ground_truth_path=ground_truth_path,
    )

    assert report["ground_truth_available"] is True
    assert report["ground_truth_event_count"] == 1

    assert report["true_positives"] == 1
    assert report["false_positives"] == 2
    assert report["false_negatives"] == 0

    assert report["precision"] == 0.333333
    assert report["recall"] == 1.0
    assert report["f1"] == 0.5

    assert report["metrics_by_event_type"]["INTRUSION"] == {
        "true_positives": 1,
        "false_positives": 2,
        "false_negatives": 0,
        "precision": 0.333333,
        "recall": 1.0,
        "f1": 0.5,
    }

    assert report["detection_latencies_seconds"] == [0.4]
    assert report["mean_detection_latency_seconds"] == 0.4

    assert report["false_positive_rate"] is None
    assert report["false_positive_rate_available"] is False

    assert report_path.exists()
    report_path.unlink()


def test_generate_evaluation_report_rejects_mismatched_ground_truth(
    tmp_path,
):
    artifact_path = tmp_path / "evaluation.json"
    ground_truth_path = tmp_path / "ground_truth.json"
    report_path = tmp_path / "report.json"

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

    ground_truth = {
        "video": "different.mp4",
        "camera_id": "CAM-001",
        "events": [],
    }

    artifact_path.write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )
    ground_truth_path.write_text(
        json.dumps(ground_truth),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="ground truth video does not match",
    ):
        generate_evaluation_report(
            artifact_path,
            report_path,
            ground_truth_path=ground_truth_path,
        )
