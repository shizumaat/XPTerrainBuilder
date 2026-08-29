"""THE ROAD'S OWN PATH METRIC — round-5b spec Amendment 1 twins.

Owner ruling 2026-08-28, on lane/hecar5b's measured fork: *"WITHIN-SHAPE
ROAD-FAMILY PAIRS ARE PRICED ALONG THE ROAD'S OWN PATH METRIC (the
route-metric-within-shape precedent extended to the road family), and a
chord that LEAVES the shape's own pavement polygon is the GAP-CHORD class
— never priced as surface grade.  ONE implementation, consumed by both
readers."*

THE COLLISION THESE PIN (measured, lane/hecar5b): the free-road profile
solves a chain's ramp in the PATH coordinate and the within-shape law
priced the result by EUCLIDEAN CHORD, so a path-lawful 8 % ramp across a
U-loop read 8.33-9.11 % — CYXY gained 120 within-shape road rows, every
one of them exactly 8 % x (path / chord).

Hand-computed geometry, no build, no network, no solver.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch import config as CFG                          # noqa: E402
from auto_patch import grade_law as GL                        # noqa: E402
from auto_patch import groundside as GS                       # noqa: E402

def _pair_ctx(**kw):
    """A road ``PairContext`` with the law's required positional facts
    filled in — only the clause under test varies."""
    base = dict(role="service_road", dist=10.0, ring_adjacent=False,
                a_seam=False, b_seam=False, a_building=False,
                b_building=False, spine_caps=(), body_cap=0.08)
    base.update(kw)
    return GL.PairContext(**base)


#: A 6 m x 100 m road rect — the shape whose facing long edges are 6 m
#: apart in the plane and half a lap apart along the walk.
ROAD_RING = [(0.0, 0.0), (100.0, 0.0), (100.0, 6.0), (0.0, 6.0)]


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 1 — PATH, NOT CHORD (and the arithmetic that made CYXY's +120)
# ══════════════════════════════════════════════════════════════════════

class TestThePathMetric:

    def test_the_walk_is_never_tighter_than_the_chord(self):
        """The posture the airside route metric already takes: a metric
        that RELAXES only.  A ring walk is >= the chord by the triangle
        inequality, so no pair can be tightened by this law."""
        cum, total = GL.ring_path_cumulative(ROAD_RING)
        for i in range(len(ROAD_RING)):
            for j in range(len(ROAD_RING)):
                if i == j:
                    continue
                (xa, ya), (xb, yb) = ROAD_RING[i], ROAD_RING[j]
                chord = math.hypot(xa - xb, ya - yb)
                d = GL.road_pair_distance(ROAD_RING, cum, total, i, j, chord)
                assert d >= chord - 1e-9

    def test_the_diagonal_across_the_loop_is_priced_at_the_WALK(self):
        cum, total = GL.ring_path_cumulative(ROAD_RING)
        chord = math.hypot(100.0, 6.0)                 # ~100.18 m
        d = GL.road_pair_distance(ROAD_RING, cum, total, 0, 2, chord)
        assert d == pytest.approx(106.0, abs=0.01)     # 100 + 6, the walk

    def test_the_metric_is_SCOPED_to_longitudinal_pairs(self, ):
        """MEASURED SCOPE (this lane, CYXY): applied to every pair of the
        ring the walk also relaxed the DIAGONAL cross-section pairs — the
        ones the road CROSS-SECTION law (RULINGS 2026-08-25g) rides on —
        and CYXY gained 46 road_cross_section + 102 transverse rows.  A
        cross-section is measured ACROSS the road by definition, so it
        keeps the chord; the walk prices travel ALONG the road, which is
        what the profile solves in.  ONE predicate decides which is which,
        in both readers."""
        import inspect
        from auto_patch import grade_graph as GG
        src = inspect.getsource(GG.shape_constraints)
        assert "_road_cum is not None and not _xsec_pair" in src
        band = inspect.getsource(GS._chord_band)
        assert "path is not None and not _xsec_pair" in band
        # …and the predicate is THE law's, not a local re-spelling.
        assert GS._pair_is_transverse is GL.pair_is_transverse

    def test_the_facing_cross_section_pair_is_UNCHANGED(self):
        """SCOPE: the law relaxes the pairs that go AROUND, not the ones
        straight across.  A road's cross-section stays 6 m wide and its
        own 2 % transverse law goes on pricing it."""
        cum, total = GL.ring_path_cumulative(ROAD_RING)
        d = GL.road_pair_distance(ROAD_RING, cum, total, 0, 3, 6.0)
        assert d == pytest.approx(6.0, abs=1e-9)

    def test_THE_CYXY_ARITHMETIC_falls_out(self):
        """The measured rows were 8 % x (path/chord) = 8.33-9.11 %.  A
        1.0 m rise over a 100.18 m chord whose WALK is 106.0 m reads
        0.998 % on the chord and 0.943 % on the walk: the same surface,
        priced by the metric the profile solved it in."""
        cum, total = GL.ring_path_cumulative(ROAD_RING)
        chord = math.hypot(100.0, 6.0)
        walk = GL.road_pair_distance(ROAD_RING, cum, total, 0, 2, chord)
        rise = CFG.SERVICE_ROAD_MAX_GRADE * walk       # an 8 % ramp on the walk
        assert rise / walk <= CFG.SERVICE_ROAD_MAX_GRADE + 1e-9
        assert rise / chord > CFG.SERVICE_ROAD_MAX_GRADE   # the collision
        assert (rise / chord) / (rise / walk) == pytest.approx(
            walk / chord, rel=1e-9)


# ══════════════════════════════════════════════════════════════════════
# CLAUSE 1 (other half) — THE GAP CHORD, BOTH SIDES
# ══════════════════════════════════════════════════════════════════════

class TestTheGapChord:

    def test_a_chord_that_LEAVES_the_pavement_is_not_priced(self):
        """RULINGS 2026-08-24b's class, and it is STANDING law in
        ``classify_pair`` — pinned here because Amendment 1 composes with
        it: the two legs of a U with open ground between them are not a
        graded pair at all."""
        import inspect
        src = inspect.getsource(GL.classify_pair)
        assert "leaves the pavement is not a surface path" in src
        # …and the predicate is asked for every non-ring-adjacent pair.
        ctx = _pair_ctx(dist=50.0, ring_adjacent=False,
                        visible_fn=lambda: False)
        assert GL.classify_pair(ctx) is GL.SKIP

    def test_a_chord_INSIDE_the_pavement_IS_priced(self):
        ctx = _pair_ctx(dist=50.0, ring_adjacent=False,
                        visible_fn=lambda: True)
        assert GL.classify_pair(ctx) is not GL.SKIP

    def test_a_RING_EDGE_is_never_gap_skipped(self):
        """A ring edge is a physical stretch of surface, not a chord —
        the standing exemption, kept."""
        ctx = _pair_ctx(dist=5.0, ring_adjacent=True,
                        visible_fn=lambda: False)
        assert GL.classify_pair(ctx) is not GL.SKIP


# ══════════════════════════════════════════════════════════════════════
# "ONE IMPLEMENTATION, BOTH READERS" — the census-wrapper law, on a metric
# ══════════════════════════════════════════════════════════════════════

class TestTwoReadersOnePath:

    def test_the_census_prices_through_the_law_function(self):
        """``check_grade.iter_shape_grade_constraints`` reaches the road
        pair distance through ``grade_graph.shape_constraints``, which
        calls ``grade_law.road_pair_distance`` — there is no second
        distance in the validator."""
        import inspect
        from auto_patch import grade_graph as GG
        src = inspect.getsource(GG.shape_constraints)
        assert "road_pair_distance" in src
        assert "ring_path_cumulative" in src

    def test_the_limiter_prices_through_THE_SAME_function(self):
        import inspect
        band = inspect.getsource(GS._chord_band)
        assert "_GL_ROAD_PAIR_DISTANCE" in band
        assert GS._GL_ROAD_PAIR_DISTANCE is GL.road_pair_distance

    def test_the_two_readers_agree_pair_for_pair(self):
        """THE twin the census-wrapper law asks for: give both readers
        the same ring and assert they price every pair identically."""
        cum, total = GL.ring_path_cumulative(ROAD_RING)
        for i in range(len(ROAD_RING)):
            for j in range(len(ROAD_RING)):
                if i == j:
                    continue
                (xa, ya), (xb, yb) = ROAD_RING[i], ROAD_RING[j]
                chord = math.hypot(xa - xb, ya - yb)
                law = GL.road_pair_distance(ROAD_RING, cum, total, i, j,
                                            chord)
                limiter = GS._GL_ROAD_PAIR_DISTANCE(
                    ROAD_RING, cum, total, i, j, chord)
                assert law == limiter


# ══════════════════════════════════════════════════════════════════════
# THE GATE
# ══════════════════════════════════════════════════════════════════════

class TestTheGate:

    def test_the_metric_ships_OFF_until_its_arm_is_measured(self):
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.ROAD_PATH_METRIC is False
        finally:
            importlib.reload(_fresh)

    def test_the_gate_off_leaves_the_euclidean_chord(self, monkeypatch):
        """OFF must be the pre-amendment arithmetic exactly: the pricing
        site is skipped, not merely fed a different number."""
        import inspect
        from auto_patch import grade_graph as GG
        src = inspect.getsource(GG.shape_constraints)
        assert "if (ROAD_PATH_METRIC and shape.role in GL.ROAD_ROLES)" in src
        assert "_road_cum = _road_total = None" in src
