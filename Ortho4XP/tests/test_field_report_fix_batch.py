"""Field-report fix batch (Fable spec 2026-08-02): the four class-disjoint
laws, tested at their law functions and their readers.

Headless, no X-Plane install, no network: every case is synthetic geometry
or a pure law call.  Build-level behaviour (which shapes an emitter skips)
is covered by the battery arms, not here — what these tests pin is that the
LAW says what the ruling says and that the emitter and the validator read
the SAME law function.
"""
import importlib
import math
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(_REPO, "src"), os.path.join(_REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import config as CFG                     # noqa: E402
from auto_patch import grade_law as GL                   # noqa: E402
from auto_patch import grade_graph as GG                 # noqa: E402
import check_grade as CG                                 # noqa: E402


# ── §A runway-strip wall inadmissibility ────────────────────────────

def _straight_runway_ring(length_m=3000.0, half_width_m=22.5):
    return [(0.0, -half_width_m), (length_m, -half_width_m),
            (length_m, half_width_m), (0.0, half_width_m)]


def test_runway_axis_and_width_is_the_centreline_not_the_diagonal():
    ring = _straight_runway_ring()
    a, b, width = GL.runway_axis_and_width(ring)
    assert width == pytest.approx(45.0)
    assert a[1] == pytest.approx(0.0, abs=1e-9)
    assert b[1] == pytest.approx(0.0, abs=1e-9)
    assert math.hypot(b[0] - a[0], b[1] - a[1]) == pytest.approx(3000.0)


def test_runway_strip_footprint_uses_the_code_half_width():
    a, b, width = GL.runway_axis_and_width(_straight_runway_ring())
    rings = GL.runway_strip_wall_keepout_rings(a, b, width)
    assert len(rings) == 3                     # strip + two end corridors
    strip = rings[0]
    half = max(abs(y) for _x, y in strip)
    # 3000 m ⇒ ICAO code 4 ⇒ 75 m graded strip half-width.
    assert half == pytest.approx(
        CFG.RUNWAY_STRIP_HALF_WIDTH_BY_CODE[4])
    ends = [r for r in rings[1:]]
    for r in ends:
        assert max(abs(y) for _x, y in r) == pytest.approx(
            GL.runway_end_corridor_half_width_m(width, 3000.0))


def test_wall_inside_strip_flags_and_outside_does_not():
    a, b, width = GL.runway_axis_and_width(_straight_runway_ring())
    rings = GL.runway_strip_wall_keepout_rings(a, b, width)
    inside = CG._point_in_rect_ring(1500.0, 60.0, rings[0], 0.05)
    outside = CG._point_in_rect_ring(1500.0, 90.0, rings[0], 0.05)
    on_edge = CG._point_in_rect_ring(1500.0, 75.0, rings[0], 0.05)
    assert inside and not outside
    # A face the emitter CLIPPED at the strip boundary leaves vertices ON
    # the boundary; the margin must not turn those into violations.
    assert not on_edge


def test_beyond_the_end_corridor_is_out_of_scope():
    a, b, width = GL.runway_axis_and_width(_straight_runway_ring())
    rings = GL.runway_strip_wall_keepout_rings(a, b, width)
    end_len = CFG.RUNWAY_END_CLEARANCE_LENGTH_BY_CODE[4]
    assert any(CG._point_in_rect_ring(-end_len * 0.5, 0.0, r, 0.05)
               for r in rings)
    assert not any(CG._point_in_rect_ring(-end_len - 10.0, 0.0, r, 0.05)
                   for r in rings)


def test_wall_scope_never_admits_the_runway_roles():
    """STANDING LAW (owner 2026-08-01, ungated 2026-08-05): a runway must
    never QUALIFY an apron wall — walls at runway edges are not lawful.
    The former gate-off half of this twin retired with the gate."""
    cfg = importlib.reload(CFG)
    ag = importlib.reload(
        importlib.import_module("auto_patch.adjacent_ground"))
    assert cfg.RUNWAY_STRIP_WALL_LAW_ENABLED is True
    assert "runway" not in ag._WALL_SCOPE_PAVEMENT_ROLES
    assert {"apron", "junction", "groundside_pavement",
            "service_road"} <= ag._WALL_SCOPE_PAVEMENT_ROLES
    # ...and the retired env name can no longer move it.
    os.environ["O4_RUNWAY_STRIP_WALL_LAW"] = "0"
    try:
        cfg = importlib.reload(CFG)
        assert cfg.RUNWAY_STRIP_WALL_LAW_ENABLED is True
    finally:
        os.environ.pop("O4_RUNWAY_STRIP_WALL_LAW", None)
        importlib.reload(CFG)
        importlib.reload(
            importlib.import_module("auto_patch.adjacent_ground"))


# ── §B drainage-spine law ───────────────────────────────────────────

def test_spine_ceiling_is_at_least_the_fall_below_every_edge():
    fall = CFG.DRAINAGE_SPINE_MIN_FALL_M
    for d in (0.5, 5.0, 19.0, 40.0, 67.5, 95.0):
        _floor, ceil = GL.drainage_spine_envelope("junction", None, "E", d)
        assert ceil is not None
        assert ceil <= -fall + 1e-12, (d, ceil)


def test_spine_law_only_tightens_the_lateral_ceiling():
    """Never LOOSER than the lateral corridor — the spine law may only
    lower the ceiling, and it leaves a finite floor alone."""
    for d in (5.0, 12.0, 18.9):
        lat_floor, lat_ceil = GL.adjacent_ground_envelope(
            "junction", None, "E", d)
        sp_floor, sp_ceil = GL.drainage_spine_envelope(
            "junction", None, "E", d)
        assert sp_ceil <= lat_ceil + 1e-12
        if lat_floor is not None and lat_floor <= sp_ceil:
            assert sp_floor == pytest.approx(lat_floor)


def test_spine_law_composes_to_below_the_LOWER_of_two_edges():
    """The reader composes per-parent offsets as min(edge + ceil_off) —
    which must land at min(edge1, edge2) - FALL."""
    fall = CFG.DRAINAGE_SPINE_MIN_FALL_M
    edge1, edge2 = 100.0, 97.0
    ceils = []
    for edge, d in ((edge1, 60.0), (edge2, 70.0)):
        _f, c = GL.drainage_spine_envelope("junction", None, "E", d)
        ceils.append(edge + c)
    assert min(ceils) == pytest.approx(min(edge1, edge2) - fall)


def test_spine_floor_never_exceeds_its_ceiling():
    """Zone 1's steep lip floor sits ABOVE the drainage ceiling; the law
    must pin, not hand back an empty interval."""
    floor, ceil = GL.drainage_spine_envelope("junction", None, "E", 0.5)
    assert floor is not None and floor <= ceil + 1e-12


def test_gap_fill_binds_the_drainage_spine_envelope():
    """STANDING LAW (ungated 2026-08-05): gap-fill spines read the
    drainage-spine envelope, and the retired env name cannot restore the
    un-clamped one."""
    importlib.reload(CFG)
    gf = importlib.reload(importlib.import_module("auto_patch.gap_fill"))
    assert gf._spine_envelope.__name__ == "drainage_spine_envelope"
    os.environ["O4_DRAINAGE_SPINE_LAW"] = "0"
    try:
        importlib.reload(CFG)
        gf = importlib.reload(
            importlib.import_module("auto_patch.gap_fill"))
        assert gf._spine_envelope.__name__ == "drainage_spine_envelope"
    finally:
        os.environ.pop("O4_DRAINAGE_SPINE_LAW", None)
        importlib.reload(CFG)
        importlib.reload(importlib.import_module("auto_patch.gap_fill"))


# ── §C exact route legs + the chord gate ────────────────────────────

class _CL:
    is_service = False

    def __init__(self, pts):
        self.pts = pts


def _oracle(centerlines, exact):
    saved = GG.ROUTE_LEG_EXACT
    GG.ROUTE_LEG_EXACT = exact
    try:
        return GG._RouteDistanceOracle(centerlines)
    finally:
        GG.ROUTE_LEG_EXACT = saved


def test_exact_attachment_prices_the_offset_to_the_CENTRELINE():
    """A 2-point polyline: the nearest graph VERTEX of a mid-segment point
    is up to half the segment away; the nearest POINT ON the line is the
    perpendicular offset.  440/692 HECA axes are 2-point polylines."""
    cls = [_CL([(0.0, 0.0), (1000.0, 0.0)])]
    p, q = (480.0, 5.0), (520.0, 5.0)
    saved = GG.ROUTE_LEG_EXACT
    try:
        GG.ROUTE_LEG_EXACT = False
        legs_v = _oracle(cls, False).legs(p, q)
        GG.ROUTE_LEG_EXACT = True
        legs_e = _oracle(cls, True).legs(p, q)
    finally:
        GG.ROUTE_LEG_EXACT = saved
    assert legs_v[0] > 400.0 and legs_v[2] > 400.0     # vertex attachment
    assert legs_e[0] == pytest.approx(5.0)             # exact attachment
    assert legs_e[2] == pytest.approx(5.0)
    # same segment ⇒ the graph leg IS their separation along it
    assert legs_e[1] == pytest.approx(40.0)


def test_exact_attachment_reduces_to_the_vertex_answer_on_a_vertex():
    cls = [_CL([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)])]
    saved = GG.ROUTE_LEG_EXACT
    try:
        GG.ROUTE_LEG_EXACT = True
        o = _oracle(cls, True)
        legs = o.legs((0.0, 0.0), (100.0, 100.0))
    finally:
        GG.ROUTE_LEG_EXACT = saved
    assert legs[0] == pytest.approx(0.0)
    assert legs[2] == pytest.approx(0.0)
    assert legs[1] == pytest.approx(200.0)


