"""§16g (10) (4) / §16g (5) as amended by owner RULINGS 2026-09-14bo.

(1) ``Part.height_m`` IS THE AUTHORED EXTENT, IN ONE FRAME.  It was
``box_max[y] - base_y`` — a PLACED maximum (``contact._place`` adds
``anchor_z + agl_m``) minus the AUTHORED minimum (``Component.min_y``),
i.e. an MSL number.  At LEMD it read 580–646 m over all 29,684 parts, so
``chain_min_height_m`` 2.5 passed every body as walled and the leaf rule
removed nothing.

(2) A PER-PLACEMENT ``OBJECT_MSL`` ROW IS SEATED AT ITS OWN FEET unless
its footprint stands on the unit's pad.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.airport import contact as _contact
from auto_patch_v2.airport import obj8 as _obj8
from auto_patch_v2.airport import pack_partition as _pp


def _box_geom(h: float) -> _obj8.ObjGeometry:
    """A 10 x 10 box ``h`` metres tall, authored with its base at y=0."""
    v = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 0.0, 10.0],
                  [0.0, 0.0, 10.0], [0.0, h, 0.0], [10.0, h, 0.0],
                  [10.0, h, 10.0], [0.0, h, 10.0]], dtype=float)
    tris = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],
                     [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
                     [1, 2, 6], [1, 6, 5], [3, 0, 4], [3, 4, 7]], dtype=int)
    return _obj8.ObjGeometry("box.obj", v, tris,
                             np.ones(len(tris), dtype=int),
                             np.zeros((0, 3), dtype=int))


def _placed(anchor_z: float, agl_m: float = 0.0) -> _obj8.PlacedObject:
    return _obj8.PlacedObject("dsf:obj0", "box.obj", "box.obj", (0.0, 0.0),
                              0.0, agl_m, "OBJECT", anchor_z,
                              None, None, None, None, None, None)


def _parts(anchor_z: float, h: float, agl_m: float = 0.0):
    geom = _box_geom(h)
    comps = list(enumerate(_obj8.solid_components(geom)))
    return _contact.placed_parts([(_placed(anchor_z, agl_m), geom, comps)])


def _rows(parts):
    """``_parts_by_member`` with an identity lat/lon transform."""
    part = type("P", (), {"parts": parts})()
    return _pp._parts_by_member(part, lambda xs, ys: (np.asarray(ys, dtype=float),
                                                      np.asarray(xs, dtype=float)))


@pytest.mark.parametrize("anchor_z", [0.0, 12.5, 602.42, -3.0])
def test_height_m_is_the_authored_extent_whatever_the_anchor(anchor_z):
    """THE FRAME BUG (RULINGS 2026-09-14bo): a placed part's ``height_m``
    is its AUTHORED y extent — 7.25 m for a 7.25 m box — no matter what
    elevation the pack seats it at.  With ``base_y`` (authored) subtracted
    from ``box_max[1]`` (placed) this read ``anchor_z + 7.25``."""
    rows = _rows(_parts(anchor_z, 7.25))
    got = [p.height_m for ps in rows.values() for p in ps]
    assert got, "the fixture must produce at least one part"
    assert all(g == pytest.approx(7.25, abs=1e-3) for g in got), got


def test_a_zero_height_quad_reads_zero_at_any_elevation():
    """The LEMD carriers: AESlite VOR quads authored at extent 0.000 m,
    placed 600 m up, carried 3,300 cluster edges each because their
    ``height_m`` read 600.  A leaf must read 0 wherever it is placed."""
    v = np.array([[0.0, 0.0, 0.0], [40.0, 0.0, 0.0], [40.0, 0.0, 40.0],
                  [0.0, 0.0, 40.0]], dtype=float)
    tris = np.array([[0, 1, 2], [0, 2, 3]], dtype=int)
    geom = _obj8.ObjGeometry("quad.obj", v, tris, np.ones(2, dtype=int),
                             np.zeros((0, 3), dtype=int))
    comps = list(enumerate(_obj8.solid_components(geom)))
    parts = _contact.placed_parts([(_placed(602.42), geom, comps)])
    got = [p.height_m for ps in _rows(parts).values() for p in ps]
    assert got == [0.0], got


def test_the_agl_offset_is_not_height_either():
    """An ``OBJECT_AGL`` row lifts the whole body; its solid height is
    unchanged."""
    ground = [p.height_m for ps in _rows(_parts(0.0, 3.5)).values() for p in ps]
    lifted = [p.height_m for ps in _rows(_parts(0.0, 3.5, agl_m=9.0)).values()
              for p in ps]
    assert ground == lifted == [pytest.approx(3.5, abs=1e-3)]


def test_base_y_stays_the_authored_minimum():
    """Only ``height_m`` changes frame: ``base_y`` is still the AUTHORED
    minimum (the seat reads ``mesh(foot) - base_y``), so a box authored
    1 m below its origin keeps ``base_y`` -1 whatever the anchor."""
    geom = _box_geom(4.0)
    geom.vertices[:, 1] -= 1.0
    comps = list(enumerate(_obj8.solid_components(geom)))
    parts = _contact.placed_parts([(_placed(500.0), geom, comps)])
    rows = _rows(parts)
    got = [(p.base_y, p.height_m) for ps in rows.values() for p in ps]
    assert got == [(pytest.approx(-1.0, abs=1e-3),
                    pytest.approx(4.0, abs=1e-3))], got


# ── §16g (5) AMENDED: A ROW IS SEATED AT ITS OWN FEET (RULINGS 14bo) ────

class _PPart:
    def __init__(self, pid, box):
        self.pid, self.box, self.line = pid, box, False
        self.lat, self.lon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
        self.base_y, self.feet, self.comp, self.area_m2 = 0.0, (), 0, 1.0


class _PMember:
    def __init__(self, resource, parts):
        self.id = self.resource = resource
        self.parts = tuple(parts)
        self.deck_datum_z = self.deck_ring = None
        self.deck_kind = ""


class _PUnit:
    def __init__(self, uid, members):
        self.id, self.members = uid, tuple(members)


class _PPlan:
    def __init__(self, units):
        self.units, self.contacts = tuple(units), ()


def _dump_and_plan():
    """One multi-anchor resource the plan does NOT hold, at two rows
    inside a unit's box, and the walled member the plan does hold."""
    import types

    def P(path, lat, lon, kind="OBJECT", elevation=None):
        return types.SimpleNamespace(def_path=path, lat=lat, lon=lon,
                                     heading_deg=90.0, kind=kind,
                                     elevation=elevation)
    rows = [P("objects/loader.obj", 40.0005, -2.9995),
            P("objects/loader.obj", 40.0008, -2.9992)]
    dump = types.SimpleNamespace(placements=rows)
    wall = _PMember("objects/wall.obj",
                    [_PPart(1, (40.0000, -3.0000, 40.0010, -2.9990))])
    return rows, dump, _PPlan([_PUnit("unit:0", [wall])])


