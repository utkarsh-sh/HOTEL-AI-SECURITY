import json

import pytest

from video.camera_config import load_camera_configs


def test_load_camera_config(tmp_path):
    config_path = tmp_path / "cameras.json"

    config_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "camera_id": "CAM-001",
                        "name": "Lobby",
                        "location": "Main Lobby",
                        "source_type": "rtsp",
                        "source": "rtsp://camera/stream",
                        "ai_fps": 5,
                        "reconnect": {
                            "max_attempts": 4,
                            "delay_seconds": 2,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    configs = load_camera_configs(str(config_path))

    assert len(configs) == 1

    camera = configs[0]

    assert camera.camera_id == "CAM-001"
    assert camera.name == "Lobby"
    assert camera.location == "Main Lobby"
    assert camera.source_type == "rtsp"
    assert camera.source == "rtsp://camera/stream"
    assert camera.ai_fps == 5
    assert camera.reconnect.max_attempts == 4
    assert camera.reconnect.delay_seconds == 2


def test_missing_config_file():
    with pytest.raises(FileNotFoundError):
        load_camera_configs(
            "does-not-exist.json"
        )


def test_invalid_camera_list(tmp_path):
    config_path = tmp_path / "cameras.json"

    config_path.write_text(
        json.dumps({"cameras": {}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_camera_configs(str(config_path))


def test_missing_required_field(tmp_path):
    config_path = tmp_path / "cameras.json"

    config_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "camera_id": "CAM-001"
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_camera_configs(str(config_path))


def test_invalid_ai_fps(tmp_path):
    config_path = tmp_path / "cameras.json"

    config_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "camera_id": "CAM-001",
                        "name": "Lobby",
                        "location": "Main Lobby",
                        "source_type": "file",
                        "source": "test.mp4",
                        "ai_fps": 0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_camera_configs(str(config_path))


def test_default_reconnect_settings(tmp_path):
    config_path = tmp_path / "cameras.json"

    config_path.write_text(
        json.dumps(
            {
                "cameras": [
                    {
                        "camera_id": "CAM-001",
                        "name": "Lobby",
                        "location": "Main Lobby",
                        "source_type": "file",
                        "source": "test.mp4",
                        "ai_fps": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    configs = load_camera_configs(str(config_path))

    assert configs[0].reconnect.max_attempts == 3
    assert configs[0].reconnect.delay_seconds == 1.0
