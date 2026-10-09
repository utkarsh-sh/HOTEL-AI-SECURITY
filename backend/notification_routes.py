from fastapi import APIRouter, Depends, HTTPException, Query

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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    database: NotificationDatabase = Depends(_get_database),
):
    """
    Return a paginated page of notification delivery records.

    Authentication is required. Notification records are read-only
    through this API.
    """

    result = database.get_notifications_page(
        page=page,
        page_size=page_size,
    )

    return {
        "total": result["total"],
        "page": page,
        "page_size": page_size,
        "notifications": result["notifications"],
    }


@router.get("/event/{event_id}")
def get_event_notifications(
    event_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    database: NotificationDatabase = Depends(_get_database),
):
    """
    Return a paginated page of notification delivery records
    associated with an event.
    """

    result = database.get_notifications_page(
        page=page,
        page_size=page_size,
        event_id=event_id,
    )

    return {
        "event_id": event_id,
        "total": result["total"],
        "page": page,
        "page_size": page_size,
        "notifications": result["notifications"],
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
