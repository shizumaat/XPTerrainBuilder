"""§34 TWINS — RAMPS FOLLOW THEIR ROUTE; ZONES YIELD TO ROADS; A BRIDGE
STATES THE CROSSING (Fable 2026-09-13i; RULINGS 2026-09-13i items 1/7/8,
2026-09-13q item 3, 2026-09-13r's owed refinement) — lane ``v2rampwalk``.

One test per clause:

* (1) A RAMP IS PRICED ALONG ITS ROUTE — ``ramp_top`` reads the axis
  walked, never the straight chord from the mouth;
* (2) THE APPROACH WALK KEEPS ITS HEADING — smallest turn at a hop, a
  turn over ``approach_turn_max_deg`` refused, a way's own nodes never
  a hop;
* (3) A RAMP CLIMBS MONOTONICALLY — one one-way row per consecutive
  station toward the top, reversed where the top stands below the datum;
* (4) ZONES YIELD TO ROADS — the band subtracts a mapped ribbon with no
  cell, a GOVERNING rim road still ends the band at its OUTER edge, and
  the census's new within-face step family reads the step;
* (5) A BRIDGE STATES THE CROSSING — an aeroway ``bridge=yes layer=1``
  over a road seeds a bore; layer 0 and a clip do not;
* (6) A DECK END READS THE ROAD — a mapped end with no cell under it
  takes the governed cell within ``bridge.deck_end_reach_m``.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, OsmWay, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar import structure_approach as _sa
from auto_patch_v2.planar import structure_deck as _sd
from auto_patch_v2.planar import structure_underpass as _su
from auto_patch_v2.planar.terrain_edge import road_lines
from auto_patch_v2.planar.zones import zone_regions


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Ramp:
    """A DEM that rises linearly with x from ``z0`` at x = 0."""

    provenance = {"synthetic": "linear ramp in x"}

    def __init__(self, z0=700.0, slope=0.05):
        self.z0, self.slope = z0, slope

    def z(self, x, y):
        return self.z0 + self.slope * x

    def bounds(self):
        return (-40000.0, -40000.0, 40000.0, 40000.0)


def _airport(law, ways=(), dem=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), tuple(ways), (), (), pack, dem or _Ramp(),
                   law.ruleset_key)


TAGS_R = {"highway": "service", "lanes": "2"}
TAGS_T = {"highway": "service", "tunnel": "yes", "lanes": "2"}


# ── (1) a ramp is priced along its route ─────────────────────────────────

def test_the_ramp_is_priced_along_the_route_not_the_chord(law):
    """§34 (1): on a route that DOUBLES BACK, the top is the first station
    where the climb meets the DEM along the AXIS.  The retired chord term
    (``chord × grade >= rise``) held the ramp open while the walked
    distance ran ahead of the straight one — the mechanism behind LEMD
    −15327's 420 m of axis for a 178 m chord."""
    # a hairpin: out along +x to 100, back along -x at y = 20.  At s = 100
    # the chord is 100 m; at s = 200 it is only 20 m.
    path = [(0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0)]
    ln = LineString(path)
    axis = lambda s: (ln.interpolate(min(s, ln.length)).x,
                      ln.interpolate(min(s, ln.length)).y)
    airport = _airport(law, dem=_Ramp(z0=700.0, slope=0.05))
    mouth_z = 700.0 - 4.0            # the DEM at x = 0 is 700; the floor 4 m under
    s_top, _ss = _sa.ramp_top(airport, law, axis, mouth_z, 0.0, 12.0)
    assert s_top is not None
    # the route test: |DEM(s) - mouth_z| <= grade * s.  The DEM rises 5 %
    # in x while the ramp climbs 8 % along the route, so it catches up on
    # the OUTWARD leg and never reaches the doubling-back part.
    g = law.tables.structures.tunnel.ramp_max_grade
    p = axis(s_top - 12.0)
    assert abs(airport.dem.z(*p) - mouth_z) <= g * (s_top - 12.0) + 1e-9
    assert s_top <= 160.0, "the ramp must not run past its own route reading"
    # and the CHORD at that station is shorter than the axis: the retired
    # term would still have been unsatisfied there
    q = axis(s_top)
    assert math.hypot(q[0], q[1]) < s_top


# ── (2) the approach walk keeps its heading ──────────────────────────────

