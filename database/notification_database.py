import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")


class NotificationDatabase:

    def __init__(
        self,
        database_path=DATABASE_PATH
    ):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.connection = sqlite3.connect(
            self.database_path
        )

        self.connection.row_factory = sqlite3.Row

        self._create_tables()

    # ==========================================================
    # DATABASE SETUP
    # ==========================================================

    def _create_tables(self):

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_id INTEGER NOT NULL,

                channel TEXT NOT NULL,

                recipient TEXT,

                severity TEXT NOT NULL,

                provider TEXT NOT NULL,

                status TEXT NOT NULL DEFAULT 'PENDING',

                retry_count INTEGER NOT NULL DEFAULT 0,

                error_message TEXT,

                created_at TEXT NOT NULL,

                sent_at TEXT,

                updated_at TEXT NOT NULL,

                FOREIGN KEY (event_id)
                    REFERENCES events(id)
            )
            """
        )

        self.connection.commit()

    # ==========================================================
    # CREATE NOTIFICATION
    # ==========================================================

    def create_notification(
        self,
        event_id,
        channel,
        severity,
        provider,
        recipient=None,
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO notifications (
                event_id,
                channel,
                recipient,
                severity,
                provider,
                status,
                retry_count,
                error_message,
                created_at,
                sent_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'PENDING',
                0,
                NULL,
                ?,
                NULL,
                ?
            )
            """,
            (
                event_id,
                channel,
                recipient,
                severity,
                provider,
                timestamp,
                timestamp,
            )
        )

        self.connection.commit()

        return cursor.lastrowid

    # ==========================================================
    # GET NOTIFICATION
    # ==========================================================

    def get_notification(
        self,
        notification_id,
    ):

        row = self.connection.execute(
            """
            SELECT *
            FROM notifications
            WHERE id = ?
            """,
            (
                notification_id,
            )
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    # ==========================================================
    # GET ALL NOTIFICATIONS
    # ==========================================================

    def get_all_notifications(self):

        rows = self.connection.execute(
            """
            SELECT *
            FROM notifications
            ORDER BY id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ==========================================================
    # UPDATE STATUS
    # ==========================================================

    def update_status(
        self,
        notification_id,
        status,
        error_message=None,
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        sent_at = None

        if status == "SENT":
            sent_at = timestamp

        cursor = self.connection.execute(
            """
            UPDATE notifications
            SET
                status = ?,
                error_message = ?,
                sent_at = COALESCE(?, sent_at),
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                error_message,
                sent_at,
                timestamp,
                notification_id,
            )
        )

        self.connection.commit()

        return cursor.rowcount > 0

    # ==========================================================
    # INCREMENT RETRY COUNT
    # ==========================================================

    def increment_retry_count(
        self,
        notification_id,
        error_message=None,
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        cursor = self.connection.execute(
            """
            UPDATE notifications
            SET
                retry_count = retry_count + 1,
                status = 'FAILED',
                error_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                error_message,
                timestamp,
                notification_id,
            )
        )

        self.connection.commit()

        return cursor.rowcount > 0

    # ==========================================================
    # CLOSE
    # ==========================================================

    def close(self):

        self.connection.close()
