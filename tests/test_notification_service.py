import sqlite3

import pytest

from database.notification_database import NotificationDatabase
from notifications.providers import (
    ConsoleNotificationProvider,
    NotificationMessage,
    NotificationProvider,
    NotificationResult,
)
from notifications.rules import get_notification_channels
from notifications.service import NotificationService


class FailingNotificationProvider(NotificationProvider):

    @property
    def provider_name(self) -> str:
        return "FAILING_TEST"

    def send(
        self,
        notification: NotificationMessage,
    ) -> NotificationResult:

        return NotificationResult(
            success=False,
            provider=self.provider_name,
            error_message="Simulated provider failure",
        )


class RetryThenSuccessProvider(NotificationProvider):

    def __init__(self):
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "RETRY_SUCCESS_TEST"

    def send(
        self,
        notification: NotificationMessage,
    ) -> NotificationResult:

        self.calls += 1

        if self.calls < 3:

            return NotificationResult(
                success=False,
                provider=self.provider_name,
                error_message=(
                    f"Simulated failure #{self.calls}"
                ),
            )

        return NotificationResult(
            success=True,
            provider=self.provider_name,
        )


class AlwaysFailingNotificationProvider(
    NotificationProvider
):

    def __init__(self):
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "ALWAYS_FAIL_TEST"

    def send(
        self,
        notification: NotificationMessage,
    ) -> NotificationResult:

        self.calls += 1

        return NotificationResult(
            success=False,
            provider=self.provider_name,
            error_message=(
                f"Simulated failure #{self.calls}"
            ),
        )


