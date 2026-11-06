"""#1883 round 3 / #1914 (spec lgav-corridor-cut-and-deck-ends-20261106): the
pack's CONCAVE CUT SHELL is the ground over its whole footprint (A1-A4), a
shallower shell inside a deeper one owns none (A4), the deepest shell with its
rim at the ground is left out of the written DSF (A7, owner 2026-11-06T16:13Z),
and its frame is written whole at the zero the shell was read at except a
deck the pavement drives across (B1/B2).  ONE shape reading serves the engine
and the drawn instrument (``geom/shape_class``)."""
from __future__ import annotations

import dataclasses
import sys
import types
from pathlib import Path

import numpy as np
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from auto_patch_v2.airport import terrain_shaped as TS
from auto_patch_v2.geom import shape_class as SC
from auto_patch_v2.geom.plane_groups import plane_groups
from auto_patch_v2.model.placement import HIDDEN, MslSeat, PlacementPlan, Provenance
from test_hanging_objects1298 import LAW, THICK, _placed, _write


def _quad(a, b, c, d):
    return [(a, b, c), (a, c, d)]


def _section(xs, ys, length=100.0):
    """A trough along z: the cross-section ``(x, y)`` swept 0..length."""
    tris = []
    pts = list(zip(xs, ys, strict=True))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        tris += _quad((x0, y0, 0.0), (x1, y1, 0.0), (x1, y1, length), (x0, y0, length))
    return tris


def _shell(tmp_path, name="shell.obj", floor=-8.0, half=10.0, lip=18.0, bank=3.0):
    """Lips at y 0 out to ``lip``, steep banks ``bank`` wide down to
    ``floor``, a floor ``2 half`` wide (a floor object would be all plates:
    its banks here are walls, under ``plate_normal_y_min``)."""
    xs = [-lip, -half - bank, -half, half, half + bank, lip]
    ys = [0.0, 0.0, floor, floor, 0.0, 0.0]
    return _write(tmp_path / name, [_section(xs, ys)])


def test_one_shape_reading_serves_the_engine_and_the_drawn_instrument(tmp_path):
    g = O.parse_obj8(_shell(tmp_path))
    P = g.vertices[g.solid][:, :, [0, 2, 1]]
    r = SC.rasterise(P, 20000)
    sh = SC.shape_of(r, P.reshape(-1, 3), band_m=1.0, reach_m=2.0, hollow_m=1.0,
                     stacked_m=1.5, flat_m=1.0)
    assert sh["class"] == SC.CONCAVE and abs(sh["rim"]) < 0.01
    plate = np.array([[[0, 0, 0.0], [10, 0, 0.0], [0, 10, 0.1]]])
    assert SC.shape_of(SC.rasterise(plate), plate.reshape(-1, 3), band_m=1.0, reach_m=2.0,
                       hollow_m=1.0, stacked_m=1.5, flat_m=1.0)["class"] == SC.FLAT
    top, low = np.array([0.0, 0.0, 0.0]), np.array([-6.0, -6.0, 0.0])
    assert SC.shape_class(top, low, 0.5, hollow_m=1.0, stacked_m=1.5)[0] == SC.COVERED
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import drawn_site_check as DC
    assert DC._shape is SC


def test_a_shell_parts_into_its_planes():
    xs, ys = [-18.0, -13.0, -10.0, 10.0, 13.0, 18.0], [0.0, 0.0, -8.0, -8.0, 0.0, 0.0]
    faces = np.array([[(x, z, y) for x, y, z in t] for t in _section(xs, ys)])
    groups = plane_groups(faces, 0.5, 1.0)
    # two lips, two banks, the floor: five planes of two faces each
    assert len(groups) == 5 and sorted(len(g) for g in groups) == [2, 2, 2, 2, 2]


