"""#1884: a body standing on the NEIGHBOUR tile is written in that tile's
DSF of the pack (``airport/tile_route``), never undone with its whole
placement.

LOWS's pack places every object at one datum on ``+47+012``; the east GA
hangars stand past lon 13.0.  DSFTool refuses a row off its DSF's tile, so
``split_guard`` wrote 82 placements whole from the datum and
``Terminal_LOWS_15``'s walls stood 3.8 m over their ground.  Now the
bodies on ``+47+013`` are GUEST rows of ``+47+013.dsf``, recorded under
``LOWS@+47+012`` beside that DSF's own ``LOWS`` row."""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import backup_state as B
from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import placement_write as PW
from auto_patch_v2.airport import tile_route as TR
from auto_patch_v2.airport import unpatched_pack as UP
from auto_patch_v2.model import placement as PM
from tests.auto_patch_v2.test_backup_state import (
    _Cut, _objs, _record_doc, _stand_in_dsftool)

A, B_ = (47, 12), (47, 13)
DUMP_A = ("PROPERTY sim/west 12\n"
          "PROPERTY sim/overlay 1\n"
          "OBJECT_DEF objects/hangar.obj\n"
          "OBJECT_DEF objects/shed.obj\n"
          "OBJECT_DEF objects/tree.obj\n"
          "OBJECT 0 12.99657 47.79329 329.5\n"
          "OBJECT 1 12.99657 47.79329 329.5\n"
          "OBJECT 2 12.5 47.5 0.0\n")
DUMP_B = ("PROPERTY sim/west 13\n"
          "PROPERTY sim/overlay 1\n"
          "OBJECT_DEF objects/mast.obj\n"
          "OBJECT_MSL 0 13.2 47.6 430.0 0.0\n")


@pytest.fixture(autouse=True)
def _clean_memo():
    B.invalidate_memo()
    yield
    B.invalidate_memo()


def _two_tile_pack(tmp_path):
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    nav = pack / "Earth nav data" / "+40+010"
    nav.mkdir(parents=True)
    a, b = nav / "+47+012.dsf", nav / "+47+013.dsf"
    a.write_text(DUMP_A, encoding="utf-8", newline="")
    b.write_text(DUMP_B, encoding="utf-8", newline="")
    return pack, a, b


def _body(k, res, lon, lat):
    return PM.Body(f"b{k}", "building", (k,), PM.Anchor(lon, lat, 329.5), "",
                   res)


def _plan(pack, dsf, **kw):
    return PM.PlacementPlan("LOWS", "pack", str(pack), str(dsf),
                            str(dsf) + ".anchor_bak",
                            PM.Provenance("", "1.0.513", ""), **kw)


def _lows_a(pack, a):
    """Placement 0 stands on both tiles; placement 1 wholly on +47+013."""
    sp0 = PM.Split(PM.PlacementRef(0, "objects/hangar.obj", 12.99657, 47.79329, 329.5),
                   (_body(0, "objects/hangar__b0_aa.obj", 12.9970, 47.7960),
                    _body(1, "objects/hangar__b1_bb.obj", 13.0051, 47.7960)))
    sp1 = PM.Split(PM.PlacementRef(1, "objects/shed.obj", 12.99657, 47.79329, 329.5),
                   (_body(0, "objects/shed__b0_cc.obj", 13.0078, 47.7924),))
    files = [_Cut(r) for r in ("objects/hangar__b0_aa.obj",
                               "objects/hangar__b1_bb.obj",
                               "objects/shed__b0_cc.obj")]
    return _plan(pack, a, splits=(sp0, sp1)), files


def _rows(dsf):
    """The placement rows, each def index spelled as its definition."""
    lines = dsf.read_text(encoding="utf-8").splitlines()
    defs = [ln.split()[1] for ln in lines if ln.startswith("OBJECT_DEF ")]
    out = []
    for ln in lines:
        t = ln.split()
        if t and t[0] in ("OBJECT", "OBJECT_MSL", "OBJECT_AGL"):
            out.append(" ".join([t[0], defs[int(t[1])]] + t[2:]))
    return out


