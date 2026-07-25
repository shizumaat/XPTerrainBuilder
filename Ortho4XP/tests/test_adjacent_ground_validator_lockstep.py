"""Adjacent-ground EMITTER↔VALIDATOR lockstep (the four mirrors).

``verification.check_adjacent_ground`` keeps its OWN station march — it
reads the DEM where ``adjacent_ground._derive_shape_stations_and_bands``
reads-and-writes band geometry — so every per-station behaviour the
emitter applies has to be mirrored in the validator or the two disagree
the moment a gate flips.  ``grade_law.adjacent_ground_supported_depths``
states the mandate: *the validator flags any un-covered corridor breach,
so an emitter-only clamp would leave the clamped-away deep columns still
breaching and mint findings.*

Four behaviours are pinned here, each over the SAME synthetic input fed
to BOTH readers:

  1. **band caps** — the arc-A4 per-station FILL clamp
     (``STRIP_WIDTH_FROM_CENTERLINE_ENABLED``) and the OLS handover CUT
     cap (``OLS_CUT_ENABLED``), asserted equal in all FOUR gate states on
     a shoulder-widened runway;
  2. **the A3 end-skip bench pin** (``ADJACENT_GROUND_END_PIN_ENABLED``)
     — flag-vector equality, INCLUDING the ordering corner: the emitter
     decides ``"end"`` BEFORE the crossing-zone and static-probe tests,
     so an end-edge station whose outward probe is static-covered still
     reads ``"end"`` and still pins its neighbour;
  3. **the B1 pocket-collar exemption**
     (``POCKET_COLLAR_RINGS_ENABLED``) — a flagged column whose
     station→sample transect crosses an emitted collar ring is the
     collar's ground, not the lateral band's;
  4. **the B1 collared-pocket STATION STAND-DOWN** (same gate) — the
     emitter drops every station facing a pocket whose collar rings
     emitted, so the validator must drop the same ones.  Its companion
     invariant, ``check_collar_ring_band_overlap`` (no collar ring may
     run inside a band polygon), is pinned at the end of this file: it
     is the check that would have caught the SPJC X-Plane crash.

GATE PLUMBING.  The emitter reads MODULE-LOCAL bindings snapshotted from
config at import time (``AG._END_PIN`` & co, "so a test can flip it
without re-importing config"); the validator reads ``config`` at call
time.  ``_set_gates`` drives BOTH off one boolean per gate, which is
exactly the lockstep claim under test — one gate value, two readers.

Everything is headless: synthetic rings, stub DEM, no X-Plane data.
"""
import math

import pytest
from shapely.geometry import LineString, Point, Polygon
from shapely.prepared import prep

from auto_patch import adjacent_ground as AG
from auto_patch import config as cfg
from auto_patch import elevation as ELEV
from auto_patch import verification as V
from auto_patch.apt_dat_reader import Runway
from auto_patch.config import (
    CLEARANCE_MAX_REACH_M,
    CLEARANCE_STATION_STEP_M,
    RUNWAY_STRIP_HALF_WIDTH_BY_CODE,
)
from auto_patch.grade_law import (
    adjacent_ground_envelope,
    ols_lateral_handover_distance_m,
    runway_strip_band_width_m,
)
from auto_patch.layout import BuiltShape, PavementLayout, R_EARTH

STEP = CLEARANCE_STATION_STEP_M
EDGE_ALT = 100.0
TRIGGER = 1.0
REACH = CLEARANCE_MAX_REACH_M["runway"]

# A shoulder-widened runway: the emitted pavement is 81 m wide (SPJC
# 16R/34L with its apt.dat shoulders) while the Annex-14 graded strip is
# measured from the CENTERLINE — which is the whole point of arc A4.
PAVEMENT_HALF = 40.5
RUNWAY_LEN = 3000.0                      # ICAO code 4
CODE_NUMBER = 4
STRIP_HALF = RUNWAY_STRIP_HALF_WIDTH_BY_CODE[CODE_NUMBER]
AXIS = (1.0, 0.0)
AXIS_LINE = LineString([(0.0, 0.0), (RUNWAY_LEN, 0.0)])
# Two DIFFERENT end classes, so a test that silently used only one would
# pick a different S than the ``min`` the emitter takes.
AXIS_CLASSES = ("precision", "visual")


