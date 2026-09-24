from typing import Dict, List, Optional, Tuple


class FireSmokeDetector:
    """
    Temporal event detector for fire/smoke model observations.

    This class does not perform visual inference itself. It consumes
    detections produced by a fire/smoke model and converts persistent
    observations into security events.

    It is an AI-assisted security signal and is not a certified
    fire-alarm or life-safety system.
    """

    VALID_CLASSES = {"fire", "smoke"}

    def __init__(
        self,
        persistence_frames: int = 3,
        min_confidence: float = 0.50,
        region_tolerance: float = 75.0,
    ) -> None:
        if not isinstance(persistence_frames, int):
            raise ValueError(
                "persistence_frames must be an integer"
            )

        if persistence_frames <= 0:
            raise ValueError(
                "persistence_frames must be > 0"
            )

        if not isinstance(
            min_confidence,
            (int, float),
        ):
            raise ValueError(
                "min_confidence must be a number"
            )

        if not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError(
                "min_confidence must be between 0 and 1"
            )

        if not isinstance(
            region_tolerance,
            (int, float),
        ):
            raise ValueError(
                "region_tolerance must be a number"
            )

        if region_tolerance < 0:
            raise ValueError(
                "region_tolerance must be >= 0"
            )

        self.persistence_frames = persistence_frames
        self.min_confidence = float(min_confidence)
        self.region_tolerance = float(region_tolerance)

        self._states: Dict[
            Tuple[str, int],
            Dict[str, object],
        ] = {}

        self._alerted_regions: set[
            Tuple[str, int]
        ] = set()

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_detection(
        self,
        detection: Dict,
    ) -> None:
        if not isinstance(detection, dict):
            raise ValueError(
                "each detection must be a dictionary"
            )

        if "class_name" not in detection:
            raise ValueError(
                "detection missing class_name"
            )

        if "confidence" not in detection:
            raise ValueError(
                "detection missing confidence"
            )

        if "box" not in detection:
            raise ValueError(
                "detection missing box"
            )

        class_name = detection["class_name"]

        if not isinstance(class_name, str):
            raise ValueError(
                "class_name must be a string"
            )

        class_name = class_name.lower().strip()

        if class_name not in self.VALID_CLASSES:
            raise ValueError(
                f"unsupported fire/smoke class: {class_name}"
            )

        confidence = detection["confidence"]

        if not isinstance(
            confidence,
            (int, float),
        ):
            raise ValueError(
                "confidence must be a number"
            )

        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError(
                "confidence must be between 0 and 1"
            )

        self._validate_box(
            detection["box"]
        )

    def _validate_box(
        self,
        box: List[float],
    ) -> None:
        if not isinstance(
            box,
            (list, tuple),
        ):
            raise ValueError(
                "box must be a list or tuple"
            )

        if len(box) != 4:
            raise ValueError(
                "box must contain four coordinates"
            )

        if not all(
            isinstance(value, (int, float))
            for value in box
        ):
            raise ValueError(
                "box coordinates must be numeric"
            )

        x1, y1, x2, y2 = box

        if x2 <= x1:
            raise ValueError(
                "box x2 must be greater than x1"
            )

        if y2 <= y1:
            raise ValueError(
                "box y2 must be greater than y1"
            )

    # ==========================================================
    # REGION MATCHING
    # ==========================================================

    def _center(
        self,
        box: List[float],
    ) -> Tuple[float, float]:
        x1, y1, x2, y2 = box

        return (
            (float(x1) + float(x2)) / 2.0,
            (float(y1) + float(y2)) / 2.0,
        )

    def _find_region_key(
        self,
        class_name: str,
        box: List[float],
    ) -> Optional[Tuple[str, int]]:
        center_x, center_y = self._center(box)

        for key, state in self._states.items():
            state_class = state["class_name"]
            state_center = state["center"]

            if state_class != class_name:
                continue

            previous_x, previous_y = state_center

            distance = (
                (center_x - previous_x) ** 2
                + (center_y - previous_y) ** 2
            ) ** 0.5

            if distance <= self.region_tolerance:
                return key

        return None

    # ==========================================================
    # DETECTION
    # ==========================================================

    def evaluate(
        self,
        detections: List[Dict],
    ) -> List[Dict]:
        """
        Evaluate model detections for one AI frame.

        A FIRE or SMOKE event is returned only after the same
        detection region persists for the configured number of
        consecutive evaluations.
        """

        if not isinstance(
            detections,
            list,
        ):
            raise ValueError(
                "detections must be a list"
            )

        current_keys: set[
            Tuple[str, int]
        ] = set()

        events: List[Dict] = []

        for detection in detections:
            self._validate_detection(
                detection
            )

            class_name = (
                detection["class_name"]
                .lower()
                .strip()
            )

            confidence = float(
                detection["confidence"]
            )

            if confidence < self.min_confidence:
                continue

            box = detection["box"]

            region_key = self._find_region_key(
                class_name,
                box,
            )

            if region_key is None:
                region_id = (
                    max(
                        [
                            key[1]
                            for key in self._states
                            if key[0] == class_name
                        ],
                        default=0,
                    )
                    + 1
                )

                region_key = (
                    class_name,
                    region_id,
                )

                self._states[region_key] = {
                    "class_name": class_name,
                    "center": self._center(box),
                    "count": 0,
                    "last_box": list(box),
                }

            state = self._states[region_key]

            state["center"] = self._center(box)
            state["last_box"] = list(box)
            state["count"] = int(
                state["count"]
            ) + 1

            current_keys.add(
                region_key
            )

            if (
                int(state["count"])
                >= self.persistence_frames
                and region_key
                not in self._alerted_regions
            ):
                self._alerted_regions.add(
                    region_key
                )

                if class_name == "fire":
                    event_type = "FIRE"
                    severity = "CRITICAL"
                    message = (
                        "Potential fire detected "
                        "by CCTV analysis"
                    )
                else:
                    event_type = "SMOKE"
                    severity = "HIGH"
                    message = (
                        "Potential smoke detected "
                        "by CCTV analysis"
                    )

                events.append(
                    {
                        "event_type": event_type,
                        "severity": severity,
                        "track_id": None,
                        "message": message,
                    }
                )

        # ------------------------------------------------------
        # Reset regions that disappeared from the current frame.
        # ------------------------------------------------------

        disappeared = (
            set(self._states)
            - current_keys
        )

        for region_key in disappeared:
            self._states.pop(
                region_key,
                None,
            )

            self._alerted_regions.discard(
                region_key
            )

        return events

    # ==========================================================
    # RESET
    # ==========================================================

    def reset_region(
        self,
        class_name: str,
        region_id: int,
    ) -> None:
        if not isinstance(
            class_name,
            str,
        ):
            raise ValueError(
                "class_name must be a string"
            )

        if not isinstance(
            region_id,
            int,
        ):
            raise ValueError(
                "region_id must be an integer"
            )

        key = (
            class_name.lower().strip(),
            region_id,
        )

        self._states.pop(
            key,
            None,
        )

        self._alerted_regions.discard(
            key
        )

    def reset(self) -> None:
        self._states.clear()
        self._alerted_regions.clear()
