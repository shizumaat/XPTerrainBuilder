"""Adjacent-ground BAND RAY OCCLUSION (owner ruling 2026-07-25:
"Yes for adjacent ground using a ray occlusion, it should stop at
pavement"; gate ``O4_BAND_RAY_OCCLUSION``).

THE LAW: a lateral band's outward reach is measured through FREE GROUND
ONLY — each station's outward march terminates at the first sample whose
point falls inside the static pavement union, and the station's band depth
becomes the last free-ground sample before that hit.

Diagnosed at CYXY shapeID 395: junction 129's deep cut slab marched
straight THROUGH apron 132 + junction 131 (the lidar reads the built apron
bench as "terrain needing a cut", so daylight never closed) and the
after-the-fact exact clip ``poly.difference(static_union)`` left the band
wrapping the apron's NE corner with a ~1 m drop hugging its edge.

Cases pinned here:

  * the helper's own contract — hit at 30 m of a 100 m reach ⇒ limit 25 m
    (the last free-ground sample), clear ray ⇒ +inf, first sample already
    inside ⇒ 0.0, nothing occluded ⇒ ``None`` (the builders' no-op path);
  * the vectorized containment IS the naive per-sample
    ``prep.contains(Point)`` (equivalence of the build-time guard);
  * CUT and FILL band depth clamped at the occluder, on the shared
    ``_derive_shape_stations_and_bands`` march both the pre-solve
    constructor and the post-solve emit re-march run through;
  * gate OFF ⇒ byte-identical bands;
  * VALIDATOR LOCKSTEP (MIRROR 5): with the emitter stopping at the
    pavement, ``verification.check_adjacent_ground`` must stop there too —
    no should_fill/should_cut minted beyond an occluding pavement — while
    still flagging the un-emitted breach INSIDE the free-ground reach.
"""
import math

import pytest
from shapely.geometry import Point, Polygon
from shapely.prepared import prep

from auto_patch import adjacent_ground as AG
from auto_patch import config as CFG
from auto_patch import elevation, verification
from auto_patch.apt_dat_reader import Runway
from auto_patch.config import (
    CLEARANCE_MAX_REACH_M,
    CLEARANCE_STATION_STEP_M,
)
from auto_patch.grade_law import adjacent_ground_envelope
from auto_patch.layout import BuiltShape, PavementLayout, R_EARTH

STEP = CLEARANCE_STATION_STEP_M            # 5.0 m
EDGE_ALT = 100.0
TRIGGER = 1.0


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    """These cases are ABOUT the feature, so pin the gate ON regardless of
    the environment the suite runs under (the two gate-OFF cases below
    monkeypatch it back down themselves — a later setattr wins)."""
    monkeypatch.setattr(AG, "_RAY_OCCLUSION", True)
    monkeypatch.setattr(CFG, "BAND_RAY_OCCLUSION_ENABLED", True)



# ══════════════════════════════════════════════════════════════════════
# 1. The helper contract
# ══════════════════════════════════════════════════════════════════════
def _one_station(cap=100.0):
    """One station at the origin marching +y with a ``cap`` m reach."""
    return [(0.0, 0.0)], [(0.0, 1.0)], [cap]


def test_hit_at_30_of_100_gives_last_free_sample():
    # Occluder from y = 48: the first sample INSIDE is d = 30 (y = 30 is
    # not, y = 30 is below 48 — the first inside sample is d = 50).  Use a
    # slab starting at 28 so the first inside sample is exactly d = 30.
    occluder = Polygon([(-50.0, 28.0), (50.0, 28.0),
                        (50.0, 60.0), (-50.0, 60.0)])
    st, outs, caps = _one_station()
    limits = AG._station_occlusion_limits(
        st, outs, caps, STEP, prep(occluder))
    assert limits is not None
    # First sample inside is d = 30 (y = 30 ∈ [28, 60]); the last
    # free-ground sample is d = 25.
    assert limits[0] == pytest.approx(25.0)
    assert limits[0] <= 30.0


def test_clear_ray_is_unbounded():
    aside = Polygon([(-200.0, -50.0), (-150.0, -50.0),
                     (-150.0, 50.0), (-200.0, 50.0)])
    st, outs, caps = _one_station()
    limits = AG._station_occlusion_limits(
        st, outs, caps, STEP, prep(aside))
    # Nothing occluded ⇒ None, the builders' structural no-op path.
    assert limits is None


