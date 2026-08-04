"""Kill-prep round — the three fixes that unblock quarantine deletion.

Spec: ``docs/specs/kill-prep-round-spec.md`` (+ the owner amendment of
2026-08-03 on §1: portion-only absorption, mandatory mouth cuts, the SPINE
remains, cap constants are owner-only).  Owner rulings: ``docs/RULINGS.md``
(lateral-contiguity absorption is class-universal; feasibility is
guaranteed; quarantine is unauthorized; law compliance, not
instrument-zero).

Each gate is tested on BOTH sides — the behaviour it introduces and the
inertness of its off state — because every one of them is default-OFF and
ships that way this round.
"""
from __future__ import annotations

import importlib
import math
import types

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.layout import BuiltShape


# ═════════════════════════════════════════════════════════════════════
# helpers
# ═════════════════════════════════════════════════════════════════════

def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _layout(shapes):
    return types.SimpleNamespace(shapes=list(shapes))


def _dem_lot(x0, y0, x1, y1, z=10.0):
    """A DEM-followed groundside lot: per-vertex altitudes in the CLOSED
    convention (``_dem_follow_polygon``), which is what makes it illegal as
    an absorb host until the class-universal gate is on."""
    poly = _rect(x0, y0, x1, y1)
    n = len(poly.exterior.coords)
    return BuiltShape(polygon=poly, role="groundside_pavement",
                      node_altitudes=[z] * n)


@pytest.fixture()
def lateral_on(monkeypatch):
    """The landed lateral-contiguity law's gate ON, this round's gate OFF."""
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    monkeypatch.delenv("O4_SERVICE_LOT_ABSORPTION", raising=False)
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


@pytest.fixture()
def absorption_on(monkeypatch):
    """Both gates ON — the class-universal absorption arm."""
    monkeypatch.setenv("O4_LATERAL_CONTIGUITY_LAW", "1")
    monkeypatch.setenv("O4_SERVICE_LOT_ABSORPTION", "1")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    import auto_patch.groundside as gs
    yield gs
    importlib.reload(cfg)


# ═════════════════════════════════════════════════════════════════════
# §1 — service↔lot absorption (the emitter half)
# ═════════════════════════════════════════════════════════════════════

