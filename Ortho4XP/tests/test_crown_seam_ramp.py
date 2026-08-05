"""The crown ramps to ZERO at a tile seam, and the spine reaches the cut
edge (owner ruling 2026-07-24).

    "We need to deal with the crown spine when a seam crosses a runway.
     Because we have to be at DEM we need to be sure the crown spine
     connects all the way to the shape edge after the seam cut, and that
     the spine ramps smoothly down to 0 crown at the seam at less than 1%
     grade."

Since 99f39a6 a tile seam is an ANCHOR in the runway profile solve — the
tile line and BOTH cut-back lines are sampled and anchored at the DEM.  The
runway therefore MEETS the terrain at its cut-back edge, so a crowned edge
there sits ``crown_drop`` below the terrain the 10 m tile-cut gap renders.

What these tests pin:

R1  the runway crown SPINE terminates exactly ON a tile-cut edge — the
    ``_SPINE_EDGE_CLEAR_M`` erosion is re-extended there (and only there;
    a physical runway end keeps its clearance), and the ring-clearance
    rejection is waived inside the cut band only;
R2  the crown drop is exactly 0 on a cut-back line, monotone approaching
    it, and its gradient never exceeds ``RUNWAY_CROWN_SEAM_TAPER`` — which
    is STRICTLY under 1% and sheds the largest emittable runway crown over
    MORE than 30 m;
D   cross-tile determinism: the ramp is a function of the node's own
    lat/lon against the graticule plus fixed constants, so it is symmetric
    about the seam and carries no dependence on which side of the cut the
    building tile owns;
G   ``O4_CROWN_SEAM_RAMP=0`` restores the pre-ruling behaviour, and an
    airport with no tile-cut seam vertices at all is a strict no-op.

Hermetic: hand-built layouts, no fixtures, no DEM, no network.
"""
from __future__ import annotations

import importlib
import math
import os
import sys

import pytest
from shapely.geometry import LineString, Polygon

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_patch.pipeline  # noqa: F401,E402  (import-cycle order)
from auto_patch import config as CFG                        # noqa: E402
from auto_patch import crown as CR                          # noqa: E402
from auto_patch.canonical_points import (                   # noqa: E402
    CanonicalPointRegistry)
from auto_patch.layout import ROLE_RUNWAY, vertex_bucket     # noqa: E402


# ── synthetic world ──────────────────────────────────────────────────
# The airport is anchored ON the integer LONGITUDE line lon == 1, so in
# local metres the seam is x == 0 and the two cut-back lines are x == ±5.
ANCHOR_LAT = 0.5
ANCHOR_LON = 1.0
M_PER_DEG = 111320.0
HALF = CFG.TILE_CUT_HALF_WIDTH_M
RATE = CFG.RUNWAY_CROWN_SEAM_TAPER
UNIFORM = 0.23                      # == 1.0% x a 22.86 m half-width
HW = 22.86


