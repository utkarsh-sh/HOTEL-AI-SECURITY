from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.auth_password import hash_password
from backend.auth_service import UserDatabase
from backend.auth_jwt import create_access_token
from backend.main import app
from database.event_database import EventDatabase
from database.notification_database import NotificationDatabase


TEST_EVENT_DATABASE = Path(
    "database/test_notification_api_events.db"
)

TEST_NOTIFICATION_DATABASE = Path(
    "database/test_notification_api_notifications.db"
)

TEST_USER_DATABASE = Path(
    "database/test_notification_api_users.db"
)


@pytest.fixture
def test_user():
    database = UserDatabase(
        database_path=TEST_USER_DATABASE
    )

    try:
        user_id = database.create_user(
            username="notification_viewer",
            password_hash=hash_password("test-password"),
            full_name="Notification Viewer",
            role="VIEWER",
        )

        return {
            "id": user_id,
            "username": "notification_viewer",
            "full_name": "Notification Viewer",
            "role": "VIEWER",
        }

    finally:
        database.close()


@pytest.fixture
def access_token(test_user):
    return create_access_token(test_user)


@pytest.fixture
def notification_records():
    event_database = EventDatabase(
        database_path=TEST_EVENT_DATABASE
    )

    notification_database = NotificationDatabase(
        database_path=TEST_NOTIFICATION_DATABASE
    )

    try:
        event_id = event_database.create_event(
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-001",
            zone_id="restricted_01",
            zone_name="Restricted Area",
            track_id=7,
            message="Person 7 entered Restricted Area",
            model_version="test-v1",
            evidence_path=None,
        )

        first_notification_id = (
            notification_database.create_notification(
                event_id=event_id,
                channel="CONSOLE",
                severity="HIGH",
                provider="TEST_PROVIDER",
                recipient=None,
            )
        )

        second_notification_id = (
            notification_database.create_notification(
                event_id=event_id,
                channel="CONSOLE",
                severity="HIGH",
                provider="TEST_PROVIDER",
                recipient=None,
            )
        )

        notification_database.update_status(
            notification_id=first_notification_id,
            status="SENT",
        )

        return {
            "event_id": event_id,
            "first_notification_id": first_notification_id,
            "second_notification_id": second_notification_id,
        }

    finally:
        notification_database.close()
        event_database.close()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        "backend.notification_routes.NotificationDatabase",
        lambda: NotificationDatabase(
            database_path=TEST_NOTIFICATION_DATABASE
        ),
    )

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def cleanup_databases():
    for database_path in (
        TEST_EVENT_DATABASE,
        TEST_NOTIFICATION_DATABASE,
        TEST_USER_DATABASE,
    ):
        if database_path.exists():
            database_path.unlink()

    yield

    for database_path in (
        TEST_EVENT_DATABASE,
        TEST_NOTIFICATION_DATABASE,
        TEST_USER_DATABASE,
    ):
        if database_path.exists():
            database_path.unlink()


def authorization_header(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def test_notifications_require_authentication(client):
    response = client.get("/notifications")

    assert response.status_code == 401


def test_authenticated_user_can_list_notifications(
    client,
    access_token,
    notification_records,
):
    response = client.get(
        "/notifications",
        headers=authorization_header(access_token),
    )

    assert response.status_code == 200

    payload = response.json()

    assert "notifications" in payload
    assert len(payload["notifications"]) == 2


def test_authenticated_user_can_get_notification(
    client,
    access_token,
    notification_records,
):
    notification_id = notification_records[
        "first_notification_id"
    ]

    response = client.get(
        f"/notifications/{notification_id}",
        headers=authorization_header(access_token),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["notification"]["id"] == notification_id
    assert payload["notification"]["status"] == "SENT"


def test_missing_notification_returns_404(
    client,
    access_token,
):
    response = client.get(
        "/notifications/999999",
        headers=authorization_header(access_token),
    )

    assert response.status_code == 404


def test_authenticated_user_can_get_event_notifications(
    client,
    access_token,
    notification_records,
):
    event_id = notification_records["event_id"]

    response = client.get(
        f"/notifications/event/{event_id}",
        headers=authorization_header(access_token),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["event_id"] == event_id
    assert len(payload["notifications"]) == 2

    returned_event_ids = {
        notification["event_id"]
        for notification in payload["notifications"]
    }

    assert returned_event_ids == {event_id}


def test_event_without_notifications_returns_empty_list(
    client,
    access_token,
):
    response = client.get(
        "/notifications/event/999999",
        headers=authorization_header(access_token),
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["event_id"] == 999999
    assert payload["notifications"] == []
