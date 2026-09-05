import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")


class AuditDatabase:
    """
    Stores an append-only record of important security-system actions.
    """

    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            self.database_path
        )

        self.connection.row_factory = sqlite3.Row

        self._create_tables()

    def _create_tables(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                action TEXT NOT NULL,

                entity_type TEXT NOT NULL,

                entity_id TEXT,

                actor TEXT NOT NULL,

                details TEXT,

                timestamp TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def create_log(
        self,
        action,
        entity_type,
        entity_id=None,
        actor="system",
        details=None,
    ):
        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO audit_logs (
                action,
                entity_type,
                entity_id,
                actor,
                details,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_type,
                str(entity_id)
                if entity_id is not None
                else None,
                actor,
                details,
                timestamp,
            ),
        )

        self.connection.commit()

        return cursor.lastrowid

    def get_all_logs(self):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM audit_logs
            ORDER BY id DESC
            """
        )

        return cursor.fetchall()

    def get_logs_for_entity(
        self,
        entity_type,
        entity_id,
    ):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM audit_logs
            WHERE entity_type = ?
              AND entity_id = ?
            ORDER BY id ASC
            """,
            (
                entity_type,
                str(entity_id),
            ),
        )

        return cursor.fetchall()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None