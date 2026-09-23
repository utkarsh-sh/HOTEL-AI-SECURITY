import ai.run_intrusion_detection as runner


def test_process_camera_worker_uses_fleet_notification_dispatcher(monkeypatch):
    calls = []

    class FakeDatabase:
        def __init__(self, path):
            calls.append(("database_created", path))

        def close(self):
            calls.append(("database_closed", None))

    class FakeHealthService:
        def __init__(self, event_database):
            calls.append(("health_service_created", event_database))

    def fake_process_camera(**kwargs):
        calls.append(("process_camera", kwargs))
        return {
            "camera_id": kwargs["camera_config"].camera_id,
            "success": True,
        }

    monkeypatch.setattr(runner, "EventDatabase", FakeDatabase)
    monkeypatch.setattr(runner, "CameraDatabase", FakeDatabase)
    monkeypatch.setattr(runner, "CameraHealthEventService", FakeHealthService)
    monkeypatch.setattr(runner, "process_camera", fake_process_camera)

    dispatcher = object()
    camera_config = type("CameraConfig", (), {"camera_id": "CAM-001"})()

    result = runner.process_camera_worker(
        camera_config=camera_config,
        camera_manager="manager",
        detector="detector",
        zones=[],
        zone_detector="zone_detector",
        notification_dispatcher=dispatcher,
    )

    assert result["camera_id"] == "CAM-001"

    created = [item for item in calls if item[0] == "database_created"]
    closed = [item for item in calls if item[0] == "database_closed"]

    assert len(created) == 2
    assert len(closed) == 2

    process_calls = [item for item in calls if item[0] == "process_camera"]
    assert len(process_calls) == 1

    kwargs = process_calls[0][1]
    assert kwargs["camera_manager"] == "manager"
    assert kwargs["detector"] == "detector"
    assert kwargs["zones"] == []
    assert kwargs["zone_detector"] == "zone_detector"
    assert kwargs["event_database"] is not None
    assert kwargs["camera_database"] is not None
    assert kwargs["camera_health_events"] is not None
    assert kwargs["notification_dispatcher"] is dispatcher


def test_process_camera_worker_closes_databases_on_failure(monkeypatch):
    closed = []

    class FakeDatabase:
        def __init__(self, path):
            pass

        def close(self):
            closed.append(True)

    class FakeHealthService:
        def __init__(self, event_database):
            pass

    def failing_process_camera(**kwargs):
        raise RuntimeError("simulated processing failure")

    monkeypatch.setattr(runner, "EventDatabase", FakeDatabase)
    monkeypatch.setattr(runner, "CameraDatabase", FakeDatabase)
    monkeypatch.setattr(runner, "CameraHealthEventService", FakeHealthService)
    monkeypatch.setattr(runner, "process_camera", failing_process_camera)

    camera_config = type("CameraConfig", (), {"camera_id": "CAM-001"})()

    try:
        runner.process_camera_worker(
            camera_config=camera_config,
            camera_manager="manager",
            detector="detector",
            zones=[],
            zone_detector="zone_detector",
            notification_dispatcher=object(),
        )
    except RuntimeError as exc:
        assert str(exc) == "simulated processing failure"
    else:
        raise AssertionError("Expected RuntimeError was not raised.")

    assert len(closed) == 2
