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


class TestCameraHealthEndToEnd(unittest.TestCase):

    TEST_DATABASE_PATH = Path(
        "database/test_camera_health_e2e.db"
    )

    CAMERA_ID = "CAM-E2E-001"

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

        self.database = CameraDatabase(
            self.TEST_DATABASE_PATH
        )

        self.event_database = EventDatabase(
            self.TEST_DATABASE_PATH
        )

        self.database.create_camera(
            camera_id=self.CAMERA_ID,
            name="E2E Test Camera",
            location="E2E Test Location",
        )

        self.monitor = CameraHealthMonitor(
            camera_id=self.CAMERA_ID,
            database=self.database,
            failure_threshold=self.FAILURE_THRESHOLD,
        )

        self.event_service = CameraHealthEventService(
            event_database=self.event_database
        )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    def tearDown(self):

        try:
            self.database.close()
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

    def get_camera(self):

        camera = self.database.get_camera(
            self.CAMERA_ID
        )

        self.assertIsNotNone(
            camera
        )

        return camera

    def get_events(self):

        return list(
            self.event_database.get_all_events()
        )

    def get_events_chronological(self):

        """
        EventDatabase returns newest events first.

        Reverse the result so tests can reason about the
        lifecycle chronologically:

            oldest -> newest
        """

        return list(
            reversed(
                self.get_events()
            )
        )

    def establish_online_state(self):

        """
        Establish a genuine previously-seen ONLINE state.

        Recovery detection requires the camera to have
        previously provided at least one frame.
        """

        transition = self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertIsNone(
            transition
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertIsNotNone(
            camera["last_seen"]
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

    def reach_offline_state(self):

        """
        Simulate three consecutive frame failures and
        verify the ONLINE -> OFFLINE transition.
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

        self.assertTrue(
            self.monitor.is_offline()
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            3,
        )

    # --------------------------------------------------------
    # Test 1
    # --------------------------------------------------------

    def test_online_to_offline_transition(self):

        self.establish_online_state()

        # ----------------------------------------------------
        # Failure 1
        # ----------------------------------------------------

        transition = self.monitor.frame_failed(
            error="Failure 1"
        )

        self.assertIsNone(
            transition
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            1,
        )

        # ----------------------------------------------------
        # Failure 2
        # ----------------------------------------------------

        transition = self.monitor.frame_failed(
            error="Failure 2"
        )

        self.assertIsNone(
            transition
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            2,
        )

        # ----------------------------------------------------
        # Failure 3 -> OFFLINE
        # ----------------------------------------------------

        transition = self.monitor.frame_failed(
            error="Failure 3"
        )

        self.assertEqual(
            transition,
            CAMERA_OFFLINE,
        )

        self.assertTrue(
            self.monitor.is_offline()
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            3,
        )

        # ----------------------------------------------------
        # Create offline event
        # ----------------------------------------------------

        event_id = (
            self.event_service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="Failure 3",
            )
        )

        self.assertIsInstance(
            event_id,
            int,
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

        self.assertEqual(
            events[0]["severity"],
            "HIGH",
        )

        self.assertEqual(
            events[0]["status"],
            "NEW",
        )

        self.assertEqual(
            events[0]["camera_id"],
            self.CAMERA_ID,
        )

        self.assertEqual(
            events[0]["id"],
            event_id,
        )

        self.assertEqual(
            events[0]["workflow_version"],
            "workflow-v2",
        )

    # --------------------------------------------------------
    # Test 2
    # --------------------------------------------------------

    def test_continued_failures_do_not_duplicate_offline_event(self):

        self.establish_online_state()

        self.reach_offline_state()

        first_event_id = (
            self.event_service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="Failure 3",
            )
        )

        self.assertIsInstance(
            first_event_id,
            int,
        )

        # ----------------------------------------------------
        # Camera remains offline.
        # ----------------------------------------------------

        for failure_number in range(4, 11):

            transition = self.monitor.frame_failed(
                error=f"Failure {failure_number}"
            )

            self.assertIsNone(
                transition
            )

            self.assertTrue(
                self.monitor.is_offline()
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

        self.assertEqual(
            events[0]["id"],
            first_event_id,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            10,
        )

    # --------------------------------------------------------
    # Test 3
    # --------------------------------------------------------

    def test_offline_to_online_recovery(self):

        self.establish_online_state()

        self.reach_offline_state()

        offline_event_id = (
            self.event_service.create_offline_event(
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

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )

        self.assertIsNotNone(
            camera["last_seen"]
        )

        self.assertFalse(
            self.monitor.is_offline()
        )

        # ----------------------------------------------------
        # Create recovery event.
        # ----------------------------------------------------

        recovery_event_id = (
            self.event_service.create_recovered_event(
                camera_id=self.CAMERA_ID
            )
        )

        self.assertIsInstance(
            recovery_event_id,
            int,
        )

        events = self.get_events_chronological()

        # Exactly two events.
        self.assertEqual(
            len(events),
            2,
        )

        # Chronological order:
        #
        # OFFLINE -> RECOVERED
        #
        self.assertEqual(
            events[0]["event_type"],
            CAMERA_OFFLINE_EVENT,
        )

        self.assertEqual(
            events[1]["event_type"],
            CAMERA_RECOVERED_EVENT,
        )

        # Verify IDs.
        self.assertEqual(
            events[0]["id"],
            offline_event_id,
        )

        self.assertEqual(
            events[1]["id"],
            recovery_event_id,
        )

        # Verify camera.
        self.assertEqual(
            events[0]["camera_id"],
            self.CAMERA_ID,
        )

        self.assertEqual(
            events[1]["camera_id"],
            self.CAMERA_ID,
        )

        # Verify workflow versions.
        self.assertEqual(
            events[0]["workflow_version"],
            "workflow-v2",
        )

        self.assertEqual(
            events[1]["workflow_version"],
            "workflow-v2",
        )

    # --------------------------------------------------------
    # Test 4
    # --------------------------------------------------------

    def test_new_failure_after_recovery_creates_new_offline_event(self):

        self.establish_online_state()

        # ----------------------------------------------------
        # First outage.
        # ----------------------------------------------------

        self.reach_offline_state()

        first_offline_event = (
            self.event_service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="First outage",
            )
        )

        self.assertIsInstance(
            first_offline_event,
            int,
        )

        # ----------------------------------------------------
        # Recovery.
        # ----------------------------------------------------

        recovery_transition = (
            self.monitor.frame_received(
                fps=25.0,
                width=1920,
                height=1080,
            )
        )

        self.assertEqual(
            recovery_transition,
            CAMERA_RECOVERED,
        )

        recovery_event = (
            self.event_service.create_recovered_event(
                camera_id=self.CAMERA_ID
            )
        )

        self.assertIsInstance(
            recovery_event,
            int,
        )

        # ----------------------------------------------------
        # Second outage.
        # ----------------------------------------------------

        for failure_number in range(1, 4):

            transition = self.monitor.frame_failed(
                error=f"Second outage {failure_number}"
            )

            if failure_number < 3:

                self.assertIsNone(
                    transition
                )

            else:

                self.assertEqual(
                    transition,
                    CAMERA_OFFLINE,
                )

        second_offline_event = (
            self.event_service.create_offline_event(
                camera_id=self.CAMERA_ID,
                error="Second outage",
            )
        )

        self.assertIsInstance(
            second_offline_event,
            int,
        )

        # The second outage must have a different event ID.
        self.assertNotEqual(
            first_offline_event,
            second_offline_event,
        )

        events = self.get_events_chronological()

        # ----------------------------------------------------
        # There are exactly THREE events:
        #
        # 1. OFFLINE
        # 2. RECOVERED
        # 3. OFFLINE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Verify IDs.
        # ----------------------------------------------------

        self.assertEqual(
            events[0]["id"],
            first_offline_event,
        )

        self.assertEqual(
            events[1]["id"],
            recovery_event,
        )

        self.assertEqual(
            events[2]["id"],
            second_offline_event,
        )

        # ----------------------------------------------------
        # Verify all events belong to this camera.
        # ----------------------------------------------------

        for event in events:

            self.assertEqual(
                event["camera_id"],
                self.CAMERA_ID,
            )

        # ----------------------------------------------------
        # Verify final camera state.
        # ----------------------------------------------------

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "OFFLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            3,
        )

    # --------------------------------------------------------
    # Test 5
    # --------------------------------------------------------

    def test_recovery_without_previous_offline_does_not_create_event(self):

        self.establish_online_state()

        # ----------------------------------------------------
        # Another valid frame while already ONLINE.
        # ----------------------------------------------------

        transition = self.monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertIsNone(
            transition
        )

        # ----------------------------------------------------
        # No recovery event should exist.
        # ----------------------------------------------------

        events = self.get_events()

        self.assertEqual(
            len(events),
            0,
        )

        camera = self.get_camera()

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertEqual(
            camera["consecutive_failures"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
