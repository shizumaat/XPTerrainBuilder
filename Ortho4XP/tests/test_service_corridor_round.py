"""SERVICE-CORRIDOR ROUND — the twins.

Spec: ``docs/specs/service-corridor-round-spec.md``, implementing the owner
rulings of 2026-08-12b (``docs/RULINGS.md``): service roads ENABLED AND
BUILT; apt.dat truck routes are an authoritative corridor source and ONE
corridor = ONE continuous law object end-to-end; a road's own course is
never terraced (free ends grade to DEM under the road cap, and no wall may
cut across a corridor's course); the road-width classification read is
corridor-aware.

Each class below is one ruling, stated as the measured defect it closes:

1. SOURCES — the minter runs (gate default ON, env kill switch recorded in
   the gate provenance) and the two sources DEDUPE at centerline level, so
   one physical corridor is never minted (and never spined) twice.
2. MINTING — pavement is minted only where NONE exists: an existing apron /
   ribbon is never double-paved.
3. ONE LAW OBJECT PER CORRIDOR — a corridor course registers as ONE chain
   whose axis coverage has no axis-free gap, and it REPLACES the free-road
   scoped pieces it covers rather than duplicating them (the HECA
   four-disjoint-axes state is the named defect).  The sidecar mirror agrees
   by construction because both readers walk ``centerline_specs``.
4. FREE-END LAW — a corridor end over open terrain reaches DEM at the road
   cap, and the groundside terrace-wall emitter may not emit a wall across a
   corridor's course (the ruled KCLT lot-road wall).
5. CLASSIFICATION — a contiguous widening (a lot entrance) never vetoes a
   road ribbon: the corridor-width part still reads as a corridor.
6. ONE GRADE NUMBER — ``config.SERVICE_ROAD_MAX_GRADE`` and no second
   spelling anywhere in the road path.

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters: ``auto_patch.junction_repair`` ↔ ``elevation`` is a
# cycle that only resolves when the package is entered through the pipeline
# (auto_patch/CLAUDE.md, "Import cycle").
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch import grade_graph as GG                      # noqa: E402
from auto_patch.canonical_points import (                     # noqa: E402
    CanonicalPointRegistry)
from auto_patch.layout import BuiltShape                      # noqa: E402
from auto_patch.pavement.service_roads import (                # noqa: E402
    build_service_road_network, dedupe_service_sources)
from auto_patch.verification import taxi_axes_exact_ll        # noqa: E402


def _rect(x0, y0, x1, y1) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


# ══════════════════════════════════════════════════════════════════════
# 1 — SOURCES: the gate, the kill switch, the centerline-level dedupe
# ══════════════════════════════════════════════════════════════════════

class TestSources:
    def test_the_minter_is_on_by_default(self):
        """Owner 2026-08-12b: service roads are ENABLED AND BUILT."""
        assert CFG.ENABLE_SERVICE_ROADS is True

    def test_the_kill_switch_is_an_o4_gate_in_the_provenance(self):
        """The switch must be readable off a shipped patch, so it has to be
        an ``O4_`` env gate the config introspection can see — a bare
        module constant would be invisible."""
        from auto_patch import provenance
        gates = provenance.introspect_config_gates()
        assert "O4_ENABLE_SERVICE_ROADS" in gates
        assert gates["O4_ENABLE_SERVICE_ROADS"]["default"] == "1"
        assert "O4_ENABLE_SERVICE_ROADS" in provenance.gate_provenance()["on"]

    def test_an_osm_respelling_of_a_1206_route_is_suppressed(self):
        """Ruling 1: the 1206 spelling wins.  The OSM line runs 1 m beside
        the truck route over its whole length — one physical corridor."""
        apt = [(LineString([(0.0, 0.0), (100.0, 0.0)]), "N")]
        osm = [(LineString([(0.0, 1.0), (100.0, 1.0)]), "dup"),
               (LineString([(0.0, 40.0), (100.0, 40.0)]), "own-road")]
        kept, dropped = dedupe_service_sources(
            apt, osm, width=CFG.SERVICE_ROAD_WIDTH_M, min_frac=0.5)
        assert dropped == 1
        assert [n for (_ln, n) in kept] == ["own-road"]

    def test_a_road_that_only_touches_a_1206_route_survives(self):
        """Complement, not duplicate: a side road crossing the corridor
        shares only a few metres of its own length and must be kept."""
        apt = [(LineString([(0.0, 0.0), (100.0, 0.0)]), "N")]
        osm = [(LineString([(50.0, -60.0), (50.0, 60.0)]), "side")]
        kept, dropped = dedupe_service_sources(
            apt, osm, width=CFG.SERVICE_ROAD_WIDTH_M, min_frac=0.5)
        assert dropped == 0 and len(kept) == 1

    def test_dedupe_preserves_entry_identity(self):
        """The caller's entries travel through unchanged — names/refs are
        the caller's, never re-minted here."""
        apt = [(LineString([(0.0, 0.0), (100.0, 0.0)]), "N")]
        entry = (LineString([(0.0, 40.0), (100.0, 40.0)]), "own-road")
        kept, _ = dedupe_service_sources(apt, [entry],
                                         width=CFG.SERVICE_ROAD_WIDTH_M)
        assert kept[0] is entry

    def test_no_apt_source_means_no_suppression(self):
        """Absence of the authoritative source is never evidence."""
        osm = [(LineString([(0.0, 0.0), (100.0, 0.0)]), "only")]
        kept, dropped = dedupe_service_sources([], osm, width=6.0)
        assert dropped == 0 and kept == osm


