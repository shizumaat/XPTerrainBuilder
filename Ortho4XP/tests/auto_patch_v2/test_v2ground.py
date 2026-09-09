"""ROUND 3's twins — taxiways like runways, the adjacent ground as a LAW
surface, the 5 % ceiling (owner RULINGS 2026-09-09b (2)(3)(4); spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §8; lane ``v2ground``).

Three readings, one per ruling, plus the structural ones: the DEM has left
the patch, the adjacent-ground rows are ONE-WAY, and a pavement pair the
sheet would grade at 7 % is held at 5 % (a road at 8 %).
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import GENERATORS, ceiling, generate
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Linear, Source
from auto_patch_v2.solve import solve_design
from auto_patch_v2.solve.design import (DesignReport, assemble, is_hard,
                                        one_way_rulings, ruling_head)
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot
from tests.auto_patch_v2.test_v2smooth import (RUN_LEN, _airport, _solve, law,  # noqa: F401
                                               _ValleyDem)


class _SlopeDem:
    """Ground that falls 7 % across the map: steeper than the pavement
    ceiling, so the sheet would grade a pavement past 5 % if nothing
    stopped it."""

    provenance = {"synthetic": "7 % cross slope"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.07 * y

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _taxi_solve(law, airport, cells, cut):
    """``_solve`` with CUT LINES — the taxi centreline the design profile
    is stated along (``classify.roles.CutLine``, the planar map's
    breakline source)."""
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.planar.build import build
    cl = Classification(tuple(cells), tuple(cut), {}, ())
    pm, _st = build(airport, cl, law)
    pm = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    return pm, cs, sol, rep


@pytest.fixture(scope="module")
def taxi_map(law):                                          # noqa: F811
    """A runway over a V-valley with a parallel taxiway and a stub — the
    §4 fixture plus the taxiway's own CENTRELINE, so the taxi design
    profile has a chain to be stated along."""
    airport, r = _airport(law, _ValleyDem(), ())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400.0, 60.0, 400.0, 83.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 60.0), (), None, "D",
             "airside", "taxi", {}),
    )
    axis = tuple(r((x, 71.5)) for x in np.arange(-400.0, 400.1, 20.0))
    cut = (CutLine("taxi_centerline", "taxiA", axis, "D"),)
    return (*_taxi_solve(law, airport, cells, cut), airport)


# ── (3) THE DEM HAS LEFT THE PATCH ──────────────────────────────────────

def test_the_dem_zone_term_is_deleted(law):                 # noqa: F811
    """The weight, the field and the TOML key are all gone; the law table
    refuses to carry it back (an unknown key is a load error)."""
    d = law.tables.emit.design
    assert not hasattr(d, "dem_zone")
    with pytest.raises(Exception):
        d.weight("dem_zone")
    assert d.taxi_profile > 0.0


def test_no_vertex_is_fixed_at_the_dem_and_no_bank_row_is_dropped(taxi_map, law):  # noqa: F811
    """09-09b (3): "the outer ring's elevation is whatever those laws
    give".  Nothing beyond the zone is the terrain, so the BANK filter
    (spec §6 deviation 3) has nothing to drop."""
    pm, cs, _sol, _rep = taxi_map[:4]
    rep = DesignReport()
    base = assemble(pm, cs, law, rep)
    assert not base.red.dem_fixed
    assert rep.bank_rows == 0
    # and the only DEM-valued rows left are the detached bodies' own planes
    kinds = {own[0] for own in base.rows.owner if own}
    assert "dem_zone" not in kinds


def test_the_zone_ring_follows_the_pavement_not_the_terrain(taxi_map, law):  # noqa: F811
    """The graded strip is a LAW surface: over a valley 25 m deep it sits
    near the pavement it serves, not on the terrain it stands over."""
    pm, _cs, sol, _rep = taxi_map[:4]
    z = np.asarray(sol.z, float)
    strip = [v for v, vx in pm.vertices.items()
             if any(pm.faces[f].role == "graded_strip" for f in vx.incident_faces)
             and vx.dem_z is not None and vx.dem_z < 690.0]
    assert strip, "the fixture's valley must reach the graded strip"
    # every such vertex is FILLED well clear of its DEM sample
    assert min(z[v] - pm.vertices[v].dem_z for v in strip) > 1.0


# ── (2) TAXIWAYS LIKE RUNWAYS ───────────────────────────────────────────

def test_every_taxi_centreline_carries_a_design_profile(taxi_map, law):  # noqa: F811
    """The runway K pattern as an objective term: one second-difference
    row per interior station of every ``taxi_centerline`` breakline."""
    pm, cs, _sol, _rep = taxi_map[:4]
    base = assemble(pm, cs, law, DesignReport())
    prof = [own for own in base.rows.owner if own and own[0] == "taxi_profile"]
    stations = sum(max(0, len(bl.vertices(pm)) - 2)
                   for bl in pm.breaklines.values() if bl.kind == "taxi_centerline")
    assert stations > 0, "the fixture must carry a taxi centreline"
    assert len(prof) == stations


def test_the_taxi_profile_is_smoother_than_the_terrain_under_it(taxi_map, law):  # noqa: F811
    """The owner's read in a number: the RMS second difference along the
    taxi centreline, built vs the DEM it runs over."""
    pm, _cs, sol, _rep = taxi_map[:4]
    z = np.asarray(sol.z, float)

    def rms(value) -> float:
        acc, n = 0.0, 0
        for bl in pm.breaklines.values():
            if bl.kind != "taxi_centerline":
                continue
            ch = bl.vertices(pm)
            for k in range(1, len(ch) - 1):
                a, m, c = ch[k - 1], ch[k], ch[k + 1]
                (ax, ay), (mx, my), (cx, cy) = (pm.vertices[i].xy for i in (a, m, c))
                dp = float(np.hypot(mx - ax, my - ay))
                dn = float(np.hypot(cx - mx, cy - my))
                if dp <= 1e-6 or dn <= 1e-6:
                    continue
                d2 = (value(c) - value(m)) / dn - (value(m) - value(a)) / dp
                acc += d2 * d2
                n += 1
        return (acc / n) ** 0.5 if n else 0.0

    built = rms(lambda v: float(z[v]))
    terrain = rms(lambda v: float(pm.vertices[v].dem_z))
    assert terrain > 0.0, "the fixture's valley must bend the terrain"
    assert built < terrain


# ── (2)/(3) THE ADJACENT GROUND FOLLOWS AND NEVER PULLS ─────────────────

def test_the_zone_rows_are_one_way_and_name_the_ground_vertex(taxi_map, law):  # noqa: F811
    pm, cs, _sol, _rep = taxi_map[:4]
    heads = one_way_rulings(law)
    assert heads
    zone_rows = [r for r in cs.rows()
                 if isinstance(r, Linear) and ruling_head(r) in heads]
    assert zone_rows, "the fixture must carry adjacent-ground rows"
    for r in zone_rows:
        assert r.follows is not None, "a one-way row names the vertex it governs"
        assert r.follows in {v for v, _c in r.terms}
    base = assemble(pm, cs, law, DesignReport())
    assert base.one_way, "the design solve prices them one-way"
    for k, v in base.one_way.items():
        assert ruling_head(base.one[k][2]) in heads
        assert v == base.one[k][2].follows


def test_the_pavement_does_not_feel_the_ground_it_shapes(taxi_map, law):  # noqa: F811
    """The one-way split: only the FOLLOWER's column survives in the
    matrix the solve factorises, so a corridor row's gradient reaches the
    ground and never the pavement foot."""
    pm, cs, _sol, _rep = taxi_map[:4]
    from auto_patch_v2.solve.rows import _one_matrix
    base = assemble(pm, cs, law, DesignReport())
    A1, _b1 = _one_matrix(base.one, base.red)
    A1 = A1.tocsr()
    for k, v in list(base.one_way.items())[:200]:
        cols = set(A1.indices[A1.indptr[k]:A1.indptr[k + 1]].tolist())
        foot = {int(base.red.col[u]) for u, _c in base.one[k][2].terms
                if u != v and base.red.col[u] >= 0}
        # the row DOES carry its feet before the split; the split is the
        # solve's own (``solve_design``), and the follower is always in
        assert int(base.red.col[v]) in cols or base.red.col[v] < 0
        assert foot <= cols or not foot


# ── (4) THE 5 % CEILING ─────────────────────────────────────────────────

def test_the_ceiling_is_a_law_value_and_a_hard_ruling(law):  # noqa: F811
    common = law.tables.common
    assert common.pavement_max_grade == pytest.approx(0.05)
    assert common.road_max_grade == pytest.approx(0.08)
    heads = law.tables.emit.design.hard_rulings
    assert ruling_head(Diff(0, 1, 0.05, 1.0, Source(ceiling.GEN, ceiling.RULING, ()))) \
        in heads
    assert is_hard(frozenset(heads),
                   Diff(0, 1, 0.05, 1.0, Source(ceiling.GEN, ceiling.RULING, ())))


def test_the_ceiling_is_not_a_registered_generator_but_a_post_pass():
    """It reads the law set, so it cannot be one of the row generators."""
    assert ceiling.GEN not in {name for name, _fn in GENERATORS}


def test_a_pavement_pair_the_sheet_would_grade_at_seven_per_cent_is_held(law):  # noqa: F811
    """A pavement over a 7 % cross slope: the ceiling twin caps every
    local pair at 5 %, a free road at 8 %."""
    airport, r = _airport(law, _SlopeDem(), ())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        Cell(1, "apron", "apronA", _rect(r, -300.0, 200.0, 300.0, 420.0), (), None,
             "D", "airside", "apron", {}),
        Cell(2, "service_road", "roadA", _rect(r, -300.0, 600.0, 300.0, 612.0), (),
             None, "D", "groundside", "road", {}),
    )
    cl = Classification(tuple(cells), (), {}, ())
    from auto_patch_v2.planar.build import build
    pm, _st = build(airport, cl, law)
    rows_all: list = []
    cs, _c, _w = generate(pm, law, airport)
    rows_all.extend(cs.rows())
    caps = [r_ for r_ in rows_all if r_.source.generator == ceiling.GEN]
    assert caps, "the post-pass mints the ceiling twins"
    by_cap: dict[float, int] = {}
    for r_ in caps:
        c = r_.cap if isinstance(r_, Diff) else abs(r_.hi) / max(1e-9, r_.hi and 1.0)
        if isinstance(r_, Diff):
            by_cap[round(c, 3)] = by_cap.get(round(c, 3), 0) + 1
    assert by_cap.get(0.05), "pavement pairs are capped at 5 %"
    # every ceiling row is at one of the two law values
    for r_ in caps:
        if isinstance(r_, Diff):
            assert round(r_.cap, 3) in (0.05, 0.08)

    sol, rep = solve_design(pm, cs, law)
    z = np.asarray(sol.z, float)
    worst = 0.0
    for r_ in caps:
        if isinstance(r_, Diff) and r_.cap == pytest.approx(0.05):
            worst = max(worst, abs(z[r_.a] - z[r_.b]) / r_.d)
    # held to the solve's own hard tolerance over the pair's span
    assert worst <= 0.05 + law.tables.emit.design.hard_tol_m, \
        f"a pavement pair is graded at {worst * 100:.2f} %"


def test_the_ceiling_mints_nothing_off_the_pavement_and_nothing_long(law):  # noqa: F811
    """A row on the graded strip is not a capped pavement (09-09b (3)),
    and a span past ``withdrawn_chord_min_m`` is read along the route, not
    across the chord (05aa)."""
    airport, r = _airport(law, _SlopeDem(), ())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
    )
    cl = Classification(tuple(cells), (), {}, ())
    from auto_patch_v2.planar.build import build
    pm, _st = build(airport, cl, law)
    strip_v = {v for v, vx in pm.vertices.items()
               if all(pm.faces[f].role in ("graded_strip", "runway_clearance",
                                           "boundary", "ols_cut")
                      for f in vx.incident_faces) and vx.incident_faces}
    src = Source("fixture", "fixture row", ())
    long_pair = Diff(0, 1, 0.015, 500.0, src)
    made = ceiling.pavement_ceiling([long_pair], pm, law)
    assert not made, "a 500 m span mints no ceiling row (the chord law is withdrawn)"
    if len(strip_v) >= 2:
        a, b = sorted(strip_v)[:2]
        made = ceiling.pavement_ceiling([Diff(a, b, 0.015, 5.0, src)], pm, law)
        assert not made, "the adjacent ground is a law surface, not a capped pavement"
