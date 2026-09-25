import json
import os
from pathlib import Path

import cv2
import numpy as np

from ai.person_detector import PersonDetector
from ai.tracker import PersonTracker
from ai.fall_event_processor import FallEventProcessor
from ai.fire_smoke_event_processor import FireSmokeEventProcessor
from ai.fire_smoke_vision_adapter import FireSmokeVisionAdapter
from ai.weapon_event_processor import WeaponEventProcessor
from ai.weapon_vision_adapter import (
    WEAPON_MODEL_SHA256,
    WEAPON_MODEL_VERSION,
    WeaponVisionAdapter,
)
from ai.zone_detector import ZoneDetector
from ai.camera_health import (
    CameraHealthMonitor,
    CAMERA_OFFLINE,
    CAMERA_RECOVERED,
)
from ai.camera_health_events import (
    CameraHealthEventService,
)
from ai.evidence_recorder import EvidenceRecorder

from database.event_database import EventDatabase
from database.camera_database import (
    BOOTSTRAP_METADATA_KEY,
    CameraDatabase,
)
from notifications.dispatcher import NotificationDispatcher
from notifications.providers import ConsoleNotificationProvider

from rules.intrusion_rules import IntrusionRule
from rules.crowding_rules import CrowdingRule
from rules.after_hours_rules import AfterHoursRule

from video.camera_config import (
    load_camera_configs,
    load_camera_configs_from_database,
)
from video.frame_sampler import FrameSampler
from video.source_factory import create_video_source
from video.camera_manager import CameraManager
from video.camera_worker_pool import CameraWorkerPool


# ============================================================
# Configuration
# ============================================================

CAMERA_CONFIG_PATH = "configs/cameras.json"
ZONE_PATH = "configs/zones.json"
OUTPUT_DIRECTORY = "data/output"
EVIDENCE_DIRECTORY = "data/output/events"

PRE_EVENT_SECONDS = 5
POST_EVENT_SECONDS = 5

CAMERA_FAILURE_THRESHOLD = 3

CAMERA_HEALTH_MODEL_VERSION = "camera-health-v1"
INTRUSION_MODEL_VERSION = "prototype-v1"
CROWDING_MODEL_VERSION = "crowding-rule-v1"
AFTER_HOURS_MODEL_VERSION = "after-hours-rule-v1"
FALL_MODEL_VERSION = "fall-heuristic-v1"
FIRE_SMOKE_MODEL_PATH = Path("data/models/fire_smoke/cctv_yolov8n/best.onnx")
FIRE_SMOKE_MODEL_VERSION = "fire-smoke-event-v1"
WEAPON_MODEL_PATH = Path("data/models/weapon/gun-knife-yolo11n/best.onnx")
RULES_CONFIG_PATH = "configs/rules.json"


# ============================================================
# Utility functions
# ============================================================

def load_zones(path):
    """Load configured security zones from JSON."""

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        config = json.load(file)

    return config["zones"]


def load_rule_config(path):
    """Load configurable security-rule settings from JSON."""

    with open(path, "r", encoding="utf-8-sig") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("Rule configuration root must be an object.")

    return config


def get_event_model_version(event_type):
    """Return the model/rule version associated with an event."""

    if event_type == "FALL":
        return FALL_MODEL_VERSION
    if event_type in {"FIRE", "SMOKE"}:
        return FIRE_SMOKE_MODEL_VERSION
    if event_type == "WEAPON":
        return WEAPON_MODEL_VERSION
    if event_type == "CROWDING":
        return CROWDING_MODEL_VERSION
    if event_type == "AFTER_HOURS":
        return AFTER_HOURS_MODEL_VERSION
    return INTRUSION_MODEL_VERSION


def get_capture_metadata(source):
    """
    Read video metadata from the underlying OpenCV capture.

    Returns:
        source_fps, total_frames, width, height
    """

    capture = getattr(
        source,
        "capture",
        None,
    )

    if capture is None:
        raise RuntimeError(
            "Video source has no active capture."
        )

    source_fps = float(
        capture.get(
            cv2.CAP_PROP_FPS
        )
    )

    total_frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    return (
        source_fps,
        total_frames,
        width,
        height,
    )


def normalize_source_fps(source_fps):
    """
    Ensure a usable FPS value.

    RTSP streams may report 0 or an invalid FPS.
    """

    if source_fps <= 0:
        return 25.0

    return source_fps


def is_finite_source(camera_config):
    """Return True for recorded/file sources."""

    return (
        camera_config.source_type.lower().strip()
        == "file"
    )



# ============================================================
# Per-camera processing
# ============================================================

