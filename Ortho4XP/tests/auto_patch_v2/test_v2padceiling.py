"""§30 THE PAD CEILING CARRIES NO AUTHORED RELIEF — the twins
(owner RULINGS 2026-09-12u; lane ``v2padceiling``).

Scout ``v2unsettled`` attributed LEMD's shipped ``HARD SET NOT SETTLED``
(725 violated hard rows, worst 1.3037 m) to a MUTUALLY INFEASIBLE PAIR of
hard rows on APRON vertices at the T4S block: ``pad_relief_offsets``
handed a rim vertex the authored −2.20 m of the nearest FOOT, and
``pads._pad_rows`` put that ``rel`` into the hard 1 % pad-slope CEILING —
2.20 m demanded over 3.0 m of apron against the 5 % pavement ceiling's
0.15 m.  Two sentences answer it, and each is twinned here:

1. THE CEILING CARRIES NO ``rel`` (§30 (1)) — the authored relief stays
   expressed by the ``pad_flat`` TARGET, where a target belongs.
2. PAVEMENT SENIORITY IS BY VERTEX (§30 (2)) — a pad rim vertex the
   AIRSIDE pavement shares takes offset 0, whatever foot is nearest.
3. THE INSTRUMENTS (§30 (3)) — the replay's capture is the build's whole
   pre-solve half or it is refused; ``hard_active`` counts the VIOLATED
   rows of the shipped surface, not phase C's multipliers; and
   ``converged`` is asserted only under the settled condition.

Hermetic: hand-built cells and a synthetic DEM, no pack, no environment.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.pads import (CEILING_RULING, pad_flats,
                                            pad_slope_ceiling)
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import design as design_law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design_roles import hard_rulings, ruling_head

RUN_LEN = 1600.0
HALF_W = 22.5
Y0, Y1 = 140.0, 260.0
PAD = ((-60.0, 180.0), (60.0, 180.0), (60.0, 240.0), (-60.0, 240.0))


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    provenance = {"synthetic": "flat"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


RUNWAY = Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
              (), 3, "D", "airside", "runway", {})


def _cells(pad_role: str = "apron"):
    """One apron (or car park) with the pad cut out of it as a hole, so the
    pad's whole rim is SHARED with that face — the LEMD T4S shape."""
    return [RUNWAY,
            Cell(1, pad_role, "faceA", _rect(-260, Y0, 260, Y1), (PAD,),
                 None, None, "airside" if pad_role == "apron" else "groundside",
                 pad_role, {}),
            Cell(2, "building", "padA", PAD, (), None, None, "airside", "pad", {})]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _pm(law, cells):
    airport = _airport(law)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return pm, airport


def _pad_vertices(pm):
    f = next(f for f in pm.faces.values() if f.ref == "padA")
    return sorted(set(pm.ring_vertices(f.ring)))


# ── (1) THE CEILING CARRIES NO AUTHORED RELIEF ──────────────────────────

def test_the_ceiling_rows_carry_rel_zero_while_the_flat_target_carries_it(
        law, monkeypatch):
    """The one sentence §30 (1) is: the same pairs, the same caps, and the
    relief on the TARGET only.  Measured at LEMD: with the relief in the
    ceiling the shipped surface violated 725 hard rows (365 of them this
    family) at 1.3037 m; without it, 0."""
    pm, airport = _pm(law, _cells())
    vs = _pad_vertices(pm)
    assert len(vs) >= 4
    # a body authored 2.20 m down at half the pad's rim — the T4S shape
    off = {v: (-2.20 if i % 2 else 0.0) for i, v in enumerate(vs)}
    monkeypatch.setattr("auto_patch_v2.constraints.pads.pad_relief_offsets",
                        lambda _p, _l, _a: off)
    ceil = pad_slope_ceiling(pm, law, airport)
    flat = pad_flats(pm, law, airport)
    assert ceil and flat
    assert {round(float(r.rel), 9) for r in ceil} == {0.0}, "the ceiling is bare"
    assert max(abs(float(r.rel)) for r in flat) == pytest.approx(2.20, abs=1e-9)
    # the ROW SET is unchanged: same pairs, same caps, same count
    assert len(ceil) == len(flat)
    assert {(r.a, r.b) for r in ceil} == {(r.a, r.b) for r in flat}
    cap = float(law.tables.emit.within_shape.pad_slope_max)
    assert {round(float(r.cap), 9) for r in ceil} == {round(cap, 9)}


