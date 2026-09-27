import json

import pytest

from database.monitoring_config import (
    MonitoringConfiguration,
    MonitoringConfigurationError,
)


def write_config(path, configuration):
    path.write_text(
        json.dumps(configuration),
        encoding="utf-8",
    )


def valid_configuration():
    return {
        "resource_thresholds": {
            "cpu_utilization_percent": 90.0,
            "memory_utilization_percent": 90.0,
            "disk_utilization_percent": 90.0,
        }
    }


def test_valid_configuration_loads():
    configuration = MonitoringConfiguration()

    assert configuration.cpu_threshold == 90.0
    assert configuration.memory_threshold == 90.0
    assert configuration.disk_threshold == 90.0


def test_missing_configuration_fails(tmp_path):
    with pytest.raises(
        MonitoringConfigurationError,
        match="configuration not found",
    ):
        MonitoringConfiguration(
            tmp_path / "missing.json"
        )


def test_missing_resource_thresholds_fails(tmp_path):
    path = tmp_path / "monitoring.json"
    write_config(path, {})

    with pytest.raises(
        MonitoringConfigurationError,
        match="resource_thresholds",
    ):
        MonitoringConfiguration(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu_utilization_percent", "90"),
        ("memory_utilization_percent", None),
        ("disk_utilization_percent", []),
    ],
)
def test_non_numeric_threshold_fails(tmp_path, field, value):
    configuration = valid_configuration()
    configuration["resource_thresholds"][field] = value

    path = tmp_path / "monitoring.json"
    write_config(path, configuration)

    with pytest.raises(
        MonitoringConfigurationError,
        match="must be a number",
    ):
        MonitoringConfiguration(path)


@pytest.mark.parametrize(
    "field",
    [
        "cpu_utilization_percent",
        "memory_utilization_percent",
        "disk_utilization_percent",
    ],
)
def test_boolean_threshold_fails(tmp_path, field):
    configuration = valid_configuration()
    configuration["resource_thresholds"][field] = True

    path = tmp_path / "monitoring.json"
    write_config(path, configuration)

    with pytest.raises(
        MonitoringConfigurationError,
        match="must be a number",
    ):
        MonitoringConfiguration(path)


@pytest.mark.parametrize(
    "value",
    [-0.1, 100.1, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_threshold_value_fails(tmp_path, value):
    configuration = valid_configuration()
    configuration["resource_thresholds"][
        "cpu_utilization_percent"
    ] = value

    path = tmp_path / "monitoring.json"
    write_config(path, configuration)

    with pytest.raises(MonitoringConfigurationError):
        MonitoringConfiguration(path)


def test_alternate_configuration_path(tmp_path):
    path = tmp_path / "monitoring.json"
    configuration = valid_configuration()
    configuration["resource_thresholds"][
        "cpu_utilization_percent"
    ] = 75

    write_config(path, configuration)

    loaded = MonitoringConfiguration(path)

    assert loaded.cpu_threshold == 75.0
    assert loaded.memory_threshold == 90.0
    assert loaded.disk_threshold == 90.0
