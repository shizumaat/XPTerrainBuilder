"""Membership round — context-conservative absorption (the one mechanism
this family LANDED), plus the retained-footprint registry it records.

Spec: ``docs/specs/membership-round-spec.md``.  Owner rulings:
``docs/RULINGS.md`` (lateral-contiguity absorption is class-universal;
airside is king; groundside terrace law; single-solve architecture; law
compliance, not instrument-zero).

What survived, and what did not — all three verdicts are MEASURED:

1. **LANDED — §V2.A, context-conservative absorption.**  Absorption had
   DELETED the road's footprint from two solve-input CONTEXT sets (the
   ``build_context`` road-carve zone, the ``_build_shape_constraints``
   airside visibility union), moving the solve globally — 21 HECA runway
   vertices 4.2-4.6 km away.  Retaining the footprint restored
   airside-is-king: 0 of 514 runway vertices move gate-on vs gate-off.
2. **RETIRED unimplemented — V1's grade-graph membership predicate**
   (measured a non-mechanism; nothing here re-lands it).
3. **RETIRED on measurement — §V2.B, the merged-surface exemption from
   the finalize groundside chain.**  Exempting the surface made things
   worse (HECA groundside within-shape 398 → 2,161), because
   ``anchors.adopt_projected_mouths`` deliberately writes the lot ring
   over cap and names the post-solve chord limiter as the pass that
   repairs it — so the exemption removed the surface's only repairer.
   Merged-surface lawfulness has to be solved IN the solve; that is the
   one-solve groundside round's job.  ``TestFinalizeChainHasNoExemption``
   exists so the exemption cannot return silently.

The registry stays: identifying a merged surface across the chain's
fresh-``BuiltShape`` boundary is the hard part, and it is solved.
"""
from __future__ import annotations

import importlib
import types

import pytest
from shapely.geometry import Polygon

from auto_patch.layout import (BuiltShape, absorbed_road_context_polys,
                               is_absorbed_merged_surface)


# ═════════════════════════════════════════════════════════════════════
# helpers
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    # ``anchor`` only so the groundside passes can build their DEM sampler;
    # ``dem=None`` makes every sample None, which is what keeps these tests
    # DEM-free (a rebuilt piece then carries no altitudes, which is exactly
    # the value loss the exemption exists to prevent).
    return types.SimpleNamespace(shapes=list(shapes), anchor=(0.0, 0.0))


def _dem_lot(x0, y0, x1, y1, z=10.0):
    poly = _rect(x0, y0, x1, y1)
    return BuiltShape(polygon=poly, role="groundside_pavement",
                      node_altitudes=[z] * len(poly.exterior.coords))


@pytest.fixture()
def law_off(monkeypatch):
    """Everything this round rides on is OFF.

    NO LONGER the shipping default — both gates flipped ON 2026-08-04
    (spec kill-half §1), so this fixture now asks for the pre-flip world
    explicitly.  What it pins (the passes are inert with the law off) is
    unchanged."""
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "0")
    monkeypatch.setenv("O4_SERVICE_LOT_ABSORPTION", "0")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


@pytest.fixture()
def lateral_on(monkeypatch):
    """The lateral-contiguity law ON, the class-universal gate OFF."""
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    # KILL-HALF FLIP 2026-08-04 (spec kill-half §1): this gate now DEFAULTS
    # ON, so "off" must be asked for explicitly.  The property under test
    # is unchanged.
    monkeypatch.setenv("O4_SERVICE_LOT_ABSORPTION", "0")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


@pytest.fixture()
def absorption_on(monkeypatch):
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    monkeypatch.setenv("O4_SERVICE_LOT_ABSORPTION", "1")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


def _absorbed_lot_layout(gs):
    """A lot that has ABSORBED a road stretch, plus an ordinary lot far
    away — the two populations every exemption test needs to separate."""
    lot = _dem_lot(0, 0, 100, 60)
    road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
    other = _dem_lot(500, 500, 560, 560, z=20.0)
    layout = _layout([lot, road, other])
    summary = gs.apply_lateral_contiguity_law(layout, "TEST")
    assert summary["absorbed_dem_host"] == 1, summary
    return layout, lot, other, summary


# ═════════════════════════════════════════════════════════════════════
# §V2.A — absorption is CONTEXT-CONSERVATIVE
# ═════════════════════════════════════════════════════════════════════

