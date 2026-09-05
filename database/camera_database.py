import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")


class CameraDatabase:

    def __init__(self, database_path=DATABASE_PATH):
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

    def _create_tables(self):

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OFFLINE',

                last_seen TEXT,

                fps REAL,
                width INTEGER,
                height INTEGER,

                consecutive_failures INTEGER NOT NULL DEFAULT 0,

                last_error TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def create_camera(
        self,
        camera_id,
        name,
        location,
        status="OFFLINE"
    ):
        now = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO cameras (
                camera_id,
                name,
                location,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                camera_id,
                name,
                location,
                status,
                now,
                now
            )
        )

        self.connection.commit()

    def get_camera(self, camera_id):

        cursor = self.connection.execute(
            """
            SELECT *
            FROM cameras
            WHERE camera_id = ?
            """,
            (camera_id,)
        )

        return cursor.fetchone()

    def get_all_cameras(self):

        cursor = self.connection.execute(
            """
            SELECT *
            FROM cameras
            ORDER BY camera_id
            """
        )

        return cursor.fetchall()

    def update_health(
        self,
        camera_id,
        status,
        fps=None,
        width=None,
        height=None,
        error=None,
        consecutive_failures=None,
    ):

        now = datetime.now(timezone.utc).isoformat()

        if status == "ONLINE":

            self.connection.execute(
                """
                UPDATE cameras
                SET
                    status = ?,
                    last_seen = ?,
                    fps = ?,
                    width = ?,
                    height = ?,
                    consecutive_failures = 0,
                    last_error = NULL,
                    updated_at = ?
                WHERE camera_id = ?
                """,
                (
                    status,
                    now,
                    fps,
                    width,
                    height,
                    now,
                    camera_id,
                ),
            )

        elif status == "OFFLINE":

            if consecutive_failures is None:
                consecutive_failures = 1

            self.connection.execute(
                """
                UPDATE cameras
                SET
                    status = ?,
                    consecutive_failures = ?,
                    last_error = ?,
                    updated_at = ?
                WHERE camera_id = ?
                """,
                (
                    status,
                    consecutive_failures,
                    error,
                    now,
                    camera_id,
                ),
            )

        else:

            raise ValueError(
                f"Unsupported camera status: {status}"
            )

        self.connection.commit()

    def record_failure(
        self,
        camera_id,
        consecutive_failures,
        error="No frame received",
    ):

        now = datetime.now(timezone.utc).isoformat()

        # Camera becomes OFFLINE after 3 consecutive failures.
        # Before that, keep it ONLINE but record the failures.
        status = (
            "OFFLINE"
            if consecutive_failures >= 3
            else "ONLINE"
        )

        self.connection.execute(
            """
            UPDATE cameras
            SET
                status = ?,
                consecutive_failures = ?,
                last_error = ?,
                updated_at = ?
            WHERE camera_id = ?
            """,
            (
                status,
                consecutive_failures,
                error,
                now,
                camera_id,
            ),
        )

        self.connection.commit()

    def delete_camera(self, camera_id):

        self.connection.execute(
            """
            DELETE FROM cameras
            WHERE camera_id = ?
            """,
            (camera_id,)
        )

        self.connection.commit()

    def close(self):

        if self.connection:
            self.connection.close()
            self.connection = None