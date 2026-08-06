"""THE FAN-RAMP LAW — the generation-binding twins.

Owner ruling ``docs/RULINGS.md`` 2026-08-05 (commit 21f0980), all four
clarifications answered:

  1. RAMP CAP: 5 % — the groundside-pavement class; no new constant.
  2. FORM PRECEDENCE: ramps FIRST; a declared wall/step is the FALLBACK
     only where 5 % cannot span the demand within the zone.
  3. ZONE: bounded by adjacent buildings' frontage chords, the back apron
     edge, and standard clearance from every spine corridor.
  4. SCOPE: GENERAL — every apron with building frontage.

And the composition clause: "aircraft-movement surfaces (spine corridors
+ frontage chords + stand entries) hold the strict apron cap, always …
no ramp, joint, or wall may touch any movement surface."

The twins drive the REAL zone builder and the REAL cap rewriters on
synthetic layouts — the same discipline the terrace twins keep — and the
last one asserts the LOCKSTEP: the solver's predicate and
``check_grade``'s predicate are the same question asked of the same
geometry, which is the only thing that stops a lawful ramp being
censused as a violation (the named precedent in this repo's CLAUDE.md).
"""
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch.config import APRON_MAX_GRADE, GROUNDSIDE_MAX_GRADE
from auto_patch.elevation_per_surface.route_profile import apron_terrace as AT
from auto_patch.layout import BuiltShape


class _Centerline:
    def __init__(self, pts):
        self.line = LineString(pts)


class _Layout:
    def __init__(self, shapes, centerlines=()):
        self.shapes = list(shapes)
        self.apt_taxi_centerlines = [_Centerline(p) for p in centerlines]
        self.anchor = (0.0, 0.0)

    def m_to_ll(self, x, y):
        return (30.0 + y / 111320.0, 31.0 + x / 96000.0)


def _rect(x0, y0, x1, y1, role, ref=""):
    return BuiltShape(
        polygon=Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]),
        role=role, ref=ref)


def _terminal_apron():
    """One 400 x 300 m apron, a taxi spine along its far edge, and TWO
    terminal buildings standing on the near (back) edge with a gap
    between them.

    The frontage chords run building → spine, so the ground BETWEEN them
    at the back edge — clear of the spine corridor, both chords and both
    pads — is the fan-ramp zone the ruling describes.
    """
    apron = _rect(0.0, 0.0, 400.0, 300.0, "apron", "apron_fan")
    left = _rect(20.0, 5.0, 120.0, 55.0, "building", "T1")
    right = _rect(280.0, 5.0, 380.0, 55.0, "building", "T2")
    spine = [(-50.0, 260.0), (450.0, 260.0)]
    return _Layout([apron, left, right], centerlines=[spine]), apron


# ── 1. THE ZONE ─────────────────────────────────────────────────────

def test_a_zone_is_born_between_two_adjacent_frontages():
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    assert plan.zones, "no fan-ramp zone on a two-terminal apron"
    assert all(z["cap"] == GROUNDSIDE_MAX_GRADE for z in plan.zones)
    assert all(z["buildings"] >= 2 for z in plan.zones)
    assert plan.stats["zone_area_m2"] > 0.0


def test_one_building_is_not_ADJACENT_buildings():
    """"Between adjacent buildings" needs two of them; a single stand's
    surroundings are ordinary apron."""
    apron = _rect(0.0, 0.0, 400.0, 300.0, "apron")
    only = _rect(20.0, 5.0, 120.0, 55.0, "building", "T1")
    layout = _Layout([apron, only],
                     centerlines=[[(-50.0, 260.0), (450.0, 260.0)]])
    assert AT.plan_fan_ramp_zones(layout, icao="TEST").zones == []


def test_an_apron_with_no_corridor_declares_nothing():
    """No corridors ⇒ no frontage chords, no movement surfaces to be
    clear OF, and nothing this law can be about."""
    apron = _rect(0.0, 0.0, 400.0, 300.0, "apron")
    layout = _Layout([apron,
                      _rect(20.0, 5.0, 120.0, 55.0, "building", "T1"),
                      _rect(280.0, 5.0, 380.0, 55.0, "building", "T2")])
    assert AT.plan_fan_ramp_zones(layout, icao="TEST").zones == []


