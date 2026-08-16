"""GAP CONFORMANCE — rings never cliff, interiors erode, spines descend.

Owner ruling 2026-08-15 evening (``docs/RULINGS.md``, "GAP INTERIOR
RINGS NEVER CLIFF AGAINST PAVEMENT"), implemented to Fable spec F3
``docs/specs/gap-conformance-spec.md``.  The measured offenders the
ruling names — CYXY ring ``-10527`` at 698.5-698.9 sitting 4-5 m below
adjacent road/groundside 702.7 within 11 m, and the flat-695.8 drainage
spine 7.7 m below its own 703.5 terrain — are the classes these twins
close BY CONSTRUCTION.

The four law classes, one section each:

  (a) LAW 2, THE ERODED POCKET — a lobe narrower than twice the margin
      erodes away entirely and is pure conformance band; the emitted
      ring is the eroded boundary, so it cuts across the neck with no
      hand-drawn line;
  (b) LAW 1, THE CONFORMANCE BAND — a band vertex equals its nearest
      enclosing pavement edge's SOLVED elevation, read the mouth-weld
      way (interpolated ALONG the edge), never terrain and never a
      stamped basin value;
  (c) LAW 1, THE SLIVER — a vertex near TWO pavements blends by inverse
      distance, so a sliver between pavements at different levels is
      one continuous surface with no step;
  (d) LAW 3, THE SPINE — the profile leaves its conformed boundary
      endpoints at the lawful graded slope and descends until it MEETS
      terrain, then follows terrain.  A spine value below its own local
      terrain is impossible.

Headless synthetic geometry only (the ``test_gap_interior_rings`` frame
pattern): a pavement frame enclosing one hole plus a stub DEM.
"""
import math

import pytest
from shapely.geometry import LineString, Point, Polygon

from auto_patch import gap_fill as GF
from auto_patch.clearance import _edge_interp_alt
from auto_patch.gap_fill import emit_gap_fill_spines
from auto_patch.layout import BuiltShape, ROLE_RUNWAY, ROLE_STUB

EDGE_ALT = 100.0
MARGIN = GF.GAP_PAVEMENT_CONFORM_MARGIN_M
CAP = GF._RING_ALONG_BENCH_SLOPE


class _FakeLayout:
    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)

    def ll_to_m(self, lat, lon):
        return (lon * 111320.0, lat * 111320.0)

    def __init__(self, shapes):
        self.shapes = shapes
        self.airport_boundary = None
        self.anchor = (0.0, 0.0)


class _StubDem:
    def __init__(self, fn):
        self._fn = fn

    def alt(self, t):
        dx, dy = t
        return self._fn(dx * 111320.0, dy * 111320.0)


def _rect(x0, y0, x1, y1, role=ROLE_RUNWAY, alt=None):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    coords = list(poly.exterior.coords)
    if alt is None:
        alts = [EDGE_ALT] * len(coords)
    elif callable(alt):
        alts = [float(alt(vx, vy)) for vx, vy in coords]
    else:
        alts = [float(alt)] * len(coords)
    return BuiltShape(polygon=poly, role=role, node_altitudes=alts)


_LOW = _StubDem(lambda x, y: 90.0)          # 10 m below the pavement


@pytest.fixture(autouse=True)
def _rings_on(monkeypatch):
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_RINGS_ENABLED", True)
    GF._CONFORM_INDEX_CACHE.clear()
    GF._NEAREST_INDEX_CACHE.clear()


def _rings_m(layout):
    return [([(lon * 111320.0, lat * 111320.0) for lat, lon in pts_ll],
             list(alts))
            for pts_ll, alts in (getattr(layout, "gap_interior_rings", None)
                                 or [])]


def _spines_m(layout):
    return [([(lon * 111320.0, lat * 111320.0) for lat, lon in pts_ll],
             list(vals))
            for pts_ll, vals in (getattr(layout, "gap_spines", None) or [])]


# ══════════════════════════════════════════════════════════════════════
# (a) LAW 2 — the interior is the ERODED pocket; narrow lobes are band
# ══════════════════════════════════════════════════════════════════════

LOBE_X0, LOBE_X1 = 600.0, 900.0
LOBE_H = 15.0                      # < 2 x MARGIN: erodes away entirely
BODY_X0, BODY_Y0, BODY_Y1 = 30.0, 30.0, 204.0


