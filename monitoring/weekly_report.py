from collections import Counter
import json
from pathlib import Path

from monitoring.camera_health_report import (
    generate_camera_health_report,
)
from monitoring.report import (
    generate_monitoring_report,
)


def _parse_timestamp(value):
    if value is None:
        return None

    from datetime import datetime

    parsed = datetime.fromisoformat(str(value))

    if parsed.tzinfo is None:
        raise ValueError(
            "weekly report timestamps must be timezone-aware"
        )

    return parsed


def _count_values(rows, field):
    return dict(
        sorted(
            Counter(
                row[field]
                for row in rows
                if row[field] is not None
            ).items()
        )
    )


def generate_weekly_operational_report(
    report_path,
    event_database,
    notification_database,
    audit_database,
    monitoring_database,
    camera_health_database,
    start_time,
    end_time,
):
    """
    Generate a weekly operational report for an explicit time window.

    The report combines existing persisted operational data without
    changing the underlying database or event lifecycle behavior.
    """

    if event_database is None:
        raise ValueError("event_database is required")

    if notification_database is None:
        raise ValueError("notification_database is required")

    if audit_database is None:
        raise ValueError("audit_database is required")

    if monitoring_database is None:
        raise ValueError("monitoring_database is required")

    if camera_health_database is None:
        raise ValueError("camera_health_database is required")

    period_start = _parse_timestamp(start_time)
    period_end = _parse_timestamp(end_time)

    if period_end <= period_start:
        raise ValueError(
            "end_time must be later than start_time"
        )

    start_iso = period_start.isoformat()
    end_iso = period_end.isoformat()

    events = event_database.get_events_in_window(
        start_time=start_iso,
        end_time=end_iso,
    )

    event_quality = (
        event_database.get_event_quality_metrics_in_window(
            start_time=start_iso,
            end_time=end_iso,
        )
    )

    notifications = (
        notification_database.get_notifications_in_window(
            start_time=start_iso,
            end_time=end_iso,
        )
    )

    audit_logs = audit_database.get_logs_in_window(
        start_time=start_iso,
        end_time=end_iso,
    )

    report_path = Path(report_path)

    temporary_monitoring_path = (
        report_path.with_suffix(".system_monitoring.json")
    )

    temporary_camera_health_path = (
        report_path.with_suffix(".camera_health.json")
    )

    system_monitoring = generate_monitoring_report(
        temporary_monitoring_path,
        monitoring_database,
        start_time=start_iso,
        end_time=end_iso,
    )

    camera_health = generate_camera_health_report(
        temporary_camera_health_path,
        camera_health_database,
        start_time=start_iso,
        end_time=end_iso,
    )

    event_rows = [
        dict(row)
        for row in events
    ]

    notification_rows = [
        dict(row)
        for row in notifications
    ]

    audit_rows = [
        dict(row)
        for row in audit_logs
    ]

    event_summary = {
        "total": len(event_rows),
        "by_event_type": _count_values(
            event_rows,
            "event_type",
        ),
        "by_camera": _count_values(
            event_rows,
            "camera_id",
        ),
        "by_severity": _count_values(
            event_rows,
            "severity",
        ),
    }

    report = {
        "report_type": "weekly_operational",
        "report_version": "1.0",
        "period": {
            "start_time": start_iso,
            "end_time": end_iso,
        },
        "system_monitoring": system_monitoring,
        "camera_health": camera_health,
        "events": event_summary,
        "event_quality": event_quality,
        "notifications": {
            "total": len(notification_rows),
            "by_status": _count_values(
                notification_rows,
                "status",
            ),
        },
        "audit": {
            "total": len(audit_rows),
            "by_action": _count_values(
                audit_rows,
                "action",
            ),
        },
    }

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    temporary_monitoring_path.unlink(
        missing_ok=True
    )

    temporary_camera_health_path.unlink(
        missing_ok=True
    )

    return report
