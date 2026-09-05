from dataclasses import dataclass, field
from typing import List, Dict
import math

import cv2
import numpy as np


@dataclass
class Track:
    track_id: int
    box: List[int]
    confidence: float

    age: int = 1
    missed: int = 0

    total_matches: int = 1
    total_misses: int = 0
    recovery_count: int = 0

    state: str = "TRACKED"

    history: List[List[int]] = field(default_factory=list)

    def __post_init__(self):
        self.kalman = cv2.KalmanFilter(4, 2)

        # State:
        # [center_x, center_y, velocity_x, velocity_y]

        self.kalman.transitionMatrix = np.array(
            [
                [1, 0, 1, 0],
                [0, 1, 0, 1],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ],
            dtype=np.float32,
        )

        self.kalman.measurementMatrix = np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
            ],
            dtype=np.float32,
        )

        self.kalman.processNoiseCov = (
            np.eye(4, dtype=np.float32) * 0.03
        )

        self.kalman.measurementNoiseCov = (
            np.eye(2, dtype=np.float32) * 0.5
        )

        self.kalman.errorCovPost = (
            np.eye(4, dtype=np.float32)
        )

        cx, cy = self._center(self.box)

        self.kalman.statePost = np.array(
            [
                [cx],
                [cy],
                [0],
                [0],
            ],
            dtype=np.float32,
        )

        self.predicted_center = (cx, cy)

        self.history.append(self.box)

    @staticmethod
    def _center(box):
        x1, y1, x2, y2 = box

        return (
            (x1 + x2) / 2.0,
            (y1 + y2) / 2.0,
        )

    def predict(self):
        prediction = self.kalman.predict()

        self.predicted_center = (
            float(prediction[0, 0]),
            float(prediction[1, 0]),
        )

        return self.predicted_center

    def correct(self, box):
        cx, cy = self._center(box)

        measurement = np.array(
            [
                [cx],
                [cy],
            ],
            dtype=np.float32,
        )

        self.kalman.correct(measurement)

        self.predicted_center = (cx, cy)

    def predicted_box(self):
        """
        Move the current bounding box according to
        the predicted center.

        This allows the track to continue moving even
        when the detector temporarily misses the person.
        """

        old_cx, old_cy = self._center(self.box)

        new_cx, new_cy = self.predicted_center

        dx = new_cx - old_cx
        dy = new_cy - old_cy

        x1, y1, x2, y2 = self.box

        predicted_box = [
            int(x1 + dx),
            int(y1 + dy),
            int(x2 + dx),
            int(y2 + dy),
        ]

        return predicted_box