# ══════════════════════════════════════════════════════════════════════
# 2 — MINTING: rects + junction fill, pavement-clear
# ══════════════════════════════════════════════════════════════════════

class TestMinter:
    def test_a_free_route_mints_a_rect_of_the_corridor_width(self):
        rects, _junctions = build_service_road_network(
            [(LineString([(0.0, 0.0), (200.0, 0.0)]), "N")], None,
            width=6.0, min_len=25.0)
        assert len(rects) == 1
        poly, axis, role, name = rects[0]
        assert role == "service_road" and name == "N"
        minx, miny, maxx, maxy = poly.bounds
        assert (maxy - miny) == pytest.approx(6.0, abs=1e-6)
        assert axis.length == pytest.approx(maxx - minx, abs=1e-6)

    def test_a_bend_becomes_junction_fill_between_two_rects(self):
        rects, junctions = build_service_road_network(
            [(LineString([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]), "N")],
            None, width=6.0, min_len=25.0)
        assert len(rects) == 2
        assert junctions and all(j[1] == "service_junction"
                                 for j in junctions)

    def test_existing_pavement_is_never_double_paved(self):
        """Ruling 2: minted ONLY where no pavement exists.  The route runs
        the full length of an apron and only its free tail may mint."""
        apron = _rect(0.0, -30.0, 100.0, 30.0)
        rects, junctions = build_service_road_network(
            [(LineString([(0.0, 0.0), (200.0, 0.0)]), "N")], apron,
            width=6.0, min_len=25.0)
        for poly, _axis, _role, _name in rects:
            assert poly.intersection(apron).area == pytest.approx(0.0,
                                                                  abs=1e-6)
        for poly, _role, _name in junctions:
            assert poly.intersection(apron).area == pytest.approx(0.0,
                                                                  abs=1e-6)
        assert rects, "the free tail beyond the apron must still mint"


# ══════════════════════════════════════════════════════════════════════
# 3 — ONE LAW OBJECT PER CORRIDOR
# ══════════════════════════════════════════════════════════════════════

# A corridor 600 m long with a branch grafting at s=300 (the "3-branch"
# shape: trunk in, trunk out, branch).  Free-road scoping cut the trunk
# into two pieces with an axis-free gap between s=100 and s=400 — the HECA
# corridor-A state, in miniature.
CORRIDOR_PTS = [(0.0, 0.0), (300.0, 0.0), (600.0, 0.0)]
SCOPED_A = [(0.0, 0.0), (100.0, 0.0)]
SCOPED_B = [(400.0, 0.0), (600.0, 0.0)]
BRANCH = [(300.0, 0.0), (300.0, 120.0)]


class _FakeCenterline:
    def __init__(self, pts, is_service=False, seg_sizes=None):
        self.line = LineString(pts)
        self.route_line = None
        self.is_service = is_service
        self.name = "N" if is_service else "T"
        self.seg_sizes = (list(seg_sizes) if seg_sizes is not None
                          else [""] * (len(pts) - 1))


