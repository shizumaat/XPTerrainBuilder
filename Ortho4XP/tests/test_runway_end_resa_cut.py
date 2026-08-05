"""Runway-end RESA CUT (arc A2) — the skirt's twin in the other direction.

The runway-end skirt FILLS terrain that drops below the lawful floor; the
RESA cut TAKES DOWN terrain that rises above the lawful ceiling — a gentle
``RUNWAY_END_RESA_MAX_SLOPE`` ramp off the pavement-exit elevation (ICAO
Annex 14 §3.5.10), so an overrun meets a ramp instead of a wall.  Both are
emitted by ``clearance.emit_runway_end_skirts`` off the same apt.dat
row-100 anchor; the cut is gated by ``RUNWAY_END_RESA_ENABLED``.

Everything here is headless and deterministic: a synthetic one-runway
layout plus a stub DEM, so no X-Plane install, no network, no fixture
terrain.
"""
import math

import pytest
from shapely.geometry import Polygon

from auto_patch.config import (
    CLEARANCE_MAX_REACH_M,
    CLEARANCE_OBSTRUCTION_THRESHOLD_M,
    RUNWAY_END_RESA_MAX_SLOPE,
    runway_strip_half_width_m,
)
from auto_patch.grade_law import (
    runway_end_corridor_half_width_m,
    runway_end_envelope,
)
from auto_patch.layout import (
    REF_RUNWAY_END_RESA,
    REF_RUNWAY_END_SKIRT,
    ROLE_RUNWAY_CLEARANCE,
    RUNWAY_END_REGIME_REFS,
)


# ──────────────────────────────────────────────────────────────────────
# LOCKSTEP: the scalar slope the emitter hands _build_graded_strips IS
# the envelope's ceiling
# ──────────────────────────────────────────────────────────────────────
# ``emit_runway_end_skirts`` builds the cut by passing the SCALAR
# ``RUNWAY_END_RESA_MAX_SLOPE`` to ``_build_graded_strips`` (whose ceiling
# is ``ref + slope * d``) rather than calling ``runway_end_envelope`` once
# per station.  That shortcut is only licensed while the envelope's
# ceiling is exactly that linear ramp inside the reach and unbounded
# outside it — which is what these assertions pin down.  If the law ever
# gains a second ceiling regime, this test fails and the emitter must
# switch to a per-station law call.
class TestResaCeilingLockstep:
    _GOVERNED = 240.0
    _REACH = CLEARANCE_MAX_REACH_M["runway"]

    @pytest.mark.parametrize("d", [1e-6, 0.5, 1.0, 5.0, 17.3, 60.0, 90.0,
                                   150.0, 239.0, 240.0, 241.0, 299.0,
                                   299.999])
    def test_ceiling_is_the_linear_ramp_inside_the_reach(self, d):
        _floor, ceiling = runway_end_envelope(
            d, governed_length_beyond_pavement_m=self._GOVERNED)
        assert ceiling == pytest.approx(RUNWAY_END_RESA_MAX_SLOPE * d)

    @pytest.mark.parametrize("d", [300.0, 300.001, 400.0, 1000.0])
    def test_ceiling_is_unbounded_at_and_past_the_reach(self, d):
        _floor, ceiling = runway_end_envelope(
            d, governed_length_beyond_pavement_m=self._GOVERNED)
        assert ceiling is None

    def test_ceiling_ignores_the_governed_length(self):
        """The ceiling is bounded by the REACH, not by the (shorter)
        governed length that bounds the floor — so the emitter is right
        to pass ``resa_reach`` as the band cap and not ``governed``."""
        d = self._GOVERNED + 20.0
        floor, ceiling = runway_end_envelope(
            d, governed_length_beyond_pavement_m=self._GOVERNED)
        assert floor is None                      # past the fill footprint
        assert ceiling == pytest.approx(RUNWAY_END_RESA_MAX_SLOPE * d)

    def test_entry_grade_and_overrun_do_not_move_the_ceiling(self):
        """Those two arguments belong to the FLOOR law; the RESA ramp is
        anchored purely at the pavement-exit elevation, which is why the
        emitter can share one scalar slope across both ends."""
        for d in (10.0, 100.0, 250.0):
            base = runway_end_envelope(
                d, governed_length_beyond_pavement_m=self._GOVERNED)[1]
            for entry in (-0.05, 0.0, 0.05):
                for overrun in (0.0, 60.0):
                    assert runway_end_envelope(
                        d, governed_length_beyond_pavement_m=self._GOVERNED,
                        entry_grade=entry,
                        pavement_beyond_end_m=overrun)[1] == base

    def test_reach_default_is_the_config_runway_reach(self):
        assert runway_end_envelope(
            self._REACH - 1e-3,
            governed_length_beyond_pavement_m=self._GOVERNED)[1] is not None
        assert runway_end_envelope(
            self._REACH,
            governed_length_beyond_pavement_m=self._GOVERNED)[1] is None


