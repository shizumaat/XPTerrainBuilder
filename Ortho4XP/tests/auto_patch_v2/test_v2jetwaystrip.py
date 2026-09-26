"""Twins for THE JETWAY STRIP (spec ``docs/specs/jetway-strip-spec.md``;
owner RULINGS 2026-09-18t Q3: "UNDER THE JETWAYS THE APRON STRIP IS LEVEL
WITH THE TERMINAL — a NEW AIRSIDE LAW, solved airside-first"; issues
#31/#32; lane ``jetwaystrip``).

The fixture is one terminal pad inside one apron whose ground FALLS 4 m
along the terminal, a taxiway along the apron's far edge, and three
placements the plan holds no geometry for: a jetway ``.agp`` 1.4 m off the
wall inside its +/-5 m TILE (rides), the same ``.agp`` 40 m out (does not)
and a ``lib/`` marshaller 30 m out (never rides).
"""
from __future__ import annotations

import dataclasses as _dc
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, DsfObject, Runway,
                                         RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design

RUN_LEN = 1600.0
HALF_W = 22.5
#: the terminal pad and the apron in front of it (south = +y side facing)
PAD = (-150.0, 260.0, 150.0, 300.0)
APRON = (-300.0, 140.0, 300.0, 300.0)
TWY = (-300.0, 60.0, 300.0, 100.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """Ground falling 2.7 m west -> east along the terminal (0.9 %: a
    plane the pad's 1 % ceiling can take, so the frontage passes the
    Q-32d (i) planarity gate)."""

    provenance = {"synthetic": "tilt"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 2.7 * max(0.0, min(1.0, (x + 150.0) / 300.0))

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Cluster:
    def __init__(self, airport, rect, cid="unit:1#0"):
        _to_xy, to_ll = airport.frame.transformers()
        self.id = cid
        self.unit = cid.split("#", 1)[0]
        self.members = ("objects/terminal.obj", "objects/roof.obj")
        la0, lo0 = to_ll(rect[0], rect[1])
        la1, lo1 = to_ll(rect[2], rect[3])
        self.boxes = ((min(la0, la1), min(lo0, lo1), max(la0, la1),
                       max(lo0, lo1)),)
        self.rings = (tuple(to_ll(x, y) for x, y in _rect(*rect)),)
        self.floors = (0.0, 0.0)
        self.bodies = 2
        self.footed = 2
        self.walled = 2
        self.area_m2 = 12000.0
        self.hull = self.boxes[0]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def agp(tmp_path_factory):
    d = tmp_path_factory.mktemp("agp")
    p = d / "Jetway.agp"
    p.write_text("A\n1000\nAG_POINT\n\nTEXTURE_SCALE 10.0 10.0\n"
                 "TEXTURE_WIDTH 10.0\nOBJECT Jetway.obj\n"
                 "TILE -5.0 -5.0 5.0 5.0\nANCHOR_PT 0.0 0.0\n")
    return str(p)


def _airport(law, agp_path, objects=True):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    objs = ()
    if objects:
        # rotundas 1.4 m off the wall (y = 260 is the pad's apron side),
        # inside their +/-5 m TILE; one 40 m out; a lib marshaller 30 m out
        objs = (DsfObject("dsf:obj0", "Airport/Jetway.agp", (-100.0, 258.6),
                          180.0, None, False, None, 0.0, agp_path),
                DsfObject("dsf:obj1", "Airport/Jetway.agp", (100.0, 258.6),
                          180.0, None, False, None, 0.0, agp_path),
                DsfObject("dsf:obj2", "Airport/Jetway.agp", (0.0, 220.0),
                          180.0, None, False, None, 0.0, agp_path),
                DsfObject("dsf:obj3", "lib/airport/marshaller.obj", (50.0, 230.0),
                          180.0, None, False, None, 0.0, None))
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), objs, pack, _Dem(), law.ruleset_key)


def _cells():
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W,
                                             RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronA", _rect(*APRON), (_rect(*PAD),),
                 None, None, "airside", "apron", {}),
            Cell(2, "building", "terminal", _rect(*PAD), (), None, None,
                 "airside", "pad", {}),
            Cell(4, "primary_parallel", "twyA", _rect(*TWY), (), 3, "D",
                 "airside", "taxiway", {})]


def _prep(law, agp_path, objects=True):
    airport = _airport(law, agp_path, objects)
    airport = _dc.replace(airport, clusters=(_Cluster(airport, PAD),))
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    cs, _counts, _w = generate(pm, law, airport)
    return airport, pm, cs


def _strips(law, airport, pm, cs):
    from auto_patch_v2.airport.riders import rider_candidates
    from auto_patch_v2.constraints.jetway_strip import jetway_strips
    return jetway_strips(pm, law, airport, cs, rider_candidates(airport, law))


