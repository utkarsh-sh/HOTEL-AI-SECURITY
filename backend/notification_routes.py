from fastapi import APIRouter, Depends, HTTPException

from backend.auth_dependencies import get_current_user
from database.notification_database import NotificationDatabase


router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


def _get_database():
    database = NotificationDatabase()

    try:
        yield database
    finally:
        database.close()


@router.get("")
def get_notifications(
    current_user: dict = Depends(get_current_user),
    database: NotificationDatabase = Depends(_get_database),
):
    """
    Return notification delivery records.

    Authentication is required. Notification records are read-only
    through this API.
    """

    return {
        "notifications": database.get_all_notifications()
    }


@router.get("/event/{event_id}")
def get_event_notifications(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    database: NotificationDatabase = Depends(_get_database),
):
    """
    Return notification delivery records associated with an event.
    """

    notifications = [
        notification
        for notification in database.get_all_notifications()
        if notification["event_id"] == event_id
    ]

    return {
        "event_id": event_id,
        "notifications": notifications,
    }


@router.get("/{notification_id}")
def get_notification(
    notification_id: int,
    current_user: dict = Depends(get_current_user),
    database: NotificationDatabase = Depends(_get_database),
):
    """
    Return one notification delivery record.
    """

    notification = database.get_notification(
        notification_id
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )

    return {
        "notification": notification
    }
