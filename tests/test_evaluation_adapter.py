import pytest

from evaluation.adapter import (
    convert_prediction_events,
)
from evaluation.schema import EvaluationEvent


def test_convert_prediction_event():
    predictions = [
        {
            "event_type": "INTRUSION",
            "zone_id": "ZONE-001",
            "start_frame": 100,
            "end_frame": 140,
        }
    ]

    result = convert_prediction_events(predictions)

    assert len(result) == 1
    assert isinstance(result[0], EvaluationEvent)
    assert result[0].event_type == "INTRUSION"
    assert result[0].zone_id == "ZONE-001"
    assert result[0].start_frame == 100
    assert result[0].end_frame == 140


def test_convert_multiple_prediction_events():
    predictions = [
        {
            "event_type": "INTRUSION",
            "zone_id": "ZONE-001",
            "start_frame": 100,
            "end_frame": 140,
        },
        {
            "event_type": "INTRUSION",
            "zone_id": "ZONE-002",
            "start_frame": 300,
            "end_frame": 350,
        },
    ]

    result = convert_prediction_events(predictions)

    assert len(result) == 2
    assert result[0].zone_id == "ZONE-001"
    assert result[1].zone_id == "ZONE-002"


def test_missing_required_field_is_rejected():
    predictions = [
        {
            "event_type": "INTRUSION",
            "zone_id": "ZONE-001",
            "start_frame": 100,
        }
    ]

    with pytest.raises(ValueError):
        convert_prediction_events(predictions)


def test_invalid_event_type_is_rejected():
    predictions = [
        {
            "event_type": "",
            "zone_id": "ZONE-001",
            "start_frame": 100,
            "end_frame": 140,
        }
    ]

    with pytest.raises(ValueError):
        convert_prediction_events(predictions)


def test_non_list_input_is_rejected():
    with pytest.raises(ValueError):
        convert_prediction_events({})
