from pathlib import Path

from backend.auth_dependencies import (
    authenticate_token,
    require_roles,
)
from backend.auth_jwt import create_access_token
from database.user_database import UserDatabase


TEST_DATABASE = "database/test_rbac.db"


def main():
    print("RBAC AUTHENTICATION DEPENDENCY TEST")
    print()

    # Always start with a fresh test database.
    test_database_path = Path(TEST_DATABASE)

    if test_database_path.exists():
        test_database_path.unlink()

    database = UserDatabase(TEST_DATABASE)

    try:
        admin_id = database.create_user(
            username="admin",
            password_hash="test-hash-admin",
            full_name="System Administrator",
            role="ADMIN",
        )

        operator_id = database.create_user(
            username="operator",
            password_hash="test-hash-operator",
            full_name="Security Operator",
            role="SECURITY_OPERATOR",
        )

        viewer_id = database.create_user(
            username="viewer",
            password_hash="test-hash-viewer",
            full_name="Security Viewer",
            role="VIEWER",
        )

    finally:
        database.close()

    print("Created test users.")
    print()

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    admin = {
        "id": admin_id,
        "username": "admin",
        "full_name": "System Administrator",
        "role": "ADMIN",
    }

    admin_token = create_access_token(admin)

    print("Testing ADMIN authentication...")

    authenticated_admin = authenticate_token(
        admin_token,
        TEST_DATABASE,
    )

    print(
        f"Authenticated: "
        f"{authenticated_admin['username']} | "
        f"{authenticated_admin['role']}"
    )

    if authenticated_admin["role"] == "ADMIN":
        print("PASS: ADMIN role authenticated.")
    else:
        print("FAIL: ADMIN role incorrect.")

    print()

    # --------------------------------------------------------
    # SECURITY OPERATOR
    # --------------------------------------------------------

    operator = {
        "id": operator_id,
        "username": "operator",
        "full_name": "Security Operator",
        "role": "SECURITY_OPERATOR",
    }

    operator_token = create_access_token(operator)

    print("Testing SECURITY_OPERATOR authentication...")

    authenticated_operator = authenticate_token(
        operator_token,
        TEST_DATABASE,
    )

    print(
        f"Authenticated: "
        f"{authenticated_operator['username']} | "
        f"{authenticated_operator['role']}"
    )

    if authenticated_operator["role"] == "SECURITY_OPERATOR":
        print("PASS: SECURITY_OPERATOR role authenticated.")
    else:
        print("FAIL: SECURITY_OPERATOR role incorrect.")

    print()

    # --------------------------------------------------------
    # VIEWER
    # --------------------------------------------------------

    viewer = {
        "id": viewer_id,
        "username": "viewer",
        "full_name": "Security Viewer",
        "role": "VIEWER",
    }

    viewer_token = create_access_token(viewer)

    print("Testing VIEWER authentication...")

    authenticated_viewer = authenticate_token(
        viewer_token,
        TEST_DATABASE,
    )

    print(
        f"Authenticated: "
        f"{authenticated_viewer['username']} | "
        f"{authenticated_viewer['role']}"
    )

    if authenticated_viewer["role"] == "VIEWER":
        print("PASS: VIEWER role authenticated.")
    else:
        print("FAIL: VIEWER role incorrect.")

    print()

    # --------------------------------------------------------
    # ROLE PERMISSIONS
    # --------------------------------------------------------

    print("Testing ADMIN permission...")

    admin_permission = require_roles(
        "ADMIN",
        "SECURITY_OPERATOR",
    )

    admin_permission(authenticated_admin)

    print("PASS: ADMIN permission accepted.")

    print()

    print("Testing SECURITY_OPERATOR permission...")

    operator_permission = require_roles(
        "ADMIN",
        "SECURITY_OPERATOR",
    )

    operator_permission(authenticated_operator)

    print("PASS: SECURITY_OPERATOR permission accepted.")

    print()

    print("Testing VIEWER restriction...")

    viewer_permission = require_roles(
        "ADMIN",
        "SECURITY_OPERATOR",
    )

    try:
        viewer_permission(authenticated_viewer)

        print(
            "FAIL: VIEWER was incorrectly granted "
            "operator permission."
        )

    except Exception as error:
        print(
            f"PASS: VIEWER correctly rejected: "
            f"{error}"
        )

    print()

    print("RBAC AUTHENTICATION DEPENDENCY TEST COMPLETE")


if __name__ == "__main__":
    main()