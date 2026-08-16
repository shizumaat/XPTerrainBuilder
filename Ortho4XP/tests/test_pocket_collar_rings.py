"""Pocket collar rings (arc B1) + pit floor v2 (arc B2), owner ruling
2026-07-24.

    "we should be able to identify when there's a significant drop in the
     center of an enclosed area, but first there should be two fully
     enclosed rings of adjacent ground covering the necessary drainage
     slope rules per zone, THEN the gap pit in the middle."

Synthetic headless fixtures only (no airport build), mirroring
``test_gap_interior_floor``'s frame pattern: a rectangular pavement frame
encloses ONE hole that is deliberately WIDER than
``GAP_FILL_MAX_WIDTH_M`` so the drainage-spine emitter width-skips it —
the pocket class arc B is about.  A fake DEM plants lawful-but-low
terrain (so the collar rings engage) plus a genuine artifact pit in the
middle (so the v2 pit pass fires).

The pavement is deliberately NOT flat (edge altitude rises 1 % with x):
that is what makes the ring-2 law surface — and therefore the LOCAL pit
floor derived from it — a FIELD rather than one number, which is the
whole point of arc B2's reference change.
"""
import math

import pytest
from shapely.geometry import Point, Polygon

from auto_patch import gap_fill as GF
from auto_patch import elevation as ELEV
from auto_patch.gap_fill import (
    _GAP_PIT_FLOOR_REF,
    emit_gap_fill_spines,
    emit_gap_interior_floor,
)
from auto_patch.layout import BuiltShape, ROLE_GRADED_STRIP, ROLE_RUNWAY

# ── Fixture geometry ──────────────────────────────────────────────────
# Hole = (60, 60)-(760, 460): 700 x 400 m, so the SHORT dimension (400 m)
# is far over GAP_FILL_MAX_WIDTH_M (175 m) — a width-skipped pocket.
HOLE = (60.0, 60.0, 760.0, 460.0)
PIT_CENTER = (410.0, 260.0)
PIT_FLAT_R = 40.0          # depth is at its maximum inside this radius
PIT_TOE_R = 120.0          # depth reaches zero here
PIT_DEPTH_M = 8.0

# Pavement edge altitude and the terrain that hangs off it.
#
# RECALIBRATED for F3 law 1 (owner 2026-08-15, RULINGS "GAP INTERIOR
# RINGS NEVER CLIFF AGAINST PAVEMENT").  Ring 2 no longer stands on the
# band floor (edge - 1.5 at the old 30 m offset): it stands on the
# ERODED boundary, inside the conformance band, so its value IS the
# pavement edge's.  The v2 pit floor derived from it is therefore
# (edge - GAP_FILL_INTERIOR_FLOOR_DEPTH_M) = edge - 2.5.  The terrain
# now sits 2 m under the edge — below the ring (every station engages,
# no economy skip), deep enough that the adjacent-ground band march
# still builds real footprint inside the pocket (the stand-down twin),
# and ABOVE the pit floor, so nothing outside the artifact pit triggers
# the pass and the patch's rim still daylights onto natural ground.
def _edge_alt(x: float) -> float:
    return 98.0 + 0.01 * x


def _base_terrain(x: float) -> float:
    return _edge_alt(x) - 2.0


def _terrain(x: float, y: float) -> float:
    r = math.hypot(x - PIT_CENTER[0], y - PIT_CENTER[1])
    if r <= PIT_FLAT_R:
        d = PIT_DEPTH_M
    elif r >= PIT_TOE_R:
        d = 0.0
    else:
        d = PIT_DEPTH_M * (PIT_TOE_R - r) / (PIT_TOE_R - PIT_FLAT_R)
    return _base_terrain(x) - d


class _FakeLayout:
    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)

    def ll_to_m(self, lat, lon):
        return (lon * 111320.0, lat * 111320.0)

    def __init__(self, shapes):
        self.shapes = shapes
        self.airport_boundary = None
        self.anchor = (0.0, 0.0)


def _rect(x0, y0, x1, y1, role=ROLE_RUNWAY):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    coords = list(poly.exterior.coords)
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=[_edge_alt(vx) for vx, _vy in coords])


