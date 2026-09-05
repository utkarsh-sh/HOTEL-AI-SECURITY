import json

from ai.zone_detector import ZoneDetector
from rules.intrusion_rules import IntrusionRule


def load_zones():

    with open(
        "configs/zones.json",
        "r",
        encoding="utf-8",
    ) as file:

        config = json.load(file)

    return config["zones"]


def main():

    zones = load_zones()

    zone_detector = ZoneDetector(
        zones
    )

    rule = IntrusionRule(
        persistence_frames=3
    )

    # Simulated person inside zone
    track = {
        "track_id": 1,
        "box": [
            1400,
            500,
            1550,
            900,
        ],
    }

    print("=" * 60)
    print("HOTEL AI CCTV - ZONE TEST")
    print("=" * 60)

    for frame in range(1, 6):

        zone_results = (
            zone_detector.check_tracks(
                [track]
            )
        )

        events = rule.evaluate(
            zone_results
        )

        print(
            f"Frame {frame}: "
            f"inside={zone_results[0]['inside']}"
        )

        if events:

            for event in events:

                print(
                    f"🚨 EVENT: "
                    f"{event['message']}"
                )

    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()