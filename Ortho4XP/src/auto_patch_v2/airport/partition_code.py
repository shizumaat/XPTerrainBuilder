"""THE PARTITION CACHE'S CODE HALF (issue #362): which modules the cached
pack reading runs through, and ONE digest of their source bytes — taken
from the sources in a checkout, and from the file the FREEZE wrote in a
frozen engine.

WHY A FILE WRITTEN AT FREEZE TIME.  A frozen engine has no source files,
and until #362 the app's VERSION stood in for the code: every app update
moved every user's partition key, whether or not one line of the reading
had changed, and OTHH paid ~500 s for it on each new version.  The specs
(``Ortho4XP.spec`` / ``Ortho4XP_Qt.spec``) now run :func:`freeze_digest`
over the same sources PyInstaller is about to compile and bundle the
answer as ``auto_patch_v2/airport/partition_code.sha256``; the frozen
engine reads that file.  Same sources, same digest — in a checkout and in
every engine frozen from it.

STDLIB ONLY, NO RELATIVE IMPORT: the specs execute this one file with
``runpy`` (they never import engine packages).  Keep it that way.
"""
from __future__ import annotations

import hashlib
import os
import typing as _t

__all__ = ["CODE_MODULES", "DIGEST_FILENAME", "digest_of", "freeze_digest",
           "write_freeze_digest", "frozen_digest"]

#: The file the freeze writes beside this module (one line: the digest).
DIGEST_FILENAME = "partition_code.sha256"

#: The modules the cached reading runs through — their source bytes are
#: the code half of the fingerprint.  Import paths inside the package.
CODE_MODULES: tuple[str, ...] = (
    "auto_patch_v2.airport.pack_partition",
    "auto_patch_v2.airport.contact",
    "auto_patch_v2.airport.obj8",
    "auto_patch_v2.airport.obj8_clip",
    # the base read (``Member.base_profile``) and its composition onto the
    # cached clusters (``PlanCluster.base_profile``) run through it — a
    # change to the read was invisible to the cache (lane t3onelevel10)
    "auto_patch_v2.airport.obj8_grade",
    "auto_patch_v2.airport.frame_entry",
    "auto_patch_v2.airport.skirt",
    "auto_patch_v2.airport.bulk_geos",
    "auto_patch_v2.airport.scatter",
    "auto_patch_v2.airport.deck_signature",
    "auto_patch_v2.airport.line_object",
    "auto_patch_v2.airport.placement_boxes",
    "auto_patch_v2.airport.placement_contact",
    "auto_patch_v2.airport.placement_family",
    "auto_patch_v2.airport.pack",
    "auto_patch_v2.planar.basins",
    "auto_patch_v2.planar.cluster",
    # unit-platform spec §2: the cached clusters read the connector verdict
    "auto_patch_v2.airport.footprint_connector",
    "auto_patch_v2.airport.footprint_unit",
    # issue #104: the seat machinery split out of ``footprint_unit``
    "auto_patch_v2.airport.footprint_seats",
    "auto_patch_v2.airport.sheet_chain",
    "auto_patch_v2.model.rebake",
)


def digest_of(sources: _t.Iterable[tuple[str, "str | None"]]) -> str | None:
    """sha256 over ``name \\0 source bytes \\0`` of every ``(module name,
    source path)`` in order, or ``None`` when ANY source is missing or
    unreadable — a digest of some of the code is not a digest of the code."""
    h = hashlib.sha256()
    for name, src in sources:
        try:
            if not src or not os.path.isfile(src):
                return None
            with open(src, "rb") as fh:
                h.update(name.encode()); h.update(b"\0")
                h.update(fh.read()); h.update(b"\0")
        except OSError:
            return None
    return h.hexdigest()


def freeze_digest(src_root: str) -> str | None:
    """:func:`digest_of` over :data:`CODE_MODULES` read under ``src_root``
    (the directory holding ``auto_patch_v2``) — what the freeze writes to
    :data:`DIGEST_FILENAME`.  Equal to the checkout's own digest."""
    return digest_of((name, os.path.join(src_root, *name.split(".")) + ".py")
                     for name in CODE_MODULES)


def write_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT: write :func:`freeze_digest` of ``src_root`` to
    ``out_dir/``:data:`DIGEST_FILENAME` and return that path (the spec
    bundles it beside this module).  RAISES ``SystemExit`` when a listed
    module has no source — an engine frozen without the file would key the
    cache on its version again, silently."""
    digest = freeze_digest(src_root)
    if not digest:
        raise SystemExit(
            "ERROR: could not digest the partition cache's code modules under "
            f"{src_root!r} (partition_code.CODE_MODULES names a module with no "
            "source file) — refusing to freeze an engine whose partition "
            "cache would key on the app version.")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, DIGEST_FILENAME)
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(digest + "\n")
    return path


def frozen_digest(directory: str | None = None) -> str | None:
    """The digest the freeze wrote beside this module, or ``None`` when
    the file is absent or is not one sha256 (a checkout; an engine frozen
    by a spec that predates it) — the caller then falls back."""
    d = directory if directory is not None else os.path.dirname(
        os.path.abspath(__file__))
    try:
        with open(os.path.join(d, DIGEST_FILENAME), "r", encoding="ascii") as fh:
            got = fh.read(256).strip().lower()
    except (OSError, ValueError):
        return None
    if len(got) == 64 and all(c in "0123456789abcdef" for c in got):
        return got
    return None
