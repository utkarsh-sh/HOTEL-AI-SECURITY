from datetime import datetime, timedelta, timezone
import json

from database.camera_health_database import CameraHealthDatabase
from monitoring.camera_health_report import (
    generate_camera_health_report,
)


def record_interval(
    database,
    camera_id,
    status,
    start_time,
    end_time,
    successful_frames,
    failed_frames,
    source_fps=1.0,
):
    database.record_interval(
        camera_id=camera_id,
        status=status,
        start_time=start_time.isoformat(),
        end_time=(
            None
            if end_time is None
            else end_time.isoformat()
        ),
        successful_frames=successful_frames,
        failed_frames=failed_frames,
        source_fps=source_fps,
        observed_feed_rate=1.0,
    )


def test_camera_health_report_single_online_interval(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )
    end = start + timedelta(seconds=10)

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        start,
        end,
        10,
        0,
    )

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
    )

    camera = report["cameras"][0]

    assert report["report_type"] == "camera_health"
    assert report["camera_health_version"] == "1.0"
    assert report["camera_count"] == 1
    assert camera["camera_id"] == "CAM-001"
    assert camera["observed_duration_seconds"] == 10.0
    assert camera["online_duration_seconds"] == 10.0
    assert camera["offline_duration_seconds"] == 0.0
    assert camera["uptime_percent"] == 100.0
    assert camera["successful_frames"] == 10
    assert camera["failed_frames"] == 0
    assert camera["observed_feed_rate"] == 1.0
    assert camera["feed_rate_status"] == "MEASURED"

    database.close()


def test_camera_health_report_online_offline_recovery(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )

    online_end = start + timedelta(seconds=10)
    offline_end = start + timedelta(seconds=15)
    recovery_end = start + timedelta(seconds=25)

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        start,
        online_end,
        10,
        3,
    )

    record_interval(
        database,
        "CAM-001",
        "OFFLINE",
        online_end,
        offline_end,
        0,
        3,
    )

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        offline_end,
        recovery_end,
        10,
        0,
    )

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
    )

    camera = report["cameras"][0]

    assert camera["observed_duration_seconds"] == 25.0
    assert camera["online_duration_seconds"] == 20.0
    assert camera["offline_duration_seconds"] == 5.0
    assert camera["uptime_percent"] == 80.0
    assert camera["successful_frames"] == 20
    assert camera["failed_frames"] == 6
    assert camera["observed_feed_rate"] == 0.8
    assert camera["feed_rate_status"] == "MEASURED"
    assert camera["interval_count"] == 3

    database.close()


def test_camera_health_report_clips_requested_period(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )
    end = start + timedelta(seconds=20)

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        start,
        end,
        20,
        0,
    )

    report_start = start + timedelta(seconds=5)
    report_end = start + timedelta(seconds=15)

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
        start_time=report_start.isoformat(),
        end_time=report_end.isoformat(),
    )

    camera = report["cameras"][0]

    assert camera["observed_duration_seconds"] == 10.0
    assert camera["online_duration_seconds"] == 10.0
    assert camera["uptime_percent"] == 100.0

    assert camera["successful_frames"] == 20
    assert camera["failed_frames"] == 0

    assert camera["observed_feed_rate"] is None
    assert (
        camera["feed_rate_status"]
        == "UNAVAILABLE_FOR_CLIPPED_INTERVALS"
    )

    assert camera["intervals"][0][
        "was_clipped"
    ] is True

    assert camera["intervals"][0][
        "effective_start_time"
    ] == report_start.isoformat()

    assert camera["intervals"][0][
        "effective_end_time"
    ] == report_end.isoformat()

    database.close()


def test_camera_health_report_does_not_count_gaps_as_observed_time(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )

    first_end = start + timedelta(seconds=10)
    second_start = start + timedelta(seconds=30)
    second_end = start + timedelta(seconds=40)

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        start,
        first_end,
        10,
        0,
    )

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        second_start,
        second_end,
        10,
        0,
    )

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
    )

    camera = report["cameras"][0]

    assert camera["observed_duration_seconds"] == 20.0
    assert camera["online_duration_seconds"] == 20.0
    assert camera["offline_duration_seconds"] == 0.0
    assert camera["uptime_percent"] == 100.0
    assert camera["successful_frames"] == 20
    assert camera["observed_feed_rate"] == 1.0
    assert camera["feed_rate_status"] == "MEASURED"

    database.close()


def test_camera_health_report_multiple_cameras(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )
    end = start + timedelta(seconds=10)

    record_interval(
        database,
        "CAM-002",
        "ONLINE",
        start,
        end,
        10,
        0,
    )

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        start,
        end,
        5,
        0,
    )

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
    )

    assert report["camera_count"] == 2
    assert [
        camera["camera_id"]
        for camera in report["cameras"]
    ] == [
        "CAM-001",
        "CAM-002",
    ]

    database.close()


def test_camera_health_report_open_interval_with_end_time(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time=start.isoformat(),
        end_time=None,
        successful_frames=5,
        failed_frames=0,
        source_fps=1.0,
        observed_feed_rate=1.0,
    )

    report_end = start + timedelta(seconds=10)

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
        start_time=start.isoformat(),
        end_time=report_end.isoformat(),
    )

    camera = report["cameras"][0]

    assert camera["observed_duration_seconds"] == 10.0
    assert camera["online_duration_seconds"] == 10.0
    assert camera["uptime_percent"] == 100.0
    assert camera["observed_feed_rate"] is None
    assert (
        camera["feed_rate_status"]
        == "UNAVAILABLE_FOR_CLIPPED_INTERVALS"
    )
    assert camera["intervals"][0][
        "was_open_at_report_generation"
    ] is True

    database.close()


def test_camera_health_report_empty_window(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    report = generate_camera_health_report(
        tmp_path / "report.json",
        database,
        start_time="2026-09-27T10:00:00+00:00",
        end_time="2026-09-27T11:00:00+00:00",
    )

    assert report["camera_count"] == 0
    assert report["cameras"] == []

    database.close()


def test_camera_health_report_persists_json(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    start = datetime(
        2026, 9, 27, 10, 0,
        tzinfo=timezone.utc,
    )
    end = start + timedelta(seconds=10)

    record_interval(
        database,
        "CAM-001",
        "ONLINE",
        start,
        end,
        10,
        0,
    )

    report_path = tmp_path / "report.json"

    report = generate_camera_health_report(
        report_path,
        database,
    )

    saved = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    assert saved == report

    database.close()


def test_camera_health_report_rejects_missing_database():
    try:
        generate_camera_health_report(
            "report.json",
            None,
        )
    except ValueError as error:
        assert str(error) == (
            "camera_health_database is required"
        )
        return

    raise AssertionError(
        "Expected ValueError for missing database"
    )


def test_camera_health_report_rejects_invalid_period(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "health.db"
    )

    try:
        generate_camera_health_report(
            tmp_path / "report.json",
            database,
            start_time="2026-09-27T11:00:00+00:00",
            end_time="2026-09-27T10:00:00+00:00",
        )
    except ValueError as error:
        assert str(error) == (
            "end_time must be later than start_time"
        )
        database.close()
        return

    database.close()

    raise AssertionError(
        "Expected ValueError for invalid period"
    )
