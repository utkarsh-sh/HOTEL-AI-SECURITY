import tempfile
import unittest
from pathlib import Path

from database.event_database import EventDatabase


class TestEventDatabaseLifecycle(unittest.TestCase):

    def create_test_database(self):
        temp_dir = tempfile.TemporaryDirectory()

        database_path = Path(temp_dir.name) / "test.db"

        database = EventDatabase(database_path)

        return database, temp_dir

    def close_test_database(self, database, temp_dir):
        database.close()
        temp_dir.cleanup()

    def create_test_event(self, database):

        return database.create_event(
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-TEST-01",
            zone_id="restricted_01",
            zone_name="Restricted Area",
            track_id=1,
            message="Test intrusion event",
            model_version="test-v1",
        )

    # ----------------------------------------------------------
    # NEW EVENT
    # ----------------------------------------------------------

    def test_new_event_is_clean(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "NEW"
            )

            self.assertIsNone(
                event["acknowledged_at"]
            )

            self.assertIsNone(
                event["dispatched_at"]
            )

            self.assertIsNone(
                event["resolved_at"]
            )

            self.assertIsNone(
                event["resolution"]
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # ACKNOWLEDGED
    # ----------------------------------------------------------

    def test_acknowledge_event(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "ACKNOWLEDGED"
            )

            self.assertIsNotNone(
                event["acknowledged_at"]
            )

            self.assertIsNone(
                event["dispatched_at"]
            )

            self.assertIsNone(
                event["resolved_at"]
            )

            self.assertIsNone(
                event["resolution"]
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # DISPATCH REQUIRES ACKNOWLEDGEMENT
    # ----------------------------------------------------------

    def test_dispatch_requires_acknowledgement(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            with self.assertRaises(ValueError):

                database.update_status(
                    event_id,
                    "DISPATCHED"
                )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "NEW"
            )

            self.assertIsNone(
                event["acknowledged_at"]
            )

            self.assertIsNone(
                event["dispatched_at"]
            )

            self.assertIsNone(
                event["resolved_at"]
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # FULL LIFECYCLE
    # ----------------------------------------------------------

    def test_full_lifecycle(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            database.update_status(
                event_id,
                "DISPATCHED"
            )

            database.update_status(
                event_id,
                "RESOLVED",
                resolution=(
                    "Security team verified and "
                    "handled incident"
                )
            )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "RESOLVED"
            )

            self.assertIsNotNone(
                event["acknowledged_at"]
            )

            self.assertIsNotNone(
                event["dispatched_at"]
            )

            self.assertIsNotNone(
                event["resolved_at"]
            )

            self.assertEqual(
                event["resolution"],
                (
                    "Security team verified and "
                    "handled incident"
                )
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # FALSE POSITIVE FROM NEW
    # ----------------------------------------------------------

    def test_false_positive_from_new(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            database.update_status(
                event_id,
                "FALSE_POSITIVE",
                resolution="False detection during testing"
            )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "FALSE_POSITIVE"
            )

            self.assertIsNone(
                event["acknowledged_at"]
            )

            self.assertIsNone(
                event["dispatched_at"]
            )

            self.assertIsNone(
                event["resolved_at"]
            )

            self.assertEqual(
                event["resolution"],
                "False detection during testing"
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # FALSE POSITIVE FROM ACKNOWLEDGED
    # ----------------------------------------------------------

    def test_false_positive_from_acknowledged(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            acknowledged_event = database.get_event(
                event_id
            )

            acknowledged_at = (
                acknowledged_event["acknowledged_at"]
            )

            database.update_status(
                event_id,
                "FALSE_POSITIVE",
                resolution=(
                    "Operator confirmed false positive"
                )
            )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "FALSE_POSITIVE"
            )

            self.assertEqual(
                event["acknowledged_at"],
                acknowledged_at
            )

            self.assertIsNone(
                event["dispatched_at"]
            )

            self.assertIsNone(
                event["resolved_at"]
            )

            self.assertEqual(
                event["resolution"],
                "Operator confirmed false positive"
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # RESOLVE REQUIRES DISPATCH
    # ----------------------------------------------------------

    def test_resolve_requires_dispatch(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            with self.assertRaises(ValueError):

                database.update_status(
                    event_id,
                    "RESOLVED",
                    resolution="Should not be allowed"
                )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "ACKNOWLEDGED"
            )

            self.assertIsNotNone(
                event["acknowledged_at"]
            )

            self.assertIsNone(
                event["dispatched_at"]
            )

            self.assertIsNone(
                event["resolved_at"]
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # TERMINAL STATES
    # ----------------------------------------------------------

    def test_terminal_states_cannot_change(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            database.update_status(
                event_id,
                "FALSE_POSITIVE",
                resolution="Testing terminal state"
            )

            with self.assertRaises(ValueError):

                database.update_status(
                    event_id,
                    "ACKNOWLEDGED"
                )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "FALSE_POSITIVE"
            )

            self.assertIsNone(
                event["resolved_at"]
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # RESOLUTION REQUIRED
    # ----------------------------------------------------------

    def test_resolution_required_for_terminal_states(self):

        database, temp_dir = self.create_test_database()

        try:

            event_id = self.create_test_event(database)

            with self.assertRaises(ValueError):

                database.update_status(
                    event_id,
                    "FALSE_POSITIVE"
                )

            event = database.get_event(event_id)

            self.assertEqual(
                event["status"],
                "NEW"
            )

        finally:

            self.close_test_database(
                database,
                temp_dir
            )


if __name__ == "__main__":
    unittest.main()