from pathlib import Path

import pytest

from database.event_database import EventDatabase
from database.notification_database import NotificationDatabase
from notifications.providers import (
    NotificationMessage,
    NotificationProvider,
)
from notifications.service import NotificationService


class RecordingNotificationProvider(NotificationProvider):

    provider_name = "RECORDING_TEST"

    def __init__(self):
        self.messages = []

    def send(self, notification: NotificationMessage):
        self.messages.append(notification)

        from notifications.providers import NotificationResult

        return NotificationResult(
            success=True,
            provider=self.provider_name,
            error_message=None,
        )


class FailingNotificationProvider(NotificationProvider):

    provider_name = "FAILING_TEST"

    def send(self, notification: NotificationMessage):
        from notifications.providers import NotificationResult

        return NotificationResult(
            success=False,
            provider=self.provider_name,
            error_message="Simulated notification failure",
        )


@pytest.fixture
def databases(tmp_path):
    database_path = tmp_path / "stage20.db"

    event_database = EventDatabase(
        str(database_path)
    )

    notification_database = NotificationDatabase(
        str(database_path)
    )

    try:
        yield (
            event_database,
            notification_database,
        )
    finally:
        notification_database.close()
        event_database.close()


def create_event(event_database, severity="HIGH"):
    return event_database.create_event(
        event_type="INTRUSION",
        severity=severity,
        camera_id="CAM-001",
        zone_id="ZONE-001",
        zone_name="Restricted Area",
        track_id=42,
        message="Unauthorized entry detected",
        model_version="prototype-v1",
        evidence_path=None,
    )


def test_high_event_creates_notification(databases):

    event_database, notification_database = databases

    event_id = create_event(
        event_database,
        severity="HIGH",
    )

    provider = RecordingNotificationProvider()

    service = NotificationService(
        database=notification_database,
        providers={
            "CONSOLE": provider,
        },
    )

    results = service.notify_event(
        event_id=event_id,
        severity="HIGH",
        recipient=None,
        subject="Hotel Security Alert - INTRUSION",
        message="Camera CAM-001: Unauthorized entry detected",
    )

    assert len(results) == 1
    assert results[0]["success"] is True

    notifications = (
        notification_database.get_all_notifications()
    )

    assert len(notifications) == 1
    assert notifications[0]["event_id"] == event_id
    assert notifications[0]["severity"] == "HIGH"
    assert notifications[0]["status"] == "SENT"

    assert len(provider.messages) == 1
    assert (
        provider.messages[0].event_id
        == event_id
    )


def test_critical_event_creates_notification(databases):

    event_database, notification_database = databases

    event_id = create_event(
        event_database,
        severity="CRITICAL",
    )

    provider = RecordingNotificationProvider()

    service = NotificationService(
        database=notification_database,
        providers={
            "CONSOLE": provider,
        },
    )

    results = service.notify_event(
        event_id=event_id,
        severity="CRITICAL",
        recipient=None,
        subject="Critical Security Alert",
        message="Critical intrusion detected",
    )

    assert len(results) == 1
    assert results[0]["success"] is True

    notifications = (
        notification_database.get_all_notifications()
    )

    assert len(notifications) == 1
    assert notifications[0]["status"] == "SENT"


@pytest.mark.parametrize(
    "severity",
    [
        "MEDIUM",
        "LOW",
        "UNKNOWN",
    ],
)
def test_non_alert_severity_creates_no_notification(
    databases,
    severity,
):

    event_database, notification_database = databases

    event_id = create_event(
        event_database,
        severity=severity,
    )

    provider = RecordingNotificationProvider()

    service = NotificationService(
        database=notification_database,
        providers={
            "CONSOLE": provider,
        },
    )

    results = service.notify_event(
        event_id=event_id,
        severity=severity,
        recipient=None,
        subject="Security Event",
        message="Test event",
    )

    assert results == []

    notifications = (
        notification_database.get_all_notifications()
    )

    assert notifications == []

    assert provider.messages == []


def test_notification_failure_is_recorded(
    databases,
):

    event_database, notification_database = databases

    event_id = create_event(
        event_database,
        severity="HIGH",
    )

    provider = FailingNotificationProvider()

    service = NotificationService(
        database=notification_database,
        providers={
            "CONSOLE": provider,
        },
    )

    results = service.notify_event(
        event_id=event_id,
        severity="HIGH",
        recipient=None,
        subject="Hotel Security Alert",
        message="Test notification",
    )

    assert len(results) == 1
    assert results[0]["success"] is False

    notifications = (
        notification_database.get_all_notifications()
    )

    assert len(notifications) == 1

    notification = notifications[0]

    assert notification["event_id"] == event_id
    assert notification["status"] == "FAILED"
    assert notification["retry_count"] == 3
    assert (
        notification["error_message"]
        == "Simulated notification failure"
    )
