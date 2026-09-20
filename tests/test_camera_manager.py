from dataclasses import replace

import pytest

from video.camera_config import (
    CameraConfig,
    ReconnectConfig,
)
from video.camera_manager import CameraManager


class FakeSource:
    def __init__(
        self,
        *,
        open_error=None,
        read_value=None,
        release_error=None,
    ):
        self.open_error = open_error
        self.read_value = read_value
        self.release_error = release_error

        self.open_calls = 0
        self.read_calls = 0
        self.release_calls = 0

    def open(self):
        self.open_calls += 1

        if self.open_error:
            raise RuntimeError(self.open_error)

    def read(self):
        self.read_calls += 1
        return self.read_value

    def release(self):
        self.release_calls += 1

        if self.release_error:
            raise RuntimeError(self.release_error)


def make_config(
    camera_id,
    source="test-source",
    source_type="file",
):
    return CameraConfig(
        camera_id=camera_id,
        name=f"Camera {camera_id}",
        location=f"Location {camera_id}",
        source_type=source_type,
        source=source,
        ai_fps=5.0,
        reconnect=ReconnectConfig(
            max_attempts=2,
            delay_seconds=0.0,
        ),
    )


def build_manager(monkeypatch, configs, sources):
    def fake_create_source(config):
        return sources[config.camera_id]

    monkeypatch.setattr(
        "video.camera_manager.create_video_source",
        fake_create_source,
    )

    return CameraManager(configs)


def test_camera_manager_initializes_all_cameras(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-002"),
        make_config("CAM-003"),
    ]

    sources = {
        "CAM-001": FakeSource(),
        "CAM-002": FakeSource(),
        "CAM-003": FakeSource(),
    }

    manager = build_manager(
        monkeypatch,
        configs,
        sources,
    )

    assert len(manager) == 3
    assert manager.camera_ids() == [
        "CAM-001",
        "CAM-002",
        "CAM-003",
    ]


def test_camera_manager_preserves_configuration_lookup(monkeypatch):
    config = make_config("CAM-001")

    source = FakeSource()

    manager = build_manager(
        monkeypatch,
        [config],
        {"CAM-001": source},
    )

    assert manager.get_config("CAM-001") == config
    assert manager.get_source("CAM-001") is source


def test_open_all_opens_every_camera(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-002"),
    ]

    sources = {
        "CAM-001": FakeSource(),
        "CAM-002": FakeSource(),
    }

    manager = build_manager(
        monkeypatch,
        configs,
        sources,
    )

    opened = manager.open_all()

    assert set(opened) == {
        "CAM-001",
        "CAM-002",
    }

    assert sources["CAM-001"].open_calls == 1
    assert sources["CAM-002"].open_calls == 1
    assert manager.open_errors == {}


def test_open_all_isolates_camera_failure(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-002"),
        make_config("CAM-003"),
    ]

    sources = {
        "CAM-001": FakeSource(),
        "CAM-002": FakeSource(
            open_error="camera unavailable"
        ),
        "CAM-003": FakeSource(),
    }

    manager = build_manager(
        monkeypatch,
        configs,
        sources,
    )

    opened = manager.open_all()

    assert set(opened) == {
        "CAM-001",
        "CAM-003",
    }

    assert sources["CAM-001"].open_calls == 1
    assert sources["CAM-002"].open_calls == 1
    assert sources["CAM-003"].open_calls == 1

    assert manager.open_errors == {
        "CAM-002": "camera unavailable"
    }


def test_read_delegates_to_correct_camera(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-002"),
    ]

    sources = {
        "CAM-001": FakeSource(
            read_value="FRAME-001"
        ),
        "CAM-002": FakeSource(
            read_value="FRAME-002"
        ),
    }

    manager = build_manager(
        monkeypatch,
        configs,
        sources,
    )

    assert manager.read("CAM-001") == "FRAME-001"
    assert manager.read("CAM-002") == "FRAME-002"

    assert sources["CAM-001"].read_calls == 1
    assert sources["CAM-002"].read_calls == 1


def test_open_camera_retries_after_previous_failure(monkeypatch):
    configs = [make_config("CAM-001")]

    source = FakeSource(
        open_error="camera unavailable"
    )

    manager = build_manager(
        monkeypatch,
        configs,
        {"CAM-001": source},
    )

    with pytest.raises(RuntimeError, match="camera unavailable"):
        manager.open_camera("CAM-001")

    assert manager.open_errors["CAM-001"] == "camera unavailable"

    source.open_error = None

    manager.open_camera("CAM-001")

    assert source.open_calls == 2
    assert manager.open_errors == {}


def test_release_all_releases_every_camera(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-002"),
        make_config("CAM-003"),
    ]

    sources = {
        "CAM-001": FakeSource(),
        "CAM-002": FakeSource(),
        "CAM-003": FakeSource(),
    }

    manager = build_manager(
        monkeypatch,
        configs,
        sources,
    )

    errors = manager.release_all()

    assert errors == {}

    assert sources["CAM-001"].release_calls == 1
    assert sources["CAM-002"].release_calls == 1
    assert sources["CAM-003"].release_calls == 1


def test_release_all_isolates_release_failure(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-002"),
    ]

    sources = {
        "CAM-001": FakeSource(
            release_error="release failed"
        ),
        "CAM-002": FakeSource(),
    }

    manager = build_manager(
        monkeypatch,
        configs,
        sources,
    )

    errors = manager.release_all()

    assert errors == {
        "CAM-001": "release failed"
    }

    assert sources["CAM-001"].release_calls == 1
    assert sources["CAM-002"].release_calls == 1


def test_unknown_camera_is_rejected(monkeypatch):
    config = make_config("CAM-001")
    source = FakeSource()

    manager = build_manager(
        monkeypatch,
        [config],
        {"CAM-001": source},
    )

    with pytest.raises(
        KeyError,
        match="Unknown camera ID: CAM-999",
    ):
        manager.read("CAM-999")


def test_duplicate_camera_ids_are_rejected(monkeypatch):
    configs = [
        make_config("CAM-001"),
        make_config("CAM-001"),
    ]

    with pytest.raises(
        ValueError,
        match="Duplicate camera ID: CAM-001",
    ):
        build_manager(
            monkeypatch,
            configs,
            {
                "CAM-001": FakeSource(),
            },
        )


def test_empty_camera_id_is_rejected(monkeypatch):
    config = make_config("   ")

    with pytest.raises(
        ValueError,
        match="Camera ID must not be empty",
    ):
        build_manager(
            monkeypatch,
            [config],
            {"   ": FakeSource()},
        )


def test_invalid_config_type_is_rejected(monkeypatch):
    with pytest.raises(
        TypeError,
        match="CameraConfig instance",
    ):
        build_manager(
            monkeypatch,
            ["not-a-camera-config"],
            {},
        )


def test_none_configuration_is_rejected():
    with pytest.raises(
        ValueError,
        match="camera_configs must not be None",
    ):
        CameraManager(None)
