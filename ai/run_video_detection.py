from pathlib import Path
import time

import cv2

from ai.person_detector import PersonDetector


VIDEO_PATH = Path("data/input/test_cctv.mp4")
OUTPUT_PATH = Path(
    "data/output/person_detection_video.mp4"
)

TARGET_AI_FPS = 5.0
CONFIDENCE_THRESHOLD = 0.50


def main():
    print("=" * 60)
    print("HOTEL AI CCTV - VIDEO-WIDE PERSON DETECTION")
    print("=" * 60)

    # --------------------------------
    # Open video
    # --------------------------------

    capture = cv2.VideoCapture(str(VIDEO_PATH))

    if not capture.isOpened():
        raise RuntimeError(
            f"Could not open video: {VIDEO_PATH}"
        )

    width = int(
        capture.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    source_fps = capture.get(
        cv2.CAP_PROP_FPS
    )

    total_frames = int(
        capture.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    duration = (
        total_frames / source_fps
        if source_fps > 0
        else 0
    )

    print(f"Resolution : {width} x {height}")
    print(f"Source FPS : {source_fps:.2f}")
    print(f"Frames     : {total_frames}")
    print(f"Duration   : {duration:.2f}s")
    print(f"AI FPS     : {TARGET_AI_FPS}")

    # --------------------------------
    # Output video
    # --------------------------------

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

    # --------------------------------
    # Load AI
    # --------------------------------

    detector = PersonDetector(
        confidence_threshold=CONFIDENCE_THRESHOLD
    )

    print("-" * 60)
    print("AI detector loaded.")
    print("Processing video...")
    print("-" * 60)

    # --------------------------------
    # Frame sampling
    # --------------------------------

    sample_every = max(
        1,
        int(round(source_fps / TARGET_AI_FPS))
    )

    frame_index = 0
    processed_frames = 0
    total_people = 0

    inference_time_total = 0.0

    last_detections = []

    while True:

        success, frame = capture.read()

        if not success:
            break

        # Run AI only on sampled frames
        if frame_index % sample_every == 0:

            start_time = time.perf_counter()

            last_detections = detector.detect(
                frame
            )

            inference_time = (
                time.perf_counter()
                - start_time
            )

            inference_time_total += (
                inference_time
            )

            processed_frames += 1
            total_people += len(
                last_detections
            )

        # --------------------------------
        # Draw latest detections
        # --------------------------------

        for detection in last_detections:

            x1, y1, x2, y2 = (
                detection["box"]
            )

            confidence = (
                detection["confidence"]
            )

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                3
            )

            label = (
                f"PERSON "
                f"{confidence:.2f}"
            )

            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 10, 25)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

        # --------------------------------
        # Draw system information
        # --------------------------------

        info = (
            f"AI FPS: {TARGET_AI_FPS:.1f} | "
            f"Frame: {frame_index}/{total_frames} | "
            f"People: {len(last_detections)}"
        )

        cv2.putText(
            frame,
            info,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        writer.write(frame)

        frame_index += 1

        # Progress
        if frame_index % 100 == 0:

            progress = (
                frame_index / total_frames
            ) * 100

            print(
                f"Progress: "
                f"{progress:.1f}% | "
                f"AI frames: "
                f"{processed_frames}"
            )

    # --------------------------------
    # Cleanup
    # --------------------------------

    capture.release()
    writer.release()

    average_inference = (
        inference_time_total / processed_frames
        if processed_frames > 0
        else 0
    )

    print("=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)

    print(
        f"Total video frames : {frame_index}"
    )

    print(
        f"AI frames processed: "
        f"{processed_frames}"
    )

    print(
        f"Average inference : "
        f"{average_inference * 1000:.1f} ms"
    )

    print(
        f"Total detections   : "
        f"{total_people}"
    )

    print(
        f"Output video       : "
        f"{OUTPUT_PATH}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()