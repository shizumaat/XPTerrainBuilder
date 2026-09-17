"""THE RELIEF TARGET and THE PACK PARTITION AT LOAD — round 2's twins
(owner RULINGS 2026-09-11j; spec ``object-placement-spec.md`` §11a).

Round 1 landed the grouping and measured that it is not where the site's
residual lives: LEMD38's canopy modules are nine column feet authored
2.63 m apart inside ONE placement, with no abutment anywhere, and 1,158
of LEMD's 9,546 bodies carry more than 3 m of authored relief.  §11a
restates the mechanism — the unit is the BODY, the fix is a PER-FOOT
TARGET on the pad, and the pack partition moves before ``classify`` so
the pad law can see the bodies at all.  These twins pin the four
sentences that follow from it:

1. THE ORDER (§11a (3)).  ``partition_pack`` reads the pack once at load
   and ``plan()`` FILTERS that reading; the two orders are not identical
   by construction, so the twin asserts the INVARIANTS that must hold —
   the same members survive, every surviving part is the same part, and
   every contact and abutment of the filtered reading is one the
   unfiltered reading also carried.  The real-pack numbers are the
   ``v2_rebake_replay.py order`` tool's, reported per round.
2. THE RELIEF TARGET (§11a (2)).  Nine columns over 2.63 m of authored
   relief give the pad under them a per-foot offset, and ``Diff.rel``
   carries it into the solver's two one-sided rows, so the pad is priced
   FLAT ON ITS LEVEL PLANE.
3. PAVEMENT IS SENIOR (09af-1).  Feet standing on an apron take no
   relief row at all.
4. THE LONG SPAN (§11 (4), body level).  An INFEASIBLE group whose
   connecting BODY is long releases it; an infeasible SHORT group is
   reported and never split.

Hermetic: hand-built partitions and planar maps, no pack, no mesh, no
environment.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport.pack_partition import PackPartition, Screen
from auto_patch_v2.constraints.pad_relief import pad_relief_offsets, relief_radius_m
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Source
from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit
from auto_patch_v2.planar import group as G
from auto_patch_v2.solve.rows import _law_sides
from auto_patch_v2.model.constraints import ConstraintSet

LAT, LON = 40.48, -3.56
DLAT = 1.0 / 111_132.0
DLON = 1.0 / (111_132.0 * 0.76)


def _part(pid, comp, dx, dy, feet, area=100.0, line=False):
    lat, lon = LAT + dy * DLAT, LON + dx * DLON
    ff = tuple((LAT + b * DLAT, LON + a * DLON, float(y)) for a, b, y in feet)
    return Part(pid, comp, lat, lon, min((f[2] for f in ff), default=0.0), area,
                (lat, lon, lat, lon), ff, line)


def _member(mid, parts, *, deck=False):
    return Member(mid, f"objects/{mid}.obj", f"/p/objects/{mid}.obj",
                  f"/p/objects/{mid}.obj", 0.0, tuple(parts), elevated_deck=deck)


def _partition(members, contacts=(), abutments=()):
    unit = Unit("unit:0", (LAT, LON), 0.0, tuple(members))
    counts = {"members": len(members),
              "parts": sum(len(m.parts) for m in members),
              "contacts": len(contacts), "abutments": len(abutments)}
    return PackPartition("ZZZZ", "pack", "/p", (unit,), (), counts,
                         tuple(contacts), tuple(abutments),
                         {(0, i): (m.id, m.resource) for i, m in enumerate(members)})


# ── 1. THE ORDER: plan() filters a partition (§11a (3)) ─────────────────

def _law():
    return Law.for_airport("ZZZZ")


def test_the_filter_keeps_every_surviving_part_and_no_new_edge():
    """The invariant the order twin rests on: filtering a reading never
    INVENTS a part, a contact or an abutment, and every member the screen
    leaves alone comes through with its parts unchanged."""
    keep = _member("TERM", [_part(1, 0, 0.0, 0.0, [(-5, -5, 0.0), (5, 5, 0.0)])])
    drop = _member("BASIN", [_part(2, 0, 40.0, 0.0, [(38, -2, 0.0), (42, 2, 0.0)])])
    p = _partition([keep, drop], contacts=[(1, 2)], abutments=[(1, 2)])
    out = p.filtered(Screen(excluded=frozenset({"BASIN"})), _law())
    assert out.counts["members"] == 1
    assert [m.resource for u in out.units for m in u.members] == ["objects/TERM.obj"]
    assert out.units[0].members[0].parts == keep.parts
    # every edge touching the screened member is gone, and none is new
    assert out.contacts == () and out.abutments == ()
    assert set(out.contacts) <= set(p.contacts)
    assert set(out.abutments) <= set(p.abutments)


def test_an_empty_screen_is_the_identity():
    p = _partition([_member("A", [_part(1, 0, 0.0, 0.0, [(-5, -5, 0.0), (5, 5, 0.0)])])],
                   contacts=[], abutments=[])
    assert Screen().is_empty()
    out = p.filtered(Screen(), _law())
    assert out.units == p.units and out.contacts == p.contacts


def test_a_below_grade_component_leaves_its_siblings_in_place():
    """09w (1) through the filter: the deep component's PART goes, the
    at-grade sibling in the same file stays."""
    m = _member("SCATTER", [_part(1, 0, 0.0, 0.0, [(-5, -5, 0.0), (5, 5, 0.0)]),
                            _part(2, 1, 30.0, 0.0, [(28, -2, -9.0), (32, 2, -9.0)])])
    p = _partition([m], contacts=[(1, 2)])
    out = p.filtered(Screen(below_comps={"SCATTER": frozenset({1})}), _law())
    kept = out.units[0].members[0]
    assert [q.comp for q in kept.parts] == [0]
    assert out.contacts == ()


def test_a_structure_seated_member_is_no_line_object():
    """14.1 rule 4 restated by the filter: the load partition reads the
    line verdict raw, the screen withdraws it where a structure seat
    governs the member's elevation."""
    m = _member("FENCE", [_part(1, 0, 0.0, 0.0, [(-5, 0, 0.0), (5, 0, 0.0)], line=True)])
    p = _partition([m])
    assert p.units[0].members[0].parts[0].line
    out = p.filtered(Screen(structure_seated=frozenset({"FENCE"})), _law())
    assert not out.units[0].members[0].parts[0].line
    assert out.counts["line_objects"] == 0


