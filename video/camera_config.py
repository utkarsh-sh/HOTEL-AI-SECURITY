import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReconnectConfig:
    max_attempts: int = 3
    delay_seconds: float = 1.0


@dataclass(frozen=True)
class CameraConfig:
    camera_id: str
    name: str
    location: str
    source_type: str
    source: str
    ai_fps: float
    reconnect: ReconnectConfig


def _camera_config_from_mapping(camera: dict) -> CameraConfig:
    required_fields = [
        "camera_id",
        "name",
        "location",
        "source_type",
        "source",
        "ai_fps",
    ]

    for field in required_fields:
        if field not in camera:
            raise ValueError(
                f"Camera is missing '{field}'."
            )

    ai_fps = float(camera["ai_fps"])
    if ai_fps <= 0:
        raise ValueError(
            f"Camera '{camera['camera_id']}' "
            "ai_fps must be greater than 0."
        )

    reconnect_data = camera.get(
        "reconnect",
        {},
    )

    if not isinstance(reconnect_data, dict):
        raise ValueError(
            f"Camera '{camera['camera_id']}' "
            "'reconnect' must be an object."
        )

    max_attempts = int(
        reconnect_data.get(
            "max_attempts",
            3,
        )
    )
    delay_seconds = float(
        reconnect_data.get(
            "delay_seconds",
            1.0,
        )
    )

    if max_attempts < 0:
        raise ValueError(
            f"Camera '{camera['camera_id']}' "
            "max_attempts must be >= 0."
        )

    if delay_seconds < 0:
        raise ValueError(
            f"Camera '{camera['camera_id']}' "
            "delay_seconds must be >= 0."
        )

    return CameraConfig(
        camera_id=str(camera["camera_id"]),
        name=str(camera["name"]),
        location=str(camera["location"]),
        source_type=str(camera["source_type"]),
        source=str(camera["source"]),
        ai_fps=ai_fps,
        reconnect=ReconnectConfig(
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
        ),
    )


def load_camera_configs(path: str) -> list[CameraConfig]:
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Camera configuration not found: {config_path}"
        )

    with config_path.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            "Camera configuration root must be an object."
        )

    cameras = data.get("cameras")
    if not isinstance(cameras, list):
        raise ValueError(
            "'cameras' must be a list."
        )

    configs = []

    for index, camera in enumerate(cameras):
        if not isinstance(camera, dict):
            raise ValueError(
                f"Camera at index {index} must be an object."
            )

        try:
            configs.append(
                _camera_config_from_mapping(camera)
            )
        except ValueError as error:
            raise ValueError(
                f"Camera at index {index}: {error}"
            ) from error

    return configs


def load_camera_configs_from_database(database) -> list[CameraConfig]:
    """
    Convert persisted camera configuration rows into the immutable
    CameraConfig objects consumed by CameraManager.
    """
    configs = []

    for camera in database.get_all_cameras():
        source = str(
            camera["source"] or ""
        ).strip()

        if not source:
            raise ValueError(
                f"Camera '{camera['camera_id']}' "
                "has no configured source. Configure it through "
                "the admin camera API before starting the runner."
            )

        configs.append(
            _camera_config_from_mapping(
                {
                    "camera_id": camera["camera_id"],
                    "name": camera["name"],
                    "location": camera["location"],
                    "source_type": camera["source_type"],
                    "source": source,
                    "ai_fps": camera["ai_fps"],
                    "reconnect": {
                        "max_attempts": (
                            camera["reconnect_max_attempts"]
                        ),
                        "delay_seconds": (
                            camera["reconnect_delay_seconds"]
                        ),
                    },
                }
            )
        )

    return configs
