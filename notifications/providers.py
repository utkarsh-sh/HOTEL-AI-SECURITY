from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime, timezone


@dataclass
class NotificationMessage:
    event_id: int
    severity: str
    channel: str
    recipient: str | None
    subject: str
    message: str


@dataclass
class NotificationResult:
    success: bool
    provider: str
    error_message: str | None = None
    sent_at: str | None = None


class NotificationProvider(ABC):

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def send(
        self,
        notification: NotificationMessage,
    ) -> NotificationResult:
        raise NotImplementedError


class ConsoleNotificationProvider(NotificationProvider):

    @property
    def provider_name(self) -> str:
        return "CONSOLE"

    def send(
        self,
        notification: NotificationMessage,
    ) -> NotificationResult:

        try:
            print(
                "\n"
                "========== SECURITY NOTIFICATION ==========\n"
                f"Event ID : {notification.event_id}\n"
                f"Severity : {notification.severity}\n"
                f"Channel  : {notification.channel}\n"
                f"Recipient: {notification.recipient}\n"
                f"Subject  : {notification.subject}\n"
                f"Message  : {notification.message}\n"
                "============================================"
            )

            sent_at = datetime.now(
                timezone.utc
            ).isoformat()

            return NotificationResult(
                success=True,
                provider=self.provider_name,
                sent_at=sent_at,
            )

        except Exception as exc:

            return NotificationResult(
                success=False,
                provider=self.provider_name,
                error_message=str(exc),
            )
