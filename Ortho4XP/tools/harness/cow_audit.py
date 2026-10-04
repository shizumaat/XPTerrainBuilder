#!/usr/bin/env python3
"""THE COPY-ON-WRITE AUDIT — what a lane's cache overlay REALLY costs.

    venv/bin/python tools/harness/cow_audit.py audit  TREE [--shared DIR]
    venv/bin/python tools/harness/cow_audit.py reseed TREE --shared DIR

WHY (#338, measured 2026-10-04).  A lane's ``tmp/engine_caches/
Airport_mod_cache`` reads 29 GB under ``du`` in EVERY worktree, and the
data volume was 99% full, so the overlay was taken for seven full copies.
It is not: ``build_airport.redirect_engine_caches`` seeds it with APFS
``clonefile(2)`` and a clone shares its source's blocks.  ``du`` and
``st_blocks`` count a clone at full size — they cannot tell the two cases
apart.  The number that can is the file's PRIVATE size (``getattrlist``
``ATTR_CMNEXT_PRIVATESIZE``: the bytes that would come back if the file
were deleted).  Measured on the seven live trees: 30,326 MB apparent each,
0–130 MB private in five, 1,872 MB in one, 4,513 MB in the main tree.

``audit`` reports apparent vs private bytes (0.25 s over 2,000 files).
``reseed`` reclaims the one class that is pure waste: a file that is
PRIVATE yet BYTE-IDENTICAL to its shared counterpart (a clone whose blocks
were rewritten with the same bytes, or a real copy from a clonefile
fallback) is replaced by a fresh clone.  A file the lane REWROTE (differs
from the shared one) or DERIVED (no shared counterpart) is never touched —
those are the lane-persistent sidecars the overlay exists to keep
(``build_airport.lane_cache_root``).

The caller (``lane_worktree.sh reclaim``) owns the "no build is running in
this tree" refusal; this module is the pure half and has the twin.
"""
from __future__ import annotations

import argparse
import ctypes
import filecmp
import os
import struct
import sys
from pathlib import Path

_FSOPT_NOFOLLOW = 0x1
_FSOPT_ATTR_CMN_EXTENDED = 0x20
_ATTR_CMNEXT_PRIVATESIZE = 0x8


class _AttrList(ctypes.Structure):
    _fields_ = [("bitmapcount", ctypes.c_ushort), ("reserved", ctypes.c_ushort),
                ("commonattr", ctypes.c_uint32), ("volattr", ctypes.c_uint32),
                ("dirattr", ctypes.c_uint32), ("fileattr", ctypes.c_uint32),
                ("forkattr", ctypes.c_uint32)]


def _libsystem():
    """libSystem with ``getattrlist``, or None off macOS.  Cached."""
    if not hasattr(_libsystem, "lib"):
        lib = None
        if sys.platform == "darwin":
            try:
                lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            except OSError:
                lib = None
        _libsystem.lib = lib                        # type: ignore[attr-defined]
    return _libsystem.lib                           # type: ignore[attr-defined]


def private_bytes(path) -> int | None:
    """Bytes of ``path`` NO other file shares — what deleting it frees.

    0 for an untouched clone, the full allocation for a real copy.  None
    where the filesystem cannot say (not macOS, or not APFS): the caller
    reports "not measurable" rather than guessing.  Never raises.
    """
    lib = _libsystem()
    if lib is None:
        return None
    request = _AttrList(5, 0, 0, 0, 0, 0, _ATTR_CMNEXT_PRIVATESIZE)
    buf = ctypes.create_string_buffer(32)
    try:
        rc = lib.getattrlist(os.fsencode(str(path)), ctypes.byref(request),
                             buf, len(buf),
                             _FSOPT_ATTR_CMN_EXTENDED | _FSOPT_NOFOLLOW)
    except Exception:
        return None
    if rc != 0:
        return None
    length, size = struct.unpack_from("=Iq", buf.raw)
    return size if length >= 12 else None


def _regular_files(tree):
    for dirpath, _dirs, names in os.walk(tree):
        for name in names:
            path = os.path.join(dirpath, name)
            if os.path.isfile(path) and not os.path.islink(path):
                yield path


