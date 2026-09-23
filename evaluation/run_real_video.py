import json

from ai.person_detector import PersonDetector
from ai.tracker import PersonTracker
from ai.zone_detector import ZoneDetector
from rules.intrusion_rules import IntrusionRule

from evaluation.artifact import (
    EvaluationArtifact,
    save_evaluation_artifact,
)

from evaluation.video_runner import (
    OpenCVVideoSource,
    run_event_pipeline,
)


VIDEO = "data/input/01_person_tracking_intrusion.mp4"
ZONES = "configs/zones.json"

CAMERA_ID = "CAM-001"
SOURCE_FPS = 25.0
AI_FPS = 5.0
MODEL_VERSION = "prototype-v1"

OUTPUT = "data/output/evaluation_CAM-001.json"


with open(ZONES, "r", encoding="utf-8") as f:
    zone_config = json.load(f)

zones = zone_config["zones"]

source = OpenCVVideoSource(VIDEO)

detector = PersonDetector()
tracker = PersonTracker()
zone_detector = ZoneDetector(zones)
intrusion_rule = IntrusionRule(
    persistence_frames=3
)

result = run_event_pipeline(
    source=source,
    detector=detector,
    tracker=tracker,
    zone_detector=zone_detector,
    intrusion_rule=intrusion_rule,
    source_fps=SOURCE_FPS,
    ai_fps=AI_FPS,
)

artifact = EvaluationArtifact(
    video=VIDEO,
    camera_id=CAMERA_ID,
    source_fps=SOURCE_FPS,
    ai_fps=AI_FPS,
    model_version=MODEL_VERSION,
    result=result,
)

save_evaluation_artifact(
    artifact,
    OUTPUT,
)

print()
print("==============================================")
print("EVALUATION ARTIFACT CREATED")
print("==============================================")
print(f"Video          : {VIDEO}")
print(f"Camera         : {CAMERA_ID}")
print(f"Model          : {MODEL_VERSION}")
print(f"Total frames   : {result.total_frames}")
print(f"AI frames      : {result.ai_frames}")
print(f"Predictions    : {len(result.predictions)}")
print(f"Saved artifact : {OUTPUT}")
print("==============================================")
