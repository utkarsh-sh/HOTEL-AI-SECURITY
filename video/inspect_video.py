from pathlib import Path

import cv2


VIDEO_PATH = Path("data/input/test_cctv.mp4")
OUTPUT_DIR = Path("data/output/video_test")


def main():
    print("=" * 60)
    print("HOTEL AI CCTV - VIDEO INSPECTION")
    print("=" * 60)

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(
            f"Video not found: {VIDEO_PATH}"
        )

    print(f"Video: {VIDEO_PATH}")

    capture = cv2.VideoCapture(str(VIDEO_PATH))

    if not capture.isOpened():
        raise RuntimeError(
            "OpenCV could not open the video."
        )

    # Read video metadata
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    duration = frame_count / fps if fps > 0 else 0

    print(f"Resolution : {width} x {height}")
    print(f"FPS        : {fps:.2f}")
    print(f"Frames     : {frame_count}")
    print(f"Duration   : {duration:.2f} seconds")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read a few frames
    frame_numbers = [0, frame_count // 2, max(frame_count - 1, 0)]

    saved = 0

    for frame_number in frame_numbers:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        success, frame = capture.read()

        if not success:
            print(f"Could not read frame {frame_number}")
            continue

        output_path = OUTPUT_DIR / f"frame_{frame_number:06d}.jpg"

        if cv2.imwrite(str(output_path), frame):
            print(f"Saved: {output_path}")
            saved += 1
        else:
            print(f"FAILED to save: {output_path}")

    capture.release()

    print("-" * 60)
    print(f"Frames successfully saved: {saved}")
    print("=" * 60)


if __name__ == "__main__":
    main()