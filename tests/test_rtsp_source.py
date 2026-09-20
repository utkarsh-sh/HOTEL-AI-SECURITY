import numpy as np
import pytest

from video.rtsp_source import RTSPVideoSource


class FakeCapture:
    def __init__(
        self,
        opened=True,
        read_results=None,
    ):
        self.opened = opened
        self.read_results = list(read_results or [])
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        if self.read_results:
            return self.read_results.pop(0)

        return False, None

    def release(self):
        self.released = True


def test_empty_url_rejected():
    with pytest.raises(ValueError):
        RTSPVideoSource("")


def test_negative_reconnect_attempts_rejected():
    with pytest.raises(ValueError):
        RTSPVideoSource(
            "rtsp://camera",
            max_reconnect_attempts=-1,
        )


def test_negative_reconnect_delay_rejected():
    with pytest.raises(ValueError):
        RTSPVideoSource(
            "rtsp://camera",
            reconnect_delay_seconds=-1,
        )


def test_read_before_open_rejected():
    source = RTSPVideoSource("rtsp://camera")

    with pytest.raises(RuntimeError):
        source.read()


def test_open_success(monkeypatch):
    capture = FakeCapture(opened=True)

    def fake_video_capture(url, backend):
        assert url == "rtsp://camera"
        return capture

    monkeypatch.setattr(
        "video.rtsp_source.cv2.VideoCapture",
        fake_video_capture,
    )

    source = RTSPVideoSource("rtsp://camera")
    source.open()

    assert source.capture is capture
    assert source.reconnect_attempts == 0


def test_open_failure(monkeypatch):
    capture = FakeCapture(opened=False)

    monkeypatch.setattr(
        "video.rtsp_source.cv2.VideoCapture",
        lambda url, backend: capture,
    )

    source = RTSPVideoSource("rtsp://camera")

    with pytest.raises(RuntimeError):
        source.open()

    assert source.capture is None
    assert capture.released is True


def test_read_success(monkeypatch):
    frame = np.zeros(
        (100, 200, 3),
        dtype=np.uint8,
    )

    capture = FakeCapture(
        opened=True,
        read_results=[
            (True, frame),
        ],
    )

    monkeypatch.setattr(
        "video.rtsp_source.cv2.VideoCapture",
        lambda url, backend: capture,
    )

    source = RTSPVideoSource("rtsp://camera")
    source.open()

    result = source.read()

    assert result is frame
    assert result.shape == (100, 200, 3)
    assert source.reconnect_attempts == 0


def test_failed_read_reconnects_successfully(monkeypatch):
    first_capture = FakeCapture(
        opened=True,
        read_results=[
            (False, None),
        ],
    )

    recovered_frame = np.ones(
        (100, 200, 3),
        dtype=np.uint8,
    )

    second_capture = FakeCapture(
        opened=True,
        read_results=[
            (True, recovered_frame),
        ],
    )

    captures = [
        first_capture,
        second_capture,
    ]

    def fake_video_capture(url, backend):
        return captures.pop(0)

    monkeypatch.setattr(
        "video.rtsp_source.cv2.VideoCapture",
        fake_video_capture,
    )

    source = RTSPVideoSource(
        "rtsp://camera",
        max_reconnect_attempts=2,
        reconnect_delay_seconds=0,
    )

    source.open()

    result = source.read()

    assert result is recovered_frame
    assert source.capture is second_capture
    assert source.reconnect_attempts == 0
    assert first_capture.released is True


def test_reconnect_failure_returns_none(monkeypatch):
    first_capture = FakeCapture(
        opened=True,
        read_results=[
            (False, None),
        ],
    )

    failed_capture_1 = FakeCapture(opened=False)
    failed_capture_2 = FakeCapture(opened=False)

    captures = [
        first_capture,
        failed_capture_1,
        failed_capture_2,
    ]

    def fake_video_capture(url, backend):
        return captures.pop(0)

    monkeypatch.setattr(
        "video.rtsp_source.cv2.VideoCapture",
        fake_video_capture,
    )

    source = RTSPVideoSource(
        "rtsp://camera",
        max_reconnect_attempts=2,
        reconnect_delay_seconds=0,
    )

    source.open()

    result = source.read()

    assert result is None
    assert source.capture is None
    assert source.reconnect_attempts == 2
    assert failed_capture_1.released is True
    assert failed_capture_2.released is True


def test_release_closes_capture(monkeypatch):
    capture = FakeCapture(opened=True)

    monkeypatch.setattr(
        "video.rtsp_source.cv2.VideoCapture",
        lambda url, backend: capture,
    )

    source = RTSPVideoSource("rtsp://camera")
    source.open()

    source.release()

    assert capture.released is True
    assert source.capture is None
    assert source.reconnect_attempts == 0


def test_credentials_are_redacted():
    source = RTSPVideoSource(
        "rtsp://admin:secret123@192.168.1.50:554/stream"
    )

    safe_url = source._safe_url()

    assert "secret123" not in safe_url
    assert "admin" not in safe_url
    assert "192.168.1.50" in safe_url
    assert safe_url == (
        "rtsp://[REDACTED]@192.168.1.50:554/stream"
    )
