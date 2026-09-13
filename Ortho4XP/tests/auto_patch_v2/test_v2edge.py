"""THE TERRAIN EDGE — lane ``v2edge``'s twins (owner RULINGS 2026-09-10b /
2026-09-10c; spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §19.4).

CYXY: the 14R/32L end corridor — a LAW surface with no DEM term — held
705.1 m for 176 m off the runway end, 29 m past the rim road and out over
the lip of a natural plateau, and the bank behind it fell 19 m in 5.6 m.
The owner ruled the EXTENT ends at the physical edge: a rim road running
along the crest (flush at the road's OUTER edge, the road keeping its own
profile) or, with no road, the crest itself.  Beyond it: no patch, no
bank, the DEM.

The four twins of §19.4 are the four grounds an adjacent-ground region can
sit on: level, a plateau, a plateau with a rim road, and a gentle slope.

ONE READING RECORDED (§19.2 (1) as written): the crest test is a FORWARD
probe — a station is CREST when the DEM drops more than ``bank_slope``
over the ``edge_probe_m`` AHEAD of it — so the first crest station stands
up to one probe INBOARD of the lip itself, and a crest-cut region ends
there.  The road rule (which the CYXY site takes) is exact: the road
REPLACES the crest it runs along and the region ends at the road's own
outer edge.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m
from auto_patch_v2.planar.terrain_edge import EdgeReport, road_lines
from auto_patch_v2.planar.zones import zone_regions

#: The pavement: a runway body whose zone 2 reaches ``x = +75`` (code 4).
PAV = ((-400.0, -500.0), (0.0, -500.0), (0.0, 500.0), (-400.0, 500.0))
#: Where the fixture's plateau lip stands.
LIP = 50.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _Dem:
    """Level at 700 m, falling by ``drop`` m over ``run`` m past the lip."""

    provenance = {"synthetic": "plateau"}

    def __init__(self, drop: float = 0.0, run: float = 15.0, lip: float = LIP):
        self.drop, self.run, self.lip = drop, run, lip

    def z(self, x: float, y: float) -> float:
        t = min(1.0, max(0.0, (x - self.lip) / self.run))
        return 700.0 - self.drop * t

    def z_many(self, xs, ys):
        import numpy as np
        t = np.clip((np.asarray(xs, float) - self.lip) / self.run, 0.0, 1.0)
        return 700.0 - self.drop * t

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _cells():
    return (Cell(0, "runway", "09/27", PAV, (), 4, None, "airside", "runway", {}),)


def _regions(law, dem=None, roads=(), rep=None):
    return zone_regions(_cells(), law, (), dem, roads, rep)


def _outer(regions) -> float:
    """How far out (+x) the adjacent ground reaches."""
    return max(r.polygon.bounds[2] for r in regions)


def test_flat_dem_is_byte_identical(law):
    """A region over level ground has no edge: the polygons are the ones a
    build without this law derives, coordinate for coordinate."""
    base = _regions(law)
    rep = EdgeReport()
    over = _regions(law, _Dem(drop=0.0), (), rep)
    assert [r.ref for r in base] == [r.ref for r in over]
    for a, b in zip(base, over):
        assert a.polygon.wkt == b.polygon.wkt
        assert b.edge_kind == "none" and b.edge_lines == ()
    assert (rep.trimmed_crest, rep.trimmed_road, rep.emptied) == (0, 0, 0)


def test_gentle_slope_is_untouched(law):
    """20 % is shallower than the 1:3 bank: the bank can follow it, so it
    is not an edge and nothing is trimmed (§19.2 (1))."""
    base = _regions(law)
    rep = EdgeReport()
    over = _regions(law, _Dem(drop=3.0, run=15.0), (), rep)
    assert _outer(over) == pytest.approx(_outer(base), abs=1e-9)
    assert rep.trimmed_crest == 0 and rep.area_cut_m2 == 0.0
    assert all(r.edge_kind == "none" for r in over)


def test_plateau_ends_at_the_crest(law):
    """20 m over 15 m (133 %) past ``x = 50``: the region ends at the crest
    — never beyond the lip, and within one forward probe of it."""
    d = law.tables.emit.design
    base = _regions(law)
    assert _outer(base) == pytest.approx(75.0, abs=0.01)   # zone 2, code 4
    rep = EdgeReport()
    over = _regions(law, _Dem(drop=20.0), (), rep)
    out = _outer(over)
    assert out <= LIP + d.edge_grid_m
    assert out >= LIP - d.edge_probe_m - d.edge_grid_m
    assert rep.trimmed_crest >= 1 and rep.trimmed_road == 0
    assert rep.area_cut_m2 > 0.0 and rep.edge_length_m > 0.0
    cut = [r for r in over if r.edge_kind != "none"]
    assert cut and all(r.edge_kind == "crest" for r in cut)
    assert all(r.edge_lines for r in cut)


def test_rim_road_ends_the_region_at_its_outer_edge(law):
    """The same plateau with a road at ``x = 92 − 50 = 42`` running along
    the crest: the region ends AT THE ROAD, NOT at the crest — the road
    keeps its own profile beyond it (§19.2 (2)).

    AMENDED by spec §34 (4) (Fable 2026-09-13i, lane ``v2rampwalk``): the
    road's own RIBBON is now subtracted at the zone derivation site
    WHETHER OR NOT the classifier gave it a cell, so the region ends at
    the road's INNER edge (its half-width plus the groundside cut-back
    the band already stands off every road) rather than its outer one.
    §19.2 (2)'s "flush at the OUTER edge" was written for a road that has
    a CELL — in that case the cell ⊕ cut-back is subtracted anyway and the
    outer edge only says "nothing beyond".  A cell-less road (LEMD −6289)
    read literally left the band holding its designed level right over the
    road's own ground: 1.73 m over 1.5 m, priced by no family.  Both
    barriers still stand, so nothing survives beyond the road either."""
    half = (law.tables.emit.road_profile.lane_width_m
            + law.tables.zones.adjacent_ground.groundside_cutback_m)
    road = LineString([(42.0, -600.0), (42.0, 600.0)])
    rep = EdgeReport()
    over = _regions(law, _Dem(drop=20.0), (road,), rep)
    assert rep.roads_governing >= 1 and rep.trimmed_road >= 1
    assert _outer(over) == pytest.approx(42.0 - half, abs=law.tables.emit
                                         .road_profile.lane_width_m)
    cut = [r for r in over if r.edge_kind != "none"]
    assert cut and all(r.edge_kind == "road" for r in cut)


def test_a_short_road_does_not_govern(law):
    """A road stub shorter than ``edge_road_run_m`` is not a rim road: the
    crest is still the edge."""
    road = LineString([(42.0, -10.0), (42.0, 10.0)])         # 20 m < 30 m
    rep = EdgeReport()
    over = _regions(law, _Dem(drop=20.0), (road,), rep)
    assert rep.roads_governing == 0
    assert _outer(over) <= LIP + law.tables.emit.design.edge_grid_m


def test_road_lines_reads_only_highways(law):
    class _W:
        def __init__(self, tags, pts):
            self.tags, self.points = tags, pts
    ways = (_W({"highway": "track"}, ((0.0, 0.0), (10.0, 0.0))),
            _W({"building": "yes"}, ((0.0, 5.0), (10.0, 5.0))),
            _W({"highway": "track"}, ((0.0, 9.0),)))
    lines = road_lines(ways)
    assert len(lines) == 1 and lines[0].length == pytest.approx(10.0)


def _edge_fixture(law):
    """A coverage whose east side IS a terrain edge, and the cut it makes."""
    from auto_patch_v2.emit.terrain_edge import no_bank_region
    from auto_patch_v2.model.planar import PlanarMap

    edge = ((50.0, -400.0), (50.0, 400.0))
    pm = PlanarMap("ZZZZ", {}, {}, {}, {}, terrain_edges=(edge,))
    cov = Polygon(((-400.0, -500.0), (50.0, -500.0), (50.0, 500.0),
                   (-400.0, 500.0)))
    return cov, no_bank_region(pm, law, cov)


def test_no_bank_beyond_the_edge(law):
    """§19 (3): the ground beyond an edge segment is cut OUT of the banked
    region — the DEM's own slope is the bank there, exactly as the water
    line is cut in §18.  What survives is the MINIMUM-WIDTH COLLAR the law
    gives every ring and nothing more: the 200 m daylight reach that built
    CYXY's plateau wall is gone."""
    from shapely.geometry import Point

    min_w = float(law.tables.emit.design.bank_min_width_m)
    cov, geom = _edge_fixture(law)
    assert geom is not None and not geom.is_empty
    assert geom.contains(Point(50.0 + min_w + 10.0, 0.0))   # beyond: no bank
    assert not geom.intersects(cov.buffer(-1.0))            # never inside
    banked = cov.buffer(law.tables.emit.design.bank_max_width_m)
    across = banked.difference(geom).intersection(
        LineString([(-500.0, 0.0), (500.0, 0.0)]))
    assert across.bounds[2] == pytest.approx(50.0 + min_w, abs=0.01)


