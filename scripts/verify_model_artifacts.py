from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import onnxruntime as ort


@dataclass(frozen=True)
class ModelSpec:
    name: str
    path: Path
    expected_sha256: str
    expected_input_shape: tuple[int, ...]
    expected_output_shape: tuple[int, ...]


ROOT = Path(__file__).resolve().parents[1]


MODEL_SPECS = (
    ModelSpec(
        name="fire/smoke",
        path=ROOT / "data/models/fire_smoke/cctv_yolov8n/best.onnx",
        expected_sha256=(
            "f2699b753e78be8d392bfa63e64bf102ea3ceb8b6086a59dfd8192b61a0c6fad"
        ),
        expected_input_shape=(1, 3, 320, 320),
        expected_output_shape=(1, 6, 2100),
    ),
    ModelSpec(
        name="weapon",
        path=ROOT / "data/models/weapon/gun-knife-yolo11n/best.onnx",
        expected_sha256=(
            "ba7466e4036db5aa86189a59125a42c0e64de254e9d89429c09082f45d99ec6d"
        ),
        expected_input_shape=(1, 3, 640, 640),
        expected_output_shape=(1, 300, 6),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def verify_model(spec: ModelSpec) -> None:
    print(f"\n[{spec.name}]")
    print(f"Path: {spec.path}")

    if not spec.path.is_file():
        raise RuntimeError(f"Model file not found: {spec.path}")

    actual_hash = sha256_file(spec.path)

    print(f"SHA-256: {actual_hash}")

    if actual_hash.lower() != spec.expected_sha256.lower():
        raise RuntimeError(
            "SHA-256 mismatch.\n"
            f"Expected: {spec.expected_sha256}\n"
            f"Actual:   {actual_hash}"
        )

    session = ort.InferenceSession(
        str(spec.path),
        providers=["CPUExecutionProvider"],
    )

    inputs = session.get_inputs()
    outputs = session.get_outputs()

    if len(inputs) != 1:
        raise RuntimeError(
            f"Expected exactly one input, found {len(inputs)}."
        )

    if len(outputs) != 1:
        raise RuntimeError(
            f"Expected exactly one output, found {len(outputs)}."
        )

    actual_input_shape = tuple(inputs[0].shape)
    actual_output_shape = tuple(outputs[0].shape)

    print(
        f"Input:  {inputs[0].name} {actual_input_shape} {inputs[0].type}"
    )
    print(
        f"Output: {outputs[0].name} {actual_output_shape} {outputs[0].type}"
    )
    print(f"Providers: {session.get_providers()}")

    if actual_input_shape != spec.expected_input_shape:
        raise RuntimeError(
            "Input shape mismatch.\n"
            f"Expected: {spec.expected_input_shape}\n"
            f"Actual:   {actual_input_shape}"
        )

    if actual_output_shape != spec.expected_output_shape:
        raise RuntimeError(
            "Output shape mismatch.\n"
            f"Expected: {spec.expected_output_shape}\n"
            f"Actual:   {actual_output_shape}"
        )

    print("Status: PASS")


def main() -> int:
    print("HOTEL AI SECURITY - Production Model Verification")
    print("=" * 52)
    print(f"ONNX Runtime: {ort.__version__}")
    print(
        "Available providers: "
        + ", ".join(ort.get_available_providers())
    )

    failures: list[str] = []

    for spec in MODEL_SPECS:
        try:
            verify_model(spec)
        except Exception as exc:
            failures.append(f"{spec.name}: {exc}")
            print(f"Status: FAIL - {exc}")

    print("\n" + "=" * 52)

    if failures:
        print("MODEL VERIFICATION FAILED")
        return 1

    print("MODEL VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