def test_the_zone_is_BETWEEN_the_buildings_not_merely_near_them():
    """The bound the first cut of this law did not have.

    ``apron − cover`` adjacent to two pads came out as 77 142 m² of this
    fixture's 120 000 m² apron — one component wrapping the whole
    surface through the 5 m strip behind the pads — and a plain buffered
    hull still spilled sideways past each building onto the apron's outer
    corners.  The zone is bounded by the two buildings it fans between:
    laterally by their own span, in depth by the gap they fan across.
    """
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    assert plan.zones
    total = sum(z["area_m2"] for z in plan.zones)
    assert total < 0.5 * apron.polygon.area, (
        f"the fan zones claim {total:,.0f} m² of a "
        f"{apron.polygon.area:,.0f} m² apron")
    for z in plan.zones:
        x0, y0, x1, y1 = z["polygon"].bounds
        # the pads span x 20..380 — nothing beside them qualifies
        assert x0 >= 20.0 - 1e-6 and x1 <= 380.0 + 1e-6
        # and it reaches the BACK edge, which is where the seats are
        assert y0 <= 1.0


def test_no_zone_touches_a_movement_surface():
    """THE STRUCTURAL GUARANTEE.  The zone is ``apron − corridor_cover``,
    and the cover already carries every spine corridor, frontage chord,
    stand entry and pad buffered by the standard clearance — so this
    cannot fail without the cover itself being wrong."""
    layout, _apron = _terminal_apron()
    cover = AT.corridor_cover(layout)
    plan = AT.plan_fan_ramp_zones(layout, cover, icao="TEST")
    assert plan.zones
    for z in plan.zones:
        assert not z["polygon"].intersects(cover.buffer(-1e-9)), (
            "a declared fan-ramp zone overlaps an aircraft-movement "
            "surface")


# ── 2. THE CAP, AND WHO KEEPS THE STRICT ONE ────────────────────────

def test_a_pair_inside_a_zone_is_raised_to_the_ramp_cap():
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    z = max(plan.zones, key=lambda r: r["area_m2"])
    (cx, cy) = z["polygon"].representative_point().coords[0]
    # A short chord that stays inside the zone.
    node_xy = {0: (cx - 5.0, cy), 1: (cx + 5.0, cy)}
    d = 10.0
    edges = [(0, 1, APRON_MAX_GRADE * d)]
    entry = {"shape_id": id(apron), "nodes": [0, 1], "edges": edges}
    n = AT.apply_fan_ramp_caps(plan, [entry], node_xy)
    assert n == 1
    assert entry["edges"][0][2] == pytest.approx(GROUNDSIDE_MAX_GRADE * d)


def test_a_pair_crossing_out_of_the_zone_keeps_the_strict_apron_cap():
    """"Movement surfaces hold the strict apron cap, always."  A chord
    with one end outside — or one that merely passes over a corridor —
    is not a chord inside the zone."""
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    z = max(plan.zones, key=lambda r: r["area_m2"])
    (cx, cy) = z["polygon"].representative_point().coords[0]
    node_xy = {0: (cx, cy), 1: (cx, 295.0)}      # out through the spine
    d = math.dist(node_xy[0], node_xy[1])
    entry = {"shape_id": id(apron), "nodes": [0, 1],
             "edges": [(0, 1, APRON_MAX_GRADE * d)]}
    assert AT.apply_fan_ramp_caps(plan, [entry], node_xy) == 0
    assert entry["edges"][0][2] == pytest.approx(APRON_MAX_GRADE * d)


def test_the_rewrite_never_TIGHTENS_an_edge():
    """RELAXING ONLY — the zone cap is an upper bound the ruling GRANTS;
    an edge already carrying a looser budget keeps it."""
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    z = max(plan.zones, key=lambda r: r["area_m2"])
    (cx, cy) = z["polygon"].representative_point().coords[0]
    node_xy = {0: (cx - 5.0, cy), 1: (cx + 5.0, cy)}
    generous = 99.0
    entry = {"shape_id": id(apron), "nodes": [0, 1],
             "edges": [(0, 1, generous)]}
    AT.apply_fan_ramp_caps(plan, [entry], node_xy)
    assert entry["edges"][0][2] == pytest.approx(generous)


