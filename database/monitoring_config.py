import json
import math
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("configs/monitoring.json")


class MonitoringConfigurationError(ValueError):
    """Raised when monitoring configuration is invalid."""


class MonitoringConfiguration:
    """Validated configuration for system resource monitoring."""

    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.cpu_threshold = None
        self.memory_threshold = None
        self.disk_threshold = None

        self._load_configuration()

    def _load_configuration(self):
        if not self.config_path.exists():
            raise MonitoringConfigurationError(
                f"Monitoring configuration not found: "
                f"{self.config_path}"
            )

        try:
            with self.config_path.open(
                "r",
                encoding="utf-8-sig",
            ) as file:
                configuration = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise MonitoringConfigurationError(
                f"Invalid monitoring configuration: {error}"
            ) from error

        if not isinstance(configuration, dict):
            raise MonitoringConfigurationError(
                "Monitoring configuration must be a JSON object."
            )

        resource_thresholds = configuration.get(
            "resource_thresholds"
        )

        if not isinstance(resource_thresholds, dict):
            raise MonitoringConfigurationError(
                "resource_thresholds must be a JSON object."
            )

        cpu_threshold = resource_thresholds.get(
            "cpu_utilization_percent"
        )
        memory_threshold = resource_thresholds.get(
            "memory_utilization_percent"
        )
        disk_threshold = resource_thresholds.get(
            "disk_utilization_percent"
        )

        self._validate_threshold(
            "cpu_utilization_percent",
            cpu_threshold,
        )
        self._validate_threshold(
            "memory_utilization_percent",
            memory_threshold,
        )
        self._validate_threshold(
            "disk_utilization_percent",
            disk_threshold,
        )

        self.cpu_threshold = float(cpu_threshold)
        self.memory_threshold = float(memory_threshold)
        self.disk_threshold = float(disk_threshold)

    @staticmethod
    def _validate_threshold(name, value):
        if isinstance(value, bool):
            raise MonitoringConfigurationError(
                f"{name} must be a number between 0 and 100."
            )

        if not isinstance(value, (int, float)):
            raise MonitoringConfigurationError(
                f"{name} must be a number between 0 and 100."
            )

        if not math.isfinite(value):
            raise MonitoringConfigurationError(
                f"{name} must be a finite number between 0 and 100."
            )

        if value < 0 or value > 100:
            raise MonitoringConfigurationError(
                f"{name} must be a number between 0 and 100."
            )
