import json
from datetime import datetime, timedelta, timezone

import pytest

from database.audit_database import AuditDatabase
from database.camera_health_database import CameraHealthDatabase
from database.event_database import EventDatabase
from database.monitoring_database import MonitoringDatabase
from database.notification_database import NotificationDatabase
from monitoring.weekly_report import (
    generate_weekly_operational_report,
)


def _timestamp(minutes):
    return (
        datetime(
            2026,
            9,
            20,
            10,
            0,
            tzinfo=timezone.utc,
        )
        + timedelta(minutes=minutes)
    ).isoformat()
    

def _create_databases(tmp_path):
    return (
        EventDatabase(tmp_path / "events.db"),
        NotificationDatabase(tmp_path / "notifications.db"),
        AuditDatabase(tmp_path / "audit.db"),
        MonitoringDatabase(tmp_path / "monitoring.db"),
        CameraHealthDatabase(tmp_path / "camera_health.db"),
    )


def test_weekly_report_aggregates_period_data(tmp_path):
    (
        event_db,
        notification_db,
        audit_db,
        monitoring_db,
        camera_health_db,
    ) = _create_databases(tmp_path)

    try:
        start = _timestamp(0)
        end = _timestamp(120)

        event_db.connection.execute(
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
                workflow_version,
                evidence_path,
                created_at,
                acknowledged_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INTRUSION",
                "HIGH",
                "RESOLVED",
                "CAM-001",
                None,
                None,
                None,
                "Test intrusion",
                _timestamp(30),
                "test-model",
                "test-workflow",
                None,
                _timestamp(30),
                _timestamp(32),
            ),
        )

        event_db.connection.execute(
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
                workflow_version,
                evidence_path,
                created_at,
                acknowledged_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "CROWDING",
                "MEDIUM",
                "FALSE_POSITIVE",
                "CAM-002",
                None,
                None,
                None,
                "Test crowding",
                _timestamp(60),
                "test-model",
                "test-workflow",
                None,
                _timestamp(60),
                None,
            ),
        )

        event_db.connection.execute(
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
                workflow_version,
                evidence_path,
                created_at,
                acknowledged_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "FIRE",
                "CRITICAL",
                "RESOLVED",
                "CAM-003",
                None,
                None,
                None,
                "Outside period",
                _timestamp(180),
                "test-model",
                "test-workflow",
                None,
                _timestamp(180),
                None,
            ),
        )

        event_db.connection.commit()

        notification_db.connection.execute(
            """
            INSERT INTO notifications (
                event_id,
                channel,
                recipient,
                severity,
                provider,
                status,
                retry_count,
                error_message,
                created_at,
                sent_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "CONSOLE",
                "operator",
                "HIGH",
                "console",
                "SENT",
                0,
                None,
                _timestamp(30),
                _timestamp(31),
                _timestamp(31),
            ),
        )

        notification_db.connection.execute(
            """
            INSERT INTO notifications (
                event_id,
                channel,
                recipient,
                severity,
                provider,
                status,
                retry_count,
                error_message,
                created_at,
                sent_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "CONSOLE",
                "operator",
                "MEDIUM",
                "console",
                "FAILED",
                1,
                "test failure",
                _timestamp(60),
                None,
                _timestamp(61),
            ),
        )

        notification_db.connection.execute(
            """
            INSERT INTO notifications (
                event_id,
                channel,
                recipient,
                severity,
                provider,
                status,
                retry_count,
                error_message,
                created_at,
                sent_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                3,
                "CONSOLE",
                "operator",
                "CRITICAL",
                "console",
                "SENT",
                0,
                None,
                _timestamp(180),
                _timestamp(181),
                _timestamp(181),
            ),
        )

        notification_db.connection.commit()

        audit_db.connection.execute(
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
                "ACKNOWLEDGE_EVENT",
                "EVENT",
                "1",
                "operator",
                "test",
                _timestamp(30),
            ),
        )

        audit_db.connection.execute(
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
                "RESOLVE_EVENT",
                "EVENT",
                "1",
                "operator",
                "test",
                _timestamp(90),
            ),
        )

        audit_db.connection.commit()

        monitoring_db.connection.execute(
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
                _timestamp(30),
                25.0,
                40.0,
                50.0,
                1000,
                2000,
                0,
                "{}",
                "OK",
                "{}",
                "[]",
            ),
        )

        monitoring_db.connection.commit()

        camera_health_db.record_interval(
            camera_id="CAM-001",
            status="ONLINE",
            start_time=_timestamp(0),
            end_time=_timestamp(120),
            successful_frames=120,
            failed_frames=0,
            source_fps=1.0,
            observed_feed_rate=1.0,
        )

        report_path = tmp_path / "weekly_report.json"

        report = generate_weekly_operational_report(
            report_path=report_path,
            event_database=event_db,
            notification_database=notification_db,
            audit_database=audit_db,
            monitoring_database=monitoring_db,
            camera_health_database=camera_health_db,
            start_time=start,
            end_time=end,
        )

        assert report_path.exists()

        written_report = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )

        assert written_report == report

        assert report["report_type"] == "weekly_operational"
        assert report["report_version"] == "1.1"

        assert report["period"]["start_time"] == start
        assert report["period"]["end_time"] == end

        assert report["events"]["total"] == 2
        assert report["events"]["by_event_type"] == {
            "CROWDING": 1,
            "INTRUSION": 1,
        }
        assert report["events"]["by_camera"] == {
            "CAM-001": 1,
            "CAM-002": 1,
        }
        assert report["events"]["by_severity"] == {
            "HIGH": 1,
            "MEDIUM": 1,
        }

        assert report["event_quality"]["total_events"] == 2
        assert report["event_quality"]["false_positive_events"] == 1
        assert report["event_quality"]["resolved_events"] == 1
        assert report["event_quality"]["reviewed_events"] == 2
        assert (
            report["event_quality"]["false_positive_rate_percent"]
            == 50.0
        )

        assert report["notifications"]["total"] == 2
        assert report["notifications"]["by_status"] == {
            "FAILED": 1,
            "SENT": 1,
        }

        assert report["notifications"]["acknowledgement"] == {
            "acknowledged_events": 1,
            "unacknowledged_events": 1,
            "mean_ms": 120000.0,
            "median_ms": 120000.0,
            "p95_ms": 120000.0,
            "max_ms": 120000.0,
        }

        assert report["audit"]["total"] == 2
        assert report["audit"]["by_action"] == {
            "ACKNOWLEDGE_EVENT": 1,
            "RESOLVE_EVENT": 1,
        }

        assert report["system_monitoring"]["sample_count"] == 1
        assert report["camera_health"]["camera_count"] == 1

        assert not (
            tmp_path / "weekly_report.system_monitoring.json"
        ).exists()

        assert not (
            tmp_path / "weekly_report.camera_health.json"
        ).exists()

    finally:
        event_db.close()
        notification_db.close()
        audit_db.close()
        monitoring_db.close()
        camera_health_db.close()


def test_weekly_report_rejects_reversed_period(tmp_path):
    (
        event_db,
        notification_db,
        audit_db,
        monitoring_db,
        camera_health_db,
    ) = _create_databases(tmp_path)

    try:
        with pytest.raises(
            ValueError,
            match="end_time must be later than start_time",
        ):
            generate_weekly_operational_report(
                report_path=tmp_path / "report.json",
                event_database=event_db,
                notification_database=notification_db,
                audit_database=audit_db,
                monitoring_database=monitoring_db,
                camera_health_database=camera_health_db,
                start_time=_timestamp(120),
                end_time=_timestamp(0),
            )
    finally:
        event_db.close()
        notification_db.close()
        audit_db.close()
        monitoring_db.close()
        camera_health_db.close()


def test_weekly_report_rejects_naive_timestamp(tmp_path):
    (
        event_db,
        notification_db,
        audit_db,
        monitoring_db,
        camera_health_db,
    ) = _create_databases(tmp_path)

    try:
        with pytest.raises(
            ValueError,
            match="timezone-aware",
        ):
            generate_weekly_operational_report(
                report_path=tmp_path / "report.json",
                event_database=event_db,
                notification_database=notification_db,
                audit_database=audit_db,
                monitoring_database=monitoring_db,
                camera_health_database=camera_health_db,
                start_time="2026-09-20T10:00:00",
                end_time="2026-09-20T12:00:00+00:00",
            )
    finally:
        event_db.close()
        notification_db.close()
        audit_db.close()
        monitoring_db.close()
        camera_health_db.close()
