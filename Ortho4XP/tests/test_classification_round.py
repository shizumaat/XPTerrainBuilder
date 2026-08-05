"""Classification round — the lateral-contiguity grade law, the scorer's
service-adjacency feature, the needle-collapse source discriminator and the
drainage second-parent lockstep.

Spec: ``docs/specs/classification-round-spec.md``.  Owner rulings:
``docs/RULINGS.md`` (lateral-contiguity grade law, FINAL 2026-08-02;
grade-law completeness standard).

Every law here is TWO-SIDED by requirement (completeness standard): the
generation-binding constraint and its validator twin must read the same
number, so the tests assert the pair, not one side.
"""
import importlib
import math
import os
import types

import pytest
from shapely.geometry import Polygon

from auto_patch.grade_law import (
    DRAINAGE_SPINE_PARENT_ROLES,
    drainage_spine_parents,
    lateral_contiguity_cap,
    lateral_contiguity_segments,
)
from auto_patch.layout import BuiltShape
from auto_patch.pipeline import _collapse_ring_needles


# ═════════════════════════════════════════════════════════════════════
# §2 — the law itself
# ═════════════════════════════════════════════════════════════════════

class TestLateralContiguityLaw:
    def test_strictest_cap_of_the_cross_section(self):
        # "a road alongside or through an apron grades as apron"
        assert lateral_contiguity_cap({"service_junction", "apron"}) == 0.01
        # a road beside a taxiway takes the taxi cap
        assert lateral_contiguity_cap(
            {"service_road", "primary_parallel"}) == 0.015
        # a road beside a groundside lot takes the LOT's cap — the class the
        # earlier apron/taxi-only adoption passes could not express.  The
        # number itself is an owner constant (docs/RULINGS.md 2026-08-03),
        # so it is read from config rather than spelled here.
        from auto_patch import config as _cfg
        assert lateral_contiguity_cap(
            {"service_road", "groundside_pavement"}) == \
            _cfg.GROUNDSIDE_MAX_GRADE
        # a free road is alone in its cross-section and keeps its own cap
        assert lateral_contiguity_cap({"service_road"}) == \
            _cfg.SERVICE_ROAD_MAX_GRADE

    def test_unregulated_classes_are_not_pavement(self):
        # walls / boundary / clearance cuts carry no within-shape cap and
        # never enter the closure
        from auto_patch import config as _cfg
        assert lateral_contiguity_cap({"retaining_wall", "boundary"}) is None
        assert lateral_contiguity_cap(
            {"service_road", "retaining_wall"}) == _cfg.SERVICE_ROAD_MAX_GRADE

    def test_segments_are_maximal_runs(self):
        runs = lateral_contiguity_segments(
            [0.05, 0.05, 0.01, 0.01, 0.01, 0.05])
        assert runs == [(0, 1, 0.05), (2, 4, 0.01), (5, 5, 0.05)]

    def test_a_station_without_a_verdict_breaks_the_run(self):
        # None = off the shape, inside a runway strip (clause 5), or an
        # unmeasurable cross-section: it never JOINS a run.
        runs = lateral_contiguity_segments([0.01, None, 0.01])
        assert runs == [(0, 0, 0.01), (2, 2, 0.01)]


# ═════════════════════════════════════════════════════════════════════
# §2 — the emitter (the owner's two thought tests)
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    return types.SimpleNamespace(shapes=list(shapes))


@pytest.fixture()
def lateral_on(monkeypatch):
    """The law's gate ON, for the emitter tests."""
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    monkeypatch.delenv("O4_LATERAL_CONTIGUITY_LAW", raising=False)
    importlib.reload(cfg)


