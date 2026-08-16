"""Twins for R5c — GRADED-ROAD CHARACTER (service-road law spec, Fable
2026-08-15; owner in-sim on R5 at CYXY 60.7087015,-135.0746305).

R5's tracker follows the low-passed terrain faithfully — INCLUDING its
wiggles — where the owner wants ROAD character: "a smooth graded
surface".  And the visible road is a COMPOSITE (CYXY ``service_road``
349 + ``service_junction`` 63 on one corridor): each shape took station
values from ITS OWN chain projection, so the corridor could slope
LATERALLY across itself even though every single shape is
cross-section-flat.

Two mechanisms, one twin block each:

1. REVERSAL SUPPRESSION (longitudinal) — a grade reversal whose
   interior amplitude is below ``config.SVC_PROFILE_REVERSAL_MIN_M``
   is levelled through into a monotone bridge; a REAL terrain feature
   at any wavelength survives; the cap and the pegs still bind.
2. CORRIDOR CO-LEVEL (lateral) — a ``service_junction`` vertex within
   the seeder's station reach of an adjoining road's chain joins THAT
   chain's station cluster, so road and junction pieces at equal
   arclength take ONE value.  Multi-chain junctions: mouth welds win,
   then the through-chain of the widest road.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from auto_patch.config import SVC_PROFILE_REVERSAL_MIN_M   # noqa: E402
from auto_patch.elevation_per_surface.route_profile import anchors  # noqa: E402
from auto_patch.elevation_per_surface.route_profile.corridor_profile import (  # noqa: E402
    monotone_bridge, track_dem_profile, turning_points)

CAP = 0.08          # config.SERVICE_ROAD_MAX_GRADE — the existing constant


def _uniform(n: int, step: float = 10.0) -> list[float]:
    return [i * step for i in range(n)]


def _wide_band(n: int, lo: float = -1e6, hi: float = 1e6):
    return [lo] * n, [hi] * n


def _reversals(z, tol: float = 1e-9) -> int:
    """Interior direction changes actually present in ``z``."""
    return max(0, len(turning_points(z, tol=tol)) - 2)


# ══ 1. REVERSAL SUPPRESSION ═════════════════════════════════════════

def test_the_constant_is_the_spec_default():
    """ONE new constant, default 0.4 m (spec wording)."""
    assert SVC_PROFILE_REVERSAL_MIN_M == 0.4


# ── the primitives ──────────────────────────────────────────────────
def test_turning_points_ignore_plateaus_and_keep_pegs():
    z = [100.0, 100.0, 101.0, 101.0, 100.5, 100.5, 102.0]
    assert turning_points(z) == [0, 3, 5, 6]
    # a peg is a law target: it is a fixed turning point, never dropped
    assert turning_points(z, fixed=(2,)) == [0, 2, 3, 5, 6]


def test_monotone_bridge_is_monotone_and_keeps_its_endpoints():
    z = [100.0, 100.4, 100.2, 100.9, 100.7, 101.5]
    out = monotone_bridge(z, 0, 5)
    assert out[0] == pytest.approx(100.0)
    assert out[5] == pytest.approx(101.5)
    for i in range(1, 6):
        assert out[i] >= out[i - 1] - 1e-12
    # it never overshoots the far endpoint, and never drops below the near one
    assert min(out) >= 100.0 - 1e-12 and max(out) <= 101.5 + 1e-12


def test_monotone_bridge_preserves_the_cap():
    """A running extremum cannot move by more than the step that made
    it — so a cap-lawful profile stays cap-lawful through the bridge."""
    s = _uniform(21)
    z = [100.0 + 0.2 * ((i * 7) % 5 - 2) + 0.05 * i for i in range(21)]
    for i in range(1, 21):
        assert abs(z[i] - z[i - 1]) / 10.0 <= CAP + 1e-9   # premise
    out = monotone_bridge(z, 0, 20)
    for i in range(1, 21):
        assert abs(out[i] - out[i - 1]) / (s[i] - s[i - 1]) <= CAP + 1e-9


# ── (a) A SYNTHETIC WIGGLE IS LEVELLED THROUGH ──────────────────────
def _wiggly_ramp(n: int, rise_per_station: float = 0.10,
                 wiggle: float = 0.15) -> list[float]:
    """A steady ramp carrying a sub-materiality saw — the terrain
    character R5 tracked faithfully and R5c must grade out."""
    return [100.0 + rise_per_station * i + (wiggle if i % 2 else 0.0)
            for i in range(n)]


def test_r5c_sub_materiality_wiggles_become_a_monotone_ramp():
    n = 31
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = _wiggly_ramp(n)

    # CONTROL: the bare R5 tracker reproduces the terrain, wiggles and
    # all — 15 reversals in 300 m of road.
    bare = track_dem_profile(s, f, c, {}, CAP, dem=dem, reversal_min_m=0.0)
    assert bare is not None
    for i in range(n):
        assert bare.z[i] == pytest.approx(dem[i], abs=1e-9)
    assert _reversals(bare.z) >= 10
    assert bare.audit.reversals_collapsed == 0

    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    # THE ACCEPTANCE SHAPE: "monotone within one reversal".  Every
    # interior wiggle is levelled through; only the run's own tail
    # half-excursion can survive, because a rise-fall-rise needs a run
    # on both sides (collapsing half features cascades — see
    # ``_suppress_reversals``).
    assert _reversals(out.z) <= 1, "the graded road still reverses"
    assert out.audit.reversals_collapsed >= 14
    assert out.audit.reversals_kept <= 1
    assert out.audit.reversal_max_amplitude_m < SVC_PROFILE_REVERSAL_MIN_M
    # monotone all the way to that last reversal
    turn = turning_points(out.z)[-2] if _reversals(out.z) else n - 1
    for i in range(1, turn + 1):
        assert out.z[i] >= out.z[i - 1] - 1e-9
    # levelling through is not re-shaping: the ramp still tracks terrain
    assert max(abs(out.z[i] - dem[i]) for i in range(n)) <= 0.2


def test_r5c_the_cap_still_binds_through_the_filter():
    """Owner condition 1 is a HARD constraint; character never relaxes
    it.  Terrain far steeper than the cap, with pegs, filtered."""
    n = 41
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0 + 3.0 * ((i * 5) % 7) + 0.25 * ((i * 3) % 4)
           for i in range(n)]
    out = track_dem_profile(s, f, c, {0: 100.0, 20: 104.0, 40: 101.0},
                            CAP, dem=dem)
    assert out is not None
    for i in range(1, n):
        g = abs(out.z[i] - out.z[i - 1]) / (s[i] - s[i - 1])
        assert g <= CAP + 1e-9, f"segment {i} rides {g * 100:.3f} % > cap"
    assert out.audit.over_cap_segments == 0


def test_r5c_pegs_stay_exact_and_are_never_bridged_over():
    """A peg is a LAW TARGET: the filter may not move it, and no
    monotone bridge may span it (an interior peg 0.2 m off its
    neighbours would otherwise be levelled away)."""
    n = 21
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = _wiggly_ramp(n)
    pegs = {0: 100.0, 10: 101.2, 20: 102.0}
    out = track_dem_profile(s, f, c, pegs, CAP, dem=dem)
    assert out is not None
    for i, v in pegs.items():
        assert out.z[i] == pytest.approx(v, abs=1e-9)


def test_r5c_the_tube_outranks_character():
    """Law over character: a bridge that would push through a band wall
    yields to the wall — the emitted profile stays inside the tube.

    The ceiling is a real reach-band wall (cap-Lipschitz, grown from an
    anchor at station 10), which is the only kind this module promises
    to respect — an arbitrary cliff wall is not a reach band."""
    n = 21
    s = _uniform(n)
    f = [-1e6] * n
    c = [100.35 + CAP * abs(s[i] - s[10]) for i in range(n)]
    dem = _wiggly_ramp(n)
    bare = track_dem_profile(s, f, c, {}, CAP, dem=dem, reversal_min_m=0.0)
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert bare is not None and out is not None
    assert out.z != bare.z, "control: the filter must be doing something"
    for i in range(n):
        assert out.z[i] <= c[i] + 1e-9, f"station {i} left the tube"


# ── (b) A REAL TERRAIN FEATURE SURVIVES ─────────────────────────────
def test_r5c_a_real_two_metre_feature_is_kept():
    """The filter is an AMPLITUDE floor, not a smoothing length: a 2 m
    dip inside the cap is still tracked, wiggles and all removed around
    it (R5's owner condition — big terrain movement stays tracked)."""
    n = 31
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = []
    for i in range(n):
        if i <= 10:
            base = 100.0
        elif i <= 15:
            base = 100.0 - 2.0 * (i - 10) / 5.0      # 4 % descent, < cap
        elif i <= 20:
            base = 98.0 + 2.0 * (i - 15) / 5.0
        else:
            base = 100.0
        dem.append(base + (0.15 if i % 2 else 0.0))

    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    assert min(out.z) <= 98.35, "the 2 m dip was levelled away"
    # Three reversals survive: the dip's floor, plus the run's own two
    # END half-excursions (the spec's pattern needs a run on both
    # sides).  The eight interior wiggles on the flats are gone.
    assert out.audit.reversals_kept == 3
    assert out.audit.reversals_collapsed == 8
    assert out.audit.reversal_max_amplitude_m < SVC_PROFILE_REVERSAL_MIN_M
    # the ramps still TRACK the feature, within the wiggle they lost
    for i in (12, 14, 16, 18):
        base = (100.0 - 2.0 * (i - 10) / 5.0 if i <= 15
                else 98.0 + 2.0 * (i - 15) / 5.0)
        assert abs(out.z[i] - base) <= 0.2
    # …and the flats around it are LEVEL, not bumpy
    assert max(out.z[1:10]) - min(out.z[1:10]) <= 1e-9
    assert max(out.z[21:30]) - min(out.z[21:30]) <= 1e-9


def test_r5c_the_floor_is_the_only_discriminator():
    """Wavelength is irrelevant; AMPLITUDE decides.  Two saw profiles on
    identical geometry: one whose teeth clear
    ``SVC_PROFILE_REVERSAL_MIN_M`` (every reversal kept) and one whose
    teeth do not (every interior reversal gone)."""
    n = 21
    s = _uniform(n)
    f, c = _wide_band(n)

    def _saw(amp):
        return [100.0 + (amp if i % 2 else 0.0) for i in range(n)]

    keep = track_dem_profile(s, f, c, {}, CAP,
                             dem=_saw(SVC_PROFILE_REVERSAL_MIN_M * 1.5))
    drop = track_dem_profile(s, f, c, {}, CAP,
                             dem=_saw(SVC_PROFILE_REVERSAL_MIN_M * 0.5))
    assert keep is not None and drop is not None
    assert keep.audit.reversals_collapsed == 0
    assert _reversals(keep.z) == 19
    assert drop.audit.reversals_collapsed >= 8
    assert _reversals(drop.z) <= 1


def test_r5c_a_lone_end_excursion_is_left_alone():
    """THE SPEC'S PATTERN, exactly: a rise-fall-rise needs a run on BOTH
    sides.  A single sub-materiality V with nothing beyond it is a HALF
    feature at each end and is NOT collapsed — collapsing half features
    re-measures their neighbours against a run endpoint instead of the
    extremum it turned at, and the amplitudes cascade until a genuine
    feature dies (measured on the R5 twin
    ``test_r5_empty_pegs_still_returns_a_profile_that_tracks_dem``: a
    0.6 m sine, twice the floor, eaten in three steps)."""
    n = 21
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0 - 0.2 * max(0.0, 1.0 - abs(i - 10) / 5.0)
           for i in range(n)]
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    assert out.audit.reversals_collapsed == 0
    assert _reversals(out.z) == 1