def _frame_layout():
    """Pavement frame around the wide hole."""
    x0, y0, x1, y1 = HOLE
    return _FakeLayout([
        _rect(0, 0, 820, y0),             # south
        _rect(0, y1, 820, y1 + 60),       # north
        _rect(0, y0, x0, y1),             # west
        _rect(x1, y0, 820, y1),           # east
    ])


def _fake_sample_dem(dem, tile_lat, tile_lon, lat, lon):
    return _terrain(lon * 111320.0, lat * 111320.0)


def _dem_at(x, y):
    return _terrain(x, y)


def _pit_patches(layout):
    return [s for s in layout.shapes
            if getattr(s, "ref", None) == _GAP_PIT_FLOOR_REF]


def _run(monkeypatch, *, collar: bool, interior_floor: bool = True):
    """Build the fixture and run both gap passes.

    ``interior_floor`` forces ``GAP_FILL_INTERIOR_FLOOR_ENABLED`` on by
    default so the B2 pit-floor tests below keep exercising the pass.
    That pass is DISABLED in shipped config by owner ruling 2026-07-24
    ("once we're past the grade law zones on a large infield, we want to
    blend back into DEM"), but the code is retained for a future
    narrower re-enable, so its behaviour still needs covering — the
    ruling is about the DEFAULT, not about the pass being wrong.
    ``test_interior_floor_is_disabled_by_default`` pins the default.
    """
    monkeypatch.setattr(ELEV, "_sample_dem", _fake_sample_dem)
    monkeypatch.setattr(GF, "POCKET_COLLAR_RINGS_ENABLED", collar)
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_FLOOR_ENABLED",
                        interior_floor)
    layout = _frame_layout()
    faces = emit_gap_fill_spines(layout, dem=object(), tile_lat=0,
                                 tile_lon=0)
    pits = emit_gap_interior_floor(layout, dem=object(), tile_lat=0,
                                   tile_lon=0)
    return layout, faces, pits


# ══════════════════════════════════════════════════════════════════════
# Owner ruling 2026-07-24 — nothing overrides the DEM past the zones
# ══════════════════════════════════════════════════════════════════════

def test_interior_floor_is_disabled_by_default(monkeypatch):
    """SHIPPED CONFIG: past the grade-law zones a large infield blends
    back into the DEM, so the interior-floor pass emits nothing at all.

    This restores the round-8 interior-rings design ("Terrain INSIDE ring
    2 stays open-floor — large infields lawfully follow terrain"), which
    the 2026-07-19 floor pass had contradicted.  Pinned as a test because
    it is a RULING, not a tuning default: re-enabling wants an enclosure
    test, not a flip of this switch.
    """
    from auto_patch.config import GAP_FILL_INTERIOR_FLOOR_ENABLED
    assert GAP_FILL_INTERIOR_FLOOR_ENABLED is False
    layout, _faces, pits = _run(monkeypatch, collar=True,
                                interior_floor=False)
    assert pits == 0
    assert _pit_patches(layout) == []


def test_collar_survives_the_interior_floor_ruling(monkeypatch):
    """The ruling disables the CORE fill only — the collar rings still
    carry the per-zone drainage law off the pocket's own pavement ring,
    so the graded slope down from pavement is unaffected."""
    layout, _faces, pits = _run(monkeypatch, collar=True,
                                interior_floor=False)
    rings = getattr(layout, "gap_interior_rings", None) or []
    assert len(rings) >= 2, "collar rings are not part of the ruling"
    assert pits == 0


# ══════════════════════════════════════════════════════════════════════
# B1 — collar rings for the width-skipped pocket
# ══════════════════════════════════════════════════════════════════════

def test_width_skipped_pocket_is_not_spine_treated(monkeypatch):
    """Guard on the fixture itself: the pocket must be WIDTH-skipped, so
    no gap-fill face is emitted for it in either regime."""
    _layout, faces, _pits = _run(monkeypatch, collar=False)
    assert faces == 0


def test_collar_emits_two_closed_rings(monkeypatch):
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    rings = getattr(layout, "gap_interior_rings", None) or []
    assert len(rings) >= 2, "the pocket owes ring 1 AND ring 2"
    for pts_ll, alts in rings:
        # ROUND-8 semantics: complete, unbroken CLOSED loops — never
        # per-arc runs.
        assert len(pts_ll) >= 5
        assert pts_ll[0] == pts_ll[-1]
        assert len(alts) == len(pts_ll)
        assert alts[0] == alts[-1]
        assert all(a is not None for a in alts)