class _SpecLayout:
    def __init__(self, *, corridors=None, sliced=None):
        self.icao = "TEST"
        self.shapes = []
        self.anchor = (0.0, 0.0)
        self.canonical_points = None
        self.apt_taxi_centerlines = [_FakeCenterline([(0.0, -500.0),
                                                      (0.0, 500.0)],
                                                     seg_sizes=["C"])]
        if sliced is not None:
            self._slice_service_subsegments = [LineString(p) for p in sliced]
        if corridors is not None:
            self._service_corridor_lines = [LineString(p) for p in corridors]

    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


def _service_specs(layout):
    return [s for s in GG.centerline_specs(layout) if s[2]]


def _axis_gaps(pts_list, corridor_pts):
    """Arc intervals of ``corridor_pts`` covered by NO registered axis."""
    course = LineString(corridor_pts)
    covered = []
    for pts in pts_list:
        line = LineString(pts)
        inter = line.intersection(course.buffer(1.0))
        for piece in ([inter] if inter.geom_type == "LineString"
                      else list(getattr(inter, "geoms", ()))):
            if piece.is_empty or piece.geom_type != "LineString":
                continue
            ss = sorted(course.project(Point(c)) for c in
                        (piece.coords[0], piece.coords[-1]))
            covered.append(tuple(ss))
    covered.sort()
    gaps, cursor = [], 0.0
    for (a, b) in covered:
        if a > cursor + 1e-6:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < course.length - 1e-6:
        gaps.append((cursor, course.length))
    return gaps


class TestCorridorChains:
    def test_the_scoped_pieces_alone_leave_axis_free_gaps(self):
        """The measured defect, reproduced: without the corridor course,
        the law's own axis set has a hole in the middle of the road."""
        layout = _SpecLayout(sliced=[SCOPED_A, SCOPED_B])
        specs = _service_specs(layout)
        gaps = _axis_gaps([s[0] for s in specs], CORRIDOR_PTS)
        assert gaps, "fixture must reproduce the axis-free gap"
        assert any(b - a > 100.0 for (a, b) in gaps)

    def test_one_chain_per_corridor_closes_every_gap(self):
        layout = _SpecLayout(corridors=[CORRIDOR_PTS, BRANCH],
                             sliced=[SCOPED_A, SCOPED_B])
        specs = _service_specs(layout)
        trunk = [s for s in specs
                 if LineString(s[0]).length == pytest.approx(600.0)]
        assert len(trunk) == 1, "the corridor is ONE law object"
        assert _axis_gaps([trunk[0][0]], CORRIDOR_PTS) == []

    def test_the_chain_replaces_its_scoped_pieces_never_duplicates(self):
        """Ruling 6 / the cycle-9 invariant: one physical road, one spine.
        The scoped pieces lie inside the corridor, so they must not also
        register."""
        layout = _SpecLayout(corridors=[CORRIDOR_PTS],
                             sliced=[SCOPED_A, SCOPED_B])
        lengths = sorted(LineString(s[0]).length
                         for s in _service_specs(layout))
        assert lengths == [pytest.approx(600.0)]

    def test_a_scoped_piece_no_corridor_covers_is_never_dropped(self):
        """Coverage, not deletion: a road the corridor set does not know
        about keeps its own registration."""
        stray = [(0.0, 300.0), (200.0, 300.0)]
        layout = _SpecLayout(corridors=[CORRIDOR_PTS],
                             sliced=[SCOPED_A, stray])
        lengths = sorted(round(LineString(s[0]).length, 3)
                         for s in _service_specs(layout))
        assert lengths == [200.0, 600.0]

    def test_a_branch_grafts_and_the_trunk_continues(self):
        """Rod-degree≥3 splitting stays a TAXIWAY rule: a minor service
        branch does not cut the corridor's own through-run."""
        layout = _SpecLayout(corridors=[CORRIDOR_PTS, BRANCH])
        specs = _service_specs(layout)
        assert sorted(round(LineString(s[0]).length, 3)
                      for s in specs) == [120.0, 600.0]

    def test_every_corridor_segment_carries_the_road_cap(self):
        layout = _SpecLayout(corridors=[CORRIDOR_PTS])
        (_pts, caps, _svc, _rkey, _rpts) = _service_specs(layout)[0]
        assert caps == [CFG.SERVICE_ROAD_MAX_GRADE] * 2

    def test_the_corridor_is_its_own_route_chain(self):
        """One law object ⇒ one route key for the whole course, so the
        solver's spine-arc frame does not reset at the joints."""
        layout = _SpecLayout(corridors=[CORRIDOR_PTS])
        (_pts, _caps, _svc, rkey, rpts) = _service_specs(layout)[0]
        assert rkey[0] == "corridor"
        assert rpts == CORRIDOR_PTS

    def test_the_frame_stamp_names_the_corridor_source(self):
        """Instrument truth: every reported number carries its frame."""
        assert GG.service_spine_source(
            _SpecLayout(corridors=[CORRIDOR_PTS])) == "corridor"
        assert GG.service_spine_source(
            _SpecLayout(sliced=[SCOPED_A])) == "sliced"
        assert GG.service_spine_source(_SpecLayout()) == "apt1206"

    def test_the_sidecar_mirror_carries_the_same_chain(self):
        """Both law readers walk ``centerline_specs``, so the census
        cannot judge a patch under a spine the build never graded to."""
        layout = _SpecLayout(corridors=[CORRIDOR_PTS],
                             sliced=[SCOPED_A, SCOPED_B])
        svc_axes = [a for a in taxi_axes_exact_ll(layout)[0] if a[3]]
        assert len(svc_axes) == 1
        assert len(svc_axes[0][0]) == len(CORRIDOR_PTS)
        assert svc_axes[0][1] == [CFG.SERVICE_ROAD_MAX_GRADE] * 2

    def test_the_gate_off_restores_the_per_piece_registration(self, monkeypatch):
        monkeypatch.setattr(CFG, "SERVICE_CORRIDOR_CHAINS", False)
        layout = _SpecLayout(corridors=[CORRIDOR_PTS],
                             sliced=[SCOPED_A, SCOPED_B])
        assert sorted(round(LineString(s[0]).length, 3)
                      for s in _service_specs(layout)) == [100.0, 200.0]


