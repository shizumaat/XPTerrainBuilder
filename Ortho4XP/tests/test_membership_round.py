"""Membership round V2 — context-conservative absorption + the merged-
surface exemption from the finalize groundside chain.

Spec: ``docs/specs/membership-round-spec.md`` §V2 (V1's grade-graph
membership predicate was MEASURED false and is retired unimplemented —
nothing here re-lands it).  Owner rulings: ``docs/RULINGS.md``
(lateral-contiguity absorption is class-universal; airside is king;
groundside terrace law; law compliance, not instrument-zero).

The two mechanisms this round binds, both measured interventionally:

1. absorption DELETED the road's footprint from two solve-input CONTEXT
   sets (the ``build_context`` road-carve zone, the
   ``_build_shape_constraints`` airside visibility union), which moved the
   solve globally — 21 HECA runway vertices 4.2-4.6 km away;
2. ``finalize.emit_terrain_transition_features``'s groundside chain is a
   SECOND grading authority over the merged ring, and it rebuilds the
   surface as a fresh ``BuiltShape`` (so no per-shape flag can carry the
   exemption — it is keyed on the retained footprint registry).

Both halves are tested on BOTH sides: the behaviour, and the inertness of
the state that ships (the lateral-contiguity law is default-OFF).
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
    """Everything this round rides on is OFF — the shipping default."""
    monkeypatch.delenv("O4_LATERAL_CONTIGUITY_LAW", raising=False)
    monkeypatch.delenv("O4_SERVICE_LOT_ABSORPTION", raising=False)
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


@pytest.fixture()
def lateral_on(monkeypatch):
    """The lateral-contiguity law ON, the class-universal gate OFF."""
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    monkeypatch.delenv("O4_SERVICE_LOT_ABSORPTION", raising=False)
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
# §V2.B — merged surfaces are EXEMPT from the finalize chain
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

    def test_an_airside_host_merge_mints_no_exemption(self, absorption_on):
        """Only DEM-followed (groundside) hosts are merged SURFACES in the
        §V2.B sense; the finalize chain only ever touches groundside, and
        an apron absorption must not exempt some unrelated lot."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 60), role="apron")
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        lot = _dem_lot(0, 60, 100, 70)      # same footprint as the stretch
        layout = _layout([apron, road, lot])
        absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert is_absorbed_merged_surface(layout, lot) is False


class TestFinalizeChainExemption:

    def test_merge_touching_groundside_skips_it(self, absorption_on):
        gs = absorption_on
        layout, lot, _o, _s = _absorbed_lot_layout(gs)
        # a plain lot flush against the merged surface: it WOULD be merged
        touching = _dem_lot(100, 0, 200, 70, z=10.0)
        layout.shapes.append(touching)
        before = lot.polygon.area
        n = gs._merge_touching_groundside(layout, None, 0, 0)
        assert n == 0
        assert lot in layout.shapes
        assert lot.polygon.area == pytest.approx(before, rel=1e-9)

    def test_separation_leaves_the_merged_surface_alone(self,
                                                       absorption_on):
        gs = absorption_on
        layout, lot, _o, _s = _absorbed_lot_layout(gs)
        # a building overlapping the lot would normally clip it back
        layout.shapes.append(BuiltShape(polygon=_rect(40, 20, 60, 40),
                                        role="building"))
        ring_before = list(lot.polygon.exterior.coords)
        alts_before = list(lot.node_altitudes)
        gs._separate_groundside_from_airside(layout, None, 0, 0,
                                             preserve_field=True)
        assert lot in layout.shapes
        assert list(lot.polygon.exterior.coords) == ring_before
        assert list(lot.node_altitudes) == alts_before

    def test_deconfliction_makes_others_yield_to_it(self, absorption_on):
        """The exemption is not merely permissive: the merged surface is
        the authority for its own ring, so an overlapping ordinary lot —
        LARGER, which would otherwise win the largest-first order — yields
        to it instead."""
        gs = absorption_on
        layout, lot, _o, _s = _absorbed_lot_layout(gs)
        # laps a QUARTER of the absorbed stretch — an overlapping
        # neighbour, never the host
        big = _dem_lot(50, 65, 400, 400, z=15.0)
        layout.shapes.append(big)
        assert is_absorbed_merged_surface(layout, big) is False
        gs._deconflict_groundside_overlaps(layout, None, 0, 0)
        assert any(s is lot for s in layout.shapes)    # never clipped
        assert not any(s is big for s in layout.shapes)   # it yielded

    def test_the_chord_limiter_never_rewrites_the_merged_ring(
            self, absorption_on):
        gs = absorption_on
        layout, lot, other, _s = _absorbed_lot_layout(gs)
        # a steep field the limiter would normally pull down hard
        lot.node_altitudes = [
            0.0 if k % 2 else 50.0
            for k in range(len(lot.polygon.exterior.coords))]
        before = list(lot.node_altitudes)
        other.node_altitudes = [
            0.0 if k % 2 else 50.0
            for k in range(len(other.polygon.exterior.coords))]
        gs._grade_limit_groundside_chords(layout)
        assert list(lot.node_altitudes) == before          # exempt
        assert list(other.node_altitudes) != [             # not exempt
            0.0 if k % 2 else 50.0
            for k in range(len(other.polygon.exterior.coords))]


class TestExemptionInertness:
    """Every pass must behave exactly as before when nothing was absorbed —
    the population the exemption must not reach is "every ordinary lot"."""

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
