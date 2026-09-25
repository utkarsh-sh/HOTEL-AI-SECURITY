from ai.zone_detector import ZoneDetector


def _track():
    return {
        "track_id": 1,
        "box": [10, 10, 30, 30],
    }


def _zones():
    return [
        {
            "zone_id": "zone-a",
            "camera_id": "cam-a",
            "name": "Zone A",
            "type": "restricted",
            "points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        },
        {
            "zone_id": "zone-b",
            "camera_id": "cam-b",
            "name": "Zone B",
            "type": "restricted",
            "points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        },
    ]


def test_check_track_filters_to_requested_camera():
    detector = ZoneDetector(_zones())

    results = detector.check_track(_track(), camera_id="cam-a")

    assert [result["zone_id"] for result in results] == ["zone-a"]
    assert results[0]["camera_id"] == "cam-a"


def test_check_tracks_filters_to_requested_camera():
    detector = ZoneDetector(_zones())

    results = detector.check_tracks([_track()], camera_id="cam-b")

    assert [result["zone_id"] for result in results] == ["zone-b"]


def test_check_track_without_camera_id_preserves_all_zones():
    detector = ZoneDetector(_zones())

    results = detector.check_track(_track())

    assert {result["zone_id"] for result in results} == {"zone-a", "zone-b"}


def test_zone_without_camera_id_is_not_returned_for_scoped_check():
    zones = [
        {
            "zone_id": "legacy-zone",
            "name": "Legacy Zone",
            "type": "restricted",
            "points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        }
    ]
    detector = ZoneDetector(zones)

    results = detector.check_track(_track(), camera_id="cam-a")

    assert results == []
