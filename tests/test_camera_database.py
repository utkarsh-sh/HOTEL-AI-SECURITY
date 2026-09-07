import unittest
from pathlib import Path

from database.camera_database import CameraDatabase


class TestCameraDatabase(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_security.db"
    )

    def setUp(self):
        if self.TEST_DATABASE_PATH.exists():
            self.TEST_DATABASE_PATH.unlink()

        self.database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

    def tearDown(self):
        self.database.close()

        if self.TEST_DATABASE_PATH.exists():
            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

    def create_camera(
        self,
        camera_id="CAM-TEST-001",
        name="Test Camera",
        location="Test Location",
    ):
        self.database.create_camera(
            camera_id=camera_id,
            name=name,
            location=location,
        )

    def get_camera(self, camera_id="CAM-TEST-001"):
        camera = self.database.get_camera(camera_id)

        self.assertIsNotNone(camera)

        return camera

    def test_create_camera(self):
        self.create_camera()

        camera = self.get_camera()

        self.assertEqual(
            camera["camera_id"],
            "CAM-TEST-001",
        )

        self.assertEqual(
            camera["name"],
            "Test Camera",
        )

        self.assertEqual(
            camera["location"],
            "Test Location",
        )

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

        self.assertIsNone(
            camera["last_seen"]
        )

        self.assertIsNone(
            camera["last_error"]
        )

        self.assertIsNotNone(
            camera["created_at"]
        )

        self.assertIsNotNone(
            camera["updated_at"]
        )

    def test_get_all_cameras(self):
        self.create_camera(
            camera_id="CAM-003",
            name="Camera 3",
            location="Area 3",
        )

        self.create_camera(
            camera_id="CAM-001",
            name="Camera 1",
            location="Area 1",
        )

        self.create_camera(
            camera_id="CAM-002",
            name="Camera 2",
            location="Area 2",
        )

        cameras = self.database.get_all_cameras()

        self.assertEqual(
            len(cameras),
            3,
        )

        camera_ids = [
            camera["camera_id"]
            for camera in cameras
        ]

        self.assertEqual(
            camera_ids,
            [
                "CAM-001",
                "CAM-002",
                "CAM-003",
            ],
        )

    def test_duplicate_camera_id_is_rejected(self):
        self.create_camera()

        with self.assertRaises(Exception):
            self.database.create_camera(
                camera_id="CAM-TEST-001",
                name="Duplicate Camera",
                location="Another Location",
            )

    def test_online_health_update(self):
        self.create_camera()

        self.database.update_health(
            camera_id="CAM-TEST-001",
            status="ONLINE",
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
            camera["fps"],
            25.0,
        )

        self.assertEqual(
            camera["width"],
            1920,
        )

        self.assertEqual(
            camera["height"],
            1080,
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

        self.assertIsNotNone(
            camera["last_seen"]
        )

        self.assertIsNone(
            camera["last_error"]
        )

    def test_online_update_resets_previous_failures(self):
        self.create_camera()

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=2,
            error="Temporary failure",
            failure_threshold=3,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["consecutive_failures"],
            2,
        )

        self.database.update_health(
            camera_id="CAM-TEST-001",
            status="ONLINE",
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

        self.assertIsNone(
            camera["last_error"]
        )

    def test_first_failure_keeps_camera_online(self):
        self.create_camera()

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=1,
            error="Failure 1",
            failure_threshold=3,
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
            "Failure 1",
        )

    def test_failure_at_threshold_marks_camera_offline(self):
        self.create_camera()

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=3,
            error="Failure 3",
            failure_threshold=3,
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
            "Failure 3",
        )

    def test_custom_failure_threshold(self):
        self.create_camera()

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=2,
            error="Failure 2",
            failure_threshold=2,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            2,
        )

    def test_failure_below_custom_threshold_keeps_camera_online(self):
        self.create_camera()

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=1,
            error="Failure 1",
            failure_threshold=2,
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

    def test_failure_error_is_updated(self):
        self.create_camera()

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=1,
            error="First error",
            failure_threshold=3,
        )

        self.database.record_failure(
            camera_id="CAM-TEST-001",
            consecutive_failures=2,
            error="Second error",
            failure_threshold=3,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["consecutive_failures"],
            2,
        )

        self.assertEqual(
            camera["last_error"],
            "Second error",
        )

    def test_missing_camera_is_rejected(self):
        with self.assertRaises(ValueError):
            self.database.update_health(
                camera_id="DOES-NOT-EXIST",
                status="ONLINE",
                fps=25.0,
                width=1920,
                height=1080,
            )

    def test_missing_camera_failure_is_rejected(self):
        with self.assertRaises(ValueError):
            self.database.record_failure(
                camera_id="DOES-NOT-EXIST",
                consecutive_failures=1,
                error="Test failure",
                failure_threshold=3,
            )

    def test_invalid_status_is_rejected(self):
        self.create_camera()

        with self.assertRaises(ValueError):
            self.database.update_health(
                camera_id="CAM-TEST-001",
                status="UNKNOWN",
            )

    def test_invalid_failure_threshold_is_rejected(self):
        self.create_camera()

        with self.assertRaises(ValueError):
            self.database.record_failure(
                camera_id="CAM-TEST-001",
                consecutive_failures=1,
                error="Test failure",
                failure_threshold=0,
            )

    def test_invalid_failure_count_is_rejected(self):
        self.create_camera()

        with self.assertRaises(ValueError):
            self.database.record_failure(
                camera_id="CAM-TEST-001",
                consecutive_failures=0,
                error="Test failure",
                failure_threshold=3,
            )

    def test_delete_camera(self):
        self.create_camera()

        self.assertIsNotNone(
            self.database.get_camera(
                "CAM-TEST-001"
            )
        )

        self.database.delete_camera(
            "CAM-TEST-001"
        )

        self.assertIsNone(
            self.database.get_camera(
                "CAM-TEST-001"
            )
        )


if __name__ == "__main__":
    unittest.main()