def test_collar_publishes_a_core_record(monkeypatch):
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    store = getattr(layout, GF._POCKET_COLLAR_STORE, None)
    assert store and len(store) == 1
    rec = store[0]
    assert rec["core"] is not None and not rec["core"].is_empty
    assert rec["ring2"], "the ring-2 stations are the pit pass's law"
    # The core is strictly INSIDE the pocket (band annulus removed).
    assert rec["core"].area < rec["pocket"].area
    assert rec["pocket"].buffer(1e-6).covers(rec["core"])


def test_collar_gate_off_emits_nothing(monkeypatch):
    layout, _faces, _pits = _run(monkeypatch, collar=False)
    assert not (getattr(layout, "gap_interior_rings", None) or [])
    assert not (getattr(layout, GF._POCKET_COLLAR_STORE, None) or [])


# ══════════════════════════════════════════════════════════════════════
# B2 — pit floor v2
# ══════════════════════════════════════════════════════════════════════

def test_pit_v2_patch_slopes_and_daylights(monkeypatch):
    layout, _faces, n_pits = _run(monkeypatch, collar=True)
    patches = _pit_patches(layout)
    assert n_pits == len(patches) >= 1, "a genuine artifact pit is filled"
    store = getattr(layout, GF._POCKET_COLLAR_STORE)
    core = store[0]["core"]
    covered = any(p.polygon.contains(Point(*PIT_CENTER)) for p in patches)
    assert covered, "the pit center must be inside a v2 patch"
    for p in patches:
        assert p.role == ROLE_GRADED_STRIP
        alts = p.node_altitudes
        # NOT a flat plateau — the 2026-07-19 [round(floor,2)]*n is gone.
        assert len(set(alts)) > 1
        assert max(alts) - min(alts) > 0.5, (
            "values must slope with the LOCAL ring-2 floor field")
        # SCOPE: inside the ring-2 core only.
        assert core.buffer(1e-6).covers(p.polygon)
        # RIM ON THE DAYLIGHT CONTOUR: every rim vertex meets natural
        # ground (no wall) — the patch value equals the DEM there.
        ring = list(p.polygon.exterior.coords)[:-1]
        assert len(ring) == len(alts) - 1
        steps = [abs(a - _dem_at(vx, vy))
                 for a, (vx, vy) in zip(alts, ring)]
        assert max(steps) < 0.5, (
            f"rim must daylight; worst step {max(steps):.2f} m")


def test_pit_v2_footprint_is_not_an_axis_aligned_staircase(monkeypatch):
    """The 2026-07-19 footprint was a union of axis-aligned sample cells:
    every edge bearing piled at 0 deg / 90 deg.  The morphological
    open/close at the rings' minimum-feature radius must break that."""
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    patches = _pit_patches(layout)
    assert patches
    ring = list(patches[0].polygon.exterior.coords)
    orthogonal = 0
    total = 0
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        if math.hypot(bx - ax, by - ay) < 1e-9:
            continue
        total += 1
        ang = math.degrees(math.atan2(by - ay, bx - ax)) % 90.0
        if min(ang, 90.0 - ang) < 2.0:
            orthogonal += 1
    assert total >= 8
    assert orthogonal / total < 0.5, (
        f"{orthogonal}/{total} edges are axis-aligned — still a staircase")


def test_pit_v2_reference_is_local_not_a_pocket_median(monkeypatch):
    """The retired pass took the MEDIAN pavement value over the whole
    pocket ring.  Here the pavement rises 1 % across 820 m, so a median
    reference would put the floor metres away from the local law
    surface.  v2's patch must track the LOCAL ring-2 value: the west
    side of the pit must sit clearly below the east side."""
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    patches = _pit_patches(layout)
    assert patches
    p = max(patches, key=lambda s: s.polygon.area)
    ring = list(p.polygon.exterior.coords)[:-1]
    alts = p.node_altitudes[:-1]
    west = [a for a, (vx, _vy) in zip(alts, ring)
            if vx < PIT_CENTER[0] - 40.0]
    east = [a for a, (vx, _vy) in zip(alts, ring)
            if vx > PIT_CENTER[0] + 40.0]
    assert west and east
    assert sum(east) / len(east) - sum(west) / len(west) > 0.8


