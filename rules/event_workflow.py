"""
Hotel AI Security - Event Workflow State Machine

This module defines and validates legal security-event status
transitions.

The workflow is intentionally enforced on the backend so that
frontend clients cannot bypass operational security rules.
"""


class InvalidEventTransitionError(Exception):
    """
    Raised when an event attempts an illegal status transition.
    """


# ============================================================
# EVENT STATUSES
# ============================================================

EVENT_STATUS_NEW = "NEW"
EVENT_STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
EVENT_STATUS_DISPATCHED = "DISPATCHED"
EVENT_STATUS_RESOLVED = "RESOLVED"
EVENT_STATUS_FALSE_POSITIVE = "FALSE_POSITIVE"


VALID_EVENT_STATUSES = {
    EVENT_STATUS_NEW,
    EVENT_STATUS_ACKNOWLEDGED,
    EVENT_STATUS_DISPATCHED,
    EVENT_STATUS_RESOLVED,
    EVENT_STATUS_FALSE_POSITIVE,
}


# ============================================================
# ALLOWED STATE TRANSITIONS
# ============================================================

ALLOWED_TRANSITIONS = {
    EVENT_STATUS_NEW: {
        EVENT_STATUS_ACKNOWLEDGED,
        EVENT_STATUS_FALSE_POSITIVE,
    },

    EVENT_STATUS_ACKNOWLEDGED: {
        EVENT_STATUS_DISPATCHED,
        EVENT_STATUS_FALSE_POSITIVE,
    },

    EVENT_STATUS_DISPATCHED: {
        EVENT_STATUS_RESOLVED,
    },

    EVENT_STATUS_RESOLVED: set(),

    EVENT_STATUS_FALSE_POSITIVE: set(),
}


# ============================================================
# HELPERS
# ============================================================

def normalize_status(status: str) -> str:
    """
    Normalize an event status before validation.
    """

    if status is None:
        raise ValueError("Event status cannot be None.")

    normalized = str(status).strip().upper()

    if not normalized:
        raise ValueError("Event status cannot be empty.")

    return normalized


def is_valid_event_status(status: str) -> bool:
    """
    Return True when the supplied status is a supported
    event status.
    """

    try:
        normalized = normalize_status(status)
    except ValueError:
        return False

    return normalized in VALID_EVENT_STATUSES


def get_allowed_transitions(current_status: str) -> set[str]:
    """
    Return the statuses that an event may transition to from
    its current status.
    """

    normalized = normalize_status(current_status)

    if normalized not in VALID_EVENT_STATUSES:
        raise ValueError(
            f"Unknown event status: {normalized}"
        )

    return set(ALLOWED_TRANSITIONS[normalized])


def can_transition(
    current_status: str,
    new_status: str,
) -> bool:
    """
    Return True if the requested transition is legal.
    """

    current = normalize_status(current_status)
    new = normalize_status(new_status)

    if current not in VALID_EVENT_STATUSES:
        return False

    if new not in VALID_EVENT_STATUSES:
        return False

    return new in ALLOWED_TRANSITIONS[current]


def validate_transition(
    current_status: str,
    new_status: str,
) -> None:
    """
    Validate an event state transition.

    Raises:
        ValueError:
            If either status is unknown.

        InvalidEventTransitionError:
            If the statuses are valid but the requested
            transition is not permitted.
    """

    current = normalize_status(current_status)
    new = normalize_status(new_status)

    if current not in VALID_EVENT_STATUSES:
        raise ValueError(
            f"Unknown current event status: {current}"
        )

    if new not in VALID_EVENT_STATUSES:
        raise ValueError(
            f"Unknown target event status: {new}"
        )

    if new not in ALLOWED_TRANSITIONS[current]:

        allowed = sorted(
            ALLOWED_TRANSITIONS[current]
        )

        if allowed:
            allowed_text = ", ".join(allowed)
        else:
            allowed_text = "none"

        raise InvalidEventTransitionError(
            f"Invalid event transition: "
            f"{current} -> {new}. "
            f"Allowed transitions from {current}: "
            f"{allowed_text}."
        )