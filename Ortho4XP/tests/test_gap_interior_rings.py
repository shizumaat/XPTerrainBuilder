"""GAP INTERIOR RINGS (ratified 2026-07-11; ROUND-8 revision: complete
closed loops, value-gated; gate O4_GAP_FILL_INTERIOR_RINGS, chained
under O4_GAP_FILL_SPINE).

Synthetic fixtures only (the test_gap_fill_spine frame pattern): a
rectangular pavement frame enclosing one hole, plus a stub DEM whose
``alt`` drives the per-station value clamp.

Round-8 pins:
  * gate OFF emits no rings and leaves the plain gap-fill path
    untouched; ring gate ON + spine gate OFF is a HARD error;
  * rings emit as COMPLETE CLOSED LOOPS (first node repeats at the
    end) — no arcs, no taper stations, no mid-gap chain ends;
  * station values are clamp(terrain, floor, ceiling) at the
    point-law distances: a deep dip pins AT the floor (fill), lawful
    terrain rides invisibly;
  * a gap whose EVERY station of BOTH rings is a value no-op skips
    its rings entirely (per-gap economy gate, all-or-nothing) and its
    spine emits exactly as gate-OFF;
  * ALONG-RING continuity: adjacent-station value steps are bench- or
    terrain-limited, never a pin-to-terrain cliff;
  * the SPINE is trimmed to the ring-2 core (a full-length spine
    would cross the closed loops at the gap ends);
  * narrow gaps collapse (ladder rung 4): no rings, today's
    spine-only behavior;
  * runway-bounded ring widths key the TRUE ICAO code from runway
    AXES, not the tile-cut segment chord;
  * zero-lens guards: nodes inside the gap, clear of boundary/spine/
    other chains, minimum spacing.
"""
import math

import pytest
from shapely.geometry import LineString, Point, Polygon

from auto_patch import gap_fill as GF
from auto_patch.gap_fill import emit_gap_fill_spines
from auto_patch.grade_law import adjacent_ground_envelope
from auto_patch.layout import BuiltShape, ROLE_RUNWAY, ROLE_STUB

EDGE_ALT = 100.0


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
    """DEM stub: ``alt((dx, dy))`` in tile-offset degrees; the fake
    layout maps x = lon * 111320, y = lat * 111320."""
    def __init__(self, fn):
        self._fn = fn

    def alt(self, t):
        dx, dy = t
        return self._fn(dx * 111320.0, dy * 111320.0)


def _rect(x0, y0, x1, y1, role):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    coords = list(poly.exterior.coords)
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=[EDGE_ALT] * len(coords))


FRAME_LENGTH = 1300.0


def _frame_layout(gap_half_width_m, length=FRAME_LENGTH):
    """Two parallel RUNWAY rects joined by two end STUBS enclosing one
    hole ``2*gap_half_width_m`` across (the test_gap_fill_spine frame)."""
    inner_x0, inner_x1 = 30.0, length - 30.0
    y_bot1 = 30.0
    y_gap0, y_gap1 = y_bot1, y_bot1 + 2.0 * gap_half_width_m
    y_top1 = y_gap1 + 30.0
    shapes = [
        _rect(0.0, 0.0, length, y_bot1, ROLE_RUNWAY),
        _rect(0.0, y_gap1, length, y_top1, ROLE_RUNWAY),
        _rect(0.0, y_gap0, inner_x0, y_gap1, ROLE_STUB),
        _rect(inner_x1, y_gap0, length, y_gap1, ROLE_STUB),
    ]
    return _FakeLayout(shapes)


def _lawful_terrain(gap_half_width_m, length=FRAME_LENGTH):
    """Terrain INSIDE every parent's corridor: edge − 3 %·d − 1 mm,
    ``d`` = distance to the nearest frame inner edge (lawful for the
    runway, taxiway and lip envelopes alike — every station is a value
    no-op, so the economy gate must skip the gap)."""
    y0, y1 = 30.0, 30.0 + 2.0 * gap_half_width_m
    x0, x1 = 30.0, length - 30.0

    def fn(x, y):
        d = max(0.0, min(y - y0, y1 - y, x - x0, x1 - x))
        return EDGE_ALT - 0.03 * d - 0.001
    return _StubDem(fn)