# ──────────────────────────────────────────────────────────────────────
# The corridor half-width is single-sourced in grade_law
# ──────────────────────────────────────────────────────────────────────
class TestCorridorHalfWidth:
    @pytest.mark.parametrize("width,length", [
        (45.0, 3496.5), (30.0, 700.0), (23.0, 1500.0), (60.0, 900.0),
        (18.0, 1200.0), (45.0, 2500.0),
    ])
    def test_matches_the_inline_expression_it_replaced(self, width, length):
        assert runway_end_corridor_half_width_m(width, length) == max(
            width, runway_strip_half_width_m(length))

    def test_annex14_reference_values(self):
        assert runway_end_corridor_half_width_m(45.0, 3496.5) == 75.0
        assert runway_end_corridor_half_width_m(30.0, 700.0) == 30.0


# ──────────────────────────────────────────────────────────────────────
# The cut-only vertex rule
# ──────────────────────────────────────────────────────────────────────
class TestResaCutAlt:
    def test_is_the_mirror_of_the_skirt_lift(self):
        from auto_patch.clearance import _resa_cut_alt, _skirt_lift_alt
        for ceiling, dem in ((10.0, 12.0), (10.0, 8.0), (10.0, 10.0)):
            assert _resa_cut_alt(ceiling, dem) == min(ceiling, dem)
            assert _skirt_lift_alt(ceiling, dem) == max(ceiling, dem)

    def test_missing_dem_falls_back_to_the_analytic_ceiling(self):
        from auto_patch.clearance import _resa_cut_alt
        assert _resa_cut_alt(7.5, None) == 7.5


# ──────────────────────────────────────────────────────────────────────
# End-to-end emission on a synthetic layout + stub DEM
# ──────────────────────────────────────────────────────────────────────
_RUNWAY_LEN = 1500.0      # ICAO code 3
_RUNWAY_ALT = 100.0
_HALF_WIDTH = 22.5        # apt.dat width 45 m
_TRIGGER = CLEARANCE_OBSTRUCTION_THRESHOLD_M["runway"]


class ResaHarness:
    """One 45 m x 1500 m runway at 100 m, anchored at (0, 0), running
    east along +x.  The DEM is supplied per test as ``f(x, y) -> alt``."""

    def _make_layout(self):
        from auto_patch.layout import BuiltShape, PavementLayout
        rect = Polygon([
            (0.0, -_HALF_WIDTH), (_RUNWAY_LEN, -_HALF_WIDTH),
            (_RUNWAY_LEN, _HALF_WIDTH), (0.0, _HALF_WIDTH)])
        layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
        layout.shapes.append(BuiltShape(
            polygon=rect, role="runway", ref="09-27",
            altitude_high=_RUNWAY_ALT, altitude_low=_RUNWAY_ALT))
        return layout

    def _make_runway(self):
        from auto_patch.apt_dat_reader import Runway
        from auto_patch.layout import R_EARTH
        lon_b = math.degrees(_RUNWAY_LEN / R_EARTH)
        return Runway(
            desig_a="09", desig_b="27",
            lat_a=0.0, lon_a=0.0, lat_b=0.0, lon_b=lon_b,
            width_m=45.0, surface_code=1,
            displaced_a_m=0.0, displaced_b_m=0.0,
            markings_a=0, approach_lights_a=0,
            markings_b=0, approach_lights_b=0)

    def _emit(self, monkeypatch, dem_fn, *, resa_gate=True,
              skirt_gate=True, layout=None):
        from auto_patch import clearance
        from auto_patch.layout import R_EARTH

        def _fake_sample_dem(dem, tile_lat, tile_lon, lat, lon):
            x = math.radians(lon) * R_EARTH
            y = math.radians(lat) * R_EARTH
            return dem_fn(x, y)

        if layout is None:
            layout = self._make_layout()
        monkeypatch.setattr(clearance, "_sample_dem", _fake_sample_dem)
        monkeypatch.setattr(clearance, "RUNWAY_END_SKIRT_ENABLED",
                            skirt_gate)
        monkeypatch.setattr(clearance, "RUNWAY_END_RESA_ENABLED",
                            resa_gate)
        n = clearance.emit_runway_end_skirts(
            layout, dem=object(), tile_lat=0, tile_lon=0,
            source_runways=[self._make_runway()])
        return layout, n

    @staticmethod
    def _anchor_x():
        """The pavement-EXIT abscissa the emitter anchors the east end at.

        Computed through the emitter's own ``_pavement_exit_along`` (which
        resolves the exit to half a station), so the expected-altitude
        arithmetic below is anchored exactly where the emitter anchors it
        rather than at the nominal runway end.
        """
        from shapely.prepared import prep
        from auto_patch.clearance import (
            _pavement_exit_along, _RESA_PAVEMENT_PROBE_MAX_M,
            _RESA_SEED_INSET_M, CLEARANCE_STATION_STEP_M)
        rect = Polygon([
            (0.0, -_HALF_WIDTH), (_RUNWAY_LEN, -_HALF_WIDTH),
            (_RUNWAY_LEN, _HALF_WIDTH), (0.0, _HALF_WIDTH)])
        seed_x = _RUNWAY_LEN - _RESA_SEED_INSET_M
        return seed_x + _pavement_exit_along(
            prep(rect), seed_x, 0.0, 1.0, 0.0,
            _RESA_PAVEMENT_PROBE_MAX_M, CLEARANCE_STATION_STEP_M)

    @staticmethod
    def _resa(layout):
        return [s for s in layout.shapes
                if s.role == ROLE_RUNWAY_CLEARANCE
                and s.ref == REF_RUNWAY_END_RESA]

    @staticmethod
    def _skirts(layout):
        return [s for s in layout.shapes
                if s.role == ROLE_RUNWAY_CLEARANCE
                and s.ref == REF_RUNWAY_END_SKIRT]


