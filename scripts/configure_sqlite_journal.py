"""Explicit CLI for configuring an existing SQLite database journal mode."""

import argparse
import sqlite3
import sys
from pathlib import Path

from database.sqlite_setup import configure_journal_mode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure and verify an SQLite database journal mode."
    )
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--mode",
        required=True,
        type=str.upper,
        choices=("WAL", "DELETE"),
    )
    args = parser.parse_args()
    database_path = Path(args.database)

    if not database_path.is_file():
        print(
            f"Error: database file does not exist: {database_path}",
            file=sys.stderr,
        )
        return 1

    try:
        effective_mode = configure_journal_mode(
            database_path, args.mode
        )
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        print(f"Error configuring journal mode: {exc}", file=sys.stderr)
        return 1

    print(
        f"Verified SQLite journal mode: {effective_mode} "
        f"(database: {database_path})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
