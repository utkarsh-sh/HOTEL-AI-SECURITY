import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("database/hotel_security.db")

VALID_SOURCE_TYPES = {"file", "rtsp"}
BOOTSTRAP_METADATA_KEY = "camera_configuration_initialized"


class CameraDatabase:
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
        self._migrate_camera_configuration_columns()

    def _create_tables(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT NOT NULL,

                source_type TEXT NOT NULL DEFAULT 'file',
                source TEXT NOT NULL DEFAULT '',
                ai_fps REAL NOT NULL DEFAULT 5.0,
                reconnect_max_attempts INTEGER NOT NULL DEFAULT 3,
                reconnect_delay_seconds REAL NOT NULL DEFAULT 1.0,

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

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS system_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        self.connection.commit()

    def _migrate_camera_configuration_columns(self):
        existing_columns = {
            row["name"]
            for row in self.connection.execute(
                "PRAGMA table_info(cameras)"
            ).fetchall()
        }

        required_columns = {
            "source_type": "TEXT NOT NULL DEFAULT 'file'",
            "source": "TEXT NOT NULL DEFAULT ''",
            "ai_fps": "REAL NOT NULL DEFAULT 5.0",
            "reconnect_max_attempts": (
                "INTEGER NOT NULL DEFAULT 3"
            ),
            "reconnect_delay_seconds": (
                "REAL NOT NULL DEFAULT 1.0"
            ),
        }

        for column_name, definition in required_columns.items():
            if column_name in existing_columns:
                continue

            self.connection.execute(
                f"ALTER TABLE cameras "
                f"ADD COLUMN {column_name} {definition}"
            )

        self.connection.commit()

    @staticmethod
    def _validate_configuration(
        source_type,
        source,
        ai_fps,
        reconnect_max_attempts,
        reconnect_delay_seconds,
    ):
        normalized_source_type = str(
            source_type
        ).strip().lower()

        if normalized_source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported camera source_type: {source_type}"
            )

        normalized_source = str(source).strip()

        if not normalized_source:
            raise ValueError(
                "camera source is required"
            )

        ai_fps = float(ai_fps)
        if ai_fps <= 0:
            raise ValueError(
                "ai_fps must be greater than 0"
            )

        reconnect_max_attempts = int(
            reconnect_max_attempts
        )
        if reconnect_max_attempts < 0:
            raise ValueError(
                "reconnect_max_attempts must be >= 0"
            )

        reconnect_delay_seconds = float(
            reconnect_delay_seconds
        )
        if reconnect_delay_seconds < 0:
            raise ValueError(
                "reconnect_delay_seconds must be >= 0"
            )

        return (
            normalized_source_type,
            normalized_source,
            ai_fps,
            reconnect_max_attempts,
            reconnect_delay_seconds,
        )

    def get_metadata(self, key):
        row = self.connection.execute(
            """
            SELECT value
            FROM system_metadata
            WHERE key = ?
            """,
            (key,),
        ).fetchone()

        return None if row is None else row["value"]

    def set_metadata(self, key, value):
        self.connection.execute(
            """
            INSERT INTO system_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )
        self.connection.commit()

    def initialize_from_bootstrap(self, camera_configs):
        """
        One-time bootstrap/backfill from configs/cameras.json.

        The database becomes authoritative after the bootstrap marker is
        written. Later ADMIN-created, updated, or deleted cameras are not
        silently overwritten by the JSON seed file.
        """

        if self.get_metadata(BOOTSTRAP_METADATA_KEY) == "1":
            return

        for camera_config in camera_configs:
            existing = self.get_camera(
                camera_config.camera_id
            )

            if existing is None:
                self.create_camera(
                    camera_id=camera_config.camera_id,
                    name=camera_config.name,
                    location=camera_config.location,
                    source_type=camera_config.source_type,
                    source=camera_config.source,
                    ai_fps=camera_config.ai_fps,
                    reconnect_max_attempts=(
                        camera_config.reconnect.max_attempts
                    ),
                    reconnect_delay_seconds=(
                        camera_config.reconnect.delay_seconds
                    ),
                )
            elif not str(existing["source"] or "").strip():
                self.update_camera_configuration(
                    camera_id=camera_config.camera_id,
                    name=existing["name"],
                    location=existing["location"],
                    source_type=camera_config.source_type,
                    source=camera_config.source,
                    ai_fps=camera_config.ai_fps,
                    reconnect_max_attempts=(
                        camera_config.reconnect.max_attempts
                    ),
                    reconnect_delay_seconds=(
                        camera_config.reconnect.delay_seconds
                    ),
                )

        self.set_metadata(
            BOOTSTRAP_METADATA_KEY,
            "1",
        )

    def create_camera(
        self,
        camera_id,
        name,
        location,
        status="OFFLINE",
        source_type="file",
        source="",
        ai_fps=5.0,
        reconnect_max_attempts=3,
        reconnect_delay_seconds=1.0,
    ):
        if not camera_id or not str(camera_id).strip():
            raise ValueError(
                "camera_id is required"
            )

        if not name or not str(name).strip():
            raise ValueError(
                "camera name is required"
            )

        if not location or not str(location).strip():
            raise ValueError(
                "camera location is required"
            )

        if status not in {
            "ONLINE",
            "OFFLINE",
        }:
            raise ValueError(
                f"Unsupported camera status: {status}"
            )

        normalized_source_type = str(
            source_type
        ).strip().lower()

        if normalized_source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported camera source_type: {source_type}"
            )

        if source:
            (
                source_type,
                source,
                ai_fps,
                reconnect_max_attempts,
                reconnect_delay_seconds,
            ) = self._validate_configuration(
                source_type=normalized_source_type,
                source=source,
                ai_fps=ai_fps,
                reconnect_max_attempts=reconnect_max_attempts,
                reconnect_delay_seconds=reconnect_delay_seconds,
            )
        else:
            source_type = normalized_source_type
            ai_fps = float(ai_fps)
            reconnect_max_attempts = int(
                reconnect_max_attempts
            )
            reconnect_delay_seconds = float(
                reconnect_delay_seconds
            )

            if ai_fps <= 0:
                raise ValueError(
                    "ai_fps must be greater than 0"
                )

            if reconnect_max_attempts < 0:
                raise ValueError(
                    "reconnect_max_attempts must be >= 0"
                )

            if reconnect_delay_seconds < 0:
                raise ValueError(
                    "reconnect_delay_seconds must be >= 0"
                )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        self.connection.execute(
            """
            INSERT INTO cameras (
                camera_id,
                name,
                location,
                source_type,
                source,
                ai_fps,
                reconnect_max_attempts,
                reconnect_delay_seconds,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(camera_id).strip(),
                str(name).strip(),
                str(location).strip(),
                source_type,
                source,
                ai_fps,
                reconnect_max_attempts,
                reconnect_delay_seconds,
                status,
                now,
                now,
            ),
        )

        self.connection.commit()

    def get_camera(self, camera_id):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM cameras
            WHERE camera_id = ?
            """,
            (camera_id,),
        )

        return cursor.fetchone()

    def ensure_camera(
        self,
        camera_id,
        name,
        location,
        source_type="file",
        source="",
        ai_fps=5.0,
        reconnect_max_attempts=3,
        reconnect_delay_seconds=1.0,
    ):
        """Backward-compatible bootstrap helper."""
        existing = self.get_camera(camera_id)

        if existing is None:
            self.create_camera(
                camera_id=camera_id,
                name=name,
                location=location,
                status="OFFLINE",
                source_type=source_type,
                source=source,
                ai_fps=ai_fps,
                reconnect_max_attempts=reconnect_max_attempts,
                reconnect_delay_seconds=reconnect_delay_seconds,
            )
            return self.get_camera(camera_id)

        if not str(existing["source"] or "").strip() and str(
            source or ""
        ).strip():
            self.update_camera_configuration(
                camera_id=camera_id,
                name=existing["name"],
                location=existing["location"],
                source_type=source_type,
                source=source,
                ai_fps=ai_fps,
                reconnect_max_attempts=reconnect_max_attempts,
                reconnect_delay_seconds=reconnect_delay_seconds,
            )

        return self.get_camera(camera_id)

    def get_all_cameras(self):
        cursor = self.connection.execute(
            """
            SELECT *
            FROM cameras
            ORDER BY camera_id
            """
        )

        return cursor.fetchall()

    def update_camera_configuration(
        self,
        camera_id,
        name,
        location,
        source_type,
        source,
        ai_fps,
        reconnect_max_attempts,
        reconnect_delay_seconds,
    ):
        if not name or not str(name).strip():
            raise ValueError(
                "camera name is required"
            )

        if not location or not str(location).strip():
            raise ValueError(
                "camera location is required"
            )

        (
            source_type,
            source,
            ai_fps,
            reconnect_max_attempts,
            reconnect_delay_seconds,
        ) = self._validate_configuration(
            source_type=source_type,
            source=source,
            ai_fps=ai_fps,
            reconnect_max_attempts=reconnect_max_attempts,
            reconnect_delay_seconds=reconnect_delay_seconds,
        )

        if self.get_camera(camera_id) is None:
            raise ValueError(
                f"Camera not found: {camera_id}"
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        self.connection.execute(
            """
            UPDATE cameras
            SET
                name = ?,
                location = ?,
                source_type = ?,
                source = ?,
                ai_fps = ?,
                reconnect_max_attempts = ?,
                reconnect_delay_seconds = ?,
                updated_at = ?
            WHERE camera_id = ?
            """,
            (
                str(name).strip(),
                str(location).strip(),
                source_type,
                source,
                ai_fps,
                reconnect_max_attempts,
                reconnect_delay_seconds,
                now,
                camera_id,
            ),
        )

        self.connection.commit()

        return self.get_camera(camera_id)

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
        if status not in {
            "ONLINE",
            "OFFLINE",
        }:
            raise ValueError(
                f"Unsupported camera status: {status}"
            )

        if self.get_camera(camera_id) is None:
            raise ValueError(
                f"Camera not found: {camera_id}"
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

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
        else:
            if consecutive_failures is None:
                consecutive_failures = 1

            if consecutive_failures < 1:
                raise ValueError(
                    "consecutive_failures must be at least 1"
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

    def record_failure(
        self,
        camera_id,
        consecutive_failures,
        error="No frame received",
        failure_threshold=3,
    ):
        if failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be at least 1"
            )

        if consecutive_failures < 1:
            raise ValueError(
                "consecutive_failures must be at least 1"
            )

        if self.get_camera(camera_id) is None:
            raise ValueError(
                f"Camera not found: {camera_id}"
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        status = (
            "OFFLINE"
            if consecutive_failures >= failure_threshold
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
        if self.get_camera(camera_id) is None:
            raise ValueError(
                f"Camera not found: {camera_id}"
            )

        self.connection.execute(
            """
            DELETE FROM cameras
            WHERE camera_id = ?
            """,
            (camera_id,),
        )

        self.connection.commit()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