class TestClassUniversalAbsorption:
    """Owner 2026-08-03: "another class" in the lateral-contiguity law means
    ANY paved class — groundside lots included, not only aprons."""

    def test_a_dem_followed_lot_is_now_a_legal_host(self, absorption_on):
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        summary = absorption_on.apply_lateral_contiguity_law(
            _layout([lot, road]), "TEST")
        assert summary["absorbed"] == 1
        assert summary["absorbed_dem_host"] == 1
        assert summary["merge_failed"] == 0
        # the road is gone as a surface; the lot IS the merged surface
        assert lot.polygon.area == pytest.approx(100 * 70, rel=1e-6)

    def test_the_hosts_altitudes_stay_aligned_with_its_ring(self,
                                                           absorption_on):
        """The 1:1 ``node_altitudes`` alignment is exactly what made these
        hosts illegal before; the merge must MAINTAIN it, not assume it."""
        lot = _dem_lot(0, 0, 100, 60, z=12.5)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        absorption_on.apply_lateral_contiguity_law(_layout([lot, road]),
                                                   "TEST")
        ring = list(lot.polygon.exterior.coords)
        assert lot.node_altitudes is not None
        assert len(lot.node_altitudes) == len(ring)        # CLOSED convention
        assert lot.node_altitudes[0] == lot.node_altitudes[-1]
        assert all(a is not None and math.isfinite(a)
                   for a in lot.node_altitudes)

    def test_gate_off_keeps_the_lot_out_of_the_class_set(self, lateral_on):
        """The landed behaviour (classification round): the road carries the
        lot's 4 % instead of merging.  Unchanged when this gate is off."""
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([lot, road])
        summary = lateral_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 0
        assert summary["capped"] == 1
        assert summary["absorbed_dem_host"] == 0
        roads = [s for s in layout.shapes if s.role == "service_road"]
        assert roads[0].lateral_cap == pytest.approx(0.04)

    def test_the_strictest_cap_still_decides_the_host(self, absorption_on):
        """A road between an apron (1 %) and a lot (4 %) takes the STRICTEST
        cap of its cross-section and can only be absorbed by the surface
        that owns it — the apron, never the lot."""
        apron = BuiltShape(polygon=_rect(0, 0, 100, 60), role="apron")
        lot = _dem_lot(0, 70, 100, 130)
        road = BuiltShape(polygon=_rect(0, 60, 100, 70), role="service_road")
        layout = _layout([apron, lot, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["absorbed"] == 1
        assert list(summary["absorbed_caps"]) == [0.01]
        assert apron.polygon.area == pytest.approx(100 * 70, rel=1e-6)
        assert lot.polygon.area == pytest.approx(100 * 60, rel=1e-6)


class TestPortionOnlyAbsorption:
    """Owner amendment 2026-08-03: only the portion sharing a LATERAL edge
    absorbs; the portion with no pavement beside it stays a service road,
    and the mouth cut between them is mandatory."""

    def test_only_the_contiguous_portion_is_absorbed(self, absorption_on):
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 200, 70), role="service_road")
        layout = _layout([lot, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["cut"] == 1                 # the mouth cut FIRED
        assert summary["absorbed"] == 1
        assert summary["cut_failed"] == 0
        left = [s for s in layout.shapes if s.role == "service_road"]
        assert left, "the FREE stretch must survive as a road"
        assert all(s.lateral_cap is None for s in left)
        # the surviving road is the free (east) half, and the lot grew by
        # roughly the contiguous (west) half only
        assert min(s.polygon.bounds[0] for s in left) > 60.0
        # the lot grew by the contiguous (west) half only — the cut lands at
        # the first FREE station's centre, so it may overshoot the contact
        # end by at most one station step (5 m), never by the free length
        assert 100 * 60 < lot.polygon.area
        assert lot.polygon.bounds[2] <= 100.0 + 5.0 + 1e-6

    def test_a_piece_the_cut_could_not_separate_is_never_absorbed(
            self, absorption_on, monkeypatch):
        """The uncut-road defect the owner named: when the mouth cut fails,
        one piece still holds BOTH the contiguous and the free stations.
        Absorbing it would absorb the free road end to end — so it is kept,
        carrying the cap, and the failure is COUNTED."""
        import auto_patch.pavement.apron_necks as necks
        monkeypatch.setattr(necks, "_cut_at_mouth",
                            lambda *a, **k: None)
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 200, 70), role="service_road")
        layout = _layout([lot, road])
        summary = absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert summary["cut_failed"] == 1
        assert summary["absorbed"] == 0
        assert lot.polygon.area == pytest.approx(100 * 60, rel=1e-6)
        roads = [s for s in layout.shapes if s.role == "service_road"]
        assert len(roads) == 1
        assert roads[0].lateral_cap == pytest.approx(0.04)
        assert roads[0].polygon.area == pytest.approx(200 * 10, rel=1e-6)

    def test_the_split_reports_whether_a_piece_is_uniform(self):
        """``_lateral_split``'s third field is the law's own evidence that
        the cut separated the classes."""
        import auto_patch.groundside as gs
        poly = _rect(0, 0, 100, 10)
        stations = [(10, 5), (30, 5), (50, 5), (70, 5), (90, 5)]
        caps = [0.04, 0.04, 0.05, 0.05, 0.05]
        runs = [(0, 1, 0.04), (2, 4, 0.05)]
        out = gs._lateral_split(poly, stations, caps, runs, 0.0, 1.0,
                                lambda *a, **k: None)      # cut always fails
        assert len(out) == 1
        _piece, cap, uniform = out[0]
        assert cap == pytest.approx(0.04)
        assert uniform is False


class TestAbsorptionLeavesTheSpineAlone:
    """Owner amendment 2026-08-03: absorption removes a SURFACE, never the
    service spine — routing, reach and band semantics are unchanged."""

    def test_the_centerlines_are_untouched(self, absorption_on):
        from shapely.geometry import LineString
        spine = types.SimpleNamespace(
            line=LineString([(0, 65), (200, 65)]), is_service=True)
        lot = _dem_lot(0, 0, 100, 60)
        road = BuiltShape(polygon=_rect(0, 60, 200, 70), role="service_road")
        layout = _layout([lot, road])
        layout.apt_taxi_centerlines = [spine]
        before = list(spine.line.coords)
        absorption_on.apply_lateral_contiguity_law(layout, "TEST")
        assert layout.apt_taxi_centerlines == [spine]
        assert list(spine.line.coords) == before


# ═════════════════════════════════════════════════════════════════════
# §1 — the service DEM-follow envelope (the second-authority half)
# ═════════════════════════════════════════════════════════════════════

class _FakeLayout:
    """The minimum ``apply_service_road_dem_follow`` reads: shapes, the
    canonical-point registry, and (absent) service centerlines so the
    spine-first path yields to the per-vertex operator."""

    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry(tol_m=0.05)
        self.apt_taxi_centerlines = []


