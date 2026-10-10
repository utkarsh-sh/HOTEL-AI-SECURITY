"""Explicit SQLite journal-mode configuration helpers."""

import os
import sqlite3
import time
from pathlib import Path
from typing import Union


DatabasePath = Union[str, Path]
_SUPPORTED_JOURNAL_MODES = {"DELETE", "WAL"}
_INITIALIZATION_TIMEOUT_SECONDS = 10.0
_RETRY_INTERVAL_SECONDS = 0.05


def configure_journal_mode(
    database_path: DatabasePath,
    journal_mode: str,
) -> str:
    """Explicitly configure and verify SQLite journal mode.

    Concurrent initializers are retried for a bounded period when SQLite
    reports a lock or busy error. Importing this module changes no database.
    """
    requested_mode = str(journal_mode).strip().upper()

    if requested_mode not in _SUPPORTED_JOURNAL_MODES:
        supported = ", ".join(sorted(_SUPPORTED_JOURNAL_MODES))
        raise ValueError(
            f"Unsupported journal mode {journal_mode!r}; "
            f"supported modes are: {supported}"
        )

    deadline = time.monotonic() + _INITIALIZATION_TIMEOUT_SECONDS

    while True:
        connection = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise sqlite3.OperationalError(
                    f"Timed out configuring SQLite journal mode "
                    f"for {database_path!s}"
                )

            connection = sqlite3.connect(
                str(database_path),
                timeout=min(1.0, remaining),
            )
            row = connection.execute(
                f"PRAGMA journal_mode={requested_mode}"
            ).fetchone()

            if not row or not isinstance(row[0], str):
                raise RuntimeError(
                    f"SQLite did not report a journal mode "
                    f"for {database_path!s}"
                )

            effective_mode = row[0].lower()
            if effective_mode != requested_mode.lower():
                raise RuntimeError(
                    f"Could not set journal mode for {database_path!s}: "
                    f"requested {requested_mode.lower()!r}, "
                    f"effective mode is {effective_mode!r}"
                )

            return effective_mode

        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            is_lock_error = "locked" in message or "busy" in message

            if not is_lock_error or time.monotonic() >= deadline:
                raise

            time.sleep(
                min(
                    _RETRY_INTERVAL_SECONDS,
                    max(0.0, deadline - time.monotonic()),
                )
            )
        finally:
            if connection is not None:
                connection.close()


def verify_journal_mode(
    database_path: DatabasePath,
    expected_mode: str,
) -> str:
    """Verify an existing SQLite journal mode without changing it."""
    requested_mode = str(expected_mode).strip().upper()

    if requested_mode not in _SUPPORTED_JOURNAL_MODES:
        supported = ", ".join(sorted(_SUPPORTED_JOURNAL_MODES))
        raise ValueError(
            f"Unsupported journal mode {expected_mode!r}; "
            f"supported modes are: {supported}"
        )

    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"SQLite database does not exist: {path}"
        )

    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro",
        uri=True,
        timeout=10.0,
    )
    try:
        row = connection.execute("PRAGMA journal_mode").fetchone()
        if not row or not isinstance(row[0], str):
            raise RuntimeError(
                f"Could not read journal mode for {path}"
            )

        effective_mode = row[0].lower()
        if effective_mode != requested_mode.lower():
            raise RuntimeError(
                f"SQLite journal mode mismatch for {path}: "
                f"expected {requested_mode.lower()!r}, "
                f"found {effective_mode!r}"
            )

        return effective_mode
    finally:
        connection.close()


def verify_configured_journal_mode(database_path: DatabasePath):
    """Verify the configured journal mode, if explicitly requested.

    HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE may be set to WAL
    or DELETE. When unset, existing application behavior is unchanged.
    This function never changes the journal mode.
    """
    expected_mode = os.getenv(
        "HOTEL_SECURITY_SQLITE_EXPECTED_JOURNAL_MODE"
    )

    if expected_mode is None or not expected_mode.strip():
        return None

    return verify_journal_mode(database_path, expected_mode)