class TestRetainedContextFootprint:

    # The absorption machinery needs a host STRICTER than the road (owner
    # 2026-08-12 put a lot on the road limit, so a road beside a lot binds
    # nothing).  These scenes exercise the MACHINERY, so they supply the
    # precondition explicitly; the ruling itself is pinned in
    # test_owner_constants_round.TestTheRoadLimitEndsLotAbsorption.
    @pytest.fixture(autouse=True)
    def _absorption_precondition(self, absorption_on, stricter_lot_cap):
        stricter_lot_cap()

    def test_the_absorbed_stretch_is_retained_as_a_footprint(
            self, absorption_on):
        layout, lot, _other, summary = _absorbed_lot_layout(absorption_on)
        assert summary["context_retained"] == 1
        assert summary["context_retained_dem_host"] == 1
        polys = absorbed_road_context_polys(layout)
        assert len(polys) == 1
        # the FOOTPRINT of the road as it was before the merge
        assert polys[0].area == pytest.approx(100 * 10, rel=1e-6)
        # …and it is a footprint, not a resurrection: no shape carries it
        assert not [s for s in layout.shapes if s.role == "service_road"]

    def test_a_NON_DEM_host_absorption_is_retained_too(self,
                                                       absorption_on):
        """Conservation is unconditional on WHICH class hosted the merge.
        A conservation that applied to the DEM-lot arm only would itself
        be a context difference between the two arms of the round's own
        A/B.

        THE HOST WAS AN AIRSIDE JUNCTION UNTIL 2026-08-26b.  RULINGS
        2026-08-25b (spec ``road-band-seal-scope-spec.md`` Amendment 1)
        took the APRON out of the absorption path — an edge-sharing road
        conforms to its law and stays road-family population — and
        RULINGS 2026-08-26b item 2 (spec
        ``road-airside-crossing-conformance-spec.md`` §1.1) widened that
        contact term to EVERY airside neighbour, so there is no
        airside-hosted merge left to conserve at all.  The invariant this
        twin exists for is about the HOST'S CLASS (does the non-DEM
        branch conserve?), so the host here is a lot carrying no
        per-vertex altitudes; the junction's new behaviour is pinned just
        below, beside the apron's."""
        lot = BuiltShape(polygon=_rect(0, 0, 100, 60),
                         role="groundside_pavement")
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([lot, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 1
        assert summary["context_retained"] == 1
        assert summary["context_retained_dem_host"] == 0
        assert len(absorbed_road_context_polys(layout)) == 1

    def test_a_junction_host_conforms_instead_of_absorbing(self,
                                                           absorption_on):
        """RULINGS 2026-08-26b item 2 — the 25b contact term, widened from
        ``{"apron"}`` to the canonical airside family.  A road sharing an
        edge with a taxi JUNCTION now takes the junction's cap and keeps
        its own role, geometry and population, exactly as the apron case
        below: conformance is PRICING, never population (Amendment 1's
        measured reason — absorbing these rings moved HECA airside
        1,735 -> 1,948, the airside-contamination direction)."""
        junction = BuiltShape(polygon=_rect(0, 0, 100, 60), role="junction")
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([junction, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 0
        assert summary["apron_contact"] == 1
        assert summary["context_retained"] == 0
        assert absorbed_road_context_polys(layout) == []
        assert road in layout.shapes and road.role == "service_road"
        from auto_patch.config import TAXI_MAX_GRADE
        assert road.lateral_cap == pytest.approx(TAXI_MAX_GRADE)
        assert junction.polygon.area == pytest.approx(100 * 60, rel=1e-6)

    def test_an_apron_host_conforms_instead_of_absorbing(self,
                                                         absorption_on):
        """RULINGS 2026-08-25b as amended: the edge-sharing road takes the
        apron's cap and KEEPS its own role, geometry and population — so
        there is nothing to conserve, because nothing was consumed."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 60), role="apron")
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([apron, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 0
        assert summary["apron_contact"] == 1
        assert summary["context_retained"] == 0
        assert absorbed_road_context_polys(layout) == []
        assert road in layout.shapes and road.role == "service_road"
        assert road.lateral_cap == 0.01
        assert apron.polygon.area == pytest.approx(100 * 60, rel=1e-6)

    def test_the_road_carve_zone_is_absorption_invariant(self,
                                                         absorption_on):
        """THE §V2.A invariant: the law's context geometry is the same
        whether or not the stretch was absorbed."""
        from auto_patch import grade_graph as GG
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        before = GG.build_context(_layout([_dem_lot(0, 0, 100, 60), road]))
        layout, _lot, _o, _s = _absorbed_lot_layout(absorption_on)
        after = GG.build_context(layout)
        assert before.road_zone is not None and after.road_zone is not None
        # the zone is PREPARED, so compare it where it matters: a point on
        # the absorbed stretch is still inside the carve zone.
        from shapely.geometry import Point
        p = Point(50.0, 65.0)
        assert before.road_zone.contains(p)
        assert after.road_zone.contains(p)

    def test_the_airside_visibility_union_keeps_the_stretch(
            self, absorption_on):
        """``_build_shape_constraints``'s ``airside_buf`` is built from
        PAVEMENT_ROLES shapes; a stretch absorbed into a groundside lot is
        no longer one, so without the retained footprint the union loses
        real pavement and distant junction chords stop being visible."""
        from auto_patch.elevation_per_surface import solver_primitives as SP
        layout, _lot, _o, _s = _absorbed_lot_layout(absorption_on)
        polys = [s.polygon for s in layout.shapes
                 if s.role in SP.PAVEMENT_ROLES and s.polygon is not None]
        assert polys == []                       # nothing airside survives
        assert len(absorbed_road_context_polys(layout)) == 1

    def test_retention_counts_exactly_the_deleted_shapes(self,
                                                         absorption_on):
        """One retained footprint per stretch that actually MERGED.  A
        piece whose merge failed comes back as a shape and is already in
        every context set — retaining it too would double-count it."""
        layout, _lot, _o, summary = _absorbed_lot_layout(absorption_on)
        assert summary["merge_failed"] == 0
        assert summary["context_retained"] == summary["absorbed"]
        assert (len(absorbed_road_context_polys(layout))
                == summary["absorbed"])


class TestContextConservationInertness:

    def test_readers_tolerate_a_layout_without_the_field(self):
        """The validator reaches ``build_context`` with a shape bag, and
        old pickles have no such field."""
        assert absorbed_road_context_polys(types.SimpleNamespace()) == []
        assert is_absorbed_merged_surface(types.SimpleNamespace(), None) \
            is False


# ═════════════════════════════════════════════════════════════════════
# the retained-footprint REGISTRY (§V2.A's record; §V2.B retired on it)
# ═════════════════════════════════════════════════════════════════════

class TestMergedSurfaceIdentity:

    # The absorption machinery needs a host STRICTER than the road (owner
    # 2026-08-12 put a lot on the road limit, so a road beside a lot binds
    # nothing).  These scenes exercise the MACHINERY, so they supply the
    # precondition explicitly; the ruling itself is pinned in
    # test_owner_constants_round.TestTheRoadLimitEndsLotAbsorption.
    @pytest.fixture(autouse=True)
    def _absorption_precondition(self, absorption_on, stricter_lot_cap):
        stricter_lot_cap()

    def test_the_merged_host_is_recognised(self, absorption_on):
        layout, lot, other, _s = _absorbed_lot_layout(absorption_on)
        assert is_absorbed_merged_surface(layout, lot) is True
        assert is_absorbed_merged_surface(layout, other) is False

    def test_identity_survives_a_fresh_builtshape(self, absorption_on):
        """THE keying requirement (spec §V2.B): the finalize chain rebuilds
        every piece it rewrites, so a per-shape flag is dead by the time
        the exemption is decided.  A geometry-keyed registry is not."""
        layout, lot, _o, _s = _absorbed_lot_layout(absorption_on)
        rebuilt = BuiltShape(polygon=lot.polygon,
                             role="groundside_pavement",
                             ref="groundside",
                             node_altitudes=list(lot.node_altitudes))
        assert not hasattr(rebuilt, "absorbed_graph_member")
        assert is_absorbed_merged_surface(layout, rebuilt) is True

    def test_a_mere_neighbour_is_not_the_merged_surface(self,
                                                        absorption_on):
        """A shape that only TOUCHES the absorbed footprint — or laps a
        minority of it — is a neighbour, not the host: the merged surface
        is the one holding the MAJORITY of the stretch."""
        layout, _lot, _o, _s = _absorbed_lot_layout(absorption_on)
        assert is_absorbed_merged_surface(
            layout, _dem_lot(0, 70, 100, 130)) is False      # touching
        assert is_absorbed_merged_surface(
            layout, _dem_lot(0, 65, 100, 130)) is False      # laps half

    def test_an_airside_host_merge_registers_no_groundside_surface(
            self, absorption_on):
        """Only DEM-followed (groundside) hosts are merged SURFACES: an
        apron absorption must not make some unrelated lot answer True."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 60), role="apron")
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        lot = _dem_lot(0, 60, 100, 70)      # same footprint as the stretch
        layout = _layout([apron, road, lot])
        absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert is_absorbed_merged_surface(layout, lot) is False


class TestFinalizeChainHasNoExemption:
    """THE V2.2 RETREAT, bound on all four passes.  §V2.B exempted the
    merged surface from the finalize groundside chain; measured, that is
    net-negative — ``anchors.adopt_projected_mouths`` deliberately leaves
    the ring over cap and names the post-solve chord limiter as the pass
    that repairs it, so exempting the surface removes its only repairer.
    These tests exist so the exemption cannot come back silently: a merged
    surface is an ORDINARY lot to every pass in the chain."""

    # The absorption machinery needs a host STRICTER than the road (owner
    # 2026-08-12 put a lot on the road limit, so a road beside a lot binds
    # nothing).  These scenes exercise the MACHINERY, so they supply the
    # precondition explicitly; the ruling itself is pinned in
    # test_owner_constants_round.TestTheRoadLimitEndsLotAbsorption.
    @pytest.fixture(autouse=True)
    def _absorption_precondition(self, absorption_on, stricter_lot_cap):
        stricter_lot_cap()

    def test_merge_touching_groundside_merges_it(self, absorption_on):
        gs = absorption_on
        layout, lot, _o, _s = _absorbed_lot_layout(gs)
        touching = _dem_lot(100, 0, 200, 70, z=10.0)
        layout.shapes.append(touching)
        assert is_absorbed_merged_surface(layout, lot) is True
        assert gs._merge_touching_groundside(layout, None, 0, 0) == 1

    def test_separation_clips_the_merged_surface(self, absorption_on):
        gs = absorption_on
        layout, lot, _o, _s = _absorbed_lot_layout(gs)
        # a building overlapping the lot clips it back, like any lot
        layout.shapes.append(BuiltShape(polygon=_rect(40, 20, 60, 40),
                                        role="building"))
        ring_before = list(lot.polygon.exterior.coords)
        gs._separate_groundside_from_airside(layout, None, 0, 0,
                                             preserve_field=True)
        rings = [list(s.polygon.exterior.coords) for s in layout.shapes
                 if s.role == "groundside_pavement"]
        assert ring_before not in rings

    def test_deconfliction_uses_the_ordinary_largest_first_order(
            self, absorption_on):
        """No seeding ahead of the order: a LARGER overlapping lot wins and
        the merged surface yields, exactly as two ordinary lots would."""
        gs = absorption_on
        layout, lot, _o, _s = _absorbed_lot_layout(gs)
        big = _dem_lot(50, 65, 400, 400, z=15.0)
        layout.shapes.append(big)
        assert is_absorbed_merged_surface(layout, big) is False
        gs._deconflict_groundside_overlaps(layout, None, 0, 0)
        assert any(s is big for s in layout.shapes)        # largest kept
        assert not any(s is lot for s in layout.shapes)    # it yielded

    def test_the_chord_limiter_rewrites_the_merged_ring(self,
                                                        absorption_on):
        gs = absorption_on
        layout, lot, other, _s = _absorbed_lot_layout(gs)
        steep = [0.0 if k % 2 else 50.0
                 for k in range(len(lot.polygon.exterior.coords))]
        lot.node_altitudes = list(steep)
        other.node_altitudes = [
            0.0 if k % 2 else 50.0
            for k in range(len(other.polygon.exterior.coords))]
        assert gs._grade_limit_groundside_chords(layout) == 2
        assert list(lot.node_altitudes) != steep


# ═════════════════════════════════════════════════════════════════════
# the chord law FUNCTION (the one piece of §V2.1 that outlived it)
# ═════════════════════════════════════════════════════════════════════

def _diag_dem(g=0.04):
    """A DEM whose gradient is ``g`` in BOTH axes: every axis-aligned ring
    edge reads ``g`` (lawful at 4 %), while the DIAGONAL chord reads
    ``g·√2`` = 5.66 % — the exact shape of the gap V2 measured."""
    return lambda x, y: g * (x + y)


def _ring_and_alts(shape):
    ring = list(shape.polygon.exterior.coords)
    alts = list(shape.node_altitudes)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring, alts = ring[:-1], alts[:-1]
    return ring, alts


def _worst_pair_grades(shape):
    """``(worst adjacent ring grade, worst ALL-pair chord grade)`` — the
    two metrics the round separates.  Chords under 0.5 m are skipped, the
    same floor ``tools/check_grade`` applies."""
    import math
    ring, alts = _ring_and_alts(shape)
    n = len(ring)
    adj = chord = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(ring[i][0] - ring[j][0], ring[i][1] - ring[j][1])
            if d < 0.5:
                continue
            g = abs(alts[i] - alts[j]) / d
            chord = max(chord, g)
            if j == i + 1 or (i == 0 and j == n - 1):
                adj = max(adj, g)
    return adj, chord


class TestChordLimitLawFunction:
    """``chord_limit_ring_altitudes`` is the ALL-PAIR half of the
    groundside law — the metric ``check_grade`` applies to a plane shape,
    and the reason a ring-ramp limit alone is not enough.  V2.1 tried to
    apply it at absorption time and the mouth adoption erased the result,
    so the PLACEMENT is retired; the function is the surviving asset and
    its contract is tested here directly (its live callers are the
    finalize chord limiter and ``apply_groundside_reach``)."""

    def test_a_ring_ramp_lawful_field_can_still_be_chord_unlawful(self):
        """The premise, stated as a test: a diagonal DEM gives every
        axis-aligned ring edge 4 % and the diagonal chord 5.66 %."""
        from auto_patch import config as cfg
        lot = _dem_lot(0, 0, 100, 100)
        dem = _diag_dem()
        ring, _a = _ring_and_alts(lot)
        lot.node_altitudes = [dem(x, y) for x, y in ring] + [dem(*ring[0])]
        adj, chord = _worst_pair_grades(lot)
        assert adj <= cfg.GROUNDSIDE_MAX_GRADE + 1e-9
        assert chord > cfg.GROUNDSIDE_MAX_GRADE + 1e-3

    def test_it_returns_a_chord_lawful_field(self):
        from auto_patch import config as cfg
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 100, 100)
        dem = _diag_dem()
        ring, _a = _ring_and_alts(lot)
        alts = [dem(x, y) for x, y in ring]
        out = gs.chord_limit_ring_altitudes(ring, alts,
                                            cfg.GROUNDSIDE_MAX_GRADE)
        lot.node_altitudes = out + [out[0]]     # the CLOSED convention
        _adj, chord = _worst_pair_grades(lot)
        assert chord <= cfg.GROUNDSIDE_MAX_GRADE + 1e-3

    def test_it_CUTS_AND_FILLS(self):
        """R7c (owner ruling 2026-08-15, "groundside lots cut and fill"):
        the field is the LAWFUL field CLOSEST to the input, not the
        largest one under it.  SUPERSEDES ``test_it_only_ever_lowers``:
        the one-sided law was the last writer that undid every lawful
        FILL the seat and reach passes made, and the measured mechanism
        of the CYXY lot-377 hollow's persistence."""
        from auto_patch import config as cfg
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 100, 100)
        dem = _diag_dem()
        ring, _a = _ring_and_alts(lot)
        alts = [dem(x, y) for x, y in ring]
        out = gs.chord_limit_ring_altitudes(ring, alts,
                                            cfg.GROUNDSIDE_MAX_GRADE)
        assert any(b < a - 1e-6 for a, b in zip(alts, out)), "no cut"
        assert any(b > a + 1e-6 for a, b in zip(alts, out)), "no fill"

    def test_a_deep_hollow_is_FILLED_back_to_its_lawful_band(self):
        """The apron-42 mirror stated as a law test: one vertex dropped
        far below a ring the cap cannot reach it from is RAISED into the
        band — under the one-sided law it stayed where it was and the
        whole ring was cut down to meet it."""
        from auto_patch import config as cfg
        import auto_patch.groundside as gs
        ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        alts = [700.0, 700.0, 700.0, 690.0]     # the last one is a pit
        out = gs.chord_limit_ring_altitudes(ring, alts,
                                            cfg.GROUNDSIDE_MAX_GRADE)
        # 100 m at 5 % reaches 5 m: the pit may not sit 10 m below.
        assert out[3] > 690.0 + 1e-6
        # and the SHARED ring is lawful on every chord afterwards.
        import math
        for i in range(4):
            for j in range(4):
                if i == j:
                    continue
                d = math.dist(ring[i], ring[j])
                assert abs(out[i] - out[j]) <= \
                    cfg.GROUNDSIDE_MAX_GRADE * d + 5e-3

    def test_a_PINNED_weld_is_never_moved_and_generates_the_band(self):
        """R7c's band is the WELD-reachable one: a pinned weld holds its
        law value and everything else clamps into
        ``[weld − cap·d, weld + cap·d]``."""
        from auto_patch import config as cfg
        import auto_patch.groundside as gs
        ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        alts = [690.0, 700.0, 700.0, 700.0]     # index 0 is the weld
        out = gs.chord_limit_ring_altitudes(
            ring, alts, cfg.GROUNDSIDE_MAX_GRADE, pinned={0})
        assert out[0] == 690.0, "a weld is law — it may not move"
        # 100 m at 5 % = 5 m of reach from the weld.
        assert out[1] <= 690.0 + cfg.GROUNDSIDE_MAX_GRADE * 100.0 + 5e-3

    def test_an_already_lawful_field_is_left_alone(self):
        """Cut-and-fill is a CLAMP, not a smoother: a field already
        inside the band is returned unchanged."""
        from auto_patch import config as cfg
        import auto_patch.groundside as gs
        ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
        alts = [700.0, 701.0, 701.5, 700.5]
        out = gs.chord_limit_ring_altitudes(ring, alts,
                                            cfg.GROUNDSIDE_MAX_GRADE)
        assert all(abs(a - b) <= 5e-3 for a, b in zip(alts, out))

    def test_a_stricter_cap_binds_harder(self):
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 100, 100)
        dem = _diag_dem()
        ring, _a = _ring_and_alts(lot)
        alts = [dem(x, y) for x, y in ring]
        out = gs.chord_limit_ring_altitudes(ring, alts, 0.01)
        lot.node_altitudes = out + [out[0]]     # the CLOSED convention
        _adj, chord = _worst_pair_grades(lot)
        assert chord <= 0.01 + 1e-3


class TestFinalizeChainUnchanged:
    """The chain's behaviour on an ordinary lot is the pre-round one, and
    stays so with every gate off — the V2.2 retreat left it untouched."""

    def test_ordinary_lots_still_merge(self, law_off):
        gs = law_off
        a = _dem_lot(0, 0, 100, 60)
        b = _dem_lot(100, 0, 200, 60)
        layout = _layout([a, b])
        assert gs._merge_touching_groundside(layout, None, 0, 0) == 1

    def test_ordinary_lots_are_still_chord_limited(self, law_off):
        gs = law_off
        lot = _dem_lot(0, 0, 100, 60)
        lot.node_altitudes = [
            0.0 if k % 2 else 50.0
            for k in range(len(lot.polygon.exterior.coords))]
        layout = _layout([lot])
        assert gs._grade_limit_groundside_chords(layout) == 1

    def test_ordinary_lots_are_still_deconflicted(self, law_off):
        gs = law_off
        big = _dem_lot(0, 0, 200, 200)
        small = _dem_lot(50, 50, 150, 150)
        layout = _layout([big, small])
        assert gs._deconflict_groundside_overlaps(layout, None, 0, 0) == 1


# ═════════════════════════════════════════════════════════════════════
# THE ROAD CHORD LIMITER — the road family joins the finalize-stage
# Lipschitz clamp (wave-3 step 1; spec
# docs/specs/road-chord-limiter-spec.md).  Ruled basis: ROADS CARRY
# SPINES LIKE TAXIWAYS (2026-08-15 evening); ONE CORRIDOR = ONE LAW
# OBJECT (2026-08-12b); airside is king (standing).
# ═════════════════════════════════════════════════════════════════════

def _svc(x0, y0, x1, y1, alts=None, role="service_road", z=10.0):
    """A road-family rect carrying the CLOSED altitude convention."""
    poly = _rect(x0, y0, x1, y1)
    n = len(poly.exterior.coords)
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=(list(alts) if alts is not None
                                      else [z] * n))


