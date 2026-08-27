"""THE APRON INTERIOR LATTICE — twins for §1b of
docs/specs/heca-apron-round2-spec.md (Amendment 1; legs pinned to their
precedents by Amendment 2).

§1's route-synthesis premise was REFUTED at HECA by measurement: apt.dat
nodes 462/470 are CONNECTED (560.6 m network path against 252.7 m
straight, a 2.2x detour) and neither is a leaf.  The routes go AROUND
the apron, so there is no feed gap — but the VOID is real: 10 nodeless
interiors, worst 175.4 m empty radius, and 247 m of the owner's cliff
line with no emitted station at all, dropping 6.06 m at ZERO census
rows.  That ground needs ANCHORS, not invented taxi geometry.

These twins pin the four legs:
  * the TRIGGER is the §2 measurement itself (one implementation);
  * the GEOMETRY is deterministic from the shape's own frame, clipped,
    and held off the ring so no lattice point interns into a ring bucket;
  * the LAW is the apron's own — edges priced through
    ``_grade_graph_edges``/``classify_pair``, never a private cap;
  * the CENSUS family prices the emitted membrane against the budget the
    SOLVE published, and an unmatched edge is a LOST MEASUREMENT.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import importlib
import json
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import apron_lattice as AL                # noqa: E402
from auto_patch.nodeless_interior import (                # noqa: E402
    largest_nodeless_disk)

ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron", ref=""):
        self.polygon = polygon
        self.role = role
        self.ref = ref
        self.fan_ramp_zone = False
        self.lateral_cap = None


def _square(side):
    h = side / 2.0
    return Polygon([(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)])


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.anchor = ANCHOR

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


# ═════════════════════════════════════════════════════════════════════
# GEOMETRY: deterministic, clipped, off the ring
# ═════════════════════════════════════════════════════════════════════

def test_a_300m_apron_gains_a_lattice_at_the_declared_spacing():
    pts = AL.lattice_points(_square(300.0), 50.0)
    assert pts, "a 300 m apron must carry lattice points"
    xs = sorted({round(x, 3) for (_i, _j, x, _y) in pts})
    gaps = {round(b - a, 3) for a, b in zip(xs, xs[1:])}
    assert gaps == {50.0}, gaps


def test_every_lattice_point_is_inside_and_clear_of_the_ring():
    """A point inside the registry tolerance of a ring vertex would
    INTERN into it and silently become a ring variable."""
    poly = _square(300.0)
    for (_i, _j, x, y) in AL.lattice_points(poly, 50.0):
        from shapely.geometry import Point
        p = Point(x, y)
        assert poly.contains(p)
        assert poly.exterior.distance(p) >= AL.LATTICE_RING_MARGIN_M - 1e-6


def test_the_lattice_is_deterministic_from_the_shapes_own_frame():
    """A function of the polygon alone: no build order, no global grid
    phase, no dependence on which apron was processed first."""
    a = AL.lattice_points(_square(300.0), 50.0)
    b = AL.lattice_points(_square(300.0), 50.0)
    assert a == b
    # and the same polygon described from a different starting vertex
    # gives the same POINT SET
    rot = Polygon([(150.0, -150.0), (150.0, 150.0), (-150.0, 150.0),
                   (-150.0, -150.0), (150.0, -150.0)])
    got = {(round(x, 3), round(y, 3)) for (_i, _j, x, y)
           in AL.lattice_points(rot, 50.0)}
    want = {(round(x, 3), round(y, 3)) for (_i, _j, x, y) in a}
    assert got == want


def test_a_concave_apron_clips_the_lattice_to_its_own_footprint():
    """An L-shaped apron gets no lattice point in the missing quadrant."""
    L = Polygon([(0, 0), (300, 0), (300, 120), (120, 120), (120, 300),
                 (0, 300), (0, 0)])
    from shapely.geometry import Point
    for (_i, _j, x, y) in AL.lattice_points(L, 50.0):
        assert L.contains(Point(x, y))
        assert not (x > 130 and y > 130)


def test_the_polylines_are_rows_and_columns_of_the_lattice():
    pts = AL.lattice_points(_square(300.0), 50.0)
    lines = AL._rows_and_columns(pts)
    assert lines
    for line in lines:
        assert len(line) >= 2
        # each polyline is axis-aligned in the shape's own frame
        xs = {round(p[0], 3) for p in line}
        ys = {round(p[1], 3) for p in line}
        assert len(xs) == 1 or len(ys) == 1


# ═════════════════════════════════════════════════════════════════════
# ROUND-3 §2: A LATTICE SEGMENT CLIPS TO ITS OWN APRON
#
# RULINGS 2026-08-26b item 1 (owner sim read): the lattice OVERLAPS
# other shapes.  Measured on /tmp/harness/HECA_20260826T213425.osm — 7
# of 970 segments leave the apron footprint, 89.5 m: 28.1 m through
# building shapeID 157, 23.5 + 8.2 m through junctions 2775/2776, the
# rest through graded strips.  ``_rows_and_columns`` joins consecutive
# grid POINTS with only per-POINT containment, so a segment between two
# lawful points bridges a hole or a concavity.
# ═════════════════════════════════════════════════════════════════════

def _grid_gap(poly, spacing=50.0):
    """Two INDEX-ADJACENT lattice points of ``poly`` and the midpoint
    between them.  The defect lives exactly here: ``_rows_and_columns``
    keeps a run whose indices are consecutive, so an obstruction that
    fits BETWEEN two grid points never breaks the run and the segment
    bridges it — which is what the 7 HECA segments do."""
    pts = AL.lattice_points(poly, spacing)
    by_i = {}
    for (i, j, x, y) in pts:
        by_i.setdefault(i, []).append((j, x, y))
    for i in sorted(by_i):
        row = sorted(by_i[i])
        for (j0, x0, y0), (j1, x1, y1) in zip(row, row[1:]):
            if j1 == j0 + 1:
                return (x0, y0), (x1, y1), ((x0 + x1) / 2.0,
                                            (y0 + y1) / 2.0)
    raise AssertionError("no index-adjacent lattice pair")


def _blocker(mid, half=8.0):
    """A small obstruction centred between two adjacent grid points and
    small enough that neither point — nor the ring margin around it —
    reaches it."""
    cx, cy = mid
    return Polygon([(cx - half, cy - half), (cx + half, cy - half),
                    (cx + half, cy + half), (cx - half, cy + half),
                    (cx - half, cy - half)])


def _all_segments(lines):
    return [(a, b) for run in lines for a, b in zip(run, run[1:])]


def _carved(base, mid):
    """``base`` with a HOLE at ``mid`` (a building carved out of the
    apron — the measured HECA case, 28.1 m of lattice through building
    shapeID 157)."""
    return base.difference(_blocker(mid))


def _notched(base, mid):
    """``base`` with a narrow SLOT cut in from the nearest edge (a
    concavity — the junctions 2775/2776 case)."""
    cx, cy = mid
    minx, miny, maxx, maxy = base.bounds
    slot = Polygon([(cx - 8.0, cy - 8.0), (cx + 8.0, cy - 8.0),
                    (cx + 8.0, maxy + 10.0), (cx - 8.0, maxy + 10.0),
                    (cx - 8.0, cy - 8.0)])
    return base.difference(slot)


def test_no_lattice_segment_crosses_a_carved_hole():
    """A building carved out of an apron is an interior HOLE.  The
    points either side of it are lawful and index-adjacent, so only a
    per-SEGMENT test can see the bridge."""
    from shapely.geometry import LineString
    base = _square(400.0)
    _a, _b, mid = _grid_gap(base)
    poly = _carved(base, mid)
    raw = AL._rows_and_columns(AL.lattice_points(poly, 50.0))
    assert any(not poly.contains(LineString([a, b]))
               for (a, b) in _all_segments(raw)), \
        "the unclipped output must actually bridge the hole"
    for (a, b) in _all_segments(AL.clip_lines_to_apron(raw, poly)):
        assert poly.contains(LineString([a, b])), (a, b)


def test_no_lattice_segment_crosses_a_concave_notch():
    """The two arms either side of a narrow slot both hold grid points,
    and an unclipped row joins them straight across ground the apron
    does not own."""
    from shapely.geometry import LineString
    base = _square(400.0)
    _a, _b, mid = _grid_gap(base)
    poly = _notched(base, mid)
    raw = AL._rows_and_columns(AL.lattice_points(poly, 50.0))
    assert any(not poly.contains(LineString([a, b]))
               for (a, b) in _all_segments(raw)), \
        "the unclipped output must actually contain the defect"
    for (a, b) in _all_segments(AL.clip_lines_to_apron(raw, poly)):
        assert poly.contains(LineString([a, b])), (a, b)


def test_a_convex_apron_is_byte_identical_under_the_clip():
    """The clip is a REFUSAL, not a re-layout: where nothing leaves the
    footprint the runs are the ones the pre-round build emitted."""
    poly = _square(300.0)
    raw = AL._rows_and_columns(AL.lattice_points(poly, 50.0))
    assert AL.clip_lines_to_apron(raw, poly) == raw


def test_a_clipped_run_SPLITS_and_a_sub_run_under_two_points_dies():
    base = _square(400.0)
    _a, _b, mid = _grid_gap(base)
    poly = _carved(base, mid)
    raw = AL._rows_and_columns(AL.lattice_points(poly, 50.0))
    clipped = AL.clip_lines_to_apron(raw, poly)
    assert all(len(run) >= 2 for run in clipped)
    assert len(_all_segments(clipped)) < len(_all_segments(raw))


def test_the_margin_is_the_one_the_points_already_honour():
    """No new constant (spec section 2.2)."""
    src = inspect_source(AL.clip_lines_to_apron)
    assert "LATTICE_RING_MARGIN_M" in src


def test_a_point_orphaned_by_the_clip_is_dropped_with_its_segments():
    """A point in NO surviving run is referenced by no emitted way, so
    ``to_osm`` never writes it — the census would then report its law
    edges as LOST measurements.  Points and lines stay one population."""
    base = _square(400.0)
    _a, _b, mid = _grid_gap(base)
    layout = _Layout([_Shape(_carved(base, mid))])
    entries = AL.construct_apron_lattice_presolve(layout)
    assert entries
    for e in entries:
        in_lines = {(x, y) for run in e["lines"] for (x, y) in run}
        assert set(e["points"]) <= in_lines


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)


# ═════════════════════════════════════════════════════════════════════
# TRIGGER: the §2 measurement, not a second notion
# ═════════════════════════════════════════════════════════════════════

def _offset(poly, dx, dy):
    from shapely.affinity import translate
    return translate(poly, dx, dy)


def test_a_big_empty_apron_is_latticed_and_a_small_one_is_not():
    big = _Shape(_square(300.0))
    # WELL CLEAR of the big one: a concentric small apron would fill the
    # big one's interior with its own ring vertices and (correctly) stop
    # it being empty at all.
    small = _Shape(_offset(_square(100.0), 900.0, 0.0))
    layout = _Layout([big, small])
    entries = AL.construct_apron_lattice_presolve(layout)
    assert len(entries) == 1
    assert entries[0]["shape"] is big
    assert entries[0]["radius_m"] >= 80.0
    assert entries[0]["points"]


def test_the_trigger_is_the_section_2_instrument_itself():
    """One implementation of 'is this apron empty'.  A private second
    notion here is the census-wrapper defect in miniature."""
    import inspect
    src = inspect.getsource(AL.construct_apron_lattice_presolve)
    assert "largest_nodeless_disk" in src
    poly = _square(300.0)
    ring = [(float(x), float(y)) for x, y in poly.exterior.coords]
    assert largest_nodeless_disk(poly, None, ring, 80.0) is not None


def test_an_apron_crossed_by_another_shape_is_not_empty():
    """The disk is measured against EVERY shape's vertices — an apron a
    taxiway is sliced through has no empty disk left.  (Four far-apart
    corners would NOT do it, and must not: a 4-vertex ring across a
    300 m apron leaves the middle just as uncontrolled as before.)"""
    big = _Shape(_square(300.0))
    band = Polygon([(-150, -12), (150, -12), (150, 12), (-150, 12),
                    (-150, -12)])
    dense = Polygon([(x, y) for x in range(-150, 151, 20)
                     for y in (-12,)]
                    + [(x, 12) for x in range(150, -151, -20)])
    assert band.is_valid and dense.is_valid
    layout = _Layout([big, _Shape(dense, role="taxiway")])
    assert AL.construct_apron_lattice_presolve(layout) == []


def test_only_apron_role_shapes_are_latticed():
    layout = _Layout([_Shape(_square(300.0), role="taxiway")])
    assert AL.construct_apron_lattice_presolve(layout) == []


# ═════════════════════════════════════════════════════════════════════
# THE FLAG
# ═════════════════════════════════════════════════════════════════════

def test_the_flag_defaults_on_and_off_mints_nothing():
    import auto_patch.config as cfg
    assert cfg.APRON_INTERIOR_LATTICE is True
    assert cfg.APRON_LATTICE_SPACING_M == 50.0
    import os
    os.environ["O4_APRON_INTERIOR_LATTICE"] = "0"
    try:
        importlib.reload(cfg)
        layout = _Layout([_Shape(_square(300.0))])
        assert AL.construct_apron_lattice_presolve(layout) == []
        assert layout.apron_lattice_presolve == []
    finally:
        os.environ.pop("O4_APRON_INTERIOR_LATTICE", None)
        importlib.reload(cfg)


def test_flag_off_also_makes_the_constraint_leg_vacuous():
    import auto_patch.config as cfg
    import os
    layout = _Layout([_Shape(_square(300.0))])
    AL.construct_apron_lattice_presolve(layout)
    assert layout.apron_lattice_presolve
    os.environ["O4_APRON_INTERIOR_LATTICE"] = "0"
    try:
        importlib.reload(cfg)
        sc, idx, edges = AL.build_apron_lattice_constraints(
            layout, {}, None)
        assert (sc, idx, edges) == ([], set(), [])
    finally:
        os.environ.pop("O4_APRON_INTERIOR_LATTICE", None)
        importlib.reload(cfg)


# ═════════════════════════════════════════════════════════════════════
# SOLVER ADMISSION (Amendment 2 clause 1)
# ═════════════════════════════════════════════════════════════════════

def test_lattice_points_are_admitted_above_the_terrain_yield_boundary():
    """A lattice node is APRON MEMBRANE priced by the apron's caps, not a
    free terrain leaf yielding to a host.  Admitting it below
    ``_terrain_host_yield_first_index`` would hand it to the terrain
    lever and freeze the very membrane it exists to control."""
    import inspect
    from auto_patch.elevation_per_surface import solver_primitives as SP
    src = inspect.getsource(SP._build_node_list)
    i_lat = src.index("apron_lattice_presolve")
    i_bound = src.index("_terrain_host_yield_first_index = len(nodes)")
    assert i_lat < i_bound, (
        "the lattice must be admitted BEFORE the terrain-yield boundary")


def test_the_scaffold_seed_reseats_the_lattice_as_apron_interior():
    """§1b's seed clause: lattice nodes join the ``interior_nodes`` set
    the 24c scaffold interpolation re-seats (DEM-last)."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    assert "_lattice_idx" in src
    assert "apron_body = set(apron_body) | {i for i in _lattice_idx" in src


