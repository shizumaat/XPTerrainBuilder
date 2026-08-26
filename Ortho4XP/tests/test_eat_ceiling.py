"""END-AROUND TAXIWAY (EAT) departure-surface law — owner rulings
2026-07-27, ANCHOR-RECT revision (docs/specs/eat-anchor-rect-spec.md).

An end-around taxiway loops beyond a runway end and crosses the extended
centreline, so an aircraft on it stands under the departure / take-off-climb
surface.  The surface must clear the aircraft's TAIL, which forces the EAT
PAVEMENT below the runway-end elevation (KATL taxiway Victor ≈ −9 m).

This file pins:

  * the LAW — ``grade_law.eat_pavement_ceiling`` at the KCLT-class numbers
    (D = 460 m, code E: FAA −8.6 m, EASA −12.1 m off the runway end);
  * the REGION selector — FAA for North America (ICAO K/C/P/M), EASA
    everywhere else;
  * the ANCHOR RECT — the crossing segment (extended centreline corridor
    at the runway's DECLARED half-width ∩ taxi/junction/apron pavement,
    beyond the 300 m minimum crossing distance) HARD-PINNED flat at
    ``end_elev + eat_pavement_ceiling(D_mid)`` inside
    ``solver_primitives._seed_elevations`` — the regulation value,
    unconditionally; lower value wins where two ends' corridors overlap;
    senior pins (runway / seam) never overridden;
  * the scoping HELPERS the rect construction and the verification
    reader share (``eat_end_projection``, ``eat_scoping_bounds``,
    ``eat_ceiling_offset``, ``_eat_shape_may_be_governed``);
  * the GATE — off ⇒ no pins, no findings, and verify output with no
    trace of the feature.

The first implementation's one-sided pavement↔pavement interval edges
(``_build_eat_ceiling_constraints``) are RETIRED: their negative slab
weights blew up the reach-envelope Dijkstra (KCLT killed at 15 min CPU /
20.3 GB).  The gate now defaults ON — the tests still state the gate they
want explicitly, so neither direction silently stops testing anything if
the default ever moves again.

Hermetic: hand-built layouts, no fixtures, no DEM files, no X-Plane, no
network.
"""
import pytest
from shapely.geometry import Polygon

import auto_patch.config as cfg
import auto_patch.verification as V
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.grade_law import eat_pavement_ceiling
from auto_patch.layout import (
    BuiltShape, PavementLayout, ROLE_APRON, ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY, ROLE_SERVICE_ROAD,
)


@pytest.fixture(autouse=True)
def _eat_gate_on(monkeypatch):
    """Every test here states the gate it wants; the default (ON) and
    any ``O4_*`` override in the developer's shell must not silently
    decide what these tests measure.  The gate-OFF tests re-patch it to
    False."""
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", True)


def test_gate_defaults_on_with_the_anchor_rect_revision():
    """The anchor-rect revision rides the positive-weight hard-anchor
    machinery — no negative slab exists anywhere — so the build-time
    blocker that kept the first implementation gated off is structurally
    gone and the owner ruling is to ship the law ON.

    Read from the source line, not the imported value: the autouse
    fixture above (and any ``O4_*`` override in the developer's shell)
    deliberately moves the imported one."""
    import re
    from pathlib import Path
    src = (Path(cfg.__file__)).read_text(encoding="utf-8")
    m = re.search(r'O4_EAT_SURFACE_CEILING",\s*"(\d)"', src)
    assert m is not None, "the gate's env default line moved"
    assert m.group(1) == "1"


