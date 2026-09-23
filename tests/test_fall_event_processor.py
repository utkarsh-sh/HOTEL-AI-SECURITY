from ai.fall_event_processor import FallEventProcessor


def test_processor_returns_fall_event_from_tracker_output():
    processor = FallEventProcessor(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    tracks = [
        {
            "track_id": 1,
            "box": [400, 400, 700, 500],
        }
    ]

    assert processor.evaluate(tracks) == []

    tracks = [
        {
            "track_id": 1,
            "box": [405, 405, 705, 505],
        }
    ]

    events = processor.evaluate(tracks)

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "FALL"
    assert event["severity"] == "HIGH"
    assert event["track_id"] == 1


def test_processor_handles_multiple_tracks_independently():
    processor = FallEventProcessor(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    tracks = [
        {
            "track_id": 1,
            "box": [400, 400, 700, 500],
        },
        {
            "track_id": 2,
            "box": [800, 200, 900, 500],
        },
    ]

    assert processor.evaluate(tracks) == []

    tracks = [
        {
            "track_id": 1,
            "box": [405, 405, 705, 505],
        },
        {
            "track_id": 2,
            "box": [805, 205, 905, 505],
        },
    ]

    events = processor.evaluate(tracks)

    assert len(events) == 1
    assert events[0]["track_id"] == 1


def test_processor_does_not_repeat_same_fall_event():
    processor = FallEventProcessor(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    tracks = [
        {
            "track_id": 1,
            "box": [400, 400, 700, 500],
        }
    ]

    processor.evaluate(tracks)

    events = processor.evaluate(tracks)

    assert len(events) == 1

    events = processor.evaluate(tracks)

    assert events == []


def test_processor_rejects_invalid_track_list():
    processor = FallEventProcessor()

    try:
        processor.evaluate(None)
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid tracks"
    )


def test_processor_rejects_invalid_track():
    processor = FallEventProcessor()

    try:
        processor.evaluate(
            [
                {
                    "track_id": 1,
                }
            ]
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for missing track box"
    )
