from __future__ import annotations

import ast
import math
import threading
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Sequence

import cv2
import numpy as np


WEAPON_MODEL_SHA256 = (
    "BA7466E4036DB5AA86189A59125A42C0E64DE254E9D89429C09082F45D99EC6D"
)
WEAPON_MODEL_VERSION = "weapon-yolo11n-gun-knife-v1"
WEAPON_CLASS_NAMES = {0: "gun", 1: "knife"}


class WeaponVisionAdapter:
    """ONNX Runtime adapter for the validated gun/knife weapon detector."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.50,
        expected_sha256: str | None = WEAPON_MODEL_SHA256,
        session: Any | None = None,
        session_factory: Callable[..., Any] | None = None,
        prefer_cuda: bool = True,
        input_size: int = 640,
    ) -> None:
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Weapon model not found: {self.model_path}"
            )

        if not 0.0 <= float(confidence_threshold) <= 1.0:
            raise ValueError(
                "confidence_threshold must be between 0 and 1"
            )

        if not isinstance(input_size, int) or input_size <= 0:
            raise ValueError("input_size must be a positive integer")

        if session is not None and session_factory is not None:
            raise ValueError(
                "Provide either session or session_factory, not both"
            )

        self.confidence_threshold = float(confidence_threshold)
        self.input_size = input_size

        if expected_sha256 is not None:
            expected = expected_sha256.strip().upper()
            if (
                len(expected) != 64
                or any(c not in "0123456789ABCDEF" for c in expected)
            ):
                raise ValueError(
                    "expected_sha256 must be a 64-character hex digest"
                )

            actual = self._sha256_file()

            if actual != expected:
                raise RuntimeError(
                    "Weapon model SHA-256 mismatch. "
                    f"expected={expected}, actual={actual}"
                )

        if session is not None:
            self._session = session
        else:
            factory = session_factory or self._default_session_factory
            self._session = factory(
                self.model_path,
                prefer_cuda=prefer_cuda,
            )

        # The runner shares one adapter across camera workers. Serialize CUDA session.run() calls because concurrent calls on one ONNX Runtime CUDA session can trigger CUDA error 700.
        self._run_lock = threading.RLock()

        self._input_name = self._validate_session()

        get_providers = getattr(
            self._session,
            "get_providers",
            None,
        )

        if callable(get_providers):
            self.execution_providers = list(get_providers())
        else:
            self.execution_providers = []

        metadata_names = self._parse_model_names(self._session)
        if metadata_names is not None:
            if metadata_names != WEAPON_CLASS_NAMES:
                raise RuntimeError(
                    "Weapon ONNX class mapping mismatch. "
                    f"expected={WEAPON_CLASS_NAMES}, actual={metadata_names}"
                )

    def _default_session_factory(
        self,
        model_path: Path,
        *,
        prefer_cuda: bool,
    ) -> Any:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError(
                "onnxruntime is required for weapon detection"
            ) from exc

        # The current project environment already contains PyTorch CUDA
        # 12.8. ORT can reuse those CUDA/cuDNN DLLs when torch is imported
        # before creating the CUDA session.
        if prefer_cuda and hasattr(ort, "preload_dlls"):
            try:
                import torch  # noqa: F401
                ort.preload_dlls()
            except Exception:
                pass

        available = set(ort.get_available_providers())
        providers: list[str] = []

        if (
            prefer_cuda
            and "CUDAExecutionProvider" in available
        ):
            providers.append("CUDAExecutionProvider")

        providers.append("CPUExecutionProvider")

        return ort.InferenceSession(
            str(model_path),
            providers=providers,
        )

    def _validate_session(self) -> str:
        inputs = list(self._session.get_inputs())

        if len(inputs) != 1:
            raise RuntimeError(
                "Weapon ONNX model must expose exactly one input"
            )

        input_meta = inputs[0]
        shape = list(input_meta.shape)

        if shape != [1, 3, self.input_size, self.input_size]:
            raise RuntimeError(
                "Unexpected weapon model input shape: "
                f"{shape}; expected "
                f"[1, 3, {self.input_size}, {self.input_size}]"
            )

        outputs = list(self._session.get_outputs())

        if len(outputs) != 1:
            raise RuntimeError(
                "Weapon ONNX model must expose exactly one output"
            )

        output_shape = list(outputs[0].shape)

        if (
            len(output_shape) != 3
            or output_shape[0] != 1
            or output_shape[1] != 300
            or output_shape[2] != 6
        ):
            raise RuntimeError(
                "Unexpected weapon model output shape: "
                f"{output_shape}; expected [1, 300, 6]"
            )

        return str(input_meta.name)

    def _sha256_file(self) -> str:
        digest = sha256()

        with self.model_path.open("rb") as stream:
            for chunk in iter(
                lambda: stream.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest().upper()

    @staticmethod
    def _valid_box(box: Sequence[float]) -> bool:
        if len(box) != 4:
            return False

        try:
            x1, y1, x2, y2 = (
                float(value)
                for value in box
            )
        except (TypeError, ValueError):
            return False

        return (
            all(
                math.isfinite(value)
                for value in (x1, y1, x2, y2)
            )
            and x2 > x1
            and y2 > y1
        )

    def _letterbox(
        self,
        frame: np.ndarray,
    ) -> tuple[np.ndarray, float, float, float]:
        height, width = frame.shape[:2]

        scale = min(
            self.input_size / width,
            self.input_size / height,
        )

        resized_width = int(
            round(width * scale)
        )
        resized_height = int(
            round(height * scale)
        )

        resized = cv2.resize(
            frame,
            (resized_width, resized_height),
            interpolation=cv2.INTER_LINEAR,
        )

        pad_x = self.input_size - resized_width
        pad_y = self.input_size - resized_height

        pad_x_half = pad_x / 2.0
        pad_y_half = pad_y / 2.0

        left = int(
            round(pad_x_half - 0.1)
        )
        right = int(
            round(pad_x_half + 0.1)
        )
        top = int(
            round(pad_y_half - 0.1)
        )
        bottom = int(
            round(pad_y_half + 0.1)
        )

        padded = cv2.copyMakeBorder(
            resized,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )

        return (
            padded,
            scale,
            float(left),
            float(top),
        )

    def _preprocess(
        self,
        frame: np.ndarray,
    ) -> tuple[np.ndarray, float, float, float]:
        letterboxed, scale, pad_x, pad_y = self._letterbox(frame)

        rgb = cv2.cvtColor(
            letterboxed,
            cv2.COLOR_BGR2RGB,
        )

        tensor = rgb.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)

        return (
            np.ascontiguousarray(tensor),
            scale,
            pad_x,
            pad_y,
        )

    def _restore_box(
        self,
        box: Sequence[float],
        frame_shape: tuple[int, ...],
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> list[float]:
        height, width = frame_shape[:2]

        x1, y1, x2, y2 = (
            float(value)
            for value in box
        )

        x1 = (x1 - pad_x) / scale
        y1 = (y1 - pad_y) / scale
        x2 = (x2 - pad_x) / scale
        y2 = (y2 - pad_y) / scale

        x1 = min(max(x1, 0.0), float(width))
        x2 = min(max(x2, 0.0), float(width))
        y1 = min(max(y1, 0.0), float(height))
        y2 = min(max(y2, 0.0), float(height))

        return [x1, y1, x2, y2]

    @staticmethod
    def _parse_model_names(session: Any) -> dict[int, str] | None:
        try:
            metadata = session.get_modelmeta()
            raw = getattr(
                metadata,
                "custom_metadata_map",
                {},
            ).get("names")
        except Exception:
            return None

        if not raw:
            return None

        try:
            parsed = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return None

        if not isinstance(parsed, dict):
            return None

        result: dict[int, str] = {}

        for key, value in parsed.items():
            try:
                result[int(key)] = str(value).strip().lower()
            except (TypeError, ValueError):
                continue

        return result or None

    def detect(
        self,
        frame: np.ndarray,
    ) -> list[dict[str, Any]]:
        if frame is None or not isinstance(frame, np.ndarray):
            raise ValueError("frame must be a numpy array")

        if (
            frame.size == 0
            or frame.ndim != 3
            or frame.shape[2] != 3
        ):
            raise ValueError(
                "Expected BGR frame with shape HxWx3, "
                f"got {getattr(frame, 'shape', None)}"
            )

        tensor, scale, pad_x, pad_y = self._preprocess(frame)

        # Serialize ONNX Runtime CUDA inference for the shared
        # multi-camera adapter.
        with self._run_lock:
            if self._session is None:
                raise RuntimeError("WeaponVisionAdapter is closed")

            outputs = self._session.run(
                None,
                {self._input_name: tensor},
            )

        if not outputs:
            raise RuntimeError(
                "Weapon ONNX model returned no outputs"
            )

        detections = np.asarray(outputs[0])

        if detections.ndim == 3:
            detections = detections[0]

        if (
            detections.ndim != 2
            or detections.shape[1] != 6
        ):
            raise RuntimeError(
                "Weapon ONNX model returned unexpected "
                f"runtime output shape: {detections.shape}"
            )

        results: list[dict[str, Any]] = []

        for row in detections:
            confidence = float(row[4])
            class_id_float = float(row[5])

            if (
                not math.isfinite(confidence)
                or not math.isfinite(class_id_float)
            ):
                continue

            class_id = int(round(class_id_float))

            if class_id not in WEAPON_CLASS_NAMES:
                continue

            if confidence < self.confidence_threshold:
                continue

            raw_box = [
                float(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
            ]

            if not self._valid_box(raw_box):
                continue

            box = self._restore_box(
                raw_box,
                frame.shape,
                scale,
                pad_x,
                pad_y,
            )

            if not self._valid_box(box):
                continue

            class_name = WEAPON_CLASS_NAMES[class_id]

            results.append(
                {
                    "class_name": class_name,
                    "model_class_name": class_name,
                    "model_class_id": class_id,
                    "confidence": confidence,
                    "box": box,
                }
            )

        results.sort(
            key=lambda item: item["confidence"],
            reverse=True,
        )

        return results

    def close(self) -> None:
        with self._run_lock:
            self._session = None