# ── 2. THE RELIEF TARGET (§11a (2)) ─────────────────────────────────────

def _columns(n=9, pitch=12.0, rise=2.63):
    """A canopy module: ``n`` column feet in a row, the far one authored
    ``rise`` above the near one — the LEMD38 class."""
    feet = [(i * pitch, 0.0, rise * i / (n - 1)) for i in range(n)]
    return _member("CANOPY", [_part(1, 0, (n - 1) * pitch / 2.0, 0.0, feet, area=90.0)],
                   deck=True)


def test_a_body_of_nine_columns_carries_its_authored_relief():
    gs = G.derive(_partition([_columns()]))
    g = gs.groups[0]
    assert len(g.feet) == 9
    assert g.y_zero == pytest.approx(0.0)
    assert g.relief_m == pytest.approx(2.63, abs=1e-6)
    # §11 (2): the target under a foot is level + (y_foot - y_zero)
    far = g.feet[-1]
    assert g.target_at(far.lat, far.lon, 700.0, 5.0) == pytest.approx(702.63, abs=1e-6)
    near = g.feet[0]
    assert g.target_at(near.lat, near.lon, 700.0, 5.0) == pytest.approx(700.0, abs=1e-6)
    # and outside every foot's radius the pad keeps its level
    assert g.target_at(LAT + 500 * DLAT, LON, 700.0, 5.0) is None


def test_the_relief_row_is_priced_on_the_level_plane():
    """``Diff.rel`` shifts BOTH one-sided rows, so a pad whose two feet
    are authored 2.63 m apart is satisfied exactly at that difference and
    a FLAT pad under it is the violation."""
    src = Source("pads", "structures.building_pad flat")
    d = Diff(1, 2, 0.0, 30.0, src, rel=2.63)
    one, _eq = _law_sides(ConstraintSet(diffs=(d,)))
    (t_ab, hi_ab, _), (t_ba, hi_ba, _) = one
    assert t_ab == ((1, 1.0), (2, -1.0)) and hi_ab == pytest.approx(2.63)
    assert t_ba == ((2, 1.0), (1, -1.0)) and hi_ba == pytest.approx(-2.63)
    # z1 - z2 == 2.63 satisfies both sides exactly; a flat pad does not
    for z1, z2, ok in ((702.63, 700.0, True), (700.0, 700.0, False)):
        sat = (z1 - z2 <= hi_ab + 1e-9) and (z2 - z1 <= hi_ba + 1e-9)
        assert sat is ok


