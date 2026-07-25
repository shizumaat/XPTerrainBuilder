"""Adjacent-ground arcs A3 (END-AWARE BENCH PIN) and A4 (RUNWAY STRIP
WIDTH MEASURED FROM THE CENTERLINE).

A3 — ``adjacent_ground_supported_depths`` benches a band's daylight depth
down toward any neighbour at depth 0.  A runway END-edge station is at
depth 0 only because ``_station_reference`` SKIPS it (its outward normal
points along the runway axis — the end is skirt / RESA territory), so the
lateral wing collapses diagonally into the end corner.  With
``ADJACENT_GROUND_END_PIN_ENABLED`` the station adjacent to an end-skip
run is PINNED (holds its raw scanned depth in both bench sweeps, the
existing ``at_continuation_seam`` mechanism) and the wing ends square.

A4 — ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` is an Annex-14 half-width from
the CENTERLINE, but the march spends it outward from the pavement EDGE
and the emitted runway carries apt.dat shoulders.  With
``STRIP_WIDTH_FROM_CENTERLINE_ENABLED`` each runway-family station's caps
are clamped by ``grade_law.runway_strip_band_width_m``.

Both gates default OFF and both must be structurally inert when off.
Everything here is headless: synthetic rings, stub DEM, no X-Plane data.
"""
import types

import pytest
from shapely.geometry import LineString, Polygon
from shapely.prepared import prep

from auto_patch.config import (
    CLEARANCE_STATION_STEP_M,
    RUNWAY_STRIP_HALF_WIDTH_BY_CODE,
)
from auto_patch.grade_law import (
    ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT,
    adjacent_ground_end_pin_flags,
    adjacent_ground_envelope,
    adjacent_ground_supported_depths,
    runway_strip_band_width_m,
)
from auto_patch import adjacent_ground as AG

STEP = CLEARANCE_STATION_STEP_M
EDGE_ALT = 100.0
TRIGGER = 1.0

# Runway axis along +x; the rect's END edges therefore carry outward
# normals (±1, 0), which is what ``_station_reference`` skips.
AXIS = (1.0, 0.0)
RUNWAY_LEN = 600.0
# ICAO code-4 graded strip half-width — read from config, never a literal.
STRIP_HALF = RUNWAY_STRIP_HALF_WIDTH_BY_CODE[4]


def _runway_closures(width):
    """The real corridor closures for the runway family, code 3."""
    def ceil_off(d):
        return adjacent_ground_envelope("runway", 3, None, d)[1]

    def floor_depth(d):
        f = adjacent_ground_envelope("runway", 3, None, min(d, width))[0]
        return None if f is None else -f
    return ceil_off, floor_depth


def _ring(half_width):
    """CCW runway rectangle of the given PAVEMENT half-width."""
    return [(0.0, -half_width), (RUNWAY_LEN, -half_width),
            (RUNWAY_LEN, half_width), (0.0, half_width),
            (0.0, -half_width)]


def _far_static():
    """A prepared static block nowhere near the ring, so the
    terrain-facing probe never skips a station."""
    return prep(Polygon([(-9000, -9000), (-8000, -9000),
                         (-8000, -8000), (-9000, -8000)]))


def _high_dem(rise=30.0):
    """DEM far above the corridor ceiling everywhere → every station that
    keeps a reference is obstructed to its full band cap."""
    def dem(x, y):
        return EDGE_ALT + rise
    return dem


def _derive(monkeypatch, *, half_width=22.5, reach=100.0,
            width=STRIP_HALF, axis=AXIS, axis_line=None,
            end_pin=False, strip_from_centerline=False, dem=None,
            ols_cut=False, axis_classes=None):
    monkeypatch.setattr(AG, "_END_PIN", end_pin)
    monkeypatch.setattr(AG, "_STRIP_WIDTH_FROM_CENTERLINE",
                        strip_from_centerline)
    monkeypatch.setattr(AG, "_OLS_CUT", ols_cut)
    ceil_off, floor_depth = _runway_closures(width)
    coords = _ring(half_width)
    return AG._derive_shape_stations_and_bands(
        coords, True, [EDGE_ALT] * len(coords), axis, width, reach,
        TRIGGER, floor_depth, ceil_off, STEP, _far_static(), set(),
        dem if dem is not None else _high_dem(),
        axis_line=axis_line, axis_classes=axis_classes)


