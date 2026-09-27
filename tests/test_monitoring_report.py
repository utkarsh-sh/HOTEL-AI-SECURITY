import json

from database.monitoring_database import MonitoringDatabase
from monitoring.report import generate_monitoring_report


def sample_metrics(
    timestamp="2026-09-26T21:00:00+00:00",
):
    return {
        "timestamp": timestamp,
        "cpu": {
            "utilization_percent": 45.0,
        },
        "memory": {
            "utilization_percent": 60.0,
        },
        "disk": {
            "utilization_percent": 70.0,
        },
        "network": {
            "bytes_sent": 1000,
            "bytes_received": 2000,
        },
        "gpu": {
            "available": True,
            "gpus": [
                {
                    "name": "Test GPU",
                    "utilization_percent": 25.0,
                    "memory_used_mb": 500.0,
                    "memory_total_mb": 4096.0,
                }
            ],
        },
    }


def test_generate_monitoring_report(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    database.record_system_metrics(
        sample_metrics()
    )

    report_path = tmp_path / "monitoring_report.json"

    report = generate_monitoring_report(
        report_path,
        database,
    )

    assert report["report_type"] == "system_monitoring"
    assert report["monitoring_version"] == "1.0"
    assert report["sample_count"] == 1

    assert (
        report["monitoring_status"]["ok_sample_count"]
        == 1
    )
    assert (
        report["monitoring_status"]["alert_sample_count"]
        == 0
    )

    assert report["resource_utilization"][
        "cpu_percent"
    ] == [45.0]

    assert report["resource_utilization"][
        "memory_percent"
    ] == [60.0]

    assert report["resource_utilization"][
        "disk_percent"
    ] == [70.0]

    assert report["network"]["bytes_sent"] == [1000]
    assert report["network"]["bytes_received"] == [2000]

    assert (
        report["gpu"]["available_sample_count"]
        == 1
    )

    assert report["alerts"]["count"] == 0

    assert report_path.exists()

    saved = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    assert saved["sample_count"] == 1

    database.close()


def test_monitoring_report_includes_alerts(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    evaluation = {
        "status": "ALERT",
        "checks": {
            "cpu": {
                "value": 95.0,
                "threshold": 90.0,
            },
            "memory": {
                "value": 60.0,
                "threshold": 90.0,
            },
            "disk": {
                "value": 70.0,
                "threshold": 90.0,
            },
        },
        "alerts": [
            {
                "resource": "cpu",
                "value": 95.0,
                "threshold": 90.0,
            }
        ],
    }

    database.record_system_metrics(
        sample_metrics(),
        evaluation,
    )

    report = generate_monitoring_report(
        tmp_path / "alert_report.json",
        database,
    )

    assert report["sample_count"] == 1
    assert (
        report["monitoring_status"]["alert_sample_count"]
        == 1
    )
    assert report["alerts"]["count"] == 1

    alert_sample = report["alerts"]["samples"][0]

    assert alert_sample["alerts"] == [
        {
            "resource": "cpu",
            "value": 95.0,
            "threshold": 90.0,
        }
    ]

    assert alert_sample["threshold_checks"]["cpu"] == {
        "value": 95.0,
        "threshold": 90.0,
    }

    database.close()


def test_monitoring_report_respects_time_window(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    database.record_system_metrics(
        sample_metrics(
            "2026-09-26T21:00:00+00:00"
        )
    )

    database.record_system_metrics(
        sample_metrics(
            "2026-09-26T22:00:00+00:00"
        )
    )

    report = generate_monitoring_report(
        tmp_path / "window_report.json",
        database,
        start_time="2026-09-26T21:30:00+00:00",
        end_time="2026-09-26T22:30:00+00:00",
    )

    assert report["sample_count"] == 1
    assert report["samples"][0]["timestamp"] == (
        "2026-09-26T22:00:00+00:00"
    )

    database.close()


def test_monitoring_report_handles_empty_window(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    report = generate_monitoring_report(
        tmp_path / "empty_report.json",
        database,
        start_time="2026-09-26T21:00:00+00:00",
        end_time="2026-09-26T22:00:00+00:00",
    )

    assert report["sample_count"] == 0

    assert (
        report["monitoring_status"]["ok_sample_count"]
        == 0
    )
    assert (
        report["monitoring_status"]["alert_sample_count"]
        == 0
    )

    assert report["alerts"]["count"] == 0

    assert (
        report["gpu"]["available_sample_count"]
        == 0
    )
    assert (
        report["gpu"]["unavailable_sample_count"]
        == 0
    )

    assert report["resource_utilization"][
        "cpu_percent"
    ] == []

    database.close()


def test_monitoring_report_handles_unavailable_gpu(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    metrics = sample_metrics()

    metrics["gpu"] = {
        "available": False,
        "gpus": [],
    }

    database.record_system_metrics(metrics)

    report = generate_monitoring_report(
        tmp_path / "gpu_report.json",
        database,
    )

    assert (
        report["gpu"]["available_sample_count"]
        == 0
    )
    assert (
        report["gpu"]["unavailable_sample_count"]
        == 1
    )

    assert report["gpu"]["samples"][0] == {
        "timestamp": "2026-09-26T21:00:00+00:00",
        "available": False,
        "gpus": [],
    }

    database.close()


def test_monitoring_report_rejects_missing_database():
    try:
        generate_monitoring_report(
            "report.json",
            None,
        )
    except ValueError as error:
        assert str(error) == (
            "monitoring_database is required"
        )
        return

    raise AssertionError(
        "Expected ValueError for missing database"
    )