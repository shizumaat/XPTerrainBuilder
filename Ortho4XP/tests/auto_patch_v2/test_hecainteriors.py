"""S6 THE RIGID BUILDING UNIT — CONTENTS (spec ``pack-read-once-fast-spec.md``
§F.2 / F.9 R1; issues #30 and #10 [HECA-5]) — lane ``hecainteriors``.

The defect the twins pin (HECA hecabodies closing plan): §16g (10) (4) made
only WALLED bodies links of a footprint unit, and the unit was then the
walled bodies ALONE — every leaf inside a building (glass panes, door
leaves, floor slabs, window frames: 11,874 of them) was seated on its own
ground or its own carrier, 3,478 of them apart from the walls around them
(2,765 by more than 0.5 m).  A building's contents take the building's one
zero; they never link two buildings and never move the building's datum.
"""
from __future__ import annotations

import auto_patch_v2.airport.footprint_unit as FU
from auto_patch_v2.airport.placement_plan import _split_by_unit
import auto_patch_v2.airport.anchor_rule as AR


def _lat(m: float) -> float:
    return 41.0 + m / 111_132.0


def _lon(m: float) -> float:
    return -3.0 + m / 83_900.0


def _box(x0, y0, x1, y1):
    """A plan box ``x`` metres east, ``y`` metres north of 41 N / 3 W."""
    return (_lat(y0), _lon(x0), _lat(y1), _lon(x1))


def _ring(b):
    la0, lo0, la1, lo1 = b
    return ((la0, lo0), (la0, lo1), (la1, lo1), (la1, lo0))


class _Part:
    def __init__(self, pid, box, height, base_y=0.0, ring=True):
        self.pid = pid
        self.box = box
        self.line = False
        self.lat = 0.5 * (box[0] + box[2])
        self.lon = 0.5 * (box[1] + box[3])
        self.base_y = base_y
        self.height_m = height
        self.feet = ((self.lat, self.lon, base_y),)
        self.comp = pid
        self.area_m2 = 1.0
        self.rings = (_ring(box),) if ring else ()


class _Member:
    def __init__(self, resource, parts, deck_datum_z=None):
        self.id = resource
        self.resource = resource
        self.parts = tuple(parts)
        self.deck_datum_z = deck_datum_z
        self.deck_ring = None
        self.deck_kind = ""
        self.heading_deg = 0.0


class _Unit:
    def __init__(self, uid, members):
        self.id = uid
        self.anchor = (41.0, -3.0)
        self.members = tuple(members)


class _Plan:
    def __init__(self, units, contacts=()):
        self.units = tuple(units)
        self.contacts = tuple(contacts)


def _building(extra=(), second=True):
    """A 40 x 20 m hangar of two touching walled bodies (8 m tall), its
    interior floor slab, a glass pane on its façade and a chair inside —
    each authored as its OWN placement (the HECA material-sliced class) —
    plus a free cart 30 m away and whatever ``extra`` adds."""
    walls_a = _Member("objects/walls_a.obj",
                      [_Part(1, _box(0, 0, 20, 20), 8.0)])
    walls_b = _Member("objects/walls_b.obj",
                      [_Part(2, _box(20, 0, 40, 20), 8.0)])
    floor = _Member("objects/floor.obj", [_Part(10, _box(1, 1, 39, 19), 0.2)])
    glass = _Member("objects/glass.obj", [_Part(11, _box(5, 0, 15, 0.2), 2.0,
                                                base_y=3.0)])
    chair = _Member("objects/chair.obj", [_Part(12, _box(8, 8, 9, 9), 1.0)])
    cart = _Member("objects/cart.obj", [_Part(13, _box(70, 0, 72, 2), 1.5)])
    ms = [walls_a, walls_b, floor, glass, chair, cart] + list(extra)
    if not second:
        ms.remove(walls_b)
    return _Plan([_Unit("unit:0", ms)])


def _units(plan, frac=0.95):
    return FU.plan_units_and_connectors(plan, 0.5, 200.0, None, 2.5,
                                        contents_min_fraction=frac)[0]