def _open_ring_alts(shape):
    ring = list(shape.polygon.exterior.coords)
    alts = list(shape.node_altitudes)
    if ring and ring[0] == ring[-1]:
        ring, alts = ring[:-1], alts[:-1]
    return ring, alts


def _worst_chord_grade(shape):
    """Worst ALL-PAIR chord grade of one ring — the within-shape
    validator's own metric."""
    import math
    ring, alts = _open_ring_alts(shape)
    worst = 0.0
    for i in range(len(ring)):
        for j in range(i + 1, len(ring)):
            d = math.hypot(ring[i][0] - ring[j][0], ring[i][1] - ring[j][1])
            if d < 1e-9:
                continue
            worst = max(worst, abs(alts[i] - alts[j]) / d)
    return worst


class TestTheRoadFamilyIsChordLimited:
    """§1 SCOPE + §4 KERNEL: the road roles are clamped by the SAME pass,
    the same two-sided kernel, and ``tunnel_ramp`` is not."""

    def test_a_road_ring_over_cap_is_clamped_two_sided(self):
        """(a) A road ring whose INTERIOR chord exceeds the road cap is
        pulled inside it — and the clamp both CUTS and FILLS (R7c
        posture): the high vertex comes down AND the low one comes up."""
        import auto_patch.groundside as gs
        from auto_patch import config as cfg
        # 40 m x 20 m road face: one corner 4 m high, one 4 m low —
        # 20 %+ across the ring's own chords, far past the 8 % road cap.
        road = _svc(0, 0, 40, 20, alts=[10.0, 14.0, 10.0, 6.0, 10.0])
        layout = _layout([road])
        assert gs._grade_limit_groundside_chords(layout) == 1
        _ring, out = _open_ring_alts(road)
        cap = cfg.ROLE_GRADE_LIMITS["service_road"]
        assert _worst_chord_grade(road) <= cap + 5e-3
        assert out[1] < 14.0, "the high vertex was not CUT"
        assert out[3] > 6.0, "the low vertex was not FILLED"

    def test_the_road_cap_comes_from_ROLE_GRADE_LIMITS(self):
        """§2 CAP: one constant, read from the one table — not a second
        number invented in the limiter."""
        import auto_patch.groundside as gs
        from auto_patch import config as cfg
        assert (gs._chord_limit_cap_for_role("service_road")
                == cfg.ROLE_GRADE_LIMITS["service_road"])
        assert (gs._chord_limit_cap_for_role("service_junction")
                == cfg.ROLE_GRADE_LIMITS["service_junction"])
        # …and the LOT keeps its shaping margin (the standing law).
        assert (gs._chord_limit_cap_for_role("groundside_pavement")
                == cfg.GROUNDSIDE_MAX_GRADE)

    def test_tunnel_ramp_is_never_touched(self):
        """(e) ``tunnel_ramp``'s law is the portal walk — this pass must
        not be able to see it."""
        import auto_patch.groundside as gs
        ramp = _svc(0, 0, 40, 20, alts=[10.0, 30.0, 10.0, -10.0, 10.0],
                    role="tunnel_ramp")
        before = list(ramp.node_altitudes)
        layout = _layout([ramp])
        assert gs._grade_limit_groundside_chords(layout) == 0
        assert list(ramp.node_altitudes) == before
        assert "tunnel_ramp" not in gs._CHORD_LIMIT_ROLES

    def test_a_below_grade_ring_inside_a_tunnel_cut_keeps_its_values(self):
        """§4 EXTENSION (spec
        ``docs/specs/tunnel-corridor-node-book-exclusion-spec.md``, the
        2026-08-25 owner-ordered fix).

        The role exemption above is the WRONG AXIS on its own: OTHH's
        site-1 bore floor is a ``groundside_pavement`` ring, not a
        ``tunnel_ramp``, and the unified node book handed it the
        surrounding road's at-grade bench (+2.28/+2.96 against a −1.1 m
        floor).  The exemption that matters is by AUTHORITY — any ring
        belonging to the portal walk's OWN OPEN CUT
        (``layout.tunnel_open_cut_polys``) leaves this book entirely,
        keeping its values and minting no shared key.

        RE-KEYED (RULINGS 2026-08-31b, redesign spec §5.2, census #51):
        the region used to be R14-1's claim set, which retired with the
        claim class.  Full battery of twins, including the seam-probe-4
        membership record: ``tests/test_tunnel_corridor_exclusion.py``.
        """
        import auto_patch.groundside as gs
        floor = _dem_lot(0, 0, 40, 10, z=-1.1)
        road = _svc(40, 0, 60, 10, z=2.3, role="service_junction")
        layout = _layout([floor, road])
        layout.tunnel_open_cut_polys = [floor.polygon]
        before = list(floor.node_altitudes)
        assert gs._grade_limit_groundside_chords(layout) == 0
        assert list(floor.node_altitudes) == before
        assert layout._chord_limit_stats["nodes"] == 0
        assert (layout._chord_limit_stats["tunnel_corridor_excluded_rings"]
                == 2)


