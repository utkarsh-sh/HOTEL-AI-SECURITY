from database.camera_database import CameraDatabase


database = CameraDatabase()

camera_id = "CAM-001"

existing = database.get_camera(camera_id)

if existing is None:
    database.create_camera(
        camera_id="CAM-001",
        name="Main Lobby Camera",
        location="Main Lobby",
        status="OFFLINE",
    )

    print("CAM-001 created successfully.")
else:
    print("CAM-001 already exists.")

database.close()