def _max_lateral(bands, x_min=None):
    """Greatest |y| any band vertex reaches (optionally only past
    ``x_min``) — how deep the corridor actually got."""
    ys = [abs(y) for ring, _a in bands for x, y in ring
          if x_min is None or x >= x_min]
    return max(ys) if ys else 0.0


# ──────────────────────────────────────────────────────────────────────
# The law itself (grade_law.adjacent_ground_end_pin_flags)
# ──────────────────────────────────────────────────────────────────────
class TestEndPinFlags:
    def test_flags_the_usable_neighbours_of_an_end_run(self):
        end = [False, False, True, True, False, False]
        usable = [True, True, False, False, True, True]
        assert adjacent_ground_end_pin_flags(end, usable) == [
            False, True, False, False, True, False]

    def test_an_unusable_station_is_never_pinned(self):
        end = [True, False, True]
        usable = [False, False, False]
        assert adjacent_ground_end_pin_flags(end, usable) == [
            False, False, False]

    def test_no_end_skips_pins_nothing(self):
        n = 6
        assert adjacent_ground_end_pin_flags([False] * n, [True] * n) == \
            [False] * n

    def test_a_pinned_station_holds_its_raw_depth(self):
        """The pin reuses ``at_continuation_seam`` verbatim: a marked
        station is never lowered by either bench sweep."""
        depths = [0.0, 100.0, 100.0, 100.0]
        positions = [(0.0, 0.0), (0.0, 5.0), (0.0, 10.0), (0.0, 15.0)]
        benched = adjacent_ground_supported_depths(depths, positions)
        assert benched[1] == pytest.approx(
            ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT * 5.0)
        pinned = adjacent_ground_supported_depths(
            depths, positions, [False, True, False, False])
        assert pinned[1] == pytest.approx(100.0)
        # …and the pinned station SUPPORTS its interior neighbours, so
        # the daylight line stays continuous into the shape.
        assert pinned[2] >= benched[2]


# ──────────────────────────────────────────────────────────────────────
# A3 in the march
# ──────────────────────────────────────────────────────────────────────
class TestEndPinInTheMarch:
    _REACH = 100.0
    # The last 20 m of frontage before the end corner (x = 600).
    _CORNER_X = RUNWAY_LEN - 20.0

    def test_gate_off_tapers_into_the_end_corner(self, monkeypatch):
        _fill, cut, _st, _sa, _ou = _derive(
            monkeypatch, reach=self._REACH, end_pin=False)
        assert cut
        deep = _max_lateral(cut)
        corner = _max_lateral(cut, x_min=self._CORNER_X)
        # Mid-frontage the band reaches its full cap; at the corner the
        # daylight bench has collapsed it toward the (skipped) end
        # stations at depth 0.
        assert deep > corner + 20.0

    def test_gate_on_holds_full_depth_at_the_end_corner(self,
                                                        monkeypatch):
        off = _derive(monkeypatch, reach=self._REACH, end_pin=False)[1]
        on = _derive(monkeypatch, reach=self._REACH, end_pin=True)[1]
        assert on
        corner_off = _max_lateral(off, x_min=self._CORNER_X)
        corner_on = _max_lateral(on, x_min=self._CORNER_X)
        assert corner_on > corner_off + 20.0
        # The pinned wing terminates at the SAME depth it holds
        # mid-frontage — square against the end regime, not diagonal.
        assert corner_on == pytest.approx(_max_lateral(on), abs=0.5)

    def test_gate_on_never_reduces_coverage(self, monkeypatch):
        off = _derive(monkeypatch, reach=self._REACH, end_pin=False)[1]
        on = _derive(monkeypatch, reach=self._REACH, end_pin=True)[1]
        assert _max_lateral(on) >= _max_lateral(off) - 1e-9

    def test_gate_off_is_byte_identical(self, monkeypatch):
        """The pin's inputs are built unconditionally; with the gate OFF
        the march must reproduce the pre-feature rings exactly."""
        a = _derive(monkeypatch, reach=self._REACH, end_pin=False)
        b = _derive(monkeypatch, reach=self._REACH, end_pin=False)
        assert [r for r, _ in a[0]] == [r for r, _ in b[0]]
        assert [r for r, _ in a[1]] == [r for r, _ in b[1]]
        assert a[2] == b[2] and a[3] == b[3] and a[4] == b[4]

    def test_pin_is_inert_without_a_runway_axis(self, monkeypatch):
        """No axis → no end-normal skip → nothing to pin, so the gate
        cannot move a taxiway/apron march."""
        off = _derive(monkeypatch, reach=self._REACH, axis=None,
                      end_pin=False)
        on = _derive(monkeypatch, reach=self._REACH, axis=None,
                     end_pin=True)
        assert [r for r, _ in off[1]] == [r for r, _ in on[1]]
        assert [r for r, _ in off[0]] == [r for r, _ in on[0]]
        assert AG._APPARATUS_HITS.get("end_pin_flagged_stations", 0) >= 0

    def test_pin_fires_only_on_end_skips_not_probe_skips(self,
                                                         monkeypatch):
        """A station skipped by the terrain-facing PROBE (a neighbouring
        pavement) is genuinely covered ground — the bench must still
        ramp down to it, so no pin is minted there."""
        monkeypatch.setattr(AG, "_END_PIN", True)
        monkeypatch.setattr(AG, "_STRIP_WIDTH_FROM_CENTERLINE", False)
        ceil_off, floor_depth = _runway_closures(STRIP_HALF)
        coords = _ring(22.5)
        # Static pavement hugging the NORTH flank over its middle third:
        # the probe (1.5 m out) lands on it, so those stations skip.
        blocker = prep(Polygon([(200.0, 23.0), (400.0, 23.0),
                                (400.0, 60.0), (200.0, 60.0)]))
        _f, cut, _st, _sa, _ou = AG._derive_shape_stations_and_bands(
            coords, True, [EDGE_ALT] * len(coords), AXIS, STRIP_HALF,
            self._REACH, TRIGGER, floor_depth, ceil_off, STEP,
            blocker, set(), _high_dem())
        # The band still benches in toward the probe-skipped run (its
        # depth near x = 200 is well under the full cap).
        near = [abs(y) for ring, _a in cut for x, y in ring
                if 190.0 <= x <= 210.0 and y > 0.0]
        assert near, "no north-flank band vertices near the blocker"
        assert max(near) < 22.5 + self._REACH - 20.0


