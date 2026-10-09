from pathlib import Path

from fastapi.testclient import TestClient

from backend.auth_jwt import create_access_token
from backend.auth_password import hash_password
from backend.main import app
from database.audit_database import AuditDatabase
from database.user_database import UserDatabase


TEST_USER_DATABASE = Path("database/test_audit_api_users.db")
TEST_AUDIT_DATABASE = Path("database/test_audit_api_audit.db")


def setup_test_databases():
    for path in (TEST_USER_DATABASE, TEST_AUDIT_DATABASE):
        if path.exists():
            path.unlink()

    user_database = UserDatabase(TEST_USER_DATABASE)

    try:
        user_database.create_user(
            username="audit-test-user",
            password_hash=hash_password("TestPassword123!"),
            full_name="Audit Test User",
            role="ADMIN",
        )
    finally:
        user_database.close()

    audit_database = AuditDatabase(TEST_AUDIT_DATABASE)

    try:
        for index in range(5):
            audit_database.create_log(
                action=f"ACTION_{index}",
                entity_type="event",
                entity_id=index,
                actor="audit-test-user",
                details=f"Test audit log {index}",
            )

        audit_database.create_log(
            action="CAMERA_UPDATED",
            entity_type="camera",
            entity_id=99,
            actor="audit-test-user",
            details="Camera test",
        )
    finally:
        audit_database.close()


def teardown_test_databases():
    for path in (TEST_USER_DATABASE, TEST_AUDIT_DATABASE):
        if path.exists():
            path.unlink()


def get_client(monkeypatch):
    setup_test_databases()

    monkeypatch.setenv(
        "HOTEL_SECURITY_JWT_SECRET",
        "test-secret-for-hotel-security-p3-3-2026-strong",
    )

    monkeypatch.setattr(
        "backend.auth_dependencies.UserDatabase",
        lambda: UserDatabase(TEST_USER_DATABASE),
    )

    monkeypatch.setattr(
        "backend.main.AuditDatabase",
        lambda: AuditDatabase(TEST_AUDIT_DATABASE),
    )

    return TestClient(app)


def admin_headers():
    token = create_access_token(
        {
            "id": 1,
            "username": "audit-test-user",
            "full_name": "Audit Test User",
            "role": "ADMIN",
        }
    )

    return {
        "Authorization": f"Bearer {token}"
    }


def test_audit_logs_requires_authentication(monkeypatch):
    client = get_client(monkeypatch)

    try:
        response = client.get("/audit-logs")

        assert response.status_code == 401

    finally:
        client.close()
        teardown_test_databases()


def test_audit_logs_supports_pagination(monkeypatch):
    client = get_client(monkeypatch)

    try:
        response = client.get(
            "/audit-logs?page=2&page_size=2",
            headers=admin_headers(),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["total"] == 6
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert len(data["logs"]) == 2

    finally:
        client.close()
        teardown_test_databases()


def test_audit_logs_supports_entity_filter(monkeypatch):
    client = get_client(monkeypatch)

    try:
        response = client.get(
            "/audit-logs"
            "?entity_type=event"
            "&entity_id=2"
            "&page=1"
            "&page_size=10",
            headers=admin_headers(),
        )

        assert response.status_code == 200

        data = response.json()

        assert data["total"] == 1
        assert len(data["logs"]) == 1
        assert data["logs"][0]["entity_type"] == "event"
        assert data["logs"][0]["entity_id"] == "2"

    finally:
        client.close()
        teardown_test_databases()


def test_audit_logs_rejects_invalid_pagination(monkeypatch):
    client = get_client(monkeypatch)

    try:
        headers = admin_headers()

        response = client.get(
            "/audit-logs?page=0",
            headers=headers,
        )
        assert response.status_code == 422

        response = client.get(
            "/audit-logs?page_size=101",
            headers=headers,
        )
        assert response.status_code == 422

    finally:
        client.close()
        teardown_test_databases()
