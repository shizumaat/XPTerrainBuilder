"""EAT RECOGNITION SCOPING — routed wrap, vacuous bound, cut-only pin.

Owner ruling 2026-08-25c (docs/RULINGS.md; spec
``docs/specs/eat-recognition-scoping-spec.md``): **an end-around taxiway
is a ROUTED WRAP, bounded by the surface's own geometry, and its pin only
CUTS.**  The anchor-rect MECHANISM of 2026-07-27 — the corridor rect, the
``end_elev + eat_pavement_ceiling(D_mid)`` value, the region table, the
contradiction guard — is untouched; what these twins pin is WHICH
pavement is recognised as an end-around taxiway in the first place.

Measured basis (LEMD +40-004, 2026-08-25): 149 pins over 10 crossing
segments at 1.0-4.6 km beyond the 14R / 36R ends, owning shapes plain
apron and junction rings, the 36R pins 59-66 m ABOVE the adjacent
DEM-seeded pavement.  All 12 contradictory final-band anchor pairs were
EAT-pin vs EAT-pin, the phase-A harmonic split an empty polytope at
2,291 nodes, and the build died on the final-band inversion assert.  The
owner rules LEMD HAS NO EATs.  Real ones cross at 439-482 m (KCLT).

The three clauses, one twin apiece plus the gate:

  (a) a wrap — crossing centreline, regulation below reference — pins
      EXACTLY as it did before this round;
  (b) an apron ring in the corridor with no through-centreline: no rect;
  (c) a crossing whose route binds on ONE side only (a dead-end spur):
      no rect — priced at the guard site on the law graph;
  (d) a wrap beyond the FAR BOUND: no rect.  Two rules set that bound
      and the stricter governs — ``D_clear = setback + tail/slope``
      (2026-08-25c) and the 600 m recognition cap
      ``EAT_MAX_CROSSING_DIST_M`` (2026-08-25d);
  (e) a wrap whose regulation sits ABOVE the reference everywhere: the
      rect is refused whole and says so out loud;
  (f) gate OFF: the 2026-07-27 recognition exactly.

AMENDED by owner ruling 2026-08-25d.  25c's three clauses all PASSED
LEMD's 14R wrap at D = 1066 m — a taxi centreline genuinely crosses the
extended centreline there, inside the 1280 m vacuous bound, and the
regulation value genuinely cuts — so it was the one rect left standing
of the original ten.  The owner rules that is not an end-around taxiway
but the airport's own taxi network crossing a projected line: **nothing
is recognised beyond 600 m**, the measured band of real EATs being
439-482 m.

Hermetic: hand-built layouts, no DEM files, no X-Plane, no network.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon

import auto_patch.config as cfg
from auto_patch.apt_dat_reader import TaxiCenterline
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.elevation_per_surface.route_profile import solve as SV
from auto_patch.grade_law import (eat_ceiling_clear_distance,
                                  eat_pavement_ceiling)
from auto_patch.layout import (
    BuiltShape, PavementLayout, ROLE_APRON, ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
)

# The same frame ``tests/test_eat_ceiling.py`` uses: a 45 m (code E)
# runway lying along −x with its DER at the origin, outward +x.
_RWY = Polygon([(-1000.0, -22.0), (0.0, -22.0), (0.0, 22.0),
                (-1000.0, 22.0)])
_ANCHOR_XY = (0.0, -22.0)
_END_ELEV = 100.0
_HALF = 22.5


def _rect(x0, x1, y0=-10.0, y1=10.0):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _end_spec():
    return {
        "p0": (0.0, 0.0),
        "outward": (1.0, 0.0),
        "code_letter": "E",
        "code_number": 4,
        "slope": float(cfg.EAT_FAA_DEPARTURE_SLOPE),
        "setback_m": float(cfg.EAT_FAA_SETBACK_M),
        "tail_height_m": float(cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"]),
        "anchor_xy": _ANCHOR_XY,
        "half_width_m": _HALF,
        "end_id": "09",
    }


#: FAA 40:1, no setback, code-E tail ⇒ the surface has cleared the tail
#: 804 m past the DER.  Under the 2026-08-25d recognition cap (600 m)
#: THAT is the stricter of the two far bounds at this end, so 600 m is
#: what actually governs here.  KCLT's real crossing is at 439-482 m,
#: comfortably inside both.
_D_CLEAR = 804.0
_D_CAP = 600.0
#: The bound that actually fires at ``_end_spec()``.
_D_FAR = min(_D_CLEAR, _D_CAP)


def _layout(*taxi_polys, crossings=(), role=ROLE_PRIMARY_PARALLEL):
    """Runway + taxi shapes + the taxi ROUTES that cross the extended
    centreline at the given stations (``crossings`` in metres of ``s``).

    ``crossings`` is deliberately independent of the taxi polygons: the
    whole point of clause 1 is that pavement in the corridor and a taxi
    route through it are DIFFERENT facts, and the twins below need to
    vary them one at a time.
    """
    layout = PavementLayout(icao="KTST", anchor=(35.231, -80.955))
    layout.canonical_points = CanonicalPointRegistry()
    layout.shapes = [BuiltShape(role=ROLE_RUNWAY, polygon=_RWY,
                                altitude_high=_END_ELEV,
                                altitude_low=_END_ELEV)]
    layout.shapes += [BuiltShape(role=role, polygon=p) for p in taxi_polys]
    layout.eat_ceiling_presolve = [_end_spec()]
    layout.apt_taxi_centerlines = [
        TaxiCenterline(line=LineString([(float(s), -120.0),
                                        (float(s), 120.0)]))
        for s in crossings]
    return layout


def _ring(poly):
    return list(poly.exterior.coords)[:-1]


def _build(layout, *, reference=None, v2=True, monkeypatch=None):
    """Run the pin builder on a hand-seeded node space.

    The arrays reproduce the state ``_seed_elevations`` is in when it
    calls the builder: the runway ring HARD at its profile value (so the
    end anchor reads), every taxi vertex SOFT but carrying its
    unconstrained level — which is what ``have_initial`` means and what
    clause 3 prices against.  Passing ``reference=None`` models a node
    with no reference at all.
    """
    if monkeypatch is not None:
        monkeypatch.setattr(cfg, "EAT_SCOPING_V2_ENABLED", bool(v2))
    nodes, b2i = SP._build_node_list(layout)
    cps = layout.canonical_points
    n = len(nodes)
    elev = [0.0] * n
    is_hard = [False] * n
    have = [False] * n
    for (x, y) in _ring(_RWY):
        i = b2i[cps.get_or_add(float(x), float(y))]
        elev[i] = _END_ELEV
        is_hard[i] = True
        have[i] = True
    if reference is not None:
        for s in layout.shapes:
            if s.role == ROLE_RUNWAY:
                continue
            for (x, y) in _ring(s.polygon):
                i = b2i[cps.get_or_add(float(x), float(y))]
                if not is_hard[i]:
                    elev[i] = float(reference)
                    have[i] = True
    pins, counts, pin_rect, pin_side = SP._build_eat_anchor_rect_pins(
        layout, b2i, elev, is_hard, have_initial=have)
    return pins, counts, pin_rect, pin_side, b2i


def _taxi_idx(layout, b2i, poly):
    cps = layout.canonical_points
    return [b2i[cps.get_or_add(float(x), float(y))] for (x, y) in _ring(poly)]


# ── the far bound is the LAW's own root, not a new constant ─────────
class TestTheVacuousBoundIsTheLawsOwnGeometry:
    def test_d_clear_is_where_the_ceiling_reaches_zero(self):
        """``D_clear`` is defined as the root of the ceiling function —
        so evaluating the ceiling there must give exactly 0."""
        for (slope, setback, tail) in ((0.025, 0.0, 20.1),
                                       (0.02, 60.0, 24.4),
                                       (0.02, 60.0, 13.7)):
            d = eat_ceiling_clear_distance(slope, setback, tail)
            assert eat_pavement_ceiling(d, slope, setback, tail) == \
                pytest.approx(0.0, abs=1e-9)

    def test_the_two_regions_worked_values(self):
        """FAA code E 804 m; EASA code F 1280 m — LEMD's own numbers,
        against which its false pins sat at 1.0-4.6 km."""
        assert eat_ceiling_clear_distance(
            cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"]) == pytest.approx(804.0)
        assert eat_ceiling_clear_distance(
            cfg.EAT_EASA_TAKEOFF_CLIMB_SLOPE, cfg.EAT_EASA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["F"]) == pytest.approx(1280.0)

    def test_a_missing_surface_bounds_nothing(self):
        """Slope 0 ⇒ no surface ⇒ no far bound.  A missing bound is
        honest; it must never read as "refuse everything"."""
        assert eat_ceiling_clear_distance(0.0, 0.0, 20.1) == float("inf")

    def test_the_far_bound_helper_reads_the_ends_own_constants(self):
        """At a code-E FAA end the RECOGNITION CAP (600 m) is stricter
        than ``D_clear`` (804 m), so the cap governs — and the helper
        says which rule set the number it returned."""
        bound, rule = SP.eat_scoping_far_bound(_end_spec())
        assert bound == pytest.approx(_D_CAP)
        assert rule == "EAT_MAX_CROSSING_DIST_M"

    def test_the_vacuous_bound_still_bites_where_it_is_stricter(self):
        """The two far bounds compose as a MINIMUM.  A code-A tail under
        FAA 40:1 clears at 6.1/0.025 = 244 m — well inside the 600 m
        cap — so there the regulation's own geometry governs and the
        helper names ``D_clear``."""
        spec = dict(_end_spec(), code_letter="A",
                    tail_height_m=cfg.TAIL_HEIGHT_BY_CODE_LETTER["A"])
        bound, rule = SP.eat_scoping_far_bound(spec)
        assert bound == pytest.approx(244.0)
        assert rule == "D_clear"
        assert bound < _D_CAP

    def test_the_bound_is_not_a_tuning_constant(self):
        """``D_clear`` itself is still computed from slope / setback /
        tail — the 2026-08-25d cap is a SEPARATE, explicitly named
        recognition constant, not a knob bolted onto the law function."""
        import re
        from pathlib import Path
        src = Path(cfg.__file__).read_text(encoding="utf-8")
        # No ``D_clear`` knob: the vacuous bound has no config value.
        assert not re.search(r"^EAT_\w*(FAR|CLEAR)\w*\s*=", src, re.M)
        # The cap IS a constant, and it lives in config with the other
        # rule values — never hard-coded at the call site.
        assert re.search(r"^EAT_MAX_CROSSING_DIST_M\s*=", src, re.M)
        # …and the helper READS it rather than restating the number.
        import inspect
        body = inspect.getsource(SP.eat_scoping_far_bound)
        body = body.split('"""')[2]          # code only, not the prose
        assert "EAT_MAX_CROSSING_DIST_M" in body
        assert "600" not in body, (
            "the cap's VALUE must come from config, not the helper")


