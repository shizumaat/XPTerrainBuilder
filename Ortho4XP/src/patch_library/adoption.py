"""THE ADOPTION RECORD (#1699 phase 2): which library entry an airport's
patch came from, read by the build's reuse gate.

``Patches/<10°>/<tile>/o4_library_<ICAO>.json``, written by
:mod:`.apply` beside the solved files it laid down::

    {"format": "xptl-adopted-1", "icao", "tile", "entry", "version",
     "signature", "law", "solve", "patch_sha256", "publisher",
     "verified", "adopted"}

The reuse gate (``auto_patch.driver._auto_patch_is_current``) asks
:func:`verdict` FIRST.  A library patch was solved on another machine,
so its own freshness stamps name that machine's DEM, OSM and CIFP and
would never read as current here; what decides it instead is the entry's
match key (:mod:`.key`) against this machine's: the same pack, law and
solve settings reuse it and the solve is skipped, anything else re-solves
the airport locally (the fallback; design "Fallbacks", tier 3).

A record whose patch is no longer the file it laid down (a local rebuild
rewrote it) is inert: :func:`verdict` answers ``None`` and the gate reads
the patch's own stamps, as for any patch.
"""
from __future__ import annotations

import json
import os
import time

from auto_patch_v2.airport.file_hash import sha256_file as _sha256

__all__ = ["FORMAT", "FILENAME", "read", "write", "remove", "verdict"]

FORMAT = "xptl-adopted-1"
FILENAME = "o4_library_{icao}.json"


def _path(patch_dir: str, icao: str) -> str:
    """The record's path for ``icao`` in ``patch_dir``."""
    return os.path.join(patch_dir, FILENAME.format(icao=icao.upper()))


def read(patch_dir: str, icao: str) -> dict | None:
    """The record, or ``None`` when there is none (or it is unreadable)."""
    try:
        with open(_path(patch_dir, icao), encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and doc.get("format") == FORMAT else None


def write(patch_dir: str, manifest: dict, entry: str, verified: bool) -> dict:
    """Record that ``manifest``'s entry (folder ``entry``) was laid down."""
    import O4_File_Names as FNAMES
    icao = manifest["icao"].upper()
    doc = {"format": FORMAT, "icao": icao, "tile": manifest["tile"],
           "entry": entry, "version": manifest["version"],
           "pack": manifest["pack"]["name"],
           "signature": manifest["signature"], "law": manifest["law"],
           "solve": manifest["solve"], "publisher": manifest["publisher"],
           "verified": bool(verified),
           "patch_sha256": _sha256(os.path.join(patch_dir, FNAMES.auto_patch_name(icao))),
           "adopted": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    target = _path(patch_dir, icao)
    with open(target + ".tmp", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
    os.replace(target + ".tmp", target)
    return doc


def remove(patch_dir: str, icao: str) -> None:
    """Drop the record (the airport is no longer the library's)."""
    try:
        os.remove(_path(patch_dir, icao))
    except OSError:
        pass


def verdict(patch_file: str, icao: str, xp_root: str | None, tile) -> tuple | None:
    """``None`` when ``patch_file`` is not a library patch this machine
    adopted; else ``(True, "")`` when the entry still matches this
    machine (reuse, skip the solve) or ``(False, why)`` (re-solve)."""
    import O4_File_Names as FNAMES

    from . import key as _key
    doc = read(os.path.dirname(patch_file), icao)
    if doc is None or not os.path.isfile(patch_file):
        return None
    try:
        if _sha256(patch_file) != doc.get("patch_sha256"):
            return None
    except OSError:
        return None
    parsed = FNAMES.parse_tile_key(str(doc.get("tile", "")))
    if parsed is None or not xp_root:
        return False, "the library record is damaged"
    local = {"signature": _key.pack_now(xp_root, icao, *parsed).get("signature"),
             "law": _key.law_now(tile), "solve": _key.solve_now(tile)}
    why = _key.first_difference(doc, local)
    return (why is None, why or "")