def test_r5c_a_monotone_profile_is_untouched():
    """Nothing to collapse ⇒ byte-identical to the bare R5 tracker."""
    n = 15
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [700.0 + 0.5 * i for i in range(n)]
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    bare = track_dem_profile(s, f, c, {}, CAP, dem=dem, reversal_min_m=0.0)
    assert out is not None and bare is not None
    assert out.z == bare.z
    assert out.audit.reversals_collapsed == 0


# ══ 2. CORRIDOR CO-LEVEL ════════════════════════════════════════════

from shapely.geometry import LineString, Polygon      # noqa: E402

from auto_patch.layout import (                        # noqa: E402
    ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD)

#: The seeder's own station reach — ``ROAD_CARVE_MAX_WIDTH_M / 2 + 2``.
REACH_M = 13.0 / 2.0 + 2.0


def _shape(role, poly):
    return types.SimpleNamespace(role=role, polygon=Polygon(poly),
                                 lateral_cap=None)


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ONE CORRIDOR, TWO PIECES.  Road 349's analogue runs along y=0 and
# registers chain 0; junction 63's analogue sits beside it and registers
# its OWN chain 1, five metres off — near enough that both project onto
# either within the station reach, far enough that neither the 2 m XY
# station merge nor the (default-off) wide parallel merge can see them.
_LINES = [LineString([(0.0, 0.0), (40.0, 0.0)]),
          LineString([(0.0, 5.0), (40.0, 5.0)])]
