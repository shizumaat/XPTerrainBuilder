"""#1689 / #1718: a headwall portal holds the survey's cover BEHIND its
roof, and the road under a hard-deck bridge is the deck's.

* ``portal_objects._ground_covers_roof`` reads the cover over the bore
  inward from the end (as far as the roof reaches along it, plus
  ``bore_end_tolerance_m``) against the lowest of the end and the road the
  tolerance out of it: a survey cell straddling the mouth blends the cut's
  two sides, and the roof plan alone reads no cover.
* ``walled_pit.hard_deck_share``: the share of a floor under a ``flag`` /
  ``signature`` hard deck of its frame standing a road's clearance
  (``bridge.clearance_minimum_m``) over it -- a walled pit or a portal floor
  read under it would give the bridge's frame a second zero; a pit whose
  own floor is hard deck still reads (R2 A1).
* ``terrain_shaped.portal_frame_records``: a roofed portal leads only the
  co-placed placements standing half in its OWN FOOTPRINT (its solids'
  plan, ``portal_objects._solids_plan``) grown by ``bore_end_tolerance_m``
  (R2 A2, R3).
* ``portal_objects._front_wall_top``: a TALL portal's top is its front
  wall's own top over its zero, read on the walls at the end (R3).
* ``planar/entrance_skirt``: a TALL portal states its top (R2 A3); its skirt
  keeps off roads and foreign pads (A4); its host pad is cut by its own
  footprint grown by ``entrance_skirt_m`` (``host_blade``, A5 / R3); an
  entrance face's skirt and blade are unchanged.
* ``planar/structures._cut_part_refs``: the largest surviving part of a cut
  cell keeps its plain ref; ``pad_touch.without_pads`` drops the touch
  witness to a pad cut to nothing (R3, A6).
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import portal_objects as P
from auto_patch_v2.airport.walled_pit import hard_deck_share
from auto_patch_v2.law import Law
from shapely.geometry import Point, box

LAW = Law.for_airport("")


def _cut_dem(x: float, y: float) -> float:
    """A road at 169 m for x < 0 rising through a blended cell to cover at
    177 m by x = 10 (the bore runs along +x from its end at the origin)."""
    if x <= -5.0:
        return 169.0
    if x >= 10.0:
        return 177.0
    return 169.0 + (x + 5.0) / 15.0 * 8.0


def test_cover_behind_the_roof_is_read_along_the_bore():
    roof = box(-12.0, -15.0, 2.0, 15.0)   # the headwall's top, mostly out over the road
    assert P._ground_covers_roof(roof, (0.0, 0.0), _cut_dem, LAW) is None
    cover = P._ground_covers_roof(roof, (0.0, 0.0), _cut_dem, LAW, (1.0, 0.0))
    assert cover is not None and cover >= 169.0 + LAW.tables.structures.channel.object_min_depth_m


def test_no_cover_where_the_ground_is_flat():
    flat = lambda x, y: 170.0  # noqa: E731
    roof = box(-12.0, -15.0, 2.0, 15.0)
    assert P._ground_covers_roof(roof, (0.0, 0.0), flat, LAW, (1.0, 0.0)) is None


import numpy as np  # noqa: E402

#: a 10 x 10 m plate in OBJ (x, z), two triangles, at OBJ height ``y``
_PLATE_T = np.array([[0, 1, 2], [0, 2, 3]])


def _plate(y: float):
    v = np.array([[0.0, y, 0.0], [10.0, y, 0.0], [10.0, y, 10.0], [0.0, y, 10.0]])
    return types.SimpleNamespace(vertices=v, solid=_PLATE_T, hard_deck=_PLATE_T)


class _Cache:
    """Resource -> geometry / plan box (``ResourceCache``'s two reads)."""

    def __init__(self, geoms=None, boxes=None):
        self.geoms, self.boxes = geoms or {}, boxes or {}

    def geometry(self, path):
        return self.geoms.get(path)

    def y_range(self, path):
        x0, x1, z0, z1 = self.boxes[path]
        return (0.0, 1.0, x0, x1, z0, z1)


def _placed(path, kind="flag", xy=(0.0, 0.0), hdg=0.0, i=0):
    return types.SimpleNamespace(id=f"dsf:obj{i}", path=path, resolved=path, xy=xy,
                                 heading_deg=hdg, deck_kind=kind, plan_bbox=None)


#: the plate's plan in the frame (heading 0: north = -z)
_FOOT = box(0.0, -10.0, 10.0, 0.0)


def _share(deck_y, kind="flag"):
    cache = _Cache({"d.obj": _plate(deck_y)})
    return hard_deck_share(_FOOT, [_placed("d.obj", kind)], cache, LAW, lambda _p: 0.0, 0.0)


def test_a_pit_whose_own_floor_is_hard_deck_still_reads():
    """#1689 R2 F8: OTHH TerminalRoads_02_000 -- 96 % of its floor under its
    OWN ATTR_hard_deck -- is a pit: a deck at the floor is no road under it."""
    assert _share(0.0) == 0.0


def test_a_deck_a_road_clearance_over_the_floor_is_refused():
    """A deck whose lowest vertex stands clearance_minimum_m (4.2) over the
    floor is a bridge a road passes under; 4.1 m is not."""
    assert LAW.tables.structures.bridge.clearance_minimum_m == 4.2
    assert _share(4.2) == 1.0 >= LAW.tables.structures.deck.on_fraction
    assert _share(4.1) == 0.0
    assert _share(6.0, kind="candidate") == 0.0


def _obj(i, xy=(0.0, 0.0), hdg=10.0, path=None):
    p = path or f"Objects/p{i}.obj"
    return types.SimpleNamespace(id=f"dsf:obj{i}", path=p, resolved=p, xy=xy, heading_deg=hdg)


def test_a_roofed_portal_leads_its_frame():
    from auto_patch_v2.airport.terrain_shaped import PORTAL_SEAT, portal_frame_records
    objs = [_obj(1), _obj(2), _obj(3, xy=(0.5, 0.0)), _obj(4, xy=(40.0, 0.0)),
            _obj(5, hdg=95.0), _obj(6)]
    cache = _Cache(boxes={o.path: (-5.0, 5.0, -5.0, 5.0) for o in objs})
    recs = [{"id": "dsf:obj1", "resource": "Objects/p1.obj", "datum": "portal",
             "seat": PORTAL_SEAT, "elevation": 168.7},
            {"id": "dsf:obj6", "resource": "Objects/p6.obj", "seat": "object floor",
             "elevation": 160.0}]
    roofs = {"dsf:obj1": box(-10.0, -10.0, 10.0, 10.0)}
    got = portal_frame_records(recs, objs, 2.0, roofs, cache, 5.0)
    assert {r["id"] for r in got} == {"dsf:obj2", "dsf:obj3"}
    assert all(r["elevation"] == 168.7 and r["led_by"] == "dsf:obj1" for r in got)
    # no roof plan: the portal leads nothing
    assert portal_frame_records(recs, objs, 2.0, {}, cache, 5.0) == []


def test_the_lead_stops_at_the_roof_reach_on_a_shared_datum():
    """#1689 R2 A2 / F9 (LFMN ``LFMN_Bld10_08``: 82 co-placed mates): 50
    placements share one datum; only those whose plan box stands half in
    the roof grown by bore_end_tolerance_m are led."""
    from auto_patch_v2.airport.terrain_shaped import PORTAL_SEAT, portal_frame_records
    objs = [_obj(i, hdg=0.0) for i in range(50)]
    # box i spans x 10 i .. 10 i + 8 (heading 0: east = x)
    cache = _Cache(boxes={o.path: (10.0 * i, 10.0 * i + 8.0, -4.0, 4.0)
                          for i, o in enumerate(objs)})
    recs = [{"id": "dsf:obj0", "resource": objs[0].path, "seat": PORTAL_SEAT,
             "elevation": 170.0}]
    tol = LAW.tables.structures.tunnel.object.bore_end_tolerance_m
    got = portal_frame_records(recs, objs, 2.0, {"dsf:obj0": box(0.0, -4.0, 20.0, 4.0)},
                               cache, tol)
    # boxes 1 (10-18) and 2 (20-28: half within 20 + 5) are led, 3 (30-38) is not
    assert {r["id"] for r in got} == {"dsf:obj1", "dsf:obj2"}


def _pin(entrance: bool):
    return types.SimpleNamespace(face_plan=box(-10.0, 0.0, 10.0, 6.0), face_top_z=177.88,
                                 bottom_y=-1.0 if entrance else None)


def _cell(role, ref, side="groundside"):
    return types.SimpleNamespace(role=role, ref=ref, side=side)


def _skirt(pin, cells, polys, hosts=frozenset()):
    from auto_patch_v2.planar.entrance_skirt import entrance_skirt
    ramp = box(-10.0, -40.0, 10.0, 0.0)
    return entrance_skirt(pin, ramp, cells, polys, LAW, lambda x, y: 176.0, 1.0, hosts)


def test_a_tall_portal_skirt_keeps_off_a_road_and_a_foreign_pad():
    """#1689 R2 A4: a roofed portal's skirt (a top, no bottom) keeps off
    every road cell and every pad but its hosts, by the stand-off; an
    entrance face's skirt is unchanged by them (byte-equal)."""
    road = box(-30.0, 8.0, 30.0, 14.0)
    pad = box(12.0, -5.0, 30.0, 6.0)
    cells = [_cell("service_road", "route1"), _cell("building", "building9")]
    core, bank, top = _skirt(_pin(False), cells, [road, pad])
    assert top == 177.88
    assert core.intersection(road.buffer(1.0 - 1e-6)).area < 1e-6
    assert core.intersection(pad.buffer(1.0 - 1e-6)).area < 1e-6
    hosted, _b, _t = _skirt(_pin(False), cells, [road, pad], hosts={"building9"})
    assert hosted.intersection(pad).area > 1.0
    # an entrance face: the same skirt with or without the road and the pad
    alone = _skirt(_pin(True), [], [])
    beside = _skirt(_pin(True), cells, [road, pad])
    assert all(a.equals(b) for a, b in zip(alone[:2], beside[:2], strict=True))
    assert alone[0].wkb == beside[0].wkb


def test_a_tall_portal_cuts_its_host_pad_whole():
    """#1689 R2 A5: the host pad (the frame's own footprint read as a
    building) inside the roof grown by entrance_skirt_m is cut to nothing;
    an entrance face's blade is its footprint alone."""
    from auto_patch_v2.planar.entrance_skirt import host_blade
    outer = box(-10.0, -40.0, 10.0, 1.0)
    host = box(-9.0, -1.0, 9.0, 8.0)                 # the frame's U ring, behind the roof
    blade = host_blade(_pin(False), outer, (), LAW)
    assert host.difference(blade).area < 0.25
    assert host_blade(_pin(True), outer, (), LAW) is outer
    assert host.difference(host_blade(_pin(True), outer, (), LAW)).area > 100.0


def test_the_lead_reaches_the_portal_footprint_beyond_its_roof():
    """#1689 R3: KBNA Murfreesboro east -- the wing blocks and road plate
    stand out along the road past the stub roof, inside the portal
    object's own footprint: they are led; a placement past the footprint
    is not."""
    from auto_patch_v2.airport.terrain_shaped import PORTAL_SEAT, portal_frame_records
    objs = [_obj(i, hdg=0.0) for i in range(4)]
    cache = _Cache(boxes={objs[0].path: (-20.0, 20.0, -3.0, 4.0),    # the portal
                          objs[1].path: (-20.0, -12.0, 5.0, 26.0),   # a wing block
                          objs[2].path: (-12.0, 12.0, 5.0, 26.0),    # the road plate
                          objs[3].path: (-12.0, 12.0, 60.0, 80.0)})  # beyond
    recs = [{"id": "dsf:obj0", "resource": objs[0].path, "seat": PORTAL_SEAT,
             "elevation": 168.71}]
    tol = LAW.tables.structures.tunnel.object.bore_end_tolerance_m
    # heading 0: frame (x, -z)
    roof = box(-20.0, -4.0, 20.0, 3.0)
    foot = box(-20.0, -26.0, 20.0, 3.0)
    got = portal_frame_records(recs, objs, 2.0, {"dsf:obj0": foot}, cache, tol)
    assert {r["id"] for r in got} == {"dsf:obj1", "dsf:obj2"}
    assert portal_frame_records(recs, objs, 2.0, {"dsf:obj0": roof}, cache, tol) == []


def _tall_portal():
    """A stub roof (y 7.78, z -2..4.5) with a headwall in front of it
    (walls x -12.6 / 13 at z 5, to y 9.17) and a mast 30 m off (to y 15),
    in OBJ ``(x, y, z)``."""
    v, t = [], []

    def quad(a, b, c, d):
        k = len(v)
        v.extend([a, b, c, d])
        t.extend([[k, k + 1, k + 2], [k, k + 2, k + 3]])

    quad((-19.0, 7.78, -2.0), (19.0, 7.78, -2.0), (19.0, 7.78, 4.5), (-19.0, 7.78, 4.5))
    quad((-12.6, 0.5, 4.9), (-12.6, 0.5, 5.4), (-12.6, 9.17, 5.4), (-12.6, 9.17, 4.9))
    quad((13.0, 0.5, 4.9), (13.0, 0.5, 5.4), (13.0, 8.5, 5.4), (13.0, 8.5, 4.9))
    quad((50.0, 0.0, 0.0), (50.0, 0.0, 0.5), (50.0, 15.0, 0.5), (50.0, 15.0, 0.0))
    g = types.SimpleNamespace(vertices=np.array(v, dtype=float))
    comp = types.SimpleNamespace(tris=np.array(t))
    return g, [comp]


def test_a_tall_portal_states_its_front_wall_top():
    """#1689 R3 (master ruling 2026-11-15): the top is the headwall's own
    top (9.17 over the zero), not the stub roof (7.78); a wall standing off
    the roof's reach (the mast) is no front wall; no wall -> ``None``."""
    g, genuine = _tall_portal()
    o = types.SimpleNamespace(xy=(0.0, 0.0), heading_deg=0.0)
    roof = box(-19.0, -4.5, 19.0, 2.0)          # heading 0: frame (x, -z)
    assert abs(P._front_wall_top(o, g, genuine, roof, LAW) - 9.17) < 1e-9
    assert P._front_wall_top(o, g, genuine, box(-60.0, 100.0, -50.0, 110.0), LAW) is None
    flat = types.SimpleNamespace(tris=genuine[0].tris[:2])
    assert P._front_wall_top(o, g, [flat], roof, LAW) is None


def test_the_solids_plan_is_the_portal_footprint():
    g, genuine = _tall_portal()
    o = types.SimpleNamespace(xy=(100.0, 50.0), heading_deg=0.0)
    foot = P._solids_plan(o, g, genuine, LAW)
    # the roof's plan (walls stand edge-on): x 81..119, y 45.5..52
    assert abs(foot.area - 38.0 * 6.5) < 1.0
    assert foot.bounds[0] == 81.0 and foot.bounds[3] == 52.0


def test_a_tall_portal_cuts_its_host_pad_to_its_own_footprint():
    """#1689 R3: the host pad running out past the top plan along the wings
    is cut whole by the footprint grown by entrance_skirt_m."""
    from auto_patch_v2.planar.entrance_skirt import host_blade
    outer = box(-10.0, -40.0, 10.0, 1.0)
    host = box(-11.0, -1.0, 11.0, 28.0)          # the U ring out along the wings
    pin = _pin(False)
    assert host.difference(host_blade(pin, outer, (), LAW)).area > 100.0
    pin.footprint = box(-10.0, 0.0, 10.0, 26.0)
    assert host.difference(host_blade(pin, outer, (), LAW)).area < 0.25


def test_the_largest_cut_part_keeps_the_plain_ref():
    from auto_patch_v2.planar.structures import _cut_part_refs
    parts = [box(0.0, 0.0, 0.4, 0.4), box(0.0, 0.0, 1.0, 1.0), box(0.0, 0.0, 5.0, 5.0)]
    assert [r for r, _p in _cut_part_refs("building5", False, parts)] == \
        ["building5#1", "building5"]
    assert [r for r, _p in _cut_part_refs("rwy", True, parts)] == ["rwy", "rwy"]
    assert _cut_part_refs("building5", False, [box(0.0, 0.0, 0.4, 0.4)]) == []


def test_a_pad_cut_to_nothing_leaves_no_touch_witness():
    from auto_patch_v2.classify.pad_touch import EVIDENCE_KEY, HELD_KEY, without_pads

    @__import__("dataclasses").dataclass(frozen=True)
    class C:
        ref: str
        evidence: dict

    cells = [C("road1", {EVIDENCE_KEY: {"building5": 0.0, "building9": 3.0},
                         HELD_KEY: ("building5",)}),
             C("road2", {EVIDENCE_KEY: {"building5": 0.0}}), C("road3", {})]
    out = without_pads(cells, {"building5"})
    assert out[0].evidence == {EVIDENCE_KEY: {"building9": 3.0}, HELD_KEY: ()}
    assert out[1].evidence == {}
    assert out[2] is cells[2]
    assert without_pads(cells, set()) == cells


# ── #1689 R4: wings and the corridor out of the mouth ──────────────────

class _Geom:
    """OBJ ``(x, y, z)`` quads as a still solid geometry."""

    def __init__(self):
        self.v, self.t = [], []

    def quad(self, a, b, c, d):
        k = len(self.v)
        self.v.extend([a, b, c, d])
        self.t.extend([[k, k + 1, k + 2], [k, k + 2, k + 3]])

    def wall_z(self, x, z0, z1, y0, y1):
        """A wall in the plane x = ``x`` along z ``z0..z1``, y ``y0..y1``."""
        self.quad((x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0))

    def plate(self, x0, x1, z0, z1, y):
        self.quad((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))

    def slab(self, x0, x1, z0, z1, y0, y1):
        """A closed box: its two plates and four walls."""
        self.plate(x0, x1, z0, z1, y1)
        self.plate(x0, x1, z0, z1, y0)
        self.wall_z(x0, z0, z1, y0, y1)
        self.wall_z(x1, z0, z1, y0, y1)
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
        self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))

    def done(self):
        return types.SimpleNamespace(vertices=np.array(self.v, dtype=float),
                                     solid=np.array(self.t), animated=np.zeros(0, bool))