def _lobed_layout(alt=None):
    """A wide body hole with a NARROW LOBE off its east side — the CYXY
    sliver class (measured 8-15 m at 60.709358,-135.0734701)."""
    return _FakeLayout([
        _rect(0.0, 0.0, 1300.0, BODY_Y0, ROLE_RUNWAY, alt),
        _rect(0.0, BODY_Y1, 1300.0, BODY_Y1 + 30.0, ROLE_RUNWAY, alt),
        _rect(0.0, BODY_Y0, BODY_X0, BODY_Y1, ROLE_STUB, alt),
        _rect(LOBE_X1, BODY_Y0, 1300.0, BODY_Y1, ROLE_STUB, alt),
        # the block that narrows the east arm to LOBE_H
        _rect(LOBE_X0, BODY_Y0 + LOBE_H, LOBE_X1, BODY_Y1, ROLE_STUB, alt),
    ])


def _lobe_poly():
    return Polygon([(LOBE_X0, BODY_Y0), (LOBE_X1, BODY_Y0),
                    (LOBE_X1, BODY_Y0 + LOBE_H),
                    (LOBE_X0, BODY_Y0 + LOBE_H)])


def _lobed_gap():
    return Polygon([(BODY_X0, BODY_Y0), (LOBE_X1, BODY_Y0),
                    (LOBE_X1, BODY_Y0 + LOBE_H), (LOBE_X0, BODY_Y0 + LOBE_H),
                    (LOBE_X0, BODY_Y1), (BODY_X0, BODY_Y1)])


def _core_loop(layout, gap):
    """The ERODED-BOUNDARY loop: of the emitted loops, the one standing
    farthest off the pocket boundary (ring 1 is the 3 m drainage lip)."""
    loops = _rings_m(layout)
    assert loops, "expected emitted ring loops"
    return max(loops, key=lambda c: min(gap.exterior.distance(Point(p))
                                        for p in c[0]))


def test_a_narrow_lobe_erodes_away_and_the_ring_cuts_at_the_neck():
    layout = _lobed_layout()
    assert emit_gap_fill_spines(layout, _LOW, 0, 0) == 1
    gap = _lobed_gap()
    assert gap.buffer(-MARGIN).intersection(_lobe_poly()).is_empty, (
        "fixture: the lobe must erode away entirely")
    pts, _alts = _core_loop(layout, gap)
    lobe = _lobe_poly()
    for p in pts:
        assert not lobe.buffer(-1e-6).contains(Point(p)), (
            f"ring node {p} stands inside a lobe narrower than "
            f"2 x {MARGIN:.0f} m — that lobe is pure conformance band")
    # THE CUT ACROSS THE NECK, with no hand-drawn line: the eroded
    # boundary closes a margin short of the lobe mouth.
    east = max(p[0] for p in pts)
    assert east <= LOBE_X0 - MARGIN + 0.25, (
        f"the eroded boundary must close {MARGIN:.0f} m short of the "
        f"lobe mouth at x={LOBE_X0:.0f}, got {east:.2f}")


def test_every_ring_node_stands_at_the_margin_off_the_pocket_boundary():
    """LAW 2 stated as the property the erosion guarantees: the emitted
    ring IS the eroded boundary, so no station of it is nearer the
    pocket than the conformance margin (up to arithmetic)."""
    layout = _lobed_layout()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    gap = _lobed_gap()
    pts, _alts = _core_loop(layout, gap)
    for p in pts:
        d = gap.exterior.distance(Point(p))
        assert d >= MARGIN - 0.05, (
            f"ring node {p} sits {d:.2f} m off the pocket boundary, "
            f"inside the {MARGIN:.0f} m conformance band")


# ══════════════════════════════════════════════════════════════════════
# (b) LAW 1 — a band vertex takes its nearest pavement edge's value
# ══════════════════════════════════════════════════════════════════════

def _sloping(x, _y):
    """A pavement that RISES 1 % with x, so "the nearest edge's solved
    elevation" is a field and not one number — an edge-interpolated read
    is the only thing that can reproduce it."""
    return EDGE_ALT + 0.01 * x


