import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.auth_dependencies import get_current_user
from database.camera_database import CameraDatabase


class TestCameraHealthSummaryAPI(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_health_summary_api.db"
    )

    ONLINE_CAMERA_1 = "CAM-SUMMARY-001"
    ONLINE_CAMERA_2 = "CAM-SUMMARY-002"
    OFFLINE_CAMERA = "CAM-SUMMARY-003"

    # --------------------------------------------------------
    # Setup
    # --------------------------------------------------------

    def setUp(self):

        if self.TEST_DATABASE_PATH.exists():
            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

        database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

        # Camera 1 -> ONLINE
        database.create_camera(
            camera_id=self.ONLINE_CAMERA_1,
            name="Lobby Camera",
            location="Lobby",
        )

        database.update_health(
            camera_id=self.ONLINE_CAMERA_1,
            status="ONLINE",
            fps=25.0,
            width=1920,
            height=1080,
        )

        # Camera 2 -> ONLINE
        database.create_camera(
            camera_id=self.ONLINE_CAMERA_2,
            name="Reception Camera",
            location="Reception",
        )

        database.update_health(
            camera_id=self.ONLINE_CAMERA_2,
            status="ONLINE",
            fps=24.0,
            width=1280,
            height=720,
        )

        # Camera 3 -> OFFLINE
        database.create_camera(
            camera_id=self.OFFLINE_CAMERA,
            name="Parking Camera",
            location="Parking",
            status="ONLINE",
        )

        database.record_failure(
            camera_id=self.OFFLINE_CAMERA,
            consecutive_failures=3,
            error="Camera disconnected",
            failure_threshold=3,
        )

        database.close()

        self.test_user = {
            "id": 999,
            "username": "api-test-user",
            "full_name": "API Test User",
            "role": "ADMIN",
            "active": True,
        }

        app.dependency_overrides[
            get_current_user
        ] = lambda: self.test_user

        self.database_patch = patch(
            "backend.main.CameraDatabase",
            side_effect=lambda: CameraDatabase(
                self.TEST_DATABASE_PATH
            ),
        )

        self.database_patch.start()

        self.client = TestClient(app)

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    def tearDown(self):

        try:
            self.client.close()
        except Exception:
            pass

        self.database_patch.stop()

        app.dependency_overrides.clear()

        if self.TEST_DATABASE_PATH.exists():
            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

    # --------------------------------------------------------
    # Test 1
    # --------------------------------------------------------

    def test_health_summary_authenticated(self):

        response = self.client.get(
            "/cameras/health/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertIn(
            "total_cameras",
            data,
        )

        self.assertIn(
            "online",
            data,
        )

        self.assertIn(
            "offline",
            data,
        )

        self.assertIn(
            "health_percentage",
            data,
        )

    # --------------------------------------------------------
    # Test 2
    # --------------------------------------------------------

    def test_health_summary_total_camera_count(self):

        response = self.client.get(
            "/cameras/health/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["total_cameras"],
            3,
        )

    # --------------------------------------------------------
    # Test 3
    # --------------------------------------------------------

    def test_health_summary_online_camera_count(self):

        response = self.client.get(
            "/cameras/health/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["online"],
            2,
        )

    # --------------------------------------------------------
    # Test 4
    # --------------------------------------------------------

    def test_health_summary_offline_camera_count(self):

        response = self.client.get(
            "/cameras/health/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["offline"],
            1,
        )

    # --------------------------------------------------------
    # Test 5
    # --------------------------------------------------------

    def test_health_summary_percentage(self):

        response = self.client.get(
            "/cameras/health/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["health_percentage"],
            66.67,
        )

    # --------------------------------------------------------
    # Test 6
    # --------------------------------------------------------

    def test_health_summary_requires_authentication(self):

        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

        response = self.client.get(
            "/cameras/health/summary"
        )

        self.assertEqual(
            response.status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()