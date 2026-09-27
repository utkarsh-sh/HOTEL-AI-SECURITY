from datetime import datetime, timezone
from ai.camera_health import CAMERA_OFFLINE, CAMERA_RECOVERED
from ai.camera_health_history import CameraHealthHistoryService
from database.camera_health_database import CameraHealthDatabase
class FakeClock:
    def __init__(self, value):
        self.value = value
    def now(self):
        return self.value
    def advance(self, seconds):
        self.value = self.value + __import__(
            "datetime"
        ).timedelta(seconds=seconds)
def test_first_frame_starts_online_interval(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["successful_frames"] == 1
    assert rows[0]["failed_frames"] == 0
    assert rows[0]["source_fps"] == 25.0
    assert rows[0]["end_time"] is None
    database.close()
def test_successful_frames_update_feed_rate(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    clock.advance(2)
    service.frame_received(source_fps=25.0)
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 1
    assert rows[0]["successful_frames"] == 2
    assert rows[0]["observed_feed_rate"] == 1.0
    database.close()
def test_failures_before_threshold_stay_in_online_interval(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    clock.advance(1)
    service.frame_failed()
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["failed_frames"] == 1
    assert rows[0]["end_time"] is None
    database.close()
def test_offline_transition_closes_online_and_starts_offline(
    tmp_path,
):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    clock.advance(1)
    service.frame_failed()
    clock.advance(1)
    service.frame_failed(
        transition=CAMERA_OFFLINE,
    )
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 2
    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["end_time"] == (
        "2026-09-27T00:00:02+00:00"
    )
    assert rows[0]["failed_frames"] == 2
    assert rows[1]["status"] == "OFFLINE"
    assert rows[1]["start_time"] == (
        "2026-09-27T00:00:02+00:00"
    )
    assert rows[1]["end_time"] is None
    assert rows[1]["failed_frames"] == 2
    database.close()
def test_offline_failures_update_offline_interval(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    clock.advance(1)
    service.frame_failed(
        transition=CAMERA_OFFLINE,
    )
    clock.advance(5)
    service.frame_failed()
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 2
    assert rows[1]["status"] == "OFFLINE"
    assert rows[1]["failed_frames"] == 2
    assert rows[1]["end_time"] is None
    database.close()
def test_recovery_closes_offline_and_starts_online(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    clock.advance(1)
    service.frame_failed(
        transition=CAMERA_OFFLINE,
    )
    clock.advance(10)
    service.frame_received(
        source_fps=25.0,
        transition=CAMERA_RECOVERED,
    )
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 3
    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["end_time"] == (
        "2026-09-27T00:00:01+00:00"
    )
    assert rows[1]["status"] == "OFFLINE"
    assert rows[1]["start_time"] == (
        "2026-09-27T00:00:01+00:00"
    )
    assert rows[1]["end_time"] == (
        "2026-09-27T00:00:11+00:00"
    )
    assert rows[2]["status"] == "ONLINE"
    assert rows[2]["start_time"] == (
        "2026-09-27T00:00:11+00:00"
    )
    assert rows[2]["successful_frames"] == 1
    assert rows[2]["end_time"] is None
    database.close()
def test_close_finalizes_open_interval(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    service.frame_received(source_fps=25.0)
    clock.advance(5)
    service.close()
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 1
    assert rows[0]["end_time"] == (
        "2026-09-27T00:00:05+00:00"
    )
    database.close()
def test_service_restart_restores_existing_open_interval(tmp_path):
    database = CameraHealthDatabase(
        tmp_path / "camera_health.db"
    )
    clock = FakeClock(
        datetime(
            2026, 9, 27, 0, 0, 0,
            tzinfo=timezone.utc,
        )
    )
    first_service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    first_service.frame_received(source_fps=25.0)
    clock.advance(2)
    second_service = CameraHealthHistoryService(
        camera_id="CAM-001",
        database=database,
        now_provider=clock.now,
    )
    assert second_service.successful_frames == 1
    assert second_service.failed_frames == 0
    assert second_service.source_fps == 25.0
    assert second_service.interval_started_at == datetime(
        2026, 9, 27, 0, 0, 0,
        tzinfo=timezone.utc,
    )
    second_service.frame_received(source_fps=25.0)
    rows = database.get_intervals(
        camera_id="CAM-001"
    )
    assert len(rows) == 1
    assert rows[0]["status"] == "ONLINE"
    assert rows[0]["successful_frames"] == 2
    assert rows[0]["end_time"] is None
    database.close()