def _verts(pm, ref):
    f = next(q for q in pm.faces.values() if q.ref == ref)
    out = set(pm.ring_vertices(f.ring))
    for h in (f.holes or ()):
        out |= set(pm.ring_vertices(h))
    return out


def test_the_agp_tile_is_the_rider_reach(law, agp):
    """§1 (1): reach = max(footprint_touch_m, the .agp TILE half-extent)
    capped at rider_reach_max_m — HECA's jetway reads 5.0 m."""
    from auto_patch_v2.airport.riders import agp_half_extent_m, rider_candidates
    assert agp_half_extent_m(agp) == pytest.approx(5.0)
    got = rider_candidates(_airport(law, agp), law)
    assert got["dsf:obj0"] == (pytest.approx(5.0), "agp")
    # an unreadable extent keeps the 0.5 m anchor rule, never a guess
    assert got["dsf:obj3"] == (pytest.approx(0.5), "lib")


def test_a_rotunda_off_the_wall_rides_and_the_far_ones_do_not(law, agp):
    """§1 (1): 1.4 m off the wall inside its TILE rides; the same jetway
    40 m out does not; the marshaller never rides (name-free)."""
    airport, pm, cs = _prep(law, agp)
    st = _strips(law, airport, pm, cs)
    riders = {r.obj_id: r for r in st.riders}
    assert set(riders) == {"dsf:obj0", "dsf:obj1"}
    assert riders["dsf:obj0"].gap_m == pytest.approx(1.4, abs=1e-6)
    assert riders["dsf:obj0"].host_ref == "terminal"
    assert len(st.strips) == 1 and st.strips[0].pad_ref == "terminal"


def test_the_strip_is_the_apron_within_d_minus_the_strike_set(law, agp):
    """§1 (2): strip vertices are APRON vertices within D of a rider edge
    — never a taxi-family vertex, never a no-step-coupled one."""
    from auto_patch_v2.constraints.jetway_strip import strike_set
    from shapely.geometry import LineString, Point
    airport, pm, cs = _prep(law, agp)
    st = _strips(law, airport, pm, cs)
    s = st.strips[0]
    taxi = _verts(pm, "twyA")
    assert s.vertices and not (set(s.vertices) & taxi)
    struck = strike_set(pm, law, airport, _verts(pm, "terminal"))
    assert not any(v in struck for v in s.vertices)
    edges = [LineString(e) for e in s.rider_edges]
    D = float(law.tables.emit.design.jetway_strip_m)
    for v in s.vertices:
        p = Point(*pm.vertices[v].xy)
        assert min(e.distance(p) for e in edges) <= D * 1.5 + 1e-6
    # a pad with no rider mints no strip
    a0, pm0, cs0 = _prep(law, agp, objects=False)
    assert not _strips(law, a0, pm0, cs0).strips


def test_the_strip_takes_the_pad_plane(law, agp):
    """§2 (1) as ruled (Q-32a (d), 2026-09-25): every strip vertex takes
    the PAD'S PLANE at it — §20's least-squares plane through the pad's
    airside frontage at its stage-1 values, tilt bounded by the pad's 1 %
    ceiling.  The fixture's apron falls 0.9 % along the terminal, so the
    plane follows the fall instead of standing level against it."""
    from auto_patch_v2.solve.project_strip import _at, project_strips
    airport, pm, cs = _prep(law, agp)
    st = _strips(law, airport, pm, cs)
    s = st.strips[0]
    n = len(pm.vertices)
    z1 = np.array([_Dem().z(*pm.vertices[v].xy) for v in range(n)])
    levels = {v: float(z1[v]) for v in range(n)}
    before = dict(levels)
    rep = project_strips(pm, law, st, levels, z1)
    pl = tuple(rep.strips[0]["plane"])
    tilt = float(np.hypot(pl[1], pl[2]))
    assert tilt == pytest.approx(0.009, abs=2e-4)         # the frontage's own
    assert rep.strips[0]["gated"] is False
    assert pl[1] < 0.0                                    # it follows the fall
    for v in s.vertices:
        assert levels[v] == pytest.approx(_at(pl, pm.vertices[v].xy), abs=1e-3)
        assert rep.strips[0]["targets"][v] == pytest.approx(levels[v], abs=1e-3)
    tgt = {v: levels[v] for v in s.vertices}
    # the transition carries each strip vertex's CHANGE outward decaying
    # at the apron max: nothing moves by more than the largest change less
    # s·d, and nothing beyond L_t = |fall| / s moves at all
    cap = 0.015
    dmax = max(abs(tgt[u] - before[u]) for u in s.vertices)
    moved = [v for v in range(n) if abs(levels[v] - before[v]) > 1e-9
             and v not in set(s.vertices)]
    for v in moved:
        d = min(np.hypot(*np.subtract(pm.vertices[v].xy, pm.vertices[u].xy))
                for u in s.vertices)
        assert abs(levels[v] - before[v]) <= max(0.0, dmax - cap * d) + 1e-6
        assert d <= dmax / cap + 1e-6
    # the taxi family is byte-identical, and a clamp names it where the
    # field wanted it moved
    for v in _verts(pm, "twyA"):
        assert levels[v] == before[v]
    clamped = {c[0] for d in rep.strips for c in d["clamps"]}
    assert all(st.fixed.get(v) for v in clamped)