def test_first_sample_inside_gives_zero_depth():
    occluder = Polygon([(-50.0, 1.0), (50.0, 1.0),
                        (50.0, 60.0), (-50.0, 60.0)])
    st, outs, caps = _one_station()
    limits = AG._station_occlusion_limits(
        st, outs, caps, STEP, prep(occluder))
    assert limits == [0.0]


def test_gate_off_returns_none(monkeypatch):
    occluder = Polygon([(-50.0, 28.0), (50.0, 28.0),
                        (50.0, 60.0), (-50.0, 60.0)])
    st, outs, caps = _one_station()
    monkeypatch.setattr(AG, "_RAY_OCCLUSION", False)
    assert AG._station_occlusion_limits(
        st, outs, caps, STEP, prep(occluder)) is None


def test_wrap_skirt_is_a_join_target_not_an_occluder():
    """The taxiway-end WRAP exemption, verbatim from the station probe: a
    hit that lies on a runway-END skirt does not occlude."""
    skirt = Polygon([(-50.0, 28.0), (50.0, 28.0),
                     (50.0, 60.0), (-50.0, 60.0)])
    st, outs, caps = _one_station()
    assert AG._station_occlusion_limits(
        st, outs, caps, STEP, prep(skirt)) == [25.0]
    assert AG._station_occlusion_limits(
        st, outs, caps, STEP, prep(skirt),
        wrap_skirt_prep=prep(skirt)) is None


def test_vectorized_containment_equals_naive_per_sample():
    """BUILD-TIME GUARD EQUIVALENCE: the one vectorized ``contains_xy``
    over the whole station x sample grid decides exactly what a prepared
    ``contains(Point(...))`` per sample decides."""
    slabs = [
        Polygon([(-20.0, 12.0), (35.0, 12.0), (35.0, 33.0), (-20.0, 33.0)]),
        Polygon([(60.0, -5.0), (95.0, -5.0), (95.0, 80.0), (60.0, 80.0)]),
        Polygon([(10.0, 70.0), (55.0, 70.0), (55.0, 90.0), (10.0, 90.0)]),
    ]
    from shapely.ops import unary_union
    union = unary_union(slabs)
    prep_static = prep(union)
    stations, outs, caps = [], [], []
    for i in range(37):
        ang = 0.17 * i
        stations.append((2.0 * i, 1.5 * i - 10.0))
        outs.append((math.cos(ang), math.sin(ang)))
        caps.append(100.0 if i % 3 else 42.0)
    limits = AG._station_occlusion_limits(
        stations, outs, caps, STEP, prep_static)
    # Naive reference: march each station sample by sample, break on the
    # first prepared containment, remember the previous distance.
    naive = []
    for (sx, sy), (nx, ny), cap in zip(stations, outs, caps):
        nst = max(1, int(math.ceil(cap / STEP)))
        lim = AG._OCCLUSION_CLEAR
        prev = 0.0
        for k in range(1, nst + 1):
            d = min(cap, k * STEP)
            if prep_static.contains(Point(sx + nx * d, sy + ny * d)):
                lim = prev
                break
            prev = d
        naive.append(lim)
    assert limits is not None
    assert limits == naive
    assert any(v != AG._OCCLUSION_CLEAR for v in naive), "case must bite"


# ══════════════════════════════════════════════════════════════════════
# 2. The two band builders, through the SHARED march
#    (``_derive_shape_stations_and_bands`` — the one path the pre-solve
#    constructor and the post-solve emit re-march both run through)
# ══════════════════════════════════════════════════════════════════════
# Runway-family closures with an explicit 100 m reach and the Annex-14
# code-3 graded half-width (75 m), so BOTH directions can be governed well
# past the 30 m occluder (a taxiway's fill cap is only 12.5 m).
_WIDTH = 75.0
_REACH = 100.0


def _runway_fns():
    def ceil_off(d):
        return adjacent_ground_envelope("runway", 3, None, d)[1]

    def floor_depth(d):
        f = adjacent_ground_envelope("runway", 3, None, min(d, _WIDTH))[0]
        return None if f is None else -f

    return ceil_off, floor_depth, _WIDTH, _REACH


def _taxi_rect():
    """CCW rectangle 200 m long, 20 m wide.  The NORTH edge (y = 20) has
    outward normal +y; that is the frontage under test."""
    return [(0.0, 0.0), (200.0, 0.0), (200.0, 20.0), (0.0, 20.0),
            (0.0, 0.0)]


