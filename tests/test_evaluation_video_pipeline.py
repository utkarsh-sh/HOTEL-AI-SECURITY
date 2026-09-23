from pathlib import Path

from evaluation.video_runner import run_event_pipeline


class FakeDetector:
    def detect(self, frame):
        return [{"class": "person", "confidence": 0.9, "box": [10, 10, 50, 100]}]


class FakeTracker:
    def update(self, detections):
        return [
            {
                "track_id": 1,
                "box": [10, 10, 50, 100],
                "confidence": 0.9,
            }
        ]


class FakeZoneDetector:
    def check_tracks(self, tracks):
        return [
            {
                "zone_id": "ZONE-001",
                "zone_name": "Restricted Area",
                "track_id": 1,
                "inside": True,
                "point": [30, 100],
            }
        ]


class FakeRule:
    def __init__(self):
        self.calls = 0

    def evaluate(self, zone_results):
        self.calls += 1

        if self.calls == 3:
            return [
                {
                    "event_type": "INTRUSION",
                    "severity": "HIGH",
                    "zone_id": "ZONE-001",
                    "zone_name": "Restricted Area",
                    "track_id": 1,
                    "message": "Person 1 entered Restricted Area",
                }
            ]

        return []


class FakeSource:
    def __init__(self, frame_count):
        self.frames = [object() for _ in range(frame_count)]

    def read(self):
        if not self.frames:
            return None

        return self.frames.pop(0)


def test_pipeline_collects_intrusion_event():
    source = FakeSource(frame_count=10)

    result = run_event_pipeline(
        source=source,
        detector=FakeDetector(),
        tracker=FakeTracker(),
        zone_detector=FakeZoneDetector(),
        intrusion_rule=FakeRule(),
        source_fps=10.0,
        ai_fps=5.0,
    )

    assert result.total_frames == 10
    assert result.ai_frames == 5
    assert len(result.predictions) == 1

    prediction = result.predictions[0]

    assert prediction["event_type"] == "INTRUSION"
    assert prediction["zone_id"] == "ZONE-001"
    assert prediction["start_frame"] == 4
    assert prediction["end_frame"] == 4


def test_pipeline_returns_no_events_when_rule_never_fires():
    class NeverRule:
        def evaluate(self, zone_results):
            return []

    source = FakeSource(frame_count=6)

    result = run_event_pipeline(
        source=source,
        detector=FakeDetector(),
        tracker=FakeTracker(),
        zone_detector=FakeZoneDetector(),
        intrusion_rule=NeverRule(),
        source_fps=10.0,
        ai_fps=5.0,
    )

    assert result.total_frames == 6
    assert result.ai_frames == 3
    assert result.predictions == []


def test_invalid_fps_is_rejected():
    source = FakeSource(frame_count=1)

    try:
        run_event_pipeline(
            source=source,
            detector=FakeDetector(),
            tracker=FakeTracker(),
            zone_detector=FakeZoneDetector(),
            intrusion_rule=FakeRule(),
            source_fps=0,
            ai_fps=5.0,
        )
    except ValueError:
        return

    raise AssertionError("Expected ValueError for invalid source_fps")