class TestLateralContiguityEmitter:
    def test_ring_roads_touching_one_apron_become_one_surface(self, lateral_on):
        """Owner: "five ring roads touching one apron are one apron-grade
        surface" — every road shares a flank with the apron along its whole
        length, so every one of them is absorbed and ONE shape remains."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 100), role="apron")
        roads = [
            BuiltShape(polygon=_rect(-10, 0, 0, 100), role="service_road"),
            BuiltShape(polygon=_rect(100, 0, 110, 100), role="service_road"),
            BuiltShape(polygon=_rect(0, -10, 100, 0), role="service_road"),
            BuiltShape(polygon=_rect(0, 100, 100, 110), role="service_road"),
        ]
        layout = _layout([apron] + roads)
        summary = lateral_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["roads"] == 4
        assert summary["absorbed"] == 4
        assert [s.role for s in layout.shapes] == ["apron"]
        merged = layout.shapes[0].polygon
        # one surface, and it is the union (100×100 + four 10×100 strips)
        assert merged.area == pytest.approx(100 * 100 + 4 * 10 * 100, rel=1e-6)

    def test_two_aprons_and_a_connector_keep_the_free_middle(self, lateral_on):
        """Owner: "two aprons joined by a road: only the free between-segment
        is road-capped" — the closure never propagates through the END
        connections, so the middle of the connector keeps the 5 % road law."""
        west = BuiltShape(polygon=_rect(0, 0, 60, 60), role="apron")
        east = BuiltShape(polygon=_rect(160, 0, 220, 60), role="apron")
        # the road runs east-west between them at mid height, touching each
        # apron only at its END face
        road = BuiltShape(polygon=_rect(60, 25, 160, 35), role="service_road")
        layout = _layout([west, east, road])
        summary = lateral_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["roads"] == 1
        assert summary["absorbed"] == 0        # an end connection is not lateral
        roads = [s for s in layout.shapes if s.role == "service_road"]
        assert len(roads) == 1
        assert roads[0].lateral_cap is None    # free: its own 5 %
        assert west.polygon.area == pytest.approx(3600.0)

    def test_a_road_that_leaves_the_apron_is_cut_at_the_mouth(self, lateral_on):
        """Half the road runs along the apron's flank, half runs free: the
        law cuts it at the station where lateral contact ends, absorbs the
        contiguous half and leaves the free half at the road cap."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 60), role="apron")
        road = BuiltShape(polygon=_rect(0, 60, 200, 70), role="service_road")
        layout = _layout([apron, road])
        summary = lateral_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["cut"] == 1
        assert summary["absorbed"] == 1
        assert apron.polygon.area > 6000.0          # grew by the absorbed half
        left = [s for s in layout.shapes if s.role == "service_road"]
        assert left, "the FREE stretch must survive as a road"
        assert all(s.lateral_cap is None for s in left)
        # the surviving road is the free (east) half
        assert min(s.polygon.bounds[0] for s in left) > 60.0




