import threading
import time

import pytest

from video.camera_worker_pool import (
    CameraWorkerPool,
    CameraWorkerResult,
)


def test_worker_pool_runs_all_cameras():
    pool = CameraWorkerPool(max_workers=2)

    def worker(camera_id):
        return f"processed-{camera_id}"

    results = pool.run(
        ["CAM-001", "CAM-002", "CAM-003"],
        worker,
    )

    assert len(results) == 3
    assert all(result.success for result in results)

    assert [result.camera_id for result in results] == [
        "CAM-001",
        "CAM-002",
        "CAM-003",
    ]

    assert [result.value for result in results] == [
        "processed-CAM-001",
        "processed-CAM-002",
        "processed-CAM-003",
    ]


def test_worker_failure_does_not_stop_other_cameras():
    pool = CameraWorkerPool(max_workers=2)

    def worker(camera_id):
        if camera_id == "CAM-002":
            raise RuntimeError("simulated camera failure")

        return f"processed-{camera_id}"

    results = pool.run(
        ["CAM-001", "CAM-002", "CAM-003"],
        worker,
    )

    assert results[0].success is True
    assert results[0].value == "processed-CAM-001"

    assert results[1].success is False
    assert "RuntimeError" in results[1].error
    assert "simulated camera failure" in results[1].error

    assert results[2].success is True
    assert results[2].value == "processed-CAM-003"


def test_worker_pool_is_actually_concurrent():
    pool = CameraWorkerPool(max_workers=2)

    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def worker(camera_id):
        nonlocal active, maximum_active

        with lock:
            active += 1
            maximum_active = max(maximum_active, active)

        time.sleep(0.15)

        with lock:
            active -= 1

        return camera_id

    start = time.perf_counter()

    results = pool.run(
        ["CAM-001", "CAM-002"],
        worker,
    )

    elapsed = time.perf_counter() - start

    assert all(result.success for result in results)
    assert maximum_active == 2

    # Two 150ms workers should overlap rather than take ~300ms.
    assert elapsed < 0.28


def test_worker_pool_respects_worker_limit():
    pool = CameraWorkerPool(max_workers=2)

    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def worker(camera_id):
        nonlocal active, maximum_active

        with lock:
            active += 1
            maximum_active = max(maximum_active, active)

        time.sleep(0.05)

        with lock:
            active -= 1

        return camera_id

    results = pool.run(
        ["CAM-001", "CAM-002", "CAM-003", "CAM-004"],
        worker,
    )

    assert all(result.success for result in results)
    assert maximum_active <= 2


def test_worker_pool_preserves_camera_order():
    pool = CameraWorkerPool(max_workers=3)

    def worker(camera_id):
        time.sleep(0.02 if camera_id == "CAM-001" else 0.01)
        return camera_id

    results = pool.run(
        ["CAM-001", "CAM-002", "CAM-003"],
        worker,
    )

    assert [result.camera_id for result in results] == [
        "CAM-001",
        "CAM-002",
        "CAM-003",
    ]


def test_duplicate_camera_ids_are_rejected():
    pool = CameraWorkerPool(max_workers=2)

    with pytest.raises(ValueError, match="Duplicate camera IDs"):
        pool.run(
            ["CAM-001", "CAM-001"],
            lambda camera_id: camera_id,
        )


def test_invalid_worker_count():
    with pytest.raises(ValueError):
        CameraWorkerPool(max_workers=0)

    with pytest.raises(TypeError):
        CameraWorkerPool(max_workers="2")


def test_invalid_worker():
    pool = CameraWorkerPool(max_workers=2)

    with pytest.raises(ValueError):
        pool.run(["CAM-001"], None)

    with pytest.raises(TypeError):
        pool.run(["CAM-001"], "not-callable")


def test_result_type():
    pool = CameraWorkerPool(max_workers=1)

    results = pool.run(
        ["CAM-001"],
        lambda camera_id: "done",
    )

    assert isinstance(results[0], CameraWorkerResult)
    assert results[0].camera_id == "CAM-001"
    assert results[0].success is True
    assert results[0].value == "done"
    assert results[0].error is None
