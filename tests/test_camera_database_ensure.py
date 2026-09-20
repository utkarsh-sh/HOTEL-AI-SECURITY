from database.camera_database import CameraDatabase


def test_ensure_camera_creates_missing_camera(tmp_path):
    database = CameraDatabase(tmp_path / "camera.db")

    camera = database.ensure_camera(
        camera_id="CAM-002",
        name="Test Secondary Camera",
        location="Test Area",
    )

    assert camera["camera_id"] == "CAM-002"
    assert camera["status"] == "OFFLINE"
    assert camera["consecutive_failures"] == 0
    assert camera["last_seen"] is None

    database.close()


def test_ensure_camera_is_idempotent(tmp_path):
    database = CameraDatabase(tmp_path / "camera.db")

    database.ensure_camera(
        camera_id="CAM-002",
        name="Test Secondary Camera",
        location="Test Area",
    )

    second = database.ensure_camera(
        camera_id="CAM-002",
        name="Changed Name",
        location="Changed Location",
    )

    assert second["name"] == "Test Secondary Camera"
    assert second["location"] == "Test Area"

    database.close()


def test_ensure_camera_preserves_existing_health_state(tmp_path):
    database = CameraDatabase(tmp_path / "camera.db")

    database.create_camera(
        camera_id="CAM-001",
        name="Main Lobby Camera",
        location="Main Lobby",
    )

    database.update_health(
        camera_id="CAM-001",
        status="ONLINE",
        fps=25.0,
        width=1920,
        height=1080,
    )

    before = database.get_camera("CAM-001")

    after = database.ensure_camera(
        camera_id="CAM-001",
        name="Different Name",
        location="Different Location",
    )

    assert after["status"] == "ONLINE"
    assert after["fps"] == before["fps"]
    assert after["width"] == before["width"]
    assert after["height"] == before["height"]
    assert after["last_seen"] == before["last_seen"]
    assert after["name"] == "Main Lobby Camera"
    assert after["location"] == "Main Lobby"

    database.close()


def test_ensure_camera_does_not_duplicate_rows(tmp_path):
    database = CameraDatabase(tmp_path / "camera.db")

    database.ensure_camera(
        camera_id="CAM-002",
        name="Test Secondary Camera",
        location="Test Area",
    )

    database.ensure_camera(
        camera_id="CAM-002",
        name="Test Secondary Camera",
        location="Test Area",
    )

    row = database.connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM cameras
        WHERE camera_id = ?
        """,
        ("CAM-002",),
    ).fetchone()

    assert row["count"] == 1

    database.close()