UNIT = [(40.0000, -3.0000, 40.0010, -2.9990, 602.42, "cluster_pad")]


def _seats(dump, plan, surface, **kw):
    from auto_patch_v2.airport import footprint_unit as FU
    return FU.msl_seats_for_dump(dump, plan, UNIT, surface, "", frozenset(),
                                 **kw)


def test_a_vehicle_off_the_pad_on_higher_apron_seats_at_the_apron():
    """THE LEMD ITEM 3 CASE (owner 14bl item 3, RULINGS 2026-09-14bo): the
    unit's pad plane is 602.42 and the apron the vehicle actually stands
    on is 1 m above it.  13cb wrote the row at 602.42 and sank the vehicle
    1 m into the apron; the row now takes the surface at its OWN FEET.
    With an authored offset it is written there; with none the drape
    already does it and the row is left alone."""
    rows, dump, plan = _dump_and_plan()
    counts: dict = {}
    assert _seats(dump, plan, lambda la, lo: 603.42, counts=counts) == ()
    assert counts["msl_left_to_the_drape"] == 2
    assert counts.get("msl_base_own_feet", 0) == 0
    # the same vehicle authored 0.35 m up on its own trailer: written at
    # the APRON + 0.35, never at the pad plane
    for r in rows:
        r.kind, r.elevation = "OBJECT_AGL", 0.35
    counts = {}
    got = _seats(dump, plan, lambda la, lo: 603.42, counts=counts)
    assert [(round(m.elevation, 2), m.why) for m in got] \
        == [(603.77, "own_feet"), (603.77, "own_feet")]
    assert counts["msl_base_own_feet"] == 2


def test_a_placement_standing_on_the_units_pad_keeps_the_family_plane():
    """The other half of 14bo, and 13cb's own case: where the design
    surface at the placement's feet IS the unit's datum, the family
    relation holds and the authored offset rides the pad plane — the
    second-floor passenger stays on the floor the author put them on."""
    rows, dump, plan = _dump_and_plan()
    for r in rows:
        r.kind, r.elevation = "OBJECT_AGL", 4.20
    counts: dict = {}
    got = _seats(dump, plan, lambda la, lo: 602.42, counts=counts)
    assert [(round(m.elevation, 2), m.why) for m in got] \
        == [(606.62, "cluster_pad"), (606.62, "cluster_pad")]
    assert counts["msl_base_unit_pad"] == 2


def test_no_graded_face_at_its_feet_leaves_the_row_draped():
    """Where nothing was emitted under the placement the DEM governs and
    the row stays plain ``OBJECT`` — an elevation read off a surface
    nobody emitted would be a guess (14bo)."""
    rows, dump, plan = _dump_and_plan()
    for r in rows:
        r.kind, r.elevation = "OBJECT_AGL", 4.20
    counts: dict = {}
    assert _seats(dump, plan, lambda la, lo: None, counts=counts) == ()
    assert counts["msl_off_sheet_left_draped"] == 2


