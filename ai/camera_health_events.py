from database.event_database import EventDatabase


CAMERA_OFFLINE_EVENT = "CAMERA_OFFLINE"
CAMERA_RECOVERED_EVENT = "CAMERA_RECOVERED"


class CameraHealthEventService:
    """
    Creates persistent camera-health events.

    Transition detection belongs to CameraHealthMonitor.
    This service is intentionally stateless: it only creates the
    corresponding event when the monitor reports a transition.
    """

    def __init__(self, event_database):
        if not isinstance(event_database, EventDatabase):
            raise TypeError(
                "event_database must be an EventDatabase instance"
            )

        self.event_database = event_database

    def create_offline_event(
        self,
        camera_id,
        error="Camera stopped providing frames",
    ):
        if not camera_id:
            raise ValueError("camera_id is required")

        return self.event_database.create_event(
            event_type=CAMERA_OFFLINE_EVENT,
            severity="HIGH",
            camera_id=camera_id,
            zone_id=None,
            zone_name=None,
            track_id=None,
            message=(
                f"Camera {camera_id} is offline. "
                f"Reason: {error}"
            ),
            model_version="camera-health-v1",
            evidence_path=None,
        )

    def create_recovered_event(self, camera_id):
        if not camera_id:
            raise ValueError("camera_id is required")

        return self.event_database.create_event(
            event_type=CAMERA_RECOVERED_EVENT,
            severity="MEDIUM",
            camera_id=camera_id,
            zone_id=None,
            zone_name=None,
            track_id=None,
            message=(
                f"Camera {camera_id} has recovered "
                "and is providing frames again."
            ),
            model_version="camera-health-v1",
            evidence_path=None,
        )