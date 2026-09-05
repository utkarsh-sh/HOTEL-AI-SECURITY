from database.audit_database import AuditDatabase


TEST_DATABASE = "database/audit_test.db"


def main():
    database = AuditDatabase(TEST_DATABASE)

    print("Creating test audit logs...")

    log_1 = database.create_log(
        action="EVENT_CREATED",
        entity_type="event",
        entity_id=21,
        actor="system",
        details="Intrusion event created",
    )

    log_2 = database.create_log(
        action="EVENT_ACKNOWLEDGED",
        entity_type="event",
        entity_id=21,
        actor="operator",
        details="Security operator acknowledged alert",
    )

    log_3 = database.create_log(
        action="EVENT_DISPATCHED",
        entity_type="event",
        entity_id=21,
        actor="operator",
        details="Security team dispatched",
    )

    print(f"Created log IDs: {log_1}, {log_2}, {log_3}")

    logs = database.get_all_logs()

    print()
    print("Audit logs:")

    for log in logs:
        print(
            f"ID={log['id']} | "
            f"Action={log['action']} | "
            f"Entity={log['entity_type']}:{log['entity_id']} | "
            f"Actor={log['actor']} | "
            f"Time={log['timestamp']}"
        )

    print()
    print("Logs for Event 21:")

    event_logs = database.get_logs_for_entity(
        "event",
        21,
    )

    for log in event_logs:
        print(
            f"{log['action']} -> {log['actor']}"
        )

    database.close()

    print()
    print("AUDIT DATABASE TEST COMPLETE")


if __name__ == "__main__":
    main()