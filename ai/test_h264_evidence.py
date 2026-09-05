from pathlib import Path

import cv2

from ai.evidence_recorder import EvidenceRecorder


VIDEO_PATH = Path(
    "data/input/01_person_tracking_intrusion.mp4"
)

OUTPUT_DIRECTORY = Path(
    "data/output/h264_test"
)


def main():

    print("=" * 60)
    print("H.264 EVIDENCE RECORDER TEST")
    print("=" * 60)

    capture = cv2.VideoCapture(
        str(VIDEO_PATH)
    )

    if not capture.isOpened():

        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    source_fps = capture.get(
        cv2.CAP_PROP_FPS
    )

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    print(
        f"Source FPS : {source_fps:.2f}"
    )

    print(
        f"Resolution : {width} x {height}"
    )

    recorder = EvidenceRecorder(
        output_directory=OUTPUT_DIRECTORY,
        fps=source_fps,
        pre_event_seconds=2,
        post_event_seconds=2,
    )

    event_started = False
    frame_number = 0

    while True:

        success, frame = capture.read()

        if not success:
            break

        recorder.add_frame(frame)

        # Simulate an event around frame 150.
        if frame_number == 150:

            event_path = (
                recorder.start_event_capture(
                    event_type="INTRUSION",
                    event_id=999,
                )
            )

            print(
                f"[TEST EVENT] "
                f"Evidence path: {event_path}"
            )

            event_started = True

        frame_number += 1

    recorder.finalize()

    capture.release()

    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()