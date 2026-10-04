"""THE SHA-256 OF A FILE ON DISK — one reader for every stamp and cache key
(lane ``v2trim``, owner RULINGS 2026-10-04c (2); it replaced four copies in
``pack``, ``dsf_write``, ``backup_state`` and ``partition_cache``).
"""
from __future__ import annotations

import hashlib

__all__ = ["sha256_file", "sha256_file_or_none"]


def sha256_file(path: str) -> str:
    """The file's SHA-256 hex digest; an unreadable file RAISES ``OSError``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file_or_none(path: str) -> str | None:
    """:func:`sha256_file`, or ``None`` where the file cannot be read (a
    missing file is an answer for a cache key, not an error)."""
    try:
        return sha256_file(path)
    except OSError:
        return None