# ──────────────────────────────────────────────────────────────────────
# A4 — the strip measured from the centreline
# ──────────────────────────────────────────────────────────────────────
class TestStripWidthFromCenterline:
    # SPJC 16R/34L: apt.dat width 45 m, emitted pavement 81 m wide.
    _PAV_HALF = 40.5
    _REACH = 300.0
    _AXIS_LINE = LineString([(0.0, 0.0), (RUNWAY_LEN, 0.0)])

    def test_law_helper_matches_the_legacy_pass_a3_clamp(self):
        # Pass A3: band = min(band_cap, strip_half − dist(station, axis)).
        for dist in (0.0, 10.0, 40.5, 74.0, 75.0, 90.0):
            assert runway_strip_band_width_m(
                STRIP_HALF, dist, self._REACH) == max(
                    0.0, min(self._REACH, STRIP_HALF - dist))
        # No axis → the cap passes through untouched (inert).
        assert runway_strip_band_width_m(
            STRIP_HALF, None, self._REACH) == self._REACH

    def test_gate_off_overshoots_the_strip_by_the_shoulder(self,
                                                           monkeypatch):
        _fill, cut, _st, _sa, _ou = _derive(
            monkeypatch, half_width=self._PAV_HALF, reach=self._REACH,
            axis_line=self._AXIS_LINE, strip_from_centerline=False)
        assert cut
        # Full half-width spent off the pavement EDGE: 40.5 + 75 = 115.5
        # from the centreline, where the Annex-14 strip is 75.
        assert _max_lateral(cut) > STRIP_HALF + 20.0

    def test_gate_on_leaves_the_cut_reaching_past_the_graded_strip(
            self, monkeypatch):
        """A4 clamps the FILL only — the CUT keeps the family reach.

        REVISED 2026-07-24 (was ``test_gate_on_stops_at_the_strip_edge``,
        which asserted the cut stopped at the graded strip edge too).
        That behaviour was a functional REGRESSION: zone 3 — the UNGRADED
        strip, which ICAO Annex 14 §3.4.16 governs at ≤5 % up out to the
        FULL strip edge — was erased entirely, so rising terrain beyond
        the graded band lost the protection it has today.  The cut cap now
        belongs to the OLS handover (see the test below); with the OLS
        gate off the cut keeps the zone-3-to-reach stand-in it has always
        had, and each gate is independently sound.
        """
        _fill, cut, _st, _sa, _ou = _derive(
            monkeypatch, half_width=self._PAV_HALF, reach=self._REACH,
            axis_line=self._AXIS_LINE, strip_from_centerline=True)
        assert cut, "the clamp must not delete the cut band"
        assert _max_lateral(cut) > STRIP_HALF + 1e-6

    def test_gate_on_clamps_the_fill_cap(self, monkeypatch):
        """A4's whole job: the FILL stops at the true strip edge.

        Filling is a GRADED-strip mandate, so the graded half-width is the
        right bound — and this is the only cap A4 owns (the cut's belongs
        to the OLS handover; see the test above and ``TestOlsHandover``).
        """
        def _low_dem(x, y):
            return EDGE_ALT - 30.0        # deep drop → fill everywhere
        off = _derive(monkeypatch, half_width=self._PAV_HALF,
                      reach=self._REACH, axis_line=self._AXIS_LINE,
                      strip_from_centerline=False, dem=_low_dem)[0]
        on = _derive(monkeypatch, half_width=self._PAV_HALF,
                     reach=self._REACH, axis_line=self._AXIS_LINE,
                     strip_from_centerline=True, dem=_low_dem)[0]
        assert off and on
        assert _max_lateral(off) > STRIP_HALF + 20.0
        assert _max_lateral(on) <= STRIP_HALF + 1e-6

    def test_no_axis_line_is_byte_identical(self, monkeypatch):
        """``axis_line=None`` (every non-runway family, and the runway
        family before the gate) reproduces the pre-feature march."""
        a = _derive(monkeypatch, half_width=self._PAV_HALF,
                    reach=self._REACH, axis_line=None,
                    strip_from_centerline=True)
        b = _derive(monkeypatch, half_width=self._PAV_HALF,
                    reach=self._REACH, axis_line=None,
                    strip_from_centerline=False)
        assert [r for r, _ in a[0]] == [r for r, _ in b[0]]
        assert [r for r, _ in a[1]] == [r for r, _ in b[1]]

    def test_gate_off_with_an_axis_line_is_byte_identical(self,
                                                          monkeypatch):
        a = _derive(monkeypatch, half_width=self._PAV_HALF,
                    reach=self._REACH, axis_line=self._AXIS_LINE,
                    strip_from_centerline=False)
        b = _derive(monkeypatch, half_width=self._PAV_HALF,
                    reach=self._REACH, axis_line=None,
                    strip_from_centerline=False)
        assert [r for r, _ in a[0]] == [r for r, _ in b[0]]
        assert [r for r, _ in a[1]] == [r for r, _ in b[1]]


