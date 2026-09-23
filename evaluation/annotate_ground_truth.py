import cv2
import json
from pathlib import Path
import numpy as np


VIDEO = "data/input/01_person_tracking_intrusion.mp4"
ZONE_FILE = "configs/zones.json"
OUTPUT = "data/output/ground_truth_ranges.json"


with open(ZONE_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

zone = config["zones"][0]
polygon_points = np.array(zone["points"], dtype=np.int32)


cap = cv2.VideoCapture(VIDEO)

if not cap.isOpened():
    raise RuntimeError("Could not open video")

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))


current_frame = 0
start_frame = None
ranges = []
playing = False


def get_frame(index):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()

    if not ok:
        return None

    return frame


def draw_frame(frame):
    display = frame.copy()

    # Draw restricted zone.
    cv2.polylines(
        display,
        [polygon_points],
        True,
        (0, 255, 255),
        5,
    )

    # Zone label.
    cv2.putText(
        display,
        "RESTRICTED ZONE",
        (520, 650),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 255),
        3,
        cv2.LINE_AA,
    )

    # Frame information.
    timestamp = current_frame / fps

    cv2.putText(
        display,
        f"Frame: {current_frame}/{total_frames - 1}",
        (30, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        display,
        f"Time: {timestamp:.2f}s",
        (30, 85),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if start_frame is None:
        status = "No start marked"
    else:
        status = f"START = {start_frame}"

    if ranges:
        status += f" | Completed ranges = {len(ranges)}"

    cv2.putText(
        display,
        status,
        (30, 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        display,
        "SPACE Play/Pause | N/RIGHT Next | P/LEFT Previous",
        (30, display.shape[0] - 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        display,
        "S = mark START | E = mark END | R = reset | Q = save & quit",
        (30, display.shape[0] - 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    return display


print()
print("==============================================")
print("GROUND-TRUTH ANNOTATION TOOL")
print("==============================================")
print()
print("Look at the person's feet/bottom-center.")
print("When that point ENTERS the yellow zone:")
print("    press S")
print()
print("When that point LEAVES the yellow zone:")
print("    press E")
print()
print("Controls:")
print("    SPACE       Play / Pause")
print("    RIGHT / N   Next frame")
print("    LEFT / P    Previous frame")
print("    S           Mark intrusion START")
print("    E           Mark intrusion END")
print("    R           Reset current unfinished range")
print("    Q           Save and quit")
print()
print("==============================================")


cv2.namedWindow(
    "Ground Truth Annotation",
    cv2.WINDOW_NORMAL,
)

cv2.resizeWindow(
    "Ground Truth Annotation",
    1280,
    720,
)


while True:

    frame = get_frame(current_frame)

    if frame is None:
        break

    display = draw_frame(frame)

    cv2.imshow(
        "Ground Truth Annotation",
        display,
    )

    key = cv2.waitKey(30 if playing else 0) & 0xFF

    # Q = quit and save.
    if key in (ord("q"), ord("Q")):
        break

    # SPACE = play/pause.
    elif key == 32:
        playing = not playing

    # Next frame.
    elif key in (ord("n"), ord("N"), 83):
        current_frame = min(
            current_frame + 1,
            total_frames - 1,
        )

    # Previous frame.
    elif key in (ord("p"), ord("P"), 81):
        current_frame = max(
            current_frame - 1,
            0,
        )

    # Mark start.
    elif key in (ord("s"), ord("S")):

        start_frame = current_frame

        print(
            f"[START] frame={start_frame} "
            f"time={start_frame / fps:.2f}s"
        )

    # Mark end.
    elif key in (ord("e"), ord("E")):

        if start_frame is None:
            print("[WARNING] Mark START first.")
            continue

        if current_frame < start_frame:
            print("[WARNING] END must be after START.")
            continue

        ranges.append(
            {
                "event_type": "INTRUSION",
                "zone_id": zone["zone_id"],
                "start_frame": start_frame,
                "end_frame": current_frame,
            }
        )

        print(
            f"[RANGE SAVED] "
            f"{start_frame} -> {current_frame} "
            f"({start_frame / fps:.2f}s -> "
            f"{current_frame / fps:.2f}s)"
        )

        start_frame = None

    # Reset unfinished annotation.
    elif key in (ord("r"), ord("R")):

        start_frame = None
        print("[RESET] Current unfinished range cleared.")

    # Advance automatically during playback.
    if playing:

        if current_frame < total_frames - 1:
            current_frame += 1
        else:
            playing = False


cap.release()
cv2.destroyAllWindows()


result = {
    "video": VIDEO,
    "camera_id": "CAM-001",
    "fps": fps,
    "total_frames": total_frames,
    "events": ranges,
}


Path(OUTPUT).parent.mkdir(
    parents=True,
    exist_ok=True,
)

with open(
    OUTPUT,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        result,
        f,
        indent=2,
    )


print()
print("==============================================")
print("ANNOTATION COMPLETE")
print("==============================================")
print(f"Saved: {OUTPUT}")
print(f"Events marked: {len(ranges)}")

for index, event in enumerate(ranges, 1):
    print(
        f"Event {index}: "
        f"{event['start_frame']} -> "
        f"{event['end_frame']}"
    )
