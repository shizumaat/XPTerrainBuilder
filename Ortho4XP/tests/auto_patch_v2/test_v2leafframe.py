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
