import numpy as np
import pytest

from ai.weapon_vision_adapter import WeaponVisionAdapter


class FakePredictions:
    def __init__(self, class_id, confidence, xyxy):
        self.class_id = np.asarray(class_id)
        self.confidence = np.asarray(confidence)
        self.xyxy = np.asarray(xyxy, dtype=float)


class FakeRFDETR:
    last_instance = None

    def __init__(self, resolution, pretrain_weights):
        self.resolution = resolution
        self.pretrain_weights = pretrain_weights
        self.optimize_calls = 0
        self.predict_calls = []
        FakeRFDETR.last_instance = self

    def optimize_for_inference(self):
        self.optimize_calls += 1

    def predict(self, image, threshold):
        self.predict_calls.append(
            {
                "image": image,
                "threshold": threshold,
            }
        )

        return FakePredictions(
            class_id=[1, 4, 2, 999],
            confidence=[0.95, 0.80, 0.99, 0.99],
            xyxy=[
                [10, 20, 100, 120],
                [200, 100, 300, 300],
                [20, 20, 80, 80],
                [0, 0, 10, 10],
            ],
        )


def test_weapon_adapter_requires_model_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        WeaponVisionAdapter(
            tmp_path / "missing.pth",
            model_factory=FakeRFDETR,
        )


def test_weapon_adapter_rejects_invalid_threshold(tmp_path):
    model_path = tmp_path / "weapon.pth"
    model_path.write_bytes(b"test")

    with pytest.raises(ValueError):
        WeaponVisionAdapter(
            model_path,
            confidence_threshold=1.1,
            model_factory=FakeRFDETR,
        )


def test_weapon_adapter_initializes_selected_model(tmp_path):
    model_path = tmp_path / "weapon.pth"
    model_path.write_bytes(b"test")

    adapter = WeaponVisionAdapter(
        model_path,
        confidence_threshold=0.50,
        model_factory=FakeRFDETR,
    )

    assert FakeRFDETR.last_instance.resolution == 640
    assert (
        FakeRFDETR.last_instance.pretrain_weights
        == str(model_path)
    )
    assert FakeRFDETR.last_instance.optimize_calls == 1

    adapter.close()


def test_weapon_adapter_filters_to_gun_and_knife(tmp_path):
    model_path = tmp_path / "weapon.pth"
    model_path.write_bytes(b"test")

    adapter = WeaponVisionAdapter(
        model_path,
        confidence_threshold=0.50,
        model_factory=FakeRFDETR,
    )

    frame = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )

    detections = adapter.detect(frame)

    assert detections == [
        {
            "class_name": "gun",
            "confidence": 0.95,
            "box": [10.0, 20.0, 100.0, 120.0],
        },
        {
            "class_name": "knife",
            "confidence": 0.80,
            "box": [200.0, 100.0, 300.0, 300.0],
        },
    ]

    assert len(FakeRFDETR.last_instance.predict_calls) == 1
    assert (
        FakeRFDETR.last_instance.predict_calls[0]["threshold"]
        == 0.50
    )

    image = FakeRFDETR.last_instance.predict_calls[0]["image"]

    # The adapter must pass an RGB PIL image to RF-DETR.
    assert image.mode == "RGB"
    assert image.size == (640, 480)

    adapter.close()


def test_weapon_adapter_clamps_boxes_to_frame(tmp_path):
    model_path = tmp_path / "weapon.pth"
    model_path.write_bytes(b"test")

    class ClampingModel(FakeRFDETR):
        def predict(self, image, threshold):
            return FakePredictions(
                class_id=[1],
                confidence=[0.90],
                xyxy=[[-20, -10, 700, 500]],
            )

    adapter = WeaponVisionAdapter(
        model_path,
        model_factory=ClampingModel,
    )

    frame = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )

    detections = adapter.detect(frame)

    assert detections == [
        {
            "class_name": "gun",
            "confidence": 0.90,
            "box": [0.0, 0.0, 640.0, 480.0],
        }
    ]

    adapter.close()


def test_weapon_adapter_rejects_invalid_frame(tmp_path):
    model_path = tmp_path / "weapon.pth"
    model_path.write_bytes(b"test")

    adapter = WeaponVisionAdapter(
        model_path,
        model_factory=FakeRFDETR,
    )

    with pytest.raises(ValueError):
        adapter.detect(None)

    with pytest.raises(ValueError):
        adapter.detect(
            np.zeros(
                (480, 640),
                dtype=np.uint8,
            )
        )

    adapter.close()
