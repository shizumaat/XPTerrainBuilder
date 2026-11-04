"""R6 (owner RULINGS 2026-10-28k, Q228 a; spec ``lfpg-cuts-tunnels-rules-
spec.md`` R6): A ROAD UNDER STACKED VIADUCTS INSIDE THE AIRPORT SITS A MOUTH
DEPTH BELOW THE APRON (``planar/viaduct_road``).

Found at LFPG (the Terminal 2 central road under the departure and arrival
viaducts).  The twins hold the general rule on a synthetic field: a mapped
road running >= ``viaduct_min_run_m`` under ``layer >= viaduct_min_layer``
bridge ways inside the aerodrome boundary is two sibling Law-B halves level
at ``apron - mouth_depth_m``, climbing back to the ground beyond the run; a
lower viaduct, a short run or a run outside the boundary builds nothing."""
from __future__ import annotations

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Boundary, OsmWay
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.planar.viaduct_road import ID_PREFIX, viaduct_road_groups
from shapely.geometry import Polygon

GROUND = 100.0
#: an apron north of the road, its south edge 60 m off it
APRON = ((-300.0, 60.0), (300.0, 60.0), (300.0, 200.0), (-300.0, 200.0))
BOX = ((-2000.0, -2000.0), (2000.0, -2000.0), (2000.0, 2000.0), (-2000.0, 2000.0))


class _Dem:
    def z(self, x: float, y: float) -> float:
        return GROUND


class _Field:
    def __init__(self, ways, boundary=BOX):
        self.osm_ways = tuple(ways)
        self.dem = _Dem()
        self.boundaries = (Boundary("b", boundary, ()),) if boundary else ()


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ways(layer: int = 2, span: float = 200.0):
    road = OsmWay(1, "big_roads", ((-1000.0, 0.0), (0.0, 0.0), (1000.0, 0.0)), False,
                  {"highway": "service"})
    via = OsmWay(2, "big_roads", ((-span / 2.0, 0.0), (span / 2.0, 0.0)), False,
                 {"highway": "trunk", "bridge": "yes", "layer": str(layer)})
    return [road, via]


def _cells():
    c = Cell(0, "apron", "A", APRON, (), None, None, "airside", "apron", {})
    return (c,), (Polygon(APRON),)


def test_a_road_under_stacked_viaducts_is_lowered_a_mouth_depth(law):
    cells, polys = _cells()
    groups, notes, refused = viaduct_road_groups(_Field(_ways()), law, cells, polys)
    assert not refused and len(notes) == 1 and "R6" in notes[0]
    assert len(groups) == 2
    a, b = groups
    assert a.sibling == b.tid and b.sibling == a.tid
    assert a.tid.startswith(ID_PREFIX) and a.kind == "sunken_road"
    assert not a.capped and not a.mouth_strip
    tn = law.tables.structures.tunnel
    floor = GROUND - tn.mouth_depth_m
    for g in groups:
        # level under the viaducts (100 m each side of the midpoint) ...
        assert profile_z(g.profile, 0.0) == pytest.approx(floor)
        assert profile_z(g.profile, 95.0) == pytest.approx(floor)
        # ... climbing back to the ground beyond the run at the design grade
        s_top, z_top = g.profile[-1]
        assert z_top == pytest.approx(GROUND, abs=tn.ramp_grade * 5.0 + 1e-6)
        rise = (z_top - floor) / (s_top - g.profile[1][0])
        assert rise <= tn.ramp_grade + 1e-9
        assert g.corridor.floor_z == pytest.approx(floor)


@pytest.mark.parametrize("layer,span,boundary", [
    (1, 200.0, BOX),                     # a single-level bridge is not a viaduct stack
    (2, 60.0, BOX),                      # under 100 m of cover
    (2, 200.0, ((1500.0, 1500.0), (1900.0, 1500.0), (1900.0, 1900.0))),  # outside the field
    (2, 200.0, None),                    # no aerodrome boundary at all
])
def test_no_witness_builds_nothing(law, layer, span, boundary):
    cells, polys = _cells()
    groups, notes, refused = viaduct_road_groups(_Field(_ways(layer, span), boundary), law,
                                                 cells, polys)
    assert groups == [] and notes == [] and refused == []


def test_no_apron_near_the_run_is_refused_by_name(law):
    groups, notes, refused = viaduct_road_groups(_Field(_ways()), law, (), ())
    assert groups == [] and len(refused) == 1 and "no airside apron" in refused[0]


# ── #1808: the floor is level B under the SOLVED apron beside it ─────────

def _field_airport(law):
    """A synthetic airport carrying the R6 witness (``_ways``) with the apron
    north of the road on a DEM sloping 0.5 % along it."""
    from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
    from auto_patch_v2.model.frame import Frame

    class _Slope:
        provenance = {"synthetic": "plane 0.5 % along x"}

        def z(self, x: float, y: float) -> float:
            return GROUND + 0.005 * x

        def bounds(self):
            return (-5000.0, -5000.0, 5000.0, 5000.0)

    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, GROUND - 3.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, GROUND + 3.0, "fixture"))
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, GROUND, (Runway("09/27", 45.0, 1, ends, 3, "D"),),
                   (), (), {}, (), (), (Boundary("b", BOX, ()),), (), tuple(_ways()), (), (),
                   pack, _Slope(), law.ruleset_key)


