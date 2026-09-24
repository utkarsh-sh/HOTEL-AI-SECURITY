
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort


@dataclass(frozen=True)
class FireSmokeDetection:
    class_name: str
    confidence: float
    box: list[float]


class FireSmokeVisionAdapter:
    """
    Adapter around the currently benchmarked ONNX fire/smoke detector.

    The adapter intentionally exposes a model-independent detection contract
    so the underlying detector can be replaced later without changing the
    event pipeline.
    """

    CLASS_NAMES = {
        0: "fire",
        1: "smoke",
    }

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.50,
        providers: list[str] | None = None,
    ) -> None:
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Fire/smoke model not found: {self.model_path}"
            )

        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")

        self.confidence_threshold = confidence_threshold

        # When PyTorch is installed, preload its compatible CUDA/cuDNN
        # DLLs before ONNX Runtime creates the inference session.
        # This prevents Windows DLL resolution from silently forcing
        # inference onto CPU.
        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception:
                # Provider creation below remains authoritative.
                pass

        if providers is None:
            available = ort.get_available_providers()
            preferred = [
                provider
                for provider in (
                    "CUDAExecutionProvider",
                    "CPUExecutionProvider",
                )
                if provider in available
            ]

            if not preferred:
                raise RuntimeError(
                    "No supported ONNX Runtime execution provider is available."
                )

            providers = preferred

        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=providers,
        )

        self.active_providers = self.session.get_providers()

        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()

        if len(inputs) != 1:
            raise RuntimeError(
                f"Expected exactly one model input, found {len(inputs)}."
            )

        if len(outputs) != 1:
            raise RuntimeError(
                f"Expected exactly one model output, found {len(outputs)}."
            )

        self.input_name = inputs[0].name
        self.output_name = outputs[0].name

        shape = inputs[0].shape

        if len(shape) != 4:
            raise RuntimeError(
                f"Expected NCHW input, received shape {shape}."
            )

        self.input_height = self._resolve_dimension(shape[2], 320)
        self.input_width = self._resolve_dimension(shape[3], 320)

    @staticmethod
    def _resolve_dimension(value: Any, fallback: int) -> int:
        if isinstance(value, int) and value > 0:
            return value

        return fallback

    @property
    def provider(self) -> str:
        if self.active_providers:
            return self.active_providers[0]

        return "UNKNOWN"

    def _preprocess(
        self,
        frame: np.ndarray,
    ) -> np.ndarray:
        if frame is None or not isinstance(frame, np.ndarray):
            raise ValueError("frame must be a numpy array")

        if frame.size == 0:
            raise ValueError("frame must not be empty")

        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(
                f"Expected BGR frame with shape HxWx3, got {frame.shape}"
            )

        resized = cv2.resize(
            frame,
            (self.input_width, self.input_height),
            interpolation=cv2.INTER_LINEAR,
        )

        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        tensor = rgb.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)

        return np.ascontiguousarray(tensor, dtype=np.float32)

    def _decode(
        self,
        raw_output: np.ndarray,
        original_width: int,
        original_height: int,
    ) -> list[dict[str, Any]]:
        output = np.asarray(raw_output)

        if output.ndim == 3 and output.shape[0] == 1:
            output = output[0]

        if output.ndim != 2:
            raise RuntimeError(
                f"Unexpected fire/smoke output shape: {output.shape}"
            )

        # Current benchmarked model produces [1, 6, 2100].
        # After removing batch dimension this is [6, 2100].
        if output.shape[0] == 6:
            output = output.T

        # Also accept [2100, 6].
        if output.shape[1] != 6:
            raise RuntimeError(
                f"Expected six values per detection, got {output.shape}"
            )

        scale_x = original_width / float(self.input_width)
        scale_y = original_height / float(self.input_height)

        candidates: list[dict[str, Any]] = []

        for row in output:
            cx, cy, width, height, fire_score, smoke_score = (
                float(value) for value in row
            )

            class_scores = {
                0: fire_score,
                1: smoke_score,
            }

            class_id = max(
                class_scores,
                key=class_scores.get,
            )

            confidence = class_scores[class_id]

            if not np.isfinite(confidence):
                continue

            if confidence < self.confidence_threshold:
                continue

            if not all(
                np.isfinite(value)
                for value in (cx, cy, width, height)
            ):
                continue

            x1 = (cx - width / 2.0) * scale_x
            y1 = (cy - height / 2.0) * scale_y
            x2 = (cx + width / 2.0) * scale_x
            y2 = (cy + height / 2.0) * scale_y

            x1 = max(0.0, min(float(original_width), x1))
            y1 = max(0.0, min(float(original_height), y1))
            x2 = max(0.0, min(float(original_width), x2))
            y2 = max(0.0, min(float(original_height), y2))

            if x2 <= x1 or y2 <= y1:
                continue

            candidates.append(
                {
                    "class_name": self.CLASS_NAMES[class_id],
                    "confidence": confidence,
                    "box": [x1, y1, x2, y2],
                }
            )

        # The current ONNX model exports with NMS disabled.
        # Apply per-class NMS here so overlapping predictions for the
        # same physical fire/smoke region collapse into one detection.
        detections: list[dict[str, Any]] = []

        for class_name in self.CLASS_NAMES.values():
            class_candidates = [
                candidate
                for candidate in candidates
                if candidate["class_name"] == class_name
            ]

            if not class_candidates:
                continue

            boxes = []
            scores = []

            for candidate in class_candidates:
                x1, y1, x2, y2 = candidate["box"]

                boxes.append(
                    [
                        int(round(x1)),
                        int(round(y1)),
                        int(round(x2 - x1)),
                        int(round(y2 - y1)),
                    ]
                )

                scores.append(float(candidate["confidence"]))

            keep = cv2.dnn.NMSBoxes(
                boxes,
                scores,
                self.confidence_threshold,
                0.45,
            )

            if len(keep) == 0:
                continue

            keep_indices = np.asarray(keep).reshape(-1)

            for index in keep_indices:
                detections.append(class_candidates[int(index)])

        detections.sort(
            key=lambda detection: detection["confidence"],
            reverse=True,
        )

        return detections

    def detect(
        self,
        frame: np.ndarray,
    ) -> list[dict[str, Any]]:
        # Validate the frame before accessing shape so invalid inputs
        # consistently raise ValueError instead of AttributeError.
        if frame is None or not isinstance(frame, np.ndarray):
            raise ValueError("frame must be a numpy array")

        if frame.size == 0:
            raise ValueError("frame must not be empty")

        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(
                f"Expected BGR frame with shape HxWx3, got {frame.shape}"
            )

        original_height, original_width = frame.shape[:2]

        tensor = self._preprocess(frame)

        outputs = self.session.run(
            [self.output_name],
            {
                self.input_name: tensor,
            },
        )

        return self._decode(
            outputs[0],
            original_width=original_width,
            original_height=original_height,
        )

    def close(self) -> None:
        self.session = None