def _north_occluder(y0=48.0):
    """Pavement standing in the north frontage's rays: the north edge is
    at y = 20, so the first sample INSIDE is d = 30 (y = 50 ∈ (48, 88))
    and the lawful depth is the last free-ground sample, d = 25."""
    return Polygon([(-100.0, y0), (300.0, y0),
                    (300.0, y0 + 40.0), (-100.0, y0 + 40.0)])


def _rising_dem(x, y):
    """Terrain 8 m ABOVE the pavement everywhere → the CUT fires at every
    station, out to the full reach (daylight never closes)."""
    return EDGE_ALT + 8.0


def _sinking_dem(x, y):
    """Terrain 8 m BELOW the pavement everywhere → the FILL twin fires."""
    return EDGE_ALT - 8.0


def _derive(dem, occluder, ccw=True):
    ceil_off, floor_depth, width, reach = _runway_fns()
    coords = _taxi_rect()
    return AG._derive_shape_stations_and_bands(
        coords, ccw, [EDGE_ALT] * len(coords), None, width, reach,
        TRIGGER, floor_depth, ceil_off, STEP, prep(occluder), set(), dem)


def _north_depth(bands):
    """Deepest lateral depth any band vertex reaches on the NORTH frontage
    (0 when the frontage carries no band)."""
    ys = [y for ring, _a in bands for _x, y in ring if y > 20.0]
    return (max(ys) - 20.0) if ys else 0.0


def test_cut_band_stops_at_half_the_corridor():
    """HALF-CORRIDOR CUT CAP (owner ruling 2026-07-26, CYXY shape 337):
    the CUT claims at most half its occlusion distance, so two facing
    frontages meet mid-corridor instead of one marching to the
    neighbour's edge and ending in a wall.  The occlusion limit here is
    ~25 m (the pre-ruling stop), so the cut now reaches ~12.5 m."""
    fill, cut, _st, _a, _o = _derive(_rising_dem, _north_occluder())
    assert cut, "the rising DEM must produce cut bands"
    assert _north_depth(cut) <= 30.0
    assert _north_depth(cut) == pytest.approx(12.499, abs=1e-3)
    # The fill twin has nothing to do against a rising DEM.
    assert _north_depth(fill) == 0.0


def test_cut_half_corridor_gate_off_stops_at_the_pavement(monkeypatch):
    """O4_ADJACENT_GROUND_CUT_HALF_CORRIDOR=0 restores the 2026-07-25
    behaviour: the cut stops at the occluding pavement itself."""
    monkeypatch.setattr(AG, "_CUT_HALF_CORRIDOR", False)
    fill, cut, _st, _a, _o = _derive(_rising_dem, _north_occluder())
    assert cut
    assert _north_depth(cut) == pytest.approx(25.0, abs=1e-6)


def test_fill_band_stops_at_the_occluding_pavement():
    fill, _cut, _st, _a, _o = _derive(_sinking_dem, _north_occluder())
    assert fill, "the sinking DEM must produce fill bands"
    assert _north_depth(fill) <= 30.0
    assert _north_depth(fill) == pytest.approx(25.0, abs=1e-6)


def test_clear_frontage_is_untouched():
    """A ray with no pavement in it keeps the full march: the south
    frontage of the same rect (occluder is north-only) reaches deeper than
    the occluded north frontage."""
    _fill, cut, _st, _a, _o = _derive(_rising_dem, _north_occluder())
    south = [-y for ring, _a in cut for _x, y in ring if y < 0.0]
    assert south and max(south) > 40.0
    assert _north_depth(cut) == pytest.approx(12.499, abs=1e-3)


def test_gate_off_is_byte_identical(monkeypatch):
    """OFF ⇒ the pre-fix march verbatim: the band reaches past the
    occluder (the defect), and the geometry equals a run whose occluder is
    somewhere else entirely."""
    monkeypatch.setattr(AG, "_RAY_OCCLUSION", False)
    _fill_off, cut_off, _s, _a, _o = _derive(
        _rising_dem, _north_occluder())
    assert _north_depth(cut_off) > 30.0          # marched straight through
    elsewhere = Polygon([(-900.0, -900.0), (-800.0, -900.0),
                         (-800.0, -800.0), (-900.0, -800.0)])
    _fill_e, cut_e, _s2, _a2, _o2 = _derive(_rising_dem, elsewhere)
    assert cut_off == cut_e                      # byte-identical rings