# ── THE LAW ──────────────────────────────────────────────────────────
class TestEatPavementCeiling:
    def test_faa_460m_code_e(self):
        """KCLT class: the 18C-end EAT crosses at D ≈ 460 m; an ADG-V
        (code E) tail is 20.1 m.  40:1 from the DER, no setback."""
        assert eat_pavement_ceiling(
            460.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"]) == pytest.approx(-8.6)

    def test_easa_460m_code_e(self):
        """The same geometry under CS-ADR-DSN: 2 % from a 60 m inner
        edge — a LOWER ceiling than FAA beyond ~240 m."""
        assert eat_pavement_ceiling(
            460.0, cfg.EAT_EASA_TAKEOFF_CLIMB_SLOPE, cfg.EAT_EASA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"]) == pytest.approx(-12.1)

    def test_ceiling_is_below_the_runway_end_at_realistic_distances(self):
        """The whole point of the law: the pavement must go DOWN.  The
        offset is not clamped at 0."""
        for d in (300.0, 460.0, 700.0):
            assert eat_pavement_ceiling(d, 0.025, 0.0, 20.1) < 0.0

    def test_setback_floors_the_surface_rise_not_the_ceiling(self):
        """Inside the EASA setback the SURFACE is at its inner-edge
        height (rise 0) — never a fictitious below-DER surface — so the
        ceiling there is exactly minus the tail height."""
        assert eat_pavement_ceiling(30.0, 0.02, 60.0, 13.7) == \
            pytest.approx(-13.7)
        assert eat_pavement_ceiling(0.0, 0.02, 60.0, 13.7) == \
            pytest.approx(-13.7)

    def test_ceiling_rises_with_distance_at_the_surface_slope(self):
        a = eat_pavement_ceiling(400.0, 0.025, 0.0, 20.1)
        b = eat_pavement_ceiling(500.0, 0.025, 0.0, 20.1)
        assert b - a == pytest.approx(100.0 * 0.025)

    def test_taller_tail_is_the_stricter_ceiling(self):
        tall = eat_pavement_ceiling(
            460.0, 0.025, 0.0, cfg.TAIL_HEIGHT_BY_CODE_LETTER["F"])
        short = eat_pavement_ceiling(
            460.0, 0.025, 0.0, cfg.TAIL_HEIGHT_BY_CODE_LETTER["C"])
        assert tall < short


def test_tail_height_table_is_the_ac_table_1_1_set():
    assert cfg.TAIL_HEIGHT_BY_CODE_LETTER == {
        "A": 6.1, "B": 9.1, "C": 13.7, "D": 18.3, "E": 20.1, "F": 24.4}
    # Same key set as the wingspan table it sits beside.
    assert (set(cfg.TAIL_HEIGHT_BY_CODE_LETTER)
            == set(cfg.WINGSPAN_BY_CODE_LETTER))


# ── the REGION selector ──────────────────────────────────────────────
_FAA = (cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M)
_EASA = (cfg.EAT_EASA_TAKEOFF_CLIMB_SLOPE, cfg.EAT_EASA_SETBACK_M)


@pytest.mark.parametrize("icao,expected", [
    ("KCLT", _FAA),       # contiguous USA
    ("CYYZ", _FAA),       # Canada
    ("PANC", _FAA),       # Alaska / US Pacific
    ("MMMX", _FAA),       # Mexico
    ("EGLL", _EASA),      # United Kingdom
    ("LFPG", _EASA),      # France
    ("HECA", _EASA),      # Egypt
    ("SPJC", _EASA),      # Peru
])
def test_region_selection(icao, expected):
    assert cfg.eat_surface_slope_and_setback(icao) == expected


def test_unknown_icao_falls_to_the_stricter_easa_surface():
    """Missing data must never buy a permissive surface."""
    for bad in (None, "", "   "):
        assert cfg.eat_surface_slope_and_setback(bad) == _EASA
    assert (eat_pavement_ceiling(460.0, *_EASA, 20.1)
            < eat_pavement_ceiling(460.0, *_FAA, 20.1))


def test_runway_code_letter_resolves_a_45m_runway_to_E():
    """ADG IV and V share the 150 ft width; a ceiling law takes the
    taller tail (E), which is what KCLT/KATL actually are."""
    assert cfg.runway_code_letter(45.0) == "E"
    assert cfg.runway_code_letter(60.0) == "F"
    assert cfg.runway_code_letter(30.0) == "D"
    assert cfg.runway_code_letter(23.0) == "C"


# ── the anchor-rect pin builder ──────────────────────────────────────
# Runway lying along −x, its EAST end (the DER) at x = 0.
_RWY = Polygon([(-1000.0, -22.0), (0.0, -22.0), (0.0, 22.0),
                (-1000.0, 22.0)])
_ANCHOR_XY = (0.0, -22.0)          # a runway ring vertex at the end
_END_ELEV = 100.0                  # the runway's (flat) profile value
_HALF = 22.5                       # declared 45 m runway → half-width


def _rect(x0, x1, y0, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _end_spec(letter="E", slope=None, setback=None):
    slope = cfg.EAT_FAA_DEPARTURE_SLOPE if slope is None else slope
    setback = cfg.EAT_FAA_SETBACK_M if setback is None else setback
    return {
        "p0": (0.0, 0.0),
        "outward": (1.0, 0.0),
        "code_letter": letter,
        "code_number": 4,
        "slope": float(slope),
        "setback_m": float(setback),
        "tail_height_m": float(cfg.TAIL_HEIGHT_BY_CODE_LETTER[letter]),
        "anchor_xy": _ANCHOR_XY,
        "half_width_m": _HALF,
    }


# Candidate taxi rects: one too close to the end, one squarely in the
# rect corridor, one inside the 90 m SCOPING corridor but outside the
# declared half-width, one far off to the side.
_NEAR = _rect(40.0, 60.0, -10.0, 10.0)            # s ≈ 50 m
_IN = _rect(390.0, 410.0, -10.0, 10.0)            # s ≈ 400 m, |q| ≤ 10
_FLANK = _rect(390.0, 410.0, 30.0, 50.0)          # |q| 30-50 > 22.5
_ASIDE = _rect(390.0, 410.0, 190.0, 210.0)        # s ≈ 400 m, |q| ≥ 190
# The expected pin for ``_IN``: flat at the mid-distance (D_mid = 400)
# regulation value off the 100 m runway end.
_IN_PIN = _END_ELEV + eat_pavement_ceiling(
    400.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
    cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])           # = 89.9


def _layout(*taxi_polys, roles=None, specs=None):
    """A real ``PavementLayout``: the 100 m runway (its corners seed
    HARD, so the end anchor is readable) plus the given taxi shapes."""
    roles = roles or [ROLE_PRIMARY_PARALLEL] * len(taxi_polys)
    layout = PavementLayout(icao="KTST", anchor=(35.231, -80.955))
    layout.canonical_points = CanonicalPointRegistry()
    layout.shapes = [BuiltShape(role=ROLE_RUNWAY, polygon=_RWY,
                                altitude_high=_END_ELEV,
                                altitude_low=_END_ELEV)]
    layout.shapes += [BuiltShape(role=role, polygon=poly)
                      for role, poly in zip(roles, taxi_polys)]
    layout.eat_ceiling_presolve = ([_end_spec()] if specs is None
                                   else list(specs))
    # A TAXI CENTRELINE crossing the extended centreline at each taxi
    # shape's own station.  Recognition scoping v2 (owner ruling
    # 2026-08-25c clause 1) asks whether a taxi ROUTE wraps the runway
    # end, not merely whether pavement lies in the corridor — and every
    # rect built here is MEANT to be an end-around taxiway, so each one
    # gets its through-route.  Adds no solver node (verified: the node
    # list is unchanged), so the mechanism these tests pin is measured
    # on exactly the geometry it always was.
    from shapely.geometry import LineString

    from auto_patch.apt_dat_reader import TaxiCenterline
    layout.apt_taxi_centerlines = [
        TaxiCenterline(line=LineString([(poly.centroid.x, -120.0),
                                        (poly.centroid.x, 120.0)]))
        for poly in taxi_polys]
    return layout


def _seed(layout):
    """Run the real seeding pass; returns ``(nodes, b2i, elev, hard)``."""
    nodes, b2i = SP._build_node_list(layout)
    elev, hard, _have = SP._seed_elevations(layout, nodes, b2i)
    return nodes, b2i, elev, hard


def _taxi_idx(layout, b2i, poly):
    cps = layout.canonical_points
    return [b2i[cps.get_or_add(float(x), float(y))]
            for (x, y) in list(poly.exterior.coords)[:-1]]


class TestAnchorRectPins:
    def test_rect_pins_flat_at_the_mid_distance_regulation_value(self):
        """THE MECHANISM: the crossing segment (s 390-410, D_mid 400) is
        HARD-PINNED flat at ``end_elev + eat_pavement_ceiling(400)`` =
        89.9 — a KATL-scale depression below the 100 m runway end,
        stamped as a hard anchor the solver grades to."""
        layout = _layout(_IN)
        _nodes, b2i, elev, hard = _seed(layout)
        idx = _taxi_idx(layout, b2i, _IN)
        assert len(idx) == 4
        for i in idx:
            assert hard[i], "a rect pin must be HARD"
            assert elev[i] == pytest.approx(_IN_PIN)
        assert _IN_PIN == pytest.approx(89.9)
        assert _IN_PIN < _END_ELEV - 9.0

    def test_pins_are_published_and_join_the_seam_pin_store(self):
        """The solve registers the pins as runway-class anchors via
        ``layout._eat_anchor_pin_idx``, and the seam-pin protection set
        keeps every downstream seat-stamp / yield relaxation off them."""
        layout = _layout(_IN)
        _nodes, b2i, _elev, _hard = _seed(layout)
        idx = set(_taxi_idx(layout, b2i, _IN))
        assert set(layout._eat_anchor_pin_idx) == idx
        for v in layout._eat_anchor_pin_idx.values():
            assert v == pytest.approx(_IN_PIN)
        assert idx <= layout._seam_pin_idx

    def test_pavement_near_the_end_is_not_pinned(self):
        """A node at s = 50 m is an ordinary runway-end connector, not
        an end-around taxiway — the regulation value there would be
        −18.6 m."""
        layout = _layout(_NEAR)
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _NEAR))
        assert layout._eat_anchor_pin_idx == {}

    def test_rect_uses_the_declared_half_width_not_the_corridor(self):
        """|q| = 30-50 m is inside the 90 m SCOPING corridor but outside
        the 22.5 m declared half-width: the rect is only the segment the
        runway itself would cover if extended — the loop parts are
        governed via the caps, not pinned."""
        layout = _layout(_FLANK)
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _FLANK))

    def test_pavement_off_to_the_side_is_not_pinned(self):
        layout = _layout(_ASIDE)
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _ASIDE))

    def test_only_the_rect_shape_is_pinned(self):
        layout = _layout(_NEAR, _IN, _ASIDE)
        _nodes, b2i, _elev, _hard = _seed(layout)
        assert (set(layout._eat_anchor_pin_idx)
                == set(_taxi_idx(layout, b2i, _IN)))

    def test_kclt_class_rect_solves_to_end_minus_8_6(self):
        """The spec's smoke arithmetic: a code-E crossing at D_mid =
        460 m under FAA 40:1 pins at end − 8.6 m."""
        layout = _layout(_rect(450.0, 470.0, -10.0, 10.0))
        _nodes, _b2i, _elev, _hard = _seed(layout)
        for v in layout._eat_anchor_pin_idx.values():
            assert v == pytest.approx(_END_ELEV - 8.6)

    def test_two_crossings_pin_at_their_own_mid_distance(self):
        """Two connected segments split by an along-centreline gap
        larger than ``EAT_RECT_SEGMENT_GAP_M`` — one per EAT, each flat
        at its OWN ``D_mid`` regulation value."""
        far_rect = _rect(600.0, 620.0, -10.0, 10.0)
        layout = _layout(_IN, far_rect)
        _nodes, b2i, elev, _hard = _seed(layout)
        far_pin = _END_ELEV + eat_pavement_ceiling(
            610.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        for i in _taxi_idx(layout, b2i, _IN):
            assert elev[i] == pytest.approx(_IN_PIN)
        for i in _taxi_idx(layout, b2i, far_rect):
            assert elev[i] == pytest.approx(far_pin)
        assert far_pin > _IN_PIN          # the surface rises with D

    def test_overlapping_end_corridors_take_the_lower_value(self):
        """Two ends whose corridors cover one EAT: the most restrictive
        (lower) regulation value governs, deterministically.  The far
        end's runway sits 20 m lower, so its surface wins even though
        its D is larger."""
        far_rwy = Polygon([(-1200.0, -22.0), (-200.0, -22.0),
                           (-200.0, 22.0), (-1200.0, 22.0)])
        layout = _layout(_IN)
        layout.shapes.append(BuiltShape(
            role=ROLE_RUNWAY, polygon=far_rwy,
            altitude_high=80.0, altitude_low=80.0))
        far_spec = dict(_end_spec(), p0=(-200.0, 0.0),
                        anchor_xy=(-200.0, -22.0))
        layout.eat_ceiling_presolve = [_end_spec(), far_spec]
        _nodes, b2i, elev, _hard = _seed(layout)
        far_pin = 80.0 + eat_pavement_ceiling(
            600.0, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        assert far_pin < _IN_PIN
        for i in _taxi_idx(layout, b2i, _IN):
            assert elev[i] == pytest.approx(far_pin)

    def test_senior_hard_nodes_are_never_overridden(self):
        """A rect vertex shared with a runway ring is already HARD at
        the profile value — the runway (and the seam law) outrank the
        rect; the pin never masquerades over a datum."""
        cross = Polygon([(390.0, -10.0), (420.0, -10.0),
                         (420.0, -60.0), (390.0, -60.0)])
        layout = _layout(_IN)
        layout.shapes.append(BuiltShape(
            role=ROLE_RUNWAY, polygon=cross,
            altitude_high=95.0, altitude_low=95.0))
        _nodes, b2i, elev, hard = _seed(layout)
        shared = b2i[layout.canonical_points.get_or_add(390.0, -10.0)]
        assert hard[shared]
        assert elev[shared] == pytest.approx(95.0)
        assert shared not in layout._eat_anchor_pin_idx
        others = [i for i in _taxi_idx(layout, b2i, _IN) if i != shared]
        for i in others:
            assert elev[i] == pytest.approx(_IN_PIN)

    def test_an_unresolvable_anchor_pins_nothing(self):
        """No readable end elevation ⇒ no pin — a guessed datum would
        masquerade as regulation."""
        layout = _layout(_IN,
                         specs=[dict(_end_spec(),
                                     anchor_xy=(5000.0, 5000.0))])
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _IN))
        assert layout._eat_anchor_pin_idx == {}

    def test_a_legacy_spec_without_half_width_is_skipped(self):
        spec = _end_spec()
        del spec["half_width_m"]
        layout = _layout(_IN, specs=[spec])
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _IN))

    def test_a_small_runway_end_owns_no_eat(self):
        """FALSE-EAT GUARD 1: end-around taxiways exist at transport-
        category runways only (code ≥ 3).  CYXY's 700 m code-1 strip
        02/20 aimed its corridor across the GA apron — 23 vertices were
        pinned ~5 m into the ground as a phantom EAT."""
        assert cfg.EAT_MIN_RUNWAY_CODE_NUMBER == 3
        layout = _layout(_IN,
                         specs=[dict(_end_spec(), code_number=2)])
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _IN))
        assert layout._eat_anchor_pin_idx == {}

    def test_pavement_running_along_the_corridor_is_refused(self):
        """FALSE-EAT GUARD 2: a real EAT CROSSES the corridor — its
        segment is short along ``s`` (KCLT: 43 m).  A shape running
        ALONG the extended centreline (CYXY: a 327 m apron smear) is
        another facility under the surface and is refused whole."""
        along = _rect(310.0, 310.0 + cfg.EAT_RECT_MAX_ALONG_M + 60.0,
                      -10.0, 10.0)
        layout = _layout(along)
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, along))
        assert layout._eat_anchor_pin_idx == {}
        # The KCLT-class short crossing stays pinned under the same cap.
        assert 410.0 - 390.0 < cfg.EAT_RECT_MAX_ALONG_M

    def test_service_roads_and_runways_are_not_governed(self):
        """A service road carries no aircraft tail; the runway profile
        is HARD and the rect must never bend it."""
        assert ROLE_SERVICE_ROAD not in SP.EAT_CEILING_ROLES
        assert ROLE_RUNWAY not in SP.EAT_CEILING_ROLES
        assert ROLE_APRON in SP.EAT_CEILING_ROLES
        layout = _layout(_IN, roles=[ROLE_SERVICE_ROAD])
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _IN))

    def test_no_store_means_no_pins(self):
        layout = _layout(_IN)
        del layout.eat_ceiling_presolve
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not any(hard[i] for i in _taxi_idx(layout, b2i, _IN))
        assert not hasattr(layout, "_eat_anchor_pin_idx")

    def test_gate_off_is_byte_inert(self, monkeypatch):
        """Gate OFF with a (stale) store present: seeding is byte-
        identical to the no-store build and publishes nothing."""
        monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", False)
        layout = _layout(_IN)
        _nodes, _b2i, elev_off, hard_off = _seed(layout)
        assert not hasattr(layout, "_eat_anchor_pin_idx")
        bare = _layout(_IN)
        del bare.eat_ceiling_presolve
        _nodes2, _b2i2, elev_bare, hard_bare = _seed(bare)
        assert elev_off == elev_bare
        assert hard_off == hard_bare

    def test_pins_stay_hard_through_the_projection(self):
        """The anchor discipline the spec rides: a hard pin is held by
        every projection exactly like a tile-seam pin — the ramps grade
        to it; it never moves."""
        from auto_patch.elevation_per_surface.route_profile.one_solve \
            import feasibility_project
        layout = _layout(_IN)
        nodes, b2i, elev, hard = _seed(layout)
        idx = _taxi_idx(layout, b2i, _IN)
        hard_set = {i for i in range(len(elev)) if hard[i]}
        # One symmetric law edge from each pin to the runway-end anchor
        # at a generous budget — the projection must leave the hard pins
        # alone whatever the edges say.
        anchor = b2i[layout.canonical_points.get_or_add(*_ANCHOR_XY)]
        scs = [{"nodes": list(idx) + [anchor],
                "edges": [(i, anchor, 50.0) for i in idx],
                "flat": False, "flat_pairs": (), "area": 0.0,
                "role": ROLE_PRIMARY_PARALLEL, "ref": "eat_test"}]
        before = list(elev)
        feasibility_project(elev, scs, hard_set, force_scalar=True)
        for i in idx:
            assert elev[i] == pytest.approx(before[i], abs=1e-12)


