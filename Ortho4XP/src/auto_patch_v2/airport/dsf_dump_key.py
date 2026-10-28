"""The key a #25 sibling record names its pristine dump by (#1584).

A DSF serving several airports (TNCM + TFFG) keeps one row per airport
in its record; a row's edits are re-applied beside the next airport's
only when they were built against THIS pristine dump.  The row used to
name the dump by ``dump_sha256``, the sha256 of DSFTool's printed
``--dsf2text``.  That text's ``HEIGHTS`` row follows memory DSFTool
over-reads (``dsf_heights``): one file, two dumps, two hashes, and a
sibling's edits read as stale and dropped.

:func:`dump_key` hashes the dump with its ``HEIGHTS`` row(s) EXCLUDED —
every other line is the file's own.  A row carries it as
:data:`KEY_FIELD`.  A row written before this key existed carries only
the printed hash; :func:`row_is_current` re-keys it once, when its edits
are still provably built against the same pristine file."""
from __future__ import annotations

import hashlib
import re
import typing as _t

#: the row field that holds :func:`dump_key`
KEY_FIELD = "dump_key"

_HEIGHTS_ROW = re.compile(r"^HEIGHTS\s[^\n]*(\n|$)", re.M)


def printed_sha(text: str) -> str:
    """sha256 of the dump as DSFTool printed it (the legacy key, and the
    record's top-level ``dump_sha256``)."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def dump_key(text: str) -> str:
    """sha256 of the dump with every ``HEIGHTS`` row excluded: two dumps
    of one DSF that differ only in the printed row share it."""
    return printed_sha(_HEIGHTS_ROW.sub("", text.replace("\r\n", "\n")))


def row_is_current(row: _t.Mapping, entry: _t.Mapping, key: str,
                   printed: str, backup_sha: str) -> bool:
    """Was ``row`` built against the pristine dump keyed ``key``?

    A keyed row answers by its key.  A LEGACY row (printed hash only) is
    current when that hash is this dump's printed one, or when the
    record's last write read THIS backup (``backup_sha256`` equal: the
    same pristine bytes) and the row names that write's dump: every row
    a write keeps was matched against it, so its edits still apply."""
    if row.get(KEY_FIELD):
        return row.get(KEY_FIELD) == key
    old = row.get("dump_sha256")
    if not old:
        return False
    if old == printed:
        return True
    return bool(backup_sha) and entry.get("backup_sha256") == backup_sha \
        and entry.get("dump_sha256") == old


__all__ = ["KEY_FIELD", "dump_key", "printed_sha", "row_is_current"]
