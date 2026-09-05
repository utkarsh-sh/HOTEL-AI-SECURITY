from database.event_database import EventDatabase


def main():

    print("=" * 60)
    print("HOTEL AI CCTV - EVENT DATABASE TEST")
    print("=" * 60)

    database = EventDatabase(
        "database/test_hotel_security.db"
    )

    print("Database initialized.")

    # --------------------------------------------------
    # Create test event
    # --------------------------------------------------

    event_id = database.create_event(
        event_type="INTRUSION",
        severity="HIGH",
        camera_id="CAM-001",
        zone_id="restricted_01",
        zone_name="Restricted Area",
        track_id=7,
        message=(
            "Person 7 entered Restricted Area"
        ),
    )

    print(
        f"Event created: ID={event_id}"
    )

    # --------------------------------------------------
    # Read event
    # --------------------------------------------------

    event = database.get_event(
        event_id
    )

    print("\nStored event:")

    for key in event.keys():

        print(
            f"  {key}: {event[key]}"
        )

    # --------------------------------------------------
    # Test status update
    # --------------------------------------------------

    database.update_status(
        event_id,
        "ACKNOWLEDGED",
    )

    event = database.get_event(
        event_id
    )

    print(
        f"\nAfter acknowledgement: "
        f"{event['status']}"
    )

    database.update_status(
        event_id,
        "DISPATCHED",
    )

    event = database.get_event(
        event_id
    )

    print(
        f"After dispatch: "
        f"{event['status']}"
    )

    database.update_status(
        event_id,
        "RESOLVED",
        resolution="Security team verified incident.",
    )

    event = database.get_event(
        event_id
    )

    print(
        f"After resolution: "
        f"{event['status']}"
    )

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------

    database.close()

    print("\n" + "=" * 60)
    print("DATABASE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()