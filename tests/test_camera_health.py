from database.camera_database import CameraDatabase


def test_camera_health_lifecycle(tmp_path):
    database_path = tmp_path / "camera_health_test.db"
    database = CameraDatabase(database_path)

    camera_id = "CAM-001"

    database.create_camera(
        camera_id=camera_id,
        name="Test Camera",
        location="Test Area",
        status="OFFLINE",
    )

    try:
        camera = database.get_camera(camera_id)
        assert camera is not None
        assert camera["status"] == "OFFLINE"

        database.update_health(
            camera_id=camera_id,
            status="ONLINE",
            fps=25.0,
            width=1920,
            height=1080,
        )

        camera = database.get_camera(camera_id)

        assert camera["status"] == "ONLINE"
        assert camera["fps"] == 25.0
        assert camera["width"] == 1920
        assert camera["height"] == 1080
        assert camera["last_seen"] is not None
        assert camera["consecutive_failures"] == 0
        assert camera["last_error"] is None

        database.update_health(
            camera_id=camera_id,
            status="OFFLINE",
            error="No frames received",
        )

        camera = database.get_camera(camera_id)

        assert camera["status"] == "OFFLINE"
        assert camera["consecutive_failures"] == 1
        assert camera["last_error"] == "No frames received"

        database.update_health(
            camera_id=camera_id,
            status="ONLINE",
            fps=25.0,
            width=1920,
            height=1080,
        )

        camera = database.get_camera(camera_id)

        assert camera["status"] == "ONLINE"
        assert camera["fps"] == 25.0
        assert camera["width"] == 1920
        assert camera["height"] == 1080
        assert camera["consecutive_failures"] == 0
        assert camera["last_error"] is None

    finally:
        database.close()
