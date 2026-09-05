from database.user_database import UserDatabase
from backend.auth_password import verify_password


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class AuthService:
    """
    Handles username/password authentication.
    """

    def __init__(self, database_path=None):
        if database_path is None:
            self.database = UserDatabase()
        else:
            self.database = UserDatabase(database_path)

    def authenticate(
        self,
        username: str,
        password: str,
    ):
        user = self.database.get_user_by_username(
            username
        )

        if user is None:
            raise AuthenticationError(
                "Invalid username or password."
            )

        if not user["active"]:
            raise AuthenticationError(
                "User account is inactive."
            )

        password_valid = verify_password(
            password,
            user["password_hash"],
        )

        if not password_valid:
            raise AuthenticationError(
                "Invalid username or password."
            )

        return {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "active": bool(user["active"]),
        }

    def close(self):
        self.database.close()