def test_pit_v2_welds_exactly_no_standoff(monkeypatch):
    """The retired pass inset the patch by ``buffer(-0.5)`` off the
    pocket and stood ``buffer(0.25)`` off every other shape — the groove
    class the 2026-07-09 weld ruling exists to kill.  v2 clips EXACTLY:
    the patch reaches its scope boundary."""
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    store = getattr(layout, GF._POCKET_COLLAR_STORE)
    core = store[0]["core"]
    patches = _pit_patches(layout)
    assert patches
    # The pit is interior here, so the test is that no shrink was
    # applied: the detected region's own area survives intact (a
    # buffer(-0.5) inset of a ~38,000 m2 disc would cost ~2 %).
    total = sum(p.polygon.area for p in patches)
    assert total > 0.9 * math.pi * PIT_TOE_R ** 2 * 0.55
    assert core.buffer(1e-6).covers(patches[0].polygon)


def test_pit_v2_welds_to_ring_two_where_it_reaches_the_collar(monkeypatch):
    """When the depression fills the WHOLE ring-2 core the pit rim IS the
    collar boundary.  The neighbouring surface there is not raw DEM — it
    is ring 2, a constrained breakline carrying the law value at that
    coordinate — so the rim must adopt the RING value, not (ring −
    depth).  A floor-pinned rim would put two values on one node over
    the entire shared frontage: the node-split wall the 2026-07-09 weld
    ruling forbids."""
    def _uniform_low(dem, tla, tlo, lat, lon):
        return _base_terrain(lon * 111320.0) - 6.0

    monkeypatch.setattr(ELEV, "_sample_dem", _uniform_low)
    monkeypatch.setattr(GF, "POCKET_COLLAR_RINGS_ENABLED", True)
    # The pit pass ships DISABLED (owner ruling 2026-07-24) — force it on
    # so this B2 behaviour test still exercises it.  See ``_run``.
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_FLOOR_ENABLED", True)
    layout = _frame_layout()
    emit_gap_fill_spines(layout, dem=object(), tile_lat=0, tile_lon=0)
    n = emit_gap_interior_floor(layout, dem=object(), tile_lat=0,
                                tile_lon=0)
    patches = _pit_patches(layout)
    assert n == len(patches) >= 1
    rec = getattr(layout, GF._POCKET_COLLAR_STORE)[0]
    stations = rec["ring2"]
    assert stations
    depth = GF.GAP_FILL_INTERIOR_FLOOR_DEPTH_M
    for p in patches:
        ring = list(p.polygon.exterior.coords)[:-1]
        alts = p.node_altitudes[:-1]
        for a, (vx, vy) in zip(alts, ring):
            if rec["core"].boundary.distance(Point(vx, vy)) > 0.01:
                continue                     # daylight rim, not a weld
            near = min(stations, key=lambda r: (r["pt"][0] - vx) ** 2
                                               + (r["pt"][1] - vy) ** 2)
            law = float(near.get("benched", near["v"]))
            assert abs(a - law) < 1.0, (
                f"rim at ({vx:.0f},{vy:.0f}) is {a:.2f}, law {law:.2f}")
            assert a - (law - depth) > 0.5 * depth, (
                "the welded rim must sit at the ring value, not the floor")


def test_lawful_terrain_emits_no_pit(monkeypatch):
    """No-op economy survives the rewrite: with the artifact pit removed
    the collar still emits, but no pit patch does."""
    monkeypatch.setattr(
        ELEV, "_sample_dem",
        lambda dem, tla, tlo, lat, lon: _base_terrain(lon * 111320.0))
    monkeypatch.setattr(GF, "POCKET_COLLAR_RINGS_ENABLED", True)
    layout = _frame_layout()
    emit_gap_fill_spines(layout, dem=object(), tile_lat=0, tile_lon=0)
    assert getattr(layout, "gap_interior_rings", None)
    assert emit_gap_interior_floor(layout, dem=object(), tile_lat=0,
                                   tile_lon=0) == 0
    assert not _pit_patches(layout)


def test_depth_zero_still_kills_the_pass(monkeypatch):
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_FLOOR_DEPTH_M", 0.0)
    layout, _faces, n = _run(monkeypatch, collar=True)
    assert n == 0
    assert not _pit_patches(layout)