# The east end meets a 50 % wall; everything else is dead flat at runway
# level, so the WEST end is the mirrored no-cut control inside the very
# same build.
def _east_wall_dem(x, y):
    if x <= _RUNWAY_LEN:
        return _RUNWAY_ALT
    return min(_RUNWAY_ALT + 0.5 * (x - _RUNWAY_LEN), _RUNWAY_ALT + 40.0)


def _flat_dem(x, y):
    return _RUNWAY_ALT


class TestResaEmission(ResaHarness):
    def test_gate_off_emits_no_cut(self, monkeypatch):
        layout, _n = self._emit(monkeypatch, _east_wall_dem,
                                resa_gate=False)
        assert self._resa(layout) == []

    def test_gate_off_leaves_the_fill_untouched(self, monkeypatch):
        """Byte-identity of the FILL path across the gate: the same
        terrain must yield the same skirt polygons and the same node
        altitudes with the cut on or off."""
        off, _ = self._emit(monkeypatch, _east_wall_dem, resa_gate=False)
        on, _ = self._emit(monkeypatch, _east_wall_dem, resa_gate=True)
        off_fill = [(list(s.polygon.exterior.coords), s.node_altitudes)
                    for s in self._skirts(off)]
        on_fill = [(list(s.polygon.exterior.coords), s.node_altitudes)
                   for s in self._skirts(on)]
        assert off_fill == on_fill

    def test_rising_terrain_beyond_an_end_is_cut(self, monkeypatch):
        layout, n = self._emit(monkeypatch, _east_wall_dem)
        cuts = self._resa(layout)
        assert cuts, "a 50 % wall past the end must breach the 5 % ramp"
        assert n >= len(cuts)
        # Every piece sits at or beyond the east pavement exit anchor —
        # never behind it, and never off the WEST end (flat there, the
        # mirrored control inside this very build).
        anchor = self._anchor_x()
        runway = layout.shapes[0].polygon
        for s in cuts:
            assert s.polygon.bounds[0] >= anchor - 1e-6
            # …and never ON the pavement it protects (the static clip).
            assert s.polygon.intersection(runway).area < 1e-6

    def test_flat_terrain_emits_nothing(self, monkeypatch):
        layout, _n = self._emit(monkeypatch, _flat_dem)
        assert self._resa(layout) == []

    def test_terrain_under_the_ramp_emits_nothing(self, monkeypatch):
        """A rise the ramp already clears (4 % < 5 %) is lawful and must
        not be cut — this is the law working, not a miss."""
        def _gentle(x, y):
            if x <= _RUNWAY_LEN:
                return _RUNWAY_ALT
            return _RUNWAY_ALT + 0.04 * (x - _RUNWAY_LEN)
        layout, _n = self._emit(monkeypatch, _gentle)
        assert self._resa(layout) == []

    def test_cut_never_rides_above_the_dem_and_never_fills(self,
                                                           monkeypatch):
        layout, _n = self._emit(monkeypatch, _east_wall_dem)
        cuts = self._resa(layout)
        assert cuts
        for s in cuts:
            ring = list(s.polygon.exterior.coords)
            for (vx, vy), alt in zip(ring, s.node_altitudes):
                dem = _east_wall_dem(vx, vy)
                # CUT-ONLY: at most the DEM (rounding to 0.1 m is the
                # emit quantum, so allow exactly that).
                assert alt <= dem + 0.05, (
                    f"vertex ({vx:.1f},{vy:.1f}) rides {alt - dem:.2f} m "
                    f"above the DEM — that is a FILL")

    def test_cut_vertices_equal_min_ceiling_dem(self, monkeypatch):
        layout, _n = self._emit(monkeypatch, _east_wall_dem)
        cuts = self._resa(layout)
        assert cuts
        reach = CLEARANCE_MAX_REACH_M["runway"]
        anchor = self._anchor_x()
        checked = 0
        for s in cuts:
            ring = list(s.polygon.exterior.coords)
            for (vx, vy), alt in zip(ring, s.node_altitudes):
                d = vx - anchor           # outward = +x at the east end
                if d <= 0.02:
                    continue              # weld row: pavement value
                ceiling = _RUNWAY_ALT + RUNWAY_END_RESA_MAX_SLOPE * max(
                    0.0, min(reach, d))
                expected = round(min(ceiling, _east_wall_dem(vx, vy)), 1)
                assert alt == pytest.approx(expected, abs=1e-6), (
                    f"vertex ({vx:.2f},{vy:.2f}) d={d:.2f}: "
                    f"{alt} != min(ceiling={ceiling:.3f}, "
                    f"DEM={_east_wall_dem(vx, vy):.3f})")
                checked += 1
        assert checked > 10

    def test_cut_daylights_where_the_ramp_meets_the_dem(self,
                                                        monkeypatch):
        """The far edge of the cut must stop at (or one station past) the
        DEM crossing, not run on to the reach cap: with a 50 % wall the
        ramp is overtaken immediately, so the cut is SHORT."""
        layout, _n = self._emit(monkeypatch, _east_wall_dem)
        cuts = self._resa(layout)
        assert cuts
        far = max(s.polygon.bounds[2] for s in cuts) - _RUNWAY_LEN
        # The wall reaches its 40 m plateau at d = 80 m; the ramp catches
        # it at d = 800 m, well past the 300 m reach, so the cut runs to
        # the reach cap here.  What must NOT happen is the cut exceeding
        # the reach.
        assert far <= CLEARANCE_MAX_REACH_M["runway"] + 1e-6

    def test_cut_daylights_on_a_finite_hump(self, monkeypatch):
        """A hump that falls back under the ramp daylights there: the cut
        stops at the crossing (plus the builder's one-station overshoot),
        far short of the 300 m reach."""
        def _hump(x, y):
            if x <= _RUNWAY_LEN:
                return _RUNWAY_ALT
            d = x - _RUNWAY_LEN
            if d <= 40.0:
                return _RUNWAY_ALT + 0.25 * d          # 25 % rise
            return max(_RUNWAY_ALT, _RUNWAY_ALT + 10.0 - 0.5 * (d - 40.0))
        layout, _n = self._emit(monkeypatch, _hump)
        cuts = self._resa(layout)
        assert cuts
        far = max(s.polygon.bounds[2] for s in cuts) - _RUNWAY_LEN
        assert far < 120.0, (
            f"cut ran {far:.0f} m past the end — it must daylight where "
            f"the DEM drops back under the ramp")

    def test_cut_stays_inside_the_annex14_corridor(self, monkeypatch):
        layout, _n = self._emit(monkeypatch, _east_wall_dem)
        cuts = self._resa(layout)
        assert cuts
        half = runway_end_corridor_half_width_m(45.0, _RUNWAY_LEN)
        for s in cuts:
            minx, miny, maxx, maxy = s.polygon.bounds
            assert miny >= -half - 1e-6 and maxy <= half + 1e-6

    def test_cut_does_not_overlap_the_fill(self, monkeypatch):
        """A brow that rises on one flank and drops on the other emits
        both regimes off the same end; their footprints may ABUT but must
        never overlap."""
        def _split(x, y):
            if x <= _RUNWAY_LEN:
                return _RUNWAY_ALT
            d = x - _RUNWAY_LEN
            if y >= 0.0:
                return min(_RUNWAY_ALT + 0.5 * d, _RUNWAY_ALT + 40.0)
            return max(_RUNWAY_ALT - 0.5 * d, _RUNWAY_ALT - 40.0)
        layout, _n = self._emit(monkeypatch, _split)
        cuts = self._resa(layout)
        fills = self._skirts(layout)
        assert cuts and fills
        for c in cuts:
            for f in fills:
                assert c.polygon.intersection(f.polygon).area < 1e-6

    def test_cut_and_fill_share_the_end_regime_refs(self, monkeypatch):
        layout, _n = self._emit(monkeypatch, _east_wall_dem)
        assert REF_RUNWAY_END_RESA in RUNWAY_END_REGIME_REFS
        assert REF_RUNWAY_END_SKIRT in RUNWAY_END_REGIME_REFS
        for s in self._resa(layout):
            assert s.ref in RUNWAY_END_REGIME_REFS

    def test_cut_welds_to_the_pavement_edge(self, monkeypatch):
        """The inner row carries the local pavement value verbatim (the
        weld ruling), so the cut abuts the runway with zero step."""
        layout, _n = self._emit(monkeypatch, _east_wall_dem)
        cuts = self._resa(layout)
        assert cuts
        anchor = self._anchor_x()
        weld = [alt for s in cuts
                for (vx, _vy), alt in zip(list(s.polygon.exterior.coords),
                                          s.node_altitudes)
                if anchor - 0.02 <= vx <= _RUNWAY_LEN + 0.02]
        assert weld, "no vertex landed on the pavement exit edge"
        for alt in weld:
            assert alt == pytest.approx(_RUNWAY_ALT, abs=0.11)


