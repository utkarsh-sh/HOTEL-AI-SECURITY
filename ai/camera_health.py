from database.camera_database import CameraDatabase


class CameraHealthMonitor:
    """
    Tracks the health of a camera source.

    A camera is considered offline after a configurable
    number of consecutive frame failures.
    """

    def __init__(
        self,
        camera_id: str,
        database: CameraDatabase,
        failure_threshold: int = 3,
    ):
        self.camera_id = camera_id
        self.database = database
        self.failure_threshold = failure_threshold

        self.consecutive_failures = 0

    def frame_received(
        self,
        fps: float,
        width: int,
        height: int,
    ):
        """
        Call whenever a valid frame is received.
        """

        self.consecutive_failures = 0

        self.database.update_health(
            camera_id=self.camera_id,
            status="ONLINE",
            fps=fps,
            width=width,
            height=height,
        )

    def frame_failed(
        self,
        error: str = "No frame received",
    ):
        """
        Call whenever the camera fails to provide a frame.
        """

        self.consecutive_failures += 1

        self.database.record_failure(
            camera_id=self.camera_id,
            consecutive_failures=self.consecutive_failures,
            error=error,
        )

    def get_failure_count(self):
        return self.consecutive_failures