"""Tunnel wall crest = DEM all the way round the ramp — the L1-L4 twins.

Spec: ``docs/specs/tunnel-wall-crest-dem-spec.md`` (owner ruling
2026-09-03, sim read of 1.0.275 at OTHH 25.2715296,51.6022683 and
25.2556192,51.6080938).

L1  THE CREST IS THE DEM AT ITS STATION.  No transition law in either
    wall emitter; at a mouth the crest stands the bore datum above the
    ramp's mouth vertex by construction and the cap is the headwall.
L2  THE WALL IS THE DISCONTINUITY.  ``retaining_wall`` is out of
    ``groundside.TRANSITION_ROLES``; the post-emit pass moves 0 walls.
L3  GROUND OUTSIDE A WALLED RAMP STANDS AT THE CREST.  A ramp with a
    wall band registered against it is not a below-grade source; an
    unwalled ramp keeps round-4 R5.
L4  SERVICE-ROAD-FAMILY HOSTS ARE TAKEN WHOLE ALONGSIDE THE RUN — a
    geometric partition at the ramp's far-end line, no tolerance.

Every twin is INTERVENTIONAL where the old law can be named: the value
the deleted mechanism would have produced is asserted absent.
"""
import math

import pytest
from shapely.geometry import Point, Polygon, box

from auto_patch import bridges, groundside
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_RETAINING_WALL,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_TUNNEL_RAMP,
)


_ANCHOR = (25.2715296, 51.6022683)          # the owner's site-1 wall node
_WALL_GAP_M = 0.5
_WALL_W_M = 1.0
_DEM_M = 4.0                                 # the OTHH DEM at both sites
_DEPTH_M = 5.1                               # BRIDGE_ROAD_CLEARANCE_M
_MOUTH_M = _DEM_M - _DEPTH_M                 # -1.1: the owner's ramp node


def _ring_open(polygon):
    ring = list(polygon.exterior.coords)
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def _flat_dem(x, y):
    return _DEM_M


def _tilted_dem(x, y):
    return _DEM_M + 0.5 * y


# ── L1 ───────────────────────────────────────────────────────────────

_BODY = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 12.0), (0.0, 12.0)])


def _walled_diving_body(dem_at, arm_ends):
    """One ramp body diving from DEM at x = 60 to the mouth at x = 0,
    walled by the perimeter band.  ``arm_ends=[]`` wraps the ends (the
    cap across the mouth); an arm end at x = 60 cuts the far end open."""
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)
    ramp = BuiltShape(polygon=_BODY, role=ROLE_TUNNEL_RAMP,
                      ref="tunnel_ramp",
                      node_altitudes=[_MOUTH_M, _DEM_M, _DEM_M, _MOUTH_M,
                                      _MOUTH_M])
    layout.shapes.append(ramp)
    zones: list = []
    bridges.emit_wall_band(layout, zones, [_BODY], [ramp], arm_ends,
                           _WALL_GAP_M, _WALL_W_M, dem_at, _DEM_M)
    walls = [s for s in layout.shapes if s.ref == "tunnel_wall"]
    assert walls, "the perimeter band emitted no tunnel_wall piece"
    return layout, ramp, walls


def test_l1_the_crest_is_the_dem_all_the_way_round_including_the_mouth():
    """The owner's site 1 by construction: DEM 4.0, mouth −1.1.  EVERY
    band node — both sides AND the cap across the mouth — reads 4.0.
    The deleted mechanism put the mouth-side nodes at −1.10 / −1.08 and
    climbed away at the 4 % cap (0.94, 3.06, 4.00): none of that
    profile may survive anywhere on the band."""
    _layout, _ramp, walls = _walled_diving_body(_flat_dem, [])
    values = [a for w in walls for a in (w.node_altitudes or [])]
    assert values
    assert min(values) == pytest.approx(_DEM_M, abs=1e-9), (
        f"a band node left the DEM: min {min(values)} (the old crest "
        f"profile bottomed at {_MOUTH_M + 0.04 * _WALL_GAP_M:.2f})")
    assert max(values) == pytest.approx(_DEM_M, abs=1e-9)
    # The headwall: band nodes BEYOND the mouth (x < 0) exist and stand
    # at DEM too.
    cap_nodes = [(v, a) for w in walls
                 for v, a in zip(_ring_open(w.polygon), w.node_altitudes)
                 if v[0] < -1e-6]
    assert cap_nodes, "no cap across the mouth — the ends were not wrapped"
    assert all(a == pytest.approx(_DEM_M, abs=1e-9) for _v, a in cap_nodes)