class _FakeRunway:
    """apt.dat runway row stand-in: just the two threshold lat/lons."""
    def __init__(self, x_a, y_a, x_b, y_b):
        self.lat_a, self.lon_a = y_a / 111320.0, x_a / 111320.0
        self.lat_b, self.lon_b = y_b / 111320.0, x_b / 111320.0


def _rings(layout):
    return getattr(layout, "gap_interior_rings", None) or []


def _ring_chains_m(layout):
    out = []
    for pts_ll, alts in _rings(layout):
        out.append(([(lon * 111320.0, lat * 111320.0)
                     for lat, lon in pts_ll], list(alts)))
    return out


_LOW = _StubDem(lambda x, y: 90.0)          # deep dip everywhere


@pytest.fixture
def rings_on(monkeypatch):
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_RINGS_ENABLED", True)


def test_gate_off_emits_no_rings(monkeypatch):
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_RINGS_ENABLED", False)
    layout = _frame_layout(30.0)
    n = emit_gap_fill_spines(layout, _LOW, 0, 0)
    assert n == 1
    assert not _rings(layout)


def test_ring_gate_requires_spine_gate(monkeypatch):
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_RINGS_ENABLED", True)
    monkeypatch.setattr(GF, "GAP_FILL_SPINE_ENABLED", False)
    layout = _frame_layout(30.0)
    with pytest.raises(RuntimeError):
        emit_gap_fill_spines(layout, _LOW, 0, 0)


def test_rings_are_complete_closed_simple_loops(rings_on):
    """Round-8 mandate: complete unbroken closed loops (first node
    repeats at the end, no mid-gap chain ends) — and the ROUND-9 hard
    invariant: every loop is SIMPLE (the polygon-offset construction
    cannot self-cross; a violation is a bug, not a repair case).
    The 174 m frame keeps a 24 m core strip between the two 75 m
    runway bands (wider than twice the minimum-feature radius), so
    ring 2 exists alongside ring 1."""
    from shapely.geometry import LinearRing
    layout = _frame_layout(87.0)
    n = emit_gap_fill_spines(layout, _LOW, 0, 0)
    assert n == 1
    chains = _ring_chains_m(layout)
    assert len(chains) >= 2, "ring 1 + ring 2 loops expected"
    for pts, alts in chains:
        assert len(pts) >= 9
        assert pts[0] == pts[-1], "every ring chain must be CLOSED"
        assert alts[0] == alts[-1]
        assert LinearRing(pts[:-1]).is_simple, (
            "round-9 invariant: emitted loop must be SIMPLE")


def test_deep_dip_conforms_to_the_pavement_edge(rings_on):
    """F3 LAW 1 (owner 2026-08-15, RULINGS "GAP INTERIOR RINGS NEVER
    CLIFF AGAINST PAVEMENT") SUPERSEDES the round-8 floor pin this twin
    used to assert.

    Both emitted loops stand inside the conformance band (ring 1 at the
    3 m lip, ring 2 on the eroded boundary at
    ``GAP_PAVEMENT_CONFORM_MARGIN_M``), so with terrain 10 m below the
    pavement NOT ONE station rides the terrain or pins to the band
    floor: every one takes its nearest pavement edge's SOLVED value.
    That is the ruling — conformance, not terrain — and it is what
    leaves no cliff at the pavement edge to fall off."""
    layout = _frame_layout(87.0)
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    checked = 0
    for pts, alts in _ring_chains_m(layout):
        open_pts = pts[:-1] if pts[0] == pts[-1] else pts
        for (x, y), v in zip(open_pts, alts):
            assert abs(v - EDGE_ALT) <= 0.01, (
                f"band node at ({x:.0f},{y:.0f}) is {v}, not its "
                f"pavement edge's solved {EDGE_ALT}")
            checked += 1
    assert checked >= 40