def audit_tree(tree, shared=None) -> dict:
    """Apparent vs private bytes of every regular file under ``tree``.

    With ``shared`` (the corpus dir ``tree`` was seeded from) each private
    file is also classified: ``identical`` (reclaimable by :func:`reseed_tree`),
    ``rewritten`` (differs from the shared file) or ``lane_only`` (no shared
    counterpart).  ``measurable`` is False where :func:`private_bytes`
    cannot answer; the byte counts are then apparent sizes only.
    """
    out = {"files": 0, "apparent": 0, "private": 0, "measurable": True,
           "identical": [0, 0], "rewritten": [0, 0], "lane_only": [0, 0],
           "reclaimable": []}
    for path in _regular_files(tree):
        allocated = os.lstat(path).st_blocks * 512
        private = private_bytes(path)
        out["files"] += 1
        out["apparent"] += allocated
        if private is None:
            out["measurable"] = False
            continue
        out["private"] += private
        if not private or shared is None:
            continue
        twin = os.path.join(shared, os.path.relpath(path, tree))
        if not os.path.isfile(twin):
            kind = "lane_only"
        elif filecmp.cmp(path, twin, shallow=False):
            kind = "identical"
            out["reclaimable"].append((path, twin))
        else:
            kind = "rewritten"
        out[kind][0] += 1
        out[kind][1] += private
    return out


def reseed_tree(tree, shared) -> dict:
    """Replace every private-but-identical file under ``tree`` with a clone
    of its ``shared`` counterpart; keep everything the lane rewrote or
    derived.  Returns the audit plus ``recloned`` / ``failed`` counts.

    The clone is made beside the target and renamed over it, so a reader
    never sees a missing or partial file; a clone that cannot be made
    (cross-volume, not APFS) leaves the original in place and is counted.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shared_repo_guard import _clonefile
    out = audit_tree(tree, shared)
    out["recloned"] = out["failed"] = 0
    for path, twin in out["reclaimable"]:
        scratch = f"{path}.reclone.{os.getpid()}"
        if _clonefile(twin, scratch):
            os.replace(scratch, path)
            out["recloned"] += 1
        else:
            out["failed"] += 1
    return out


def _mb(count: int) -> str:
    return f"{count / 1e6:,.0f} MB"


def describe(report: dict) -> str:
    """One ``[ritual]``-style line per fact, for the shell entry."""
    if not report["files"]:
        return "empty (the first build seeds it)"
    if not report["measurable"]:
        return (f"{report['files']} file(s), {_mb(report['apparent'])} apparent; "
                "private size NOT MEASURABLE here (needs macOS + APFS)")
    text = (f"{report['files']} file(s), {_mb(report['apparent'])} apparent, "
            f"{_mb(report['private'])} PRIVATE (real disk)")
    for kind, label in (("identical", "identical to shared — reclaimable"),
                        ("rewritten", "rewritten by the lane"),
                        ("lane_only", "derived by the lane")):
        if report[kind][0]:
            text += f"; {report[kind][0]} {label} ({_mb(report[kind][1])})"
    if "recloned" in report:
        text += f"; RECLONED {report['recloned']}, failed {report['failed']}"
    return text


def main(argv=None) -> int:
    # The console is UTF-8 before the parser can print (#171, #125); a
    # library with a CLI pins in its entry.  Twin: test_console_encoding.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=("audit", "reseed"))
    parser.add_argument("tree", type=Path)
    parser.add_argument("--shared", type=Path, default=None,
                        help="the corpus dir the tree was seeded from")
    args = parser.parse_args(argv)
    if args.action == "reseed":
        if args.shared is None or not args.shared.is_dir():
            parser.error("reseed needs --shared, an existing corpus dir")
        report = reseed_tree(str(args.tree), str(args.shared))
    else:
        report = audit_tree(str(args.tree),
                            str(args.shared) if args.shared else None)
    print(describe(report))
    # FULL COPY: most of a non-trivial tree is private.  Exit 3 so the
    # shell entry can flag it; never a failure of the audit itself.
    full_copy = (report["measurable"] and report["apparent"] > 1 << 20
                 and report["private"] * 2 > report["apparent"])
    if args.action == "reseed":
        return 1 if report["failed"] else 0
    return 3 if full_copy else 0


if __name__ == "__main__":
    sys.exit(main())
