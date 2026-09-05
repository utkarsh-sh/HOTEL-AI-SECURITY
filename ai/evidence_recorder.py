from collections import deque
from datetime import datetime
from pathlib import Path
import shutil
import subprocess

import cv2


class EvidenceRecorder:
    """
    Records evidence clips around security events.

    Workflow:
        1. Keep a rolling pre-event frame buffer.
        2. Start a temporary OpenCV recording when an event occurs.
        3. Continue recording the post-event window.
        4. Convert the temporary recording to browser-compatible H.264 MP4
           using FFmpeg.
        5. Keep the final MP4 path stable for the database/API.
    """

    def __init__(
        self,
        output_directory,
        fps,
        pre_event_seconds=5,
        post_event_seconds=5,
    ):
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.fps = float(fps)

        if self.fps <= 0:
            raise ValueError("FPS must be greater than zero.")

        self.pre_event_seconds = pre_event_seconds
        self.post_event_seconds = post_event_seconds

        self.pre_event_frames = max(
            1,
            int(round(
                self.fps * self.pre_event_seconds
            )),
        )

        self.post_event_frames = max(
            1,
            int(round(
                self.fps * self.post_event_seconds
            )),
        )

        self.pre_buffer = deque(
            maxlen=self.pre_event_frames
        )

        self.active_recordings = {}

        self.frame_width = None
        self.frame_height = None

        # FFmpeg must be available on PATH.
        self.ffmpeg_path = shutil.which("ffmpeg")

        if self.ffmpeg_path is None:
            raise RuntimeError(
                "FFmpeg was not found on PATH. "
                "Run 'ffmpeg -version' in PowerShell."
            )

        print(
            f"FFmpeg found: {self.ffmpeg_path}"
        )

    def add_frame(self, frame):
        """
        Add a frame to the rolling buffer and
        all currently active event recordings.
        """

        if frame is None:
            return

        height, width = frame.shape[:2]

        self.frame_width = width
        self.frame_height = height

        completed_events = []

        # Write current frame to every active event.
        for event_id, recording in list(
            self.active_recordings.items()
        ):
            writer = recording["writer"]

            writer.write(frame)

            recording["frames_remaining"] -= 1

            if recording["frames_remaining"] <= 0:

                writer.release()

                completed_events.append(event_id)

                print(
                    f"[EVIDENCE TEMP COMPLETE] "
                    f"EventID={event_id}"
                )

        # Convert completed temporary recordings
        # into browser-compatible H.264 MP4 files.
        for event_id in completed_events:

            recording = self.active_recordings[event_id]

            temporary_path = recording[
                "temporary_path"
            ]

            final_path = recording[
                "output_path"
            ]

            try:

                self._convert_to_h264(
                    temporary_path,
                    final_path,
                )

                print(
                    f"[EVIDENCE COMPLETE] "
                    f"EventID={event_id} "
                    f"Path={final_path}"
                )

                # Temporary MPEG-4 file is no longer needed.
                if temporary_path.exists():
                    temporary_path.unlink()

            except Exception as error:

                print(
                    f"[EVIDENCE CONVERSION ERROR] "
                    f"EventID={event_id} "
                    f"Error={error}"
                )

                print(
                    f"[EVIDENCE TEMPORARY FILE] "
                    f"{temporary_path}"
                )

            finally:

                del self.active_recordings[
                    event_id
                ]

        # Add frame to rolling pre-event buffer
        # AFTER writing it to active recordings.
        self.pre_buffer.append(
            frame.copy()
        )

    def start_event_capture(
        self,
        event_type,
        event_id,
    ):
        """
        Start an evidence recording.

        Returns the final browser-compatible MP4 path.
        """

        if event_id in self.active_recordings:
            return self.active_recordings[
                event_id
            ]["output_path"]

        if not self.pre_buffer:

            print(
                f"[EVIDENCE WARNING] "
                f"EventID={event_id} "
                f"No frames available in pre-event buffer."
            )

            return None

        first_frame = self.pre_buffer[0]

        height, width = first_frame.shape[:2]

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        safe_event_type = (
            str(event_type)
            .lower()
            .replace(" ", "_")
        )

        # Final browser-compatible filename.
        filename = (
            f"event_{event_id}_"
            f"{safe_event_type}_"
            f"{timestamp}.mp4"
        )

        final_path = (
            self.output_directory / filename
        )

        # Temporary file used by OpenCV.
        temporary_path = (
            self.output_directory
            / f"{final_path.stem}.tmp.mp4"
        )

        fourcc = cv2.VideoWriter_fourcc(
            *"mp4v"
        )

        writer = cv2.VideoWriter(
            str(temporary_path),
            fourcc,
            self.fps,
            (width, height),
        )

        if not writer.isOpened():

            print(
                f"[EVIDENCE ERROR] "
                f"Could not create temporary file "
                f"{temporary_path}"
            )

            return None

        # Write the complete pre-event buffer
        # into the temporary recording.
        for buffered_frame in self.pre_buffer:

            writer.write(
                buffered_frame
            )

        self.active_recordings[event_id] = {

            "writer": writer,

            "temporary_path":
                temporary_path,

            "output_path":
                final_path,

            "frames_remaining":
                self.post_event_frames,
        }

        print(
            f"[EVIDENCE CAPTURE CREATED] "
            f"EventID={event_id} "
            f"PreFrames={len(self.pre_buffer)} "
            f"PostFrames={self.post_event_frames}"
        )

        print(
            f"[EVIDENCE TEMP FILE] "
            f"{temporary_path}"
        )

        print(
            f"[EVIDENCE FINAL FILE] "
            f"{final_path}"
        )

        return final_path

    def _convert_to_h264(
        self,
        temporary_path,
        final_path,
    ):
        """
        Convert temporary OpenCV MPEG-4 recording
        into browser-compatible H.264 MP4.
        """

        temporary_path = Path(
            temporary_path
        )

        final_path = Path(
            final_path
        )

        command = [

            self.ffmpeg_path,

            "-y",

            "-i",
            str(temporary_path),

            "-c:v",
            "libx264",

            "-preset",
            "fast",

            "-crf",
            "23",

            "-pix_fmt",
            "yuv420p",

            "-movflags",
            "+faststart",

            "-an",

            str(final_path),
        ]

        print(
            "[FFMPEG] Converting evidence to H.264..."
        )

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:

            error_message = (
                result.stderr[-3000:]
                if result.stderr
                else "Unknown FFmpeg error."
            )

            raise RuntimeError(
                "FFmpeg conversion failed:\n"
                f"{error_message}"
            )

        if not final_path.exists():

            raise RuntimeError(
                "FFmpeg completed successfully "
                "but final evidence file was not created."
            )

        if final_path.stat().st_size == 0:

            raise RuntimeError(
                "Final evidence file was created "
                "but is empty."
            )

    def is_recording(self, event_id=None):

        if event_id is None:
            return bool(
                self.active_recordings
            )

        return (
            event_id
            in self.active_recordings
        )

    def get_active_event_ids(self):

        return list(
            self.active_recordings.keys()
        )

    def finalize(self):
        """
        Finalize all currently active recordings.

        Used when the video source ends or the application
        shuts down before the normal post-event window ends.
        """

        for event_id, recording in list(
            self.active_recordings.items()
        ):

            writer = recording["writer"]

            writer.release()

            temporary_path = recording[
                "temporary_path"
            ]

            final_path = recording[
                "output_path"
            ]

            try:

                self._convert_to_h264(
                    temporary_path,
                    final_path,
                )

                print(
                    f"[EVIDENCE FINALIZED] "
                    f"EventID={event_id} "
                    f"Path={final_path}"
                )

                if temporary_path.exists():
                    temporary_path.unlink()

            except Exception as error:

                print(
                    f"[EVIDENCE FINALIZATION ERROR] "
                    f"EventID={event_id} "
                    f"Error={error}"
                )

                print(
                    f"[EVIDENCE TEMPORARY FILE] "
                    f"{temporary_path}"
                )

        self.active_recordings.clear()

    def close(self):

        self.finalize()