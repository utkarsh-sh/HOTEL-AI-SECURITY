import pytest

from prometheus_client.parser import text_string_to_metric_families

from monitoring.prometheus_metrics import PrometheusMetrics


def sample_system_metrics():
    return {
        "cpu": {"utilization_percent": 45.0},
        "memory": {"utilization_percent": 60.0},
        "disk": {"utilization_percent": 70.0},
        "gpu": {
            "available": True,
            "gpus": [
                {
                    "name": "Test GPU",
                    "utilization_percent": 25.0,
                    "memory_used_mb": 100.0,
                    "memory_total_mb": 4000.0,
                }
            ],
        },
    }


def metric_value(output, name, labels=None):
    labels = labels or {}

    for family in text_string_to_metric_families(output):
        for sample in family.samples:
            if sample.name != name:
                continue

            if all(
                sample.labels.get(key) == value
                for key, value in labels.items()
            ):
                return sample.value

    raise AssertionError(
        f"Metric {name!r} with labels {labels!r} was not found"
    )


def test_system_metrics_render():
    exporter = PrometheusMetrics()

    exporter.update_system_metrics(
        sample_system_metrics(),
        {"status": "OK"},
    )

    output = exporter.render().decode("utf-8")

    assert metric_value(
        output,
        "hotel_security_cpu_utilization_percent",
    ) == pytest.approx(45.0)

    assert metric_value(
        output,
        "hotel_security_memory_utilization_percent",
    ) == pytest.approx(60.0)

    assert metric_value(
        output,
        "hotel_security_disk_utilization_percent",
    ) == pytest.approx(70.0)

    assert metric_value(
        output,
        "hotel_security_monitoring_status",
    ) == pytest.approx(1.0)

    assert metric_value(
        output,
        "hotel_security_gpu_utilization_percent",
        {"gpu": "Test GPU"},
    ) == pytest.approx(25.0)

    assert metric_value(
        output,
        "hotel_security_gpu_memory_used_bytes",
        {"gpu": "Test GPU"},
    ) == pytest.approx(104857600.0)

    assert metric_value(
        output,
        "hotel_security_gpu_memory_total_bytes",
        {"gpu": "Test GPU"},
    ) == pytest.approx(4194304000.0)


def test_alert_status_and_camera_metrics():
    exporter = PrometheusMetrics()

    exporter.update_system_metrics(
        sample_system_metrics(),
        {"status": "ALERT"},
    )

    exporter.update_camera_metrics(
        [
            {
                "camera_id": "CAM-001",
                "status": "ONLINE",
                "fps": 25.0,
            },
            {
                "camera_id": "CAM-002",
                "status": "OFFLINE",
                "fps": None,
            },
        ]
    )

    output = exporter.render().decode("utf-8")

    assert metric_value(
        output,
        "hotel_security_monitoring_status",
    ) == pytest.approx(0.0)

    assert metric_value(
        output,
        "hotel_security_camera_status",
        {"camera_id": "CAM-001"},
    ) == pytest.approx(1.0)

    assert metric_value(
        output,
        "hotel_security_camera_status",
        {"camera_id": "CAM-002"},
    ) == pytest.approx(0.0)

    assert metric_value(
        output,
        "hotel_security_camera_fps",
        {"camera_id": "CAM-001"},
    ) == pytest.approx(25.0)

    assert metric_value(
        output,
        "hotel_security_camera_fps",
        {"camera_id": "CAM-002"},
    ) == pytest.approx(0.0)


def test_stale_camera_and_gpu_series_are_removed():
    exporter = PrometheusMetrics()

    exporter.update_system_metrics(
        sample_system_metrics(),
        {"status": "OK"},
    )
    exporter.update_camera_metrics(
        [
            {
                "camera_id": "CAM-001",
                "status": "ONLINE",
                "fps": 25.0,
            }
        ]
    )

    exporter.update_system_metrics(
        {
            "cpu": {"utilization_percent": 50.0},
            "memory": {"utilization_percent": 65.0},
            "disk": {"utilization_percent": 72.0},
            "gpu": {"available": False, "gpus": []},
        },
        {"status": "OK"},
    )
    exporter.update_camera_metrics([])

    output = exporter.render().decode("utf-8")

    assert 'gpu="Test GPU"' not in output
    assert 'camera_id="CAM-001"' not in output


def test_invalid_monitoring_status_is_treated_as_alert():
    exporter = PrometheusMetrics()

    exporter.update_system_metrics(
        sample_system_metrics(),
        {"status": "UNKNOWN"},
    )

    output = exporter.render().decode("utf-8")

    assert metric_value(
        output,
        "hotel_security_monitoring_status",
    ) == pytest.approx(0.0)
