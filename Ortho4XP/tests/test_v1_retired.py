"""THE TREE CANNOT RE-GROW A v1 IMPORT — the standing closure twin of the v1
retirement (session ruling (h) of the stage-B brief, lane `v1retire` round 1;
RULINGS 2026-09-13au / 13aw / 13az).

Stage B deletes 104 modules of `src/auto_patch/`.  What made that impossible
before was not the deletion but the FIVE SEAMS: a handful of import edges from
the surviving modules into the v1 tree, each of which re-admitted the whole
185k-line package into the production import closure (13aw measured 125 of 127
modules kept by a naive closure).  Round 1 cut them.  Nothing keeps them cut
except this twin, which is `docs/v1-retirement/g2.py`'s own closure promoted
into the suite:

    from every PRODUCTION ROOT — `Ortho4XP.py`, `Ortho4XP_Qt.py`, every
    `src/O4_*.py`, every module of `src/o4_engine/` and all of
    `src/auto_patch_v2/` — the static AST import closure over `src/**`
    must reach NO module under `auto_patch/` outside the KEEP SET.

It is a STATIC closure, exactly like the inventory's: the same reader, the
same resolution rule, and the same blind spot (a `getattr`/`importlib` import
is invisible to it — `tools/blast.py` is the backstop for that).  It runs in
milliseconds and needs no build.

THE KEEP SET IS DECLARED HERE, in one place, and a module joining or leaving
it is a visible edit to this file.  It is the 23 modules of 13aw plus the
three this round minted:

  * `build_support` — the helpers the driver and the flat-site detector used
    to reach into `layout` / `osm_load` / `elevation` / `object_pads` /
    `pavement.runway_geometry` for (seams S1 + S2)
  * `object_terrain_kinds` — the decision kinds and sampling steps `post_mesh`
    read out of `object_terrain_assembly` (seam S3)
  * `flat_site` — the flat-site DETECTOR: 13aw reached it only THROUGH S1 and
    so never judged it, but `flat_site_mode` (production DEM prep) IS its
    caller, and copying ~250 lines of detector law into a second spelling is
    what ruling (d) forbids.  It moved SIDE instead.

Two more lines the same cut bought, asserted here because they are the same
promise from the other end:

  * `tools/check_grade.py` — the harness library every defect count comes
    from — imports no v1 module either (seam S4; its own copy lives in
    `tools/harness/law_support/`, twinned in `tests/test_law_support.py`).
  * the WIRE PROTOCOL is untouched by all of it: `o4_engine/events.py`'s
    class names ARE the JSONL names `Sources/SceneryKit/OrthoEngineClient.swift`
    matches as string literals, and `driver` / `engine_v2` — keep modules that
    emit those events — still import `o4_engine` and nothing else new.
"""

from __future__ import annotations

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
SRC = ENGINE / "src"

#: The modules of `src/auto_patch/` the production closure MAY reach.
KEEP = frozenset({
    "auto_patch",
    # the readers
    "auto_patch.agp_reader",
    "auto_patch.apt_dat_reader",
    "auto_patch.cifp_reader",
    "auto_patch.dsf_reader",
    "auto_patch.osm_aeroway",
    "auto_patch.flat_site_mode",
    "auto_patch.flat_site",
    # the object stage
    "auto_patch.mesh_sampler",
    "auto_patch.obj8_partition",
    "auto_patch.obj8_reader",
    "auto_patch.object_anchor",
    "auto_patch.object_clusters",
    "auto_patch.object_footprints",
    "auto_patch.object_frame",
    "auto_patch.object_rebake",
    "auto_patch.object_terrain_features",
    "auto_patch.object_terrain_kinds",
    "auto_patch.post_mesh",
    # the drivers and the shared support
    "auto_patch.build_support",
    "auto_patch.config",
    "auto_patch.driver",
    "auto_patch.engine_v2",
    "auto_patch.geom_safe",
    "auto_patch.progress",
    "auto_patch.provenance",
})