_ROAD = _shape(ROLE_SERVICE_ROAD, _rect(10.0, -3.0, 30.0, 3.0))
_JCT = _shape(ROLE_SERVICE_JUNCTION, _rect(16.0, 3.0, 24.0, 7.0))
# node 1 is the WELD — shared by both pieces, which is what makes them
# one corridor.
_NODE_POS = {0: (20.0, -2.0), 1: (20.0, 2.0),
             2: (20.0, 4.0), 3: (20.0, 6.0)}
_NODE_SHAPES = {0: [_ROAD], 1: [_ROAD, _JCT], 2: [_JCT], 3: [_JCT]}


def _raw(node_pos=None, lines=None):
    """The seeder's nearest-chain assignment, before co-level."""
    from shapely.geometry import Point
    node_pos = _NODE_POS if node_pos is None else node_pos
    lines = _LINES if lines is None else lines
    out = {}
    for i, p in node_pos.items():
        P = Point(p)
        best = min(((lines[li].distance(P), li) for li in range(len(lines))),
                   key=lambda t: t[0])
        if best[0] <= REACH_M:
            out[i] = (best[1], lines[best[1]].project(P))
    return out


def test_without_colevel_the_composite_splits_across_two_chains():
    """The premise: nearest-chain assignment puts the junction's
    vertices on a DIFFERENT chain from the road it welds to."""
    raw = _raw()
    assert raw[0][0] == 0 and raw[1][0] == 0
    assert raw[2][0] == 1 and raw[3][0] == 1


