from database.event_database import EventDatabase
from ai.fall_event_processor import FallEventProcessor


def test_fall_event_persists_through_existing_event_database(tmp_path):
    database_path = tmp_path / "fall_test.db"

    database = EventDatabase(database_path)

    processor = FallEventProcessor(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    tracks = [
        {
            "track_id": 7,
            "box": [400, 400, 700, 500],
        }
    ]

    assert processor.evaluate(tracks) == []

    tracks = [
        {
            "track_id": 7,
            "box": [405, 405, 705, 505],
        }
    ]

    events = processor.evaluate(tracks)

    assert len(events) == 1

    fall_event = events[0]

    event_id = database.create_event(
        event_type=fall_event["event_type"],
        severity=fall_event["severity"],
        camera_id="CAM-001",
        zone_id=None,
        zone_name=None,
        track_id=fall_event["track_id"],
        message=fall_event["message"],
        model_version="fall-heuristic-v1",
    )

    assert isinstance(event_id, int)

    saved_event = database.get_event(event_id)

    assert saved_event is not None
    assert saved_event["event_type"] == "FALL"
    assert saved_event["severity"] == "HIGH"
    assert saved_event["camera_id"] == "CAM-001"
    assert saved_event["track_id"] == 7
    assert saved_event["model_version"] == "fall-heuristic-v1"

    database.close()
