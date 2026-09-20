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
                    f"Camera at index {index} is missing "
                    f"'{field}'."
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

        configs.append(
            CameraConfig(
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
        )

    return configs
