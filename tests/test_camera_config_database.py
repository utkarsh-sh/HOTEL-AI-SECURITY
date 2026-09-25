from pathlib import Path

from database.camera_database import (
    BOOTSTRAP_METADATA_KEY,
    CameraDatabase,
)
from video.camera_config import (
    CameraConfig,
    ReconnectConfig,
    load_camera_configs_from_database,
)


def test_runtime_camera_configuration_round_trip(tmp_path):
    database = CameraDatabase(Path(tmp_path) / "camera.db")

    database.create_camera(
        camera_id="CAM-CONFIG",
        name="Lobby",
        location="Main Lobby",
        source_type="rtsp",
        source="rtsp://camera/stream",
        ai_fps=4.0,
        reconnect_max_attempts=5,
        reconnect_delay_seconds=2.5,
    )

    camera = database.get_camera("CAM-CONFIG")
    assert camera["source_type"] == "rtsp"
    assert camera["source"] == "rtsp://camera/stream"
    assert camera["ai_fps"] == 4.0
    assert camera["reconnect_max_attempts"] == 5
    assert camera["reconnect_delay_seconds"] == 2.5

    database.update_camera_configuration(
        camera_id="CAM-CONFIG",
        name="Updated Lobby",
        location="North Lobby",
        source_type="file",
        source="data/input/lobby.mp4",
        ai_fps=5.0,
        reconnect_max_attempts=3,
        reconnect_delay_seconds=1.0,
    )

    updated = database.get_camera("CAM-CONFIG")
    assert updated["name"] == "Updated Lobby"
    assert updated["location"] == "North Lobby"
    assert updated["source_type"] == "file"
    assert updated["source"] == "data/input/lobby.mp4"
    assert updated["ai_fps"] == 5.0

    database.close()


def test_bootstrap_initializes_once(tmp_path):
    database = CameraDatabase(Path(tmp_path) / "camera.db")

    config = CameraConfig(
        camera_id="CAM-001",
        name="Main Lobby",
        location="Lobby",
        source_type="file",
        source="data/input/lobby.mp4",
        ai_fps=5.0,
        reconnect=ReconnectConfig(),
    )

    database.initialize_from_bootstrap([config])

    assert database.get_metadata(BOOTSTRAP_METADATA_KEY) == "1"
    assert database.get_camera("CAM-001")["source"] == "data/input/lobby.mp4"

    database.delete_camera("CAM-001")
    database.initialize_from_bootstrap([config])

    assert database.get_camera("CAM-001") is None
    database.close()


def test_bootstrap_backfills_legacy_config_without_overwriting_admin_config(tmp_path):
    database_path = Path(tmp_path) / "camera.db"
    database = CameraDatabase(database_path)

    database.create_camera(
        camera_id="CAM-LEGACY",
        name="Legacy Name",
        location="Legacy Location",
    )

    bootstrap = CameraConfig(
        camera_id="CAM-LEGACY",
        name="Bootstrap Name",
        location="Bootstrap Location",
        source_type="file",
        source="data/input/bootstrap.mp4",
        ai_fps=5.0,
        reconnect=ReconnectConfig(),
    )

    database.initialize_from_bootstrap([bootstrap])

    legacy = database.get_camera("CAM-LEGACY")
    assert legacy["name"] == "Legacy Name"
    assert legacy["location"] == "Legacy Location"
    assert legacy["source"] == "data/input/bootstrap.mp4"

    database.update_camera_configuration(
        camera_id="CAM-LEGACY",
        name="Admin Name",
        location="Admin Location",
        source_type="rtsp",
        source="rtsp://admin/stream",
        ai_fps=2.0,
        reconnect_max_attempts=9,
        reconnect_delay_seconds=4.0,
    )
    database.close()

    database = CameraDatabase(database_path)
    database.initialize_from_bootstrap([bootstrap])

    updated = database.get_camera("CAM-LEGACY")
    assert updated["name"] == "Admin Name"
    assert updated["location"] == "Admin Location"
    assert updated["source_type"] == "rtsp"
    assert updated["source"] == "rtsp://admin/stream"
    assert updated["ai_fps"] == 2.0

    database.close()


def test_load_camera_configs_from_database(tmp_path):
    database = CameraDatabase(Path(tmp_path) / "camera.db")

    database.create_camera(
        camera_id="CAM-001",
        name="Main Lobby",
        location="Lobby",
        source_type="rtsp",
        source="rtsp://camera/stream",
        ai_fps=4.0,
        reconnect_max_attempts=6,
        reconnect_delay_seconds=2.0,
    )

    configs = load_camera_configs_from_database(database)
    assert len(configs) == 1

    config = configs[0]
    assert config.camera_id == "CAM-001"
    assert config.source_type == "rtsp"
    assert config.source == "rtsp://camera/stream"
    assert config.ai_fps == 4.0
    assert config.reconnect.max_attempts == 6
    assert config.reconnect.delay_seconds == 2.0

    database.close()


def test_load_camera_configs_rejects_empty_source(tmp_path):
    database = CameraDatabase(Path(tmp_path) / "camera.db")

    database.create_camera(
        camera_id="CAM-UNCONFIGURED",
        name="Unconfigured",
        location="Test",
    )

    try:
        load_camera_configs_from_database(database)
    except ValueError as error:
        assert "CAM-UNCONFIGURED" in str(error)
    else:
        raise AssertionError("Expected ValueError for missing camera source")
    finally:
        database.close()