def test_a_deck_datum_is_not_on_the_graded_sheet_and_still_carries():
    """13cb's road-under-the-deck case: a unit whose datum is a DECK is
    not drawn on the graded surface at all — the sheet there is the road
    beneath — so the placement keeps the deck's plane."""
    rows, dump, plan = _dump_and_plan()
    from auto_patch_v2.airport import footprint_unit as FU
    deck = [(40.0000, -3.0000, 40.0010, -2.9990, 610.00, "deck")]
    counts: dict = {}
    got = FU.msl_seats_for_dump(dump, plan, deck, lambda la, lo: 598.0, "",
                                frozenset(), counts=counts)
    assert [(round(m.elevation, 2), m.why) for m in got] \
        == [(610.0, "deck"), (610.0, "deck")]
    assert counts["msl_base_deck"] == 2


def test_the_tools_dry_msl_census_IS_the_writers_own_call():
    """``obj8_split_report --dsf-dump`` reads §16g (5) DRY from the SAME
    ``msl_seats_for_dump`` the writer calls, and prices each row against
    the design surface AT ITS OWN FEET — the number 14bo's bar is stated
    in.  A row on the unit's pad is lawfully off its own feet by exactly
    its authored offset; the instrument must report that, not hide it."""
    import os
    import sys
    import types
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as RPT

    rows, dump, plan = _dump_and_plan()
    for r in rows:
        r.kind, r.elevation = "OBJECT_AGL", 4.20
    ss = types.SimpleNamespace(unit_seats=UNIT)
    plan.flat = None

    def surface(la, lo):
        return 602.42
    seats, counts, offs = RPT.msl_census_rows(dump, plan, ss, surface, 0.02)
    assert [round(m.elevation, 2) for m in seats] == [606.62, 606.62]
    assert counts["msl_base_unit_pad"] == 2
    assert counts["multi_anchor_object_msl"] == 2
    # the row stands 4.20 m over the surface at its feet BY LAW
    assert [round(o, 2) for o in offs] == [4.20, 4.20]
    # off the pad with no authored offset there is nothing to write
    for r in rows:
        r.kind, r.elevation = "OBJECT", None
    seats, counts, offs = RPT.msl_census_rows(
        dump, plan, ss, lambda la, lo: 603.42, 0.02)
    assert seats == () and offs == []
    assert counts["msl_left_to_the_drape"] == 2


# ── tools/site_read.py — the promoted coordinate reader (7e90032) ───────

def _site_read():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import site_read
    return site_read