# ── the crossing-station reader (clause 1, geometry half) ───────────
class TestTheWrapCrossingReader:
    def test_a_crossing_route_reports_its_station(self):
        layout = _layout(_rect(440.0, 460.0), crossings=(450.0,))
        assert SP.eat_wrap_crossing_stations(layout, _end_spec()) == \
            [pytest.approx(450.0)]

    def test_a_route_that_never_crosses_reports_nothing(self):
        """A taxiway running PARALLEL to the extended centreline, 40 m
        off it, is not a wrap however long it is."""
        layout = _layout(_rect(440.0, 460.0))
        layout.apt_taxi_centerlines = [TaxiCenterline(
            line=LineString([(300.0, 40.0), (900.0, 40.0)]))]
        assert SP.eat_wrap_crossing_stations(layout, _end_spec()) == []

    def test_a_service_road_is_never_a_wrap(self):
        """Row-1206 ground-vehicle routes carry no aircraft tail, and
        the airside route graph withholds them for the same reason."""
        layout = _layout(_rect(440.0, 460.0))
        layout.apt_taxi_centerlines = [TaxiCenterline(
            line=LineString([(450.0, -120.0), (450.0, 120.0)]),
            is_service=True)]
        assert SP.eat_wrap_crossing_stations(layout, _end_spec()) == []

    def test_stations_are_interpolated_not_snapped_to_vertices(self):
        """An oblique crossing's station is where ``q`` reaches 0, not
        the nearest vertex — the rect window is only ±75 m wide."""
        layout = _layout(_rect(440.0, 460.0))
        layout.apt_taxi_centerlines = [TaxiCenterline(
            line=LineString([(400.0, -50.0), (500.0, 50.0)]))]
        got = SP.eat_wrap_crossing_stations(layout, _end_spec())
        assert got == [pytest.approx(450.0)]


