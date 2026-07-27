"""END-AROUND TAXIWAY (EAT) departure-surface ceiling — owner ruling
2026-07-27.

An end-around taxiway loops beyond a runway end and crosses the extended
centreline, so an aircraft on it stands under the departure / take-off-climb
surface.  The surface must clear the aircraft's TAIL, which forces the EAT
PAVEMENT below the runway-end elevation (KATL taxiway Victor ≈ −9 m).

This file pins:

  * the LAW — ``grade_law.eat_pavement_ceiling`` at the KCLT-class numbers
    (D = 460 m, code E: FAA −8.6 m, EASA −12.1 m off the runway end);
  * the REGION selector — FAA for North America (ICAO K/C/P/M), EASA
    everywhere else;
  * the constraint-builder SCOPING — the 300 m minimum crossing distance
    and the 90 m corridor half-width, and the one-sided edge form;
  * the GATE — off ⇒ no edges, no findings, and verify output with no
    trace of the feature.

``EAT_SURFACE_CEILING_ENABLED`` currently defaults OFF (see the config
comment: the reach-envelope Dijkstra in ``one_solve`` cannot yet carry a
pavement↔pavement negative slab — measured at KCLT), so the tests that
exercise the machinery force the gate ON; the gate-OFF tests force it
OFF explicitly rather than relying on the default, so neither direction
silently stops testing anything when the default flips.

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
    """Every test here states the gate it wants; today's default is OFF
    and must not silently decide what these tests measure.  The gate-OFF
    tests re-patch it to False."""
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", True)


def test_gate_defaults_off_pending_the_reach_envelope_fix():
    """The law is complete and unit-proven, but a pavement↔pavement
    negative slab blows up ``one_solve``'s reach-envelope Dijkstra
    (measured KCLT: 228.9 s with the constraints neutered → killed at
    15 min CPU / 20 GB with them active).  Until that is fixed in the
    solver the gate ships OFF — flip this assertion WITH the default,
    never before it.

    Read from the source line, not the imported value: the autouse
    fixture above (and any ``O4_*`` override in the developer's shell)
    deliberately moves the imported one."""
    import re
    from pathlib import Path
    src = (Path(cfg.__file__)).read_text(encoding="utf-8")
    m = re.search(r'O4_EAT_SURFACE_CEILING",\s*"(\d)"', src)
    assert m is not None, "the gate's env default line moved"
    assert m.group(1) == "0"


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


# ── the constraint builder ───────────────────────────────────────────
class _FakeShape:
    def __init__(self, role, polygon, ref=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.node_altitudes = node_altitudes


class _FakeLayout:
    def __init__(self, shapes):
        self.shapes = shapes
        self.canonical_points = CanonicalPointRegistry()


# Runway lying along −x, its EAST end (the DER) at x = 0.
_RWY = Polygon([(-1000.0, -22.0), (0.0, -22.0), (0.0, 22.0),
                (-1000.0, 22.0)])
_ANCHOR_XY = (0.0, -22.0)          # a runway ring vertex at the end


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
    }


# Three candidate taxi rects: one too close to the end, one squarely in
# the corridor, one far off to the side.
_NEAR = _rect(40.0, 60.0, -10.0, 10.0)            # s ≈ 50 m
_IN = _rect(390.0, 410.0, -10.0, 10.0)            # s ≈ 400 m, |q| ≤ 10
_ASIDE = _rect(390.0, 410.0, 190.0, 210.0)        # s ≈ 400 m, |q| ≥ 190


def _layout(*taxi_polys, roles=None):
    roles = roles or [ROLE_PRIMARY_PARALLEL] * len(taxi_polys)
    shapes = [_FakeShape(ROLE_RUNWAY, _RWY)]
    shapes += [_FakeShape(role, poly)
               for role, poly in zip(roles, taxi_polys)]
    layout = _FakeLayout(shapes)
    layout.eat_ceiling_presolve = [_end_spec()]
    return layout


def _build(layout):
    _nodes, b2i = SP._build_node_list(layout)
    return b2i, SP._build_eat_ceiling_constraints(layout, b2i)


class TestScoping:
    def test_pavement_near_the_end_takes_no_edge(self):
        """A node at s = 50 m is an ordinary runway-end connector, not an
        end-around taxiway — the ceiling there would be −18.6 m."""
        _b2i, (scs, idx, counts) = _build(_layout(_NEAR))
        assert scs == []
        assert idx == set()
        assert counts == (0, 0, 0)

    def test_pavement_in_the_corridor_takes_one_edge_per_node(self):
        b2i, (scs, idx, counts) = _build(_layout(_IN))
        assert len(scs) == 1
        entry = scs[0]
        assert entry["role"] == ROLE_PRIMARY_PARALLEL
        assert entry["ref"] == SP.REF_EAT_CEILING
        assert len(idx) == 4
        assert len(entry["edges"]) == 4
        assert counts == (4, 0, 0)

    def test_pavement_off_to_the_side_takes_no_edge(self):
        """|q| = 190-210 m is outside the 90 m corridor half-width."""
        _b2i, (scs, idx, counts) = _build(_layout(_ASIDE))
        assert scs == []
        assert idx == set()
        assert counts == (0, 0, 0)

    def test_only_the_corridor_shape_is_governed(self):
        _b2i, (scs, idx, _c) = _build(_layout(_NEAR, _IN, _ASIDE))
        assert len(scs) == 1
        assert len(idx) == 4

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


class TestEdgeForm:
    def test_edges_are_one_sided_intervals_to_the_end_anchor(self):
        layout = _layout(_IN)
        b2i, (scs, _idx, _c) = _build(layout)
        cps = layout.canonical_points
        anchor = b2i[cps.get_or_add(*_ANCHOR_XY)]
        nodes, _ = SP._build_node_list(layout)
        for (i, j, lo, hi) in scs[0]["edges"]:
            assert j == anchor
            assert lo is None, "nothing forbids an EAT sitting LOWER"
            s = nodes[i][0]           # outward = +x, p0 = origin
            assert hi == pytest.approx(
                eat_pavement_ceiling(s, cfg.EAT_FAA_DEPARTURE_SLOPE,
                                     cfg.EAT_FAA_SETBACK_M,
                                     cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"]),
                abs=1e-9)
            assert hi < 0.0

    def test_the_edge_constrains_a_PAVEMENT_variable(self):
        """Unlike the RESA cut this law DELIBERATELY binds pavement — it
        is the taxiway itself that must go down."""
        layout = _layout(_IN)
        b2i, (scs, _idx, _c) = _build(layout)
        first_terrain = layout._terrain_host_yield_first_index
        for (i, j, _lo, _hi) in scs[0]["edges"]:
            assert i < first_terrain
            assert j < first_terrain

    def test_a_shared_node_takes_no_second_edge(self):
        """Two slabs on one variable is the measured B2 ping-pong class:
        the first claimant governs."""
        layout = _layout(_IN, _IN)
        _b2i, (scs, idx, counts) = _build(layout)
        assert len(idx) == 4
        assert sum(len(e["edges"]) for e in scs) == 4
        assert counts[1] == 4          # the second ring's four re-claims

    def test_crossing_corridors_take_the_lowest_ceiling(self):
        """Two ends whose corridors overlap: the most restrictive
        surface governs, deterministically."""
        layout = _layout(_IN)
        far = dict(_end_spec(), p0=(-200.0, 0.0))     # s is 200 m larger
        layout.eat_ceiling_presolve = [_end_spec(), far]
        _b2i, (scs, _idx, _c) = _build(layout)
        nodes, _ = SP._build_node_list(layout)
        for (i, _j, _lo, hi) in scs[0]["edges"]:
            near_off = SP.eat_ceiling_offset(
                layout.eat_ceiling_presolve[0], *nodes[i])
            far_off = SP.eat_ceiling_offset(far, *nodes[i])
            assert hi == pytest.approx(min(near_off, far_off))

    def test_service_roads_and_runways_are_not_governed(self):
        """A service road carries no aircraft tail; the runway profile is
        HARD and an EAT ceiling must never bend it."""
        assert ROLE_SERVICE_ROAD not in SP.EAT_CEILING_ROLES
        assert ROLE_RUNWAY not in SP.EAT_CEILING_ROLES
        assert ROLE_APRON in SP.EAT_CEILING_ROLES
        _b2i, (scs, idx, _c) = _build(
            _layout(_IN, roles=[ROLE_SERVICE_ROAD]))
        assert scs == [] and idx == set()


# ── the projection actually depresses the pavement ───────────────────
def test_projection_drives_the_taxiway_under_the_surface():
    """THE point of the law: with the runway end HARD, projecting the
    solved surface onto the one-sided slab pulls the EAT pavement down to
    the ceiling — from +1 m above the runway end (the pre-law symptom) to
    a whole tail height below the departure surface."""
    from auto_patch.elevation_per_surface.route_profile.one_solve import (
        feasibility_project)
    layout = _layout(_IN)
    nodes, b2i = SP._build_node_list(layout)
    scs, idx, _c = SP._build_eat_ceiling_constraints(layout, b2i)
    anchor = b2i[layout.canonical_points.get_or_add(*_ANCHOR_XY)]
    end_elev = 221.5

    elev = [end_elev] * len(nodes)
    for i in idx:
        elev[i] = end_elev + 0.9          # the pre-law KCLT symptom
    feasibility_project(elev, scs, {anchor}, force_scalar=True)

    assert elev[anchor] == pytest.approx(end_elev, abs=1e-12), \
        "the runway end is HARD — the ceiling must never bend it"
    q = cfg.EMIT_QUANTIZATION_MARGIN_M
    for i in sorted(idx):
        s = nodes[i][0]
        ceiling = end_elev + eat_pavement_ceiling(
            s, cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M,
            cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"])
        assert elev[i] <= ceiling + 1e-6
        assert elev[i] == pytest.approx(ceiling, abs=q + 1e-6)
        assert elev[i] < end_elev - 9.0    # a real, KATL-scale depression


def test_projection_leaves_a_compliant_taxiway_alone():
    """One-sided: nothing forbids an EAT sitting LOWER than the surface
    demands, so a taxiway already under the ceiling does not move."""
    from auto_patch.elevation_per_surface.route_profile.one_solve import (
        feasibility_project)
    layout = _layout(_IN)
    nodes, b2i = SP._build_node_list(layout)
    scs, idx, _c = SP._build_eat_ceiling_constraints(layout, b2i)
    anchor = b2i[layout.canonical_points.get_or_add(*_ANCHOR_XY)]
    elev = [221.5] * len(nodes)
    for i in idx:
        elev[i] = 221.5 - 40.0             # far below the surface
    before = list(elev)
    feasibility_project(elev, scs, {anchor}, force_scalar=True)
    assert elev == pytest.approx(before, abs=1e-12)


def test_no_store_means_no_constraints():
    layout = _FakeLayout([])
    assert SP._build_eat_ceiling_constraints(layout, {}) == (
        [], set(), (0, 0, 0))


def test_gate_off_produces_zero_edges(monkeypatch):
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", False)
    layout = _layout(_IN)
    _nodes, b2i = SP._build_node_list(layout)
    assert SP._build_eat_ceiling_constraints(layout, b2i) == (
        [], set(), (0, 0, 0))


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
