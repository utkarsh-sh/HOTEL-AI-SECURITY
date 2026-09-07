import tempfile
import unittest
from pathlib import Path

from database.event_database import EventDatabase


class TestAtomicEventTransitions(unittest.TestCase):

    def create_database(self):

        temp_dir = tempfile.TemporaryDirectory()

        database_path = (
            Path(temp_dir.name)
            / "atomic_test.db"
        )

        database = EventDatabase(
            database_path
        )

        return database, temp_dir

    def cleanup_database(
        self,
        database,
        temp_dir
    ):

        database.close()

        temp_dir.cleanup()

    def create_event(
        self,
        database
    ):

        return database.create_event(
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-TEST",
            zone_id="restricted_01",
            zone_name="Restricted Area",
            track_id=1,
            message="Atomic transition test",
            model_version="test-v1",
        )

    # ----------------------------------------------------------
    # DUPLICATE ACKNOWLEDGE
    # ----------------------------------------------------------

    def test_duplicate_acknowledge_is_rejected(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            event_id = self.create_event(
                database
            )

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    event_id,
                    "ACKNOWLEDGED"
                )

            event = database.get_event(
                event_id
            )

            self.assertEqual(
                event["status"],
                "ACKNOWLEDGED"
            )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # DUPLICATE DISPATCH
    # ----------------------------------------------------------

    def test_duplicate_dispatch_is_rejected(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            event_id = self.create_event(
                database
            )

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            database.update_status(
                event_id,
                "DISPATCHED"
            )

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    event_id,
                    "DISPATCHED"
                )

            event = database.get_event(
                event_id
            )

            self.assertEqual(
                event["status"],
                "DISPATCHED"
            )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # RESOLVED TERMINAL
    # ----------------------------------------------------------

    def test_resolved_event_is_terminal(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            event_id = self.create_event(
                database
            )

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
                resolution="Incident handled"
            )

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    event_id,
                    "ACKNOWLEDGED"
                )

            event = database.get_event(
                event_id
            )

            self.assertEqual(
                event["status"],
                "RESOLVED"
            )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # FALSE POSITIVE TERMINAL
    # ----------------------------------------------------------

    def test_false_positive_is_terminal(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            event_id = self.create_event(
                database
            )

            database.update_status(
                event_id,
                "FALSE_POSITIVE",
                resolution="Operator verified false alert"
            )

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    event_id,
                    "ACKNOWLEDGED"
                )

            event = database.get_event(
                event_id
            )

            self.assertEqual(
                event["status"],
                "FALSE_POSITIVE"
            )

            self.assertIsNone(
                event["resolved_at"]
            )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # INVALID NEW -> DISPATCH
    # ----------------------------------------------------------

    def test_new_cannot_dispatch(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            event_id = self.create_event(
                database
            )

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    event_id,
                    "DISPATCHED"
                )

            event = database.get_event(
                event_id
            )

            self.assertEqual(
                event["status"],
                "NEW"
            )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # INVALID ACKNOWLEDGED -> RESOLVED
    # ----------------------------------------------------------

    def test_acknowledged_cannot_resolve(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            event_id = self.create_event(
                database
            )

            database.update_status(
                event_id,
                "ACKNOWLEDGED"
            )

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    event_id,
                    "RESOLVED",
                    resolution="Invalid resolution"
                )

            event = database.get_event(
                event_id
            )

            self.assertEqual(
                event["status"],
                "ACKNOWLEDGED"
            )

            self.assertIsNone(
                event["resolved_at"]
            )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )

    # ----------------------------------------------------------
    # EVENT NOT FOUND
    # ----------------------------------------------------------

    def test_missing_event_is_rejected(self):

        database, temp_dir = (
            self.create_database()
        )

        try:

            with self.assertRaises(
                ValueError
            ):

                database.update_status(
                    999999,
                    "ACKNOWLEDGED"
                )

        finally:

            self.cleanup_database(
                database,
                temp_dir
            )


if __name__ == "__main__":
    unittest.main()