def test_rel_defaults_to_zero_so_every_other_row_is_unchanged():
    src = Source("x", "y")
    one, _eq = _law_sides(ConstraintSet(diffs=(Diff(1, 2, 0.01, 100.0, src),)))
    assert [hi for _t, hi, _r in one] == [pytest.approx(1.0), pytest.approx(1.0)]


# ── 3. PAVEMENT IS SENIOR (09af-1) ──────────────────────────────────────

class _FakeVertex:
    def __init__(self, xy):
        self.xy = xy


class _FakePlanar:
    def __init__(self, vertices):
        self.vertices = {i: _FakeVertex(xy) for i, xy in vertices.items()}


def _offsets(monkeypatch, law, airport, pad_vertices, pad_poly, pavement):
    """Drive ``pad_relief_offsets`` over a hand-made pad and pavement."""
    from auto_patch_v2.constraints import pad_relief as PR
    pm = _FakePlanar(pad_vertices)
    monkeypatch.setattr("auto_patch_v2.constraints.pads._pad_polys",
                        lambda _p, _l: [(1, "building1", list(pad_vertices), pad_poly)])
    monkeypatch.setattr("auto_patch_v2.constraints.pads._pavement_geoms",
                        lambda _p, _l: [("apron", set(), q) for q in pavement])
    return PR.pad_relief_offsets(pm, law, airport)


class _Frame:
    """A metre frame at the fixture's origin (the pad_relief reader only
    ever asks for ``to_xy(lon, lat)``)."""

    def transformers(self):
        def to_xy(lon, lat):
            return ((lon - LON) / DLON, (lat - LAT) / DLAT)
        return to_xy, None

    def entry(self):
        # §46: a fixture frame carries no law quantum, so ENTRY == exact
        return self.transformers()[0]


class _Airport:
    def __init__(self, groups):
        self.groups = groups
        self.frame = _Frame()


def test_a_pad_vertex_takes_the_nearest_foot_and_the_far_one_keeps_the_level(monkeypatch):
    law = _law()
    gs = G.derive(_partition([_columns(n=3, pitch=20.0, rise=2.0)]))
    ap = _Airport(gs)
    r = relief_radius_m(law)
    assert r > 0.0
    verts = {10: (0.0, 0.0), 11: (40.0, 0.0), 12: (0.0, 400.0)}
    pad = Polygon([(-20, -20), (60, -20), (60, 500), (-20, 500)])
    off = _offsets(monkeypatch, law, ap, verts, pad, [])
    assert off.get(10, 0.0) == pytest.approx(0.0, abs=1e-9)   # the zero foot
    assert off[11] == pytest.approx(2.0, abs=1e-6)            # the high foot
    assert 12 not in off                                      # no foot within r


def test_an_infeasible_body_gets_no_relief_target(monkeypatch):
    """§11 (4): the terrain is only adapted where the adapted surface
    stays lawful.  A body whose authored relief asks more of the ground
    than the ground law allows keeps TODAY'S FLAT PAD, anchors at its
    low-side foot (§9) and is REPORTED — measured at LEMD, without this
    gate the published targets reached +35.53 / -14.51 m, which is not a
    relief profile but a body whose feet are vertices up its own
    structure."""
    law = _law()
    # 2 m over 20 m = 10 %, refused by a 1 % bar and admitted by 33 %
    steep = G.derive(_partition([_columns(n=3, pitch=20.0, rise=2.0)]), 0.0, 0.01)
    gentle = G.derive(_partition([_columns(n=3, pitch=20.0, rise=2.0)]), 0.0, 0.33)
    assert steep.groups[0].infeasible and not gentle.groups[0].infeasible
    verts = {10: (0.0, 0.0), 11: (40.0, 0.0)}
    pad = Polygon([(-20, -20), (60, -20), (60, 20), (-20, 20)])
    assert _offsets(monkeypatch, law, _Airport(steep), verts, pad, []) == {}
    assert _offsets(monkeypatch, law, _Airport(gentle), verts, pad, [])[11] \
        == pytest.approx(2.0, abs=1e-6)


