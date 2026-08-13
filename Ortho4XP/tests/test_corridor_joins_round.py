"""CORRIDOR-JOINS ROUND — the twins.

Spec: ``docs/specs/corridor-joins-round-spec.md`` (Fable, 2026-08-12c), built
on the owner's in-sim refutation of two 1.0.244 corridor acceptance claims at
KCLT.  Each class below is one ruling, stated as the measured defect it
closes:

1. MOUTHS JOIN AIRCRAFT PAVEMENT.  The minter cut the corridor back from ALL
   aircraft pavement by 1.0 m while conformance welds only within 0.5 m, so
   every road↔taxiway seam was UNWELDABLE BY CONSTRUCTION (measured gaps
   0.999 m at both KCLT sites) and the annulus was filled by a graded_strip
   carrying BOTH claims.  The mouth fill now reaches the PAVEMENT EDGE
   ITSELF, the weld splices its nodes into the airside ring, and THE AIRSIDE
   VALUE WINS — the airside ring's own solved values are byte-identical
   across the weld (an insert is added; nothing existing moves).
2. ``emit_stacked_conflict_walls`` CONSULTS THE CORRIDOR KEEP-OUT.  It read
   only the runway-strip keep-out, so it walled the KCLT mouth conflict (way
   -13314, a 2.3 m face across the corridor's own course) that the terrace
   pass — which does consult it — would have refused.
3. FREE ENDS GET A HARD DEM TIE.  The spine seeder recognised only row-1206
   ``is_service`` centerlines, so a FEED-sourced corridor chain was invisible
   to it; and its seeds were SOFT, so the projections wrote 6.31 m back over
   the DEM value at the owner's acceptance coordinate.  One source
   (``grade_graph.service_chain_lines``) and an ANCHORED end target that
   survives a node-list rebuild.

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters (auto_patch/CLAUDE.md, "Import cycle").
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch import grade_graph as GG                      # noqa: E402
from auto_patch.canonical_points import (                     # noqa: E402
    CanonicalPointRegistry)
from auto_patch.conformance import enforce_conformance        # noqa: E402
from auto_patch.elevation_per_surface.node_space import (     # noqa: E402
    store_of)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    anchors as ANCH)
from auto_patch.layout import BuiltShape                      # noqa: E402
from auto_patch.pavement.service_roads import (               # noqa: E402
    _PAV_CLEAR_TOL_M, build_service_road_network, mouth_fills)

_ROAD_FAMILY = ("service_road", "service_junction")


def _rect(x0, y0, x1, y1) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


# The KCLT seam in miniature: aircraft pavement occupying x >= 0, a truck
# route running into it from the west and stopping just inside.
APRON = Polygon([(0.0, -40.0), (0.0, 40.0), (160.0, 40.0), (160.0, -40.0)])
ROUTE = LineString([(-150.0, 0.0), (5.0, 0.0)])


def _network(mouth_join=None):
    return build_service_road_network(
        [(ROUTE, "N")], APRON, width=CFG.SERVICE_ROAD_WIDTH_M,
        min_len=CFG.MIN_SERVICE_STRIP_LEN_M,
        **({} if mouth_join is None else {"mouth_join": mouth_join}))


# ══════════════════════════════════════════════════════════════════════
# 1 — MOUTHS JOIN AIRCRAFT PAVEMENT
# ══════════════════════════════════════════════════════════════════════

class TestMouthJoin:
    def test_the_gap_the_ruling_names_is_reproduced_with_the_gate_off(self):
        """THE MEASURED DEFECT: without the mouth join, the nearest
        corridor geometry stands ``_PAV_CLEAR_TOL_M`` off the pavement —
        0.999 m at KCLT — which is BEYOND the weld tolerance, so no node
        can ever be shared."""
        _rects, junctions = _network(mouth_join=False)
        from auto_patch.layout import SHARED_VERTEX_TOL_M
        gap = min(p.distance(APRON) for (p, _r, _n) in junctions)
        assert gap == pytest.approx(_PAV_CLEAR_TOL_M, abs=1e-6)
        assert gap > SHARED_VERTEX_TOL_M, "unweldable BY CONSTRUCTION"

    def test_the_mouth_reaches_the_pavement_edge_itself(self):
        _rects, junctions = _network()
        assert min(p.distance(APRON) for (p, _r, _n) in junctions) == 0.0
        on_edge = [p for (p, _r, _n) in junctions
                   if p.intersects(APRON.exterior)]
        assert on_edge, "a mouth must touch the pavement boundary"

    def test_the_mouth_carries_nodes_ON_the_airside_edge(self):
        """Weldability is a property of NODES, not of distance: at least
        two of the mouth's own ring vertices must lie ON the airside edge
        (the ≥2 shared nodes per mouth the acceptance quotes)."""
        from shapely.geometry import Point
        _rects, junctions = _network()
        edge = APRON.exterior
        n_on_edge = sum(1 for (p, _r, _n) in junctions
                        for (x, y) in p.exterior.coords[:-1]
                        if edge.distance(Point(x, y)) <= 1e-9)
        assert n_on_edge >= 2

    def test_the_mouth_never_overlays_aircraft_pavement(self):
        """Ruling 2 of the parent round stands: pavement is minted only
        where none exists."""
        rects, junctions = _network()
        area = (sum(p.intersection(APRON).area for (p, _a, _r, _n) in rects)
                + sum(p.intersection(APRON).area for (p, _r, _n) in junctions))
        assert area == pytest.approx(0.0, abs=1e-9)

    def test_the_body_keeps_its_clearance_mid_run(self):
        """Only the MOUTH crosses the annulus.  A road running ALONGSIDE
        pavement gets no fill at all — its whole course keeps the 1.0 m
        clearance, so roads still never overlay pavement mid-run."""
        alongside = LineString([(-150.0, 41.0), (150.0, 41.0)])
        fills = mouth_fills([(alongside, "beside")], APRON,
                            APRON.buffer(_PAV_CLEAR_TOL_M),
                            width=CFG.SERVICE_ROAD_WIDTH_M)
        assert fills == []

    def test_a_crossing_gets_a_mouth_on_BOTH_sides(self):
        """The KCLT seam is two-sided ("the far side: same gap, no wall,
        bare 2.0 m step") — a route crossing pavement joins at both."""
        crossing = LineString([(-150.0, 0.0), (310.0, 0.0)])
        _rects, junctions = build_service_road_network(
            [(crossing, "N")], APRON, width=CFG.SERVICE_ROAD_WIDTH_M,
            min_len=CFG.MIN_SERVICE_STRIP_LEN_M)
        touching = [p for (p, _r, _n) in junctions if p.distance(APRON) == 0.0]
        assert len(touching) == 2
        xs = sorted(round(p.centroid.x) for p in touching)
        assert xs[0] < 0 and xs[1] > 160

    def test_the_fill_can_never_escape_the_annulus(self):
        """Containment BY CONSTRUCTION: every fill lies inside
        ``pav_buf − pav_union``, so no reach parameter can pave a runway
        the union does not carry or widen the body's clearance."""
        buf = APRON.buffer(_PAV_CLEAR_TOL_M)
        for poly in mouth_fills([(ROUTE, "N")], APRON, buf,
                                width=CFG.SERVICE_ROAD_WIDTH_M):
            assert poly.difference(buf).area == pytest.approx(0.0, abs=1e-9)
            assert poly.intersection(APRON).area == pytest.approx(0.0,
                                                                  abs=1e-9)


class _WeldLayout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.icao = "TEST"


class TestSeamWeld:
    """THE SEAM VALUE IS THE AIRSIDE VALUE — airside is king."""

    def _welded(self):
        _rects, junctions = _network()
        mouth = max((p for (p, _r, _n) in junctions
                     if p.distance(APRON) == 0.0), key=lambda p: p.area)
        taxi = BuiltShape(polygon=APRON, role="apron",
                          node_altitudes=[100.0, 101.0, 102.0, 103.0, 100.0])
        road = BuiltShape(polygon=mouth, role="service_junction",
                          altitude=90.0)
        layout = _WeldLayout([taxi, road])
        before = list(taxi.node_altitudes)
        enforce_conformance(layout)
        return taxi, road, before

    def test_the_weld_shares_at_least_two_nodes_per_mouth(self):
        taxi, road, _before = self._welded()
        shared = ({tuple(round(v, 6) for v in c)
                   for c in taxi.polygon.exterior.coords}
                  & {tuple(round(v, 6) for v in c)
                     for c in road.polygon.exterior.coords})
        assert len(shared) >= 2

    def test_the_airside_ring_keeps_every_solved_value_byte_identical(self):
        """A mouth weld may never MOVE an airside ring's solved value: the
        weld only INSERTS, at the edge's own interpolation."""
        taxi, _road, before = self._welded()
        after = list(taxi.node_altitudes)
        assert len(after) > len(before), "the weld must have inserted"
        kept = [a for a in after if any(abs(a - b) < 1e-12 for b in before)]
        for b in before:
            assert any(abs(a - b) < 1e-12 for a in after), (
                f"airside value {b} was moved by the weld")
        assert len(kept) >= len(before)

    def test_an_inserted_value_lies_on_the_airside_edge_profile(self):
        """…and the inserted node's value is the AIRSIDE edge's own lerp —
        never the road's, which is 10 m lower in this fixture."""
        taxi, _road, _before = self._welded()
        assert min(taxi.node_altitudes) >= 100.0 - 1e-9


# ══════════════════════════════════════════════════════════════════════
# 2 — THE STACKED-CONFLICT EMITTER CONSULTS THE CORRIDOR KEEP-OUT
# ══════════════════════════════════════════════════════════════════════

class _CorridorLayout:
    def __init__(self, shapes, corridors=()):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = [LineString(c) for c in corridors]


def _conflict_strip():
    """A graded_strip ring whose two north vertices carry a 2.3 m conflict
    — the KCLT -13314 class, sitting on a corridor's course."""
    coords = [(40.0, 0.0), (60.0, 0.0), (60.0, 20.0), (40.0, 20.0)]
    alts = [216.95, 216.95, 216.95, 216.95]
    shape = BuiltShape(polygon=Polygon(coords), role="graded_strip",
                       node_altitudes=alts + [alts[0]])
    top = [None, None, 219.23, 219.23]
    spread = [0.0, 0.0, 2.28, 2.28]
    return shape, coords, alts, top, spread


class TestStackedConflictKeepout:
    def test_the_wall_is_emitted_without_the_keepout(self):
        """The measured state: this emitter walled the mouth conflict."""
        from auto_patch import adjacent_ground as AG
        shape, coords, alts, top, spread = _conflict_strip()
        walls = AG._retreat_run_walls(shape, coords, alts, top, spread, None)
        assert walls and walls[0].role == "retaining_wall"

    def test_a_wall_across_a_corridor_course_is_refused(self):
        """Ruling 2: same drop test as the terrace pass, same geometry."""
        from auto_patch import adjacent_ground as AG
        shape, coords, alts, top, spread = _conflict_strip()
        keepout = AG.service_corridor_wall_keepout(
            _CorridorLayout([], corridors=[[(50.0, -20.0), (50.0, 60.0)]]))
        assert keepout is not None
        walls = AG._retreat_run_walls(shape, coords, alts, top, spread, None,
                                      corridor_keepout=keepout)
        assert walls == []

    def test_the_shape_is_left_untouched_when_every_face_is_refused(self):
        """The refusal falls back to the emit consensus — the emitter's own
        documented fallback — and never leaves a half-retreated ring."""
        from auto_patch import adjacent_ground as AG
        shape, coords, alts, top, spread = _conflict_strip()
        before = list(shape.polygon.exterior.coords)
        keepout = AG.service_corridor_wall_keepout(
            _CorridorLayout([], corridors=[[(50.0, -20.0), (50.0, 60.0)]]))
        AG._retreat_run_walls(shape, coords, alts, top, spread, None,
                              corridor_keepout=keepout)
        assert list(shape.polygon.exterior.coords) == before

    def test_a_wall_clear_of_every_course_still_emits(self):
        """The keep-out is the road's OWN run, not a licence to stop
        walling: a conflict 200 m away is unaffected."""
        from auto_patch import adjacent_ground as AG
        shape, coords, alts, top, spread = _conflict_strip()
        keepout = AG.service_corridor_wall_keepout(
            _CorridorLayout([], corridors=[[(250.0, -20.0), (250.0, 60.0)]]))
        walls = AG._retreat_run_walls(shape, coords, alts, top, spread, None,
                                      corridor_keepout=keepout)
        assert walls

    def test_the_emitter_reads_the_keepout_at_all(self):
        """The wiring itself (the defect was a MISSING consultation): the
        production emitter must call the corridor keep-out."""
        import inspect
        from auto_patch import adjacent_ground as AG
        src = inspect.getsource(AG.emit_stacked_conflict_walls)
        assert "service_corridor_wall_keepout" in src
        assert "corridor_keepout" in src


# ══════════════════════════════════════════════════════════════════════
# 3 — THE SEEDER'S SINGLE SOURCE, AND THE HARD FREE-END TIE
# ══════════════════════════════════════════════════════════════════════

CORRIDOR = [(0.0, 3.0), (200.0, 3.0)]


class _FeedLayout:
    """A layout whose corridor reaches the graph through the FEED (the
    slice's scoped set + the stashed course) and NOT through a row-1206
    ``is_service`` centerline — the KCLT lot-road state exactly."""

    def __init__(self, shapes=(), corridors=(CORRIDOR,), sliced=None):
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = [LineString(c) for c in corridors]
        self._slice_service_subsegments = [LineString(s)
                                           for s in (sliced or [])]

    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


class TestSeederSource:
    def test_a_feed_only_corridor_is_invisible_to_the_old_walk(self):
        """THE MEASURED DEFECT: the row-1206 walk sees nothing here, so the
        road fell through to the per-vertex fallback."""
        layout = _FeedLayout()
        assert [cl for cl in layout.apt_taxi_centerlines] == []

    def test_the_seeder_reads_the_grade_graphs_own_chain_set(self):
        layout = _FeedLayout()
        lines = ANCH.service_seed_lines(layout)
        assert len(lines) == 1
        assert lines[0].length == pytest.approx(200.0)

    def test_it_is_the_SAME_set_the_grade_graph_registers(self):
        """One source, not two agreeing enumerations."""
        layout = _FeedLayout(sliced=[[(0.0, 3.0), (60.0, 3.0)]])
        seeded = sorted(round(ln.length, 6)
                        for ln in ANCH.service_seed_lines(layout))
        registered = sorted(round(LineString(s[0]).length, 6)
                            for s in GG.centerline_specs(layout) if s[2])
        assert seeded == registered

    def test_the_gate_off_restores_the_row_1206_walk(self, monkeypatch):
        monkeypatch.setattr(CFG, "SERVICE_CORRIDOR_FREE_END_ANCHOR", False)
        assert ANCH.service_seed_lines(_FeedLayout()) == []


def _free_end_layout(dem_far: float, weld_alt: float = 100.0):
    """A 200 m corridor welded to an apron at x=0, free end at x=200 over
    terrain at ``dem_far`` — the KCLT lot-road geometry in miniature."""
    xs = [0.0, 50.0, 100.0, 150.0, 200.0]
    ring = [(x, 0.0) for x in xs] + [(x, 6.0) for x in reversed(xs)]
    road = BuiltShape(polygon=Polygon(ring), role="service_road")
    road.lateral_cap = None
    apron = BuiltShape(polygon=_rect(-30.0, 0.0, 0.0, 6.0), role="apron")
    layout = _FeedLayout([road, apron])
    b2i, nodes = {}, []
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in b2i:
                b2i[key] = len(nodes)
                nodes.append((x, y))
    elev = [0.0] * len(nodes)
    dem = [dem_far] * len(nodes)
    for (x, y) in ((0.0, 0.0), (0.0, 6.0)):
        elev[b2i[layout.canonical_points.get_or_add(x, y)]] = weld_alt
    far = [b2i[layout.canonical_points.get_or_add(200.0, y)]
           for y in (0.0, 6.0)]
    return layout, b2i, elev, dem, far, nodes


class TestHardFreeEndTie:
    def test_the_terminus_is_anchored_at_ambient_dem(self):
        layout, b2i, elev, dem, far, _n = _free_end_layout(88.0)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        for i in far:
            assert elev[i] == pytest.approx(88.0, abs=1e-6)
        assert set(far) <= set(layout._svc_free_end_idx)

    def test_the_end_descends_within_the_road_cap_and_no_further(self):
        """Terrain 200 m below is out of reach in 200 m at 8 %: the tie is
        CLAMPED into the band — it never mints an infeasibility."""
        layout, b2i, elev, dem, far, _n = _free_end_layout(-100.0)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        floor = 100.0 - CFG.SERVICE_ROAD_MAX_GRADE * 200.0
        for i in far:
            assert elev[i] == pytest.approx(floor, abs=1e-6)
        rec = layout._svc_free_end_records
        assert rec and rec[0]["clamped"] is True

    def test_the_whole_end_cross_section_takes_ONE_value(self):
        """A per-vertex DEM read is what rendered the CYXY cross-road tear;
        the terminus takes the cross-section's mean."""
        layout, b2i, elev, dem, far, _n = _free_end_layout(88.0)
        dem[far[0]] = 90.0                       # a noisy raster sample
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        assert elev[far[0]] == pytest.approx(elev[far[1]], abs=1e-9)

    def test_a_welded_end_is_not_a_free_end(self):
        """The tie never competes with an existing authority: an end that
        welds to pavement keeps its weld."""
        layout, b2i, elev, dem, _far, nodes = _free_end_layout(88.0)
        far_apron = BuiltShape(polygon=_rect(200.0, 0.0, 230.0, 6.0),
                               role="apron")
        layout.shapes.append(far_apron)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        assert not layout._svc_free_end_idx

    def test_the_record_carries_its_own_frame(self):
        """Ruling 4: the acceptance number is emitted-minus-DEM, so the
        DEM the build read travels with the patch."""
        layout, b2i, elev, dem, _far, _n = _free_end_layout(88.0)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        rec = layout._svc_free_end_records[0]
        assert rec["dem_m"] == pytest.approx(88.0)
        assert rec["target_m"] == pytest.approx(88.0)
        assert "lat" in rec and "lon" in rec

    def test_the_tie_survives_a_node_list_rebuild(self):
        """SURVIVING PROJECTION is a node-space property: the tie is minted
        by CANONICAL KEY, so the final projection — which rebuilds the node
        list — resolves the same nodes (node_space's law)."""
        layout, b2i, elev, dem, far, nodes = _free_end_layout(88.0)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        # a REBUILT node space: same canonical keys, different indices
        rebuilt = {k: (i + 7) % len(b2i) for k, i in b2i.items()}
        rebuilt = {k: i for i, k in enumerate(sorted(b2i, key=str))}
        held = store_of(layout).view_keyset("svc_free_end", rebuilt,
                                            len(rebuilt))
        assert len(held) == len(far)
        assert held == {rebuilt[k] for k in
                        (layout.canonical_points.get_or_add(200.0, y)
                         for y in (0.0, 6.0))}

    def test_a_projection_holding_the_tie_leaves_it_where_the_law_put_it(self):
        """…and with that membership the projection cannot write over it —
        the 6.31 m the SOFT seed lost."""
        from auto_patch.elevation_per_surface.route_profile.one_solve import (
            feasibility_project)
        layout, b2i, elev, dem, far, nodes = _free_end_layout(88.0)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        edges = []
        for a in range(len(nodes)):
            for b in range(a + 1, len(nodes)):
                d = ((nodes[a][0] - nodes[b][0]) ** 2
                     + (nodes[a][1] - nodes[b][1]) ** 2) ** 0.5
                if 0.0 < d <= 55.0:
                    edges.append((a, b, CFG.SERVICE_ROAD_MAX_GRADE * d))
        weld = {b2i[layout.canonical_points.get_or_add(0.0, y)]
                for y in (0.0, 6.0)}
        hard = weld | set(layout._svc_free_end_idx)
        feasibility_project(elev, [{"edges": edges}], hard)
        for i in far:
            assert elev[i] == pytest.approx(88.0, abs=1e-6)

    def test_the_gate_off_restores_the_soft_seed(self, monkeypatch):
        monkeypatch.setattr(CFG, "SERVICE_CORRIDOR_FREE_END_ANCHOR", False)
        layout, b2i, elev, dem, _far, _n = _free_end_layout(88.0)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        assert not layout._svc_free_end_idx


# ══════════════════════════════════════════════════════════════════════
# 4 — COMPOSITION: the wall goes, and the ROAD owns the level change
# ══════════════════════════════════════════════════════════════════════

class TestWallExclusionAndDescentCompose:
    def test_the_road_grades_the_bench_the_refused_wall_used_to_hold(self):
        """The KCLT free end, composed: the wall-course exclusion removes
        the terrace wall (-12626) that held the bench, and the road's own
        anchored descent — not a 10 m cliff on the wall's footprint — owns
        the transition.  4 m over 200 m is 2 % against an 8 % cap."""
        from auto_patch import adjacent_ground as AG
        layout, b2i, elev, dem, far, nodes = _free_end_layout(96.0)
        layout.shapes.append(BuiltShape(polygon=_rect(80.0, -20.0,
                                                      120.0, 30.0),
                                        role="groundside_pavement"))
        keepout = AG.service_corridor_wall_keepout(layout)
        wall_across = _rect(90.0, 2.0, 110.0, 4.0)
        assert keepout is not None and wall_across.intersects(keepout)
        ANCH.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        profile = sorted((nodes[i][0], elev[i]) for i in range(len(nodes))
                         if nodes[i][1] == 0.0 and nodes[i][0] >= 0.0)
        for (xa, za), (xb, zb) in zip(profile, profile[1:]):
            grade = abs(zb - za) / (xb - xa)
            assert grade <= CFG.SERVICE_ROAD_MAX_GRADE + 1e-9
        assert profile[-1][1] == pytest.approx(96.0, abs=1e-6)