# ══════════════════════════════════════════════════════════════════════
# Gate-off regression: the 2026-07-19 behaviour is preserved verbatim
# ══════════════════════════════════════════════════════════════════════

def test_gate_off_keeps_the_flat_whole_pocket_clamp(monkeypatch):
    """With the arc-B gate OFF the pocket must still get the 2026-07-19
    treatment: a FLAT patch at (pocket-median lip - depth)."""
    layout, _faces, n = _run(monkeypatch, collar=False)
    patches = _pit_patches(layout)
    assert n == len(patches) >= 1
    for p in patches:
        assert len(set(p.node_altitudes)) == 1, "the legacy patch is flat"


# ══════════════════════════════════════════════════════════════════════
# B1 STAND-DOWN — the collared pocket is the COLLAR's ground, never the
# adjacent-ground bands'
#
# The bands' own "covered frontage" mechanism is a 1.5 m outward probe
# against the shape union: a TREATED gap has a face, so it stands the
# bands down, but a WIDTH-SKIPPED pocket has no face and nothing stood
# them down — at SPJC collar ring 1 sat 3 m out while the bands covered
# the first ~10 m, and the double-cover crashes X-Plane.  The fix mirrors
# the crossing-influence-zone pattern: gap_fill PUBLISHES the collared
# pockets, adjacent_ground CONSUMES the zone in both halves (station
# march + polygon clip).
# ══════════════════════════════════════════════════════════════════════

def _south_frame_shape(layout):
    """The frame's SOUTH bar — its north edge (y = 60) is pocket frontage."""
    return layout.shapes[0]


def _march(layout, shape, collar_prep):
    """Run the emitter's shared station march for one frame bar.

    Returns the raw ``_derive_shape_stations_and_bands`` tuple.  The
    envelope functions are the taxiway-C set the other adjacent-ground
    unit tests use — this exercise is about WHICH stations survive, not
    about the corridor numbers."""
    from shapely.ops import unary_union
    from shapely.prepared import prep

    from auto_patch import adjacent_ground as AG
    from auto_patch.config import (CLEARANCE_MAX_REACH_M,
                                   CLEARANCE_STATION_STEP_M,
                                   taxiway_strip_graded_half_width_for_letter)
    from auto_patch.grade_law import adjacent_ground_envelope

    width = taxiway_strip_graded_half_width_for_letter("C")
    reach = CLEARANCE_MAX_REACH_M["taxiway"]

    def ceil_off(d):
        return adjacent_ground_envelope("taxiway", None, "C", d)[1]

    def floor_depth(d):
        f = adjacent_ground_envelope("taxiway", None, "C",
                                     min(d, width))[0]
        return None if f is None else -f

    others = [s.polygon for s in layout.shapes if s is not shape
              and s.polygon is not None and not s.polygon.is_empty]
    prep_static = prep(unary_union(others))
    coords = list(shape.polygon.exterior.coords)
    return AG._derive_shape_stations_and_bands(
        coords, bool(shape.polygon.exterior.is_ccw),
        list(shape.node_altitudes), None, width, reach, 1.0,
        floor_depth, ceil_off, CLEARANCE_STATION_STEP_M, prep_static,
        set(), _dem_at, collar_zone_prep=collar_prep)


def _pocket_facing_refs(stations, st_alts):
    """References kept by stations sitting on the pocket frontage (the
    south bar's north edge, y = 60, between the pocket's x limits)."""
    x0, _y0, x1, y1 = HOLE
    return sum(1 for (sx, sy), a in zip(stations, st_alts)
               if a is not None and abs(sy - HOLE[1]) < 1e-6
               and x0 < sx < x1)


def test_collar_publishes_a_pocket_zone(monkeypatch):
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    union = GF.collared_pocket_zone_union(layout)
    assert union is not None and not union.is_empty
    # The zone IS the pocket — no buffer, no reconstruction.
    rec = getattr(layout, GF._POCKET_COLLAR_STORE)[0]
    assert abs(union.area - rec["pocket"].area) < 1e-6
    assert GF.collared_pocket_zone_prepared(layout) is not None


