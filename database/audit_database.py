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
            self.database_path,
            timeout=10.0
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

    def get_logs_page(
        self,
        page=1,
        page_size=50,
        entity_type=None,
        entity_id=None,
    ):
        """Return a filtered, paginated page of audit logs."""

        offset = (page - 1) * page_size

        conditions = []
        parameters = []

        if entity_type is not None:
            conditions.append("entity_type = ?")
            parameters.append(entity_type)

        if entity_id is not None:
            conditions.append("entity_id = ?")
            parameters.append(str(entity_id))

        where_clause = ""

        if conditions:
            where_clause = (
                " WHERE " + " AND ".join(conditions)
            )

        total = self.connection.execute(
            f"""
            SELECT COUNT(*)
            FROM audit_logs
            {where_clause}
            """,
            parameters,
        ).fetchone()[0]

        rows = self.connection.execute(
            f"""
            SELECT *
            FROM audit_logs
            {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            parameters + [page_size, offset],
        ).fetchall()

        return {
            "total": total,
            "logs": [
                dict(row)
                for row in rows
            ],
        }
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

    def get_logs_in_window(
        self,
        start_time=None,
        end_time=None,
    ):
        """Return audit logs within an optional timestamp window."""

        query = """
            SELECT *
            FROM audit_logs
        """

        parameters = []
        conditions = []

        if start_time is not None:
            conditions.append("timestamp >= ?")
            parameters.append(start_time)

        if end_time is not None:
            conditions.append("timestamp <= ?")
            parameters.append(end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp ASC, id ASC"

        return self.connection.execute(
            query,
            parameters,
        ).fetchall()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
