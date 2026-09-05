from database.user_database import UserDatabase


TEST_DATABASE = "database/test_users.db"


def main():
    database = UserDatabase(TEST_DATABASE)

    print("Creating test users...")

    admin_id = database.create_user(
        username="admin",
        password_hash="TEST_HASH_ADMIN",
        full_name="System Administrator",
        role="ADMIN",
    )

    operator_id = database.create_user(
        username="security",
        password_hash="TEST_HASH_OPERATOR",
        full_name="Security Operator",
        role="SECURITY_OPERATOR",
    )

    viewer_id = database.create_user(
        username="auditor",
        password_hash="TEST_HASH_VIEWER",
        full_name="Security Auditor",
        role="VIEWER",
    )

    print(
        f"Created user IDs: "
        f"{admin_id}, {operator_id}, {viewer_id}"
    )

    print()
    print("All users:")

    users = database.get_all_users()

    for user in users:
        print(
            f"ID={user['id']} | "
            f"Username={user['username']} | "
            f"Name={user['full_name']} | "
            f"Role={user['role']} | "
            f"Active={user['active']}"
        )

    print()
    print("Testing username lookup...")

    user = database.get_user_by_username(
        "security"
    )

    print(
        f"Found: "
        f"{user['username']} | "
        f"{user['role']}"
    )

    print()
    print("Testing password hash protection...")

    if "password_hash" not in users[0].keys():
        print(
            "PASS: get_all_users() "
            "does not expose password_hash."
        )
    else:
        print(
            "FAIL: password_hash is exposed."
        )

    database.close()

    print()
    print("USER DATABASE TEST COMPLETE")


if __name__ == "__main__":
    main()