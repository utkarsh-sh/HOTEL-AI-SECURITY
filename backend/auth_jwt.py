import os
from datetime import datetime, timedelta, timezone

import jwt


JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
MIN_JWT_SECRET_LENGTH = 32


class JWTError(Exception):
    """Raised when a JWT is invalid or expired."""


class JWTConfigurationError(RuntimeError):
    """Raised when JWT security configuration is invalid."""


def _get_jwt_secret() -> str:
    secret = os.getenv("HOTEL_SECURITY_JWT_SECRET")

    if not secret:
        raise JWTConfigurationError(
            "HOTEL_SECURITY_JWT_SECRET is not configured."
        )

    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise JWTConfigurationError(
            "HOTEL_SECURITY_JWT_SECRET must be at least "
            f"{MIN_JWT_SECRET_LENGTH} characters long."
        )

    return secret


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
        _get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
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