"""Tests for the string SUBSTRATE (Fable RULING 1, 2026-07-31).

Headless, synthetic, no network and no X-Plane install: every fixture is
hand-built metre-space geometry, so the ruled mechanics are asserted
directly rather than through an airport.

The ruled mechanics under test, each with its own case:
  1. per-station membership at ``tol_m``;
  2. maximal runs;
  3. sub-``tol_m`` runs absorbed (anti-chatter, derived from the owner's
     constant);
  4. every CUT mints a seam joint to the covering piece — and a way's own
     endpoint is not a cut.
Plus the two properties the ruling turns on: SUBSEGMENT (not per-way)
granularity, and RECOGNITION-NOT-BRIDGING.
"""

from __future__ import annotations

import math

import pytest

from auto_patch.config import TAUT_STRING_SPINE_TOLERANCE_M
from auto_patch.elevation_per_surface.route_profile.string_substrate import (
    SeamJoint, build_string_substrate, polyline_length, resample_polyline)

TOL = float(TAUT_STRING_SPINE_TOLERANCE_M)
STEP = 5.0


def _line(x0, y0, x1, y1):
    return [(x0, y0), (x1, y1)]


def _sub(apt, osm, tol=TOL, step=STEP):
    return build_string_substrate(apt, osm, tol_m=tol, station_m=step)


# ── the owner's constant is what we test against ────────────────────

def test_owner_constant_is_eight_metres():
    """The ruling wires ``bound_m``/the corridor at the owner's 8.0 m.

    Guards the literal from drifting silently under the module (this is
    the constant the anti-chatter rule is DERIVED from, so a change moves
    two behaviours at once).
    """
    assert TAUT_STRING_SPINE_TOLERANCE_M == pytest.approx(8.0)


# ── resampling ──────────────────────────────────────────────────────

def test_resample_is_uniform_and_keeps_the_far_end():
    pts = resample_polyline(_line(0, 0, 103, 0), 5.0)
    assert pts[0] == (0.0, 0.0)
    # the last station is the polyline's own end, never a truncation
    assert pts[-1] == pytest.approx((103.0, 0.0))
    gaps = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 2)]
    assert all(g == pytest.approx(5.0) for g in gaps)


def test_resample_follows_a_bend_not_the_chord():
    pts = resample_polyline([(0, 0), (50, 0), (50, 50)], 10.0)
    assert polyline_length(pts) == pytest.approx(100.0, abs=1e-6)
    assert any(p[0] == pytest.approx(50.0) and p[1] > 0.0 for p in pts)


# ── (1) per-station membership ──────────────────────────────────────

def test_osm_inside_the_corridor_yields_entirely():
    """A whole OSM way lying on apt.dat pavement contributes nothing."""
    apt = [_line(0, 0, 1000, 0)]
    osm = [("w1", _line(0, 3.0, 1000, 3.0))]      # 3 m off, inside 8 m
    s = _sub(apt, osm)
    assert s.standing == ()
    assert s.seams == ()
    assert s.stats["yielded_m"] == pytest.approx(1000.0, abs=STEP)


def test_osm_outside_the_corridor_stands_entirely():
    """OSM stands where apt.dat is absent — here, everywhere."""
    apt = [_line(0, 0, 1000, 0)]
    osm = [("w1", _line(0, 400.0, 1000, 400.0))]
    s = _sub(apt, osm)
    assert len(s.standing) == 1
    assert s.standing[0].length_m == pytest.approx(1000.0, abs=1e-6)
    # both ends are the way's OWN endpoints -> no cut, no seam
    assert s.seams == ()


def test_membership_is_measured_at_the_owner_tolerance():
    """Just inside yields, just outside stands — the boundary is tol_m."""
    apt = [_line(0, 0, 1000, 0)]
    inside = _sub(apt, [("w", _line(0, TOL - 0.5, 1000, TOL - 0.5))])
    outside = _sub(apt, [("w", _line(0, TOL + 0.5, 1000, TOL + 0.5))])
    assert inside.standing == ()
    assert len(outside.standing) == 1


