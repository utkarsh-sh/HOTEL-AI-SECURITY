import pytest

from ai.weapon_event_processor import WeaponEventProcessor


def det(cls="gun", conf=0.90, box=None):
    return {
        "class_name": cls,
        "confidence": conf,
        "box": box or [110, 120, 150, 170],
    }


def track(track_id=7):
    return {
        "track_id": track_id,
        "box": [50, 50, 300, 350],
        "state": "TRACKED",
    }


def test_persistence_and_track_association():
    processor = WeaponEventProcessor(persistence_frames=3)
    assert processor.evaluate([det()], [track()]) == []
    assert processor.evaluate([det()], [track()]) == []
    events = processor.evaluate([det(conf=0.95)], [track()])
    assert len(events) == 1
    assert events[0]["event_type"] == "WEAPON"
    assert events[0]["track_id"] == 7
    assert events[0]["weapon_class"] == "gun"
    assert events[0]["severity"] == "CRITICAL"


def test_no_repeat_until_region_disappears():
    processor = WeaponEventProcessor(persistence_frames=2)
    assert processor.evaluate([det()], [track()]) == []
    assert len(processor.evaluate([det()], [track()])) == 1
    assert processor.evaluate([det(box=[115, 122, 155, 172])], [track()]) == []
    assert processor.evaluate([], [track()]) == []
    assert processor.evaluate([det()], [track()]) == []
    assert len(processor.evaluate([det()], [track()])) == 1


def test_knife_is_supported():
    processor = WeaponEventProcessor(persistence_frames=1)
    events = processor.evaluate([det(cls="knife")])
    assert len(events) == 1
    assert events[0]["weapon_class"] == "knife"


def test_unsupported_class_is_rejected():
    processor = WeaponEventProcessor()
    with pytest.raises(ValueError, match="unsupported weapon class"):
        processor.evaluate([det(cls="grenade")])


def test_low_confidence_is_ignored():
    processor = WeaponEventProcessor(persistence_frames=1, min_confidence=0.75)
    assert processor.evaluate([det(conf=0.60)]) == []


def test_bad_box_rejected():
    processor = WeaponEventProcessor()
    with pytest.raises(ValueError):
        processor.evaluate([det(box=[10, 10, 5, 5])])
