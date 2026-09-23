import cv2
from pathlib import Path

video = Path("data/input/01_person_tracking_intrusion.mp4")
output = Path("data/output/ground_truth_contact_sheet.jpg")

cap = cv2.VideoCapture(str(video))

fps = cap.get(cv2.CAP_PROP_FPS)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

if not cap.isOpened():
    raise RuntimeError("Could not open video")

indices = [round(i * (total - 1) / 17) for i in range(18)]

frames = []

for frame_index in indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()

    if not ok:
        continue

    frame = cv2.resize(frame, (480, 270))

    cv2.putText(
        frame,
        f"Frame {frame_index} | {frame_index / fps:.2f}s",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    frames.append(frame)

cap.release()

cols = 3
rows = (len(frames) + cols - 1) // cols

blank = 255 * __import__("numpy").ones_like(frames[0])

rows_data = []

for row in range(rows):
    row_frames = frames[row * cols:(row + 1) * cols]

    while len(row_frames) < cols:
        row_frames.append(blank.copy())

    rows_data.append(cv2.hconcat(row_frames))

sheet = cv2.vconcat(rows_data)

output.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(output), sheet)

print(f"Created: {output}")
print(f"FPS: {fps}")
print(f"Frames: {total}")
print(f"Duration: {total / fps:.2f} seconds")
print(f"Annotation frames: {indices}")
