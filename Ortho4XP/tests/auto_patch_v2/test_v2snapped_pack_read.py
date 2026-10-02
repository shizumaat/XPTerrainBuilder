"""EVERY PRODUCTION ``ResourceCache`` CARRIES THE §51 (6) INPUT QUANTUM —
STANDING LAW (owner RULINGS 2026-10-02v (4), issue #222, lane ``snap222``).

``airport/obj8.ResourceCache.__init__`` takes the quantum as its SECOND
argument and defaults it to ``0.0``.  At ``0`` every
``frame_entry.enter`` under the cache runs the affine and the validity
repair and SKIPS THE SNAP (§51 (2) (b)) — which the class documents as
the synthetic-twin frame, "a caller that built the cache without a law".
A production pack reader built that way reads geometry the law does not
have, and the default is silent: nothing fails, the map is simply a
different map.

MEASURED (lane ``sweep1005attr``, KCLT at main ``219fbccd``, capture
``frames/sweep1005attr/KCLT.pkl``).  ``pipeline/build.pack_stage`` built
its cache WITHOUT the quantum while ``planar/build.build_planar``,
``planar/basins``, ``airport/basin_witness``, ``airport/skirt`` and
``planar/__main__`` all built theirs WITH it:

    read          tunnel_ramp at 35.2217, -80.9417      planar vertices
    unsnapped     face + structure_rim / tunnel_wall     22,263
    snapped       neither                                22,249

and the surface moved with it: 2,381 row-side values apart, worst
1.12 m on the building pads at 35.22179501, -80.94166620.  The owner
ruled the SNAPPED read is the law and the build is what changes.

So the law this twin pins: a non-test module that constructs a
``ResourceCache`` passes the quantum — positionally or as
``input_quantum_m=`` — and takes it through the package's ONE accessor
(``airport/frame_entry.quantum``; §51 (6) forbids a second copy of
``emit.identity.input_quantum_m``).  A quantum-less construction is the
defect, whatever that call site reads today, UNLESS it is in
:data:`_REGISTER` with its reason — and the only reasons that register
entry admits are a SYNTHETIC TWIN FRAME and the class's own documented
lawless default, never a production pack read.

SCOPE.  Every module under ``src/`` (``auto_patch_v2`` is the engine,
RULINGS 2026-09-13au) and every tool under ``Ortho4XP/tools/`` and the
repo-root ``tools/`` — a measuring or replaying tool that reads the pack
on another grid than the build reports geometry the build does not have,
which is the same defect wearing a tool's clothes (the replay mirror,
``tools/v2_solve_replay.py``, is why issue #222 was found at all).
``tests/`` is out of scope: a twin frame is exactly where quantum 0 is
lawful.
"""
from __future__ import annotations

import ast
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2]
REPO = ENGINE.parent

#: The constructor names a call site can spell.  ``ResourceCache`` is the
#: class; ``_RCache`` is the local alias ``pipeline/build`` and the
#: replay tools import it under.
_CTOR_NAMES = ("ResourceCache", "_RCache")

#: The quantum's keyword spelling, when a call site does not pass it
#: positionally.
_QUANTUM_KW = "input_quantum_m"

#: THE REASONED REGISTER.  ``"<relpath>:<code line, stripped>"`` -> the
#: one-line reason a quantum-less construction is lawful THERE.  Keyed by
#: the LINE TEXT, not a line number, so an entry cannot drift onto a
#: neighbouring call as the file moves.  An entry is admissible only for
#: a SYNTHETIC TWIN FRAME or the class's own documented lawless default
#: (§51 (2) (b)) — a production pack reader never belongs here, and the
#: owner's ruling is what that costs (issue #222).
_REGISTER: dict[str, str] = {
    "Ortho4XP/src/auto_patch_v2/airport/obj8.py:"
    "cache = cache or ResourceCache(thickness_m)":
        "the class's own module and its documented lawless default: "
        "``read_placed_objects`` is handed no law, and its only "
        "production caller (airport/basin_witness.py) always passes a "
        "cache built with ``frame_entry.quantum(law)``, so this fallback "
        "is reached only by a caller that has no law — the synthetic "
        "twin frame §51 (2) (b) describes.",
}


def _scoped_files() -> list[Path]:
    out = sorted((ENGINE / "src").rglob("*.py"))
    for d in (ENGINE / "tools", REPO / "tools"):
        if d.is_dir():
            out.extend(sorted(p for p in d.rglob("*.py")
                              if not p.name.startswith("test_")))
    return out


def _ctor_name(func: ast.expr) -> str | None:
    """The constructor name this call spells, or ``None``."""
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return None
    return name if name in _CTOR_NAMES else None


def _has_quantum(call: ast.Call) -> bool:
    """The §51 (6) quantum reaches the constructor.

    Positionally it is the SECOND argument; a ``*args`` / ``**kwargs``
    splat is counted as carrying it (the call site is then not readable
    statically and the pin would be a false red).
    """
    if any(isinstance(a, ast.Starred) for a in call.args):
        return True
    if len(call.args) >= 2:
        return True
    return any(kw.arg == _QUANTUM_KW or kw.arg is None for kw in call.keywords)