def test_route_takes_each_body_to_the_tile_it_stands_on(tmp_path):
    pack, a, _b = _two_tile_pack(tmp_path)
    plan, _files = _lows_a(pack, a)
    here, guests = TR.route(plan, A, TR._pack_has_dsf(str(pack)))
    assert [len(s.bodies) for s in here.splits] == [1, 0]
    assert here.splits[0].bodies[0].new_resource == "objects/hangar__b0_aa.obj"
    assert list(guests) == [B_]
    assert [(s.placement.index, [b.new_resource for b in s.bodies])
            for s in guests[B_]] == [(0, ["objects/hangar__b1_bb.obj"]),
                                     (1, ["objects/shed__b0_cc.obj"])]
    assert here.provenance.counts["bodies_routed_to_neighbour"] == 2
    assert here.provenance.counts["placements_routed_whole"] == 1


def test_route_leaves_a_body_with_no_neighbour_dsf_or_on_the_edge(tmp_path):
    pack, a, b = _two_tile_pack(tmp_path)
    plan, _files = _lows_a(pack, a)
    same, guests = TR.route(plan, A, lambda _t: False)
    assert same is plan and guests == {}
    edge = PM.Split(PM.PlacementRef(0, "objects/hangar.obj", 12.99657, 47.79329, 329.5),
                    (_body(0, "objects/hangar__b0_aa.obj", 13.000004, 47.7960),))
    same, guests = TR.route(_plan(pack, a, splits=(edge,)), A, lambda _t: True)
    assert guests == {}
    assert TR._tile_of(47.7960, 13.000004) is None
    assert TR._tile_of(47.7960, 13.0051) == B_


def test_plan_carries_guests_through_json_record_and_compose(tmp_path):
    pack, a, b = _two_tile_pack(tmp_path)
    plan, _files = _lows_a(pack, a)
    _here, guests = TR.route(plan, A, lambda _t: True)
    gp = TR.guest_plan(plan, A, B_, guests[B_])
    assert gp.icao == "LOWS@+47+012" and D.owner_of(gp.icao) == "LOWS"
    assert gp.dsf_path.endswith("+47+013.dsf")
    assert gp.new_resources() == ("objects/hangar__b1_bb.obj",
                                  "objects/shed__b0_cc.obj")
    back = PM.PlacementPlan.from_dict({**gp.edit_rows(), "pack_root": str(pack)})
    assert back.guests == tuple(
        PM.Split(s.placement, tuple(PM.Body(x.body_id, x.body_class, (), x.anchor,
                                            "", x.new_resource) for x in s.bodies))
        for s in gp.guests)
    assert PM.PlacementPlan.from_dict(gp.to_dict()).guests == gp.guests
    own = _plan(pack, b)
    assert own.compose([gp]).guests == gp.guests
    assert own.claimed_indices() == own.compose([gp]).claimed_indices()


def test_guest_rows_land_in_the_neighbour_dsf_and_survive_its_own_build(
        tmp_path, monkeypatch):
    """RED ON BASE: both bodies on +47+013 undid their splits and the two
    placements were written whole at the datum on +47+012."""
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    plan, files = _lows_a(pack, a)
    said = []

    def write_guest(gp, gfiles):
        return PW.apply_plan(gp, gfiles, tool, work_dir=str(tmp_path / "wg"))
    here, own, guest_files = TR.write_guests(plan, files, A, write_guest,
                                             say=said.append)
    PW.apply_plan(here, own, tool, work_dir=str(tmp_path / "wa"))
    PW.write_files(str(pack), guest_files)

    # +47+012: placement 0 keeps its west body, placement 1 is gone
    rows_a = _rows(a)
    assert rows_a == [
        "OBJECT objects/hangar__b0_aa.obj 12.997000000 47.796000000 329.500000",
        "OBJECT objects/tree.obj 12.5 47.5 0.0"]
    # +47+013: its own row as authored, then the two guest bodies
    rows_b = _rows(b)
    guests = ["OBJECT objects/hangar__b1_bb.obj 13.005100000 47.796000000 329.500000",
              "OBJECT objects/shed__b0_cc.obj 13.007800000 47.792400000 329.500000"]
    assert rows_b == ["OBJECT_MSL objects/mast.obj 13.2 47.6 430.0 0.0"] + guests
    assert _objs(pack) == ["hangar__b0_aa.obj", "hangar__b1_bb.obj",
                           "shed__b0_cc.obj"]
    entry = _record_doc(b)["dsfs"]["+47+013.dsf"]
    assert entry["airports"]["LOWS@+47+012"]["body_files"] == [
        "objects/hangar__b1_bb.obj", "objects/shed__b0_cc.obj"]
    assert said and "+47+013" in said[0]

    # +47+013's own LOWS build re-applies the guest rows beside its edit
    conv = PM.Conversion(0, "objects/mast.obj", 13.2, 47.6, 0.0, "OBJECT_MSL", 430.0)
    res = PW.apply_plan(_plan(pack, b, conversions=(conv,)), [], tool,
                        work_dir=str(tmp_path / "wb"))
    assert res.dsf.composed_airports == ("LOWS@+47+012",)
    assert _rows(b) == ["OBJECT objects/mast.obj 13.2 47.6 0.0"] + guests
    assert _objs(pack) == ["hangar__b0_aa.obj", "hangar__b1_bb.obj",
                           "shed__b0_cc.obj"]

    # an airport left without a patch takes its guest rows with it
    assert UP.seated_airports(str(b)) == ("LOWS",)
    out = UP.restore_airport(str(pack), str(b), "LOWS", tool)
    assert out.state == UP.RESTORED
    assert _rows(b) == ["OBJECT_MSL objects/mast.obj 13.2 47.6 430.0 0.0"]