def test_the_shell_is_the_ground_its_liner_owns_none_and_it_is_hidden(tmp_path):
    """Read as §33 (6) B shells (``object_cut``'s pairing): the deeper one
    is the ground, the liner inside it owns none, the rail rides the zero."""
    cache = O.ResourceCache(THICK)
    objs = [_placed(_shell(tmp_path), "dsf:obj1"),
            _placed(_shell(tmp_path, "liner.obj", floor=-3.0, half=4.0, lip=7.0, bank=1.0),
                    "dsf:obj2"),
            _placed(_write(tmp_path / "rail.obj", [_section([-1.0, 1.0], [-7.9, -7.9])]),
                    "dsf:obj3")]
    shells = {"dsf:obj1": ("dsf:obj3", None), "dsf:obj2": ("dsf:obj3", None)}
    floors, notes = OF.read_object_floors(
        objs, cache, LAW, {}, shells=shells, ground=lambda xs, ys: np.full(len(xs), 100.0))
    by = {f.object_id: f for f in floors}
    shell, liner = by["dsf:obj1"], by["dsf:obj2"]
    assert shell.kind == OF.SHELL and OF.owns_ground(shell), notes
    assert shell.footprint.area > 0.95 * 36.0 * 100.0          # lip to lip, end to end
    z = OF.floor_z_at(shell.faces, [0.0, -11.5, -15.0], [-50.0, -50.0, -50.0])
    assert abs(z[0] - 92.0) < 1e-6 and abs(z[1] - 96.0) < 1e-6 and abs(z[2] - 100.0) < 1e-6
    assert not OF.owns_ground(liner) and not liner.hidden      # A4: inside a deeper one
    assert shell.hidden                                       # A7: rim at the ground
    recs = {r["id"]: r for r in OF.seat_records(floors)}
    assert recs["dsf:obj1"]["seat"] == TS.HIDDEN_SEAT          # its row is dropped
    assert recs["dsf:obj3"]["seat"] == TS.OBJECT_FLOOR_SEAT    # B1: the frame at its zero
    assert recs["dsf:obj3"]["elevation"] == 100.0


def test_a_deck_of_the_frame_is_planned_at_the_frame_zero(tmp_path):
    cache = O.ResourceCache(THICK)
    floors, _notes = OF.read_object_floors(
        [_placed(_shell(tmp_path), "dsf:obj1"),
         _placed(_write(tmp_path / "deck.obj", [_section([-17.0, 17.0], [0.1, 0.1], 20.0)]),
                 "dsf:obj4")], cache, LAW, {}, shells={"dsf:obj1": ("dsf:obj4", None)},
        ground=lambda xs, ys: np.full(len(xs), 100.0))
    deck = OF.FloorDeck("dsf:obj4#0", "dsf:obj4", "objects/dsf:obj4.obj", (), (), (), 0.1, 0.1)
    f = dataclasses.replace(floors[0], decks=(deck,),
                            seats=tuple(s for s in floors[0].seats if s[0] != "dsf:obj4"))
    recs = {r["id"]: r for r in OF.seat_records([f])}
    assert recs["dsf:obj4"]["seat"] == TS.FRAME_SEAT
    assert TS.frame_zeros(recs.values()) == {"dsf:obj4": 100.0}


def test_a_hidden_row_is_left_out_of_the_written_dsf():
    rows = [types.SimpleNamespace(def_path="Trench/shell.obj", lon=23.94, lat=37.93,
                                  heading_deg=0.0)]
    got = TS.row_seats(types.SimpleNamespace(placements=rows),
                       [{"id": "dsf:obj0", "resource": "Trench/shell.obj",
                         "seat": TS.HIDDEN_SEAT, "elevation": 77.72}], frozenset())
    assert [m.why for m in got] == [HIDDEN]
    text = ("A\n800 written by DSFTool 2.4.0-b1\nDSF2TEXT\n\nPROPERTY sim/west 23\n"
            "OBJECT_DEF Trench/shell.obj\nOBJECT_DEF Trench/deck.obj\n"
            "OBJECT 0 23.940777352 37.935378042 0.000000\n"
            "OBJECT 1 23.940777352 37.935378042 0.000000\n")
    plan = PlacementPlan(icao="T", pack_name="p", pack_root="/r", dsf_path="/r/x.dsf",
                         dsf_backup_path="/r/x.dsf.anchor_bak",
                         provenance=Provenance("", "", "", {}),
                         msl_seats=(MslSeat(0, "Trench/shell.obj", 23.94, 37.93, 0.0, 77.72,
                                            HIDDEN),))
    out = W.edit_dump(text, plan)
    assert "OBJECT 0 " not in out and "OBJECT 1 23.940777352" in out