# ──────────────────────────────────────────────────────────────────────
# The taxiway-end WRAP treats the cut as a join target too
# ──────────────────────────────────────────────────────────────────────
class TestEndRegimeWrapTarget:
    def test_skirt_prep_selects_both_regime_refs(self):
        from shapely.geometry import Point
        from auto_patch import adjacent_ground as AG
        from auto_patch.layout import BuiltShape, PavementLayout

        layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
        layout.shapes.append(BuiltShape(
            polygon=Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
            role=ROLE_RUNWAY_CLEARANCE, ref=REF_RUNWAY_END_SKIRT))
        layout.shapes.append(BuiltShape(
            polygon=Polygon([(20, 0), (30, 0), (30, 10), (20, 10)]),
            role=ROLE_RUNWAY_CLEARANCE, ref=REF_RUNWAY_END_RESA))
        prepared = AG._runway_end_skirt_prep(layout)
        assert prepared is not None
        assert prepared.contains(Point(5, 5))      # the fill skirt
        assert prepared.contains(Point(25, 5))     # the RESA cut

    def test_unrelated_refs_are_not_join_targets(self):
        from auto_patch import adjacent_ground as AG
        from auto_patch.layout import BuiltShape, PavementLayout

        layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
        layout.shapes.append(BuiltShape(
            polygon=Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
            role=ROLE_RUNWAY_CLEARANCE, ref="something_else"))
        assert AG._runway_end_skirt_prep(layout) is None


