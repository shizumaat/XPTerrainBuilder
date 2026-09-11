"""THE CANOPY-AND-BUILDING GROUP twins (owner RULINGS 2026-09-11i; spec
``object-placement-spec.md`` §11; lane ``v2canopy``).

``planar/group.py`` is the ONE derivation site for "which bodies are one
object" — the thing the group pad is laid under, the split writer writes
a file for and the census reports a row against.  These twins pin the
four sentences of the law and the one number:

1. a BUILDING and a CANOPY on four columns, authored abutting, in
   different placements: ONE group, the building senior, every column
   foot in the group's feet, the span short;
2. the same pair 60 m apart in plan (no abutment): TWO groups of one —
   a canopy that touches nothing keeps its own anchor;
3. BUILDING + BUILDING abutting, neither an elevated deck: never one
   group (11a/10i — each seats on its own feet).  This is the gate
   round 1 of ``v2bridgegroup`` failed and 11g fixed;
4. THE LONG SPAN (§11 (4)), AMENDED BY §11a (1): the span law binds the
   CONNECTING BODY's own plan diagonal, never the group's footprint.  A
   canopy 10 m long joining a building 400 m away is NOT the HECA railway
   class and is never releasable — round 1 priced the group's footprint
   and released exactly the canopies 11i exists to keep.  A 400 m
   connecting SPAN is, and it names itself releasable;
5. §11 (2)'s per-foot target: ``level + (y_foot - y_zero)``, flat when
   every foot is authored at zero and the group's authored RELIEF
   otherwise — read at a foot, and absent outside every foot's radius.

Hermetic: a hand-built ``RebakePlan``, no pack, no mesh, no environment.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import group_span_max_m
from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit
from auto_patch_v2.planar import group as G

LAT, LON = 40.48, -3.56
#: ~1 m in degrees at the fixture's latitude
DLAT = 1.0 / 111_132.0
DLON = 1.0 / (111_132.0 * 0.76)


def _part(pid: int, comp: int, dx: float, dy: float, feet, area=100.0, line=False):
    """One welded part at ``(dx, dy)`` metres from the fixture origin;
    ``feet`` are ``(dx, dy, authored y)`` triples."""
    lat, lon = LAT + dy * DLAT, LON + dx * DLON
    ff = tuple((LAT + b * DLAT, LON + a * DLON, float(y)) for a, b, y in feet)
    return Part(pid, comp, lat, lon, min((f[2] for f in ff), default=0.0), area,
                (lat, lon, lat, lon), ff, line)


def _member(mid: str, parts, *, deck=False, skirted=False):
    return Member(mid, f"objects/{mid}.obj", f"/p/objects/{mid}.obj",
                  f"/p/objects/{mid}.obj", 0.0, tuple(parts),
                  skirted=skirted, elevated_deck=deck)


def _plan(members, abutments=(), contacts=()):
    unit = Unit("unit:0", (LAT, LON), 0.0, tuple(members))
    return RebakePlan("ZZZZ", "pack", "/p", (unit,), (), {}, tuple(contacts),
                      None, tuple(abutments))


# ── the fixture: a building and a canopy on four columns ────────────────

def _building(pid0=1, x=0.0):
    """A terminal: one part, a big footprint, four feet at authored 0."""
    return _member("TERM", [_part(pid0, 0, x, 0.0,
                                  [(x - 10, -10, 0.0), (x + 10, -10, 0.0),
                                   (x + 10, 10, 0.0), (x - 10, 10, 0.0)],
                                  area=400.0)])


def _canopy(pid0=2, x=18.0, y_high=2.63, deck=True):
    """A roadway canopy: a roof on FOUR columns, the two far feet
    authored ``y_high`` above the two near ones — the LEMD38 class (nine
    column feet authored 2.63 m apart, measured 2026-09-11)."""
    return _member("CANOPY", [_part(pid0, 0, x, 0.0,
                                    [(x - 5, -6, 0.0), (x - 5, 6, 0.0),
                                     (x + 5, -6, y_high), (x + 5, 6, y_high)],
                                    area=90.0)], deck=deck)


def _derive(members, abut, span_max=150.0):
    return G.derive(_plan(members, abut), span_max)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── 1. the canopy stays with its building ───────────────────────────────

def test_canopy_and_building_are_one_group():
    gs = _derive([_building(), _canopy()], [(1, 2)])
    assert gs.counts["cross_groups"] == 1, gs.counts
    g = next(x for x in gs.groups if x.cross_placement)
    # the BUILDING is senior (the larger plan area), the canopy its junior
    assert g.senior == (0, 0, 0)
    assert g.bodies == ((0, 0, 0), (0, 1, 0))
    # §11a (1): the canopy BODY is 10 m long, so it is never releasable
    assert g.releasable == ()
    assert g.body_span_m[1] < 20.0
    assert len(g.bodies) == 2
    # every column foot is IN the group — the terrain must meet them all
    assert len(g.feet) == 8
    assert g.relief_m == pytest.approx(2.63, abs=1e-6)
    assert g.span_m < 60.0
    assert not g.long_span
    # and both bodies index back to the same group
    assert gs.group_of((0, 0, 0)) is gs.group_of((0, 1, 0))


# ── 2. a canopy that abuts nothing keeps its own anchor ─────────────────

def test_canopy_clear_of_the_building_is_its_own_group():
    gs = _derive([_building(), _canopy(x=60.0)], [])
    assert gs.counts["cross_groups"] == 0
    assert len(gs.groups) == 2
    assert gs.group_of((0, 0, 0)) is not gs.group_of((0, 1, 0))
    assert all(not g.cross_placement and not g.releasable for g in gs.groups)


# ── 3. THE GATE: buildings never group with buildings ───────────────────

def test_building_never_groups_with_building():
    gs = _derive([_building(), _canopy(deck=False)], [(1, 2)])
    assert gs.counts["cross_groups"] == 0
    assert gs.counts["refused_building"] == 1
    assert len(gs.groups) == 2


def test_a_deck_never_carries_a_larger_deck():
    """Only a STRICTLY smaller junior joins: a tie is two peers."""
    a = _member("DECKA", [_part(1, 0, 0.0, 0.0,
                                [(-5, -5, 0.0), (5, 5, 0.0)], area=100.0)], deck=True)
    b = _member("DECKB", [_part(2, 0, 8.0, 0.0,
                                [(3, -5, 0.0), (13, 5, 0.0)], area=100.0)], deck=True)
    gs = _derive([a, b], [(1, 2)])
    assert gs.counts["cross_groups"] == 0
    assert gs.counts["refused_peer"] >= 1


# ── 4. THE LONG SPAN (§11 (4)) ──────────────────────────────────────────

def test_short_group_is_never_releasable(law):
    """The law's own 150 m: a kerbside canopy is SHORT, so an infeasible
    pad under it is REPORTED, never split (11i)."""
    assert group_span_max_m(law) == pytest.approx(150.0)
    gs = _derive([_building(), _canopy()], [(1, 2)], span_max=group_span_max_m(law))
    g = next(x for x in gs.groups if x.cross_placement)
    assert not g.long_span
    assert gs.counts["released_candidates"] == 0


def _span_deck(pid0=2, length=400.0, y_high=0.0):
    """THE HECA RAILWAY CLASS: one elevated body that is ITSELF long —
    a span whose two ends stand ``length`` apart."""
    return _member("RAIL", [_part(pid0, 0, length / 2.0, 0.0,
                                  [(12.0, -3.0, 0.0), (12.0, 3.0, 0.0),
                                   (length, -3.0, y_high), (length, 3.0, y_high)],
                                  area=90.0)], deck=True)


def test_a_far_but_short_junior_is_not_the_railway_class():
    """§11a (1): round 1 read the GROUP's footprint and called this long.
    The connecting BODY is 10 m; 11i forbids releasing it."""
    gs = _derive([_building(), _canopy(x=400.0)], [(1, 2)], span_max=150.0)
    g = next(x for x in gs.groups if x.cross_placement)
    assert g.span_m > 150.0                 # the group footprint IS long
    assert max(g.body_span_m) < 150.0       # no BODY is
    assert not g.long_span
    assert g.releasable == ()
    assert gs.counts["released_candidates"] == 0


def test_long_span_group_names_its_releasable_junior():
    """The HECA railway class: one CONNECTING BODY longer than the law."""
    gs = _derive([_building(), _span_deck()], [(1, 2)], span_max=150.0)
    g = next(x for x in gs.groups if x.cross_placement)
    assert g.body_span_m[1] > 150.0
    assert g.long_span
    assert g.releasable == ((0, 1, 0),)
    assert gs.counts["long_span"] == 1
    assert gs.counts["released_candidates"] == 1


def test_span_max_zero_disarms_the_exception():
    gs = _derive([_building(), _span_deck()], [(1, 2)], span_max=0.0)
    g = next(x for x in gs.groups if x.cross_placement)
    assert not g.long_span and gs.counts["released_candidates"] == 0


def test_the_airport_may_state_its_own_span():
    """§11 (4): per airport in ``airports.toml``; every airport the table
    does not name takes the global law.  ONE resolution site."""
    base = Law.for_airport("ZZZZ")
    assert group_span_max_m(base) == pytest.approx(
        base.tables.structures.placement.group_span_max_m)
    own = _dc.replace(base, tables=base.tables)
    aff = _dc.replace(own.affordances, group_span_max_m=42.0)
    patched = _dc.replace(own, tables=_dc.replace(
        own.tables, airports={**own.tables.airports, "ZZZZ": aff}))
    assert group_span_max_m(patched) == pytest.approx(42.0)


# ── 5. §11 (2): the per-foot target ─────────────────────────────────────

def test_target_is_the_level_plus_the_authored_relief():
    gs = _derive([_building(), _canopy()], [(1, 2)])
    g = next(x for x in gs.groups if x.cross_placement)
    level = 600.0
    # under a foot authored at the group's zero: the level itself
    low = next(f for f in g.feet if f.y == 0.0)
    assert g.target_at(low.lat, low.lon, level, 5.0) == pytest.approx(level)
    # under a HIGH column foot: the level plus the authored relief
    high = next(f for f in g.feet if f.y > 1.0)
    assert g.target_at(high.lat, high.lon, level, 5.0) == pytest.approx(level + 2.63)
    # far from every foot the pad has no target of its own and keeps the
    # level — which is exactly today's flat pad
    assert g.target_at(LAT + 300 * DLAT, LON, level, 5.0) is None


def test_a_flat_footed_group_asks_for_a_flat_pad():
    gs = _derive([_building(), _canopy(y_high=0.0)], [(1, 2)])
    g = next(x for x in gs.groups if x.cross_placement)
    assert g.relief_m == pytest.approx(0.0)
    assert all(g.target_at(f.lat, f.lon, 600.0, 5.0) == pytest.approx(600.0)
               for f in g.feet)


# ── the body law is IMPORTED, never re-implemented (§11 (3)) ────────────

def test_bodies_are_the_split_writers_own_bodies():
    """An intra-placement ε-contact edge binds two parts into ONE body —
    ``placement_plan._bodies_of``'s law, read here, not restated."""
    m = _member("TWO", [_part(1, 0, 0.0, 0.0, [(0, 0, 0.0)]),
                        _part(2, 1, 3.0, 0.0, [(3, 0, 0.0)])])
    welded = _plan([m], (), contacts=[(1, 2)])
    loose = _plan([m], (), contacts=[])
    assert len(G.bodies_of_plan(welded)[0]) == 1
    assert len(G.bodies_of_plan(loose)[0]) == 2
    # and the group set follows the bodies
    assert len(G.derive(welded, 150.0).groups) == 1
    assert len(G.derive(loose, 150.0).groups) == 2


def test_a_line_object_binds_nothing_and_founds_no_group():
    """10bb rule 2, restated by ``_eligible``: a fence is out of the
    class — it drapes per segment and carries no group pad."""
    fence = _member("FENCE", [_part(1, 0, 0.0, 0.0, [(0, 0, 0.0)], line=True),
                              _part(2, 0, 50.0, 0.0, [(50, 0, 0.0)], line=True)])
    gs = G.derive(_plan([fence, _building(pid0=3)], [(1, 3)]), 150.0)
    assert gs.counts["refused_ineligible"] == 1
    assert all(g.gid.startswith("TERM") for g in gs.groups)
