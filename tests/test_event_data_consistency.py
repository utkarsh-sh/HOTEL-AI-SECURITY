from database.event_database import (
    EventDatabase,
    CURRENT_WORKFLOW_VERSION,
)


REQUIRED_FIELDS = {
    "id",
    "status",
    "timestamp",
    "created_at",
    "acknowledged_at",
    "dispatched_at",
    "resolved_at",
    "resolution",
    "workflow_version",
}


VALID_STATUSES = {
    "NEW",
    "ACKNOWLEDGED",
    "DISPATCHED",
    "RESOLVED",
    "FALSE_POSITIVE",
}


def check_timestamp_order(event):

    errors = []

    timestamps = []

    for field in (
        "created_at",
        "acknowledged_at",
        "dispatched_at",
        "resolved_at",
    ):

        timestamp = event.get(field)

        if timestamp is not None:

            timestamps.append(
                (
                    field,
                    str(timestamp)
                )
            )

    for index in range(
        len(timestamps) - 1
    ):

        first_name, first_value = (
            timestamps[index]
        )

        second_name, second_value = (
            timestamps[index + 1]
        )

        if first_value > second_value:

            errors.append(
                "timestamp order invalid: "
                f"{first_name}={first_value} > "
                f"{second_name}={second_value}"
            )

    return errors


def check_workflow_rules(event):

    errors = []

    status = event.get("status")

    acknowledged_at = event.get(
        "acknowledged_at"
    )

    dispatched_at = event.get(
        "dispatched_at"
    )

    resolved_at = event.get(
        "resolved_at"
    )

    resolution = event.get(
        "resolution"
    )

    if status not in VALID_STATUSES:

        errors.append(
            f"unknown status: {status!r}"
        )

        return errors

    # ----------------------------------------------------------
    # NEW
    # ----------------------------------------------------------

    if status == "NEW":

        if acknowledged_at is not None:
            errors.append(
                "NEW event has acknowledged_at"
            )

        if dispatched_at is not None:
            errors.append(
                "NEW event has dispatched_at"
            )

        if resolved_at is not None:
            errors.append(
                "NEW event has resolved_at"
            )

        if resolution:
            errors.append(
                "NEW event has resolution"
            )

    # ----------------------------------------------------------
    # ACKNOWLEDGED
    # ----------------------------------------------------------

    elif status == "ACKNOWLEDGED":

        if acknowledged_at is None:
            errors.append(
                "ACKNOWLEDGED event is missing "
                "acknowledged_at"
            )

        if dispatched_at is not None:
            errors.append(
                "ACKNOWLEDGED event has dispatched_at"
            )

        if resolved_at is not None:
            errors.append(
                "ACKNOWLEDGED event has resolved_at"
            )

        if resolution:
            errors.append(
                "ACKNOWLEDGED event has resolution"
            )

    # ----------------------------------------------------------
    # DISPATCHED
    # ----------------------------------------------------------

    elif status == "DISPATCHED":

        if acknowledged_at is None:
            errors.append(
                "DISPATCHED event is missing "
                "acknowledged_at"
            )

        if dispatched_at is None:
            errors.append(
                "DISPATCHED event is missing "
                "dispatched_at"
            )

        if resolved_at is not None:
            errors.append(
                "DISPATCHED event has resolved_at"
            )

        if resolution:
            errors.append(
                "DISPATCHED event has resolution"
            )

    # ----------------------------------------------------------
    # RESOLVED
    # ----------------------------------------------------------

    elif status == "RESOLVED":

        if acknowledged_at is None:
            errors.append(
                "RESOLVED event is missing "
                "acknowledged_at"
            )

        if dispatched_at is None:
            errors.append(
                "RESOLVED event is missing "
                "dispatched_at"
            )

        if resolved_at is None:
            errors.append(
                "RESOLVED event is missing "
                "resolved_at"
            )

        if (
            not resolution
            or not str(resolution).strip()
        ):
            errors.append(
                "RESOLVED event is missing resolution"
            )

    # ----------------------------------------------------------
    # FALSE POSITIVE
    # ----------------------------------------------------------

    elif status == "FALSE_POSITIVE":

        if dispatched_at is not None:
            errors.append(
                "FALSE_POSITIVE event has dispatched_at"
            )

        if resolved_at is not None:
            errors.append(
                "FALSE_POSITIVE event has resolved_at"
            )

        if (
            not resolution
            or not str(resolution).strip()
        ):
            errors.append(
                "FALSE_POSITIVE event is missing resolution"
            )

    return errors


