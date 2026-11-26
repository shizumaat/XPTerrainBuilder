"""The built tiles that did not go into the World pack (#2226): never a
silent failure.

A tile can be built (``BuildDone`` ok) and still not reach X-Plane: its
publish into the World pack (``world_publish``) refuses a staged tile
that does not verify, a swap ``O4_World_Pack.swap_in`` refuses, or the
copy fails (disk full, a file it cannot read).  The pack then keeps its
previous version of the tile, and before #2226 only
``logs/world_pack.log`` said so (#2224: X-Plane kept serving an older
tile and the app showed nothing).

What the engine can recover it does first: ``world_publish`` publishes
a failed tile once more after :data:`RETRY_AFTER_S` (a texture another
writer was still finishing), and a short copy into the pack stays
staged for the staged sweep's retries.  What it cannot is noted here,
in the user's words (``O4_Tile_Failures`` codes
``world_publish_failed`` / ``world_publish_no_space``, the shape of a
``BuildDone.warnings`` entry plus ``tile`` and ``utc``), kept in
``logs/`` (:data:`FILE_NAME`) until the tile's next publish succeeds,
and carried on the wire by ``WorldTilesWaiting.failed``: both apps show
it on the tile pane and raise it once in a run report.
"""
from __future__ import annotations

import errno
import json
import os
import threading
import time
from typing import Iterable, Optional

import O4_File_Names as FNAMES
import O4_Tile_Failures as FAIL

from .storage_installed import write_json

__all__ = ["RETRY_AFTER_S", "FILE_NAME", "note", "clear", "entries"]

#: Seconds before the one automatic second publish of a failed tile.
RETRY_AFTER_S = 10.0
#: The record under ``logs/`` (tile name -> wire entry).
FILE_NAME = "world_publish_failed.json"

# The plain-words cause, by what refused the tile.
_REASONS = {
    "verify": "Files its scenery names were missing or unreadable when it "
              "was copied into the World pack.",
    "pack": "Copying it into the World pack came out short; the app keeps "
            "trying while it waits.",
    "staged": "Files its scenery names were missing from the copy made for "
              "the World pack.",
    "error": "The app hit a problem while copying it into the World pack.",
}
_REASONS["stage"] = _REASONS["error"]

_LOCK = threading.Lock()


def _path() -> str:
    return os.path.join(FNAMES.data_path("logs"), FILE_NAME)


def _read() -> dict:
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _code(error: Optional[BaseException], errnum: Optional[int]) -> str:
    if isinstance(error, OSError):
        errnum = error.errno
    return ("world_publish_no_space" if errnum == errno.ENOSPC
            else "world_publish_failed")


def note(tile: str, where: str, problems: Iterable[str] = (),
         error: Optional[BaseException] = None,
         report_button: bool = True, errnum: Optional[int] = None) -> dict:
    """Tile ``tile`` (``+46-115``) did not go in: ``where`` names what
    refused it (``O4_World_Pack.publish``'s ``where``: ``stage``,
    ``verify``, ``staged``, ``pack``; ``error`` for an exception),
    ``problems`` / ``error`` the technical detail, ``errnum`` the errno
    of a failed staging (``ENOSPC``: the disk is full).  The wire entry,
    recorded until :func:`clear`."""
    detail = [str(p) for p in problems][:5]
    if error is not None:
        detail.append(repr(error)[:300])
    record = FAIL.record(_code(error, errnum), "\n".join(detail),
                         reason=_REASONS.get(where, _REASONS["error"]))
    entry = FAIL.fold([record], tile, built=True,
                      report_button=report_button)[0]
    entry.update(tile=tile, utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                              time.gmtime()))
    with _LOCK:
        data = _read()
        data[tile] = entry
        write_json(_path(), data)
    return entry


def clear(tile: str) -> bool:
    """Tile ``tile`` went in (or is no longer ours to publish): forget
    its failure; whether there was one."""
    with _LOCK:
        data = _read()
        if tile not in data:
            return False
        del data[tile]
        write_json(_path(), data)
    return True


def entries() -> tuple:
    """Every recorded failure, by tile name (``WorldTilesWaiting.failed``)."""
    with _LOCK:
        data = _read()
    return tuple(data[name] for name in sorted(data)
                 if isinstance(data[name], dict))
