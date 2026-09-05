from getpass import getpass

from database.user_database import UserDatabase
from backend.auth_password import hash_password


def main():
    print("=" * 50)
    print("HOTEL AI SECURITY - CREATE VIEWER")
    print("=" * 50)
    print()

    username = input("Viewer username: ").strip()
    full_name = input("Full name: ").strip()

    password = getpass("Viewer password: ")
    confirm_password = getpass("Confirm password: ")

    if not username or not full_name or not password:
        print("ERROR: All fields are required.")
        return

    if password != confirm_password:
        print("ERROR: Passwords do not match.")
        return

    database = UserDatabase()

    try:
        existing_user = database.get_user_by_username(username)

        if existing_user is not None:
            print(f"ERROR: User '{username}' already exists.")
            return

        user_id = database.create_user(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role="VIEWER",
            active=True,
        )

        print()
        print("VIEWER USER CREATED SUCCESSFULLY")
        print()
        print(f"User ID:  {user_id}")
        print(f"Username: {username}")
        print(f"Name:     {full_name}")
        print("Role:     VIEWER")
        print("Active:   True")

    finally:
        database.close()


if __name__ == "__main__":
    main()