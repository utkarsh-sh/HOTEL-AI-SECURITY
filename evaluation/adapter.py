from typing import Any, Dict, List

from evaluation.schema import EvaluationEvent


_REQUIRED_FIELDS = {
    "event_type",
    "zone_id",
    "start_frame",
    "end_frame",
}


def convert_prediction_events(
    predictions: List[Dict[str, Any]],
) -> List[EvaluationEvent]:
    """
    Convert production-style prediction dictionaries into
    EvaluationEvent objects.

    Required fields:
    - event_type
    - zone_id
    - start_frame
    - end_frame
    """

    if not isinstance(predictions, list):
        raise ValueError("predictions must be a list")

    converted: List[EvaluationEvent] = []

    for index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            raise ValueError(
                f"prediction at index {index} must be an object"
            )

        missing = _REQUIRED_FIELDS - prediction.keys()

        if missing:
            raise ValueError(
                f"prediction at index {index} is missing fields: "
                f"{sorted(missing)}"
            )

        converted.append(
            EvaluationEvent(
                event_type=prediction["event_type"],
                zone_id=prediction["zone_id"],
                start_frame=prediction["start_frame"],
                end_frame=prediction["end_frame"],
            )
        )

    return converted
