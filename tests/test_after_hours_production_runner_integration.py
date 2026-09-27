from datetime import datetime, timedelta, timezone

import numpy as np

import ai.run_intrusion_detection as runner
from database.event_database import EventDatabase
from database.camera_health_database import CameraHealthDatabase


TZ = timezone(timedelta(hours=5, minutes=30))


class FakeSource:
    def __init__(self, frame):
        self.frame = frame
        self.reads = 0

    def read(self):
        self.reads += 1
        return self.frame if self.reads <= 3 else None


class FakeCameraManager:
    def __init__(self, source):
        self.source = source

    def get_source(self, camera_id):
        return self.source


class FakeCameraDatabase:
    def get_camera(self, camera_id):
        return {
            "camera_id": camera_id,
            "name": "Test Camera",
            "location": "Test Location",
            "status": "ONLINE",
            "consecutive_failures": 0,
            "last_seen": "already-seen",
        }


class FakeHealthEvents:
    def __init__(self):
        self.offline_calls = []
        self.recovered_calls = []

    def create_offline_event(self, **kwargs):
        self.offline_calls.append(kwargs)
        return 1001

    def create_recovered_event(self, **kwargs):
        self.recovered_calls.append(kwargs)
        return 1002


class FakeHealth:
    def __init__(self, *args, **kwargs):
        pass

    def frame_received(self, *args, **kwargs):
        return None

    def frame_failed(self, *args, **kwargs):
        return None

    def get_failure_count(self):
        return 0

    def is_offline(self):
        return False


class FakeWriter:
    def __init__(self):
        self.frames = 0
        self.released = False

    def isOpened(self):
        return True

    def write(self, frame):
        self.frames += 1

    def release(self):
        self.released = True


class FakeEvidence:
    def __init__(self, *args, **kwargs):
        pass

    def add_frame(self, frame):
        pass

    def start_event_capture(self, *args, **kwargs):
        return None

    def finalize(self):
        pass


class FakeDetector:
    def detect(self, frame):
        return [{
            "class": "person",
            "confidence": 0.99,
            "box": [100, 100, 200, 300],
        }]


class FakeTracker:
    def update(self, detections):
        return [{
            "track_id": 1,
            "box": [10, 10, 100, 200],
            "state": "TRACKED",
            "missed": 0,
        }]


class FakeZoneDetector:
    def check_tracks(self, tracks):
        return []


class FakeIntrusion:
    def __init__(self, *args, **kwargs):
        pass

    def evaluate(self, zone_results):
        return []


class FakeFall:
    def __init__(self, *args, **kwargs):
        pass

    def evaluate(self, tracks):
        return []


class Dispatcher:
    def __init__(self):
        self.calls = []

    def notify_event(self, **kwargs):
        self.calls.append(kwargs)
        return "FAKE-FUTURE"


def make_camera_config():
    return type(
        "CameraConfig",
        (),
        {
            "camera_id": "CAM-001",
            "name": "Test Camera",
            "location": "Test Location",
            "source_type": "FILE",
            "ai_fps": 1.0,
        },
    )()


def test_after_hours_event_reaches_full_runner_pipeline(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    writer = FakeWriter()
    dispatcher = Dispatcher()
    database = EventDatabase(tmp_path / "events.db")

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (1.0, 3, 640, 480),
    )
    monkeypatch.setattr(
        runner,
        "is_finite_source",
        lambda config: True,
    )
    monkeypatch.setattr(
        runner.cv2,
        "VideoWriter",
        lambda *args, **kwargs: writer,
    )
    monkeypatch.setattr(runner, "EvidenceRecorder", FakeEvidence)
    monkeypatch.setattr(runner, "CameraHealthMonitor", FakeHealth)
    monkeypatch.setattr(runner, "PersonTracker", FakeTracker)
    monkeypatch.setattr(runner, "IntrusionRule", FakeIntrusion)
    monkeypatch.setattr(runner, "FallEventProcessor", FakeFall)

    result = runner.process_camera(
        camera_config=make_camera_config(),
        camera_manager=FakeCameraManager(FakeSource(frame)),
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=database,
        camera_database=FakeCameraDatabase(),
        camera_health_events=FakeHealthEvents(),
        notification_dispatcher=dispatcher,
        after_hours_config={
            "enabled": True,
            "timezone": "Asia/Kolkata",
            "persistence_frames": 3,
            "severity": "HIGH",
            "default_schedule": {
                "working_days": [0, 1, 2, 3, 4],
                "start": "09:00",
                "end": "18:00",
                "zone_ids": [],
            },
            "cameras": {},
        },
        after_hours_now_provider=lambda: datetime(
            2026,
            9,
            25,
            20,
            0,
            tzinfo=TZ,
        ),
    )

    assert result["error"] is None
    assert result["frames"] == 3
    assert result["ai_frames"] == 3
    assert result["events"] == 1

    latency = result["latency"]
    assert latency["overall"]["count"] == 1
    assert latency["overall"]["mean_ms"] is not None
    assert latency["overall"]["median_ms"] is not None
    assert latency["overall"]["p95_ms"] is not None
    assert latency["overall"]["max_ms"] is not None

    assert "AFTER_HOURS" in latency["by_event_type"]
    assert latency["by_event_type"]["AFTER_HOURS"]["count"] == 1

    events = database.get_all_events()
    assert len(events) == 1

    event = events[0]
    assert event["event_type"] == "AFTER_HOURS"
    assert event["severity"] == "HIGH"
    assert event["camera_id"] == "CAM-001"
    assert event["zone_id"] is None
    assert event["zone_name"] is None
    assert event["track_id"] is None
    assert event["model_version"] == "after-hours-rule-v1"
    assert event["status"] == "NEW"
    assert "After-hours presence detected" in event["message"]

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["subject"] == (
        "Hotel Security Alert - AFTER_HOURS"
    )

    assert writer.frames == 3
    assert writer.released is True

    database.close()