# ═════════════════════════════════════════════════════════════════════
# THE LAW IS THE APRON'S OWN (Amendment 2 clause 1)
# ═════════════════════════════════════════════════════════════════════

def test_the_edges_are_priced_through_the_shared_classify_pair():
    """One law.  A private cap table here would be a second authority
    over the same pairs the ring already obeys."""
    import inspect
    src = inspect.getsource(AL.build_apron_lattice_constraints)
    assert "_grade_graph_edges" in src
    for forbidden in ("ROLE_GRADE_LIMITS", "APRON_MAX_GRADE", "0.015"):
        assert forbidden not in src, forbidden


def test_only_the_edges_the_lattice_introduces_are_stated():
    """The apron's own ring pairs already have a within-shape entry;
    stating them twice hands the POCS sweep two copies of one law."""
    import inspect
    src = inspect.getsource(AL.build_apron_lattice_constraints)
    assert "lat_set" in src and "a in lat_set or b in lat_set" in src


# ═════════════════════════════════════════════════════════════════════
# CENSUS FAMILY (Amendment 2 clause 3)
# ═════════════════════════════════════════════════════════════════════

def test_the_family_is_registered():
    """A check in ``run_checks`` that is not in ``LAW_FAMILIES`` fails
    ``test_harness``; registration is what makes omission impossible."""
    import check_grade as CG
    keys = [k for k, _t, _b in CG.LAW_FAMILIES]
    assert "apron_lattice_membrane" in keys
    bucket = {k: b for k, _t, b in CG.LAW_FAMILIES}
    assert bucket["apron_lattice_membrane"] == "within"


