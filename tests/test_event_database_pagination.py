from database.event_database import EventDatabase


def create_event(
    database,
    event_type,
    severity,
    camera_id,
):
    return database.create_event(
        event_type=event_type,
        severity=severity,
        camera_id=camera_id,
        zone_id="zone-01",
        zone_name="Test Zone",
        track_id=1,
        message=f"{event_type} test event",
    )


def test_get_events_page_paginates_and_returns_total(tmp_path):
    database = EventDatabase(
        tmp_path / "events.db"
    )

    try:
        for index in range(5):
            create_event(
                database,
                event_type="INTRUSION",
                severity="HIGH",
                camera_id=f"CAM-{index}",
            )

        result = database.get_events_page(
            page=1,
            page_size=2,
        )

        assert result["total"] == 5
        assert len(result["events"]) == 2

        second_page = database.get_events_page(
            page=2,
            page_size=2,
        )

        assert second_page["total"] == 5
        assert len(second_page["events"]) == 2

        first_ids = {
            event["id"]
            for event in result["events"]
        }
        second_ids = {
            event["id"]
            for event in second_page["events"]
        }

        assert first_ids.isdisjoint(second_ids)

    finally:
        database.close()


def test_get_events_page_filters_in_sql(tmp_path):
    database = EventDatabase(
        tmp_path / "events.db"
    )

    try:
        create_event(
            database,
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-001",
        )
        create_event(
            database,
            event_type="FIRE",
            severity="CRITICAL",
            camera_id="CAM-002",
        )
        create_event(
            database,
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-003",
        )

        result = database.get_events_page(
            page=1,
            page_size=10,
            status="NEW",
            severity="HIGH",
            event_type="INTRUSION",
            camera_id="CAM-001",
        )

        assert result["total"] == 1
        assert len(result["events"]) == 1
        assert result["events"][0]["camera_id"] == "CAM-001"

    finally:
        database.close()


def test_get_events_page_returns_newest_first(tmp_path):
    database = EventDatabase(
        tmp_path / "events.db"
    )

    try:
        first_id = create_event(
            database,
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-001",
        )
        second_id = create_event(
            database,
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-002",
        )

        result = database.get_events_page(
            page=1,
            page_size=10,
        )

        assert [
            event["id"]
            for event in result["events"]
        ] == [second_id, first_id]

    finally:
        database.close()


def test_get_events_page_empty_page(tmp_path):
    database = EventDatabase(
        tmp_path / "events.db"
    )

    try:
        create_event(
            database,
            event_type="INTRUSION",
            severity="HIGH",
            camera_id="CAM-001",
        )

        result = database.get_events_page(
            page=2,
            page_size=10,
        )

        assert result["total"] == 1
        assert result["events"] == []

    finally:
        database.close()
