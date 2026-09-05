from pathlib import Path

import cv2
import torch

from ai.person_detector import PersonDetector


VIDEO_PATH = Path("data/input/test_cctv.mp4")
OUTPUT_PATH = Path(
    "data/output/person_detection_test.jpg"
)


def main():
    print("=" * 60)
    print("HOTEL AI CCTV - FIRST PERSON DETECTION")
    print("=" * 60)

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(
            f"Video not found: {VIDEO_PATH}"
        )

    # -----------------------------
    # Load video
    # -----------------------------

    capture = cv2.VideoCapture(
        str(VIDEO_PATH)
    )

    if not capture.isOpened():
        raise RuntimeError(
            "Could not open CCTV video."
        )

    # Read first frame
    success, frame = capture.read()

    capture.release()

    if not success:
        raise RuntimeError(
            "Could not read first video frame."
        )

    print(
        f"Input frame: "
        f"{frame.shape[1]} x {frame.shape[0]}"
    )

    # -----------------------------
    # Load detector
    # -----------------------------

    detector = PersonDetector(
        confidence_threshold=0.50
    )

    # -----------------------------
    # Run AI inference
    # -----------------------------

    print("Running AI inference...")

    detections = detector.detect(frame)

    # -----------------------------
    # Draw detections
    # -----------------------------

    for detection in detections:

        x1, y1, x2, y2 = detection["box"]

        confidence = detection["confidence"]

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            3,
        )

        label = (
            f"PERSON "
            f"{confidence:.2f}"
        )

        cv2.putText(
            frame,
            label,
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

    # -----------------------------
    # Save result
    # -----------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    success = cv2.imwrite(
        str(OUTPUT_PATH),
        frame
    )

    if not success:
        raise RuntimeError(
            "Could not save detection image."
        )

    # -----------------------------
    # Results
    # -----------------------------

    print("-" * 60)
    print(
        f"People detected: "
        f"{len(detections)}"
    )

    for index, detection in enumerate(
        detections,
        start=1
    ):
        print(
            f"Person {index}: "
            f"confidence="
            f"{detection['confidence']:.3f}, "
            f"box="
            f"{detection['box']}"
        )

    print(
        f"GPU memory allocated: "
        f"{torch.cuda.memory_allocated() / 1024**2:.1f} MB"
        if torch.cuda.is_available()
        else "GPU not available"
    )

    print(
        f"Result saved: {OUTPUT_PATH}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()