class TestScoping:
    def test_scoping_thresholds_come_from_config(self):
        """The 300 m / 90 m numbers are rule VALUES and live in config."""
        assert cfg.EAT_MIN_CROSSING_DIST_M == 300.0
        assert cfg.EAT_CORRIDOR_HALF_WIDTH_M == 90.0
        spec = _end_spec()
        just_inside = cfg.EAT_MIN_CROSSING_DIST_M + 0.1
        just_outside = cfg.EAT_MIN_CROSSING_DIST_M - 0.1
        assert SP.eat_ceiling_offset(spec, just_inside, 0.0) is not None
        assert SP.eat_ceiling_offset(spec, just_outside, 0.0) is None
        half = cfg.EAT_CORRIDOR_HALF_WIDTH_M
        assert SP.eat_ceiling_offset(spec, 400.0, half) is not None
        assert SP.eat_ceiling_offset(spec, 400.0, -half) is not None
        assert SP.eat_ceiling_offset(spec, 400.0, half + 0.1) is None


    @pytest.mark.parametrize("outward", [
        (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
        (0.6, 0.8), (-0.6, 0.8), (0.6, -0.8), (-0.6, -0.8),
    ])
    def test_shape_bbox_prefilter_never_rejects_a_governed_vertex(
            self, outward):
        """The whole-shape reject is a pure speed hoist: ``s``/``q`` are
        affine, so a box whose corners all fail cannot contain a governed
        vertex.  Swept over a grid in every quadrant, the closed-form
        filter never disagrees with the law itself."""
        spec = dict(_end_spec(), outward=outward)
        bounds = SP.eat_scoping_bounds()
        checked = 0
        for x0 in range(-900, 900, 150):
            for y0 in range(-900, 900, 150):
                bbox = (x0, y0, x0 + 150, y0 + 150)
                governed = any(
                    SP.eat_ceiling_offset(spec, x, y, bounds) is not None
                    for x in range(x0, x0 + 151, 15)
                    for y in range(y0, y0 + 151, 15))
                if governed:
                    checked += 1
                    assert SP._eat_shape_may_be_governed(
                        bbox, spec, bounds), (outward, bbox)
        assert checked > 5, "the sweep must actually hit the corridor"

    @pytest.mark.parametrize("outward", [
        (1.0, 0.0), (0.0, -1.0), (0.6, 0.8), (-0.6, -0.8),
    ])
    def test_bbox_prefilter_matches_the_naive_four_corner_form(self,
                                                               outward):
        """The closed form is the four-corner test with the sign of each
        coefficient picking the favourable bound — pin the equivalence."""
        spec = dict(_end_spec(), outward=outward)
        min_s, half = SP.eat_scoping_bounds()

        def naive(bbox):
            x0, y0, x1, y1 = bbox
            p0 = spec["p0"]
            nx, ny = spec["outward"]
            sv, qv = [], []
            for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                dx, dy = x - p0[0], y - p0[1]
                sv.append(dx * nx + dy * ny)
                qv.append(-dx * ny + dy * nx)
            if max(sv) < min_s:
                return False
            return not (min(qv) > half or max(qv) < -half)

        for x0 in range(-800, 800, 130):
            for y0 in range(-800, 800, 130):
                bbox = (x0, y0, x0 + 130, y0 + 170)
                assert SP._eat_shape_may_be_governed(
                    bbox, spec, (min_s, half)) == naive(bbox), bbox

    def test_projection_helper_matches_the_inlined_frame(self):
        """``eat_ceiling_offset`` inlines ``eat_end_projection``'s
        arithmetic for speed — the two must not drift."""
        spec = dict(_end_spec(), p0=(12.0, -34.0),
                    outward=(0.6, 0.8))
        bounds = SP.eat_scoping_bounds()
        for x, y in ((500.0, 300.0), (-100.0, 40.0), (900.0, -250.0)):
            s, q = SP.eat_end_projection(spec, x, y)
            governed = (s >= bounds[0] and abs(q) <= bounds[1])
            assert (SP.eat_ceiling_offset(spec, x, y, bounds) is not None) \
                == governed

    def test_hoisted_bounds_do_not_change_the_answer(self):
        spec = _end_spec()
        bounds = SP.eat_scoping_bounds()
        for x, y in ((50.0, 0.0), (400.0, 0.0), (400.0, 200.0),
                     (900.0, -89.0)):
            assert (SP.eat_ceiling_offset(spec, x, y)
                    == SP.eat_ceiling_offset(spec, x, y, bounds))


# ── the verification reader ──────────────────────────────────────────
def _real_layout():
    """A minimal real ``PavementLayout``: a runway at 100 m and an EAT
    rect 400 m past its east end, emitted 1 m ABOVE the runway end (the
    pre-law KCLT symptom)."""
    layout = PavementLayout(icao="KTST", anchor=(35.231, -80.955))
    layout.shapes = [
        BuiltShape(role=ROLE_RUNWAY, polygon=_RWY,
                   altitude_high=100.0, altitude_low=100.0),
        BuiltShape(role=ROLE_PRIMARY_PARALLEL, polygon=_IN, ref="V",
                   altitude_high=101.0, altitude_low=101.0),
    ]
    layout.eat_ceiling_presolve = [_end_spec()]
    return layout


def _quiet_other_readers(monkeypatch):
    """Silence the DEM-reading law readers so this stays headless."""
    monkeypatch.setattr(cfg, "ADJACENT_GROUND_LAW_ENABLED", False)
    monkeypatch.setattr(cfg, "OLS_CUT_ENABLED", False)
    monkeypatch.setattr(cfg, "OBJECT_BRIDGE_TERRAIN", False)


def test_reader_flags_pavement_above_the_surface():
    findings = V.check_eat_ceiling(_real_layout())
    assert findings, "an EAT 1 m above the runway end must be flagged"
    kind, ref, mag, tol, loc = findings[0]
    assert kind == "eat_above_departure_surface"
    assert ref == "V"
    assert tol == pytest.approx(0.15)
    # Worst = the NEAREST corner (lowest ceiling): at s = 390 m,
    # 390·0.025 − 20.1 = −10.35 ⇒ max 89.65 m, so 101.0 is 11.35 m over.
    assert mag == pytest.approx(101.0 - (100.0 - 10.35), abs=1e-6)
    assert "," in loc
    assert findings == sorted(findings, key=lambda r: -r[2])


def test_reader_is_silent_on_a_compliant_layout():
    layout = _real_layout()
    # Put the taxiway under the worst (nearest) corner's ceiling.
    for shape in layout.shapes[1:]:
        shape.altitude_high = shape.altitude_low = 100.0 - 12.0
    assert V.check_eat_ceiling(layout) == []


def test_reader_and_builder_share_one_scoping_function():
    """LOCKSTEP: a finding can only ever be "the solve did not reach the
    ceiling", never a disagreement about where the surface is."""
    layout = _real_layout()
    layout.shapes[1] = BuiltShape(
        role=ROLE_PRIMARY_PARALLEL, polygon=_ASIDE, ref="V",
        altitude_high=101.0, altitude_low=101.0)
    assert V.check_eat_ceiling(layout) == []


def test_reader_is_gate_guarded(monkeypatch):
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", False)
    assert V.check_eat_ceiling(_real_layout()) == []


def test_gate_off_leaves_verify_output_untouched(monkeypatch, tmp_path):
    _quiet_other_readers(monkeypatch)
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", False)
    log = tmp_path / "verify_off.log"
    counts = V.verify_and_log(_real_layout(), "KTST", str(log))
    assert "eat_ceiling" not in counts
    text = log.read_text() if log.exists() else ""
    assert "EAT-CEILING" not in text


def test_gate_on_counts_and_logs_the_finding(monkeypatch, tmp_path):
    _quiet_other_readers(monkeypatch)
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", True)
    log = tmp_path / "verify_on.log"
    counts = V.verify_and_log(_real_layout(), "KTST", str(log))
    assert counts["eat_ceiling"] > 0
    assert "EAT-CEILING" in log.read_text()


def test_gate_on_without_a_store_is_silent(monkeypatch, tmp_path):
    _quiet_other_readers(monkeypatch)
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", True)
    layout = _real_layout()
    del layout.eat_ceiling_presolve
    log = tmp_path / "verify_nostore.log"
    counts = V.verify_and_log(layout, "KTST", str(log))
    assert counts["eat_ceiling"] == 0
    assert "EAT-CEILING" not in (log.read_text() if log.exists() else "")


# ══════════════════════════════════════════════════════════════════════
# THE CONTRADICTION GUARD — an EAT pin never contradicts a senior hard
# anchor within route budget (docs/specs/
# eat-anchor-contradiction-guard-spec.md)
# ══════════════════════════════════════════════════════════════════════
# THE GEOMETRY IS KSTJ's, from the SQ1 interventional attribution: the
# rect pinned 241.8184 m into junction nodes at ANOTHER runway's
# threshold, 5.692 m below the RW35 CIFP floor anchor 247.510 over
# 0.93-1.24 m of route budget, which inverted the final band at 31 nodes
# and dropped the whole KSTJ patch from every +39-095 build.
_KSTJ_ANCHOR = 100          # the RW35 CIFP floor anchor node
_KSTJ_ANCHOR_V = 247.510
_KSTJ_PIN_V = 241.8184
#: 100 --0.93-- 201 --0.31-- 200 : route budgets 0.93 m and 1.24 m, the
#: two the attribution named.
_KSTJ_ADJ = {
    _KSTJ_ANCHOR: [(201, 0.93)],
    201: [(_KSTJ_ANCHOR, 0.93), (200, 0.31)],
    200: [(201, 0.31)],
    # a sibling crossing node in its OWN component: the anchors do not
    # reach it, so it has no bound and its pin stands (refusal is per
    # node, never per rect).
    300: [(301, 0.40)],
    301: [(300, 0.40)],
}


def _kstj_pins():
    return {200: _KSTJ_PIN_V, 201: _KSTJ_PIN_V, 300: _KSTJ_PIN_V}


class TestEatPinContradictionGuard:
    """Twin (a): the KSTJ shape."""

    def test_the_guard_refuses_the_pins_that_contradict_the_threshold(self):
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        refused = SV.eat_pin_contradiction_refusals(
            _kstj_pins(), _KSTJ_ADJ,
            {**_kstj_pins(), _KSTJ_ANCHOR: _KSTJ_ANCHOR_V})
        assert set(refused) == {200, 201}, (
            "the two nodes inside the anchor's reach are refused; the "
            "sibling the anchors cannot reach keeps its pin")
        for i in (200, 201):
            assert refused[i]["side"] == "floor"
            assert refused[i]["witness"] == _KSTJ_ANCHOR
        # 247.510 − 0.93 = 246.580 floor at 201 ⇒ 4.7616 m short;
        # 247.510 − 1.24 = 246.270 floor at 200 ⇒ 4.4516 m short.
        assert refused[201]["excess_m"] == pytest.approx(4.7616, abs=1e-4)
        assert refused[200]["excess_m"] == pytest.approx(4.4516, abs=1e-4)
        assert refused[201]["route_budget_m"] == pytest.approx(0.93)
        assert refused[200]["route_budget_m"] == pytest.approx(1.24)

    def test_the_predicate_is_the_seat_guards_own_implementation(self):
        """THE SAME PREDICATE THROUGH THE SAME IMPLEMENTATION (spec):
        the refusal is exactly ``AnchorEnvelope.violation`` on the
        law-graph budget oracle.  A second spelling of ``pin + cap·route
        < anchor`` is the census-wrapper defect class."""
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        from auto_patch.elevation_per_surface.route_profile \
            .law_graph_budget import build_anchor_envelope
        env = build_anchor_envelope(_KSTJ_ADJ, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V})
        refused = SV.eat_pin_contradiction_refusals(
            _kstj_pins(), _KSTJ_ADJ, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V})
        for i, row in refused.items():
            assert row == env.violation(i, _KSTJ_PIN_V, tol=0.01)

    def test_a_pin_never_bounds_itself_or_its_sibling(self):
        """The law asks whether the pin contradicts a SENIOR anchor.  A
        pin is junior by construction, so the pins are removed from the
        anchor set before the envelope is built.

        THE CONFIGURATION THAT SEPARATES THE TWO READINGS is the one the
        rect builder already produces: two crossing segments pinned at
        their OWN ``D_mid`` regulation values, close together on the
        graph.  Both sit comfortably inside the senior anchor's box, so
        the law refuses neither — but each is 10 m from the other across
        0.5 m of budget, so a guard that let a pin act as an anchor would
        refuse BOTH on the authority of a value that is itself only a
        junior derivative of the runway end."""
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        adj = {400: [(401, 0.5), (402, 10.0)],
               401: [(400, 0.5), (402, 10.0)],
               402: [(400, 10.0), (401, 10.0)]}
        pins = {400: 240.0, 401: 250.0}
        # ``hard_values`` is shaped as the solve passes it: EVERY hard
        # node on the graph, and a stamped pin IS hard — so the exclusion
        # has to happen inside the guard, where the law is.
        assert SV.eat_pin_contradiction_refusals(
            pins, adj, {**pins, 402: 245.0}) == {}
        # every hard node IS a pin ⇒ no senior anchor ⇒ nothing to refuse
        assert SV.eat_pin_contradiction_refusals(
            _kstj_pins(), _KSTJ_ADJ, dict(_kstj_pins())) == {}

    def test_no_graph_and_no_pins_refuse_nothing(self):
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        assert SV.eat_pin_contradiction_refusals(
            {}, _KSTJ_ADJ, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V}) == {}
        assert SV.eat_pin_contradiction_refusals(
            _kstj_pins(), {}, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V}) == {}
        assert SV.eat_pin_contradiction_refusals(
            _kstj_pins(), _KSTJ_ADJ, {}) == {}

    def test_the_released_nodes_no_longer_invert_the_band(self):
        """The pre-registered outcome: after the refusal the node's own
        value sits INSIDE the senior envelope — the inversion the pin
        authored is gone, and it is gone because the pin is, not because
        anything moved a runway."""
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        from auto_patch.elevation_per_surface.route_profile \
            .law_graph_budget import build_anchor_envelope
        env = build_anchor_envelope(_KSTJ_ADJ, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V})
        n = 302
        elev = [0.0] * n
        base_hard = [False] * n
        have_initial = [False] * n
        seed = 247.4          # the real 1 m-lidar ground at those nodes
        layout = PavementLayout(icao="KSTJ", anchor=(39.77, -94.91))
        layout._eat_anchor_pin_prev = {i: (seed, True)
                                       for i in _kstj_pins()}
        layout._eat_anchor_pin_idx = _kstj_pins()
        layout._seam_pin_idx = set(_kstj_pins())
        for i, v in _kstj_pins().items():
            elev[i] = v
            base_hard[i] = True
        refused = SV.eat_pin_contradiction_refusals(
            _kstj_pins(), _KSTJ_ADJ, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V})
        assert SV.release_refused_eat_pins(
            layout, refused, elev, base_hard, have_initial) == 2
        for i in (200, 201):
            assert elev[i] == pytest.approx(seed)
            assert not base_hard[i], "a refused pin is not a truth anchor"
            assert i not in layout._eat_anchor_pin_idx, (
                "a refused pin is not registered as a runway-class "
                "reach-band anchor either")
            assert i not in layout._seam_pin_idx
            assert env.violation(i, elev[i], tol=0.01) is None
        # the sibling the guard did not refuse is untouched
        assert elev[300] == pytest.approx(_KSTJ_PIN_V)
        assert base_hard[300]
        assert layout._eat_anchor_pin_idx == {300: _KSTJ_PIN_V}
        assert 300 in layout._seam_pin_idx

    def test_a_node_with_no_snapshot_is_left_alone(self):
        """Inventing a seed for a node the seeder did not record would be
        the same class of defect the pin itself committed."""
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        layout = PavementLayout(icao="KSTJ", anchor=(39.77, -94.91))
        layout._eat_anchor_pin_prev = {}
        layout._eat_anchor_pin_idx = {200: _KSTJ_PIN_V}
        elev = [0.0] * 201
        elev[200] = _KSTJ_PIN_V
        base_hard = [False] * 201
        base_hard[200] = True
        assert SV.release_refused_eat_pins(
            layout, {200: {}}, elev, base_hard, None) == 0
        assert elev[200] == pytest.approx(_KSTJ_PIN_V)
        assert base_hard[200]