def _set_gates(monkeypatch, *, a4=False, ols=False, end_pin=False,
               collar=False):
    """Drive the emitter's module-local bindings AND the validator's
    config reads off the SAME per-gate boolean."""
    monkeypatch.setattr(AG, "_STRIP_WIDTH_FROM_CENTERLINE", a4)
    monkeypatch.setattr(cfg, "STRIP_WIDTH_FROM_CENTERLINE_ENABLED", a4)
    monkeypatch.setattr(AG, "_OLS_CUT", ols)
    monkeypatch.setattr(cfg, "OLS_CUT_ENABLED", ols)
    monkeypatch.setattr(AG, "_END_PIN", end_pin)
    monkeypatch.setattr(cfg, "ADJACENT_GROUND_END_PIN_ENABLED", end_pin)
    monkeypatch.setattr(cfg, "POCKET_COLLAR_RINGS_ENABLED", collar)


def _ring(half_width=PAVEMENT_HALF, length=RUNWAY_LEN):
    """CCW runway rectangle of the given PAVEMENT half-width.  Every
    corner sits between an END edge and a side edge, so the emitter
    suppresses every corner fan (a fan needs both flanks unskipped) and
    the two readers' station lists align 1:1."""
    return [(0.0, -half_width), (length, -half_width),
            (length, half_width), (0.0, half_width),
            (0.0, -half_width)]


def _closures(width):
    """The emitter's ``_band_family_closures`` for the runway family."""
    def ceil_off(d):
        return adjacent_ground_envelope("runway", CODE_NUMBER, None, d)[1]

    def floor_depth(d):
        f = adjacent_ground_envelope(
            "runway", CODE_NUMBER, None, min(d, width))[0]
        return None if f is None else -f
    return ceil_off, floor_depth


def _flat_dem(x, y):
    """Terrain far above the corridor ceiling → every usable station is
    obstructed to its full cap, so the builders actually run."""
    return EDGE_ALT + 30.0


def _emitter_march(monkeypatch, *, coords, static_poly=None,
                   axis_line=AXIS_LINE, axis_classes=AXIS_CLASSES,
                   width=STRIP_HALF, reach=REACH):
    """Run the emitter's march and CAPTURE the two per-station arrays it
    hands the band builders: ``band_caps`` (positional 3) and
    ``at_continuation_seam`` (positional 10, i.e. ``at_seam`` AFTER the
    A3 end pin has been OR-ed in).  Returns
    ``(stations, fill_caps, cut_caps, at_seam)``."""
    captured = {}
    real_fill, real_cut = AG._build_fill_bands, AG._build_cut_bands

    def _cap_fill(*a, **k):
        captured["fill_caps"] = list(a[3])
        captured["at_seam"] = list(a[10])
        return real_fill(*a, **k)

    def _cap_cut(*a, **k):
        captured["cut_caps"] = list(a[3])
        captured["at_seam"] = list(a[10])
        return real_cut(*a, **k)

    monkeypatch.setattr(AG, "_build_fill_bands", _cap_fill)
    monkeypatch.setattr(AG, "_build_cut_bands", _cap_cut)
    ceil_off, floor_depth = _closures(width)
    if static_poly is None:
        static_poly = Polygon([(-9000, -9000), (-8000, -9000),
                               (-8000, -8000), (-9000, -8000)])
    _fb, _cb, stations, _sa, _ou = AG._derive_shape_stations_and_bands(
        coords, True, [EDGE_ALT] * len(coords), AXIS, width, reach,
        TRIGGER, floor_depth, ceil_off, STEP, prep(static_poly), set(),
        _flat_dem, axis_line=axis_line, axis_classes=axis_classes)
    return (stations, captured["fill_caps"], captured["cut_caps"],
            captured["at_seam"])


def _validator_march(*, coords, static_poly=None, axis_line=AXIS_LINE,
                     axis_classes=AXIS_CLASSES, width=STRIP_HALF,
                     reach=REACH):
    """The validator's twin of ``_emitter_march``: its station march plus
    its per-station caps.  Returns
    ``(stations, fill_caps, cut_caps, st_seam, st_end_skip, st_flag,
    st_outn)``."""
    if static_poly is None:
        static_poly = Polygon([(-9000, -9000), (-8000, -9000),
                               (-8000, -8000), (-9000, -8000)])

    def _probe_covered(px, py):
        return static_poly.covers(Point(px, py))

    (st_x, st_y, st_outn, _ref, st_flag, st_seam,
     st_end_skip) = V._adjacent_ground_stations(
        coords, True, [EDGE_ALT] * len(coords), AXIS, STEP, set(),
        _probe_covered)
    stations = list(zip(st_x, st_y))
    fill_caps, cut_caps = V._adjacent_ground_station_caps(
        stations, width, reach, axis_line, axis_classes)
    return (stations, fill_caps, cut_caps, st_seam, st_end_skip, st_flag,
            st_outn)


