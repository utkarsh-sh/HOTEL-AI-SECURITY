import json
from pathlib import Path

import cv2
import numpy as np

from ai.person_detector import PersonDetector
from ai.tracker import PersonTracker
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
from database.camera_database import CameraDatabase

from rules.intrusion_rules import IntrusionRule

from video.camera_config import load_camera_configs
from video.frame_sampler import FrameSampler
from video.source_factory import create_video_source
from video.camera_manager import CameraManager


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

                events = intrusion_rule.evaluate(
                    zone_results
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
                            zone_id=event[
                                "zone_id"
                            ],
                            zone_name=event[
                                "zone_name"
                            ],
                            track_id=event[
                                "track_id"
                            ],
                            message=event[
                                "message"
                            ],
                            model_version=(
                                INTRUSION_MODEL_VERSION
                            ),
                            evidence_path=None,
                        )
                    )

                    # ----------------------------------------
                    # Start evidence capture
                    # ----------------------------------------

                    evidence_path = (
                        evidence_recorder
                        .start_event_capture(
                            event_type=event[
                                "event_type"
                            ],
                            event_id=event_id,
                        )
                    )

                    # ----------------------------------------
                    # Save evidence path
                    # ----------------------------------------

                    if evidence_path is not None:

                        event_database.update_evidence_path(
                            event_id=event_id,
                            evidence_path=str(
                                evidence_path
                            ),
                        )

                    # ----------------------------------------
                    # Log event
                    # ----------------------------------------

                    print(
                        f"[INTRUSION EVENT] "
                        f"Camera={camera_id} "
                        f"Frame={frame_index} "
                        f"EventID={event_id} "
                        f"Track={event['track_id']} "
                        f"Zone={event['zone_name']} "
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
                    # Display intrusion alert
                    # ----------------------------------------

                    cv2.putText(
                        frame,
                        "!!! INTRUSION DETECTED !!!",
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
# Main fleet orchestration
# ============================================================

def main():

    print("=" * 60)
    print("HOTEL AI CCTV - MULTI-CAMERA INTRUSION DETECTION")
    print("=" * 60)

    camera_manager = None
    camera_database = None
    event_database = None

    results = []

    try:

        # ----------------------------------------------------
        # Load camera configuration
        # ----------------------------------------------------

        camera_configs = load_camera_configs(
            CAMERA_CONFIG_PATH
        )

        if not camera_configs:
            raise RuntimeError(
                "No cameras configured."
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

        zones = load_zones(
            ZONE_PATH
        )

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

        camera_database = CameraDatabase(
            "database/hotel_security.db"
        )

        camera_health_events = CameraHealthEventService(
            event_database=event_database
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
        # Process each camera sequentially.
        #
        # This stage intentionally does NOT introduce
        # concurrency yet. Stage 16D will address concurrent
        # live-camera processing after this lifecycle is proven.
        # ----------------------------------------------------

        for camera_config in camera_configs:

            camera_id = camera_config.camera_id

            if camera_id not in opened:

                results.append(
                    {
                        "camera_id": camera_id,
                        "name": camera_config.name,
                        "frames": 0,
                        "ai_frames": 0,
                        "events": 0,
                        "output_path": None,
                        "error": (
                            camera_manager
                            .open_errors
                            .get(
                                camera_id,
                                "Camera source failed to open.",
                            )
                        ),
                    }
                )

                print(
                    f"[CAMERA SKIPPED] "
                    f"Camera={camera_id} "
                    "Source was not opened."
                )

                continue

            result = process_camera(
                camera_config=camera_config,
                camera_manager=camera_manager,
                detector=detector,
                zones=zones,
                zone_detector=zone_detector,
                event_database=event_database,
                camera_database=camera_database,
                camera_health_events=camera_health_events,
            )

            results.append(result)

    except Exception as error:

        print(
            f"[FLEET ERROR] {error}"
        )

        raise

    finally:

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