class TestTheRefusalIsCarriedAcrossRebuilds:
    """The verdict is priced ONCE (only the solve has the graph) and
    CARRIED to every later ``_seed_elevations`` by CANONICAL POINT."""

    def test_a_carried_verdict_makes_the_seeder_skip_the_node(self):
        layout = _layout(_IN)
        _nodes, b2i, _elev, _hard = _seed(layout)
        idx = _taxi_idx(layout, b2i, _IN)
        cps = layout.canonical_points
        refused_xy = list(_IN.exterior.coords)[:2]
        layout._eat_pin_refused_keys = {
            cps.get_or_add(float(x), float(y)) for (x, y) in refused_xy}
        # a fresh seeding pass, exactly as the final projection does it
        layout2 = _layout(_IN)
        layout2.canonical_points = cps
        layout2._eat_pin_refused_keys = layout._eat_pin_refused_keys
        nodes2, b2i2 = SP._build_node_list(layout2)
        elev2, hard2, _h2 = SP._seed_elevations(layout2, nodes2, b2i2)
        skipped = {b2i2[cps.get_or_add(float(x), float(y))]
                   for (x, y) in refused_xy}
        for i in skipped:
            assert not hard2[i], (
                "a node the guard refused must never be re-pinned by a "
                "later pass — the writeback clamp rescuing it is not the "
                "law holding")
            assert i not in layout2._eat_anchor_pin_idx
        kept = set(_taxi_idx(layout2, b2i2, _IN)) - skipped
        assert kept, "the fixture must still leave lawful siblings"
        for i in kept:
            assert hard2[i]
            assert i in layout2._eat_anchor_pin_idx
        assert len(idx) == 4

    def test_the_verdict_is_keyed_by_point_never_by_node_index(self):
        """Index keys are meaningful inside ONE ``_build_node_list`` call
        only; every later pass rebuilds on a GROWN layout."""
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        layout = _layout(_IN)
        nodes, b2i, _elev, _hard = _seed(layout)
        idx = _taxi_idx(layout, b2i, _IN)[:2]
        keys = SV.publish_eat_refusal_keys(layout, {i: {} for i in idx},
                                           nodes)
        assert keys == layout._eat_pin_refused_keys
        assert not (keys & set(range(len(nodes)))) or all(
            not isinstance(k, int) for k in keys), (
            "a node index must never end up in the point-keyed set")
        for i in idx:
            assert layout.canonical_points.get(
                float(nodes[i][0]), float(nodes[i][1])) in keys

    def test_no_verdict_carries_nothing(self):
        layout = _layout(_IN)
        _nodes, b2i, _elev, hard = _seed(layout)
        assert not hasattr(layout, "_eat_pin_refused_keys")
        assert all(hard[i] for i in _taxi_idx(layout, b2i, _IN))


