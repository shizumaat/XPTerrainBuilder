"""The key a #25 sibling record names its pristine dump by (#1584, #1799).

A DSF serving several airports (TNCM + TFFG) keeps one row per airport
in its record; a row's edits are re-applied beside the next airport's
only when they were built against THIS pristine dump.  The row used to
name the dump by ``dump_sha256``, the sha256 of DSFTool's printed
``--dsf2text``.  Two of that text's lines do not come from the file:

* the ``HEIGHTS`` row follows memory DSFTool over-reads
  (``dsf_heights``): one file, two dumps, two hashes (#1584);
* the ``# file: <absolute path>`` comment names wherever the DSF stood
  when it was dumped: a renamed, moved or copied pack re-dumps the same
  bytes under another path (#1799).

:func:`dump_key` hashes the dump with both EXCLUDED — every other line
is the file's own, so the key is the content's.  A row carries it as
:data:`KEY_FIELD`, and so does the record entry of every write that
uses it (the marker that its rows are content-keyed).

A row written before these keys existed is re-keyed once, when its
edits are still provably built against the same pristine file
(:func:`row_is_current`)."""
from __future__ import annotations

import hashlib
import re
import typing as _t

#: the row (and entry) field that holds :func:`dump_key`
KEY_FIELD = "dump_key"

_HEIGHTS_ROW = re.compile(r"^HEIGHTS\s[^\n]*(\n|$)", re.M)
_FILE_COMMENT = re.compile(r"^# file:[^\n]*(\n|$)", re.M)


def printed_sha(text: str) -> str:
    """sha256 of the dump as DSFTool printed it (the legacy key, and the
    record's top-level ``dump_sha256``)."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _without_heights(text: str) -> str:
    return _HEIGHTS_ROW.sub("", text.replace("\r\n", "\n"))


def dump_key(text: str) -> str:
    """sha256 of the dump with every ``HEIGHTS`` row and ``# file:``
    comment excluded: two dumps of one DSF's bytes share it, whatever
    row DSFTool printed and wherever the file stood."""
    return printed_sha(_FILE_COMMENT.sub("", _without_heights(text)))


def path_dump_key(text: str) -> str:
    """The #1584 key (``HEIGHTS`` excluded, ``# file:`` kept), which rows
    written before #1799 carry: it still names this dump when the pack
    has not moved."""
    return printed_sha(_without_heights(text))


def _entry_row_key(entry: _t.Mapping) -> str | None:
    """The one key every keyed row of a pre-#1799 ``entry`` carries (a
    write re-keys every row it keeps to its own dump), else ``None``."""
    rows = entry.get("airports")
    keys = {r.get(KEY_FIELD) for r in (rows.values() if isinstance(rows, dict)
                                       else ()) if isinstance(r, dict)}
    keys.discard(None)
    return keys.pop() if len(keys) == 1 else None


def row_is_current(row: _t.Mapping, entry: _t.Mapping, key: str,
                   printed: str, backup_sha: str, path_key: str = "") -> bool:
    """Was ``row`` built against the pristine dump keyed ``key``?

    A content-keyed row answers by its key.  A row keyed before #1799
    (the key covered the ``# file:`` path) is current when that key is
    this dump's ``path_key``, or — the pack moved — when its entry
    predates #1799 (no entry :data:`KEY_FIELD`), the record's last write
    read THIS backup (``backup_sha256`` equal: the same pristine bytes)
    and the row carries that write's key, the one every kept row shares.
    A LEGACY row (printed hash only) is current when that hash is this
    dump's printed one, or under the same backup rule with the row
    naming that write's dump."""
    same_backup = bool(backup_sha) and entry.get("backup_sha256") == backup_sha
    have = row.get(KEY_FIELD)
    if have:
        if have == key or (path_key and have == path_key):
            return True
        return same_backup and not entry.get(KEY_FIELD) \
            and have == _entry_row_key(entry)
    old = row.get("dump_sha256")
    if not old:
        return False
    if old == printed:
        return True
    return same_backup and entry.get("dump_sha256") == old


__all__ = ["KEY_FIELD", "dump_key", "path_dump_key", "printed_sha",
           "row_is_current"]
