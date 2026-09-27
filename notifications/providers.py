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

class WebhookNotificationProvider(NotificationProvider):

    def __init__(
        self,
        url: str,
        timeout_seconds: float = 5.0,
    ):
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than 0"
            )

        self.url = url.strip()
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "WEBHOOK"

    def send(
        self,
        notification: NotificationMessage,
    ) -> NotificationResult:

        import json
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        payload = {
            "event_id": notification.event_id,
            "severity": notification.severity,
            "channel": notification.channel,
            "recipient": notification.recipient,
            "subject": notification.subject,
            "message": notification.message,
        }

        request = Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:

                if not 200 <= response.status < 300:
                    return NotificationResult(
                        success=False,
                        provider=self.provider_name,
                        error_message=(
                            f"Webhook returned HTTP "
                            f"{response.status}"
                        ),
                    )

            return NotificationResult(
                success=True,
                provider=self.provider_name,
                sent_at=datetime.now(
                    timezone.utc
                ).isoformat(),
            )

        except HTTPError as exc:

            return NotificationResult(
                success=False,
                provider=self.provider_name,
                error_message=(
                    f"Webhook returned HTTP {exc.code}"
                ),
            )

        except (URLError, TimeoutError, OSError) as exc:

            return NotificationResult(
                success=False,
                provider=self.provider_name,
                error_message=str(exc),
            )
