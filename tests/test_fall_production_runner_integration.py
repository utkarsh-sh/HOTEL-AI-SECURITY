import numpy as np

import ai.run_intrusion_detection as runner
from database.event_database import EventDatabase
from ai.fall_event_processor import FallEventProcessor


class FakeSource:
    def __init__(self, frame):
        self.frame = frame
        self.reads = 0

    def read(self):
        self.reads += 1
        if self.reads <= 3:
            return self.frame
        return None


class FakeCameraManager:
    def __init__(self, source):
        self.source = source

    def get_source(self, camera_id):
        assert camera_id == "CAM-001"
        return self.source


class FakeCameraDatabase:
    def __init__(self, camera=None):
        self.camera = camera or {
            "camera_id": "CAM-001",
            "name": "Test Camera",
            "location": "Test Location",
            "status": "ONLINE",
            "consecutive_failures": 0,
        }

    def get_camera(self, camera_id):
        assert camera_id == "CAM-001"
        return self.camera


class FakeCameraHealthEvents:
    pass



class FakeHealthMonitor:
    def __init__(self, camera_id, database, failure_threshold=3):
        self.camera_id = camera_id
        self.database = database
        self.failure_threshold = failure_threshold

    def frame_received(self, fps, width, height):
        return None

    def frame_failed(self, error):
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


class FakeEvidenceRecorder:
    def __init__(self, *args, **kwargs):
        self.started = []
        self.finalized = False

    def add_frame(self, frame):
        pass

    def start_event_capture(self, event_type, event_id):
        self.started.append((event_type, event_id))
        return None

    def finalize(self):
        self.finalized = True


class FakeDetector:
    def detect(self, frame):
        return [{"class": "person", "confidence": 0.99,
                 "box": [100, 100, 400, 200]}]


class FakeTracker:
    def update(self, detections):
        return [{
            "track_id": 1,
            "box": [100, 100, 400, 200],
            "state": "TRACKED",
        }]


class FakeZoneDetector:
    def check_tracks(self, tracks):
        return []


class FakeIntrusionRule:
    def __init__(self, persistence_frames=3):
        pass

    def evaluate(self, zone_results):
        return []


class RecordingDispatcher:
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


def test_process_camera_persists_fall_and_queues_notification(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    source = FakeSource(frame)
    camera_manager = FakeCameraManager(source)
    camera_database = FakeCameraDatabase()
    camera_health_events = FakeCameraHealthEvents()
    dispatcher = RecordingDispatcher()

    event_database = EventDatabase(
        tmp_path / "events.db"
    )

    writer = FakeWriter()

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (1.0, 3, 640, 480),
    )
    monkeypatch.setattr(
        runner,
        "is_finite_source",
        lambda camera_config: True,
    )
    monkeypatch.setattr(
        runner.cv2,
        "VideoWriter",
        lambda *args, **kwargs: writer,
    )
    monkeypatch.setattr(
        runner,
        "EvidenceRecorder",
        FakeEvidenceRecorder,
    )
    monkeypatch.setattr(
        runner,
        "CameraHealthMonitor",
        FakeHealthMonitor,
    )
    monkeypatch.setattr(
        runner,
        "PersonTracker",
        FakeTracker,
    )
    monkeypatch.setattr(
        runner,
        "IntrusionRule",
        FakeIntrusionRule,
    )

    result = runner.process_camera(
        camera_config=make_camera_config(),
        camera_manager=camera_manager,
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=event_database,
        camera_database=camera_database,
        camera_health_events=camera_health_events,
        notification_dispatcher=dispatcher,
    )

    assert result["camera_id"] == "CAM-001"
    assert result["error"] is None
    assert result["frames"] == 3
    assert result["ai_frames"] == 3
    assert result["events"] == 1

    events = event_database.get_all_events()

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "FALL"
    assert event["severity"] == "HIGH"
    assert event["camera_id"] == "CAM-001"
    assert event["track_id"] == 1
    assert event["zone_id"] is None
    assert event["zone_name"] is None
    assert event["model_version"] == "fall-heuristic-v1"
    assert event["status"] == "NEW"

    assert len(dispatcher.calls) == 1

    notification = dispatcher.calls[0]

    assert notification["event_id"] == event["id"]
    assert notification["severity"] == "HIGH"
    assert notification["recipient"] is None
    assert notification["subject"] == "Hotel Security Alert - FALL"
    assert "Potential person-down event detected" in notification["message"]

    assert writer.frames == 3
    assert writer.released is True

    event_database.close()