def test_exact_attachment_routes_through_a_shared_junction_vertex():
    cls = [_CL([(0.0, 0.0), (500.0, 0.0)]),
           _CL([(500.0, 0.0), (500.0, 300.0)])]
    saved = GG.ROUTE_LEG_EXACT
    try:
        GG.ROUTE_LEG_EXACT = True
        legs = _oracle(cls, True).legs((100.0, 2.0), (503.0, 200.0))
    finally:
        GG.ROUTE_LEG_EXACT = saved
    assert legs is not None
    assert legs[0] == pytest.approx(2.0)
    assert legs[2] == pytest.approx(3.0)
    assert legs[1] == pytest.approx(600.0)      # 400 along + 200 up


def test_chord_gate_constant_is_the_predecessor_s():
    """§C2 names no new constant: the local-pair threshold is the one
    ``_route_metric_far_pair`` already uses."""
    assert GG.PAIR_CHORD_LOCAL_M == 120.0


# ── §C3 transverse reader ───────────────────────────────────────────

def test_transverse_cap_mapping_follows_the_role_letter_law():
    assert CG._transverse_cap_for_seg_cap(CFG.TAXI_MAX_GRADE) == \
        pytest.approx(CFG.TAXI_MAX_GRADE)                 # C-F isotropic
    assert CG._transverse_cap_for_seg_cap(CFG.TAXI_MAX_GRADE_NARROW) == \
        pytest.approx(CFG.TAXI_MAX_TRANSVERSE_NARROW)     # A/B 3%∥ 2%⊥
    assert CG._transverse_cap_for_seg_cap(CFG.SERVICE_ROAD_MAX_GRADE) == \
        pytest.approx(CFG.SERVICE_ROAD_MAX_TRANSVERSE)


