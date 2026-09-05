from pathlib import Path

import cv2


class FileVideoSource:
    """Read frames from a recorded CCTV video file."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.capture = None

    def open(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Video not found: {self.path}"
            )

        self.capture = cv2.VideoCapture(str(self.path))

        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open video: {self.path}"
            )

    def read(self):
        if self.capture is None:
            raise RuntimeError(
                "Video source is not open."
            )

        success, frame = self.capture.read()

        if not success:
            return None

        return frame

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None