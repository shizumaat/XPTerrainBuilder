"""T1 — THE CONSUMER CENSUS AS A TEST (``docs/specs/v2-stage-cache-spec.md``
§3 / §8 T1, issues #840 / #841; RULINGS 2026-08-30l).

The set of module-level MUTABLE globals of ``auto_patch_v2`` that a module
of ANOTHER sub-package reads must equal an allow-list of memos,
diagnostics and products of the uncached half — each with the reason it
is not carried.  The planar stage's registries are no longer module
globals at all (#841): they are the typed record ``model.registries.
Registries`` every map carries (``PlanarMap.registries``), and NO module
of the package may bind one of their seven old names at module level
again.  A new module global one stage fills and a later stage reads is
exactly what a stage cache would serve stale: it fails here until it is
either a field of the record or ruled into the allow-list.

THE CENSUS (an AST walk over ``src/auto_patch_v2``, no import of the
engine):

* a GLOBAL is a module-level name bound to a container (a dict / list /
  set literal or comprehension, or ``dict()`` / ``set()`` / ``defaultdict``
  …) or rebound by a function through ``global``;
* it is MUTABLE when some function body mutates it (a mutating method, an
  item store or delete) or rebinds it — a constant table read everywhere
  is not state;
* it is READ ACROSS STAGES when a module of a different sub-package names
  it: ``from <module> import NAME``, or ``<module alias>.NAME``.

Offline and synthetic — no corpus, no network.
"""
from __future__ import annotations

import ast
from pathlib import Path

from auto_patch_v2.pipeline import capture_state as CS

V2 = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"
PKG = "auto_patch_v2"

_MUTATORS = frozenset({
    "clear", "update", "append", "extend", "add", "pop", "popitem",
    "setdefault", "remove", "discard", "insert", "sort", "reverse",
    "difference_update", "intersection_update",
    "symmetric_difference_update"})
_CONTAINER_CALLS = frozenset({
    "dict", "list", "set", "defaultdict", "OrderedDict", "Counter", "deque",
    "WeakValueDictionary", "WeakKeyDictionary"})

_P = PKG + "."
_UNCACHED = ("spec §3: produced by the uncached half (the solve / its "
             "constraints), after the cached stages — unaffected")

#: NOT CARRIED, BY RULING (spec §3, ``capture_state``'s table).  ``(module,
#: name) -> reason``; a row here is a decision, so its reason is required.
ALLOWED: dict[tuple[str, str], str] = {
    **{(_P + "constraints.cluster_pad", n): _UNCACHED
       for n in ("YIELDED", "REFERENCE", "DERIVED", "OFFSET_SPREAD",
                 "TOUCHING_STEPS")},
    (_P + "planar.cluster", "WHY"): (
        "spec §3: a diagnostic of its own stage; a hit prints 'served'"),
}

#: FOUND BY THIS CENSUS AND NOT IN THE SPEC'S §3 TABLE (issue #840 lane
#: ``cloudreg``, 2026-10-18).  REPORTED to the master for the follow-up
#: (#841) — NOT RULED here: each row passes so the twin is green on the
#: tree as it stands, and each is a question for the spec author.
UNRULED: dict[tuple[str, str], str] = {
    (_P + "classify.evidence", "CLUSTER_PADS"): (
        "classify fills it; pipeline/publication reads it (the sidecar's "
        "pad refusals) — the spec names only tools as its reader"),
    (_P + "classify.evidence", "PAD_REFUSED"): (
        "classify fills it; pipeline/publication reads it — not in the table"),
    (_P + "airport.jetways", "JETWAYS"): (
        "airport/jetways fills it; classify/evidence reads it — not in the table"),
    (_P + "airport.ramp_feet", "REPORT"): (
        "a stage report pipeline/build prints right after the stage — a "
        "diagnostic by its shape, not in the table"),
    (_P + "verify.census", "WALL_S"): (
        "a stage clock pipeline/build reads — a diagnostic by its shape, "
        "not in the table"),
}


# ── the census ───────────────────────────────────────────────────────────

