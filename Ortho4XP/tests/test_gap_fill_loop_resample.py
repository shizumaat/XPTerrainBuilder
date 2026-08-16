"""Collar / interior ring LOOP RESAMPLE ladder — ruling 2026-07-25.

``gap_fill._build_collar_rings`` resamples every ring loop at the station
step and, when the chords of that resample could "cut inside pavement at a
concave boundary detail", densifies (``n`` → ``2n`` → ``4n``) until the
closed polyline is covered.  The cover target used to be
``gap.buffer(-0.8)`` — a PROXY for the real criterion — and when all three
rungs failed against that proxy the code fell through to
``loop.simplify(0.75)`` with **no cover test at all**.

The incoherence that ruling fixes, reproduced exactly at SPJC's (731,-160)
pocket: at ``n`` the cover test fails LEGITIMATELY (13.1 m of chord
genuinely outside the pocket), but at ``2n`` and ``4n`` the only failure is
the 0.8 m margin itself — 0 m outside the pocket.  The guard therefore
rejected a 324-node candidate with real clearance in favour of a 61-node
polyline over 2,419 m with chords to 320 m, and law values interpolated
linearly across those chords with no bench station between them.  14 of 49
HECA collar loops (29 %) took the same fallback, chords to 445 m.

Pinned here:

* the ladder against the inner cover is UNCHANGED (a loop that passes it
  today still passes it, at the same rung);
* when it fails, the SAME three candidates are re-tested against
  ``gap_poly`` itself and the SPARSEST that passes is taken — 2n at this
  fixture, 0 m outside the gap;
* the simplify fallback, when it is genuinely needed, is POST-DENSIFIED so
  no chord exceeds the station step and every node carries a law record.

Headless synthetic geometry only — a pavement frame around a pocket with a
thin pavement PENINSULA intruding, which is the concave-detail class the
ladder exists for.
"""
import math

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch import elevation as ELEV
from auto_patch import gap_fill as GF
from auto_patch.layout import BuiltShape, ROLE_APRON

# ── THE APRON CORRIDOR MOVED UNDER THIS FIXTURE (W2, 2026-08-08) ──────
# These twins build a drainage-spine gap between APRON parents, and
# ``drainage_spine_envelope`` takes its FLOOR — the crater guard —
# straight from ``adjacent_ground_envelope``'s apron branch.  W2 retires
# the apron surround (reg-set §5.1 T2/T3, ruling 4) and, on the ICAO
# ruleset, gives the apron edge no lip at all (F-3: ICAO states none),
# so that corridor is open downward from the edge and the spine has no
# floor to build a chain against — measured here as zero accepted
# chains, not an error.  Under the fabric model that IS the drape.
#
# BISECTED, not assumed: disabling EITHER
# ``O4_FABRIC_W2_RETIRE_APRON_SURROUND`` or
# ``O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY`` alone restores all 15.  The
# emitted-geometry consequence (gap fill stops filling between ICAO
# aprons) is REPORTED for the battery round to adjudicate; the resample
# mechanics these twins own are unchanged and are certified here on the
# flag-OFF arm.
@pytest.fixture(autouse=True)
def _pre_w2_apron_corridor(monkeypatch):
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_APRON_SURROUND", "0")
    monkeypatch.setenv("O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY", "0")


STEP_M = GF.GAP_FILL_SPINE_STEP_M
GAP_W, GAP_H = 600.0, 400.0
PEN_W, PEN_LEN = 40.0, 200.0
EDGE_ALT_M = 100.0
TERRAIN_M = 96.0            # below the band floor, so every station engages


class _FakeLayout:
    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)

    def ll_to_m(self, lat, lon):
        return (lon * 111320.0, lat * 111320.0)

    def __init__(self, shapes):
        self.shapes = shapes
        self.airport_boundary = None
        self.anchor = (0.0, 0.0)


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _shape(poly):
    return BuiltShape(polygon=poly, role=ROLE_APRON,
                      node_altitudes=[EDGE_ALT_M]
                      * len(poly.exterior.coords))


def _pocket():
    """``(gap_poly, airside)`` — a rectangular pocket with a thin pavement
    peninsula intruding from the north edge."""
    pen = _rect(GAP_W / 2 - PEN_W / 2, GAP_H - PEN_LEN,
                GAP_W / 2 + PEN_W / 2, GAP_H)
    gap = _rect(0, 0, GAP_W, GAP_H).difference(pen)
    frame = [
        _rect(-40, -40, GAP_W + 40, 0),
        _rect(-40, GAP_H, GAP_W + 40, GAP_H + 40),
        _rect(-40, 0, 0, GAP_H),
        _rect(GAP_W, 0, GAP_W + 40, GAP_H),
        pen,
    ]
    return gap, [_shape(p) for p in frame]


