import json

from database.monitoring_database import MonitoringDatabase


def sample_metrics():
    return {
        "timestamp": "2026-09-26T21:00:00+00:00",
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


def test_record_and_read_system_metrics(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    database.record_system_metrics(
        sample_metrics()
    )

    rows = database.get_system_samples()

    assert len(rows) == 1

    row = rows[0]

    assert row["timestamp"] == "2026-09-26T21:00:00+00:00"
    assert row["cpu_utilization_percent"] == 45.0
    assert row["memory_utilization_percent"] == 60.0
    assert row["disk_utilization_percent"] == 70.0
    assert row["network_bytes_sent"] == 1000
    assert row["network_bytes_received"] == 2000
    assert row["gpu_available"] == 1

    gpu_metrics = json.loads(
        row["gpu_metrics_json"]
    )

    assert gpu_metrics[0]["name"] == "Test GPU"

    assert row["monitoring_status"] == "OK"
    assert json.loads(
        row["threshold_checks_json"]
    ) == {}
    assert json.loads(
        row["alerts_json"]
    ) == []

    database.close()


def test_alert_evaluation_is_persisted(tmp_path):
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

    row = database.get_system_samples()[0]

    assert row["monitoring_status"] == "ALERT"
    assert json.loads(
        row["threshold_checks_json"]
    ) == evaluation["checks"]
    assert json.loads(
        row["alerts_json"]
    ) == evaluation["alerts"]

    database.close()


def test_ok_evaluation_is_persisted(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    evaluation = {
        "status": "OK",
        "checks": {
            "cpu": {
                "value": 45.0,
                "threshold": 90.0,
            }
        },
        "alerts": [],
    }

    database.record_system_metrics(
        sample_metrics(),
        evaluation,
    )

    row = database.get_system_samples()[0]

    assert row["monitoring_status"] == "OK"
    assert json.loads(
        row["threshold_checks_json"]
    ) == evaluation["checks"]
    assert json.loads(
        row["alerts_json"]
    ) == []

    database.close()


def test_time_window_filtering(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    first = sample_metrics()

    second = sample_metrics()
    second["timestamp"] = (
        "2026-09-26T22:00:00+00:00"
    )

    database.record_system_metrics(first)
    database.record_system_metrics(second)

    rows = database.get_system_samples(
        start_time="2026-09-26T21:30:00+00:00",
        end_time="2026-09-26T22:30:00+00:00",
    )

    assert len(rows) == 1
    assert rows[0]["timestamp"] == (
        "2026-09-26T22:00:00+00:00"
    )

    database.close()


def test_gpu_unavailable_is_persisted(tmp_path):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    metrics = sample_metrics()
    metrics["gpu"] = {
        "available": False,
        "gpus": [],
    }

    database.record_system_metrics(metrics)

    row = database.get_system_samples()[0]

    assert row["gpu_available"] == 0
    assert json.loads(
        row["gpu_metrics_json"]
    ) == []

    database.close()
