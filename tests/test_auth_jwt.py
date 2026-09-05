from backend.auth_jwt import (
    create_access_token,
    decode_access_token,
    JWTError,
)


def main():
    print("JWT AUTHENTICATION TEST")
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