# ── THE RING GEOMETRY MOVED UNDER THIS FIXTURE (F3, 2026-08-15) ──────
# The ring-2 region is now the pocket ERODED by
# ``GAP_PAVEMENT_CONFORM_MARGIN_M`` (owner ruling "GAP INTERIOR RINGS
# NEVER CLIFF AGAINST PAVEMENT"; spec docs/specs/gap-conformance-
# spec.md law 2).  At the shipped 10 m margin the loop stands 10 m off
# the peninsula and its chords clear the inner cover at the FIRST rung
# — the concave detail this module exists for is eroded away, and every
# ladder assertion below would be vacuous.
#
# The ladder itself is UNCHANGED code, so it is certified here on a
# SMALL margin (1 m), which puts the loop back against the peninsula
# exactly as the retired band-annulus core did: measured, that
# reproduces the module's premise verbatim — inner-cover 0, gap-cover 1,
# simplify 0.  Nothing about the ladder is margin-dependent; the margin
# only decides whether a concave detail reaches the loop at all.
_LADDER_MARGIN_M = 1.0


def _build(monkeypatch, *, force_fallback: bool = False):
    monkeypatch.setattr(
        ELEV, "_sample_dem",
        lambda dem, tla, tlo, lat, lon: TERRAIN_M)
    monkeypatch.setattr(GF, "GAP_PAVEMENT_CONFORM_MARGIN_M",
                        _LADDER_MARGIN_M)
    GF._CONFORM_INDEX_CACHE.clear()
    GF._NEAREST_INDEX_CACHE.clear()
    if force_fallback:
        # Neuter the gap-cover rung: the ONLY way past the ladder is then
        # the simplify fallback, which is what this exercises.
        monkeypatch.setattr(GF, "_ring_covered_by",
                            lambda cover, pts: False)
    gap, airside = _pocket()
    layout = _FakeLayout(list(airside))
    res = GF._build_collar_rings(layout, airside, gap, object(), 0, 0, [],
                                 STEP_M)
    return gap, res


def _chords(closed_pts):
    return [math.hypot(closed_pts[i + 1][0] - closed_pts[i][0],
                       closed_pts[i + 1][1] - closed_pts[i][1])
            for i in range(len(closed_pts) - 1)]


