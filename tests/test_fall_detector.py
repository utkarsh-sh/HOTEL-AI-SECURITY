import pytest

from ai.fall_detector import FallDetector


def test_fall_detector_requires_positive_persistence_frames():
    with pytest.raises(ValueError):
        FallDetector(persistence_frames=0)


def test_fall_detector_requires_positive_aspect_ratio():
    with pytest.raises(ValueError):
        FallDetector(min_horizontal_aspect_ratio=0)


def test_vertical_person_is_not_fall():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    result = detector.evaluate(
        track_id=1,
        box=[400, 200, 500, 500],
    )

    assert result is None


def test_horizontal_person_becomes_fall_after_persistence():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    assert detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    ) is None

    result = detector.evaluate(
        track_id=1,
        box=[405, 405, 705, 505],
    )

    assert result is not None
    assert result["event_type"] == "FALL"
    assert result["severity"] == "HIGH"
    assert result["track_id"] == 1
    assert "Potential person-down" in result["message"]


def test_non_fall_resets_persistence():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    assert detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    ) is None

    assert detector.evaluate(
        track_id=1,
        box=[400, 200, 500, 500],
    ) is None

    assert detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    ) is None


def test_same_track_alerts_only_once_until_reset():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    )

    first = detector.evaluate(
        track_id=1,
        box=[405, 405, 705, 505],
    )

    second = detector.evaluate(
        track_id=1,
        box=[410, 410, 710, 510],
    )

    assert first is not None
    assert second is None


def test_tracks_are_independent():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    assert detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    ) is None

    assert detector.evaluate(
        track_id=2,
        box=[800, 200, 900, 500],
    ) is None

    result = detector.evaluate(
        track_id=1,
        box=[405, 405, 705, 505],
    )

    assert result is not None
    assert result["track_id"] == 1


def test_invalid_box_is_rejected():
    detector = FallDetector()

    with pytest.raises(ValueError):
        detector.evaluate(
            track_id=1,
            box=[100, 100, 50, 200],
        )


def test_reset_track_allows_new_alert():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    )

    first = detector.evaluate(
        track_id=1,
        box=[405, 405, 705, 505],
    )

    assert first is not None

    detector.reset_track(1)

    detector.evaluate(
        track_id=1,
        box=[410, 410, 710, 510],
    )

    second = detector.evaluate(
        track_id=1,
        box=[415, 415, 715, 515],
    )

    assert second is not None
    assert second["event_type"] == "FALL"


def test_reset_clears_all_tracks():
    detector = FallDetector(
        persistence_frames=2,
        min_horizontal_aspect_ratio=1.5,
    )

    detector.evaluate(
        track_id=1,
        box=[400, 400, 700, 500],
    )

    detector.evaluate(
        track_id=2,
        box=[800, 400, 1100, 500],
    )

    detector.reset()

    first = detector.evaluate(
        track_id=1,
        box=[405, 405, 705, 505],
    )

    second = detector.evaluate(
        track_id=2,
        box=[805, 405, 1105, 505],
    )

    assert first is None
    assert second is None