def _end_edge_indices(st_outn):
    """Stations whose outward normal points ALONG the runway axis — the
    END-edge stations (``clearance._RING_END_NORMAL_DOT``)."""
    from auto_patch.clearance import _RING_END_NORMAL_DOT
    return [i for i, (nx, ny) in enumerate(st_outn)
            if abs(nx * AXIS[0] + ny * AXIS[1]) > _RING_END_NORMAL_DOT]


# ══════════════════════════════════════════════════════════════════════
# MIRROR 1 — per-station band caps, all four gate states
# ══════════════════════════════════════════════════════════════════════
class TestBandCapsLockstep:
    """The emitter clamps the FILL to the remaining strip width (A4) and
    hands the CUT cap to the OLS handover S; the validator scanned and
    flagged to the bare family reach with no caps at all, so flipping
    either gate made it over-report — ``should_fill`` on
    ``[strip-remaining, width]`` and ``should_cut`` on ``[S, reach]``."""

    @pytest.mark.parametrize("a4", [False, True])
    @pytest.mark.parametrize("ols", [False, True])
    def test_caps_match_the_emitter_exactly(self, monkeypatch, a4, ols):
        _set_gates(monkeypatch, a4=a4, ols=ols)
        coords = _ring()
        e_st, e_fill, e_cut, _seam = _emitter_march(
            monkeypatch, coords=coords)
        v_st, v_fill, v_cut, _s, _e, _f, _o = _validator_march(coords=coords)
        # The station SEQUENCES must align first — a cap comparison over
        # differently-stationed frontage would be meaningless.
        assert len(v_st) == len(e_st)
        for (vx, vy), (ex, ey) in zip(v_st, e_st):
            assert vx == pytest.approx(ex, abs=1e-9)
            assert vy == pytest.approx(ey, abs=1e-9)
        assert v_fill == e_fill
        assert v_cut == e_cut

    def test_gates_off_caps_are_the_family_defaults(self, monkeypatch):
        """Off both gates the caps are the emitter's plain defaults —
        graded half-width for fill, family reach for cut — which is what
        the validator's corridor already implied (its fill floor goes
        ``None`` at exactly ``width``, and its march never reaches
        ``reach``).  That is why gates-off is byte-identical."""
        _set_gates(monkeypatch)
        _st, fill, cut, _s, _e, _f, _o = _validator_march(coords=_ring())
        assert set(fill) == {STRIP_HALF}
        assert set(cut) == {REACH}

    def test_a4_clamps_the_fill_below_the_shoulder_overshoot(
            self, monkeypatch):
        """The band lands ``PAVEMENT_HALF`` off the centreline before it
        starts marching, so the un-clamped fill cap overshoots the strip
        by exactly the shoulder width.  With A4 on the cap is the
        REMAINING strip — and the cut is untouched (A4 owns the fill
        only; clamping the cut there would erase zone 3)."""
        _set_gates(monkeypatch, a4=True)
        st, fill, cut, _s, _e, _f, _o = _validator_march(coords=_ring())
        expected = runway_strip_band_width_m(
            STRIP_HALF, PAVEMENT_HALF, STRIP_HALF)
        assert expected == pytest.approx(STRIP_HALF - PAVEMENT_HALF)
        # The SIDE-edge stations are the ones the shoulder pushes out to
        # ``PAVEMENT_HALF`` off the axis; their cap is the strip
        # REMAINING outward of them, 34.5 m where the un-clamped cap was
        # the full 75 m half-width.
        side = [fill[i] for i, (_x, y) in enumerate(st)
                if abs(y) == pytest.approx(PAVEMENT_HALF)]
        assert side
        assert max(side) == pytest.approx(expected)
        assert max(fill) < STRIP_HALF     # no station keeps the full width
        assert set(cut) == {REACH}        # A4 owns the fill only

    def test_ols_owns_the_cut_cap_and_min_composes_the_two_classes(
            self, monkeypatch):
        """S is the MINIMUM over the runway's two apt.dat end classes,
        matching how ``ols._flank_law`` min-composes the surfaces — a
        split would overlap the OLS flank band with this cut band on
        differently-anchored surfaces (a wall)."""
        _set_gates(monkeypatch, ols=True)
        _st, fill, cut, _s, _e, _f, _o = _validator_march(coords=_ring())
        expected = min(ols_lateral_handover_distance_m(
            CODE_NUMBER, cls, PAVEMENT_HALF) for cls in AXIS_CLASSES)
        assert min(cut) == pytest.approx(expected)
        assert max(cut) < REACH
        assert set(fill) == {STRIP_HALF}

    def test_missing_classes_fall_back_to_the_blank_row_default(
            self, monkeypatch):
        """No apt.dat metadata (the ``source_runways=None`` verify path)
        takes ``runway_end_approach_class``'s own conservative blank-row
        answer, exactly as the emitter does — and the emitter agrees."""
        _set_gates(monkeypatch, ols=True)
        coords = _ring()
        _e_st, _e_fill, e_cut, _seam = _emitter_march(
            monkeypatch, coords=coords, axis_classes=None)
        _v_st, _v_fill, v_cut, _s, _e, _f, _o = _validator_march(
            coords=coords, axis_classes=None)
        assert v_cut == e_cut
        expected = ols_lateral_handover_distance_m(
            CODE_NUMBER, "non_precision", PAVEMENT_HALF)
        assert min(v_cut) == pytest.approx(expected)

    def test_no_axis_line_leaves_both_caps_inert(self, monkeypatch):
        """``axis_line`` presence IS the runway-family test in the
        emitter; a taxiway / apron shape (or a runway with no axis) keeps
        the family defaults in every gate state."""
        _set_gates(monkeypatch, a4=True, ols=True)
        _st, fill, cut, _s, _e, _f, _o = _validator_march(
            coords=_ring(), axis_line=None)
        assert set(fill) == {STRIP_HALF}
        assert set(cut) == {REACH}