# ── (a) THE WRAP PINS EXACTLY AS IT DID BEFORE ─────────────────────
class TestAWrapIsPinnedExactlyAsToday:
    """(a) Crossing centreline, both sides connected, regulation below
    reference at D = 450 → the 2026-07-27 mechanism, unchanged."""

    def test_the_rect_pins_at_the_regulation_value(self, monkeypatch):
        rect = _rect(440.0, 460.0)
        layout = _layout(rect, crossings=(450.0,))
        pins, counts, pin_rect, _side, b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        want = _END_ELEV + eat_pavement_ceiling(
            450.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        assert set(pins) == set(_taxi_idx(layout, b2i, rect))
        for v in pins.values():
            assert v == pytest.approx(want)
        assert counts[0] == 1                       # one crossing segment
        assert len(set(pin_rect.values())) == 1

    def test_recognition_does_not_move_the_value(self, monkeypatch):
        """The gate changes WHICH rects are recognised, never what a
        recognised one is worth: same rect, both gate states, same
        numbers."""
        rect = _rect(440.0, 460.0)
        on = _build(_layout(rect, crossings=(450.0,)),
                    reference=_END_ELEV, v2=True, monkeypatch=monkeypatch)[0]
        off = _build(_layout(rect, crossings=(450.0,)),
                     reference=_END_ELEV, v2=False,
                     monkeypatch=monkeypatch)[0]
        assert on == off

    def test_the_side_of_each_pin_is_published(self, monkeypatch):
        """The wrap's connectivity half is priced at the guard site, on
        the law graph — so the builder publishes the side it already
        knew rather than making that site re-derive it."""
        rect = _rect(440.0, 460.0, -10.0, 10.0)
        layout = _layout(rect, crossings=(450.0,))
        pins, _c, _r, side, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert set(side) == set(pins)
        assert set(side.values()) == {1, -1}        # the rect straddles


# ── (b) PAVEMENT IN THE CORRIDOR IS NOT A WRAP ─────────────────────
class TestAnApronRingWithNoThroughCentrelineIsNotAnEat:
    """(b) THE LEMD CLASS: a plain apron ring lying under the projected
    centreline, no taxi route through it → no rect at all."""

    def test_no_through_centreline_no_rect(self, monkeypatch):
        layout = _layout(_rect(440.0, 460.0), role=ROLE_APRON)
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert pins == {}
        assert counts[0] == 0

    def test_a_crossing_elsewhere_does_not_licence_this_rect(
            self, monkeypatch):
        """The route must cross AT the rect.  A genuine wrap 600 m
        further out says nothing about an apron at 450 m — the window is
        the rect's own extent widened by the segmentation gap."""
        layout = _layout(_rect(440.0, 460.0), crossings=(700.0,),
                         role=ROLE_APRON)
        pins, _c, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert pins == {}

    def test_a_crossing_inside_the_segmentation_gap_does_licence_it(
            self, monkeypatch):
        """A decimated ring can carry vertices well to either side of
        the true crossing, so the window is ±``EAT_RECT_SEGMENT_GAP_M``
        — the same constant that decides "one crossing" along ``s``.
        No new number is born to hold this tolerance."""
        near = 460.0 + cfg.EAT_RECT_SEGMENT_GAP_M - 1.0
        layout = _layout(_rect(440.0, 460.0), crossings=(near,))
        pins, _c, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert pins != {}


# ── (c) A WRAP ROUTES ON BOTH SIDES ────────────────────────────────
#: A runway anchor at 0 and a taxi chain 0-1-2 reaching the rect's node
#: 3 on ONE side; node 4 (the far side) hangs off nothing.  Exactly what
#: ``u_spine_adj_airside`` looks like for a dead-end spur.
_ONE_SIDED = {0: [(1, 1.0)], 1: [(0, 1.0), (2, 1.0)],
              2: [(1, 1.0), (3, 1.0)], 3: [(2, 1.0)], 4: []}
_BOTH_SIDES = {0: [(1, 1.0)], 1: [(0, 1.0), (2, 1.0)],
               2: [(1, 1.0), (3, 1.0), (4, 1.0)],
               3: [(2, 1.0)], 4: [(2, 1.0)]}
_RUNWAY_ANCHOR = {0: 12.0}
_PINS = {3: 91.15, 4: 91.15}
_RECTS = {3: 1, 4: 1}
_SIDES = {3: -1, 4: 1}


class TestTheWrapMustRouteOnBothSides:
    """(c) A crossing connected on one side only is a dead-end spur
    under the corridor, not an end-around taxiway."""

    def test_one_sided_connectivity_refuses_the_whole_rect(self):
        bound = SV.eat_pin_taxi_bound(_PINS, _ONE_SIDED, _RUNWAY_ANCHOR)
        assert bound == {3}                     # the far side never binds
        out = SV.eat_unroutable_rect_refusals(_PINS, _RECTS, bound,
                                              side_of=_SIDES)
        assert set(out) == {3, 4}, "the refusal is WHOLE-RECT"

    def test_both_sided_connectivity_keeps_the_rect(self):
        bound = SV.eat_pin_taxi_bound(_PINS, _BOTH_SIDES, _RUNWAY_ANCHOR)
        assert bound == {3, 4}
        assert SV.eat_unroutable_rect_refusals(
            _PINS, _RECTS, bound, side_of=_SIDES) == {}

    def test_the_strengthening_subsumes_the_standing_guard(self):
        """Both-sides implies some-side: nothing the 2026-08-12
        single-side law refused may survive the new one."""
        for adj in (_ONE_SIDED, _BOTH_SIDES, {}):
            bound = SV.eat_pin_taxi_bound(_PINS, adj, _RUNWAY_ANCHOR)
            old = SV.eat_unroutable_rect_refusals(_PINS, _RECTS, bound)
            new = SV.eat_unroutable_rect_refusals(_PINS, _RECTS, bound,
                                                  side_of=_SIDES)
            assert set(old) <= set(new)

    def test_a_one_sided_pin_population_keeps_the_one_sided_reading(self):
        """THE MISSING WITNESS IS HONEST.  A rect all of whose pinned
        vertices landed on one side cannot speak for the far side — the
        pinned population is a decimated ring, not a survey — so it
        keeps the reading it has always had.  Refusing on an absent
        witness is the unpriceable-pin defect (2026-08-21) in reverse."""
        one_side = {3: -1, 4: -1}
        bound = SV.eat_pin_taxi_bound(_PINS, _ONE_SIDED, _RUNWAY_ANCHOR)
        assert SV.eat_unroutable_rect_refusals(_PINS, _RECTS, bound,
                                               side_of=one_side) == {}

    def test_no_side_map_is_exactly_the_old_law(self):
        """Gate OFF publishes no side map, and the call must then be
        bit-for-bit the standing single-side law."""
        for adj in (_ONE_SIDED, _BOTH_SIDES):
            bound = SV.eat_pin_taxi_bound(_PINS, adj, _RUNWAY_ANCHOR)
            assert SV.eat_unroutable_rect_refusals(
                _PINS, _RECTS, bound, side_of=None) == \
                SV.eat_unroutable_rect_refusals(_PINS, _RECTS, bound)


# ── (d) NOTHING IS RECOGNISED BEYOND D_clear ───────────────────────
class TestNothingIsRecognisedBeyondTheVacuousBound:
    """(d) Past ``D_clear`` the regulation surface has cleared the
    tallest tail, so it binds nothing and recognition there is vacuous
    by the regulation's own geometry."""

    def test_a_wrap_beyond_d_clear_builds_no_rect(self, monkeypatch):
        far = _rect(_D_FAR + 60.0, _D_FAR + 80.0)
        layout = _layout(far, crossings=(_D_FAR + 70.0,))
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert pins == {}
        assert counts[0] == 0

    def test_a_wrap_just_inside_d_clear_still_builds(self, monkeypatch):
        """The bound is a bound, not a margin: 30 m inside it the rect
        still stands (and its value is still a cut against a reference
        at the runway-end level)."""
        near = _rect(_D_FAR - 40.0, _D_FAR - 20.0)
        layout = _layout(near, crossings=(_D_FAR - 30.0,))
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert counts[0] == 1
        assert pins != {}

    def test_the_bound_is_judged_on_the_rects_near_edge(self, monkeypatch):
        """A rect that STRADDLES the bound keeps its geometry and is
        left to clause 3 — its value is then within a tail of the
        runway end, which is exactly the case the cut test decides."""
        strad = _rect(_D_FAR - 20.0, _D_FAR + 20.0)
        layout = _layout(strad, crossings=(_D_FAR,))
        _p, counts, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV + 40.0, monkeypatch=monkeypatch)
        assert counts[0] == 1


