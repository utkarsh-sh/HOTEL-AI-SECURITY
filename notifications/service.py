from database.notification_database import NotificationDatabase
from notifications.providers import (
    NotificationMessage,
    NotificationProvider,
    NotificationResult,
)
from notifications.rules import (
    get_notification_channels,
)


class NotificationService:

    def __init__(
        self,
        database: NotificationDatabase,
        providers: dict[str, NotificationProvider],
        max_retries: int = 2,
    ):
        if max_retries < 0:
            raise ValueError(
                "max_retries must be greater than or equal to 0"
            )

        self.database = database
        self.providers = providers
        self.max_retries = max_retries

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

        total_attempts = self.max_retries + 1
        final_result = None

        for attempt_number in range(1, total_attempts + 1):

            try:

                result = provider.send(notification)

                if not isinstance(result, NotificationResult):
                    raise TypeError(
                        "Notification provider must return "
                        "NotificationResult"
                    )

            except Exception as exc:

                result = NotificationResult(
                    success=False,
                    provider=provider.provider_name,
                    error_message=str(exc),
                )

            final_result = result

            if result.success:

                self.database.update_status(
                    notification_id=notification_id,
                    status="SENT",
                )

                return {
                    "notification_id": notification_id,
                    "success": True,
                    "provider": result.provider,
                    "error_message": None,
                    "attempts": attempt_number,
                }

            self.database.increment_retry_count(
                notification_id=notification_id,
                error_message=result.error_message,
            )

        return {
            "notification_id": notification_id,
            "success": False,
            "provider": final_result.provider,
            "error_message": final_result.error_message,
            "attempts": total_attempts,
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