def test_the_sidecar_key_is_registered_as_LAW_input():
    import check_grade as CG
    assert CG.SIDECAR_LAW_KEYS["apron_lattice_edges"] == \
        "apron_lattice_edges_ll"
    assert "apron_lattice_edges" not in CG.SIDECAR_EVIDENCE_KEYS


def _parse_with_features(path):
    """``(nodes, ways, lattice_ways)`` — the lattice is an OPEN
    constrained breakline, so ``_parse_osm`` routes it to
    ``feature_out`` and never into ``ways``.  A ring-only population
    would find none of it."""
    import check_grade as CG
    feats: dict = {}
    nodes, ways = CG._parse_osm(Path(path), feature_out=feats)
    return nodes, ways, feats.get("apron_lattice", [])


def test_the_lattice_is_a_registered_open_feature_class():
    """Without this the emitted polylines are dropped by the ring filter
    and every lattice edge silently becomes a LOST MEASUREMENT."""
    import check_grade as CG
    assert "apron_lattice" in CG.ROLE_LESS_FEATURE_CLASSES


def _membrane_patch(tmp_path, name, alt_b, *, budget=0.50):
    """An emitted lattice polyline whose first two stations are 50 m
    apart, with a declared budget for that pair.  THREE nodes, because
    ``_parse_osm`` drops a way with fewer (its open-feature route is
    reached after that filter) — which is itself why a 2-station run
    lands in the LOST-MEASUREMENT count rather than passing silently."""
    lat0, lon0 = ANCHOR
    dlon = 50.0 / (111320.0 * math.cos(math.radians(lat0)))
    txt = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n",
           f"  <node id='-1' lat='{lat0:.9f}' lon='{lon0:.9f}'>\n"
           f"    <tag k='alt_abs' v='100.0'/>\n  </node>\n",
           f"  <node id='-2' lat='{lat0:.9f}' lon='{lon0 + dlon:.9f}'>\n"
           f"    <tag k='alt_abs' v='{alt_b}'/>\n  </node>\n",
           f"  <node id='-3' lat='{lat0:.9f}' lon='{lon0 + 2 * dlon:.9f}'>\n"
           f"    <tag k='alt_abs' v='{alt_b}'/>\n  </node>\n",
           "  <way id='-900'>\n    <nd ref='-1'/>\n    <nd ref='-2'/>\n"
           "    <nd ref='-3'/>\n"
           "    <tag k='o4_feature' v='apron_lattice'/>\n"
           "    <tag k='aeroway' v='apron'/>\n  </way>\n",
           "</osm>\n"]
    p = tmp_path / name
    p.write_text("".join(txt))
    edges = [{"a": [lat0, lon0], "b": [lat0, lon0 + dlon],
              "budget_m": budget, "shapeID": 7}]
    (tmp_path / (name + ".axes.json")).write_text(json.dumps(
        {"anchor": list(ANCHOR), "ruleset": "icao",
         "apron_lattice_edges": edges}))
    return p, edges


