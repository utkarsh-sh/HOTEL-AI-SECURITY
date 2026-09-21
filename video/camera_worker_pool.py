from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, Any


@dataclass(frozen=True)
class CameraWorkerResult:
    camera_id: str
    success: bool
    value: Any = None
    error: str | None = None


class CameraWorkerPool:
    """
    Bounded concurrent execution for independent camera workers.

    A worker failure is isolated to that camera and does not
    terminate processing for the remaining cameras.
    """

    def __init__(self, max_workers: int = 2):
        if not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")

        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")

        self.max_workers = max_workers

    def run(
        self,
        camera_ids: Iterable[str],
        worker: Callable[[str], Any],
    ) -> list[CameraWorkerResult]:
        camera_ids = list(camera_ids)

        if worker is None:
            raise ValueError("worker must be callable")

        if not callable(worker):
            raise TypeError("worker must be callable")

        if len(set(camera_ids)) != len(camera_ids):
            raise ValueError("Duplicate camera IDs are not allowed")

        results = {}

        with ThreadPoolExecutor(
            max_workers=min(self.max_workers, max(1, len(camera_ids))),
            thread_name_prefix="camera-worker",
        ) as executor:

            futures = {
                executor.submit(worker, camera_id): camera_id
                for camera_id in camera_ids
            }

            for future in as_completed(futures):
                camera_id = futures[future]

                try:
                    value = future.result()

                    results[camera_id] = CameraWorkerResult(
                        camera_id=camera_id,
                        success=True,
                        value=value,
                    )

                except Exception as exc:
                    results[camera_id] = CameraWorkerResult(
                        camera_id=camera_id,
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )

        return [
            results[camera_id]
            for camera_id in camera_ids
        ]
