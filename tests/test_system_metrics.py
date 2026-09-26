from datetime import datetime

import monitoring.system_metrics as system_metrics


def test_collect_system_metrics_structure(monkeypatch):
    monkeypatch.setattr(
        system_metrics.psutil,
        "cpu_percent",
        lambda interval: 25.0,
    )
    monkeypatch.setattr(
        system_metrics.psutil,
        "cpu_count",
        lambda logical=True: 12,
    )

    result = system_metrics.collect_system_metrics()

    assert "timestamp" in result
    datetime.fromisoformat(result["timestamp"])

    assert result["cpu"]["utilization_percent"] == 25.0
    assert result["cpu"]["logical_cpu_count"] == 12

    assert 0 <= result["memory"]["utilization_percent"] <= 100
    assert result["memory"]["total_bytes"] > 0

    assert 0 <= result["disk"]["utilization_percent"] <= 100
    assert result["disk"]["total_bytes"] > 0

    assert result["network"]["bytes_sent"] >= 0
    assert result["network"]["bytes_received"] >= 0

    assert "available" in result["gpu"]
    assert isinstance(result["gpu"]["available"], bool)
    assert isinstance(result["gpu"]["gpus"], list)


def test_gpu_metrics_unavailable(monkeypatch):
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi not found")

    monkeypatch.setattr(
        system_metrics.subprocess,
        "run",
        raise_file_not_found,
    )

    result = system_metrics._get_gpu_metrics()

    assert result == {
        "available": False,
        "gpus": [],
    }


def test_gpu_metrics_parses_valid_nvidia_smi_output(monkeypatch):
    class FakeCompletedProcess:
        stdout = (
            "NVIDIA GeForce RTX 2050, 37, 512, 4096\n"
        )

    monkeypatch.setattr(
        system_metrics.subprocess,
        "run",
        lambda *args, **kwargs: FakeCompletedProcess(),
    )

    result = system_metrics._get_gpu_metrics()

    assert result["available"] is True
    assert result["gpus"] == [
        {
            "name": "NVIDIA GeForce RTX 2050",
            "utilization_percent": 37.0,
            "memory_used_mb": 512.0,
            "memory_total_mb": 4096.0,
        }
    ]


def test_gpu_metrics_ignores_malformed_rows(monkeypatch):
    class FakeCompletedProcess:
        stdout = (
            "NVIDIA GeForce RTX 2050, 37, 512, 4096\n"
            "malformed,row\n"
            "NVIDIA GeForce RTX 2050, invalid, 512, 4096\n"
        )

    monkeypatch.setattr(
        system_metrics.subprocess,
        "run",
        lambda *args, **kwargs: FakeCompletedProcess(),
    )

    result = system_metrics._get_gpu_metrics()

    assert result["available"] is True
    assert len(result["gpus"]) == 1
