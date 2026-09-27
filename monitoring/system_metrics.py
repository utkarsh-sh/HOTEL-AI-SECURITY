from datetime import datetime, timezone
import subprocess

import psutil


def _get_gpu_metrics():
    """Return NVIDIA GPU metrics when nvidia-smi is available."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        OSError,
    ):
        return {
            "available": False,
            "gpus": [],
        }

    gpus = []

    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]

        if len(parts) != 4:
            continue

        name, utilization, memory_used, memory_total = parts

        try:
            gpus.append(
                {
                    "name": name,
                    "utilization_percent": float(utilization),
                    "memory_used_mb": float(memory_used),
                    "memory_total_mb": float(memory_total),
                }
            )
        except ValueError:
            continue

    return {
        "available": bool(gpus),
        "gpus": gpus,
    }


def collect_system_metrics():
    """Collect one point-in-time snapshot of host resource metrics."""
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    network = psutil.net_io_counters()

    gpu = _get_gpu_metrics()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": {
            "utilization_percent": psutil.cpu_percent(interval=0.1),
            "logical_cpu_count": psutil.cpu_count(logical=True),
        },
        "memory": {
            "utilization_percent": memory.percent,
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_bytes": memory.used,
        },
        "disk": {
            "utilization_percent": disk.percent,
            "total_bytes": disk.total,
            "free_bytes": disk.free,
            "used_bytes": disk.used,
            "mount": "/",
        },
        "network": {
            "bytes_sent": network.bytes_sent,
            "bytes_received": network.bytes_recv,
        },
        "gpu": gpu,
    }