def _way(wid, role, nids, elevs, tags=None):
    return CG.Way(wid=wid, role=role, ref="", aeroway="", nids=list(nids),
                  elevs=list(elevs), tags=dict(tags or {"role": role}))


def test_transverse_check_flags_a_cross_corridor_step():
    """A 40 m-wide junction with a 4 m cross-fall, one straight axis down
    its middle: the transverse law must see it."""
    # 40 m wide, 200 m long corridor; z rises 4 m across.
    nodes = {"1": (0.0, 0.0), "2": (0.0, 0.0), "3": (0.0, 0.0),
             "4": (0.0, 0.0)}
    # place them via a fake ll_to_m so the metre frame is explicit
    coords = {"1": (0.0, -20.0), "2": (200.0, -20.0),
              "3": (200.0, 20.0), "4": (0.0, 20.0)}

    def ll_to_m(lat, lon):
        return coords[f"{int(lat)}"]

    nodes = {k: (float(k), 0.0) for k in coords}
    w = _way("-1", "junction", ["1", "2", "3", "4"],
             [100.0, 100.0, 104.0, 104.0])
    axes = [([(0.0, 0.0), (200.0, 0.0)], [0.015], None, 0)]
    vios, n_st, n_rows, n_shapes = CG._check_transverse_grade(
        [w], nodes, ll_to_m, axes)
    assert n_rows > 0 and n_shapes == 1
    assert vios, "a 4 m step across 40 m (10 %) must flag at a 1.5 % cap"
    assert vios[0].grade_pct == pytest.approx(10.0, abs=0.1)