def _walk_ways():
    """A mouth at the origin, the bore to the west; a straight
    continuation east and a 90° branch north sharing the junction node."""
    bore = OsmWay(-1, "big_roads", ((-50.0, 0.0), (0.0, 0.0)), False, TAGS_T)
    lead = OsmWay(-2, "big_roads", ((0.0, 0.0), (60.0, 0.0)), False, TAGS_R)
    straight = OsmWay(-3, "big_roads", ((60.0, 0.0), (200.0, 0.0)), False, TAGS_R)
    branch = OsmWay(-4, "big_roads", ((60.0, 0.0), (60.0, 200.0)), False, TAGS_R)
    return bore, lead, straight, branch


def test_the_walk_takes_the_smallest_turn_and_refuses_a_sharp_one(law):
    """§34 (2): at the node where the way it entered ENDS, the walk takes
    the smallest-turn continuation — not the first in load order — and a
    turn over ``approach_turn_max_deg`` is refused outright."""
    bore, lead, straight, branch = _walk_ways()
    cap = law.tables.structures.tunnel.approach_turn_max_deg
    # the BRANCH is offered first in load order; the walk must still take
    # the straight continuation
    path = _sa.approach((0.0, 0.0), (-1.0, 0.0), [bore, lead, branch, straight],
                        300.0, ("yes",), cap)
    assert max(p[1] for p in path) < 1.0, path      # never turned north
    assert LineString(path).length >= 200.0
    # with ONLY the branch on offer the 90° turn is refused and the walk
    # ends with the straight extension of its own heading
    path2 = _sa.approach((0.0, 0.0), (-1.0, 0.0), [bore, lead, branch],
                         300.0, ("yes",), cap)
    assert max(p[1] for p in path2) < 1.0, path2
    # ...and an unrestricted cap would have taken it
    path3 = _sa.approach((0.0, 0.0), (-1.0, 0.0), [bore, lead, branch],
                         300.0, ("yes",), 180.0)
    assert max(p[1] for p in path3) > 100.0


def test_a_ways_own_nodes_are_never_a_hop(law):
    """§34 (2): "the route stays on the way it entered until that way
    ends" — a mapped HAIRPIN turns through 180° in its OWN nodes and is
    walked whole (LEMD −5958), so the cap never shortens a mapped route."""
    hairpin = OsmWay(-5, "big_roads",
                     ((0.0, 0.0), (100.0, 0.0), (140.0, 20.0), (100.0, 40.0),
                      (0.0, 40.0)), False, TAGS_R)
    bore = OsmWay(-1, "big_roads", ((-50.0, 0.0), (0.0, 0.0)), False, TAGS_T)
    cap = law.tables.structures.tunnel.approach_turn_max_deg
    path = _sa.approach((0.0, 0.0), (-1.0, 0.0), [bore, hairpin], 400.0,
                        ("yes",), cap)
    assert LineString(hairpin.points).length == pytest.approx(
        LineString(path[:len(hairpin.points)]).length, abs=0.01)
    assert path[len(hairpin.points) - 1] == pytest.approx((0.0, 40.0))


# ── (5) a bridge states the crossing ─────────────────────────────────────

def _underpass_ways(layer="1", aeroway="taxiway"):
    # a REAL taxiway bridge's width: the lanes fallback (2 x 3.5) is a third
    # of one and, less the rim stand-off, clips to nothing
    tags = {"aeroway": aeroway, "bridge": "yes", "width": "23"}
    if layer is not None:
        tags["layer"] = layer
    deck = OsmWay(-10, "airport", ((-40.0, 0.0), (40.0, 0.0)), False, tags)
    road = OsmWay(-11, "big_roads", ((0.0, -200.0), (0.0, 200.0)), False, TAGS_R)
    return deck, road