def test_the_ceilings_ruling_head_still_names_the_hard_register(law):
    """``[design] hard_rulings`` selects by the ruling HEAD (everything
    before the first parenthesis), so the sentence added to the row's
    ruling must not move the row out of the hard set."""
    pm, airport = _pm(law, _cells())
    rows = pad_slope_ceiling(pm, law, airport)
    assert rows
    heads = {ruling_head(r) for r in rows}
    assert heads == {CEILING_RULING}
    assert CEILING_RULING in hard_rulings(law)


def test_a_flat_footed_body_is_the_identity_for_both(law, monkeypatch):
    """Every offset 0 (or no pack at all): the ceiling and the target are
    exactly the pre-11j rows, so nothing but a relief body changes."""
    pm, airport = _pm(law, _cells())
    monkeypatch.setattr("auto_patch_v2.constraints.pads.pad_relief_offsets",
                        lambda _p, _l, _a: {})
    for rows in (pad_slope_ceiling(pm, law, airport), pad_flats(pm, law, airport)):
        assert rows and {round(float(r.rel), 9) for r in rows} == {0.0}


# ── (2) PAVEMENT SENIORITY IS BY VERTEX ─────────────────────────────────

class _Foot:
    def __init__(self, lat, lon, y):
        self.lat, self.lon, self.y = lat, lon, y


class _Group:
    infeasible = False
    y_zero = 0.0

    def __init__(self, feet):
        self.feet = feet


class _Groups:
    def __init__(self, groups):
        self.groups = groups


def _with_feet(airport, pm, vertices, y):
    """A body whose feet sit exactly ON the named pad vertices, authored
    ``y`` below the pad's zero — the T4S body."""
    _to_xy, to_ll = airport.frame.transformers()
    feet = []
    for v in vertices:
        key = pm.vertices[v].key
        feet.append(_Foot(key[0], key[1], y))
    # one extra zero foot so ``y_zero`` is 0 and the offsets read ``y``
    return _Groups([_Group(tuple(feet))])


def _offsets(pm, law, airport, vertices, y=-2.20):
    import dataclasses as _dc
    from auto_patch_v2.constraints.pad_relief import pad_relief_offsets
    ap = _dc.replace(airport, groups=_with_feet(airport, pm, vertices, y))
    return pad_relief_offsets(pm, law, ap)


def test_a_pad_vertex_shared_with_airside_pavement_takes_no_relief(law):
    """§30 (2).  Every vertex of this pad's rim is the APRON's too
    (identity is the weld, 09-01g) — the pavement law owns them, and at
    LEMD the −2.20 m authored onto them is what no surface could hold."""
    pm, airport = _pm(law, _cells("apron"))
    vs = _pad_vertices(pm)
    assert _offsets(pm, law, airport, vs) == {}


PAD_B = ((-60.0, 400.0), (60.0, 400.0), (60.0, 460.0), (-60.0, 460.0))


def test_a_pad_only_vertex_still_takes_its_foot(law):
    """The relief target itself is untouched where the pad's vertices are
    the pad's OWN: only the SHARED rim is the pavement's, so a detached
    pad under the same body keeps every offset."""
    cells = _cells("apron") + [Cell(3, "building", "padB", PAD_B, (), None, None,
                                    "airside", "pad", {})]
    pm, airport = _pm(law, cells)
    f = next(f for f in pm.faces.values() if f.ref == "padB")
    own = sorted(set(pm.ring_vertices(f.ring)))
    assert own
    off = _offsets(pm, law, airport, own)
    assert off and min(off.values()) == pytest.approx(-2.20, abs=1e-6)
    assert set(off) <= set(own)          # nothing on the fronting pad


def test_a_groundside_face_is_not_senior_here(law):
    """09-01g leaves a rim vertex a LOT shares to the lot, and §28 is where
    a groundside frontage is stated: §30 (2) narrows to the AIRSIDE side by
    ``role_side`` and mints nothing against a car park."""
    pm, airport = _pm(law, _cells("parking_lot"))
    vs = _pad_vertices(pm)
    off = _offsets(pm, law, airport, vs)
    assert off, "a groundside neighbour does not withdraw the relief target"
    assert min(off.values()) == pytest.approx(-2.20, abs=1e-6)


