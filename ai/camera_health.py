from database.camera_database import CameraDatabase


CAMERA_OFFLINE = "CAMERA_OFFLINE"
CAMERA_RECOVERED = "CAMERA_RECOVERED"


class CameraHealthMonitor:
    """
    Persistent camera health monitor.

    Supported transitions:
        ONLINE  -> OFFLINE
        OFFLINE -> ONLINE

    Camera status and consecutive failure count are persisted in the
    CameraDatabase so that state survives application restarts.

    The initial OFFLINE state of a camera with no previous frame
    (last_seen is None) is not considered a recovery transition.
    """

    def __init__(
        self,
        camera_id,
        database,
        failure_threshold=3,
    ):
        if not camera_id:
            raise ValueError("camera_id is required")

        if not isinstance(database, CameraDatabase):
            raise TypeError("database must be a CameraDatabase instance")

        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")

        camera = database.get_camera(camera_id)

        if camera is None:
            raise ValueError(f"Camera not found: {camera_id}")

        self.camera_id = camera_id
        self.database = database
        self.failure_threshold = failure_threshold

        # IMPORTANT:
        # Restore the persisted failure count after a process restart.
        self.consecutive_failures = int(
            camera["consecutive_failures"] or 0
        )

    def frame_received(self, fps, width, height):
        """
        Record a successful frame.

        Returns:
            CAMERA_RECOVERED when a previously operationally-seen
            OFFLINE camera comes back ONLINE.

            None otherwise.
        """

        camera = self.database.get_camera(self.camera_id)

        if camera is None:
            raise ValueError(f"Camera not found: {self.camera_id}")

        previous_status = camera["status"]
        previously_seen = camera["last_seen"] is not None

        self.consecutive_failures = 0

        self.database.update_health(
            camera_id=self.camera_id,
            status="ONLINE",
            fps=fps,
            width=width,
            height=height,
            error=None,
            consecutive_failures=0,
        )

        # Do not treat the application's first successful frame as
        # a recovery from the camera's initial OFFLINE state.
        if previous_status == "OFFLINE" and previously_seen:
            return CAMERA_RECOVERED

        return None

    def frame_failed(self, error="No frame received"):
        """
        Record a failed frame.

        Returns:
            CAMERA_OFFLINE when this failure causes an ONLINE camera
            to cross the offline threshold.

            None for normal failures or failures while already offline.
        """

        camera = self.database.get_camera(self.camera_id)

        if camera is None:
            raise ValueError(f"Camera not found: {self.camera_id}")

        previous_status = camera["status"]

        # Use the persisted count as the source of truth.
        #
        # This is critical after a process restart. For example:
        #
        #   before restart: consecutive_failures = 3, status = OFFLINE
        #   after restart:  must continue from 3, not reset to 0.
        persisted_failures = int(
            camera["consecutive_failures"] or 0
        )

        self.consecutive_failures = persisted_failures + 1

        self.database.record_failure(
            camera_id=self.camera_id,
            consecutive_failures=self.consecutive_failures,
            error=error,
            failure_threshold=self.failure_threshold,
        )

        # Generate the transition only when the camera was previously
        # ONLINE and this failure crosses the configured threshold.
        if (
            previous_status == "ONLINE"
            and self.consecutive_failures >= self.failure_threshold
        ):
            return CAMERA_OFFLINE

        return None

    def is_offline(self):
        """
        Return True when the persisted/current failure count has
        reached the configured threshold.
        """
        return self.consecutive_failures >= self.failure_threshold

    def get_failure_count(self):
        """Return the current consecutive failure count."""
        return self.consecutive_failures