def _ladder_n(loop):
    """The ladder's base rung count, computed exactly as the emitter does."""
    perim = loop.length
    n = max(8, int(round(perim / STEP_M)))
    if perim / n < GF._RING_MIN_NODE_SPACING_M:
        n = max(3, int(perim // GF._RING_MIN_NODE_SPACING_M))
    return n


# ══════════════════════════════════════════════════════════════════════
# Fixture guard — this pocket really does defeat the inner-cover rung
# ══════════════════════════════════════════════════════════════════════

def test_fixture_defeats_the_inner_cover_ladder(monkeypatch):
    """Without this the rest of the module would be vacuous: the pocket's
    peninsula must make all three inner-cover rungs fail."""
    _gap, res = _build(monkeypatch)
    st = res["stats"]
    assert st["resample_inner"] == 0
    assert st["resample_gap"] + st["resample_simplify"] >= 1


# ══════════════════════════════════════════════════════════════════════
# Rung 2 — the real criterion, sparsest candidate that passes it
# ══════════════════════════════════════════════════════════════════════

def test_gap_cover_rung_accepts_the_sparsest_passing_candidate(monkeypatch):
    gap, res = _build(monkeypatch)
    st = res["stats"]
    assert st["resample_gap"] == 1, "the gap-cover rung must carry this loop"
    assert st["resample_simplify"] == 0, "no fallback is warranted here"

    loops = res["ring2_loops"]
    assert len(loops) == 1
    loop = loops[0]
    n = _ladder_n(loop)
    assert len(res["chains"]) == 1
    pts, _alts = res["chains"][0]
    # SPARSEST-THAT-PASSES.  The accepted candidate is a ladder rung, it
    # passes the real criterion, and EVERY sparser rung fails it — that
    # is the ruling, stated without hard-coding which rung this
    # particular geometry lands on (the rung moves with the ring
    # offset; the LAW does not).
    accepted = len(pts) - 1
    rungs = [n, 2 * n, 4 * n]
    assert accepted in rungs, f"accepted {accepted} is not a ladder rung"

    def _cand(n_try):
        perim = loop.length
        return [(float(loop.interpolate((i / n_try) * perim).x),
                 float(loop.interpolate((i / n_try) * perim).y))
                for i in range(n_try)]

    assert GF._ring_covered_by(gap, _cand(accepted))
    for sparser in [r for r in rungs if r < accepted]:
        assert not GF._ring_covered_by(gap, _cand(sparser)), (
            f"rung {sparser} passes the gap cover — the ladder must have "
            f"taken it instead of {accepted}")


def test_accepted_loop_lies_entirely_inside_the_gap(monkeypatch):
    """The criterion the ladder is FOR: zero chord length outside the gap
    (the 0.8 m inner-cover margin is a proxy for exactly this)."""
    gap, res = _build(monkeypatch)
    pts, _alts = res["chains"][0]
    assert LineString(pts).difference(gap).length == pytest.approx(0.0,
                                                                  abs=1e-9)


def test_accepted_loop_is_a_uniform_dense_resample(monkeypatch):
    """A ladder candidate is an equal-arc interpolation, so its chords are
    all within a hair of ``perimeter / n_try`` — nothing like the ragged
    simplify polyline it replaces."""
    _gap, res = _build(monkeypatch)
    loop = res["ring2_loops"][0]
    pts, _alts = res["chains"][0]
    # The rung the ladder landed on decides the arc spacing — read it off
    # the accepted node count rather than assuming one.
    spacing = loop.length / (len(pts) - 1)
    ch = _chords(pts)
    # A chord of an equal-ARC resample is at most its arc length.
    assert max(ch) <= spacing + 1e-6
    assert min(ch) > 0.35 * spacing


def test_every_accepted_node_carries_a_law_value(monkeypatch):
    _gap, res = _build(monkeypatch)
    pts, alts = res["chains"][0]
    assert len(alts) == len(pts)
    assert alts[0] == alts[-1]
    assert all(a is not None for a in alts)


# ══════════════════════════════════════════════════════════════════════
# Rung 3 — the simplify fallback is post-densified
# ══════════════════════════════════════════════════════════════════════

def test_forced_fallback_reproduces_the_long_chord_problem(monkeypatch):
    """Evidence that the fallback IS the pathology being fixed: before the
    densify, the simplified loop's worst chord is hundreds of metres."""
    _gap, res = _build(monkeypatch, force_fallback=True)
    st = res["stats"]
    assert st["resample_simplify"] == 1
    assert st["resample_max_chord_m"] > 10.0 * STEP_M


def test_forced_fallback_is_densified_to_the_station_step(monkeypatch):
    _gap, res = _build(monkeypatch, force_fallback=True)
    pts, alts = res["chains"][0]
    ch = _chords(pts)
    assert max(ch) <= STEP_M + 1e-6, (
        f"post-densify chord {max(ch):.1f} m exceeds the {STEP_M:.0f} m step")
    # Per-node law records: the whole point of the densify is that the
    # added nodes enter the value bench, not just the polyline.
    assert len(alts) == len(pts)
    assert all(a is not None for a in alts)


def test_forced_fallback_stays_inside_the_gap(monkeypatch):
    """Densification inserts COLLINEAR points, so it cannot move the
    polyline off the (already accepted) simplify geometry."""
    gap, res = _build(monkeypatch, force_fallback=True)
    pts, _alts = res["chains"][0]
    assert LineString(pts).difference(gap).length == pytest.approx(0.0,
                                                                  abs=1e-9)


# ══════════════════════════════════════════════════════════════════════
# The densifier itself
# ══════════════════════════════════════════════════════════════════════

class TestDensifier:
    def test_short_chords_are_untouched(self):
        pts = [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)]
        assert GF._densify_closed_ring(pts, 10.0) == pts

    def test_long_chords_are_split_below_the_cap(self):
        pts = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        out = GF._densify_closed_ring(pts, 15.0)
        ch = _chords(out + [out[0]])
        assert max(ch) <= 15.0 + 1e-9
        assert len(out) > len(pts)

    def test_inserted_points_are_exactly_collinear(self):
        """Geometrically UNCHANGED is the whole licence for this pass: the
        ring's area and its shapely geometry must be bit-comparable."""
        pts = [(0.0, 0.0), (317.0, 11.0), (250.0, 400.0), (13.0, 260.0)]
        out = GF._densify_closed_ring(pts, 9.0)
        before = Polygon(pts)
        after = Polygon(out)
        assert after.area == pytest.approx(before.area, rel=1e-12)
        assert after.symmetric_difference(before).area == pytest.approx(
            0.0, abs=1e-9)
        # every ORIGINAL vertex survives, in order
        assert all(p in out for p in pts)

    def test_degenerate_inputs_are_returned_unchanged(self):
        pts = [(0.0, 0.0), (100.0, 0.0)]
        assert GF._densify_closed_ring(pts, 5.0) == pts
        assert GF._densify_closed_ring(pts, 0.0) == pts


class TestRingCoveredBy:
    def test_none_cover_means_no_test(self):
        assert GF._ring_covered_by(None, [(0.0, 0.0), (1.0, 0.0),
                                          (1.0, 1.0)]) is True

    def test_empty_cover_rejects(self):
        empty = Polygon([(0, 0), (1, 0), (1, 1)]).buffer(-10.0)
        assert empty.is_empty
        assert GF._ring_covered_by(empty, [(0.0, 0.0), (1.0, 0.0),
                                           (1.0, 1.0)]) is False

    def test_a_chord_leaving_the_cover_rejects(self):
        cover = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        assert GF._ring_covered_by(cover, [(1.0, 1.0), (9.0, 1.0),
                                           (9.0, 9.0)]) is True
        assert GF._ring_covered_by(cover, [(1.0, 1.0), (20.0, 1.0),
                                           (9.0, 9.0)]) is False
