# HOTEL AI SECURITY — Pilot Runbook

## 1. Purpose

This runbook defines the controlled operating procedure for the HOTEL AI SECURITY pilot/shadow period.

The system is an AI-assisted CCTV security system with human oversight. AI detections are security events for operator handling; they are not autonomous decisions.

This runbook covers:

- Pre-pilot readiness
- Configuration and model verification
- API and CCTV runner operation
- Camera health monitoring
- System resource monitoring
- Security-event handling
- Failure response and recovery
- Configuration changes
- Evidence and retention
- Controlled restart/shutdown
- Pilot acceptance checks
- Manual-surveillance fallback

## 2. Current Pilot Configuration

The repository contains these configuration/bootstrap files. Camera and zone configuration is bootstrapped from the repository configuration and, after bootstrap, the runtime database is authoritative for active camera and zone configuration:

| File | Purpose |
|---|---|
| `configs/cameras.json` | Camera configuration |
| `configs/zones.json` | Zone configuration |
| `configs/rules.json` | Detection-rule configuration |
| `configs/monitoring.json` | Resource alert thresholds |
| `configs/retention.json` | Event/evidence retention |
| `configs/weapon_model.json` | Weapon-model configuration |

Current configured values include:

- CPU alert threshold: 90%
- Memory alert threshold: 90%
- Disk alert threshold: 90%
- Event retention: 30 days
- Evidence retention: 30 days
- Crowding: enabled
- Crowding threshold: 5 people
- Crowding persistence: 3 frames
- After-hours: currently disabled
- After-hours timezone: `Asia/Kolkata`
- Current configured camera: `CAM-001`
- Current camera source type: file
- Current AI FPS: 5.0
- Camera reconnect configuration: 3 attempts, 1 second delay
- Current configured restricted zone: `restricted_01`

For a real hotel pilot, review camera sources, zones, schedules, and rule settings before starting the pilot.

## 3. Prerequisites

Before starting a pilot run:

- Activate the project virtual environment.
- Confirm the repository is on the intended feature/release branch.
- Confirm the working tree is clean before an operational run.
- Confirm required configuration files are present.
- Confirm required production model artifacts are present.
- Do not commit model binaries, generated model caches, videos, images, or runtime databases.
- Ensure the `HOTEL_SECURITY_JWT_SECRET` environment variable is configured for production authentication.
- The JWT secret must contain at least 32 characters and must not be committed to Git.
- Confirm required camera sources are reachable.
- Confirm sufficient disk space is available for runtime data and evidence.

## 4. Verify Production Models

The production inference models are external artifacts and are intentionally excluded from Git.

Required model artifacts:

- Fire/smoke detector:
  `data/models/fire_smoke/cctv_yolov8n/best.onnx`
- Weapon detector:
  `data/models/weapon/gun-knife-yolo11n/best.onnx`

Run:

```powershell
python scripts\verify_model_artifacts.py
```

Expected result:

```text
MODEL VERIFICATION PASSED
```

If verification fails, do not start the pilot inference workload. Resolve the model artifact problem first.

## 5. Verify Configuration

Review the configuration/bootstrap files before a pilot. For an active runtime, verify camera and zone state through the authenticated management API/database rather than editing the JSON files directly:

```powershell
Get-Content configs\cameras.json
Get-Content configs\zones.json
Get-Content configs\rules.json
Get-Content configs\monitoring.json
Get-Content configs\retention.json
```

Verify:

- Every pilot camera has the intended source.
- Camera IDs are unique and match their zones.
- Restricted/security zones are correct.
- Detection rules are intentionally enabled or disabled.
- After-hours schedules are intentionally configured.
- Resource thresholds are appropriate for the pilot machine.
- Retention values are approved for the pilot.

Do not change production configuration casually during an active pilot. Record configuration changes and the operator responsible for them.

## 6. API Health Verification

The backend exposes a health endpoint:

```text
GET /health
```

The expected healthy response contains:

```json
{
  "status": "healthy"
}
```

Authenticated operational endpoints include:

- `/cameras`
- `/cameras/health/summary`
- `/cameras/{camera_id}/health`
- `/events`
- `/event-quality`
- `/audit-logs`

Use the authenticated API/dashboard to verify that the service is responding before relying on AI alerts.

The API also exposes a Prometheus metrics endpoint:

```text
GET /metrics
```

Verify that it responds successfully during pilot validation. The endpoint exposes API request count, API error count, and API request latency metrics, along with the existing system and camera monitoring metrics. API request metrics use normalized route labels and exclude the `/metrics` scrape request itself. Runner event-path latency is measured separately by the CCTV processing runtime and is not exposed through the FastAPI `/metrics` endpoint.

## 7. CCTV Runner

The CCTV processing entry point is:

```powershell
python ai\run_intrusion_detection.py
```

The runner uses the configured camera fleet, camera workers, detection components, event persistence, notifications, and camera-health handling.

Do not invent or add command-line arguments that are not supported by the current runner.

During operation, monitor the console output for:

- Camera worker completion
- Camera worker failures
- Fleet errors
- Camera-health transitions
- Detection/event activity

