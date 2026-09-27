from collections import Counter
from datetime import datetime
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


def _calculate_acknowledgement_metrics(event_rows):
    durations_ms = []

    for row in event_rows:
        acknowledged_at = row.get("acknowledged_at")
        if not acknowledged_at:
            continue

        event_timestamp = row.get("timestamp")
        if not event_timestamp:
            continue

        event_time = datetime.fromisoformat(event_timestamp)
        acknowledged_time = datetime.fromisoformat(acknowledged_at)

        if event_time.tzinfo is None or acknowledged_time.tzinfo is None:
            raise ValueError(
                "event acknowledgement timestamps must be timezone-aware"
            )

        duration_ms = (
            acknowledged_time - event_time
        ).total_seconds() * 1000.0

        if duration_ms < 0:
            raise ValueError(
                "acknowledged_at cannot be earlier than event timestamp"
            )

        durations_ms.append(duration_ms)

    acknowledged_events = len(durations_ms)
    unacknowledged_events = len(event_rows) - acknowledged_events

    if not durations_ms:
        return {
            "acknowledged_events": 0,
            "unacknowledged_events": unacknowledged_events,
            "mean_ms": None,
            "median_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }

    ordered = sorted(durations_ms)

    def percentile(values, percentile_value):
        if len(values) == 1:
            return values[0]

        position = (len(values) - 1) * percentile_value
        lower = int(position)
        upper = lower + 1

        if upper >= len(values):
            return values[-1]

        fraction = position - lower
        return (
            values[lower]
            + (values[upper] - values[lower]) * fraction
        )

    return {
        "acknowledged_events": acknowledged_events,
        "unacknowledged_events": unacknowledged_events,
        "mean_ms": sum(durations_ms) / len(durations_ms),
        "median_ms": percentile(ordered, 0.50),
        "p95_ms": percentile(ordered, 0.95),
        "max_ms": max(durations_ms),
    }


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

    acknowledgement_metrics = _calculate_acknowledgement_metrics(
        event_rows
    )

    report = {
        "report_type": "weekly_operational",
        "report_version": "1.1",
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
            "acknowledgement": acknowledgement_metrics,
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
