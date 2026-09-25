from backend.notification_routes import router as notification_router
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from typing import Optional

from fastapi import FastAPI, HTTPException, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database.event_database import EventDatabase
from database.camera_database import CameraDatabase
from database.audit_database import AuditDatabase

from backend.auth_service import (
    AuthService,
    AuthenticationError,
)
from backend.auth_jwt import create_access_token
from backend.camera_schemas import (
    CameraCreateRequest,
    CameraUpdateRequest,
)

from backend.auth_dependencies import (
    get_current_user,
    require_roles,
)

from rules.event_workflow import (
    validate_transition,
    InvalidEventTransitionError,
)


app = FastAPI(
    title="Hotel AI Security API",
    description="Backend API for the Hotel AI CCTV Security System",
    version="0.3.0",
)


# ============================================================
# CORS
# ============================================================

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


# ============================================================
# REQUEST MODELS
# ============================================================


class EventStatusUpdate(BaseModel):
    resolution: Optional[str] = None


def _sanitize_camera_source(source, source_type):
    # Return an operator-safe camera source.
    raw_source = str(source or "")
    if str(source_type or "").strip().lower() != "rtsp":
        return raw_source

    try:
        parsed = urlsplit(raw_source)
    except ValueError:
        return "rtsp://***"

    if not parsed.netloc:
        return raw_source

    authority = parsed.netloc.split("@", 1)[-1]
    safe_netloc = f"***:***@{authority}"

    return urlunsplit(
        (
            parsed.scheme,
            safe_netloc,
            parsed.path,
            "",
            "",
        )
    )


def serialize_camera(camera):
    # Serialize camera data without exposing RTSP credentials.
    data = dict(camera)
    raw_source = data.get("source")
    source_type = data.get("source_type")

    data["source"] = _sanitize_camera_source(
        raw_source,
        source_type,
    )
    data["source_configured"] = bool(
        str(raw_source or "").strip()
    )

    return data


# ============================================================
# EVENT WORKFLOW VALIDATION
# ============================================================


def validate_event_transition(
    current_status: str,
    new_status: str,
) -> None:
    """
    Validate whether an event can move from its current
    status to the requested new status.

    The actual state-machine rules are defined in:
        rules/event_workflow.py

    Invalid transitions are returned to API clients as
    HTTP 409 Conflict responses.
    """

    try:
        validate_transition(
            current_status=current_status,
            new_status=new_status,
        )

    except InvalidEventTransitionError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )


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
# AUTHENTICATION
# ============================================================


@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
):
    auth_service = AuthService()

    try:
        try:
            user = auth_service.authenticate(
                username=username,
                password=password,
            )

        except AuthenticationError as error:
            raise HTTPException(
                status_code=401,
                detail=str(error),
            )

        access_token = create_access_token(user)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user,
        }

    finally:
        auth_service.close()


# ============================================================
# CAMERAS
# ============================================================


@app.get("/cameras")
def get_cameras(
    current_user: dict = Depends(get_current_user),
):
    database = CameraDatabase()

    try:
        cameras = database.get_all_cameras()

        return {
            "total": len(cameras),
            "cameras": [
                serialize_camera(camera)
                for camera in cameras
            ],
        }

    finally:
        database.close()

@app.get("/cameras/health/summary")
def get_camera_health_summary(
    current_user: dict = Depends(get_current_user),
):
    """
    Return fleet-level camera health statistics.

    The CameraDatabase is the single source of truth for
    persisted camera health state.
    """

    database = CameraDatabase()

    try:
        cameras = database.get_all_cameras()

        total_cameras = len(cameras)

        online = sum(
            1
            for camera in cameras
            if camera["status"] == "ONLINE"
        )

        offline = sum(
            1
            for camera in cameras
            if camera["status"] == "OFFLINE"
        )

        if total_cameras == 0:
            health_percentage = 0.0
        else:
            health_percentage = round(
                (online / total_cameras) * 100,
                2,
            )

        return {
            "total_cameras": total_cameras,
            "online": online,
            "offline": offline,
            "health_percentage": health_percentage,
        }

    finally:
        database.close()