def test_a_membrane_pair_over_its_budget_is_a_row(tmp_path):
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "over.osm", 101.2, budget=0.50)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    rows, n_checked, n_unmatched = CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)
    assert n_checked == 1 and n_unmatched == 0
    assert len(rows) == 1
    assert rows[0].de_m == pytest.approx(1.2, abs=1e-6)


def test_a_membrane_pair_inside_its_budget_is_not(tmp_path):
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "under.osm", 100.4, budget=0.50)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    rows, n_checked, _u = CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)
    assert n_checked == 1 and rows == []


def test_the_budget_is_the_solvers_own_not_re_derived(tmp_path):
    """The same geometry judged against two declared budgets gives two
    answers — proof the family reads the published number."""
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "b1.osm", 100.8, budget=0.50)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    assert CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)[0]
    edges[0]["budget_m"] = 1.5
    assert CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)[0] == []


def test_an_unmatched_edge_is_a_LOST_MEASUREMENT_not_a_pass(tmp_path):
    """The emit decimators can remove a lattice vertex.  A published
    edge with no emitted endpoint must be COUNTED, never silently
    dropped into a clean report."""
    import check_grade as CG
    p, edges = _membrane_patch(tmp_path, "gone.osm", 100.1)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    edges[0]["b"] = [ANCHOR[0] + 0.01, ANCHOR[1] + 0.01]   # far away
    rows, n_checked, n_unmatched = CG._check_apron_lattice_membrane(
        edges, lat_ways, ways, nodes, to_m)
    assert (rows, n_checked, n_unmatched) == ([], 0, 1)


