import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DATABASE_PATH = Path("database/hotel_security.db")
ZONE_BOOTSTRAP_METADATA_KEY = "zone_configuration_initialized"


class ZoneDatabase:
    """Persistence for camera-scoped polygon security zones."""

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
            CREATE TABLE IF NOT EXISTS zones (
                zone_id TEXT PRIMARY KEY,
                camera_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                points TEXT NOT NULL,
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

    @staticmethod
    def _normalize_points(points):
        if not isinstance(points, (list, tuple)):
            raise ValueError("zone points must be a list")
        if len(points) < 3:
            raise ValueError("zone polygon must contain at least 3 points")

        normalized = []
        for index, point in enumerate(points):
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(
                    f"zone point {index} must contain exactly 2 coordinates"
                )
            try:
                x = float(point[0])
                y = float(point[1])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"zone point {index} must contain numeric coordinates"
                ) from error

            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(
                    f"zone point {index} must contain finite coordinates"
                )
            normalized.append([x, y])

        area = 0.0
        for index, point in enumerate(normalized):
            next_point = normalized[(index + 1) % len(normalized)]
            area += (
                point[0] * next_point[1]
                - next_point[0] * point[1]
            )

        if abs(area) < 1e-9:
            raise ValueError(
                "zone polygon must enclose a non-zero area"
            )
        return normalized

    @classmethod
    def _normalize_zone(
        cls,
        zone_id,
        camera_id,
        name,
        zone_type,
        points,
    ):
        zone_id = str(zone_id or "").strip()
        camera_id = str(camera_id or "").strip()
        name = str(name or "").strip()
        zone_type = str(zone_type or "").strip()

        if not zone_id:
            raise ValueError("zone_id is required")
        if not camera_id:
            raise ValueError("camera_id is required")
        if not name:
            raise ValueError("zone name is required")
        if not zone_type:
            raise ValueError("zone type is required")

        return (
            zone_id,
            camera_id,
            name,
            zone_type,
            cls._normalize_points(points),
        )

    def initialize_from_bootstrap(self, zones):
        """Bootstrap from JSON once; DB remains authoritative afterwards."""
        if self.get_metadata(ZONE_BOOTSTRAP_METADATA_KEY) == "1":
            return

        for zone in zones:
            if not isinstance(zone, dict):
                raise ValueError("Each bootstrap zone must be an object")
            zone_id = str(zone.get("zone_id") or "").strip()
            if not zone_id:
                raise ValueError("Bootstrap zone is missing 'zone_id'")
            if self.get_zone(zone_id) is not None:
                continue

            self.create_zone(
                zone_id=zone_id,
                camera_id=zone.get("camera_id"),
                name=zone.get("name"),
                zone_type=zone.get("type"),
                points=zone.get("points"),
            )

        self.set_metadata(ZONE_BOOTSTRAP_METADATA_KEY, "1")

    def create_zone(
        self,
        zone_id,
        camera_id,
        name,
        zone_type,
        points,
    ):
        (
            zone_id,
            camera_id,
            name,
            zone_type,
            points,
        ) = self._normalize_zone(
            zone_id,
            camera_id,
            name,
            zone_type,
            points,
        )

        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            INSERT INTO zones (
                zone_id,
                camera_id,
                name,
                type,
                points,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                zone_id,
                camera_id,
                name,
                zone_type,
                json.dumps(points, separators=(",", ":")),
                now,
                now,
            ),
        )
        self.connection.commit()

    def get_zone(self, zone_id):
        return self.connection.execute(
            """
            SELECT *
            FROM zones
            WHERE zone_id = ?
            """,
            (zone_id,),
        ).fetchone()

    def _decode_zone(self, row):
        if row is None:
            return None
        data = dict(row)
        try:
            data["points"] = json.loads(data["points"])
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"Zone {data['zone_id']} contains invalid polygon data"
            ) from error
        return data

    def get_zone_data(self, zone_id):
        return self._decode_zone(self.get_zone(zone_id))

    def get_all_zones(self):
        rows = self.connection.execute(
            """
            SELECT *
            FROM zones
            ORDER BY camera_id, zone_id
            """
        ).fetchall()
        return [self._decode_zone(row) for row in rows]

    def get_zones_for_camera(self, camera_id):
        rows = self.connection.execute(
            """
            SELECT *
            FROM zones
            WHERE camera_id = ?
            ORDER BY zone_id
            """,
            (camera_id,),
        ).fetchall()
        return [self._decode_zone(row) for row in rows]

    def update_zone(
        self,
        zone_id,
        camera_id,
        name,
        zone_type,
        points,
    ):
        if self.get_zone(zone_id) is None:
            raise ValueError(f"Zone not found: {zone_id}")

        (
            normalized_zone_id,
            camera_id,
            name,
            zone_type,
            points,
        ) = self._normalize_zone(
            zone_id,
            camera_id,
            name,
            zone_type,
            points,
        )

        now = datetime.now(timezone.utc).isoformat()
        self.connection.execute(
            """
            UPDATE zones
            SET
                camera_id = ?,
                name = ?,
                type = ?,
                points = ?,
                updated_at = ?
            WHERE zone_id = ?
            """,
            (
                camera_id,
                name,
                zone_type,
                json.dumps(points, separators=(",", ":")),
                now,
                normalized_zone_id,
            ),
        )
        self.connection.commit()
        return self.get_zone_data(zone_id)

    def delete_zone(self, zone_id):
        if self.get_zone(zone_id) is None:
            raise ValueError(f"Zone not found: {zone_id}")

        self.connection.execute(
            """
            DELETE FROM zones
            WHERE zone_id = ?
            """,
            (zone_id,),
        )
        self.connection.commit()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None
