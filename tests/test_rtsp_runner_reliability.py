from dataclasses import dataclass

from ai.camera_health import (
    CAMERA_OFFLINE,
    CAMERA_RECOVERED,
    CameraHealthMonitor,
)
from database.camera_database import CameraDatabase


@dataclass
class FakeSource:
    frames: list

    def read(self):
        if not self.frames:
            return None
        return self.frames.pop(0)

    def release(self):
        pass


def test_rtsp_failure_does_not_terminate_monitoring(tmp_path):
    """
    Stage 15G:
    Verify that RTSP failures keep the monitoring loop alive
    and that a later valid frame produces recovery.
    """

    database = CameraDatabase(str(tmp_path / "camera_health.db"))

    database.create_camera(
        camera_id="CAM-TEST",
        name="RTSP Test Camera",
        location="Test",
    )

    health = CameraHealthMonitor(
        camera_id="CAM-TEST",
        database=database,
        failure_threshold=3,
    )

    # A newly created camera has no previous frame.
    # It must not generate an OFFLINE state until it has
    # first been seen and subsequently loses connectivity.
    assert not health.is_offline()
    assert health.get_failure_count() == 0

    # First valid frame establishes the camera as ONLINE.
    transition = health.frame_received(
        fps=25.0,
        width=1920,
        height=1080,
    )

    assert transition is None
    assert not health.is_offline()
    assert health.get_failure_count() == 0

    # Simulate three consecutive RTSP failures.
    transitions = []

    for failure_number in range(3):
        transition = health.frame_failed(
            error=f"RTSP test failure {failure_number + 1}"
        )
        transitions.append(transition)

    # The camera should become OFFLINE exactly at threshold.
    assert transitions[0] is None
    assert transitions[1] is None
    assert transitions[2] == CAMERA_OFFLINE

    assert health.is_offline()
    assert health.get_failure_count() == 3

    # Additional failures must NOT generate another offline transition.
    transition = health.frame_failed(
        error="RTSP test failure 4"
    )

    assert transition is None
    assert health.is_offline()
    assert health.get_failure_count() == 4

    # Simulate the RTSP stream recovering.
    transition = health.frame_received(
        fps=25.0,
        width=1920,
        height=1080,
    )

    assert transition == CAMERA_RECOVERED
    assert not health.is_offline()
    assert health.get_failure_count() == 0

    # A second valid frame must not generate another recovery event.
    transition = health.frame_received(
        fps=25.0,
        width=1920,
        height=1080,
    )

    assert transition is None
    assert not health.is_offline()


def test_fake_rtsp_source_continues_after_failures():
    """
    Verify that a monitoring loop can continue after failures
    and process a later recovered frame.
    """

    source = FakeSource(
        frames=[
            None,
            None,
            None,
            "RECOVERED_FRAME",
        ]
    )

    received = []

    for _ in range(4):
        frame = source.read()

        if frame is None:
            # Required RTSP runner behavior:
            # failure must not terminate monitoring.
            continue

        received.append(frame)

    assert received == ["RECOVERED_FRAME"]