def check_event(event):

    errors = []

    missing_fields = (
        REQUIRED_FIELDS - set(event.keys())
    )

    if missing_fields:

        errors.append(
            f"missing fields: {sorted(missing_fields)}"
        )

        return errors

    errors.extend(
        check_workflow_rules(event)
    )

    errors.extend(
        check_timestamp_order(event)
    )

    return errors


def main():

    database = EventDatabase()

    try:

        events = [
            dict(event)
            for event in database.get_all_events()
        ]

        print("=" * 70)
        print("EVENT DATA CONSISTENCY AUDIT")
        print("=" * 70)
        print()

        print(
            f"Events found: {len(events)}"
        )

        print()

        current_events = [
            event
            for event in events
            if event.get("workflow_version")
            == CURRENT_WORKFLOW_VERSION
        ]

        legacy_events = [
            event
            for event in events
            if event.get("workflow_version")
            != CURRENT_WORKFLOW_VERSION
        ]

        # ======================================================
        # CURRENT WORKFLOW
        # ======================================================

        print("=" * 70)
        print("CURRENT WORKFLOW EVENTS")
        print("=" * 70)
        print()

        current_errors = 0

        if not current_events:

            print(
                "No workflow-v2 events exist yet."
            )

            print(
                "This is expected because all existing "
                "events predate workflow-v2."
            )

        else:

            for event in current_events:

                errors = check_event(event)

                if errors:

                    current_errors += len(
                        errors
                    )

                    print(
                        f"[FAIL] Event #{event['id']} "
                        f"status={event['status']}"
                    )

                    for error in errors:

                        print(
                            f"       - {error}"
                        )

                    print()

                else:

                    print(
                        f"[PASS] Event #{event['id']} "
                        f"status={event['status']}"
                    )

        print()

        # ======================================================
        # LEGACY WORKFLOW
        # ======================================================

        print("=" * 70)
        print("LEGACY WORKFLOW EVENTS")
        print("=" * 70)
        print()

        legacy_anomalies = 0
        legacy_events_with_anomalies = 0

        for event in legacy_events:

            errors = check_event(event)

            if errors:

                legacy_events_with_anomalies += 1
                legacy_anomalies += len(errors)

                print(
                    f"[LEGACY-ANOMALY] "
                    f"Event #{event['id']} "
                    f"status={event['status']}"
                )

                for error in errors:

                    print(
                        f"                 - {error}"
                    )

                print()

            else:

                print(
                    f"[LEGACY-PASS] "
                    f"Event #{event['id']} "
                    f"status={event['status']}"
                )

        print()

        # ======================================================
        # SUMMARY
        # ======================================================

        print("=" * 70)
        print("AUDIT SUMMARY")
        print("=" * 70)

        print(
            f"Total events:                  "
            f"{len(events)}"
        )

        print(
            f"Current workflow events:       "
            f"{len(current_events)}"
        )

        print(
            f"Legacy workflow events:        "
            f"{len(legacy_events)}"
        )

        print(
            f"Current workflow errors:       "
            f"{current_errors}"
        )

        print(
            f"Legacy events with anomalies:  "
            f"{legacy_events_with_anomalies}"
        )

        print(
            f"Legacy anomaly count:          "
            f"{legacy_anomalies}"
        )

        print()

        if current_errors == 0:

            print("RESULT: PASS")

            print(
                "Current workflow data has no "
                "consistency failures."
            )

            if legacy_anomalies:

                print(
                    "Historical legacy anomalies were "
                    "detected and preserved."
                )

        else:

            print("RESULT: FAIL")

            print(
                "Current workflow data contains "
                "consistency failures."
            )

        print("=" * 70)

        return (
            0
            if current_errors == 0
            else 1
        )

    finally:

        database.close()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )