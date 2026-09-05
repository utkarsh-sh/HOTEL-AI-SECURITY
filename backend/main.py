from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database.event_database import EventDatabase
from database.camera_database import CameraDatabase
from database.audit_database import AuditDatabase

app = FastAPI(
    title="Hotel AI Security API",
    description="Backend API for the Hotel AI CCTV Security System",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EventStatusUpdate(BaseModel):
    resolution: Optional[str] = None


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "hotel-ai-security-api",
        "version": "0.3.0",
    }


# ============================================================
# CAMERAS
# ============================================================

@app.get("/cameras")
def get_cameras():
    database = CameraDatabase()

    try:
        cameras = database.get_all_cameras()

        return {
            "total": len(cameras),
            "cameras": [dict(camera) for camera in cameras],
        }

    finally:
        database.close()


@app.get("/cameras/{camera_id}")
def get_camera(camera_id: str):
    database = CameraDatabase()

    try:
        camera = database.get_camera(camera_id)

        if camera is None:
            raise HTTPException(
                status_code=404,
                detail=f"Camera {camera_id} not found",
            )

        return dict(camera)

    finally:
        database.close()


@app.get("/cameras/{camera_id}/health")
def get_camera_health(camera_id: str):
    database = CameraDatabase()

    try:
        camera = database.get_camera(camera_id)

        if camera is None:
            raise HTTPException(
                status_code=404,
                detail=f"Camera {camera_id} not found",
            )

        return {
            "camera_id": camera["camera_id"],
            "status": camera["status"],
            "last_seen": camera["last_seen"],
            "fps": camera["fps"],
            "resolution": (
                f"{camera['width']}x{camera['height']}"
                if camera["width"] and camera["height"]
                else None
            ),
            "consecutive_failures": camera[
                "consecutive_failures"
            ],
            "last_error": camera["last_error"],
        }

    finally:
        database.close()


# ============================================================
# EVENTS
# ============================================================

@app.get("/events")
def get_events(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    camera_id: Optional[str] = None,
):
    database = EventDatabase()

    try:
        events = database.get_all_events()

        filtered_events = []

        for event in events:
            event_dict = dict(event)

            if status and event_dict["status"] != status:
                continue

            if severity and event_dict["severity"] != severity:
                continue

            if event_type and event_dict["event_type"] != event_type:
                continue

            if camera_id and event_dict["camera_id"] != camera_id:
                continue

            filtered_events.append(event_dict)

        return {
            "total": len(filtered_events),
            "events": filtered_events,
        }

    finally:
        database.close()


@app.get("/events/{event_id}")
def get_event(event_id: int):
    database = EventDatabase()

    try:
        event = database.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail=f"Event {event_id} not found",
            )

        return dict(event)

    finally:
        database.close()


# ============================================================
# EVENT EVIDENCE
# ============================================================

@app.get("/events/{event_id}/evidence")
def get_event_evidence(event_id: int):
    """
    Return the recorded evidence clip for an event.
    """

    database = EventDatabase()

    try:
        event = database.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail=f"Event {event_id} not found",
            )

        evidence_path = event["evidence_path"]

        if not evidence_path:
            raise HTTPException(
                status_code=404,
                detail=f"No evidence available for event {event_id}",
            )

        evidence_file = Path(evidence_path)

        if not evidence_file.exists():
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Evidence file not found for event {event_id}"
                ),
            )

        return FileResponse(
            path=evidence_file,
            media_type="video/mp4",
            filename=evidence_file.name,
        )

    finally:
        database.close()


# ============================================================
# ACKNOWLEDGE EVENT
# ============================================================

@app.post("/events/{event_id}/acknowledge")
def acknowledge_event(event_id: int):
    database = EventDatabase()
    audit_database = AuditDatabase()

    try:
        event = database.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail=f"Event {event_id} not found",
            )

        database.update_status(
            event_id=event_id,
            status="ACKNOWLEDGED",
        )

        audit_database.create_log(
            action="EVENT_ACKNOWLEDGED",
            entity_type="event",
            entity_id=event_id,
            actor="operator",
            details="Security operator acknowledged alert",
        )

        updated_event = database.get_event(event_id)

        return {
            "message": "Event acknowledged",
            "event": dict(updated_event),
        }

    finally:
        database.close()
        audit_database.close()


# ============================================================
# DISPATCH EVENT
# ============================================================

@app.post("/events/{event_id}/dispatch")
def dispatch_event(event_id: int):
    database = EventDatabase()
    audit_database = AuditDatabase()

    try:
        event = database.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail=f"Event {event_id} not found",
            )

        database.update_status(
            event_id=event_id,
            status="DISPATCHED",
        )

        audit_database.create_log(
            action="EVENT_DISPATCHED",
            entity_type="event",
            entity_id=event_id,
            actor="operator",
            details="Security team dispatched",
        )

        updated_event = database.get_event(event_id)

        return {
            "message": "Event dispatched",
            "event": dict(updated_event),
        }

    finally:
        database.close()
        audit_database.close()


# ============================================================
# RESOLVE EVENT
# ============================================================

@app.post("/events/{event_id}/resolve")
def resolve_event(
    event_id: int,
    request: EventStatusUpdate,
):
    database = EventDatabase()
    audit_database = AuditDatabase()

    try:
        event = database.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail=f"Event {event_id} not found",
            )

        database.update_status(
            event_id=event_id,
            status="RESOLVED",
            resolution=request.resolution,
        )

        audit_database.create_log(
            action="EVENT_RESOLVED",
            entity_type="event",
            entity_id=event_id,
            actor="operator",
            details=request.resolution
            or "Security operator resolved event",
        )

        updated_event = database.get_event(event_id)

        return {
            "message": "Event resolved",
            "event": dict(updated_event),
        }

    finally:
        database.close()
        audit_database.close()


# ============================================================
# FALSE POSITIVE
# ============================================================

@app.post("/events/{event_id}/false-positive")
def mark_false_positive(
    event_id: int,
    request: EventStatusUpdate,
):
    database = EventDatabase()
    audit_database = AuditDatabase()

    try:
        event = database.get_event(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail=f"Event {event_id} not found",
            )

        database.update_status(
            event_id=event_id,
            status="FALSE_POSITIVE",
            resolution=request.resolution,
        )

        audit_database.create_log(
            action="EVENT_FALSE_POSITIVE",
            entity_type="event",
            entity_id=event_id,
            actor="operator",
            details=request.resolution
            or "Security operator marked event as false positive",
        )

        updated_event = database.get_event(event_id)

        return {
            "message": "Event marked as false positive",
            "event": dict(updated_event),
        }

    finally:
        database.close()
        audit_database.close()



@app.get("/audit-logs")
def get_audit_logs():
    database = AuditDatabase()

    try:
        logs = database.get_all_logs()

        return {
            "total": len(logs),
            "logs": [dict(log) for log in logs],
        }

    finally:
        database.close()