def test_colevel_rehomes_the_junction_onto_the_roads_chain():
    raw = _raw()
    moved = anchors._corridor_colevel_rehome(
        _LINES, _NODE_POS, raw, _NODE_SHAPES, {}, REACH_M)
    assert moved == 2
    assert {raw[i][0] for i in raw} == {0}
    # …at the same arclength the road piece uses — that is the point
    for i in raw:
        assert raw[i][1] == pytest.approx(20.0, abs=1e-9)


def test_colevel_leaves_vertices_beyond_the_station_reach_alone():
    """The reach is the seeder's, unchanged: a yard vertex too far from
    the road's chain keeps its own station."""
    far_pos = dict(_NODE_POS)
    far_pos[3] = (20.0, 12.0)           # 12 m from chain 0 > 8.5 m reach
    raw = _raw(far_pos)
    moved = anchors._corridor_colevel_rehome(
        _LINES, far_pos, raw, _NODE_SHAPES, {}, REACH_M)
    assert moved == 1
    assert raw[2][0] == 0 and raw[3][0] == 1


def test_colevel_needs_an_adjoining_road():
    """A junction that welds to no road is not part of a composite and
    is never re-homed."""
    raw = _raw()
    lone = {0: [_ROAD], 1: [_ROAD], 2: [_JCT], 3: [_JCT]}
    assert anchors._corridor_colevel_rehome(
        _LINES, _NODE_POS, raw, lone, {}, REACH_M) == 0
    assert raw[2][0] == 1 and raw[3][0] == 1