class TestTheCorridorChainIsOneLawObject:
    """§3 CORRIDOR COHERENCE — the shared-node unification spans
    rect↔junction↔rect, so the clamp cannot mint a step at a segment
    boundary."""

    def _chain(self):
        # rect A [0,50] — junction [50,60] — rect B [60,110], all 10 m
        # wide and sharing their boundary vertices exactly.
        a = _svc(0, 0, 50, 10, alts=[6.0, 10.0, 10.0, 6.0, 6.0])
        j = _svc(50, 0, 60, 10, alts=[10.0, 10.4, 10.4, 10.0, 10.0],
                 role="service_junction")
        b = _svc(60, 0, 110, 10, alts=[10.4, 14.0, 14.0, 10.4, 10.4])
        return a, j, b

    def test_the_chain_shares_node_values_across_shapes(self):
        """(b) After the clamp, every node two chain members share holds
        ONE value — no minted step at the joints."""
        import auto_patch.groundside as gs
        a, j, b = self._chain()
        layout = _layout([a, j, b])
        gs._grade_limit_groundside_chords(layout)
        vals = {}
        for shape in (a, j, b):
            ring, alts = _open_ring_alts(shape)
            for (x, y), v in zip(ring, alts):
                k = (round(x, 2), round(y, 2))
                if k in vals:
                    assert vals[k] == pytest.approx(v, abs=1e-9), (
                        f"chain joint {k} minted a step "
                        f"{vals[k]} vs {v}")
                vals[k] = v

    def test_the_census_counts_the_chain_joints(self):
        """§2/§3 report: the pass says out loud what it unified and where
        a stricter cap won."""
        import auto_patch.groundside as gs
        a, j, b = self._chain()
        lot = _dem_lot(0, 10, 50, 40, z=10.0)      # welds rect A's flank
        layout = _layout([a, j, b, lot])
        gs._grade_limit_groundside_chords(layout)
        st = layout._chord_limit_stats
        assert st["shared_rect_junction_nodes"] == 4      # two joints
        assert st["shared_road_lot_nodes"] == 2
        # lot 5 % vs road 8 % at a shared node ⇒ the STRICTER cap wins
        assert st["stricter_cap_nodes"] == 2
        assert st["rings"]["service_road"] == 2
        assert st["rings"]["service_junction"] == 1

    def test_a_shared_node_takes_the_stricter_cap(self):
        """The pre-delegated rule, as behaviour: the road chords that
        touch a lot-shared node are budgeted at the LOT's cap."""
        import auto_patch.groundside as gs
        from auto_patch import config as cfg
        road = _svc(0, 0, 40, 10, alts=[10.0, 13.0, 13.0, 10.0, 10.0])
        # the lot shares the road's two right-hand corners
        lot = _dem_lot(40, 0, 80, 10, z=13.0)
        layout = _layout([road, lot])
        gs._grade_limit_groundside_chords(layout)
        assert _worst_chord_grade(road) <= cfg.GROUNDSIDE_MAX_GRADE + 5e-3


