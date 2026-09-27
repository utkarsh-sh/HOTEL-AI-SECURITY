from datetime import datetime, timezone

from ai.camera_health import CAMERA_OFFLINE, CAMERA_RECOVERED
from database.camera_health_database import CameraHealthDatabase


class CameraHealthHistoryService:
    """
    Persist historical camera health intervals.

    This service records observed feed health separately from the
    current-state CameraHealthMonitor.
    """

    def __init__(
        self,
        camera_id,
        database,
        now_provider=None,
    ):
        if not camera_id:
            raise ValueError("camera_id is required")

        if not isinstance(database, CameraHealthDatabase):
            raise TypeError(
                "database must be a CameraHealthDatabase instance"
            )

        self.camera_id = camera_id
        self.database = database
        self.now_provider = (
            now_provider
            if now_provider is not None
            else lambda: datetime.now(timezone.utc)
        )

        self.successful_frames = 0
        self.failed_frames = 0
        self.source_fps = None
        self.interval_started_at = None

        open_interval = self.database.get_open_interval(
            camera_id=self.camera_id
        )

        if open_interval is not None:
            self.successful_frames = int(
                open_interval["successful_frames"]
            )
            self.failed_frames = int(
                open_interval["failed_frames"]
            )
            self.source_fps = open_interval["source_fps"]
            self.interval_started_at = datetime.fromisoformat(
                open_interval["start_time"]
            )

    def _now(self):
        value = self.now_provider()

        if not isinstance(value, datetime):
            raise TypeError(
                "now_provider must return a datetime"
            )

        if value.tzinfo is None:
            raise ValueError(
                "now_provider must return a timezone-aware datetime"
            )

        return value

    def _now_string(self):
        return self._now().isoformat()

    def _calculate_feed_rate(self, now):
        if self.successful_frames <= 0:
            return 0.0

        if self.interval_started_at is None:
            return 0.0

        elapsed_seconds = (
            now - self.interval_started_at
        ).total_seconds()

        if elapsed_seconds <= 0:
            return 0.0

        return self.successful_frames / elapsed_seconds

    def frame_received(
        self,
        source_fps,
        transition=None,
    ):
        """
        Record one successfully received frame.

        A first successful frame starts an ONLINE interval.
        CAMERA_RECOVERED closes the previous OFFLINE interval
        before starting the new ONLINE interval.
        """

        if source_fps is None:
            raise ValueError("source_fps is required")

        source_fps = float(source_fps)

        if source_fps <= 0:
            raise ValueError(
                "source_fps must be greater than 0"
            )

        now = self._now()

        if transition == CAMERA_RECOVERED:
            self.database.close_open_interval(
                camera_id=self.camera_id,
                end_time=now.isoformat(),
            )

            self.successful_frames = 1
            self.failed_frames = 0
            self.source_fps = source_fps
            self.interval_started_at = now

            self.database.record_interval(
                camera_id=self.camera_id,
                status="ONLINE",
                start_time=now.isoformat(),
                successful_frames=1,
                failed_frames=0,
                source_fps=source_fps,
                observed_feed_rate=0.0,
            )

            return

        if self.interval_started_at is None:
            self.source_fps = source_fps
            self.successful_frames = 1
            self.failed_frames = 0
            self.interval_started_at = now

            self.database.record_interval(
                camera_id=self.camera_id,
                status="ONLINE",
                start_time=now.isoformat(),
                successful_frames=1,
                failed_frames=0,
                source_fps=source_fps,
                observed_feed_rate=0.0,
            )

            return

        self.successful_frames += 1
        self.source_fps = source_fps

        self.database.update_open_interval(
            camera_id=self.camera_id,
            successful_frames=self.successful_frames,
            failed_frames=self.failed_frames,
            source_fps=source_fps,
            observed_feed_rate=self._calculate_feed_rate(now),
        )

    def frame_failed(
        self,
        transition=None,
    ):
        """
        Record one failed frame from a continuous source.

        Failures before the offline threshold remain associated
        with the current ONLINE interval. Once CAMERA_OFFLINE is
        reported, that interval is closed and an OFFLINE interval
        begins.
        """

        now = self._now()
        self.failed_frames += 1

        if transition == CAMERA_OFFLINE:
            if self.interval_started_at is not None:
                self.database.update_open_interval(
                    camera_id=self.camera_id,
                    successful_frames=self.successful_frames,
                    failed_frames=self.failed_frames,
                    source_fps=self.source_fps,
                    observed_feed_rate=self._calculate_feed_rate(now),
                )

                self.database.close_open_interval(
                    camera_id=self.camera_id,
                    end_time=now.isoformat(),
                )

            self.database.record_interval(
                camera_id=self.camera_id,
                status="OFFLINE",
                start_time=now.isoformat(),
                successful_frames=0,
                failed_frames=self.failed_frames,
                source_fps=self.source_fps,
                observed_feed_rate=0.0,
            )

            self.interval_started_at = now
            return

        if self.interval_started_at is not None:
            if self.database.get_intervals(
                camera_id=self.camera_id,
            ):
                self.database.update_open_interval(
                    camera_id=self.camera_id,
                    successful_frames=self.successful_frames,
                    failed_frames=self.failed_frames,
                    source_fps=self.source_fps,
                    observed_feed_rate=self._calculate_feed_rate(now),
                )

    def close(self):
        """Close the currently open historical interval."""

        if self.interval_started_at is None:
            return

        self.database.close_open_interval(
            camera_id=self.camera_id,
            end_time=self._now_string(),
        )
        self.interval_started_at = None