def test_band_vertices_equal_their_nearest_edge_solved_value():
    layout = _lobed_layout(alt=_sloping)
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    chains = _rings_m(layout)
    assert chains
    # The pavement only — the emitted gap FACE is also in ``shapes`` and
    # its exterior IS the pocket boundary, which would read as a
    # conformance source at every station.
    pav = [s for s in layout.shapes
           if s.node_altitudes and s.role in (ROLE_RUNWAY, ROLE_STUB)]
    checked = solo = 0
    for pts, alts in chains:
        open_pts = pts[:-1] if pts[0] == pts[-1] else pts
        for (x, y), v in zip(open_pts, alts):
            p = Point(x, y)
            in_range = [(s.polygon.exterior.distance(p), s) for s in pav]
            in_range = [(d, s) for d, s in in_range if d <= MARGIN + 0.01]
            assert in_range, (
                f"band node at ({x:.0f},{y:.0f}) has no pavement in range")
            want = [_edge_interp_alt(s, x, y) for _d, s in in_range]
            assert all(w is not None for w in want)
            # ``_bench_along`` rounds to the centimetre; the spec's
            # materiality floor is 0.01 m.
            assert min(want) - 0.011 <= v <= max(want) + 0.011, (
                f"band node at ({x:.0f},{y:.0f}) is {v}, outside the "
                f"solved edge values in range {sorted(want)}")
            if len(in_range) == 1:
                # ONE pavement in range: no blend, exact conformance.
                assert abs(v - want[0]) <= 0.011, (
                    f"band node at ({x:.0f},{y:.0f}) is {v}, its only "
                    f"pavement edge in range ships {want[0]:.3f}")
                solo += 1
            checked += 1
    assert checked >= 40
    assert solo >= 20, "most band nodes face a single pavement"


def test_a_band_vertex_never_takes_terrain():
    """The ruling's own words — "conformance, not terrain".  With the
    DEM 10 m under the pavement, not one band station rides it."""
    layout = _lobed_layout()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    chains = _rings_m(layout)
    assert chains
    for _pts, alts in chains:
        assert min(alts) > 90.0 + 0.05, (
            "a band station dropped to terrain — the cliff class the "
            "ruling forbids")


# ══════════════════════════════════════════════════════════════════════
# (c) LAW 1 — the SLIVER: two pavements blend by inverse distance
# ══════════════════════════════════════════════════════════════════════

def test_a_two_pavement_sliver_blends_with_no_step():
    """Both sides conform and there is no interior, so the surface
    across the sliver is ONE continuous inverse-distance blend between
    the two edge values — bounded by them, monotone across, and equal to
    each edge's own value where it meets that edge."""
    south = _rect(0.0, 0.0, 400.0, 30.0, ROLE_RUNWAY, 100.0)
    north = _rect(0.0, 42.0, 400.0, 72.0, ROLE_RUNWAY, 104.0)
    layout = _FakeLayout([south, north])
    airside = [south, north]
    _shapes, index = GF._conform_index(layout, airside)
    xs = 200.0
    ys = [30.0 + 0.5 * k for k in range(25)]     # 30 -> 42, the sliver
    vals = []
    for y in ys:
        v, d = GF._conform_edge_value(index, xs, y)
        assert v is not None, f"the sliver at y={y} must conform"
        assert d <= MARGIN + 1e-6
        vals.append(v)
    assert 100.0 - 1e-9 <= min(vals) and max(vals) <= 104.0 + 1e-9, (
        "the blend must stay between the two edge values")
    assert vals[0] == pytest.approx(100.0, abs=1e-6), "meets the south edge"
    assert vals[-1] == pytest.approx(104.0, abs=1e-6), "meets the north edge"
    for a, b in zip(vals, vals[1:]):
        assert b >= a - 1e-9, "the blend must not reverse"
    # NO STEP: the largest jump between adjacent 0.5 m samples is a
    # smooth fraction of the 4 m difference, not a cliff.
    assert max(b - a for a, b in zip(vals, vals[1:])) < 1.0


# ══════════════════════════════════════════════════════════════════════
# (d) LAW 3 — the spine descends lawfully and NEVER below terrain
# ══════════════════════════════════════════════════════════════════════

