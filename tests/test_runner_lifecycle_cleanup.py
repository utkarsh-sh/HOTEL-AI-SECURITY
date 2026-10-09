import pytest

import ai.run_intrusion_detection as runner


class FakeDatabase:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self.metadata = {}

    def get_metadata(self, key):
        return "1"

    def initialize_from_bootstrap(self, *args, **kwargs):
        pass

    def ensure_camera(self, **kwargs):
        return {
            "camera_id": kwargs["camera_id"],
            "name": kwargs["name"],
            "location": kwargs["location"],
            "status": "OFFLINE",
        }

    def close(self):
        self.closed = True


class FakeCameraManager:
    instances = []

    def __init__(self, configs):
        self.configs = configs
        self.open_errors = {}
        self.release_called = False
        self.__class__.instances.append(self)

    def __len__(self):
        return len(self.configs)

    def open_all(self):
        return {
            config.camera_id: object()
            for config in self.configs
        }

    def release_all(self):
        self.release_called = True
        return {}


class FakeNotificationDispatcher:
    instances = []

    def __init__(self, *args, **kwargs):
        self.shutdown_called = False
        self.__class__.instances.append(self)

    def shutdown(self, wait=True, cancel_futures=False):
        self.shutdown_called = True


class FakeWorkerPool:
    def __init__(self, *args, **kwargs):
        self.max_workers = kwargs.get("max_workers", 2)

    def run(self, *args, **kwargs):
        raise RuntimeError("simulated fleet worker failure")


class FakeAdapter:
    def __init__(self, *args, **kwargs):
        self.closed = False

    def close(self):
        self.closed = True


def test_main_cleans_up_shared_resources_when_worker_pool_fails(monkeypatch):
    FakeCameraManager.instances.clear()
    FakeNotificationDispatcher.instances.clear()

    camera_database = FakeDatabase()
    zone_database = FakeDatabase()
    event_database = FakeDatabase()

    camera_config = type(
        "CameraConfig",
        (),
        {
            "camera_id": "CAM-001",
            "name": "Test Camera",
            "location": "Test Location",
        },
    )()

    monkeypatch.setattr(
        runner,
        "CameraDatabase",
        lambda *args, **kwargs: camera_database,
    )
    monkeypatch.setattr(
        runner,
        "ZoneDatabase",
        lambda *args, **kwargs: zone_database,
    )
    monkeypatch.setattr(
        runner,
        "EventDatabase",
        lambda *args, **kwargs: event_database,
    )

    monkeypatch.setattr(
        runner,
        "load_camera_configs_from_database",
        lambda database: [camera_config],
    )
    monkeypatch.setattr(
        runner,
        "load_camera_configs",
        lambda path: [camera_config],
    )
    monkeypatch.setattr(
        runner,
        "load_runtime_zones",
        lambda database, path: [],
    )
    monkeypatch.setattr(
        runner,
        "load_rule_config",
        lambda path: {
            "crowding": {},
            "after_hours": {},
        },
    )

    monkeypatch.setattr(
        runner,
        "CameraManager",
        FakeCameraManager,
    )
    monkeypatch.setattr(
        runner,
        "PersonDetector",
        lambda: object(),
    )
    monkeypatch.setattr(
        runner,
        "ZoneDetector",
        lambda zones: object(),
    )
    monkeypatch.setattr(
        runner,
        "CameraHealthEventService",
        lambda event_database: object(),
    )
    monkeypatch.setattr(
        runner,
        "NotificationDispatcher",
        FakeNotificationDispatcher,
    )
    monkeypatch.setattr(
        runner,
        "CameraWorkerPool",
        FakeWorkerPool,
    )
    monkeypatch.setattr(
        runner,
        "ConsoleNotificationProvider",
        lambda: object(),
    )

    monkeypatch.delenv("ENABLE_FIRE_SMOKE", raising=False)
    monkeypatch.delenv("ENABLE_WEAPON", raising=False)
    monkeypatch.delenv(
        "HOTEL_SECURITY_WEBHOOK_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated fleet worker failure",
    ):
        runner.main()

    assert FakeNotificationDispatcher.instances
    assert (
        FakeNotificationDispatcher.instances[0].shutdown_called
        is True
    )

    assert FakeCameraManager.instances
    assert (
        FakeCameraManager.instances[0].release_called
        is True
    )

    assert zone_database.closed is True
    assert camera_database.closed is True
    assert event_database.closed is True