# ── (3a) THE REPLAY'S CAPTURE IS THE BUILD'S WHOLE PRE-SOLVE HALF ───────

_TOOL = Path(__file__).resolve().parents[2] / "tools" / "v2_solve_replay.py"


def _replay_module():
    spec = importlib.util.spec_from_file_location("_v2_solve_replay", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_capture_without_groups_is_refused_by_name():
    """The trap §30 (3a) names: a capture with no pack partition solves a
    DIFFERENT problem (no foot rows, no relief), silently."""
    mod = _replay_module()

    class _A:
        partition = None
        groups = None

    class _G:
        groups = ()

    class _B:
        partition = object()
        groups = _G()

    class _C:
        partition = object()
        groups = type("g", (), {"groups": (1,)})()

    assert mod.capture_has_groups({"airport": _A()}) is False
    assert mod.capture_has_groups({"airport": _C()}) is True
    assert mod.capture_has_groups({}) is False
    # AN EMPTY GROUP SET IS A MEASUREMENT, NOT A MISSING STAGE (lane
    # ``v2roadcap2``): KCLT's pack partitions 7,163 bodies into 0 groups,
    # and reading ``bool(groups.groups)`` refused every complete capture
    # of it.  ``partition is None`` is what actually catches a pre-12u
    # capture, and ``_A`` above is that case.
    assert mod.capture_has_groups({"airport": _B()}) is True


def test_the_capture_runs_every_pre_solve_stage_the_build_runs():
    """The capture claims to be ``pipeline/build.py``'s pre-solve half; the
    twin reads BOTH sources and asserts the stage names the build calls
    before its solve are all called by the capture.  A stage added to the
    build and forgotten here is the §30 (3a) defect again."""
    import ast
    import inspect

    from auto_patch_v2.pipeline.build import build as build_fn

    def _calls(src: str) -> set[str]:
        tree = ast.parse(src)
        out: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    out.add(f.id)
                elif isinstance(f, ast.Attribute):
                    out.add(f.attr)
        return out

    mod = _replay_module()
    cap_calls = _calls(inspect.getsource(mod.capture))
    build_calls = _calls(inspect.getsource(build_fn))
    stages = {"load_with_report", "partition_pack", "derive", "read_objects",
              "classify", "build", "detect", "preferred_road_z", "shape_stage"}
    missing = (stages & build_calls) - cap_calls
    assert not missing, f"the capture skips {sorted(missing)}"


# ── (3b)/(3c) THE SOLVE'S OWN INSTRUMENTS ───────────────────────────────

def test_hard_active_is_the_violated_rows_of_the_shipped_surface(law):
    """§30 (3b): until 12u this was phase C's MULTIPLIER count, read before
    the final projection — LEMD reported 1,457 where the shipped surface
    violated 725.  The invariant that count must satisfy: a SETTLED hard
    set violates nothing."""
    pm, airport = _pm(law, _cells())
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    assert 0 <= rep.hard_active <= rep.hard_rows
    assert rep.hard_settled == (rep.hard_active == 0)
    assert rep.hard_settled == (rep.hard_max_violation_m
                                <= float(design_law(law).hard_tol_m))
    assert "hard rows violated" in rep.line()


def test_converged_is_asserted_only_where_the_set_settled(law):
    """§30 (3c): the objective stalling and the line search buying nothing
    are EXITS, not settlement.  Where the report claims convergence the
    flip it exited on must be inside one tolerance band of the bound; where
    it does not, the flip is REPORTED rather than silent."""
    pm, airport = _pm(law, _cells())
    cs, _c, _w = generate(pm, law, airport)
    _sol, rep = solve_design(pm, cs, law)
    tol = float(design_law(law).active_set_tol_m)
    if rep.converged:
        assert rep.set_flips == 0 or rep.set_flip_max_m <= 2.0 * tol + 1e-12
    else:
        assert "SET NOT SETTLED" in rep.line()
        assert f"{rep.set_flips} rows flipped" in rep.line()
    assert rep.as_dict()["set_flips"] == rep.set_flips
