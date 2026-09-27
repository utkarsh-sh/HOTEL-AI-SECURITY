from database.monitoring_config import MonitoringConfiguration
from monitoring.resource_thresholds import (
    evaluate_resource_thresholds,
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


def metrics(cpu=50.0, memory=60.0, disk=70.0):
    return {
        "cpu": {
            "utilization_percent": cpu,
        },
        "memory": {
            "utilization_percent": memory,
        },
        "disk": {
            "utilization_percent": disk,
        },
        "network": {
            "bytes_sent": 100,
            "bytes_received": 200,
        },
        "gpu": {
            "available": False,
            "gpus": [],
        },
    }


def test_all_resources_within_thresholds(tmp_path):
    result = evaluate_resource_thresholds(
        metrics(),
        configuration(tmp_path),
    )

    assert result["status"] == "OK"
    assert result["alerts"] == []
    assert set(result["checks"]) == {
        "cpu",
        "memory",
        "disk",
    }


def test_cpu_threshold_triggers_alert(tmp_path):
    result = evaluate_resource_thresholds(
        metrics(cpu=90.0),
        configuration(tmp_path),
    )

    assert result["status"] == "ALERT"
    assert result["alerts"] == [
        {
            "resource": "cpu",
            "value": 90.0,
            "threshold": 90.0,
        }
    ]


def test_memory_threshold_triggers_alert(tmp_path):
    result = evaluate_resource_thresholds(
        metrics(memory=95.0),
        configuration(tmp_path),
    )

    assert result["status"] == "ALERT"
    assert result["alerts"] == [
        {
            "resource": "memory",
            "value": 95.0,
            "threshold": 90.0,
        }
    ]


def test_disk_threshold_triggers_alert(tmp_path):
    result = evaluate_resource_thresholds(
        metrics(disk=91.0),
        configuration(tmp_path),
    )

    assert result["status"] == "ALERT"
    assert result["alerts"] == [
        {
            "resource": "disk",
            "value": 91.0,
            "threshold": 90.0,
        }
    ]


def test_multiple_resources_can_trigger_alerts(tmp_path):
    result = evaluate_resource_thresholds(
        metrics(cpu=91.0, memory=92.0, disk=93.0),
        configuration(tmp_path),
    )

    assert result["status"] == "ALERT"
    assert result["alerts"] == [
        {
            "resource": "cpu",
            "value": 91.0,
            "threshold": 90.0,
        },
        {
            "resource": "memory",
            "value": 92.0,
            "threshold": 90.0,
        },
        {
            "resource": "disk",
            "value": 93.0,
            "threshold": 90.0,
        },
    ]


def test_gpu_is_not_given_an_invented_threshold(tmp_path):
    result = evaluate_resource_thresholds(
        metrics(),
        configuration(tmp_path),
    )

    assert "gpu" not in result["checks"]
    assert result["alerts"] == []
