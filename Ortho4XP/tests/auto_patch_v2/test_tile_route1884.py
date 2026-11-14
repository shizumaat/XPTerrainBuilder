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
from auto_patch_v2.airport import pack_lock as PL
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


GUESTS = ["OBJECT objects/hangar__b1_bb.obj 13.005100000 47.796000000 329.500000",
          "OBJECT objects/shed__b0_cc.obj 13.007800000 47.792400000 329.500000"]
MAST_MSL = "OBJECT_MSL objects/mast.obj 13.2 47.6 430.0 0.0"
ALL3 = ["hangar__b0_aa.obj", "hangar__b1_bb.obj", "shed__b0_cc.obj"]


def _routed(pack, a, tool, tmp_path, tag="wa", plan_files=None):
    """+47+012's LOWS write, routed (``placement_write.apply_routed``)."""
    plan, files = plan_files or _lows_a(pack, a)
    said: list = []
    res = PW.apply_routed(plan, files, tool, here=A, say=said.append,
                          work_dir=str(tmp_path / tag))
    return res, said


def _snapshot(pack):
    """Every file of the pack: ``{relative path: bytes}``."""
    return {str(p.relative_to(pack)): p.read_bytes()
            for p in sorted(pack.rglob("*")) if p.is_file()}


def _b_own(pack, b, tool, tmp_path, tag="wb"):
    """+47+013's own LOWS build: its mast converted to on-ground."""
    conv = PM.Conversion(0, "objects/mast.obj", 13.2, 47.6, 0.0, "OBJECT_MSL", 430.0)
    return PW.apply_plan(_plan(pack, b, conversions=(conv,)), [], tool,
                         work_dir=str(tmp_path / tag))


def test_guest_rows_land_in_the_neighbour_dsf_and_survive_its_own_build(
        tmp_path, monkeypatch):
    """RED ON BASE: both bodies on +47+013 undid their splits and the two
    placements were written whole at the datum on +47+012."""
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    res, said = _routed(pack, a, tool, tmp_path)

    # +47+012: placement 0 keeps its west body, placement 1 is gone
    assert _rows(a) == [
        "OBJECT objects/hangar__b0_aa.obj 12.997000000 47.796000000 329.500000",
        "OBJECT objects/tree.obj 12.5 47.5 0.0"]
    # +47+013: its own row as authored, then the two guest bodies
    assert _rows(b) == [MAST_MSL] + GUESTS
    assert _objs(pack) == ALL3
    entry = _record_doc(b)["dsfs"]["+47+013.dsf"]
    assert entry["airports"]["LOWS@+47+012"]["body_files"] == [
        "objects/hangar__b1_bb.obj", "objects/shed__b0_cc.obj"]
    assert [g.dsf_path for g in res.guests] == [str(b)]
    assert res.counts["guest_bodies_written"] == 2
    assert res.files_written == (str(pack / "objects" / "hangar__b0_aa.obj"),)
    assert said and "+47+013" in said[0]

    # +47+013's own LOWS build re-applies the guest rows beside its edit
    own_b = _b_own(pack, b, tool, tmp_path)
    assert own_b.dsf.composed_airports == ("LOWS@+47+012",)
    assert _rows(b) == ["OBJECT objects/mast.obj 13.2 47.6 0.0"] + GUESTS
    assert _objs(pack) == ALL3


def test_neighbour_unpatched_keeps_the_guest_rows(tmp_path, monkeypatch):
    """#1884 round 2 B1 (i), RED ON lows1884: +47+013 left without a patch
    for LOWS folded ``LOWS@+47+012`` into LOWS and took the guest rows
    with it — the placements were drawn by neither tile."""
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    _b_own(pack, b, tool, tmp_path)
    assert UP.seated_airports(str(b)) == ("LOWS", "LOWS@+47+012")
    out = UP.restore_airport(str(pack), str(b), "LOWS", tool,
                             work_dir=str(tmp_path / "wr"))
    assert out.state == UP.RECOMPOSED and out.kept == ("LOWS@+47+012",)
    assert _rows(b) == [MAST_MSL] + GUESTS
    assert _objs(pack) == ALL3
    assert UP.seated_airports(str(b)) == ("LOWS@+47+012",)
    # a key no build wrote leaves it alone
    assert UP.restore_airport(str(pack), str(b), "EDNV", tool).state == UP.NONE


def test_home_unpatched_takes_its_guest_rows_out_of_the_neighbour(
        tmp_path, monkeypatch):
    """#1884 round 2 B1 (ii), RED ON lows1884: unpatching +47+012 put its
    DSF back to whole objects while +47+013 kept the guest rows — the
    placements were drawn by both."""
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    out = UP.restore_airport(str(pack), str(a), "LOWS", tool)
    assert out.state == UP.RESTORED
    assert [(n.state, n.dsf_path) for n in out.neighbours] == [(UP.RESTORED, str(b))]
    assert a.read_text(encoding="utf-8") == DUMP_A
    assert b.read_text(encoding="utf-8") == DUMP_B
    assert _objs(pack) == []                # no orphaned body file


