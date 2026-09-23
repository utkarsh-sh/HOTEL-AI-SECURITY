from database.event_database import EventDatabase
from database.notification_database import NotificationDatabase
from notifications.dispatcher import NotificationDispatcher
from notifications.providers import (
    NotificationProvider,
    NotificationResult,
)


class RecordingProvider(NotificationProvider):
    provider_name = "recording"

    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)
        return NotificationResult(
            success=True,
            provider=self.provider_name,
            sent_at="2026-09-23T00:00:00",
        )


def test_fall_event_uses_existing_notification_dispatcher(tmp_path):
    database_path = tmp_path / "fall_notification.db"

    event_database = EventDatabase(database_path)

    event_id = event_database.create_event(
        event_type="FALL",
        severity="HIGH",
        camera_id="CAM-001",
        zone_id=None,
        zone_name=None,
        track_id=7,
        message="Potential person-down event detected",
        model_version="fall-heuristic-v1",
    )

    event_database.close()

    provider = RecordingProvider()

    dispatcher = NotificationDispatcher(
        providers={"CONSOLE": provider},
        database_path=database_path,
        max_workers=1,
        max_retries=0,
    )

    future = dispatcher.notify_event(
        event_id=event_id,
        severity="HIGH",
        recipient="security",
        subject="Potential FALL detected",
        message="Potential person-down event detected on CAM-001",
    )

    results = future.result(timeout=5)

    dispatcher.shutdown()

    assert len(results) == 1
    assert results[0]["success"] is True
    assert results[0]["provider"] == "recording"
    assert len(provider.messages) == 1

    notification_database = NotificationDatabase(
        database_path
    )

    notifications = [
        notification
        for notification in notification_database.get_all_notifications()
        if notification["event_id"] == event_id
    ]

    assert len(notifications) == 1

    notification = notifications[0]

    assert notification["event_id"] == event_id
    assert notification["severity"] == "HIGH"
    assert notification["channel"] == "CONSOLE"
    assert notification["provider"] == "recording"
    assert notification["status"] == "SENT"
    assert notification["retry_count"] == 0

    notification_database.close()
