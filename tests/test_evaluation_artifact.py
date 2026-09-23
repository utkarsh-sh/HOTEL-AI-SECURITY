import json

from evaluation.video_runner import VideoPipelineResult
from evaluation.artifact import (
    EvaluationArtifact,
    save_evaluation_artifact,
    load_evaluation_artifact,
)


def test_evaluation_artifact_round_trip(tmp_path):

    result = VideoPipelineResult(
        total_frames=534,
        ai_frames=107,
        predictions=[
            {
                "event_type": "INTRUSION",
                "zone_id": "restricted_01",
                "start_frame": 10,
                "end_frame": 10,
            },
            {
                "event_type": "INTRUSION",
                "zone_id": "restricted_01",
                "start_frame": 45,
                "end_frame": 45,
            },
        ],
    )

    artifact = EvaluationArtifact(
        video="data/input/01_person_tracking_intrusion.mp4",
        camera_id="CAM-001",
        source_fps=25.0,
        ai_fps=5.0,
        model_version="prototype-v1",
        result=result,
    )

    path = tmp_path / "evaluation.json"

    save_evaluation_artifact(artifact, path)

    loaded = load_evaluation_artifact(path)

    assert loaded.video == artifact.video
    assert loaded.camera_id == artifact.camera_id
    assert loaded.source_fps == 25.0
    assert loaded.ai_fps == 5.0
    assert loaded.model_version == "prototype-v1"

    assert loaded.result.total_frames == 534
    assert loaded.result.ai_frames == 107
    assert len(loaded.result.predictions) == 2


def test_saved_artifact_is_valid_json(tmp_path):

    result = VideoPipelineResult(
        total_frames=10,
        ai_frames=2,
        predictions=[],
    )

    artifact = EvaluationArtifact(
        video="test.mp4",
        camera_id="CAM-001",
        source_fps=25.0,
        ai_fps=5.0,
        model_version="prototype-v1",
        result=result,
    )

    path = tmp_path / "evaluation.json"

    save_evaluation_artifact(artifact, path)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["video"] == "test.mp4"
    assert data["camera_id"] == "CAM-001"
    assert data["result"]["total_frames"] == 10


def test_invalid_fps_rejected():

    result = VideoPipelineResult(
        total_frames=1,
        ai_frames=1,
        predictions=[],
    )

    try:
        EvaluationArtifact(
            video="test.mp4",
            camera_id="CAM-001",
            source_fps=0,
            ai_fps=5.0,
            model_version="prototype-v1",
            result=result,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for invalid source_fps"
    )
