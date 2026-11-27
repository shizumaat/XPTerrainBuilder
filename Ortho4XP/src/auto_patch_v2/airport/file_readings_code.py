"""THE PER-FILE READINGS' CODE HALF (#2176 census recommendation 1, lane
``lfilecache``): per reading kind, the modules whose code the reading RUNS,
and ONE digest of their source bytes — taken from the sources in a
checkout, and from the table the FREEZE wrote in a frozen engine.

WHY NOT THE IMPORT CLOSURE.  ``partition_code`` keys the partition on the
static import closure of its entry modules, and that closure is the whole
``airport`` package: ``obj8`` imports a dozen placement readers, so the
closure of ANY reader here is 223 modules, and an edit anywhere in the pack
code would make every file's reading cold again — the miss this store
exists to avoid.  So each kind names the modules its reading EXECUTES, and
the twin (``tests/auto_patch_v2/test_file_readings.py``) runs every reader
on synthetic files under a profiler and fails on a module the reading ran
whose source the kind does not key on.  A module listed and never run only
costs a needless miss.

STDLIB ONLY, NO RELATIVE IMPORT: the specs execute this file with ``runpy``
(the ``partition_code`` rule); the shared mechanism
(``src/O4_Code_Closure.py``) is loaded by path then.
"""
from __future__ import annotations

import os

__all__ = ["READER_MODULES", "DIGEST_FILENAME", "freeze_digests",
           "write_freeze_digest", "runtime_digests"]

#: The table the freeze writes beside this module: one ``kind digest`` line.
DIGEST_FILENAME = "file_readings_code.sha256"

_A = "auto_patch_v2.airport."

#: Per kind, the modules the reading runs.  ``obj8`` is in every kind: it
#: parses the file and splits its components.
READER_MODULES: dict[str, tuple[str, ...]] = {
    # ``skirt.reading`` (RULINGS 2026-09-10af/ag): the below-zero plan union
    "skirt": tuple(_A + m for m in ("bulk_geos", "frame_entry", "obj8", "obj8_clip",
                                    "skirt")),
    # ``obj8.derive_base_profile`` (base-profile spec §1 (4))
    "base": tuple(_A + m for m in ("frame_entry", "obj8", "obj8_clip", "obj8_grade")),
    # ``deck_signature.elevated_deck`` (RULINGS 2026-09-11a, spec §17.5)
    "deck": tuple(_A + m for m in ("deck_signature", "obj8")),
    # ``terrain_model.shape_of`` (RULINGS 2026-11-13i): the file's own shape
    "terrain_shape": tuple(_A + m for m in (
        "file_verdict", "msl_feet", "obj8", "relief_skin", "rock_witness",
        "terrain_model", "terrain_rock", "terrain_shaped", "terrain_shell")
    ) + ("auto_patch_v2.geom.terrain_deck",),
    # ``contact.part_attrs`` of a component at one placement, exactly
    # (``part_readings``; census recommendation 2)
    "part": tuple(_A + m for m in ("contact", "obj8", "part_readings")),
}

try:
    import O4_Code_Closure as _closure_module
    _CLOSURE = vars(_closure_module)
except ImportError:
    import runpy as _runpy
    _CLOSURE = _runpy.run_path(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir,
        "O4_Code_Closure.py"))


def freeze_digests(src_root: str) -> dict[str, "str | None"]:
    """``{kind: digest}`` of each kind's :data:`READER_MODULES` read under
    ``src_root`` (the directory holding ``auto_patch_v2``)."""
    return {kind: _CLOSURE["modules_digest"](src_root, mods)
            for kind, mods in READER_MODULES.items()}


def write_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT: write :func:`freeze_digests` to
    ``out_dir/``:data:`DIGEST_FILENAME` and return that path.  RAISES
    ``SystemExit`` when a kind has no digest (a frozen engine would then
    keep no reading across builds, silently)."""
    return _CLOSURE["write_digest_file"](
        out_dir, DIGEST_FILENAME, freeze_digests(src_root),
        "ERROR: could not digest the per-file readings' code modules under "
        f"{src_root!r} (file_readings_code.READER_MODULES names a module with "
        "no source file) — refusing to freeze.")


_RUNTIME: "dict[str, str | None] | None" = None


def runtime_digests() -> dict[str, "str | None"]:
    """``{kind: digest}`` for THIS engine, once per process: of the sources
    in a checkout, else the table the freeze wrote.  A kind with neither is
    ``None``: the store neither reads nor writes it."""
    global _RUNTIME
    if _RUNTIME is None:
        here = os.path.dirname(os.path.abspath(__file__))
        got = freeze_digests(os.path.dirname(os.path.dirname(here)))
        if any(v is None for v in got.values()):
            frozen = _CLOSURE["read_digest_table"](here, DIGEST_FILENAME) or {}
            got = {k: got.get(k) or frozen.get(k) for k in READER_MODULES}
        _RUNTIME = got
    return dict(_RUNTIME)