def test_lawful_terrain_economy_skips_whole_gap(rings_on):
    """Per-gap economy gate (all-or-nothing), re-founded on F3 law 1:
    the ring value is the pavement's, so the gate fires where TERRAIN
    ALREADY IS the pavement value (nothing for a ring to hold) — not
    where terrain merely falls away lawfully, which under the ruling
    still conforms.  No rings, and the spine emits exactly as the
    gate-OFF run (the ring gate must stay value-invisible)."""
    dem = _StubDem(lambda x, y: EDGE_ALT)
    layout_on = _frame_layout(30.0)
    emit_gap_fill_spines(layout_on, dem, 0, 0)
    assert not _rings(layout_on)
    layout_off = _frame_layout(30.0)
    orig = GF.GAP_FILL_INTERIOR_RINGS_ENABLED
    GF.GAP_FILL_INTERIOR_RINGS_ENABLED = False
    try:
        emit_gap_fill_spines(layout_off, dem, 0, 0)
    finally:
        GF.GAP_FILL_INTERIOR_RINGS_ENABLED = orig
    assert layout_on.gap_spines == layout_off.gap_spines


def test_along_ring_continuity(rings_on):
    """Round-8 continuity: adjacent-station value steps are bench- or
    terrain-limited — never a pin-to-terrain cliff.  A hard 9 m step
    in the DEM must NOT appear as a hard step in the ring values."""
    y0 = 30.0

    def fn(x, y):
        if x < 500.0:
            return 90.0                      # deep dip west
        d = max(0.0, min(y - y0, (y0 + 60.0) - y, x - 30.0,
                         (FRAME_LENGTH - 30.0) - x))
        return EDGE_ALT - 0.03 * d - 0.001   # lawful east
    layout = _frame_layout(30.0)
    emit_gap_fill_spines(layout, _StubDem(fn), 0, 0)
    chains = _ring_chains_m(layout)
    assert chains, "engaged west half must emit rings"
    from auto_patch.gap_fill import _RING_ALONG_BENCH_SLOPE
    for pts, alts in chains:
        assert pts[0] == pts[-1], "loops stay closed under partial dip"
        for i in range(1, len(pts)):
            dz = abs(alts[i] - alts[i - 1])
            dd = math.hypot(pts[i][0] - pts[i - 1][0],
                            pts[i][1] - pts[i - 1][1])
            if dd < 0.1:
                continue
            assert dz <= _RING_ALONG_BENCH_SLOPE * dd + 0.75, (
                f"along-ring cliff {dz:.2f} m over {dd:.1f} m at "
                f"({pts[i][0]:.0f},{pts[i][1]:.0f})")


def test_narrow_gap_collapses_to_spine_only(rings_on):
    # 6 m across: not even the lip fits (rung 4) — no rings, and the
    # spine still emits exactly as the plain gap-fill.
    layout = _frame_layout(3.0)
    n = emit_gap_fill_spines(layout, _LOW, 0, 0)
    assert n == 1
    assert not _rings(layout)
    assert getattr(layout, "gap_spines", None)


def test_the_ring_offset_is_the_margin_not_the_runway_code(rings_on):
    """F3 LAW 2 SUPERSEDES the round-9 band-width offset this twin used
    to assert (ring 2 at the runway strip's own graded half-width, keyed
    by the TRUE ICAO code from the runway AXES).

    The emitted ring IS the eroded boundary now — ``pocket.buffer(-
    GAP_PAVEMENT_CONFORM_MARGIN_M)`` — so the SAME frame gives the SAME
    offset whether the runway code comes from a 2000 m axis or from the
    900 m segment chord.  The code source still keys the point-law
    interval for stations OUTSIDE the band; it no longer places the
    ring."""
    length = 900.0
    bottom_edge = LineString([(0.0, 30.0), (length, 30.0)])

    def _offsets(source_runways):
        layout = _frame_layout(87.0, length=length)
        emit_gap_fill_spines(layout, _LOW, 0, 0,
                             source_runways=source_runways)
        return [bottom_edge.distance(Point(x, y))
                for pts, alts in _ring_chains_m(layout)
                for x, y in pts if y < 110.0 and 200 < x < 700]

    axis = _FakeRunway(-600.0, 15.0, 1400.0, 15.0)   # 2000 m axis
    offs = _offsets([axis])
    offs2 = _offsets(None)
    assert offs and offs2, "expected ring nodes off the bottom runway edge"
    margin = GF.GAP_PAVEMENT_CONFORM_MARGIN_M
    for name, got in (("axis code 4", offs), ("chord code 2", offs2)):
        assert abs(max(got) - margin) <= 0.05, (
            f"{name}: ring 2 must stand at the conformance margin "
            f"{margin:.1f} m, got {max(got):.2f}")
    assert max(offs) == pytest.approx(max(offs2), abs=1e-6), (
        "the ring offset must not depend on the runway code source")


