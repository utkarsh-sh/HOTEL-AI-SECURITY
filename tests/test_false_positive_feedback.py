from pathlib import Path

import pytest

from database.event_database import EventDatabase
from rules.event_workflow import InvalidEventTransitionError, validate_transition


def create_test_event(database: EventDatabase) -> int:
    return database.create_event(
        event_type="INTRUSION",
        severity="HIGH",
        camera_id="CAM-TEST-001",
        zone_id="ZONE-TEST",
        zone_name="Test Zone",
        track_id=1,
        message="Test intrusion event",
        model_version="test-model",
        evidence_path=None,
    )


def test_new_event_can_be_marked_false_positive(tmp_path: Path):
    database = EventDatabase(tmp_path / "events.db")

    try:
        event_id = create_test_event(database)

        database.update_status(
            event_id=event_id,
            status="FALSE_POSITIVE",
            resolution="Operator confirmed this was a false alarm.",
        )

        event = database.get_event(event_id)

        assert event is not None
        assert event["status"] == "FALSE_POSITIVE"
        assert (
            event["resolution"]
            == "Operator confirmed this was a false alarm."
        )
        assert event["dispatched_at"] is None
        assert event["resolved_at"] is None
    finally:
        database.close()


def test_acknowledged_event_can_be_marked_false_positive(tmp_path: Path):
    database = EventDatabase(tmp_path / "events.db")

    try:
        event_id = create_test_event(database)

        database.update_status(
            event_id=event_id,
            status="ACKNOWLEDGED",
        )

        database.update_status(
            event_id=event_id,
            status="FALSE_POSITIVE",
            resolution="Security operator verified no incident occurred.",
        )

        event = database.get_event(event_id)

        assert event is not None
        assert event["status"] == "FALSE_POSITIVE"
        assert (
            event["resolution"]
            == "Security operator verified no incident occurred."
        )
    finally:
        database.close()


def test_false_positive_transition_rejects_invalid_source_statuses():
    invalid_statuses = [
        "DISPATCHED",
        "RESOLVED",
        "FALSE_POSITIVE",
    ]

    for status in invalid_statuses:
        with pytest.raises(InvalidEventTransitionError):
            validate_transition(
                current_status=status,
                new_status="FALSE_POSITIVE",
            )


def test_false_positive_transition_allows_expected_source_statuses():
    validate_transition(
        current_status="NEW",
        new_status="FALSE_POSITIVE",
    )

    validate_transition(
        current_status="ACKNOWLEDGED",
        new_status="FALSE_POSITIVE",
    )


def test_false_positive_persists_operator_reason(tmp_path: Path):
    database = EventDatabase(tmp_path / "events.db")

    try:
        event_id = create_test_event(database)

        reason = "Person was authorized hotel staff."

        database.update_status(
            event_id=event_id,
            status="FALSE_POSITIVE",
            resolution=reason,
        )

        event = database.get_event(event_id)

        assert event["status"] == "FALSE_POSITIVE"
        assert event["resolution"] == reason
    finally:
        database.close()