def _svc_fixture(anchor_west=0.0, anchor_east=4.5, lateral_cap=None):
    """A straight 100 m service road welded to an apron at each end, with
    ring vertices every 25 m (so there ARE interior nodes to grade)."""
    xs = [0.0, 25.0, 50.0, 75.0, 100.0]
    ring = ([(x, 0.0) for x in xs] + [(x, 10.0) for x in reversed(xs)])
    road = BuiltShape(polygon=Polygon(ring), role="service_road")
    road.lateral_cap = lateral_cap
    west = BuiltShape(polygon=_rect(-20.0, 0.0, 0.0, 10.0), role="apron")
    east = BuiltShape(polygon=_rect(100.0, 0.0, 120.0, 10.0), role="apron")
    layout = _FakeLayout([road, west, east])

    bucket_to_idx, nodes = {}, []
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = layout.canonical_points.get_or_add(float(x), float(y))
            if key not in bucket_to_idx:
                bucket_to_idx[key] = len(nodes)
                nodes.append(key)
    elev = [0.0] * len(nodes)
    for (x, y), v in (((0.0, 0.0), anchor_west), ((0.0, 10.0), anchor_west),
                      ((100.0, 0.0), anchor_east),
                      ((100.0, 10.0), anchor_east)):
        elev[bucket_to_idx[layout.canonical_points.get_or_add(x, y)]] = v
    dem = [100.0] * len(nodes)          # DEM far above: the ceiling binds
    mid = bucket_to_idx[layout.canonical_points.get_or_add(50.0, 0.0)]
    return layout, bucket_to_idx, elev, dem, mid


def _run_svc(monkeypatch, gate, **kw):
    monkeypatch.setenv("O4_SERVICE_LOT_ABSORPTION", "1" if gate else "0")
    import auto_patch.config as cfg
    importlib.reload(cfg)
    from auto_patch.elevation_per_surface.route_profile import anchors
    layout, b2i, elev, dem, mid = _svc_fixture(**kw)
    anchors.apply_service_road_dem_follow(layout, b2i, elev, dem, 0.05)
    broken = set(getattr(layout, "_service_break_idx", None) or ())
    importlib.reload(cfg)
    return elev[mid], broken, mid


class TestServiceEnvelopeConsumesTheOneLaw:
    """Spec §1: the private cap-Lipschitz envelope stops being a SECOND
    grading authority — it prices its legs with the lateral-contiguity
    law's cap, and it no longer quarantines nodes that law owns."""

    def test_gate_off_uses_the_service_cap(self, monkeypatch):
        z, broken, _ = _run_svc(monkeypatch, False, lateral_cap=0.04)
        # 5 % from the west weld over 50 m, DEM-clamped to the ceiling
        assert z == pytest.approx(2.5, abs=1e-6)
        assert broken == set()

    def test_a_free_road_still_grades_at_the_service_cap(self, monkeypatch):
        z, broken, _ = _run_svc(monkeypatch, True, lateral_cap=None)
        assert z == pytest.approx(2.5, abs=1e-6)
        assert broken == set()

    def test_the_lateral_cap_prices_the_envelope(self, monkeypatch):
        """4 % (the lot's) instead of 5 % (the road's private number): the
        band tightens to an empty interval here, so the node takes the
        designed blend — the point being that the NUMBER came from the one
        law, not from this pass."""
        z, _broken, _ = _run_svc(monkeypatch, True, lateral_cap=0.04)
        assert z == pytest.approx(2.25, abs=1e-6)

    def test_a_laterally_bound_contradiction_is_not_quarantined(
            self, monkeypatch):
        z_on, broken_on, mid = _run_svc(monkeypatch, True, anchor_east=6.0,
                                        lateral_cap=0.04)
        z_off, broken_off, _ = _run_svc(monkeypatch, False, anchor_east=6.0,
                                        lateral_cap=0.04)
        # gate OFF: the envelope declares its own break pocket
        assert mid in broken_off
        # gate ON: the contiguous surface's law owns the node; the blend is
        # still applied (the surface does not change shape) but nothing is
        # quarantined — a residual is a VISIBLE violation
        assert broken_on == set()
        assert math.isfinite(z_on) and math.isfinite(z_off)


# ═════════════════════════════════════════════════════════════════════
# §2 — the triangle-plane demotion
# ═════════════════════════════════════════════════════════════════════

