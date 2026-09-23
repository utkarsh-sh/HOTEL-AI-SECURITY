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
