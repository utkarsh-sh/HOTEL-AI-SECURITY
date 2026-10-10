import sqlite3
from pathlib import Path

import pytest

from database.sqlite_setup import verify_journal_mode


def create_database(path: Path, mode: str = "DELETE") -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(f"PRAGMA journal_mode={mode}")
    finally:
        connection.close()


def test_verify_delete_mode(tmp_path):
    path = tmp_path / "test.db"
    create_database(path)

    assert verify_journal_mode(path, "DELETE") == "delete"


def test_verify_wal_mode(tmp_path):
    path = tmp_path / "test.db"
    create_database(path, "WAL")

    assert verify_journal_mode(path, "WAL") == "wal"


def test_mismatched_mode_raises(tmp_path):
    path = tmp_path / "test.db"
    create_database(path)

    with pytest.raises(RuntimeError, match="journal mode mismatch"):
        verify_journal_mode(path, "WAL")


def test_missing_database_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_journal_mode(tmp_path / "missing.db", "WAL")


def test_invalid_mode_raises(tmp_path):
    path = tmp_path / "test.db"
    create_database(path)

    with pytest.raises(ValueError, match="Unsupported journal mode"):
        verify_journal_mode(path, "MEMORY")
from database.sqlite_setup import verify_configured_journal_mode


def test_configured_mode_is_optional_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv(
        "HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE",
        raising=False,
    )

    # With no setting, no database access is needed.
    assert verify_configured_journal_mode(
        tmp_path / "database-does-not-exist.db"
    ) is None


def test_configured_mode_verifies_existing_database(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "test.db"
    connection = sqlite3.connect(path)
    connection.close()

    monkeypatch.setenv(
        "HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE",
        "DELETE",
    )

    assert verify_configured_journal_mode(path) == "delete"


def test_configured_mode_rejects_invalid_value(tmp_path, monkeypatch):
    import sqlite3
    import pytest

    path = tmp_path / "test.db"
    connection = sqlite3.connect(path)
    connection.close()

    monkeypatch.setenv(
        "HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE",
        "INVALID",
    )

    with pytest.raises(ValueError, match="Unsupported journal mode"):
        verify_configured_journal_mode(path)
