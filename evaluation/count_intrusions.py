import json
from collections import defaultdict

from ai.person_detector import PersonDetector
from ai.tracker import PersonTracker
from ai.zone_detector import ZoneDetector
from evaluation.video_runner import OpenCVVideoSource


VIDEO = "data/input/01_person_tracking_intrusion.mp4"
ZONES = "configs/zones.json"

SOURCE_FPS = 25.0
AI_FPS = 5.0


with open(ZONES, "r", encoding="utf-8") as f:
    zone_config = json.load(f)

zones = zone_config["zones"]

source = OpenCVVideoSource(VIDEO)
detector = PersonDetector()
tracker = PersonTracker()
zone_detector = ZoneDetector(zones)


sample_interval = max(
    1,
    round(SOURCE_FPS / AI_FPS),
)

total_frames = 0
ai_frames = 0

# Current inside/outside state for each track-zone pair.
inside_state = {}

# Active entry episodes.
active_entries = {}

# Completed intrusion episodes.
intrusions = []


while True:

    frame = source.read()

    if frame is None:
        break

    frame_index = total_frames
    total_frames += 1

    if frame_index % sample_interval != 0:
        continue

    ai_frames += 1

    detections = detector.detect(frame)
    tracks = tracker.update(detections)

    zone_results = zone_detector.check_tracks(tracks)

    current_pairs = set()

    for result in zone_results:

        zone_id = result["zone_id"]
        track_id = result["track_id"]
        inside = result["inside"]

        key = (zone_id, track_id)

        current_pairs.add(key)

        previous_inside = inside_state.get(
            key,
            False,
        )

        # Outside -> Inside = new intrusion episode.
        if inside and not previous_inside:

            active_entries[key] = frame_index

            print(
                f"[ENTRY] "
                f"track={track_id} "
                f"zone={zone_id} "
                f"frame={frame_index} "
                f"time={frame_index / SOURCE_FPS:.2f}s"
            )

        # Inside -> Outside = intrusion episode ended.
        elif not inside and previous_inside:

            start_frame = active_entries.pop(
                key,
                frame_index,
            )

            intrusion = {
                "event_type": "INTRUSION",
                "zone_id": zone_id,
                "track_id": track_id,
                "start_frame": start_frame,
                "end_frame": frame_index,
            }

            intrusions.append(intrusion)

            print(
                f"[EXIT] "
                f"track={track_id} "
                f"zone={zone_id} "
                f"frame={frame_index} "
                f"time={frame_index / SOURCE_FPS:.2f}s"
            )

        inside_state[key] = inside

    # If a tracked pair disappears from the current
    # zone results while it was inside, close it.
    disappeared = set(inside_state) - current_pairs

    for key in disappeared:

        if inside_state[key]:

            start_frame = active_entries.pop(
                key,
                total_frames - 1,
            )

            zone_id, track_id = key

            intrusion = {
                "event_type": "INTRUSION",
                "zone_id": zone_id,
                "track_id": track_id,
                "start_frame": start_frame,
                "end_frame": total_frames - 1,
            }

            intrusions.append(intrusion)

            print(
                f"[TRACK END] "
                f"track={track_id} "
                f"zone={zone_id}"
            )

        inside_state.pop(key, None)


source.close()


# Close anything still inside at video end.
for key, start_frame in active_entries.items():

    zone_id, track_id = key

    intrusions.append(
        {
            "event_type": "INTRUSION",
            "zone_id": zone_id,
            "track_id": track_id,
            "start_frame": start_frame,
            "end_frame": total_frames - 1,
        }
    )


print()
print("==============================================")
print("AUTOMATED INTRUSION COUNT")
print("==============================================")
print(f"Total video frames : {total_frames}")
print(f"AI frames          : {ai_frames}")
print(f"Intrusion episodes  : {len(intrusions)}")
print()

for index, event in enumerate(intrusions, 1):

    duration_frames = (
        event["end_frame"]
        - event["start_frame"]
    )

    print(
        f"{index}. "
        f"Track={event['track_id']} | "
        f"Zone={event['zone_id']} | "
        f"Frames={event['start_frame']}-"
        f"{event['end_frame']} | "
        f"Duration={duration_frames / SOURCE_FPS:.2f}s"
    )

print("==============================================")

output = {
    "video": VIDEO,
    "camera_id": "CAM-001",
    "source_fps": SOURCE_FPS,
    "ai_fps": AI_FPS,
    "total_frames": total_frames,
    "ai_frames": ai_frames,
    "intrusion_count": len(intrusions),
    "intrusions": intrusions,
}

with open(
    "data/output/automated_intrusion_count.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        output,
        f,
        indent=2,
    )

print()
print(
    "Saved: "
    "data/output/automated_intrusion_count.json"
)