class _Shape:
    def __init__(self, role, polygon, *, ref=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = None
        self.adopts_apron_grade = False
        self.is_bridge = False
        self.source_axis = None
        self.from_single_poly = True


class _Layout:
    def __init__(self, shapes, seam_keys=None):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry()
        self.anchor = (ANCHOR_LAT, ANCHOR_LON)
        self.apt_taxi_centerlines = []
        self.crown_spines = []
        self._seam_anchor_keys = set(seam_keys or ())
        self._runway_redistributed_profiles = {}

    def m_to_ll(self, x, y):
        return (ANCHOR_LAT + float(y) / M_PER_DEG,
                ANCHOR_LON + float(x) / M_PER_DEG)

    def ll_to_m(self, lat, lon):
        return ((float(lon) - ANCHOR_LON) * M_PER_DEG,
                (float(lat) - ANCHOR_LAT) * M_PER_DEG)


def _bare_layout():
    return _Layout([])


# ── R2a: the rate itself ─────────────────────────────────────────────

def test_taper_rate_is_strictly_under_one_percent():
    """The ruling is 'less than 1%' — the pre-ruling code used exactly
    1.0% (TAXI_CROWN_TRANSVERSE).  The named constant must be strictly
    below it, with real headroom rather than a hairline pass."""
    assert RATE < 0.010
    assert RATE <= 0.005, "the chosen rate should keep 2x headroom under 1%"
    # and it must stay well under the runway's own longitudinal cap so the
    # ramp alone can never carry a rail pair to it.
    assert RATE * 3 <= CFG.RUNWAY_MAX_GRADE
    # ... and under the FAA end-zone longitudinal limit.
    assert RATE < CFG.RUNWAY_END_GRADE


def test_max_runway_crown_sheds_over_more_than_thirty_metres():
    """A 0.30 m drop (RUNWAY_CROWN_TRANSVERSE x the 30 m half-width cap)
    must shed over MORE than 30 m — the ruling's explicit yardstick."""
    max_drop = CFG.RUNWAY_CROWN_TRANSVERSE * CR._RUNWAY_HALFW_CAP_M
    assert max_drop == pytest.approx(0.30)
    assert max_drop / RATE > 30.0
    assert max_drop / RATE == pytest.approx(60.0)


# ── R2b: the ramp geometry ───────────────────────────────────────────

def test_seam_distances_are_measured_against_the_graticule():
    L = _bare_layout()
    assert CR._seam_line_dist_m(L, 0.0, 0.0) == pytest.approx(0.0, abs=1e-6)
    assert CR._seam_line_dist_m(L, 40.0, 0.0) == pytest.approx(40.0, abs=0.01)
    # ... and symmetric about the line.
    assert (CR._seam_line_dist_m(L, -40.0, 0.0)
            == pytest.approx(CR._seam_line_dist_m(L, 40.0, 0.0), abs=1e-9))
    # the cut distance is the seam distance offset by the cut half width
    assert CR._seam_cut_dist_m(L, HALF, 0.0) == pytest.approx(0.0, abs=1e-3)
    assert CR._seam_cut_dist_m(L, 0.0, 0.0) == 0.0        # inside the gap
    assert (CR._seam_cut_dist_m(L, HALF + 30.0, 0.0)
            == pytest.approx(30.0, abs=0.01))


def test_ramp_cap_is_zero_on_the_cut_back_line_and_linear_inboard():
    L = _bare_layout()
    assert CR._seam_ramp_cap(L, HALF, 0.0) == pytest.approx(0.0, abs=1e-5)
    assert CR._seam_ramp_cap(L, -HALF, 0.0) == pytest.approx(0.0, abs=1e-5)
    assert CR._seam_ramp_cap(L, 0.0, 0.0) == 0.0
    for d in (10.0, 25.0, 50.0, 120.0):
        assert (CR._seam_ramp_cap(L, HALF + d, 0.0)
                == pytest.approx(RATE * d, abs=1e-3))


def test_ramp_cap_gradient_never_exceeds_the_rate_in_any_direction():
    """The cap is a function of the perpendicular distance to the seam
    line alone, so |grad| == RATE exactly — the realised shed along ANY
    line (runway axis, a rail, an oblique cut edge) is therefore <= RATE,
    and equals it only for a seam crossed at 90 degrees."""
    L = _bare_layout()
    step = 0.25
    worst = 0.0
    for i in range(1, 400):
        x = HALF + i * 0.5
        for (dx, dy) in ((step, 0.0), (0.0, step),
                         (step * 0.7071, step * 0.7071)):
            c0 = CR._seam_ramp_cap(L, x, 0.0)
            c1 = CR._seam_ramp_cap(L, x + dx, dy)
            run = math.hypot(dx, dy)
            worst = max(worst, abs(c1 - c0) / run)
    assert worst <= RATE + 1e-9
    # the axis-normal direction actually attains it (no accidental softening)
    assert worst == pytest.approx(RATE, rel=1e-3)


def test_ramp_cap_is_monotone_approaching_the_seam():
    L = _bare_layout()
    prev = None
    for i in range(200, -1, -1):          # walking IN toward the seam
        c = CR._seam_ramp_cap(L, HALF + i * 1.0, 0.0)
        if prev is not None:
            assert c <= prev + 1e-12
        prev = c
    assert prev == pytest.approx(0.0, abs=1e-5)


# ── D: cross-tile determinism ────────────────────────────────────────

def test_ramp_is_symmetric_about_the_seam():
    """Neither tile sees a different ramp on its own side of the cut: the
    cap at +d and at -d agree far below the 1 mm the field is rounded to
    (they differ only by the last bits of ``lon +/- eps`` around an
    integer, ~1e-12 m of drop)."""
    L = _bare_layout()
    for d in (5.0, 5.5, 9.0, 21.37, 60.0, 137.0, 400.0):
        a = CR._seam_ramp_cap(L, d, 0.0)
        b = CR._seam_ramp_cap(L, -d, 0.0)
        assert a == pytest.approx(b, abs=1e-9)
    # the physically load-bearing case — BOTH cut-back lines — rounds to
    # the same emitted 0 at the field's 1 mm quantum.
    assert round(CR._seam_ramp_cap(L, HALF, 0.0), 3) == 0.0
    assert round(CR._seam_ramp_cap(L, -HALF, 0.0), 3) == 0.0


def test_ramp_depends_only_on_position_and_constants():
    """Two layouts built for DIFFERENT tiles (different shapes, different
    seam-key sets, different everything) return the identical cap at the
    identical lat/lon — nothing tile-local enters."""
    a = _Layout([], seam_keys={("a",)})
    b = _Layout([_Shape(ROLE_RUNWAY, Polygon(
        [(1000, 0), (2000, 0), (2000, 10), (1000, 10)]), ref="09/27")],
        seam_keys={("b",), ("c",)})
    for d in (-450.0, -12.0, -5.0, 0.0, 5.0, 33.3, 981.25):
        la, lo = a.m_to_ll(d, -77.0)
        xa, ya = a.ll_to_m(la, lo)
        xb, yb = b.ll_to_m(la, lo)
        assert CR._seam_ramp_cap(a, xa, ya) == CR._seam_ramp_cap(b, xb, yb)


# ── the drop FIELD on a seam-cut runway ──────────────────────────────

# A runway cut at the seam, keeping the x >= HALF side; the cut edge is
# densified like production's over-60 m edge densify, so the ramp (not the
# seam-bucket exemption) is what has to zero the interior cut-edge nodes.
_STATIONS = [HALF, 20.0, 40.0, 60.0, 80.0, 120.0, 400.0, 1000.0]


def _seam_runway_layout():
    bot = [(x, -HW) for x in _STATIONS]
    top = [(x, HW) for x in reversed(_STATIONS)]
    cut = [(HALF, HW / 3.0), (HALF, -HW / 3.0)]
    ring = bot + top + cut
    s = _Shape(ROLE_RUNWAY, Polygon(ring), ref="09/27")
    seam_keys = {vertex_bucket(HALF, -HW), vertex_bucket(HALF, HW)}
    L = _Layout([s], seam_keys=seam_keys)
    # FIXTURE COMPLETED 2026-08-04 (landing commit d371e68, "Working-tree
    # snapshot: remaining uncommitted engine work", which added
    # ``crown._rail_continuous_drops``).  ``axis_len2`` — the squared
    # length of the axis displacement — is part of the record
    # ``redistribute_runway_profile`` writes
    # (runway_redistribute.py:1216-1218) and
    # ``sample_redistributed_profile`` indexes it unconditionally
    # (runway_redistribute.py:246).  Before d371e68 nothing in
    # ``build_crown_drop_field`` sampled the profile, so this hand-built
    # stub could omit the key; after it, every test in this module died on
    # ``KeyError: 'axis_len2'`` inside production code — a stale FIXTURE,
    # not a law failure.  ``axis_d`` is the raw displacement (b - a), so
    # ``axis_len2`` is its squared norm.
    L._runway_redistributed_profiles = {
        "09/27": {"crown_drop_m": UNIFORM, "half_width_m": HW,
                  "axis_a": (HALF, 0.0), "axis_d": (1000.0 - HALF, 0.0),
                  "axis_len2": (1000.0 - HALF) ** 2,
                  "fractions": [0.0, 1.0], "elevs": [10.0, 20.0]}}
    return L, ring


def _build_field(L, ring):
    cps = L.canonical_points
    nodes, bucket_to_idx = [], {}
    for (x, y) in ring:
        key = cps.get_or_add(float(x), float(y))
        if key not in bucket_to_idx:
            bucket_to_idx[key] = len(nodes)
            nodes.append((float(x), float(y)))
    drops = CR.build_crown_drop_field(L, nodes, bucket_to_idx, set())
    return {ring[i]: L._crown_drop_key.get(
        cps.get_or_add(float(ring[i][0]), float(ring[i][1])), 0.0)
        for i in range(len(ring))}, drops


def test_field_is_zero_on_the_cut_back_edge():
    L, ring = _seam_runway_layout()
    by_pt, _ = _build_field(L, ring)
    cut_pts = [p for p in ring if abs(p[0] - HALF) < 1e-6]
    assert len(cut_pts) == 4                     # 2 corners + 2 densified
    for p in cut_pts:
        assert by_pt[p] == 0.0, f"{p} carries crown {by_pt[p]}"


def test_field_ramps_monotonically_and_within_the_rate():
    L, ring = _seam_runway_layout()
    by_pt, _ = _build_field(L, ring)
    for rail in (-HW, HW):
        pts = sorted([p for p in ring if abs(p[1] - rail) < 1e-6])
        vals = [by_pt[p] for p in pts]
        assert vals[0] == 0.0                    # on the cut edge
        for i in range(1, len(vals)):
            assert vals[i] >= vals[i - 1] - 1e-9, "ramp is not monotone"
            run = abs(pts[i][0] - pts[i - 1][0])
            assert (abs(vals[i] - vals[i - 1]) / run
                    <= RATE + 1e-6), "ramp exceeds the taper rate"
        assert vals[-1] == pytest.approx(UNIFORM)   # releases into uniform


def test_field_never_exceeds_the_ramp_rule():
    """The ramp is the OUTERMOST min, so it is a hard ceiling on every
    node — the other crown terms may only push a node further DOWN.

    RE-PINNED 2026-08-04 (landing commit d371e68, which added
    ``crown._rail_continuous_drops``).  The CEILING half above is the law
    and is unchanged.  The old second half additionally claimed "nothing
    else should bind in this geometry — the ramp is the only active cap
    inside its zone"; that was a statement about the FIXTURE, and d371e68
    made it false by adding RAIL CONTINUITY, a later cap that RELEASES
    the crown at ring vertices where holding it would break the runway
    profile's own grade budget (the build prints "[crown] rail
    continuity: released the crown at 4 runway ring vertex(es)").

    Measured at this HEAD on this fixture: 14 of the 18 ring nodes sit
    exactly on the rule; the 4 releases are the x=20 and x=40 nodes on
    both edges, at 0.0740 vs rule 0.0750 and 0.1730 vs rule 0.1750 —
    i.e. 1-2 mm BELOW it.  A release is a push DOWN, so it obeys the
    docstring's own rule; what it refutes is only the exclusivity
    claim."""
    L, ring = _seam_runway_layout()
    by_pt, _ = _build_field(L, ring)
    n_on_rule, released = 0, []
    for p in ring:
        d_cut = max(0.0, CR._seam_line_dist_m(L, p[0], p[1]) - HALF)
        rule = round(min(UNIFORM, RATE * d_cut), 3)
        assert by_pt[p] <= rule + 1e-9, f"{p}: {by_pt[p]} over rule {rule}"
        if abs(by_pt[p] - rule) <= 1e-9:
            n_on_rule += 1
        else:
            released.append((p, rule - by_pt[p]))
    # The ramp is still the SHAPING authority: it binds on the large
    # majority of the ring, and every node off it is a rail-continuity
    # release sitting a sub-centimetre distance BELOW it (never above).
    assert n_on_rule >= len(ring) - 4, (
        f"the ramp stopped binding: only {n_on_rule}/{len(ring)} nodes "
        f"sit on the rule (off-rule: {released})")
    for p, slack in released:
        assert 0.0 < slack <= 0.01, (
            f"{p}: off-rule by {slack:.4f} m — not the sub-centimetre "
            "rail-continuity push-down d371e68 introduced")


def test_gate_off_restores_the_pre_ruling_crown_at_the_cut_edge(monkeypatch):
    """With the ramp gated off the interior cut-edge nodes emit a NON-ZERO
    crown — the defect the ruling names.  The pre-ruling taper measured
    ``TAXI_CROWN_TRANSVERSE`` x the distance to the nearest seam-bucket
    VERTEX, so here (a 45.7 m perpendicular cut edge) it lands at
    1.0% x 15.24 m; at SPLP's 18-degree oblique crossing the same nodes sit
    49 m from a corner and it does not bind at all, leaving the FULL
    0.23 m uniform drop on the cut edge."""
    monkeypatch.setenv("O4_CROWN_SEAM_RAMP", "0")
    cfg = importlib.reload(CFG)
    cr = importlib.reload(CR)
    try:
        assert cfg.CROWN_SEAM_RAMP is False
        L, ring = _seam_runway_layout()
        cps = L.canonical_points
        nodes, b2i = [], {}
        for (x, y) in ring:
            key = cps.get_or_add(float(x), float(y))
            if key not in b2i:
                b2i[key] = len(nodes)
                nodes.append((float(x), float(y)))
        cr.build_crown_drop_field(L, nodes, b2i, set())
        interior = [p for p in ring
                    if abs(p[0] - HALF) < 1e-6 and abs(abs(p[1]) - HW) > 1e-6]
        assert interior
        expect = cfg.TAXI_CROWN_TRANSVERSE * (HW - HW / 3.0)
        for p in interior:
            got = L._crown_drop_key.get(cps.get_or_add(*p), 0.0)
            assert got > 0.1, "gate off must leave a crown at the cut edge"
            assert got == pytest.approx(expect, abs=1e-3), (
                "gate off must reproduce the pre-ruling vertex taper")
    finally:
        monkeypatch.delenv("O4_CROWN_SEAM_RAMP", raising=False)
        importlib.reload(CFG)
        importlib.reload(CR)


def test_airport_without_seam_vertices_is_a_strict_no_op():
    """An airport the tile cut never touched has no seam pins, so the ramp
    must never fire even if its pavement happens to sit near a tile line."""
    L, ring = _seam_runway_layout()
    L._seam_anchor_keys = set()
    by_pt, _ = _build_field(L, ring)
    # every node keeps the plain uniform drop (no ramp, no zeroing)
    for p in ring:
        assert by_pt[p] == pytest.approx(UNIFORM)


# ── R1: the spine reaches the cut edge ───────────────────────────────

def _axis_and_body():
    """A runway body cut at x == HALF and ending physically at x == 1000."""
    body = Polygon([(HALF, -HW), (1000.0, -HW), (1000.0, HW), (HALF, HW)])
    axis = LineString([(0.0, 0.0), (1200.0, 0.0)])
    return axis, body


def test_spine_is_re_extended_to_the_cut_edge_only():
    L = _bare_layout()
    ax, body = _axis_and_body()
    inner = body.buffer(-CR._SPINE_EDGE_CLEAR_M)
    clipped = ax.intersection(inner)
    segs = [clipped] if clipped.geom_type == "LineString" else list(
        clipped.geoms)
    # baseline: the erosion pulls BOTH ends 1 m in
    assert segs[0].coords[0][0] == pytest.approx(HALF + 1.0, abs=1e-6)
    assert segs[0].coords[-1][0] == pytest.approx(999.0, abs=1e-6)

    out = CR._extend_spine_to_cut_edges(segs, ax, body, L)
    assert len(out) == 1
    xs = [c[0] for c in out[0].coords]
    # the SEAM end now lands on the cut-back line ...
    assert min(xs) == pytest.approx(HALF, abs=1e-3)
    # ... and the physical runway end keeps its clearance untouched.
    assert max(xs) == pytest.approx(999.0, abs=1e-3)


def test_spine_extension_leaves_a_body_with_no_cut_edge_alone():
    """A runway nowhere near a tile line must come back byte-identical."""
    L = _bare_layout()
    body = Polygon([(4000.0, -HW), (5000.0, -HW), (5000.0, HW),
                    (4000.0, HW)])
    ax = LineString([(3900.0, 0.0), (5100.0, 0.0)])
    inner = body.buffer(-CR._SPINE_EDGE_CLEAR_M)
    clipped = ax.intersection(inner)
    segs = [clipped]
    out = CR._extend_spine_to_cut_edges(segs, ax, body, L)
    assert list(out[0].coords) == list(segs[0].coords)


def test_ring_clearance_waiver_is_scoped_to_the_cut_band():
    """A sample ON the cut edge is admitted (crown drop 0 there, so the
    ridge and the ring agree by construction); every other sample keeps the
    0.9 m ring clearance."""
    from shapely.strtree import STRtree
    L = _bare_layout()
    ax, body = _axis_and_body()
    ring_geoms = [LineString(body.exterior.coords)]
    tree = STRtree(ring_geoms)
    seg = LineString([(HALF, 0.0), (1000.0, 0.0)])   # both ends ON a ring

    def alt_at(_st):
        return 12.0

    waived = CR._emit_ways_for_profile(seg, ax, alt_at, None, tree,
                                       ring_geoms, L, seam_cut_exempt=True)
    plain = CR._emit_ways_for_profile(seg, ax, alt_at, None, tree,
                                      ring_geoms, L, seam_cut_exempt=False)
    wx = [L.ll_to_m(la, lo)[0] for (pts, _a) in waived for (la, lo) in pts]
    px = [L.ll_to_m(la, lo)[0] for (pts, _a) in plain for (la, lo) in pts]
    # the seam end is admitted only with the waiver ...
    assert min(wx) == pytest.approx(HALF, abs=0.05)
    assert min(px) > HALF + 0.5
    # ... and the physical end is rejected by the ring clearance either way.
    assert max(wx) < 1000.0 - 0.5
    assert max(px) < 1000.0 - 0.5
