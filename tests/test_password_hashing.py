from backend.auth_password import (
    hash_password,
    verify_password,
)


def main():
    print("PASSWORD HASHING TEST")
    print()

    password = "HotelSecurity@2026"

    print("Original password:")
    print(password)

    hashed_password = hash_password(password)

    print()
    print("Generated hash:")
    print(hashed_password)

    print()
    print("Checking that password is not stored as plain text...")

    if hashed_password != password:
        print("PASS: Password is hashed.")
    else:
        print("FAIL: Password was not hashed.")

    print()
    print("Testing correct password...")

    correct_result = verify_password(
        password,
        hashed_password,
    )

    print(
        f"Correct password result: "
        f"{correct_result}"
    )

    print()
    print("Testing incorrect password...")

    incorrect_result = verify_password(
        "WrongPassword123!",
        hashed_password,
    )

    print(
        f"Incorrect password result: "
        f"{incorrect_result}"
    )

    print()

    if correct_result is True and incorrect_result is False:
        print("PASS: Password verification works.")
    else:
        print("FAIL: Password verification failed.")

    print()
    print("PASSWORD HASHING TEST COMPLETE")


if __name__ == "__main__":
    main()