# ══════════════════════════════════════════════════════════════════════
# 4 — FREE-END LAW: DEM tie, and no wall across a road's course
# ══════════════════════════════════════════════════════════════════════

class _WallLayout:
    def __init__(self, shapes, corridors=()):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = [LineString(c) for c in corridors]


class _DemLayout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []


def _free_end_fixture(dem_far: float, anchor: float = 100.0):
    """A 100 m road welded to an apron at x=0 and running out to a FREE
    end at x=100 over terrain at ``dem_far``."""
    xs = [0.0, 25.0, 50.0, 75.0, 100.0]
    ring = [(x, 0.0) for x in xs] + [(x, 6.0) for x in reversed(xs)]
    road = BuiltShape(polygon=Polygon(ring), role="service_road")
    road.lateral_cap = None
    apron = BuiltShape(polygon=_rect(-20.0, 0.0, 0.0, 6.0), role="apron")
    layout = _DemLayout([road, apron])
    bucket_to_idx, nodes = {}, []
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in bucket_to_idx:
                bucket_to_idx[key] = len(nodes)
                nodes.append((x, y))
    elev = [0.0] * len(nodes)
    dem = [dem_far] * len(nodes)
    for (x, y) in ((0.0, 0.0), (0.0, 6.0)):
        elev[bucket_to_idx[layout.canonical_points.get_or_add(x, y)]] = anchor
    far = bucket_to_idx[layout.canonical_points.get_or_add(100.0, 0.0)]
    return layout, bucket_to_idx, elev, dem, far


