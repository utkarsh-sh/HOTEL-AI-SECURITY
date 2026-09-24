from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class WeaponDetection:
    """Model-independent weapon detection contract."""

    class_name: str
    confidence: float
    box: list[float]


class WeaponVisionAdapter:
    """
    Adapter around the selected RF-DETR threat-detection checkpoint.

    The adapter deliberately exposes only the detection contract needed by
    the Hotel AI Security event pipeline. RF-DETR/supervision remain behind
    this boundary so the model can be replaced later without changing event
    processing.
    """

    MODEL_NAME = "Subh775/Threat-Detection-RFDETR"
    MODEL_REVISION = "main"
    INPUT_SIZE = 640

    # Class IDs documented by the selected model card.
    CLASS_NAMES = {
        1: "gun",
        4: "knife",
    }

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.50,
        model_factory: Any | None = None,
    ) -> None:
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Weapon model not found: {self.model_path}"
            )

        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be between 0 and 1"
            )

        self.confidence_threshold = confidence_threshold

        if model_factory is None:
            try:
                from rfdetr import RFDETRNano
            except ImportError as exc:
                raise RuntimeError(
                    "RF-DETR is required for weapon detection. "
                    "Install the pinned project dependency before "
                    "creating WeaponVisionAdapter."
                ) from exc

            model_factory = RFDETRNano

        self.model = model_factory(
            resolution=self.INPUT_SIZE,
            pretrain_weights=str(self.model_path),
        )

        optimize = getattr(
            self.model,
            "optimize_for_inference",
            None,
        )

        if callable(optimize):
            optimize()

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> None:
        if frame is None or not isinstance(frame, np.ndarray):
            raise ValueError("frame must be a numpy array")

        if frame.size == 0:
            raise ValueError("frame must not be empty")

        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(
                f"Expected BGR frame with shape HxWx3, got {frame.shape}"
            )

    @staticmethod
    def _as_detection_array(value: Any) -> np.ndarray:
        if value is None:
            return np.asarray([])

        array = np.asarray(value)

        if array.ndim == 0:
            array = array.reshape(1)

        return array.reshape(-1)

    def _decode(
        self,
        predictions: Any,
        frame_width: int,
        frame_height: int,
    ) -> list[dict[str, Any]]:
        class_ids = self._as_detection_array(
            getattr(predictions, "class_id", None)
        )
        confidences = self._as_detection_array(
            getattr(predictions, "confidence", None)
        )
        boxes = np.asarray(
            getattr(predictions, "xyxy", None)
        )

        if boxes.size == 0:
            return []

        if boxes.ndim != 2 or boxes.shape[1] != 4:
            raise RuntimeError(
                f"Expected xyxy boxes with shape Nx4, got {boxes.shape}"
            )

        if not (
            len(class_ids)
            == len(confidences)
            == len(boxes)
        ):
            raise RuntimeError(
                "RF-DETR prediction arrays have inconsistent lengths: "
                f"class_id={len(class_ids)}, "
                f"confidence={len(confidences)}, "
                f"boxes={len(boxes)}"
            )

        detections: list[dict[str, Any]] = []

        for class_id, confidence, box in zip(
            class_ids,
            confidences,
            boxes,
        ):
            try:
                class_id_int = int(class_id)
                confidence_float = float(confidence)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    "RF-DETR returned a non-numeric class ID or confidence."
                ) from exc

            class_name = self.CLASS_NAMES.get(class_id_int)

            # The MVP intentionally ignores Explosive and Grenade classes.
            if class_name is None:
                continue

            if not np.isfinite(confidence_float):
                continue

            if confidence_float < self.confidence_threshold:
                continue

            coordinates = [
                float(value)
                for value in box
            ]

            if not all(np.isfinite(value) for value in coordinates):
                continue

            x1, y1, x2, y2 = coordinates

            x1 = max(0.0, min(float(frame_width), x1))
            y1 = max(0.0, min(float(frame_height), y1))
            x2 = max(0.0, min(float(frame_width), x2))
            y2 = max(0.0, min(float(frame_height), y2))

            if x2 <= x1 or y2 <= y1:
                continue

            detections.append(
                {
                    "class_name": class_name,
                    "confidence": confidence_float,
                    "box": [x1, y1, x2, y2],
                }
            )

        detections.sort(
            key=lambda detection: detection["confidence"],
            reverse=True,
        )

        return detections

    def detect(
        self,
        frame: np.ndarray,
    ) -> list[dict[str, Any]]:
        self._validate_frame(frame)

        frame_height, frame_width = frame.shape[:2]

        # RF-DETR accepts PIL images. The project video pipeline supplies
        # OpenCV BGR frames, so convert explicitly at the model boundary.
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)

        predictions = self.model.predict(
            image,
            threshold=self.confidence_threshold,
        )

        return self._decode(
            predictions,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    def close(self) -> None:
        """Release the model reference when the camera worker shuts down."""
        self.model = None