def test_a_refused_neighbour_write_keeps_the_bodies_here(tmp_path):
    pack, a, _b = _two_tile_pack(tmp_path)
    plan, files = _lows_a(pack, a)

    def refuse(_gp, _gfiles):
        raise RuntimeError("backup unproven")
    said = []
    here, own, written = TR.write_guests(plan, files, A, refuse, said.append)
    assert here.splits == plan.splits and written == []
    assert [f.resource for f in own] == [f.resource for f in files]
    assert "written whole" in said[0]


def test_the_split_reads_the_neighbours_ground_past_the_edge():
    """RED ON BASE: the mesh ends at the tile edge, so every body past it
    had no ground and the split lumped them into one file."""
    def mesh(lat, lon):
        return (431.0, False) if lon < 13.0 else None
    mesh.many = lambda las, los: [mesh(a, o) for a, o in zip(las, los, strict=True)]

    def ground(lats, lons):
        import numpy as np
        return np.full(np.shape(lats), 428.0)
    s = TR.with_neighbour_ground(mesh, A, ground)
    assert s(47.79, 12.99) == (431.0, False)
    assert s(47.79, 13.005) == (428.0, False)
    assert s.many([47.79, 47.79], [12.99, 13.005]) == [(431.0, False), (428.0, False)]
    assert TR.with_neighbour_ground(mesh, A, None) is mesh


def test_on_tile_leaves_a_routable_body_to_its_own_tile():
    """``split_guard.on_tile`` clamped every off-tile body with a known
    zero into this DSF by an OBJECT_MSL row; one another DSF of the pack
    carries is now left where it stands — unless a cut gave it its exact
    seat (an entrance face, #1903)."""
    from auto_patch_v2.airport import placement_record as PR
    from auto_patch_v2.airport import split_guard as SG
    rec = _record(PR, surface_z=428.0)
    box = (12.0, 47.0, 13.0, 48.0)
    same = SG.on_tile(rec, box, lambda _b: None, lambda la, lo: lo > 13.0)
    assert same is rec
    clamped = SG.on_tile(rec, box, lambda _b: None, lambda _la, _lo: False)
    assert clamped.bodies[0].msl_z is not None
    face = SG.on_tile(rec, box, lambda _b: 430.9, lambda la, lo: lo > 13.0)
    assert face.bodies[0].anchor.lon < 13.0


def _record(PR, surface_z):
    """A one-body split on +47+012 whose body stands past lon 13.0."""
    from auto_patch_v2.airport import anchor_rule as AR
    a = AR.Anchor("building", 47.7960, 13.0051, 0.0, "own ground",
                  surface_z=surface_z)
    return PR.Split(0, "dsf:obj0", "objects/hangar.obj", "", 47.79329,
                    12.99657, 329.5, (PR.Body(0, "building", (0,), a,
                                              "objects/hangar__b0.obj"),))