def test_site_read_faces_rows_and_bodies_at_one_coordinate(tmp_path):
    """The promoted reader answers ONE question of THREE products and
    derives nothing: a containing face reads distance 0 and a face only
    near reads its own distance; a DSF row keeps its written elevation
    verbatim (``None`` for a plain ``OBJECT``, never 0.0); and a plan body
    is found by its PLAN BOX, so a point inside a large body is 0.0 m
    away and not tens of metres to its nearest vertex."""
    import json
    SR = _site_read()
    graded = {"vertices": [[0, 40.0000, -3.0000, 602.40],
                           [1, 40.0010, -3.0000, 602.44],
                           [2, 40.0010, -2.9990, 602.42],
                           [3, 40.0000, -2.9990, 602.42],
                           [4, 40.0100, -3.0000, 588.00],
                           [5, 40.0110, -3.0000, 588.00],
                           [6, 40.0110, -2.9990, 588.00]],
               "faces": [{"id": 4, "role": "building", "ref": "building4",
                          "side": None, "ring": [0, 1, 2, 3]},
                         {"id": 9, "role": "apron", "ref": "pav1",
                          "side": "left", "ring": [4, 5, 6]}]}
    got = SR.graded_faces_near(graded, 40.0005, -2.9995, 40.0)
    assert [(r["id"], r["inside"], round(r["distance_m"], 1)) for r in got] \
        == [(4, True, 0.0)]
    assert got[0]["z_med"] == 602.42 and got[0]["z_min"] == 602.40
    # widen past the apron 105 m north and it appears, at its distance
    wide = SR.graded_faces_near(graded, 40.0005, -2.9995, 2000.0)
    assert [r["id"] for r in wide] == [4, 9]
    assert 1000.0 < wide[1]["distance_m"] < 1200.0

    dump = tmp_path / "x.dsf.text"
    dump.write_text("OBJECT_DEF objects/loader.obj\n"
                    "OBJECT_DEF objects/mast.obj\n"
                    "OBJECT 0 -2.9995 40.0005 90.000\n"
                    "OBJECT_MSL 1 -2.9994 40.0006 603.770 12.0\n"
                    "OBJECT 0 -2.8000 40.0005 0.000\n")
    rows = SR.dsf_rows_near(str(dump), 40.0005, -2.9995, 60.0)
    assert [(r["kind"], r["resource"], r["elevation"]) for r in rows] \
        == [("OBJECT", "objects/loader.obj", None),
            ("OBJECT_MSL", "objects/mast.obj", 603.77)]

    plan = tmp_path / "o4_v2_placement_TEST.json"
    plan.write_text(json.dumps({"splits": [{
        "placement": {"resource": "objects/wall.obj"},
        "bodies": [{"body_id": "b0", "class": "building",
                    "plan_box": [40.0000, -3.0000, 40.0010, -2.9990],
                    "unit_of": "fu:0:0@cluster_pad", "surface_z": 602.42,
                    "y_zero": 0.0, "anchor_reason": "on pad building4"},
                   {"body_id": "b1", "class": "other",
                    "plan_box": [40.0500, -3.0000, 40.0501, -2.9999],
                    "unit_of": None, "surface_z": 588.0, "y_zero": 0.0,
                    "anchor_reason": "surface at the body's zero"}]}]}))
    b = SR.plan_bodies_near(json.load(open(plan)), 40.0005, -2.9995, 60.0)
    assert [(r["body_id"], round(r["distance_m"], 2)) for r in b] \
        == [("b0", 0.0)]
    assert b[0]["unit_of"] == "fu:0:0@cluster_pad"
    # --patch-dir resolves both products by glob and the CLI writes what
    # it printed
    (tmp_path / "TEST.graded.json").write_text(json.dumps(graded))
    out = tmp_path / "site.json"
    assert SR.main(["40.0005", "-2.9995", "60", "--patch-dir", str(tmp_path),
                    "--dsf-dump", str(dump), "--json", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert [f["id"] for f in doc["faces"]] == [4]
    assert len(doc["dsf_rows"]) == 2 and [r["body_id"] for r in doc["bodies"]] \
        == ["b0"]


def test_site_read_is_in_the_tool_index():
    """Every promotion lands WITH its index row, in the same commit
    (RULINGS `7e90032`)."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    text = open(os.path.join(root, "tools", "INDEX.md"), encoding="utf-8").read()
    assert "tools/site_read.py" in text
    assert "--dsf-dump" in text


# ── §16g (10) (4) AMENDED + (10) (9) ONE PAD DATUM (owner RULINGS
#    2026-09-17t, on the scout attributions 17s / 17u) — lane v2leafseat ──
#
# 17s: HECA's ``Airport/T23/T3_brick_clean.obj`` is ONE shared-datum
# placement whose 138 parts are elevated façade panels with NO feet plus
# 0.49 m ground plinths.  Every plinth is a LEAF (under
# ``chain_min_height_m``), the walls are ELEVATED and never candidates, so
# the plinth's OWN pids named no unit and it fell to its own apron — the
# shell written in pieces up to 2.34 m apart.  A LEAF IS STILL NEVER A
# LINK; a leaf whose own elevated members belong to a unit now SEATS in
# that unit.
#
# 17u: the pad datum was ``min(p.z)`` over the WHOLE ring of ONE FACE of a
# multi-face ref — LEMD's ``building45`` is five faces and the T4 unit's
# 64 bodies took a vertex 590 m away.  ONE rule for both seats: the
# MEDIAN, over EVERY FACE of the ref.

class _LPart:
    """A plan part, with the fields §16g (10) (4) reads (``height_m``,
    ``rings``) that ``_PPart`` above predates."""

    def __init__(self, pid, box, height_m, feet=()):
        self.pid, self.box, self.line = pid, box, False
        self.lat = 0.5 * (box[0] + box[2])
        self.lon = 0.5 * (box[1] + box[3])
        self.base_y, self.comp, self.area_m2 = 0.0, 0, 1.0
        self.height_m = float(height_m)
        self.feet = tuple(feet)
        self.rings = ((box[0], box[1]), (box[0], box[3]),
                      (box[2], box[3]), (box[2], box[1])),


class _LMember:
    def __init__(self, resource, parts):
        self.id = self.resource = resource
        self.parts = tuple(parts)
        self.deck_datum_z = self.deck_ring = None
        self.deck_kind = ""
        self.heading_deg = 0.0


class _LUnit:
    def __init__(self, uid, members, anchor=(41.0, -3.0)):
        self.id, self.members, self.anchor = uid, tuple(members), anchor


class _LPlan:
    def __init__(self, units, contacts=()):
        self.units, self.contacts = tuple(units), tuple(contacts)


def _lat_m(m: float) -> float:
    return 41.0 + m / 111_132.0


def _lbox(m0, m1, lo0=-3.0000, lo1=-2.9990):
    return (_lat_m(m0), lo0, _lat_m(m1), lo1)


def _lcand(member, boxes, z, pids, group=0):
    import auto_patch_v2.airport.anchor_rule as AR
    import auto_patch_v2.airport.placement_boxes as _PB
    import auto_patch_v2.airport.placement_carrier as _PC
    hull = _PB.hull_of(list(boxes))
    return _PC.Candidate(member, f"objects/m{member}.obj",
                         AR.Anchor(AR.BUILDING, 0.5 * (hull[0] + hull[2]),
                                   0.5 * (hull[1] + hull[3]), 0.0,
                                   "surface at the body's zero", z),
                         frozenset(pids), 4, hull, part_boxes=list(boxes),
                         group=group, body_class=AR.BUILDING, fill=1.0,
                         ground_off=0.0)


class _LStaged:
    """The staged member ``_bind_plan_wide`` reads: one FOOTED group (the
    plinth) plus the member's own ELEVATED parts, which is the shape a
    material-sliced pack has."""

    def __init__(self, mi, resource, raw, elevated=frozenset()):
        import types
        import auto_patch_v2.airport.anchor_rule as AR
        self.mi = mi
        self.m = types.SimpleNamespace(resource=resource, deck_kind="",
                                       deck_ring=None)
        self.raw, self.part_boxes = [], []
        for parts, box, feet in raw:
            self.raw.append((list(parts), AR.BUILDING,
                             AR.Anchor(AR.BUILDING, box[0], box[1], 0.0,
                                       "r", 0.0), tuple(feet), False, (),
                             (), None))
            self.part_boxes.append([box])
        self.elevated = frozenset(elevated)
        self.groups = [[0]]
        self.ground_off = [0.0]


def _t3_plan():
    """A WALLED block (a 12 m wall, footed) beside a MATERIAL-SLICED
    placement: a 0.49 m plinth with feet (a LEAF) whose own ELEVATED
    façade panel (18 m up, no feet) stands over it and touches the wall.
    The panel is in the wall's unit; the plinth's own pids are not."""
    wall = _LMember("objects/wall.obj",
                    [_LPart(1, _lbox(0, 40), 12.0,
                            feet=((_lat_m(5), -2.9995, 0.0),))])
    # the façade panel overlaps the wall in plan (so they chain) AND
    # stands over the plinth
    panel = _LPart(10, _lbox(30, 70), 6.0)
    plinth = _LPart(11, _lbox(45, 70), 0.49,
                    feet=((_lat_m(50), -2.9995, 0.0),))
    shell = _LMember("objects/shell.obj", [panel, plinth])
    return wall, panel, plinth, _LPlan([_LUnit("unit:0", [wall, shell])])


def _t3_arms(surface):
    """``(counts, the plinth candidate after the bind)`` — the whole
    §16g pipeline the shipped ``build_splits`` runs, on the fixture."""
    from auto_patch_v2.airport import footprint_unit as FU
    _wall, panel, plinth, plan = _t3_plan()
    counts: dict = {}
    pw, _s = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, counts,
                                0.0, 2.5)
    cands = [_lcand(0, [_lbox(0, 40)], surface(_lat_m(20), -2.9995), {1}),
             _lcand(1, [plinth.box], surface(_lat_m(57), -2.9995), {11})]
    st = [_LStaged(0, "objects/wall.obj",
                   [([_LPart(1, _lbox(0, 40), 12.0)], _lbox(0, 40),
                     ((_lat_m(5), -2.9995, 0.0),))]),
          _LStaged(1, "objects/shell.obj",
                   [([plinth], plinth.box, ((_lat_m(50), -2.9995, 0.0),)),
                    ([panel], panel.box, ())],
                   elevated={1})]
    FU.bind_footprint_units(cands, st, surface, (), counts, unit_id="unit:0",
                            touch_m=0.5, visual_m=0.5, connector_span_m=0.0,
                            plan_wide=pw)
    return counts, cands[1]


def test_a_leaf_seats_in_the_unit_its_own_elevated_members_belong_to():
    """§16g (10) (4) AMENDED (17t, fix A): the 0.49 m plinth is a LEAF and
    its own pids name no unit — but the façade panel §15 merges into its
    file is a member of the wall's unit, so the plinth takes the UNIT's
    zero instead of the sloping ground under itself."""
    from auto_patch_v2.airport import footprint_unit as FU

    def surface(la, lo):          # the ground climbs 3 m over the site
        return 10.0 + 3.0 * (la - 41.0) / (_lat_m(70) - 41.0)

    counts, plinth = _t3_arms(surface)
    assert counts["unit_leaf_seated_by_elevated"] == 1
    assert plinth.anchor.reason.startswith(FU.UNIT_REASON)
    assert plinth.anchor.unit_seat is True
    # and it is on the UNIT's zero — the median ground under the unit's
    # parts, 11.50 — not on the ground under its own plinth, which the
    # sloping site puts ~1 m higher.  That difference IS the 2.34 m the
    # shell's pieces were written apart at HECA.
    zero = plinth.anchor.surface_z - plinth.anchor.y_zero
    own = surface(_lat_m(57), -2.9995)
    assert zero == pytest.approx(11.50, abs=0.05), zero
    assert own - zero > 0.8, (own, zero)


def test_the_chain_is_untouched_a_leaf_is_still_never_a_link():
    """The other half of the amendment, and the bar 17s set: the leaf
    count and the chain are read BEFORE the seat and cannot move.
    Disarming ``chain_min_height_m`` was REFUTED by replay (HECA units
    180 -> 323, chain bodies 7,264 -> 24,165) and this twin is what keeps
    fix A from becoming that."""
    from auto_patch_v2.airport import footprint_unit as FU
    _w, _p, _pl, plan = _t3_plan()
    counts: dict = {}
    FU.plan_wide_seats(plan, lambda la, lo: 10.0, (), 0.5, 0.0, counts,
                       0.0, 2.5)
    # the plinth (0.49 m) is a LEAF and never links; only the wall and the
    # panel chain, so the plan-wide partition is the pre-17t one
    assert counts["unit_leaf_bodies"] == 1
    assert counts["plan_wide_units"] == 1


def test_a_leaf_with_no_elevated_member_in_any_unit_is_unchanged():
    """The negative: a leaf standing alone keeps §16c's own anchor — fix
    A reads the elevated members ONLY where the body's own pids name no
    unit, and adds nothing when they name none either."""
    from auto_patch_v2.airport import footprint_unit as FU
    lone = _LMember("objects/slab.obj",
                    [_LPart(1, _lbox(0, 30), 0.30,
                            feet=((_lat_m(10), -2.9995, 0.0),))])
    far = _LMember("objects/other.obj",
                   [_LPart(2, _lbox(900, 940), 12.0,
                           feet=((_lat_m(910), -2.9995, 0.0),))])
    plan = _LPlan([_LUnit("unit:0", [lone, far])])
    counts: dict = {}
    pw, _s = FU.plan_wide_seats(plan, lambda la, lo: 10.0, (), 0.5, 0.0,
                                counts, 0.0, 2.5)
    cands = [_lcand(0, [_lbox(0, 30)], 10.0, {1})]
    st = [_LStaged(0, "objects/slab.obj",
                   [([_LPart(1, _lbox(0, 30), 0.30)], _lbox(0, 30),
                     ((_lat_m(10), -2.9995, 0.0),))])]
    FU.bind_footprint_units(cands, st, lambda la, lo: 10.0, (), counts,
                            unit_id="unit:0", touch_m=0.5, visual_m=0.5,
                            connector_span_m=0.0, plan_wide=pw)
    assert counts.get("unit_leaf_seated_by_elevated", 0) == 0
    assert cands[0].anchor.reason == "surface at the body's zero"
    assert cands[0].anchor.unit_seat is False


@pytest.mark.xfail(strict=True, reason="§16g (2) fix B is GATED OFF (RULINGS 2026-09-17z): a unit-seated body's ground_off still refuses it as a carrier (zero_off_ground); the twin stands for the ungated law")
def test_a_unit_seated_body_is_not_refused_as_a_carrier():
    """§16g (2): "no per-member cut, no carrier search, NO GROUND TEST
    BETWEEN MEMBERS".  §16a (2) refuses a carrier whose zero stands off
    the ground under its own feet because it would carry its own error —
    a UNIT SEAT is not that error, it is the law working.

    MEASURED (lane v2leafseat, HECA dry replay): without this, fix A's 24
    re-seated bodies — the T3 district's principal carriers — cost 2,398
    riders every carrier, files 3,743 -> 6,165 and §15 footed float
    608 -> 3,176.  With it, files 3,423."""
    import auto_patch_v2.airport.anchor_rule as AR
    import auto_patch_v2.airport.placement_carrier as PC
    seated = _lcand(0, [_lbox(0, 40)], 10.0, {1})
    seated = type(seated)(**{**seated.__dict__,
                             "anchor": AR.Anchor(AR.BUILDING, _lat_m(20),
                                                 -2.9995, 0.0, "r", 10.0,
                                                 unit_seat=True),
                             "ground_off": 2.08})
    plain = type(seated)(**{**seated.__dict__,
                            "anchor": AR.Anchor(AR.BUILDING, _lat_m(20),
                                                -2.9995, 0.0, "r", 10.0),
                            "ground_off": 2.08})
    body = (_lat_m(10), -3.0000, _lat_m(30), -2.9990)
    ref: dict = {}
    assert PC.carriers_for(frozenset({9}), body, [seated], {}, (),
                           tol_m=0.3, refusals=ref, solid_cands=[seated],
                           reach_m=100.0)
    ref = {}
    assert not PC.carriers_for(frozenset({9}), body, [plain], {}, (),
                               tol_m=0.3, refusals=ref, solid_cands=[plain],
                               reach_m=100.0)
    assert ref.get("zero_off_ground", 0) >= 1


# ── §16g (10) (9) ONE PAD DATUM, THE MEDIAN, OVER EVERY FACE ────────────

def _five_face_pad():
    """LEMD's ``building45``: ONE ref, FIVE faces, whose minima differ.
    The face the scan happens to touch LAST decided the datum (17u)."""
    import auto_patch_v2.airport.anchor_rule as AR
    faces = []
    for k, z in enumerate((614.77, 615.18, 615.40, 615.60, 616.00)):
        la0 = _lat_m(100 * k)
        la1 = _lat_m(100 * k + 90)
        ring = ((la0, -3.0000), (la0, -2.9990), (la1, -2.9990), (la1, -3.0000))
        faces.append(AR.PadRing("building45", ring, (z, z + 0.2, z + 0.4,
                                                     z + 0.6)))
    return tuple(faces)


def test_pad_plurality_and_pad_majority_fold_every_face_of_a_ref():
    """fix C, a pure defect: a `building` REF may be emitted as several
    FACES, and both readers COUNTED per ref while KEEPING the last face
    they matched — an iteration-order datum (LEMD 0.41 m).  The fold is
    order-free and its plane is the ref's."""
    import auto_patch_v2.airport.anchor_rule as AR
    from auto_patch_v2.airport import placement_family as PF
    pads = _five_face_pad()
    # one contact on face 0 and one on face 3: whatever the order, the
    # pad handed back carries EVERY face's heights and every face's ring
    cands = [(_lat_m(45), -2.9995, 0.0, 0.0), (_lat_m(345), -2.9995, 0.0, 0.0)]
    for order in (pads, tuple(reversed(pads))):
        p = PF.pad_plurality(cands, order)
        assert p is not None and p.ref == "building45"
        assert len(p.z) == 20 and len(p.rings) == 5
        assert min(p.z) == 614.77 and max(p.z) == 616.60
        q = AR.pad_majority(cands, order)
        assert q is not None and tuple(sorted(q.z)) == tuple(sorted(p.z))
    # the containment test is the REF's, not the largest face's
    p = PF.pad_plurality(cands, pads)
    assert AR.pad_contains(p, _lat_m(45), -2.9995)
    assert AR.pad_contains(p, _lat_m(345), -2.9995)
    assert not AR.pad_contains(p, _lat_m(95), -2.9995)   # the gap between


def test_the_cluster_seat_and_the_connector_datum_take_ONE_rule():
    """§16g (10) (9) AMENDED (17t, verbatim: "Pad datum: median, one rule
    for both seats").  14az's low side read ``min(p.z)`` and 17s measured
    the two seats 0.95 m apart on HECA's ``building9``; ``low_side`` is
    gone from the signature, so ``plan_unit_datums`` cannot answer the two
    callers differently."""
    import inspect
    from auto_patch_v2.airport import footprint_unit as FU
    assert "low_side" not in inspect.signature(FU.plan_unit_datums).parameters
    assert "low_side" not in inspect.signature(FU.plan_wide_seats).parameters
    pads = _five_face_pad()
    un = FU.PlanUnit(id="unit:0", bodies=(), pids=frozenset(), members=(),
                     boxes=(_lbox(0, 90), _lbox(300, 390)), area_m2=10.0)
    plan = _LPlan([_LUnit("unit:0", [])])
    dat = FU.plan_unit_datums([un], plan, lambda la, lo: 600.0, pads, 0.0)
    z, where, src = dat["unit:0"]
    assert where == "building45" and src == "pad"
    # the MEDIAN of the folded ref (20 vertices, 614.77 … 616.60), never
    # the global minimum 614.77 the low side took
    allz = sorted(v for f in pads for v in f.z)
    want = 0.5 * (allz[9] + allz[10])
    assert z == pytest.approx(want, abs=1e-6), (z, want)
    assert z > min(allz) + 0.5


# ── §16g (2) AMENDED — THE GRADED AIRSIDE SURFACE IS A FLOOR UNDER EVERY
#    MEMBER (owner RULINGS 2026-09-17x (1), fix B) — lane v2leafseat ─────

class _Roles:
    """The sampler's §17 role channel: ``apron`` everywhere except the
    named boxes (``ground``), so a foot can be ON or OFF the airside."""

    def __init__(self, off=()):
        self.off = tuple(off)

    def roles_many(self, lats, lons):
        out = []
        for la, lo in zip(lats, lons):
            r = "apron"
            for b in self.off:
                if b[0] <= la <= b[2] and b[1] <= lo <= b[3]:
                    r = "ground"
            out.append(r)
        return out


class _Surface:
    """A callable design surface carrying §17's two channels."""

    def __init__(self, fn, roles=None, rolled_on=("apron",)):
        self._fn, self.roles, self.rolled_on = fn, roles, rolled_on

    def __call__(self, la, lo):
        return self._fn(la, lo)


def _floor_fixture(cluster_of, armed=True):
    """A four-member unit on a pad at 600.00 with the apron stepping up
    2.00 m under the last two members — LEMD T4 in miniature (17u: one
    rigid plane carried 600 m to an apron 1–1.9 m higher)."""
    from auto_patch_v2.airport import footprint_unit as FU
    import auto_patch_v2.airport.anchor_rule as AR
    mem, cands, st = [], [], []
    for i, (m0, m1, g) in enumerate([(0, 40, 600.0), (38, 78, 600.0),
                                     (76, 116, 602.0), (114, 154, 602.0)]):
        box = _lbox(m0, m1)
        mem.append(_LMember(f"objects/m{i}.obj",
                            [_LPart(1 + i, box, 12.0,
                                    feet=((_lat_m(m0 + 20), -2.9995, 0.0),))]))
        cands.append(_lcand(i, [box], g, {1 + i}))
        st.append(_LStaged(i, f"objects/m{i}.obj",
                           [([_LPart(1 + i, box, 12.0)], box,
                             ((_lat_m(m0 + 20), -2.9995, 0.0),))]))
    plan = _LPlan([_LUnit("unit:0", mem)])
    # one pad over the whole unit, its plane 600.00
    ring = ((_lat_m(-5), -3.0001), (_lat_m(-5), -2.9989),
            (_lat_m(160), -2.9989), (_lat_m(160), -3.0001))
    pads = (AR.PadRing("building1", ring, (600.0, 600.0, 600.0, 600.0)),)
    # member 0's foot stands on GROUND, not apron: §16g (2)'s "pavement is
    # king" stands down for a unit only PART of which is on pavement,
    # which is the mixed case the datum rule is written for
    surf = _Surface(lambda la, lo: 600.0 if la < _lat_m(76) else 602.0,
                    roles=_Roles(((_lat_m(-5), -3.0001,
                                   _lat_m(30), -2.9989),)))
    counts: dict = {}
    pw, _s = FU.plan_wide_seats(plan, surf, pads, 0.5, 0.0, counts, 0.0, 2.5)
    FU.bind_footprint_units(cands, st, surf, pads, counts, unit_id="unit:0",
                            touch_m=0.5, visual_m=0.5, connector_span_m=0.0,
                            plan_wide=pw, cluster_of=cluster_of,
                            airside_floor=armed)
    return counts, [round(c.anchor.surface_z - c.anchor.y_zero, 2)
                    for c in cands]


def test_a_member_on_a_higher_apron_floors_at_its_own_feet():
    """17x (1): the unit's pad plane is 600.00 and members 2 and 3 stand
    on apron 2.00 m above it.  Rigidity yields to the apron — those two
    seat at 602.00, the two over the pad stay at 600.00.  Before this
    every member took 600.00 and the last two were buried 2 m."""
    counts, zeros = _floor_fixture({})
    assert zeros == [600.0, 600.0, 602.0, 602.0], zeros
    assert counts["unit_members_floored"] == 2   # members 2 and 3
    assert counts["unit_floor_worst_lift_m"] == pytest.approx(2.0, abs=1e-3)


def test_a_rigid_cluster_rises_together_so_a_weld_is_never_a_step():
    """The session's refinement, and the reason the cross-body contact
    census is 17x's bar: member 1 is welded to member 2 (§16c (7)'s rigid
    cluster, published by ``placement_atom.bind_unit``).  The cluster
    takes the HIGHEST floor among its members, so the two are written at
    ONE zero and the 2 mm pack contact between them is not a step."""
    counts, zeros = _floor_fixture({1: 1, 2: 1})
    assert zeros == [600.0, 602.0, 602.0, 602.0], zeros
    assert counts["unit_members_floored"] == 3


def test_no_airside_foot_and_no_roles_both_read_NO_FLOOR():
    """Two negatives, and both are "no reading is no evidence": a member
    whose every foot stands on `ground` has no airside floor, and a
    sampler carrying no roles at all gives none to anybody — the unit's
    own datum stands in both, exactly as before 17x."""
    from auto_patch_v2.airport import footprint_unit as FU
    cc = [(_lat_m(10), -2.9995, 0.0, 602.0)]
    assert FU._airside_floor(cc, _Surface(lambda la, lo: 602.0)) is None
    off = (( _lat_m(-5), -3.0001, _lat_m(160), -2.9989),)
    assert FU._airside_floor(
        cc, _Surface(lambda la, lo: 602.0, roles=_Roles(off))) is None
    assert FU._airside_floor(
        cc, _Surface(lambda la, lo: 602.0, roles=_Roles())) == 602.0


def test_the_floor_is_the_MEDIAN_foot_not_the_lowest_and_not_the_box():
    """§17 (2)'s reading, as the session refined it: one foot over lower
    ground must not float the body, and the whole plan box is not the
    member's ground.  Three feet at 601.0 / 602.0 / 602.2 floor at
    602.0."""
    from auto_patch_v2.airport import footprint_unit as FU
    cc = [(_lat_m(10), -2.9995, 0.0, 601.0),
          (_lat_m(20), -2.9995, 0.0, 602.0),
          (_lat_m(30), -2.9995, 0.0, 602.2)]
    got = FU._airside_floor(cc, _Surface(lambda la, lo: 0.0, roles=_Roles()))
    assert got == pytest.approx(602.0, abs=1e-6), got


def test_the_floor_ships_OFF_and_the_key_reproduces_both_arms():
    """`[placement] airside_floor` ships FALSE and the reason is measured,
    not doubted: the 17x bar (17s's cross-body contact census within 60 m
    of the owner's site) is MET at LEMD T4 (pairs > 0.5 m 99 -> 42, worst
    1.748 -> 0.807 m, worst buried foot 1.73 -> 0.43 m) and MISSED at
    HECA T3 (44 -> 245, the six `T3_brick_clean` shells back on SEVEN
    datums, site datums 5 -> 18) — HECA's shells stand on an apron that
    falls 5.4 m across the district and are not one rigid cluster, so
    each floors locally and fix A is undone at the owner's own site.  17x
    (1)'s reserve shape (partition the unit by reach) is the answer and
    is not this lane's to choose.  Disarmed, NOTHING moves."""
    counts, zeros = _floor_fixture({}, armed=False)
    assert zeros == [600.0, 600.0, 600.0, 600.0], zeros
    assert "unit_members_floored" not in counts
    armed, _z = _floor_fixture({}, armed=True)
    assert armed["unit_members_floored"] == 2


def test_the_shipped_law_value_is_false():
    """The key is the arm, and a lane that measured a bar MISSED does not
    flip it (build economy: a mechanism awaiting the owner's adjudication
    is the one thing a gate is for)."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    text = open(os.path.join(root, "src", "auto_patch_v2", "law",
                             "structures.toml"), encoding="utf-8").read()
    assert "airside_floor       = false" in text
