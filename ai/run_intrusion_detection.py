import json

import cv2
import numpy as np

from ai.person_detector import PersonDetector
from ai.tracker import PersonTracker
from ai.zone_detector import ZoneDetector
from ai.camera_health import CameraHealthMonitor
from ai.evidence_recorder import EvidenceRecorder

from database.event_database import EventDatabase
from database.camera_database import CameraDatabase

from rules.intrusion_rules import IntrusionRule

from video.source import FileVideoSource


VIDEO_PATH = "data/input/01_person_tracking_intrusion.mp4"
ZONE_PATH = "configs/zones.json"
OUTPUT_PATH = "data/output/intrusion_detection_video.mp4"
EVIDENCE_DIRECTORY = "data/output/events"

AI_FPS = 5.0

PRE_EVENT_SECONDS = 5
POST_EVENT_SECONDS = 5


def load_zones(path):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        config = json.load(file)

    return config["zones"]


def main():

    print("=" * 60)
    print("HOTEL AI CCTV - INTRUSION DETECTION")
    print("=" * 60)

    # --------------------------------------------------
    # Load video
    # --------------------------------------------------

    source = FileVideoSource(
        VIDEO_PATH
    )

    source.open()

    capture = source.capture

    source_fps = capture.get(
        cv2.CAP_PROP_FPS
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

    duration = (
        total_frames / source_fps
        if source_fps > 0
        else 0
    )

    print(
        f"Resolution : "
        f"{width} x {height}"
    )

    print(
        f"Source FPS : "
        f"{source_fps:.2f}"
    )

    print(
        f"Frames     : "
        f"{total_frames}"
    )

    print(
        f"Duration   : "
        f"{duration:.2f}s"
    )

    print(
        f"AI FPS     : "
        f"{AI_FPS}"
    )

    # --------------------------------------------------
    # Load AI components
    # --------------------------------------------------

    detector = PersonDetector()

    tracker = PersonTracker()

    zones = load_zones(
        ZONE_PATH
    )

    zone_detector = ZoneDetector(
        zones
    )

    intrusion_rule = IntrusionRule(
        persistence_frames=3
    )

    # --------------------------------------------------
    # Initialize databases
    # --------------------------------------------------

    event_database = EventDatabase(
        "database/hotel_security.db"
    )

    camera_database = CameraDatabase(
        "database/hotel_security.db"
    )

    camera_id = "CAM-001"

    print(
        "Event database initialized."
    )

    print(
        "Camera database initialized."
    )

    # --------------------------------------------------
    # Verify camera registration
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Camera health monitor
    # --------------------------------------------------

    camera_health = CameraHealthMonitor(
        camera_id=camera_id,
        database=camera_database,
        failure_threshold=3,
    )

    camera_health.frame_received(
        fps=source_fps,
        width=width,
        height=height,
    )

    print(
        f"Camera health: "
        f"{camera_id} ONLINE"
    )

    # --------------------------------------------------
    # Evidence recorder
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Display loaded components
    # --------------------------------------------------

    print("-" * 60)

    print(
        "Detector loaded."
    )

    print(
        "Tracker loaded."
    )

    print(
        f"Zones loaded: "
        f"{len(zones)}"
    )

    for zone in zones:

        print(
            f"  - {zone['zone_id']}: "
            f"{zone['name']}"
        )

    print(
        "Intrusion rule loaded."
    )

    print(
        "Camera health monitor loaded."
    )

    print(
        "Evidence recorder loaded."
    )

    print("-" * 60)

    # --------------------------------------------------
    # Output video
    # --------------------------------------------------

    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    writer = cv2.VideoWriter(
        OUTPUT_PATH,
        fourcc,
        source_fps,
        (width, height),
    )

    if not writer.isOpened():

        raise RuntimeError(
            f"Could not create output video: "
            f"{OUTPUT_PATH}"
        )

    # --------------------------------------------------
    # Frame sampling
    # --------------------------------------------------

    sample_interval = max(
        1,
        round(
            source_fps / AI_FPS
        ),
    )

    frame_index = 0
    ai_frames = 0
    total_events = 0

    print(
        "Processing..."
    )

    print("-" * 60)

    # --------------------------------------------------
    # Main processing loop
    # --------------------------------------------------

    while True:

        frame = source.read()

        # --------------------------------------------------
        # Camera health monitoring
        # --------------------------------------------------

        if frame is None:

            camera_health.frame_failed(
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

            if (
                failure_count
                >= camera_health.failure_threshold
            ):

                print(
                    f"[CAMERA OFFLINE] "
                    f"Camera={camera_id} "
                    f"FailureThreshold="
                    f"{camera_health.failure_threshold}"
                )

            break

        # --------------------------------------------------
        # Valid frame received
        # --------------------------------------------------

        camera_health.frame_received(
            fps=source_fps,
            width=width,
            height=height,
        )

        # --------------------------------------------------
        # Add every frame to evidence recorder
        # --------------------------------------------------

        evidence_recorder.add_frame(
            frame
        )

        # --------------------------------------------------
        # Run AI every sample_interval frames
        # --------------------------------------------------

        if (
            frame_index
            % sample_interval
            == 0
        ):

            ai_frames += 1

            # ----------------------------------------------
            # Person detection
            # ----------------------------------------------

            detections = detector.detect(
                frame
            )

            # ----------------------------------------------
            # Person tracking
            # ----------------------------------------------

            tracks = tracker.update(
                detections
            )

            # ----------------------------------------------
            # Zone detection
            # ----------------------------------------------

            zone_results = (
                zone_detector.check_tracks(
                    tracks
                )
            )

            # ----------------------------------------------
            # Intrusion rule
            # ----------------------------------------------

            events = intrusion_rule.evaluate(
                zone_results
            )

            # ----------------------------------------------
            # Draw zones
            # ----------------------------------------------

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

            # ----------------------------------------------
            # Draw tracked people
            # ----------------------------------------------

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
                            y1 - 10
                        ),
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )

            # ----------------------------------------------
            # Process intrusion events
            # ----------------------------------------------

            for event in events:

                total_events += 1

                # ------------------------------------------
                # Create event in database
                # ------------------------------------------

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
                            "prototype-v1"
                        ),
                    )
                )

                # ------------------------------------------
                # Start evidence capture
                # ------------------------------------------

                evidence_path = (
                    evidence_recorder
                    .start_event_capture(
                        event_type=event[
                            "event_type"
                        ],
                        event_id=event_id,
                    )
                )

                # ------------------------------------------
                # Save evidence path
                # ------------------------------------------

                if evidence_path is not None:

                    event_database.update_evidence_path(
                        event_id=event_id,
                        evidence_path=str(
                            evidence_path
                        ),
                    )

                # ------------------------------------------
                # Log event
                # ------------------------------------------

                print(
                    f"[INTRUSION EVENT] "
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
                        f"EventID={event_id} "
                        f"Path={evidence_path}"
                    )

                else:

                    print(
                        f"[EVIDENCE WARNING] "
                        f"EventID={event_id} "
                        f"Evidence capture "
                        f"could not be started."
                    )

                # ------------------------------------------
                # Display intrusion alert
                # ------------------------------------------

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

        # --------------------------------------------------
        # Write processed frame
        # --------------------------------------------------

        writer.write(
            frame
        )

        frame_index += 1

        # --------------------------------------------------
        # Progress
        # --------------------------------------------------

        if (
            frame_index
            % max(
                1,
                total_frames // 10,
            )
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

    # --------------------------------------------------
    # Finalize evidence recording
    # --------------------------------------------------

    evidence_recorder.finalize()

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------

    writer.release()

    source.release()

    camera_database.close()

    event_database.close()

    # --------------------------------------------------
    # Final summary
    # --------------------------------------------------

    print("=" * 60)

    print(
        "INTRUSION DETECTION COMPLETE"
    )

    print("=" * 60)

    print(
        f"Total frames : "
        f"{frame_index}"
    )

    print(
        f"AI frames    : "
        f"{ai_frames}"
    )

    print(
        f"Events       : "
        f"{total_events}"
    )

    print(
        f"Output       : "
        f"{OUTPUT_PATH}"
    )

    print(
        f"Evidence dir : "
        f"{EVIDENCE_DIRECTORY}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()