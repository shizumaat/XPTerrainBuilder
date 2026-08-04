"""Owner constants (lot 5 %, service road 8 %) + the merged-surface law.

Rulings: ``docs/RULINGS.md`` — "Owner constants: lot 5%, service road 8%"
(2026-08-03, approved on the primary-source research) and the
merged-surface ruling of the same day: *the merged lot+road polygon is
ONE surface and gets graded as one*.

The constants are LAW, so their test twin asserts the cited numbers
directly (a test that read the constant back would assert nothing).  The
merged-surface law is GENERATION-BINDING, so its twin asserts the
property of the produced surface, not the presence of a call.
"""
from __future__ import annotations

import importlib
import math
import types

import pytest
from shapely.geometry import Polygon

from auto_patch.layout import BuiltShape


# ═════════════════════════════════════════════════════════════════════
# helpers
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    return types.SimpleNamespace(shapes=list(shapes))


def _dem_lot(x0, y0, x1, y1, z=10.0):
    poly = _rect(x0, y0, x1, y1)
    n = len(poly.exterior.coords)
    return BuiltShape(polygon=poly, role="groundside_pavement",
                      node_altitudes=[z] * n)


def _ramp_dem(slope=0.5, z0=10.0):
    """A DEM far steeper than any landside cap, so the ramp limit is the
    only thing that can make the emitted ring lawful."""
    return lambda x, y: z0 + slope * float(x)


def _worst_adjacent(shape):
    ring = list(shape.polygon.exterior.coords)
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    alts = list(shape.node_altitudes or [])
    if len(alts) == len(ring) + 1:
        alts = alts[:-1]
    assert len(alts) == len(ring), (len(alts), len(ring))
    worst = 0.0
    n = len(ring)
    for k in range(n):
        (x0, y0), (x1, y1) = ring[k], ring[(k + 1) % n]
        d = math.hypot(x1 - x0, y1 - y0)
        if d > 1e-6:
            worst = max(worst, abs(alts[(k + 1) % n] - alts[k]) / d)
    return worst


@pytest.fixture()
def absorption_on(monkeypatch):
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    monkeypatch.setenv("O4_SERVICE_LOT_ABSORPTION", "1")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


@pytest.fixture()
def absorption_off(monkeypatch):
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    monkeypatch.delenv("O4_SERVICE_LOT_ABSORPTION", raising=False)
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


# ═════════════════════════════════════════════════════════════════════
# the constants themselves
# ═════════════════════════════════════════════════════════════════════

class TestOwnerConstants:
    """The two numbers the owner approved on 2026-08-03, with their
    citations recorded in ``docs/STANDARDS.md`` rows 25/27."""

    def test_the_lot_cap_is_the_walking_surface_ceiling(self):
        # ADA 2010 §403.3 running slope 1:20; Iowa SUDAS §8B-1; City of
        # Santa Barbara Parking Design Standards §D.5.
        from auto_patch import config as cfg
        assert cfg.GROUNDSIDE_MAX_GRADE == pytest.approx(0.050)
        assert cfg.ROLE_GRADE_LIMITS["groundside_pavement"] == \
            pytest.approx(0.050)

    def test_the_service_road_cap_is_the_vdot_level_terrain_standard(self):
        # VDOT Road Design Manual App. A1, GS-9: level terrain 8 % at
        # 10-20 mph.
        from auto_patch import config as cfg
        assert cfg.SERVICE_ROAD_MAX_GRADE == pytest.approx(0.080)
        assert cfg.ROLE_GRADE_LIMITS["service_road"] == pytest.approx(0.080)

    def test_service_junction_rides_the_service_road_constant(self):
        """The COUPLING the round flags for the owner: junctions are not a
        separate number.  If they are ever split, this test is the one that
        must be changed deliberately."""
        from auto_patch import config as cfg
        assert (cfg.ROLE_GRADE_LIMITS["service_junction"]
                is cfg.ROLE_GRADE_LIMITS["service_road"])

    def test_the_landside_caps_stay_distinct_from_the_tunnel_ramp(self):
        """Several dispatch sites resolve a cap by VALUE equality; the lot
        cap used to collide with the tunnel ramp's 4 %.  It must not
        collide with anything now."""
        from auto_patch import config as cfg
        vals = [cfg.GROUNDSIDE_MAX_GRADE, cfg.SERVICE_ROAD_MAX_GRADE,
                cfg.TUNNEL_RAMP_MAX_GRADE, cfg.TAXI_MAX_GRADE,
                cfg.APRON_MAX_GRADE, cfg.TAXI_MAX_GRADE_NARROW]
        assert len(set(round(v, 6) for v in vals)) == len(vals)


# ═════════════════════════════════════════════════════════════════════
# the merged surface is ONE surface
# ═════════════════════════════════════════════════════════════════════

