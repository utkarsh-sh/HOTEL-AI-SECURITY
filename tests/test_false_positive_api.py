from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.auth_jwt import create_access_token
from backend.auth_password import hash_password
from backend.main import app
from database.audit_database import AuditDatabase
from database.event_database import EventDatabase
from database.user_database import UserDatabase


TEST_EVENT_DATABASE = Path(
    "database/test_false_positive_api.db"
)
TEST_USER_DATABASE = Path(
    "database/test_false_positive_api_users.db"
)
TEST_AUDIT_DATABASE = Path(
    "database/test_false_positive_api_audit.db"
)


@pytest.fixture
def test_users():
    if TEST_USER_DATABASE.exists():
        TEST_USER_DATABASE.unlink()

    database = UserDatabase(TEST_USER_DATABASE)

    try:
        admin_id = database.create_user(
            username="fp_admin",
            password_hash=hash_password("TestPassword123!"),
            full_name="False Positive Administrator",
            role="ADMIN",
        )

        operator_id = database.create_user(
            username="fp_operator",
            password_hash=hash_password("TestPassword123!"),
            full_name="False Positive Operator",
            role="SECURITY_OPERATOR",
        )

        viewer_id = database.create_user(
            username="fp_viewer",
            password_hash=hash_password("TestPassword123!"),
            full_name="False Positive Viewer",
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
                "username": (
                    "fp_admin"
                    if role == "ADMIN"
                    else "fp_operator"
                    if role == "SECURITY_OPERATOR"
                    else "fp_viewer"
                ),
                "full_name": f"False Positive {role}",
                "role": role,
            }
        )
        for role, user_id in test_users.items()
    }


@pytest.fixture
def client():
    for path in (
        TEST_EVENT_DATABASE,
        TEST_USER_DATABASE,
        TEST_AUDIT_DATABASE,
    ):
        if path.exists():
            path.unlink()

    event_database = EventDatabase(TEST_EVENT_DATABASE)

    try:
        event_id = event_database.create_event(
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-FP-001",
            zone_id="restricted_01",
            zone_name="Restricted Area",
            track_id=7,
            message="Person 7 entered Restricted Area",
            model_version="test-model",
        )
    finally:
        event_database.close()

    try:
        with patch(
            "backend.main.EventDatabase",
            side_effect=lambda: EventDatabase(
                TEST_EVENT_DATABASE
            ),
        ), patch(
            "backend.auth_dependencies.UserDatabase",
            side_effect=lambda: UserDatabase(
                TEST_USER_DATABASE
            ),
        ), patch(
            "backend.main.AuditDatabase",
            side_effect=lambda: AuditDatabase(
                TEST_AUDIT_DATABASE
            ),
        ):
            with TestClient(app) as test_client:
                test_client.test_event_id = event_id
                yield test_client
    finally:
        for path in (
            TEST_EVENT_DATABASE,
            TEST_USER_DATABASE,
            TEST_AUDIT_DATABASE,
        ):
            if path.exists():
                path.unlink()


def auth_header(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}"
    }


def test_security_operator_can_mark_false_positive(
    client,
    tokens,
):
    response = client.post(
        f"/events/{client.test_event_id}/false-positive",
        headers=auth_header(tokens["SECURITY_OPERATOR"]),
        json={
            "resolution": "Authorized hotel employee.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["message"] == (
        "Event marked as false positive"
    )
    assert body["event"]["status"] == "FALSE_POSITIVE"
    assert body["event"]["resolution"] == (
        "Authorized hotel employee."
    )


def test_admin_can_mark_false_positive(
    client,
    tokens,
):
    response = client.post(
        f"/events/{client.test_event_id}/false-positive",
        headers=auth_header(tokens["ADMIN"]),
        json={
            "resolution": "False alarm verified by security.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["event"]["status"] == "FALSE_POSITIVE"


def test_viewer_cannot_mark_false_positive(
    client,
    tokens,
):
    response = client.post(
        f"/events/{client.test_event_id}/false-positive",
        headers=auth_header(tokens["VIEWER"]),
        json={
            "resolution": "Viewer should not be allowed.",
        },
    )

    assert response.status_code == 403


def test_false_positive_is_persisted_and_audited(
    client,
    tokens,
):
    reason = "Security operator verified authorized activity."

    response = client.post(
        f"/events/{client.test_event_id}/false-positive",
        headers=auth_header(tokens["SECURITY_OPERATOR"]),
        json={
            "resolution": reason,
        },
    )

    assert response.status_code == 200

    event_database = EventDatabase(
        TEST_EVENT_DATABASE
    )

    try:
        event = event_database.get_event(
            client.test_event_id
        )
    finally:
        event_database.close()

    assert event is not None
    assert event["status"] == "FALSE_POSITIVE"
    assert event["resolution"] == reason

    audit_database = AuditDatabase(
        TEST_AUDIT_DATABASE
    )

    try:
        logs = audit_database.get_logs_for_entity(
            "event",
            client.test_event_id,
        )
    finally:
        audit_database.close()

    false_positive_logs = [
        log
        for log in logs
        if log["action"] == "EVENT_FALSE_POSITIVE"
    ]

    assert len(false_positive_logs) == 1

    audit_log = false_positive_logs[0]

    assert audit_log["actor"] == "fp_operator"
    assert audit_log["entity_type"] == "event"
    assert str(audit_log["entity_id"]) == str(client.test_event_id)
    assert audit_log["details"] == reason


def test_false_positive_endpoint_requires_authentication(
    client,
):
    response = client.post(
        f"/events/{client.test_event_id}/false-positive",
        json={
            "resolution": "Unauthenticated request.",
        },
    )

    assert response.status_code == 401