# ══════════════════════════════════════════════════════════════════════
# MIRROR 2 — the A3 end-skip bench pin (incl. the evaluation-order corner)
# ══════════════════════════════════════════════════════════════════════
def _end_probe_block(length=RUNWAY_LEN, half=PAVEMENT_HALF):
    """A static block that covers the outward probes of the +x END edge
    ONLY (the probe sits ``_RING_PROBE_M`` = 1.5 m out).  Side-edge
    stations all live at x < length and probe in ±y, so they are
    untouched — this isolates the EVALUATION ORDER."""
    from auto_patch.clearance import _RING_PROBE_M
    x0 = length + _RING_PROBE_M / 3.0
    return Polygon([(x0, -half - 50.0), (x0 + 200.0, -half - 50.0),
                    (x0 + 200.0, half + 50.0), (x0, half + 50.0)])


class TestEndPinLockstep:
    def test_pin_flag_vector_matches_the_emitter(self, monkeypatch):
        """Gate ON: the validator's ``at_continuation_seam`` list (seam
        pins OR end pins) must equal the emitter's, station for
        station."""
        _set_gates(monkeypatch, end_pin=True)
        coords = _ring()
        e_st, _ef, _ec, e_seam = _emitter_march(monkeypatch, coords=coords)
        v_st, _vf, _vc, v_seam, _es, _fl, _o = _validator_march(coords=coords)
        assert len(v_st) == len(e_st)
        assert list(map(bool, v_seam)) == list(map(bool, e_seam))
        assert any(v_seam), "the pin must actually fire on this fixture"

    def test_gate_off_pins_nothing_in_either_reader(self, monkeypatch):
        _set_gates(monkeypatch, end_pin=False)
        coords = _ring()
        _e_st, _ef, _ec, e_seam = _emitter_march(monkeypatch, coords=coords)
        _v_st, _vf, _vc, v_seam, _es, _fl, _o = _validator_march(coords=coords)
        assert not any(e_seam)
        assert not any(v_seam)

    def test_end_skip_is_decided_before_the_static_probe(self,
                                                         monkeypatch):
        """THE ORDERING CORNER.  ``_station_reference_ex`` returns
        ``"end"`` BEFORE it ever builds the outward probe, so an end-edge
        station whose probe is static-covered STILL reads ``"end"`` — and
        therefore still pins its usable neighbour.  A validator that
        tested the probe first (or that derived end-skip from "skipped
        and not covered") would drop those stations out of the end run
        and pin nothing there."""
        _set_gates(monkeypatch, end_pin=True)
        coords = _ring()
        block = _end_probe_block()
        e_st, _ef, _ec, e_seam = _emitter_march(
            monkeypatch, coords=coords, static_poly=block)
        v_st, _vf, _vc, v_seam, v_end, v_flag, v_outn = _validator_march(
            coords=coords, static_poly=block)
        assert len(v_st) == len(e_st)
        assert list(map(bool, v_seam)) == list(map(bool, e_seam))
        # The +x END edge's stations: outward normal along the axis, at
        # x == L.  The fixture must genuinely cover their probes — that
        # is what makes this an ORDERING test and not a dot-test test.
        from auto_patch.clearance import _RING_PROBE_M
        end_idx = [i for i in _end_edge_indices(v_outn)
                   if v_st[i][0] == pytest.approx(RUNWAY_LEN)]
        assert end_idx, "fixture must contain the +x end edge"
        assert all(
            block.covers(Point(v_st[i][0] + v_outn[i][0] * _RING_PROBE_M,
                               v_st[i][1] + v_outn[i][1] * _RING_PROBE_M))
            for i in end_idx), "fixture must cover the end probes"
        # Probe-covered, and STILL end-skipped — the load-bearing order.
        assert all(v_end[i] for i in end_idx)
        assert not any(v_flag[i] for i in end_idx)
        # …and the pin fires on the usable neighbour of that run.
        assert any(v_seam), "an end run must still pin its neighbour"

    def test_static_cover_alone_never_reads_as_an_end_skip(self,
                                                           monkeypatch):
        """The converse guard: a SIDE-edge station whose probe is covered
        is skipped for the ``"static"`` reason, which must NOT enter the
        end-skip vector (or every band clipped by abutting pavement would
        pin its neighbours)."""
        _set_gates(monkeypatch, end_pin=True)
        coords = _ring()
        # Cover the outward probes of the -y side edge over its middle.
        block = Polygon([(1000.0, -PAVEMENT_HALF - 60.0),
                         (2000.0, -PAVEMENT_HALF - 60.0),
                         (2000.0, -PAVEMENT_HALF - 0.5),
                         (1000.0, -PAVEMENT_HALF - 0.5)])
        v_st, _vf, _vc, v_seam, v_end, v_flag, v_outn = _validator_march(
            coords=coords, static_poly=block)
        covered = [i for i, (x, y) in enumerate(v_st)
                   if y == pytest.approx(-PAVEMENT_HALF)
                   and 1000.0 < x < 2000.0]
        assert covered, "fixture must cover some side-edge stations"
        assert not any(v_flag[i] for i in covered)     # skipped…
        assert not any(v_end[i] for i in covered)      # …but not as END
        _e_st, _ef, _ec, e_seam = _emitter_march(
            monkeypatch, coords=coords, static_poly=block)
        assert list(map(bool, v_seam)) == list(map(bool, e_seam))


