from dataclasses import dataclass

from video.camera_config import CameraConfig
from video.source_factory import create_video_source


@dataclass
class ManagedCamera:
    config: CameraConfig
    source: object


class CameraManager:
    """
    Manage the lifecycle of multiple configured camera sources.

    This class intentionally does not contain AI inference,
    tracking, rules, or event processing.
    """

    def __init__(self, camera_configs):
        if camera_configs is None:
            raise ValueError(
                "camera_configs must not be None."
            )

        self.camera_configs = list(camera_configs)

        self._validate_configs()

        self._cameras = {}
        self.open_errors = {}

        for config in self.camera_configs:
            self._cameras[config.camera_id] = ManagedCamera(
                config=config,
                source=create_video_source(config),
            )

    def _validate_configs(self):
        """Validate camera configuration collection."""

        seen_ids = set()

        for config in self.camera_configs:
            if not isinstance(config, CameraConfig):
                raise TypeError(
                    "Every camera configuration must be "
                    "a CameraConfig instance."
                )

            camera_id = config.camera_id.strip()

            if not camera_id:
                raise ValueError(
                    "Camera ID must not be empty."
                )

            if camera_id in seen_ids:
                raise ValueError(
                    f"Duplicate camera ID: {camera_id}"
                )

            seen_ids.add(camera_id)

    def camera_ids(self):
        """Return configured camera IDs in configuration order."""

        return [
            config.camera_id
            for config in self.camera_configs
        ]

    def get_config(self, camera_id):
        """Return the configuration for a camera."""

        camera = self._get_camera(camera_id)

        return camera.config

    def get_source(self, camera_id):
        """Return the underlying video source."""

        camera = self._get_camera(camera_id)

        return camera.source

    def open_all(self):
        """
        Attempt to open every configured camera.

        A failure on one camera does not prevent other cameras
        from being opened.

        Returns:
            dict containing camera IDs that opened successfully.
        """

        self.open_errors.clear()

        opened = {}

        for camera_id in self.camera_ids():
            camera = self._cameras[camera_id]

            try:
                camera.source.open()

                opened[camera_id] = camera.source

            except Exception as exc:
                self.open_errors[camera_id] = str(exc)

        return opened

    def open_camera(self, camera_id):
        """Open one camera source."""

        camera = self._get_camera(camera_id)

        try:
            camera.source.open()
            self.open_errors.pop(camera_id, None)

        except Exception as exc:
            self.open_errors[camera_id] = str(exc)
            raise

    def read(self, camera_id):
        """Read one frame from one camera."""

        camera = self._get_camera(camera_id)

        return camera.source.read()

    def release_camera(self, camera_id):
        """Release one camera source."""

        camera = self._get_camera(camera_id)

        camera.source.release()

    def release_all(self):
        """Release every configured camera source safely."""

        errors = {}

        for camera_id in self.camera_ids():
            try:
                self.release_camera(camera_id)

            except Exception as exc:
                errors[camera_id] = str(exc)

        return errors

    def _get_camera(self, camera_id):
        if camera_id not in self._cameras:
            raise KeyError(
                f"Unknown camera ID: {camera_id}"
            )

        return self._cameras[camera_id]

    def __len__(self):
        return len(self._cameras)