class TestTheRoadRoundLeavesTheLotPassAlone:
    """(d) With NO road shapes present the pass is the pre-round one —
    same node identity, same scalar-cap arithmetic, same output."""

    def test_a_lot_only_layout_is_byte_identical_to_the_kernel(self):
        import auto_patch.groundside as gs
        from auto_patch import config as cfg
        lot = _dem_lot(0, 0, 100, 60)
        lot.node_altitudes = [
            0.0 if k % 2 else 50.0
            for k in range(len(lot.polygon.exterior.coords))]
        ring, alts = _open_ring_alts(lot)
        # the reference: the ONE kernel, one scalar cap, no per-node caps
        keys = [(round(x, 2), round(y, 2)) for x, y in ring]
        vals = [float(a) for a in alts]
        live = list(range(len(keys)))
        for _round in range(4):
            before = list(vals)
            gs._chord_cut_and_fill(keys, vals, live, live,
                                   cfg.GROUNDSIDE_MAX_GRADE)
            if all(abs(v - b) <= 1e-6 for v, b in zip(vals, before)):
                break
        expect = [round(v, 2) for v in vals]
        layout = _layout([lot])
        assert gs._grade_limit_groundside_chords(layout) == 1
        assert list(lot.node_altitudes) == expect + [expect[0]]

    def test_two_lots_still_key_by_min_within_the_role(self):
        """The historical within-role seed rule (``min`` at a shared
        node) is untouched — only ACROSS roles does precedence decide."""
        import auto_patch.groundside as gs
        a = _dem_lot(0, 0, 50, 20, z=10.0)
        b = _dem_lot(50, 0, 100, 20, z=10.6)
        layout = _layout([a, b])
        gs._grade_limit_groundside_chords(layout)
        _ra, va = _open_ring_alts(a)
        _rb, vb = _open_ring_alts(b)
        shared = [v for (x, y), v in zip(_rb, vb) if round(x, 2) == 50.0]
        assert shared and all(v == pytest.approx(10.0, abs=1e-9)
                              for v in shared)
        assert all(v == pytest.approx(10.0, abs=1e-9) for v in va)


