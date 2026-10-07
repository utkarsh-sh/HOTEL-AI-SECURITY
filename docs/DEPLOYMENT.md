# HOTEL AI SECURITY — Deployment Guide

## 1. Purpose

This document describes the supported deployment procedure for the current HOTEL AI SECURITY pilot/local environment.

The deployment consists of:
- Python application environment
- SQLite runtime database
- Production ONNX model artifacts
- FastAPI management/authentication service
- CCTV processing runner
- Camera and zone configuration
- System and camera health monitoring
- Event/evidence persistence
- Console and optional webhook notifications

This guide complements:
- `docs/setup.md` — environment setup and reproducibility
- `docs/model_acquisition.md` — production model acquisition and checksum verification
- `docs/PILOT_RUNBOOK.md` — operational procedures, failure response, and pilot validation

The current implementation is suitable for controlled pilot/shadow operation. It is not yet a containerized or automated production deployment.

## 2. Prerequisites

- Windows 10/11 for the current supported development workflow
- Python 3.13
- Git
- A working Python virtual environment
- Sufficient disk space for runtime databases and evidence
- Required production ONNX model artifacts
- Camera sources reachable from the deployment host
- Optional NVIDIA/CUDA environment when GPU inference is required

Complete environment preparation in `docs/setup.md` before continuing.

## 3. Repository and environment

If the repository is not already present:

    git clone https://github.com/utkarsh-sh/HOTEL-AI-SECURITY.git
    cd HOTEL-AI-SECURITY

Create and activate the virtual environment:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1

Install the CI-tested dependency set:

    python -m pip install -r requirements-ci.txt

If an existing prepared virtual environment is already available, do not recreate it unnecessarily.

## 4. Authentication configuration

Set the deployment JWT secret:

    $env:HOTEL_SECURITY_JWT_SECRET = "<strong-secret-at-least-32-characters>"

The secret must contain at least 32 characters and must never be committed to Git or exposed in logs.

## 5. Production model artifacts

Required model paths:

- Fire/smoke: `data/models/fire_smoke/cctv_yolov8n/best.onnx`
- Weapon: `data/models/weapon/gun-knife-yolo11n/best.onnx`

Follow `docs/model_acquisition.md` to obtain the artifacts.

Verify them before deployment:

    python scripts\verify_model_artifacts.py

Expected result: `MODEL VERIFICATION PASSED`.

Do not start the inference workload if model verification fails.

## 6. Configuration review

Review the deployment configuration before starting the application:

    Get-Content configs\cameras.json
    Get-Content configs\zones.json
    Get-Content configs\rules.json
    Get-Content configs\monitoring.json
    Get-Content configs\retention.json

Confirm camera IDs, camera sources, zones, detection rules, monitoring thresholds, and retention settings are appropriate for the pilot.

The current configured retention policy is 30 days for event/evidence retention covered by the retention service.

## 7. Camera and zone configuration authority

Camera and zone configuration follows a one-time JSON bootstrap followed by database-backed runtime configuration.

After bootstrap, the database is authoritative for runtime camera and zone configuration.

Administrative camera or zone changes require the runner to be restarted before the running inference process uses the new configuration. Do not assume that changing JSON files hot-reloads a running runner.

## 8. Create application users

Create an administrator interactively:

    python scripts\create_admin.py

Create a viewer when required:

    python scripts\create_viewer.py

The account creation scripts hash passwords using Argon2. Do not share administrator credentials between operators.

## 9. Pre-deployment validation

Run the full regression suite:

    python -m pytest -q

Then verify model artifacts:

    python scripts\verify_model_artifacts.py

Check the working tree:

    git status --short
    git diff --check

Generated databases, evidence, videos, images, model binaries, caches, and secrets must not be committed to Git.

## 10. Start the FastAPI service

Start the API from the repository root:

    uvicorn backend.main:app --host 127.0.0.1 --port 8000

Verify the API:

    Invoke-WebRequest http://127.0.0.1:8000/openapi.json

A successful response should return HTTP 200.

The login endpoint is `POST /login`.

Authenticated event lifecycle endpoints include:

- `POST /events/{event_id}/acknowledge`
- `POST /events/{event_id}/dispatch`
- `POST /events/{event_id}/resolve`
- `POST /events/{event_id}/false-positive`

Use authenticated API operations for operator event handling so that audit records are generated.

## 11. Optional webhook notifications

Console notification is available by default.

To enable the configurable webhook provider:

    $env:HOTEL_SECURITY_WEBHOOK_URL = "https://example.invalid/security-webhook"

When configured, the CCTV runner registers the webhook provider in addition to the console provider.

The webhook provider sends event information as JSON and treats HTTP 2xx responses as successful delivery.

HTTP, network, timeout, and operating-system failures are handled as notification failures by the provider and dispatcher.

If the variable is not configured, the console provider remains available.

Do not place webhook credentials or secrets directly into source code.

## 12. Start the CCTV processing runner

After the API and configuration environment are ready:

    python -m ai.run_intrusion_detection

The runner handles camera ingestion, frame sampling, person detection and tracking, zone and rule evaluation, security-event persistence, evidence recording, notifications, and camera health tracking.

