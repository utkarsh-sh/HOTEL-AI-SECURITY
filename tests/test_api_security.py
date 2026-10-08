from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_testclient_host_remains_allowed():
    response = client.get("/health")

    assert response.status_code == 200


def test_localhost_host_is_allowed():
    response = client.get(
        "/health",
        headers={"host": "localhost"},
    )

    assert response.status_code == 200


def test_loopback_host_is_allowed():
    response = client.get(
        "/health",
        headers={"host": "127.0.0.1"},
    )

    assert response.status_code == 200


def test_untrusted_host_is_rejected():
    response = client.get(
        "/health",
        headers={"host": "attacker.example"},
    )

    assert response.status_code == 400


def test_security_headers_are_present():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
