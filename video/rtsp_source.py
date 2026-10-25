import time

import cv2


class RTSPVideoSource:
    """Read frames from an RTSP CCTV stream with reconnect support."""

    def __init__(
        self,
        url: str,
        max_reconnect_attempts: int = 3,
        reconnect_delay_seconds: float = 1.0,
    ):
        if not url or not url.strip():
            raise ValueError("RTSP URL must not be empty.")

        if max_reconnect_attempts < 0:
            raise ValueError(
                "max_reconnect_attempts must be >= 0."
            )

        if reconnect_delay_seconds < 0:
            raise ValueError(
                "reconnect_delay_seconds must be >= 0."
            )

        self.url = url
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay_seconds = reconnect_delay_seconds

        self.capture = None
        self.reconnect_attempts = 0
        self._started = False

    def open(self) -> None:
        """Open the RTSP stream."""
        self._started = False
        self._release_capture()

        self.capture = cv2.VideoCapture(
            self.url,
            cv2.CAP_FFMPEG,
        )

        if not self.capture.isOpened():
            self._release_capture()
            raise RuntimeError(
                f"Could not open RTSP stream: {self._safe_url()}"
            )

        self.reconnect_attempts = 0
        self._started = True

    def read(self):
        """Read a frame, retrying connection after exhausted reconnects."""
        if self.capture is None:
            if not self._started:
                raise RuntimeError(
                    "RTSP video source is not open."
                )

            # A previously opened source may have exhausted its reconnects.
            # Retry on subsequent read() calls rather than staying offline.
            if not self._reconnect():
                return None

            success, frame = self.capture.read()
            if success:
                self.reconnect_attempts = 0
                return frame

            return None

        success, frame = self.capture.read()

        if success:
            self.reconnect_attempts = 0
            return frame

        if self._reconnect():
            success, frame = self.capture.read()

            if success:
                self.reconnect_attempts = 0
                return frame

        return None

    def release(self) -> None:
        """Release the stream and disable subsequent reads until reopened."""
        self._release_capture()
        self.reconnect_attempts = 0
        self._started = False

    def _reconnect(self) -> bool:
        """Attempt to reconnect to the RTSP stream."""
        self._release_capture()

        for attempt in range(
            1,
            self.max_reconnect_attempts + 1,
        ):
            self.reconnect_attempts = attempt

            if self.reconnect_delay_seconds > 0:
                time.sleep(
                    self.reconnect_delay_seconds
                )

            capture = cv2.VideoCapture(
                self.url,
                cv2.CAP_FFMPEG,
            )

            if capture.isOpened():
                self.capture = capture
                return True

            capture.release()

        return False

    def _release_capture(self) -> None:
        """Release the current OpenCV capture if present."""
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def _safe_url(self) -> str:
        """Return a URL suitable for logs without exposing credentials."""
        if "@" not in self.url:
            return self.url

        scheme_separator = "://"

        if scheme_separator not in self.url:
            return "[REDACTED RTSP URL]"

        scheme, remainder = self.url.split(
            scheme_separator,
            1,
        )

        if "@" not in remainder:
            return self.url

        return f"{scheme}://[REDACTED]@{remainder.split('@', 1)[1]}"