class TestFreeEnd:
    def test_a_free_end_reaches_dem_when_the_cap_allows_it(self):
        """Ruling 4: the end ties to AMBIENT DEM, not to the pavement it
        left.  DEM 96 m is 4 m below the weld over 100 m — inside the 8 %
        cap, so the road arrives exactly at terrain."""
        from auto_patch.elevation_per_surface.route_profile import anchors
        layout, b2i, elev, dem, far = _free_end_fixture(96.0)
        anchors.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        assert elev[far] == pytest.approx(96.0, abs=1e-6)

    def test_the_descent_never_exceeds_the_road_cap(self):
        """DEM 0 m is unreachable in 100 m; the profile takes the whole cap
        and no more — a cliff would be the defect."""
        from auto_patch.elevation_per_surface.route_profile import anchors
        layout, b2i, elev, dem, far = _free_end_fixture(0.0)
        anchors.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        assert elev[far] == pytest.approx(
            100.0 - CFG.SERVICE_ROAD_MAX_GRADE * 100.0, abs=1e-6)

    def test_no_wall_may_cross_a_corridors_course(self):
        """The ruled KCLT lot-road wall (-12269 at 35.2077303,-80.9290869)
        dies by construction: the keep-out covers the corridor course."""
        from auto_patch import adjacent_ground as AG
        lot = BuiltShape(polygon=_rect(0.0, 0.0, 100.0, 100.0),
                         role="groundside_pavement")
        layout = _WallLayout([lot], corridors=[[(50.0, -20.0),
                                                (50.0, 120.0)]])
        keepout = AG.service_corridor_wall_keepout(layout)
        assert keepout is not None
        wall_across = Polygon([(40.0, 45.0), (60.0, 45.0),
                               (60.0, 47.0), (40.0, 47.0)])
        wall_beside = Polygon([(5.0, 45.0), (25.0, 45.0),
                               (25.0, 47.0), (5.0, 47.0)])
        assert wall_across.intersects(keepout)
        assert not wall_beside.intersects(keepout)

    def test_the_emitted_road_axes_are_part_of_the_course(self):
        """A corridor exists in the patch as a stashed course, as minted
        rects, or as both — the keep-out reads a minted rect's own AXIS."""
        from auto_patch import adjacent_ground as AG
        road = BuiltShape(polygon=_rect(40.0, 0.0, 46.0, 100.0),
                          role="service_road",
                          source_axis=LineString([(43.0, 0.0),
                                                  (43.0, 100.0)]))
        keepout = AG.service_corridor_wall_keepout(_WallLayout([road]))
        assert keepout is not None
        assert keepout.intersects(_rect(35.0, 40.0, 55.0, 42.0))   # across
        assert not keepout.intersects(_rect(20.0, 40.0, 39.0, 42.0))

    def test_a_kerbside_terrace_beside_the_road_is_lawful(self):
        """The ruling forbids a wall CUTTING ACROSS the run — not the
        ordinary terrace standing alongside it.  A kerbside wall 2 m from
        the carriageway is inside a road-POLYGON keep-out and outside this
        one; refusing it would leave its lot carrying the level change."""
        from auto_patch import adjacent_ground as AG
        road = BuiltShape(polygon=_rect(40.0, 0.0, 46.0, 100.0),
                          role="service_road",
                          source_axis=LineString([(43.0, 0.0),
                                                  (43.0, 100.0)]))
        keepout = AG.service_corridor_wall_keepout(_WallLayout([road]))
        kerb = _rect(46.0, 10.0, 48.0, 90.0)          # along the far edge
        assert not kerb.intersects(keepout)

    def test_the_gate_off_removes_the_keepout(self, monkeypatch):
        from auto_patch import adjacent_ground as AG
        monkeypatch.setattr(CFG, "SERVICE_CORRIDOR_FREE_END", False)
        layout = _WallLayout([], corridors=[[(0.0, 0.0), (100.0, 0.0)]])
        assert AG.service_corridor_wall_keepout(layout) is None

    def test_a_layout_with_no_corridor_keeps_walls_unchanged(self):
        from auto_patch import adjacent_ground as AG
        assert AG.service_corridor_wall_keepout(_WallLayout([])) is None


# ══════════════════════════════════════════════════════════════════════
# 5 — CLASSIFICATION: a widening never vetoes the ribbon
# ══════════════════════════════════════════════════════════════════════

def _ribbon_with_entrance(widening_m: float = 40.0) -> Polygon:
    """The KCLT lot-road fixture: a 263 m ribbon of ~11.6 m mean width with
    ONE contiguous widening at the lot entrance (way -11671; the measured
    ``buffer(-12.5)`` blobs are what denied the whole shape)."""
    ribbon = _rect(0.0, 0.0, 263.0, 11.6)
    blob = _rect(60.0, -(widening_m - 11.6) / 2.0,
                 60.0 + widening_m, 11.6 + (widening_m - 11.6) / 2.0)
    return ribbon.union(blob)


def _road_corridor_feature(polygon) -> float:
    """The production feature vector's own ``road_corridor`` gate.

    A FRESH layout per call — ``evidence_sources`` / ``score_sources``
    memoise on the layout object."""
    from auto_patch import pavement_scoring as PS
    from auto_patch.layout import PavementLayout
    layout = PavementLayout(icao="TEST", anchor=(35.2, -80.94))
    layout.shapes = []
    return PS.shape_features(polygon, layout).get("road_corridor", 0.0)