def test_multi_chain_junction_takes_the_widest_roads_through_chain():
    """Two roads meet the junction — a 6 m one on chain 0 and a 12 m
    one on chain 1.  With no weld to arbitrate, the WIDEST road's
    through-chain wins."""
    lines = [LineString([(0.0, 0.0), (40.0, 0.0)]),
             LineString([(20.0, -20.0), (20.0, 20.0)])]
    narrow = _shape(ROLE_SERVICE_ROAD, _rect(0.0, -3.0, 16.0, 3.0))    # 6 m
    wide = _shape(ROLE_SERVICE_ROAD, _rect(14.0, -20.0, 26.0, -6.0))   # 12 m
    jct = _shape(ROLE_SERVICE_JUNCTION, _rect(14.0, -6.0, 26.0, 6.0))
    node_pos = {0: (8.0, 2.0),          # narrow road, chain 0
                1: (20.0, -12.0),       # wide road, chain 1
                2: (16.0, 1.0),         # narrow's weld into the junction
                3: (22.0, -6.0)}        # wide's weld into the junction
    node_shapes = {0: [narrow], 1: [wide],
                   2: [narrow, jct], 3: [wide, jct]}
    raw = _raw(node_pos, lines)
    assert raw[2][0] == 0 and raw[3][0] == 1        # premise: two chains
    anchors._corridor_colevel_rehome(
        lines, node_pos, raw, node_shapes, {}, REACH_M)
    assert {raw[i][0] for i in (2, 3)} == {1}, "the widest road lost"


def test_mouth_welds_win_over_the_widest_road():
    """Same junction, but its welded (anchor) vertex names chain 0 —
    a weld is a law target and it names the corridor the junction
    belongs to, ahead of the width tie-break."""
    lines = [LineString([(0.0, 0.0), (40.0, 0.0)]),
             LineString([(20.0, -20.0), (20.0, 20.0)])]
    narrow = _shape(ROLE_SERVICE_ROAD, _rect(0.0, -3.0, 16.0, 3.0))
    wide = _shape(ROLE_SERVICE_ROAD, _rect(14.0, -20.0, 26.0, -6.0))
    jct = _shape(ROLE_SERVICE_JUNCTION, _rect(14.0, -6.0, 26.0, 6.0))
    node_pos = {0: (8.0, 2.0), 1: (20.0, -12.0),
                2: (16.0, 1.0), 3: (22.0, -6.0)}
    node_shapes = {0: [narrow], 1: [wide],
                   2: [narrow, jct], 3: [wide, jct]}
    raw = _raw(node_pos, lines)
    anchors._corridor_colevel_rehome(
        lines, node_pos, raw, node_shapes, {2: 101.0}, REACH_M)
    assert {raw[i][0] for i in (2, 3)} == {0}, "the mouth weld lost"


# ── end to end: the junction vertex adopts the through-chain VALUE ───
def _seed_targets(colevel: bool, dem):
    layout = types.SimpleNamespace(apt_taxi_centerlines=[
        types.SimpleNamespace(is_service=True, line=ln) for ln in _LINES])
    empty: dict = {}
    return anchors._svc_spine_station_seeds(
        layout, set(_NODE_POS), _NODE_POS, {}, dem, CAP,
        empty, empty, empty, empty, prox_pairs=(),
        node_shapes=(_NODE_SHAPES if colevel else None))[0]


def test_junction_vertices_adopt_the_through_chains_station_value():
    """THE ACCEPTANCE SHAPE (CYXY road 349 + junction 63): road nodes
    over 100 m terrain, junction nodes over 106 m terrain.  Split
    across two chains the composite carries a 6 m lateral slope with
    every shape cross-section-flat; co-levelled it is ONE station and
    ONE value."""
    dem = [100.0, 100.0, 106.0, 106.0]
    split = _seed_targets(False, dem)
    assert abs(split[0] - split[2]) == pytest.approx(6.0, abs=1e-6)

    level = _seed_targets(True, dem)
    assert set(level) == {0, 1, 2, 3}
    for i in (1, 2, 3):
        assert level[i] == pytest.approx(level[0], abs=1e-9), (
            "the corridor still slopes laterally across its pieces")
    assert level[0] == pytest.approx(103.0, abs=1e-6)   # one shared mean