The FastAPI service and CCTV runner are separate processes.

## 13. Runtime verification

During startup and operation, verify:

1. Configured camera sources open successfully.
2. The expected camera count is loaded.
3. AI inference initializes successfully.
4. Required models load successfully.
5. Events are persisted when test detections occur.
6. Evidence is generated for supported events.
7. Notifications are recorded.
8. Camera health records are updated.
9. System monitoring samples are collected.
10. Authentication and operator event actions work through the API.

Collect a system monitoring sample with:

    python -m scripts.collect_system_monitoring

For the complete operational validation procedure, use `docs/PILOT_RUNBOOK.md`.

## 14. GPU verification

Do not assume that an NVIDIA GPU means GPU inference is active.

Inspect ONNX Runtime providers with the following Python command:

    python -c "import onnxruntime as ort; print(ort.get_available_providers())"

If CUDA is expected, confirm during deployment validation that the relevant model adapter actually uses the CUDA execution provider.

CPU execution remains supported by the ONNX adapters.

## 15. Shadow/pilot validation

Before treating the deployment as operationally ready, perform a controlled shadow/pilot run.

Use `docs/PILOT_RUNBOOK.md` for the complete procedure.

Validation should cover model verification, camera availability, camera uptime/feed-rate measurement, system resource monitoring, event generation, notification outcomes, operator acknowledgement/dispatch/resolution, false-positive review, audit logging, evidence generation, failure/recovery testing, and operational reporting.

AI detections remain human-reviewed security events. The system is not intended to make autonomous security decisions.

## 16. Configuration changes and restart

Camera and zone changes require the runtime process to be restarted before they take effect.

After stopping the runner cleanly, restart it with:

    python -m ai.run_intrusion_detection

If the API also needs restarting:

    uvicorn backend.main:app --host 127.0.0.1 --port 8000

After a restart, repeat the relevant model, service, camera, and health checks.

## 17. Controlled shutdown

For a controlled shutdown:

1. Stop the CCTV runner.
2. Allow runner cleanup and notification-dispatcher shutdown to complete.
3. Stop the FastAPI service.
4. Confirm required processes have stopped.
5. Preserve required evidence and operational reports.
6. Do not delete runtime databases or evidence as part of normal shutdown.

For incident-specific shutdown and recovery procedures, use `docs/PILOT_RUNBOOK.md`.

## 18. Runtime data and retention

Runtime state includes SQLite databases, event records, audit records, notification records, camera health history, system monitoring samples, generated evidence, and operational reports.

Handle runtime data according to deployment backup and retention requirements.

The current application uses SQLite. PostgreSQL migration is a future infrastructure item and is not part of the current deployment.

## 19. Current deployment limitations

The current repository does not provide a complete automated enterprise deployment stack.

The following are not currently implemented as part of this deployment:
- Docker/container deployment
- Automated CI/CD deployment to production infrastructure
- PostgreSQL production migration
- Prometheus/Grafana monitoring
- Automated external restart orchestration
- Complete external alerting infrastructure
- Validated 10+ camera performance/load deployment
- Validated 40+ camera production infrastructure

These limitations must be considered when moving beyond a controlled pilot/shadow deployment.

Do not describe the current system as a fully automated enterprise production platform.

## 20. Security requirements

Before a real deployment:

- Keep JWT secrets outside Git.
- Use strong unique passwords.
- Use separate operator/admin accounts.
- Protect camera credentials.
- Do not expose RTSP credentials in logs or reports.
- Do not commit model binaries or runtime artifacts.
- Restrict API network exposure appropriately.
- Review camera and zone configuration before starting inference.
- Keep human operators responsible for security-event decisions.
- Follow pilot failure/recovery procedures.

## 21. Deployment checklist

### Environment
- [ ] Python environment prepared
- [ ] Dependencies installed
- [ ] JWT secret configured
- [ ] Production models installed
- [ ] Model checksum verification passed
- [ ] Full test suite passed

### Configuration
- [ ] Cameras reviewed
- [ ] Camera sources reachable
- [ ] Zones reviewed
- [ ] Detection rules reviewed
- [ ] Monitoring thresholds reviewed
- [ ] Retention configuration reviewed
- [ ] Admin account created
- [ ] Required viewer accounts created

### Services
- [ ] FastAPI service starts successfully
- [ ] `/openapi.json` responds successfully
- [ ] Authentication works
- [ ] CCTV runner starts successfully
- [ ] AI inference initializes
- [ ] Camera health is recorded
- [ ] System monitoring is recorded
- [ ] Notifications are recorded
- [ ] Evidence is generated

### Operational validation
- [ ] Shadow/pilot run completed
- [ ] Event lifecycle tested
- [ ] Audit records verified
- [ ] False-positive review performed
- [ ] Camera failure/recovery procedure validated
- [ ] Operational report generated
- [ ] Manual-surveillance fallback understood

## 22. Related documentation

- `docs/setup.md` — local environment setup and reproducibility
- `docs/model_acquisition.md` — model acquisition and checksum verification
- `docs/PILOT_RUNBOOK.md` — pilot operation, monitoring, failure response, recovery, and acceptance
- `README.md` — project overview, capabilities, security model, and development workflow