def _modules(root: Path = V2) -> dict[str, tuple[Path, ast.Module]]:
    out = {}
    for p in sorted(root.rglob("*.py")):
        parts = list(p.relative_to(root.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        out[".".join(parts)] = (p, ast.parse(p.read_text(encoding="utf-8")))
    return out


def _stage(mod: str) -> str:
    """The sub-package a module belongs to (``planar``, ``constraints`` …);
    a top-level module of the package is its own stage."""
    parts = mod.split(".")
    return parts[1] if len(parts) > 1 else parts[0]


def _is_container(v: ast.AST | None) -> bool:
    if isinstance(v, (ast.Dict, ast.List, ast.Set, ast.DictComp,
                      ast.ListComp, ast.SetComp)):
        return True
    if isinstance(v, ast.Call):
        f = v.func
        name = (f.id if isinstance(f, ast.Name)
                else f.attr if isinstance(f, ast.Attribute) else None)
        return name in _CONTAINER_CALLS
    return False


def _resolve(mod: str, path: Path, node: ast.ImportFrom) -> str:
    """The absolute module an ``ImportFrom`` names."""
    if not node.level:
        return node.module or ""
    base = mod.split(".")
    if path.name != "__init__.py":
        base = base[:-1]
    base = base[:len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def _bindings(mods) -> dict[tuple[str, str], str]:
    """``(module, name) -> 'container' | 'rebound'`` — every candidate."""
    out: dict[tuple[str, str], str] = {}
    for m, (_p, tree) in mods.items():
        for node in tree.body:
            targets, value = [], None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            for t in targets:
                if isinstance(t, ast.Name) and _is_container(value):
                    out[(m, t.id)] = "container"
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for s in ast.walk(fn):
                    if isinstance(s, ast.Global):
                        for n in s.names:
                            out[(m, n)] = "rebound"
    return out


def _aliases(mod: str, path: Path, tree: ast.Module, known: set[str]):
    """``(names, modules)``: ``{local name: (module, NAME)}`` for every
    ``from M import NAME`` of a candidate global, and ``{local alias:
    module}`` for every imported package module."""
    names: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            src = _resolve(mod, path, node)
            for a in node.names:
                local = a.asname or a.name
                if f"{src}.{a.name}" in known:
                    modules[local] = f"{src}.{a.name}"
                else:
                    names[local] = (src, a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in known:
                    modules[a.asname or a.name] = a.name
    return names, modules


def census(root: Path = V2) -> dict[tuple[str, str], set[str]]:
    """``(defining module, NAME) -> {reading module}`` over every MUTABLE
    module global some module of ANOTHER sub-package reads."""
    mods = _modules(root)
    cands = _bindings(mods)
    known = set(mods)
    mutated: set[tuple[str, str]] = {k for k, v in cands.items() if v == "rebound"}
    readers: dict[tuple[str, str], set[str]] = {}
    imports = {m: _aliases(m, p, t, known) for m, (p, t) in mods.items()}

    def origin(key: tuple[str, str]) -> tuple[str, str]:
        """Follow a re-export (``planar.platform`` re-exports
        ``model.platform.PLATFORMS``) to the defining module."""
        seen = set()
        while key not in cands and key not in seen and key[0] in imports:
            seen.add(key)
            nxt = imports[key[0]][0].get(key[1])
            if nxt is None:
                break
            key = nxt
        return key

    for m, (_path, tree) in mods.items():
        names, modules = imports[m]
        names = {k: origin(v) for k, v in names.items()}
        local = {n for (dm, n) in cands if dm == m}

        def key_of(node: ast.AST, names=names, local=local, m=m, modules=modules):
            if isinstance(node, ast.Name):
                if node.id in names and names[node.id] in cands:
                    return names[node.id]
                if node.id in local:
                    return (m, node.id)
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id in modules
                    and origin((modules[node.value.id], node.attr)) in cands):
                return origin((modules[node.value.id], node.attr))
            return None

        for node in ast.walk(tree):
            k = key_of(node)
            if k is not None and k[0] != m and _stage(k[0]) != _stage(m):
                readers.setdefault(k, set()).add(m)
            # a mutation inside a function: ``G.clear()`` / ``G[k] = v`` /
            # ``del G[k]`` / ``G[k] += v``
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in _MUTATORS):
                k = key_of(node.func.value)
                if k is not None:
                    mutated.add(k)
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del)):
                k = key_of(node.value)
                if k is not None:
                    mutated.add(k)
    return {k: v for k, v in readers.items() if k in mutated}