def test_l1_the_mouth_crest_stands_the_bore_datum_above_the_ramp_vertex():
    """5.1 m above the ramp's mouth vertex — the owner's stated number —
    BY CONSTRUCTION, not by a transition run."""
    _layout, ramp, walls = _walled_diving_body(_flat_dem, [])
    mouth_ramp = min(ramp.node_altitudes)
    mouth_wall = [a for w in walls
                  for v, a in zip(_ring_open(w.polygon), w.node_altitudes)
                  if abs(v[0]) <= _WALL_GAP_M + _WALL_W_M + 1.0]
    assert mouth_wall
    for a in mouth_wall:
        assert a - mouth_ramp == pytest.approx(_DEPTH_M, abs=1e-9)


def test_l1_a_varying_dem_is_read_at_the_station_never_graded():
    """On a tilted DEM the crest follows the DEM along the body's own
    ring (one value per station, §F1 stands) and is nowhere pulled
    toward the ramp: every node is within emit rounding of the DEM at
    its nearest point on the body."""
    _layout, _ramp, walls = _walled_diving_body(_tilted_dem, [])
    checked = 0
    for w in walls:
        for v, a in zip(_ring_open(w.polygon), w.node_altitudes):
            station_pt = _BODY.exterior.interpolate(
                _BODY.exterior.project(Point(v)))
            expected = _tilted_dem(station_pt.x, station_pt.y)
            assert a == pytest.approx(expected, abs=0.051), (
                f"band node {v} carries {a}, DEM at its station "
                f"{expected:.2f}")
            checked += 1
    assert checked >= 8


def test_l1_the_crest_profile_takes_no_transition_index():
    """§6, delete-don't-gate: the profile is built from the body and the
    DEM alone.  A caller still passing an index is a caller of the
    deleted law."""
    import inspect
    params = list(inspect.signature(bridges._CrestProfile.__init__)
                  .parameters)
    assert params == ["self", "body", "dem_at", "apt_elev"], params
    src = inspect.getsource(bridges._CrestProfile)
    assert "transition_law_altitudes" not in src
    src_band = inspect.getsource(bridges.emit_wall_band)
    assert "_BelowGradeIndex" not in src_band
    assert "transition_law_altitudes" not in src_band
    src_low = inspect.getsource(bridges._emit_low_corridor_connectors)
    assert "_BelowGradeIndex" not in src_low


def test_l1_the_low_corridor_crest_is_the_dem_at_its_station():
    """The second emitter, same law: no crest node below the DEM at its
    station (the old index pinned the deepest station at floor + cap ×
    gap, ~5 m under the DEM)."""
    corridor = Polygon([(0.0, 0.0), (60.0, 0.0), (60.0, 12.0),
                        (0.0, 12.0)])
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)
    zones: list = []
    n = bridges._emit_low_corridor_connectors(
        layout, [corridor], zones, None, lambda x, y: _DEM_M,
        _tilted_dem, _DEPTH_M, _WALL_GAP_M, _WALL_W_M)
    assert n >= 1
    walls = [s for s in layout.shapes if s.ref == "tunnel_wall"]
    assert walls
    floor = _DEM_M - _DEPTH_M
    for w in walls:
        for v, a in zip(_ring_open(w.polygon), w.node_altitudes):
            if abs(a - floor) <= 1e-6:
                continue                     # R16-2b: an edge node
            station_pt = corridor.exterior.interpolate(
                corridor.exterior.project(Point(v)))
            assert a == pytest.approx(
                _tilted_dem(station_pt.x, station_pt.y), abs=0.051)


# ── L2 ───────────────────────────────────────────────────────────────

class _Shape:
    def __init__(self, polygon, role, ref, node_altitudes=None,
                 altitude=None):
        self.polygon = polygon
        self.role = role
        self.ref = ref
        self.node_altitudes = node_altitudes
        self.altitude = altitude


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)


