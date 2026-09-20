from video.camera_config import (
    CameraConfig,
    ReconnectConfig,
)
from video.rtsp_source import RTSPVideoSource
from video.source import FileVideoSource
from video.source_factory import create_video_source


def make_config(
    source_type,
    source,
):
    return CameraConfig(
        camera_id="CAM-001",
        name="Test Camera",
        location="Test Location",
        source_type=source_type,
        source=source,
        ai_fps=5.0,
        reconnect=ReconnectConfig(
            max_attempts=4,
            delay_seconds=2.0,
        ),
    )


def test_file_source_created():
    config = make_config(
        "file",
        "data/input/test.mp4",
    )

    source = create_video_source(config)

    assert isinstance(
        source,
        FileVideoSource,
    )

    assert str(source.path).endswith(
        "data\\input\\test.mp4"
    ) or str(source.path).endswith(
        "data/input/test.mp4"
    )


def test_rtsp_source_created():
    config = make_config(
        "rtsp",
        "rtsp://camera/stream",
    )

    source = create_video_source(config)

    assert isinstance(
        source,
        RTSPVideoSource,
    )

    assert source.url == "rtsp://camera/stream"
    assert source.max_reconnect_attempts == 4
    assert source.reconnect_delay_seconds == 2.0


def test_source_type_is_case_insensitive():
    config = make_config(
        "RTSP",
        "rtsp://camera/stream",
    )

    source = create_video_source(config)

    assert isinstance(
        source,
        RTSPVideoSource,
    )


def test_unsupported_source_type_rejected():
    config = make_config(
        "websocket",
        "ws://camera/stream",
    )

    try:
        create_video_source(config)
    except ValueError as error:
        assert "Unsupported video source type" in str(error)
    else:
        raise AssertionError(
            "Expected ValueError"
        )
