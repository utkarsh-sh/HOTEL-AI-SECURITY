from pathlib import Path

import pytest

from database.event_database import EventDatabase
from database.notification_database import NotificationDatabase
from notifications.dispatcher import NotificationDispatcher
from notifications.providers import (
    NotificationMessage,
    NotificationProvider,
    NotificationResult,
)


class RecordingProvider(NotificationProvider):
    @property
    def provider_name(self) -> str:
        return "recording"

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.calls = []

    def send(self, message: NotificationMessage) -> NotificationResult:
        if self.delay:
            import time

            time.sleep(self.delay)

        self.calls.append(message)

        return NotificationResult(
            success=True,
            provider=self.provider_name,
            sent_at="2026-09-22T23:00:00+00:00",
        )


class FailingProvider(NotificationProvider):
    @property
    def provider_name(self) -> str:
        return "failing"

    def __init__(self):
        self.calls = []

    def send(self, message: NotificationMessage) -> NotificationResult:
        self.calls.append(message)

        return NotificationResult(
            success=False,
            provider=self.provider_name,
            error_message="delivery failed",
        )


def create_event(database_path: Path, event_id: int) -> None:
    database = EventDatabase(database_path)

    try:
        created_event_id = database.create_event(
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-TEST",
            zone_id=None,
            zone_name="Test Zone",
            track_id=None,
            message="Test intrusion event",
            model_version="test-model",
            evidence_path=None,
        )

        assert created_event_id == event_id
    finally:
        database.close()


def test_dispatcher_delivers_notification(tmp_path):
    database_path = tmp_path / "hotel_security.db"

    create_event(database_path, 1)

    provider = RecordingProvider()

    dispatcher = NotificationDispatcher(
        providers={"CONSOLE": provider},
        database_path=database_path,
        max_workers=1,
        max_retries=0,
    )

    try:
        future = dispatcher.notify_event(
            event_id=1,
            severity="HIGH",
            recipient="security@test.local",
            subject="Security Alert",
            message="Test intrusion detected",
        )

        result = future.result(timeout=5)

        assert result is not None
        assert len(provider.calls) == 1
        assert provider.calls[0].event_id == 1
    finally:
        dispatcher.shutdown()


def test_dispatcher_runs_multiple_jobs_concurrently(tmp_path):
    database_path = tmp_path / "hotel_security.db"

    create_event(database_path, 1)
    create_event(database_path, 2)

    provider = RecordingProvider(delay=0.25)

    dispatcher = NotificationDispatcher(
        providers={"CONSOLE": provider},
        database_path=database_path,
        max_workers=2,
        max_retries=0,
    )

    try:
        future_1 = dispatcher.notify_event(
            event_id=1,
            severity="HIGH",
            recipient="security@test.local",
            subject="Camera 1 Alert",
            message="Intrusion detected on CAM-001",
        )

        future_2 = dispatcher.notify_event(
            event_id=2,
            severity="HIGH",
            recipient="security@test.local",
            subject="Camera 2 Alert",
            message="Intrusion detected on CAM-002",
        )

        future_1.result(timeout=5)
        future_2.result(timeout=5)

        assert len(provider.calls) == 2
    finally:
        dispatcher.shutdown()


def test_dispatcher_persists_notification(tmp_path):
    database_path = tmp_path / "hotel_security.db"

    create_event(database_path, 1)

    provider = RecordingProvider()

    dispatcher = NotificationDispatcher(
        providers={"CONSOLE": provider},
        database_path=database_path,
        max_workers=1,
        max_retries=0,
    )

    try:
        future = dispatcher.notify_event(
            event_id=1,
            severity="HIGH",
            recipient="security@test.local",
            subject="Security Alert",
            message="Test intrusion detected",
        )

        future.result(timeout=5)
    finally:
        dispatcher.shutdown()

    database = NotificationDatabase(database_path)

    try:
        rows = database.connection.execute(
            """
            SELECT event_id, status, retry_count
            FROM notifications
            WHERE event_id = ?
            """,
            (1,),
        ).fetchall()

        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "SENT"
        assert rows[0][2] == 0
    finally:
        database.close()


def test_dispatcher_delegates_retry_policy(tmp_path):
    database_path = tmp_path / "hotel_security.db"

    create_event(database_path, 1)

    provider = FailingProvider()

    dispatcher = NotificationDispatcher(
        providers={"CONSOLE": provider},
        database_path=database_path,
        max_workers=1,
        max_retries=2,
    )

    try:
        future = dispatcher.notify_event(
            event_id=1,
            severity="HIGH",
            recipient="security@test.local",
            subject="Security Alert",
            message="Test intrusion detected",
        )

        future.result(timeout=5)
    finally:
        dispatcher.shutdown()

    database = NotificationDatabase(database_path)

    try:
        row = database.connection.execute(
            """
            SELECT status, retry_count
            FROM notifications
            WHERE event_id = ?
            """,
            (1,),
        ).fetchone()

        assert row is not None
        assert row[0] == "FAILED"
        assert row[1] == 3
        assert len(provider.calls) == 3
    finally:
        database.close()


def test_dispatcher_rejects_invalid_worker_count(tmp_path):
    with pytest.raises(ValueError):
        NotificationDispatcher(
            providers={},
            database_path=tmp_path / "hotel_security.db",
            max_workers=0,
        )


def test_dispatcher_rejects_negative_retries(tmp_path):
    with pytest.raises(ValueError):
        NotificationDispatcher(
            providers={},
            database_path=tmp_path / "hotel_security.db",
            max_workers=1,
            max_retries=-1,
        )


def test_dispatcher_rejects_submission_after_shutdown(tmp_path):
    database_path = tmp_path / "hotel_security.db"

    create_event(database_path, 1)

    provider = RecordingProvider()

    dispatcher = NotificationDispatcher(
        providers={"CONSOLE": provider},
        database_path=database_path,
        max_workers=1,
        max_retries=0,
    )

    dispatcher.shutdown()

    with pytest.raises(RuntimeError):
        dispatcher.notify_event(
            event_id=1,
            severity="HIGH",
            recipient="security@test.local",
            subject="Security Alert",
            message="Test intrusion detected",
        )