def test_both_edge_sets_carry_the_same_law():
    """The unified graph is projected SEPARATELY from
    ``shape_constraints``: relief granted only in one is taken straight
    back by the other (the two-instruments trap in its edge-set
    costume)."""
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    z = max(plan.zones, key=lambda r: r["area_m2"])
    (cx, cy) = z["polygon"].representative_point().coords[0]
    node_xy = {0: (cx - 5.0, cy), 1: (cx + 5.0, cy)}
    u_edges, n = AT.apply_fan_ramp_caps_to_edges(
        plan, [(0, 1, APRON_MAX_GRADE * 10.0)], node_xy)
    assert n == 1
    assert u_edges[0][2] == pytest.approx(GROUNDSIDE_MAX_GRADE * 10.0)


# ── 3. PRECEDENCE: ramps first, wall fallback ───────────────────────

def _pinned(z_fn):
    def _env(x, y):
        z = z_fn(x, y)
        return None if z is None else (float(z), float(z))
    return _env


def test_relief_a_ramp_can_span_buys_no_wall():
    """Owner answer 2, the FIRST half.  A demand the 5 % zone spans is
    answered by the ramp, so the wall/step law sees nothing left."""
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    z = max(plan.zones, key=lambda r: r["area_m2"])
    sub = AT._fan_for(plan, apron)
    assert sub is not None
    # A 2 %-pinned envelope across the zone: over the zone's own span
    # that is well past the 1 % apron cap and well inside 5 %.
    env = _pinned(lambda x, y: 100.0 + 0.02 * x)
    with_ramp = AT._envelope_demand(z["polygon"], env, APRON_MAX_GRADE,
                                    fan=sub)
    without = AT._envelope_demand(z["polygon"], env, APRON_MAX_GRADE)
    assert without["excess_m"] > 0.0, "fixture does not demand relief"
    assert with_ramp["excess_m"] < without["excess_m"], (
        "the ramp cap did not absorb any of the demand")
    assert with_ramp["excess_m"] <= 0.0, (
        "5 % spans this demand — nothing should be left for a wall")


def test_relief_a_ramp_cannot_span_still_reaches_the_wall_law():
    """Owner answer 2, the SECOND half.  The fallback is a fallback, not
    a deletion: an 8 % demand is past the ramp cap and what remains is
    still the wall/step law's to answer."""
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    z = max(plan.zones, key=lambda r: r["area_m2"])
    sub = AT._fan_for(plan, apron)
    env = _pinned(lambda x, y: 100.0 + 0.08 * x)
    with_ramp = AT._envelope_demand(z["polygon"], env, APRON_MAX_GRADE,
                                    fan=sub)
    assert with_ramp["excess_m"] > 0.0


def test_a_foreign_aprons_zone_never_licenses_this_apron():
    """The ground between two aprons is inside neither one's zone."""
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    other = _rect(1000.0, 0.0, 1100.0, 100.0, "apron", "elsewhere")
    assert AT._fan_for(plan, other) is None


# ── 4. THE LOCKSTEP — one declaration, two readers ──────────────────

def test_the_sidecar_round_trips_into_the_validators_own_reader():
    """The census must judge a zone pair at the zone cap.  The named
    precedent: a census that dropped ``terrace_joints_ll`` reported
    lawful declared terraces as violations."""
    import check_grade as CG
    layout, apron = _terminal_apron()
    layout._fan_ramp_plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    rows = AT.fan_ramp_zones_sidecar(layout)
    assert rows and all(r["cap"] == GROUNDSIDE_MAX_GRADE for r in rows)
    assert all(len(r["ring_ll"]) >= 3 for r in rows)

    # Back to metres through the validator's own converter, then ask the
    # validator's own predicate about a pair the SOLVER would relax.
    lat0, lon0 = layout.m_to_ll(0.0, 0.0)

    def ll_to_m(la, lo):
        return ((lo - lon0) * 96000.0, (la - lat0) * 111320.0)

    zones_m = CG._fan_ramp_zones_to_m(rows, ll_to_m)
    assert zones_m
    z = max(layout._fan_ramp_plan.zones, key=lambda r: r["area_m2"])
    (cx, cy) = z["polygon"].representative_point().coords[0]
    solver_cap = layout._fan_ramp_plan.pair_cap(
        cx - 5.0, cy, cx + 5.0, cy, APRON_MAX_GRADE)
    census_cap = CG._fan_ramp_pair_cap(zones_m, cx - 5.0, cy, cx + 5.0, cy)
    assert solver_cap == pytest.approx(GROUNDSIDE_MAX_GRADE)
    assert census_cap == pytest.approx(GROUNDSIDE_MAX_GRADE)


