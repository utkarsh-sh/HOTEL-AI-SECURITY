from dataclasses import dataclass

from ai.camera_health import (
    CAMERA_OFFLINE,
    CAMERA_RECOVERED,
    CameraHealthMonitor,
)
from ai.camera_health_events import (
    CAMERA_OFFLINE_EVENT,
    CAMERA_RECOVERED_EVENT,
    CameraHealthEventService,
)
from database.camera_database import CameraDatabase
from database.event_database import EventDatabase
from video.camera_config import CameraConfig, ReconnectConfig
from video.camera_manager import CameraManager
from video.camera_worker_pool import CameraWorkerPool


@dataclass
class SequenceSource:
    """Deterministic test source. None represents a failed read."""

    values: list

    def open(self):
        return None

    def read(self):
        if not self.values:
            return None
        return self.values.pop(0)

    def release(self):
        return None


def make_config(camera_id):
    return CameraConfig(
        camera_id=camera_id,
        name=f"Camera {camera_id}",
        location=f"Location {camera_id}",
        source_type="file",
        source=f"test://{camera_id}",
        ai_fps=5.0,
        reconnect=ReconnectConfig(
            max_attempts=0,
            delay_seconds=0.0,
        ),
    )


def test_concurrent_camera_health_failure_isolation(tmp_path):
    """
    Verify that one camera can go OFFLINE and RECOVERED while
    another camera continues independently through the worker pool.

    Each worker owns its own SQLite connections.
    """

    camera_db_path = tmp_path / "camera_health.db"
    event_db_path = tmp_path / "events.db"

    # Create the cameras using a connection owned by the main thread.
    setup_db = CameraDatabase(str(camera_db_path))

    try:
        setup_db.create_camera(
            camera_id="CAM-001",
            name="Camera CAM-001",
            location="Location CAM-001",
        )
        setup_db.create_camera(
            camera_id="CAM-002",
            name="Camera CAM-002",
            location="Location CAM-002",
        )
    finally:
        setup_db.close()

    sources = {
        "CAM-001": SequenceSource(
            [
                "frame-1",
                "frame-2",
                "frame-3",
                None,
                None,
                None,
                "frame-recovered",
            ]
        ),
        "CAM-002": SequenceSource(
            [
                "frame-1",
                "frame-2",
                "frame-3",
                "frame-4",
                "frame-5",
                "frame-6",
                "frame-7",
            ]
        ),
    }

    manager = CameraManager(
        [
            make_config("CAM-001"),
            make_config("CAM-002"),
        ]
    )

    manager._cameras["CAM-001"].source = sources["CAM-001"]
    manager._cameras["CAM-002"].source = sources["CAM-002"]

    opened = manager.open_all()

    assert set(opened) == {"CAM-001", "CAM-002"}

    def worker(camera_id):
        # Critical: database connections are created inside the worker.
        camera_db = CameraDatabase(str(camera_db_path))
        event_db = EventDatabase(str(event_db_path))

        try:
            source = manager.get_source(camera_id)

            health = CameraHealthMonitor(
                camera_id=camera_id,
                database=camera_db,
                failure_threshold=3,
            )

            event_service = CameraHealthEventService(
                event_database=event_db,
            )

            offline_event_id = None
            recovered_event_id = None
            valid_frames = 0
            failed_frames = 0

            for _ in range(7):
                frame = source.read()

                if frame is None:
                    failed_frames += 1

                    transition = health.frame_failed(
                        error="Simulated camera failure"
                    )

                    if transition == CAMERA_OFFLINE:
                        offline_event_id = (
                            event_service.create_offline_event(
                                camera_id=camera_id,
                                error="Simulated camera failure",
                            )
                        )

                    continue

                previous_failures = health.get_failure_count()

                valid_frames += 1

                transition = health.frame_received(
                    fps=25.0,
                    width=1920,
                    height=1080,
                )

                if transition == CAMERA_RECOVERED:
                    assert previous_failures > 0

                    recovered_event_id = (
                        event_service.create_recovered_event(
                            camera_id=camera_id,
                        )
                    )

            return {
                "camera_id": camera_id,
                "valid_frames": valid_frames,
                "failed_frames": failed_frames,
                "offline_event_id": offline_event_id,
                "recovered_event_id": recovered_event_id,
                "final_offline": health.is_offline(),
            }

        finally:
            camera_db.close()
            event_db.close()

    pool = CameraWorkerPool(max_workers=2)

    results = pool.run(
        ["CAM-001", "CAM-002"],
        worker,
    )

    assert len(results) == 2
    assert all(result.success for result in results)

    by_camera = {
        result.camera_id: result.value
        for result in results
    }

    camera_1 = by_camera["CAM-001"]
    camera_2 = by_camera["CAM-002"]

    # CAM-001: failure followed by recovery.
    assert camera_1["valid_frames"] == 4
    assert camera_1["failed_frames"] == 3
    assert camera_1["offline_event_id"] is not None
    assert camera_1["recovered_event_id"] is not None
    assert camera_1["final_offline"] is False

    # CAM-002: unaffected by CAM-001 failure.
    assert camera_2["valid_frames"] == 7
    assert camera_2["failed_frames"] == 0
    assert camera_2["offline_event_id"] is None
    assert camera_2["recovered_event_id"] is None
    assert camera_2["final_offline"] is False

    # Verify persisted events using the actual EventDatabase API.
    verification_db = EventDatabase(str(event_db_path))

    try:
        events = verification_db.get_all_events()
    finally:
        verification_db.close()

    camera_1_events = [
        event
        for event in events
        if event["camera_id"] == "CAM-001"
    ]

    camera_2_events = [
        event
        for event in events
        if event["camera_id"] == "CAM-002"
    ]

    # Do not assume database retrieval order.
    camera_1_event_types = {
        event["event_type"]
        for event in camera_1_events
    }

    assert camera_1_event_types == {
        CAMERA_OFFLINE_EVENT,
        CAMERA_RECOVERED_EVENT,
    }

    assert len(camera_1_events) == 2
    assert camera_2_events == []