class TestCorridorAwareWidthRead:
    def test_the_whole_shape_erosion_denies_the_ribbon(self):
        """The measured defect: ONE widening vetoes 263 m of road."""
        from auto_patch.pavement_classification import _is_tail
        assert not _is_tail(_ribbon_with_entrance(),
                            0.5 * CFG.PAVEMENT_CLASS_TAIL_MAX_WIDTH_M)

    def test_the_corridor_width_part_still_reads_as_a_corridor(self):
        assert _road_corridor_feature(_ribbon_with_entrance()) == 1.0

    def test_a_plain_ribbon_is_unaffected(self):
        assert _road_corridor_feature(_rect(0.0, 0.0, 263.0, 11.6)) == 1.0

    def test_a_lot_is_still_not_a_road(self):
        """The read must not turn a parking lot into a corridor: a shape
        that is mostly widening keeps its groundside class."""
        assert _road_corridor_feature(_rect(0.0, 0.0, 120.0, 90.0)) == 0.0

    def test_a_driveway_stub_does_not_make_a_lot_a_road(self):
        lot = _rect(0.0, 0.0, 90.0, 90.0)
        stub = _rect(90.0, 40.0, 130.0, 46.0)
        assert _road_corridor_feature(lot.union(stub)) == 0.0

    def test_the_gate_off_restores_the_whole_shape_erosion(self, monkeypatch):
        from auto_patch import pavement_scoring as PS
        monkeypatch.setattr(PS, "SCORER_CORRIDOR_WIDTH", False)
        assert _road_corridor_feature(_ribbon_with_entrance()) == 0.0

    def test_the_service_adjacency_feature_is_live(self):
        """Ruling 5: the RULINGS:128 corollary goes live."""
        assert CFG.SCORER_SERVICE_ADJ is True


# ══════════════════════════════════════════════════════════════════════
# 6 — ONE GRADE NUMBER
# ══════════════════════════════════════════════════════════════════════

_ROAD_PATH_SOURCES = (
    "src/auto_patch/pavement/service_roads.py",
    "src/auto_patch/grade_graph.py",
)


class TestOneGradeNumber:
    def test_the_role_table_reads_the_constant(self):
        assert (CFG.ROLE_GRADE_LIMITS["service_road"]
                == CFG.SERVICE_ROAD_MAX_GRADE)
        assert (CFG.ROLE_GRADE_LIMITS["service_junction"]
                == CFG.SERVICE_ROAD_MAX_GRADE)
        assert (CFG.GROUNDSIDE_PAVEMENT_MAX_GRADE
                == CFG.SERVICE_ROAD_MAX_GRADE)

    @pytest.mark.parametrize("rel", _ROAD_PATH_SOURCES)
    def test_no_second_grade_number_is_spelled_in_the_road_path(self, rel):
        """The stale "4 %" (service_roads) and "5 %" (grade_graph) copies
        outlived the constant they claimed to quote — 8 % has been the road
        number since 2026-08-03.  A percentage next to a service-road word
        is the defect this asserts against."""
        text = (ROOT / rel).read_text(encoding="utf-8")
        offenders = [
            line.strip() for line in text.splitlines()
            if re.search(r"\b\d+(\.\d+)?\s*%", line)
            and re.search(r"service[_ ]road|service[_ ]junction|truck route",
                          line, re.I)
        ]
        assert offenders == []


# ══════════════════════════════════════════════════════════════════════
# 7 — FINALARCH items 4/5: stage-aware anchors and the fallback
#     neighbour term (S1f dossier item 5; RULINGS 2026-08-14)
# ══════════════════════════════════════════════════════════════════════