def _modules() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for f in SRC.rglob("*.py"):
        parts = list(f.relative_to(SRC).parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        out[".".join(parts)] = f
    return out


def _imports_of(path: Path, pkg: str) -> set[str]:
    """Every dotted name an import statement in ``path`` names (module and
    member forms both, so ``from x import y`` resolves either way) —
    ``g2.py``'s own reader."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:                                    # pragma: no cover
        return set()
    out: set[str] = set()
    parts = pkg.split(".")
    base = parts if path.name == "__init__.py" else parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                b = (base[:len(base) - (node.level - 1)] if node.level > 1
                     else base)
                name = ".".join(b + ([node.module] if node.module else []))
            else:
                name = node.module or ""
            out.add(name)
            for a in node.names:
                out.add(f"{name}.{a.name}")
    return out


def _resolve(name: str, mods: dict[str, Path]) -> str | None:
    parts = name.split(".")
    while parts:
        cand = ".".join(parts)
        if cand in mods:
            return cand
        parts.pop()
    return None


def _is_auto_patch(m: str) -> bool:
    return m == "auto_patch" or m.startswith("auto_patch.")


def _production_roots(mods: dict[str, Path]) -> list[str]:
    """Every root the SHIPPED app and the CLI enter the engine through."""
    roots = [m for m in mods
             if m.startswith("O4_")
             or m == "o4_engine" or m.startswith("o4_engine.")
             or m == "auto_patch_v2" or m.startswith("auto_patch_v2.")]
    assert len(roots) > 60, f"the root set collapsed to {len(roots)} — a " \
                            "closure over nothing proves nothing"
    return roots


def _closure(seeds, mods):
    """(reached modules, {module: [importer:line, ...]}) — every module the
    static import graph reaches from ``seeds``, transitively."""
    seen: set[str] = set()
    why: dict[str, list[str]] = {}
    queue = list(seeds)
    # the two loose entry scripts are not importable modules
    scripts = [ENGINE / "Ortho4XP.py", ENGINE / "Ortho4XP_Qt.py"]
    for s in scripts:
        if not s.exists():                                 # pragma: no cover
            continue
        for name in _imports_of(s, s.stem):
            r = _resolve(name, mods)
            if r:
                why.setdefault(r, []).append(s.name)
                queue.append(r)
    while queue:
        m = queue.pop()
        if m in seen:
            continue
        seen.add(m)
        for name in _imports_of(mods[m], m):
            r = _resolve(name, mods)
            if r and r != m:
                why.setdefault(r, []).append(m)
                if r not in seen:
                    queue.append(r)
    return seen, why


def test_the_production_closure_reaches_no_v1_module():
    """THE LINE ITSELF.  Every DELETE module must be unreachable from every
    production root, with the v1 tree still sitting on disk."""
    mods = _modules()
    reached, why = _closure(_production_roots(mods), mods)
    v1 = sorted(m for m in reached if _is_auto_patch(m) and m not in KEEP)
    assert not v1, "the production closure reaches v1 again: " + "; ".join(
        f"{m} <- {sorted(set(why.get(m, [])))[:4]}" for m in v1)


def test_the_keep_set_is_neither_stale_nor_vacuous():
    """A keep name that no longer exists, or one nothing reaches, is a stale
    declaration — and a closure that reaches almost nothing would pass the
    test above for the wrong reason."""
    mods = _modules()
    missing = sorted(m for m in KEEP if m not in mods)
    assert not missing, f"KEEP names modules that are gone: {missing}"
    reached, _ = _closure(_production_roots(mods), mods)
    inside = {m for m in reached if _is_auto_patch(m)}
    assert len(inside) >= 20, (
        f"the closure reaches only {sorted(inside)} — it has stopped "
        "measuring anything")
    assert inside <= KEEP


def test_the_v1_tree_is_still_on_disk_in_round_1():
    """Round 1 is the SEAM cut and nothing else: the twin above must be green
    while every DELETE module still exists.  Round 2 removes them, and this
    check goes with them (it is the only line in this file that expects the
    tree to be big)."""
    mods = _modules()
    v1_left = [m for m in mods if _is_auto_patch(m) and m not in KEEP]
    if not v1_left:
        return          # round 2 has landed; the closure test above is the law
    assert len(v1_left) > 50, (
        f"only {len(v1_left)} v1 modules remain — a partial deletion is not "
        "a state this campaign has: round 2 removes them in one commit per "
        "sub-package")


def test_the_census_library_imports_no_v1_module():
    """Seam S4 from the other end: `tools/check_grade.py` is the harness
    library every defect count comes from, and it priced v2 patches with law
    that lived in eleven v1 modules until 2026-09-17."""
    src = (ENGINE / "tools" / "check_grade.py").read_text()
    tree = ast.parse(src)
    allowed = ("auto_patch.config", "auto_patch.build_support",
               "auto_patch.apt_dat_reader", "auto_patch_v2")
    offenders = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module or ""]
        for n in names:
            if n.startswith("auto_patch") and not n.startswith(allowed):
                offenders.append(f"{node.lineno}: {n}")
    assert not offenders, ("check_grade imports v1 again: "
                           + "; ".join(offenders))


def test_the_wire_protocol_names_are_untouched_by_the_retirement():
    """The silent-break hazard (repo CLAUDE.md): `o4_engine/events.py`'s class
    names ARE the JSONL wire names, matched as STRING LITERALS in
    `Sources/SceneryKit/OrthoEngineClient.swift`.  The retirement moved code
    around the emitters (`driver`, `engine_v2` — keep modules), so the twin
    states the invariant rather than trusting that nobody renamed anything."""
    events = SRC / "o4_engine" / "events.py"
    swift = ENGINE.parent / "Sources" / "SceneryKit" / "OrthoEngineClient.swift"
    if not swift.exists():                                 # pragma: no cover
        return                     # engine checked out standalone
    tree = ast.parse(events.read_text())
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    text = swift.read_text()
    matched = [c for c in classes if f'"{c}"' in text]
    assert len(matched) >= 10, (
        f"the Swift client matches only {matched} of {len(classes)} event "
        "class names — the wire protocol has drifted")
    for name in ("AutoPatchBegin", "AutoPatchProgress", "AutoPatchFailed"):
        assert name in classes, f"{name} is gone from events.py"
        assert f'"{name}"' in text, f"{name} is no longer matched in Swift"
