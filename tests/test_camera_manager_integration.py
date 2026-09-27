import cv2
import numpy as np

from video.camera_config import (
    CameraConfig,
    ReconnectConfig,
)
from video.camera_manager import CameraManager


def make_file_camera(camera_id, test_video):
    return CameraConfig(
        camera_id=camera_id,
        name=f"Test Camera {camera_id}",
        location=f"Test Location {camera_id}",
        source_type="file",
        source=str(test_video),
        ai_fps=5.0,
        reconnect=ReconnectConfig(
            max_attempts=1,
            delay_seconds=0.0,
        ),
    )


def test_camera_manager_reads_multiple_real_video_sources(tmp_path):
    test_video = tmp_path / "camera_test.mp4"
    writer = cv2.VideoWriter(
        str(test_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        5.0,
        (64, 48),
    )
    assert writer.isOpened()

    try:
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        writer.write(frame)
        writer.write(frame)
    finally:
        writer.release()

    manager = CameraManager(
        [
            make_file_camera("CAM-TEST-001", test_video),
            make_file_camera("CAM-TEST-002", test_video),
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

        source_001 = manager.get_source("CAM-TEST-001")
        source_002 = manager.get_source("CAM-TEST-002")

        assert source_001 is not source_002

    finally:
        errors = manager.release_all()

        assert errors == {}
