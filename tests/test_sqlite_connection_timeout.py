import pytest

from database.audit_database import AuditDatabase
from database.camera_database import CameraDatabase
from database.camera_health_database import CameraHealthDatabase
from database.event_database import EventDatabase
from database.monitoring_database import MonitoringDatabase
from database.notification_database import NotificationDatabase
from database.user_database import UserDatabase
from database.zone_database import ZoneDatabase


DATABASE_CLASSES = [
    AuditDatabase,
    CameraDatabase,
    CameraHealthDatabase,
    EventDatabase,
    MonitoringDatabase,
    NotificationDatabase,
    UserDatabase,
    ZoneDatabase,
]


@pytest.mark.parametrize(
    "database_class",
    DATABASE_CLASSES,
    ids=lambda cls: cls.__name__,
)
def test_database_connection_uses_ten_second_busy_timeout(
    database_class,
    tmp_path,
):
    database_path = tmp_path / f"{database_class.__name__}.db"
    database = database_class(database_path)

    try:
        busy_timeout = database.connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]

        assert busy_timeout == 10_000
    finally:
        database.close()
