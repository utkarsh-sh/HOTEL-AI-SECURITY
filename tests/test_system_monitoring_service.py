from database.monitoring_config import MonitoringConfiguration
from database.monitoring_database import MonitoringDatabase
from monitoring.system_monitoring_service import (
    SystemMonitoringService,
)


def configuration(tmp_path):
    path = tmp_path / "monitoring.json"
    path.write_text(
        """
        {
            "resource_thresholds": {
                "cpu_utilization_percent": 90.0,
                "memory_utilization_percent": 90.0,
                "disk_utilization_percent": 90.0
            }
        }
        """,
        encoding="utf-8",
    )

    return MonitoringConfiguration(path)


def sample_metrics():
    return {
        "timestamp": "2026-09-26T21:30:00+00:00",
        "cpu": {
            "utilization_percent": 45.0,
            "logical_cpu_count": 12,
        },
        "memory": {
            "utilization_percent": 60.0,
            "total_bytes": 1000,
            "available_bytes": 400,
            "used_bytes": 600,
        },
        "disk": {
            "utilization_percent": 70.0,
            "total_bytes": 2000,
            "free_bytes": 600,
            "used_bytes": 1400,
            "mount": "/",
        },
        "network": {
            "bytes_sent": 1000,
            "bytes_received": 2000,
        },
        "gpu": {
            "available": False,
            "gpus": [],
        },
    }


def test_collect_and_record_persists_and_returns_result(
    tmp_path,
    monkeypatch,
):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    configuration_object = configuration(tmp_path)
    expected_metrics = sample_metrics()

    monkeypatch.setattr(
        "monitoring.system_monitoring_service.collect_system_metrics",
        lambda: expected_metrics,
    )

    service = SystemMonitoringService(
        database,
        configuration_object,
    )

    result = service.collect_and_record()

    assert result["metrics"] == expected_metrics
    assert result["evaluation"]["status"] == "OK"
    assert result["evaluation"]["alerts"] == []

    rows = database.get_system_samples()

    assert len(rows) == 1
    assert rows[0]["timestamp"] == expected_metrics["timestamp"]
    assert rows[0]["monitoring_status"] == "OK"
    assert rows[0]["cpu_utilization_percent"] == 45.0

    database.close()


def test_collect_and_record_persists_alert_result(
    tmp_path,
    monkeypatch,
):
    database = MonitoringDatabase(
        tmp_path / "monitoring.db"
    )

    configuration_object = configuration(tmp_path)
    alert_metrics = sample_metrics()
    alert_metrics["cpu"]["utilization_percent"] = 95.0

    monkeypatch.setattr(
        "monitoring.system_monitoring_service.collect_system_metrics",
        lambda: alert_metrics,
    )

    service = SystemMonitoringService(
        database,
        configuration_object,
    )

    result = service.collect_and_record()

    assert result["evaluation"]["status"] == "ALERT"
    assert result["evaluation"]["alerts"] == [
        {
            "resource": "cpu",
            "value": 95.0,
            "threshold": 90.0,
        }
    ]

    rows = database.get_system_samples()

    assert len(rows) == 1
    assert rows[0]["monitoring_status"] == "ALERT"

    database.close()


def test_service_rejects_invalid_database_dependency(
    tmp_path,
):
    configuration_object = configuration(tmp_path)

    try:
        SystemMonitoringService(
            object(),
            configuration_object,
        )
    except TypeError as error:
        assert "MonitoringDatabase" in str(error)
    else:
        raise AssertionError(
            "Expected TypeError for invalid database dependency"
        )
