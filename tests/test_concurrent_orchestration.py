from pathlib import Path
import ai.run_intrusion_detection as runner
from video.camera_worker_pool import CameraWorkerResult


def test_concurrent_orchestration_dispatches_open_cameras(monkeypatch):
    calls = []

    class FakePool:
        def __init__(self, max_workers):
            calls.append(("pool_init", max_workers))
            self.max_workers = max_workers

        def run(self, camera_ids, worker):
            calls.append(("pool_run", list(camera_ids)))

            results = []

            for camera_id in camera_ids:
                value = worker(camera_id)

                results.append(
                    CameraWorkerResult(
                        camera_id=camera_id,
                        success=True,
                        value=value,
                    )
                )

            return results

    def fake_worker(**kwargs):
        camera_id = kwargs["camera_config"].camera_id

        calls.append(("worker", camera_id))

        return {
            "camera_id": camera_id,
            "success": True,
            "frames": 100,
            "ai_frames": 20,
            "events": 1,
            "output_path": None,
            "error": None,
        }

    monkeypatch.setattr(
        runner,
        "CameraWorkerPool",
        FakePool,
    )

    monkeypatch.setattr(
        runner,
        "process_camera_worker",
        fake_worker,
    )

    configs = []

    for camera_id in ["CAM-001", "CAM-002"]:
        configs.append(
            type(
                "CameraConfig",
                (),
                {
                    "camera_id": camera_id,
                    "name": f"Camera {camera_id}",
                    "location": "Test",
                },
            )()
        )

    opened = {"CAM-001", "CAM-002"}

    opened_configs = [
        config
        for config in configs
        if config.camera_id in opened
    ]

    camera_configs_by_id = {
        config.camera_id: config
        for config in opened_configs
    }

    worker_pool = runner.CameraWorkerPool(
        max_workers=2
    )

    def camera_worker(camera_id):
        return runner.process_camera_worker(
            camera_config=camera_configs_by_id[camera_id],
            camera_manager="manager",
            detector="detector",
            zones=[],
            zone_detector="zone_detector",
        )

    results = worker_pool.run(
        camera_ids=[
            config.camera_id
            for config in opened_configs
        ],
        worker=camera_worker,
    )

    assert worker_pool.max_workers == 2

    assert [
        result.camera_id
        for result in results
    ] == [
        "CAM-001",
        "CAM-002",
    ]

    assert all(
        result.success
        for result in results
    )

    assert calls[0] == ("pool_init", 2)

    assert calls[1] == (
        "pool_run",
        ["CAM-001", "CAM-002"],
    )


def test_concurrent_orchestration_isolates_worker_failure():
    pool = runner.CameraWorkerPool(
        max_workers=2
    )

    def worker(camera_id):
        if camera_id == "CAM-002":
            raise RuntimeError(
                "simulated camera failure"
            )

        return {
            "camera_id": camera_id,
            "success": True,
        }

    results = pool.run(
        camera_ids=[
            "CAM-001",
            "CAM-002",
        ],
        worker=worker,
    )

    assert len(results) == 2

    first = results[0]
    second = results[1]

    assert first.camera_id == "CAM-001"
    assert first.success is True
    assert first.value["camera_id"] == "CAM-001"

    assert second.camera_id == "CAM-002"
    assert second.success is False
    assert "RuntimeError" in second.error
    assert "simulated camera failure" in second.error
