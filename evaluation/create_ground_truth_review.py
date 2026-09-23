import cv2
import json
from pathlib import Path

video = Path("data/input/01_person_tracking_intrusion.mp4")
output = Path("data/output/ground_truth_review.mp4")

with open("configs/zones.json", "r", encoding="utf-8") as f:
    config = json.load(f)

zone = config["zones"][0]
points = zone["points"]

cap = cv2.VideoCapture(str(video))

fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(
    str(output),
    fourcc,
    fps,
    (width, height),
)

frame_index = 0

while True:
    ok, frame = cap.read()

    if not ok:
        break

    polygon = __import__("numpy").array(
        points,
        dtype="int32",
    )

    cv2.polylines(
        frame,
        [polygon],
        True,
        (0, 255, 255),
        4,
    )

    cv2.putText(
        frame,
        f"Frame: {frame_index} | Time: {frame_index / fps:.2f}s",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 255),
        3,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        "RESTRICTED ZONE",
        (520, 650),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        3,
        cv2.LINE_AA,
    )

    writer.write(frame)
    frame_index += 1

cap.release()
writer.release()

print(f"Created: {output}")
print(f"Frames: {frame_index}")
print(f"FPS: {fps}")
print(f"Duration: {frame_index / fps:.2f}s")
