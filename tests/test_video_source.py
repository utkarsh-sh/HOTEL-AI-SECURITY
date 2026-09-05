import cv2
import numpy as np


def main():
    # Create a synthetic CCTV-like frame.
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Draw a simple test scene.
    cv2.rectangle(
        frame,
        (450, 150),
        (830, 650),
        (255, 255, 255),
        3,
    )

    cv2.putText(
        frame,
        "HOTEL AI CCTV - VIDEO PIPELINE TEST",
        (220, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 255, 255),
        2,
    )

    output_path = "data/output/video_pipeline_test.jpg"

    cv2.imwrite(output_path, frame)

    print(f"Test frame saved: {output_path}")
    print(f"Frame size: {frame.shape}")


if __name__ == "__main__":
    main()