import json
import sqlite3
from pathlib import Path


DATABASE_PATH = Path("database/hotel_security.db")


class MonitoringDatabase:
    """Persistence layer for system monitoring samples."""

    def __init__(self, database_path=DATABASE_PATH):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS system_resource_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_utilization_percent REAL NOT NULL,
                memory_utilization_percent REAL NOT NULL,
                disk_utilization_percent REAL NOT NULL,
                network_bytes_sent INTEGER NOT NULL,
                network_bytes_received INTEGER NOT NULL,
                gpu_available INTEGER NOT NULL,
                gpu_metrics_json TEXT NOT NULL,
                monitoring_status TEXT NOT NULL,
                threshold_checks_json TEXT NOT NULL,
                alerts_json TEXT NOT NULL
            )
            """
        )

        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_system_resource_samples_timestamp
            ON system_resource_samples(timestamp)
            """
        )

        self.connection.commit()

    def record_system_metrics(
        self,
        metrics,
        threshold_evaluation=None,
    ):
        """Persist one system resource snapshot."""

        gpu = metrics.get("gpu", {})
        gpu_metrics = gpu.get("gpus", [])

        if threshold_evaluation is None:
            threshold_evaluation = {
                "status": "OK",
                "checks": {},
                "alerts": [],
            }

        self.connection.execute(
            """
            INSERT INTO system_resource_samples (
                timestamp,
                cpu_utilization_percent,
                memory_utilization_percent,
                disk_utilization_percent,
                network_bytes_sent,
                network_bytes_received,
                gpu_available,
                gpu_metrics_json,
                monitoring_status,
                threshold_checks_json,
                alerts_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics["timestamp"],
                metrics["cpu"]["utilization_percent"],
                metrics["memory"]["utilization_percent"],
                metrics["disk"]["utilization_percent"],
                metrics["network"]["bytes_sent"],
                metrics["network"]["bytes_received"],
                1 if gpu.get("available", False) else 0,
                json.dumps(gpu_metrics),
                threshold_evaluation["status"],
                json.dumps(
                    threshold_evaluation.get(
                        "checks",
                        {},
                    )
                ),
                json.dumps(
                    threshold_evaluation.get(
                        "alerts",
                        [],
                    )
                ),
            ),
        )

        self.connection.commit()

    def get_system_samples(
        self,
        start_time=None,
        end_time=None,
    ):
        """Return persisted system samples within an optional time window."""

        query = """
            SELECT *
            FROM system_resource_samples
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
