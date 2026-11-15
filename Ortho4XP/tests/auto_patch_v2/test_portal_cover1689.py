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
from shapely.geometry import box

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
