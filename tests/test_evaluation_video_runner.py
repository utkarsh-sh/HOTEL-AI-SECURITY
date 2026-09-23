from evaluation.video_runner import (
    prediction_from_event,
)


def test_prediction_from_intrusion_event():
    event = {
        "event_type": "INTRUSION",
        "zone_id": "ZONE-001",
        "zone_name": "Restricted Area",
        "track_id": 7,
        "severity": "HIGH",
        "message": "Person 7 entered Restricted Area",
    }

    result = prediction_from_event(
        event=event,
        frame_index=125,
    )

    assert result == {
        "event_type": "INTRUSION",
        "zone_id": "ZONE-001",
        "start_frame": 125,
        "end_frame": 125,
    }


def test_prediction_from_event_ignores_runtime_metadata():
    event = {
        "event_type": "INTRUSION",
        "zone_id": "ZONE-002",
        "zone_name": "Lobby",
        "track_id": 12,
        "severity": "HIGH",
        "message": "Person 12 entered Lobby",
        "model_version": "prototype-v1",
        "event_id": 99,
    }

    result = prediction_from_event(
        event=event,
        frame_index=300,
    )

    assert result["event_type"] == "INTRUSION"
    assert result["zone_id"] == "ZONE-002"
    assert result["start_frame"] == 300
    assert result["end_frame"] == 300


def test_prediction_from_event_does_not_mutate_input():
    event = {
        "event_type": "INTRUSION",
        "zone_id": "ZONE-001",
        "track_id": 1,
    }

    original = dict(event)

    prediction_from_event(
        event=event,
        frame_index=50,
    )

    assert event == original