def test_home_unpatched_recomposes_a_neighbour_with_its_own_rows(
        tmp_path, monkeypatch):
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    _b_own(pack, b, tool, tmp_path)
    out = UP.restore_airport(str(pack), str(a), "LOWS", tool,
                             work_dir=str(tmp_path / "wr"))
    assert [n.state for n in out.neighbours] == [UP.RECOMPOSED]
    assert _rows(a) == ["OBJECT objects/hangar.obj 12.99657 47.79329 329.5",
                        "OBJECT objects/shed.obj 12.99657 47.79329 329.5",
                        "OBJECT objects/tree.obj 12.5 47.5 0.0"]
    assert _rows(b) == ["OBJECT objects/mast.obj 13.2 47.6 0.0"]
    assert UP.seated_airports(str(b)) == ("LOWS",)
    assert _objs(pack) == []


def test_a_stale_guest_row_takes_its_home_dsf_back(tmp_path, monkeypatch):
    """#1884 round 2 B1: a guest row a write cannot re-apply (built
    against another version of the neighbour DSF) takes its home DSF back
    to the original for that airport, said at verbosity 0 — rigid as
    authored, never missing."""
    import json

    import O4_UI_Utils as UI
    from auto_patch_v2.airport import dsf_dump_key as DK
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    record = b.parent / "o4_placement_provenance.json"
    doc = json.loads(record.read_text(encoding="utf-8"))
    doc["dsfs"]["+47+013.dsf"]["airports"]["LOWS@+47+012"][DK.KEY_FIELD] = "stale"
    record.write_text(json.dumps(doc), encoding="utf-8", newline="\n")
    B.invalidate_memo()
    said: list = []
    monkeypatch.setattr(UI, "vprint",
                        lambda lvl, *a: said.append((lvl, " ".join(map(str, a)))))

    res = _b_own(pack, b, tool, tmp_path)
    assert res.dsf.stale_guests == ("LOWS@+47+012",)
    assert _rows(b) == ["OBJECT objects/mast.obj 13.2 47.6 0.0"]
    assert a.read_text(encoding="utf-8") == DUMP_A
    assert _objs(pack) == []
    assert any(lvl == 0 and "LOWS" in t and "+47+012.dsf" in t and "original" in t
               for lvl, t in said), said


def test_a_body_that_changed_tile_is_never_removed(tmp_path, monkeypatch):
    """The second write of a tile moves one body from its own DSF to the
    neighbour's and one back: every restore runs before any body lands,
    so neither is removed after it was written (the post-hoc
    ``write_files`` of lows1884 is gone)."""
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    sp0 = PM.Split(PM.PlacementRef(0, "objects/hangar.obj", 12.99657, 47.79329, 329.5),
                   (_body(0, "objects/hangar__b0_aa.obj", 13.0040, 47.7960),
                    _body(1, "objects/hangar__b1_bb.obj", 12.9990, 47.7960)))
    sp1 = PM.Split(PM.PlacementRef(1, "objects/shed.obj", 12.99657, 47.79329, 329.5),
                   (_body(0, "objects/shed__b0_cc.obj", 13.0078, 47.7924),))
    files = [_Cut(r) for r in ("objects/hangar__b0_aa.obj",
                               "objects/hangar__b1_bb.obj",
                               "objects/shed__b0_cc.obj")]
    _routed(pack, a, tool, tmp_path, "wa2", (_plan(pack, a, splits=(sp0, sp1)), files))
    assert _objs(pack) == ALL3
    assert _rows(a)[0] == ("OBJECT objects/hangar__b1_bb.obj 12.999000000 "
                           "47.796000000 329.500000")
    assert _rows(b)[1] == ("OBJECT objects/hangar__b0_aa.obj 13.004000000 "
                           "47.796000000 329.500000")