class PersonTracker:

    def __init__(
        self,
        iou_threshold=0.10,
        max_missed=12,
        max_center_distance=300,
    ):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.max_center_distance = max_center_distance

        self.tracks: List[Track] = []

        self.next_track_id = 1

        self.total_created = 0
        self.total_expired = 0
        self.total_recovered = 0

    @staticmethod
    def _iou(box_a, box_b):

        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        x_left = max(ax1, bx1)
        y_top = max(ay1, by1)

        x_right = min(ax2, bx2)
        y_bottom = min(ay2, by2)

        if x_right <= x_left or y_bottom <= y_top:
            return 0.0

        intersection = (
            (x_right - x_left)
            * (y_bottom - y_top)
        )

        area_a = (
            (ax2 - ax1)
            * (ay2 - ay1)
        )

        area_b = (
            (bx2 - bx1)
            * (by2 - by1)
        )

        union = area_a + area_b - intersection

        if union <= 0:
            return 0.0

        return intersection / union

    @staticmethod
    def _center(box):

        x1, y1, x2, y2 = box

        return (
            (x1 + x2) / 2.0,
            (y1 + y2) / 2.0,
        )

    @staticmethod
    def _distance(point_a, point_b):

        return math.sqrt(
            (point_a[0] - point_b[0]) ** 2
            + (point_a[1] - point_b[1]) ** 2
        )

    def _create_track(self, detection):

        track = Track(
            track_id=self.next_track_id,
            box=detection["box"],
            confidence=detection["confidence"],
        )

        self.tracks.append(track)

        self.next_track_id += 1
        self.total_created += 1

        print(
            f"[TRACK CREATED] "
            f"ID={track.track_id} "
            f"box={track.box}"
        )

    def update(self, detections: List[Dict]):

        # --------------------------------------------------
        # 1. No existing tracks
        # --------------------------------------------------

        if not self.tracks:

            for detection in detections:
                self._create_track(detection)

            return self._export_tracks()

        # --------------------------------------------------
        # 2. Predict all existing tracks
        # --------------------------------------------------

        for track in self.tracks:
            track.predict()

        # --------------------------------------------------
        # 3. Build possible associations
        # --------------------------------------------------

        possible_matches = []

        for track_index, track in enumerate(self.tracks):

            predicted_box = track.predicted_box()

            for detection_index, detection in enumerate(
                detections
            ):

                detection_box = detection["box"]

                iou_score = self._iou(
                    predicted_box,
                    detection_box,
                )

                predicted_center = self._center(
                    predicted_box
                )

                detection_center = self._center(
                    detection_box
                )

                center_distance = self._distance(
                    predicted_center,
                    detection_center,
                )

                if (
                    iou_score >= self.iou_threshold
                    or center_distance
                    <= self.max_center_distance
                ):

                    distance_score = max(
                        0.0,
                        1.0
                        - (
                            center_distance
                            / self.max_center_distance
                        ),
                    )

                    combined_score = (
                        0.65 * iou_score
                        + 0.35 * distance_score
                    )

                    possible_matches.append(
                        (
                            combined_score,
                            track_index,
                            detection_index,
                            iou_score,
                            center_distance,
                        )
                    )

        # Best matches first
        possible_matches.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        unmatched_tracks = set(
            range(len(self.tracks))
        )

        unmatched_detections = set(
            range(len(detections))
        )

        # --------------------------------------------------
        # 4. Associate detections with tracks
        # --------------------------------------------------

        for (
            score,
            track_index,
            detection_index,
            iou_score,
            center_distance,
        ) in possible_matches:

            if track_index not in unmatched_tracks:
                continue

            if detection_index not in unmatched_detections:
                continue

            track = self.tracks[track_index]

            detection = detections[
                detection_index
            ]

            was_missed = track.missed > 0

            # Update track
            track.box = detection["box"]
            track.confidence = detection[
                "confidence"
            ]

            track.age += 1
            track.total_matches += 1

            track.missed = 0

            track.correct(
                detection["box"]
            )

            track.history.append(
                detection["box"]
            )

            if was_missed:

                track.state = "RECOVERED"

                track.recovery_count += 1

                self.total_recovered += 1

                print(
                    f"[TRACK RECOVERED] "
                    f"ID={track.track_id} "
                    f"recovery={track.recovery_count}"
                )

            else:

                track.state = "TRACKED"

            unmatched_tracks.remove(
                track_index
            )

            unmatched_detections.remove(
                detection_index
            )

        # --------------------------------------------------
        # 5. Handle missed tracks
        # --------------------------------------------------

        for track_index in unmatched_tracks:

            track = self.tracks[
                track_index
            ]

            track.age += 1

            track.missed += 1
            track.total_misses += 1

            # Move box according to Kalman prediction
            track.box = track.predicted_box()

            track.state = "MISSED"

            if track.missed == 1:

                print(
                    f"[TRACK MISSED] "
                    f"ID={track.track_id}"
                )

        # --------------------------------------------------
        # 6. Create tracks for unmatched detections
        # --------------------------------------------------

        for detection_index in unmatched_detections:

            self._create_track(
                detections[detection_index]
            )

        # --------------------------------------------------
        # 7. Remove expired tracks
        # --------------------------------------------------

        active_tracks = []

        for track in self.tracks:

            if track.missed > self.max_missed:

                self.total_expired += 1

                track.state = "EXPIRED"

                print(
                    f"[TRACK EXPIRED] "
                    f"ID={track.track_id} "
                    f"age={track.age} "
                    f"missed={track.missed}"
                )

            else:

                active_tracks.append(track)

        self.tracks = active_tracks

        return self._export_tracks()

    def _export_tracks(self):

        return [

            {
                "track_id": track.track_id,
                "box": track.box,
                "confidence": track.confidence,
                "age": track.age,
                "missed": track.missed,
                "state": track.state,
                "matches": track.total_matches,
                "misses": track.total_misses,
                "recoveries": track.recovery_count,
            }

            for track in self.tracks
        ]