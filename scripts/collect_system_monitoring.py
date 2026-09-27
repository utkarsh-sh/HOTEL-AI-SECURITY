import json

from database.monitoring_config import MonitoringConfiguration
from database.monitoring_database import MonitoringDatabase
from monitoring.system_monitoring_service import (
    SystemMonitoringService,
)


def main():
    database = MonitoringDatabase()
    configuration = MonitoringConfiguration()

    service = SystemMonitoringService(
        database,
        configuration,
    )

    try:
        result = service.collect_and_record()
    finally:
        database.close()

    metrics = result["metrics"]
    evaluation = result["evaluation"]

    print(
        json.dumps(
            {
                "timestamp": metrics["timestamp"],
                "status": evaluation["status"],
                "cpu_percent": metrics["cpu"][
                    "utilization_percent"
                ],
                "memory_percent": metrics["memory"][
                    "utilization_percent"
                ],
                "disk_percent": metrics["disk"][
                    "utilization_percent"
                ],
                "gpu_available": metrics["gpu"][
                    "available"
                ],
                "alerts": evaluation["alerts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
