from ai.fall_detector import FallDetector
from ai.tracker import PersonTracker


def test_fall_detector_consumes_person_tracker_output():
    tracker = PersonTracker()

    detections = [
        {
            "class": "person",
            "confidence": 0.95,
            "box": [400, 400, 700, 500],
        }
    ]

    tracks = tracker.update(detections)

    assert len(tracks) == 1

    track = tracks[0]

    assert "track_id" in track
    assert "box" in track

    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    first = detector.evaluate(
        track_id=track["track_id"],
        box=track["box"],
    )

    assert first is None

    detections = [
        {
            "class": "person",
            "confidence": 0.95,
            "box": [405, 405, 705, 505],
        }
    ]

    tracks = tracker.update(detections)

    assert len(tracks) == 1

    track = tracks[0]

    result = detector.evaluate(
        track_id=track["track_id"],
        box=track["box"],
    )

    assert result is not None
    assert result["event_type"] == "FALL"
    assert result["severity"] == "HIGH"