# ──────────────────────────────────────────────────────────────────────
# _family_params now carries the axis LineString for runway shapes
# ──────────────────────────────────────────────────────────────────────
class TestFamilyParamsAxisLine:
    def _axes(self):
        line = LineString([(0.0, 0.0), (RUNWAY_LEN, 0.0)])
        return [(line, (1.0, 0.0), RUNWAY_LEN)]

    def test_runway_shape_gets_its_nearest_axis_line(self):
        shape = types.SimpleNamespace(
            role="runway", ref="09-27",
            polygon=Polygon(_ring(40.5)))
        params = AG._family_params(types.SimpleNamespace(shapes=[shape]),
                                   shape, self._axes())
        assert params is not None
        (family, _code_n, _code_l, _reach, width, axis, axis_line,
         _axis_classes) = params
        assert family == "runway"
        assert axis == (1.0, 0.0)
        assert axis_line is not None
        assert axis_line.equals(
            LineString([(0.0, 0.0), (RUNWAY_LEN, 0.0)]))
        # The band width is the Annex-14 strip half-width for the axis'
        # own code number — never a literal at the call site.
        from auto_patch.config import (
            RUNWAY_STRIP_HALF_WIDTH_BY_CODE, runway_code_number)
        assert width == RUNWAY_STRIP_HALF_WIDTH_BY_CODE[
            runway_code_number(RUNWAY_LEN)]

    def test_non_runway_families_carry_no_axis_line(self):
        apron = types.SimpleNamespace(
            role="apron", ref=None, polygon=Polygon(_ring(40.5)))
        params = AG._family_params(types.SimpleNamespace(shapes=[apron]),
                                   apron, self._axes())
        assert params is not None
        assert params[5] is None and params[6] is None


