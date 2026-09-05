import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")


class UserDatabase:
    """
    Handles application users and their roles.
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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                username TEXT NOT NULL UNIQUE,

                password_hash TEXT NOT NULL,

                full_name TEXT NOT NULL,

                role TEXT NOT NULL,

                active INTEGER NOT NULL DEFAULT 1,

                created_at TEXT NOT NULL,

                updated_at TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def create_user(
        self,
        username,
        password_hash,
        full_name,
        role,
        active=True,
    ):
        now = datetime.now(
            timezone.utc
        ).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                role,
                active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                full_name,
                role,
                1 if active else 0,
                now,
                now,
            ),
        )

        self.connection.commit()

        return cursor.lastrowid

    def get_user_by_username(self, username):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,),
        )

        return cursor.fetchone()

    def get_user(self, user_id):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        )

        return cursor.fetchone()

    def get_all_users(self):
        cursor = self.connection.execute(
            """
            SELECT
                id,
                username,
                full_name,
                role,
                active,
                created_at,
                updated_at
            FROM users
            ORDER BY id
            """
        )

        return cursor.fetchall()

    def update_user_status(
        self,
        user_id,
        active,
    ):
        now = datetime.now(
            timezone.utc
        ).isoformat()

        self.connection.execute(
            """
            UPDATE users
            SET active = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                1 if active else 0,
                now,
                user_id,
            ),
        )

        self.connection.commit()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None