class TestTheEmitAuthorityStillWins:
    """(c) The weld values that EMIT are the road's, and the welds are
    not pinned — the two halves of §4 the measured groundside lesson
    fixes in place."""

    def test_a_shared_node_is_seeded_from_the_ROAD_not_the_lot(self):
        """``AUTHORITY_PRECEDENCE`` is airside-first: at a road↔lot weld
        the emit ships the ROAD's value, so that is the value this pass
        clamps with — never the lot's lower one."""
        import auto_patch.groundside as gs
        from auto_patch.layout import authority_rank
        assert (authority_rank("service_road")
                < authority_rank("groundside_pavement"))
        road = _svc(0, 0, 40, 10, z=10.0)
        lot = _dem_lot(40, 0, 80, 10, z=4.0)   # LOWER, and it shares 2 nodes
        layout = _layout([road, lot])
        gs._grade_limit_groundside_chords(layout)
        _ring, alts = _open_ring_alts(lot)
        weld = [v for (x, y), v in zip(_ring, alts) if round(x, 2) == 40.0]
        assert weld and all(v > 4.0 for v in weld), (
            "the lot's own value survived at a node the ROAD owns")

    def test_the_welds_are_not_pinned(self):
        """A weld node MOVES when the ring's own law needs it to — the
        pinning R7c's literal reading would impose is exactly what the
        CYXY way -10126 measurement refused."""
        import auto_patch.groundside as gs
        road = _svc(0, 0, 40, 10, alts=[10.0, 16.0, 16.0, 10.0, 10.0])
        lot = _dem_lot(40, 0, 80, 10, z=16.0)
        layout = _layout([road, lot])
        gs._grade_limit_groundside_chords(layout)
        _ring, alts = _open_ring_alts(road)
        moved = [v for (x, y), v in zip(_ring, alts) if round(x, 2) == 40.0]
        assert moved and all(v < 16.0 for v in moved), (
            "the weld was pinned — the ring could not reach its law")