# ══════════════════════════════════════════════════════════════════════
# MIRROR 3 — the B1 pocket-collar exemption
# ══════════════════════════════════════════════════════════════════════
_COLLAR_LEN = 1500.0                     # ICAO code 3 → 75 m graded strip
_COLLAR_HALF = 22.5
_COLLAR_OFFSET_M = 2.5                   # ring inboard of the first sample


def _collar_layout():
    """A flat code-3 runway rect over terrain that sits 10 m below the
    pavement edge across the whole graded band — the un-filled-drop case
    of ``test_adjacent_ground_validator`` — so the reader has real
    ``should_fill`` findings to exempt."""
    rect = Polygon([
        (0.0, -_COLLAR_HALF), (_COLLAR_LEN, -_COLLAR_HALF),
        (_COLLAR_LEN, _COLLAR_HALF), (0.0, _COLLAR_HALF)])
    layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
    layout.shapes.append(BuiltShape(
        polygon=rect, role="runway", ref="09-27", altitude=EDGE_ALT))
    return layout


def _collar_runway():
    lon_b = math.degrees(_COLLAR_LEN / R_EARTH)
    return Runway(desig_a="09", desig_b="27", lat_a=0.0, lon_a=0.0,
                  lat_b=0.0, lon_b=lon_b, width_m=45.0, surface_code=1,
                  displaced_a_m=0.0, displaced_b_m=0.0,
                  markings_a=0, approach_lights_a=0,
                  markings_b=0, approach_lights_b=0)