def test_the_cut_never_reaches_the_design_ring(law):
    """THE FOLD TWIN (owner RULINGS 2026-09-10g).

    Round 1 cut the slab back to the coverage itself, so the banked
    region's boundary came to rest ON the design ring for the whole edge
    run.  ``bank._push_off`` then pushed the vertices merely NEAR the
    coverage out to ``bank_min_width_m`` and left the vertices exactly ON
    it alone, and the foot ring emitted from that run crossed the strip's
    own ring — a zero-area needle Triangle4XP filled to its recursion
    limit (CYXY: 59,634 vertices on 216 plan positions in one 50 m cell,
    18.4 M overlapping pairs).  The cut must therefore never come within
    the push-off's own threshold of the coverage."""
    min_w = float(law.tables.emit.design.bank_min_width_m)
    cov, geom = _edge_fixture(law)
    assert geom.distance(cov) >= 0.5 * min_w
    assert geom.distance(cov) == pytest.approx(min_w, abs=0.05)
    # and the boundary the bank is emitted from is a clean simple ring
    banked = cov.buffer(min_w).difference(geom)
    assert banked.is_valid and banked.exterior.is_simple
    assert banked.exterior.distance(cov.exterior) == pytest.approx(
        0.0, abs=min_w + 0.05)


def test_edge_ways_reuse_existing_vertices(law):
    """§19.3 C12: the edge is published as an OPEN way over the boundary
    vertices it already runs through — no new node, no new geometry."""
    import dataclasses as _dc
    from auto_patch_v2.emit.terrain_edge import EDGE_KIND, with_terrain_edges
    from auto_patch_v2.emit.surface import GradedSurface, SurfaceVertex
    from auto_patch_v2.model.planar import PlanarMap, Vertex

    xs = [(50.0, y) for y in (-20.0, 0.0, 20.0)] + [(10.0, 0.0)]
    verts = {i: Vertex(i, p, (60.0 + i * 1e-7, -135.0), 700.0, ())
             for i, p in enumerate(xs)}
    pm = PlanarMap("ZZZZ", verts, {}, {}, {},
                   terrain_edges=(((50.0, -20.0), (50.0, 20.0)),))
    surf = GradedSurface("ZZZZ", law.ruleset_key, (60.0, -135.0), "EPSG:3857",
                         11, tuple(SurfaceVertex(i, verts[i].key, 700.0)
                                   for i in verts), (), (), {})
    out = with_terrain_edges(surf, pm, law)
    bl = [b for b in out.breaklines if b.kind == EDGE_KIND]
    assert len(bl) == 1
    assert bl[0].vertices == (0, 1, 2)       # ordered along the edge, no #3
    assert len(out.vertices) == len(surf.vertices)
    assert snap_margin_m(law) > 0.0
    assert _dc.is_dataclass(bl[0])