@app.post("/cameras")
def create_camera(
    request: CameraCreateRequest,
    current_user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    camera_id = request.camera_id.strip()
    name = request.name.strip()
    location = request.location.strip()
    source = request.source.strip()

    if not camera_id:
        raise HTTPException(
            status_code=422,
            detail="Camera ID is required",
        )
    if not name:
        raise HTTPException(
            status_code=422,
            detail="Camera name is required",
        )
    if not location:
        raise HTTPException(
            status_code=422,
            detail="Camera location is required",
        )
    if not source:
        raise HTTPException(
            status_code=422,
            detail="Camera source is required",
        )

    database = CameraDatabase()
    audit_database = AuditDatabase()

    try:
        try:
            database.create_camera(
                camera_id=camera_id,
                name=name,
                location=location,
                source_type=request.source_type,
                source=source,
                ai_fps=request.ai_fps,
                reconnect_max_attempts=(
                    request.reconnect.max_attempts
                ),
                reconnect_delay_seconds=(
                    request.reconnect.delay_seconds
                ),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Camera {camera_id} already exists.",
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        # Do not write raw source URLs into audit logs because an RTSP
        # URL can contain embedded credentials.
        audit_database.create_log(
            action="CAMERA_CREATED",
            entity_type="camera",
            entity_id=camera_id,
            actor=current_user["username"],
            details=json.dumps(
                {
                    "name": name,
                    "location": location,
                    "source_type": request.source_type,
                    "source_configured": True,
                    "ai_fps": request.ai_fps,
                    "reconnect": {
                        "max_attempts": (
                            request.reconnect.max_attempts
                        ),
                        "delay_seconds": (
                            request.reconnect.delay_seconds
                        ),
                    },
                },
                sort_keys=True,
            ),
        )

        return {
            "message": "Camera created",
            "runner_reload_required": True,
            "camera": serialize_camera(
                database.get_camera(camera_id)
            ),
        }
    finally:
        database.close()
        audit_database.close()


@app.put("/cameras/{camera_id}")
def update_camera(
    camera_id: str,
    request: CameraUpdateRequest,
    current_user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    camera_id = camera_id.strip()
    name = request.name.strip()
    location = request.location.strip()
    source = request.source.strip()

    if not camera_id:
        raise HTTPException(
            status_code=422,
            detail="Camera ID is required",
        )
    if not name:
        raise HTTPException(
            status_code=422,
            detail="Camera name is required",
        )
    if not location:
        raise HTTPException(
            status_code=422,
            detail="Camera location is required",
        )
    if not source:
        raise HTTPException(
            status_code=422,
            detail="Camera source is required",
        )

    database = CameraDatabase()
    audit_database = AuditDatabase()

    try:
        existing = database.get_camera(camera_id)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"Camera {camera_id} not found",
            )

        previous = {
            "name": existing["name"],
            "location": existing["location"],
            "source_type": existing["source_type"],
            "source_configured": bool(
                str(existing["source"] or "").strip()
            ),
            "ai_fps": existing["ai_fps"],
            "reconnect": {
                "max_attempts": (
                    existing["reconnect_max_attempts"]
                ),
                "delay_seconds": (
                    existing["reconnect_delay_seconds"]
                ),
            },
        }

        try:
            database.update_camera_configuration(
                camera_id=camera_id,
                name=name,
                location=location,
                source_type=request.source_type,
                source=source,
                ai_fps=request.ai_fps,
                reconnect_max_attempts=(
                    request.reconnect.max_attempts
                ),
                reconnect_delay_seconds=(
                    request.reconnect.delay_seconds
                ),
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        audit_database.create_log(
            action="CAMERA_UPDATED",
            entity_type="camera",
            entity_id=camera_id,
            actor=current_user["username"],
            details=json.dumps(
                {
                    "before": previous,
                    "after": {
                        "name": name,
                        "location": location,
                        "source_type": request.source_type,
                        "source_configured": True,
                        "ai_fps": request.ai_fps,
                        "reconnect": {
                            "max_attempts": (
                                request.reconnect.max_attempts
                            ),
                            "delay_seconds": (
                                request.reconnect.delay_seconds
                            ),
                        },
                    },
                },
                sort_keys=True,
            ),
        )

        return {
            "message": "Camera updated",
            "runner_reload_required": True,
            "camera": serialize_camera(
                database.get_camera(camera_id)
            ),
        }
    finally:
        database.close()
        audit_database.close()


@app.delete("/cameras/{camera_id}")
def delete_camera(
    camera_id: str,
    current_user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    camera_id = camera_id.strip()
    database = CameraDatabase()
    audit_database = AuditDatabase()

    try:
        existing = database.get_camera(camera_id)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"Camera {camera_id} not found",
            )

        snapshot = {
            "name": existing["name"],
            "location": existing["location"],
            "source_type": existing["source_type"],
            "source_configured": bool(
                str(existing["source"] or "").strip()
            ),
            "ai_fps": existing["ai_fps"],
            "reconnect": {
                "max_attempts": (
                    existing["reconnect_max_attempts"]
                ),
                "delay_seconds": (
                    existing["reconnect_delay_seconds"]
                ),
            },
        }

        try:
            database.delete_camera(camera_id)
        except ValueError as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error

        audit_database.create_log(
            action="CAMERA_DELETED",
            entity_type="camera",
            entity_id=camera_id,
            actor=current_user["username"],
            details=json.dumps(
                snapshot,
                sort_keys=True,
            ),
        )

        return {
            "message": "Camera deleted",
            "runner_reload_required": True,
            "camera_id": camera_id,
        }
    finally:
        database.close()
        audit_database.close()


@app.get("/cameras/{camera_id}")
def get_camera(
    camera_id: str,
    current_user: dict = Depends(get_current_user),
):
    database = CameraDatabase()

    try:
        camera = database.get_camera(camera_id)

        if camera is None:
            raise HTTPException(
                status_code=404,
                detail=f"Camera {camera_id} not found",
            )

        return serialize_camera(camera)

    finally:
        database.close()


@app.get("/cameras/{camera_id}/health")
def get_camera_health(
    camera_id: str,
    current_user: dict = Depends(get_current_user),
):
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

@app.get("/event-quality")
def get_event_quality(
    current_user: dict = Depends(get_current_user),
):
    database = EventDatabase()

    try:
        return database.get_event_quality_metrics()

    finally:
        database.close()




@app.get("/events")
def get_events(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    camera_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
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
def get_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
):
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
def get_event_evidence(
    event_id: int,
    current_user: dict = Depends(get_current_user),
):
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
def acknowledge_event(
    event_id: int,
    current_user: dict = Depends(
        require_roles(
            "ADMIN",
            "SECURITY_OPERATOR",
        )
    ),
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

        # Validate state transition before modifying database.
        validate_event_transition(
            current_status=event["status"],
            new_status="ACKNOWLEDGED",
        )

        database.update_status(
            event_id=event_id,
            status="ACKNOWLEDGED",
        )

        audit_database.create_log(
            action="EVENT_ACKNOWLEDGED",
            entity_type="event",
            entity_id=event_id,
            actor=current_user["username"],
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
def dispatch_event(
    event_id: int,
    current_user: dict = Depends(
        require_roles(
            "ADMIN",
            "SECURITY_OPERATOR",
        )
    ),
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

        # Validate state transition before modifying database.
        validate_event_transition(
            current_status=event["status"],
            new_status="DISPATCHED",
        )

        database.update_status(
            event_id=event_id,
            status="DISPATCHED",
        )

        audit_database.create_log(
            action="EVENT_DISPATCHED",
            entity_type="event",
            entity_id=event_id,
            actor=current_user["username"],
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
    current_user: dict = Depends(
        require_roles(
            "ADMIN",
            "SECURITY_OPERATOR",
        )
    ),
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

        # Validate state transition before modifying database.
        validate_event_transition(
            current_status=event["status"],
            new_status="RESOLVED",
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
            actor=current_user["username"],
            details=(
                request.resolution
                or "Security operator resolved event"
            ),
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
    current_user: dict = Depends(
        require_roles(
            "ADMIN",
            "SECURITY_OPERATOR",
        )
    ),
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

        # Validate state transition before modifying database.
        validate_event_transition(
            current_status=event["status"],
            new_status="FALSE_POSITIVE",
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
            actor=current_user["username"],
            details=(
                request.resolution
                or "Security operator marked event as false positive"
            ),
        )

        updated_event = database.get_event(event_id)

        return {
            "message": "Event marked as false positive",
            "event": dict(updated_event),
        }

    finally:
        database.close()
        audit_database.close()


# ============================================================
# AUDIT LOGS
# ============================================================


@app.get("/audit-logs")
def get_audit_logs(
    current_user: dict = Depends(get_current_user),
):
    database = AuditDatabase()

    try:
        logs = database.get_all_logs()

        return {
            "total": len(logs),
            "logs": [dict(log) for log in logs],
        }

    finally:
        database.close()

app.include_router(notification_router)
