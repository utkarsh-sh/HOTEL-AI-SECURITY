from database.audit_database import AuditDatabase


def create_log(
    database,
    action,
    entity_type,
    entity_id,
):
    return database.create_log(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor="test",
        details=f"{action} test",
    )


def test_get_logs_page_paginates_and_returns_total(tmp_path):
    database = AuditDatabase(
        tmp_path / "audit.db"
    )

    try:
        for index in range(5):
            create_log(
                database,
                action=f"ACTION_{index}",
                entity_type="event",
                entity_id=index,
            )

        result = database.get_logs_page(
            page=1,
            page_size=2,
        )

        assert result["total"] == 5
        assert len(result["logs"]) == 2

        second_page = database.get_logs_page(
            page=2,
            page_size=2,
        )

        assert second_page["total"] == 5
        assert len(second_page["logs"]) == 2

        first_ids = {
            log["id"]
            for log in result["logs"]
        }
        second_ids = {
            log["id"]
            for log in second_page["logs"]
        }

        assert first_ids.isdisjoint(second_ids)

    finally:
        database.close()


def test_get_logs_page_filters_by_entity(tmp_path):
    database = AuditDatabase(
        tmp_path / "audit.db"
    )

    try:
        create_log(
            database,
            action="EVENT_CREATED",
            entity_type="event",
            entity_id=21,
        )
        create_log(
            database,
            action="EVENT_ACKNOWLEDGED",
            entity_type="event",
            entity_id=21,
        )
        create_log(
            database,
            action="CAMERA_UPDATED",
            entity_type="camera",
            entity_id=21,
        )

        result = database.get_logs_page(
            page=1,
            page_size=10,
            entity_type="event",
            entity_id=21,
        )

        assert result["total"] == 2
        assert len(result["logs"]) == 2
        assert all(
            log["entity_type"] == "event"
            and log["entity_id"] == "21"
            for log in result["logs"]
        )

    finally:
        database.close()


def test_get_logs_page_returns_newest_first(tmp_path):
    database = AuditDatabase(
        tmp_path / "audit.db"
    )

    try:
        first_id = create_log(
            database,
            action="FIRST",
            entity_type="event",
            entity_id=1,
        )
        second_id = create_log(
            database,
            action="SECOND",
            entity_type="event",
            entity_id=2,
        )

        result = database.get_logs_page(
            page=1,
            page_size=10,
        )

        assert [
            log["id"]
            for log in result["logs"]
        ] == [second_id, first_id]

    finally:
        database.close()


def test_get_logs_page_empty_page(tmp_path):
    database = AuditDatabase(
        tmp_path / "audit.db"
    )

    try:
        create_log(
            database,
            action="EVENT_CREATED",
            entity_type="event",
            entity_id=21,
        )

        result = database.get_logs_page(
            page=2,
            page_size=10,
        )

        assert result["total"] == 1
        assert result["logs"] == []

    finally:
        database.close()
