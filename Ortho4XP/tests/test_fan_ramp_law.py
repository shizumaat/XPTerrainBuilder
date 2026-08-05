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


def test_a_patch_predating_the_law_is_judged_exactly_as_before():
    import check_grade as CG
    assert CG._fan_ramp_zones_to_m(None, lambda a, b: (a, b)) == []
    assert CG._fan_ramp_pair_cap([], 0.0, 0.0, 1.0, 1.0) is None
