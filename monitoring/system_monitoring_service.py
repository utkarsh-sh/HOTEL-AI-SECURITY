from database.monitoring_config import MonitoringConfiguration
from database.monitoring_database import MonitoringDatabase
from monitoring.resource_thresholds import (
    evaluate_resource_thresholds,
)
from monitoring.system_metrics import collect_system_metrics


class SystemMonitoringService:
    """Collect, evaluate, and persist one system monitoring sample."""

    def __init__(
        self,
        monitoring_database,
        configuration=None,
    ):
        if not isinstance(
            monitoring_database,
            MonitoringDatabase,
        ):
            raise TypeError(
                "monitoring_database must be a "
                "MonitoringDatabase instance"
            )

        self.monitoring_database = monitoring_database
        self.configuration = (
            configuration
            if configuration is not None
            else MonitoringConfiguration()
        )

    def collect_and_record(self):
        """Collect one sample, evaluate it, and persist it."""

        metrics = collect_system_metrics()

        evaluation = evaluate_resource_thresholds(
            metrics,
            self.configuration,
        )

        self.monitoring_database.record_system_metrics(
            metrics,
            evaluation,
        )

        return {
            "metrics": metrics,
            "evaluation": evaluation,
        }