def _publish_collar(layout):
    """Publish ONE collar ring the way ``gap_fill._emit_pocket_collar_rings``
    does: a closed loop on ``layout.gap_interior_rings`` in LAT/LON (first
    point repeated), plus the pocket record on ``layout.pocket_collars``
    in LOCAL METRES.  The loop hugs the pavement at
    ``_COLLAR_OFFSET_M``, inboard of the march's first 5 m sample, so
    EVERY outward transect crosses it."""
    off = _COLLAR_HALF + _COLLAR_OFFSET_M
    pts = [(-_COLLAR_OFFSET_M, -off), (_COLLAR_LEN + _COLLAR_OFFSET_M, -off),
           (_COLLAR_LEN + _COLLAR_OFFSET_M, off), (-_COLLAR_OFFSET_M, off)]
    pts = pts + [pts[0]]
    layout.gap_interior_rings = [
        ([layout.m_to_ll(x, y) for x, y in pts],
         [EDGE_ALT - 1.0] * len(pts))]
    pocket = Polygon([(-400.0, -400.0), (_COLLAR_LEN + 400.0, -400.0),
                      (_COLLAR_LEN + 400.0, 400.0), (-400.0, 400.0)])
    layout.pocket_collars = [{
        "pocket": pocket, "core": None, "ring2": [], "chains": 1,
        "nodes": len(pts)}]
    return layout


def _patch_dem(monkeypatch):
    """10 m below the pavement edge inside the graded band, flat beyond —
    the same scenario ``test_adjacent_ground_validator`` uses for its
    flagged ``should_fill`` case."""
    def _fake(dem, tile_lat, tile_lon, lat, lon):
        d = abs(math.radians(lat) * R_EARTH) - _COLLAR_HALF
        return EDGE_ALT - 10.0 if d < 60.0 else EDGE_ALT
    monkeypatch.setattr(ELEV, "_sample_dem", _fake)


def _collar_findings(layout):
    return V.check_adjacent_ground(
        layout, dem=object(), tile_lat=0, tile_lon=0,
        source_runways=[_collar_runway()])


class TestPocketCollarExemption:
    def test_collared_columns_are_exempt(self, monkeypatch):
        """Collars emitted: every flagged transect crosses a collar ring,
        so the collar is carrying the law there and the band has nothing
        to answer for — no findings."""
        _set_gates(monkeypatch, collar=True)
        _patch_dem(monkeypatch)
        layout = _publish_collar(_collar_layout())
        assert V._pocket_collar_ring_lines(layout), \
            "the fixture must publish a collar ring"
        assert _collar_findings(layout) == []

    def test_findings_return_when_the_collars_are_suppressed(
            self, monkeypatch):
        """Force-suppress the emitted rings (same layout, same DEM, same
        gate): the drop is nobody's but the band's again, so the findings
        come back.

        Suppression is the emitter's OWN economy-skip state — no ring
        ways AND ``chains == 0`` on the record — so MIRROR 4 publishes no
        stand-down zone either and the frontage stays the band's to
        grade.  (A record with ``chains > 0`` but no ways cannot arise:
        ``_emit_pocket_collar_rings`` appends one way per chain.)"""
        _set_gates(monkeypatch, collar=True)
        _patch_dem(monkeypatch)
        layout = _publish_collar(_collar_layout())
        layout.gap_interior_rings = []
        layout.pocket_collars[0]["chains"] = 0
        assert V._pocket_collar_ring_lines(layout) == []
        assert V._collared_pocket_zone_prep(layout) is None
        findings = _collar_findings(layout)
        assert findings
        assert {f[0] for f in findings} == {"should_fill"}

    def test_gate_off_ignores_published_collars(self, monkeypatch):
        """The exemption is gated: with ``POCKET_COLLAR_RINGS_ENABLED``
        off the reader must behave exactly as it did before the mirror,
        even on a layout that carries collar records."""
        _set_gates(monkeypatch, collar=False)
        _patch_dem(monkeypatch)
        layout = _publish_collar(_collar_layout())
        assert V._pocket_collar_ring_lines(layout) == []
        assert _collar_findings(layout)

    def test_treated_gap_rings_outside_a_pocket_are_not_collars(
            self, monkeypatch):
        """``gap_interior_rings`` also holds the interior rings of gaps
        the drainage-spine emitter DID treat; only the loops inside a
        published pocket are collar rings, so a treated-gap ring
        elsewhere must not exempt anything."""
        _set_gates(monkeypatch, collar=True)
        _patch_dem(monkeypatch)
        layout = _publish_collar(_collar_layout())
        # Move the pocket far away: the ring is now a plain interior ring.
        layout.pocket_collars[0]["pocket"] = Polygon(
            [(9000.0, 9000.0), (9500.0, 9000.0),
             (9500.0, 9500.0), (9000.0, 9500.0)])
        assert V._pocket_collar_ring_lines(layout) == []
        assert _collar_findings(layout)

    def test_ring_geometry_is_read_as_latlon(self, monkeypatch):
        """The published ring is in LAT/LON — reading it as metres would
        collapse the loop to a sub-metre blob at the anchor and exempt
        nothing.  Pin the converted geometry against the metres it came
        from."""
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        lines = V._pocket_collar_ring_lines(layout)
        assert len(lines) == 1
        minx, miny, maxx, maxy = lines[0].bounds
        assert maxx - minx == pytest.approx(
            _COLLAR_LEN + 2 * _COLLAR_OFFSET_M, abs=1.0)
        assert maxy - miny == pytest.approx(
            2 * (_COLLAR_HALF + _COLLAR_OFFSET_M), abs=1.0)


