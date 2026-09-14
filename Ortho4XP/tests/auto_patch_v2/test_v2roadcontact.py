"""§37 (10) THE AIRSIDE CONTACT SET INCLUDES TAXIWAYS; A ROUTE PAIR IS
FOUND BY GEOMETRY (owner RULINGS 2026-09-13cs items 3/4/5; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §37 (10); lane
``v2roadcontact``).

The two defects the ruling names, both read on the owner's 1.0.329 HECA
products and both twinned here on synthetic geometry:

* (5) ``service_road:route0`` ENDS 4.4 m short of ``secondary_parallel:
  pav74`` and so had NO contact at all — §37 (6) read a contact only where
  the road SHARES a vertex with the airside face — and targeted its own
  DEM 1.46 m above the taxiway's edge.  The contact is now taken at the
  nearest edge point within ``[road_contact] contact_reach_m``, and it is
  a ROW AGAINST THE AIRSIDE EDGE'S OWN COLUMNS, not an estimate: at the
  site ``pav74``'s ring vertices carry NO published target and their DEM
  stands 1.4 m ABOVE the level the solve gives that edge, so an estimated
  contact RAISED the road (measured, arm 1).  ``follows`` keeps the row
  one-way — airside is king.
* (4) a 3 m ribbon carried two route frames (route 5936, a 40 m stub, and
  route 5934), so §37 (7) returned ``NOT_A_PAIR``, the section was never
  priced and the road stepped 1.30 m over 3.05 m (42.6 %) against a 1.5 %
  cap.  Two routes running together are MERGED; and, whether or not they
  merge, ``NOT_A_PAIR`` is never the verdict for two vertices ONE RIBBON
  apart in plan.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport.road_ramp import (contact_roles, merge_routes,
                                             with_road_ramp)
from auto_patch_v2.constraints import GENERATORS
from auto_patch_v2.constraints.road_ramp import (CONTACT_RULING,
                                                 road_contact_rows)
from auto_patch_v2.constraints.roads import (NOT_A_PAIR, one_ribbon_m,
                                             road_pair_reading)
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Linear
from auto_patch_v2.solve.design_roles import hard_rulings, one_way_rulings
from tests.auto_patch_v2.test_v2roadramp import (PLATEAU_Z, _Hill, _airport,
                                                 _cells, _map)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _near(law, gap: float):
    """The fixture road moved ``gap`` metres clear of the apron's edge: it
    TOUCHES at 0 and merely REACHES beyond it."""
    airport, r = _airport(law, _Hill())
    cells = _cells(r, contact=(gap <= 0.0))
    if gap > 0.0:
        import dataclasses as _dc
        from tests.auto_patch_v2.test_crown import _rect
        from auto_patch_v2.classify.roles import Cell
        road = cells[2]
        x0 = -20.0 + gap
        cells = cells[:2] + (Cell(2, "service_road", "roadA",
                                  _rect(r, x0, 196.0, x0 + 300.0, 204.0),
                                  (), None, "D", "groundside",
                                  "service_road", {}),)
    pm, rep = _map(law, airport, cells)
    return airport, pm, rep


# ── (1) THE CONTACT SET ─────────────────────────────────────────────────

def test_the_contact_set_is_every_airside_face_that_carries_a_level(law):
    """§37 (6) named "apron, pad or lot" and a TAXIWAY was not in it.  The
    set is read off ``precedence.toml`` — airside AND value — so the taxi
    family, the runway family and §40's shoulder join by being declared,
    never by being typed here; the LOT comes from ``[road_contact]
    extra_roles``.  A role that carries no level of its own (the graded
    strip, the boundary, a clearance) is NOT a contact."""
    cs = contact_roles(law)
    for r in ("apron", "building", "parking_lot", "junction", "stub",
              "primary_parallel", "secondary_parallel", "cross_connector",
              "runway"):
        assert r in cs, r
    for r in ("graded_strip", "boundary", "runway_clearance",
              "taxiway_clearance", "service_road", "service_junction"):
        assert r not in cs, r


# ── (2) THE CONTACT A ROAD DOES NOT TOUCH ───────────────────────────────

def test_a_road_ending_within_reach_takes_the_airside_edge_as_its_contact(law):
    """4 m short of the apron: the road's END carries a contact edge, and
    the vertex AT the mouth carries route distance ~0 — the airside's own
    level, not its own terrain."""
    airport, pm, rep = _near(law, 4.0)
    assert rep["reach_contacts"] >= 1, rep
    ce = pm.road_contact_edge
    assert ce, rep
    apron = {v for f in pm.faces.values() if f.role == "apron"
             for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)}
    at_mouth = [v for v, (_a, _b, _u, s) in ce.items() if s <= 1.0]
    assert at_mouth, ce
    for v in at_mouth:
        a, b, u, _s = ce[v]
        assert a in apron and b in apron, (v, a, b)
        assert 0.0 <= u <= 1.0
    # AND ITS TARGET IS WITHDRAWN: at the mouth the level is the
    # airside's, and only the airside's — two authorities at one weight
    # left HECA's ``route0`` 0.70 m short of its contact (arm 3).
    assert all(v not in pm.road_ramp_z for v in at_mouth)
    assert rep["contact_mouth_withdrawn"] == len(at_mouth)


def test_beyond_the_reach_a_road_has_no_contact(law):
    """40 m clear of the apron — well beyond ``contact_reach_m`` (15 m):
    the road keeps the §37 (6) reading it had, targeting its own floor."""
    airport, pm, rep = _near(law, 40.0)
    assert rep["reach_contacts"] == 0, rep
    assert not pm.road_contact_edge
    assert rep["no_contact"] > 0, rep


def test_the_reach_is_the_law_key(law):
    """The 15 m is ``[road_contact] contact_reach_m`` — one number, read
    from the tables, and a road just outside it takes nothing."""
    assert law.tables.emit.road_contact.contact_reach_m == 15.0
    assert _near(law, 12.0)[2]["reach_contacts"] >= 1
    assert _near(law, 18.0)[2]["reach_contacts"] == 0


# ── (3) THE ROW: ONE-WAY, A CEILING, AT THE ROAD'S OWN CAP ──────────────

def test_the_contact_row_is_a_one_way_ceiling_against_the_airside_columns(law):
    """``z[v] - (1-u)·z[a] - u·z[b] <= cap·s``: three terms, no lower
    bound, and ``follows`` names ONLY the road vertex, so the two airside
    columns enter the lag as leaders and never feel the road."""
    airport, pm, rep = _near(law, 4.0)
    rows = road_contact_rows(pm, law, airport)
    assert rows and len(rows) == len(pm.road_contact_edge)
    heads = one_way_rulings(law)
    for row in rows:
        assert isinstance(row, Linear)
        assert row.lo is None and row.hi >= 0.0
        assert len(row.terms) == 3
        v, cv = row.terms[0]
        assert cv == pytest.approx(1.0)
        assert sum(c for _t, c in row.terms) == pytest.approx(0.0, abs=1e-9)
        assert row.follows == (v,)
        a, b, u, s = pm.road_contact_edge[v]
        assert row.hi == pytest.approx(0.08 * s)
    assert CONTACT_RULING.split("(")[0].strip() in heads
    # NOT HARD: ``solve/design`` carries ONE ``shift`` vector and the
    # augmented Lagrangian overwrites the one-way lag of a row in both
    # registers — registered hard, this row drove HECA's roads 108 m
    # below their DEM (arm 2).
    assert CONTACT_RULING.split("(")[0].strip() not in hard_rulings(law)


def test_the_generator_is_registered_and_mints_nothing_without_the_channel(law):
    """One derivation site: a map the publisher never ran over carries no
    channel and the generator mints nothing."""
    assert "road_contact" in dict(GENERATORS)
    airport, pm, rep = _near(law, 40.0)
    assert road_contact_rows(pm, law, airport) == []


# ── (3b) AIRSIDE IS KING: NO ROW OF THIS LANE IS TWO-SIDED ON A MOUTH ──

def test_no_airside_vertex_carries_a_ramp_target_or_loses_one(law):
    """(b) of the round-2 remedy: the §37 (6) target governs ROAD-OWNED
    vertices only, so withdrawing it over the end group cannot RELEASE an
    airside vertex the target was incidentally holding — there is no such
    vertex.  MEASURED at HECA: 544 targets, 0 airside; 66 withdrawn, 0
    airside."""
    from auto_patch_v2.airport.road_ramp import road_ramp_targets
    from auto_patch_v2.law.tables import role_side
    airport, pm, rep = _near(law, 4.0)
    air = lambda v: any(role_side(law, r) == "airside"
                        for r in pm.roles_at(v))
    tg = road_ramp_targets(pm, law, airport).targets
    assert tg and not [v for v in tg if air(v)]
    withdrawn = set(tg) - set(pm.road_ramp_z)
    assert withdrawn and not [v for v in withdrawn if air(v)]


def test_a_ribbon_pair_that_binds_a_mouth_is_one_way_on_the_road(law):
    """(a) of the round-2 remedy.  A road RING's vertices include the
    MOUTH it shares with the apron; a pair this lane newly prices across
    that ribbon — or on a route the MERGE fused — is minted under
    ``RIBBON_RULING`` with ``follows`` naming the ROAD vertex, so the
    airside column is a leader and never feels the road.  A cross-ribbon
    pair whose BOTH vertices are airside is not minted at all: before
    §37 (10) it read ``NOT_A_PAIR`` and the road family never priced it.
    """
    from auto_patch_v2.constraints.roads import (RIBBON_RULING, STATS,
                                                 road_within_shape)
    from auto_patch_v2.law.tables import role_side
    from auto_patch_v2.model.constraints import Diff
    airport, pm, rep = _near(law, 4.0)
    rows = road_within_shape(pm, law, airport)
    air = lambda v: any(role_side(law, r) == "airside"
                        for r in pm.roles_at(v))
    assert RIBBON_RULING.split("(")[0].strip() in one_way_rulings(law)
    assert RIBBON_RULING.split("(")[0].strip() not in hard_rulings(law)
    for row in rows:
        if not isinstance(row, Diff) or row.source.ruling != RIBBON_RULING:
            continue
        assert row.follows is not None and len(row.follows) == 1
        assert not air(row.follows[0])          # the ROAD vertex follows
        assert air(row.a) or air(row.b)         # and a mouth is the leader
    assert "ribbon_follower" in STATS["road_within_shape"]


# ── (4) TWO ROUTES ON ONE RIBBON ────────────────────────────────────────

class _Way:
    """The two fields ``merge_routes`` reads off a clamped centreline."""

    def __init__(self, pts, ref, kind="osm"):
        import numpy as np
        from shapely.geometry import LineString
        self.xy = np.asarray(pts, dtype=float)
        d = np.diff(self.xy, axis=0)
        self.s = np.concatenate(([0.0], np.cumsum(np.hypot(d[:, 0], d[:, 1]))))
        self.ref, self.kind = ref, kind
        self._line = LineString(pts)

    @property
    def line(self):
        return self._line


def _frames(ways, per):
    """``raw`` / ``xy`` as ``road_route_frame`` builds them: ``per`` points
    laid along each way at its own stations."""
    raw, xy = {}, {}
    v = 0
    for i, w in enumerate(ways):
        for s in per[i]:
            p = w.line.interpolate(s)
            raw[v] = (i, float(s), 0.0)
            xy[v] = (p.x + (0.0 if i == 0 else 3.0), p.y)
            v += 1
    return raw, xy


def test_two_routes_running_together_are_one_carriageway(law):
    """A 40 m stub laid 3 m beside a long route, sharing 30 m of arc: ONE
    route after the merge, and the SHORTER merges into the LONGER."""
    long_w = _Way([(0.0, 0.0), (200.0, 0.0)], "osm:-13192")
    stub = _Way([(100.0, 3.0), (140.0, 3.0)], "osm:-13190")
    raw, xy = _frames([long_w, stub], [[100.0, 110.0, 120.0, 130.0],
                                       [0.0, 10.0, 20.0, 30.0]])
    # the stub's own vertices sit at x + 3 in ``_frames``; put them beside
    # the long way instead
    for v in (4, 5, 6, 7):
        xy[v] = (xy[v][0] - 3.0, 3.0)
    into, named = merge_routes([long_w, stub], raw, xy, 6.0, 10.0, 4.0)
    assert into == {1: 0}, (into, named)
    assert named[0]["into_ref"] == "osm:-13192"
    assert named[0]["ref"] == "osm:-13190"


def test_a_crossing_is_not_a_carriageway(law):
    """Two routes that MEET (one point in common, no arc together) are two
    routes: the overlap is under ``pair_overlap_m``."""
    a = _Way([(0.0, 0.0), (200.0, 0.0)], "A")
    b = _Way([(100.0, -50.0), (100.0, 50.0)], "B")
    raw, xy = _frames([a, b], [[98.0, 100.0, 102.0], [48.0, 50.0, 52.0]])
    for v in (3, 4, 5):
        xy[v] = (100.0, xy[v][1] - 50.0)
    into, named = merge_routes([a, b], raw, xy, 6.0, 10.0, 4.0)
    assert into == {} and named == []


def test_a_route_that_leaves_the_corridor_never_merges(law):
    """The containment guard: without it one 6 m proximity chains route to
    route across a network and the survivor's stations mean nothing.  A way
    that runs together for 30 m and then departs 200 m is not merged."""
    a = _Way([(0.0, 0.0), (400.0, 0.0)], "A")
    b = _Way([(0.0, 3.0), (30.0, 3.0), (30.0, 203.0)], "B")
    raw, xy = _frames([a, b], [[0.0, 10.0, 20.0, 30.0],
                               [0.0, 10.0, 20.0, 30.0]])
    for v in (4, 5, 6, 7):
        xy[v] = (xy[v][0] - 3.0, 3.0)
    into, named = merge_routes([a, b], raw, xy, 6.0, 10.0, 4.0)
    assert into == {} and named == []


# ── (5) NOT_A_PAIR IS NEVER THE VERDICT ON ONE RIBBON ───────────────────

def test_two_vertices_one_ribbon_apart_are_a_cross_section_pair(law):
    """HECA item 4: the two vertices stand 3.05 m apart in PLAN on route
    frames 5936 and 5934.  Priced ACROSS the ribbon at the transverse cap,
    never ``NOT_A_PAIR`` — the step was 1.30 m over 3.05 m (42.6 %)."""
    deg = law.tables.common.road_transverse_axis_min_deg
    ribbon = one_ribbon_m(law)
    assert ribbon == 6.0
    read = road_pair_reading(0.08, 0.015, deg, (5936, 542.13, 4.10),
                             (5934, 1840.30, -2.12), 3.05, ribbon)
    assert read != NOT_A_PAIR
    bound, transverse = read
    assert transverse is True
    assert bound == pytest.approx(0.015 * 3.05)


def test_a_switchback_is_still_not_a_pair(law):
    """KCLT ``dsf:pol51``: two branches of ONE page 45.6 m apart in plan
    and 279.9 m apart along the road.  The ruling that freed them stands —
    the ribbon test is a plan distance, not a route one."""
    deg = law.tables.common.road_transverse_axis_min_deg
    assert road_pair_reading(0.08, 0.015, deg, (827, 0.0, 0.0),
                             (828, 279.9, 0.0), 45.6,
                             one_ribbon_m(law)) == NOT_A_PAIR


def test_the_census_prices_the_ribbon_exactly_as_the_generator_does(law):
    """THE TWIN (the census-wrapper precedent): ``check_grade`` reads the
    ONE-RIBBON width through the engine's own accessor, so all three
    readers — generator, verify, census — return the same verdict."""
    import importlib.util
    import sys
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "tools" / "check_grade.py"
    spec = importlib.util.spec_from_file_location("_cg_ribbon", p)
    cg = importlib.util.module_from_spec(spec)
    sys.modules["_cg_ribbon"] = cg
    spec.loader.exec_module(cg)
    deg = law.tables.common.road_transverse_axis_min_deg
    for fa, fb, chord in (((1, 0.0, 2.0), (2, 100.0, -1.0), 3.05),
                          ((1, 0.0, 0.0), (2, 10.0, 0.0), 45.6),
                          ((1, 0.0, 0.0), (1, 30.0, 4.0), 30.3)):
        assert cg._road_pair_reading_v2(0.08, 0.015, fa, fb, chord) == \
            road_pair_reading(0.08, 0.015, deg, fa, fb, chord,
                              one_ribbon_m(law))