def _stub(gm: _Geom, top: float = 7.78):
    """The stub roof (x -19..19, z -2..4.5) and the headwall under its front
    edge (z 4.5) to 9.17."""
    gm.plate(-19.0, 19.0, -2.0, 4.5, top)
    gm.quad((-19.0, 0.5, 4.5), (19.0, 0.5, 4.5), (19.0, 9.17, 4.5), (-19.0, 9.17, 4.5))


#: heading 0: frame (x, -z); the bore runs +y (into) from its end at the origin
_ROOF = box(-19.0, -4.5, 19.0, 2.0)
_O = types.SimpleNamespace(xy=(0.0, 0.0), heading_deg=0.0)


def _wings(g, top=9.17, into=(0.0, 1.0)):
    return P._wing_plan(_O, g, _ROOF, _ROOF, top, (0.0, 0.0), into, LAW)


def test_a_tall_portal_reads_its_wings():
    """T1: two wing walls running 16 m out of the bore to 8.8 are the
    wings; the end steps (to 3.9) and a mast 30 m off are not."""
    gm = _Geom()
    _stub(gm)
    gm.wall_z(-12.6, 4.5, 20.5, 0.5, 8.8)
    gm.wall_z(13.0, 4.5, 20.5, 0.5, 8.8)
    gm.plate(-20.0, -14.0, 20.5, 23.0, 3.9)                 # the end steps
    gm.wall_z(50.0, 0.0, 0.5, 0.0, 15.0)                    # the mast
    wing = _wings(gm.done())
    parts = list(getattr(wing, "geoms", [wing]))
    assert len(parts) == 2
    for q, x in zip(sorted(parts, key=lambda q: q.bounds[0]), (-12.6, 13.0), strict=True):
        x0, y0, x1, y1 = q.bounds
        assert x0 < x < x1 and x1 - x0 < 0.3
        assert abs(y0 + 20.6) < 0.05 and y1 < -4.5
    assert wing.intersection(box(-21.0, -24.0, -13.0, -20.7)).area < 1e-9
    assert wing.distance(box(48.0, -2.0, 52.0, 2.0)) > 20.0
    assert _wings(gm.done(), into=None) is None


