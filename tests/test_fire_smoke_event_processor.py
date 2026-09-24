from ai.fire_smoke_event_processor import (
    FireSmokeEventProcessor,
)


def fire_detection(
    confidence=0.90,
    box=None,
):
    if box is None:
        box = [100, 100, 300, 300]

    return {
        "class_name": "fire",
        "confidence": confidence,
        "box": box,
    }


def smoke_detection(
    confidence=0.90,
    box=None,
):
    if box is None:
        box = [100, 100, 300, 300]

    return {
        "class_name": "smoke",
        "confidence": confidence,
        "box": box,
    }


def test_fire_requires_persistence():
    processor = FireSmokeEventProcessor(
        persistence_frames=2,
    )

    assert processor.evaluate(
        [fire_detection()]
    ) == []

    events = processor.evaluate(
        [fire_detection()]
    )

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "FIRE"
    assert event["severity"] == "CRITICAL"
    assert event["track_id"] is None


def test_smoke_requires_persistence():
    processor = FireSmokeEventProcessor(
        persistence_frames=2,
    )

    assert processor.evaluate(
        [smoke_detection()]
    ) == []

    events = processor.evaluate(
        [smoke_detection()]
    )

    assert len(events) == 1

    event = events[0]

    assert event["event_type"] == "SMOKE"
    assert event["severity"] == "HIGH"
    assert event["track_id"] is None


def test_fire_event_is_not_repeated_while_region_persists():
    processor = FireSmokeEventProcessor(
        persistence_frames=2,
    )

    processor.evaluate(
        [fire_detection()]
    )

    assert len(
        processor.evaluate(
            [fire_detection()]
        )
    ) == 1

    assert processor.evaluate(
        [fire_detection()]
    ) == []


def test_region_reset_allows_new_event():
    processor = FireSmokeEventProcessor(
        persistence_frames=2,
    )

    processor.evaluate(
        [fire_detection()]
    )

    processor.evaluate(
        [fire_detection()]
    )

    assert processor.evaluate(
        []
    ) == []

    assert processor.evaluate(
        [fire_detection()]
    ) == []

    events = processor.evaluate(
        [fire_detection()]
    )

    assert len(events) == 1
    assert events[0]["event_type"] == "FIRE"


def test_low_confidence_detection_is_ignored():
    processor = FireSmokeEventProcessor(
        persistence_frames=1,
        min_confidence=0.70,
    )

    assert processor.evaluate(
        [fire_detection(confidence=0.60)]
    ) == []


def test_fire_and_smoke_can_be_detected_independently():
    processor = FireSmokeEventProcessor(
        persistence_frames=2,
    )

    assert processor.evaluate(
        [
            fire_detection(),
            smoke_detection(
                box=[600, 100, 800, 300]
            ),
        ]
    ) == []

    events = processor.evaluate(
        [
            fire_detection(),
            smoke_detection(
                box=[600, 100, 800, 300]
            ),
        ]
    )

    assert len(events) == 2

    event_types = {
        event["event_type"]
        for event in events
    }

    assert event_types == {
        "FIRE",
        "SMOKE",
    }


def test_invalid_detection_list_is_rejected():
    processor = FireSmokeEventProcessor()

    try:
        processor.evaluate(None)
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid detections"
    )


def test_invalid_detection_is_rejected():
    processor = FireSmokeEventProcessor()

    try:
        processor.evaluate(
            [
                {
                    "class_name": "fire",
                    "confidence": 0.90,
                }
            ]
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for missing box"
    )


def test_unsupported_class_is_rejected():
    processor = FireSmokeEventProcessor()

    try:
        processor.evaluate(
            [
                {
                    "class_name": "person",
                    "confidence": 0.90,
                    "box": [100, 100, 200, 200],
                }
            ]
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for unsupported class"
    )


def test_invalid_confidence_is_rejected():
    processor = FireSmokeEventProcessor()

    try:
        processor.evaluate(
            [
                {
                    "class_name": "fire",
                    "confidence": 1.5,
                    "box": [100, 100, 200, 200],
                }
            ]
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid confidence"
    )
