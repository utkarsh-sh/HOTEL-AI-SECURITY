import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")


class EventDatabase:

    def __init__(
        self,
        database_path=DATABASE_PATH
    ):
        self.database_path = Path(
            database_path
        )

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
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NEW',

                camera_id TEXT NOT NULL,

                zone_id TEXT,
                zone_name TEXT,

                track_id INTEGER,

                message TEXT NOT NULL,

                timestamp TEXT NOT NULL,

                model_version TEXT,

                evidence_path TEXT,

                created_at TEXT NOT NULL,

                acknowledged_at TEXT,
                dispatched_at TEXT,
                resolved_at TEXT,

                resolution TEXT
            )
            """
        )

        self.connection.commit()

        # --------------------------------------------------
        # Database migration
        # --------------------------------------------------
        # If the existing database was created before
        # evidence_path existed, add the column.
        # --------------------------------------------------

        columns = self.connection.execute(
            "PRAGMA table_info(events)"
        ).fetchall()

        column_names = {
            column["name"]
            for column in columns
        }

        if "evidence_path" not in column_names:

            self.connection.execute(
                """
                ALTER TABLE events
                ADD COLUMN evidence_path TEXT
                """
            )

            self.connection.commit()

    def create_event(
        self,
        event_type,
        severity,
        camera_id,
        zone_id,
        zone_name,
        track_id,
        message,
        model_version="prototype-v1",
        evidence_path=None,
    ):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        cursor = self.connection.execute(
            """
            INSERT INTO events (
                event_type,
                severity,
                status,
                camera_id,
                zone_id,
                zone_name,
                track_id,
                message,
                timestamp,
                model_version,
                evidence_path,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                event_type,
                severity,
                "NEW",
                camera_id,
                zone_id,
                zone_name,
                track_id,
                message,
                timestamp,
                model_version,
                evidence_path,
                timestamp,
            )
        )

        self.connection.commit()

        return cursor.lastrowid

    def update_evidence_path(
        self,
        event_id,
        evidence_path,
    ):

        self.connection.execute(
            """
            UPDATE events
            SET evidence_path = ?
            WHERE id = ?
            """,
            (
                evidence_path,
                event_id,
            )
        )

        self.connection.commit()

    def get_event(
        self,
        event_id
    ):

        cursor = self.connection.execute(
            """
            SELECT *
            FROM events
            WHERE id = ?
            """,
            (event_id,)
        )

        return cursor.fetchone()

    def get_all_events(self):

        cursor = self.connection.execute(
            """
            SELECT *
            FROM events
            ORDER BY id DESC
            """
        )

        return cursor.fetchall()

    def update_status(
        self,
        event_id,
        status,
        resolution=None
    ):

        now = datetime.now(
            timezone.utc
        ).isoformat()

        if status == "ACKNOWLEDGED":

            self.connection.execute(
                """
                UPDATE events
                SET
                    status = ?,
                    acknowledged_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    event_id,
                )
            )

        elif status == "DISPATCHED":

            self.connection.execute(
                """
                UPDATE events
                SET
                    status = ?,
                    dispatched_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    event_id,
                )
            )

        elif status == "RESOLVED":

            self.connection.execute(
                """
                UPDATE events
                SET
                    status = ?,
                    resolved_at = ?,
                    resolution = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    resolution,
                    event_id,
                )
            )

        elif status == "FALSE_POSITIVE":

            self.connection.execute(
                """
                UPDATE events
                SET
                    status = ?,
                    resolved_at = ?,
                    resolution = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    resolution,
                    event_id,
                )
            )

        else:

            raise ValueError(
                f"Unsupported event status: {status}"
            )

        self.connection.commit()

    def close(self):

        if self.connection:

            self.connection.close()

            self.connection = None