def test_the_floor_is_tied_to_the_solved_apron_beside_it(law):
    """RULINGS 2026-11-03b Q342 a (#1808): no floor vertex is pinned at the
    planner's raw-DEM level; every one stands ``mouth_depth_m`` under the
    mean SOLVED level of the apron beside the run, both halves one level,
    and each climb runs straight from that floor to its planned top."""
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.structures import ramp_faces_of, ramp_groups
    from auto_patch_v2.constraints.structures import structures as structure_rows
    from auto_patch_v2.model.constraints import Linear, Pin
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.solve import Status, solve_design
    airport = _field_airport(law)
    run = Cell(0, "runway", "09/27", ((-600.0, 500.0), (600.0, 500.0), (600.0, 545.0),
                                      (-600.0, 545.0)), (), 3, "D", "airside", "runway", {})
    apron = Cell(1, "apron", "apron1", APRON, (), None, None, "airside", "apron", {})
    pm, stats = build(airport, Classification((run, apron), (), {}, ()), law)
    halves = [t for t in pm.structures if t.id.startswith(ID_PREFIX)]
    assert len(halves) == 2, stats.structures.refused
    rows = structure_rows(pm, law, airport)
    from auto_patch_v2.constraints.viaduct_floor import HALF_PREFIX
    assert HALF_PREFIX == f"{ID_PREFIX}:"
    ties = [r for r in rows if isinstance(r, Linear) and "R6 floor" in r.source.ruling]
    assert ties
    ramps = ramp_faces_of(pm, halves)
    floor_vs = {v for t in halves for f in ramps[t.id] for s, vs in ramp_groups(pm, t, f)
                for v in vs if s <= t.profile[1][0] - 0.5}
    pinned = {r.v for r in rows if isinstance(r, Pin)}
    assert floor_vs and not floor_vs & pinned
    witnesses = {v for r in ties for v, _c in r.terms[1:]}
    assert witnesses and all(any(pm.faces[f].role == "apron" for f in
                                 pm.vertices[w].incident_faces) for w in witnesses)
    cs, _counts, _w = generate(pm, law, airport)
    sol = solve_design(pm, cs, law)[0]
    assert sol.status is Status.OPTIMAL, sol.iis[:5]
    level = sum(sol.z[w] for w in witnesses) / len(witnesses) \
        - law.tables.structures.tunnel.mouth_depth_m
    for v in floor_vs:
        assert sol.z[v] == pytest.approx(level, abs=0.02)
    for t in halves:
        (s_f, _z), (s_top, z_top) = t.profile[1], t.profile[-1]
        for f in ramps[t.id]:
            for s, vs in ramp_groups(pm, t, f):
                if s_f + 0.5 < s < s_top:
                    want = level + (z_top - level) * (s - s_f) / (s_top - s_f)
                    assert all(sol.z[v] == pytest.approx(want, abs=0.02) for v in vs)


def test_a_half_opening_onto_level_b_does_not_climb():
    """Q340 a (#1638 / #1808, MEASURED LFPG T2): a half whose far end meets
    a LOWER LEVEL's face (``building35/p2#strip``) runs on at the floor —
    no climb rows; a half ending on ordinary ground climbs."""
    from types import SimpleNamespace as NS

    from auto_patch_v2.constraints.viaduct_floor import _half_rows, _opens_onto_level_b
    from auto_patch_v2.model.constraints import Linear, Pin, Source
    faces = {0: NS(ref="tunnel_ramp"), 1: NS(ref="building35/p2#strip"), 2: NS(ref="lot7")}
    pm = NS(vertices={0: NS(incident_faces=(0,)), 1: NS(incident_faces=(0,)),
                      2: NS(incident_faces=(0, 1)), 3: NS(incident_faces=(0, 2))},
            faces=faces)
    tn = NS(top_s=100.0, profile=((0.0, 90.0), (40.0, 90.0), (100.0, 97.0)))
    into_b = [(0.0, [0]), (60.0, [1]), (100.0, [2])]
    onto_ground = [(0.0, [0]), (60.0, [1]), (100.0, [3])]
    assert _opens_onto_level_b(pm, tn, into_b)
    assert not _opens_onto_level_b(pm, tn, onto_ground)
    src = Source("structures", "tunnel.mouth_depth_m (twin)", ())
    flat = _half_rows(tn, into_b, [7, 8], 7.5, src, set(), True)
    climb = _half_rows(tn, onto_ground, [7, 8], 7.5, src, set(), False)
    # level: every vertex z - mean(w) = -7.5; climbing: the top pinned at 97
    assert all(isinstance(r, Linear) and abs(abs(r.hi) - 7.5) < 1e-9 for r in flat)
    assert any(isinstance(r, Pin) and r.z == 97.0 for r in climb)
    mid = [r for r in climb if isinstance(r, Linear) and r.terms[0][0] == 1]
    t = (60.0 - 40.0) / 60.0
    assert mid and abs(mid[0].hi - (t * 97.0 - (1.0 - t) * 7.5)) < 1e-9
