import sqlite3
import threading
import time

from database.event_database import EventDatabase


def test_event_database_waits_for_transient_sqlite_write_lock(tmp_path):
    """
    Regression test for the production SQLite timeout.

    A separate thread owns a SQLite connection and briefly holds a write
    lock. The application EventDatabase connection must wait for the lock
    to clear instead of immediately failing with "database is locked".
    """

    database_path = tmp_path / "events.db"

    # Initialize the database schema through the real application API.
    setup_db = EventDatabase(str(database_path))
    setup_db.close()

    lock_ready = threading.Event()
    release_lock = threading.Event()
    lock_errors = []

    def hold_write_lock():
        connection = sqlite3.connect(
            str(database_path),
            timeout=0.1,
            isolation_level=None,
        )

        try:
            connection.execute("BEGIN IMMEDIATE")
            lock_ready.set()

            assert release_lock.wait(timeout=2.0)

            connection.rollback()
        except Exception as exc:
            lock_errors.append(exc)
            lock_ready.set()
        finally:
            connection.close()

    lock_thread = threading.Thread(target=hold_write_lock)
    lock_thread.start()

    application_db = EventDatabase(str(database_path))

    try:
        assert lock_ready.wait(timeout=2.0)
        assert not lock_errors

        # Give the lock holder a short, deterministic interval before
        # releasing it. The application connection should wait for it.
        release_timer = threading.Timer(
            0.2,
            release_lock.set,
        )
        release_timer.start()

        try:
            started_at = time.monotonic()

            event_id = application_db.create_event(
                event_type="INTRUSION",
                severity="HIGH",
                camera_id="CAM-LOCK-TEST",
                zone_id=None,
                zone_name=None,
                track_id=None,
                message="SQLite transient lock regression test",
            )

            elapsed = time.monotonic() - started_at
        finally:
            release_timer.cancel()

        assert event_id is not None

        # The write must have waited for the transient lock rather than
        # failing immediately with "database is locked".
        assert elapsed >= 0.15

    finally:
        release_lock.set()
        application_db.close()
        lock_thread.join(timeout=2.0)

    assert not lock_thread.is_alive()
    assert not lock_errors

    verification_db = EventDatabase(str(database_path))

    try:
        events = verification_db.get_all_events()
    finally:
        verification_db.close()

    matching_events = [
        event
        for event in events
        if event["camera_id"] == "CAM-LOCK-TEST"
    ]

    assert len(matching_events) == 1
    assert matching_events[0]["event_type"] == "INTRUSION"
    assert matching_events[0]["severity"] == "HIGH"
