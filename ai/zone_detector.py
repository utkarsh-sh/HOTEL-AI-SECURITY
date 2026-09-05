from typing import List, Dict, Tuple

import cv2
import numpy as np


class ZoneDetector:
    """
    Determines whether tracked persons are inside
    configured polygon zones.
    """

    def __init__(self, zones: List[Dict]):
        self.zones = zones

    @staticmethod
    def _person_point(box: List[int]) -> Tuple[int, int]:
        """
        Use the bottom-center of the person's bounding box.

        This approximates the person's position on the floor.
        """

        x1, y1, x2, y2 = box

        center_x = int((x1 + x2) / 2)
        bottom_y = int(y2)

        return center_x, bottom_y

    def check_track(self, track: Dict) -> List[Dict]:
        """
        Check one tracked person against all zones.
        """

        results = []

        point = self._person_point(track["box"])

        for zone in self.zones:

            polygon = np.array(
                zone["points"],
                dtype=np.int32,
            )

            inside = cv2.pointPolygonTest(
                polygon,
                point,
                False,
            )

            is_inside = inside >= 0

            results.append(
                {
                    "zone_id": zone["zone_id"],
                    "zone_name": zone["name"],
                    "track_id": track["track_id"],
                    "inside": is_inside,
                    "point": point,
                }
            )

        return results

    def check_tracks(
        self,
        tracks: List[Dict],
    ) -> List[Dict]:

        results = []

        for track in tracks:

            results.extend(
                self.check_track(track)
            )

        return results