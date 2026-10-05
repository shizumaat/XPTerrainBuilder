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

__all__ = ["CODE_MODULES", "ENTRY_MODULES", "PLUMBING_MODULES",
           "DIGEST_FILENAME", "digest_of", "source_path", "freeze_digest",
           "write_freeze_digest", "frozen_digest"]

#: The file the freeze writes beside this module (one line: the digest).
DIGEST_FILENAME = "partition_code.sha256"

#: The modules the cached reading runs through — their source bytes are
#: the code half of the fingerprint.
#:
#: THE WHOLE STATIC IMPORT CLOSURE of the reading's entry modules
#: (:data:`ENTRY_MODULES`), every ``import`` in every function included,
#: sorted (issue #362).  The list was kept by hand until then and held 22
#: of these: ``basin_witness`` — where ``read_objects`` actually lives —
#: was not in it, while ``planar.basins``, which only re-exports that
#: name, was.  A stale HIT after a code change is the one failure this key
#: must not have, and "does the reading call into this module" is not a
#: question anyone can keep answering by eye; "does it import it" is one a
#: twin can (``tests/auto_patch_v2/test_partition_code_closure.py`` fails
#: on any module the closure has and this list has not, and on the
#: reverse).  The price is named: an edit to any of these re-reads the
#: pack once.  A package is listed as its ``__init__``.
CODE_MODULES: tuple[str, ...] = (
    "auto_patch_v2.airport.anchor_rule",
    "auto_patch_v2.airport.apt_dat",
    "auto_patch_v2.airport.backup_state",
    "auto_patch_v2.airport.basin_ring",
    "auto_patch_v2.airport.basin_witness",
    "auto_patch_v2.airport.borrow",
    "auto_patch_v2.airport.bridge_family",
    "auto_patch_v2.airport.bulk_geos",
    "auto_patch_v2.airport.cluster_profile",
    "auto_patch_v2.airport.contact",
    "auto_patch_v2.airport.contents",
    "auto_patch_v2.airport.deck_signature",
    "auto_patch_v2.airport.dsf",
    "auto_patch_v2.airport.file_hash",
    "auto_patch_v2.airport.footprint_carry",
    "auto_patch_v2.airport.footprint_connector",
    "auto_patch_v2.airport.footprint_seats",
    "auto_patch_v2.airport.footprint_unit",
    "auto_patch_v2.airport.frame_entry",
    "auto_patch_v2.airport.line_object",
    "auto_patch_v2.airport.obj8",
    "auto_patch_v2.airport.obj8_clip",
    "auto_patch_v2.airport.obj8_grade",
    "auto_patch_v2.airport.obj8_split",
    "auto_patch_v2.airport.pack",
    "auto_patch_v2.airport.pack_partition",
    "auto_patch_v2.airport.pack_work",
    "auto_patch_v2.airport.pad_block_seat",
    "auto_patch_v2.airport.placement_atom",
    "auto_patch_v2.airport.placement_body",
    "auto_patch_v2.airport.placement_boxes",
    "auto_patch_v2.airport.placement_carrier",
    "auto_patch_v2.airport.placement_census",
    "auto_patch_v2.airport.placement_cockpit",
    "auto_patch_v2.airport.placement_contact",
    "auto_patch_v2.airport.placement_cut",
    "auto_patch_v2.airport.placement_deck",
    "auto_patch_v2.airport.placement_family",
    "auto_patch_v2.airport.placement_file",
    "auto_patch_v2.airport.placement_geom",
    "auto_patch_v2.airport.placement_motion",
    "auto_patch_v2.airport.placement_orphan",
    "auto_patch_v2.airport.placement_plan",
    "auto_patch_v2.airport.placement_read",
    "auto_patch_v2.airport.placement_record",
    "auto_patch_v2.airport.placement_seams",
    "auto_patch_v2.airport.placement_seat_tilt",
    "auto_patch_v2.airport.placement_targets",
    "auto_patch_v2.airport.pool",
    "auto_patch_v2.airport.rebake_plan",
    "auto_patch_v2.airport.scatter",
    "auto_patch_v2.airport.sheet_chain",
    "auto_patch_v2.airport.skirt",
    "auto_patch_v2.geom",
    "auto_patch_v2.geom.cluster_outline",
    "auto_patch_v2.geom.pad_evidence",
    "auto_patch_v2.geom.rotated_rect",
    "auto_patch_v2.geom.triangulate",
    "auto_patch_v2.geom.union_find",
    "auto_patch_v2.law",
    "auto_patch_v2.law.airports_schema",
    "auto_patch_v2.law.base_profile_schema",
    "auto_patch_v2.law.basin_schema",
    "auto_patch_v2.law.cockpit_schema",
    "auto_patch_v2.law.cutout_schema",
    "auto_patch_v2.law.design_schema",
    "auto_patch_v2.law.eat_schema",
    "auto_patch_v2.law.flat_site_schema",
    "auto_patch_v2.law.model",
    "auto_patch_v2.law.model_types",
    "auto_patch_v2.law.rebake_schema",
    "auto_patch_v2.law.role_cap_schema",
    "auto_patch_v2.law.tables",
    "auto_patch_v2.law.terrace_schema",
    "auto_patch_v2.law.tunnel_object_schema",
    "auto_patch_v2.law.units",
    "auto_patch_v2.model.airport",
    "auto_patch_v2.model.frame",
    "auto_patch_v2.model.placement",
    "auto_patch_v2.model.planar",
    "auto_patch_v2.model.pulse",
    "auto_patch_v2.model.rebake",
    "auto_patch_v2.model.structures",
    "auto_patch_v2.planar.cluster",
)