def test_the_new_sidecar_key_is_registered_with_a_reader():
    """Every emitted sidecar key must be law input or declared evidence —
    ``tests/test_harness.py`` twin-asserts it, and this names the one
    this law adds so a future reader cannot silently ignore it."""
    import check_grade as CG
    assert CG.SIDECAR_LAW_KEYS["fan_ramp_zones"] == "fan_ramp_zones_ll"


def test_the_zone_rows_survive_the_NON_QUIET_reporting_path():
    """Regression twin, and it earned its place.

    The zone rows grew from ``(polygon, cap)`` to
    ``(polygon, cap, bounds, prepared)`` when the reader was indexed, and
    the announce branch — which only runs when the census is NOT quiet —
    still destructured two.  Every census called with ``quiet=False`` on a
    patch carrying zones died with ``ValueError: too many values to
    unpack``; the harness census is quiet, so nothing caught it until the
    fixture-airport suite did.  Whatever shape the row takes, the report
    line has to be able to read a cap out of it.
    """
    import check_grade as CG
    layout, _apron = _terminal_apron()
    layout._fan_ramp_plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    rows = AT.fan_ramp_zones_sidecar(layout)
    zones_m = CG._fan_ramp_zones_to_m(rows, lambda la, lo: (lo, la))
    assert zones_m
    caps = sorted({row[1] for row in zones_m})
    assert caps == [GROUNDSIDE_MAX_GRADE]
    assert all(len(row) == len(zones_m[0]) for row in zones_m)


def test_a_patch_predating_the_law_is_judged_exactly_as_before():
    import check_grade as CG
    assert CG._fan_ramp_zones_to_m(None, lambda a, b: (a, b)) == []
    assert CG._fan_ramp_pair_cap([], 0.0, 0.0, 1.0, 1.0) is None


# ── 5. ACTIVATION — the zone is a SHAPE, not a region in one ────────
#
# The law above is correct and was INERT.  Measured on HECA's plateau
# build: 808 declared zones, 295 526 m² of movement-clear apron, and 170
# within-apron edges raised.  The cause is structural — the chord
# predicate can only raise a pair that EXISTS, an apron's solve variables
# are its RING vertices, and a fan-ramp zone is interior ground.  Of
# 10 255 within-apron census rows, 9 739 had neither endpoint in any zone
# and 9 were blocked by the whole-chord test.
#
# These twins bind the fix: the zone is CUT OUT before the solve, so it
# has ring vertices of its own and its interior pairs are its own
# all-pairs at 5 %.

def _split_fixture():
    layout, apron = _terminal_apron()
    plan = AT.plan_fan_ramp_zones(layout, icao="TEST")
    n = AT.split_aprons_at_fan_zones(layout, plan, icao="TEST")
    return layout, apron, plan, n


def test_the_zone_becomes_its_own_shape():
    """THE ACTIVATION.  Before the split the zone is interior ground with
    no variables; after it, it is a piece with a ring."""
    layout, apron, plan, n = _split_fixture()
    assert n >= 1, "no fan-ramp zone became a shape"
    ramps = [s for s in layout.shapes if getattr(s, "fan_ramp_zone", False)]
    assert len(ramps) == n
    original = _terminal_apron()[1].polygon
    for s in ramps:
        assert s.role == "apron", "a ramp piece is still apron ground"
        assert s.polygon.area >= 200.0
        assert not s.polygon.interiors
        # it came out of the apron it was declared on …
        assert original.buffer(1e-6).contains(
            s.polygon.representative_point())
        # … and out of it: the apron kept its identity as the largest
        # REMAINDER panel, so the ramp is no longer part of it.
        assert not apron.polygon.buffer(-1e-6).intersects(s.polygon)


