import unittest

from rules.event_workflow import (
    EVENT_STATUS_NEW,
    EVENT_STATUS_ACKNOWLEDGED,
    EVENT_STATUS_DISPATCHED,
    EVENT_STATUS_RESOLVED,
    EVENT_STATUS_FALSE_POSITIVE,
    InvalidEventTransitionError,
    can_transition,
    get_allowed_transitions,
    is_valid_event_status,
    validate_transition,
)


class TestEventWorkflow(unittest.TestCase):

    # ========================================================
    # STATUS VALIDATION
    # ========================================================

    def test_valid_statuses(self):

        statuses = [
            EVENT_STATUS_NEW,
            EVENT_STATUS_ACKNOWLEDGED,
            EVENT_STATUS_DISPATCHED,
            EVENT_STATUS_RESOLVED,
            EVENT_STATUS_FALSE_POSITIVE,
        ]

        for status in statuses:
            self.assertTrue(
                is_valid_event_status(status)
            )

    def test_invalid_status(self):

        self.assertFalse(
            is_valid_event_status("UNKNOWN")
        )

    # ========================================================
    # VALID TRANSITIONS
    # ========================================================

    def test_new_to_acknowledged(self):

        self.assertTrue(
            can_transition(
                EVENT_STATUS_NEW,
                EVENT_STATUS_ACKNOWLEDGED,
            )
        )

        validate_transition(
            EVENT_STATUS_NEW,
            EVENT_STATUS_ACKNOWLEDGED,
        )

    def test_new_to_false_positive(self):

        self.assertTrue(
            can_transition(
                EVENT_STATUS_NEW,
                EVENT_STATUS_FALSE_POSITIVE,
            )
        )

    def test_acknowledged_to_dispatched(self):

        self.assertTrue(
            can_transition(
                EVENT_STATUS_ACKNOWLEDGED,
                EVENT_STATUS_DISPATCHED,
            )
        )

    def test_acknowledged_to_false_positive(self):

        self.assertTrue(
            can_transition(
                EVENT_STATUS_ACKNOWLEDGED,
                EVENT_STATUS_FALSE_POSITIVE,
            )
        )

    def test_dispatched_to_resolved(self):

        self.assertTrue(
            can_transition(
                EVENT_STATUS_DISPATCHED,
                EVENT_STATUS_RESOLVED,
            )
        )

    # ========================================================
    # INVALID TRANSITIONS
    # ========================================================

    def test_new_cannot_dispatch_directly(self):

        self.assertFalse(
            can_transition(
                EVENT_STATUS_NEW,
                EVENT_STATUS_DISPATCHED,
            )
        )

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_NEW,
                EVENT_STATUS_DISPATCHED,
            )

    def test_new_cannot_resolve_directly(self):

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_NEW,
                EVENT_STATUS_RESOLVED,
            )

    def test_resolved_cannot_be_acknowledged(self):

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_RESOLVED,
                EVENT_STATUS_ACKNOWLEDGED,
            )

    def test_resolved_cannot_be_dispatched(self):

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_RESOLVED,
                EVENT_STATUS_DISPATCHED,
            )

    def test_resolved_cannot_be_false_positive(self):

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_RESOLVED,
                EVENT_STATUS_FALSE_POSITIVE,
            )

    def test_false_positive_is_terminal(self):

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_FALSE_POSITIVE,
                EVENT_STATUS_ACKNOWLEDGED,
            )

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_FALSE_POSITIVE,
                EVENT_STATUS_DISPATCHED,
            )

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_FALSE_POSITIVE,
                EVENT_STATUS_RESOLVED,
            )

    def test_dispatched_cannot_go_backwards(self):

        with self.assertRaises(
            InvalidEventTransitionError
        ):
            validate_transition(
                EVENT_STATUS_DISPATCHED,
                EVENT_STATUS_ACKNOWLEDGED,
            )

    # ========================================================
    # TERMINAL STATES
    # ========================================================

    def test_resolved_has_no_allowed_transitions(self):

        allowed = get_allowed_transitions(
            EVENT_STATUS_RESOLVED
        )

        self.assertEqual(
            allowed,
            set(),
        )

    def test_false_positive_has_no_allowed_transitions(self):

        allowed = get_allowed_transitions(
            EVENT_STATUS_FALSE_POSITIVE
        )

        self.assertEqual(
            allowed,
            set(),
        )


if __name__ == "__main__":
    unittest.main()