# ── (2) maximal runs + SUBSEGMENT granularity ───────────────────────

def test_partial_overlap_splits_the_way_it_does_not_keep_it_whole():
    """★ THE RULING ITSELF.  A way half on apt.dat pavement and half off
    contributes ONLY its off-pavement half.

    The per-WAY reading would keep this way entire and duplicate the
    apt.dat pavement; the measured HECA consequence was 75 % duplicated
    emitted metres.  This test is the regression guard for that reading.
    """
    apt = [_line(0, 0, 500, 0)]
    osm = [("w1", _line(0, 2.0, 1000, 2.0))]      # first half on apt.dat
    s = _sub(apt, osm)
    assert len(s.standing) == 1
    run = s.standing[0]
    assert run.length_m == pytest.approx(500.0, abs=2 * STEP)
    assert min(p[0] for p in run.coords) >= 500.0 - 2 * STEP
    assert s.stats["yielded_m"] == pytest.approx(500.0, abs=2 * STEP)


def test_a_covered_middle_produces_two_maximal_runs():
    """apt.dat in the middle cuts one way into two standing runs."""
    apt = [_line(400, 0, 600, 0)]
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    assert len(s.standing) == 2
    assert [r.ordinal for r in s.standing] == [0, 1]
    assert all(r.source == "w1" for r in s.standing)
    assert sum(r.length_m for r in s.standing) == pytest.approx(
        800.0, abs=4 * STEP)


def test_runs_are_maximal_not_per_station_fragments():
    apt = [_line(400, 0, 600, 0)]
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    # 800 m of uncovered ground must arrive as 2 runs, not 160 stations
    assert len(s.standing) == 2


# ── (3) anti-chatter absorption ─────────────────────────────────────

# The absorption fixtures use a COLLINEAR construction so the uncovered
# window is exact and computable, not eyeballed: apt.dat and the OSM way
# lie on the SAME line, apt.dat covering all but a gap of width G.  A
# station is then uncovered iff it is more than tol_m from BOTH gap
# edges, so the uncovered window is exactly ``G - 2 * tol_m``.  The
# fixture places that window decisively on one side of the criterion
# rather than asserting a geometric intuition.

def _collinear_gap(gap_m):
    """apt.dat on y=0 with a centred gap of ``gap_m``; OSM straight over
    it.  Uncovered window is exactly ``gap_m - 2 * TOL``."""
    x1 = 500.0 - gap_m / 2.0
    x2 = 500.0 + gap_m / 2.0
    return [_line(0, 0, x1, 0), _line(x2, 0, 1000, 0)], \
           [("w1", _line(0, 0, 1000, 0))]


def test_sub_tolerance_run_is_absorbed():
    """A standing run shorter than the corridor is chatter, not absence."""
    apt, osm = _collinear_gap(gap_m=2 * TOL + 4.0)   # 4 m uncovered < 8 m
    s = _sub(apt, osm, step=1.0)
    assert s.standing == ()
    assert s.stats["absorbed_runs"] >= 1.0
    assert 0.0 < s.stats["absorbed_m"] < TOL


def test_absorption_threshold_is_the_owner_constant_not_a_new_number():
    """Runs are absorbed below tol_m and survive above it, so the
    behaviour moves with the owner's constant and nothing else.

    Both arms are placed decisively (half a corridor either side of the
    threshold), so neither verdict rests on sampling luck.
    """
    below_apt, below_osm = _collinear_gap(gap_m=2 * TOL + TOL / 2.0)
    above_apt, above_osm = _collinear_gap(gap_m=2 * TOL + 3.0 * TOL)
    below = _sub(below_apt, below_osm, step=1.0)
    above = _sub(above_apt, above_osm, step=1.0)
    assert below.standing == ()                       # 4 m  -> absorbed
    assert len(above.standing) == 1                   # 24 m -> stands
    assert above.standing[0].length_m >= TOL