def test_process_camera_fall_pipeline_does_not_replace_intrusion_pipeline(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    source = FakeSource(frame)
    camera_manager = FakeCameraManager(source)
    camera_database = FakeCameraDatabase()
    camera_health_events = FakeCameraHealthEvents()
    dispatcher = RecordingDispatcher()

    event_database = EventDatabase(
        tmp_path / "events.db"
    )

    writer = FakeWriter()

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (1.0, 3, 640, 480),
    )
    monkeypatch.setattr(
        runner,
        "is_finite_source",
        lambda camera_config: True,
    )
    monkeypatch.setattr(
        runner.cv2,
        "VideoWriter",
        lambda *args, **kwargs: writer,
    )
    monkeypatch.setattr(
        runner,
        "EvidenceRecorder",
        FakeEvidenceRecorder,
    )
    monkeypatch.setattr(
        runner,
        "CameraHealthMonitor",
        FakeHealthMonitor,
    )
    monkeypatch.setattr(
        runner,
        "PersonTracker",
        FakeTracker,
    )
    monkeypatch.setattr(
        runner,
        "IntrusionRule",
        lambda persistence_frames=3: FakeIntrusionRule(),
    )

    class IntrusionProducingRule:
        def __init__(self, persistence_frames=3):
            pass

        def evaluate(self, zone_results):
            return [{
                "event_type": "INTRUSION",
                "severity": "HIGH",
                "zone_id": "restricted_01",
                "zone_name": "Restricted Area",
                "track_id": 1,
                "message": "Person 1 entered Restricted Area",
            }]

    monkeypatch.setattr(
        runner,
        "IntrusionRule",
        IntrusionProducingRule,
    )

    result = runner.process_camera(
        camera_config=make_camera_config(),
        camera_manager=camera_manager,
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=event_database,
        camera_database=camera_database,
        camera_health_events=camera_health_events,
        notification_dispatcher=dispatcher,
    )

    assert result["error"] is None
    assert result["frames"] == 3
    assert result["ai_frames"] == 3
    assert result["events"] == 4

    events = event_database.get_all_events()

    assert len(events) == 4
    event_types = {event["event_type"] for event in events}

    assert event_types == {"FALL", "INTRUSION"}

    fall_event = next(
        event for event in events
        if event["event_type"] == "FALL"
    )
    intrusion_event = next(
        event for event in events
        if event["event_type"] == "INTRUSION"
    )

    assert fall_event["model_version"] == "fall-heuristic-v1"
    assert intrusion_event["model_version"] == "prototype-v1"

    assert len(dispatcher.calls) == 4
    assert {
        call["subject"]
        for call in dispatcher.calls
    } == {
        "Hotel Security Alert - FALL",
        "Hotel Security Alert - INTRUSION",
    }

    event_database.close()


class FailingEvidenceRecorder(FakeEvidenceRecorder):
    def start_event_capture(self, event_type, event_id):
        self.started.append((event_type, event_id))
        raise RuntimeError("simulated evidence recorder failure")


def test_process_camera_continues_when_evidence_capture_fails(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    source = FakeSource(frame)
    camera_manager = FakeCameraManager(source)
    camera_database = FakeCameraDatabase()
    camera_health_events = FakeCameraHealthEvents()
    dispatcher = RecordingDispatcher()

    event_database = EventDatabase(
        tmp_path / "events.db"
    )

    writer = FakeWriter()

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (1.0, 3, 640, 480),
    )
    monkeypatch.setattr(
        runner,
        "is_finite_source",
        lambda camera_config: True,
    )
    monkeypatch.setattr(
        runner.cv2,
        "VideoWriter",
        lambda *args, **kwargs: writer,
    )
    monkeypatch.setattr(
        runner,
        "EvidenceRecorder",
        FailingEvidenceRecorder,
    )
    monkeypatch.setattr(
        runner,
        "CameraHealthMonitor",
        FakeHealthMonitor,
    )
    monkeypatch.setattr(
        runner,
        "PersonTracker",
        FakeTracker,
    )
    monkeypatch.setattr(
        runner,
        "IntrusionRule",
        FakeIntrusionRule,
    )

    result = runner.process_camera(
        camera_config=make_camera_config(),
        camera_manager=camera_manager,
        detector=FakeDetector(),
        zones=[],
        zone_detector=FakeZoneDetector(),
        event_database=event_database,
        camera_database=camera_database,
        camera_health_events=camera_health_events,
        notification_dispatcher=dispatcher,
    )

    assert result["camera_id"] == "CAM-001"
    assert result["error"] is None
    assert result["frames"] == 3
    assert result["ai_frames"] == 3
    assert result["events"] == 1

    events = event_database.get_all_events()

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "FALL"
    assert event["severity"] == "HIGH"
    assert event["status"] == "NEW"
    assert event["evidence_path"] is None

    assert len(dispatcher.calls) == 1

    notification = dispatcher.calls[0]

    assert notification["event_id"] == event["id"]
    assert notification["severity"] == "HIGH"

    assert writer.frames == 3
    assert writer.released is True

    event_database.close()