def test_no_published_edges_means_no_rows_and_no_claim(tmp_path):
    import check_grade as CG
    p, _e = _membrane_patch(tmp_path, "none.osm", 100.1)
    nodes, ways, lat_ways = _parse_with_features(p)
    to_m = CG._ll_to_m_factory(nodes, ANCHOR)
    assert CG._check_apron_lattice_membrane(
        None, lat_ways, ways, nodes, to_m) == ([], 0, 0)


# ═════════════════════════════════════════════════════════════════════
# EMISSION (Amendment 2 clause 2)
# ═════════════════════════════════════════════════════════════════════

def test_the_lattice_emits_as_o4_feature_polylines(tmp_path):
    """The valued-node triple, the drainage-spine precedent."""
    from auto_patch.layout import PavementLayout
    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    layout.apron_lattice_emit = [
        ([(30.1200, 31.4000), (30.1201, 31.4001),
          (30.1202, 31.4002)], [100.0, 100.2, 100.4])]
    patch = tmp_path / "TEST_auto.patch.osm"
    layout.to_osm(str(patch))
    body = patch.read_text()
    assert "apron_lattice" in body
    nodes, ways, lat_ways = _parse_with_features(patch)
    assert lat_ways, "the lattice way must reach the OPEN-FEATURE route"
    assert any(len(w.nids) == 3 for w in lat_ways), \
        "the three lattice stations must reach the patch"
    assert all(w.elevs and all(v is not None for v in w.elevs)
               for w in lat_ways), \
        "each station must carry its own alt_abs (the valued-node triple)"


def test_the_sidecar_carries_the_lattice_edges(tmp_path):
    from auto_patch.layout import PavementLayout
    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    layout._apron_lattice_edges_ll = [
        {"a": [30.12, 31.40], "b": [30.1201, 31.40],
         "budget_m": 0.5, "shapeID": 3}]
    patch = tmp_path / "T_auto.patch.osm"
    layout.to_osm(str(patch))
    side = json.loads((tmp_path / "T_auto.patch.osm.axes.json").read_text())
    assert side["apron_lattice_edges"][0]["budget_m"] == 0.5


def test_an_empty_reading_is_not_an_absent_key(tmp_path):
    from auto_patch.layout import PavementLayout
    import check_grade as CG
    patch = tmp_path / "E_auto.patch.osm"
    PavementLayout(icao="E", anchor=ANCHOR).to_osm(str(patch))
    side = json.loads((tmp_path / "E_auto.patch.osm.axes.json").read_text())
    assert side["apron_lattice_edges"] == []
    ev = CG.sidecar_evidence(str(patch))
    assert ev["unknown_keys"] == []
