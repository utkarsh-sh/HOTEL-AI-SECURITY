import unittest
from pathlib import Path

from ai.camera_health import (
    CameraHealthMonitor,
    CAMERA_OFFLINE,
    CAMERA_RECOVERED,
)

from ai.camera_health_events import (
    CameraHealthEventService,
    CAMERA_OFFLINE_EVENT,
    CAMERA_RECOVERED_EVENT,
)

from database.camera_database import CameraDatabase
from database.event_database import EventDatabase


class TestCameraHealthEventService(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_health_events.db"
    )

    CAMERA_ID = "CAM-TEST-001"

    FAILURE_THRESHOLD = 3

    # --------------------------------------------------------
    # Setup
    # --------------------------------------------------------

    def setUp(self):

        if self.TEST_DATABASE_PATH.exists():

            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

        self.camera_database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

        self.event_database = EventDatabase(
            self.TEST_DATABASE_PATH
        )

        self.camera_database.create_camera(
            camera_id=self.CAMERA_ID,
            name="Test Camera",
            location="Test Location",
        )

        self.monitor = CameraHealthMonitor(
            camera_id=self.CAMERA_ID,
            database=self.camera_database,
            failure_threshold=self.FAILURE_THRESHOLD,
        )

        self.service = CameraHealthEventService(
            event_database=self.event_database
        )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    def tearDown(self):

        try:
            self.camera_database.close()
        except Exception:
            pass

        try:
            self.event_database.close()
        except Exception:
            pass

        if self.TEST_DATABASE_PATH.exists():

            try:
                self.TEST_DATABASE_PATH.unlink()
            except PermissionError:
                pass

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def get_events(self):

        return list(
            self.event_database.get_all_events()
        )

    def establish_online_state(self):

        """
        Establish a genuine previously-seen ONLINE state.
        """

        transition = self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertIsNone(
            transition
        )

        camera = self.camera_database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertIsNotNone(
            camera["last_seen"]
        )

    def reach_offline_state(self):

        """
        Produce the configured number of consecutive
        failures and verify the OFFLINE transition.
        """

        transition = self.monitor.frame_failed(
            error="Failure 1"
        )

        self.assertIsNone(
            transition
        )

        transition = self.monitor.frame_failed(
            error="Failure 2"
        )

        self.assertIsNone(
            transition
        )

        transition = self.monitor.frame_failed(
            error="Failure 3"
        )

        self.assertEqual(
            transition,
            CAMERA_OFFLINE,
        )

    # --------------------------------------------------------
    # Test 1
    # --------------------------------------------------------

    def test_camera_offline_creates_event(self):

        self.establish_online_state()

        transition = self.monitor.frame_failed(
            error="No frame received"
        )

        self.assertIsNone(
            transition
        )

        transition = self.monitor.frame_failed(
            error="No frame received"
        )

        self.assertIsNone(
            transition
        )

        transition = self.monitor.frame_failed(
            error="No frame received"
        )

        self.assertEqual(
            transition,
            CAMERA_OFFLINE,
        )

        event_id = (
            self.service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="No frame received",
            )
        )

        self.assertIsInstance(
            event_id,
            int,
        )

        event = self.event_database.get_event(
            event_id
        )

        self.assertIsNotNone(
            event
        )

        self.assertEqual(
            event["event_type"],
            CAMERA_OFFLINE_EVENT,
        )

        self.assertEqual(
            event["severity"],
            "HIGH",
        )

        self.assertEqual(
            event["status"],
            "NEW",
        )

        self.assertEqual(
            event["camera_id"],
            self.CAMERA_ID,
        )

        self.assertIsNone(
            event["zone_id"]
        )

        self.assertIsNone(
            event["zone_name"]
        )

        self.assertIsNone(
            event["track_id"]
        )

        self.assertIn(
            "No frame received",
            event["message"],
        )

        self.assertEqual(
            event["model_version"],
            "camera-health-v1",
        )

        self.assertEqual(
            event["workflow_version"],
            "workflow-v2",
        )

        # State belongs to the CameraHealthMonitor/database,
        # not the event service.

        camera = self.camera_database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            3,
        )

    # --------------------------------------------------------
    # Test 2
    # --------------------------------------------------------

    def test_repeated_offline_notifications_do_not_duplicate(self):

        self.establish_online_state()

        self.reach_offline_state()

        # The monitor reports the transition exactly once.

        events_created = 0

        transition = CAMERA_OFFLINE

        if transition == CAMERA_OFFLINE:

            self.service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="Failure 3",
            )

            events_created += 1

        # More failures while already offline.

        for failure_number in range(4, 8):

            transition = self.monitor.frame_failed(
                error=f"Failure {failure_number}"
            )

            self.assertIsNone(
                transition
            )

            if transition == CAMERA_OFFLINE:

                self.service.create_offline_event(
                    camera_id=self.CAMERA_ID,
                    error=f"Failure {failure_number}",
                )

                events_created += 1

        self.assertEqual(
            events_created,
            1,
        )

        events = self.get_events()

        self.assertEqual(
            len(events),
            1,
        )

        self.assertEqual(
            events[0]["event_type"],
            CAMERA_OFFLINE_EVENT,
        )

    # --------------------------------------------------------
    # Test 3
    # --------------------------------------------------------

    def test_camera_recovery_creates_event(self):

        self.establish_online_state()

        self.reach_offline_state()

        offline_event_id = (
            self.service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="Camera disconnected",
            )
        )

        self.assertIsInstance(
            offline_event_id,
            int,
        )

        # ----------------------------------------------------
        # Camera recovers.
        # ----------------------------------------------------

        transition = self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition,
            CAMERA_RECOVERED,
        )

        recovery_event_id = (
            self.service.create_recovered_event(
                camera_id=self.CAMERA_ID
            )
        )

        self.assertIsInstance(
            recovery_event_id,
            int,
        )

        self.assertNotEqual(
            offline_event_id,
            recovery_event_id,
        )

        recovery_event = self.event_database.get_event(
            recovery_event_id
        )

        self.assertIsNotNone(
            recovery_event
        )

        self.assertEqual(
            recovery_event["event_type"],
            CAMERA_RECOVERED_EVENT,
        )

        self.assertEqual(
            recovery_event["severity"],
            "MEDIUM",
        )

        self.assertEqual(
            recovery_event["status"],
            "NEW",
        )

        self.assertEqual(
            recovery_event["camera_id"],
            self.CAMERA_ID,
        )

        self.assertEqual(
            recovery_event["model_version"],
            "camera-health-v1",
        )

        self.assertEqual(
            recovery_event["workflow_version"],
            "workflow-v2",
        )

        # Camera state is now ONLINE.

        camera = self.camera_database.get_camera(
            self.CAMERA_ID
        )

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

    # --------------------------------------------------------
    # Test 4
    # --------------------------------------------------------

    def test_recovery_without_offline_does_not_create_event(self):

        self.establish_online_state()

        transition = self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        # Already ONLINE -> ONLINE.
        self.assertIsNone(
            transition
        )

        recovery_event_id = None

        if transition == CAMERA_RECOVERED:

            recovery_event_id = (
                self.service.create_recovered_event(
                    camera_id=self.CAMERA_ID
                )
            )

        self.assertIsNone(
            recovery_event_id
        )

        events = self.get_events()

        self.assertEqual(
            len(events),
            0,
        )

    # --------------------------------------------------------
    # Test 5
    # --------------------------------------------------------

    def test_second_offline_after_recovery_creates_new_event(self):

        self.establish_online_state()

        # ----------------------------------------------------
        # First outage.
        # ----------------------------------------------------

        self.reach_offline_state()

        first_offline_event = (
            self.service.create_offline_event(
                camera_id=self.CAMERA_ID
            )
        )

        self.assertIsInstance(
            first_offline_event,
            int,
        )

        # ----------------------------------------------------
        # Recovery.
        # ----------------------------------------------------

        transition = self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition,
            CAMERA_RECOVERED,
        )

        first_recovery_event = (
            self.service.create_recovered_event(
                camera_id=self.CAMERA_ID
            )
        )

        self.assertIsInstance(
            first_recovery_event,
            int,
        )

        # ----------------------------------------------------
        # Second outage.
        # ----------------------------------------------------

        self.reach_offline_state()

        second_offline_event = (
            self.service.create_offline_event(
                camera_id=self.CAMERA_ID
            )
        )

        self.assertIsInstance(
            second_offline_event,
            int,
        )

        self.assertNotEqual(
            first_offline_event,
            second_offline_event,
        )

        events = list(
            reversed(
                self.get_events()
            )
        )

        self.assertEqual(
            len(events),
            3,
        )

        event_types = [
            event["event_type"]
            for event in events
        ]

        self.assertEqual(
            event_types,
            [
                CAMERA_OFFLINE_EVENT,
                CAMERA_RECOVERED_EVENT,
                CAMERA_OFFLINE_EVENT,
            ],
        )

        self.assertEqual(
            events[0]["id"],
            first_offline_event,
        )

        self.assertEqual(
            events[1]["id"],
            first_recovery_event,
        )

        self.assertEqual(
            events[2]["id"],
            second_offline_event,
        )

    # --------------------------------------------------------
    # Test 6
    # --------------------------------------------------------

    def test_multiple_cameras_are_tracked_independently(self):

        camera_a = "CAM-A"
        camera_b = "CAM-B"

        # ----------------------------------------------------
        # Register both cameras.
        # ----------------------------------------------------

        self.camera_database.create_camera(
            camera_id=camera_a,
            name="Camera A",
            location="Location A",
        )

        self.camera_database.create_camera(
            camera_id=camera_b,
            name="Camera B",
            location="Location B",
        )

        monitor_a = CameraHealthMonitor(
            camera_id=camera_a,
            database=self.camera_database,
            failure_threshold=self.FAILURE_THRESHOLD,
        )

        monitor_b = CameraHealthMonitor(
            camera_id=camera_b,
            database=self.camera_database,
            failure_threshold=self.FAILURE_THRESHOLD,
        )

        # ----------------------------------------------------
        # Establish both cameras as genuinely ONLINE.
        # ----------------------------------------------------

        self.assertIsNone(
            monitor_a.frame_received(
                fps=25.0,
                width=1920,
                height=1080,
            )
        )

        self.assertIsNone(
            monitor_b.frame_received(
                fps=25.0,
                width=1920,
                height=1080,
            )
        )

        # ----------------------------------------------------
        # Camera A goes offline.
        # ----------------------------------------------------

        monitor_a.frame_failed(
            error="Camera A failure 1"
        )

        monitor_a.frame_failed(
            error="Camera A failure 2"
        )

        transition_a = monitor_a.frame_failed(
            error="Camera A failure 3"
        )

        self.assertEqual(
            transition_a,
            CAMERA_OFFLINE,
        )

        event_a = (
            self.service.create_offline_event(
                camera_id=camera_a,
                error="Camera A failure",
            )
        )

        self.assertIsInstance(
            event_a,
            int,
        )

        # ----------------------------------------------------
        # Camera B goes offline independently.
        # ----------------------------------------------------

        monitor_b.frame_failed(
            error="Camera B failure 1"
        )

        monitor_b.frame_failed(
            error="Camera B failure 2"
        )

        transition_b = monitor_b.frame_failed(
            error="Camera B failure 3"
        )

        self.assertEqual(
            transition_b,
            CAMERA_OFFLINE,
        )

        event_b = (
            self.service.create_offline_event(
                camera_id=camera_b,
                error="Camera B failure",
            )
        )

        self.assertIsInstance(
            event_b,
            int,
        )

        # ----------------------------------------------------
        # Verify both are offline.
        # ----------------------------------------------------

        camera_a_state = (
            self.camera_database.get_camera(
                camera_a
            )
        )

        camera_b_state = (
            self.camera_database.get_camera(
                camera_b
            )
        )

        self.assertEqual(
            camera_a_state["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera_b_state["status"],
            "OFFLINE",
        )

        # ----------------------------------------------------
        # Recover only Camera A.
        # ----------------------------------------------------

        transition_a = monitor_a.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition_a,
            CAMERA_RECOVERED,
        )

        recovery_a = (
            self.service.create_recovered_event(
                camera_id=camera_a
            )
        )

        self.assertIsInstance(
            recovery_a,
            int,
        )

        # ----------------------------------------------------
        # Camera A online, Camera B still offline.
        # ----------------------------------------------------

        camera_a_state = (
            self.camera_database.get_camera(
                camera_a
            )
        )

        camera_b_state = (
            self.camera_database.get_camera(
                camera_b
            )
        )

        self.assertEqual(
            camera_a_state["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera_b_state["status"],
            "OFFLINE",
        )

        # ----------------------------------------------------
        # Recover Camera B.
        # ----------------------------------------------------

        transition_b = monitor_b.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition_b,
            CAMERA_RECOVERED,
        )

        recovery_b = (
            self.service.create_recovered_event(
                camera_id=camera_b
            )
        )

        self.assertIsInstance(
            recovery_b,
            int,
        )

        # ----------------------------------------------------
        # Verify event records.
        # ----------------------------------------------------

        events = self.get_events()

        self.assertEqual(
            len(events),
            4,
        )

        camera_ids = [
            event["camera_id"]
            for event in events
        ]

        self.assertCountEqual(
            camera_ids,
            [
                camera_a,
                camera_b,
                camera_a,
                camera_b,
            ],
        )

        event_types = [
            event["event_type"]
            for event in events
        ]

        self.assertCountEqual(
            event_types,
            [
                CAMERA_OFFLINE_EVENT,
                CAMERA_OFFLINE_EVENT,
                CAMERA_RECOVERED_EVENT,
                CAMERA_RECOVERED_EVENT,
            ],
        )

        # ----------------------------------------------------
        # Verify final states.
        # ----------------------------------------------------

        camera_a_state = (
            self.camera_database.get_camera(
                camera_a
            )
        )

        camera_b_state = (
            self.camera_database.get_camera(
                camera_b
            )
        )

        self.assertEqual(
            camera_a_state["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera_b_state["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera_a_state["consecutive_failures"],
            0,
        )

        self.assertEqual(
            camera_b_state["consecutive_failures"],
            0,
        )


if __name__ == "__main__":
    unittest.main()