"""The whole-airport flat fast path is DELETED — and stays deleted.

Replaces ``tests/test_flat_airport_fast_path.py`` (fix cycle 2, item 1,
verdict (a)).  That file pinned the certificate's REFUSAL REASONS: one test
per subsystem that made an airport "not flat" (bridge/tunnel plate, crossing
zone, gap-fill spine, runway relief over budget, building over seat
tolerance, sampling gap, gate off, no DEM).  Read as a whole, what those
tests protected was a single property — *an airport with any of these must
not have its soft nodes seeded from the DEM and the solve skipped* — and
they protected it one escape hatch at a time.

THE EVIDENCE BASE (re-baseline 2026-08-05, ``BASELINES.md`` §1.2).  On the
four flat-world battery airports the certificate REFUSED every time, for
three distinct reasons:

    HEAZ  refused(gap-fill spine present)
    HECA  refused(gap-fill spine present)
    SPJC  refused(crossing-terrain zone present)
    KCLT  refused(eat_anchor_rect)

That is the diversity the old file enumerated, measured on real airports.
It says the path never fired where the campaign measures, and that its only
observable was a printed line — the outcome was never written to the patch,
the sidecar, the env snapshot or the frame, so recovering even this table
cost a re-run of all four builds.

So the refusal set is not re-tested here: with the path gone, refusal is
UNIVERSAL and structural.  What is tested is that it cannot come back, and
— just as important — that its deletion did not take the Tier-0/1 per-shape
machinery with it.  Those are two different things that shared a name:

  * Tier 0/1 (``FLAT_CERTIFICATE_COVERAGE``, ``lazy_certified``) defers
    building a shape's eager constraint EDGE SET.  It never writes an
    elevation.  Deferring constraint construction is an optimisation.
  * Tier 2 (deleted) wrote DEM values into ``elev`` and returned.
    Substituting the seed for the solve is a BYPASS, and under the owner's
    ruling (RULINGS 2026-08-05, "DEM is a SEED, nothing more") it is a law
    violation by construction.

SCOPE, stated honestly: these are name-level and symbol-level tripwires.
They catch the bypass returning as itself; they cannot catch a *differently
named* DEM-seed shortcut.  The instrument for that class is the constant-DEM
oracle (``tests/test_constant_dem_oracle.py``, ``tools/harness/oracle.py``),
where a node seated at the constant DEM value is a decidable predicate.

Hermetic: source/AST inspection and imports only — no fixtures, no DEM, no
build.
"""
import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

import auto_patch.config as config

_SRC = Path(__file__).resolve().parents[1] / "src" / "auto_patch"

#: Every public name the deleted module exported, plus the layout attribute
#: it stashed its refusal reason on.
_DEAD_SYMBOLS = (
    "certify_flat_airport",
    "apply_flat_airport_fast_path",
    "report_flat_certificate_fast_path",
    "FlatAirportCertificate",
    "_flat_airport_fast_path_reason",
)

#: The env gate.  A deleted gate that still reads its variable is the
#: "comment prose without its code half" failure mode in reverse.
_DEAD_ENV = "O4_FLAT_AIRPORT_FAST_PATH"


def _live_sources():
    """Every engine .py file, minus __pycache__."""
    return [p for p in _SRC.rglob("*.py") if "__pycache__" not in p.parts]


def _code_lines(path):
    """``(lineno, text)`` for lines that are not pure comments.

    The deletion deliberately leaves long comment blocks NAMING the dead
    machinery at both sites (config.py and solve.py) — that is the record of
    why it went, and it must not make this test fail.  Docstrings are left
    in as code lines: a live docstring naming these symbols would mean a
    module still documents itself as having them.
    """
    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        out.append((i, line))
    return out


def test_the_fast_path_module_is_gone():
    assert importlib.util.find_spec(
        "auto_patch.elevation_per_surface.route_profile"
        ".flat_airport_fast_path") is None, (
        "the whole-airport flat fast path is deleted (fix cycle 2 item 1): "
        "it seeded every soft node at its DEM value and returned, which is a "
        "second grading authority, not an optimisation")


def test_no_engine_module_still_references_the_bypass():
    """No live code line anywhere in the engine names a dead symbol."""
    offenders = []
    for path in _live_sources():
        for lineno, text in _code_lines(path):
            for sym in _DEAD_SYMBOLS:
                if sym in text:
                    offenders.append(f"{path.relative_to(_SRC)}:{lineno} {sym}")
    assert not offenders, (
        "the deleted fast path is referenced by live code:\n  "
        + "\n  ".join(offenders))


