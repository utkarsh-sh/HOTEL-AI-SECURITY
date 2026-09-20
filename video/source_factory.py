from video.rtsp_source import RTSPVideoSource
from video.source import FileVideoSource


def create_video_source(camera_config):
    """Create the appropriate video source from camera configuration."""

    source_type = camera_config.source_type.lower().strip()

    if source_type == "file":
        return FileVideoSource(camera_config.source)

    if source_type == "rtsp":
        return RTSPVideoSource(
            url=camera_config.source,
            max_reconnect_attempts=(
                camera_config.reconnect.max_attempts
            ),
            reconnect_delay_seconds=(
                camera_config.reconnect.delay_seconds
            ),
        )

    raise ValueError(
        f"Unsupported video source type: {camera_config.source_type}"
    )