# ══════════════════════════════════════════════════════════════════════
# MIRROR 4 — the B1 collared-pocket STATION STAND-DOWN
#
# A width-skipped pocket whose collar rings emitted is the COLLAR's
# ground: the emitter drops every station whose seed or outward probe
# falls in it, so the validator must drop the same ones or it flags the
# stood-down frontage as should_fill/should_cut.  (MIRROR 3, the
# transect exemption, stays — with the bands standing down it now
# describes reality rather than papering over the overlap.)
# ══════════════════════════════════════════════════════════════════════
def _collar_ring_coords():
    """The collar fixture's pavement ring, CCW and closed."""
    return [(0.0, -_COLLAR_HALF), (_COLLAR_LEN, -_COLLAR_HALF),
            (_COLLAR_LEN, _COLLAR_HALF), (0.0, _COLLAR_HALF),
            (0.0, -_COLLAR_HALF)]


def _far_static():
    return Polygon([(-9000, -9000), (-8000, -9000),
                    (-8000, -8000), (-9000, -8000)])


def _emitter_collar_march(coords, zone_prep):
    """The emitter's march over the collar fixture's ring (no runway
    axis, so nothing is END-skipped and the zone is the only stand-down
    in play)."""
    ceil_off, floor_depth = _closures(STRIP_HALF)
    return AG._derive_shape_stations_and_bands(
        coords, True, [EDGE_ALT] * len(coords), None, STRIP_HALF, REACH,
        TRIGGER, floor_depth, ceil_off, STEP, prep(_far_static()), set(),
        _flat_dem, collar_zone_prep=zone_prep)


def _validator_collar_march(coords, zone_prep):
    static_poly = _far_static()

    def _probe_covered(px, py):
        return static_poly.covers(Point(px, py))

    return V._adjacent_ground_stations(
        coords, True, [EDGE_ALT] * len(coords), None, STEP, set(),
        _probe_covered, collar_zone_prep=zone_prep)


class TestCollaredPocketStandDownLockstep:
    def test_both_readers_stand_the_collared_frontage_down(self,
                                                           monkeypatch):
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        zone = V._collared_pocket_zone_prep(layout)
        assert zone is not None
        coords = _collar_ring_coords()
        _fb, _cb, _st, st_alts, _outs = _emitter_collar_march(coords, zone)
        (_x, _y, _outn, _ref, st_flag, _seam,
         _end) = _validator_collar_march(coords, zone)
        assert st_alts and not any(a is not None for a in st_alts)
        assert st_flag and not any(st_flag)

    def test_without_the_zone_both_readers_govern_the_frontage(self,
                                                               monkeypatch):
        _set_gates(monkeypatch, collar=True)
        coords = _collar_ring_coords()
        _fb, _cb, _st, st_alts, _outs = _emitter_collar_march(coords, None)
        (_x, _y, _outn, _ref, st_flag, _seam,
         _end) = _validator_collar_march(coords, None)
        assert st_alts and all(a is not None for a in st_alts)
        assert st_flag and all(st_flag)

    def test_gate_off_publishes_no_zone_to_the_validator(self,
                                                         monkeypatch):
        """Same layout, gate OFF: the validator's mirror is inert, so its
        march is byte-identical to the pre-mirror one."""
        _set_gates(monkeypatch, collar=False)
        layout = _publish_collar(_collar_layout())
        assert V._collared_pocket_zone_prep(layout) is None

    def test_economy_skipped_collar_publishes_no_zone(self, monkeypatch):
        """A record with ZERO emitted chains keeps its bands — the zone
        is keyed on emission, not on the record's existence."""
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        layout.pocket_collars[0]["chains"] = 0
        assert V._collared_pocket_zone_prep(layout) is None


