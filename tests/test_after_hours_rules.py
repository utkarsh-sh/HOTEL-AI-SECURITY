from datetime import datetime, timedelta, timezone

import pytest

from rules.after_hours_rules import AfterHoursRule


TZ = timezone(timedelta(hours=5, minutes=30))


def base_config(**overrides):
    value = {
        "enabled": True,
        "timezone": "Asia/Kolkata",
        "persistence_frames": 3,
        "severity": "HIGH",
        "default_schedule": {
            "working_days": [0, 1, 2, 3, 4],
            "start": "09:00",
            "end": "18:00",
            "zone_ids": [],
        },
        "cameras": {},
    }
    value.update(overrides)
    return value


def tracks(count, missed_ids=None):
    missed_ids = set(missed_ids or [])
    return [
        {
            "track_id": index,
            "box": [10, 10, 40, 40],
            "state": "TRACKED",
            "missed": 1 if index in missed_ids else 0,
        }
        for index in range(1, count + 1)
    ]


def test_after_hours_requires_persistence():
    rule = AfterHoursRule(
        camera_id="CAM-001",
        config=base_config(),
        now_provider=lambda: datetime(
            2026, 9, 25, 20, 0, tzinfo=TZ
        ),
    )

    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(2), []) == []
    events = rule.evaluate(tracks(2), [])

    assert len(events) == 1
    assert events[0]["event_type"] == "AFTER_HOURS"
    assert events[0]["severity"] == "HIGH"
    assert events[0]["zone_id"] is None
    assert events[0]["people_count"] == 2


def test_after_hours_deduplicates_until_presence_clears():
    rule = AfterHoursRule(
        camera_id="CAM-001",
        config=base_config(),
        now_provider=lambda: datetime(
            2026, 9, 25, 20, 0, tzinfo=TZ
        ),
    )

    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(1), []) == []
    assert len(rule.evaluate(tracks(1), [])) == 1
    assert rule.evaluate(tracks(2), []) == []
    assert rule.evaluate([], []) == []
    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(1), []) == []
    assert len(rule.evaluate(tracks(1), [])) == 1


def test_working_hours_suppresses_and_resets():
    now_value = {
        "value": datetime(
            2026, 9, 25, 20, 0, tzinfo=TZ
        )
    }
    rule = AfterHoursRule(
        camera_id="CAM-001",
        config=base_config(),
        now_provider=lambda: now_value["value"],
    )

    assert rule.evaluate(tracks(1), []) == []
    assert len(rule.evaluate(tracks(1), [])) == 0
    assert len(rule.evaluate(tracks(1), [])) == 1

    now_value["value"] = datetime(
        2026, 9, 25, 10, 0, tzinfo=TZ
    )
    assert rule.evaluate(tracks(1), []) == []

    now_value["value"] = datetime(
        2026, 9, 25, 20, 0, tzinfo=TZ
    )
    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(1), []) == []
    assert len(rule.evaluate(tracks(1), [])) == 1


def test_non_working_day_is_after_hours():
    rule = AfterHoursRule(
        camera_id="CAM-001",
        config=base_config(),
        now_provider=lambda: datetime(
            2026, 9, 27, 12, 0, tzinfo=TZ
        ),
    )

    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(1), []) == []
    assert len(rule.evaluate(tracks(1), [])) == 1


def test_missed_tracks_do_not_trigger():
    rule = AfterHoursRule(
        camera_id="CAM-001",
        config={
            **base_config(),
            "persistence_frames": 1,
        },
        now_provider=lambda: datetime(
            2026, 9, 25, 20, 0, tzinfo=TZ
        ),
    )

    assert rule.evaluate(
        tracks(1, missed_ids={1}),
        [],
    ) == []


def test_zone_scoped_after_hours_presence():
    value = base_config(
        persistence_frames=1,
    )
    value["default_schedule"]["zone_ids"] = [
        "restricted_01"
    ]

    rule = AfterHoursRule(
        camera_id="CAM-001",
        config=value,
        available_zone_ids={"restricted_01"},
        now_provider=lambda: datetime(
            2026, 9, 25, 20, 0, tzinfo=TZ
        ),
    )

    events = rule.evaluate(
        tracks(2),
        [
            {
                "zone_id": "restricted_01",
                "zone_name": "Restricted Area",
                "track_id": 1,
                "inside": True,
            },
            {
                "zone_id": "restricted_01",
                "zone_name": "Restricted Area",
                "track_id": 2,
                "inside": False,
            },
        ],
    )

    assert len(events) == 1
    assert events[0]["zone_id"] == "restricted_01"
    assert events[0]["zone_name"] == "Restricted Area"
    assert events[0]["people_count"] == 1


def test_camera_override_is_applied():
    value = base_config(
        cameras={
            "CAM-001": {
                "working_days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "22:00",
                "zone_ids": [],
            }
        }
    )

    rule = AfterHoursRule(
        camera_id="CAM-001",
        config=value,
        now_provider=lambda: datetime(
            2026, 9, 25, 20, 0, tzinfo=TZ
        ),
    )

    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(1), []) == []
    assert rule.evaluate(tracks(1), []) == []


def test_invalid_timezone_is_rejected():
    with pytest.raises(ValueError, match="Unknown timezone"):
        AfterHoursRule(
            camera_id="CAM-001",
            config=base_config(timezone="Not/AZone"),
        )


def test_invalid_schedule_is_rejected():
    value = base_config()
    value["default_schedule"]["start"] = "09:00"
    value["default_schedule"]["end"] = "09:00"

    with pytest.raises(ValueError, match="must differ"):
        AfterHoursRule(
            camera_id="CAM-001",
            config=value,
        )


def test_unknown_zone_is_rejected():
    value = base_config()
    value["default_schedule"]["zone_ids"] = [
        "unknown_zone"
    ]

    with pytest.raises(
        ValueError,
        match="Unknown after-hours zone_id",
    ):
        AfterHoursRule(
            camera_id="CAM-001",
            config=value,
            available_zone_ids={"restricted_01"},
        )
