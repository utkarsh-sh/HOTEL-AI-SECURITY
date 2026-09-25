from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth_dependencies import get_current_user
from backend.main import app
from database.audit_database import AuditDatabase
from database.camera_database import CameraDatabase


CAMERA_DB = Path("database/test_camera_admin_api.db")
AUDIT_DB = Path("database/test_camera_admin_api_audit.db")


class TestCameraAdminAPI:
    def setup_method(self):
        for path in (CAMERA_DB, AUDIT_DB):
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    pass

        database = CameraDatabase(CAMERA_DB)
        database.create_camera(
            camera_id="CAM-ADMIN-001",
            name="Admin Camera",
            location="Lobby",
            source_type="rtsp",
            source="rtsp://admin:supersecret@192.168.1.50:554/stream?token=topsecret",
            ai_fps=5.0,
            reconnect_max_attempts=3,
            reconnect_delay_seconds=1.0,
        )
        database.update_health(
            camera_id="CAM-ADMIN-001",
            status="ONLINE",
            fps=5.0,
            width=1280,
            height=720,
        )
        database.close()

        self.user = {
            "id": 1,
            "username": "admin-test",
            "full_name": "Admin Test",
            "role": "ADMIN",
            "active": True,
        }

        app.dependency_overrides[get_current_user] = (
            lambda: self.user
        )

        self.camera_patch = patch(
            "backend.main.CameraDatabase",
            side_effect=lambda: CameraDatabase(CAMERA_DB),
        )
        self.audit_patch = patch(
            "backend.main.AuditDatabase",
            side_effect=lambda: AuditDatabase(AUDIT_DB),
        )

        self.camera_patch.start()
        self.audit_patch.start()
        self.client = TestClient(app)

    def teardown_method(self):
        try:
            self.client.close()
        finally:
            self.camera_patch.stop()
            self.audit_patch.stop()
            app.dependency_overrides.clear()

        for path in (CAMERA_DB, AUDIT_DB):
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    pass

    def set_role(self, role):
        self.user["role"] = role

    def test_admin_can_create_camera(self):
        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-ADMIN-002",
                "name": "Parking Camera",
                "location": "Parking",
                "source_type": "rtsp",
                "source": "rtsp://operator:secret123@parking.example.com:554/stream?token=abc123",
                "ai_fps": 4.0,
                "reconnect": {
                    "max_attempts": 5,
                    "delay_seconds": 2.0,
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["runner_reload_required"] is True

        camera = response.json()["camera"]
        assert camera["camera_id"] == "CAM-ADMIN-002"
        assert camera["source_type"] == "rtsp"
        assert camera["source"] == "rtsp://***:***@parking.example.com:554/stream"
        assert "secret123" not in camera["source"]
        assert "abc123" not in camera["source"]
        assert camera["ai_fps"] == 4.0
        assert camera["reconnect_max_attempts"] == 5

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        assert any(
            log["action"] == "CAMERA_CREATED"
            and log["entity_id"] == "CAM-ADMIN-002"
            and log["actor"] == "admin-test"
            for log in logs
        )

        create_details = next(
            log["details"]
            for log in logs
            if log["action"] == "CAMERA_CREATED"
            and log["entity_id"] == "CAM-ADMIN-002"
        )
        assert "secret123" not in create_details
        assert "abc123" not in create_details
        assert "operator" not in create_details

    def test_admin_can_update_camera_and_health_is_preserved(self):
        response = self.client.put(
            "/cameras/CAM-ADMIN-001",
            json={
                "name": "Updated Lobby Camera",
                "location": "North Lobby",
                "source_type": "file",
                "source": "data/input/updated.mp4",
                "ai_fps": 3.0,
                "reconnect": {
                    "max_attempts": 4,
                    "delay_seconds": 1.5,
                },
            },
        )

        assert response.status_code == 200
        camera = response.json()["camera"]

        assert camera["name"] == "Updated Lobby Camera"
        assert camera["source"] == "data/input/updated.mp4"
        assert camera["status"] == "ONLINE"
        assert camera["fps"] == 5.0
        assert camera["width"] == 1280
        assert camera["height"] == 720

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        assert any(
            log["action"] == "CAMERA_UPDATED"
            and log["entity_id"] == "CAM-ADMIN-001"
            for log in logs
        )

    def test_admin_can_delete_camera(self):
        response = self.client.delete(
            "/cameras/CAM-ADMIN-001"
        )

        assert response.status_code == 200

        database = CameraDatabase(CAMERA_DB)
        assert database.get_camera("CAM-ADMIN-001") is None
        database.close()

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        assert any(
            log["action"] == "CAMERA_DELETED"
            and log["entity_id"] == "CAM-ADMIN-001"
            for log in logs
        )


    def test_camera_get_response_masks_rtsp_credentials(self):
        response = self.client.get("/cameras/CAM-ADMIN-001")

        assert response.status_code == 200
        camera = response.json()

        assert (
            camera["source"]
            == "rtsp://***:***@192.168.1.50:554/stream"
        )
        assert "supersecret" not in camera["source"]
        assert "topsecret" not in camera["source"]
        assert camera["source_configured"] is True

        list_response = self.client.get("/cameras")
        assert list_response.status_code == 200

        listed = next(
            item
            for item in list_response.json()["cameras"]
            if item["camera_id"] == "CAM-ADMIN-001"
        )

        assert (
            listed["source"]
            == "rtsp://***:***@192.168.1.50:554/stream"
        )
        assert "supersecret" not in listed["source"]

    def test_audit_log_update_does_not_store_rtsp_credentials(self):
        response = self.client.put(
            "/cameras/CAM-ADMIN-001",
            json={
                "name": "Updated Secure Camera",
                "location": "Secure Lobby",
                "source_type": "rtsp",
                "source": (
                    "rtsp://updated:updated-secret@10.0.0.20:554/live"
                    "?token=updated-token"
                ),
                "ai_fps": 3.0,
                "reconnect": {
                    "max_attempts": 4,
                    "delay_seconds": 1.5,
                },
            },
        )

        assert response.status_code == 200

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        update_details = next(
            log["details"]
            for log in logs
            if log["action"] == "CAMERA_UPDATED"
        )

        assert "updated-secret" not in update_details
        assert "updated-token" not in update_details
        assert "updated:" not in update_details

    def test_unauthenticated_create_returns_401(self):
        app.dependency_overrides.pop(get_current_user, None)

        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-NO-AUTH",
                "name": "No Auth",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/test.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 401

    def test_unauthenticated_update_returns_401(self):
        app.dependency_overrides.pop(get_current_user, None)

        response = self.client.put(
            "/cameras/CAM-ADMIN-001",
            json={
                "name": "No Auth",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/test.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 401

    def test_unauthenticated_delete_returns_401(self):
        app.dependency_overrides.pop(get_current_user, None)

        response = self.client.delete(
            "/cameras/CAM-ADMIN-001"
        )

        assert response.status_code == 401

    def test_duplicate_camera_returns_conflict(self):
        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-ADMIN-001",
                "name": "Duplicate",
                "location": "Duplicate",
                "source_type": "file",
                "source": "data/input/duplicate.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 409

    def test_operator_cannot_create_camera(self):
        self.set_role("SECURITY_OPERATOR")

        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-ADMIN-002",
                "name": "Forbidden",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/forbidden.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 403

    def test_viewer_cannot_update_camera(self):
        self.set_role("VIEWER")

        response = self.client.put(
            "/cameras/CAM-ADMIN-001",
            json={
                "name": "Forbidden Update",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/forbidden.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 403

    def test_operator_cannot_delete_camera(self):
        self.set_role("SECURITY_OPERATOR")

        response = self.client.delete(
            "/cameras/CAM-ADMIN-001"
        )

        assert response.status_code == 403

    def test_operator_cannot_update_camera(self):
        self.set_role("SECURITY_OPERATOR")

        response = self.client.put(
            "/cameras/CAM-ADMIN-001",
            json={
                "name": "Forbidden Operator Update",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/forbidden.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 403


    def test_viewer_cannot_create_camera(self):
        self.set_role("VIEWER")

        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-VIEWER-CREATE",
                "name": "Forbidden Viewer Create",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/forbidden.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 403


    def test_viewer_cannot_delete_camera(self):
        self.set_role("VIEWER")

        response = self.client.delete(
            "/cameras/CAM-ADMIN-001"
        )

        assert response.status_code == 403


    def test_missing_camera_update_returns_404(self):
        response = self.client.put(
            "/cameras/CAM-MISSING",
            json={
                "name": "Missing",
                "location": "Nowhere",
                "source_type": "file",
                "source": "data/input/missing.mp4",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 404

    def test_invalid_source_type_is_rejected(self):
        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-INVALID",
                "name": "Invalid",
                "location": "Lobby",
                "source_type": "webcam",
                "source": "123",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 422

    def test_invalid_ai_fps_is_rejected(self):
        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-INVALID-FPS",
                "name": "Invalid FPS",
                "location": "Lobby",
                "source_type": "file",
                "source": "data/input/test.mp4",
                "ai_fps": 0,
            },
        )

        assert response.status_code == 422

    def test_blank_source_is_rejected(self):
        response = self.client.post(
            "/cameras",
            json={
                "camera_id": "CAM-BLANK",
                "name": "Blank Source",
                "location": "Lobby",
                "source_type": "file",
                "source": "   ",
                "ai_fps": 5.0,
            },
        )

        assert response.status_code == 422