def _diving_ramp_chain(length_m=600.0, top=4.0, portal=-4.02, pieces=30):
    ramps = []
    for i in range(pieces):
        x0, x1 = length_m * i / pieces, length_m * (i + 1) / pieces
        z0 = top + (portal - top) * (i / pieces)
        z1 = top + (portal - top) * ((i + 1) / pieces)
        ramps.append(_Shape(
            Polygon([(x0, 0), (x1, 0), (x1, 10), (x0, 10)]),
            "tunnel_ramp", "tunnel_ramp",
            node_altitudes=[z0, z1, z1, z0, z0]))
    return ramps


def _densified_band(y_inner=10.6, y_outer=11.6, length_m=600.0, step=10.0):
    xs = [i * step for i in range(int(length_m / step) + 1)]
    return Polygon([(x, y_outer) for x in xs]
                   + [(x, y_inner) for x in reversed(xs)])


def test_l2_the_wall_is_not_a_transition_role():
    assert ROLE_RETAINING_WALL not in groundside.TRANSITION_ROLES
    assert ROLE_GROUNDSIDE_PAVEMENT in groundside.TRANSITION_ROLES
    assert ROLE_SERVICE_ROAD in groundside.TRANSITION_ROLES
    assert ROLE_SERVICE_JUNCTION in groundside.TRANSITION_ROLES


def test_l2_the_post_emit_pass_moves_no_wall_even_beside_an_unwalled_ramp():
    """The round-4 fixture with the wall's re-profile deleted: a flat
    4.0 band beside a ramp diving to −4.02 stays flat at 4.0 at every
    station, the portal's included, and the pass reports 0 shapes."""
    ramps = _diving_ramp_chain()
    band = _Shape(_densified_band(), ROLE_RETAINING_WALL, "tunnel_wall",
                  altitude=4.0)
    layout = _Layout(ramps + [band])
    assert groundside.apply_below_grade_transition(layout) == 0
    assert band.altitude == 4.0
    assert band.node_altitudes is None


# ── L3 ───────────────────────────────────────────────────────────────

def _flat_site_layout():
    ramps = _diving_ramp_chain(length_m=300.0, top=4.0, portal=-4.0,
                               pieces=15)
    xs = [i * 10.0 for i in range(31)]
    plate = _Shape(
        Polygon([(x, 12.0) for x in xs] + [(x, 220.0) for x in reversed(xs)]),
        ROLE_GROUNDSIDE_PAVEMENT, "groundside", altitude=4.0)
    return _Layout(ramps + [plate]), ramps, plate


def test_l3_a_walled_ramp_is_not_a_below_grade_source():
    """The plate beside a WALLED ramp stands at the crest: the register
    names the ramps as the band's owners, and the sources drop them."""
    layout, ramps, plate = _flat_site_layout()
    band = _Shape(_densified_band(length_m=300.0), ROLE_RETAINING_WALL,
                  "tunnel_wall", altitude=4.0)
    layout.shapes.append(band)
    bridges.register_wall_band_owners(layout, band, ramps,
                                      _WALL_GAP_M + _WALL_W_M)
    assert groundside.walled_ramp_ids(layout) == frozenset(
        id(r) for r in ramps)
    assert groundside.below_grade_sources(layout) == []
    assert groundside.apply_below_grade_transition(layout) == 0
    assert plate.altitude == 4.0 and plate.node_altitudes is None


def test_l3_an_unwalled_ramp_keeps_round4_r5():
    """The control: no band registered, the plate still takes the
    transition law (S7's 5.62 m step is still forbidden there)."""
    layout, ramps, plate = _flat_site_layout()
    assert len(groundside.below_grade_sources(layout)) == len(ramps)
    assert groundside.apply_below_grade_transition(layout) == 1
    assert min(plate.node_altitudes) < 0.0


def test_l3_the_filter_lives_at_the_single_derivation_site():
    """RULINGS 2026-08-30l: trim at the derivation, never per consumer.
    ``apply_below_grade_transition`` carries no walled-ramp test of its
    own — it reads ``below_grade_sources``."""
    import inspect
    src = inspect.getsource(groundside.apply_below_grade_transition)
    assert "walled" not in src and "wall_band_owners" not in src
    assert "below_grade_sources(layout)" in src