# ──────────────────────────────────────────────────────────────────────
# ARC R slices R2 / R3 — the cut is a SOLVER-ENFORCED envelope
# ──────────────────────────────────────────────────────────────────────
# R1 admits the cut rings as free variables under a ONE-SIDED envelope
# interval edge; R2 splits the writeback so every cut vertex is
# re-evaluated against the SOLVED, CROWNED pavement-exit reference (the
# foot re-reference discipline) and retires ``_resa_alt_at`` as the
# source of emitted values; R3 pins the lockstep with the validator.
#
# The measurement that motivated the arc: the cut's anchor is NOT the
# immutable CIFP threshold, it is the pavement-EXIT elevation, and that
# read MOVES after the pre-solve emission slot (instrumented CYXY,
# default gates: median 0.110 m, p90 0.150 m, max 0.164 m over 106
# numeric anchor reads, 88 of them over 0.05 m; a further 106 read None
# pre-solve and resolve to real solved values post-solve).  The drift
# test below reproduces that class hermetically by moving the runway
# between emission and the solve.
class _SolveThroughHarness(ResaHarness):
    """Emit PRE-SOLVE (the B1 slot) and then run the real
    ``solve_route_profile`` over the result, exactly as the pipeline
    does under the one-solve terrain gates."""

    @staticmethod
    def _gates(monkeypatch, *, resa_solver):
        import auto_patch.config as cfg
        monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN", True)
        monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT", True)
        monkeypatch.setattr(cfg, "RUNWAY_END_RESA_ENABLED", True)
        monkeypatch.setattr(cfg, "ONE_SOLVE_TERRAIN_RUNWAY_END_RESA",
                            resa_solver)

    def _make_layout(self):
        from auto_patch.canonical_points import CanonicalPointRegistry
        layout = super()._make_layout()
        layout.canonical_points = CanonicalPointRegistry()
        return layout

    def _emit_and_solve(self, monkeypatch, dem_fn, *, resa_solver,
                        perturb_runway_to=None):
        import auto_patch.elevation as EL
        from auto_patch.elevation_per_surface.route_profile import (
            solve_route_profile)
        from auto_patch.layout import R_EARTH

        self._gates(monkeypatch, resa_solver=resa_solver)

        def _fake_sample_dem(dem, tile_lat, tile_lon, lat, lon):
            x = math.radians(lon) * R_EARTH
            y = math.radians(lat) * R_EARTH
            return dem_fn(x, y)

        monkeypatch.setattr(EL, "_sample_dem", _fake_sample_dem)
        layout, _n = self._emit(monkeypatch, dem_fn)
        if perturb_runway_to is not None:
            # THE DRIFT: the pavement-exit elevation the emitter stamped
            # is not the one the solve settles on.
            for s in layout.shapes:
                if s.role == "runway":
                    s.altitude_high = perturb_runway_to
                    s.altitude_low = perturb_runway_to
        solve_route_profile(layout, "ZZZZ", dem=object(), tile_lat=0,
                            tile_lon=0)
        return layout

    @staticmethod
    def _cut_values(layout):
        out = {}
        for s in layout.shapes:
            if (s.role != ROLE_RUNWAY_CLEARANCE
                    or s.ref != REF_RUNWAY_END_RESA):
                continue
            ring = list(s.polygon.exterior.coords)
            if ring and ring[0] == ring[-1]:
                ring = ring[:-1]
            for (x, y), a in zip(ring, s.node_altitudes):
                out[(round(x, 3), round(y, 3))] = a
        return out

    @staticmethod
    def _pav_values(layout):
        out = {}
        for s in layout.shapes:
            if s.role != "runway":
                continue
            out[id(s)] = (s.altitude_high, s.altitude_low,
                          tuple(s.node_altitudes or ()))
        return out


