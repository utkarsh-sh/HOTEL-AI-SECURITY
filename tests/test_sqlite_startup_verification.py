import pytest
from fastapi.testclient import TestClient

import backend.main as backend
import ai.run_intrusion_detection as runner


def test_api_startup_invokes_optional_verification_hook(monkeypatch):
    calls = []
    monkeypatch.delenv(
        "HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE",
        raising=False,
    )
    monkeypatch.setattr(
        backend,
        "verify_configured_journal_mode",
        lambda path: calls.append(path),
    )

    with TestClient(backend.app):
        pass

    assert calls == ["database/hotel_security.db"]


def test_api_startup_fails_when_verification_fails(monkeypatch):
    monkeypatch.setenv(
        "HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE",
        "WAL",
    )

    def reject_mode(path):
        raise RuntimeError("test journal mode mismatch")

    monkeypatch.setattr(
        backend,
        "verify_configured_journal_mode",
        reject_mode,
    )

    with pytest.raises(RuntimeError, match="journal mode mismatch"):
        with TestClient(backend.app):
            pass


def test_runner_verifies_before_database_initialization(monkeypatch):
    calls = []

    monkeypatch.setattr(
        runner,
        "verify_configured_journal_mode",
        lambda path: calls.append(("verify", path)),
    )

    def unexpected_database(*args, **kwargs):
        calls.append(("database", None))
        raise RuntimeError("stop after first database construction")

    monkeypatch.setattr(runner, "CameraDatabase", unexpected_database)

    with pytest.raises(RuntimeError, match="stop after first database"):
        runner.main()

    assert calls[0] == ("verify", "database/hotel_security.db")
    assert calls[1][0] == "database"