def test_l3_a_trench_is_out_of_scope():
    """``tunnel_trench`` bodies are untouched by L3 — a trench is never a
    band owner, so it stays a source beside any wall."""
    trench = _Shape(Polygon([(0, 0), (100, 0), (100, 10), (0, 10)]),
                    ROLE_TUNNEL_RAMP, "tunnel_trench",
                    node_altitudes=[-3.0] * 5)
    band = _Shape(_densified_band(length_m=100.0), ROLE_RETAINING_WALL,
                  "tunnel_wall", altitude=4.0)
    layout = _Layout([trench, band])
    bridges.register_wall_band_owners(layout, band, [trench], 1.5)
    assert groundside.below_grade_sources(layout) == [], (
        "a registered owner drops out whatever its ref — the trench is "
        "out of scope because the trench emitters never register one")
    layout2 = _Layout([trench, band])
    assert len(groundside.below_grade_sources(layout2)) == 1


# ── L4 ───────────────────────────────────────────────────────────────

_RUN = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 10.0), (0.0, 10.0)])
_FAR_END = ((100.0, 5.0), (90.0, 5.0), 5.0, [_RUN])
_CLEARANCE_M = _WALL_GAP_M + _WALL_W_M


def _host(role, poly, alt=4.0):
    n = len(poly.exterior.coords)
    return BuiltShape(polygon=poly, role=role, ref="",
                      node_altitudes=[alt] * n)


def _l4_layout(*hosts):
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)
    layout.shapes.append(BuiltShape(
        polygon=_RUN, role=ROLE_TUNNEL_RAMP, ref="tunnel_ramp",
        node_altitudes=[-1.1, 4.0, 4.0, -1.1, -1.1]))
    layout.shapes.extend(hosts)
    bridges.register_ramp_far_ends(layout, [_FAR_END])
    return layout


def test_l4_a_straddling_service_host_is_split_at_the_far_end_line():
    """Tunnel side gone, grade side kept — split AT the line, exactly."""
    straddler = box(60.0, 10.5, 140.0, 16.5)
    layout = _l4_layout(_host(ROLE_SERVICE_ROAD, straddler))
    assert bridges._service_host_corridor_take(layout, None,
                                               _CLEARANCE_M) == 1
    roads = [s for s in layout.shapes if s.role == ROLE_SERVICE_ROAD]
    assert len(roads) == 1
    kept = roads[0].polygon
    expected = box(100.0, 10.5, 140.0, 16.5)
    assert kept.symmetric_difference(expected).area == pytest.approx(
        0.0, abs=1e-6), (
        f"kept {kept.wkt}; a width/area/distance tolerance would move "
        f"this split off the far-end line")
    assert roads[0].node_altitudes is not None


def test_l4_the_host_wrapping_the_mouth_goes_whole():
    """The OTHH −10051 class: the approach road's rect wrapping the
    mouth end and running beside the wall — every part is on the tunnel
    side and touches the run, so it goes whole (no ribbon)."""
    ribbon = Polygon([(-8.0, -8.0), (60.0, -8.0), (60.0, -1.0),
                      (-1.0, -1.0), (-1.0, 11.0), (60.0, 11.0),
                      (60.0, 18.0), (-8.0, 18.0)])
    layout = _l4_layout(_host(ROLE_SERVICE_ROAD, ribbon))
    assert bridges._service_host_corridor_take(layout, None,
                                               _CLEARANCE_M) == 1
    assert not [s for s in layout.shapes if s.role == ROLE_SERVICE_ROAD]


def test_l4_a_tunnel_side_host_that_never_touches_the_run_survives():
    """On the tunnel side but nowhere near the corridor: not the ramp's
    to take."""
    far_host = box(0.0, 40.0, 50.0, 46.0)
    layout = _l4_layout(_host(ROLE_SERVICE_JUNCTION, far_host))
    assert bridges._service_host_corridor_take(layout, None,
                                               _CLEARANCE_M) == 0
    kept = [s for s in layout.shapes if s.role == ROLE_SERVICE_JUNCTION]
    assert len(kept) == 1 and kept[0].polygon.equals(far_host)