def test_a_seam_or_pinned_vertex_is_a_clamp_not_a_mover(law, agp):
    """§2 (3): a pinned (threshold / §38 seam) vertex inside the band is
    NEVER moved; the field is clamped there and it is reported."""
    from auto_patch_v2.model.jetway import StripSet
    from auto_patch_v2.solve.project_strip import project_strips
    airport, pm, cs = _prep(law, agp)
    st = _strips(law, airport, pm, cs)
    s = st.strips[0]
    # pin the transition vertex nearest the strip, as a seam would
    n = len(pm.vertices)
    z1 = np.array([_Dem().z(*pm.vertices[v].xy) for v in range(n)])
    cand = [v for v in st.movable if v not in set(s.vertices)]
    v0 = min(cand, key=lambda v: min(np.hypot(*np.subtract(
        pm.vertices[v].xy, pm.vertices[u].xy)) for u in s.vertices))
    fixed = dict(st.fixed)
    fixed[v0] = "pin"
    st2 = _dc.replace(st, fixed=fixed,
                      movable=frozenset(st.movable - {v0}))
    levels = {v: float(z1[v]) for v in range(n)}
    z_before = levels[v0]
    rep = project_strips(pm, law, st2, levels, z1)
    assert levels[v0] == z_before
    clamps = {c[0]: c for d in rep.strips for c in d["clamps"]}
    L = rep.strips[0]["level"]
    if abs(z_before - L) > 0.02 + 0.015 * 60.0 + 0.01 * 300.0:
        assert v0 in clamps and clamps[v0][1] == "pin"


def test_the_staged_solve_hands_stage2_the_levelled_strip(law, agp):
    """§2 (2)/(4): after the full staged solve every strip vertex sits at
    one level and the pad's plane meets it (the weld reads 0.00 at the
    rider edge — the pad takes the strip)."""
    airport, pm, cs = _prep(law, agp)
    st = _strips(law, airport, pm, cs)
    sol, rep = solve_design(pm, cs, law, strips=st)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    z = np.asarray(sol.z, float)
    s = st.strips[0]
    tg = rep.jetway_strip.strips[0]["targets"]
    assert rep.jetway_strip.ran
    assert max(abs(z[v] - tg[v]) for v in s.vertices) <= 0.05
    # the pad's vertices ON the rider edge are strip vertices (the weld):
    pad = _verts(pm, "terminal")
    weld = pad & set(s.vertices)
    assert weld
    assert max(abs(z[v] - tg[v]) for v in weld) <= 0.05



def test_a_rider_row_is_left_on_ground_unless_its_gate_is_clamped(law):
    """§4 / C17: on ground where the terrain at the anchor equals the unit
    datum; MSL = datum + authored offset only on a clamped gate; an .agp
    is never MSL-written (Q6 default)."""
    from auto_patch_v2.airport.anchor_rule import PadRing
    from auto_patch_v2.airport.riders import riders_for_dump

    class _P:
        def __init__(self, lat, lon, path, kind="OBJECT", elevation=None):
            self.lat, self.lon, self.def_path = lat, lon, path
            self.heading_deg, self.kind, self.elevation = 0.0, kind, elevation

    class _D:
        placements = (_P(10.0, 20.0, "lib/a.obj"),
                      _P(10.0, 20.001, "lib/b.obj"),
                      _P(10.0, 20.002, "Airport/j.agp"),
                      _P(11.0, 20.0, "lib/far.obj"))
    ring = ((10.0001, 19.999), (10.0001, 20.003), (10.001, 20.003),
            (10.001, 19.999))
    pads = (PadRing("terminal", ring, (100.0, 100.0, 100.0, 100.0)),)
    rid = [[10.0, 20.0, "lib/a.obj", 5.0], [10.0, 20.001, "lib/b.obj", 5.0],
           [10.0, 20.002, "Airport/j.agp", 5.0]]
    heights = {20.0: 100.0, 20.001: 101.0, 20.002: 101.0}
    surf = lambda la, lo: heights.get(round(lo, 3))
    flat = [{"id": "strip:u", "pad_ref": "terminal", "riders": rid,
             "clamps": []}]
    got = riders_for_dump(_D(), flat, pads, surf, frozenset(), tol_m=0.02)
    assert [r.seat_why for r in got] == ["on_ground"] * 3
    clamped = [dict(flat[0], clamps=[[10.0, 20.0, "taxi", 1.0]])]
    got = {r.resource: r for r in riders_for_dump(_D(), clamped, pads, surf,
                                                   frozenset(), tol_m=0.02)}
    assert got["lib/a.obj"].seat_why == "on_ground"          # on its datum
    assert got["lib/b.obj"].seat_why == "msl_written"        # a residual
    assert got["lib/b.obj"].seat_z == pytest.approx(100.0)
    assert got["Airport/j.agp"].seat_why == "on_ground"      # Q6: never MSL


