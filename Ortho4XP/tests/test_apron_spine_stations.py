"""APRON SPINE STATIONS — twins for §1 and §3 of
docs/specs/heca-apron-round3-spec.md (owner sim read of 1.0.260,
RULINGS 2026-08-26b items 3/4/5).

THE DEFECT.  The owner's 84.2 m line T at HECA carried ZERO interior
emitted stations (vertices only at arc 0.00/84.22).  The taxi ROUTE was
never cut — the sidecar axes chain straight across the apron at cap
1.5 % — what was cut is the ANCHORED SURFACE, so the junction pieces the
centerline profile does anchor stood 0.7-1.2 m PROUD of the membrane
beside them, and the same membrane, coupled only to its own ring, sagged
to 70.11 at the owner's dip site.  Proud ridge and bowl are the two
sides of ONE missing coupling.

These twins pin the legs:
  * the AXIS POPULATION is ``grade_graph.centerline_specs`` — the same
    enumeration the sidecar's ``axes_exact`` publishes, never a second
    notion — and SERVICE axes are excluded;
  * the SPACING is the standing ``layout.PAVEMENT_NODE_MAX_CHORD_M``,
    reused, and a crossing at or under it gets no station;
  * a station is a CENTERLINE node: it is registered in ``G.pos`` BEFORE
    the global-spine walk, which is what makes phase A value it from the
    axis's own profile;
  * the LAW is the apron's own — station↔ring and station↔lattice pairs
    priced through ``_grade_graph_edges``/``classify_pair``, never a
    private cap, and NEVER station↔station (that pair is the spine's);
  * §3: a lattice point within 1.5x ``APRON_LATTICE_SPACING_M`` of a
    station is joined to it — one membrane, one law;
  * the FLAG defaults ON and OFF is vacuous everywhere.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import importlib
import inspect
import json
import math
import os
import sys
from pathlib import Path

from shapely.geometry import Point, Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import apron_spine_stations as ST         # noqa: E402
from auto_patch.layout import PAVEMENT_NODE_MAX_CHORD_M   # noqa: E402

ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron"):
        self.polygon = polygon
        self.role = role
        self.ref = ""
        self.fan_ramp_zone = False
        self.lateral_cap = None


class _CPS:
    """The canonical registry's contract, at its own 0.5 m tolerance."""

    def __init__(self):
        self._k = {}

    def get_or_add(self, x, y):
        k = (int(round(x / 0.5)), int(round(y / 0.5)))
        self._k.setdefault(k, k)
        return k


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.anchor = ANCHOR
        self.canonical_points = _CPS()

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


def _square(side):
    h = side / 2.0
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)])


def _specs(*axes, service=False):
    """``centerline_specs``' shape: ``(pts, seg_caps, is_service,
    route_key, route_pts)``."""
    return [(list(a), [0.015] * (len(a) - 1), service, ("taxi", i), list(a))
            for i, a in enumerate(axes)]


def _patch_specs(monkeypatch, specs):
    import auto_patch.grade_graph as GG
    monkeypatch.setattr(GG, "centerline_specs", lambda layout: specs)


# ═════════════════════════════════════════════════════════════════════
# SPACING — the standing pavement-node rule, reused
# ═════════════════════════════════════════════════════════════════════

def test_the_spacing_is_the_standing_pavement_node_constant():
    """No new number.  ``PAVEMENT_NODE_MAX_CHORD_M`` exists because "a
    longer chord lets the pavement sag visibly between distant nodes" —
    which is the sag the owner saw."""
    src = inspect.getsource(ST.construct_apron_spine_stations_presolve)
    assert "PAVEMENT_NODE_MAX_CHORD_M" in src
    assert "60" not in src.replace("60 m", "")


def test_a_crossing_at_or_under_the_spacing_gets_no_station():
    assert ST.stations_on_piece([(0.0, 0.0), (59.0, 0.0)],
                                PAVEMENT_NODE_MAX_CHORD_M) == []
    assert ST.stations_on_piece([(0.0, 0.0), (60.0, 0.0)],
                                PAVEMENT_NODE_MAX_CHORD_M) == []