class TestResaSolverAbsorption(_SolveThroughHarness):
    def test_gate_off_keeps_the_analytic_valuation(self, monkeypatch):
        """Gate OFF is today's path verbatim: the cut carries exactly the
        values ``_resa_alt_at`` stamped pre-solve, and no store is
        published."""
        emitted, _n = self._emit(monkeypatch, _east_wall_dem)
        stamped = self._cut_values(emitted)
        assert stamped
        solved = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=False)
        assert getattr(solved, "runway_end_resa_presolve", None) is None
        assert self._cut_values(solved) == stamped

    def test_gate_on_publishes_a_per_end_spec(self, monkeypatch):
        layout = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=True)
        store = getattr(layout, "runway_end_resa_presolve", None)
        assert store, "the solver needs the per-end spec"
        for spec in store:
            assert spec["anchor_xy"] is not None
            assert spec["cap"] == CLEARANCE_MAX_REACH_M["runway"]
            assert spec["ref_presolve"] == pytest.approx(_RUNWAY_ALT)

    def test_gate_on_values_every_cut_vertex_from_the_solve(self,
                                                            monkeypatch):
        layout = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=True)
        counts = getattr(layout, "_runway_end_resa_writeback_counts", None)
        assert counts is not None
        n_solved, n_analytic = counts
        assert n_solved > 10
        # ``_resa_alt_at`` RETIRES under the gate: no emitted vertex is
        # left on the pre-solve analytic value.
        assert n_analytic == 0

    def test_gate_on_is_value_identical_when_the_reference_does_not_move(
            self, monkeypatch):
        """Parity by construction: with the reference unmoved the solved
        encoding reproduces the analytic clamp exactly — so any gate-ON
        delta at a real airport IS reference drift, never solver noise."""
        off = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                   resa_solver=False)
        on = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                  resa_solver=True)
        vo, vn = self._cut_values(off), self._cut_values(on)
        assert vo and set(vo) == set(vn)
        for k in vo:
            assert vn[k] == pytest.approx(vo[k], abs=1e-9), k

    def test_the_cut_tracks_the_SOLVED_reference_not_the_stamp(self,
                                                               monkeypatch):
        """THE ARC: move the pavement-exit elevation between emission and
        the solve (the measured 0.11-0.16 m class).  Gate OFF bakes the
        stale reference; gate ON follows the solved one."""
        drift = 0.5
        off = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                   resa_solver=False,
                                   perturb_runway_to=_RUNWAY_ALT + drift)
        on = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                  resa_solver=True,
                                  perturb_runway_to=_RUNWAY_ALT + drift)
        vo, vn = self._cut_values(off), self._cut_values(on)
        anchor = self._anchor_x()
        reach = CLEARANCE_MAX_REACH_M["runway"]
        moved = 0
        for (vx, vy), a_off in vo.items():
            d = vx - anchor
            if d <= 0.02:
                continue                       # weld row: pavement value
            ceiling_stale = _RUNWAY_ALT + RUNWAY_END_RESA_MAX_SLOPE * max(
                0.0, min(reach, d))
            dem = _east_wall_dem(vx, vy)
            if dem <= ceiling_stale:
                continue                       # DEM binds either way
            # The ceiling BINDS here: gate OFF sits on the stale ramp,
            # gate ON on the solved one, exactly ``drift`` higher.
            assert a_off == pytest.approx(round(ceiling_stale, 1), abs=1e-9)
            assert vn[(vx, vy)] == pytest.approx(
                round(min(dem, ceiling_stale + drift), 1), abs=1e-9)
            moved += 1
        assert moved > 10, "no ceiling-bound vertex to compare"

    def test_gate_on_never_moves_a_pavement_node(self, monkeypatch):
        """Host authority end-to-end: the one-sided edges are one-way, so
        admitting the cut cannot change a single pavement value."""
        off = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                   resa_solver=False)
        on = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                  resa_solver=True)
        assert list(self._pav_values(off).values()) == \
            list(self._pav_values(on).values())

    def test_gate_on_stays_cut_only(self, monkeypatch):
        layout = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=True)
        for (vx, vy), alt in self._cut_values(layout).items():
            dem = _east_wall_dem(vx, vy)
            assert alt <= dem + 0.05, (
                f"vertex ({vx:.1f},{vy:.1f}) rides {alt - dem:.2f} m "
                f"above the DEM — that is a FILL")

    def test_gate_on_still_welds_to_the_pavement_edge(self, monkeypatch):
        layout = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=True)
        anchor = self._anchor_x()
        weld = [a for (vx, _vy), a in self._cut_values(layout).items()
                if anchor - 0.02 <= vx <= _RUNWAY_LEN + 0.02]
        assert weld
        for alt in weld:
            assert alt == pytest.approx(_RUNWAY_ALT, abs=0.11)