def test_absorption_never_joins_two_runs():
    """★ Absorption DELETES; it must never bridge.

    A covered stretch always cuts, however short — bridging across
    ground apt.dat owns is the forbidden operation.
    """
    apt = [_line(495, 0, 505, 0)]          # a 10 m covered island
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    assert len(s.standing) == 2            # never merged into one
    xs0 = [p[0] for p in s.standing[0].coords]
    xs1 = [p[0] for p in s.standing[1].coords]
    assert max(xs0) < min(xs1)             # disjoint, with a real gap


# ── (4) seam joints ─────────────────────────────────────────────────

def test_every_cut_mints_a_seam_to_the_covering_piece():
    apt = [_line(-100, 500, -50, 500),     # piece 0, far away, a decoy
           _line(400, 0, 600, 0)]          # piece 1, the real cover
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    assert len(s.standing) == 2
    assert len(s.seams) == 2               # one per cut, not per run end
    for j in s.seams:
        assert isinstance(j, SeamJoint)
        assert j.covering_piece == 1       # names the piece that covers
        assert j.distance_m <= TOL
    assert {j.at_end for j in s.seams} == {"tail", "head"}
    assert s.seams[0].run_index == 0 and s.seams[1].run_index == 1


def test_a_ways_own_endpoint_is_not_a_cut():
    """No apt.dat contact at the way's ends => no seam joints there."""
    apt = [_line(400, 0, 600, 0)]
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    # 2 runs x 2 ends = 4 ends, but only the 2 INNER ends are cuts
    assert len(s.seams) == 2
    assert all(0.0 < j.point[0] < 1000.0 for j in s.seams)


def test_seam_points_lie_on_their_run():
    apt = [_line(400, 0, 600, 0)]
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    for j in s.seams:
        run = s.standing[j.run_index]
        end = run.coords[0] if j.at_end == "head" else run.coords[-1]
        assert j.point == end


# ── assembly, ordering, determinism ─────────────────────────────────

def test_apt_pieces_pass_through_unchanged_and_first():
    apt = [_line(0, 0, 100, 0), [(0.0, 50.0), (60.0, 50.0), (60.0, 90.0)]]
    osm = [("w1", _line(0, 400, 1000, 400))]
    s = _sub(apt, osm)
    assert s.apt_pieces[0] == ((0.0, 0.0), (100.0, 0.0))
    assert s.apt_pieces[1] == ((0.0, 50.0), (60.0, 50.0), (60.0, 90.0))
    keys = [k for k, _c in s.polylines()]
    assert keys[:2] == ["apt:0", "apt:1"]
    assert keys[2].startswith("osm:")


def test_deterministic():
    apt = [_line(400, 0, 600, 0)]
    osm = [("w1", _line(0, 1.0, 1000, 1.0)),
           ("w2", _line(0, 300.0, 1000, 300.0))]
    a = _sub(apt, osm)
    b = _sub(apt, osm)
    assert a.standing == b.standing
    assert a.seams == b.seams
    assert a.stats == b.stats


def test_empty_apt_tier_lets_all_osm_stand():
    """Degenerate but real: an airport with no apt.dat taxi network."""
    osm = [("w1", _line(0, 0, 1000, 0))]
    s = _sub([], osm)
    assert len(s.standing) == 1
    assert s.standing[0].length_m == pytest.approx(1000.0)
    assert s.seams == ()


def test_degenerate_inputs_are_skipped_not_crashed():
    s = _sub([_line(0, 0, 10, 0), [(5.0, 5.0)]],
             [("pt", [(0.0, 900.0)]), ("ok", _line(0, 900, 500, 900))])
    assert len(s.standing) == 1
    assert s.stats["osm_ways"] == 1.0      # the single-point way is skipped


# ── required-explicit sampling resolution ───────────────────────────

def test_station_m_is_required_explicit():
    with pytest.raises(TypeError):
        build_string_substrate([], [], tol_m=TOL)     # type: ignore[call-arg]