@pytest.fixture
def test_database(tmp_path):

    database_path = (
        tmp_path / "notification_test.db"
    )

    connection = sqlite3.connect(
        database_path
    )

    connection.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TEXT NOT NULL,
            workflow_version TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        INSERT INTO events (
            event_type,
            severity,
            status,
            camera_id,
            message,
            timestamp,
            created_at,
            workflow_version
        )
        VALUES (
            'INTRUSION',
            'HIGH',
            'NEW',
            'CAM-001',
            'Test intrusion',
            '2026-09-21T00:00:00+00:00',
            '2026-09-21T00:00:00+00:00',
            'workflow-v2'
        )
        """
    )

    connection.commit()
    connection.close()

    database = NotificationDatabase(
        database_path
    )

    yield database

    database.close()


def test_notification_rules():

    assert (
        get_notification_channels("CRITICAL")
        == ("CONSOLE",)
    )

    assert (
        get_notification_channels("HIGH")
        == ("CONSOLE",)
    )

    assert (
        get_notification_channels("MEDIUM")
        == ()
    )

    assert (
        get_notification_channels("LOW")
        == ()
    )

    assert (
        get_notification_channels("UNKNOWN")
        == ()
    )


def test_high_severity_event_is_sent(
    test_database,
):

    service = NotificationService(
        database=test_database,
        providers={
            "CONSOLE":
                ConsoleNotificationProvider(),
        },
    )

    results = service.notify_event(
        event_id=1,
        severity="HIGH",
        recipient="security-operator",
        subject="High Severity Alert",
        message="Person detected in restricted area.",
    )

    assert len(results) == 1
    assert results[0]["success"] is True
    assert results[0]["provider"] == "CONSOLE"
    assert results[0]["attempts"] == 1

    notification = test_database.get_notification(
        results[0]["notification_id"]
    )

    assert notification is not None
    assert notification["event_id"] == 1
    assert notification["severity"] == "HIGH"
    assert notification["channel"] == "CONSOLE"
    assert notification["status"] == "SENT"
    assert notification["retry_count"] == 0
    assert notification["sent_at"] is not None


def test_critical_severity_event_is_sent(
    test_database,
):

    service = NotificationService(
        database=test_database,
        providers={
            "CONSOLE":
                ConsoleNotificationProvider(),
        },
    )

    results = service.notify_event(
        event_id=1,
        severity="CRITICAL",
        recipient="security-operator",
        subject="Critical Security Alert",
        message="Critical test event.",
    )

    assert len(results) == 1
    assert results[0]["success"] is True

    notifications = (
        test_database.get_all_notifications()
    )

    assert len(notifications) == 1
    assert notifications[0]["severity"] == "CRITICAL"


@pytest.mark.parametrize(
    "severity",
    [
        "MEDIUM",
        "LOW",
        "UNKNOWN",
    ],
)
def test_non_alert_severity_creates_no_notification(
    test_database,
    severity,
):

    service = NotificationService(
        database=test_database,
        providers={
            "CONSOLE":
                ConsoleNotificationProvider(),
        },
    )

    results = service.notify_event(
        event_id=1,
        severity=severity,
        recipient="security-operator",
        subject="Test Alert",
        message="This should not notify.",
    )

    assert results == []

    assert (
        test_database.get_all_notifications()
        == []
    )


def test_provider_failure_is_recorded_without_retry(
    test_database,
):

    service = NotificationService(
        database=test_database,
        providers={
            "FAILING":
                FailingNotificationProvider(),
        },
        max_retries=0,
    )

    result = service.send_notification(
        event_id=1,
        severity="HIGH",
        channel="FAILING",
        recipient="security-operator",
        subject="Failure Test",
        message="This notification should fail.",
    )

    assert result["success"] is False
    assert result["provider"] == "FAILING_TEST"
    assert result["attempts"] == 1
    assert (
        result["error_message"]
        == "Simulated provider failure"
    )

    notification = test_database.get_notification(
        result["notification_id"]
    )

    assert notification is not None
    assert notification["status"] == "FAILED"
    assert notification["retry_count"] == 1
    assert (
        notification["error_message"]
        == "Simulated provider failure"
    )
    assert notification["sent_at"] is None


def test_provider_failure_is_retried_until_success(
    test_database,
):

    provider = RetryThenSuccessProvider()

    service = NotificationService(
        database=test_database,
        providers={
            "RETRY":
                provider,
        },
        max_retries=2,
    )

    result = service.send_notification(
        event_id=1,
        severity="HIGH",
        channel="RETRY",
        recipient="security-operator",
        subject="Retry Test",
        message="This should succeed on the third attempt.",
    )

    assert result["success"] is True
    assert result["provider"] == "RETRY_SUCCESS_TEST"
    assert result["attempts"] == 3
    assert result["error_message"] is None

    assert provider.calls == 3

    notification = test_database.get_notification(
        result["notification_id"]
    )

    assert notification is not None
    assert notification["status"] == "SENT"
    assert notification["retry_count"] == 2
    assert notification["sent_at"] is not None
    assert notification["error_message"] is None


def test_provider_failure_stops_after_retry_limit(
    test_database,
):

    provider = AlwaysFailingNotificationProvider()

    service = NotificationService(
        database=test_database,
        providers={
            "ALWAYS_FAIL":
                provider,
        },
        max_retries=2,
    )

    result = service.send_notification(
        event_id=1,
        severity="HIGH",
        channel="ALWAYS_FAIL",
        recipient="security-operator",
        subject="Retry Limit Test",
        message="This should fail after three attempts.",
    )

    assert result["success"] is False
    assert result["provider"] == "ALWAYS_FAIL_TEST"
    assert result["attempts"] == 3
    assert (
        result["error_message"]
        == "Simulated failure #3"
    )

    assert provider.calls == 3

    notification = test_database.get_notification(
        result["notification_id"]
    )

    assert notification is not None
    assert notification["status"] == "FAILED"
    assert notification["retry_count"] == 3
    assert (
        notification["error_message"]
        == "Simulated failure #3"
    )
    assert notification["sent_at"] is None


def test_missing_provider_is_rejected(
    test_database,
):

    service = NotificationService(
        database=test_database,
        providers={},
    )

    with pytest.raises(
        ValueError,
        match="No notification provider configured",
    ):

        service.send_notification(
            event_id=1,
            severity="HIGH",
            channel="SMS",
            recipient="security-operator",
            subject="Missing Provider",
            message="Provider does not exist.",
        )


def test_negative_retry_count_is_rejected(
    test_database,
):

    with pytest.raises(
        ValueError,
        match="max_retries",
    ):

        NotificationService(
            database=test_database,
            providers={},
            max_retries=-1,
        )