def test_no_sub_chord_exceeds_the_spacing():
    for L in (61.0, 84.2, 200.0, 507.3):
        pts = [(0.0, 0.0), (L, 0.0)]
        st = ST.stations_on_piece(pts, PAVEMENT_NODE_MAX_CHORD_M)
        assert st, L
        # at least THREE: a two-node way is dropped by
        # ``check_grade._parse_osm`` before its open-feature route, so a
        # crossing emitted with fewer would be a LOST MEASUREMENT
        assert len(st) >= 3, L
        xs = [0.0] + [p[0] for p in st] + [L]
        assert max(b - a for a, b in zip(xs, xs[1:])) <= \
            PAVEMENT_NODE_MAX_CHORD_M + 1e-6, L


def test_the_owner_line_length_gains_interior_stations():
    """The measured case: 84.2 m with ZERO interior stations was the
    defect."""
    st = ST.stations_on_piece([(0.0, 0.0), (84.2, 0.0)],
                              PAVEMENT_NODE_MAX_CHORD_M)
    assert len(st) == 3
    for k in (1, 2, 3):
        assert abs(st[k - 1][0] - k * 84.2 / 4.0) < 1e-9


def test_stations_follow_a_bent_axis_by_ARC_length():
    """An axis is a polyline, not a segment: the station is placed at an
    arc position, on the piece."""
    pts = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]
    st = ST.stations_on_piece(pts, PAVEMENT_NODE_MAX_CHORD_M)
    line = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]
    from shapely.geometry import LineString
    ls = LineString(line)
    for (x, y) in st:
        assert ls.distance(Point(x, y)) < 1e-6


# ═════════════════════════════════════════════════════════════════════
# THE AXIS POPULATION — one enumeration, aircraft only
# ═════════════════════════════════════════════════════════════════════

def test_the_population_is_centerline_specs_itself():
    """The same list the sidecar's ``axes_exact`` publishes.  A private
    second notion here is the census-wrapper defect in miniature."""
    src = inspect.getsource(ST.construct_apron_spine_stations_presolve)
    assert "centerline_specs" in src


def test_an_axis_crossing_an_apron_mints_stations(monkeypatch):
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    entries = ST.construct_apron_spine_stations_presolve(layout)
    assert len(entries) == 1
    e = entries[0]
    assert e["shape"] is ap
    assert e["points"] and e["lines"]
    poly = ap.polygon
    for (x, y) in e["points"]:
        assert poly.contains(Point(x, y)), (x, y)
        assert abs(y) < 1e-6, "a station lies ON its axis"
    # the crossing is 400 m of apron -> at least 400/60 sub-chords
    assert len(e["points"]) >= 6


def test_an_axis_that_crosses_NO_apron_mints_nothing(monkeypatch):
    """§1.5's byte-identical arm: the whole feature is inert where the
    premise does not hold."""
    layout = _Layout([_Shape(_square(400.0))])
    _patch_specs(monkeypatch, _specs([(-3000.0, 900.0), (3000.0, 900.0)]))
    assert ST.construct_apron_spine_stations_presolve(layout) == []
    assert layout.apron_spine_presolve == []


def test_a_SERVICE_axis_is_not_an_aircraft_spine(monkeypatch):
    """A truck route is never an aircraft spine
    (``grade_graph._reads_service_spines``)."""
    layout = _Layout([_Shape(_square(400.0))])
    _patch_specs(monkeypatch,
                 _specs([(-300.0, 0.0), (300.0, 0.0)], service=True))
    assert ST.construct_apron_spine_stations_presolve(layout) == []


def test_only_apron_role_shapes_are_stationed(monkeypatch):
    layout = _Layout([_Shape(_square(400.0), role="taxiway")])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    assert ST.construct_apron_spine_stations_presolve(layout) == []


