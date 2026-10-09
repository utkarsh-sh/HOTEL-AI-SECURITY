from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth_password import hash_password
from backend.auth_service import AuthService
from backend.login_rate_limiter import LoginRateLimiter
from backend.main import app
from database.user_database import UserDatabase


TEST_DATABASE = Path("database/test_login_api.db")
PASSWORD = "HotelSecurity@2026"


def _create_test_users():
    if TEST_DATABASE.exists():
        try:
            TEST_DATABASE.unlink()
        except PermissionError:
            pass

    database = UserDatabase(TEST_DATABASE)

    database.create_user(
        username="security",
        password_hash=hash_password(PASSWORD),
        full_name="Security Operator",
        role="SECURITY_OPERATOR",
    )

    database.create_user(
        username="disabled",
        password_hash=hash_password(PASSWORD),
        full_name="Disabled Operator",
        role="SECURITY_OPERATOR",
        active=False,
    )

    database.close()


def _make_client():
    limiter = LoginRateLimiter(
        max_failures=5,
        window_seconds=60,
    )

    def auth_service_factory():
        return AuthService(TEST_DATABASE)

    auth_service_patch = patch(
        "backend.main.AuthService",
        side_effect=auth_service_factory,
    )

    limiter_patch = patch(
        "backend.main.login_rate_limiter",
        limiter,
    )

    auth_service_patch.start()
    limiter_patch.start()

    return TestClient(app), auth_service_patch, limiter_patch


def test_invalid_username_and_password_return_same_error():
    _create_test_users()
    client, auth_patch, limiter_patch = _make_client()

    try:
        unknown_user = client.post(
            "/login",
            data={
                "username": "unknown",
                "password": PASSWORD,
            },
        )

        wrong_password = client.post(
            "/login",
            data={
                "username": "security",
                "password": "WrongPassword123!",
            },
        )

        inactive_user = client.post(
            "/login",
            data={
                "username": "disabled",
                "password": PASSWORD,
            },
        )

        assert unknown_user.status_code == 401
        assert wrong_password.status_code == 401
        assert inactive_user.status_code == 401

        assert unknown_user.json()["detail"] == (
            "Invalid username or password."
        )
        assert wrong_password.json()["detail"] == (
            "Invalid username or password."
        )
        assert inactive_user.json()["detail"] == (
            "Invalid username or password."
        )

    finally:
        auth_patch.stop()
        limiter_patch.stop()


def test_sixth_failed_login_attempt_is_rate_limited():
    _create_test_users()
    client, auth_patch, limiter_patch = _make_client()

    try:
        for _ in range(5):
            response = client.post(
                "/login",
                data={
                    "username": "security",
                    "password": "WrongPassword123!",
                },
            )

            assert response.status_code == 401

        response = client.post(
            "/login",
            data={
                "username": "security",
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 429
        assert response.json()["detail"] == (
            "Too many failed login attempts. Try again later."
        )
        retry_after = int(response.headers["Retry-After"])
        assert 1 <= retry_after <= 60

    finally:
        auth_patch.stop()
        limiter_patch.stop()


def test_successful_login_clears_failed_attempts():
    _create_test_users()
    client, auth_patch, limiter_patch = _make_client()

    try:
        for _ in range(4):
            response = client.post(
                "/login",
                data={
                    "username": "security",
                    "password": "WrongPassword123!",
                },
            )

            assert response.status_code == 401

        response = client.post(
            "/login",
            data={
                "username": "security",
                "password": PASSWORD,
            },
        )

        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert response.json()["user"]["username"] == "security"

        for _ in range(4):
            response = client.post(
                "/login",
                data={
                    "username": "security",
                    "password": "WrongPassword123!",
                },
            )

            assert response.status_code == 401

        response = client.post(
            "/login",
            data={
                "username": "security",
                "password": PASSWORD,
            },
        )

        assert response.status_code == 200

    finally:
        auth_patch.stop()
        limiter_patch.stop()


def test_health_and_metrics_remain_accessible():
    _create_test_users()
    client, auth_patch, limiter_patch = _make_client()

    try:
        health = client.get("/health")
        metrics = client.get("/metrics")

        assert health.status_code == 200
        assert metrics.status_code == 200

    finally:
        auth_patch.stop()
        limiter_patch.stop()
