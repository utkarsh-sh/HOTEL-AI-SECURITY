from database.notification_database import NotificationDatabase


def create_notification(database, event_id):
    return database.create_notification(
        event_id=event_id,
        channel="CONSOLE",
        severity="HIGH",
        provider="TEST_PROVIDER",
        recipient=None,
    )


def test_get_notifications_page_paginates_and_returns_total(tmp_path):
    database = NotificationDatabase(tmp_path / "notifications.db")

    try:
        for event_id in range(5):
            create_notification(database, event_id)

        result = database.get_notifications_page(
            page=1,
            page_size=2,
        )

        assert result["total"] == 5
        assert len(result["notifications"]) == 2

        second_page = database.get_notifications_page(
            page=2,
            page_size=2,
        )

        assert second_page["total"] == 5
        assert len(second_page["notifications"]) == 2

        first_ids = {
            notification["id"]
            for notification in result["notifications"]
        }
        second_ids = {
            notification["id"]
            for notification in second_page["notifications"]
        }

        assert first_ids.isdisjoint(second_ids)

    finally:
        database.close()


def test_get_notifications_page_filters_by_event(tmp_path):
    database = NotificationDatabase(tmp_path / "notifications.db")

    try:
        create_notification(database, 10)
        create_notification(database, 10)
        create_notification(database, 20)

        result = database.get_notifications_page(
            page=1,
            page_size=10,
            event_id=10,
        )

        assert result["total"] == 2
        assert len(result["notifications"]) == 2
        assert all(
            notification["event_id"] == 10
            for notification in result["notifications"]
        )

    finally:
        database.close()


def test_get_notifications_page_returns_newest_first(tmp_path):
    database = NotificationDatabase(tmp_path / "notifications.db")

    try:
        first_id = create_notification(database, 1)
        second_id = create_notification(database, 2)

        result = database.get_notifications_page(
            page=1,
            page_size=10,
        )

        assert [
            notification["id"]
            for notification in result["notifications"]
        ] == [second_id, first_id]

    finally:
        database.close()


def test_get_notifications_page_empty_page(tmp_path):
    database = NotificationDatabase(tmp_path / "notifications.db")

    try:
        create_notification(database, 1)

        result = database.get_notifications_page(
            page=2,
            page_size=10,
        )

        assert result["total"] == 1
        assert result["notifications"] == []

    finally:
        database.close()
