import pytest

from rules.crowding_rules import CrowdingRule


def make_tracks(count, missed_ids=None):
    missed_ids = set(missed_ids or [])
    return [
        {
            "track_id": index,
            "box": [10, 10, 40, 40],
            "state": "MISSED" if index in missed_ids else "TRACKED",
            "missed": 1 if index in missed_ids else 0,
        }
        for index in range(1, count + 1)
    ]


def test_crowding_requires_persistence():
    rule = CrowdingRule(minimum_people=3, persistence_frames=3)
    assert rule.evaluate(make_tracks(3)) == []
    assert rule.evaluate(make_tracks(4)) == []
    events = rule.evaluate(make_tracks(5))
    assert len(events) == 1
    assert events[0]["event_type"] == "CROWDING"
    assert events[0]["severity"] == "HIGH"
    assert events[0]["people_count"] == 5


def test_crowding_is_deduplicated_until_condition_clears():
    rule = CrowdingRule(minimum_people=3, persistence_frames=2)
    assert rule.evaluate(make_tracks(3)) == []
    assert len(rule.evaluate(make_tracks(3))) == 1
    assert rule.evaluate(make_tracks(4)) == []
    assert rule.evaluate(make_tracks(2)) == []
    assert rule.evaluate(make_tracks(3)) == []
    assert len(rule.evaluate(make_tracks(3))) == 1


def test_missed_tracks_are_not_counted():
    rule = CrowdingRule(minimum_people=3, persistence_frames=1)
    assert rule.evaluate(make_tracks(3, missed_ids={3})) == []


def test_duplicate_track_ids_are_counted_once():
    rule = CrowdingRule(minimum_people=2, persistence_frames=1)
    duplicate_tracks = [
        {"track_id": 1, "box": [10, 10, 40, 40], "state": "TRACKED", "missed": 0},
        {"track_id": 1, "box": [20, 20, 50, 50], "state": "TRACKED", "missed": 0},
    ]
    assert rule.evaluate(duplicate_tracks) == []


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        CrowdingRule(minimum_people=1)
    with pytest.raises(ValueError):
        CrowdingRule(persistence_frames=0)


def test_invalid_track_input_is_rejected():
    rule = CrowdingRule()
    with pytest.raises(ValueError, match="track_id"):
        rule.evaluate([{"box": [10, 10, 40, 40], "state": "TRACKED", "missed": 0}])


def test_reset_clears_active_alert():
    rule = CrowdingRule(minimum_people=2, persistence_frames=1)
    assert len(rule.evaluate(make_tracks(2))) == 1
    rule.reset()
    assert len(rule.evaluate(make_tracks(2))) == 1
