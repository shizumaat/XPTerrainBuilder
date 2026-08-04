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

    def test_an_airside_host_absorption_is_retained_too(self,
                                                        absorption_on):
        """Conservation is unconditional on WHICH class hosted the merge.
        A conservation that applied to the lot arm only would itself be a
        context difference between the two arms of the round's own A/B."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 60), role="apron")
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([apron, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 1
        assert summary["context_retained"] == 1
        assert summary["context_retained_dem_host"] == 0
        assert len(absorbed_road_context_polys(layout)) == 1

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

    def test_law_off_records_nothing(self, law_off):
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([lot, road])
        summary = law_off.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["context_retained"] == 0
        assert absorbed_road_context_polys(layout) == []

    def test_capped_not_absorbed_records_nothing(self, lateral_on):
        """Gate off, a DEM-followed lot is not a legal host: the road stays
        a road and carries the cap.  Nothing was deleted, nothing is
        retained."""
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([lot, road])
        summary = lateral_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 0
        assert summary["context_retained"] == 0

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

    def test_it_only_ever_lowers(self):
        """The largest lawful field UNDER the input — it never lifts
        pavement above the terrain the ring follows."""
        from auto_patch import config as cfg
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 100, 100)
        dem = _diag_dem()
        ring, _a = _ring_and_alts(lot)
        alts = [dem(x, y) for x, y in ring]
        out = gs.chord_limit_ring_altitudes(ring, alts,
                                            cfg.GROUNDSIDE_MAX_GRADE)
        assert any(b < a - 1e-6 for a, b in zip(alts, out))
        assert all(b <= a + 5e-3 for a, b in zip(alts, out))

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