def test_the_ramp_pieces_own_pairs_are_priced_at_the_zone_cap():
    """The point of the whole exercise: the ONE solve now has a surface
    it can fan.  The cap comes from the SAME function the census reads
    (``grade_graph._body_cap_unbounded``)."""
    from auto_patch import grade_graph as GG
    layout, _apron, _plan, _n = _split_fixture()
    ramp = next(s for s in layout.shapes
                if getattr(s, "fan_ramp_zone", False))
    ring = list(ramp.polygon.exterior.coords)[:-1]
    gs = GG.GradeShape(role="apron", ring=ring,
                       keys=list(range(len(ring))), fan_ramp_zone=True)
    plain = GG.GradeShape(role="apron", ring=ring,
                          keys=list(range(len(ring))))
    ctx = GG.GradeContext(centerlines=[], routes=[])
    assert GG._body_cap(gs, ctx, {}) == pytest.approx(GROUNDSIDE_MAX_GRADE)
    assert GG._body_cap(plain, ctx, {}) == pytest.approx(APRON_MAX_GRADE)
    # …and the pairs it actually generates carry it.
    sc = GG.shape_constraints(gs, ctx)
    assert sc.edges, "a ramp piece generated no within-shape pairs"
    assert max(c.flat_cap() for (_a, _b, c) in sc.edges) == pytest.approx(
        GROUNDSIDE_MAX_GRADE)


def test_no_pavement_is_lost_to_the_cut():
    """Losing pavement to a geometry op is never the lawful answer —
    every piece, ramp and remainder alike, is kept."""
    layout, apron, _plan, _n = _split_fixture()
    before = _terminal_apron()[1].polygon.area
    after = sum(s.polygon.area for s in layout.shapes
                if s.role == "apron")
    assert after == pytest.approx(before, rel=1e-9)


def test_a_ramp_piece_never_touches_a_movement_surface():
    """The composition clause, asserted on the SHAPES that ship — the
    structural guarantee has to survive the cut, not merely the plan."""
    layout, _apron, _plan, _n = _split_fixture()
    cover = AT.corridor_cover(layout)
    for s in layout.shapes:
        if not getattr(s, "fan_ramp_zone", False):
            continue
        assert not s.polygon.intersects(cover.buffer(-1e-9)), (
            "a shipped fan-ramp piece overlaps an aircraft-movement "
            "surface")


def test_a_zone_that_could_only_be_a_HOLE_is_stillborn_and_DROPPED():
    """Every shape in this system is simply connected, so a zone island
    in the middle of an apron cannot be cut out.  It is stillborn — and
    it must leave the DECLARATION too, or the census would keep granting
    5 % on ground the solver was never given at 5 %."""
    apron = _rect(0.0, 0.0, 400.0, 300.0, "apron", "a")
    layout = _Layout([apron])
    plan = AT.FanRampPlan()
    island = Polygon([(150.0, 120.0), (250.0, 120.0),
                      (250.0, 180.0), (150.0, 180.0)])
    plan.add(id(apron), {"shape_id": id(apron), "polygon": island,
                         "cap": GROUNDSIDE_MAX_GRADE, "buildings": 2,
                         "area_m2": island.area})
    n = AT.split_aprons_at_fan_zones(layout, plan, icao="TEST")
    assert n == 0
    assert plan.zones == [], "a stillborn zone still declares 5 %"
    assert plan.stats["zones_stillborn_hole"] == 1
    assert not any(getattr(s, "fan_ramp_zone", False) for s in layout.shapes)
    assert apron.polygon.area == pytest.approx(400.0 * 300.0)