def test_transverse_check_passes_a_lawful_cross_fall():
    coords = {"1": (0.0, -20.0), "2": (200.0, -20.0),
              "3": (200.0, 20.0), "4": (0.0, 20.0)}
    nodes = {k: (float(k), 0.0) for k in coords}

    def ll_to_m(lat, lon):
        return coords[f"{int(lat)}"]

    # 1.0 % across 40 m = 0.4 m — inside the 1.5 % cap.
    w = _way("-1", "junction", ["1", "2", "3", "4"],
             [100.0, 100.0, 100.4, 100.4])
    axes = [([(0.0, 0.0), (200.0, 0.0)], [0.015], None, 0)]
    vios, _n_st, n_rows, _n_shapes = CG._check_transverse_grade(
        [w], nodes, ll_to_m, axes)
    assert n_rows > 0
    assert not vios


# ── §B3 spine reader ────────────────────────────────────────────────

def test_spine_reader_flags_a_spine_at_its_lower_pavement_level():
    coords = {
        # two parallel taxiway slabs 100 m apart, at 100.0 and 97.0
        "1": (0.0, 0.0), "2": (200.0, 0.0), "3": (200.0, 20.0),
        "4": (0.0, 20.0),
        "5": (0.0, 120.0), "6": (200.0, 120.0), "7": (200.0, 140.0),
        "8": (0.0, 140.0),
        # the spine down the middle
        "9": (50.0, 70.0), "10": (150.0, 70.0),
    }
    nodes = {k: (float(k), 0.0) for k in coords}

    def ll_to_m(lat, lon):
        return coords[f"{int(lat)}"]

    a = _way("-1", "junction", ["1", "2", "3", "4"], [100.0] * 4)
    b = _way("-2", "junction", ["5", "6", "7", "8"], [97.0] * 4)
    dam = _way("-3", "", ["9", "10"], [97.5, 97.5],
               tags={"o4_feature": "gap_drainage_spine"})
    vios, n_checked, _short = CG._check_drainage_spine_below_pavement(
        [dam], [a, b], nodes, ll_to_m)
    assert n_checked == 2
    assert len(vios) == 2
    assert vios[0].de_m == pytest.approx(0.5)

    drains = _way("-4", "", ["9", "10"], [96.0, 96.0],
                  tags={"o4_feature": "gap_drainage_spine"})
    vios2, n2, short2 = CG._check_drainage_spine_below_pavement(
        [drains], [a, b], nodes, ll_to_m)
    assert n2 == 2 and not vios2 and short2 == 0


def test_parse_osm_can_hand_back_the_open_breakline_ways(tmp_path):
    """The ring-skip stays (a spine is not a pavement ring) but the ways
    are recoverable in the SAME parse for their own law."""
    osm = tmp_path / "p.osm"
    osm.write_text(
        "<?xml version='1.0'?>\n<osm version='0.6'>\n"
        "<node id='-1' lat='30.0000000' lon='31.0000000'>"
        "<tag k='alt_abs' v='10.0' /></node>\n"
        "<node id='-2' lat='30.0001000' lon='31.0000000'>"
        "<tag k='alt_abs' v='10.5' /></node>\n"
        "<node id='-3' lat='30.0001000' lon='31.0001000'>"
        "<tag k='alt_abs' v='10.5' /></node>\n"
        "<way id='-10'><nd ref='-1' /><nd ref='-2' /><nd ref='-3' />"
        "<tag k='o4_feature' v='gap_drainage_spine' /></way>\n"
        "</osm>\n")
    feats = {}
    _nodes, ways = CG._parse_osm(osm, feature_out=feats)
    assert ways == []                                  # ring-skip kept
    assert len(feats["gap_drainage_spine"]) == 1
    assert feats["gap_drainage_spine"][0].elevs[:3] == [10.0, 10.5, 10.5]


# ── §D coverage check wiring ────────────────────────────────────────

def test_source_coverage_check_is_wired_under_its_gate():
    """Before this round ``check_source_coverage`` had ZERO call sites."""
    import inspect
    from auto_patch import verification as V
    src = inspect.getsource(V.verify_and_log)
    assert "check_source_coverage(" in src
    assert "SOURCE_COVERAGE_CHECK_ENABLED" in src
    # FLIPPED ON 2026-08-04 (spec ``docs/specs/kill-half-spec.md`` §1):
    # the invariant the owner flew four holes against now runs on every
    # build.  It REPORTS (docs/RULINGS.md: "census instruments REPORT, the
    # law ADJUDICATES"), so turning it on adds visibility, not violations.
    assert CFG.SOURCE_COVERAGE_CHECK_ENABLED is True    # default ON
