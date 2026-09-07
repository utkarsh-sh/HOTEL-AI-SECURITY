import unittest
from pathlib import Path

from ai.camera_health import CameraHealthMonitor
from database.camera_database import CameraDatabase


class TestCameraHealthPersistence(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_health_persistence.db"
    )

    CAMERA_ID = "CAM-PERSIST-001"

    def setUp(self):
        if self.TEST_DATABASE_PATH.exists():
            self.TEST_DATABASE_PATH.unlink()

        self.database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

        self.database.create_camera(
            camera_id=self.CAMERA_ID,
            name="Persistence Test Camera",
            location="Test Area",
            status="OFFLINE",
        )

    def tearDown(self):
        self.database.close()

        if self.TEST_DATABASE_PATH.exists():
            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

    def create_monitor(self):
        return CameraHealthMonitor(
            camera_id=self.CAMERA_ID,
            database=self.database,
            failure_threshold=3,
        )

    def test_initial_first_frame_is_not_recovery(self):
        monitor = self.create_monitor()

        transition = monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        camera = self.database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertIsNotNone(
            camera["last_seen"]
        )

        self.assertIsNone(
            transition,
        )

    def test_online_to_offline_returns_transition(self):
        monitor = self.create_monitor()

        monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertIsNone(
            monitor.frame_failed(
                error="Failure 1"
            )
        )

        self.assertIsNone(
            monitor.frame_failed(
                error="Failure 2"
            )
        )

        transition = monitor.frame_failed(
            error="Failure 3"
        )

        self.assertEqual(
            transition,
            "CAMERA_OFFLINE",
        )

        camera = self.database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

    def test_additional_failure_does_not_return_transition(self):
        monitor = self.create_monitor()

        monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        for number in range(1, 4):
            transition = monitor.frame_failed(
                error=f"Failure {number}"
            )

        self.assertEqual(
            transition,
            "CAMERA_OFFLINE",
        )

        additional_transition = (
            monitor.frame_failed(
                error="Failure 4"
            )
        )

        self.assertIsNone(
            additional_transition
        )

    def test_restart_while_offline_does_not_duplicate_transition(self):
        first_monitor = self.create_monitor()

        first_monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        for number in range(1, 4):
            first_transition = (
                first_monitor.frame_failed(
                    error=f"Failure {number}"
                )
            )

        self.assertEqual(
            first_transition,
            "CAMERA_OFFLINE",
        )

        # Simulate application restart by creating
        # a completely new monitor instance.
        restarted_monitor = self.create_monitor()

        transition_after_restart = (
            restarted_monitor.frame_failed(
                error="Still no frames"
            )
        )

        self.assertIsNone(
            transition_after_restart
        )

        camera = self.database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

    def test_offline_to_online_returns_recovery_transition(self):
        monitor = self.create_monitor()

        monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        for number in range(1, 4):
            monitor.frame_failed(
                error=f"Failure {number}"
            )

        transition = monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition,
            "CAMERA_RECOVERED",
        )

        camera = self.database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

    def test_restart_then_recovery_is_detected(self):
        first_monitor = self.create_monitor()

        first_monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        for number in range(1, 4):
            first_monitor.frame_failed(
                error=f"Failure {number}"
            )

        camera = self.database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        # New process / new monitor instance.
        restarted_monitor = self.create_monitor()

        transition = restarted_monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition,
            "CAMERA_RECOVERED",
        )

    def test_new_outage_after_recovery_returns_new_transition(self):
        monitor = self.create_monitor()

        monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        for number in range(1, 4):
            first_outage = monitor.frame_failed(
                error=f"First outage {number}"
            )

        self.assertEqual(
            first_outage,
            "CAMERA_OFFLINE",
        )

        recovery = monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            recovery,
            "CAMERA_RECOVERED",
        )

        for number in range(1, 4):
            second_outage = monitor.frame_failed(
                error=f"Second outage {number}"
            )

        self.assertEqual(
            second_outage,
            "CAMERA_OFFLINE",
        )


if __name__ == "__main__":
    unittest.main()