#: Where the cached reading is ENTERED: ``pack_partition.partition_pack``,
#: ``basin_witness.read_objects`` (``planar.basins.read_objects`` is this
#: same function, re-exported) and ``planar.cluster`` (``clusters``,
#: ``connector_verdicts``).
ENTRY_MODULES: tuple[str, ...] = (
    "auto_patch_v2.airport.pack_partition",
    "auto_patch_v2.airport.basin_witness",
    "auto_patch_v2.planar.cluster",
)

#: The cache's own plumbing: in the closure (the reading's modules import
#: it to keep and revive records) and deliberately NOT in the digest — it
#: decides where a record is kept, never what the reading is, and a change
#: of record SHAPE is ``partition_cache.CACHE_VERSION`` / a suffix bump.
#: ``dem_witness`` (issue #382) is the same class: it passes the DEM's own
#: answers through untouched and decides only whether a record is served.
PLUMBING_MODULES: tuple[str, ...] = (
    "auto_patch_v2.airport.dem_witness",
    "auto_patch_v2.airport.extension_cache",
    "auto_patch_v2.airport.partition_cache",
    "auto_patch_v2.airport.partition_code",
    "auto_patch_v2.airport.topology_cache",
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


def source_path(src_root: str, name: str) -> str:
    """``name``'s source under ``src_root``: ``<name>.py``, or the
    package's ``__init__.py``."""
    base = os.path.join(src_root, *name.split("."))
    return os.path.join(base, "__init__.py") if os.path.isdir(base) else base + ".py"


def freeze_digest(src_root: str) -> str | None:
    """:func:`digest_of` over :data:`CODE_MODULES` read under ``src_root``
    (the directory holding ``auto_patch_v2``) — what the freeze writes to
    :data:`DIGEST_FILENAME`.  Equal to the checkout's own digest."""
    return digest_of((name, source_path(src_root, name)) for name in CODE_MODULES)


def write_freeze_digest(src_root: str, out_dir: str, *,
                        filename: str = DIGEST_FILENAME,
                        digest: str | None = None) -> str:
    """THE FREEZE'S ACT: write :func:`freeze_digest` of ``src_root`` to
    ``out_dir/<filename>`` (:data:`DIGEST_FILENAME` unless named) and
    return that path (the spec bundles it beside this module).  RAISES
    ``SystemExit`` when a listed module has no source — an engine frozen
    without the file would key the cache on its version again, silently.

    ``filename`` and ``digest`` make this the ONE writer of a freeze-time
    digest file: ``auto_patch.provenance_code`` (#346) passes its own name
    and its own whole-tree digest, having refused an empty one itself."""
    if digest is None:
        digest = freeze_digest(src_root)
    if not digest:
        raise SystemExit(
            "ERROR: could not digest the partition cache's code modules under "
            f"{src_root!r} (partition_code.CODE_MODULES names a module with no "
            "source file) — refusing to freeze an engine whose partition "
            "cache would key on the app version.")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(digest + "\n")
    return path


def frozen_digest(directory: str | None = None, *,
                  filename: str = DIGEST_FILENAME) -> str | None:
    """The digest the freeze wrote beside this module (``directory/
    <filename>``), or ``None`` when the file is absent or is not one
    sha256 (a checkout; an engine frozen by a spec that predates it) — the
    caller then falls back.  The ONE reader of a freeze-time digest file,
    as :func:`write_freeze_digest` is the one writer."""
    d = directory if directory is not None else os.path.dirname(
        os.path.abspath(__file__))
    try:
        with open(os.path.join(d, filename), "r", encoding="ascii") as fh:
            got = fh.read(256).strip().lower()
    except (OSError, ValueError):
        return None
    if len(got) == 64 and all(c in "0123456789abcdef" for c in got):
        return got
    return None
