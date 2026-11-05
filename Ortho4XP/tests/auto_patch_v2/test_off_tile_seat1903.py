"""#1903: a body off the DSF's tile keeps its seat by an ``OBJECT_MSL`` row.

LOWS 1.0.469: ``domiki_lows_48.obj``'s east entrance face stands past the
tile edge, so the writer undid the whole split and drew the west face 4.6 m
over the cut floor its reader set.  ``split_guard.on_tile`` anchors such a
body on the tile and seats it by its row; a body of unknown zero still
leaves the split to the writer's undo.  Synthetic records only.
"""
from __future__ import annotations

import dataclasses as dc

import pytest
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import dsf_heights as DH
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import entrance_seat as ES
from auto_patch_v2.airport import split_guard as SG
from auto_patch_v2.airport.placement_file import authored_offset
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.model import placement as PM

BOX = SG.box_of_tile((47, 12))
HDG = 329.5


def _body(k, lat, lon, y0, surface_z=None):
    a = AR.Anchor("building", lat, lon, y0, "seated", surface_z,
                  authored_offset(lat, lon, y0, 47.79, 12.99, HDG))
    return Body(k, "building", (k,), a, f"objects/x__b{k}.obj",
                geom_box=(lat - 1e-4, lon - 1e-4, lat + 1e-4, lon + 1e-4))


def _record(*bodies):
    return Split(183, "dsf:obj183", "objects/x.obj", "objects/x.obj",
                 47.79, 12.99, HDG, tuple(bodies))


def test_box_of_tile_reads_the_tile_or_the_dsf_name():
    assert BOX == (12.0, 47.0, 13.0, 48.0)
    assert SG.box_of_tile(None, "/p/Earth nav data/+40-010/+47-003.dsf") == (
        -3.0, 47.0, -2.0, 48.0)
    assert SG.box_of_tile(None, "") is None


def test_an_off_tile_face_is_anchored_on_the_tile_at_its_zero():
    west = _body(0, 47.7949, 12.9993, 0.67, surface_z=431.62)
    east = _body(3, 47.7969, 13.0038, -5.809)
    out = SG.on_tile(_record(west, east), BOX, lambda b: 431.076 if b is east else None)
    w2, e2 = out.bodies
    assert w2 is west                                   # on the tile: untouched
    assert BOX[0] <= e2.anchor.lon <= BOX[2] and e2.anchor.lon < 13.0
    assert e2.anchor.lat == east.anchor.lat
    # the row draws the file's zero at the face's zero: bottom on the floor
    assert e2.msl_z == pytest.approx(431.076 - 5.809)
    assert e2.anchor.surface_z - e2.anchor.y_zero == pytest.approx(431.076)
    assert e2.anchor.reason.startswith(SG.ON_TILE_REASON)
    # same geometry in the world: the offset moved with the anchor
    want = authored_offset(e2.anchor.lat, e2.anchor.lon, -5.809, 47.79, 12.99, HDG)
    assert e2.anchor.offset == pytest.approx(want)


def test_an_off_tile_body_of_unknown_zero_leaves_the_split_to_the_writer():
    rec = _record(_body(0, 47.7949, 12.9993, 0.0, 431.0),
                  _body(1, 47.7969, 13.0040, -0.1))
    assert SG.on_tile(rec, BOX, lambda b: None) is rec
    assert SG.on_tile(rec, None, lambda b: 1.0) is rec


def test_face_zero_is_the_entrance_end_within_reach():
    zeros = ES.entrance_zeros([{"id": "dsf:obj183", "seat": ES.ENTRANCE_SEAT,
                                "end": [47.7969, 13.0038], "reach_m": 10.0,
                                "elevation": 431.076}])
    m = type("M", (), {"id": "dsf:obj183"})()
    assert ES.face_zero(_body(3, 47.7969, 13.0038, -5.8), m, zeros) == 431.076
    assert ES.face_zero(_body(1, 47.81, 12.998, 0.0), m, zeros) is None


def test_the_row_is_written_object_msl_and_round_trips_the_plan():
    b = PM.Body("b3", "building", (3,), PM.Anchor(12.99999, 47.7969, HDG), "r",
                "objects/x__b3.obj", msl_z=425.267)
    row = W._body_row(["OBJECT", "7", "12.99", "47.79", "329.5"], b, 9)
    assert row.split()[:2] == ["OBJECT_MSL", "9"]
    assert float(row.split()[4]) == pytest.approx(425.267)
    assert PM.Body.from_dict(b.to_dict()).msl_z == pytest.approx(425.267)
    on_ground = dc.replace(b, msl_z=None)
    assert W._body_row(["OBJECT", "7", "1", "2", "0"], on_ground, 9).startswith("OBJECT 9 ")
    assert "msl_z" not in on_ground.to_dict()


def test_a_row_into_a_dsf_without_elevated_rows_is_encodable_finely():
    # DSFLib's empty answer is 0.5 m: a seat there was encoded 0.27 m low
    text = ("HEIGHTS 0.50000 0.0  # max encodeable 32767.50000\n"
            "OBJECT_MSL 0 12.9 47.7 425.267 329.5\n")
    q = float(DH.cover_row_elevations(text).split()[1])
    assert q <= 0.0625
    fine = "HEIGHTS 0.03125 0.0  # x\nOBJECT_MSL 0 12.9 47.7 425.267 329.5\n"
    assert DH.cover_row_elevations(fine) == fine         # unchanged, byte for byte
