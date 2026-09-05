from pathlib import Path

import cv2

from ai.person_detector import PersonDetector
from ai.tracker import PersonTracker


VIDEO_PATH = Path(
    "data/input/test_cctv.mp4"
)

OUTPUT_PATH = Path(
    "data/output/person_tracking_video.mp4"
)

TARGET_AI_FPS = 5.0

CONFIDENCE_THRESHOLD = 0.50

IOU_THRESHOLD = 0.30

MAX_MISSED = 5


def main():

    print("=" * 60)
    print("HOTEL AI CCTV - PERSON TRACKING")
    print("=" * 60)

    # ---------------------------------------
    # Open video
    # ---------------------------------------

    capture = cv2.VideoCapture(
        str(VIDEO_PATH)
    )

    if not capture.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
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

    source_fps = capture.get(
        cv2.CAP_PROP_FPS
    )

    total_frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    print(
        f"Resolution : "
        f"{width} x {height}"
    )

    print(
        f"Source FPS : "
        f"{source_fps:.2f}"
    )

    print(
        f"Frames     : "
        f"{total_frames}"
    )

    print(
        f"AI FPS     : "
        f"{TARGET_AI_FPS}"
    )

    # ---------------------------------------
    # Output video
    # ---------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    writer = cv2.VideoWriter(
        str(OUTPUT_PATH),
        fourcc,
        source_fps,
        (width, height)
    )

    if not writer.isOpened():
        capture.release()

        raise RuntimeError(
            "Could not create output video."
        )

    # ---------------------------------------
    # AI detector
    # ---------------------------------------

    detector = PersonDetector(
        confidence_threshold=CONFIDENCE_THRESHOLD
    )

    # ---------------------------------------
    # Tracker
    # ---------------------------------------

    tracker = PersonTracker(
        iou_threshold=IOU_THRESHOLD,
        max_missed=MAX_MISSED,
    )

    print("-" * 60)
    print("Detector loaded.")
    print("Tracker loaded.")
    print("Processing...")
    print("-" * 60)

    # ---------------------------------------
    # Sampling
    # ---------------------------------------

    sample_every = max(
        1,
        int(
            round(
                source_fps
                / TARGET_AI_FPS
            )
        )
    )

    frame_index = 0

    processed_ai_frames = 0

    unique_track_ids = set()

    last_tracks = []

    while True:

        success, frame = capture.read()

        if not success:
            break

        # -----------------------------------
        # Run detection + tracking
        # -----------------------------------

        if (
            frame_index
            % sample_every
            == 0
        ):

            detections = detector.detect(
                frame
            )

            last_tracks = tracker.update(
                detections
            )

            print(
                f"Frame {frame_index}: "
                f"tracks = "
                f"{[track['track_id'] for track in last_tracks]}"
     )

            processed_ai_frames += 1

            for track in last_tracks:

                unique_track_ids.add(
                    track["track_id"]
                )

        # -----------------------------------
        # Draw tracks
        # -----------------------------------

        for track in last_tracks:

            x1, y1, x2, y2 = (
                track["box"]
            )

            confidence = (
                track["confidence"]
            )

            track_id = (
                track["track_id"]
            )

            # Bounding box
            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                3,
            )

            # Track label
            label = (
                f"PERSON "
                f"ID:{track_id} "
                f"{confidence:.2f}"
            )

            cv2.putText(
                frame,
                label,
                (
                    x1,
                    max(
                        y1 - 10,
                        25
                    ),
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )

        # -----------------------------------
        # System information
        # -----------------------------------

        info = (
            f"AI FPS: "
            f"{TARGET_AI_FPS:.1f} | "
            f"Frame: "
            f"{frame_index}/"
            f"{total_frames} | "
            f"Active tracks: "
            f"{len(last_tracks)}"
        )

        cv2.putText(
            frame,
            info,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        writer.write(frame)

        # -----------------------------------
        # Progress
        # -----------------------------------

        frame_index += 1

        if (
            frame_index % 100
            == 0
        ):

            progress = (
                frame_index
                / total_frames
            ) * 100

            print(
                f"Progress: "
                f"{progress:.1f}% | "
                f"AI frames: "
                f"{processed_ai_frames} | "
                f"Tracks seen: "
                f"{len(unique_track_ids)}"
            )

    # ---------------------------------------
    # Cleanup
    # ---------------------------------------

    capture.release()
    writer.release()

    print("=" * 60)
    print("TRACKING COMPLETE")
    print("=" * 60)

    print(
        f"Total frames: "
        f"{frame_index}"
    )

    print(
        f"AI frames: "
        f"{processed_ai_frames}"
    )

    print(
        f"Unique track IDs: "
        f"{len(unique_track_ids)}"
    )

    print(
        f"Track IDs: "
        f"{sorted(unique_track_ids)}"
    )

    print(
        f"Output: "
        f"{OUTPUT_PATH}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()