# ══════════════════════════════════════════════════════════════════════
# NEW INVARIANT — collar ring INSIDE an adjacent-ground band polygon
#
# The check that would have caught the SPJC crash: collar ring 1 sitting
# 3 m out while the bands covered the first ~10 m.  Two governing
# surfaces over one patch of terrain.
# ══════════════════════════════════════════════════════════════════════
def _band_shape(y0, y1, x0=0.0, x1=_COLLAR_LEN):
    """An emitted adjacent-ground band polygon (the emitter's own ref)."""
    return BuiltShape(
        polygon=Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]),
        role="graded_strip", ref="adjacent_ground", altitude=EDGE_ALT)


class TestCollarRingBandOverlapInvariant:
    def test_fires_when_a_band_swallows_a_collar_ring(self, monkeypatch):
        """The SPJC arrangement: the band marches out past the collar's
        ring, so the ring runs through the band's interior."""
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        layout.shapes.append(_band_shape(_COLLAR_HALF, _COLLAR_HALF + 10.0))
        findings = V.check_collar_ring_band_overlap(layout)
        assert findings
        length, ident, loc = findings[0]
        assert ident == "adjacent_ground"
        assert length > 0.9 * _COLLAR_LEN
        assert "," in loc

    def test_silent_when_the_band_stands_down(self, monkeypatch):
        """The stand-down state: the band is clipped by the pocket, so no
        band polygon reaches the collar's ground at all."""
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        # 500 m out, well outside the published pocket (|y| <= 400).
        layout.shapes.append(_band_shape(500.0, 520.0))
        assert V.check_collar_ring_band_overlap(layout) == []

    def test_silent_without_bands_or_collars(self, monkeypatch):
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        assert V.check_collar_ring_band_overlap(layout) == []
        _set_gates(monkeypatch, collar=False)
        layout.shapes.append(_band_shape(_COLLAR_HALF, _COLLAR_HALF + 10.0))
        assert V.check_collar_ring_band_overlap(layout) == [], \
            "gated: the collar lines are not even materialized"

    def test_a_band_abutting_the_ring_is_not_a_finding(self, monkeypatch):
        """The lawful weld: a band whose clipped edge COINCIDES with the
        ring shares its coordinates (weld ruling 2026-07-09 — no standoff
        groove).  Sharing a boundary is not a double-cover."""
        _set_gates(monkeypatch, collar=True)
        layout = _publish_collar(_collar_layout())
        off = _COLLAR_HALF + _COLLAR_OFFSET_M
        layout.shapes.append(_band_shape(off, off + 10.0))
        assert V.check_collar_ring_band_overlap(layout) == []


class TestCollarZoneBoundingBoxGuard:
    """The zone test carries a per-PART bounding-box pre-filter in BOTH
    marches (it runs over every airside station of the airport, ~35,000 at
    SPJC).  Per part, not per union: two pockets at opposite ends of the
    field give a union box covering the whole airport, which prunes
    nothing.  These pin that the guard changes no verdict."""

    def _zone_of(self, *pockets):
        from shapely.ops import unary_union
        return prep(unary_union(list(pockets)))

    def _near(self):
        return Polygon([(-400.0, -400.0), (_COLLAR_LEN + 400.0, -400.0),
                        (_COLLAR_LEN + 400.0, 400.0), (-400.0, 400.0)])

    def _far(self):
        return Polygon([(90000.0, 90000.0), (91000.0, 90000.0),
                        (91000.0, 91000.0), (90000.0, 91000.0)])

    def test_multipart_zone_stands_down_only_the_part_it_covers(self):
        zone = self._zone_of(self._near(), self._far())
        assert zone.context.geom_type == "MultiPolygon"
        coords = _collar_ring_coords()
        _fb, _cb, _st, st_alts, _o = _emitter_collar_march(coords, zone)
        (_x, _y, _on, _r, st_flag, _s,
         _e) = _validator_collar_march(coords, zone)
        assert st_alts and not any(a is not None for a in st_alts)
        assert st_flag and not any(st_flag)

    def test_a_zone_entirely_elsewhere_stands_nothing_down(self):
        zone = self._zone_of(self._far())
        coords = _collar_ring_coords()
        _fb, _cb, _st, st_alts, _o = _emitter_collar_march(coords, zone)
        (_x, _y, _on, _r, st_flag, _s,
         _e) = _validator_collar_march(coords, zone)
        assert st_alts and all(a is not None for a in st_alts)
        assert st_flag and all(st_flag)