def test_contents_join_their_building_and_do_not_move_its_datum():
    """F.2: the floor, the glass and the chair are CONTENTS of the hangar's
    unit — one unit, all their parts in its join — while the unit's datum
    boxes are the WALLS' alone (F.4) and the free cart stays out."""
    plan = _building()
    off = _units(plan, 0.0)
    on = _units(plan)
    assert len(off) == 1 and off[0].pids == frozenset({1, 2})
    assert len(on) == 1
    assert on[0].pids == frozenset({1, 2, 10, 11, 12})
    assert on[0].boxes == off[0].boxes           # the datum is the hosts'
    assert 13 not in on[0].pids                  # the free cart seats alone


def test_a_walled_singleton_with_contents_becomes_a_unit():
    """A building that is ONE walled body touching nothing was never a
    unit (it seated alone by §16c) — its contents had nothing to join.
    Holding contents makes it one; without contents nothing changes."""
    plan = _building(second=False)
    counts: dict = {}
    assert FU.plan_units_and_connectors(plan, 0.5, 200.0, counts, 2.5)[0] == []
    on = FU.plan_units_and_connectors(plan, 0.5, 200.0, counts, 2.5,
                                      contents_min_fraction=0.95)[0]
    # the 38 m floor slab runs past the 20 m building: not contents
    assert len(on) == 1 and on[0].pids == frozenset({1, 11, 12})
    assert counts["contents_host_singletons"] == 1


def test_a_leaf_never_links_two_buildings():
    """§16g (10) (4) stands: a slab lying half in each of two separate
    buildings is contents of NEITHER, and the two stay two units."""
    other = _Member("objects/other_walls.obj",
                    [_Part(3, _box(0, 40, 40, 60), 8.0)])
    other2 = _Member("objects/other_walls2.obj",
                     [_Part(4, _box(40, 40, 60, 60), 8.0)])
    bridge = _Member("objects/slab.obj", [_Part(20, _box(10, 10, 30, 50), 0.3)])
    plan = _building(extra=[other, other2, bridge])
    on = _units(plan)
    assert len(on) == 2
    assert all(20 not in u.pids for u in on)


def test_below_grade_and_deck_leaves_are_never_contents():
    """§48 (1) (c)/(d) adopted unchanged: a pit floor authored 4 m under its
    own zero and a DECK member are never contents, however roofed."""
    pit = _Member("objects/pit.obj", [_Part(30, _box(10, 5, 12, 7), 1.0,
                                           base_y=-4.0)])
    deck = _Member("objects/deck.obj", [_Part(31, _box(25, 5, 30, 10), 0.5)],
                   deck_datum_z=100.0)
    deck.deck_kind = "flag"
    counts: dict = {}
    on = FU.plan_units_and_connectors(_building(extra=[pit, deck]), 0.5,
                                      200.0, counts, 2.5,
                                      contents_min_fraction=0.95)[0]
    assert 30 not in on[0].pids and 31 not in on[0].pids
    assert counts["contents_refused_below_grade"] == 1
    assert counts["contents_refused_deck"] == 1


def test_contents_take_the_units_one_zero():
    """§16g (2) through S6: host and contents read ONE seat row (the same
    unit id and zero) from ``plan_wide_seats``; with the law disarmed the
    contents have no row and seat on their own ground."""
    plan = _building()
    surface = lambda la, lo: 50.0 + (la - 41.0) * 111_132.0 * 0.05
    rows_off, _ = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, {},
                                     200.0, 2.5)
    rows_on, _ = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, {},
                                    200.0, 2.5, contents_min_fraction=0.95)
    assert {10, 11, 12} & set(rows_off) == set()
    zs = {rows_on[q][:2] for q in (1, 2, 10, 11, 12)}
    assert len(zs) == 1
    assert rows_on[1][:2] == rows_off[1][:2]      # the building did not move


def test_one_file_never_straddles_two_units():
    """§9's coarsening may put two buildings' bodies in one file; §16g then
    seated the whole file by its MAJORITY unit.  The group is cut along the
    units; a body in no unit stays with the largest piece."""
    P = type("P", (), {})

    def raw(*pids):
        ps = []
        for q in pids:
            p = P()
            p.pid = q
            ps.append(p)
        return (ps, AR.BUILDING)
    rows = {1: ("fu:a",), 2: ("fu:a",), 3: ("fu:b",)}
    groups, n = _split_by_unit([[0, 1, 2, 3]], [raw(1), raw(2), raw(3), raw(9)],
                               rows)
    assert n == 1
    assert groups == [[0, 1, 3], [2]]
    same, n0 = _split_by_unit([[0, 1]], [raw(1), raw(2)], rows)
    assert same == [[0, 1]] and n0 == 0