def test_a_station_never_lands_on_an_existing_plan_vertex(monkeypatch):
    """It would ADOPT that node's variable and then be emitted a second
    time at the same coordinate — a duplicate, not an anchor."""
    ap = _Shape(_square(400.0))
    # a junction ring vertex sitting exactly where a station would land
    st_ref = ST.stations_on_piece([(-200.0, 0.0), (200.0, 0.0)],
                                  PAVEMENT_NODE_MAX_CHORD_M)
    hit = st_ref[0]
    blocker = _Shape(Polygon([(hit[0], hit[1]), (hit[0] + 5, hit[1]),
                              (hit[0] + 5, hit[1] + 5),
                              (hit[0], hit[1] + 5),
                              (hit[0], hit[1])]), role="junction")
    layout = _Layout([ap, blocker])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    entries = ST.construct_apron_spine_stations_presolve(layout)
    got = {(round(x, 3), round(y, 3)) for e in entries
           for (x, y) in e["points"]}
    assert (round(hit[0], 3), round(hit[1], 3)) not in got


def test_two_aprons_on_one_axis_each_get_their_own_stations(monkeypatch):
    from shapely.affinity import translate
    a = _Shape(_square(300.0))
    b = _Shape(translate(_square(300.0), 900.0, 0.0))
    layout = _Layout([a, b])
    _patch_specs(monkeypatch, _specs([(-500.0, 0.0), (1500.0, 0.0)]))
    entries = ST.construct_apron_spine_stations_presolve(layout)
    assert len(entries) == 2
    # and no station lies in the GAP between them (the axis leaves the
    # apron there — the same per-segment discipline §2 gives the lattice)
    for e in entries:
        poly = e["shape"].polygon
        for (x, y) in e["points"]:
            assert poly.contains(Point(x, y))


# ═════════════════════════════════════════════════════════════════════
# A STATION IS A CENTERLINE NODE (§1.2)
# ═════════════════════════════════════════════════════════════════════

class _G:
    """The one graph, reduced to what the interpolation reads."""

    def __init__(self):
        self.pos = {}
        self.node_stage = {}
        self.centerline_chains = {}