def test_no_band_vertex_lands_beyond_the_occluder():
    """The acceptance probe: ZERO band vertices inside (or beyond) an
    occluding pavement, on either direction's bands."""
    occl = _north_occluder()
    for dem in (_rising_dem, _sinking_dem):
        fill, cut, _st, _a, _o = _derive(dem, occl)
        for ring, _alts in fill + cut:
            for x, y in ring:
                assert not occl.covers(Point(x, y)), (x, y)


# ══════════════════════════════════════════════════════════════════════
# 3. VALIDATOR LOCKSTEP (MIRROR 5)
#    Harness: the adjacent-ground validator's own synthetic runway rect
#    (tests/test_adjacent_ground_validator.py), plus an occluding apron
#    slab standing in the NORTH transects.
# ══════════════════════════════════════════════════════════════════════
_RUNWAY_LEN = 1500.0            # ICAO code 3 → graded half-width 75 m
_RUNWAY_ALT = 100.0
_HALF_WIDTH = 22.5              # rect half-width (short edge)
# The occluding slab spans d = 20 … 30 m off the north edge, so the first
# north sample INSIDE it is d = 25 m and the lawful free-ground depth is
# d = 20 m.  (The reader's own fill cap for this rect is ~52 m, so the
# beyond-pavement breach below must sit inside that to be flaggable at
# all — which is exactly what makes the false finding possible.)
_OCCL_Y0 = _HALF_WIDTH + 20.0
_OCCL_Y1 = _HALF_WIDTH + 30.0
_FREE_GROUND_M = 20.0


def _occluder_slab():
    return Polygon([(-200.0, _OCCL_Y0), (_RUNWAY_LEN + 200.0, _OCCL_Y0),
                    (_RUNWAY_LEN + 200.0, _OCCL_Y1), (-200.0, _OCCL_Y1)])


def _lockstep_layout(with_occluder=True):
    rect = Polygon([
        (0.0, -_HALF_WIDTH), (_RUNWAY_LEN, -_HALF_WIDTH),
        (_RUNWAY_LEN, _HALF_WIDTH), (0.0, _HALF_WIDTH)])
    layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
    layout.shapes.append(BuiltShape(
        polygon=rect, role="runway", ref="09-27", altitude=_RUNWAY_ALT))
    if with_occluder:
        layout.shapes.append(BuiltShape(
            polygon=_occluder_slab(), role="apron", ref="OCCLUDER",
            altitude=_RUNWAY_ALT))
    return layout


def _make_runway():
    lon_b = math.degrees(_RUNWAY_LEN / R_EARTH)
    return Runway(
        desig_a="09", desig_b="27",
        lat_a=0.0, lon_a=0.0, lat_b=0.0, lon_b=lon_b,
        width_m=45.0, surface_code=1,
        displaced_a_m=0.0, displaced_b_m=0.0,
        markings_a=0, approach_lights_a=0,
        markings_b=0, approach_lights_b=0)


def _patch_dem(monkeypatch, scenario):
    """``scenario(y)`` in LOCAL METRES (signed, so the north frontage can
    be treated differently from the south)."""
    def _fake(dem, tile_lat, tile_lon, lat, lon):
        return scenario(math.radians(lat) * R_EARTH)
    monkeypatch.setattr(elevation, "_sample_dem", _fake)


def _validate(layout):
    return verification.check_adjacent_ground(
        layout, dem=object(), tile_lat=0, tile_lon=0,
        source_runways=[_make_runway()])


def _runway_findings(findings):
    return [f for f in findings if f[1] == "09-27"]


# Terrain drops 12 m only BEYOND the occluder (north, past its far face
# plus the reader's 1 m coverage gap): ground the emitter can no longer
# reach through the pavement.
def _dem_beyond_only(y):
    return _RUNWAY_ALT - 12.0 if y > _OCCL_Y1 + 2.0 else _RUNWAY_ALT


# Terrain drops 12 m INSIDE the free-ground reach (north, 5 <= d <= 15 m).
def _dem_inside_reach(y):
    d = y - _HALF_WIDTH
    return _RUNWAY_ALT - 12.0 if 4.0 < d < 16.0 else _RUNWAY_ALT


