from database.monitoring_config import MonitoringConfiguration


def evaluate_resource_thresholds(
    metrics,
    configuration,
):
    """Evaluate collected resource metrics against configured thresholds."""

    checks = {
        "cpu": {
            "value": metrics["cpu"]["utilization_percent"],
            "threshold": configuration.cpu_threshold,
        },
        "memory": {
            "value": metrics["memory"]["utilization_percent"],
            "threshold": configuration.memory_threshold,
        },
        "disk": {
            "value": metrics["disk"]["utilization_percent"],
            "threshold": configuration.disk_threshold,
        },
    }

    alerts = []

    for resource, check in checks.items():
        if check["value"] >= check["threshold"]:
            alerts.append(
                {
                    "resource": resource,
                    "value": check["value"],
                    "threshold": check["threshold"],
                }
            )

    return {
        "status": "ALERT" if alerts else "OK",
        "alerts": alerts,
        "checks": checks,
    }
