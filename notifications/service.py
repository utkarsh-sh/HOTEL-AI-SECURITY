from database.notification_database import NotificationDatabase
from notifications.providers import (
    NotificationMessage,
    NotificationProvider,
)
from notifications.rules import (
    get_notification_channels,
)


class NotificationService:

    def __init__(
        self,
        database: NotificationDatabase,
        providers: dict[str, NotificationProvider],
    ):
        self.database = database
        self.providers = providers

    # ==========================================================
    # DIRECT NOTIFICATION
    # ==========================================================

    def send_notification(
        self,
        event_id: int,
        severity: str,
        channel: str,
        recipient: str | None,
        subject: str,
        message: str,
    ):

        provider = self.providers.get(channel)

        if provider is None:
            raise ValueError(
                f"No notification provider configured for channel: {channel}"
            )

        notification_id = self.database.create_notification(
            event_id=event_id,
            channel=channel,
            severity=severity,
            provider=provider.provider_name,
            recipient=recipient,
        )

        notification = NotificationMessage(
            event_id=event_id,
            severity=severity,
            channel=channel,
            recipient=recipient,
            subject=subject,
            message=message,
        )

        result = provider.send(notification)

        if result.success:

            self.database.update_status(
                notification_id=notification_id,
                status="SENT",
            )

        else:

            self.database.increment_retry_count(
                notification_id=notification_id,
                error_message=result.error_message,
            )

        return {
            "notification_id": notification_id,
            "success": result.success,
            "provider": result.provider,
            "error_message": result.error_message,
        }

    # ==========================================================
    # EVENT NOTIFICATION DISPATCH
    # ==========================================================

    def notify_event(
        self,
        event_id: int,
        severity: str,
        recipient: str | None,
        subject: str,
        message: str,
    ):

        channels = get_notification_channels(
            severity
        )

        results = []

        for channel in channels:

            result = self.send_notification(
                event_id=event_id,
                severity=severity,
                channel=channel,
                recipient=recipient,
                subject=subject,
                message=message,
            )

            results.append(result)

        return results