class _CL:
    """``grade_graph._project``'s contract: ``.pts`` + ``.arc()``."""

    def __init__(self, pts):
        self.pts = [(float(x), float(y)) for (x, y) in pts]

    def arc(self):
        out = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            out.append(out[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        return out


class _Ctx:
    def __init__(self, centerlines):
        self.centerlines = list(centerlines)


def test_a_station_is_NEVER_registered_in_G_pos():
    """AMENDMENT 2 RULING 1.  A station in ``G.pos`` is a station
    ``_build_global_spine`` strings into its axis's chain — and a
    densified chain re-solves the profile, which is what moved the
    junctions.  The registration must not exist, and the next lane must
    not restore it."""
    import auto_patch.grade_graph as GG
    src = inspect.getsource(GG.build_unified_graph)
    assert "register_station_positions" not in src
    assert not hasattr(ST, "register_station_positions")
    assert "APRON SPINE STATIONS ARE NOT REGISTERED HERE" in src, \
        "the deliberate omission must be stated where a reader will look"
    assert "interpolate_station_values" in src, \
        "and it must name where the value does come from"


def _wire_profile(layout, chain_alts, *, ci=0,
                  axis=((-300.0, 0.0), (300.0, 0.0))):
    """A solved phase-A profile on one axis: chain nodes at the given
    (x, alt) pairs, in the graph's own ``centerline_chains``."""
    G = _G()
    ctx = _Ctx([_CL(axis)])
    b2i = {}
    elev = []

    def _add(x, y, alt):
        k = layout.canonical_points.get_or_add(x, y)
        if k not in b2i:
            b2i[k] = len(elev)
            elev.append(alt)
        return b2i[k]

    chain = []
    for (x, alt) in chain_alts:
        i = _add(x, 0.0, alt)
        G.pos[i] = (x, 0.0)
        chain.append(i)
    G.centerline_chains[ci] = chain
    for e in layout.apron_spine_presolve:
        for (x, y, _ci) in e["stations"]:
            _add(x, y, -999.0)          # a seed the profile must replace
    base_hard = [False] * len(elev)
    return G, ctx, b2i, elev, base_hard


def test_a_station_takes_the_LINEAR_INTERPOLANT_of_its_axis_profile(
        monkeypatch):
    """"the solved profile of its axis, interpolated at the station's
    arc position" — the value is arithmetic on the chain's own solved
    elevations, not a re-solve and not a DEM read."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    # profile: 100 m at arc 0 (x=-300), 200 m at arc 600 (x=+300)
    G, ctx, b2i, elev, base_hard = _wire_profile(
        layout, [(-300.0, 100.0), (300.0, 200.0)])
    rep = ST.interpolate_station_values(layout, G, ctx, b2i, elev,
                                        base_hard)
    assert rep["valued"] > 0 and rep["no_chain"] == 0
    for e in layout.apron_spine_presolve:
        for (x, y, _ci) in e["stations"]:
            i = b2i[layout.canonical_points.get_or_add(x, y)]
            want = 100.0 + 100.0 * ((x + 300.0) / 600.0)
            assert abs(elev[i] - want) < 1e-6, (x, elev[i], want)
            assert base_hard[i] is True


def test_the_profile_source_is_the_graphs_own_centerline_chains():
    """ONE source for "which nodes are on this axis": the arc-ordered
    list ``_build_global_spine`` authored while it strung the axis.
    Re-deriving it here is the census-wrapper defect in miniature."""
    src = inspect.getsource(ST.interpolate_station_values)
    assert "centerline_chains" in src
    assert "_project" in src


def test_a_station_past_the_strung_range_CLAMPS_and_says_so(monkeypatch):
    """Beyond the last strung node the profile has no data; the axis's
    own end value is the honest read, and it is counted as a clamp
    rather than dressed up as an interpolation."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    # the strung range covers only the far negative end
    G, ctx, b2i, elev, base_hard = _wire_profile(
        layout, [(-300.0, 100.0), (-250.0, 101.0)])
    rep = ST.interpolate_station_values(layout, G, ctx, b2i, elev,
                                        base_hard)
    assert rep["clamped"] == rep["valued"] > 0
    for e in layout.apron_spine_presolve:
        for (x, y, _ci) in e["stations"]:
            i = b2i[layout.canonical_points.get_or_add(x, y)]
            assert abs(elev[i] - 101.0) < 1e-9


def test_an_axis_that_contributed_no_string_leaves_its_stations_FREE(
        monkeypatch):
    """The void case this round exists for.  A station with no profile
    is COUNTED and left free — never stamped with a DEM seed dressed as
    a spine value."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    G, ctx, b2i, elev, base_hard = _wire_profile(
        layout, [(-300.0, 100.0)])          # one node: no string
    rep = ST.interpolate_station_values(layout, G, ctx, b2i, elev,
                                        base_hard)
    assert rep["valued"] == 0 and rep["no_chain"] > 0
    assert not any(base_hard)
    for e in layout.apron_spine_presolve:
        for (x, y, _ci) in e["stations"]:
            i = b2i[layout.canonical_points.get_or_add(x, y)]
            assert elev[i] == -999.0, "the seed is left exactly as it was"


def test_every_station_carries_the_axis_ORDINAL_it_was_minted_from(
        monkeypatch):
    """``ci`` is the position in ``centerline_specs`` — the ordinal
    ``ctx.centerlines`` and ``G.centerline_chains`` share, because all
    three walk that one enumeration in that one order.  Joining by
    proximity instead would pick the wrong axis wherever two cross."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    svc = _specs([(-300.0, 40.0), (300.0, 40.0)], service=True)
    air = _specs([(-300.0, 0.0), (300.0, 0.0)])
    _patch_specs(monkeypatch, svc + air)     # the aircraft axis is ci=1
    ST.construct_apron_spine_stations_presolve(layout)
    got = {ci for e in layout.apron_spine_presolve
           for (_x, _y, ci) in e["stations"]}
    assert got == {1}, got


def test_the_interpolation_is_WIRED_between_the_two_passes():
    """The slot IS the ruling: after the phase-A freeze, before the body
    solve.  Written later it would be a post-hoc rewrite of a settled
    surface, which Amendment 1 forbids by name."""
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    i_freeze = src.index("for i in frozen:")
    i_interp = src.index("interpolate_station_values")
    i_body = src.index("apron_smooth=True")
    assert i_freeze < i_interp < i_body


def test_stations_are_admitted_above_the_terrain_yield_boundary():
    """A station is pavement spine, not a free terrain leaf yielding to
    a host."""
    from auto_patch.elevation_per_surface import solver_primitives as SP
    src = inspect.getsource(SP._build_node_list)
    i_st = src.index("apron_spine_presolve")
    i_bound = src.index("_terrain_host_yield_first_index = len(nodes)")
    assert i_st < i_bound


def test_a_station_is_NOT_added_to_the_apron_interior_set():
    """``apron_body`` is the DEM-following interior the scaffold
    re-seats.  A station belongs to the SPINE — putting it there would
    hand the axis's own profile to the membrane's seeder."""
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    assert "apron_body = set(apron_body) | {i for i in _lattice_idx" in src
    assert "_station_idx" in src
    assert "apron_body) | {i for i in _station_idx" not in src


# ═════════════════════════════════════════════════════════════════════
# THE LAW IS THE APRON'S OWN (§1.3) AND THE LATTICE JOINS IT (§3.1)
# ═════════════════════════════════════════════════════════════════════

def test_the_edges_are_priced_through_the_shared_classify_pair():
    src = inspect.getsource(ST.build_apron_spine_station_constraints)
    assert "_grade_graph_edges" in src
    for forbidden in ("ROLE_GRADE_LIMITS", "APRON_MAX_GRADE", "0.015"):
        assert forbidden not in src, forbidden


def _wire(monkeypatch, layout, lattice_pts):
    """Give the constraint builder a synthetic law: every pair of the
    coords list, budget 1.0.  What is under test is the SELECTION."""
    from auto_patch.elevation_per_surface import solver_primitives as SP

    def _fake(s, coords, idx, ctx, ring_only=False):
        out = []
        for p in range(len(idx)):
            for q in range(p + 1, len(idx)):
                if idx[p] is None or idx[q] is None:
                    continue
                out.append((idx[p], idx[q], 1.0))
        return out

    monkeypatch.setattr(SP, "_grade_graph_edges", _fake)
    layout.apron_lattice_presolve = [
        {"shape": layout.shapes[0], "shapeID": 0,
         "points": list(lattice_pts), "lines": []}]
    b2i = {}

    def _idx_of(x, y):
        k = layout.canonical_points.get_or_add(x, y)
        if k not in b2i:
            b2i[k] = len(b2i)
        return b2i[k]

    for (x, y) in layout.shapes[0].polygon.exterior.coords:
        _idx_of(float(x), float(y))
    for (x, y) in lattice_pts:
        _idx_of(float(x), float(y))
    for e in layout.apron_spine_presolve:
        for (x, y) in e["points"]:
            _idx_of(float(x), float(y))
    return b2i


def test_only_station_touching_pairs_are_stated(monkeypatch):
    """The apron's ring pairs already have a within-shape entry and the
    lattice pairs have theirs; restating either hands the POCS sweep two
    copies of one law."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    lat = [(0.0, 40.0), (60.0, 40.0), (0.0, 190.0)]
    b2i = _wire(monkeypatch, layout, lat)
    st_idx_expected = ST.station_node_indices(layout, b2i)
    sc, st_idx, recs = ST.build_apron_spine_station_constraints(
        layout, b2i, None)
    assert st_idx == st_idx_expected and st_idx
    assert sc and recs
    for entry in sc:
        for (a, b, _bud) in entry["edges"]:
            assert (a in st_idx) != (b in st_idx), \
                "exactly one endpoint of every stated pair is a station"


def test_station_to_station_pairs_are_NEVER_stated(monkeypatch):
    """Consecutive stations lie on the axis and are governed by the
    SPINE's cap through ``G.spine_adj``.  An apron-cap copy would be a
    second authority over the taxiway profile — the very thing this
    round removes."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    b2i = _wire(monkeypatch, layout, [])
    sc, st_idx, _r = ST.build_apron_spine_station_constraints(
        layout, b2i, None)
    for entry in sc:
        for (a, b, _bud) in entry["edges"]:
            assert not (a in st_idx and b in st_idx)


def test_a_near_lattice_point_joins_the_station_and_a_far_one_does_not(
        monkeypatch):
    """§3.1 — the owner's "join seamlessly", with the radius the spec
    names: 1.5x ``APRON_LATTICE_SPACING_M``."""
    import auto_patch.config as cfg
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    st0 = layout.apron_spine_presolve[0]["points"][0]
    r = ST.LATTICE_JOIN_SPACING_MULT * cfg.APRON_LATTICE_SPACING_M
    near = (st0[0], st0[1] + r * 0.5)
    far = (st0[0], st0[1] + r * 1.5)
    b2i = _wire(monkeypatch, layout, [near, far])
    sc, st_idx, _r2 = ST.build_apron_spine_station_constraints(
        layout, b2i, None)
    i_near = b2i[layout.canonical_points.get_or_add(*near)]
    i_far = b2i[layout.canonical_points.get_or_add(*far)]
    stated = {(a, b) for e in sc for (a, b, _c) in e["edges"]}
    flat = {x for pair in stated for x in pair}
    assert i_near in flat, "a lattice point inside the join radius joins"
    assert i_far not in flat, "one beyond it keeps its own adjacency"


def test_the_records_extend_the_lattice_family_publication(monkeypatch):
    """ONE membrane, ONE family (RULINGS 2026-08-26b item 4).  A private
    second family would be the census-wrapper defect."""
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    b2i = _wire(monkeypatch, layout, [])
    _sc, _idx, recs = ST.build_apron_spine_station_constraints(
        layout, b2i, None)
    assert recs
    for rec in recs:
        assert set(rec) >= {"a", "b", "budget_m", "shapeID", "provenance"}
        assert rec["provenance"] == "apron_spine_station"
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    # the station records EXTEND the lattice publication, they do not
    # start a second sidecar key
    assert "+ _station_edges)" in src
    assert "_apron_station_edges_ll" not in src


# ═════════════════════════════════════════════════════════════════════
# THE FLAG
# ═════════════════════════════════════════════════════════════════════

def test_the_flag_defaults_on_and_off_mints_nothing(monkeypatch):
    import auto_patch.config as cfg
    assert cfg.APRON_SPINE_STATIONS is True
    os.environ["O4_APRON_SPINE_STATIONS"] = "0"
    try:
        importlib.reload(cfg)
        layout = _Layout([_Shape(_square(400.0))])
        _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
        assert ST.construct_apron_spine_stations_presolve(layout) == []
        assert layout.apron_spine_presolve == []
    finally:
        os.environ.pop("O4_APRON_SPINE_STATIONS", None)
        importlib.reload(cfg)


def test_flag_off_also_makes_the_constraint_leg_vacuous(monkeypatch):
    import auto_patch.config as cfg
    ap = _Shape(_square(400.0))
    layout = _Layout([ap])
    _patch_specs(monkeypatch, _specs([(-300.0, 0.0), (300.0, 0.0)]))
    ST.construct_apron_spine_stations_presolve(layout)
    assert layout.apron_spine_presolve
    os.environ["O4_APRON_SPINE_STATIONS"] = "0"
    try:
        importlib.reload(cfg)
        assert ST.build_apron_spine_station_constraints(
            layout, {}, None) == ([], set(), [])
    finally:
        os.environ.pop("O4_APRON_SPINE_STATIONS", None)
        importlib.reload(cfg)


# ═════════════════════════════════════════════════════════════════════
# EMISSION + CENSUS
# ═════════════════════════════════════════════════════════════════════

def _parse_with_features(path):
    import check_grade as CG
    feats: dict = {}
    nodes, ways = CG._parse_osm(Path(path), feature_out=feats)
    return nodes, ways, feats


def test_stations_emit_as_o4_feature_polylines(tmp_path):
    """The valued-node triple, the lattice/drainage-spine precedent.  A
    station that does not reach the patch is not an anchor."""
    from auto_patch.layout import PavementLayout
    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    layout.apron_spine_station_emit = [
        ([(30.1200, 31.4000), (30.1201, 31.4001),
          (30.1202, 31.4002)], [74.0, 74.2, 74.4])]
    patch = tmp_path / "TEST_auto.patch.osm"
    layout.to_osm(str(patch))
    _nodes, _ways, feats = _parse_with_features(patch)
    st_ways = feats.get("apron_spine_station", [])
    assert st_ways, "the station way must reach the OPEN-FEATURE route"
    assert any(len(w.nids) == 3 for w in st_ways)
    assert all(w.elevs and all(v is not None for v in w.elevs)
               for w in st_ways)


def test_the_station_class_is_registered_and_not_a_host_cap_class():
    """Without the registration the emitted polylines are dropped by the
    ring filter and every station edge becomes a LOST MEASUREMENT."""
    import check_grade as CG
    assert "apron_spine_station" in CG.ROLE_LESS_FEATURE_CLASSES
    assert "apron_spine_station" not in CG.HOST_CAP_FEATURE_CLASSES


def test_the_membrane_family_joins_station_ways_too(tmp_path):
    """The sidecar's ``apron_lattice_edges`` now carries station pairs;
    a lattice-only join population would report every one of them
    unmatched — a LOST measurement reported as a pass."""
    import check_grade as CG
    lat0, lon0 = ANCHOR
    dlon = 50.0 / (111320.0 * math.cos(math.radians(lat0)))
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    for i, (dl, alt) in enumerate(((0.0, 74.00), (dlon, 74.20),
                                   (2 * dlon, 74.40))):
        txt.append(f"  <node id='-{i + 1}' lat='{lat0:.9f}' "
                   f"lon='{lon0 + dl:.9f}'>\n"
                   f"    <tag k='alt_abs' v='{alt}'/>\n  </node>\n")
    txt.append("  <way id='-900'>\n    <nd ref='-1'/>\n    <nd ref='-2'/>\n"
               "    <nd ref='-3'/>\n"
               "    <tag k='o4_feature' v='apron_spine_station'/>\n"
               "  </way>\n</osm>\n")
    p = tmp_path / "st.osm"
    p.write_text("".join(txt))
    edges = [{"a": [lat0, lon0], "b": [lat0, lon0 + dlon],
              "budget_m": 0.10, "shapeID": 3,
              "provenance": "apron_spine_station"}]
    (tmp_path / "st.osm.axes.json").write_text(json.dumps(
        {"anchor": list(ANCHOR), "ruleset": "icao",
         "apron_lattice_edges": edges}))
    nodes, ways, feats = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    join = (list(feats.get("apron_lattice", []))
            + list(feats.get("apron_spine_station", [])))
    rows, n_checked, n_unmatched = CG._check_apron_lattice_membrane(
        edges, join, ways, nodes, to_m)
    assert (n_checked, n_unmatched) == (1, 0)
    assert len(rows) == 1 and abs(rows[0].de_m - 0.20) < 1e-6
    # and the lattice-only population would have LOST it
    _r2, _c2, u2 = CG._check_apron_lattice_membrane(
        edges, list(feats.get("apron_lattice", [])), [], nodes, to_m)
    assert u2 == 1


# ═════════════════════════════════════════════════════════════════════
# THE §2 DISCIPLINE APPLIED TO THE SPINE'S OWN RUN
# ═════════════════════════════════════════════════════════════════════

def test_a_station_chord_that_cuts_a_corner_is_dropped(monkeypatch):
    """Stations sit at ARC positions on a POLYLINE axis, so the straight
    chord between two of them chords off a bend — measured on this
    round's second HECA arm as 2 of 40 segments leaving the apron
    (22.6 m of it through junction -10165).  Same law as the lattice's
    (owner item 1), one implementation."""
    from shapely.geometry import LineString
    # An L-shaped apron whose two arms hold the axis; the axis turns the
    # corner inside the apron, but the chord across the turn does not.
    poly = Polygon([(0, 0), (400, 0), (400, 60), (60, 60), (60, 400),
                    (0, 400), (0, 0)])
    axis = [(20.0, 350.0), (20.0, 20.0), (350.0, 20.0)]
    layout = _Layout([_Shape(poly)])
    _patch_specs(monkeypatch, _specs(axis))
    entries = ST.construct_apron_spine_stations_presolve(layout)
    assert entries, "the crossing must exist at all"
    for e in entries:
        for run in e["lines"]:
            for a, b in zip(run, run[1:]):
                assert poly.contains(LineString([a, b])), (a, b)
        in_lines = {p for run in e["lines"] for p in run}
        assert set(e["points"]) <= in_lines, \
            "a station in no surviving run would never be emitted"


def test_the_clip_is_the_lattice_implementation_not_a_second_copy():
    src = inspect.getsource(ST._clip)
    assert "clip_lines_to_apron" in src


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 1 RULING 1 — A STATION IS A CONSTANT IN THE MEMBRANE SOLVE
#
# The station's value is PHASE-A OUTPUT (the route profile's own solve,
# where it is a legitimate collinear interior chain point — not a
# mid-taxiway external pin).  In the membrane/POCS solve it must not be
# a free variable: a station-touching law edge is then satisfiable ONLY
# by moving the ring/lattice side.  Measured on the arm that did not do
# this: the projection lowered the ANCHORED side instead — line-T ring
# 74.02 → 73.43, dip-site junctions down 0.22 m, lattice unmoved.
# ═════════════════════════════════════════════════════════════════════

def test_a_station_is_preserved_from_the_spine_yield():
    """``hard -= _spine_yield_idx`` releases the phase-A spine into the
    final projection.  A station must not be in that set, or it is free
    again and the anchored side becomes the cheap way out."""
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    frozen = {1, 2, 3, 4}
    preserved, yield_idx = SV._spine_yield_membership(
        frozen, 10, truth_hard=set(), runway_nodes=set(),
        building_seats={}, runway_anchor=None, seam_pins=set(),
        station_nodes={3})
    assert 3 in preserved and 3 not in yield_idx
    assert yield_idx == {1, 2, 4}, yield_idx


def test_without_stations_the_membership_is_byte_identical():
    """Flag OFF, or no apron crossing: the split is the pre-round one."""
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    args = dict(truth_hard={1}, runway_nodes=set(), building_seats={},
                runway_anchor=None, seam_pins=set())
    a = SV._spine_yield_membership({1, 2, 3}, 10, **args)
    b = SV._spine_yield_membership({1, 2, 3}, 10, station_nodes=None,
                                   **args)
    c = SV._spine_yield_membership({1, 2, 3}, 10, station_nodes=set(),
                                   **args)
    assert a == b == c


def test_the_preservation_is_WIRED_at_the_call_site():
    """RULING 2026-08-21d was found UNIMPLEMENTED in production because
    its context field was never populated — the ruling existed and the
    wire did not.  This twin fails on the unwired state."""
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    assert "station_nodes=_station_idx" in src
    i_call = src.index("station_nodes=_station_idx")
    i_idx = src.index("_station_idx, _station_edges = _build_st_scs")
    assert i_idx < i_call, "the station set must exist before the split"