def test_a_capped_wing_is_read_by_its_walls():
    """T2: a wing whose only horizontal face is a 0.26 m cap in its own
    component is still read (no genuine filter at the top)."""
    gm = _Geom()
    _stub(gm)
    gm.slab(12.8, 13.2, 4.5, 20.5, 8.54, 8.8)
    wing = _wings(gm.done())
    assert wing is not None and wing.bounds[1] < -20.0


def test_a_roof_flank_is_no_wing():
    """T3: a crowned slab's flank plates (within 1 m of the top, beside the
    top bin, at the roof's own stations) run nowhere out of the bore."""
    gm = _Geom()
    _stub(gm, top=9.0)
    gm.plate(19.0, 22.0, -2.0, 4.5, 8.6)
    gm.plate(-22.0, -19.0, -2.0, 4.5, 8.6)
    assert _wings(gm.done()) is None


def test_a_headwall_return_is_no_wing():
    """T4: a wall running under entrance_skirt_m (3 m) beyond the roof's
    front is the headwall's return, not a wing."""
    gm = _Geom()
    _stub(gm)
    gm.wall_z(13.0, 4.5, 6.5, 0.5, 9.17)
    assert _wings(gm.done()) is None


def _r4_skirt(pin, outward):
    from auto_patch_v2.planar.entrance_skirt import entrance_skirt
    ramp = box(-10.0, -5.0, 10.0, 0.0)
    return entrance_skirt(pin, ramp, [], [], LAW, lambda x, y: 176.0, 1.0, outward=outward)


def test_the_corridor_out_of_the_mouth_is_never_skirt():
    """T5: with ``outward`` no part of the level piece or the bank stands in
    the ramp's prolongation; the level piece runs along a wing's outer side
    to its end."""
    pin = _pin(False)
    pin.face_plan = box(-10.0, 0.0, 10.0, 6.0).union(box(10.0, -16.0, 10.4, 0.0))
    corridor = box(-10.0, -300.0, 10.0, -5.0)
    core, bank, _t = _r4_skirt(pin, None)
    assert core.intersection(corridor).area > 1.0          # R3: it wrapped round
    core, bank, _t = _r4_skirt(pin, (0.0, -1.0))
    assert core.intersection(corridor).area < 1e-6
    assert bank.intersection(corridor).area < 1e-6
    assert core.contains(Point(12.0, -15.5))


def test_the_corridor_rule_leaves_entrance_faces_and_r3_alone():
    """T6: an entrance pin with ``outward`` equals the same pin without it;
    a tall pin with ``outward=None`` equals R3."""
    from auto_patch_v2.planar.entrance_skirt import entrance_skirt
    ramp = box(-10.0, -5.0, 10.0, 0.0)
    for pin in (_pin(True), _pin(False)):
        r3 = entrance_skirt(pin, ramp, [], [], LAW, lambda x, y: 176.0, 1.0)
        none = _r4_skirt(pin, None)
        assert all(a.wkb == b.wkb for a, b in zip(r3[:2], none[:2], strict=True))
    ent = _pin(True)
    a, b = _r4_skirt(ent, (0.0, -1.0)), _r4_skirt(ent, None)
    assert all(x.wkb == y.wkb for x, y in zip(a[:2], b[:2], strict=True))


# ── #1689 R5: the frame's cover and soffit, its back, the parapet, two levels ──

def _r5_frame(ceiling: bool = True):
    """T1's frame, three co-placed pieces read as one (heading 0: frame
    ``(x, -z)``; the bore runs INTO frame -y): a deck sheet ONE side thick
    at 7.4 (frame y -4..21), a 0.9 m parapet top at 8.9 across it at y
    12..12.9 (two sided: 155 m2 of triangles, 77 m2 of plan), a ceiling at
    6.0 (y -4..19) between jamb walls at x +-16.5, a median wall at x 0."""
    gm = _Geom()
    gm.plate(-40.0, 40.0, -21.0, 4.0, 7.4)
    gm.plate(-43.0, 43.0, -12.9, -12.0, 8.9)
    gm.plate(-43.0, 43.0, -12.9, -12.0, 8.9)            # its underside: two sided
    gm.quad((-43.0, 7.4, -12.0), (43.0, 7.4, -12.0), (43.0, 8.9, -12.0), (-43.0, 8.9, -12.0))
    if ceiling:
        gm.plate(-16.5, 16.5, -19.0, 4.0, 6.0)
    for x in (-16.5, 0.0, 16.5):
        gm.wall_z(x, -19.0, 4.0, 0.0, 6.0)
    g = gm.done()
    return g.vertices, g.solid


_O5 = types.SimpleNamespace(xy=(0.0, 0.0), heading_deg=0.0)
#: the mapped end 6.7 m up the road (frame +y) from the parapet
_END5 = (0.0, 12.9 + 6.7)
_INTO5 = (0.0, -1.0)


def test_r5_t1_the_cover_is_the_deck_and_the_soffit_the_ceiling():
    """T1: the cover is the deck at 7.4 (its one sided plan), never the
    parapet's top (a wall top, however much triangle area); the soffit is
    the ceiling; the parapet stands over the cover."""
    top, cover, soffit = P._covers(_r5_frame(), _END5, _O5, LAW)
    assert abs(top - 7.4) < 1e-9
    assert abs(cover.area - 80.0 * 25.0) < 1.0
    assert soffit.bounds == (-16.5, -4.0, 16.5, 19.0)
    para = P._parapet(_O5, _r5_frame(), top, LAW)
    assert para is not None and 11.8 < para.bounds[1] and para.bounds[3] < 13.1


def test_r5_t2_the_opening_up_the_road_is_the_soffit_jamb_to_jamb():
    """T2: the end up the road opens over the ceiling's span, jamb to jamb
    (the median wall is no jamb); without the ceiling there is no soffit
    and the reading is R4's (the circle round the end)."""
    tol = LAW.tables.structures.tunnel.object.bore_end_tolerance_m
    _t, _c, soffit = P._covers(_r5_frame(), _END5, _O5, LAW)
    width, edges = P._roof_opening(soffit, _END5, _INTO5, tol)
    assert abs(width - 33.0) < 1e-6
    assert sorted(round(e[0], 6) for e in edges) == [-16.5, 16.5]
    assert P._covers(_r5_frame(ceiling=False), _END5, _O5, LAW)[2] is None


def test_r5_t3_a_stub_roof_reads_its_own_roof_as_the_cover():
    """T3: a stub roof over the end: the cover is the roof R4 read (the
    same plan, the same top), so the opening, face_plan and face_top_z it
    states are R4's; one bin, no soffit."""
    gm = _Geom()
    _stub(gm)
    g = gm.done()
    horiz = P._face_normals_y(g.vertices, g.solid) >= \
        LAW.tables.structures.tunnel.object.plate_normal_y_min
    ymax = g.vertices[g.solid][:, :, 1].max(axis=1)
    y, _a, plan = P.roof_of(g.vertices, g.solid, horiz, P._plan_area(g.vertices, g.solid),
                            ymax, LAW.tables.structures.tunnel.object)
    top, cover, soffit = P._covers((g.vertices, g.solid), (0.0, 0.0), _O, LAW)
    roof = P._fe.enter([plan], P._obj8.placement_affine(_O.xy, _O.heading_deg),
                       P._fe.quantum(LAW))[0]
    assert top == y and cover.equals(roof) and soffit is None


def _m1(cover):
    from auto_patch_v2.planar.structure_mouth import roof_back_mouth
    from shapely.geometry import LineString
    axis = LineString([(0.0, 0.0), (0.0, -100.0)])            # the mouth outward (-y)
    return roof_back_mouth(axis, (0.0, 1.0), cover, 2.1, 10.0, 0.5)


def test_r5_t4_the_cap_never_stands_beyond_the_covers_back():
    """T4 (M1): a cover whose back stands 0.6 m into the bore: the mouth
    moves out until the cap (rim_off 1.6 beyond it, snapped) stands on the
    back within one grid step; a cover running 5 m past the mouth: kept."""
    axis, moved = _m1(box(-12.0, -15.0, 12.0, 0.6))
    assert moved < 0.0 and abs(axis.coords[0][1] - moved) < 1e-9
    cap = axis.coords[0][1] + 1.6
    assert 0.6 - 0.5 - 1e-9 <= cap <= 0.6 + 0.5
    axis, moved = _m1(box(-12.0, -15.0, 12.0, 5.0))
    assert moved == 0.0 and axis.coords[0] == (0.0, 0.0)


def _r5_pin(wings: bool, parapet=None):
    """A tall pin over a cover (frame: the bore runs into +y from its end
    at the origin): the cover y -6..2.35, two wing walls running 16 m out
    of the bore beyond its front when ``wings``."""
    cover = box(-19.0, -6.0, 19.0, 2.35)
    wing = box(-13.0, -22.0, -12.8, -6.0).union(box(12.8, -22.0, 13.0, -6.0))
    return types.SimpleNamespace(
        face_plan=cover.union(wing) if wings else cover, face_top_z=177.88, bottom_y=None,
        cover_plan=cover, cover_top_z=176.49, parapet_plan=parapet, end_xy=(0.0, 0.0))


def _r5_skirt(pin, outward=(0.0, -1.0)):
    from auto_patch_v2.planar.entrance_skirt import entrance_skirt
    ramp = box(-10.0, -60.0, 10.0, 0.25)
    return entrance_skirt(pin, ramp, [], [], LAW, lambda x, y: 174.0, 1.0, outward=outward)


