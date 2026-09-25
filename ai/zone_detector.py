from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


class ZoneDetector:
    """Determines whether tracked persons are inside configured polygon zones."""

    def __init__(self, zones: List[Dict]):
        self.zones = zones

    @staticmethod
    def _person_point(box: List[int]) -> Tuple[int, int]:
        x1, y1, x2, y2 = box
        center_x = int((x1 + x2) / 2)
        bottom_y = int(y2)
        return center_x, bottom_y

    def check_track(
        self,
        track: Dict,
        camera_id: Optional[str] = None,
    ) -> List[Dict]:
        results = []
        point = self._person_point(track["box"])

        for zone in self.zones:
            zone_camera_id = zone.get("camera_id")
            if camera_id is not None and zone_camera_id != camera_id:
                continue

            polygon = np.array(
                zone["points"],
                dtype=np.int32,
            )
            inside = cv2.pointPolygonTest(
                polygon,
                point,
                False,
            )
            results.append(
                {
                    "zone_id": zone["zone_id"],
                    "zone_name": zone["name"],
                    "camera_id": zone_camera_id,
                    "track_id": track["track_id"],
                    "inside": inside >= 0,
                    "point": point,
                }
            )

        return results

    def check_tracks(
        self,
        tracks: List[Dict],
        camera_id: Optional[str] = None,
    ) -> List[Dict]:
        results = []
        for track in tracks:
            results.extend(
                self.check_track(
                    track,
                    camera_id=camera_id,
                )
            )
        return results
