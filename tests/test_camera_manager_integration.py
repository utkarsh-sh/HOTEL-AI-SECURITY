from pathlib import Path

from video.camera_config import (
    CameraConfig,
    ReconnectConfig,
)
from video.camera_manager import CameraManager


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_VIDEO = (
    PROJECT_ROOT
    / "data"
    / "input"
    / "01_person_tracking_intrusion.mp4"
)


def make_file_camera(camera_id):
    return CameraConfig(
        camera_id=camera_id,
        name=f"Test Camera {camera_id}",
        location=f"Test Location {camera_id}",
        source_type="file",
        source=str(TEST_VIDEO),
        ai_fps=5.0,
        reconnect=ReconnectConfig(
            max_attempts=1,
            delay_seconds=0.0,
        ),
    )


def test_camera_manager_reads_multiple_real_video_sources():
    assert TEST_VIDEO.exists(), (
        f"Required test video not found: {TEST_VIDEO}"
    )

    manager = CameraManager(
        [
            make_file_camera("CAM-TEST-001"),
            make_file_camera("CAM-TEST-002"),
        ]
    )

    opened = manager.open_all()

    try:
        assert set(opened) == {
            "CAM-TEST-001",
            "CAM-TEST-002",
        }

        frame_001 = manager.read("CAM-TEST-001")
        frame_002 = manager.read("CAM-TEST-002")

        assert frame_001 is not None
        assert frame_002 is not None

        assert frame_001.shape == frame_002.shape
        assert len(frame_001.shape) == 3
        assert frame_001.shape[2] == 3

        # Each camera maintains its own source/capture.
        source_001 = manager.get_source("CAM-TEST-001")
        source_002 = manager.get_source("CAM-TEST-002")

        assert source_001 is not source_002

    finally:
        errors = manager.release_all()

        assert errors == {}