def _plain_frame(length=1300.0, half=87.0):
    y0 = 30.0
    y1 = y0 + 2.0 * half
    return _FakeLayout([
        _rect(0.0, 0.0, length, y0, ROLE_RUNWAY),
        _rect(0.0, y1, length, y1 + 30.0, ROLE_RUNWAY),
        _rect(0.0, y0, 30.0, y1, ROLE_STUB),
        _rect(length - 30.0, y0, length, y1, ROLE_STUB),
    ])


def test_the_spine_never_sits_below_its_own_terrain():
    """The CYXY 60.7124,-135.0802 class: nine nodes stamped flat at
    695.8, 7.7 m under their own 703.5 terrain.  Impossible now."""
    layout = _plain_frame()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    spines = _spines_m(layout)
    assert spines
    checked = 0
    for _pts, vals in spines:
        for v in vals:
            assert v >= 90.0 - 0.01, (
                f"spine node {v} is below its 90.0 terrain")
            checked += 1
    assert checked >= 3


def test_the_spine_descends_no_faster_than_the_lawful_slope():
    layout = _plain_frame()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    spines = _spines_m(layout)
    assert spines
    for pts, vals in spines:
        for (ax, ay), (bx, by), va, vb in zip(pts, pts[1:], vals, vals[1:]):
            d = math.hypot(bx - ax, by - ay)
            if d < 0.1:
                continue
            # Descent is capped; a RISE is terrain and is not capped by
            # this law (the profile follows the ground it meets).
            assert (va - vb) <= CAP * d + 0.06, (
                f"spine drops {va - vb:.2f} m over {d:.1f} m, past the "
                f"{CAP * 100:.0f}% cap")


def test_the_spine_follows_terrain_once_it_meets_it():
    """Flat terrain 10 m below a 100 m pavement: the profile leaves the
    conformed boundary at the cap, reaches 90.0 after ~200 m and then
    IS the terrain — flat, not a canal cut under it."""
    layout = _plain_frame()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    spines = _spines_m(layout)
    assert spines
    allv = [v for _p, vals in spines for v in vals]
    assert min(allv) == pytest.approx(90.0, abs=0.05), (
        "the middle of a long spine must SIT ON terrain")
    assert max(allv) > 90.0 + 1.0, (
        "the ends must still be descending from their conformed boundary")
    # The contact is a floor, not a crossing: nothing dips under it.
    assert all(v >= 90.0 - 0.01 for v in allv)


def test_a_high_knoll_lifts_the_spine_onto_it():
    """Terrain ABOVE the descent is followed, not cut: the profile is a
    max with terrain, so a knoll under the spine raises it."""
    def fn(x, y):
        return 97.0 if 500.0 < x < 800.0 else 90.0
    layout = _plain_frame()
    emit_gap_fill_spines(layout, _StubDem(fn), 0, 0)
    spines = _spines_m(layout)
    assert spines
    on_knoll = [v for pts, vals in spines
                for (x, _y), v in zip(pts, vals) if 520.0 < x < 780.0]
    assert on_knoll, "expected spine stations over the knoll"
    assert min(on_knoll) >= 97.0 - 0.01, (
        "the spine must ride the knoll, never trench through it")


def test_the_late_reclamp_cannot_cut_the_canal_back_open():
    """``reclamp_gap_spines`` re-references the spine against the
    pavement that actually ships — its CEILING is what stamped the
    canal.  The F3 terrain floor published with the emitted way survives
    that pass."""
    layout = _plain_frame()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    before = [list(v) for _p, v in layout.gap_spines]
    GF.reclamp_gap_spines(layout)
    after = [list(v) for _p, v in layout.gap_spines]
    assert len(before) == len(after)
    for vs in after:
        assert all(v >= 90.0 - 0.01 for v in vs), (
            "the re-clamp pushed a spine node back under its terrain")


def test_the_terrain_floor_store_stays_index_aligned():
    """The floor store is only sound if it is index-for-index with
    ``gap_spines`` — every append goes through one helper for exactly
    that reason."""
    layout = _plain_frame()
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    store = getattr(layout, GF._GAP_SPINE_TERRAIN_STORE, None)
    assert store is not None
    assert len(store) == len(layout.gap_spines)
    for (pts_ll, vals), floor in zip(layout.gap_spines, store):
        assert floor is not None
        assert len(floor) == len(vals) == len(pts_ll)
