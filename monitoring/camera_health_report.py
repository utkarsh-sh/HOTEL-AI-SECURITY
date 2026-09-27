import json
from datetime import datetime
from pathlib import Path


def _parse_timestamp(value):
    if value is None:
        return None

    parsed = datetime.fromisoformat(str(value))

    if parsed.tzinfo is None:
        raise ValueError(
            "camera health timestamps must be timezone-aware"
        )

    return parsed


def _round(value):
    if value is None:
        return None

    return round(float(value), 6)


def _clip_interval(
    interval,
    period_start,
    period_end,
):
    interval_start = _parse_timestamp(
        interval["start_time"]
    )
    interval_end = _parse_timestamp(
        interval["end_time"]
    )

    effective_start = interval_start

    if period_start is not None:
        effective_start = max(
            effective_start,
            period_start,
        )

    effective_end = interval_end

    if effective_end is None:
        effective_end = period_end

    if period_end is not None:
        if effective_end is None:
            effective_end = period_end
        else:
            effective_end = min(
                effective_end,
                period_end,
            )

    if effective_end is None:
        return None

    duration = (
        effective_end - effective_start
    ).total_seconds()

    if duration <= 0:
        return None

    start_clipped = (
        effective_start != interval_start
    )

    end_clipped = (
        interval_end is not None
        and effective_end != interval_end
    )

    is_open_interval = interval_end is None

    return {
        "id": interval["id"],
        "camera_id": interval["camera_id"],
        "status": interval["status"],
        "start_time": interval_start.isoformat(),
        "end_time": (
            None
            if interval_end is None
            else interval_end.isoformat()
        ),
        "effective_start_time": effective_start.isoformat(),
        "effective_end_time": effective_end.isoformat(),
        "duration_seconds": duration,
        "successful_frames": int(
            interval["successful_frames"]
        ),
        "failed_frames": int(
            interval["failed_frames"]
        ),
        "source_fps": (
            None
            if interval["source_fps"] is None
            else float(interval["source_fps"])
        ),
        "observed_feed_rate": (
            None
            if interval["observed_feed_rate"] is None
            else float(interval["observed_feed_rate"])
        ),
        "was_clipped": (
            start_clipped
            or end_clipped
            or (
                is_open_interval
                and period_end is not None
            )
        ),
        "was_open_at_report_generation": (
            is_open_interval
        ),
    }


def _build_camera_summary(
    camera_id,
    intervals,
    period_start,
    period_end,
):
    clipped_intervals = []

    for interval in intervals:
        clipped = _clip_interval(
            interval,
            period_start,
            period_end,
        )

        if clipped is not None:
            clipped_intervals.append(clipped)

    if not clipped_intervals:
        return None

    observed_duration_seconds = sum(
        item["duration_seconds"]
        for item in clipped_intervals
    )

    online_duration_seconds = sum(
        item["duration_seconds"]
        for item in clipped_intervals
        if item["status"] == "ONLINE"
    )

    offline_duration_seconds = sum(
        item["duration_seconds"]
        for item in clipped_intervals
        if item["status"] == "OFFLINE"
    )

    successful_frames = sum(
        item["successful_frames"]
        for item in clipped_intervals
    )

    failed_frames = sum(
        item["failed_frames"]
        for item in clipped_intervals
    )

    if observed_duration_seconds > 0:
        uptime_percent = (
            online_duration_seconds
            / observed_duration_seconds
            * 100.0
        )
    else:
        uptime_percent = 0.0

    has_clipped_interval = any(
        item["was_clipped"]
        for item in clipped_intervals
    )

    if (
        observed_duration_seconds > 0
        and not has_clipped_interval
    ):
        observed_feed_rate = (
            successful_frames
            / observed_duration_seconds
        )
        feed_rate_status = "MEASURED"
    else:
        observed_feed_rate = None
        feed_rate_status = (
            "UNAVAILABLE_FOR_CLIPPED_INTERVALS"
            if has_clipped_interval
            else "UNAVAILABLE"
        )

    observed_start = min(
        item["effective_start_time"]
        for item in clipped_intervals
    )

    observed_end = max(
        item["effective_end_time"]
        for item in clipped_intervals
    )

    return {
        "camera_id": camera_id,
        "observed_period": {
            "start_time": observed_start,
            "end_time": observed_end,
        },
        "observed_duration_seconds": _round(
            observed_duration_seconds
        ),
        "online_duration_seconds": _round(
            online_duration_seconds
        ),
        "offline_duration_seconds": _round(
            offline_duration_seconds
        ),
        "uptime_percent": _round(
            uptime_percent
        ),
        "successful_frames": successful_frames,
        "failed_frames": failed_frames,
        "observed_feed_rate": _round(
            observed_feed_rate
        ),
        "feed_rate_status": feed_rate_status,
        "interval_count": len(
            clipped_intervals
        ),
        "intervals": clipped_intervals,
    }


def generate_camera_health_report(
    report_path,
    camera_health_database,
    camera_id=None,
    start_time=None,
    end_time=None,
):
    """
    Generate a JSON report of observed camera health history.

    The report describes only interval data actually persisted by
    CameraHealthHistoryService. It does not infer camera uptime
    before historical monitoring began.

    Feed rate is reported as measured only when all included
    intervals are complete and un-clipped. This avoids assigning
    full-interval frame counts to a partial reporting window.
    """

    if camera_health_database is None:
        raise ValueError(
            "camera_health_database is required"
        )

    period_start = _parse_timestamp(start_time)
    period_end = _parse_timestamp(end_time)

    if (
        period_start is not None
        and period_end is not None
        and period_end <= period_start
    ):
        raise ValueError(
            "end_time must be later than start_time"
        )

    rows = camera_health_database.get_intervals(
        camera_id=camera_id,
        start_time=(
            None
            if period_start is None
            else period_start.isoformat()
        ),
        end_time=(
            None
            if period_end is None
            else period_end.isoformat()
        ),
    )

    cameras = {}

    for row in rows:
        current_camera_id = row["camera_id"]

        cameras.setdefault(
            current_camera_id,
            [],
        ).append(row)

    camera_reports = []

    for current_camera_id in sorted(
        cameras
    ):
        summary = _build_camera_summary(
            current_camera_id,
            cameras[current_camera_id],
            period_start,
            period_end,
        )

        if summary is not None:
            camera_reports.append(summary)

    report = {
        "report_type": "camera_health",
        "camera_health_version": "1.0",
        "period": {
            "start_time": (
                None
                if period_start is None
                else period_start.isoformat()
            ),
            "end_time": (
                None
                if period_end is None
                else period_end.isoformat()
            ),
        },
        "camera_count": len(
            camera_reports
        ),
        "cameras": camera_reports,
    }

    report_path = Path(report_path)
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

    return report
