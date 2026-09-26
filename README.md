# HOTEL AI SECURITY

AI-assisted CCTV security and event detection system for hotel environments.

## Current capabilities

The system combines CCTV ingestion, frame sampling, computer-vision detection, tracking, zone/rule evaluation, event persistence, evidence handling, notifications, authentication, and an authenticated management API.

Current implemented security detections include:

- Person/intrusion detection
- Zone-based intrusion detection
- Crowding detection
- After-hours presence
- Fire/smoke detection
- Weapon detection
- Fall-event processing
- Camera health monitoring
- Event evaluation and reporting
- ADMIN camera CRUD
- ADMIN zone CRUD
- JWT authentication
- Configurable event/evidence retention

## Production model artifacts

Production inference currently depends on two external ONNX artifacts:

| Model | Required path | Runtime version |
|---|---|---|
| Fire/smoke detector | `data/models/fire_smoke/cctv_yolov8n/best.onnx` | `fire-smoke-event-v1` |
| Weapon detector | `data/models/weapon/gun-knife-yolo11n/best.onnx` | `weapon-yolo11n-gun-knife-v1` |

Model binaries are intentionally excluded from Git through `data/models/*`.

Do not commit model binaries, generated model caches, videos, images, or runtime databases.

## Verify model artifacts

After obtaining the required production models:

```powershell
python scripts\verify_model_artifacts.py
```

## Run tests

With the virtual environment activated:

```powershell
python -m pytest -q
```

## JWT configuration

Production authentication requires the `HOTEL_SECURITY_JWT_SECRET` environment variable.

The secret must contain at least 32 characters. Never commit secrets.

## Retention

The current configured retention policy is 30 days for event and evidence retention covered by the retention service.

Configuration: `configs/retention.json`

## Development workflow

Work should be performed on feature branches.

Before committing:

```powershell
git status --short
git diff --check
python -m pytest -q
```

Review all changed files manually.

## Security model

The system is designed as an AI-assisted security system with human oversight. AI detections should be treated as security events requiring appropriate operational handling rather than as autonomous decisions.

The current design does not use face recognition.