def test_collar_gate_off_publishes_no_zone(monkeypatch):
    """Gate OFF: nothing collared, so the zone is ``None`` and every
    pocket-facing station stays GOVERNED by the bands."""
    layout, _faces, _pits = _run(monkeypatch, collar=False)
    assert GF.collared_pocket_zone_union(layout) is None
    assert GF.collared_pocket_zone_prepared(layout) is None
    shape = _south_frame_shape(layout)
    _f, _c, stations, st_alts, _o = _march(layout, shape, None)
    assert _pocket_facing_refs(stations, st_alts) > 0


def test_collared_pocket_stands_the_band_march_down(monkeypatch):
    """The march half: pocket-facing stations lose their reference (and
    with it their band geometry AND their corner fans) once the zone is
    published, while frontage AWAY from the pocket is untouched."""
    from auto_patch import adjacent_ground as AG
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    shape = _south_frame_shape(layout)
    prep_zone = AG._collar_zone_prep(layout)     # the consumer's wrapper
    assert prep_zone is not None

    _f0, _c0, st0, alts0, _o0 = _march(layout, shape, None)
    f1, c1, st1, alts1, _o1 = _march(layout, shape, prep_zone)

    assert _pocket_facing_refs(st0, alts0) > 0
    assert _pocket_facing_refs(st1, alts1) == 0
    # Only the pocket frontage stood down: the bar's SOUTH edge (y = 0)
    # faces open terrain and keeps every reference it had.
    def _south_refs(stations, st_alts):
        return sum(1 for (_sx, sy), a in zip(stations, st_alts)
                   if a is not None and abs(sy) < 1e-6)
    assert _south_refs(st1, alts1) == _south_refs(st0, alts0)
    # Band FOOTPRINT inside the pocket all but vanishes.  What is left is
    # the two run-END quads of the last kept station at each pocket corner
    # (its probe lands exactly ON the pocket boundary, so the point test
    # cannot drop it) — the polygon clip below is what removes those, and
    # is why BOTH halves exist.
    pocket = getattr(layout, GF._POCKET_COLLAR_STORE)[0]["pocket"]

    def _inside_area(bands):
        total = 0.0
        for ring, _alts in bands:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            total += poly.intersection(pocket).area
        return total
    before = _inside_area(_f0 + _c0)
    after = _inside_area(f1 + c1)
    assert before > 1000.0
    assert after < 0.02 * before


def test_economy_skipped_collar_keeps_its_bands():
    """A record is published even when ZERO chains emit (the round-8
    economy gate / no collar region) — such a pocket is still the bands'
    ground, so it must stay OUT of the zone."""
    import types
    pocket = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    lay = types.SimpleNamespace(shapes=[])
    setattr(lay, GF._POCKET_COLLAR_STORE,
            [{"pocket": pocket, "core": None, "ring2": [], "chains": 0,
              "nodes": 0}])
    assert GF.collared_pocket_zone_union(lay) is None
    # The SAME record with one emitted chain publishes the pocket.
    getattr(lay, GF._POCKET_COLLAR_STORE)[0]["chains"] = 1
    union = GF.collared_pocket_zone_union(lay)
    assert union is not None
    assert abs(union.area - pocket.area) < 1e-6


def test_collar_zone_clips_a_band_polygon_exactly(monkeypatch):
    """The clip half — the only protection under the frozen-footprint
    gate state, where the station march is not re-run.  EXACT pocket,
    ZERO buffer (weld ruling 2026-07-09: no standoff grooves)."""
    from auto_patch import adjacent_ground as AG
    layout, _faces, _pits = _run(monkeypatch, collar=True)
    # Through the CONSUMER's wrapper — the emitter builds its clip block
    # from this one published geometry, never from its own reconstruction.
    union = AG._collar_zone_union(layout)
    assert union is not None
    x0, y0, x1, _y1 = HOLE
    # A band hugging the south bar's north edge and marching 40 m in.
    band = Polygon([(x0 + 50, y0 - 5), (x1 - 50, y0 - 5),
                    (x1 - 50, y0 + 40), (x0 + 50, y0 + 40)])
    assert band.intersects(union)
    clipped = band.difference(union)
    # Exact difference: nothing is lost beyond the overlap itself.
    assert abs(clipped.area
               - (band.area - band.intersection(union).area)) < 1e-6
    # And nothing survives INSIDE the pocket.
    assert clipped.intersection(union.buffer(-0.01)).is_empty