def test_l4_groundside_pavement_keeps_25e():
    """A ``groundside_pavement`` host straddling the same line is NOT
    taken by L4 (RULINGS 2026-08-25e, the OTHH −12168 class): the
    annulus cut alone still governs it."""
    lot = box(60.0, 10.5, 140.0, 16.5)
    layout = _l4_layout(_host(ROLE_GROUNDSIDE_PAVEMENT, lot))
    assert bridges._service_host_corridor_take(layout, None,
                                               _CLEARANCE_M) == 0
    kept = [s for s in layout.shapes if s.role == ROLE_GROUNDSIDE_PAVEMENT]
    assert len(kept) == 1 and kept[0].polygon.equals(lot)


def test_l4_the_grade_side_beyond_the_line_is_never_in_the_region():
    """The partition itself: a host entirely beyond the far-end line,
    even one touching the run's corridor at the line, has no region."""
    at_grade = box(100.0, 10.5, 140.0, 16.5)
    assert bridges.service_host_take_region(
        at_grade, [_FAR_END], _CLEARANCE_M) is None
    beyond_touching = box(100.0, 0.0, 140.0, 10.0)   # the road at grade
    assert bridges.service_host_take_region(
        beyond_touching, [_FAR_END], _CLEARANCE_M) is None


def test_l4_the_take_names_every_piece(capsys):
    """The named-removal law (RULINGS 2026-08-25 §1): one
    ``[tunnel-remove]`` line per piece taken, carrying the host's index
    and area."""
    straddler = box(60.0, 10.5, 140.0, 16.5)
    layout = _l4_layout(_host(ROLE_SERVICE_ROAD, straddler))
    from O4_UI_Utils import verbosity as _v
    import O4_UI_Utils as UI
    old = UI.verbosity
    UI.verbosity = 1
    try:
        bridges._service_host_corridor_take(layout, None, _CLEARANCE_M)
    finally:
        UI.verbosity = old
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if "[tunnel-remove]" in ln]
    assert len(lines) == 1, out
    assert "L4" in lines[0] and "area=240.0m2" in lines[0], lines[0]
    assert "way=1" in lines[0]                  # the host's layout index


def test_l4_no_tolerance_constant_in_the_partition():
    """RULINGS 2026-09-01e: standoffs never on a tolerance.  The
    partition reads the far-end line and the corridor and nothing else —
    no ``_M2`` / ``_TOL`` / metre literal beside the half-plane extent."""
    import inspect, re
    src = inspect.getsource(bridges.service_host_take_region)
    body = src.split('"""', 2)[2]                # past the docstring
    literals = [v for v in re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", body)
                if float(v) != 0.0]              # ``> 0.0`` is a sign test
    assert literals == [], literals
    assert "_M2" not in body and "TOL" not in body


# ── L2, the writer the census found ──────────────────────────────────

def test_l2_deconflict_clip_carries_the_wall_profile():
    """``finalize.deconflict_road_features`` clips a wall piece an apron
    partly covers.  It used to assign the clipped ring and keep the OLD
    ``node_altitudes`` — misaligned, so the emit dropped every value
    (OTHH closing arm: 8 of 27 wall ways with no altitude).  The
    transition pass masked it by re-deriving the list; with the wall
    out of ``TRANSITION_ROLES`` the clip itself must carry the crest."""
    from auto_patch import finalize
    layout = PavementLayout(icao="ZZZZ", anchor=_ANCHOR)
    apron = BuiltShape(polygon=box(40.0, -5.0, 60.0, 5.0), role="apron",
                       ref="apron", altitude=4.0)
    ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 1.0), (0.0, 1.0)]
    wall = BuiltShape(polygon=Polygon(ring), role=ROLE_RETAINING_WALL,
                      ref="tunnel_wall",
                      node_altitudes=[4.0, 4.6, 4.6, 4.0, 4.0])
    layout.shapes.extend([apron, wall])
    finalize.deconflict_road_features(layout, "ZZZZ")
    walls = [s for s in layout.shapes if s.role == ROLE_RETAINING_WALL]
    assert len(walls) == 2, [w.polygon.bounds for w in walls]
    for w in walls:
        n_open = len(list(w.polygon.exterior.coords)) - 1
        assert w.node_altitudes is not None
        assert len(w.node_altitudes) in (n_open, n_open + 1), (
            f"clip left {len(w.node_altitudes)} value(s) on a "
            f"{n_open}-vertex ring")
        assert min(w.node_altitudes) >= 4.0 - 1e-9
        assert max(w.node_altitudes) <= 4.6 + 1e-9