class TestTrianglePlaneDemotion:
    def _disposition(self, monkeypatch, gate, tri_broken):
        monkeypatch.setenv("O4_TRIANGLE_PLANE_REPORTS", "1" if gate else "0")
        import auto_patch.config as cfg
        importlib.reload(cfg)
        from auto_patch.elevation_per_surface.route_profile import solve
        layout = types.SimpleNamespace()
        out = solve.triangle_plane_disposition(layout, tri_broken, 3)
        importlib.reload(cfg)
        return out, layout

    def test_gate_off_quarantines_as_before(self, monkeypatch):
        out, layout = self._disposition(monkeypatch, False, {4, 7, 9})
        assert out == {4, 7, 9}
        assert not hasattr(layout, "_triangle_plane_unresolved")

    def test_gate_on_reports_and_never_mints_break_membership(self,
                                                             monkeypatch):
        out, layout = self._disposition(monkeypatch, True, {4, 7, 9})
        assert out == set()
        assert layout._triangle_plane_unresolved == 3

    def test_the_report_accumulates_over_the_passes(self, monkeypatch):
        monkeypatch.setenv("O4_TRIANGLE_PLANE_REPORTS", "1")
        import auto_patch.config as cfg
        importlib.reload(cfg)
        from auto_patch.elevation_per_surface.route_profile import solve
        layout = types.SimpleNamespace()
        solve.triangle_plane_disposition(layout, {1, 2})
        solve.triangle_plane_disposition(layout, {5})
        assert layout._triangle_plane_unresolved == 3
        importlib.reload(cfg)

    def test_an_empty_unresolved_set_reports_nothing(self, monkeypatch):
        out, layout = self._disposition(monkeypatch, True, set())
        assert out == set()
        assert layout._triangle_plane_unresolved == 0

    def test_the_count_reaches_the_sidecar(self):
        """The report is a COUNT in the patch's axes sidecar, not a
        quarantine — the owner reads it to size the follow-up."""
        from auto_patch import layout as L
        import inspect
        src = inspect.getsource(L.PavementLayout._write_axes_sidecar)
        assert '"triangle_plane_unresolved"' in src
        assert "_triangle_plane_unresolved" in src


# ═════════════════════════════════════════════════════════════════════
# §3 — the raster seed-cell fix
# ═════════════════════════════════════════════════════════════════════

class TestSeedCellExactness:
    """One 3 m cell can hold two attachments metres apart; collapsing them
    prices the route leg between them at ZERO and manufactures a band
    inversion (HEAZ: four of four observed inversions reproduced)."""

    CXS = np.array([1.5, 4.5, 7.5])
    CYS = np.array([1.5, 4.5, 7.5])
    CAP = np.full((3, 3), 0.015)

    def _resolve(self, members):
        from auto_patch.elevation_per_surface import raster_reach_band as R
        return R.resolve_seed_cell(members, self.CXS, self.CYS, self.CAP)

    def test_one_attachment_is_exact(self):
        c, f, collapsed = self._resolve([(4.0, 4.0, 83.02, 82.90, 1, 1)])
        assert (c, f) == (83.02, 82.90)
        assert collapsed is False

    def test_a_collapse_is_priced_at_the_local_cap(self):
        """The HEAZ cell: ceiling 83.0247 from one node, floor 83.7379 from
        another 3.97 m away — 0.71 m of "inversion" that is really 3.97 m
        of route leg the cell priced at zero."""
        members = [(3.2, 4.0, 83.3527, 83.2000, 1, 1),
                   (5.6, 7.2, 83.5000, 83.4096, 1, 1)]
        d = math.hypot(5.6 - 3.2, 7.2 - 4.0)
        c, f, collapsed = self._resolve(members)
        assert collapsed is True
        # the interval is NOT inverted any more, and the relaxation is
        # exactly the cap × the intra-cell distance
        assert f <= c + 1e-12
        assert c == pytest.approx(min(83.3527, 83.5000 + 0.015 * d))
        assert f == pytest.approx(max(83.2000, 83.4096 - 0.015 * d))

    def test_a_genuine_inconsistency_survives(self):
        """Two anchors 0.64 m apart whose OWN values differ by 0.010 m
        (1.56 % > the 1.5 % cap): the priced relaxation covers 0.0096 m and
        the honest 0.0004 m residual stays visible.  The fix removes the
        artifact, it does not paper over the field."""
        members = [(4.0, 4.0, 69.710, 69.710, 1, 1),
                   (4.0, 4.64, 69.720, 69.720, 1, 1)]
        c, f, _ = self._resolve(members)
        assert f - c == pytest.approx(0.010 - 0.015 * 0.64, abs=1e-9)
        assert 0.0 < f - c < 0.01              # below the materiality floor

    def test_the_author_is_the_node_nearest_the_cell_centre(self):
        near = (4.6, 4.6, 90.0, 89.0, 1, 1)
        far = (3.05, 3.05, 95.0, 94.0, 1, 1)
        c1, f1, _ = self._resolve([near, far])
        c2, f2, _ = self._resolve([far, near])
        assert (c1, f1) == (c2, f2)            # order-independent
        # the author's own value is unrelaxed on at least one side
        assert c1 == pytest.approx(90.0)

    def test_the_gate_defaults_off(self):
        import auto_patch.config as cfg
        importlib.reload(cfg)
        assert cfg.BAND_SEED_EXACT is False
        assert cfg.SERVICE_LOT_ABSORPTION is False
        assert cfg.TRIANGLE_PLANE_REPORTS is False
