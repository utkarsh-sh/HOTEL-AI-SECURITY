from database.camera_database import CameraDatabase


print("=" * 60)
print("HOTEL AI CCTV - CAMERA DATABASE TEST")
print("=" * 60)


database = CameraDatabase(
    "database/test_camera_security.db"
)

print("Camera database initialized.")


# ---------------------------------------------------------
# Create test cameras
# ---------------------------------------------------------

database.create_camera(
    camera_id="CAM-001",
    name="Main Lobby Camera",
    location="Main Lobby"
)

database.create_camera(
    camera_id="CAM-002",
    name="Reception Camera",
    location="Reception"
)

database.create_camera(
    camera_id="CAM-003",
    name="Back Entrance Camera",
    location="Back Entrance"
)

print("Test cameras created.")


# ---------------------------------------------------------
# Test camera retrieval
# ---------------------------------------------------------

cameras = database.get_all_cameras()

print(f"Total cameras: {len(cameras)}")

for camera in cameras:
    print(
        f"ID={camera['camera_id']} | "
        f"Name={camera['name']} | "
        f"Location={camera['location']} | "
        f"Status={camera['status']}"
    )


# ---------------------------------------------------------
# Test camera health - ONLINE
# ---------------------------------------------------------

database.update_health(
    camera_id="CAM-001",
    status="ONLINE",
    fps=25.0,
    width=1920,
    height=1080
)

camera = database.get_camera("CAM-001")

print("-" * 60)
print("After CAM-001 comes ONLINE:")

print(
    f"Status={camera['status']} | "
    f"FPS={camera['fps']} | "
    f"Resolution={camera['width']}x{camera['height']} | "
    f"Failures={camera['consecutive_failures']}"
)


# ---------------------------------------------------------
# Test camera health - OFFLINE
# ---------------------------------------------------------

database.update_health(
    camera_id="CAM-002",
    status="OFFLINE",
    error="No frames received"
)

camera = database.get_camera("CAM-002")

print("-" * 60)
print("After CAM-002 goes OFFLINE:")

print(
    f"Status={camera['status']} | "
    f"Failures={camera['consecutive_failures']} | "
    f"Error={camera['last_error']}"
)


# ---------------------------------------------------------
# Test recovery
# ---------------------------------------------------------

database.update_health(
    camera_id="CAM-002",
    status="ONLINE",
    fps=25.0,
    width=1920,
    height=1080
)

camera = database.get_camera("CAM-002")

print("-" * 60)
print("After CAM-002 recovers:")

print(
    f"Status={camera['status']} | "
    f"FPS={camera['fps']} | "
    f"Failures={camera['consecutive_failures']} | "
    f"Error={camera['last_error']}"
)


database.close()

print("=" * 60)
print("CAMERA DATABASE TEST COMPLETE")
print("=" * 60)