from types import SimpleNamespace

import numpy as np
import pytest

from ai.weapon_vision_adapter import (
    WEAPON_CLASS_NAMES,
    WEAPON_MODEL_SHA256,
    WeaponVisionAdapter,
)


class FakeSession:
    def __init__(self, output):
        self.output = np.asarray(output, dtype=np.float32)
        self.last_input = None

    def get_inputs(self):
        return [
            SimpleNamespace(
                name="images",
                shape=[1, 3, 640, 640],
            )
        ]

    def get_outputs(self):
        return [
            SimpleNamespace(
                name="output0",
                shape=[1, 300, 6],
            )
        ]

    def get_providers(self):
        return [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]

    def get_modelmeta(self):
        return SimpleNamespace(
            custom_metadata_map={
                "names": "{0: 'gun', 1: 'knife'}"
            }
        )

    def run(self, _, feeds):
        self.last_input = feeds["images"].copy()
        return [self.output.copy()]


def make_output(rows=None):
    output = np.zeros(
        (1, 300, 6),
        dtype=np.float32,
    )
    if rows:
        for index, row in enumerate(rows):
            output[0, index] = row
    return output


def make_adapter(tmp_path, output, **kwargs):
    path = tmp_path / "best.onnx"
    path.write_bytes(b"model")
    session = FakeSession(output)
    adapter = WeaponVisionAdapter(
        path,
        expected_sha256=None,
        session=session,
        **kwargs,
    )
    return adapter, session


def test_hash_mismatch_rejected(tmp_path):
    path = tmp_path / "best.onnx"
    path.write_bytes(b"model")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        WeaponVisionAdapter(
            path,
            expected_sha256=WEAPON_MODEL_SHA256,
            session=FakeSession(make_output()),
        )


def test_class_contract():
    assert WEAPON_CLASS_NAMES == {0: "gun", 1: "knife"}


def test_detects_gun_and_knife_and_filters_low_confidence(tmp_path):
    output = make_output([
        [100, 180, 220, 280, 0.80, 0],
        [300, 200, 400, 300, 0.70, 1],
        [400, 200, 500, 300, 0.40, 0],
        [100, 100, 200, 200, 0.95, 7],
    ])
    adapter, _ = make_adapter(
        tmp_path,
        output,
        confidence_threshold=0.50,
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = adapter.detect(frame)
    assert [item["class_name"] for item in detections] == ["gun", "knife"]
    assert detections[0]["confidence"] == pytest.approx(0.80, abs=1e-6)
    assert detections[0]["box"] == pytest.approx(
        [100.0, 100.0, 220.0, 200.0],
        abs=1.0,
    )


def test_converts_bgr_to_rgb_and_normalizes(tmp_path):
    adapter, session = make_adapter(
        tmp_path,
        make_output(),
    )
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    frame[:, :] = [10, 20, 30]
    adapter.detect(frame)
    tensor = session.last_input
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor[0, 0, 0, 0] == pytest.approx(30 / 255, abs=1e-6)
    assert tensor[0, 1, 0, 0] == pytest.approx(20 / 255, abs=1e-6)
    assert tensor[0, 2, 0, 0] == pytest.approx(10 / 255, abs=1e-6)


def test_invalid_frame_rejected(tmp_path):
    adapter, _ = make_adapter(tmp_path, make_output())
    with pytest.raises(ValueError):
        adapter.detect(None)
    with pytest.raises(ValueError):
        adapter.detect(np.zeros((10, 10), dtype=np.uint8))


def test_unexpected_output_shape_rejected(tmp_path):
    path = tmp_path / "best.onnx"
    path.write_bytes(b"model")

    class BadSession(FakeSession):
        def get_outputs(self):
            return [SimpleNamespace(name="output0", shape=[1, 10, 7])]

    with pytest.raises(RuntimeError, match="Unexpected weapon model output shape"):
        WeaponVisionAdapter(
            path,
            expected_sha256=None,
            session=BadSession(np.zeros((1, 10, 7), dtype=np.float32)),
        )


def test_execution_providers_are_exposed(tmp_path):
    adapter, _ = make_adapter(tmp_path, make_output())
    assert adapter.execution_providers == [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