class TestMergedSurfaceIsOneSurface:
    """Ruling 2026-08-03: after a road stretch is absorbed, the lot
    emitter's ramp-limited DEM follow is re-run over the MERGED ring.
    Moving the host's pre-existing vertices is lawful."""

    def _merge(self, gs, dem_at, z=10.0):
        lot = _dem_lot(0, 0, 100, 60, z=z)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        before = list(lot.node_altitudes)
        summary = gs.apply_lateral_contiguity_law(
            _layout([lot, road]), "TEST", dem_at=dem_at)
        return lot, before, summary

    def test_the_merged_ring_obeys_the_lot_cap(self, absorption_on):
        from auto_patch import config as cfg
        lot, _before, summary = self._merge(absorption_on, _ramp_dem())
        assert summary["absorbed_dem_host"] == 1
        assert summary["host_regraded"] == 1
        worst = _worst_adjacent(lot)
        # the ring limiter's own bound plus the 0.01 m emit rounding over
        # the shortest ring edge
        assert worst <= cfg.GROUNDSIDE_MAX_GRADE + 1e-3, worst

    def test_the_hosts_own_vertices_move(self, absorption_on):
        """The half attempt 1 refused to do — and the reason it measured
        worse.  A regrade that only touched the new vertices would leave
        the host's field untouched and the seam step intact."""
        lot, before, summary = self._merge(absorption_on, _ramp_dem())
        assert summary["host_regraded"] == 1
        # the pre-merge lot was FLAT at 10.0; over a 0.5 slope DEM the
        # re-followed ring cannot still be flat at 10.0
        assert any(abs(a - before[0]) > 0.01 for a in lot.node_altitudes)

    def test_altitudes_stay_aligned_and_closed(self, absorption_on):
        lot, _before, _s = self._merge(absorption_on, _ramp_dem())
        ring = list(lot.polygon.exterior.coords)
        assert len(lot.node_altitudes) == len(ring)
        assert lot.node_altitudes[0] == lot.node_altitudes[-1]
        assert all(a is not None and math.isfinite(a)
                   for a in lot.node_altitudes)

    def test_without_a_dem_sampler_the_merge_is_unchanged(self,
                                                          absorption_on):
        """Every legacy / synthetic caller passes no sampler; those must
        keep exactly the pre-ruling behaviour."""
        lot, before, summary = self._merge(absorption_on, None)
        assert summary["absorbed_dem_host"] == 1
        assert summary["host_regraded"] == 0
        assert all(a == pytest.approx(before[0]) for a in lot.node_altitudes)

    def test_gate_off_never_regrades(self, absorption_off):
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([lot, road])
        summary = absorption_off.apply_lateral_contiguity_law(
            layout, "TEST", dem_at=_ramp_dem())
        assert summary["absorbed"] == 0
        assert summary["host_regraded"] == 0
        assert all(a == pytest.approx(10.0) for a in lot.node_altitudes)

    def test_a_steeper_dem_still_lands_under_the_cap(self, absorption_on):
        """The ramp limit is what makes the surface lawful, not the DEM —
        so a 200 % DEM must produce the same verdict as a 50 % one."""
        from auto_patch import config as cfg
        lot, _b, summary = self._merge(absorption_on, _ramp_dem(slope=2.0))
        assert summary["host_regraded"] == 1
        assert _worst_adjacent(lot) <= cfg.GROUNDSIDE_MAX_GRADE + 1e-3


class TestRegradeHelperIsSafe:
    """``_regrade_merged_host`` is called on real, sometimes broken,
    geometry — it must degrade to a no-op rather than corrupt a host."""

    def test_a_degenerate_ring_is_a_no_op(self):
        import auto_patch.groundside as gs
        shape = BuiltShape(polygon=None, role="groundside_pavement",
                           node_altitudes=[1.0, 1.0])
        assert gs._regrade_merged_host(shape, _ramp_dem()) is None
        assert shape.node_altitudes == [1.0, 1.0]

    def test_a_dem_with_no_valid_sample_is_a_no_op(self):
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 10, 10, z=7.0)
        before = list(lot.node_altitudes)
        assert gs._regrade_merged_host(lot, lambda x, y: None) is None
        assert lot.node_altitudes == before

    def test_a_partial_dem_fills_from_its_neighbours(self):
        """The walk-outward rule of ``_dem_follow_polygon``: a vertex off
        the tile takes its nearest valid neighbour, never a zero."""
        import auto_patch.groundside as gs
        lot = _dem_lot(0, 0, 10, 10, z=7.0)

        def _partial(x, y):
            return None if x > 5.0 else 40.0

        worst = gs._regrade_merged_host(lot, _partial)
        assert worst is not None
        assert all(a > 30.0 for a in lot.node_altitudes)
