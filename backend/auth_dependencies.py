from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth_jwt import (
    JWTError,
    decode_access_token,
)
from database.user_database import UserDatabase


security = HTTPBearer()


def authenticate_token(
    token: str,
    database_path=None,
):
    """
    Validate a JWT and load the current user from the database.

    This helper is separated from FastAPI dependencies so it can
    be tested independently.
    """

    try:
        payload = decode_access_token(token)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    database = (
        UserDatabase()
        if database_path is None
        else UserDatabase(database_path)
    )

    try:
        user = database.get_user(user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user["active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "active": bool(user["active"]),
        }

    finally:
        database.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    FastAPI dependency for authenticated requests.
    """

    return authenticate_token(
        credentials.credentials
    )


def require_roles(*allowed_roles):
    """
    FastAPI dependency factory for role-based access control.
    """

    def role_checker(
        current_user: dict = Depends(get_current_user),
    ):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker