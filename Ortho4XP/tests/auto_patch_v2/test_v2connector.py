"""§16g (6) A CONNECTOR JOINS TWO UNITS (owner RULINGS 2026-09-13cn; spec
``object-placement-spec.md`` §16g (6)) — lane ``v2connector``.

The defect the twins pin: SPJC's access-road viaduct
``SPJC_LIMANUEVA_xp11_007__b0`` (span 549 m, end-ground spread 11.58 m) was
named a CONNECTOR by span-and-slope alone, dropped out of the terminal unit
``fu:0:0@cluster_pad`` (datum 19.5604) with NO station cut written, and fell
to §16c's low-side foot at 27.366 — 7.81 m above the unit, its deck 18 m
over the apron.  A body whose every contact chains into ONE unit is that
unit's member however long it is; a body that really does bridge two units
is seated on its HIGH end's datum and never reaches the low-side foot.
"""
from __future__ import annotations

import types

import auto_patch_v2.airport.anchor_rule as AR


# ── the plan shims (the shape ``plan_units`` reads) ──────────────────────

class _PPart:
    def __init__(self, pid, box, line=False):
        self.pid = pid
        self.box = box
        self.line = line
        self.lat = 0.5 * (box[0] + box[2])
        self.lon = 0.5 * (box[1] + box[3])
        self.base_y = 0.0
        self.feet = ()
        self.comp = 0
        self.area_m2 = 1.0


class _PMember:
    def __init__(self, resource, parts, deck_datum_z=None, heading=0.0):
        self.id = resource
        self.resource = resource
        self.parts = tuple(parts)
        self.deck_datum_z = deck_datum_z
        self.deck_ring = None
        self.deck_kind = ""
        self.heading_deg = heading


class _PUnit:
    def __init__(self, uid, members, anchor=(41.0, -3.0)):
        self.id = uid
        self.anchor = anchor
        self.members = tuple(members)


class _PPlan:
    def __init__(self, units, contacts=()):
        self.units = tuple(units)
        self.contacts = tuple(contacts)


#: These twins live at 41 N, NOT at the 40 N every other fixture uses, and
#: the reason is a PRE-EXISTING instrument fragility measured here (it
#: reproduces on main 6ec78/6ec68b44 with no §16g (6) code at all):
#: ``anchor_rule._m_per_deg`` memoises on ``int(lat * 1e4)``, so any
#: earlier caller at 40.00009 N — ``placement_family.union_area_m2``
#: samples slab MIDPOINTS — leaves key 400000 holding 40.00009's value,
#: and ``_m_per_deg(40.0)`` then returns 85393.88093 where cold it returns
#: 85393.93697.  ``test_a_basin_wall_follows_its_ring_...`` builds its
#: ring node at exactly 50 m of longitude and classifies it ``b < 50.0``:
#: 50.00000000000935 cold, 49.99999999998842 warm — the arc flips and the
#: twin reads [100.0, 100.0] instead of [100.0, 101.5].  Serial only (the
#: two files land on different xdist workers).  NAMED, not fixed: it is
#: another law's twin and the fix is a ruling (round the memo key, or
#: nudge the fixture off the boundary).
def _lat(m: float) -> float:
    """The latitude ``m`` metres north of 41 N."""
    return 41.0 + m / 111_132.0


def _blk(la0: float, la1: float, lo0=-3.0000, lo1=-2.9990):
    return (la0, lo0, la1, lo1)


def _chain(pids):
    """The intra-member ε-contacts that make a member's parts ONE body
    (``bodies_of_plan`` is §9's own body law: with no contact declared
    every part is its own body, which no real pack looks like)."""
    return [(pids[i], pids[i + 1]) for i in range(len(pids) - 1)]


# ── the candidate / staged shims (the shape ``bind_footprint_units``
#    mutates — one footed body per member, group 0) ────────────────────────

def _cand(member, boxes, z, pids, cls=None):
    import auto_patch_v2.airport.placement_carrier as _PC
    import auto_patch_v2.airport.placement_boxes as _PB
    hull = _PB.hull_of(list(boxes))
    return _PC.Candidate(member, f"objects/m{member}.obj",
                         AR.Anchor(cls or AR.BUILDING,
                                   0.5 * (hull[0] + hull[2]),
                                   0.5 * (hull[1] + hull[3]), 0.0, "r", z),
                         frozenset(pids), 4, hull, part_boxes=list(boxes),
                         group=0, body_class=cls or AR.BUILDING,
                         fill=1.0, ground_off=0.0)


class _Staged:
    def __init__(self, mi, resource, feet):
        self.mi = mi
        self.m = types.SimpleNamespace(resource=resource)
        self.raw = [([], AR.BUILDING,
                     AR.Anchor(AR.BUILDING, feet[0][0], feet[0][1], 0.0,
                               "r", 0.0), tuple(feet), False, (), (), None)]
        self.groups = [[0]]
        self.ground_off = [0.0]


# ── the twins ────────────────────────────────────────────────────────────

def test_a_long_body_chained_to_one_unit_stays_a_member():
    """§16g (6) (1), THE SPJC VIADUCT: a 549 m body whose every contact
    chains into ONE unit is that unit's MEMBER — "long and sloping" alone
    identifies nothing.  Before 13cn the span-and-slope test named it a
    connector and expelled it."""
    from auto_patch_v2.airport import footprint_unit as FU
    # a terminal of two touching blocks running the length of the site,
    # and a 549 m viaduct beside them: BOTH its ends touch that one unit
    t0 = _PMember("objects/term_a.obj",
                  [_PPart(1, _blk(_lat(0), _lat(300), -3.0, -2.99950))])
    t1 = _PMember("objects/term_b.obj",
                  [_PPart(2, _blk(_lat(300), _lat(620), -3.0, -2.99950))])
    via = _PMember("objects/viaduct.obj",
                   [_PPart(10 + i, _blk(_lat(30 + 10 * i), _lat(40 + 10 * i),
                                        -2.99955, -2.99945))
                    for i in range(55)])
    plan = _PPlan([_PUnit("unit:0", [t0, t1, via])],
                  _chain([10 + i for i in range(55)]))
    units, conns = FU.plan_units_and_connectors(plan, 0.5, 200.0)
    assert conns == [], conns
    assert len(units) == 1
    # the viaduct is IN the unit, with every one of its parts
    assert set(units[0].members) == {"objects/term_a.obj",
                                     "objects/term_b.obj",
                                     "objects/viaduct.obj"}
    assert {10 + i for i in range(55)} <= units[0].pids
    # and the span really is the connector class's — the test that
    # ISOLATED it before is the one that must not fire alone
    assert FU._span_m([p.box for p in via.parts]) > 500.0


def test_a_body_bridging_two_units_is_a_connector_on_the_high_end_datum():
    """§16g (6) (1)/(2): a 300 m body whose two ends touch two DIFFERENT
    units IS a connector — and it is seated on the datum of the unit its
    HIGH end touches (DECK over PAD over GROUND, then the higher zero),
    never dropped."""
    from auto_patch_v2.airport import footprint_unit as FU
    # each end is TWO bodies (a unit is a cluster of at least two)
    lo_b = _PMember("objects/low.obj", [_PPart(1, _blk(_lat(-40), _lat(0))),
                                        _PPart(2, _blk(_lat(0), _lat(40)))])
    hi_b = _PMember("objects/high.obj",
                    [_PPart(3, _blk(_lat(340), _lat(380))),
                     _PPart(4, _blk(_lat(380), _lat(420)))],
                    deck_datum_z=25.0)
    link = _PMember("objects/link.obj",
                    [_PPart(10 + i, _blk(_lat(40 + 10 * i),
                                         _lat(50 + 10 * i),
                                         -2.99955, -2.99945))
                     for i in range(30)])
    plan = _PPlan([_PUnit("unit:0", [lo_b]), _PUnit("unit:1", [hi_b]),
                   _PUnit("unit:2", [link])],
                  _chain([10 + i for i in range(30)]))
    units, conns = FU.plan_units_and_connectors(plan, 0.5, 200.0)
    # THE PARTITION IS UNCHANGED — the link chains the two, so with it in
    # there is one unit, and the connector stays chained in it for the
    # census (§16g (6) (2)).  The two units are what it would leave
    # behind, which is the only way "two different units" can be read.
    assert len(units) == 1, [u.members for u in units]
    assert len(conns) == 1 and conns[0].resource == "objects/link.obj"
    assert conns[0].unit == units[0].id
    ends = (conns[0].end_a, conns[0].end_b)
    assert len(set(ends)) == 2 and "" not in ends
    assert len(conns[0].keys_a) == len(conns[0].keys_b) == 2
    # the low body is at the low end of the axis, the deck at the high one
    assert conns[0].boxes_a[0][0] < conns[0].boxes_b[0][0]
    # the seat: the DECK end wins the priority, whatever the ground says
    counts: dict = {}
    pid_units, _seats = FU.plan_wide_seats(plan, lambda la, lo: 10.0, (),
                                           0.5, 0.0, counts, 200.0)
    row = pid_units[10]
    assert row[1] == 25.0 and row[3] == "deck"      # the HIGH end's datum
    assert row[0] == conns[0].end_b and row[4] == ends
    # ... and the ordinary members keep the plain unit seat
    assert pid_units[1][0] == units[0].id and pid_units[1][4] == ("", "")
    assert counts["plan_wide_connectors"] == 1
    assert counts["plan_wide_connectors_to_open_ground"] == 0


def test_a_connector_never_reaches_the_low_side_foot():
    """§16g (6) (2): the exclusion in ``_bind_plan_wide`` is REPLACED by a
    seat.  An identified connector is bound with the unit at its HIGH
    end's datum and publishes ``connector_of``; nothing hands it back to
    §16c, which is the 7.81 m the owner read at SPJC."""
    from auto_patch_v2.airport import footprint_unit as FU
    box_lo = [_blk(_lat(-40), _lat(0)), _blk(_lat(0), _lat(40))]
    box_hi = [_blk(_lat(340), _lat(380)), _blk(_lat(380), _lat(420))]
    link_boxes = [_blk(_lat(40 + 10 * i), _lat(50 + 10 * i),
                       -2.99955, -2.99945) for i in range(30)]
    lo_b = _PMember("objects/low.obj",
                    [_PPart(1 + i, b) for i, b in enumerate(box_lo)])
    hi_b = _PMember("objects/high.obj",
                    [_PPart(3 + i, b) for i, b in enumerate(box_hi)],
                    deck_datum_z=25.0)
    link = _PMember("objects/link.obj",
                    [_PPart(10 + i, b) for i, b in enumerate(link_boxes)])
    plan = _PPlan([_PUnit("unit:0", [lo_b]), _PUnit("unit:1", [hi_b]),
                   _PUnit("unit:2", [link])],
                  _chain([10 + i for i in range(30)]))
    counts: dict = {}

    def surface(la, lo):          # the ground CLIMBS 15 m along the link
        return 10.0 + 15.0 * (la - 41.0) / (_lat(380) - 41.0)

    pw, _seats = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, counts,
                                    200.0)
    cands = [_cand(0, box_lo, 10.0, {1, 2}),
             _cand(1, box_hi, 25.0, {3, 4}),
             _cand(2, link_boxes, 12.0, {10 + i for i in range(30)})]
    st = [_Staged(0, "objects/low.obj",
                  [(b[0], b[1], 0.0) for b in box_lo]),
          _Staged(1, "objects/high.obj",
                  [(b[0], b[1], 0.0) for b in box_hi]),
          _Staged(2, "objects/link.obj",
                  [(b[0], b[1], 0.0) for b in link_boxes])]
    FU.bind_footprint_units(cands, st, surface, (), counts,
                            unit_id="unit:2", touch_m=0.5, visual_m=0.5,
                            connector_span_m=200.0, plan_wide=pw)
    a = cands[2].anchor
    assert counts["unit_connectors_cut"] == 0            # the bar
    assert counts["unit_connectors_seated"] == 1
    assert a.reason.startswith(FU.UNIT_REASON)           # NOT a low-side foot
    assert "CONNECTOR" in a.reason
    assert a.connector_of.count("|") == 1 and a.connector_of != "|"
    # seated on the HIGH end's datum (the deck's 25.0), not its own ground
    assert abs(a.surface_z - a.y_zero - 25.0) < 1e-6


def test_the_authored_unit_is_the_shared_dsf_origin_and_heading():
    """§16g (6) (3) PROVENANCE IS A WITNESS: placements written at one DSF
    origin and heading are one authored unit, and a footprint partition
    that separates two siblings raises ``unit_split_authored`` (WARN).
    SPJC's eleven ``LIMANUEVA`` rows are one such group."""
    from auto_patch_v2.airport import footprint_unit as FU
    a0 = _PMember("objects/a0.obj", [_PPart(1, _blk(_lat(0), _lat(40)))],
                  heading=154.4097)
    a1 = _PMember("objects/a1.obj", [_PPart(2, _blk(_lat(40), _lat(80)))],
                  heading=154.4097)
    far = _PMember("objects/far.obj",
                   [_PPart(3, _blk(_lat(5000), _lat(5040)))],
                   heading=154.4097)
    other = _PMember("objects/o.obj", [_PPart(4, _blk(_lat(10), _lat(20)))],
                     heading=12.0)
    plan = _PPlan([_PUnit("unit:0", [a0, a1, far],
                          anchor=(-12.029084649, -77.11676585)),
                   _PUnit("unit:1", [other], anchor=(-12.0, -77.0))])
    au = FU.authored_units(plan)
    assert au[(0, 0)] == au[(0, 1)] == au[(0, 2)]        # one DSF origin
    assert au[(1, 0)] != au[(0, 0)]                      # a different row
    # a0/a1 touch and are one footprint unit; `far` is 5 km away and
    # forms none — so nothing is SPLIT
    units = FU.plan_units(plan, 0.5)
    pid_units = {q: (u.id, 0.0, "", "ground", ("", ""))
                 for u in units for q in u.pids}
    c = FU.authored_unit_census(plan, pid_units)
    assert c["unit_split_authored"] == 0 and c["authored_units"] == 2
    # ... and a partition that DOES separate two siblings is the WARN
    split = dict(pid_units)
    split[2] = ("fu:9:9", 0.0, "", "ground", ("", ""))
    assert FU.authored_unit_census(plan, split)["unit_split_authored"] == 1


def test_one_unit_and_open_ground_beyond_the_span_is_a_connector():
    """§16g (6) (1)'s second clause: a body touching ONE unit whose other
    end has nothing within ``connector_span_m`` connects that unit to open
    ground — the HECA elevated-rail reading — while the same body with a
    unit inside that reach is a member."""
    from auto_patch_v2.airport import footprint_unit as FU

    def arm(far_m):
        anchor = _PMember("objects/anchor.obj",
                          [_PPart(1, _blk(_lat(0), _lat(40)))])
        rail = _PMember("objects/rail.obj",
                        [_PPart(10 + i, _blk(_lat(40 + 10 * i),
                                             _lat(50 + 10 * i),
                                             -2.99955, -2.99945))
                         for i in range(40)])
        rest = _PMember("objects/rest.obj",
                        [_PPart(500, _blk(_lat(far_m), _lat(far_m + 40)))])
        # a second body beside the anchor so the anchor forms a unit at all
        mate = _PMember("objects/mate.obj",
                        [_PPart(2, _blk(_lat(20), _lat(50)))])
        mate2 = _PMember("objects/mate2.obj",
                         [_PPart(501, _blk(_lat(far_m - 20), _lat(far_m)))])
        plan = _PPlan([_PUnit("unit:0",
                              [anchor, mate, rail, rest, mate2])],
                      _chain([10 + i for i in range(40)]))
        return FU.plan_units_and_connectors(plan, 0.5, 200.0)[1]

    # the far unit sits 900 m past the rail's south end: open ground
    far = arm(1300.0)
    assert len(far) == 1 and "" in (far[0].end_a, far[0].end_b)
    # ... and 100 m past it: a unit within the reach, so it is a member
    assert arm(500.0) == []
