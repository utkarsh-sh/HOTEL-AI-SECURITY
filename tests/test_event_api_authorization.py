from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.auth_jwt import create_access_token
from backend.auth_password import hash_password
from backend.main import app
from database.event_database import EventDatabase
from database.user_database import UserDatabase


TEST_EVENT_DATABASE = Path("database/test_event_api_authorization.db")
TEST_USER_DATABASE = Path("database/test_event_api_authorization_users.db")


@pytest.fixture
def test_users():
    if TEST_USER_DATABASE.exists():
        TEST_USER_DATABASE.unlink()

    database = UserDatabase(TEST_USER_DATABASE)

    try:
        admin_id = database.create_user(
            username="test_admin",
            password_hash=hash_password("TestPassword123!"),
            full_name="Test Administrator",
            role="ADMIN",
        )

        operator_id = database.create_user(
            username="test_operator",
            password_hash=hash_password("TestPassword123!"),
            full_name="Test Security Operator",
            role="SECURITY_OPERATOR",
        )

        viewer_id = database.create_user(
            username="test_viewer",
            password_hash=hash_password("TestPassword123!"),
            full_name="Test Security Viewer",
            role="VIEWER",
        )

        return {
            "ADMIN": admin_id,
            "SECURITY_OPERATOR": operator_id,
            "VIEWER": viewer_id,
        }
    finally:
        database.close()


@pytest.fixture
def tokens(test_users):
    return {
        role: create_access_token(
            {
                "id": user_id,
                "username": f"test_{role.lower()}",
                "full_name": f"Test {role}",
                "role": role,
            }
        )
        for role, user_id in test_users.items()
    }


@pytest.fixture
def client():
    for path in (TEST_EVENT_DATABASE, TEST_USER_DATABASE):
        if path.exists():
            path.unlink()

    event_database = EventDatabase(TEST_EVENT_DATABASE)

    try:
        event_id = event_database.create_event(
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-001",
            zone_id="restricted_01",
            zone_name="Restricted Area",
            track_id=7,
            message="Person 7 entered Restricted Area",
        )
    finally:
        event_database.close()

    try:
        with patch(
            "backend.main.EventDatabase",
            side_effect=lambda: EventDatabase(TEST_EVENT_DATABASE),
        ), patch(
            "backend.auth_dependencies.UserDatabase",
            side_effect=lambda: UserDatabase(TEST_USER_DATABASE),
        ):
            with TestClient(app) as test_client:
                test_client.test_event_id = event_id
                yield test_client
    finally:
        for path in (TEST_EVENT_DATABASE, TEST_USER_DATABASE):
            if path.exists():
                path.unlink()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_events_require_authentication(client):
    response = client.get("/events")

    assert response.status_code == 401


def test_viewer_can_read_events_but_cannot_modify(client, tokens):
    headers = auth_header(tokens["VIEWER"])

    response = client.get("/events", headers=headers)

    assert response.status_code == 200

    event_id = client.test_event_id

    response = client.post(
        f"/events/{event_id}/acknowledge",
        headers=headers,
    )

    assert response.status_code == 403


def test_security_operator_can_acknowledge_event(client, tokens):
    headers = auth_header(tokens["SECURITY_OPERATOR"])
    event_id = client.test_event_id

    response = client.post(
        f"/events/{event_id}/acknowledge",
        headers=headers,
    )

    assert response.status_code == 200


def test_admin_can_acknowledge_event(client, tokens):
    headers = auth_header(tokens["ADMIN"])
    event_id = client.test_event_id

    response = client.post(
        f"/events/{event_id}/acknowledge",
        headers=headers,
    )

    assert response.status_code == 200
