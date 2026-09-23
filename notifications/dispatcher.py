from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from database.notification_database import NotificationDatabase
from notifications.providers import NotificationProvider
from notifications.service import NotificationService


DEFAULT_DATABASE_PATH = Path(
    "database/hotel_security.db"
)


class NotificationDispatcher:
    """
    Bounded asynchronous notification delivery.

    Notification jobs execute independently from camera
    processing workers. Each notification job owns its own
    SQLite database connection.
    """

    def __init__(
        self,
        providers: dict[str, NotificationProvider],
        database_path=DEFAULT_DATABASE_PATH,
        max_workers: int = 2,
        max_retries: int = 2,
    ):
        if not isinstance(max_workers, int):
            raise TypeError(
                "max_workers must be an integer"
            )

        if max_workers < 1:
            raise ValueError(
                "max_workers must be >= 1"
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries must be >= 0"
            )

        if providers is None:
            raise ValueError(
                "providers must not be None"
            )

        if not isinstance(providers, dict):
            raise TypeError(
                "providers must be a dictionary"
            )

        self.providers = dict(providers)
        self.database_path = Path(database_path)
        self.max_retries = max_retries
        self.max_workers = max_workers

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="notification-worker",
        )

        self._shutdown = False

    # ==========================================================
    # ASYNCHRONOUS DISPATCH
    # ==========================================================

    def notify_event(
        self,
        event_id: int,
        severity: str,
        recipient: str | None,
        subject: str,
        message: str,
    ) -> Future:

        if self._shutdown:
            raise RuntimeError(
                "NotificationDispatcher has been shut down"
            )

        return self._executor.submit(
            self._deliver_notification,
            event_id,
            severity,
            recipient,
            subject,
            message,
        )

    # ==========================================================
    # BACKGROUND DELIVERY
    # ==========================================================

    def _deliver_notification(
        self,
        event_id: int,
        severity: str,
        recipient: str | None,
        subject: str,
        message: str,
    ):

        notification_database = None

        try:

            notification_database = NotificationDatabase(
                self.database_path
            )

            notification_service = NotificationService(
                database=notification_database,
                providers=self.providers,
                max_retries=self.max_retries,
            )

            return notification_service.notify_event(
                event_id=event_id,
                severity=severity,
                recipient=recipient,
                subject=subject,
                message=message,
            )

        finally:

            if notification_database is not None:
                notification_database.close()

    # ==========================================================
    # SHUTDOWN
    # ==========================================================

    def shutdown(
        self,
        wait: bool = True,
        cancel_futures: bool = False,
    ):
        """
        Shut down the notification executor.

        wait=True guarantees submitted notification jobs finish
        before shutdown returns.
        """

        if self._shutdown:
            return

        self._shutdown = True

        self._executor.shutdown(
            wait=wait,
            cancel_futures=cancel_futures,
        )