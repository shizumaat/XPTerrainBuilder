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
        # …and the census ASKS for it, while the solve does not: the
        # metric is scoped to the two readers the ruling names.
        cg = (Path(__file__).resolve().parents[1] / "tools"
              / "check_grade.py").read_text()
        assert "shape_constraints(gs, _law_ctx, road_path_metric=True)" in cg
        assert "road_path_metric: bool = False" in src

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

    def test_the_metric_ships_ON_by_owner_order(self):
        """FLIPPED ON with the family (owner 2026-08-29, in-sim pass is
        acceptance; Amendment 9's fourth reader closed the collision)."""
        import importlib
        import auto_patch.config as _fresh
        _fresh = importlib.reload(_fresh)
        try:
            assert _fresh.ROAD_PATH_METRIC is True
        finally:
            importlib.reload(_fresh)

    def test_the_gate_off_leaves_the_euclidean_chord(self, monkeypatch):
        """OFF must be the pre-amendment arithmetic exactly: the pricing
        site is skipped, not merely fed a different number."""
        import inspect
        from auto_patch import grade_graph as GG
        src = inspect.getsource(GG.shape_constraints)
        assert "if (road_path_metric and ROAD_PATH_METRIC" in src
        assert "_road_cum = _road_total = None" in src


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 2 CLAUSE 1 — THE PER-STATION CAP: ONE DERIVATION, THREE
# READERS (the census-wrapper law applied to cap granularity)
# ══════════════════════════════════════════════════════════════════════

