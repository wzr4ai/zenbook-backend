"""ULID helpers."""

import ulid

ULID_LENGTH = 26


def generate_ulid() -> str:
    """Return a string ULID for primary keys."""
    return str(ulid.new())
