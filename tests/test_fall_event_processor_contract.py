from ai.fall_event_processor import FallEventProcessor


def test_fall_event_contains_generic_event_fields():
    processor = FallEventProcessor(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    processor.evaluate(
        [
            {
                "track_id": 1,
                "box": [400, 400, 700, 500],
            }
        ]
    )

    events = processor.evaluate(
        [
            {
                "track_id": 1,
                "box": [405, 405, 705, 505],
            }
        ]
    )

    assert len(events) == 1
    assert events[0]["event_type"] == "FALL"
    assert events[0]["zone_id"] is None
    assert events[0]["zone_name"] is None
