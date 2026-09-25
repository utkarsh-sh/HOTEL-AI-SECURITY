from pathlib import Path
import cv2

from ai.weapon_vision_adapter import (
    WEAPON_MODEL_SHA256,
    WEAPON_MODEL_VERSION,
    WeaponVisionAdapter,
)

MODEL = Path("data/models/weapon/gun-knife-yolo11n/best.onnx")
POSITIVE = Path.home() / "hotel-ai-security-weapon-eval" / "data" / "weapon_positive_pistol.mp4"
NEGATIVE = Path("data/input/01_person_tracking_intrusion.mp4")


def run(adapter, label: str, path: Path) -> None:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {label} video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    gun_hits = 0
    knife_hits = 0
    max_gun = 0.0
    max_knife = 0.0
    frame_no = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        detections = adapter.detect(frame)
        guns = [d for d in detections if d["class_name"] == "gun"]
        knives = [d for d in detections if d["class_name"] == "knife"]

        if guns:
            gun_hits += 1
            max_gun = max(max_gun, max(d["confidence"] for d in guns))
        if knives:
            knife_hits += 1
            max_knife = max(max_knife, max(d["confidence"] for d in knives))

        frame_no += 1

    cap.release()

    print(f"{label}: frames={frame_no}/{total}, gun_frames={gun_hits}, knife_frames={knife_hits}, max_gun={max_gun:.4f}, max_knife={max_knife:.4f}, fps={fps:.2f}")


adapter = WeaponVisionAdapter(
    MODEL,
    confidence_threshold=0.50,
    expected_sha256=WEAPON_MODEL_SHA256,
    prefer_cuda=True,
)

print("model_version:", WEAPON_MODEL_VERSION)
print("execution_providers:", adapter.execution_providers)
run(adapter, "positive_pistol", POSITIVE)
run(adapter, "negative_cctv", NEGATIVE)
adapter.close()
