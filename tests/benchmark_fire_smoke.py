from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import torch


MODEL = Path(r"data\models\fire_smoke\cctv_yolov8n\best.onnx")
FIRE_IMAGE = Path(r"data\models\fire_smoke\test\fire_frame.jpg")
NORMAL_VIDEO = Path(r"data\input\01_person_tracking_intrusion.mp4")

OUTPUT_DIR = Path(r"data\output")
REPORT_PATH = OUTPUT_DIR / "fire_smoke_benchmark.json"

IMAGE_SIZE = 320
CONFIDENCE_THRESHOLD = 0.50

CLASS_NAMES = {
    0: "fire",
    1: "smoke",
}


def preprocess(frame: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (IMAGE_SIZE, IMAGE_SIZE))

    tensor = resized.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))
    tensor = np.expand_dims(tensor, axis=0)

    return np.ascontiguousarray(tensor)


def detect(session, input_name: str, frame: np.ndarray):
    tensor = preprocess(frame)

    start = time.perf_counter()

    output = session.run(
        None,
        {input_name: tensor},
    )[0]

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    elapsed = time.perf_counter() - start

    predictions = output[0].T

    best_confidence = 0.0
    best_class = None
    best_box = None

    for row in predictions:
        x, y, w, h = row[:4]
        class_scores = row[4:6]

        class_id = int(np.argmax(class_scores))
        confidence = float(class_scores[class_id])

        if confidence > best_confidence:
            best_confidence = confidence
            best_class = CLASS_NAMES[class_id]
            best_box = [
                float(x),
                float(y),
                float(w),
                float(h),
            ]

    return {
        "class": best_class,
        "confidence": best_confidence,
        "box": best_box,
        "latency_ms": elapsed * 1000.0,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not MODEL.exists():
        raise FileNotFoundError(f"Model not found: {MODEL}")

    if not FIRE_IMAGE.exists():
        raise FileNotFoundError(f"Fire image not found: {FIRE_IMAGE}")

    if not NORMAL_VIDEO.exists():
        raise FileNotFoundError(f"Normal CCTV video not found: {NORMAL_VIDEO}")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this benchmark.")

    torch.cuda.init()

    print("Loading Fire/Smoke model...")

    session = ort.InferenceSession(
        str(MODEL),
        providers=[
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ],
    )

    providers = session.get_providers()

    print("ACTIVE PROVIDERS:", providers)

    if "CUDAExecutionProvider" not in providers:
        raise RuntimeError("CUDAExecutionProvider is not active.")

    input_name = session.get_inputs()[0].name

    # ------------------------------------------------------------
    # Warm-up
    # ------------------------------------------------------------

    print()
    print("Running warm-up...")

    dummy = np.zeros(
        (1, 3, IMAGE_SIZE, IMAGE_SIZE),
        dtype=np.float32,
    )

    for _ in range(10):
        session.run(
            None,
            {input_name: dummy},
        )

    torch.cuda.synchronize()

    # ------------------------------------------------------------
    # Positive fire test
    # ------------------------------------------------------------

    print()
    print("Testing known fire image...")

    fire_frame = cv2.imread(str(FIRE_IMAGE))

    if fire_frame is None:
        raise RuntimeError("Could not read fire image.")

    fire_result = detect(
        session,
        input_name,
        fire_frame,
    )

    print(
        f"FIRE IMAGE -> "
        f"class={fire_result['class']} "
        f"confidence={fire_result['confidence']:.4f} "
        f"latency={fire_result['latency_ms']:.2f} ms"
    )

    # ------------------------------------------------------------
    # Normal CCTV negative test
    # ------------------------------------------------------------

    print()
    print("Testing normal CCTV video...")

    cap = cv2.VideoCapture(str(NORMAL_VIDEO))

    if not cap.isOpened():
        raise RuntimeError("Could not open normal CCTV video.")

    total_video_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    # Sample approximately 20 frames across the video.
    sample_count = min(20, total_video_frames)

    if sample_count <= 0:
        raise RuntimeError("Normal CCTV video contains no frames.")

    sample_indices = np.linspace(
        0,
        total_video_frames - 1,
        sample_count,
        dtype=int,
    )

    negative_results = []

    for index in sample_indices:

        cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            int(index),
        )

        ok, frame = cap.read()

        if not ok:
            continue

        result = detect(
            session,
            input_name,
            frame,
        )

        result["frame_index"] = int(index)

        negative_results.append(result)

        print(
            f"frame={index:04d} "
            f"class={result['class']} "
            f"confidence={result['confidence']:.4f} "
            f"latency={result['latency_ms']:.2f} ms"
        )

    cap.release()

    if not negative_results:
        raise RuntimeError("No negative frames were evaluated.")

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------

    fire_correct = (
        fire_result["class"] == "fire"
        and fire_result["confidence"] >= CONFIDENCE_THRESHOLD
    )

    false_positive_results = [
        result
        for result in negative_results
        if result["confidence"] >= CONFIDENCE_THRESHOLD
    ]

    fire_latencies = [fire_result["latency_ms"]]

    negative_latencies = [
        result["latency_ms"]
        for result in negative_results
    ]

    all_latencies = fire_latencies + negative_latencies

    average_latency = sum(all_latencies) / len(all_latencies)

    max_negative_confidence = max(
        result["confidence"]
        for result in negative_results
    )

    average_negative_confidence = (
        sum(
            result["confidence"]
            for result in negative_results
        )
        / len(negative_results)
    )

    false_positive_rate = (
        len(false_positive_results)
        / len(negative_results)
    )

    report = {
        "model": str(MODEL),
        "device": torch.cuda.get_device_name(0),
        "cuda": torch.version.cuda,
        "onnxruntime": ort.__version__,
        "providers": providers,
        "threshold": CONFIDENCE_THRESHOLD,
        "positive_test": {
            "image": str(FIRE_IMAGE),
            "expected": "fire",
            "predicted_class": fire_result["class"],
            "confidence": fire_result["confidence"],
            "latency_ms": fire_result["latency_ms"],
            "correct_at_threshold": fire_correct,
        },
        "negative_test": {
            "video": str(NORMAL_VIDEO),
            "frames_evaluated": len(negative_results),
            "false_positives": len(false_positive_results),
            "false_positive_rate": false_positive_rate,
            "maximum_confidence": max_negative_confidence,
            "average_confidence": average_negative_confidence,
            "results": negative_results,
        },
        "performance": {
            "average_latency_ms": average_latency,
            "min_latency_ms": min(all_latencies),
            "max_latency_ms": max(all_latencies),
            "estimated_fps": 1000.0 / average_latency,
        },
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------

    print()
    print("==============================================")
    print(" FIRE/SMOKE BENCHMARK — STAGE 33H")
    print("==============================================")
    print("GPU:", torch.cuda.get_device_name(0))
    print("Provider:", providers[0])

    print()
    print("POSITIVE TEST")
    print("Expected: fire")
    print("Predicted:", fire_result["class"])
    print(
        "Confidence:",
        f"{fire_result['confidence']:.4f}",
    )
    print(
        "PASS:",
        fire_correct,
    )

    print()
    print("NEGATIVE TEST")
    print(
        "Frames:",
        len(negative_results),
    )
    print(
        "False positives:",
        len(false_positive_results),
    )
    print(
        "False-positive rate:",
        f"{false_positive_rate * 100:.2f}%",
    )
    print(
        "Maximum normal-scene confidence:",
        f"{max_negative_confidence:.4f}",
    )

    print()
    print("PERFORMANCE")
    print(
        "Average latency:",
        f"{average_latency:.2f} ms",
    )
    print(
        "Estimated FPS:",
        f"{1000.0 / average_latency:.2f}",
    )

    print()
    print("REPORT:", REPORT_PATH)
    print("==============================================")

    if fire_correct:
        print("POSITIVE DETECTION: PASS")
    else:
        print("POSITIVE DETECTION: FAIL")

    if len(false_positive_results) == 0:
        print("NORMAL CCTV FALSE POSITIVES: PASS")
    else:
        print("NORMAL CCTV FALSE POSITIVES: REVIEW")

    print("BENCHMARK: COMPLETE")


if __name__ == "__main__":
    main()