def test_r5_t5_no_skirt_in_front_of_a_parapet():
    """T5 (S1): no part of the level piece or the bank stands in the
    parapet's prolongation out of the bore; the piece behind it stands."""
    para = box(-19.0, -4.0, -11.0, -3.5)
    core, bank, top = _r5_skirt(_r5_pin(False, para))
    ahead = box(-19.0, -60.0, -11.0, -4.0)
    assert top == 176.49
    assert core.intersection(ahead).area < 1e-6 and bank.intersection(ahead).area < 1e-6
    assert core.contains(Point(-15.0, 0.0)) and core.contains(Point(15.0, -5.0))


def test_r5_t6_two_levels_with_wings_one_without():
    """T6 (S2 / S3): with wings, the cover's piece and the wings' piece, a
    grid strip between them and no shared vertex, each pinned at its own
    level; without wings, one piece under the old ref at the cover's top."""
    from auto_patch_v2.constraints.entrance_skirt import skirt_pins
    from auto_patch_v2.planar.entrance_skirt import skirt_refs
    got = _r5_skirt(_r5_pin(True))
    assert len(got) == 5
    inner, bank, level, outer, wing_top = got
    assert (level, wing_top) == (176.49, 177.88)
    assert inner.distance(outer) >= 0.5 - 1e-9
    assert outer.contains(Point(-13.9, -15.0)) and inner.contains(Point(-15.0, 0.0))
    vi = {c for g in getattr(inner, "geoms", [inner]) for c in g.exterior.coords}
    vo = {c for g in getattr(outer, "geoms", [outer]) for c in g.exterior.coords}
    assert not vi & vo
    one = _r5_skirt(_r5_pin(False))
    assert len(one) == 3 and one[2] == 176.49
    # S3: each piece's ring held at its own level
    core_ref, bank_ref, wing_ref = skirt_refs("tunnel:t@0")
    tn = types.SimpleNamespace(entrance_skirt=(176.49, core_ref, bank_ref),
                               entrance_wing=(177.88, wing_ref))
    F = types.SimpleNamespace
    pm = types.SimpleNamespace(ring_vertices=lambda ring: list(ring),
                               vertices={k: F(xy=(float(k), 0.0)) for k in range(5)},
                               faces={0: F(role="object_pad"), 1: F(role="object_pad"),
                                      2: F(role="object_pad")})
    faces = {core_ref: [F(ring=(0, 1))], wing_ref: [F(ring=(2, 3))], bank_ref: [F(ring=(1, 4))]}
    vf = {0: [0], 1: [0, 2], 2: [1], 3: [1], 4: [2]}
    airport = types.SimpleNamespace(dem=types.SimpleNamespace(z=lambda x, y: 170.0))
    pins: dict = {}
    skirt_pins(pm, airport, LAW, tn, faces, vf, ("object_pad",), lambda v: False,
               lambda v, z, src, senior=False: pins.__setitem__(v, z), ())
    assert pins == {0: 176.49, 1: 176.49, 2: 177.88, 3: 177.88, 4: 170.0}


def test_r5_t7_a_pin_with_no_cover_reads_as_r4(monkeypatch):
    """T7: the new statements are reached only through a pin with a cover:
    with ``_frame`` patched to raise, an entrance face's skirt, a pin with
    no cover and the mouth rules without ``set_back`` read as before."""
    from auto_patch_v2.planar.entrance_skirt import entrance_skirt
    from auto_patch_v2.planar.structure_mouth import roof_back_mouth
    from shapely.geometry import LineString

    def boom(*_a, **_k):
        raise AssertionError("_frame read for a pin with no cover")
    monkeypatch.setattr(P, "_frame", boom)
    ramp = box(-10.0, -5.0, 10.0, 0.0)
    for pin in (_pin(True), _pin(False)):
        r4 = entrance_skirt(pin, ramp, [], [], LAW, lambda x, y: 176.0, 1.0, outward=(0.0, -1.0))
        pin.cover_plan, pin.cover_top_z, pin.parapet_plan = None, None, None
        again = entrance_skirt(pin, ramp, [], [], LAW, lambda x, y: 176.0, 1.0,
                               outward=(0.0, -1.0))
        assert len(again) == 3 and again[2] == r4[2] == 177.88
        assert all(a.wkb == b.wkb for a, b in zip(r4[:2], again[:2], strict=True))
    axis = LineString([(0.0, 0.0), (0.0, -100.0)])
    assert roof_back_mouth(axis, (0.0, 1.0), box(-5.0, -3.0, 5.0, 4.0))[1] == 4.0
