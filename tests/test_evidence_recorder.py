from pathlib import Path

import cv2

from ai.evidence_recorder import EvidenceRecorder


VIDEO_PATH = "data/input/01_person_tracking_intrusion.mp4"


def main():

    print("=" * 60)
    print("HOTEL AI CCTV - EVIDENCE RECORDER TEST")
    print("=" * 60)

    source = cv2.VideoCapture(
        VIDEO_PATH
    )

    if not source.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    fps = source.get(
        cv2.CAP_PROP_FPS
    )

    width = int(
        source.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        source.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    total_frames = int(
        source.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    print(
        f"Resolution : "
        f"{width} x {height}"
    )

    print(
        f"FPS        : "
        f"{fps:.2f}"
    )

    print(
        f"Frames     : "
        f"{total_frames}"
    )

    recorder = EvidenceRecorder(
        output_directory="data/output/events",
        fps=fps,
        pre_event_seconds=5,
        post_event_seconds=5,
    )

    print("-" * 60)
    print("Reading video...")
    print("-" * 60)

    frame_index = 0

    # Test event around frame 250.
    event_frame = 250

    event_started = False

    while True:

        success, frame = source.read()

        if not success:
            break

        recorder.add_frame(
            frame
        )

        if (
            frame_index == event_frame
            and not event_started
        ):

            print(
                f"[TEST EVENT] "
                f"Frame={frame_index}"
            )

            output_path = (
                recorder.start_event_capture(
                    event_type="INTRUSION",
                    event_id=999,
                )
            )

            print(
                f"Evidence capture started:"
            )

            print(
                output_path
            )

            event_started = True

        frame_index += 1

    recorder.finalize()

    source.release()

    print("-" * 60)

    output_directory = Path(
        "data/output/events"
    )

    clips = list(
        output_directory.glob(
            "event_*.mp4"
        )
    )

    print(
        f"Evidence clips found: "
        f"{len(clips)}"
    )

    for clip in clips:

        size_mb = (
            clip.stat().st_size
            / (1024 * 1024)
        )

        print(
            f"Clip: {clip.name}"
        )

        print(
            f"Size: {size_mb:.2f} MB"
        )

    print("=" * 60)
    print(
        "EVIDENCE RECORDER TEST COMPLETE"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()