def test_camera_health_history_reaches_full_runner_pipeline(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    writer = FakeWriter()
    dispatcher = Dispatcher()
    event_database = EventDatabase(tmp_path / "events.db")
    health_database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (1.0, 3, 640, 480),
    )
    monkeypatch.setattr(
        runner,
        "is_finite_source",
        lambda config: True,
    )
    monkeypatch.setattr(
        runner.cv2,
        "VideoWriter",
        lambda *args, **kwargs: writer,
    )
    monkeypatch.setattr(runner, "EvidenceRecorder", FakeEvidence)
    monkeypatch.setattr(runner, "CameraHealthMonitor", FakeHealth)
    monkeypatch.setattr(runner, "PersonTracker", FakeTracker)
    monkeypatch.setattr(runner, "IntrusionRule", FakeIntrusion)
    monkeypatch.setattr(runner, "FallEventProcessor", FakeFall)

    from ai.camera_health_history import CameraHealthHistoryService

    history = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=health_database,
    )

    result = runner.process_camera(
        camera_config=make_camera_config(),
        camera_manager=FakeCameraManager(FakeSource(frame)),
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=event_database,
        camera_database=FakeCameraDatabase(),
        camera_health_events=FakeHealthEvents(),
        notification_dispatcher=dispatcher,
        camera_health_history=history,
    )

    assert result["error"] is None
    assert result["frames"] == 3

    rows = health_database.get_intervals(
        camera_id="CAM-001"
    )

    assert len(rows) == 1

    row = rows[0]

    assert row["status"] == "ONLINE"
    assert row["successful_frames"] == 3
    assert row["failed_frames"] == 0
    assert row["source_fps"] == 1.0
    assert row["end_time"] is not None

    assert writer.frames == 3
    assert writer.released is True

    event_database.close()
    health_database.close()

def test_camera_health_history_tracks_offline_and_recovery(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    writer = FakeWriter()
    dispatcher = Dispatcher()
    event_database = EventDatabase(tmp_path / "events.db")
    health_database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )

    from ai.camera_health import (
        CAMERA_OFFLINE,
        CAMERA_RECOVERED,
    )
    from ai.camera_health_history import (
        CameraHealthHistoryService,
    )

    class ContinuousHealth:
        failure_threshold = 3

        def __init__(self, *args, **kwargs):
            self.failure_count = 0
            self.offline = False
            self.seen_frame = False

        def frame_received(self, *args, **kwargs):
            if self.offline:
                self.offline = False
                self.failure_count = 0
                self.seen_frame = True
                return CAMERA_RECOVERED

            self.failure_count = 0
            self.seen_frame = True
            return None

        def frame_failed(self, *args, **kwargs):
            self.failure_count += 1

            if (
                self.failure_count >= self.failure_threshold
                and not self.offline
            ):
                self.offline = True
                return CAMERA_OFFLINE

            return None

        def get_failure_count(self):
            return self.failure_count

        def is_offline(self):
            return self.offline

    class ContinuousSource:
        def __init__(self):
            self.reads = 0

        def read(self):
            self.reads += 1

            if self.reads == 1:
                return frame

            if self.reads in (2, 3, 4):
                return None

            if self.reads == 5:
                return frame

            raise RuntimeError(
                "Stop test source after recovery"
            )

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (1.0, 0, 640, 480),
    )
    monkeypatch.setattr(
        runner,
        "is_finite_source",
        lambda config: False,
    )
    monkeypatch.setattr(
        runner.cv2,
        "VideoWriter",
        lambda *args, **kwargs: writer,
    )
    monkeypatch.setattr(runner, "EvidenceRecorder", FakeEvidence)
    monkeypatch.setattr(
        runner,
        "CameraHealthMonitor",
        ContinuousHealth,
    )
    monkeypatch.setattr(runner, "PersonTracker", FakeTracker)
    monkeypatch.setattr(runner, "IntrusionRule", FakeIntrusion)
    monkeypatch.setattr(runner, "FallEventProcessor", FakeFall)

    source = ContinuousSource()

    history = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=health_database,
    )

    result = runner.process_camera(
        camera_config=make_camera_config(),
        camera_manager=FakeCameraManager(source),
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=event_database,
        camera_database=FakeCameraDatabase(),
        camera_health_events=FakeHealthEvents(),
        notification_dispatcher=dispatcher,
        camera_health_history=history,
    )

    assert result["error"] == (
        "Stop test source after recovery"
    )

    rows = health_database.get_intervals(
        camera_id="CAM-001"
    )

    assert len(rows) == 3

    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["successful_frames"] == 1
    assert rows[0]["failed_frames"] == 3
    assert rows[0]["end_time"] is not None

    assert rows[1]["status"] == "OFFLINE"
    assert rows[1]["successful_frames"] == 0
    assert rows[1]["failed_frames"] == 3
    assert rows[1]["end_time"] is not None

    assert rows[2]["status"] == "ONLINE"
    assert rows[2]["successful_frames"] == 1
    assert rows[2]["failed_frames"] == 0
    assert rows[2]["end_time"] is not None

    assert writer.released is True

    event_database.close()
    health_database.close()
