from database.event_database import EventDatabase


def main():

    print("=" * 60)
    print("HOTEL AI CCTV - SAVED EVENTS TEST")
    print("=" * 60)

    database = EventDatabase(
        "database/hotel_security.db"
    )

    events = database.get_all_events()

    print(
        f"Total saved events: {len(events)}"
    )

    print("-" * 60)

    for event in events:

        print(
            f"ID={event['id']} | "
            f"Type={event['event_type']} | "
            f"Severity={event['severity']} | "
            f"Status={event['status']} | "
            f"Camera={event['camera_id']} | "
            f"Zone={event['zone_name']} | "
            f"Track={event['track_id']}"
        )

    database.close()

    print("=" * 60)
    print("SAVED EVENTS TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()