class TestLateralCapLockstep:
    """The cap the solver builds to IS the cap the validator checks."""

    def test_solver_and_validator_read_the_same_cap(self):
        import sys
        from pathlib import Path
        tools = str(Path(__file__).resolve().parent.parent / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import check_grade as CG
        from auto_patch import grade_graph as GG

        gs = GG.GradeShape(role="service_junction", ring=[(0, 0)], keys=[0],
                           lateral_cap=0.01)
        ctx = GG.GradeContext(centerlines=[])
        assert GG._body_cap(gs, ctx, {}) == pytest.approx(0.01)

        way = CG.Way(wid="-1", role="service_junction", ref="", aeroway="",
                     nids=[], elevs=[],
                     tags={"role": "service_junction",
                           "o4_grade_law_cap": "0.010000"})
        assert CG._role_grade_limit(way, 0.05) == pytest.approx(0.01)

    def test_the_cap_only_ever_tightens(self):
        from auto_patch import grade_graph as GG
        gs = GG.GradeShape(role="apron", ring=[(0, 0)], keys=[0],
                           lateral_cap=0.05)
        ctx = GG.GradeContext(centerlines=[])
        # an apron never RELAXES to a road's cap because a road touches it
        assert GG._body_cap(gs, ctx, {}) == pytest.approx(0.01)


# ═════════════════════════════════════════════════════════════════════
# §1 — the scorer's service-adjacency feature
# ═════════════════════════════════════════════════════════════════════

class TestServiceAdjacencyFeature:
    """``service_adj``: road-width pavement sharing a SUBSTANTIAL edge with
    the service network is a service road, never a landside lot."""

    @staticmethod
    def _score(monkeypatch, on, road_poly, neighbours):
        if on:
            monkeypatch.setenv("O4_SCORER_SERVICE_ADJ", "1")
        else:
            monkeypatch.delenv("O4_SCORER_SERVICE_ADJ", raising=False)
        import auto_patch.config as cfg
        importlib.reload(cfg)
        import auto_patch.pavement_scoring as PS
        importlib.reload(PS)
        shapes = [BuiltShape(polygon=road_poly, role="service_junction")]
        shapes += list(neighbours)
        layout = types.SimpleNamespace(shapes=shapes)
        layout._pavement_score_abut_unions = None
        return PS, layout, shapes[0]

    def test_long_shared_flank_fires(self, monkeypatch):
        road = _rect(0, 0, 8, 120)
        spine = BuiltShape(polygon=_rect(8, 0, 16, 120),
                           role="service_road")
        PS, layout, shape = self._score(monkeypatch, True, road, [spine])
        x = PS.shape_features(road, layout, owner=shape)
        assert x["service_adj"] == 1.0

    def test_a_mouth_alone_does_not_fire(self, monkeypatch):
        """An END connection shares only the road's own width — under the
        20 m bar and under 20 % of a long road's perimeter."""
        road = _rect(0, 0, 8, 120)
        ahead = BuiltShape(polygon=_rect(0, 120, 8, 240),
                           role="service_road")
        PS, layout, shape = self._score(monkeypatch, True, road, [ahead])
        x = PS.shape_features(road, layout, owner=shape)
        assert x["service_adj"] == 0.0

    def test_a_wide_lot_never_qualifies(self, monkeypatch):
        """The feature is scoped to ROAD-WIDTH shapes (the same
        ``road_corridor`` predicate that gates SERVICE at all)."""
        lot = _rect(0, 0, 120, 120)
        spine = BuiltShape(polygon=_rect(120, 0, 128, 120),
                           role="service_road")
        PS, layout, shape = self._score(monkeypatch, True, lot, [spine])
        x = PS.shape_features(lot, layout, owner=shape)
        assert x["service_adj"] == 0.0

    def test_gate_off_is_inert(self, monkeypatch):
        road = _rect(0, 0, 8, 120)
        spine = BuiltShape(polygon=_rect(8, 0, 16, 120),
                           role="service_road")
        PS, layout, shape = self._score(monkeypatch, False, road, [spine])
        x = PS.shape_features(road, layout, owner=shape)
        assert x["service_adj"] == 0.0

    def test_the_weight_votes_service(self):
        from auto_patch.config import PAVEMENT_SCORE_WEIGHTS
        w = PAVEMENT_SCORE_WEIGHTS["service_adj"]
        assert set(w) == {"SERVICE"}
        # It must be able to answer the GROUNDSIDE case that demoted the
        # HECA class: road_cover 2.0 + runway_disconnected 2.0 = 4.0 vs
        # SERVICE's road_cover 0.5 + road_narrow 2.5 = 3.0.
        assert w["SERVICE"] >= 1.0


# ═════════════════════════════════════════════════════════════════════
# §3 — the needle-collapse SOURCE discriminator
# ═════════════════════════════════════════════════════════════════════

def _spike_ring():
    """The recorded artifact class (KBNA junctions 289/290): a wide-edged
    spike whose apex triangle is 80 m² — under the area cap, so area alone
    collapses it."""
    return [
        (0.0, 0.0), (100.0, 0.0), (100.0, 40.0),
        (52.0, 40.0), (50.0, 80.0), (48.0, 40.0), (0.0, 40.0),
    ]


class TestNeedleSourceGuard:
    def test_artifact_spike_off_source_still_collapses(self):
        """The KBNA apex-artifact class: the spike encloses ground the
        SOURCE never paved, so the discriminator lets it go."""
        source = _rect(0.0, 0.0, 100.0, 40.0)      # the real pavement only
        _out, _na, dropped = _collapse_ring_needles(
            _spike_ring(), None, source_union=source)
        assert dropped == 1

    def test_real_pavement_tip_on_source_is_kept(self):
        """The HECA H1 class: the same angle, the same edges, the same
        sub-cap area — but the triangle IS source pavement, so dropping it
        would carve a hole.  Area cannot tell these two apart (85 m² vs
        90.8 m²); coverage can."""
        source = Polygon(_spike_ring())            # the tongue is real
        _out, _na, dropped = _collapse_ring_needles(
            _spike_ring(), None, source_union=source)
        assert dropped == 0
        assert _collapse_ring_needles.last_kept_on_source == 1

    def test_without_the_guard_both_collapse(self):
        """Gate off ⇒ area is the only test, exactly as before — which is
        why the guard exists."""
        for src in (None,):
            _out, _na, dropped = _collapse_ring_needles(
                _spike_ring(), None, source_union=src)
            assert dropped == 1

    def test_a_broken_measurement_keeps_the_apex(self):
        """A geometry failure answers "covers source" — the conservative
        side, where no coverage can be lost to a broken probe."""
        from auto_patch.pipeline import _apex_covers_source

        class _Boom:
            def intersection(self, other):
                raise ValueError("boom")

        assert _apex_covers_source((0, 0), (1, 1), (2, 0), 1.0, _Boom())


# ═════════════════════════════════════════════════════════════════════
# §4 — the drainage second-parent lockstep
# ═════════════════════════════════════════════════════════════════════

class TestDrainageParentSelection:
    def test_nearest_two_distinct_parents(self):
        picked = drainage_spine_parents([
            (30.0, "c", "C"), (10.0, "a", "A"), (20.0, "b", "B")])
        assert [p[1] for p in picked] == ["a", "b"]

    def test_one_entry_per_parent_keeps_its_nearest(self):
        """A reader that offers per-EDGE candidates must not fill both
        slots with the same parent."""
        picked = drainage_spine_parents([
            (10.0, "a", "A1"), (12.0, "a", "A2"), (20.0, "b", "B")])
        assert [p[1] for p in picked] == ["a", "b"]
        assert picked[0][2] == "A1"

    def test_tie_order_is_the_readers_stable_key(self):
        """Tie order is load-bearing — the NEARER parent owns the
        empty-intersection fallback downstream."""
        picked = drainage_spine_parents([
            (10.0, "b", "B"), (10.0, "a", "A")])
        assert [p[1] for p in picked] == ["a", "b"]

    def test_the_role_set_is_shared_with_the_emitter(self):
        """Same law, same population: the emitter's airside pavement set
        and the validator's parent set are ONE definition."""
        from auto_patch.clearance import _AIRSIDE_PAVEMENT_ROLES
        assert set(_AIRSIDE_PAVEMENT_ROLES) == set(DRAINAGE_SPINE_PARENT_ROLES)

    def test_validator_search_is_sound(self):
        """The measured HECA defect: a parent whose nearest edge lies just
        outside the first cell ring is NEARER than one inside it.  The
        search must find it."""
        import sys
        from pathlib import Path
        tools = str(Path(__file__).resolve().parent.parent / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import check_grade as CG

        # station at the origin; parent "near" sits 67 m away (outside the
        # 40 m seed ring), parents "far1"/"far2" sit ~92 m away.
        rings = [
            ("near", [(60.0, -5.0, 99.0), (80.0, -5.0, 99.0),
                      (80.0, 5.0, 99.0), (60.0, 5.0, 99.0)]),
            ("far1", [(-120.0, -5.0, 95.0), (-95.0, -5.0, 95.0),
                      (-95.0, 5.0, 95.0), (-120.0, 5.0, 95.0)]),
            ("far2", [(-5.0, 90.0, 96.0), (5.0, 90.0, 96.0),
                      (5.0, 120.0, 96.0), (-5.0, 120.0, 96.0)]),
        ]
        grid = {}
        c = CG._SPINE_PARENT_CELL_M
        for si, (_wid, ring) in enumerate(rings):
            for ei in range(len(ring)):
                a, b = ring[ei], ring[(ei + 1) % len(ring)]
                x0, x1 = sorted((a[0], b[0]))
                y0, y1 = sorted((a[1], b[1]))
                for gx in range(int(x0 // c), int(x1 // c) + 1):
                    for gy in range(int(y0 // c), int(y1 // c) + 1):
                        grid.setdefault((gx, gy), []).append((si, ei))
        picked = CG._nearest_edge_alt_by_way(0.0, 0.0, rings, grid)
        assert [p[1] for p in picked[:2]] == ["near", "far2"]
        assert math.isclose(picked[0][0], 60.0, abs_tol=0.01)
