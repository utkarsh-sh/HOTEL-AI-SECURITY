import threading

from database.event_database import EventDatabase


def test_concurrent_event_writes_survive_sqlite_contention(tmp_path):
    database_path = tmp_path / "contention.db"

    workers = 8
    writes_per_worker = 5
    failures = []
    lock = threading.Lock()

    def worker(worker_id):
        database = EventDatabase(database_path)

        try:
            for iteration in range(writes_per_worker):
                try:
                    database.create_event(
                        event_type="SQLITE_CONTENTION_TEST",
                        severity="LOW",
                        camera_id=f"CAM-{worker_id:03d}",
                        zone_id=None,
                        zone_name=None,
                        track_id=iteration,
                        message=f"contention-{worker_id}-{iteration}",
                    )
                except Exception as exc:
                    with lock:
                        failures.append(exc)
        finally:
            database.close()

    threads = [
        threading.Thread(
            target=worker,
            args=(worker_id,),
        )
        for worker_id in range(workers)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    verifier = EventDatabase(database_path)

    try:
        count = verifier.connection.execute(
            """
            SELECT COUNT(*)
            FROM events
            WHERE event_type = 'SQLITE_CONTENTION_TEST'
            """
        ).fetchone()[0]
    finally:
        verifier.close()

    expected = workers * writes_per_worker

    assert not failures, (
        f"Concurrent SQLite writes failed: {failures}"
    )
    assert count == expected
