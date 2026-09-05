from database.camera_database import CameraDatabase


print("=" * 60)
print("HOTEL AI CCTV - CAMERA HEALTH TEST")
print("=" * 60)

database = CameraDatabase()

camera_id = "CAM-001"

camera = database.get_camera(camera_id)

if camera is None:
    print(f"ERROR: {camera_id} does not exist.")
    database.close()
    raise SystemExit(1)

print(f"Camera found: {camera_id}")
print(f"Current status: {camera['status']}")

print("-" * 60)
print("Simulating successful camera frames...")

database.update_health(
    camera_id=camera_id,
    status="ONLINE",
    fps=25.0,
    width=1920,
    height=1080,
)

camera = database.get_camera(camera_id)

print(f"Status     : {camera['status']}")
print(f"FPS        : {camera['fps']}")
print(
    f"Resolution : "
    f"{camera['width']}x{camera['height']}"
)
print(f"Last seen  : {camera['last_seen']}")
print(
    f"Failures   : "
    f"{camera['consecutive_failures']}"
)
print(f"Error      : {camera['last_error']}")

print("-" * 60)
print("Simulating camera failure...")

database.update_health(
    camera_id=camera_id,
    status="OFFLINE",
    error="No frames received",
)

camera = database.get_camera(camera_id)

print(f"Status     : {camera['status']}")
print(
    f"Failures   : "
    f"{camera['consecutive_failures']}"
)
print(f"Error      : {camera['last_error']}")

print("-" * 60)
print("Simulating camera recovery...")

database.update_health(
    camera_id=camera_id,
    status="ONLINE",
    fps=25.0,
    width=1920,
    height=1080,
)

camera = database.get_camera(camera_id)

print(f"Status     : {camera['status']}")
print(f"FPS        : {camera['fps']}")
print(
    f"Resolution : "
    f"{camera['width']}x{camera['height']}"
)
print(
    f"Failures   : "
    f"{camera['consecutive_failures']}"
)
print(f"Error      : {camera['last_error']}")

database.close()

print("=" * 60)
print("CAMERA HEALTH TEST COMPLETE")
print("=" * 60)