# ── R3 — lockstep with the validator ─────────────────────────────────
class TestResaValidatorLockstep(_SolveThroughHarness):
    def _findings(self, layout, dem_fn):
        from auto_patch import verification
        from auto_patch.layout import R_EARTH

        def _fake_sample_dem(dem, tile_lat, tile_lon, lat, lon):
            x = math.radians(lon) * R_EARTH
            y = math.radians(lat) * R_EARTH
            return dem_fn(x, y)

        import auto_patch.elevation as EL
        orig = EL._sample_dem
        EL._sample_dem = _fake_sample_dem
        try:
            return verification.check_runway_end_skirt(
                layout, dem=object(), tile_lat=0, tile_lon=0,
                source_runways=[self._make_runway()])
        finally:
            EL._sample_dem = orig

    def test_solved_cut_clears_the_end_regime_validator(self, monkeypatch):
        """The emitter's output, valued from the SOLVED refs, must leave
        the ``check_runway_end_skirt`` family (end_rise / end_drop /
        end_drop_flank) at ZERO — the reader evaluates the same
        ``grade_law.runway_end_envelope`` against the same solved
        pavement, so surface and check cannot drift."""
        layout = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=True)
        assert self._findings(layout, _east_wall_dem) == []

    def test_the_validator_sees_the_drifted_reference_too(self,
                                                          monkeypatch):
        """With the reference moved between emission and the solve the
        validator reads the SOLVED pavement — so only the gate-ON surface
        can stay lawful by construction.  Both are asserted so a
        regression in either direction shows."""
        layout = self._emit_and_solve(monkeypatch, _east_wall_dem,
                                      resa_solver=True,
                                      perturb_runway_to=_RUNWAY_ALT + 0.5)
        assert self._findings(layout, _east_wall_dem) == []