class TestAirsideIsDataToTheLimiter:
    """AIRSIDE IS KING (RULINGS, standing; lead adjudication 2026-08-20).
    A node an airside ring claims is DATA to this pass — it seats the
    weld and the road grades from it.  The carrier the pin closes is
    MEASURED: the final projection's airside pass re-projects from the
    SEED, so a groundside rewrite of a shared node moves airside even
    though the projection's partition keeps every groundside PAIR out of
    the airside constraint set."""

    def _welded_scene(self):
        # an APRON (airside) sharing its two right-hand corners with a
        # road that badly needs the clamp
        apron = BuiltShape(polygon=_rect(0, 0, 40, 10), role="apron",
                           node_altitudes=[100.0, 100.2, 100.2, 100.0,
                                           100.0])
        road = _svc(40, 0, 90, 10,
                    alts=[100.2, 106.0, 106.0, 100.2, 100.2])
        return apron, road

    def test_the_airside_ring_is_untouched_to_the_bit(self):
        import auto_patch.groundside as gs
        apron, road = self._welded_scene()
        before = list(apron.node_altitudes)
        layout = _layout([apron, road])
        gs._grade_limit_groundside_chords(layout)
        assert list(apron.node_altitudes) == before

    def test_the_weld_keeps_the_AIRSIDE_value_and_the_road_clamps(self):
        import auto_patch.groundside as gs
        from auto_patch import config as cfg
        apron, road = self._welded_scene()
        layout = _layout([apron, road])
        gs._grade_limit_groundside_chords(layout)
        ring, alts = _open_ring_alts(road)
        weld = [v for (x, y), v in zip(ring, alts) if round(x, 2) == 40.0]
        assert weld and all(v == pytest.approx(100.2, abs=1e-9) for v in weld), (
            "the pass moved a node the apron claims")
        assert _worst_chord_grade(road) <= (
            cfg.ROLE_GRADE_LIMITS["service_road"] + 5e-3), (
            "the road did not clamp against its frozen airside weld")

    def test_the_pin_set_is_the_registry_partition_not_a_list(self):
        """``layout.GROUNDSIDE_ROLES`` decides — a role added there stops
        being pinned with no edit here (the role-literal hazard)."""
        import auto_patch.groundside as gs
        from auto_patch.layout import GROUNDSIDE_ROLES
        apron, road = self._welded_scene()
        layout = _layout([apron, road])
        xy, _canon = gs._airside_claimed_keys(layout)
        assert (40.0, 0.0) in xy and (0.0, 0.0) in xy      # apron ring
        assert (90.0, 0.0) not in xy                        # road-only
        assert "apron" not in GROUNDSIDE_ROLES
        assert {"groundside_pavement", "service_road",
                "service_junction"} <= set(GROUNDSIDE_ROLES)

    def test_a_groundside_only_scene_pins_nothing(self):
        """No airside ring ⇒ the pin set is empty and the pass is the
        one the lot round shipped."""
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 100, 60)
        lot.node_altitudes = [
            0.0 if k % 2 else 50.0
            for k in range(len(lot.polygon.exterior.coords))]
        layout = _layout([lot])
        xy, canon = gs._airside_claimed_keys(layout)
        assert not xy and not canon
        assert gs._grade_limit_groundside_chords(layout) == 1