def test_no_ramp_piece_OVERLAPS_any_other_piece():
    """ZERO-TOLERANCE, and it caught a real defect.

    The first cut of the split subtracted each zone component from a
    single HOST panel found by representative point.  Panels PARTITION
    the apron, so a component an earlier cut had divided across two of
    them kept its other half inside a sibling — while still being
    emitted as a ramp piece.  The two shapes then overlapped, which put
    one coordinate pair under two different caps: measured, SPJC 0.9477
    m² of apron∩apron (``test_no_self_overlap``) and 190/12 877 CYXY
    edges where the solver priced 1 % and the validator 5 %
    (``test_solver_validator_same_edge_budgets``) — a lockstep break of
    exactly the kind this law exists to prevent.
    """
    layout, _apron, _plan, _n = _split_fixture()
    pieces = [s for s in layout.shapes if s.role == "apron"]
    assert len(pieces) >= 2
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            inter = pieces[i].polygon.intersection(pieces[j].polygon)
            assert inter.area < 1e-9, (
                f"apron pieces overlap by {inter.area:.4f} m² "
                f"(ramp={getattr(pieces[i], 'fan_ramp_zone', False)}/"
                f"{getattr(pieces[j], 'fan_ramp_zone', False)})")


def test_a_component_SPANNING_two_panels_still_leaves_both():
    """The exact geometry the host-only cut got wrong: a zone component
    that straddles ground two earlier components already divided."""
    apron = _rect(0.0, 0.0, 300.0, 100.0, "apron", "a")
    layout = _Layout([apron])
    plan = AT.FanRampPlan()
    # A first component that cuts the apron in two, then a second that
    # spans the cut — it belongs to NEITHER resulting panel alone.
    first = Polygon([(140.0, 0.0), (160.0, 0.0), (160.0, 100.0),
                     (140.0, 100.0)])
    second = Polygon([(100.0, 0.0), (200.0, 0.0), (200.0, 30.0),
                      (100.0, 30.0)])
    for g in (first, second):
        plan.add(id(apron), {"shape_id": id(apron), "polygon": g,
                             "cap": GROUNDSIDE_MAX_GRADE, "buildings": 2,
                             "area_m2": g.area})
    AT.split_aprons_at_fan_zones(layout, plan, icao="TEST")
    pieces = [s for s in layout.shapes if s.role == "apron"]
    total = sum(s.polygon.area for s in pieces)
    assert total == pytest.approx(300.0 * 100.0, rel=1e-9), (
        "the cut lost or duplicated pavement")
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            assert pieces[i].polygon.intersection(
                pieces[j].polygon).area < 1e-9


def test_the_declaration_is_what_was_BUILT():
    """One declaration, and it names the pieces that exist: every zone
    the sidecar publishes has a shape, and every ramp shape a zone."""
    layout, _apron, plan, n = _split_fixture()
    ramps = [s for s in layout.shapes if getattr(s, "fan_ramp_zone", False)]
    assert len(plan.zones) == len(ramps) == n
    by_id = {id(s): s for s in ramps}
    for z in plan.zones:
        assert z["shape_id"] in by_id
        assert z["polygon"].equals(by_id[z["shape_id"]].polygon)
        assert z["cap"] == GROUNDSIDE_MAX_GRADE


def test_the_emitted_tag_and_the_solver_read_ONE_law():
    """THE LOCKSTEP, in its shipped form.  The build stamps
    ``o4_grade_law='fan_ramp'``; the census turns that tag back into the
    same ``GradeShape`` field the solver set, so both sides reach the cap
    through ``config.fan_ramp_law_cap`` and cannot drift."""
    import check_grade as CG
    from auto_patch.config import FAN_RAMP_LAW, fan_ramp_law_cap

    assert fan_ramp_law_cap(FAN_RAMP_LAW) == pytest.approx(
        GROUNDSIDE_MAX_GRADE)
    assert fan_ramp_law_cap("apron") is None
    assert fan_ramp_law_cap(None) is None

    class _W:
        tags = {"role": "apron", "o4_grade_law": FAN_RAMP_LAW}

    class _P:
        tags = {"role": "apron"}

    assert CG._role_grade_limit(_W(), APRON_MAX_GRADE) == pytest.approx(
        GROUNDSIDE_MAX_GRADE)
    assert CG._role_grade_limit(_P(), APRON_MAX_GRADE) == pytest.approx(
        APRON_MAX_GRADE)


