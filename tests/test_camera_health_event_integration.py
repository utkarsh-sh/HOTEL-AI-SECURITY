import tempfile
import unittest
from pathlib import Path

from database.camera_database import CameraDatabase
from database.event_database import EventDatabase

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


class TestCameraHealthEventIntegration(unittest.TestCase):

    def setUp(self):

        self.temp_directory = tempfile.TemporaryDirectory()

        self.database_path = (
            Path(self.temp_directory.name)
            / "test_hotel_security.db"
        )

        self.camera_database = CameraDatabase(
            self.database_path
        )

        self.event_database = EventDatabase(
            self.database_path
        )

        self.camera_id = "CAM-TEST-001"

        self.camera_database.create_camera(
            camera_id=self.camera_id,
            name="Test Camera",
            location="Test Location",
            status="ONLINE",
        )

    def tearDown(self):

        try:
            self.camera_database.close()
        except Exception:
            pass

        try:
            self.event_database.close()
        except Exception:
            pass

        self.temp_directory.cleanup()

    def create_monitor(self):

        return CameraHealthMonitor(
            camera_id=self.camera_id,
            database=self.camera_database,
            failure_threshold=3,
        )

    def establish_camera_online(self, monitor):

        """
        Establish a genuine previously-seen ONLINE state.

        Recovery detection requires the camera to have
        previously provided at least one real frame.
        """

        transition = monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertIsNone(
            transition
        )

        camera = self.camera_database.get_camera(
            self.camera_id
        )

        self.assertEqual(
            camera["status"],
            "ONLINE",
        )

        self.assertIsNotNone(
            camera["last_seen"]
        )

    def take_camera_offline(self, monitor):

        transition = monitor.frame_failed(
            error="Failure 1"
        )

        self.assertIsNone(
            transition
        )

        transition = monitor.frame_failed(
            error="Failure 2"
        )

        self.assertIsNone(
            transition
        )

        transition = monitor.frame_failed(
            error="Failure 3"
        )

        self.assertEqual(
            transition,
            CAMERA_OFFLINE,
        )

    # --------------------------------------------------------
    # Test 1
    # --------------------------------------------------------

    def test_offline_transition_creates_one_event(self):

        monitor = self.create_monitor()

        event_service = CameraHealthEventService(
            event_database=self.event_database
        )

        self.establish_camera_online(
            monitor
        )

        self.take_camera_offline(
            monitor
        )

        event_id = (
            event_service.create_offline_event(
                camera_id=self.camera_id,
                error="Failure 3",
            )
        )

        self.assertIsInstance(
            event_id,
            int,
        )

        events = (
            self.event_database.get_all_events()
        )

        offline_events = [
            event
            for event in events
            if event["event_type"]
            == CAMERA_OFFLINE_EVENT
        ]

        self.assertEqual(
            len(offline_events),
            1,
        )

        self.assertEqual(
            offline_events[0]["id"],
            event_id,
        )

        self.assertEqual(
            offline_events[0]["camera_id"],
            self.camera_id,
        )

        self.assertEqual(
            offline_events[0]["severity"],
            "HIGH",
        )

    # --------------------------------------------------------
    # Test 2
    # --------------------------------------------------------

    def test_additional_failures_do_not_create_duplicate_event(self):

        monitor = self.create_monitor()

        event_service = CameraHealthEventService(
            event_database=self.event_database
        )

        self.establish_camera_online(
            monitor
        )

        self.take_camera_offline(
            monitor
        )

        event_service.create_offline_event(
            camera_id=self.camera_id,
            error="Failure 3",
        )

        transition = monitor.frame_failed(
            error="Failure 4"
        )

        self.assertIsNone(
            transition
        )

        transition = monitor.frame_failed(
            error="Failure 5"
        )

        self.assertIsNone(
            transition
        )

        events = (
            self.event_database.get_all_events()
        )

        offline_events = [
            event
            for event in events
            if event["event_type"]
            == CAMERA_OFFLINE_EVENT
        ]

        self.assertEqual(
            len(offline_events),
            1,
        )

    # --------------------------------------------------------
    # Test 3
    # --------------------------------------------------------

    def test_restart_while_offline_does_not_create_duplicate_event(self):

        monitor = self.create_monitor()

        event_service = CameraHealthEventService(
            event_database=self.event_database
        )

        self.establish_camera_online(
            monitor
        )

        self.take_camera_offline(
            monitor
        )

        event_service.create_offline_event(
            camera_id=self.camera_id,
            error="Failure 3",
        )

        # ----------------------------------------------------
        # Simulate application restart.
        # ----------------------------------------------------

        self.camera_database.close()

        self.event_database.close()

        self.camera_database = CameraDatabase(
            self.database_path
        )

        self.event_database = EventDatabase(
            self.database_path
        )

        restarted_monitor = self.create_monitor()

        restarted_event_service = (
            CameraHealthEventService(
                event_database=self.event_database
            )
        )

        self.assertTrue(
            restarted_monitor.is_offline()
        )

        transition = (
            restarted_monitor.frame_failed(
                error="Failure after restart"
            )
        )

        self.assertIsNone(
            transition
        )

        events = (
            self.event_database.get_all_events()
        )

        offline_events = [
            event
            for event in events
            if event["event_type"]
            == CAMERA_OFFLINE_EVENT
        ]

        self.assertEqual(
            len(offline_events),
            1,
        )

        self.assertIsNotNone(
            restarted_event_service
        )

    # --------------------------------------------------------
    # Test 4
    # --------------------------------------------------------

    def test_recovery_creates_one_recovery_event(self):

        monitor = self.create_monitor()

        event_service = CameraHealthEventService(
            event_database=self.event_database
        )

        self.establish_camera_online(
            monitor
        )

        self.take_camera_offline(
            monitor
        )

        event_service.create_offline_event(
            camera_id=self.camera_id,
            error="Failure 3",
        )

        # ----------------------------------------------------
        # Real frame arrives after offline state.
        # ----------------------------------------------------

        transition = monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition,
            CAMERA_RECOVERED,
        )

        recovery_event_id = (
            event_service.create_recovered_event(
                camera_id=self.camera_id
            )
        )

        self.assertIsInstance(
            recovery_event_id,
            int,
        )

        events = (
            self.event_database.get_all_events()
        )

        recovery_events = [
            event
            for event in events
            if event["event_type"]
            == CAMERA_RECOVERED_EVENT
        ]

        self.assertEqual(
            len(recovery_events),
            1,
        )

        self.assertEqual(
            recovery_events[0]["id"],
            recovery_event_id,
        )

        self.assertEqual(
            recovery_events[0]["camera_id"],
            self.camera_id,
        )

        self.assertEqual(
            recovery_events[0]["severity"],
            "MEDIUM",
        )

    # --------------------------------------------------------
    # Test 5
    # --------------------------------------------------------

    def test_restart_then_recovery_creates_only_one_recovery_event(self):

        monitor = self.create_monitor()

        event_service = CameraHealthEventService(
            event_database=self.event_database
        )

        self.establish_camera_online(
            monitor
        )

        self.take_camera_offline(
            monitor
        )

        event_service.create_offline_event(
            camera_id=self.camera_id,
            error="Failure 3",
        )

        # ----------------------------------------------------
        # Simulate restart while camera is still offline.
        # ----------------------------------------------------

        self.camera_database.close()

        self.event_database.close()

        self.camera_database = CameraDatabase(
            self.database_path
        )

        self.event_database = EventDatabase(
            self.database_path
        )

        restarted_monitor = self.create_monitor()

        restarted_event_service = (
            CameraHealthEventService(
                event_database=self.event_database
            )
        )

        self.assertTrue(
            restarted_monitor.is_offline()
        )

        # ----------------------------------------------------
        # First real frame after restart.
        # ----------------------------------------------------

        transition = restarted_monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertEqual(
            transition,
            CAMERA_RECOVERED,
        )

        restarted_event_service.create_recovered_event(
            camera_id=self.camera_id
        )

        # ----------------------------------------------------
        # Second valid frame must not create another
        # recovery transition.
        # ----------------------------------------------------

        transition = restarted_monitor.frame_received(
            fps=25.0,
            width=1920,
            height=1080,
        )

        self.assertIsNone(
            transition
        )

        events = (
            self.event_database.get_all_events()
        )

        offline_events = [
            event
            for event in events
            if event["event_type"]
            == CAMERA_OFFLINE_EVENT
        ]

        recovery_events = [
            event
            for event in events
            if event["event_type"]
            == CAMERA_RECOVERED_EVENT
        ]

        self.assertEqual(
            len(offline_events),
            1,
        )

        self.assertEqual(
            len(recovery_events),
            1,
        )


if __name__ == "__main__":
    unittest.main()