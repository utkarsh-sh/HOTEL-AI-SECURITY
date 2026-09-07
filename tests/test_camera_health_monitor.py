import sqlite3
import unittest
from pathlib import Path

from ai.camera_health import CameraHealthMonitor
from database.camera_database import CameraDatabase


class TestCameraHealthMonitor(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_health_monitor.db"
    )

    CAMERA_ID = "CAM-TEST-001"

    def setUp(self):
        if self.TEST_DATABASE_PATH.exists():
            self.TEST_DATABASE_PATH.unlink()

        self.database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

        self.database.create_camera(
            camera_id=self.CAMERA_ID,
            name="Test Camera",
            location="Test Location",
        )

        self.monitor = CameraHealthMonitor(
            camera_id=self.CAMERA_ID,
            database=self.database,
            failure_threshold=3,
        )

    def tearDown(self):
        self.database.close()

        if self.TEST_DATABASE_PATH.exists():
            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                # Windows can occasionally release the SQLite file
                # slightly later. The test itself has already completed.
                pass

    def get_camera(self):
        camera = self.database.get_camera(self.CAMERA_ID)

        self.assertIsNotNone(camera)

        return camera

    def test_initial_camera_state(self):
        camera = self.get_camera()

        self.assertEqual(camera["status"], "OFFLINE")
        self.assertEqual(camera["consecutive_failures"], 0)
        self.assertIsNone(camera["last_seen"])
        self.assertIsNone(camera["last_error"])

        self.assertEqual(
            self.monitor.get_failure_count(),
            0,
        )

    def test_successful_frame_marks_camera_online(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        camera = self.get_camera()

        self.assertEqual(camera["status"], "ONLINE")
        self.assertEqual(camera["fps"], 25.0)
        self.assertEqual(camera["width"], 1920)
        self.assertEqual(camera["height"], 1080)
        self.assertEqual(camera["consecutive_failures"], 0)
        self.assertIsNotNone(camera["last_seen"])
        self.assertIsNone(camera["last_error"])

        self.assertEqual(
            self.monitor.get_failure_count(),
            0,
        )

    def test_first_failure_is_recorded(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.monitor.frame_failed(
            error="Test frame failure",
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["consecutive_failures"],
            1,
        )

        self.assertEqual(
            camera["last_error"],
            "Test frame failure",
        )

        self.assertEqual(
            self.monitor.get_failure_count(),
            1,
        )

    def test_second_failure_is_recorded(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.monitor.frame_failed(
            error="Failure 1",
        )

        self.monitor.frame_failed(
            error="Failure 2",
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["consecutive_failures"],
            2,
        )

        self.assertEqual(
            camera["last_error"],
            "Failure 2",
        )

        self.assertEqual(
            self.monitor.get_failure_count(),
            2,
        )

    def test_threshold_failure_marks_camera_offline(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        for _ in range(3):
            self.monitor.frame_failed(
                error="No frame received",
            )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            3,
        )

        self.assertEqual(
            camera["last_error"],
            "No frame received",
        )

        self.assertEqual(
            self.monitor.get_failure_count(),
            3,
        )

    def test_recovery_resets_failure_counter(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.monitor.frame_failed(
            error="Failure 1",
        )

        self.monitor.frame_failed(
            error="Failure 2",
        )

        self.monitor.frame_failed(
            error="Failure 3",
        )

        self.assertEqual(
            self.monitor.get_failure_count(),
            3,
        )

        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

        self.assertEqual(
            self.monitor.get_failure_count(),
            0,
        )

        self.assertIsNone(
            camera["last_error"]
        )

    def test_failure_after_recovery_starts_from_one(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.monitor.frame_failed(
            error="Failure before recovery",
        )

        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.monitor.frame_failed(
            error="Failure after recovery",
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            1,
        )

        self.assertEqual(
            camera["last_error"],
            "Failure after recovery",
        )

        self.assertEqual(
            self.monitor.get_failure_count(),
            1,
        )

    def test_custom_failure_threshold_is_supported(self):
        custom_monitor = CameraHealthMonitor(
            camera_id=self.CAMERA_ID,
            database=self.database,
            failure_threshold=2,
        )

        custom_monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        custom_monitor.frame_failed(
            error="Failure 1",
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        custom_monitor.frame_failed(
            error="Failure 2",
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["consecutive_failures"],
            2,
        )

        self.assertEqual(
            custom_monitor.get_failure_count(),
            2,
        )

        # This test deliberately exposes the current design gap:
        # CameraDatabase currently hardcodes the offline threshold
        # to 3. Stage 13 will move threshold authority into the
        # monitor/database contract.
        self.assertEqual(
            camera["status"],
            "OFFLINE",
            )

    def test_successful_frame_clears_previous_error(self):
        self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.monitor.frame_failed(
            error="Temporary camera failure",
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["last_error"],
            "Temporary camera failure",
        )

        self.monitor.frame_received(
            fps=30.0,
            width=1280,
            height=720,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["fps"],
            30.0,
        )

        self.assertEqual(
            camera["width"],
            1280,
        )

        self.assertEqual(
            camera["height"],
            720,
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

        self.assertIsNone(
            camera["last_error"]
        )


if __name__ == "__main__":
    unittest.main()