def test_station_m_coarser_than_the_corridor_is_rejected():
    """A resolution coarser than the corridor cannot resolve the corridor
    — it must fail loudly, not silently under-sample."""
    with pytest.raises(ValueError):
        build_string_substrate([], [], tol_m=TOL, station_m=TOL + 1.0)
    with pytest.raises(ValueError):
        build_string_substrate([], [], tol_m=TOL, station_m=0.0)
    with pytest.raises(ValueError):
        build_string_substrate([], [], tol_m=0.0, station_m=1.0)


# ── stats are a closed account ──────────────────────────────────────

def test_stats_account_for_every_osm_metre():
    apt = [_line(400, 0, 600, 0)]
    osm = [("w1", _line(0, 1.0, 1000, 1.0))]
    s = _sub(apt, osm)
    st = s.stats
    assert (st["standing_m"] + st["yielded_m"] + st["absorbed_m"]
            == pytest.approx(st["osm_m"], abs=1e-6))
    assert st["substrate_m"] == pytest.approx(
        st["apt_m"] + st["standing_m"], abs=1e-6)
    assert st["tol_m"] == TOL and st["station_m"] == STEP


# ── the index is an optimisation, never a behaviour ─────────────────

def test_grid_index_agrees_with_brute_force_membership():
    """The grid window is claimed conservative; assert it against an
    exhaustive segment scan on scattered geometry (the claim is a
    build-time argument, so it must not be able to change an answer)."""
    from auto_patch.elevation_per_surface.route_profile.string_substrate \
        import _point_segment_distance, _SegmentGrid

    apt = [_line(0, 0, 1000, 0), _line(0, 30, 1000, 40),
           [(200.0, -60.0), (260.0, 5.0), (300.0, -60.0)],
           _line(700, 12, 730, 12)]
    grid = _SegmentGrid(apt, TOL)
    segs = [(c[i], c[i + 1]) for c in apt for i in range(len(c) - 1)]
    for x in range(0, 1000, 7):
        for y in range(-70, 70, 11):
            p = (float(x), float(y))
            brute = min(_point_segment_distance(p, a, b) for a, b in segs)
            got, _pi = grid.nearest(p)
            if brute <= TOL:
                assert got == pytest.approx(brute, abs=1e-9)
            else:
                assert got > TOL


# ══════════════════════════════════════════════════════════════════════
# THE RUNWAY CLIP (owner ruling 2026-07-31)
# ══════════════════════════════════════════════════════════════════════

from shapely.geometry import Polygon  # noqa: E402

from auto_patch.config import (  # noqa: E402
    TAUT_STRING_MIN_STRING_M, TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M)
from auto_patch.elevation_per_surface.route_profile.string_substrate import (  # noqa: E402
    clip_strings_to_runways)

MIN_REM = float(TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M)
DUTY = float(TAUT_STRING_MIN_STRING_M)


def _rwy(x0, x1, halfw=30.0):
    return Polygon([(x0, -halfw), (x1, -halfw), (x1, halfw), (x0, halfw)])


