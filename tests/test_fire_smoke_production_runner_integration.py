import numpy as np

import ai.run_intrusion_detection as runner

from database.event_database import EventDatabase


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
    def __init__(
        self,
        camera_id,
        database,
        failure_threshold=3,
    ):
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

    def start_event_capture(
        self,
        event_type,
        event_id,
    ):
        self.started.append(
            (event_type, event_id)
        )

        return None

    def finalize(self):
        self.finalized = True


class FakeDetector:
    def detect(self, frame):
        return [
            {
                "class": "person",
                "confidence": 0.99,
                "box": [100, 100, 400, 200],
            }
        ]


class FakeTracker:
    def update(self, detections):
        return [
            {
                "track_id": 1,
                "box": [100, 100, 400, 200],
                "state": "TRACKED",
            }
        ]


class FakeZoneDetector:
    def check_tracks(self, tracks):
        return []


class FakeIntrusionRule:
    def __init__(self, persistence_frames=3):
        pass

    def evaluate(self, zone_results):
        return []


class NoFallProcessor:
    def __init__(
        self,
        persistence_frames=3,
        min_horizontal_aspect_ratio=1.5,
    ):
        pass

    def evaluate(self, tracks):
        return []

class FakeFireSmokeProvider:
    def __init__(self):
        self.calls = 0

    def __call__(self, frame):
        self.calls += 1

        return [
            {
                "class_name": "fire",
                "confidence": 0.95,
                "box": [100, 100, 300, 300],
            }
        ]


class FakeFireSmokeProcessor:
    def __init__(self):
        self.calls = 0

    def evaluate(self, detections):
        self.calls += 1

        assert isinstance(
            detections,
            list,
        )

        assert len(detections) == 1

        assert (
            detections[0]["class_name"]
            == "fire"
        )

        return [
            {
                "event_type": "FIRE",
                "severity": "CRITICAL",
                "zone_id": None,
                "zone_name": None,
                "track_id": None,
                "message": (
                    "Potential fire detected "
                    "by CCTV analysis"
                ),
            }
        ]


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


def test_process_camera_persists_fire_and_queues_notification(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )

    source = FakeSource(frame)

    camera_manager = FakeCameraManager(
        source
    )

    camera_database = FakeCameraDatabase()
    camera_health_events = FakeCameraHealthEvents()
    dispatcher = RecordingDispatcher()

    event_database = EventDatabase(
        tmp_path / "events.db"
    )

    writer = FakeWriter()

    provider = FakeFireSmokeProvider()
    processor = FakeFireSmokeProcessor()

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (
            1.0,
            3,
            640,
            480,
        ),
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

    monkeypatch.setattr(
        runner,
        "FallEventProcessor",
        NoFallProcessor,
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
        fire_smoke_detection_provider=provider,
        fire_smoke_event_processor=processor,
    )

    assert result["camera_id"] == "CAM-001"
    assert result["error"] is None
    assert result["frames"] == 3
    assert result["ai_frames"] == 3
    assert result["events"] == 3

    assert provider.calls == 3
    assert processor.calls == 3

    events = event_database.get_all_events()

    assert len(events) == 3

    for event in events:
        assert event["event_type"] == "FIRE"
        assert event["severity"] == "CRITICAL"
        assert event["camera_id"] == "CAM-001"
        assert event["track_id"] is None
        assert event["zone_id"] is None
        assert event["zone_name"] is None
        assert event["model_version"] == (
            "fire-smoke-event-v1"
        )
        assert event["status"] == "NEW"
        assert event["evidence_path"] is None

    assert len(dispatcher.calls) == 3

    for notification in dispatcher.calls:
        assert notification["severity"] == "CRITICAL"
        assert notification["recipient"] is None
        assert notification["subject"] == (
            "Hotel Security Alert - FIRE"
        )
        assert (
            "Potential fire detected"
            in notification["message"]
        )

    assert writer.frames == 3
    assert writer.released is True

    event_database.close()


def test_process_camera_fire_does_not_replace_existing_fall_pipeline(
    monkeypatch,
    tmp_path,
):
    frame = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )

    source = FakeSource(frame)

    camera_manager = FakeCameraManager(
        source
    )

    camera_database = FakeCameraDatabase()
    camera_health_events = FakeCameraHealthEvents()
    dispatcher = RecordingDispatcher()

    event_database = EventDatabase(
        tmp_path / "events.db"
    )

    writer = FakeWriter()

    provider = FakeFireSmokeProvider()
    processor = FakeFireSmokeProcessor()

    class FallProducingProcessor:
        def __init__(
            self,
            persistence_frames=3,
            min_horizontal_aspect_ratio=1.5,
        ):
            pass

        def evaluate(self, tracks):
            return [
                {
                    "event_type": "FALL",
                    "severity": "HIGH",
                    "zone_id": None,
                    "zone_name": None,
                    "track_id": 1,
                    "message": (
                        "Potential person-down event "
                        "detected for track 1"
                    ),
                }
            ]

    monkeypatch.setattr(
        runner,
        "get_capture_metadata",
        lambda source: (
            1.0,
            3,
            640,
            480,
        ),
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

    monkeypatch.setattr(
        runner,
        "FallEventProcessor",
        FallProducingProcessor,
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
        fire_smoke_detection_provider=provider,
        fire_smoke_event_processor=processor,
    )

    assert result["error"] is None
    assert result["frames"] == 3
    assert result["ai_frames"] == 3
    assert result["events"] == 6

    events = event_database.get_all_events()

    assert len(events) == 6

    event_types = {
        event["event_type"]
        for event in events
    }

    assert event_types == {
        "FALL",
        "FIRE",
    }

    fire_events = [
        event
        for event in events
        if event["event_type"] == "FIRE"
    ]

    fall_events = [
        event
        for event in events
        if event["event_type"] == "FALL"
    ]

    assert len(fire_events) == 3
    assert len(fall_events) == 3

    assert all(
        event["model_version"]
        == "fire-smoke-event-v1"
        for event in fire_events
    )

    assert all(
        event["model_version"]
        == "fall-heuristic-v1"
        for event in fall_events
    )

    assert len(dispatcher.calls) == 6

    subjects = {
        call["subject"]
        for call in dispatcher.calls
    }

    assert subjects == {
        "Hotel Security Alert - FIRE",
        "Hotel Security Alert - FALL",
    }

    event_database.close()