def process_camera(
    camera_config,
    camera_manager,
    detector,
    zones,
    zone_detector,
    event_database,
    camera_database,
    camera_health_events,
    notification_dispatcher,
    fire_smoke_detection_provider=None,
    fire_smoke_event_processor=None,
    weapon_detection_provider=None,
    weapon_event_processor=None,
    crowding_config=None,
    after_hours_config=None,
    after_hours_now_provider=None,
):
    """
    Process one configured camera from the shared CameraManager.

    All stateful components are created per camera so tracker,
    intrusion persistence, frame sampling, camera health, evidence,
    and output video cannot leak state between cameras.

    Returns:
        dict containing camera-level processing metrics.
    """

    camera_id = camera_config.camera_id
    source = camera_manager.get_source(camera_id)
    finite_source = is_finite_source(camera_config)

    writer = None
    evidence_recorder = None

    frame_index = 0
    ai_frames = 0
    total_events = 0
    output_path = None
    camera_error = None

    # --------------------------------------------------------
    # Per-camera stateful components
    # --------------------------------------------------------

    tracker = PersonTracker()

    intrusion_rule = IntrusionRule(
        persistence_frames=3
    )

    fall_event_processor = FallEventProcessor(
        persistence_frames=3,
        min_horizontal_aspect_ratio=1.5,
    )

    if fire_smoke_event_processor is None:
        fire_smoke_event_processor = FireSmokeEventProcessor(
            persistence_frames=3,
            min_confidence=0.50,
            region_tolerance=75.0,
        )

    if weapon_event_processor is None:
        weapon_event_processor = WeaponEventProcessor(
            persistence_frames=3,
            min_confidence=0.50,
            region_tolerance=75.0,
            track_association_tolerance=100.0,
        )

    crowding_rule = None
    if crowding_config is not None and crowding_config.get("enabled", True):
        crowding_rule = CrowdingRule(
            minimum_people=int(crowding_config.get("minimum_people", 5)),
            persistence_frames=int(crowding_config.get("persistence_frames", 3)),
        )

    after_hours_rule = None
    if after_hours_config is not None and after_hours_config.get(
        "enabled",
        False,
    ):
        after_hours_rule = AfterHoursRule(
            camera_id=camera_id,
            config=after_hours_config,
            available_zone_ids={
                str(zone["zone_id"])
                for zone in zones
            },
            now_provider=after_hours_now_provider,
        )

    camera_health = CameraHealthMonitor(
        camera_id=camera_id,
        database=camera_database,
        failure_threshold=CAMERA_FAILURE_THRESHOLD,
    )

    try:
        # ----------------------------------------------------
        # Read source metadata
        # ----------------------------------------------------

        (
            source_fps,
            total_frames,
            width,
            height,
        ) = get_capture_metadata(source)

        source_fps = normalize_source_fps(
            source_fps
        )

        duration = (
            total_frames / source_fps
            if finite_source
            and total_frames > 0
            else 0
        )

        print("=" * 60)
        print(
            f"CAMERA START: {camera_config.name}"
        )
        print("=" * 60)

        print(
            f"Camera ID    : {camera_id}"
        )
        print(
            f"Location     : {camera_config.location}"
        )
        print(
            f"Source type  : {camera_config.source_type}"
        )
        print(
            f"Resolution   : {width} x {height}"
        )
        print(
            f"Source FPS   : {source_fps:.2f}"
        )

        if finite_source:
            print(
                f"Frames       : {total_frames}"
            )
            print(
                f"Duration     : {duration:.2f}s"
            )
        else:
            print(
                "Frames       : continuous RTSP stream"
            )
            print(
                "Duration     : continuous"
            )

        # ----------------------------------------------------
        # Frame sampler
        # ----------------------------------------------------

        sampler = FrameSampler(
            source_fps=source_fps,
            target_fps=camera_config.ai_fps,
        )

        print(
            f"AI FPS       : "
            f"{sampler.target_fps:.2f}"
        )

        # ----------------------------------------------------
        # Camera registration / health state
        # ----------------------------------------------------

        camera = camera_database.get_camera(
            camera_id
        )

        if camera is None:
            raise RuntimeError(
                f"Camera {camera_id} is not registered."
            )

        print(
            f"Camera registered: "
            f"{camera['name']} "
            f"({camera['location']})"
        )

        print(
            f"Camera health monitor initialized: "
            f"{camera_id}"
        )

        print(
            f"Failure threshold: "
            f"{CAMERA_FAILURE_THRESHOLD}"
        )

        print(
            f"Persisted status: "
            f"{camera['status']}"
        )

        print(
            f"Persisted failures: "
            f"{camera['consecutive_failures']}"
        )

        # ----------------------------------------------------
        # Evidence recorder
        # ----------------------------------------------------

        evidence_recorder = EvidenceRecorder(
            output_directory=EVIDENCE_DIRECTORY,
            fps=source_fps,
            pre_event_seconds=PRE_EVENT_SECONDS,
            post_event_seconds=POST_EVENT_SECONDS,
        )

        print(
            "Evidence recorder initialized."
        )

        print(
            f"Evidence directory: "
            f"{EVIDENCE_DIRECTORY}"
        )

        print(
            f"Pre-event window: "
            f"{PRE_EVENT_SECONDS}s"
        )

        print(
            f"Post-event window: "
            f"{POST_EVENT_SECONDS}s"
        )

        # ----------------------------------------------------
        # Output video
        # ----------------------------------------------------

        Path(
            OUTPUT_DIRECTORY
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path = str(
            Path(OUTPUT_DIRECTORY)
            / f"{camera_id}_intrusion_detection.mp4"
        )

        fourcc = cv2.VideoWriter_fourcc(
            *"mp4v"
        )

        writer = cv2.VideoWriter(
            output_path,
            fourcc,
            source_fps,
            (width, height),
        )

        if not writer.isOpened():
            raise RuntimeError(
                f"Could not create output video: "
                f"{output_path}"
            )

        print(
            f"Output       : "
            f"{output_path}"
        )

        print("-" * 60)
        print(
            "Processing..."
        )
        print("-" * 60)

        # ----------------------------------------------------
        # Main processing loop
        # ----------------------------------------------------

        while True:

            frame = source.read()

            # ------------------------------------------------
            # Camera health monitoring
            # ------------------------------------------------

            if frame is None:

                # ------------------------------------------------
                # Finite file source:
                #
                # None means the recorded video reached EOF.
                # This is normal completion and must NOT affect
                # camera health.
                # ------------------------------------------------

                if finite_source:

                    print(
                        f"[END OF STREAM] "
                        f"Camera={camera_id} "
                        "Recorded video reached EOF."
                    )

                    break

                # ------------------------------------------------
                # Continuous RTSP source:
                #
                # None means the source could not provide a frame
                # after its internal reconnect attempts.
                # Treat this as an actual camera failure.
                # ------------------------------------------------

                transition = camera_health.frame_failed(
                    error=(
                        "No frame received "
                        "from video source"
                    )
                )

                failure_count = (
                    camera_health.get_failure_count()
                )

                print(
                    f"[CAMERA FAILURE] "
                    f"Camera={camera_id} "
                    f"ConsecutiveFailures="
                    f"{failure_count}"
                )

                # --------------------------------------------
                # OFFLINE transition
                # --------------------------------------------

                if transition == CAMERA_OFFLINE:

                    offline_event_id = (
                        camera_health_events
                        .create_offline_event(
                            camera_id=camera_id,
                            error=(
                                "No frame received "
                                "from video source"
                            ),
                        )
                    )

                    total_events += 1

                    # --------------------------------------------
                    # Notify security operator about camera outage
                    # --------------------------------------------

                    try:

                        notification_future = (
                            notification_dispatcher.notify_event(
                                event_id=offline_event_id,
                                severity="HIGH",
                                recipient=None,
                                subject=(
                                    "Hotel Camera Offline - "
                                    f"{camera_id}"
                                ),
                                message=(
                                    f"Camera {camera_id} is offline. "
                                    f"The camera exceeded the configured "
                                    f"failure threshold of "
                                    f"{camera_health.failure_threshold} "
                                    f"consecutive failures."
                                ),
                            )
                        )

                        print(
                            f"[CAMERA OFFLINE NOTIFICATION QUEUED] "
                            f"Camera={camera_id} "
                            f"EventID={offline_event_id} "
                            f"Future={notification_future}"
                        )

                    except Exception as notification_error:

                        # Notification failure must never stop
                        # CCTV processing.
                        print(
                            f"[NOTIFICATION WARNING] "
                            f"Camera={camera_id} "
                            f"Camera offline notification failed: "
                            f"{notification_error}"
                        )

                    print(
                        f"[CAMERA OFFLINE] "
                        f"Camera={camera_id} "
                        f"FailureThreshold="
                        f"{camera_health.failure_threshold} "
                        f"EventID={offline_event_id}"
                    )

                elif camera_health.is_offline():

                    print(
                        f"[CAMERA OFFLINE] "
                        f"Camera={camera_id} "
                        "Offline state already persisted. "
                        "No duplicate event created."
                    )

                else:

                    print(
                        f"[CAMERA FAILURE] "
                        f"Camera={camera_id} "
                        "Waiting for failure threshold..."
                    )

                # RTSP failure: keep monitoring for recovery.
                continue

            # ------------------------------------------------
            # Valid frame received
            # ------------------------------------------------

            previous_failure_count = (
                camera_health.get_failure_count()
            )

            transition = camera_health.frame_received(
                fps=source_fps,
                width=width,
                height=height,
            )

            # ------------------------------------------------
            # CAMERA RECOVERED transition
            # ------------------------------------------------

            if transition == CAMERA_RECOVERED:

                recovered_event_id = (
                    camera_health_events
                    .create_recovered_event(
                        camera_id=camera_id
                    )
                )

                total_events += 1

                print(
                    f"[CAMERA RECOVERED] "
                    f"Camera={camera_id} "
                    f"PreviousFailures="
                    f"{previous_failure_count} "
                    f"EventID={recovered_event_id}"
                )

            # ------------------------------------------------
            # Add every frame to evidence recorder
            # ------------------------------------------------

            evidence_recorder.add_frame(
                frame
            )

            # ------------------------------------------------
            # Frame sampling
            # ------------------------------------------------

            process_with_ai = (
                sampler.should_process()
            )

            if process_with_ai:

                ai_frames += 1

                # --------------------------------------------
                # Person detection
                # --------------------------------------------

                detections = detector.detect(
                    frame
                )

                # --------------------------------------------
                # Person tracking
                # --------------------------------------------

                tracks = tracker.update(
                    detections
                )

                # --------------------------------------------
                # Zone detection
                # --------------------------------------------

                zone_results = (
                    zone_detector.check_tracks(
                        tracks
                    )
                )

                # --------------------------------------------
                # Intrusion rule
                # --------------------------------------------

                intrusion_events = intrusion_rule.evaluate(
                    zone_results
                )

                # --------------------------------------------
                # Crowd occupancy rule
                # --------------------------------------------

                crowding_events = []
                if crowding_rule is not None:
                    crowding_events = crowding_rule.evaluate(tracks)

                # --------------------------------------------
                # After-hours presence rule
                # --------------------------------------------

                after_hours_events = []
                if after_hours_rule is not None:
                    after_hours_events = after_hours_rule.evaluate(
                        tracks,
                        zone_results,
                    )

                # --------------------------------------------
                # Fall / person-down analysis
                # --------------------------------------------

                fall_events = fall_event_processor.evaluate(
                    tracks
                )

                # --------------------------------------------
                # Fire / Smoke analysis
                # --------------------------------------------

                fire_smoke_events = []

                if fire_smoke_detection_provider is not None:

                    fire_smoke_detections = (
                        fire_smoke_detection_provider(
                            frame
                        )
                    )

                    fire_smoke_events = (
                        fire_smoke_event_processor.evaluate(
                            fire_smoke_detections
                        )
                    )

                # --------------------------------------------
                # Weapon analysis
                # --------------------------------------------

                weapon_events = []

                if weapon_detection_provider is not None:
                    weapon_detections = weapon_detection_provider(
                        frame
                    )
                    weapon_events = weapon_event_processor.evaluate(
                        weapon_detections,
                        tracks,
                    )

                # All event types use the same downstream
                # persistence, evidence, database, and
                # notification pipeline.
                events = (
                    intrusion_events
                    + crowding_events
                    + after_hours_events
                    + fall_events
                    + fire_smoke_events
                    + weapon_events
                )

                # --------------------------------------------
                # Draw zones
                # --------------------------------------------

                for zone in zones:

                    polygon = np.array(
                        zone["points"],
                        dtype=np.int32,
                    )

                    cv2.polylines(
                        frame,
                        [polygon],
                        True,
                        (0, 255, 255),
                        3,
                    )

                    x, y = polygon[0]

                    cv2.putText(
                        frame,
                        zone["name"],
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 255),
                        2,
                    )

                # --------------------------------------------
                # Draw tracked people
                # --------------------------------------------

                for track in tracks:

                    x1, y1, x2, y2 = (
                        track["box"]
                    )

                    track_id = track[
                        "track_id"
                    ]

                    state = track[
                        "state"
                    ]

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2,
                    )

                    label = (
                        f"Person {track_id} "
                        f"| {state}"
                    )

                    cv2.putText(
                        frame,
                        label,
                        (
                            x1,
                            max(
                                30,
                                y1 - 10,
                            ),
                        ),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )

                # --------------------------------------------
                # Process intrusion events
                # --------------------------------------------

                for event in events:

                    total_events += 1

                    # ----------------------------------------
                    # Create event in database
                    # ----------------------------------------

                    event_id = (
                        event_database.create_event(
                            event_type=event[
                                "event_type"
                            ],
                            severity=event[
                                "severity"
                            ],
                            camera_id=camera_id,
                            zone_id=event.get(
                                "zone_id"
                            ),
                            zone_name=event.get(
                                "zone_name"
                            ),
                            track_id=event.get(
                                "track_id"
                            ),
                            message=event[
                                "message"
                            ],
                            model_version=get_event_model_version(
                                event["event_type"]
                            ),
                            evidence_path=None,
                        )
                    )

                    # ----------------------------------------
                    # Start evidence capture
                    # ----------------------------------------
                    #
                    # Evidence is an important security artifact,
                    # but an unexpected recorder failure must not
                    # terminate the live camera worker. The event
                    # has already been persisted in the database,
                    # so processing can continue without evidence.
                    # ----------------------------------------

                    evidence_path = None

                    try:

                        evidence_path = (
                            evidence_recorder
                            .start_event_capture(
                                event_type=event[
                                    "event_type"
                                ],
                                event_id=event_id,
                            )
                        )

                    except Exception as evidence_error:

                        print(
                            f"[EVIDENCE ERROR] "
                            f"EventID={event_id} "
                            f"Error={evidence_error}"
                        )

                    # ----------------------------------------
                    # Save evidence path
                    # ----------------------------------------

                    if evidence_path is not None:

                        try:

                            event_database.update_evidence_path(
                                event_id=event_id,
                                evidence_path=str(
                                    evidence_path
                                ),
                            )

                        except Exception as evidence_database_error:

                            print(
                                f"[EVIDENCE PATH ERROR] "
                                f"EventID={event_id} "
                                f"Error={evidence_database_error}"
                            )

                    # ----------------------------------------
                    # Send security notification
                    # ----------------------------------------
                    #
                    # Notification failure must never stop
                    # the CCTV processing worker.
                    # ----------------------------------------

                    try:

                        notification_future = (
                            notification_dispatcher.notify_event(
                                event_id=event_id,
                                severity=event["severity"],
                                recipient=None,
                                subject=(
                                    f"Hotel Security Alert - "
                                    f"{event['event_type']}"
                                ),
                                message=(
                                    f"Camera {camera_id}: "
                                    f"{event['message']}"
                                ),
                            )
                        )

                        print(
                            f"[NOTIFICATION QUEUED] "
                            f"EventID={event_id} "
                            f"Future={notification_future}"
                        )

                    except Exception as notification_error:

                        print(
                            f"[NOTIFICATION ERROR] "
                            f"EventID={event_id} "
                            f"Error={notification_error}"
                        )

                    # ----------------------------------------
                    # Log event
                    # ----------------------------------------

                    print(
                        f"[{event['event_type']} EVENT] "
                        f"Camera={camera_id} "
                        f"Frame={frame_index} "
                        f"EventID={event_id} "
                        f"Track={event['track_id']} "
                        f"Zone={event.get('zone_name') or 'N/A'} "
                        f"Severity={event['severity']} "
                        f"Status=NEW"
                    )

                    if evidence_path is not None:

                        print(
                            f"[EVIDENCE STARTED] "
                            f"Camera={camera_id} "
                            f"EventID={event_id} "
                            f"Path={evidence_path}"
                        )

                    else:

                        print(
                            f"[EVIDENCE WARNING] "
                            f"Camera={camera_id} "
                            f"EventID={event_id} "
                            f"Evidence capture "
                            f"could not be started."
                        )

                    # ----------------------------------------
                    # Display security alert
                    # ----------------------------------------

                    if event["event_type"] == "CROWDING":
                        alert_text = "!!! CROWDING DETECTED !!!"
                    elif event["event_type"] == "AFTER_HOURS":
                        alert_text = "!!! AFTER-HOURS PRESENCE DETECTED !!!"
                    elif event["event_type"] == "FALL":
                        alert_text = "!!! FALL / PERSON DOWN DETECTED !!!"
                    else:
                        alert_text = "!!! INTRUSION DETECTED !!!"

                    cv2.putText(
                        frame,
                        alert_text,
                        (50, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 0, 255),
                        3,
                    )

                    cv2.putText(
                        frame,
                        event["message"],
                        (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2,
                    )

            # ------------------------------------------------
            # Write processed frame
            # ------------------------------------------------

            writer.write(
                frame
            )

            frame_index += 1

            # ------------------------------------------------
            # Progress for finite video
            # ------------------------------------------------

            if (
                finite_source
                and total_frames > 0
            ):

                progress_interval = max(
                    1,
                    total_frames // 10,
                )

                if (
                    frame_index
                    % progress_interval
                    == 0
                ):

                    progress = (
                        frame_index
                        / total_frames
                        * 100
                    )

                    print(
                        f"Progress: "
                        f"{progress:.1f}%"
                    )

            else:

                if (
                    frame_index % 100
                    == 0
                ):

                    print(
                        f"Frames processed: "
                        f"Camera={camera_id} "
                        f"{frame_index} | "
                        f"AI frames: "
                        f"{ai_frames}"
                    )

    except Exception as error:
        camera_error = str(error)

        print(
            f"[CAMERA ERROR] "
            f"Camera={camera_id} "
            f"{error}"
        )

    finally:

        # ----------------------------------------------------
        # Finalize evidence recording
        # ----------------------------------------------------

        if evidence_recorder is not None:

            try:

                evidence_recorder.finalize()

            except Exception as error:

                print(
                    f"[CLEANUP WARNING] "
                    f"Camera={camera_id} "
                    f"Evidence finalization failed: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Release writer
        # ----------------------------------------------------

        if writer is not None:

            try:

                writer.release()

            except Exception as error:

                print(
                    f"[CLEANUP WARNING] "
                    f"Camera={camera_id} "
                    f"Video writer release failed: "
                    f"{error}"
                )

    print("-" * 60)

    if camera_error is None:
        print(
            f"CAMERA COMPLETE: {camera_id}"
        )
    else:
        print(
            f"CAMERA FAILED: {camera_id}"
        )

    print(
        f"Total frames : {frame_index}"
    )

    print(
        f"AI frames    : {ai_frames}"
    )

    print(
        f"Events       : {total_events}"
    )

    if output_path is not None:
        print(
            f"Output       : {output_path}"
        )

    print("-" * 60)

    return {
        "camera_id": camera_id,
        "name": camera_config.name,
        "frames": frame_index,
        "ai_frames": ai_frames,
        "events": total_events,
        "output_path": output_path,
        "error": camera_error,
    }


# ============================================================
# Concurrent camera worker
# ============================================================

def process_camera_worker(
    camera_config,
    camera_manager,
    detector,
    zones,
    zone_detector,
    notification_dispatcher=None,
    fire_smoke_detection_provider=None,
    fire_smoke_event_processor=None,
    weapon_detection_provider=None,
    weapon_event_processor=None,
    crowding_config=None,
    after_hours_config=None,
    after_hours_now_provider=None,
):
    """
    Process one camera inside a worker thread.

    SQLite connections are created inside the worker so they
    are never shared across worker threads.
    """

    event_database = None
    camera_database = None

    try:
        event_database = EventDatabase(
            "database/hotel_security.db"
        )

        camera_database = CameraDatabase(
            "database/hotel_security.db"
        )

        camera_health_events = CameraHealthEventService(
            event_database=event_database
        )

        return process_camera(
            camera_config=camera_config,
            camera_manager=camera_manager,
            detector=detector,
            zones=zones,
            zone_detector=zone_detector,
            event_database=event_database,
            camera_database=camera_database,
            camera_health_events=camera_health_events,
            notification_dispatcher=notification_dispatcher,
            fire_smoke_detection_provider=(
                fire_smoke_detection_provider
            ),
            fire_smoke_event_processor=(
                fire_smoke_event_processor
            ),
            weapon_detection_provider=(
                weapon_detection_provider
            ),
            weapon_event_processor=(
                weapon_event_processor
            ),
            crowding_config=crowding_config,
            after_hours_config=after_hours_config,
            after_hours_now_provider=after_hours_now_provider,
        )

    finally:
        if event_database is not None:
            event_database.close()

        if camera_database is not None:
            camera_database.close()



# ============================================================
# Main fleet orchestration
# ============================================================

def main():

    print("=" * 60)
    print("HOTEL AI CCTV - MULTI-CAMERA INTRUSION DETECTION")
    print("=" * 60)

    camera_manager = None
    camera_database = None
    event_database = None
    notification_dispatcher = None
    weapon_adapter = None
    fire_smoke_adapter = None

    results = []

    try:

        # ----------------------------------------------------
        # Shared camera database
        #
        # The database is authoritative after one-time bootstrap.
        # JSON is read only when bootstrap has not completed.
        # ----------------------------------------------------

        camera_database = CameraDatabase(
            "database/hotel_security.db"
        )

        if camera_database.get_metadata(
            BOOTSTRAP_METADATA_KEY
        ) != "1":
            bootstrap_camera_configs = load_camera_configs(
                CAMERA_CONFIG_PATH
            )

            if not bootstrap_camera_configs:
                raise RuntimeError(
                    "No bootstrap cameras configured."
                )

            camera_database.initialize_from_bootstrap(
                bootstrap_camera_configs
            )

        camera_configs = load_camera_configs_from_database(
            camera_database
        )

        if not camera_configs:
            raise RuntimeError(
                "No cameras configured in the camera database."
            )

        print(
            f"Configured cameras: "
            f"{len(camera_configs)}"
        )

        # ----------------------------------------------------
        # Camera manager
        # ----------------------------------------------------

        camera_manager = CameraManager(
            camera_configs
        )

        print(
            f"Camera manager initialized: "
            f"{len(camera_manager)} cameras"
        )

        # ----------------------------------------------------
        # Shared stateless AI components
        # ----------------------------------------------------

        detector = PersonDetector()

        # ------------------------------------------------
        # Optional shared Fire/Smoke vision adapter.
        #
        # The ONNX model/session is shared across cameras.
        # FireSmokeEventProcessor remains camera-local because
        # it contains temporal persistence state.
        #
        # Explicit opt-in prevents the prototype model from
        # becoming active accidentally in deployments where
        # commercial licensing has not yet been cleared.
        # ------------------------------------------------

        enable_fire_smoke = (
            os.environ.get(
                "ENABLE_FIRE_SMOKE",
                "0",
            ).strip().lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

        if enable_fire_smoke:

            if not FIRE_SMOKE_MODEL_PATH.exists():
                raise RuntimeError(
                    "Fire/Smoke model not found: "
                    f"{FIRE_SMOKE_MODEL_PATH}"
                )

            fire_smoke_adapter = FireSmokeVisionAdapter(
                model_path=FIRE_SMOKE_MODEL_PATH,
                confidence_threshold=0.50,
            )

            providers = (
                fire_smoke_adapter.session.get_providers()
                if fire_smoke_adapter.session is not None
                else []
            )

            print(
                "Fire/Smoke adapter enabled."
            )

            print(
                f"Fire/Smoke model: "
                f"{FIRE_SMOKE_MODEL_PATH}"
            )

            print(
                f"Fire/Smoke providers: "
                f"{providers}"
            )

            if (
                "CUDAExecutionProvider"
                not in providers
            ):
                raise RuntimeError(
                    "Fire/Smoke adapter did not initialize "
                    "with CUDAExecutionProvider."
                )

        else:

            print(
                "Fire/Smoke adapter disabled "
                "(set ENABLE_FIRE_SMOKE=1 to enable)."
            )

        # ------------------------------------------------
        # ------------------------------------------------
        # Optional shared ONNX weapon adapter.
        # Activation is explicit and hash-pinned.
        # ------------------------------------------------

        enable_weapon = (
            os.environ.get("ENABLE_WEAPON", "0").strip().lower()
            in {"1", "true", "yes", "on"}
        )

        if enable_weapon:
            if not WEAPON_MODEL_PATH.exists():
                raise RuntimeError(
                    "Weapon model not found: "
                    f"{WEAPON_MODEL_PATH}"
                )

            weapon_adapter = WeaponVisionAdapter(
                model_path=WEAPON_MODEL_PATH,
                confidence_threshold=0.50,
                expected_sha256=WEAPON_MODEL_SHA256,
            )

            print("Weapon adapter enabled.")
            print(f"Weapon model: {WEAPON_MODEL_PATH}")
            print(
                f"Weapon providers: "
                f"{weapon_adapter.execution_providers}"
            )
            print(f"Weapon model version: {WEAPON_MODEL_VERSION}")
        else:
            print(
                "Weapon adapter disabled "
                "(set ENABLE_WEAPON=1 to enable)."
            )

        zones = load_zones(
            ZONE_PATH
        )

        rule_config = load_rule_config(RULES_CONFIG_PATH)
        crowding_config = rule_config.get("crowding", {})
        if not isinstance(crowding_config, dict):
            raise ValueError("'crowding' rule configuration must be an object.")

        after_hours_config = rule_config.get("after_hours", {})
        if not isinstance(after_hours_config, dict):
            raise ValueError("'after_hours' rule configuration must be an object.")

        print(f"Crowding rule configuration: {crowding_config}")
        print(f"After-hours rule configuration: {after_hours_config}")

        zone_detector = ZoneDetector(
            zones
        )

        print(
            "Shared detector loaded."
        )

        print(
            "Shared zone detector loaded."
        )

        print(
            f"Zones loaded: {len(zones)}"
        )

        for zone in zones:
            print(
                f"  - {zone['zone_id']}: "
                f"{zone['name']}"
            )

        # ----------------------------------------------------
        # Shared databases
        # ----------------------------------------------------

        event_database = EventDatabase(
            "database/hotel_security.db"
        )

        camera_health_events = CameraHealthEventService(
            event_database=event_database
        )

        notification_dispatcher = NotificationDispatcher(
            providers={
                "CONSOLE": ConsoleNotificationProvider(),
            },
            database_path="database/hotel_security.db",
            max_workers=2,
            max_retries=2,
        )

        print(
            "Event database initialized."
        )

        print(
            "Camera database initialized."
        )

        print(
            "Camera health event service loaded."
        )

        # ----------------------------------------------------
        # ----------------------------------------------------
        # Reconcile configured cameras with the camera database.
        #
        # Existing cameras keep their persisted health state.
        # Newly configured cameras are registered OFFLINE and
        # become ONLINE only after a valid frame is received.
        # ----------------------------------------------------

        for camera_config in camera_configs:

            camera = camera_database.ensure_camera(
                camera_id=camera_config.camera_id,
                name=camera_config.name,
                location=camera_config.location,
            )

            camera_name = camera['name']
            camera_location = camera['location']
            camera_status = camera['status']

            print(
                f'Camera registered: '
                f'{camera_name} '
                f'({camera_location}) '
                f'Status={camera_status}'
            )

        # Open all configured sources.
        #
        # CameraManager isolates open failures so one bad
        # camera does not prevent the rest of the fleet from
        # being attempted.
        # ----------------------------------------------------

        opened = camera_manager.open_all()

        print(
            f"Camera sources opened: "
            f"{len(opened)}/{len(camera_configs)}"
        )

        if camera_manager.open_errors:

            for camera_id, error in (
                camera_manager.open_errors.items()
            ):
                print(
                    f"[CAMERA OPEN ERROR] "
                    f"Camera={camera_id} "
                    f"Error={error}"
                )

        # ----------------------------------------------------
        # ----------------------------------------------------
        # Concurrent camera processing.
        #
        # Only successfully opened cameras enter the worker pool.
        # Concurrency is deliberately bounded to two workers because
        # the development GPU has 4 GB VRAM.
        # ----------------------------------------------------

        opened_configs = [
            camera_config
            for camera_config in camera_configs
            if camera_config.camera_id in opened
        ]

        # Preserve explicit results for cameras that failed to open.
        for camera_config in camera_configs:

            camera_id = camera_config.camera_id

            if camera_id not in opened:

                error_message = (
                    camera_manager
                    .open_errors
                    .get(
                        camera_id,
                        "Camera source failed to open.",
                    )
                )

                results.append(
                    {
                        "camera_id": camera_id,
                        "name": camera_config.name,
                        "frames": 0,
                        "ai_frames": 0,
                        "events": 0,
                        "output_path": None,
                        "error": error_message,
                    }
                )

                print(
                    f"[CAMERA SKIPPED] "
                    f"Camera={camera_id} "
                    f"Source was not opened."
                )

        if opened_configs:

            camera_configs_by_id = {
                camera_config.camera_id: camera_config
                for camera_config in opened_configs
            }

            worker_pool = CameraWorkerPool(
                max_workers=2
            )

            print(
                f"Starting concurrent camera workers: "
                f"{len(opened_configs)} cameras, "
                f"max_workers={worker_pool.max_workers}"
            )

            def camera_worker(camera_id):

                return process_camera_worker(
                    camera_config=camera_configs_by_id[
                        camera_id
                    ],
                    camera_manager=camera_manager,
                    detector=detector,
                    zones=zones,
                    zone_detector=zone_detector,
                    notification_dispatcher=notification_dispatcher,
                    weapon_detection_provider=(
                        weapon_adapter.detect
                        if weapon_adapter is not None
                        else None
                    ),
                    fire_smoke_detection_provider=(
                        fire_smoke_adapter.detect
                        if fire_smoke_adapter is not None
                        else None
                    ),
                    crowding_config=crowding_config,
                    after_hours_config=after_hours_config,
                )

            worker_results = worker_pool.run(
                camera_ids=[
                    camera_config.camera_id
                    for camera_config in opened_configs
                ],
                worker=camera_worker,
            )

            for worker_result in worker_results:

                if worker_result.success:

                    results.append(
                        worker_result.value
                    )

                    print(
                        f"[CAMERA WORKER COMPLETE] "
                        f"Camera={worker_result.camera_id}"
                    )

                else:

                    results.append(
                        {
                            "camera_id": worker_result.camera_id,
                            "name": (
                                camera_configs_by_id[
                                    worker_result.camera_id
                                ].name
                            ),
                            "frames": 0,
                            "ai_frames": 0,
                            "events": 0,
                            "output_path": None,
                            "error": worker_result.error,
                        }
                    )

                    print(
                        f"[CAMERA WORKER FAILED] "
                        f"Camera={worker_result.camera_id} "
                        f"Error={worker_result.error}"
                    )


    except Exception as error:

        print(
            f"[FLEET ERROR] {error}"
        )

        raise

    finally:

        # ----------------------------------------------------
        # Drain and stop asynchronous notification workers
        # ----------------------------------------------------

        if notification_dispatcher is not None:

            try:

                notification_dispatcher.shutdown(
                    wait=True
                )

                print(
                    "Notification dispatcher shut down cleanly."
                )

            except Exception as error:

                print(
                    f"[CLEANUP WARNING] "
                    f"Notification dispatcher shutdown failed: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Close shared Fire/Smoke ONNX Runtime session
        # ----------------------------------------------------

        if fire_smoke_adapter is not None:

            try:

                fire_smoke_adapter.close()

                print(
                    "Fire/Smoke adapter shut down cleanly."
                )

            except Exception as error:

                print(
                    f"[CLEANUP WARNING] "
                    f"Fire/Smoke adapter shutdown failed: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Close shared weapon model resources
        # ----------------------------------------------------

        if weapon_adapter is not None:
            try:
                weapon_adapter.close()
                print("Weapon adapter shut down cleanly.")
            except Exception as error:
                print(
                    f"[CLEANUP WARNING] Weapon adapter shutdown failed: {error}"
                )

        # ----------------------------------------------------
        # Release all managed camera sources
        # ----------------------------------------------------

        if camera_manager is not None:

            release_errors = (
                camera_manager.release_all()
            )

            for camera_id, error in (
                release_errors.items()
            ):
                print(
                    f"[CLEANUP WARNING] "
                    f"Camera={camera_id} "
                    f"Video source release failed: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Close camera database
        # ----------------------------------------------------

        if camera_database is not None:

            try:

                camera_database.close()

            except Exception as error:

                print(
                    f"[CLEANUP WARNING] "
                    f"Camera database close failed: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # Close event database
        # ----------------------------------------------------

        if event_database is not None:

            try:

                event_database.close()

            except Exception as error:

                print(
                    f"[CLEANUP WARNING] "
                    f"Event database close failed: "
                    f"{error}"
                )

    # --------------------------------------------------------
    # Fleet summary
    # --------------------------------------------------------

    total_frames = sum(
        result["frames"]
        for result in results
    )

    total_ai_frames = sum(
        result["ai_frames"]
        for result in results
    )

    total_events = sum(
        result["events"]
        for result in results
    )

    successful_cameras = sum(
        1
        for result in results
        if result["error"] is None
    )

    failed_cameras = (
        len(results) - successful_cameras
    )

    print("=" * 60)
    print("MULTI-CAMERA INTRUSION DETECTION COMPLETE")
    print("=" * 60)

    print(
        f"Cameras processed : {len(results)}"
    )

    print(
        f"Cameras successful : {successful_cameras}"
    )

    print(
        f"Cameras failed     : {failed_cameras}"
    )

    print(
        f"Total frames       : {total_frames}"
    )

    print(
        f"AI frames          : {total_ai_frames}"
    )

    print(
        f"Total events       : {total_events}"
    )

    print(
        f"Evidence dir       : {EVIDENCE_DIRECTORY}"
    )

    print("-" * 60)

    for result in results:

        status = (
            "SUCCESS"
            if result["error"] is None
            else "FAILED"
        )

        print(
            f"{result['camera_id']} | "
            f"{status} | "
            f"Frames={result['frames']} | "
            f"AI={result['ai_frames']} | "
            f"Events={result['events']}"
        )

        if result["output_path"] is not None:
            print(
                f"  Output: "
                f"{result['output_path']}"
            )

        if result["error"] is not None:
            print(
                f"  Error: "
                f"{result['error']}"
            )

    print("=" * 60)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