def test_ring_zero_lens_guards(rings_on):
    layout = _frame_layout(30.0)
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    gap = Polygon([(30.0, 30.0), (FRAME_LENGTH - 30.0, 30.0),
                   (FRAME_LENGTH - 30.0, 90.0), (30.0, 90.0)])
    chains = _ring_chains_m(layout)
    assert chains
    spine_lines = []
    for pts_ll, vals in layout.gap_spines:
        pts = [(lon * 111320.0, lat * 111320.0) for lat, lon in pts_ll]
        if len(pts) >= 2:
            spine_lines.append(LineString(pts))
    for pts, alts in chains:
        open_pts = pts[:-1] if pts[0] == pts[-1] else pts
        for i, p in enumerate(open_pts):
            assert gap.buffer(1e-6).contains(Point(p))
            assert gap.exterior.distance(Point(p)) >= 1.4
            for sls in spine_lines:
                assert sls.distance(Point(p)) >= 1.4
            if i:
                assert math.hypot(p[0] - open_pts[i - 1][0],
                                  p[1] - open_pts[i - 1][1]) >= 1.9


def test_spine_trimmed_to_ring_core(rings_on):
    """Round-9: the spine is cut back to the innermost region — the
    core when ring 2 exists (a full-length spine would cross the
    closed loops at the gap ends); every surviving node keeps 2 m off
    every loop."""
    layout = _frame_layout(87.0)
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    assert _rings(layout)
    # Gap spans y in [30, 204]; the core strip (between the 75 m
    # runway bands) is y in [105, 129] — every surviving spine node
    # sits inside it, 2 m clear of every loop.
    ring_chains = [LineString(pts) for pts, _a in _ring_chains_m(layout)]
    kept = 0
    for pts_ll, vals in layout.gap_spines:
        for lat, lon in pts_ll:
            x, y = lon * 111320.0, lat * 111320.0
            assert 104.0 < y < 130.0, (
                "spine node left the core strip after the trim")
            for rc in ring_chains:
                assert rc.distance(Point(x, y)) >= 1.9
            kept += 1
    assert kept >= 3


def test_a_pocket_narrower_than_twice_the_margin_is_pure_band(rings_on):
    """F3 LAW 2, the erosion rung — SUPERSEDES the round-9
    "zones-fully-overlap" rung this twin used to assert (a 60 m gap
    swallowed whole by the 75 m runway bands, ring 1 alone).

    "Lobes narrower than 2x margin erode away entirely and are pure
    conformance band."  An 18 m gap has no interior at all: the eroded
    region is empty, so there is no ring-2 loop and nothing may descend
    to terrain — and the drainage spine still emits, untrimmed."""
    margin = GF.GAP_PAVEMENT_CONFORM_MARGIN_M
    layout = _frame_layout(0.5 * 18.0)              # 18 m < 2 x margin
    n = emit_gap_fill_spines(layout, _LOW, 0, 0)
    assert n == 1
    gap = Polygon([(30.0, 30.0), (FRAME_LENGTH - 30.0, 30.0),
                   (FRAME_LENGTH - 30.0, 48.0), (30.0, 48.0)])
    assert gap.buffer(-margin).is_empty, "fixture: the interior must erode away"
    assert not [c for c in _ring_chains_m(layout)], (
        "a pocket narrower than twice the margin is pure conformance band")
    assert getattr(layout, "gap_spines", None), "crest spine must survive"


def test_spine_recouples_to_ring_two_ceiling(rings_on):
    # With the deep dip every ring-2 node is floor-ENGAGED; the
    # surviving (trimmed) spine nodes must not exceed the highest
    # emitted ring-2 value (ring 2 is the spine ceiling in the core).
    layout = _frame_layout(87.0)
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    chains = _ring_chains_m(layout)
    assert chains
    ring_max = max(a for _pts, alts in chains for a in alts)
    checked = 0
    for pts_ll, vals in layout.gap_spines:
        for v in vals:
            checked += 1
            assert v <= ring_max + 0.15, (
                f"spine node above the ring ceiling: {v} > {ring_max}")
    assert checked >= 3