def test_feet_on_pavement_take_no_row(monkeypatch):
    """09af-1: the pavement law owns that surface, so the body's feet
    there found no target and the pad keeps its level."""
    law = _law()
    gs = G.derive(_partition([_columns(n=3, pitch=20.0, rise=2.0)]))
    ap = _Airport(gs)
    verts = {10: (0.0, 0.0), 11: (40.0, 0.0)}
    pad = Polygon([(-20, -20), (60, -20), (60, 20), (-20, 20)])
    apron = Polygon([(30, -30), (80, -30), (80, 30), (30, 30)])   # covers foot 3
    off = _offsets(monkeypatch, law, ap, verts, pad, [apron])
    assert 11 not in off


# ── 4. THE LONG SPAN RELEASES ONLY WHEN INFEASIBLE (§11 (4)) ────────────

def _building():
    return _member("TERM", [_part(1, 0, 0.0, 0.0,
                                  [(-10, -10, 0.0), (10, -10, 0.0),
                                   (10, 10, 0.0), (-10, 10, 0.0)], area=400.0)])


def _long_span(rise: float, length: float = 400.0):
    return _member("RAIL", [_part(2, 0, length / 2.0, 0.0,
                                  [(12.0, -3.0, 0.0), (12.0, 3.0, 0.0),
                                   (length, -3.0, rise), (length, 3.0, rise)],
                                  area=90.0)], deck=True)


def _derive(members, abut, span_max=150.0, slope_max=0.01):
    return G.derive(_partition(members, abutments=abut), span_max, slope_max)


def test_a_feasible_long_group_is_never_released():
    """11i: the release is the EXCEPTION — length alone never splits a
    group, the pad has to be infeasible too."""
    gs = _derive([_building(), _long_span(rise=0.5)], [(1, 2)])
    g = next(x for x in gs.groups if x.long_span)
    assert not g.infeasible
    assert g.released == ()
    assert len(g.bodies) == 2 and gs.counts["released"] == 0


def test_an_infeasible_long_group_releases_its_connecting_body():
    """The HECA railway class: the span cannot stand on a lawful pad, so
    it lets go and the building seats."""
    gs = _derive([_building(), _long_span(rise=30.0)], [(1, 2)])
    senior = next(x for x in gs.groups if x.senior == (0, 0, 0))
    assert senior.infeasible and senior.released == ((0, 1, 0),)
    assert senior.bodies == ((0, 0, 0),)          # the building seats alone
    assert gs.counts["released"] == 1
    # and the released body is its own object
    junior = gs.group_of((0, 1, 0))
    assert junior is not None and junior.bodies == ((0, 1, 0),)
    assert junior is not senior


def test_an_infeasible_short_group_is_reported_never_split():
    """11i, verbatim in its consequence: a SHORT infeasible group keeps
    its canopy and the residual goes in the report."""
    gs = _derive([_building(), _long_span(rise=30.0, length=60.0)], [(1, 2)])
    g = next(x for x in gs.groups if x.senior == (0, 0, 0))
    assert g.infeasible
    assert g.released == () and len(g.bodies) == 2
    assert gs.counts["infeasible_short"] >= 1 and gs.counts["released"] == 0


def test_slope_max_zero_disarms_the_feasibility_test():
    gs = _derive([_building(), _long_span(rise=30.0)], [(1, 2)], slope_max=0.0)
    g = next(x for x in gs.groups if x.senior == (0, 0, 0))
    assert not g.infeasible and g.released == ()


def test_a_flat_footed_body_is_always_feasible():
    gs = _derive([_building()], [])
    g = gs.groups[0]
    assert g.relief_slope == pytest.approx(0.0)
    assert not g.infeasible


# ── the law's own numbers ───────────────────────────────────────────────

def test_the_relief_radius_is_a_law_value():
    law = _law()
    assert relief_radius_m(law) == pytest.approx(
        law.tables.structures.placement.relief_radius_m)
    assert relief_radius_m(law) > 0.0


def test_the_relief_target_is_disarmable(monkeypatch):
    law = _law()
    pl = _dc.replace(law.tables.structures.placement, relief_radius_m=0.0)
    st = _dc.replace(law.tables.structures, placement=pl)
    lt = _dc.replace(law.tables, structures=st)
    off = pad_relief_offsets(_FakePlanar({}), _dc.replace(law, tables=lt),
                             _Airport(G.derive(_partition([_columns()]))))
    assert off == {}
