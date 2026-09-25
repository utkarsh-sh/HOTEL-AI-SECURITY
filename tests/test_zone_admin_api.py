from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth_dependencies import get_current_user
from backend.main import app
from database.audit_database import AuditDatabase
from database.camera_database import CameraDatabase
from database.zone_database import ZoneDatabase


CAMERA_DB = Path("database/test_zone_admin_api_camera.db")
ZONE_DB = Path("database/test_zone_admin_api_zone.db")
AUDIT_DB = Path("database/test_zone_admin_api_audit.db")


class TestZoneAdminAPI:
    def setup_method(self):
        for path in (CAMERA_DB, ZONE_DB, AUDIT_DB):
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    pass

        camera_db = CameraDatabase(CAMERA_DB)
        camera_db.create_camera(
            camera_id="CAM-ZONE-001",
            name="Zone Camera",
            location="Lobby",
            source_type="file",
            source="data/input/test.mp4",
            ai_fps=5.0,
        )
        camera_db.close()

        self.user = {
            "id": 1,
            "username": "zone-admin-test",
            "full_name": "Zone Admin Test",
            "role": "ADMIN",
            "active": True,
        }

        app.dependency_overrides[get_current_user] = lambda: self.user

        self.camera_patch = patch(
            "backend.main.CameraDatabase",
            side_effect=lambda: CameraDatabase(CAMERA_DB),
        )
        self.zone_patch = patch(
            "backend.main.ZoneDatabase",
            side_effect=lambda: ZoneDatabase(ZONE_DB),
        )
        self.audit_patch = patch(
            "backend.main.AuditDatabase",
            side_effect=lambda: AuditDatabase(AUDIT_DB),
        )

        self.camera_patch.start()
        self.zone_patch.start()
        self.audit_patch.start()
        self.client = TestClient(app)

    def teardown_method(self):
        try:
            self.client.close()
        finally:
            self.camera_patch.stop()
            self.zone_patch.stop()
            self.audit_patch.stop()
            app.dependency_overrides.clear()

        for path in (CAMERA_DB, ZONE_DB, AUDIT_DB):
            if path.exists():
                try:
                    path.unlink()
                except PermissionError:
                    pass

    def set_role(self, role):
        self.user["role"] = role

    def payload(self, zone_id="ZONE-001"):
        return {
            "zone_id": zone_id,
            "camera_id": "CAM-ZONE-001",
            "name": "Lobby Restricted Zone",
            "type": "restricted",
            "points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        }

    def test_admin_can_create_zone(self):
        response = self.client.post("/zones", json=self.payload())

        assert response.status_code == 200
        body = response.json()
        assert body["runner_reload_required"] is True
        assert body["zone"]["zone_id"] == "ZONE-001"
        assert body["zone"]["camera_id"] == "CAM-ZONE-001"

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        assert any(
            log["action"] == "ZONE_CREATED"
            and log["entity_id"] == "ZONE-001"
            and log["actor"] == "zone-admin-test"
            for log in logs
        )

    def test_admin_can_read_zone(self):
        self.client.post("/zones", json=self.payload())

        response = self.client.get("/zones/ZONE-001")
        assert response.status_code == 200
        assert response.json()["name"] == "Lobby Restricted Zone"

        listed = self.client.get("/zones")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

    def test_admin_can_update_zone(self):
        self.client.post("/zones", json=self.payload())

        response = self.client.put(
            "/zones/ZONE-001",
            json={
                "camera_id": "CAM-ZONE-001",
                "name": "Updated Zone",
                "type": "after_hours",
                "points": [[1, 1], [200, 1], [200, 200]],
            },
        )

        assert response.status_code == 200
        assert response.json()["zone"]["name"] == "Updated Zone"
        assert response.json()["zone"]["type"] == "after_hours"

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        assert any(
            log["action"] == "ZONE_UPDATED"
            and log["entity_id"] == "ZONE-001"
            for log in logs
        )

    def test_admin_can_delete_zone(self):
        self.client.post("/zones", json=self.payload())

        response = self.client.delete("/zones/ZONE-001")
        assert response.status_code == 200

        assert self.client.get("/zones/ZONE-001").status_code == 404

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        assert any(
            log["action"] == "ZONE_DELETED"
            and log["entity_id"] == "ZONE-001"
            for log in logs
        )

    def test_unauthenticated_create_returns_401(self):
        app.dependency_overrides.pop(get_current_user, None)
        response = self.client.post("/zones", json=self.payload())
        assert response.status_code == 401

    def test_unauthenticated_update_returns_401(self):
        app.dependency_overrides.pop(get_current_user, None)
        response = self.client.put(
            "/zones/ZONE-001",
            json={
                "camera_id": "CAM-ZONE-001",
                "name": "Zone",
                "type": "restricted",
                "points": [[0, 0], [1, 0], [1, 1]],
            },
        )
        assert response.status_code == 401

    def test_unauthenticated_delete_returns_401(self):
        app.dependency_overrides.pop(get_current_user, None)
        response = self.client.delete("/zones/ZONE-001")
        assert response.status_code == 401

    def test_viewer_cannot_create_zone(self):
        self.set_role("VIEWER")
        assert self.client.post("/zones", json=self.payload()).status_code == 403

    def test_viewer_cannot_update_zone(self):
        self.set_role("VIEWER")
        assert self.client.put(
            "/zones/ZONE-001",
            json={
                "camera_id": "CAM-ZONE-001",
                "name": "Zone",
                "type": "restricted",
                "points": [[0, 0], [1, 0], [1, 1]],
            },
        ).status_code == 403

    def test_viewer_cannot_delete_zone(self):
        self.set_role("VIEWER")
        assert self.client.delete("/zones/ZONE-001").status_code == 403

    def test_operator_cannot_create_zone(self):
        self.set_role("SECURITY_OPERATOR")
        assert self.client.post("/zones", json=self.payload()).status_code == 403

    def test_operator_cannot_update_zone(self):
        self.set_role("SECURITY_OPERATOR")
        assert self.client.put(
            "/zones/ZONE-001",
            json={
                "camera_id": "CAM-ZONE-001",
                "name": "Zone",
                "type": "restricted",
                "points": [[0, 0], [1, 0], [1, 1]],
            },
        ).status_code == 403

    def test_operator_cannot_delete_zone(self):
        self.set_role("SECURITY_OPERATOR")
        assert self.client.delete("/zones/ZONE-001").status_code == 403

    def test_duplicate_zone_returns_conflict(self):
        self.client.post("/zones", json=self.payload())
        response = self.client.post("/zones", json=self.payload())
        assert response.status_code == 409

    def test_unknown_camera_returns_422(self):
        payload = self.payload()
        payload["camera_id"] = "CAM-MISSING"
        response = self.client.post("/zones", json=payload)
        assert response.status_code == 422

    def test_missing_zone_returns_404(self):
        response = self.client.get("/zones/ZONE-MISSING")
        assert response.status_code == 404

    def test_degenerate_polygon_returns_422(self):
        payload = self.payload()
        payload["points"] = [[0, 0], [1, 1], [2, 2]]
        response = self.client.post("/zones", json=payload)
        assert response.status_code == 422

    def test_malformed_point_returns_422(self):
        payload = self.payload()
        payload["points"] = [[0, 0], [1], [2, 2]]
        response = self.client.post("/zones", json=payload)
        assert response.status_code == 422

    def test_blank_fields_return_422(self):
        payload = self.payload()
        payload["name"] = "   "
        response = self.client.post("/zones", json=payload)
        assert response.status_code == 422

    def test_create_does_not_write_credentials_or_unrelated_data(self):
        response = self.client.post("/zones", json=self.payload())
        assert response.status_code == 200

        audit = AuditDatabase(AUDIT_DB)
        logs = audit.get_all_logs()
        audit.close()

        details = next(
            log["details"]
            for log in logs
            if log["action"] == "ZONE_CREATED"
        )
        assert "password" not in details.lower()
        assert "rtsp://" not in details.lower()