def _constructions() -> list[tuple[Path, int, str, ast.Call]]:
    found: list[tuple[Path, int, str, ast.Call]] = []
    for path in _scoped_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        tree = ast.parse(text, str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _ctor_name(node.func) is None:
                continue
            line = lines[node.lineno - 1].strip()
            found.append((path, node.lineno, line, node))
    return found


def test_the_twin_sees_the_constructions():
    """Recall guard: the sweep finds the known population.

    A scope or name-matching regression makes every pin below vacuous,
    which is the one way this twin could go quietly useless.
    """
    found = _constructions()
    rels = {p.relative_to(REPO).as_posix() for p, _n, _l, _c in found}
    for expect in ("Ortho4XP/src/auto_patch_v2/pipeline/build.py",
                   "Ortho4XP/src/auto_patch_v2/planar/build.py",
                   "Ortho4XP/src/auto_patch_v2/airport/obj8.py",
                   "Ortho4XP/tools/v2_solve_replay.py"):
        assert expect in rels, f"{expect} no longer in the twin's sweep"
    assert len(found) >= 12, f"only {len(found)} constructions found"


def test_the_register_is_live():
    """Every register entry names a construction that still exists.

    A stale entry is how an allowlist outlives the call it excused.
    """
    keys = {f"{p.relative_to(REPO).as_posix()}:{line}"
            for p, _n, line, _c in _constructions()}
    stale = sorted(k for k in _REGISTER if k not in keys)
    assert not stale, (
        "stale _REGISTER entries (the construction is gone or its line "
        "changed — delete the entry or re-key it):\n  " + "\n  ".join(stale))


def test_no_production_resource_cache_is_unsnapped():
    """§51 (6) / RULINGS 2026-10-02v (4): no non-test module builds a
    ``ResourceCache`` without the input quantum unless the register says
    why."""
    offenders: list[str] = []
    for path, lineno, line, call in _constructions():
        if _has_quantum(call):
            continue
        rel = path.relative_to(REPO).as_posix()
        if f"{rel}:{line}" in _REGISTER:
            continue
        offenders.append(f"{rel}:{lineno}: {line}")
    assert not offenders, (
        "ResourceCache built WITHOUT the §51 (6) input quantum — at 0 the "
        "pack enters unsnapped (§51 (2) (b)) and the build reads geometry "
        "the law does not have (issue #222: a KCLT tunnel_ramp at 35.2217, "
        "-80.9417 and 2,381 row-side values, worst 1.12 m).  Pass "
        "``frame_entry.quantum(law)``, or add a reasoned _REGISTER entry "
        "if the site really is a synthetic twin frame:\n  "
        + "\n  ".join(offenders))


def test_the_quantum_comes_through_the_one_accessor():
    """§51 (6): the quantum argument comes from ``frame_entry.quantum`` —
    never a SECOND read of ``emit.identity.input_quantum_m`` taken at the
    construction itself.

    What this refuses is the ATTRIBUTE CHAIN (``law.tables.emit.identity.
    input_quantum_m`` and its spellings): a call site reaching into the
    law tables for the value the accessor exists to own.  A plain NAME is
    fine — that is a quantum handed down by a caller that did read it
    through the accessor (``tools/obj8_split_report.admit_skipped``'s
    parameter), which is the one lawful way a site without a law in scope
    can be snapped.
    """
    bad: list[str] = []
    for path, lineno, line, call in _constructions():
        if not _has_quantum(call) or len(call.args) < 2:
            continue
        arg = call.args[1]
        if isinstance(arg, ast.Attribute) and arg.attr == _QUANTUM_KW:
            bad.append(f"{path.relative_to(REPO).as_posix()}:{lineno}: "
                       f"{ast.unparse(arg)}")
    assert not bad, (
        "the quantum is read at the construction instead of through "
        "``airport/frame_entry.quantum`` — §51 (6) keeps ONE copy of "
        "``emit.identity.input_quantum_m`` for this package:\n  "
        + "\n  ".join(bad))


def test_the_build_and_planar_caches_agree():
    """The two sites issue #222 found apart now read the same accessor.

    A line-text pin, deliberately: this is the pair whose silent
    divergence moved every pack airport's surface, and the twin is what
    makes a future edit to either one visible.
    """
    for rel in ("src/auto_patch_v2/pipeline/build.py",
                "src/auto_patch_v2/planar/build.py"):
        text = (ENGINE / rel).read_text(encoding="utf-8")
        assert "_fe.quantum(law)" in text, (
            f"{rel} no longer builds its pack ``ResourceCache`` through "
            "``frame_entry.quantum(law)`` (RULINGS 2026-10-02v (4))")


def test_the_partition_cache_version_covers_the_fix():
    """The cached partition's key had to move with the fix.

    ``pipeline.build`` is not in ``partition_cache._CODE_MODULES``, so the
    code digest cannot see that the build's cache now snaps — every
    payload written before the fix holds an UNSNAPPED reading, and only
    the version bump stops one being served to a snapped build.
    """
    from auto_patch_v2.airport import partition_cache as PC
    assert "auto_patch_v2.pipeline.build" not in PC._CODE_MODULES, (
        "``pipeline.build`` joined _CODE_MODULES — re-reason this pin: the "
        "digest would then cover the build's own cache construction")
    assert PC.CACHE_VERSION >= 9, (
        "a stale pre-#222 partition payload (an unsnapped pack reading) "
        "would be served to a snapped build")
