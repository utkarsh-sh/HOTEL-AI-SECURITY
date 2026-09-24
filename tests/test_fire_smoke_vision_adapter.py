
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from ai.fire_smoke_vision_adapter import FireSmokeVisionAdapter


MODEL_PATH = Path(
    "data/models/fire_smoke/cctv_yolov8n/best.onnx"
)


class FakeInput:
    name = "images"
    shape = [1, 3, 320, 320]


class FakeOutput:
    name = "output0"


class FakeSession:
    def __init__(self, *args, **kwargs):
        self._providers = [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]

    def get_providers(self):
        return self._providers

    def get_inputs(self):
        return [FakeInput()]

    def get_outputs(self):
        return [FakeOutput()]

    def run(self, output_names, inputs):
        # One fire detection and one below-threshold smoke detection.
        output = np.array(
            [
                [
                    160.0,
                    160.0,
                    100.0,
                    80.0,
                    0.80,
                    0.10,
                ],
                [
                    200.0,
                    100.0,
                    50.0,
                    40.0,
                    0.20,
                    0.40,
                ],
            ],
            dtype=np.float32,
        ).T

        return [output[None, ...]]


def test_adapter_requires_model():
    with pytest.raises(FileNotFoundError):
        FireSmokeVisionAdapter(
            "data/models/fire_smoke/does_not_exist.onnx"
        )


def test_adapter_rejects_invalid_threshold(tmp_path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"fake")

    with patch(
        "ai.fire_smoke_vision_adapter.ort.InferenceSession",
        FakeSession,
    ):
        with pytest.raises(ValueError):
            FireSmokeVisionAdapter(
                model,
                confidence_threshold=1.5,
            )


def test_adapter_decodes_fire_detection(tmp_path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"fake")

    with patch(
        "ai.fire_smoke_vision_adapter.ort.InferenceSession",
        FakeSession,
    ):
        adapter = FireSmokeVisionAdapter(
            model,
            confidence_threshold=0.50,
        )

        frame = np.zeros(
            (480, 640, 3),
            dtype=np.uint8,
        )

        detections = adapter.detect(frame)

    assert adapter.provider == "CUDAExecutionProvider"
    assert len(detections) == 1

    detection = detections[0]

    assert detection["class_name"] == "fire"
    assert detection["confidence"] == pytest.approx(0.80)
    assert len(detection["box"]) == 4

    assert detection["box"][0] >= 0
    assert detection["box"][1] >= 0
    assert detection["box"][2] <= 640
    assert detection["box"][3] <= 480


def test_adapter_rejects_invalid_frame(tmp_path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"fake")

    with patch(
        "ai.fire_smoke_vision_adapter.ort.InferenceSession",
        FakeSession,
    ):
        adapter = FireSmokeVisionAdapter(model)

        with pytest.raises(ValueError):
            adapter.detect(None)


def test_adapter_rejects_non_three_channel_frame(tmp_path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"fake")

    with patch(
        "ai.fire_smoke_vision_adapter.ort.InferenceSession",
        FakeSession,
    ):
        adapter = FireSmokeVisionAdapter(model)

        frame = np.zeros(
            (480, 640),
            dtype=np.uint8,
        )

        with pytest.raises(ValueError):
            adapter.detect(frame)


def test_real_model_loads():
    if not MODEL_PATH.exists():
        pytest.skip("Benchmarked fire/smoke model is not present.")

    adapter = FireSmokeVisionAdapter(
        MODEL_PATH,
        confidence_threshold=0.50,
    )

    assert adapter.input_width == 320
    assert adapter.input_height == 320
    assert adapter.provider in {
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    }
