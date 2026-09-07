"""The v2ridge3 twins (RULINGS 2026-09-06s; lane v2ridge3): THE SHORT-PAIR
BOX is generator law — every taxi-family pair of one ring under
``withdrawn_chord_min_m`` carries a hard ``|Δz| ≤ cL·|Δs| + cT·|Δt|``
row against the nearest stretch axis, taxi tier; the v2 verify and the
v1 oracle read the same population (family ``taxi_box``) and bound.

On the ``ridge`` fixture (``test_v2ridge``): (1) two stub rim neighbours
4 m apart with a 2 m step — the row refuses it, both readers see it
without the row; (2) a 1.5 %/1.5 % plane over the taxiways admits every
short pair (no row binds, both readers 0); (3) pairs of 30 m or more
carry no box row; (4) the row is taxi tier, never relaxable.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.constraints import GENERATORS, generate, roads
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.stretches import stretches
from auto_patch_v2.constraints.taxi import BOX_RULING, GEN, axis_index, short_pairs
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.solve import Options, Status, solve
from auto_patch_v2.solve.relax import _law_tier, stated_role
from auto_patch_v2.verify import census
from auto_patch_v2.verify.within import FAMILY_TAXI_BOX
from tests.auto_patch_v2.test_v2ridge import _verts_of_role, build_ridge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_grade as cg  # noqa: E402

STEP_M = 2.0              # the step between two rim neighbours
NEIGHBOUR_M = 4.0         # ...4 m apart (HECA stub pav78's class, 06s)
PLANE = 0.015             # the lawful plane: 1.5 % along AND 1.5 % across


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def ridge(law):
    return build_ridge(law)


def _box_rows(cs: ConstraintSet) -> list[Diff]:
    return [r for r in cs.rows() if isinstance(r, Diff) and r.source.generator == GEN
            and r.source.ruling == BOX_RULING]


def _solve(ridge, law, only=None, extra=()):
    airport, pm, _ = ridge
    cs, _c, _w = generate(pm, law, airport, only=only)
    if extra:
        cs = ConstraintSet.from_rows([*cs.rows(), *extra])
    sol = solve(pm, cs, DEFAULT_WEIGHTS, Options(diagnose_iis=False))
    return cs, sol


def _readers(ridge, law, sol, out_dir):
    """``(v2 taxi_box rows, oracle taxi_box rows, oracle box stats)`` on
    the emitted patch of ``sol``."""
    airport, pm, _ = ridge
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    v2 = census(surf, law, pub, roads.road_law_caps(pm, law))[FAMILY_TAXI_BOX]
    paths = write_patch(surf, law, out_dir, pub)
    fam: dict = {}
    cg.run_checks_law_true(Path(paths.patch), family_out=fam)
    return v2, list(fam.get(cg.TAXI_BOX_FAMILY) or []), dict(cg._TAXI_BOX_STATS)


def _neighbours(pm, role="stub"):
    """Two ring neighbours of a ``role`` face (no runway vertex)
    ``NEIGHBOUR_M`` apart."""
    rw = _verts_of_role(pm, "runway")
    for f in pm.faces.values():
        if f.role != role:
            continue
        ring = pm.ring_vertices(f.ring)
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            if a in rw or b in rw:
                continue
            if abs(math.dist(pm.vertices[a].xy, pm.vertices[b].xy) - NEIGHBOUR_M) < 0.01:
                return f, a, b
    raise AssertionError("the fixture has no 4 m stub rim neighbours")


ALL_BUT_BOX = frozenset(n for n, _f in GENERATORS if n != "taxi_box")


# ── (3) the population: short pairs only, every ring, none at 30 m ───────

def test_every_short_pair_of_every_taxi_ring_has_one_box_row_and_no_long_pair_does(ridge, law):
    airport, pm, _ = ridge
    cs, counts, _w = generate(pm, law, airport, only={"taxi_box"})
    rows = _box_rows(cs)
    assert rows and counts["taxi_box"] == len(rows) == counts["taxi_box.pairs"]
    min_m = law.tables.emit.within_shape.withdrawn_chord_min_m
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    assert all(min_d <= r.d < min_m for r in rows)
    # the population, independently: every ring of every taxi-family face
    vw = view(pm, law)
    taxi = set(law.tables.precedence.taxi_family.members)
    expect = set()
    for f in pm.faces.values():
        if f.role in taxi:
            for ring in [vw.rings[f.id], *vw.holes[f.id]]:
                for a, b, _d in short_pairs(vw.xy, ring, min_d, min_m):
                    expect.add((min(a, b), max(a, b)))
    assert {(min(r.a, r.b), max(r.a, r.b)) for r in rows} == expect
    # the bound is the box: a pair along its axis at cL·d, across at cT·d
    index = axis_index(vw, stretches(pm, law))
    for r in rows:
        (xa, ya), (xb, yb) = vw.xy[r.a], vw.xy[r.b]
        bound, cl, ct = index.box_bound(xa, ya, xb, yb)
        assert r.bound_m == pytest.approx(bound)
        assert min(cl, ct) * r.d - 1e-9 <= r.bound_m <= (cl + ct) * r.d + 1e-9


# ── (4) taxi tier, never relaxable ────────────────────────────────────────

def test_the_box_row_is_taxi_tier_and_states_no_relaxable_role(ridge, law):
    airport, pm, _ = ridge
    cs, _c, _w = generate(pm, law, airport, only={"taxi_box"})
    tt = T.tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    stub_tier = tier_of["stub"]
    for r in _box_rows(cs):
        assert stated_role(r, tier_of) is None
        assert _law_tier(pm, r, tier_of, len(tt) - 1) <= stub_tier
        assert r.soft is None


# ── (2) the lawful plane admits every short pair ──────────────────────────

def test_a_plane_at_the_caps_admits_every_short_pair_and_both_readers_read_zero(ridge, law, tmp_path):
    airport, pm, _ = ridge
    cs, sol = _solve(ridge, law, only={"taxi_box"})
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    z = list(sol.z)
    for v in pm.vertices:
        x, y = pm.vertices[v].xy
        z[v] = PLANE * x + PLANE * y
    for r in _box_rows(cs):
        assert abs(z[r.a] - z[r.b]) <= r.bound_m + 1e-9, (r.a, r.b, r.d)
    v2, oracle, stats = _readers(ridge, law, _dc.replace(sol, z=tuple(z)), tmp_path / "plane")
    assert v2 == [] and oracle == []
    assert stats.get("pairs", 0) > 0 and stats.get("no_axis", 0) == 0, stats


# ── (1) the 4 m neighbours with a 2 m step ────────────────────────────────

def test_a_2m_step_between_4m_rim_neighbours_is_refused_by_the_row_and_read_without_it(ridge, law, tmp_path):
    airport, pm, _ = ridge
    f, a, b = _neighbours(pm)
    # WITHOUT the row: the solve lets the step stand (it is imposed here
    # as the built value) and BOTH readers flag exactly that pair
    _cs, sol = _solve(ridge, law, only=ALL_BUT_BOX)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    z = list(sol.z)
    z[b] = z[a] + STEP_M
    v2, oracle, _stats = _readers(ridge, law, _dc.replace(sol, z=tuple(z)), tmp_path / "step")
    key = (min(a, b), max(a, b))
    v2_hit = [r for r in v2 if r["distance_m"] == pytest.approx(NEIGHBOUR_M, abs=0.01)
              and r["magnitude_m"] == pytest.approx(STEP_M, abs=0.02)]
    or_hit = [r for r in oracle if r.distance_m == pytest.approx(NEIGHBOUR_M, abs=0.01)
              and r.de_m == pytest.approx(STEP_M, abs=0.02)]
    assert v2_hit and or_hit, (len(v2), len(oracle))
    assert all(r["family"] == FAMILY_TAXI_BOX for r in v2)
    assert all(getattr(r, "reading", None) == "taxi_box" for r in oracle)
    # WITH the row: the step is REFUSED — pinning the two neighbours 2 m
    # apart makes the hard set infeasible; the box row alone holds them
    # within cL·|Δs| + cT·|Δt| of each other
    src = Source("twin", "the imposed step", ())
    z0 = float(sol.z[a])
    cs, sol2 = _solve(ridge, law, extra=(Pin(a, z0, src), Pin(b, z0 + STEP_M, src)))
    assert sol2.status not in (Status.OPTIMAL, Status.FEASIBLE), sol2.status
    cs, sol3 = _solve(ridge, law)
    assert sol3.status in (Status.OPTIMAL, Status.FEASIBLE), sol3.message
    row = next(r for r in _box_rows(cs) if (min(r.a, r.b), max(r.a, r.b)) == key)
    assert abs(sol3.z[a] - sol3.z[b]) <= row.bound_m + 1e-6
    assert row.bound_m < STEP_M
    for r in _box_rows(cs):
        assert abs(sol3.z[r.a] - sol3.z[r.b]) <= r.bound_m + 1e-6
    v2b, oracle_b, _s = _readers(ridge, law, sol3, tmp_path / "held")
    assert v2b == [] and oracle_b == []


# ── the axis locator is a true nearest (HECA pav129, 2026-09-06) ─────────

def test_the_axis_index_and_the_oracle_box_agree_with_brute_force(law):
    """A segment whose bounding box spans a neighbour cell is binned there
    though its nearest point is far; the true nearest segment may lie
    outside the searched block.  Both locators (generator/verify
    ``AxisIndex``, oracle ``_StretchBox``) must return the brute-force
    nearest on a seeded random field of stretches."""
    import random
    from auto_patch_v2.constraints.geometry import project_to_chain
    from auto_patch_v2.constraints.stretches import AxisIndex
    rng = random.Random(6)
    cell = law.tables.emit.within_shape.withdrawn_chord_min_m
    axes = []
    for k in range(40):
        x, y = rng.uniform(0, 600), rng.uniform(0, 600)
        ang = rng.uniform(0, math.pi)
        ln = rng.uniform(20, 300)
        pts = [(x, y), (x + ln * math.cos(ang), y + ln * math.sin(ang))]
        axes.append((pts, 0.015, 0.015))
    index = AxisIndex(axes, cell)
    stretches = [[[[px, py] for px, py in pts], cl, "D", f"s{k}"] for k, (pts, cl, _ct) in enumerate(axes)]
    box = cg._StretchBox(stretches, lambda la, lo: (la, lo), law)
    for _ in range(300):
        p = (rng.uniform(-50, 650), rng.uniform(-50, 650))
        d_true, k_true = min((project_to_chain(p, pts)[0], k) for k, (pts, _a, _b) in enumerate(axes))
        (ux, uy), _cl, _ct = index.nearest(*p)
        (ax, ay), (bx, by) = axes[k_true][0]
        n = math.hypot(bx - ax, by - ay)
        assert (ux, uy) == pytest.approx(((bx - ax) / n, (by - ay) / n), abs=1e-9), (p, d_true)
        oux, ouy, _c1, _c2 = box.nearest(*p)
        assert (oux, ouy) == pytest.approx(((bx - ax) / n, (by - ay) / n), abs=1e-9), (p, d_true)