def _string(x0, x1, y=0.0, cid=0, step=10.0):
    """A string whose nodes lie along its own chord."""
    n = int((x1 - x0) // step)
    nodes = list(range(n + 1))
    pos = {i: (x0 + i * step, y) for i in nodes}
    return ((x0, y), (x1, y), nodes, float(x1 - x0), cid), pos


def _clip(strs, pos, rwy, min_rem=MIN_REM):
    return clip_strings_to_runways(strs, pos, rwy, min_remainder_m=min_rem)


def test_owner_clip_constant_is_fifty():
    """Owner-supplied; only he moves it (guards silent recalibration)."""
    assert TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M == pytest.approx(50.0)


def test_string_clear_of_the_runway_is_returned_identical():
    s, pos = _string(0.0, 400.0, y=500.0)
    r = _clip([s], pos, _rwy(0.0, 100.0))
    assert r.strings == (s,)                      # same tuple, untouched
    assert r.stats["clipped"] == 0.0


def test_crossing_survives_as_two_collinear_remainders():
    """★ The lawful case. Crossings must survive — and both remainders
    must lie on the ORIGINAL chord, which is the whole point of clipping
    the string rather than the substrate."""
    s, pos = _string(0.0, 400.0)
    r = _clip([s], pos, _rwy(180.0, 220.0))
    assert len(r.strings) == 2
    for a, b, _n, L, _c in r.strings:
        assert a[1] == pytest.approx(0.0) and b[1] == pytest.approx(0.0)
        assert L >= MIN_REM
    assert r.stats["split_in_two"] == 1.0
    lens = sorted(x[3] for x in r.strings)
    assert lens == pytest.approx([180.0, 180.0])


def test_running_along_is_dropped_by_the_floor_with_no_angle_test():
    """★ The rule SUBSUMES the along/across discriminator: a string that
    is mostly interior leaves only sub-floor remainders and disappears,
    with no angle anywhere in the code."""
    s, pos = _string(0.0, 300.0)
    r = _clip([s], pos, _rwy(20.0, 280.0))        # 260 of 300 m interior
    assert r.strings == ()
    assert len(r.dropped) == 2                    # 20 m and 20 m
    assert all(L < MIN_REM for _s, L in r.dropped)


def test_interior_is_discarded_not_kept():
    s, pos = _string(0.0, 400.0)
    r = _clip([s], pos, _rwy(100.0, 300.0))
    for a, b, _n, _L, _c in r.strings:
        assert not (100.0 < a[0] < 300.0)
        assert not (100.0 < b[0] < 300.0)


def test_remainder_exactly_at_the_floor_survives():
    """The floor is inclusive — 'less than 50m' drops, 50 m stays."""
    s, pos = _string(0.0, 250.0)
    r = _clip([s], pos, _rwy(50.0, 250.0))        # remainder exactly 50 m
    assert len(r.strings) == 1
    assert r.strings[0][3] == pytest.approx(50.0)
    assert r.dropped == ()


def test_nodes_are_reattributed_to_their_own_remainder():
    s, pos = _string(0.0, 400.0, step=10.0)
    r = _clip([s], pos, _rwy(180.0, 220.0))
    head, tail = sorted(r.strings, key=lambda x: x[0][0])
    assert all(pos[v][0] <= 180.0 for v in head[2])
    assert all(pos[v][0] >= 220.0 for v in tail[2])
    # no node is claimed twice, and none survives inside the runway
    assert not (set(head[2]) & set(tail[2]))
    assert all(not (180.0 < pos[v][0] < 220.0)
               for v in list(head[2]) + list(tail[2]))


def test_chain_id_is_preserved_through_the_clip():
    s, pos = _string(0.0, 400.0, cid=7)
    r = _clip([s], pos, _rwy(180.0, 220.0))
    assert {x[4] for x in r.strings} == {7}


def test_duty_band_is_counted_not_resolved():
    """★ [50, 100) — his clip floor clears it, his string-duty threshold
    does not.  This module COUNTS the interaction and hands the number
    up; it must never decide it."""
    s, pos = _string(0.0, 260.0)
    r = _clip([s], pos, _rwy(60.0, 200.0))        # 60 m and 60 m remain
    assert len(r.strings) == 2
    assert len(r.in_duty_band) == 2
    assert all(MIN_REM <= L < DUTY for _s, L in r.in_duty_band)
    # counted, but NOT dropped — the resolution is Fable's
    assert r.stats["in_duty_band"] == 2.0


def test_outline_is_required_never_derived():
    s, pos = _string(0.0, 400.0)
    with pytest.raises(ValueError):
        clip_strings_to_runways([s], pos, None, min_remainder_m=MIN_REM)
    with pytest.raises(TypeError):
        clip_strings_to_runways([s], pos, _rwy(0.0, 10.0))  # type: ignore


def test_empty_outline_list_is_a_no_op():
    s, pos = _string(0.0, 400.0)
    r = clip_strings_to_runways([s], pos, [], min_remainder_m=MIN_REM)
    assert r.strings == (s,)


def test_multiple_runways_all_clip():
    s, pos = _string(0.0, 700.0)
    r = _clip([s], pos, [_rwy(180.0, 220.0), _rwy(420.0, 460.0)])
    assert len(r.strings) == 3
    assert r.stats["split_in_two"] == 1.0


def test_clip_is_deterministic():
    s, pos = _string(0.0, 400.0)
    a = _clip([s], pos, _rwy(180.0, 220.0))
    b = _clip([s], pos, _rwy(180.0, 220.0))
    assert a.strings == b.strings and a.stats == b.stats


# ── FABLE'S NAMED REGRESSION PINS (2026-07-31) ──────────────────────
# Three properties the owner's clip must hold for good.  Each is pinned
# against the mechanism that would break it, not against a number.

def test_pin_crossing_survives_collinear_with_its_anchor_intact():
    """PIN 1 — a crossing survives as remainders that are COLLINEAR with
    the original chord, and the clause-1 runway-crossing anchor the chain
    carries is still on that line.

    This is why the clip binds on EMITTED STRINGS: §2 step 1 seats the
    runway-crossing value as a clause-1 anchor ON THE CHAIN, so the chain
    must span the crossing.  Substrate clipping would sever it into two
    independently-solving strings at the point continuity is hardest law.
    """
    s, pos = _string(0.0, 400.0)
    anchor = (200.0, 0.0)                     # the crossing value's seat
    r = _clip([s], pos, _rwy(180.0, 220.0))
    assert len(r.strings) == 2
    a0, b0 = s[0], s[1]
    ux = (b0[0] - a0[0]) / s[3]
    uy = (b0[1] - a0[1]) / s[3]
    for a, b, _n, _L, _c in r.strings:
        for p in (a, b):
            cross = ((p[0] - a0[0]) * -uy + (p[1] - a0[1]) * ux)
            assert abs(cross) < 1e-9          # exactly on the parent line
    # the anchor's seat still lies on the shared line both remainders use
    cross_anchor = ((anchor[0] - a0[0]) * -uy + (anchor[1] - a0[1]) * ux)
    assert abs(cross_anchor) < 1e-9


def test_pin_along_runway_string_drops_via_the_floor_only():
    """PIN 2 — an along-runway string disappears through the 50 m floor,
    with NO angle test anywhere in the path that produced it."""
    from auto_patch.elevation_per_surface.route_profile import (
        string_substrate as _ss)
    s, pos = _string(0.0, 400.0)
    r = _clip([s], pos, _rwy(30.0, 370.0))     # 340 of 400 m interior
    assert r.strings == ()
    assert r.dropped and all(L < MIN_REM for _s, L in r.dropped)
    # Scan the COMPILED NAMES, not the source text: the prose says
    # "load-bearing" and a source-text scan would fail on its own
    # docstring.  co_names is what the code actually calls.
    names = set(_ss.clip_strings_to_runways.__code__.co_names)
    for banned in ("atan2", "degrees", "acos", "radians"):
        assert banned not in names, (
            f"an angle test crept into the clip: {banned}")


def test_pin_on20_class_keeps_its_off_runway_majority():
    """PIN 3 — the ON-20 class: a long string clipping a runway obliquely
    near one end keeps its off-runway majority as ONE remainder.

    Measured instance: ON-20, 427 m, 85 % on the owner's drawn way
    -39326, 70 m contiguous inside 05R/23L -> survives as a single 338 m
    remainder under the ruled widened outline.
    """
    s, pos = _string(0.0, 427.0)
    r = _clip([s], pos, _rwy(357.0, 427.0))    # 70 m inside, at one end
    assert len(r.strings) == 1
    kept = r.strings[0]
    assert kept[3] == pytest.approx(357.0)
    assert kept[3] / s[3] > 0.8                # the majority survives
    assert r.stats["split_in_two"] == 0.0
