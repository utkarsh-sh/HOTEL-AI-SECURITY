import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.auth_dependencies import get_current_user
from database.camera_database import CameraDatabase


class TestCameraAPI(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_api.db"
    )

    ONLINE_CAMERA_ID = "CAM-API-ONLINE"
    OFFLINE_CAMERA_ID = "CAM-API-OFFLINE"

    # --------------------------------------------------------
    # Setup
    # --------------------------------------------------------

    def setUp(self):

        if self.TEST_DATABASE_PATH.exists():
            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

        # ----------------------------------------------------
        # Create isolated camera database.
        # ----------------------------------------------------

        database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

        database.create_camera(
            camera_id=self.ONLINE_CAMERA_ID,
            name="Main Entrance Camera",
            location="Main Entrance",
        )

        database.update_health(
            camera_id=self.ONLINE_CAMERA_ID,
            status="ONLINE",
            fps=25.0,
            width=1920,
            height=1080,
        )

        database.create_camera(
            camera_id=self.OFFLINE_CAMERA_ID,
            name="Parking Camera",
            location="Parking Area",
            status="ONLINE",
        )

        database.record_failure(
            camera_id=self.OFFLINE_CAMERA_ID,
            consecutive_failures=1,
            error="Frame timeout",
            failure_threshold=3,
        )

        database.record_failure(
            camera_id=self.OFFLINE_CAMERA_ID,
            consecutive_failures=2,
            error="Frame timeout",
            failure_threshold=3,
        )

        database.record_failure(
            camera_id=self.OFFLINE_CAMERA_ID,
            consecutive_failures=3,
            error="Camera disconnected",
            failure_threshold=3,
        )

        database.close()

        # ----------------------------------------------------
        # Fake authenticated user.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Patch CameraDatabase inside backend.main so that
        # endpoints use the isolated test database instead of
        # database/hotel_security.db.
        # ----------------------------------------------------

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

    def test_get_cameras_authenticated(self):

        response = self.client.get(
            "/cameras"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["total"],
            2,
        )

        self.assertIn(
            "cameras",
            data,
        )

        self.assertEqual(
            len(data["cameras"]),
            2,
        )

    # --------------------------------------------------------
    # Test 2
    # --------------------------------------------------------

    def test_get_cameras_contains_expected_camera_fields(self):

        response = self.client.get(
            "/cameras"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        camera = next(
            item
            for item in data["cameras"]
            if item["camera_id"]
            == self.ONLINE_CAMERA_ID
        )

        expected_fields = {
            "camera_id",
            "name",
            "location",
            "status",
            "last_seen",
            "fps",
            "width",
            "height",
            "consecutive_failures",
            "last_error",
            "created_at",
            "updated_at",
        }

        self.assertTrue(
            expected_fields.issubset(
                camera.keys()
            )
        )

    # --------------------------------------------------------
    # Test 3
    # --------------------------------------------------------

    def test_get_online_camera_health(self):

        response = self.client.get(
            f"/cameras/{self.ONLINE_CAMERA_ID}/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["camera_id"],
            self.ONLINE_CAMERA_ID,
        )

        self.assertEqual(
            data["status"],
            "ONLINE",
        )

        self.assertIsNotNone(
            data["last_seen"]
        )

        self.assertEqual(
            data["fps"],
            25.0,
        )

        self.assertEqual(
            data["resolution"],
            "1920x1080",
        )

        self.assertEqual(
            data["consecutive_failures"],
            0,
        )

        self.assertIsNone(
            data["last_error"]
        )

    # --------------------------------------------------------
    # Test 4
    # --------------------------------------------------------

    def test_get_offline_camera_health(self):

        response = self.client.get(
            f"/cameras/{self.OFFLINE_CAMERA_ID}/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["camera_id"],
            self.OFFLINE_CAMERA_ID,
        )

        self.assertEqual(
            data["status"],
            "OFFLINE",
        )

        self.assertEqual(
            data["consecutive_failures"],
            3,
        )

        self.assertEqual(
            data["last_error"],
            "Camera disconnected",
        )

    # --------------------------------------------------------
    # Test 5
    # --------------------------------------------------------

    def test_online_camera_resolution_is_formatted(self):

        response = self.client.get(
            f"/cameras/{self.ONLINE_CAMERA_ID}/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["resolution"],
            "1920x1080",
        )

    # --------------------------------------------------------
    # Test 6
    # --------------------------------------------------------

    def test_offline_camera_without_resolution_returns_none(self):

        response = self.client.get(
            f"/cameras/{self.OFFLINE_CAMERA_ID}/health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertIsNone(
            data["resolution"]
        )

    # --------------------------------------------------------
    # Test 7
    # --------------------------------------------------------

    def test_unknown_camera_returns_404(self):

        response = self.client.get(
            "/cameras/CAM-DOES-NOT-EXIST/health"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        data = response.json()

        self.assertEqual(
            data["detail"],
            "Camera CAM-DOES-NOT-EXIST not found",
        )

    # --------------------------------------------------------
    # Test 8
    # --------------------------------------------------------

    def test_get_camera_detail_endpoint(self):

        response = self.client.get(
            f"/cameras/{self.ONLINE_CAMERA_ID}"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["camera_id"],
            self.ONLINE_CAMERA_ID,
        )

        self.assertEqual(
            data["name"],
            "Main Entrance Camera",
        )

        self.assertEqual(
            data["location"],
            "Main Entrance",
        )

        self.assertEqual(
            data["status"],
            "ONLINE",
        )

    # --------------------------------------------------------
    # Test 9
    # --------------------------------------------------------

    def test_unknown_camera_detail_returns_404(self):

        response = self.client.get(
            "/cameras/UNKNOWN-CAMERA"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertEqual(
            response.json()["detail"],
            "Camera UNKNOWN-CAMERA not found",
        )

    # --------------------------------------------------------
    # Test 10
    # --------------------------------------------------------

    def test_camera_endpoint_requires_authentication(self):

        # Remove authentication override so FastAPI's
        # HTTPBearer dependency is exercised.

        app.dependency_overrides.pop(
            get_current_user,
            None,
        )

        response = self.client.get(
            "/cameras"
        )

        self.assertEqual(
            response.status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()