def test_the_env_gate_is_unreadable():
    """``O4_FLAT_AIRPORT_FAST_PATH`` is read by nothing.

    An env flag that survives its feature is worse than either: it reads as
    a live switch to the next agent and does nothing at all.
    """
    offenders = [f"{p.relative_to(_SRC)}:{n}"
                 for p in _live_sources()
                 for n, text in _code_lines(p) if _DEAD_ENV in text]
    assert not offenders, (
        f"{_DEAD_ENV} is still read at: " + ", ".join(offenders))
    assert not hasattr(config, "FLAT_AIRPORT_FAST_PATH")
    assert "FLAT_AIRPORT_FAST_PATH" not in getattr(config, "__all__", ())


def test_the_solve_cannot_return_between_the_constraints_and_the_band():
    """``solve_route_profile`` must not return once the constraint system
    exists and before the reach-band / spine / feasibility work.

    This is the SHAPE of the bypass, independent of its name.  The deleted
    path's whole action was ``seed elev from DEM; writeback(); return`` in
    exactly that window, so a re-introduction under any name has to put a
    return there too.  Structural (AST), not textual.

    The window is bounded deliberately:

      * LOWER — the ``_build_shape_constraints`` call.  Before it the two
        returns in the function are degenerate-INPUT guards ("no solver
        nodes", "no hard anchors"): they decline to solve a layout that has
        nothing to solve, they do not substitute an answer.  Those are
        legitimate and must stay legal.
      * UPPER — the hard-truth publication (``_cps_truth``), the first
        statement of the post-flex stage sequence the band consumes.

    Between those two points the solve holds a complete constraint system
    and a final runway profile.  Returning there means shipping elevations
    that no band, spine or feasibility pass ever saw — which is what the
    fast path did, and the only thing it could have done.
    """
    solve_py = _SRC / "elevation_per_surface" / "route_profile" / "solve.py"
    tree = ast.parse(solve_py.read_text())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)
               and n.name == "solve_route_profile"), None)
    assert fn is not None, "solve_route_profile vanished"

    lower = next((n.lineno for n in ast.walk(fn)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name)
                  and n.func.id == "_build_shape_constraints"), None)
    anchor = next((n.lineno for n in ast.walk(fn)
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_cps_truth"
                           for t in n.targets)), None)
    assert lower is not None and anchor is not None, (
        "the window markers moved (_build_shape_constraints / _cps_truth) — "
        "re-aim this test at the constraint build and the first statement of "
        "the post-flex stage sequence")
    assert lower < anchor

    nested = {id(n) for stmt in fn.body
              for d in ast.walk(stmt)
              if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))
              for n in ast.walk(d) if isinstance(n, ast.Return)}
    early = sorted({n.lineno for n in ast.walk(fn)
                    if isinstance(n, ast.Return)
                    and id(n) not in nested
                    and lower < n.lineno < anchor})
    assert not early, (
        f"solve_route_profile returns at line(s) {early} — after the "
        f"constraint build (line {lower}) and before the reach-band / spine / "
        f"feasibility stages (line {anchor}). That is the deleted fast path's "
        f"shape: seed from DEM, write back, skip the law.")


@pytest.mark.parametrize("name,expected", [
    ("FLAT_CERTIFICATE_COVERAGE", None),        # a bool; presence is the test
    ("FLATNESS_CERTIFICATE_RATE_FACTOR", 0.6),
    ("BUILDING_SEAT_FLATNESS_TOLERANCE_M", 0.30),
])
def test_the_tier_0_1_machinery_SURVIVES(name, expected):
    """Over-deletion guard.

    Tier 0/1 shares the word "flat" and nothing else: it decides whether to
    BUILD a shape's constraint edges eagerly, and never writes a value.  It
    is load-bearing for build time and is not part of this retirement.
    """
    assert hasattr(config, name), (
        f"config.{name} is Tier-0/1 per-shape machinery — it defers "
        f"CONSTRAINT CONSTRUCTION, it does not write elevations, and the "
        f"fast-path deletion must not have taken it")
    if expected is not None:
        assert getattr(config, name) == expected


def test_the_lazy_certificate_marker_is_still_written():
    """``lazy_certified`` is the Tier-0/1 hit-rate marker on a constraint
    entry — the certificate the deleted path *reused*.  It stays."""
    prims = importlib.import_module(
        "auto_patch.elevation_per_surface.solver_primitives")
    src = Path(prims.__file__).read_text()
    assert '"lazy_certified": True' in src, (
        "solver_primitives no longer marks lazily-certified constraint "
        "entries — that is Tier 0/1, not the deleted Tier-2 bypass")
