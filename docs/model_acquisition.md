# Model Acquisition and Verification

## Purpose

Production inference requires external ONNX model artifacts. The repository does not track these binaries because they are runtime assets and may be large.

This document records the exact artifact identity that the current application expects.

## Production fire/smoke model

### Artifact

Path:
`data/models/fire_smoke/cctv_yolov8n/best.onnx`

Runtime version:
`fire-smoke-event-v1`

SHA-256:
`F2699B753E78BE8D392BFA63E64BF102EA3CEB8B6086A59DFD8192B61A0C6FAD`

### ONNX interface verified for the current artifact

Input:
`images` — `[1, 3, 320, 320]` — `tensor(float)`

Output:
`output0` — `[1, 6, 2100]` — `tensor(float)`

The production runner directly references this artifact.

### Provenance limitation

The local artifact contains Hugging Face download-cache metadata, and that metadata records a SHA-256 matching the production file. However, the local cache does not contain a readable repository ID, source URL, or source revision for this exact `best.onnx`.

Therefore this repository intentionally does not claim an upstream model repository for this production artifact.

The exact artifact should be obtained from the project-approved model source or deployment artifact store and verified against the SHA-256 above.

Do not substitute the Qwen2-VL OpenVINO model described below.

---

## Production weapon model

### Artifact

Path:
`data/models/weapon/gun-knife-yolo11n/best.onnx`

Runtime version:
`weapon-yolo11n-gun-knife-v1`

SHA-256:
`BA7466E4036DB5AA86189A59125A42C0E64DE254E9D89429C09082F45D99EC6D`

### Recorded source metadata

Source model:
`cosgun99/gun-knife-yolo11n`

Source revision:
`572728ceaad5f1b5e3344da0a98e043749c49427`

Recorded classes:
`0 = gun`, `1 = knife`

Recorded ONNX input size:
`640 x 640`

The weapon adapter performs SHA-256 verification when the expected checksum is supplied.

---

## Experimental fire/smoke VLM export

The repository also contains:

`data/models/fire_smoke/export_and_quantize.sh`

This script is a separate experimental/export workflow for:

`Qwen/Qwen2-VL-2B-Instruct`

It exports to:

`data/models/fire_smoke/qwen2_vl_2b_ov/`

Supported export precisions are:

- `INT4`
- `INT8`
- `FP16`

The script also references the Intel fire-and-smoke Hugging Face repository for a best-effort download-tracking request.

### Important

This Qwen2-VL/OpenVINO artifact is not the production fire/smoke ONNX detector currently loaded by `ai/run_intrusion_detection.py`.

The production runner uses:

`data/models/fire_smoke/cctv_yolov8n/best.onnx`

Do not replace the production detector with the VLM export unless the application is deliberately redesigned and revalidated.

---

## Acquisition procedure

1. Obtain the approved production fire/smoke ONNX artifact.
2. Place it at `data/models/fire_smoke/cctv_yolov8n/best.onnx`.
3. Obtain the approved production weapon ONNX artifact.
4. Place it at `data/models/weapon/gun-knife-yolo11n/best.onnx`.
5. Run `python scripts\verify_model_artifacts.py`.
6. Do not proceed with production or evaluation use if verification reports a checksum or interface mismatch.

## Why checksums are pinned

A filename alone does not establish that a model artifact is the intended artifact. SHA-256 verification detects accidental replacement, corruption, or an incorrect model download before inference starts.

The verifier therefore treats the checksum as the artifact identity.

## Git policy

Do not add these model binaries to Git.

The repository intentionally ignores:

`data/models/*`

Do not remove that ignore rule merely to make local setup easier.