A failure in an individual camera worker is reported separately from the other camera workers. Treat a failed camera as an operational issue requiring investigation.

## 8. System Resource Monitoring

The project provides a system monitoring collection script:

```powershell
python scripts\collect_system_monitoring.py
```

The script records system metrics and prints JSON containing:

- Timestamp
- Monitoring status
- CPU utilization
- Memory utilization
- Disk utilization
- GPU availability
- Resource alerts

Current configured CPU, memory, and disk alert thresholds are 90%.

Run the collector during pilot observation periods and retain the generated monitoring records as pilot evidence.

## 9. Normal Pilot Operation

During normal operation:

1. Confirm the API is healthy.
2. Confirm cameras are visible and healthy.
3. Confirm the CCTV runner is active.
4. Confirm resource monitoring is operating.
5. Review generated security events.
6. Operators review alerts and evidence.
7. Operators acknowledge, dispatch, and resolve actionable events through the supported workflow.
8. Record false positives using the supported false-positive workflow.
9. Review audit logs when investigating operator actions or configuration changes.
10. Preserve pilot evidence and reports.

AI detections must remain subject to human operational review.

## 10. Camera Offline Response

A camera can enter an offline state after the configured camera-health failure threshold is reached.

When a camera is reported offline:

1. Identify the affected camera ID.
2. Check the camera health endpoint:
   `/cameras/{camera_id}/health`
3. Check the runner console for the camera worker/error information.
4. Verify the physical camera/network/source independently.
5. Do not assume an AI detection outage is a security incident.
6. If surveillance coverage is lost, immediately follow the hotel's manual-surveillance procedure for the affected area.
7. Correct the source/network/camera problem.
8. Confirm successful frames are being received again.
9. Confirm the camera returns to healthy operation.
10. Record the incident and recovery in the pilot operational record.

The system represents camera failure and subsequent recovery as camera-health transitions. Historical health reporting measures the observed period and should not be interpreted as uptime before the observation period.

## 11. Camera Recovery

After restoring a failed camera:

1. Confirm the camera source is reachable.
2. Confirm frames are being received.
3. Check `/cameras/{camera_id}/health`.
4. Confirm the camera is healthy.
5. Confirm the runner continues processing the camera.
6. Confirm no new persistent camera failure remains.
7. Record the recovery time and operational cause if known.

If the camera repeatedly fails, treat the camera/source as unstable and use manual surveillance until reliable coverage is restored.

## 12. AI or Model Failure Response

If a detector/model fails:

1. Do not treat missing AI output as proof that the monitored area is safe.
2. Check the runner console for the detector/model error.
3. Confirm required model artifacts are present.
4. Run:

```powershell
python scripts\verify_model_artifacts.py
```

5. If model verification fails, stop relying on the affected AI detection.
6. Maintain manual surveillance for the affected security coverage.
7. Correct the model/runtime problem.
8. Re-verify the model artifacts.
9. Restart the affected processing workload using the controlled restart procedure.
10. Confirm normal event processing before returning to normal pilot operation.
11. Record the failure and recovery.

## 13. CPU, Memory, or Disk Alert Response

The current monitoring thresholds are:

- CPU: 90%
- Memory: 90%
- Disk: 90%

When a resource alert occurs:

1. Record the timestamp and affected resource.
2. Determine whether the condition is transient or sustained.
3. Check whether camera processing or event handling is degraded.
4. Avoid adding workload while the system is resource-constrained.
5. For disk pressure, protect evidence/runtime data and prevent uncontrolled storage growth.
6. If processing becomes unreliable, move affected surveillance coverage to manual fallback.
7. Correct the underlying resource problem.
8. Re-run system monitoring.
9. Confirm stable operation before resuming normal pilot workload.

Do not silently increase thresholds to hide an operational problem.

## 14. Database or Storage Failure

If event, evidence, camera-health, or monitoring persistence fails:

1. Record the error and timestamp.
2. Do not assume an event was successfully persisted if the database operation failed.
3. Preserve any available console/operator evidence.
4. Check disk availability and database accessibility.
5. Do not delete runtime databases as a first response.
6. If reliable AI/event persistence cannot be maintained, use manual surveillance for affected coverage.
7. Restore database/storage availability.
8. Validate service operation before returning to normal pilot operation.
9. Record the incident and recovery.

## 15. Notification Failure

The current implementation provides notification persistence and a console notification provider. External SMS/email/push delivery is not the current pilot delivery mechanism.

If notification behavior appears abnormal:

1. Check whether the security event itself was persisted.
2. Check the notification pipeline/console output.
3. Verify the operator dashboard/API still exposes the event.
4. Do not assume absence of a notification means absence of an event.
5. Use the dashboard/event workflow and manual operational escalation if necessary.
6. Record the notification problem for pilot evidence.

## 16. Security Event Response

For an actionable event:

1. Review the event type, camera, severity, timestamp, and available evidence.
2. Verify the situation using available CCTV/operator procedures.
3. Acknowledge the event using the authorized operator workflow.
4. Dispatch the appropriate security response.
5. Resolve the event after the situation has been handled.
6. Record an appropriate resolution.
7. If the event is determined to be a false positive, use the false-positive workflow and record the reason.