def test_the_tag_is_actually_stamped_on_the_emitted_piece():
    """The half of the lockstep a unit test of the reader cannot see: the
    emitter has to write the tag, or the census silently judges a 5 %
    ramp at 1 %."""
    from auto_patch.layout import BuiltShape as _BS
    from auto_patch.config import FAN_RAMP_LAW
    import inspect
    from auto_patch import layout as _L

    src = inspect.getsource(_L.PavementLayout.to_osm)
    assert "fan_ramp_zone" in src and "FAN_RAMP_LAW" in src, (
        "to_osm no longer stamps the fan-ramp law tag")
    assert _BS.__dataclass_fields__["fan_ramp_zone"].default is False


def test_a_ramp_sibling_is_not_its_own_facing_NEIGHBOUR():
    """The cut runs the whole length of the ramp.  If the pieces faced
    each other, the joint clearance would fence the apron off from itself
    and the terrace law would be suppressed on exactly the aprons the
    ramp law just declared."""
    layout, apron, _plan, _n = _split_fixture()
    ramp = next(s for s in layout.shapes
                if getattr(s, "fan_ramp_zone", False))
    assert ramp not in AT._pavement_neighbours(layout, apron)
    assert apron not in AT._pavement_neighbours(layout, ramp)


def test_the_SOLVE_is_handed_the_zone_cap_not_just_the_census():
    """THE OTHER HALF OF THE MEMO TRAP, and the twin that decides where a
    residual defect belongs.

    ``solver_primitives._grade_graph_edges`` and
    ``grade_graph.build_unified_graph`` build ``GradeShape``s from the same
    polygons and SHARE one memo keyed by ``(polygon id, role, ring_only)``
    — whichever runs first fixes the caps for both.  The module says so in
    a comment, and notes that the older adoption flags have exactly this
    gap.  If ``fan_ramp_zone`` were passed on only one side, the ramp
    would be inert in the solve while the census judged it at 5 %, and
    every residual would be misattributed.

    Asserting on the BUDGET the solve receives (``cap·d``), not on an
    internal, is what makes this evidence: when HECA's ramp pieces came
    out at a median 10.24 % realized grade, this twin is what says the
    solve was HANDED 5 % and did something else with it.
    """
    from auto_patch.elevation_per_surface import solver_primitives as SP
    from auto_patch import grade_graph as GG

    ring = [(0.0, 0.0), (60.0, 0.0), (60.0, 40.0), (0.0, 40.0)]
    ctx = GG.GradeContext(centerlines=[], routes=[])
    got = {}
    for name, flag in (("ramp", True), ("plain", False)):
        s = BuiltShape(polygon=Polygon(ring), role="apron", ref=name,
                       fan_ramp_zone=flag)
        coords = list(s.polygon.exterior.coords)[:-1]
        edges = SP._grade_graph_edges(s, coords, list(range(len(coords))),
                                      ctx)
        caps = set()
        for (a, b, budget) in edges:
            d = math.hypot(coords[a][0] - coords[b][0],
                           coords[a][1] - coords[b][1])
            if d > 1e-6:
                caps.add(round(budget / d, 6))
        got[name] = caps
    assert got["ramp"] == {round(GROUNDSIDE_MAX_GRADE, 6)}, (
        f"the solve was handed {got['ramp']} on a ramp piece, not the "
        f"zone cap — the law is inert in the solve")
    assert got["plain"] == {round(APRON_MAX_GRADE, 6)}, (
        f"a plain apron's solve budgets moved to {got['plain']}")


def test_a_ramp_piece_is_not_a_TERRACE_candidate():
    """Owner answer 2: the wall is the fallback for what 5 % could not
    span, and 5 % is what this piece already holds.  A wall inside a ramp
    is not the law."""
    import inspect
    src = inspect.getsource(AT._construct_from_envelope)
    assert "fan_ramp_zone" in src, (
        "the terrace candidate list no longer excludes ramp pieces")
    assert src.index("split_aprons_at_fan_zones") < src.index(
        "aprons = ["), "the zones must be cut BEFORE the terrace lines"