def test_an_aeroway_bridge_over_a_road_seeds_a_bore(law):
    """§34 (5): the road under an ``aeroway`` ``bridge=yes layer>=1`` way is
    BORED though OSM tags it nothing — LEMD F-6 and KCLT taxiway U both
    carry an untagged road under a tagged taxiway bridge.  The bore is the
    road clipped to the deck's ribbon; its ends are the mouths."""
    deck, road = _underpass_ways()
    airport = _airport(law, ways=[deck, road])
    ways, parents, notes = _su.underpass_bores(airport, law, [], [])
    assert len(ways) == 1, notes
    sw = ways[0]
    assert sw.id == -11 and sw.tags["tunnel"] == "yes"
    assert sw.tags[_su.UNDERPASS_TAG] == "-10"
    # the clip is the deck's half-width LESS the rim stand-off and one
    # identity step (spec §34 (5) as amended, RULINGS 2026-09-13ai): the
    # mouth stands INSIDE the taxi cell so the corridor's end cap — the rim
    # — lands on the deck and takes its solved surface, never DEM(mouth)
    tn = law.tables.structures.tunnel
    half = _sa.carriageway_width_m(deck.tags, law) / 2.0
    grid = max(law.tables.emit.identity.min_distinct_spacing_m, 0.1)
    half_clip = max(grid, half - (tn.wall_gap_m + tn.wall_band_width_m) - grid)
    assert LineString(sw.points).length == pytest.approx(2.0 * half_clip, abs=0.2)
    assert half_clip < half
    assert notes and "underpass taxiway -10" in notes[0]
    # the PARENT line is the whole road: the ramp follows it, not a
    # straight extension from a node that does not exist
    assert parents[id(sw)].length == pytest.approx(400.0)


def test_layer_zero_and_a_clip_state_no_crossing(law):
    """§34 (5): ``layer >= underpass_min_layer`` is OSM's own statement
    that the aeroway is ABOVE what it crosses, and a road merely clipping
    the deck's corner (under ``underpass_min_span_m``) is not a crossing."""
    tn = law.tables.structures.tunnel
    deck0, road = _underpass_ways(layer="0")
    a0 = _airport(law, ways=[deck0, road])
    assert _su.underpass_bores(a0, law, [], [])[0] == []
    deck_no, _ = _underpass_ways(layer=None)
    a1 = _airport(law, ways=[deck_no, road])
    assert _su.underpass_bores(a1, law, [], [])[0] == []
    # a road grazing the ribbon's very end: under the span floor
    deck, _r = _underpass_ways()
    half = _sa.carriageway_width_m(deck.tags, law) / 2.0
    grid = max(law.tables.emit.identity.min_distinct_spacing_m, 0.1)
    hc = max(grid, half - (tn.wall_gap_m + tn.wall_band_width_m) - grid)
    graze = OsmWay(-12, "big_roads",
                   ((40.0 + hc - 1.0, -50.0), (40.0 + hc - 1.0, 50.0)),
                   False, TAGS_R)
    a2 = _airport(law, ways=[deck, graze])
    got = _su.underpass_bores(a2, law, [], [])[0]
    assert all(LineString(w.points).length >= tn.underpass_min_span_m for w in got)


def test_no_underpass_under_a_jetway(law):
    """§34 (5) NARROWED (Fable 2026-09-13; owner RULINGS 2026-09-13bm item
    1).  SPJC's OSM carries 63 ways ``{aeroway=jet_bridge, bridge=yes,
    highway=footway, layer=1}`` and every one of them bored the apron
    service roads beneath it: 19 underpasses, 86 roads, 11 of 18 tunnel
    records, and four ``bridge_deck:`` faces across a live apron.  Only an
    aeroway a TAXIING AIRCRAFT uses states a crossing."""
    from auto_patch_v2.airport.deck_signature import is_bridge_way
    for aeroway in ("taxiway", "runway", "apron"):
        assert _su.is_aeroway_bridge({"aeroway": aeroway, "bridge": "yes"})
    for aeroway in ("jet_bridge", "parking_position", "gate", ""):
        assert not _su.is_aeroway_bridge({"aeroway": aeroway,
                                          "bridge": "yes"})
    # a footway is refused whatever its aeroway says
    assert not _su.is_aeroway_bridge(
        {"aeroway": "taxiway", "bridge": "yes", "highway": "footway"})
    assert not _su.is_aeroway_bridge({"aeroway": "taxiway", "bridge": "no"})

    # and no jetway mints a terrain DECK either (symmetrically), while a
    # plain road or rail bridge still does
    jetway = {"access": "private", "aeroway": "jet_bridge", "bridge": "yes",
              "highway": "footway"}          # KCLT way -1361, verbatim
    assert not is_bridge_way(jetway)
    assert is_bridge_way({"highway": "footway", "bridge": "yes"})
    assert is_bridge_way({"railway": "rail", "bridge": "yes"})

    # end to end: the jetway bores nothing
    deck, road = _underpass_ways(aeroway="jet_bridge")
    deck = OsmWay(deck.id, deck.kind, deck.points, False,
                  {**dict(deck.tags), "highway": "footway"})
    ap = _airport(law, ways=[deck, road])
    assert _su.underpass_bores(ap, law, [], [])[0] == []


