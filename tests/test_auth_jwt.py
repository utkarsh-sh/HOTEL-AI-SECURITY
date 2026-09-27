import os

import jwt

from backend.auth_jwt import (
    JWTConfigurationError,
    JWTError,
    create_access_token,
    decode_access_token,
)


TEST_JWT_SECRET = "test-only-jwt-secret-for-local-tests-2026"
HS384_TEST_SECRET = "test-only-hs384-secret-for-algorithm-test-2026-long"


def main():
    print("JWT AUTHENTICATION TEST")
    print()

    print("Testing missing JWT secret...")

    previous_secret = os.environ.pop(
        "HOTEL_SECURITY_JWT_SECRET",
        None,
    )

    try:
        try:
            create_access_token(
                {
                    "id": 1,
                    "username": "security",
                    "full_name": "Security Operator",
                    "role": "SECURITY_OPERATOR",
                }
            )

            print(
                "FAIL: JWT was created without a configured secret."
            )

        except JWTConfigurationError as error:
            print(
                f"PASS: Missing secret rejected: {error}"
            )

    finally:
        if previous_secret is not None:
            os.environ["HOTEL_SECURITY_JWT_SECRET"] = previous_secret

    print()

    print("Testing weak JWT secret...")

    os.environ["HOTEL_SECURITY_JWT_SECRET"] = "too-short-secret"

    try:
        create_access_token(
            {
                "id": 1,
                "username": "security",
                "full_name": "Security Operator",
                "role": "SECURITY_OPERATOR",
            }
        )

        print(
            "FAIL: Weak JWT secret was accepted."
        )

    except JWTConfigurationError as error:
        print(
            f"PASS: Weak secret rejected: {error}"
        )

    print()

    print("Configuring test JWT secret...")

    os.environ["HOTEL_SECURITY_JWT_SECRET"] = TEST_JWT_SECRET

    print("Test JWT secret configured.")
    print()

    user = {
        "id": 1,
        "username": "security",
        "full_name": "Security Operator",
        "role": "SECURITY_OPERATOR",
    }

    print("Creating access token...")

    token = create_access_token(user)

    print("Token created successfully.")
    print()

    print("Decoding access token...")

    decoded = decode_access_token(token)

    print(
        f"User ID: {decoded['sub']}"
    )

    print(
        f"Username: {decoded['username']}"
    )

    print(
        f"Full name: {decoded['full_name']}"
    )

    print(
        f"Role: {decoded['role']}"
    )

    print()

    print("Testing decoded user data...")

    if decoded["sub"] == "1":
        print("PASS: User ID is correct.")
    else:
        print("FAIL: User ID is incorrect.")

    if decoded["username"] == "security":
        print("PASS: Username is correct.")
    else:
        print("FAIL: Username is incorrect.")

    if decoded["role"] == "SECURITY_OPERATOR":
        print("PASS: Role is correct.")
    else:
        print("FAIL: Role is incorrect.")

    print()

    print("Testing invalid token...")

    try:
        decode_access_token(
            token + "invalid"
        )

        print(
            "FAIL: Invalid token was accepted."
        )

    except JWTError as error:
        print(
            f"PASS: Invalid token rejected: {error}"
        )

    print()

    print("Testing expired token...")

    expired_payload = {
        "sub": "1",
        "username": "security",
        "full_name": "Security Operator",
        "role": "SECURITY_OPERATOR",
        "iat": 1,
        "exp": 1,
    }

    expired_token = jwt.encode(
        expired_payload,
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    try:
        decode_access_token(expired_token)

        print(
            "FAIL: Expired token was accepted."
        )

    except JWTError as error:
        print(
            f"PASS: Expired token rejected: {error}"
        )

    print()

    print("Testing wrong signing secret...")

    wrong_secret_token = jwt.encode(
        {
            "sub": "1",
            "username": "security",
            "full_name": "Security Operator",
            "role": "SECURITY_OPERATOR",
            "iat": 1,
            "exp": 4102444800,
        },
        "wrong-secret-for-testing-only-2026",
        algorithm="HS256",
    )

    try:
        decode_access_token(wrong_secret_token)

        print(
            "FAIL: Token signed with wrong secret was accepted."
        )

    except JWTError as error:
        print(
            f"PASS: Wrong-signature token rejected: {error}"
        )

    print()

    print("Testing unsupported JWT algorithm...")

    unsupported_algorithm_token = jwt.encode(
        {
            "sub": "1",
            "username": "security",
            "full_name": "Security Operator",
            "role": "SECURITY_OPERATOR",
            "iat": 1,
            "exp": 4102444800,
        },
        HS384_TEST_SECRET,
        algorithm="HS384",
    )

    try:
        decode_access_token(
            unsupported_algorithm_token
        )

        print(
            "FAIL: Unsupported JWT algorithm was accepted."
        )

    except JWTError as error:
        print(
            f"PASS: Unsupported algorithm rejected: {error}"
        )

    print()

    print("Testing missing required JWT claim...")

    incomplete_payload = {
        "sub": "1",
        "username": "security",
        "full_name": "Security Operator",
        "iat": 1,
        "exp": 4102444800,
    }

    incomplete_token = jwt.encode(
        incomplete_payload,
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    try:
        decode_access_token(incomplete_token)

        print(
            "FAIL: Token with missing required claim was accepted."
        )

    except JWTError as error:
        print(
            f"PASS: Missing required claim rejected: {error}"
        )

    print()

    print("Testing required JWT fields...")

    required_fields = [
        "sub",
        "username",
        "full_name",
        "role",
        "iat",
        "exp",
    ]

    missing = [
        field
        for field in required_fields
        if field not in decoded
    ]

    if not missing:
        print(
            "PASS: All required JWT fields are present."
        )
    else:
        print(
            f"FAIL: Missing fields: {missing}"
        )

    print()
    print("JWT AUTHENTICATION TEST COMPLETE")


if __name__ == "__main__":
    main()