# ── R2 — the crown frontier at the cut welds ─────────────────────────
class TestResaCrownFrontier:
    """ASSERTED, not assumed (the R2 mandate): ``crown.build_crown_drop_
    field`` freezes a node at c = 0 as soon as ANY owning shape is a
    non-crown role.  ``runway_clearance`` is such a role, so both the
    RESA cut and the runway-end skirt land in ``frozen_keys`` — a cut
    vertex never crowns, and a runway vertex the cut welds to joins the
    runway's UNCROWNED FRONTIER (which is what the axial taper exists
    to shed into)."""

    def _field(self, extra_shapes=(), crown_drop=0.15):
        from auto_patch.canonical_points import CanonicalPointRegistry
        from auto_patch.crown import build_crown_drop_field
        from auto_patch.layout import BuiltShape, PavementLayout

        rect = Polygon([(0.0, -_HALF_WIDTH), (_RUNWAY_LEN, -_HALF_WIDTH),
                        (_RUNWAY_LEN, _HALF_WIDTH), (0.0, _HALF_WIDTH)])
        layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
        layout.canonical_points = CanonicalPointRegistry()
        layout.shapes.append(BuiltShape(
            polygon=rect, role="runway", ref="09-27",
            altitude_high=_RUNWAY_ALT, altitude_low=_RUNWAY_ALT))
        layout.shapes.extend(extra_shapes)
        # FIXTURE COMPLETED 2026-08-04 (landing commit d371e68, which
        # added ``crown._rail_continuous_drops``).  This stub carried only
        # ``crown_drop_m`` because nothing in ``build_crown_drop_field``
        # sampled the redistributed profile before d371e68; after it, all
        # three tests in this class died on ``KeyError: 'axis_a'`` inside
        # ``runway_redistribute.sample_redistributed_profile`` — a stale
        # FIXTURE, not a law failure.  The remaining keys are the record
        # ``redistribute_runway_profile`` actually writes
        # (runway_redistribute.py:1216-1222).  The profile is FLAT at
        # ``_RUNWAY_ALT``, which is this fixture's own declared world
        # (the runway shape is built with altitude_high == altitude_low
        # == _RUNWAY_ALT), so completing it adds no slope the test never
        # asked for.
        layout._runway_redistributed_profiles = {
            "09-27": {"crown_drop_m": crown_drop,
                      "axis_a": (0.0, 0.0),
                      "axis_d": (_RUNWAY_LEN, 0.0),
                      "axis_len2": _RUNWAY_LEN ** 2,
                      "half_width_m": _HALF_WIDTH,
                      "fractions": [0.0, 1.0],
                      "elevs": [_RUNWAY_ALT, _RUNWAY_ALT]}}
        cps = layout.canonical_points
        nodes, b2i = [], {}
        for s in layout.shapes:
            for (x, y) in list(s.polygon.exterior.coords)[:-1]:
                k = cps.get_or_add(float(x), float(y))
                if k not in b2i:
                    b2i[k] = len(nodes)
                    nodes.append((float(x), float(y)))
        drops = build_crown_drop_field(layout, nodes, b2i, set())
        return layout, nodes, b2i, drops

    def test_a_bare_runway_does_crown(self):
        """Control: without a cut the runway's own corners take the
        per-ref drop, so the assertions below are not vacuous."""
        _layout, _nodes, _b2i, drops = self._field()
        assert drops and max(drops.values()) == pytest.approx(0.15)

    def test_cut_vertices_never_crown(self):
        from auto_patch.layout import BuiltShape
        cut = Polygon([(_RUNWAY_LEN, -_HALF_WIDTH),
                       (_RUNWAY_LEN + 60.0, -_HALF_WIDTH),
                       (_RUNWAY_LEN + 60.0, _HALF_WIDTH),
                       (_RUNWAY_LEN, _HALF_WIDTH)])
        _layout, nodes, b2i, drops = self._field(extra_shapes=[BuiltShape(
            polygon=cut, role=ROLE_RUNWAY_CLEARANCE,
            ref=REF_RUNWAY_END_RESA,
            node_altitudes=[_RUNWAY_ALT] * 5)])
        for i, (x, _y) in enumerate(nodes):
            if x >= _RUNWAY_LEN - 1e-9:
                assert i not in drops, (
                    f"node {i} at x={x} is a cut vertex (or a runway "
                    f"vertex the cut welds to) and must emit UNCROWNED")
        # …and the far runway end, untouched by the cut, still crowns —
        # so the freeze is scoped to the weld, not global.
        far = [i for i, (x, _y) in enumerate(nodes) if x < 1e-9]
        assert far and all(i in drops for i in far)

    def test_skirt_and_cut_freeze_identically(self):
        """The R2 expectation in one line: ``frozen_keys`` is ROLE-keyed,
        so the cut inherits the skirt's crown contract exactly."""
        from auto_patch.layout import BuiltShape
        poly = Polygon([(_RUNWAY_LEN, -_HALF_WIDTH),
                        (_RUNWAY_LEN + 60.0, -_HALF_WIDTH),
                        (_RUNWAY_LEN + 60.0, _HALF_WIDTH),
                        (_RUNWAY_LEN, _HALF_WIDTH)])
        by_ref = {}
        for ref in (REF_RUNWAY_END_SKIRT, REF_RUNWAY_END_RESA):
            _layout, nodes, _b2i, drops = self._field(
                extra_shapes=[BuiltShape(
                    polygon=poly, role=ROLE_RUNWAY_CLEARANCE, ref=ref,
                    node_altitudes=[_RUNWAY_ALT] * 5)])
            by_ref[ref] = {nodes[i]: d for i, d in drops.items()}
        assert by_ref[REF_RUNWAY_END_SKIRT] == by_ref[REF_RUNWAY_END_RESA]
