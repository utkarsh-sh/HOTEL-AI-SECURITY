import sqlite3

import pytest

from database.sqlite_setup import configure_journal_mode


def read_journal_mode(database_path):
    connection = sqlite3.connect(str(database_path), timeout=10.0)
    try:
        return connection.execute("PRAGMA journal_mode").fetchone()[0].lower()
    finally:
        connection.close()


def test_configure_wal_on_temporary_database(tmp_path):
    database_path = tmp_path / "wal_test.db"
    assert configure_journal_mode(database_path, "WAL") == "wal"
    assert read_journal_mode(database_path) == "wal"


def test_repeated_wal_initialization_is_safe(tmp_path):
    database_path = tmp_path / "repeated_wal_test.db"
    assert configure_journal_mode(database_path, "WAL") == "wal"
    assert configure_journal_mode(database_path, "WAL") == "wal"
    assert read_journal_mode(database_path) == "wal"


def test_delete_mode_can_be_explicitly_selected(tmp_path):
    database_path = tmp_path / "delete_test.db"
    assert configure_journal_mode(database_path, "WAL") == "wal"
    assert configure_journal_mode(database_path, "DELETE") == "delete"
    assert read_journal_mode(database_path) == "delete"


def test_unsupported_mode_is_rejected_before_opening_database(tmp_path):
    database_path = tmp_path / "unsupported_test.db"
    with pytest.raises(ValueError, match="Unsupported journal mode"):
        configure_journal_mode(database_path, "OFF")
    assert not database_path.exists()


def test_existing_data_is_preserved_when_enabling_wal(tmp_path):
    database_path = tmp_path / "existing_data_test.db"
    connection = sqlite3.connect(str(database_path))
    try:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO sample (value) VALUES (?)", ("preserve-me",)
        )
        connection.commit()
    finally:
        connection.close()

    assert configure_journal_mode(database_path, "WAL") == "wal"

    connection = sqlite3.connect(str(database_path))
    try:
        assert connection.execute("SELECT value FROM sample").fetchone() == (
            "preserve-me",
        )
    finally:
        connection.close()

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


def test_concurrent_wal_initialization(tmp_path):
    database_path = tmp_path / "concurrent_wal_test.db"
    worker_count = 4
    barrier = Barrier(worker_count)

    def initialize():
        barrier.wait(timeout=10)
        return configure_journal_mode(database_path, "WAL")

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(lambda _: initialize(), range(worker_count)))

    assert results == ["wal"] * worker_count
    assert read_journal_mode(database_path) == "wal"

import multiprocessing


def _initialize_wal_in_process(database_path, start_event, result_queue):
    try:
        if not start_event.wait(timeout=10):
            result_queue.put(("error", "Timed out waiting for start signal"))
            return

        result = configure_journal_mode(database_path, "WAL")
        result_queue.put(("ok", result))
    except Exception as exc:
        result_queue.put(("error", repr(exc)))


def test_concurrent_wal_initialization_across_processes(tmp_path):
    database_path = str(tmp_path / "multiprocess_wal_test.db")
    worker_count = 4
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    result_queue = context.Queue()

    processes = [
        context.Process(
            target=_initialize_wal_in_process,
            args=(database_path, start_event, result_queue),
        )
        for _ in range(worker_count)
    ]

    try:
        for process in processes:
            process.start()

        start_event.set()

        for process in processes:
            process.join(timeout=15)

        still_running = [
            process for process in processes if process.is_alive()
        ]
        for process in still_running:
            process.terminate()
            process.join(timeout=5)

        assert not still_running, "A WAL initializer process hung"
        assert all(process.exitcode == 0 for process in processes), [
            process.exitcode for process in processes
        ]

        results = [result_queue.get(timeout=3) for _ in processes]
        errors = [result for result in results if result[0] != "ok"]

        assert not errors, f"Process initialization failures: {errors}"
        assert [result[1] for result in results] == ["wal"] * worker_count
        assert read_journal_mode(database_path) == "wal"
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

        result_queue.close()
        result_queue.join_thread()

def test_journal_mode_must_be_explicit(tmp_path):
    database_path = tmp_path / "implicit_mode_test.db"

    with pytest.raises(TypeError):
        configure_journal_mode(database_path)

    assert not database_path.exists()
