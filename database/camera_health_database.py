import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database/hotel_security.db")

VALID_STATUSES = {"ONLINE", "OFFLINE"}


class CameraHealthDatabase:
    """Persistence layer for historical camera health intervals."""

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
            CREATE TABLE IF NOT EXISTS camera_health_intervals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                successful_frames INTEGER NOT NULL DEFAULT 0,
                failed_frames INTEGER NOT NULL DEFAULT 0,
                source_fps REAL,
                observed_feed_rate REAL,
                created_at TEXT NOT NULL
            )
            """
        )

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_camera_health_intervals_camera_time
            ON camera_health_intervals(
                camera_id,
                start_time,
                end_time
            )
            """
        )

        self.connection.commit()

    @staticmethod
    def _validate_interval(
        camera_id,
        status,
        start_time,
        end_time,
        successful_frames,
        failed_frames,
        source_fps,
        observed_feed_rate,
    ):
        if not camera_id or not str(camera_id).strip():
            raise ValueError("camera_id is required")

        if status not in VALID_STATUSES:
            raise ValueError(
                f"Unsupported camera health status: {status}"
            )

        if not start_time:
            raise ValueError("start_time is required")

        if end_time is not None and end_time < start_time:
            raise ValueError(
                "end_time must not be earlier than start_time"
            )

        successful_frames = int(successful_frames)
        failed_frames = int(failed_frames)

        if successful_frames < 0:
            raise ValueError(
                "successful_frames must be >= 0"
            )

        if failed_frames < 0:
            raise ValueError(
                "failed_frames must be >= 0"
            )

        if source_fps is not None:
            source_fps = float(source_fps)
            if source_fps <= 0:
                raise ValueError(
                    "source_fps must be greater than 0"
                )

        if observed_feed_rate is not None:
            observed_feed_rate = float(
                observed_feed_rate
            )
            if observed_feed_rate < 0:
                raise ValueError(
                    "observed_feed_rate must be >= 0"
                )

        return (
            str(camera_id).strip(),
            status,
            str(start_time),
            None if end_time is None else str(end_time),
            successful_frames,
            failed_frames,
            source_fps,
            observed_feed_rate,
        )

    def record_interval(
        self,
        camera_id,
        status,
        start_time,
        end_time=None,
        successful_frames=0,
        failed_frames=0,
        source_fps=None,
        observed_feed_rate=None,
        created_at=None,
    ):
        """
        Persist one camera health interval.

        An interval may remain open by leaving end_time as None.
        """

        (
            camera_id,
            status,
            start_time,
            end_time,
            successful_frames,
            failed_frames,
            source_fps,
            observed_feed_rate,
        ) = self._validate_interval(
            camera_id=camera_id,
            status=status,
            start_time=start_time,
            end_time=end_time,
            successful_frames=successful_frames,
            failed_frames=failed_frames,
            source_fps=source_fps,
            observed_feed_rate=observed_feed_rate,
        )

        if created_at is None:
            from datetime import datetime, timezone

            created_at = datetime.now(
                timezone.utc
            ).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO camera_health_intervals (
                camera_id,
                status,
                start_time,
                end_time,
                successful_frames,
                failed_frames,
                source_fps,
                observed_feed_rate,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camera_id,
                status,
                start_time,
                end_time,
                successful_frames,
                failed_frames,
                source_fps,
                observed_feed_rate,
                str(created_at),
            ),
        )

        self.connection.commit()

        return cursor.lastrowid

    def update_open_interval(
        self,
        camera_id,
        successful_frames=None,
        failed_frames=None,
        source_fps=None,
        observed_feed_rate=None,
    ):
        """Update the currently open interval for a camera."""

        if not camera_id or not str(camera_id).strip():
            raise ValueError("camera_id is required")

        updates = []
        parameters = []

        if successful_frames is not None:
            successful_frames = int(successful_frames)
            if successful_frames < 0:
                raise ValueError(
                    "successful_frames must be >= 0"
                )
            updates.append("successful_frames = ?")
            parameters.append(successful_frames)

        if failed_frames is not None:
            failed_frames = int(failed_frames)
            if failed_frames < 0:
                raise ValueError(
                    "failed_frames must be >= 0"
                )
            updates.append("failed_frames = ?")
            parameters.append(failed_frames)

        if source_fps is not None:
            source_fps = float(source_fps)
            if source_fps <= 0:
                raise ValueError(
                    "source_fps must be greater than 0"
                )
            updates.append("source_fps = ?")
            parameters.append(source_fps)

        if observed_feed_rate is not None:
            observed_feed_rate = float(
                observed_feed_rate
            )
            if observed_feed_rate < 0:
                raise ValueError(
                    "observed_feed_rate must be >= 0"
                )
            updates.append("observed_feed_rate = ?")
            parameters.append(observed_feed_rate)

        if not updates:
            raise ValueError(
                "At least one interval field must be provided"
            )

        parameters.append(str(camera_id).strip())

        cursor = self.connection.execute(
            f"""
            UPDATE camera_health_intervals
            SET {", ".join(updates)}
            WHERE id = (
                SELECT id
                FROM camera_health_intervals
                WHERE camera_id = ?
                  AND end_time IS NULL
                ORDER BY start_time DESC, id DESC
                LIMIT 1
            )
            """,
            parameters,
        )

        self.connection.commit()

        return cursor.rowcount

    def close_open_interval(
        self,
        camera_id,
        end_time,
    ):
        """Close the currently open interval for a camera."""

        if not camera_id or not str(camera_id).strip():
            raise ValueError("camera_id is required")

        if not end_time:
            raise ValueError("end_time is required")

        cursor = self.connection.execute(
            """
            UPDATE camera_health_intervals
            SET end_time = ?
            WHERE id = (
                SELECT id
                FROM camera_health_intervals
                WHERE camera_id = ?
                  AND end_time IS NULL
                ORDER BY start_time DESC, id DESC
                LIMIT 1
            )
            """,
            (
                str(end_time),
                str(camera_id).strip(),
            ),
        )

        self.connection.commit()

        return cursor.rowcount

    def get_open_interval(self, camera_id):
        """Return the latest open interval for a camera, if present."""

        if not camera_id or not str(camera_id).strip():
            raise ValueError("camera_id is required")

        return self.connection.execute(
            "SELECT * FROM camera_health_intervals "
            "WHERE camera_id = ? "
            "AND end_time IS NULL "
            "ORDER BY start_time DESC, id DESC "
            "LIMIT 1",
            (str(camera_id).strip(),),
        ).fetchone()

    def get_intervals(
        self,
        camera_id=None,
        start_time=None,
        end_time=None,
    ):
        """Return historical camera-health intervals."""

        query = """
            SELECT *
            FROM camera_health_intervals
        """

        conditions = []
        parameters = []

        if camera_id is not None:
            conditions.append("camera_id = ?")
            parameters.append(camera_id)

        if start_time is not None:
            conditions.append(
                "(end_time IS NULL OR end_time >= ?)"
            )
            parameters.append(start_time)

        if end_time is not None:
            conditions.append("start_time <= ?")
            parameters.append(end_time)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY start_time ASC, id ASC
        """

        return self.connection.execute(
            query,
            parameters,
        ).fetchall()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
