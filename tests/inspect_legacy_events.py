from database.event_database import EventDatabase
from database.audit_database import AuditDatabase


LEGACY_EVENT_IDS = [2, 17, 18]


def print_value(label, value):
    print(f"{label:<22}: {value}")


def main():

    event_database = EventDatabase()
    audit_database = AuditDatabase()

    try:

        print("=" * 80)
        print("LEGACY EVENT INSPECTION")
        print("=" * 80)
        print()

        for event_id in LEGACY_EVENT_IDS:

            event = event_database.get_event(event_id)

            print("-" * 80)
            print(f"EVENT #{event_id}")
            print("-" * 80)

            if event is None:
                print("Event not found.")
                print()
                continue

            print_value(
                "Event Type",
                event["event_type"]
            )

            print_value(
                "Severity",
                event["severity"]
            )

            print_value(
                "Status",
                event["status"]
            )

            print_value(
                "Camera ID",
                event["camera_id"]
            )

            print_value(
                "Zone ID",
                event["zone_id"]
            )

            print_value(
                "Zone Name",
                event["zone_name"]
            )

            print_value(
                "Track ID",
                event["track_id"]
            )

            print_value(
                "Message",
                event["message"]
            )

            print_value(
                "Detected Timestamp",
                event["timestamp"]
            )

            print_value(
                "Created At",
                event["created_at"]
            )

            print_value(
                "Acknowledged At",
                event["acknowledged_at"]
            )

            print_value(
                "Dispatched At",
                event["dispatched_at"]
            )

            print_value(
                "Resolved At",
                event["resolved_at"]
            )

            print_value(
                "Resolution",
                event["resolution"]
            )

            print()

            print("AUDIT HISTORY")
            print("-" * 80)

            logs = audit_database.get_logs_for_entity(
                entity_type="event",
                entity_id=event_id
            )

            if not logs:
                print("No audit history found.")
            else:

                for log in logs:

                    print(
                        f"{log['created_at']} | "
                        f"{log['action']} | "
                        f"actor={log['actor_username']} | "
                        f"details={log['details']}"
                    )

            print()

        print("=" * 80)
        print("INSPECTION COMPLETE")
        print("NO DATABASE CHANGES WERE MADE.")
        print("=" * 80)

    finally:

        event_database.close()
        audit_database.close()


if __name__ == "__main__":
    main()