def test_validator_without_the_mirror_mints_the_false_finding(monkeypatch):
    """Baseline (nothing published — the pre-mirror reader): the breach
    BEYOND the occluding pavement is flagged, which is exactly the false
    finding the emitter's ray occlusion would otherwise cause."""
    layout = _lockstep_layout()
    _patch_dem(monkeypatch, _dem_beyond_only)
    findings = _runway_findings(_validate(layout))
    assert findings and {f[0] for f in findings} == {"should_fill"}


def test_validator_mirrors_the_occlusion(monkeypatch):
    """MIRROR 5: with the emitter's own static union published, the reader
    stops at the pavement exactly as the emitter's march does — no finding
    against ground beyond it."""
    layout = _lockstep_layout()
    layout.adjacent_ground_occlusion = _occluder_slab()
    _patch_dem(monkeypatch, _dem_beyond_only)
    assert _runway_findings(_validate(layout)) == []


def test_validator_still_flags_inside_the_free_ground_reach(monkeypatch):
    """The mirror must not blind the reader: a breach the emitter CAN
    reach (inside the free-ground depth) is still flagged."""
    layout = _lockstep_layout()
    layout.adjacent_ground_occlusion = _occluder_slab()
    _patch_dem(monkeypatch, _dem_inside_reach)
    findings = _runway_findings(_validate(layout))
    assert findings and {f[0] for f in findings} == {"should_fill"}


def test_validator_gate_off_is_the_pre_mirror_reader(monkeypatch):
    """OFF ⇒ byte-identical: publication present but the gate down gives
    the same findings as no publication at all."""
    monkeypatch.setattr(CFG, "BAND_RAY_OCCLUSION_ENABLED", False)
    layout = _lockstep_layout()
    layout.adjacent_ground_occlusion = _occluder_slab()
    _patch_dem(monkeypatch, _dem_beyond_only)
    gated_off = _validate(layout)
    plain = _validate(_lockstep_layout())
    assert gated_off == plain
    assert _runway_findings(gated_off)


def test_emitter_and_validator_agree_on_the_occluded_frontage(monkeypatch):
    """LOCKSTEP PROOF, both directions on ONE geometry + DEM:

      * the EMITTER lays nothing on the north frontage beyond the
        occluding pavement (the breach past it is unreachable), and
      * the VALIDATOR flags nothing there.

    Run with the SAME occluder, the SAME 5 m station grid and the SAME law
    helper, so a divergence in either reader trips this test."""
    occl = _occluder_slab()
    # EMITTER: the runway rect's own march, fed the occluder as its static
    # block and a DEM that drops only beyond it.
    coords = [(0.0, -_HALF_WIDTH), (_RUNWAY_LEN, -_HALF_WIDTH),
              (_RUNWAY_LEN, _HALF_WIDTH), (0.0, _HALF_WIDTH),
              (0.0, -_HALF_WIDTH)]

    def ceil_off(d):
        return adjacent_ground_envelope("runway", 3, None, d)[1]

    def floor_depth(d):
        f = adjacent_ground_envelope("runway", 3, None, min(d, 75.0))[0]
        return None if f is None else -f

    def _march(block):
        fill, cut, _st, _a, _o = AG._derive_shape_stations_and_bands(
            coords, True, [_RUNWAY_ALT] * len(coords), None, 75.0,
            CLEARANCE_MAX_REACH_M["runway"], TRIGGER, floor_depth,
            ceil_off, STEP, prep(block), set(),
            lambda x, y: _dem_beyond_only(y))
        north = [y for ring, _al in fill + cut for _x, y in ring
                 if y > _HALF_WIDTH]
        return (max(north) - _HALF_WIDTH) if north else 0.0

    # The case must BITE: with the slab moved out of the transects the
    # emitter does reach the breach (that is the CYXY 395 behaviour).
    elsewhere = Polygon([(-9000.0, -9000.0), (-8000.0, -9000.0),
                         (-8000.0, -8000.0), (-9000.0, -8000.0)])
    assert _march(elsewhere) > _FREE_GROUND_M
    assert _march(occl) <= _FREE_GROUND_M, (
        "the emitter must not reach the beyond-pavement breach")

    # VALIDATOR: same occluder, published as the emitter's static block.
    layout = _lockstep_layout()
    layout.adjacent_ground_occlusion = occl
    _patch_dem(monkeypatch, _dem_beyond_only)
    assert _runway_findings(_validate(layout)) == [], (
        "the validator must not flag what the emitter lawfully skipped")