# ── (d2) THE 600 m RECOGNITION CAP (owner 2026-08-25d) ─────────────
class TestTheRecognitionCap:
    """(d2) The clause-2 companion the LEMD survivor forced.  25c's
    three clauses ALL passed LEMD's 14R wrap at D = 1066 m — a taxi
    centreline really does cross the extended centreline there, inside
    the 1280 m vacuous bound, and its regulation value really does cut.
    The owner rules that is not an end-around taxiway: **no rect is
    recognised beyond 600 m**, because real EATs cross at 439-482 m."""

    def test_the_cap_is_the_owners_measured_value(self):
        assert cfg.EAT_MAX_CROSSING_DIST_M == 600.0
        assert "EAT_MAX_CROSSING_DIST_M" in cfg.__all__

    def test_a_wrap_at_700_m_builds_no_rect(self, monkeypatch):
        """The spec's own case: a perfectly good routed wrap, cutting,
        inside ``D_clear`` = 804 m — and refused, because it is past the
        cap."""
        rect = _rect(690.0, 710.0)
        layout = _layout(rect, crossings=(700.0,))
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert 700.0 < _D_CLEAR, "this twin must sit INSIDE D_clear"
        assert pins == {}
        assert counts[0] == 0

    def test_the_lemd_survivor_distance_is_refused(self, monkeypatch):
        """D = 1066 m — the one rect 25c left standing at LEMD."""
        rect = _rect(1056.0, 1076.0)
        layout = _layout(rect, crossings=(1066.0,))
        pins, _c, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert pins == {}

    @pytest.mark.parametrize("d", [439.0, 460.0, 482.0])
    def test_the_kclt_crossing_band_is_untouched(self, d, monkeypatch):
        """THE FEATURE THIS LAW MUST NOT EAT.  KCLT's 18C-end loop
        crosses at 439-482 m; every station in that band still pins."""
        rect = _rect(d - 10.0, d + 10.0)
        layout = _layout(rect, crossings=(d,))
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert counts[0] == 1
        want = _END_ELEV + eat_pavement_ceiling(
            d, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        for v in pins.values():
            assert v == pytest.approx(want)

    def test_the_refusal_line_names_the_cap_not_d_clear(
            self, monkeypatch, capsys):
        """With two far bounds in play, a refusal that named neither
        would be unattributable — and naming the WRONG one would send
        the next reader to the regulation table for a number the
        regulation did not set."""
        import O4_UI_Utils as UI
        monkeypatch.setattr(UI, "verbosity", 3, raising=False)
        _build(_layout(_rect(690.0, 710.0), crossings=(700.0,)),
               reference=_END_ELEV, monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "EAT_MAX_CROSSING_DIST_M=600 m" in out
        assert "D_clear" not in out

    def test_gate_off_ignores_the_cap(self, monkeypatch):
        """The cap is recognition, so it rides the same gate: OFF is
        still the 2026-07-27 recognition exactly."""
        make = (lambda: _layout(_rect(690.0, 710.0), crossings=(700.0,)))
        assert _build(make(), reference=_END_ELEV, v2=True,
                      monkeypatch=monkeypatch)[0] == {}
        assert _build(make(), reference=_END_ELEV, v2=False,
                      monkeypatch=monkeypatch)[0] != {}


# ── (e) THE PIN ONLY CUTS ──────────────────────────────────────────
class TestThePinOnlyCuts:
    """(e) The regulation is a CEILING.  Where it sits ABOVE the
    pavement's unconstrained level everywhere it would stamp, it lifts
    pavement into the air — and pins nothing.  Amends the 2026-07-27
    "even if it has to fill DEM", which was formed on a cut."""

    def test_a_rect_above_its_reference_everywhere_is_refused(
            self, monkeypatch):
        """Reference 60 m, regulation 91.15 m — the LEMD 36R signature
        (pins 59-66 m above adjacent DEM-seeded pavement)."""
        layout = _layout(_rect(440.0, 460.0), crossings=(450.0,))
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=60.0, monkeypatch=monkeypatch)
        assert pins == {}
        assert counts[0] == 0

    def test_a_rect_that_cuts_somewhere_stands_whole(self, monkeypatch):
        """RECT-LEVEL, per the 2026-08-21 rect-refusal ruling: the rect
        is stamped FLAT at ONE value, so "does it cut?" is a question
        about the FACILITY.  One high corner is enough to keep it, and
        it keeps ALL its pins — a per-node spelling would shatter the
        flat stamp the mechanism depends on."""
        rect = _rect(440.0, 460.0)
        layout = _layout(rect, crossings=(450.0,))
        nodes, b2i = SP._build_node_list(layout)
        cps = layout.canonical_points
        n = len(nodes)
        elev, is_hard, have = [0.0] * n, [False] * n, [False] * n
        for (x, y) in _ring(_RWY):
            i = b2i[cps.get_or_add(float(x), float(y))]
            elev[i], is_hard[i], have[i] = _END_ELEV, True, True
        ring = _ring(rect)
        for k, (x, y) in enumerate(ring):
            i = b2i[cps.get_or_add(float(x), float(y))]
            # one corner well above the regulation, the rest below it
            elev[i] = 120.0 if k == 0 else 60.0
            have[i] = True
        pins, counts, _r, _s = SP._build_eat_anchor_rect_pins(
            layout, b2i, elev, is_hard, have_initial=have)
        assert counts[0] == 1
        assert set(pins) == set(_taxi_idx(layout, b2i, rect))

    def test_a_cut_below_the_materiality_floor_is_not_a_cut(
            self, monkeypatch):
        """0.01 m is the floor the anchor envelope already uses.  A rect
        that "cuts" by a millimetre is rounding, not law."""
        rect = _rect(440.0, 460.0)
        value = _END_ELEV + eat_pavement_ceiling(
            450.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        layout = _layout(rect, crossings=(450.0,))
        pins, _c, _r, _s, _b2i = _build(
            layout, reference=value + 0.001, monkeypatch=monkeypatch)
        assert pins == {}
        layout2 = _layout(rect, crossings=(450.0,))
        pins2, _c2, _r2, _s2, _b2 = _build(
            layout2, reference=value + 0.5, monkeypatch=monkeypatch)
        assert pins2 != {}

    def test_a_rect_with_no_reference_at_all_keeps_its_pin(
            self, monkeypatch):
        """A MISSING REFERENCE IS HONEST.  With no DEM and no warm start
        the node carries no unconstrained level, so the cut test has no
        witness — and an unpriceable rect is not refused, it is
        unjudged (the 2026-08-21 lesson, applied in reverse)."""
        layout = _layout(_rect(440.0, 460.0), crossings=(450.0,))
        pins, counts, _r, _s, _b2i = _build(
            layout, reference=None, monkeypatch=monkeypatch)
        assert counts[0] == 1
        assert pins != {}


# ── the verdict survives the DEM-less re-seeds ─────────────────────
class TestTheRecognitionVerdictIsCarried:
    """``final_grade_projection`` re-runs the seeder with NO dem, so a
    later pass cannot re-price clause 3 — it has no reference at all —
    and would re-pin the very rect the DEM-bearing pass refused.  The
    verdict is therefore recorded by CANONICAL POINT and re-read on
    every pass, exactly as the contradiction guard's is."""

    def test_a_cut_refusal_is_published_and_re_read(self, monkeypatch):
        rect = _rect(440.0, 460.0)
        layout = _layout(rect, crossings=(450.0,))
        pins, _c, _r, _s, _b2i = _build(
            layout, reference=60.0, monkeypatch=monkeypatch)
        assert pins == {}
        carried = getattr(layout, "_eat_scope_refused_keys", None)
        assert carried, "the verdict must be published"
        # A SECOND pass with no reference at all (the DEM-less
        # re-seed): without the carried verdict this rect would come
        # straight back, because "no reference" means "unjudged".
        again = _layout(rect, crossings=(450.0,))
        again._eat_scope_refused_keys = set(carried)
        pins2, counts2, _r2, _s2, _b2 = _build(
            again, reference=None, monkeypatch=monkeypatch)
        assert pins2 == {}
        assert counts2[0] == 0

    def test_a_node_another_end_pinned_is_never_carried_as_refused(
            self, monkeypatch, capsys):
        """Two ends' corridors can cover ONE crossing (the lower value
        wins).  If the near end refuses the rect on the cut test and the
        far end pins it, carrying the near end's refusal would DELETE on
        the next pass the pin this one just made."""
        rect = _rect(440.0, 460.0)
        layout = _layout(rect, crossings=(450.0,))
        # A second end 100 m behind the first, 40 m lower: its surface
        # at D = 550 is the more restrictive one and it CUTS — and 550 m
        # is INSIDE the 600 m recognition cap, so the cap does not
        # decide this twin.
        far = dict(_end_spec(), p0=(-100.0, 0.0), end_id="27",
                   anchor_xy=(-100.0, -22.0))
        layout.eat_ceiling_presolve = [_end_spec(), far]
        layout.shapes.append(BuiltShape(
            role=ROLE_RUNWAY,
            polygon=Polygon([(-1100.0, -22.0), (-100.0, -22.0),
                             (-100.0, 22.0), (-1100.0, 22.0)]),
            altitude_high=60.0, altitude_low=60.0))
        nodes, b2i = SP._build_node_list(layout)
        cps = layout.canonical_points
        n = len(nodes)
        elev, is_hard, have = [0.0] * n, [False] * n, [False] * n
        for (x, y) in _ring(_RWY):
            i = b2i[cps.get_or_add(float(x), float(y))]
            elev[i], is_hard[i], have[i] = _END_ELEV, True, True
        i_far = b2i[cps.get_or_add(-100.0, -22.0)]
        elev[i_far], is_hard[i_far], have[i_far] = 60.0, True, True
        for (x, y) in _ring(rect):
            i = b2i[cps.get_or_add(float(x), float(y))]
            if not is_hard[i]:
                elev[i], have[i] = 80.0, True
        import O4_UI_Utils as UI
        monkeypatch.setattr(UI, "verbosity", 3, raising=False)
        monkeypatch.setattr(cfg, "EAT_SCOPING_V2_ENABLED", True)
        pins, _c, _r, _s = SP._build_eat_anchor_rect_pins(
            layout, b2i, elev, is_hard, have_initial=have)
        out = capsys.readouterr().out
        assert "end 09" in out and "regulation above reference" in out, (
            "the near end must actually refuse, or this twin is vacuous")
        assert pins, "the far end's surface cuts and must pin"
        far_value = 60.0 + eat_pavement_ceiling(
            550.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        for v in pins.values():
            assert v == pytest.approx(far_value)
        carried = set(getattr(layout, "_eat_scope_refused_keys", None)
                      or ())
        pinned_keys = {cps.get_or_add(float(x), float(y))
                       for (x, y) in _ring(rect)}
        assert not (carried & pinned_keys)

    def test_an_accepted_rect_publishes_nothing(self, monkeypatch):
        layout = _layout(_rect(440.0, 460.0), crossings=(450.0,))
        _build(layout, reference=_END_ELEV, monkeypatch=monkeypatch)
        assert not getattr(layout, "_eat_scope_refused_keys", None)

    def test_the_gate_off_carries_nothing(self, monkeypatch):
        layout = _layout(_rect(440.0, 460.0))
        _build(layout, reference=_END_ELEV, v2=False,
               monkeypatch=monkeypatch)
        assert not getattr(layout, "_eat_scope_refused_keys", None)

    def test_the_probe_restore_lists_fence_the_store(self):
        """A measurement instrument must not leave this verdict behind
        in the production layout — the same fence every other pin
        publication of the seeder carries."""
        import inspect
        assert "_eat_scope_refused_keys" in SV._PROBE_PUBLISHED_ATTRS
        src = inspect.getsource(SV)
        assert src.count('"_eat_scope_refused_keys"') >= 3, (
            "all three snapshot/restore lists must fence the store")


# ── the loud line ──────────────────────────────────────────────────
class TestEveryRefusalIsLoudAndNamesItsClause:
    """Recognition that silently narrows is indistinguishable from
    recognition that broke.  Each refused rect prints its end, its
    distance and WHICH clause took it."""

    @pytest.mark.parametrize("case,needle", [
        ("no-route", "no through-centerline"),
        # At this code-E FAA end the 600 m CAP is the stricter of the
        # two far bounds, so that is the rule the line must name.
        ("far", "beyond the recognition cap"),
        ("above", "regulation above reference"),
    ])
    def test_the_refusal_line_names_the_clause(self, case, needle,
                                               monkeypatch, capsys):
        import O4_UI_Utils as UI
        monkeypatch.setattr(UI, "verbosity", 3, raising=False)
        if case == "no-route":
            layout, ref = _layout(_rect(440.0, 460.0)), _END_ELEV
        elif case == "far":
            layout = _layout(_rect(_D_FAR + 60.0, _D_FAR + 80.0),
                             crossings=(_D_FAR + 70.0,))
            ref = _END_ELEV
        else:
            layout, ref = _layout(_rect(440.0, 460.0),
                                  crossings=(450.0,)), 60.0
        _build(layout, reference=ref, monkeypatch=monkeypatch)
        out = capsys.readouterr().out
        assert "[eat-scope]" in out
        assert needle in out
        assert "end 09" in out, "the line names the runway end"


# ── (f) THE GATE ───────────────────────────────────────────────────
class TestTheGate:
    """(f) OFF ⇒ the 2026-07-27 recognition exactly — the attribution
    arm this round's numbers are read against."""

    def test_the_gate_defaults_on(self):
        import re
        from pathlib import Path
        src = Path(cfg.__file__).read_text(encoding="utf-8")
        m = re.search(r'O4_EAT_SCOPING_V2",\s*"(\d)"', src)
        assert m is not None, "the gate's env default line moved"
        assert m.group(1) == "1"

    @pytest.mark.parametrize("case", ["no-route", "far", "above"])
    def test_off_pins_everything_the_old_recognition_pinned(
            self, case, monkeypatch):
        """Each of the three clauses, refused ON and pinned OFF."""
        if case == "no-route":
            make, ref = (lambda: _layout(_rect(440.0, 460.0))), _END_ELEV
        elif case == "far":
            make = (lambda: _layout(
                _rect(_D_FAR + 60.0, _D_FAR + 80.0),
                crossings=(_D_FAR + 70.0,)))
            ref = _END_ELEV
        else:
            make = (lambda: _layout(_rect(440.0, 460.0),
                                    crossings=(450.0,)))
            ref = 60.0
        on = _build(make(), reference=ref, v2=True,
                    monkeypatch=monkeypatch)[0]
        off = _build(make(), reference=ref, v2=False,
                     monkeypatch=monkeypatch)[0]
        assert on == {}
        assert off != {}

    def test_off_prints_no_scope_line(self, monkeypatch, capsys):
        import O4_UI_Utils as UI
        monkeypatch.setattr(UI, "verbosity", 3, raising=False)
        _build(_layout(_rect(440.0, 460.0)), reference=_END_ELEV,
               v2=False, monkeypatch=monkeypatch)
        assert "[eat-scope]" not in capsys.readouterr().out

    def test_off_publishes_no_side_map(self, monkeypatch):
        """The guard site reads the side map only when it exists, so
        gate OFF must leave the both-sides law unarmed."""
        _p, _c, _r, side, _b2i = _build(
            _layout(_rect(440.0, 460.0), crossings=(450.0,)),
            reference=_END_ELEV, v2=False, monkeypatch=monkeypatch)
        assert side == {}