def test_a_raise_in_any_write_puts_every_dsf_back(tmp_path, monkeypatch):
    """#1884 round 2 B2, RED ON lows1884: the guest write, the own write
    and the post-hoc body write were three acts; a raise in the second
    left the guests drawn by both.  Now one transaction: a raise in the
    LAST DSF's encode leaves the pack byte-identical."""
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    before = _snapshot(pack)
    real = PW._dw.write_pack

    def boom(pack_root, plan, tool_, **kw):
        if plan.dsf_path == str(b):
            raise RuntimeError("encode failed")
        return real(pack_root, plan, tool_, **kw)
    monkeypatch.setattr(PW._dw, "write_pack", boom)
    sp0 = PM.Split(PM.PlacementRef(0, "objects/hangar.obj", 12.99657, 47.79329, 329.5),
                   (_body(0, "objects/hangar__b0_x1.obj", 12.9970, 47.7960),
                    _body(1, "objects/hangar__b1_x2.obj", 13.0051, 47.7960)))
    files = [_Cut("objects/hangar__b0_x1.obj"), _Cut("objects/hangar__b1_x2.obj")]
    with pytest.raises(RuntimeError, match="encode failed"):
        _routed(pack, a, tool, tmp_path, "wa2", (_plan(pack, a, splits=(sp0,)), files))
    B.invalidate_memo()
    assert _snapshot(pack) == before


def test_a_neighbour_dsf_that_stands_down_keeps_the_bodies_here(
        tmp_path, monkeypatch):
    """A neighbour DSF whose write would stand down (here: its original is
    lost) takes no guest: the bodies stay in this tile's plan for
    ``split_guard``'s undo (written whole), and the neighbour is named."""
    pack, a, b = _two_tile_pack(tmp_path)
    b.write_text(DUMP_B + f"PROPERTY {B.OWNERSHIP_PROPERTY} 1.0\n",
                 encoding="utf-8", newline="")
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    lost = b.read_bytes()
    res, said = _routed(pack, a, tool, tmp_path)
    assert res.guests == ()
    assert b.read_bytes() == lost
    assert "written whole" in said[0]
    # the stand-in DSFTool places an off-tile row; the real one refuses it
    # and ``write_pack`` undoes the split (``split_guard``, #1246)
    assert any("hangar__b1_bb.obj" in r for r in _rows(a))


def test_a_rewrite_of_the_neighbour_re_applies_the_guest_rows(
        tmp_path, monkeypatch):
    """A forest / drape / optimise rewrite of a DSF (``write_pack`` with
    no airport) re-applies every recorded row, the guest rows included."""
    from auto_patch_v2.airport import dsf_write as W
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    plan = PM.PlacementPlan("", "pack", str(pack), str(b), str(b) + ".anchor_bak",
                            PM.Provenance("", "1.0.513", ""))
    with PL.hold(str(pack)):
        res = W.write_pack(str(pack), plan, tool, forests={},
                           work_dir=str(tmp_path / "wf"))
    assert res.composed_airports == ("LOWS@+47+012",)
    assert _rows(b) == [MAST_MSL] + GUESTS
    assert _objs(pack) == ALL3


def test_a_held_pack_lock_refuses_every_writer(tmp_path, monkeypatch):
    """#1884 round 2 B3: ONE lock per pack, at every writer's entry; a
    lock that cannot be had REFUSES the write (``hold_file_lock`` gave up
    after 900 s and ``apply_plan`` wrote anyway)."""
    import os

    import O4_File_Lock as FL
    pack, a, b = _two_tile_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, monkeypatch)
    _routed(pack, a, tool, tmp_path)
    monkeypatch.setattr(PL, "WAIT_SECONDS", 0.3)
    lock = PL._lock_path(str(pack))
    assert lock == str(pack / "Earth nav data" / "o4_pack_write.lock")
    with open(lock, "w", encoding="utf-8", newline="\n") as fh:   # a live holder
        fh.write(f"{os.getpid()} now {FL._host()}\n")
    before = _snapshot(pack)
    plan, files = _lows_a(pack, a)
    with pytest.raises(TimeoutError):
        PW.apply_routed(plan, files, tool, here=A)
    with pytest.raises(TimeoutError):
        PW.apply_plan(_plan(pack, b), [], tool)
    with pytest.raises(TimeoutError):
        UP.restore_airport(str(pack), str(a), "LOWS", tool)
    assert _snapshot(pack) == before


def test_the_pack_lock_is_not_reentrant_and_obeys_the_write_guard(tmp_path):
    pack, _a, _b = _two_tile_pack(tmp_path)
    with PL.hold(str(pack)):
        with pytest.raises(RuntimeError, match="already held"):
            with PL.hold(str(pack)):
                pass
    with PL.hold(str(pack)):            # released: taken again
        pass
    assert not (pack / "Earth nav data" / "o4_pack_write.lock").exists()
    live = tmp_path / "X-Plane 12" / "Custom Scenery" / "pack"
    (live / "Earth nav data").mkdir(parents=True)
    with pytest.raises(PermissionError):
        with PL.hold(str(live)):
            pass
    assert list((live / "Earth nav data").iterdir()) == []
    with PL.hold(str(live), allow_live_install=True):
        assert (live / "Earth nav data" / "o4_pack_write.lock").exists()


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