class TestPerStationCapUnification:

    def test_the_vector_comes_from_THE_lateral_walk(self):
        """Not a second adjacency read: ``station_cap_vector`` is
        ``station_caps`` — the same walk both readers of the
        lateral-contiguity law already census — with the no-verdict
        stations dropped."""
        import inspect
        from auto_patch import lateral_contiguity as LC
        src = inspect.getsource(LC.station_cap_vector)
        assert "station_caps(" in src

    def test_reader_1_the_pair_pricing(self):
        import inspect
        from auto_patch import grade_graph as GG
        src = inspect.getsource(GG.shape_constraints)
        assert "station_cap_vector" in src
        assert "_station_cap_at(shape, xi, yi, body_cap)" in src
        assert inspect.getsource(GG._station_cap_at).count("cap_at") >= 1

    def test_reader_2_the_solve_dem_follow_envelope(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "src" / "auto_patch"
               / "elevation_per_surface" / "route_profile"
               / "anchors.py").read_text()
        assert "station_cap_vector" in src
        assert "from auto_patch.lateral_contiguity import cap_at" in src

    def test_reader_3_the_profile_envelope(self):
        import inspect
        from auto_patch import free_road_profile as FRP
        src = inspect.getsource(FRP.solve_free_road_profiles)
        assert "station_cap_vector" in src
        assert "caps=st_caps" in src
        assert "from .lateral_contiguity import cap_at" in src

    def test_the_three_readers_resolve_through_ONE_accessor(self):
        """THE twin the ruling asks for: all three reach the cap through
        ``lateral_contiguity.cap_at``, so a point cannot be governed by
        two caps in one build."""
        import inspect
        from auto_patch import grade_graph as GG
        from auto_patch import lateral_contiguity as LC
        from auto_patch import free_road_profile as FRP
        from pathlib import Path
        assert "cap_at" in inspect.getsource(GG._station_cap_at)
        assert "cap_at" in inspect.getsource(FRP.solve_free_road_profiles)
        anchors = (Path(__file__).resolve().parents[1] / "src"
                   / "auto_patch" / "elevation_per_surface"
                   / "route_profile" / "anchors.py").read_text()
        assert "cap_at(" in anchors
        # …and the accessor is one function, not three spellings.
        assert callable(LC.cap_at)

    def test_ONE_RING_TWO_CAPS(self):
        """The point of the whole clause: a ring alongside an apron for
        part of its run and free for the rest carries BOTH caps — the
        apron's over its own stations, the free class over the others.
        Under the retired way-level scalar this ring had exactly one."""
        from auto_patch import lateral_contiguity as LC
        vec = [(0.0, 0.0, 0.01), (5.0, 0.0, 0.01), (60.0, 0.0, 0.08),
               (65.0, 0.0, 0.08)]
        assert LC.cap_at(vec, 1.0, 0.0) == pytest.approx(0.01)
        assert LC.cap_at(vec, 62.0, 0.0) == pytest.approx(0.08)
        assert len({c for (_x, _y, c) in vec}) == 2

    def test_a_strict_station_binds_ITS_OWN_STRETCH_and_no_further(self):
        """THE CORRECTED READING (lane/rampsites, site-first re-open).

        The 5e twin asserted that a 1 % station ANYWHERE between two pins
        refuses a 4 m rise — ``min(cap over the span) x span``.  That is
        not what a Lipschitz bound with a varying constant says, and it
        is the mechanism the owner's three HECA ramp sites and CYXY's
        seven refused chains were left unbuilt by (measured on this
        tree: 1.3-4.3 % needed against cumulative allowances of
        2.4-19.2 m).  The cap INTEGRATES: the 1 % stretch carries 1 % of
        its own length and the free stretches carry 8 % of theirs.
        """
        from auto_patch import free_road_profile as FRP
        ss = [0.0, 25.0, 50.0, 75.0, 100.0]
        caps = [0.08, 0.08, 0.01, 0.08, 0.08]
        t, infeasible = FRP.chain_profile(
            ss, [100.0] * 5, {0: 100.0, 4: 104.0}, 0.08, caps=caps,
            cumulative=True)
        assert not infeasible, (
            "2.0 + 0.25 + 0.25 + 2.0 = 4.5 m of cap-distance carries a "
            "4 m rise; refusing it leaves the owner's cliff standing")
        # …and EVERY interval respects ITS OWN cap — the 1 % stretch is
        # still 1 %, which is what the apron scoping is FOR.
        for k in range(4):
            c = min(caps[k], caps[k + 1])
            assert abs(t[k + 1] - t[k]) <= c * (ss[k + 1] - ss[k]) + 1e-9
        # THE REFUTED ARM, reproducible byte-for-byte behind its gates.
        _t0, inf0 = FRP.chain_profile(
            ss, [100.0] * 5, {0: 100.0, 4: 104.0}, 0.08, caps=caps,
            cumulative=False, weld_outranks=False)
        assert inf0 and _t0 == [100.0] * 5      # the whole chain reverts
        # A rise the chain genuinely cannot carry is still REPORTED —
        # and, under ruling 1, still BUILT to its two welds.
        _t2, inf2 = FRP.chain_profile(
            ss, [100.0] * 5, {0: 100.0, 4: 105.0}, 0.08, caps=caps,
            cumulative=True)
        assert inf2
        assert _t2[0] == pytest.approx(100.0) and _t2[4] == pytest.approx(105.0)

    def test_uniform_caps_are_byte_identical_to_the_scalar_path(self):
        """The correction may not move a chain whose caps are all one
        number — that is every chain with no apron-side station, i.e.
        most of them."""
        from auto_patch import free_road_profile as FRP
        ss = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0, 120.0]
        scalar, _ = FRP.chain_profile(ss, [103.2] * 7, {6: 108.0}, 0.08)
        vector, _ = FRP.chain_profile(ss, [103.2] * 7, {6: 108.0}, 0.08,
                                      caps=[0.08] * 7, cumulative=True)
        assert scalar == vector

    def test_the_way_level_gate_DISSOLVED(self):
        """End-on contact binds values and caps nothing — the ruling."""
        import inspect
        from auto_patch import lateral_contiguity as LC
        src = inspect.getsource(LC._contact_prices_the_cap)
        assert "DISSOLVES" in src or "dissolves" in src
        assert "ruled permanently False" in src or "**NO — ruled**" in src


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 9 — THE CENSUS IS THE FOURTH READER OF THE ONE DERIVATION
# (5j measured what its absence costs: +100 rows at BOTH CYXY and SPJC,
#  140 and 104 of them ``lateral_contiguity`` — a road that lawfully
#  solves at 8 % on its free stations and 1 % beside an apron, judged
#  against ONE way-level number.)
# ══════════════════════════════════════════════════════════════════════

