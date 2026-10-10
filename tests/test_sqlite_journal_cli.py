import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(database_path, mode):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.configure_sqlite_journal",
            "--database",
            str(database_path),
            "--mode",
            mode,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )


def get_journal_mode(database_path):
    with sqlite3.connect(database_path) as connection:
        return connection.execute("PRAGMA journal_mode").fetchone()[0].lower()


def test_cli_configures_and_verifies_wal(tmp_path):
    database_path = tmp_path / "cli-wal.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO sample VALUES (1)")

    result = run_cli(database_path, "WAL")

    assert result.returncode == 0, result.stderr
    assert "verified sqlite journal mode: wal" in result.stdout.lower()
    assert get_journal_mode(database_path) == "wal"

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT id FROM sample").fetchone() == (1,)


def test_cli_can_switch_back_to_delete(tmp_path):
    database_path = tmp_path / "cli-delete.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")

    assert run_cli(database_path, "WAL").returncode == 0

    result = run_cli(database_path, "DELETE")

    assert result.returncode == 0, result.stderr
    assert "verified sqlite journal mode: delete" in result.stdout.lower()
    assert get_journal_mode(database_path) == "delete"


def test_cli_rejects_missing_database(tmp_path):
    database_path = tmp_path / "missing.db"

    result = run_cli(database_path, "WAL")

    assert result.returncode == 1
    assert "database file does not exist" in result.stderr.lower()
    assert not database_path.exists()


def test_cli_rejects_invalid_mode(tmp_path):
    database_path = tmp_path / "invalid-mode.db"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.configure_sqlite_journal",
            "--database",
            str(database_path),
            "--mode",
            "TRUNCATE",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 2
    assert "invalid choice" in result.stderr.lower()
    assert not database_path.exists()
