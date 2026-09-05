from pathlib import Path

from database.camera_database import CameraDatabase
from ai.camera_health import CameraHealthMonitor


print("=" * 60)
print("HOTEL AI CCTV - CAMERA HEALTH MONITOR TEST")
print("=" * 60)


test_database_path = Path(
    "database/test_camera_health_monitor.db"
)

if test_database_path.exists():
    test_database_path.unlink()

database = CameraDatabase(
    test_database_path
)


camera_id = "CAM-001"


# ---------------------------------------------------------
# Register camera
# ---------------------------------------------------------

database.create_camera(
    camera_id=camera_id,
    name="Test Camera",
    location="Test Location",
)


monitor = CameraHealthMonitor(
    camera_id=camera_id,
    database=database,
    failure_threshold=3,
)


# ---------------------------------------------------------
# Test successful frame
# ---------------------------------------------------------

print("Testing successful frame...")

monitor.frame_received(
    fps=25.0,
    width=1920,
    height=1080,
)

camera = database.get_camera(camera_id)

print(
    f"Status={camera['status']} | "
    f"Failures={camera['consecutive_failures']}"
)


# ---------------------------------------------------------
# Test failures
# ---------------------------------------------------------

print("-" * 60)
print("Testing consecutive failures...")

for i in range(3):

    monitor.frame_failed(
        error="No frame received"
    )

    camera = database.get_camera(
        camera_id
    )

    print(
        f"Failure {i + 1}: "
        f"Status={camera['status']} | "
        f"Failures={camera['consecutive_failures']}"
    )


# ---------------------------------------------------------
# Test recovery
# ---------------------------------------------------------

print("-" * 60)
print("Testing camera recovery...")

monitor.frame_received(
    fps=25.0,
    width=1920,
    height=1080,
)

camera = database.get_camera(
    camera_id
)

print(
    f"Status={camera['status']} | "
    f"Failures={camera['consecutive_failures']} | "
    f"Error={camera['last_error']}"
)


database.close()

print("=" * 60)
print("CAMERA HEALTH MONITOR TEST COMPLETE")
print("=" * 60)