def test_a_blob_cell_never_states_the_deck(law):
    """§34 (5) NARROWED: ``_deck_half_width`` reads the pavement CELL the
    axis stands in, and SPJC's 738,901 m2 ``pav40`` apron turned a 4 m
    jetway into a 49-127 m ribbon that caught every road on the apron.  A
    cell whose HALF-WIDTH exceeds ``DECK_CELL_MAX_RATIO`` x the way's own
    CARRIAGEWAY WIDTH is refused and the carriageway is the deck.

    The ratio is measured, not guessed: at 4x the carriageway it refuses
    all 19 of SPJC's blobs and keeps KCLT taxiway U's real 18.0 m deck."""
    from shapely.geometry import Polygon as _Poly
    from auto_patch_v2.classify.roles import Cell as _Cell

    class _C:
        kind = "pavement"
    half_default = 4.0                       # a 8 m carriageway
    cap = _su.DECK_CELL_MAX_RATIO * 2.0 * half_default
    axis = lambda s: (float(s), 0.0)
    ss = [0.0, 10.0, 20.0]

    def read(cell_half):
        poly = _Poly([(-100.0, -cell_half), (200.0, -cell_half),
                      (200.0, cell_half), (-100.0, cell_half)])
        return _su._deck_half_width(axis, ss, [_C()], [poly], half_default,
                                    cap)

    inside, n_read, n_ref = read(cap - 5.0)
    assert inside == pytest.approx(cap - 5.0) and n_read == 3 and n_ref == 0
    blob, n_read, n_ref = read(cap + 5.0)
    assert blob == half_default and n_read == 0 and n_ref == 3


def test_the_underpass_ramp_follows_the_parent_road(law):
    """§34 (5)/(1): a mouth the clip made stands mid-way along the road, at
    no mapped node, so ``approach``'s node index finds nothing there —
    ``approach_along`` walks the PARENT centreline instead."""
    parent = LineString([(0.0, -200.0), (0.0, 0.0), (60.0, 120.0)])
    # the mouth at the deck's south edge, the bore heading north
    path = _su.approach_along(parent, (0.0, -10.0), (0.0, 1.0), 150.0)
    assert path[0] == pytest.approx((0.0, -10.0))
    assert path[-1][1] < -10.0, "the ramp must leave the deck, not enter it"
    assert LineString(path).length >= 150.0


# ── (4) zones yield to roads ─────────────────────────────────────────────

def test_the_band_yields_to_a_tunnel_corridor_and_stands_off_it(law):
    """§34 (4) as NARROWED (RULINGS 2026-09-13ar): a zone band yields ONLY
    to a TUNNEL CORRIDOR — the mouth, ramp, trench and underpass corridor
    the structure pass publishes as ``Classification.keepouts`` — and it
    stands off that corridor by the same ``groundside_cutback_m`` a
    groundside cell gets, so the band never shares a vertex with the
    corridor's rim and the gap terraces against the ramp walls.

    Round 2's general "yields to every mapped road" trim is WITHDRAWN: it
    exposed a region's OWN outer ring (LEMD ``zone2#24``, 8.49 m over
    12.03 m) and cost 671 ``graded_strip|graded_strip`` rows against zero
    in the base.  A road elsewhere in adjacent ground grades WITH the
    zone."""
    from auto_patch_v2.law.tables import snap_margin_m
    taxi = Cell(1, "junction", "pav1", _rect(-200.0, -12.0, 200.0, 12.0), (),
                None, "D", "airside", "pavement", {})
    # a corridor crossing the band at x = 0, 8 m wide
    corridor = _rect(-4.0, 12.0, 4.0, 40.0)
    road = OsmWay(-20, "big_roads", ((-300.0, 24.0), (300.0, 24.0)), False, TAGS_R)
    roads = road_lines([road])
    plain = zone_regions((taxi,), law, (), None, roads)
    withc = zone_regions((taxi,), law, (corridor,), None, roads)
    # THE ROAD ALONE TAKES NOTHING (the withdrawal)
    assert sum(r.polygon.area for r in plain) == pytest.approx(
        sum(r.polygon.area for r in zone_regions((taxi,), law, (), None, ())), rel=1e-9)
    # THE CORRIDOR DOES, with the stand-off
    cut = law.tables.zones.adjacent_ground.groundside_cutback_m + snap_margin_m(law)
    keep = Polygon(corridor)
    assert sum(r.polygon.area for r in withc) < sum(r.polygon.area for r in plain)
    for r in withc:
        assert r.polygon.intersection(keep).area < 1.0, r.ref
        assert r.polygon.distance(keep) >= cut - 0.05, (r.ref, r.polygon.distance(keep))