def test_riders_and_strips_round_trip_the_plan_schema():
    """C18: ``riders`` / ``jetway_strips`` round-trip the plan JSON."""
    from auto_patch_v2.model.placement import (PlacementPlan, Provenance,
                                               Rider)
    r = Rider(3, "Airport/j.agp", 31.39, 30.108, 90.0, "OBJECT", "building9",
              "building9", 1.4, 5.0, "strip:unit:1#0", 99.37, "on_ground",
              99.37)
    js = ({"id": "strip:unit:1#0", "pad_ref": "building9", "level": 99.37,
           "rider_count": 1, "riders": [[30.108, 31.39, "Airport/j.agp", 5.0]],
           "polygon_ll": [], "vertices_ll": [], "clamps": []},)
    p = PlacementPlan("HECA", "pack", "/p", "/p/x.dsf", "/p/x.dsf.bak",
                      Provenance("", "", "", {}), riders=(r,), jetway_strips=js)
    q = PlacementPlan.from_json(p.to_json())
    assert q.riders == (r,)
    assert q.jetway_strips[0]["pad_ref"] == "building9"


def _cg():
    tools = Path(__file__).resolve().parents[2] / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import check_grade as cg
    return cg


def test_the_census_carries_the_family_and_the_key():
    """C13: a census that omits the family or the sidecar key refuses —
    the register, the sidecar contract, the law tables and v2 verify all
    carry ``jetway_strip``."""
    cg = _cg()
    assert "jetway_strip" in {k for k, _t, _b in cg.LAW_FAMILIES}
    assert cg.SIDECAR_LAW_KEYS["jetway_strips"] == "jetway_strips_ll"
    from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS
    from auto_patch_v2.verify.census import READERS
    assert "jetway_strips" in SIDECAR_KEYS
    assert "jetway_strip" in READERS
    assert "jetway_strip" in Law.for_airport("ZZZZ").tables.families


def test_the_census_prices_a_strip_vertex_off_its_level_and_each_clamp(tmp_path):
    """§2 (6) (a)/(c) through the ONE sidecar reader."""
    cg = _cg()

    class _W:
        def __init__(self):
            self.nids = [1, 2]
            self.elevs = [100.0, 100.20]
    nodes = {1: (10.0, 20.0), 2: (10.0, 20.001)}
    ways = [cg.Way("apron", "apron", "a", "", [], [], {})]
    ways[0].nids = [1, 2]
    ways[0].elevs = [100.0, 100.20]
    js = [{"pad_ref": "t", "level": 100.0,
           "vertices_ll": [[10.0, 20.0, 100.0], [10.0, 20.001]],
           "clamps": [[10.0, 20.0, "taxi", 1.25]]}]
    rows = cg._check_jetway_strip(js, nodes, ways)
    assert len(rows) == 2
    assert sorted(round(r.de_m, 2) for r in rows) == [0.2, 1.25]
    assert cg._check_jetway_strip(None, nodes, ways) == []


def test_a_pad_whose_frontage_is_not_a_plane_gets_no_strip(law, agp):
    """Q-32d (i) (spec-author ruling 2026-09-25): a strip forms only on a
    pad whose stage-1 airside frontage fits its plane within ``[design]
    jetway_strip_plane_tol_m``; elsewhere no strip — nothing of the strip
    or of the pad moves, and the pad's vertices are never moved by a
    neighbour's transition either."""
    import unittest.mock as _mock
    from auto_patch_v2.solve import project_strip as _ps
    assert float(law.tables.emit.design.jetway_strip_plane_tol_m) == 0.5
    airport, pm, cs = _prep(law, agp)
    st = _strips(law, airport, pm, cs)
    n = len(pm.vertices)
    z1 = np.array([_Dem().z(*pm.vertices[v].xy) for v in range(n)])
    levels = {v: float(z1[v]) for v in range(n)}
    before = dict(levels)
    with _mock.patch.object(_ps, "_frontage_residual", lambda *a: 0.9):
        rep = _ps.project_strips(pm, law, st, levels, z1)
    assert rep.gated == 1 and rep.strips[0]["gated"] is True
    assert levels == before
