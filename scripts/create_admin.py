from getpass import getpass

from database.user_database import UserDatabase
from backend.auth_password import hash_password


def main():
    print("=" * 50)
    print("HOTEL AI SECURITY - CREATE ADMIN USER")
    print("=" * 50)
    print()

    username = input("Admin username: ").strip()

    if not username:
        print("ERROR: Username cannot be empty.")
        return

    full_name = input("Full name: ").strip()

    if not full_name:
        print("ERROR: Full name cannot be empty.")
        return

    password = getpass("Admin password: ")
    confirm_password = getpass("Confirm password: ")

    if not password:
        print("ERROR: Password cannot be empty.")
        return

    if password != confirm_password:
        print("ERROR: Passwords do not match.")
        return

    database = UserDatabase()

    try:
        existing_user = database.get_user_by_username(username)

        if existing_user is not None:
            print(
                f"ERROR: User '{username}' already exists."
            )
            return

        password_hash = hash_password(password)

        user_id = database.create_user(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            role="ADMIN",
            active=True,
        )

        print()
        print("ADMIN USER CREATED SUCCESSFULLY")
        print()
        print(f"User ID:  {user_id}")
        print(f"Username: {username}")
        print(f"Name:     {full_name}")
        print("Role:     ADMIN")
        print("Active:   True")
        print()
        print("Password was securely hashed with Argon2.")
        print("The password itself was not stored.")
        print()

    finally:
        database.close()


if __name__ == "__main__":
    main()