import json
from pathlib import Path


def _parse_json(value, default):
    if value is None:
        return default

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _round(value):
    if value is None:
        return None
    return round(float(value), 6)


def generate_monitoring_report(
    report_path,
    monitoring_database,
    start_time=None,
    end_time=None,
):
    """
    Generate a JSON report from persisted system monitoring samples.

    The report summarizes recorded resource utilization, configured
    threshold checks, monitoring status, GPU availability, network
    counters, and resource alerts for the requested time window.
    """

    report_path = Path(report_path)

    if monitoring_database is None:
        raise ValueError(
            "monitoring_database is required"
        )

    rows = monitoring_database.get_system_samples(
        start_time=start_time,
        end_time=end_time,
    )

    samples = []

    for row in rows:
        samples.append(
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "cpu_utilization_percent": row[
                    "cpu_utilization_percent"
                ],
                "memory_utilization_percent": row[
                    "memory_utilization_percent"
                ],
                "disk_utilization_percent": row[
                    "disk_utilization_percent"
                ],
                "network_bytes_sent": row[
                    "network_bytes_sent"
                ],
                "network_bytes_received": row[
                    "network_bytes_received"
                ],
                "gpu_available": bool(
                    row["gpu_available"]
                ),
                "gpu_metrics": _parse_json(
                    row["gpu_metrics_json"],
                    [],
                ),
                "monitoring_status": row[
                    "monitoring_status"
                ],
                "threshold_checks": _parse_json(
                    row["threshold_checks_json"],
                    {},
                ),
                "alerts": _parse_json(
                    row["alerts_json"],
                    [],
                ),
            }
        )

    alert_count = sum(
        len(sample["alerts"])
        for sample in samples
    )

    alert_samples = [
        sample
        for sample in samples
        if sample["monitoring_status"] == "ALERT"
    ]

    gpu_available_samples = sum(
        1
        for sample in samples
        if sample["gpu_available"]
    )

    report = {
        "report_type": "system_monitoring",
        "monitoring_version": "1.0",
        "period": {
            "start_time": start_time,
            "end_time": end_time,
        },
        "sample_count": len(samples),
        "monitoring_status": {
            "alert_sample_count": len(alert_samples),
            "ok_sample_count": sum(
                1
                for sample in samples
                if sample["monitoring_status"] == "OK"
            ),
        },
        "resource_utilization": {
            "cpu_percent": [
                _round(
                    sample["cpu_utilization_percent"]
                )
                for sample in samples
            ],
            "memory_percent": [
                _round(
                    sample["memory_utilization_percent"]
                )
                for sample in samples
            ],
            "disk_percent": [
                _round(
                    sample["disk_utilization_percent"]
                )
                for sample in samples
            ],
        },
        "network": {
            "bytes_sent": [
                sample["network_bytes_sent"]
                for sample in samples
            ],
            "bytes_received": [
                sample["network_bytes_received"]
                for sample in samples
            ],
        },
        "gpu": {
            "available_sample_count": gpu_available_samples,
            "unavailable_sample_count": (
                len(samples) - gpu_available_samples
            ),
            "samples": [
                {
                    "timestamp": sample["timestamp"],
                    "available": sample["gpu_available"],
                    "gpus": sample["gpu_metrics"],
                }
                for sample in samples
            ],
        },
        "alerts": {
            "count": alert_count,
            "samples": [
                {
                    "id": sample["id"],
                    "timestamp": sample["timestamp"],
                    "alerts": sample["alerts"],
                    "threshold_checks": sample[
                        "threshold_checks"
                    ],
                }
                for sample in alert_samples
            ],
        },
        "samples": samples,
    }

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    return report