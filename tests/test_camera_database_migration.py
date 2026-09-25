from pathlib import Path
import sqlite3

from database.camera_database import CameraDatabase


def test_legacy_camera_schema_gets_runtime_configuration_columns(tmp_path):
    database_path = Path(tmp_path) / "legacy.db"

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE cameras (
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
    connection.commit()
    connection.close()

    database = CameraDatabase(database_path)

    columns = {
        row["name"]
        for row in database.connection.execute(
            "PRAGMA table_info(cameras)"
        ).fetchall()
    }

    assert {
        "source_type",
        "source",
        "ai_fps",
        "reconnect_max_attempts",
        "reconnect_delay_seconds",
    }.issubset(columns)

    database.close()
