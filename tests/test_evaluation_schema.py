import json
from pathlib import Path

import pytest

from evaluation.schema import (
    EvaluationEvent,
    EvaluationVideo,
    load_ground_truth,
    save_ground_truth,
)


def test_evaluation_event_round_trip():
    event = EvaluationEvent(
        event_type="INTRUSION",
        zone_id="ZONE-001",
        start_frame=120,
        end_frame=180,
    )

    payload = event.to_dict()

    assert payload == {
        "event_type": "INTRUSION",
        "zone_id": "ZONE-001",
        "start_frame": 120,
        "end_frame": 180,
    }

    restored = EvaluationEvent.from_dict(payload)

    assert restored == event


def test_evaluation_video_round_trip(tmp_path):
    video = EvaluationVideo(
        video="01_person_tracking_intrusion.mp4",
        camera_id="CAM-001",
        events=[
            EvaluationEvent(
                event_type="INTRUSION",
                zone_id="ZONE-001",
                start_frame=120,
                end_frame=180,
            )
        ],
    )

    path = tmp_path / "ground_truth.json"

    save_ground_truth(video, path)

    restored = load_ground_truth(path)

    assert restored == video


def test_negative_frame_range_rejected():
    with pytest.raises(ValueError):
        EvaluationEvent(
            event_type="INTRUSION",
            zone_id="ZONE-001",
            start_frame=-1,
            end_frame=10,
        )


def test_end_frame_before_start_frame_rejected():
    with pytest.raises(ValueError):
        EvaluationEvent(
            event_type="INTRUSION",
            zone_id="ZONE-001",
            start_frame=100,
            end_frame=50,
        )


def test_empty_event_type_rejected():
    with pytest.raises(ValueError):
        EvaluationEvent(
            event_type="",
            zone_id="ZONE-001",
            start_frame=10,
            end_frame=20,
        )


def test_invalid_ground_truth_payload_rejected(tmp_path):
    path = tmp_path / "invalid.json"

    path.write_text(
        json.dumps(
            {
                "video": "test.mp4",
                "camera_id": "CAM-001",
                "events": "not-a-list",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_ground_truth(path)
