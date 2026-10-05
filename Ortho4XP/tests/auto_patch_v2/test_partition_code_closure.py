"""issue #362 (lane perfC362) — THE PARTITION CACHE'S CODE KEY IS THE IMPORT
CLOSURE of the reading's entry modules.

A stale HIT after a code change is the one failure the key must not have.
``partition_code.CODE_MODULES`` was a hand list of 22 modules and had
already lost the reader itself (``airport/basin_witness.read_objects``).
This twin recomputes the closure from the SOURCES — every ``import`` and
``from … import`` anywhere in a module, function-level ones included — and
fails when a module the reading imports is missing from the list (or the
list names one the closure has not: a list that only grows rots too).
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

from auto_patch_v2.airport import partition_code as PCODE

SRC = Path(__file__).resolve().parents[2] / "src"
PKG = "auto_patch_v2"


def _path(mod: str) -> "str | None":
    p = PCODE.source_path(str(SRC), mod)
    return p if os.path.isfile(p) else None


def _imports(mod: str) -> set[str]:
    """Every ``auto_patch_v2`` module ``mod`` imports, anywhere in its
    source.  ``from <package> import name`` is the submodule ``name`` where
    there is one, else the package itself (a name its ``__init__`` defines
    or re-exports — whose own imports are then followed)."""
    path = _path(mod)
    pkg = mod if path.endswith("__init__.py") else mod.rsplit(".", 1)[0]
    out: set[str] = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.split(".")[0] == PKG}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                up = pkg.split(".")
                up = up[:len(up) - (node.level - 1)]
                base = ".".join(up + ([node.module] if node.module else []))
            if base.split(".")[0] != PKG or _path(base) is None:
                continue
            if _path(base).endswith("__init__.py"):
                out |= {f"{base}.{a.name}" if _path(f"{base}.{a.name}") else base
                        for a in node.names}
            else:
                out.add(base)
    return out


def _closure(roots) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        m = stack.pop()
        if m not in seen:
            seen.add(m)
            stack.extend(_imports(m))
    return seen


def test_every_module_the_reading_imports_is_in_the_code_key():
    closure = _closure(PCODE.ENTRY_MODULES)
    keyed = set(PCODE.CODE_MODULES)
    plumbing = set(PCODE.PLUMBING_MODULES)
    missing = sorted(closure - keyed - plumbing)
    assert not missing, (
        "the cached pack reading imports these and partition_code.CODE_MODULES "
        f"does not key on them — a change there would be a STALE HIT: {missing}")
    extra = sorted(keyed - closure)
    assert not extra, f"CODE_MODULES names modules the reading does not import: {extra}"
    assert not keyed & plumbing and plumbing <= closure
    assert list(PCODE.CODE_MODULES) == sorted(keyed)          # one order, no repeats
    assert all(_path(m) for m in PCODE.CODE_MODULES)


def test_the_entry_modules_are_where_the_build_enters_the_reading():
    """``pipeline/build.pack_stage`` takes the reading from these names; if
    one moves to another module, the closure must be re-rooted there."""
    from auto_patch_v2.airport import basin_witness, pack_partition
    from auto_patch_v2.planar import basins, cluster
    text = (SRC / PKG / "pipeline" / "build.py").read_text(encoding="utf-8")
    for line in ("from ..airport.pack_partition import partition_pack as _partition_pack",
                 "from ..planar.basins import read_objects as _read_objects",
                 "from ..planar.cluster import clusters as _derive_clusters",
                 "from ..planar.cluster import connector_verdicts as _cverdicts"):
        assert line in text, line
    # ``planar.basins`` only RE-EXPORTS the reader; it is not in the key
    assert basins.read_objects is basin_witness.read_objects
    assert basin_witness.read_objects.__module__ == "auto_patch_v2.airport.basin_witness"
    assert pack_partition.partition_pack.__module__ == PCODE.ENTRY_MODULES[0]
    assert cluster.clusters.__module__ == cluster.connector_verdicts.__module__ \
        == "auto_patch_v2.planar.cluster"
    assert "auto_patch_v2.planar.basins" not in PCODE.CODE_MODULES
    assert "auto_patch_v2.airport.basin_witness" in PCODE.CODE_MODULES


def test_the_twin_bites(monkeypatch):
    """Drop one imported module from the list: the check must see it."""
    closure = _closure(PCODE.ENTRY_MODULES)
    short = tuple(m for m in PCODE.CODE_MODULES if m != "auto_patch_v2.airport.anchor_rule")
    assert "auto_patch_v2.airport.anchor_rule" in closure - set(short)
    # a function-level import is followed too (``partition_cache.resolved_digest``
    # style): ``footprint_connector`` imports ``footprint_unit`` inside a function
    src = (SRC / PKG / "airport" / "footprint_connector.py").read_text(encoding="utf-8")
    assert "\nfrom .footprint_unit" not in src and "    from .footprint_unit import" in src
    assert "auto_patch_v2.airport.footprint_unit" in _imports(
        "auto_patch_v2.airport.footprint_connector")
