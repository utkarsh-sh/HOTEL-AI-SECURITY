from datetime import datetime, timezone
from pathlib import Path

from database.camera_health_database import CameraHealthDatabase


def test_record_and_query_open_interval(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    start_time = "2026-09-27T00:00:00+00:00"

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time=start_time,
        successful_frames=100,
        failed_frames=0,
        source_fps=25.0,
        observed_feed_rate=24.5,
    )

    rows = database.get_intervals(
        camera_id="CAM-001",
        start_time="2026-09-27T00:30:00+00:00",
        end_time="2026-09-27T01:00:00+00:00",
    )

    assert len(rows) == 1
    assert rows[0]["camera_id"] == "CAM-001"
    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["end_time"] is None
    assert rows[0]["successful_frames"] == 100
    assert rows[0]["source_fps"] == 25.0
    assert rows[0]["observed_feed_rate"] == 24.5

    database.close()


def test_closed_interval_is_queryable(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    database.record_interval(
        camera_id="CAM-001",
        status="OFFLINE",
        start_time="2026-09-27T00:00:00+00:00",
        end_time="2026-09-27T00:10:00+00:00",
        failed_frames=5,
    )

    rows = database.get_intervals(
        camera_id="CAM-001",
        start_time="2026-09-27T00:05:00+00:00",
        end_time="2026-09-27T00:20:00+00:00",
    )

    assert len(rows) == 1
    assert rows[0]["status"] == "OFFLINE"
    assert rows[0]["failed_frames"] == 5

    database.close()


def test_non_overlapping_interval_is_excluded(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time="2026-09-27T00:00:00+00:00",
        end_time="2026-09-27T00:10:00+00:00",
    )

    rows = database.get_intervals(
        camera_id="CAM-001",
        start_time="2026-09-27T00:20:00+00:00",
        end_time="2026-09-27T00:30:00+00:00",
    )

    assert rows == []

    database.close()
def test_update_open_interval(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time="2026-09-27T00:00:00+00:00",
        successful_frames=10,
        source_fps=25.0,
        observed_feed_rate=24.0,
    )

    updated = database.update_open_interval(
        camera_id="CAM-001",
        successful_frames=100,
        failed_frames=2,
        source_fps=30.0,
        observed_feed_rate=28.5,
    )

    assert updated == 1

    rows = database.get_intervals(camera_id="CAM-001")

    assert len(rows) == 1
    assert rows[0]["successful_frames"] == 100
    assert rows[0]["failed_frames"] == 2
    assert rows[0]["source_fps"] == 30.0
    assert rows[0]["observed_feed_rate"] == 28.5
    assert rows[0]["end_time"] is None

    database.close()


def test_close_open_interval(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time="2026-09-27T00:00:00+00:00",
    )

    closed = database.close_open_interval(
        camera_id="CAM-001",
        end_time="2026-09-27T01:00:00+00:00",
    )

    assert closed == 1

    rows = database.get_intervals(camera_id="CAM-001")

    assert len(rows) == 1
    assert rows[0]["end_time"] == "2026-09-27T01:00:00+00:00"

    database.close()


def test_update_and_close_do_not_affect_other_camera(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time="2026-09-27T00:00:00+00:00",
        successful_frames=10,
    )

    database.record_interval(
        camera_id="CAM-002",
        status="ONLINE",
        start_time="2026-09-27T00:00:00+00:00",
        successful_frames=20,
    )

    assert database.update_open_interval(
        camera_id="CAM-001",
        successful_frames=50,
    ) == 1

    assert database.close_open_interval(
        camera_id="CAM-001",
        end_time="2026-09-27T01:00:00+00:00",
    ) == 1

    cam1 = database.get_intervals(camera_id="CAM-001")
    cam2 = database.get_intervals(camera_id="CAM-002")

    assert cam1[0]["successful_frames"] == 50
    assert cam1[0]["end_time"] == "2026-09-27T01:00:00+00:00"

    assert cam2[0]["successful_frames"] == 20
    assert cam2[0]["end_time"] is None

    database.close()


def test_update_open_interval_requires_a_field(tmp_path):
    database_path = tmp_path / "camera_health.db"
    database = CameraHealthDatabase(database_path)

    database.record_interval(
        camera_id="CAM-001",
        status="ONLINE",
        start_time="2026-09-27T00:00:00+00:00",
    )

    try:
        database.update_open_interval(
            camera_id="CAM-001",
        )
    except ValueError as exc:
        assert str(exc) == (
            "At least one interval field must be provided"
        )
    else:
        raise AssertionError(
            "Expected ValueError was not raised"
        )

    database.close()
