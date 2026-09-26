from datetime import datetime, timedelta, timezone
import os

import pytest

from database.event_database import EventDatabase
from database.retention import (
    RetentionConfigurationError,
    RetentionService,
)


def create_database(tmp_path):
    database_path = tmp_path / "events.db"
    return EventDatabase(str(database_path))


def create_event(
    database,
    *,
    status="RESOLVED",
    created_at=None,
    evidence_path=None,
):
    event_id = database.create_event(
        event_type="INTRUSION",
        severity="HIGH",
        camera_id="CAM-001",
        zone_id="restricted_01",
        zone_name="Restricted Area",
        track_id="track-001",
        message="Test intrusion event",
        model_version="test-model",
        evidence_path=evidence_path,
    )

    if status != "NEW":
        database.connection.execute(
            """
            UPDATE events
            SET status = ?
            WHERE id = ?
            """,
            (status, event_id),
        )

    if created_at is not None:
        database.connection.execute(
            """
            UPDATE events
            SET created_at = ?
            WHERE id = ?
            """,
            (created_at, event_id),
        )

    database.connection.commit()

    return event_id


def write_config(path, event_days=30, evidence_days=30):
    path.write_text(
        (
            "{\n"
            f'    "event_retention_days": {event_days},\n'
            f'    "evidence_retention_days": {evidence_days}\n'
            "}\n"
        ),
        encoding="utf-8",
    )


def test_missing_configuration_raises(tmp_path):
    database = create_database(tmp_path)

    with pytest.raises(RetentionConfigurationError):
        RetentionService(
            database,
            config_path=tmp_path / "missing.json",
            evidence_directory=tmp_path / "events",
        )


def test_invalid_configuration_raises(tmp_path):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"

    config_path.write_text(
        '{"event_retention_days": 0, "evidence_retention_days": 30}',
        encoding="utf-8",
    )

    with pytest.raises(RetentionConfigurationError):
        RetentionService(
            database,
            config_path=config_path,
            evidence_directory=tmp_path / "events",
        )


def test_recent_terminal_event_is_retained(tmp_path):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    write_config(config_path)

    reference_time = datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )

    event_id = create_event(
        database,
        created_at=(
            reference_time - timedelta(days=29)
        ).isoformat(),
    )

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    result = service.cleanup(reference_time)

    assert result.events_considered == 1
    assert result.events_deleted == 0

    row = database.connection.execute(
        "SELECT id FROM events WHERE id = ?",
        (event_id,),
    ).fetchone()

    assert row is not None


def test_old_terminal_event_without_evidence_is_deleted(tmp_path):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    write_config(config_path)

    reference_time = datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )

    event_id = create_event(
        database,
        created_at=(
            reference_time - timedelta(days=31)
        ).isoformat(),
    )

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    result = service.cleanup(reference_time)

    assert result.events_considered == 1
    assert result.events_deleted == 1

    row = database.connection.execute(
        "SELECT id FROM events WHERE id = ?",
        (event_id,),
    ).fetchone()

    assert row is None


def test_old_terminal_event_with_recent_evidence_is_retained(
    tmp_path,
):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    write_config(config_path)

    evidence_path = evidence_directory / "event.mp4"
    evidence_path.write_bytes(b"test evidence")

    reference_time = datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )

    recent_timestamp = (
        reference_time - timedelta(days=5)
    ).timestamp()

    os.utime(
        evidence_path,
        (recent_timestamp, recent_timestamp),
    )

    event_id = create_event(
        database,
        created_at=(
            reference_time - timedelta(days=31)
        ).isoformat(),
        evidence_path=str(evidence_path),
    )

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    result = service.cleanup(reference_time)

    assert result.events_deleted == 0
    assert result.evidence_deleted == 0
    assert evidence_path.exists()

    row = database.connection.execute(
        "SELECT id FROM events WHERE id = ?",
        (event_id,),
    ).fetchone()

    assert row is not None


def test_old_terminal_event_with_old_evidence_is_deleted(
    tmp_path,
):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    write_config(config_path)

    evidence_path = evidence_directory / "event.mp4"
    evidence_path.write_bytes(b"test evidence")

    reference_time = datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )

    old_timestamp = (
        reference_time - timedelta(days=31)
    ).timestamp()

    os.utime(
        evidence_path,
        (old_timestamp, old_timestamp),
    )

    event_id = create_event(
        database,
        created_at=(
            reference_time - timedelta(days=31)
        ).isoformat(),
        evidence_path=str(evidence_path),
    )

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    result = service.cleanup(reference_time)

    assert result.events_deleted == 1
    assert result.evidence_deleted == 1
    assert not evidence_path.exists()

    row = database.connection.execute(
        "SELECT id FROM events WHERE id = ?",
        (event_id,),
    ).fetchone()

    assert row is None


def test_non_terminal_event_is_never_deleted(tmp_path):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    write_config(config_path)

    reference_time = datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )

    event_id = create_event(
        database,
        status="NEW",
        created_at=(
            reference_time - timedelta(days=31)
        ).isoformat(),
    )

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    result = service.cleanup(reference_time)

    assert result.events_deleted == 0

    row = database.connection.execute(
        "SELECT id FROM events WHERE id = ?",
        (event_id,),
    ).fetchone()

    assert row is not None


def test_evidence_outside_retention_directory_is_not_deleted(
    tmp_path,
):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()

    write_config(config_path)

    evidence_path = outside_directory / "event.mp4"
    evidence_path.write_bytes(b"test evidence")

    reference_time = datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )

    old_timestamp = (
        reference_time - timedelta(days=31)
    ).timestamp()

    os.utime(
        evidence_path,
        (old_timestamp, old_timestamp),
    )

    event_id = create_event(
        database,
        created_at=(
            reference_time - timedelta(days=31)
        ).isoformat(),
        evidence_path=str(evidence_path),
    )

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    result = service.cleanup(reference_time)

    assert evidence_path.exists()

    row = database.connection.execute(
        "SELECT id FROM events WHERE id = ?",
        (event_id,),
    ).fetchone()

    assert row is not None


def test_invalid_naive_reference_time_raises(tmp_path):
    database = create_database(tmp_path)
    config_path = tmp_path / "retention.json"
    evidence_directory = tmp_path / "events"
    evidence_directory.mkdir()

    write_config(config_path)

    service = RetentionService(
        database,
        config_path=config_path,
        evidence_directory=evidence_directory,
    )

    with pytest.raises(ValueError):
        service.cleanup(
            datetime(2026, 9, 26)
        )

