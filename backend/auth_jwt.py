import os
from datetime import datetime, timedelta, timezone

import jwt


JWT_SECRET_KEY = os.getenv(
    "HOTEL_SECURITY_JWT_SECRET",
    "development-only-change-this-secret",
)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class JWTError(Exception):
    """Raised when a JWT is invalid or expired."""


def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"],
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        required_fields = [
            "sub",
            "username",
            "full_name",
            "role",
            "iat",
            "exp",
        ]

        for field in required_fields:
            if field not in payload:
                raise JWTError(
                    f"Missing JWT field: {field}"
                )

        return payload

    except jwt.ExpiredSignatureError:
        raise JWTError("Token has expired.")

    except jwt.InvalidTokenError:
        raise JWTError("Invalid token.")