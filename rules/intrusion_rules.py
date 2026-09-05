from typing import Dict, List


class IntrusionRule:

    def __init__(
        self,
        persistence_frames: int = 3,
    ):
        self.persistence_frames = persistence_frames

        self.zone_presence = {}

    def evaluate(
        self,
        zone_results: List[Dict],
    ) -> List[Dict]:

        events = []

        for result in zone_results:

            zone_id = result["zone_id"]
            track_id = result["track_id"]
            inside = result["inside"]

            key = (
                zone_id,
                track_id,
            )

            if inside:

                current_count = (
                    self.zone_presence.get(
                        key,
                        0,
                    )
                )

                current_count += 1

                self.zone_presence[key] = (
                    current_count
                )

                if (
                    current_count
                    == self.persistence_frames
                ):

                    events.append(
                        {
                            "event_type": "INTRUSION",
                            "severity": "HIGH",
                            "zone_id": zone_id,
                            "zone_name": result[
                                "zone_name"
                            ],
                            "track_id": track_id,
                            "message": (
                                f"Person {track_id} "
                                f"entered "
                                f"{result['zone_name']}"
                            ),
                        }
                    )

            else:

                self.zone_presence.pop(
                    key,
                    None,
                )

        return events