# ──────────────────────────────────────────────────────────────────────
# The OLS handover owns the CUT cap ("one S", 2026-07-24)
# ──────────────────────────────────────────────────────────────────────
class TestOlsHandover:
    """The cut cap belongs to the OLS handover, not to A4.

    Design (docs/specs/obstacle-limitation-surfaces-spec.md, continuity
    ruling): the lateral cut is bounded by the OLS transitional surface,
    which takes over at the handover ``S``.  Two properties matter and
    neither held in the first implementation:

    * With the OLS gate ON the cut reach SHRINKS to ``S`` — on its own,
      not as a side effect of A4.  (The original code took ``max()`` over
      caps initialised to the family reach, which never shrank anything.)
    * ``S`` is computed from the runway's REAL apt.dat end classes, the
      same ones ``ols._flank_law`` min-composes, so the two emitters
      cannot disagree about where the handover is.
    """
    _PAV_HALF = 40.5
    _REACH = 300.0
    # A CODE-4 axis (SPJC 16R/34L is 3,496 m).  The code number is read
    # off the axis LENGTH, and at code 1 the handover's graded-width floor
    # dominates both classes — max(30−40.5, 30) == max(70−40.5, 30) == 30 —
    # so a short axis would hide the very distinction under test.  The
    # ring itself stays RUNWAY_LEN long; only the axis is full length,
    # which is also what a real layout hands the march.
    _AXIS_LINE = LineString([(0.0, 0.0), (3496.5, 0.0)])

    def _cut(self, monkeypatch, **kw):
        return _derive(monkeypatch, half_width=self._PAV_HALF,
                       reach=self._REACH, axis_line=self._AXIS_LINE,
                       **kw)[1]

    def test_gate_on_shrinks_the_cut_to_the_handover(self, monkeypatch):
        """OLS-alone must shrink the reach — no A4 required."""
        off = self._cut(monkeypatch, ols_cut=False)
        on = self._cut(monkeypatch, ols_cut=True,
                       axis_classes=("non_precision", "non_precision"))
        assert off and on
        assert _max_lateral(on) < _max_lateral(off)

    def test_handover_uses_the_real_end_classes(self, monkeypatch):
        """A VISUAL runway hands over earlier than an instrument one —
        its OLS strip is the narrower non-instrument width.  If this
        ever stopped mattering, the emitters would have silently agreed
        on a default instead of on the data."""
        visual = self._cut(monkeypatch, ols_cut=True,
                           axis_classes=("visual", "visual"))
        instrument = self._cut(monkeypatch, ols_cut=True,
                               axis_classes=("precision", "precision"))
        assert visual and instrument
        assert _max_lateral(visual) < _max_lateral(instrument)

    def test_mixed_end_classes_take_the_minimum(self, monkeypatch):
        """One runway, two ends, two classes: S is the MINIMUM over them,
        matching ``ols._flank_law``'s min-composition."""
        mixed = self._cut(monkeypatch, ols_cut=True,
                          axis_classes=("visual", "precision"))
        visual = self._cut(monkeypatch, ols_cut=True,
                           axis_classes=("visual", "visual"))
        assert mixed and visual
        assert _max_lateral(mixed) == pytest.approx(
            _max_lateral(visual), abs=1e-6)

    def test_missing_classes_fall_back_to_instrument(self, monkeypatch):
        """Blank apt.dat metadata takes the conservative (wider) reading,
        the same direction ``config.runway_end_approach_class`` takes."""
        none = self._cut(monkeypatch, ols_cut=True, axis_classes=None)
        npa = self._cut(monkeypatch, ols_cut=True,
                        axis_classes=("non_precision", "non_precision"))
        assert none and npa
        assert _max_lateral(none) == pytest.approx(
            _max_lateral(npa), abs=1e-6)

    def test_gate_off_is_inert(self, monkeypatch):
        """Gate off ⇒ the classes are never consulted."""
        a = self._cut(monkeypatch, ols_cut=False, axis_classes=None)
        b = self._cut(monkeypatch, ols_cut=False,
                      axis_classes=("visual", "visual"))
        assert _max_lateral(a) == pytest.approx(_max_lateral(b), abs=1e-9)
