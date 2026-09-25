import numpy as np

import ai.run_intrusion_detection as runner
from database.event_database import EventDatabase


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
    pass


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
        return [
            {"track_id": 1, "box": [10, 10, 100, 200], "state": "TRACKED", "missed": 0},
            {"track_id": 2, "box": [120, 10, 210, 200], "state": "TRACKED", "missed": 0},
            {"track_id": 3, "box": [230, 10, 320, 200], "state": "TRACKED", "missed": 0},
        ]


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


def camera_config():
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


def test_crowding_reaches_event_pipeline(monkeypatch, tmp_path):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    writer = FakeWriter()
    dispatcher = Dispatcher()
    db = EventDatabase(tmp_path / "events.db")

    monkeypatch.setattr(runner, "get_capture_metadata", lambda source: (1.0, 3, 640, 480))
    monkeypatch.setattr(runner, "is_finite_source", lambda config: True)
    monkeypatch.setattr(runner.cv2, "VideoWriter", lambda *a, **k: writer)
    monkeypatch.setattr(runner, "EvidenceRecorder", FakeEvidence)
    monkeypatch.setattr(runner, "CameraHealthMonitor", FakeHealth)
    monkeypatch.setattr(runner, "PersonTracker", FakeTracker)
    monkeypatch.setattr(runner, "IntrusionRule", FakeIntrusion)
    monkeypatch.setattr(runner, "FallEventProcessor", FakeFall)

    result = runner.process_camera(
        camera_config=camera_config(),
        camera_manager=FakeCameraManager(FakeSource(frame)),
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=db,
        camera_database=FakeCameraDatabase(),
        camera_health_events=FakeHealthEvents(),
        notification_dispatcher=dispatcher,
        crowding_config={
            "enabled": True,
            "minimum_people": 3,
            "persistence_frames": 3,
        },
    )

    assert result["error"] is None
    assert result["events"] == 1

    events = db.get_all_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "CROWDING"
    assert events[0]["severity"] == "HIGH"
    assert events[0]["model_version"] == "crowding-rule-v1"
    assert "3 active people" in events[0]["message"]
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["subject"] == "Hotel Security Alert - CROWDING"
    assert writer.released is True

    db.close()