The supported event lifecycle is:

```text
NEW → ACKNOWLEDGED → DISPATCHED → RESOLVED
```

False-positive handling is also supported.

## 17. Camera and Zone Configuration Changes

Camera and zone management is ADMIN-only.

When an administrator creates, updates, or deletes a camera or zone, the API returns:

```text
runner_reload_required: true
```

Therefore:

1. Make configuration changes through the authenticated management API.
2. Verify the API response.
3. Record the change through the audit trail.
4. Schedule/perform the required controlled runner reload.
5. Verify the affected camera/zone after reload.
6. Do not assume a running worker has automatically reloaded the configuration.

## 18. Evidence and Retention

The configured retention policy is currently:

- Events: 30 days
- Evidence: 30 days

Configuration:

```text
configs/retention.json
```

Do not manually delete evidence or runtime databases as an emergency workaround unless an approved operational procedure explicitly requires it.

Evidence availability can be checked through the event evidence API for events that contain an evidence path.

## 19. Controlled Restart

Before restarting the processing workload:

1. Record the reason for restart.
2. Confirm active security events are handled or transferred to manual surveillance.
3. Stop the affected workload cleanly.
4. Restart the required service/process using the repository's established startup procedure.
5. Verify API health if the API was restarted.
6. Verify camera health.
7. Verify the CCTV runner is processing cameras.
8. Verify event generation.
9. Verify notifications.
10. Record the restart and validation result.

Do not restart solely to hide an unresolved failure condition.

## 20. Controlled Shutdown

For a planned pilot shutdown:

1. Notify the responsible operator.
2. Confirm manual surveillance coverage for any remaining monitored area.
3. Stop the CCTV processing workload.
4. Stop the API if it is no longer required.
5. Preserve relevant event, health, monitoring, and audit evidence.
6. Confirm the system is no longer expected to generate alerts.

## 21. Pilot Acceptance Checklist

Before declaring a pilot observation period complete, verify:

### System

- [ ] API health is confirmed.
- [ ] Required model artifacts pass verification.
- [ ] Camera configuration is reviewed.
- [ ] Zone configuration is reviewed.
- [ ] Detection-rule configuration is reviewed.
- [ ] Resource monitoring records exist.
- [ ] Prometheus `/metrics` endpoint responds successfully.
- [ ] API request/error/latency metrics are visible from the Prometheus endpoint.
- [ ] Camera health records exist.
- [ ] Historical camera uptime/feed-rate report is generated for the observed period.
- [ ] Event records are available.
- [ ] Evidence is available where recording succeeded.
- [ ] Audit records are available.
- [ ] Operator event lifecycle actions are recorded.
- [ ] False-positive feedback is recorded where applicable.

### Operations

- [ ] Camera-offline response has been exercised or documented.
- [ ] Camera recovery has been exercised or documented.
- [ ] Manual-surveillance fallback is available.
- [ ] Resource-alert response is documented.
- [ ] AI/model failure response is documented.
- [ ] Notification failure response is documented.
- [ ] Database/storage failure response is documented.
- [ ] Configuration-change/reload procedure is documented.

### Evidence

- [ ] Pilot observation period is explicitly recorded.
- [ ] Camera health report covers the intended observation window.
- [ ] System monitoring evidence is retained.
- [ ] Event/evaluation reports are retained.
- [ ] Known incidents and recoveries are recorded.

## 22. Manual-Surveillance Fallback

The AI system must not be treated as the sole source of security coverage.

If camera health, AI inference, event persistence, notification handling, or another critical subsystem becomes unreliable:

1. Identify affected coverage.
2. Notify the responsible security operator.
3. Transfer the affected coverage to the hotel's manual CCTV/security procedure.
4. Preserve available system evidence.
5. Investigate and restore the affected subsystem.
6. Validate recovery.
7. Document the incident and recovery.

Manual surveillance remains the operational fallback when automated coverage cannot be trusted.

## 23. Current Prototype Limitations

The following must not be represented as already-implemented production capabilities:

- Real SMS/email/push notification delivery.
- Grafana dashboards or equivalent external visualization.
- Docker/container deployment.
- PostgreSQL deployment.
- 10+ camera performance/load validation.
- 40+ camera infrastructure validation.
- Automated production deployment.
- Complete external service-level restart/alerting orchestration.

These are later-stage or deployment-layer concerns and should not be claimed as pilot capabilities unless separately implemented and validated.

## 24. Operational Record

For every material pilot incident, record at minimum:

| Field | Required information |
|---|---|
| Timestamp | Time of detection/incident |
| Component | Camera/API/model/database/notification/resource/etc. |
| Camera ID | If camera-specific |
| Symptom | What was observed |
| Initial response | Action taken |
| Manual fallback | Whether activated |
| Recovery | Action that restored service |
| Validation | Checks performed after recovery |
| Operator | Responsible operator |
| Evidence | Relevant event/report/log reference |

The pilot record should preserve enough information to reconstruct what happened without relying only on memory.