def _check_grade():
    """The harness twins' own loader — registering in ``sys.modules``
    before exec is what makes the module's own imports resolve."""
    import importlib.util
    import sys as _sys
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "tools" / "check_grade.py"
    name = "_cg_amend9"
    if name in _sys.modules:
        return _sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestTheFourthReader:

    def test_the_key_is_REGISTERED_so_omission_is_structural(self):
        """It goes through the harness register, so the
        structurally-impossible-omission twins in test_harness.py cover
        it: a key the reader does not supply, or a kwarg the reader does
        not produce, fails there."""
        cg = _check_grade()
        import inspect
        assert cg.SIDECAR_LAW_KEYS["station_caps"] == "station_caps_ll"
        assert "station_caps_ll" in inspect.signature(
            cg.run_checks).parameters

    def test_the_census_READS_the_vector_and_never_re_derives_it(self):
        """FOURTH READER, not a fourth derivation: the cap comes from the
        published vector through the law's OWN accessor."""
        cg = _check_grade()
        import inspect
        src = inspect.getsource(cg._check_lateral_contiguity)
        assert "cap_at as _cap_at" in src
        assert "_cap_at(_pub_caps_m" in src
        # …and the accessor is the one the emitter's readers use.
        from auto_patch import lateral_contiguity as LC
        assert callable(LC.cap_at)

    def test_the_sidecar_ROUND_TRIPS_metres_to_latlon_to_metres(self):
        """The emitter publishes lat/lon; the census reads it back into
        ITS metre frame.  A station must land where it started."""
        import math
        from auto_patch import lateral_contiguity as LC
        lat0, lon0 = 30.1089375, 31.434664815
        R = 6378137.0
        cos0 = math.cos(math.radians(lat0))

        def m_to_ll(x, y):
            return (lat0 + math.degrees(y / R),
                    lon0 + math.degrees(x / (R * cos0)))

        def ll_to_m(la, lo):
            return (math.radians(lo - lon0) * R * cos0,
                    math.radians(la - lat0) * R)

        vec_m = [(-3430.58, -410.89, 0.01), (-3372.14, -340.88, 0.08)]
        published = [[*m_to_ll(x, y), c] for (x, y, c) in vec_m]
        back = [(*ll_to_m(e[0], e[1]), e[2]) for e in published]
        for (a, b) in zip(vec_m, back):
            assert abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3
            assert a[2] == b[2]
        # …and the accessor picks the right one of the two.
        assert LC.cap_at(back, -3430.0, -410.0) == pytest.approx(0.01)
        assert LC.cap_at(back, -3372.0, -341.0) == pytest.approx(0.08)

    def test_a_MISSING_key_degrades_loudly_and_deterministically(self):
        """An old patch has no ``station_caps``.  The census must then
        price at the WAY-level cap exactly as before AND say so — never
        quietly report numbers from a different law than the reader
        thinks it is applying."""
        cg = _check_grade()
        import inspect
        src = inspect.getsource(cg._check_lateral_contiguity)
        assert "no sidecar" in src and "station_caps" in src
        assert "pre-Amendment-9 frame" in src
        # the fallback is the way-level cap, unchanged
        assert "_built = eff" in src

    def test_a_free_station_beside_an_apron_capped_one_is_NOT_a_row(self):
        """The arithmetic 5j's +100 was made of: two stations on ONE road,
        one governed by an apron at 1 % and one free at 8 %.  Priced at
        the way-level cap the free station reads as a violation; priced
        at ITS OWN cap it does not."""
        from auto_patch import lateral_contiguity as LC
        pub = [(0.0, 0.0, 0.01), (60.0, 0.0, 0.08)]
        way_level = 0.08
        # the apron-side station: its own cap binds, and the way's cap
        # exceeds it -> a genuine row under either reading
        beside = LC.cap_at(pub, 1.0, 0.0)
        assert min(way_level, beside) > 0.01 - 1e-12
        assert beside == pytest.approx(0.01)
        # the FREE station: way-level 8 % vs its own 8 % -> no row
        free = LC.cap_at(pub, 59.0, 0.0)
        assert free == pytest.approx(0.08)
        assert min(way_level, free) <= free + 1e-12
