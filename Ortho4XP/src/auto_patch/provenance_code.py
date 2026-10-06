"""THE PATCH FRESHNESS GATE'S CODE HALF (issue #346): ONE digest of the
engine's own source, stamped on every patch as ``o4_code``.

WHY.  The gate (``driver._auto_patch_is_current``) keyed the engine on
``O4_Version.version`` alone.  That string moves only when
``scripts/make_engine.sh`` freezes: a checkout whose solve was edited kept
"build inputs unchanged" and reused the old patch, and two engines frozen
from different commits by anything but that script carry the same string.

WHAT IS DIGESTED, AND WHY THE WHOLE TREE.  Every ``.py`` and every data
table (``.toml`` — the law, the classifier's rules) under ``src``.  The static import closure
of the patch build (``auto_patch.driver``) reached 402 of the 437 modules
there on 2026-10-05 — its function-level imports run into the tile core, which prepares
the DEM the solve reads — so a hand list would be the tree with holes in
it.  A rule has no holes: ``tests/test_auto_patch_code_digest.py`` holds
the closure inside it.

THE MECHANISM IS THE PARTITION CACHE'S (``auto_patch_v2/airport/
partition_code.py``, #362), reused: the same ``digest_of``, taken from the
sources in a checkout and written to one file by the FREEZE
(``Ortho4XP.spec`` / ``Ortho4XP_Qt.spec`` run :func:`write_freeze_digest`
with ``runpy``), which the frozen engine reads back.

STDLIB ONLY, NO RELATIVE IMPORT — the specs execute this file by path.
"""
from __future__ import annotations

import os
import runpy
import sys

__all__ = ["DIGEST_FILENAME", "SOURCE_SUFFIXES", "source_files",
           "freeze_digest", "write_freeze_digest", "frozen_digest",
           "code_digest"]

#: The file the freeze writes beside this module (one line: the digest).
DIGEST_FILENAME = "engine_code.sha256"

#: What counts as engine source: modules, and the tables they load as data.
SOURCE_SUFFIXES = (".py", ".toml")

_SKIPPED_DIRECTORIES = ("__pycache__",)


def source_files(src_root: str) -> list[tuple[str, str]]:
    """``(posix path relative to src_root, path)`` of every engine source
    file under ``src_root``, sorted — the digest's order."""
    found = []
    for directory, subdirectories, names in os.walk(src_root):
        subdirectories[:] = [d for d in subdirectories
                             if d not in _SKIPPED_DIRECTORIES]
        for name in names:
            if name.endswith(SOURCE_SUFFIXES):
                path = os.path.join(directory, name)
                relative = os.path.relpath(path, src_root)
                found.append((relative.replace(os.sep, "/"), path))
    return sorted(found)


def _partition_code() -> dict:
    """``auto_patch_v2/airport/partition_code.py``'s namespace, which owns
    ``digest_of`` and the ONE reader/writer of a freeze-time digest file.

    By PATH when its source sits beside this tree (a checkout, and the
    spec, which executes this file by path with nothing importable); by
    IMPORT in a frozen engine, which has no sources — called lazily, so
    the package is loaded by then and the import is not circular."""
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "auto_patch_v2", "airport",
        "partition_code.py")
    if os.path.isfile(path):
        return runpy.run_path(path)
    from auto_patch_v2.airport import partition_code
    return vars(partition_code)


def freeze_digest(src_root: str) -> str | None:
    """The digest of :func:`source_files`, or ``None`` when ``src_root``
    holds no engine (no ``O4_Version.py``) or a file cannot be read."""
    if not os.path.isfile(os.path.join(src_root, "O4_Version.py")):
        return None
    digest_of = runpy.run_path(os.path.join(
        src_root, "auto_patch_v2", "airport", "partition_code.py"))["digest_of"]
    return digest_of(source_files(src_root))


def write_freeze_digest(src_root: str, out_dir: str) -> str:
    """THE FREEZE'S ACT: write :func:`freeze_digest` of ``src_root`` to
    ``out_dir/``:data:`DIGEST_FILENAME` and return that path.  RAISES
    ``SystemExit`` when there is no digest to write — an engine frozen
    without the file would key its patches on the version alone again."""
    digest = freeze_digest(src_root)
    if not digest:
        raise SystemExit(
            f"ERROR: could not digest the engine source under {src_root!r} — "
            "refusing to freeze an engine whose patch freshness gate would "
            "key on the version string alone.")
    return _partition_code()["write_freeze_digest"](
        src_root, out_dir, filename=DIGEST_FILENAME, digest=digest)


def frozen_digest(directory: str | None = None) -> str | None:
    """The digest the freeze wrote beside this module, or ``None`` (a
    checkout; an engine frozen by a spec that predates the file)."""
    if directory is None:
        directory = os.path.dirname(os.path.abspath(__file__))
    return _partition_code()["frozen_digest"](directory,
                                              filename=DIGEST_FILENAME)


_CODE_DIGEST: str | None = None


def code_digest() -> str:
    """The running engine's code digest (16 hex), taken once per process.

    Frozen: the file the freeze wrote.  A checkout: the sources this
    module was imported from.  ``absent`` when neither can be had — the
    explicit "could not determine" spelling of the freshness stamps; the
    version stamp is then the only code identity, as before #346.
    """
    global _CODE_DIGEST
    if _CODE_DIGEST is None:
        digest = frozen_digest()
        if digest is None and not getattr(sys, "frozen", False):
            digest = freeze_digest(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
        _CODE_DIGEST = digest[:16] if digest else "absent"
    return _CODE_DIGEST