def test_the_census_prices_a_within_face_step(law):
    """§34 (4): the new census family.  ``graded_strip`` carries no
    within-shape cap, ``adjacent_ground_tear`` fires only under a 1 m edge
    and ``strip_seam_tear`` is the CROSS-shape twin, so LEMD's 1.73 m step
    over 1.5 m INSIDE one adjacent-ground face was priced by nothing."""
    import check_grade as cg
    assert cg.ADJACENT_GROUND_STEP_FAMILY in {k for k, _t, _b in cg.LAW_FAMILIES}
    ck = cg.cockpit_law()
    step, cliff = float(ck["visual_m"]), float(ck["cliff_grade"])

    class _W:
        def __init__(self, ref, nids, elevs):
            self.ref, self.nids, self.elevs = ref, nids, elevs
            self.tags = {"role": "graded_strip"}

    nodes = {"a": (0.0, 0.0), "b": (1.35e-5, 0.0), "c": (2.7e-5, 0.0)}
    ll_to_m = lambda la, lo: (lo * 84700.0, la * 111320.0)
    w = _W("adjacent_ground:taxi:E:zone2#2", ["a", "b", "c"],
           [615.89, 613.54, 613.50])
    rows = cg._check_adjacent_ground_steps([w], nodes, ll_to_m, step, cliff)
    assert len(rows) == 1 and rows[0].de_m == pytest.approx(2.35, abs=0.01)
    assert rows[0].distance_m == pytest.approx(1.5, abs=0.2)
    # a v1 patch (ref ``adjacent_ground`` exactly) reads nothing
    v1 = _W("adjacent_ground", ["a", "b", "c"], [615.89, 613.54, 613.50])
    assert cg._check_adjacent_ground_steps([v1], nodes, ll_to_m, step, cliff) == []
    # ...and a HILLSIDE DRAPE (the same step over 30 m) is ground, not a cut
    far = {"a": (0.0, 0.0), "b": (2.7e-4, 0.0), "c": (5.4e-4, 0.0)}
    assert cg._check_adjacent_ground_steps([w], far, ll_to_m, step, cliff) == []


# ── (6) a deck end reads the road ────────────────────────────────────────

def test_a_deck_end_takes_the_governed_cell_within_reach(law):
    """§34 (6) (RULINGS 2026-09-13r, owed): a mapped way STOPS at the
    surface it runs onto — OSM does not trace a service road across an
    apron — so the governed cell the end MEETS stands a few metres past
    the last node (measured LEMD −6288: 13.3 m to apron pav92)."""
    reach = law.tables.structures.bridge.deck_end_reach_m
    apron = Cell(1, "apron", "pav92", _rect(100.0 + reach / 2.0, -50.0,
                                            400.0, 50.0), (),
                 None, "D", "airside", "pavement", {})
    cells = [apron]
    polys = [Polygon(c.ring, c.holes) for c in cells]
    tree = STRtree(polys)
    airport = _airport(law, dem=_Ramp(z0=700.0, slope=0.0))
    w = OsmWay(-6288, "big_roads", ((0.0, 0.0), (100.0, 0.0)), False,
               {"highway": "service", "bridge": "yes", "lanes": "4"})
    zs, refs, pts = _sd.deck_ends(airport, w, cells, polys, tree, law)
    assert refs[0] == "" and refs[1] == "pav92"
    assert zs[0] == pytest.approx(700.0) and pts[1] == (100.0, 0.0)
    # ...and a cell beyond the reach is NOT that end's ground
    far = Cell(2, "apron", "pav99", _rect(100.0 + reach * 2.0, -50.0, 400.0, 50.0),
               (), None, "D", "airside", "pavement", {})
    fp = [Polygon(far.ring, far.holes)]
    _z2, refs2, _p2 = _sd.deck_ends(airport, w, [far], fp, STRtree(fp), law)
    assert refs2 == ("", "")
