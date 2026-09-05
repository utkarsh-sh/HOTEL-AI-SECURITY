from database.user_database import UserDatabase
from backend.auth_password import hash_password
from backend.auth_service import (
    AuthService,
    AuthenticationError,
)


TEST_DATABASE = "database/test_auth.db"


def main():
    print("AUTHENTICATION SERVICE TEST")
    print()

    database = UserDatabase(TEST_DATABASE)

    password = "HotelSecurity@2026"

    database.create_user(
        username="security",
        password_hash=hash_password(password),
        full_name="Security Operator",
        role="SECURITY_OPERATOR",
    )

    database.create_user(
        username="disabled",
        password_hash=hash_password(password),
        full_name="Disabled Operator",
        role="SECURITY_OPERATOR",
        active=False,
    )

    database.close()

    auth = AuthService(TEST_DATABASE)

    print("Testing correct credentials...")

    user = auth.authenticate(
        "security",
        password,
    )

    print(
        f"Authenticated: "
        f"{user['username']} | "
        f"{user['role']}"
    )

    print()

    print("Testing incorrect password...")

    try:
        auth.authenticate(
            "security",
            "WrongPassword123!",
        )

        print(
            "FAIL: Incorrect password was accepted."
        )

    except AuthenticationError as error:
        print(
            f"PASS: Authentication rejected: {error}"
        )

    print()

    print("Testing unknown username...")

    try:
        auth.authenticate(
            "unknown",
            password,
        )

        print(
            "FAIL: Unknown username was accepted."
        )

    except AuthenticationError as error:
        print(
            f"PASS: Authentication rejected: {error}"
        )

    print()

    print("Testing inactive account...")

    try:
        auth.authenticate(
            "disabled",
            password,
        )

        print(
            "FAIL: Inactive account was accepted."
        )

    except AuthenticationError as error:
        print(
            f"PASS: Authentication rejected: {error}"
        )

    print()

    print("Testing returned user data...")

    if "password_hash" not in user:
        print(
            "PASS: Password hash is not returned."
        )
    else:
        print(
            "FAIL: Password hash is exposed."
        )

    auth.close()

    print()
    print("AUTHENTICATION SERVICE TEST COMPLETE")


if __name__ == "__main__":
    main()