def test_polygon_offset_multi_component(rings_on):
    """Round-9 geometry law, re-founded on F3 law 2: a dumbbell gap —
    two wide lobes joined by a neck narrower than TWICE THE CONFORMANCE
    MARGIN (the erosion's own threshold now, no longer the runway band)
    — splits its eroded interior into components, each getting its own
    SIMPLE closed collar loop."""
    from shapely.geometry import LinearRing
    # Frame with a mid-frame PLUG narrowing the gap: two 174 m lobes
    # joined by a 16 m neck (under 2 x GAP_PAVEMENT_CONFORM_MARGIN_M).
    length = FRAME_LENGTH
    y_gap0, y_gap1 = 30.0, 204.0
    neck = 16.0
    assert neck < 2.0 * GF.GAP_PAVEMENT_CONFORM_MARGIN_M
    shapes = [
        _rect(0.0, 0.0, length, 30.0, ROLE_RUNWAY),
        _rect(0.0, y_gap1, length, y_gap1 + 30.0, ROLE_RUNWAY),
        _rect(0.0, y_gap0, 30.0, y_gap1, ROLE_STUB),
        _rect(length - 30.0, y_gap0, length, y_gap1, ROLE_STUB),
        # the plug: pavement tooth from the bottom leaving the neck
        _rect(600.0, y_gap0, 700.0, y_gap1 - neck, ROLE_STUB),
    ]
    layout = _FakeLayout(shapes)
    n = emit_gap_fill_spines(layout, _LOW, 0, 0)
    assert n == 1
    chains = _ring_chains_m(layout)
    # ring-2 collars: the core splits into (at least) the two lobes.
    core_loops = 0
    for pts, alts in chains:
        assert pts[0] == pts[-1]
        assert LinearRing(pts[:-1]).is_simple
        xs = [p[0] for p in pts]
        if max(xs) - min(xs) < 560.0:      # a lobe collar, not ring 1
            core_loops += 1
    assert core_loops >= 2, (
        f"dumbbell core must split into per-lobe collars, chains="
        f"{[(len(p), max(px[0] for px in p) - min(px[0] for px in p)) for p, _a in chains]}")


def test_smoothing_does_not_trace_boundary_notches(rings_on):
    """Round-9 (Noah's reference loop class — smooth, no notch
    tracing): a small pavement jag in the gap boundary must not
    densify or wiggle the loop (no tracing), the loop must stay
    SIMPLE, and no chord may cut into pavement (no foreign-crossing
    mint at the concave detail)."""
    from shapely.geometry import LinearRing
    from auto_patch.gap_fill import GAP_FILL_SPINE_STEP_M as _step
    length = FRAME_LENGTH
    y_gap0, y_gap1 = 30.0, 204.0
    tooth = _rect(647.0, 30.0, 653.0, 34.0, ROLE_STUB)  # 6 m x 4 m jag
    shapes = [
        _rect(0.0, 0.0, length, 30.0, ROLE_RUNWAY),
        _rect(0.0, y_gap1, length, y_gap1 + 30.0, ROLE_RUNWAY),
        _rect(0.0, y_gap0, 30.0, y_gap1, ROLE_STUB),
        _rect(length - 30.0, y_gap0, length, y_gap1, ROLE_STUB),
        tooth,
    ]
    layout = _FakeLayout(shapes)
    emit_gap_fill_spines(layout, _LOW, 0, 0)
    chains = _ring_chains_m(layout)
    assert chains
    for pts, alts in chains:
        ring = LinearRing(pts[:-1])
        assert ring.is_simple
        # No tracing densification: node economy stays at the step
        # (a traced notch adds a cluster of short segments).
        assert len(pts) - 1 <= ring.length / _step + 6
        # No chord cuts into the jag pavement.
        loop_ls = LineString(pts)
        assert not loop_ls.crosses(tooth.polygon), (
            "ring chord cut into the boundary jag")