class TestLawfulEatRectIsUnchanged:
    """Twin (b): a lawful EAT rect pins identically to today."""

    def test_the_seeder_publishes_the_pre_pin_snapshot(self):
        """The refusal restores the node to the seed the seeder found —
        so the seeder records it, for EVERY pin, lawful or not."""
        layout = _layout(_IN)
        _nodes, b2i, elev, _hard = _seed(layout)
        idx = set(_taxi_idx(layout, b2i, _IN))
        assert set(layout._eat_anchor_pin_prev) == idx
        for i in idx:
            prev_elev, prev_have = layout._eat_anchor_pin_prev[i]
            assert prev_elev != pytest.approx(_IN_PIN), (
                "the snapshot is the PRE-pin value, not the pin")
            assert isinstance(prev_have, bool)
            assert elev[i] == pytest.approx(_IN_PIN)

    def test_a_lawful_rect_is_refused_nothing_and_moves_nothing(self):
        """The senior anchor sits within cap of the regulation value, so
        the guard refuses nothing and the pinned state is byte-identical
        to the un-guarded build."""
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        layout = _layout(_IN)
        _nodes, b2i, elev, hard = _seed(layout)
        pins = dict(layout._eat_anchor_pin_idx)
        idx = sorted(pins)
        # a senior anchor one hop away at the pin's own value: lawful by
        # construction, whatever the cap.
        anchor = max(idx) + 1000
        adj = {anchor: [(idx[0], 0.5)], idx[0]: [(anchor, 0.5)]}
        adj.update({i: [(idx[0], 0.5)] for i in idx[1:]})
        adj[idx[0]] = adj[idx[0]] + [(i, 0.5) for i in idx[1:]]
        before = (list(elev), list(hard), dict(pins),
                  set(layout._seam_pin_idx))
        refused = SV.eat_pin_contradiction_refusals(
            pins, adj, {anchor: _IN_PIN})
        assert refused == {}
        assert SV.release_refused_eat_pins(
            layout, refused, elev, hard, None) == 0
        assert (list(elev), list(hard), dict(layout._eat_anchor_pin_idx),
                set(layout._seam_pin_idx)) == before

    def test_the_guard_runs_before_the_pins_hold_any_authority(self):
        """THE WIRING, which no unit call can show: inside
        ``solve_route_profile`` the guard must sit AFTER the airside view
        of the unified graph it prices on and BEFORE the runway-flex
        pass, the runway-class anchor registration and the hard-truth
        publication — a refused pin that reached any of those would
        already have authored a band."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        src = inspect.getsource(SV.solve_route_profile)
        at_graph = src.index("u_spine_adj_airside = adj_without_pairs")
        at_guard = src.index("eat_pin_contradiction_refusals(")
        at_flex = src.index("_apply_runway_flex_hook(")
        # The registration is ``register_eat_anchors`` since the
        # refusal-contributes-nothing round extracted it (so the twins
        # can drive the rule instead of a transcription); the WIRING
        # question — where it sits relative to the guard — is unchanged.
        at_anchor = src.index("register_eat_anchors(G,")
        at_truth = src.index("layout._seed_hard_truth_values")
        assert at_graph < at_guard < at_flex < at_anchor < at_truth

    def test_the_guard_needs_no_env_flag(self):
        """No new switch: ``EAT_SURFACE_CEILING`` stays the feature's
        only gate, and the guard is part of the feature."""
        import os
        assert not any(k.startswith("O4_EAT_") and
                       k != "O4_EAT_SURFACE_CEILING" for k in os.environ)
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        import inspect
        src = inspect.getsource(SV.eat_pin_contradiction_refusals)
        assert "environ" not in src


class TestGuardRefusalLine:
    """Twin (c): the ONE loud line."""

    def test_the_line_carries_count_worst_shortfall_and_anchor(self):
        from auto_patch.elevation_per_surface.route_profile import solve as SV
        refused = SV.eat_pin_contradiction_refusals(
            _kstj_pins(), _KSTJ_ADJ, {_KSTJ_ANCHOR: _KSTJ_ANCHOR_V})
        worst_node, worst = max(refused.items(),
                                key=lambda r: r[1]["excess_m"])
        worst = dict(worst, pin_m=_KSTJ_PIN_V)
        line = SV.format_eat_guard_line(
            "KSTJ", 2, 3, worst_node, worst, _KSTJ_ANCHOR_V)
        assert line.count("\n") == 0, "ONE loud line, not a report"
        assert line.lstrip().startswith("[eat-anchor-rect] KSTJ:")
        assert "2 of 3 pin(s) REFUSED" in line          # nodes refused
        assert "node 201" in line                        # worst node
        assert "241.818" in line                         # its pin
        assert "4.762 m past its floor 246.580" in line  # worst shortfall
        assert "witness anchor 100 = 247.510" in line    # anchor identity
        assert "route budget 0.9300 m" in line