class TestStageAwareAnchors:
    def test_a_groundside_authority_conforms_to_the_stage_a_envelope(self):
        """Item 5: the two reach regimes ran over one stage-blind anchor
        set, so an airside weld and a groundside weld whose values are
        incompatible under the cap metric met inside the tube as
        ``floor > ceil`` — a recorded inverted-tube conflict that could
        not be partitioned.  Stage B now reads the stage-A envelope as
        IMMUTABLE: the contradiction is RECORDED and its propagation
        conforms, so the interior takes a lawful band instead of a
        break blend."""
        from auto_patch.elevation_per_surface.route_profile import anchors
        layout, b2i, elev, dem, far = _free_end_fixture(96.0)
        # The far end is a GROUNDSIDE-welded authority 100 m from a
        # 100 m airside weld, at a value the 8 % cap metric cannot
        # reconcile (200 vs 100+8).
        elev[far] = 200.0
        anchors.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE,
            anchor_extra=(far,))
        recs = getattr(layout, "_svc_cross_stage_conform", None)
        assert recs, "the cross-stage contradiction was not recorded"
        assert any(r["value"] == 200.0 for r in recs)
        # The conformed propagation: no interior node quarantined as a
        # break blend by the A-vs-B contradiction.
        interior = [i for i, (x, y) in enumerate(
            (p for s in layout.shapes if s.role == "service_road"
             for p in list(s.polygon.exterior.coords)[:-1]))
            ]
        assert not getattr(layout, "_service_break_idx", set()), (
            "the cross-stage contradiction still rendered a break blend")
        # The anchor's own held value is untouched (the mint stays
        # visible to the census; only the propagation conforms).
        assert elev[far] == 200.0

    def test_all_airside_anchors_stay_byte_identical(self):
        """With no stage-B authority the composition is the identity —
        the free-end law's own numbers reproduce exactly."""
        from auto_patch.elevation_per_surface.route_profile import anchors
        layout, b2i, elev, dem, far = _free_end_fixture(96.0)
        anchors.apply_service_road_dem_follow(
            layout, b2i, elev, dem, CFG.SERVICE_ROAD_MAX_GRADE)
        assert elev[far] == pytest.approx(96.0, abs=1e-6)


class TestFallbackNeighbourTerm:
    def test_dem_noise_between_fallback_nodes_is_capped(self):
        """Item 4: the per-vertex fallback is ``min(max(de, lo), c)`` —
        a band clamp with NO neighbour term.  The band floor/ceiling are
        each cap-Lipschitz, but a WIDE band lets one node clamp to its
        CEILING and its neighbour to its FLOOR: far from the anchors the
        pair ships at whatever grade the band width allows (here 128 %
        against the 8 % cap).  The Lipschitz envelope over the
        ``e_cap·d`` metric (the metric ``_reach`` already prices; no new
        constant) bounds every adjacent pair at the cap."""
        import math as _m
        from auto_patch.elevation_per_surface.route_profile import anchors
        cap = CFG.SERVICE_ROAD_MAX_GRADE
        xs = [0.0, 50.0, 100.0, 110.0, 150.0, 200.0]
        ring = [(x, 0.0) for x in xs] + [(x, 6.0) for x in reversed(xs)]
        road = BuiltShape(polygon=Polygon(ring), role="service_road")
        road.lateral_cap = None
        apron = BuiltShape(polygon=_rect(-20.0, 0.0, 0.0, 6.0),
                           role="apron")
        layout = _DemLayout([road, apron])
        b2i, nodes = {}, []
        for s in layout.shapes:
            for (x, y) in list(s.polygon.exterior.coords)[:-1]:
                key = layout.canonical_points.get_or_add(float(x), float(y))
                if key not in b2i:
                    b2i[key] = len(nodes)
                    nodes.append((x, y))
        cps = layout.canonical_points
        elev = [0.0] * len(nodes)
        dem = [96.0] * len(nodes)
        for (x, y) in ((0.0, 0.0), (0.0, 6.0)):
            elev[b2i[cps.get_or_add(x, y)]] = 100.0
        # Terrain noise 100 m from the weld: a crest against a pit, ten
        # metres apart — the crest clamps to its ceiling, the pit to its
        # floor, both bands satisfied, the PAIR at ~128 %.
        for y in (0.0, 6.0):
            dem[b2i[cps.get_or_add(100.0, y)]] = 110.0
            dem[b2i[cps.get_or_add(110.0, y)]] = 90.0
        anchors.apply_service_road_dem_follow(layout, b2i, elev, dem, cap)
        ring_open = list(road.polygon.exterior.coords)[:-1]
        idx = [b2i[cps.get_or_add(x, y)] for (x, y) in ring_open]
        for k in range(len(ring_open)):
            j = (k + 1) % len(ring_open)
            d = _m.hypot(ring_open[j][0] - ring_open[k][0],
                         ring_open[j][1] - ring_open[k][1])
            if d < 1e-6:
                continue
            g = abs(elev[idx[j]] - elev[idx[k]]) / d
            assert g <= cap + 1e-6, (
                f"fallback pair {ring_open[k]}–{ring_open[j]} ships "
                f"{g:.3%} against the {cap:.1%} cap — no neighbour term")