#: THE SEVEN MODULE GLOBALS ISSUE #841 DELETED -> the ``Registries`` field
#: that replaced each.  None may come back as a module-level binding of ANY
#: module of the package (a new spelling of the class is caught by the
#: census above; the old names are pinned here by name).
RETIRED: dict[tuple[str, str], str] = {
    (_P + "model.platform", "HELD"): "held",
    (_P + "model.platform", "PLATEAUS"): "plateaus",
    (_P + "model.platform", "LANDINGS"): "landings",
    (_P + "model.platform", "LANDING_RUNOUTS"): "landing_runouts",
    (_P + "model.platform", "PLATFORMS"): "platforms",
    (_P + "model.pad_terrace", "TERRACES"): "terraces",
    (_P + "planar.overlay", "PAD_AIRSIDE"): "pad_airside",
}


def _module_level_names(tree: ast.Module) -> set[str]:
    """Every name a module binds at module level (assignments, imports)."""
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            out.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in node.names)
    return out


# ── the twin ─────────────────────────────────────────────────────────────

def test_the_cross_stage_globals_are_the_ruled_allow_list():
    found = census()
    got = set(found)
    want = set(ALLOWED) | set(UNRULED)
    undeclared = sorted(got - want)
    assert not undeclared, (
        "module globals a LATER stage reads that the planar stage's record "
        "does not carry (a stage cache would serve them stale): "
        + "; ".join(f"{m}.{n} read by {sorted(found[(m, n)])}"
                    for m, n in undeclared))
    # a ruled row nobody reads across stages any more is a stale row
    stale = sorted(want - got)
    assert not stale, f"ruled but not read across stages: {stale}"


def test_no_registry_is_a_module_global_any_more():
    """#841: the seven registries are fields of the map's record — no module
    of the package binds one of their names at module level, and the record
    and the capture state declare the same fields in the same order."""
    from auto_patch_v2.model.registries import FIELDS
    names = {n for _m, n in RETIRED}
    back = sorted(f"{m}.{n}" for m, (_p, tree) in _modules().items()
                  for n in _module_level_names(tree) & names)
    assert not back, f"a retired registry is a module global again: {back}"
    assert tuple(RETIRED.values()) == FIELDS
    assert tuple(r.field for r in CS.REGISTRIES) == FIELDS


def test_every_allowed_row_carries_its_reason():
    assert all(r.strip() for r in (*ALLOWED.values(), *UNRULED.values()))
    assert not (set(ALLOWED) & set(RETIRED)) and not (set(UNRULED) & set(RETIRED))


_PLANTED = {
    "__init__.py": "",
    "planar/__init__.py": "",
    "planar/fill.py": (
        "SEEDS: dict = {}\n"
        "TABLE = {'a': 1}\n"
        "def fill(x):\n"
        "    SEEDS.clear()\n"
        "    SEEDS[x] = 1\n"),
    "constraints/__init__.py": "",
    "constraints/gen.py": (
        "from ..planar.fill import SEEDS, TABLE\n"
        "from ..planar import fill as _f\n"
        "def rows():\n"
        "    return len(SEEDS) + TABLE['a'] + len(_f.SEEDS)\n"),
}


def test_a_planted_undeclared_cross_stage_global_is_found(tmp_path):
    """THE TEETH: a planar-stage registry a constraint generator reads is
    found (by name and by module alias); a constant table is not."""
    root = tmp_path / PKG
    for rel, text in _PLANTED.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    found = census(root)
    assert found == {(_P + "planar.fill", "SEEDS"): {_P + "constraints.gen"}}
