"""Spec 2120-F (owner RULINGS 2026-11-16x option (a)): a frame whose
AIRSIDE FLOOR stands a storey over its authored zero, over a lower floor
off the airside, is read at that floor (``airport/airside_floor``, R1); the
flag rides the plan (R2); its held block seeds the frame's lower pad
(``planar/low_level.frame_seeds`` -> ``low_extent.extend_levels``, R3); it
is never a storey shell (R4).  Synthetic packs in ``tmp_path``; no corpus."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import airside_floor as AF
from auto_patch_v2.airport import obj8 as O8
from shapely.geometry import box
from test_msl_feet import _boxes

Z = 300.0
#: the apt.dat airside pavement: frame x >= 100 (heading 0: frame x = x)
AIR = box(100.0, -50.0, 400.0, 50.0)


def _witness(air=AIR):
    """``airside_floor.witness`` over one apt.dat pavement ``air``."""
    from auto_patch_v2.law import Law
    pv = types.SimpleNamespace(id="apt:1", outer=list(air.exterior.coords)[:-1], holes=[])
    return AF.witness(types.SimpleNamespace(pavements=[pv]), Law.for_airport("ZZZZ"))


def _two_floor(tmp_path, name="f.obj", under=()):
    """Six 5 m concourse boxes at y 15 on the airside, six 10 m hall boxes
    at y 0 off it (and ``under``: boxes at y 5 on the airside)."""
    conc = [(110.0 + 20.0 * i, 15.0, 120.0 + 20.0 * i, 20.0) for i in range(6)]
    hall = [(-90.0 + 15.0 * i, 0.0, -80.0 + 15.0 * i, 10.0) for i in range(6)]
    low = [(110.0 + 20.0 * i, 5.0, 115.0 + 20.0 * i, 8.0) for i in under]
    return _boxes(tmp_path, name, conc + hall + low)


def _read(tmp_path, rows, wit):
    cache = O8.ResourceCache(0.05)
    objs, rep = O8.read_placed_objects(
        rows, str(tmp_path), None, lambda x, y: Z, 0.5, 0.05, 0.3, cache,
        floor_plate_normal_y_min=0.9, msl_tol_m=0.3, airside=wit)
    return objs, rep, cache


def test_a_two_floor_frame_is_read_at_its_airside_floor(tmp_path):
    p = _two_floor(tmp_path)
    rows = [("dsf:obj0", p, (0.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj1", p, (0.0, 0.0), 0.0, 0.0, "OBJECT_AGL")]
    objs, rep, _c = _read(tmp_path, rows, _witness())
    assert [(o.zero_y, o.floor_zero) for o in objs] == [(15.0, True), (15.0, True)]
    assert len(rep.floor_frames) == 1 and "y_a +15.00 y_l +0.00" in rep.floor_frames[0]
    # no witness, no airside, or the airside elsewhere: the frame as authored
    for wit in (None, _witness(box(1000.0, 0.0, 1100.0, 10.0))):
        objs, rep, _c = _read(tmp_path, rows, wit)
        assert all(o.zero_y == 0.0 and not o.floor_zero for o in objs)
        assert not rep.floor_frames


def test_one_airside_foot_under_the_floor_refuses(tmp_path):
    """The strict clause: nothing of the frame on the airside under it."""
    p = _two_floor(tmp_path, under=(0,))
    objs, rep, _c = _read(tmp_path, [("dsf:obj0", p, (0.0, 0.0), 0.0, None, "OBJECT")],
                          _witness())
    (o,) = objs
    assert o.zero_y == 0.0 and not o.floor_zero and not rep.floor_frames


def test_msl_and_lifted_families_are_untouched(tmp_path):
    p = _two_floor(tmp_path)
    for row in (("dsf:obj0", p, (0.0, 0.0), 0.0, 3.0, "OBJECT_AGL"),
                ("dsf:obj0", p, (0.0, 0.0), 0.0, 40.0, "OBJECT_MSL")):
        objs, rep, _c = _read(tmp_path, [row], _witness())
        assert not objs[0].floor_zero and not rep.floor_frames
    # one ineligible member keeps the whole family as authored
    rows = [("dsf:obj0", p, (0.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj1", p, (0.0, 0.0), 0.0, 2.0, "OBJECT_AGL")]
    objs, rep, _c = _read(tmp_path, rows, _witness())
    assert not any(o.floor_zero for o in objs) and not rep.floor_frames


def test_no_lower_floor_no_rezero(tmp_path):
    """A frame standing wholly a storey up (nothing off the airside at its
    zero) is no two-floor frame."""
    conc = [(110.0 + 20.0 * i, 15.0, 120.0 + 20.0 * i, 20.0) for i in range(6)]
    hall = [(-90.0 + 15.0 * i, 14.0, -80.0 + 15.0 * i, 24.0) for i in range(6)]
    p = _boxes(tmp_path, "high.obj", conc + hall)
    objs, rep, _c = _read(tmp_path, [("dsf:obj0", p, (0.0, 0.0), 0.0, None, "OBJECT")],
                          _witness())
    assert not objs[0].floor_zero and not rep.floor_frames


def test_the_concourse_stands_on_the_zero_and_the_hall_a_storey_under(tmp_path):
    """The partition reads the frame at its floor: the concourse parts are
    GROUND parts (feet at authored y 0), the hall's at -15."""
    from test_msl_feet import _partition
    p = _two_floor(tmp_path)
    objs, _rep, cache = _read(tmp_path, [("dsf:obj0", p, (0.0, 0.0), 0.0, None, "OBJECT")],
                              _witness())
    part = _partition(objs, cache)
    bases = sorted({round(pp.base_y, 3) for pp in part.parts})
    assert bases == [-15.0, 0.0]
    assert all(pp.feet.shape[0] > 0 for pp in part.parts)


def test_the_flag_rides_the_plan(tmp_path):
    from auto_patch_v2.model.rebake import Member, RebakePlan, Unit
    m = Member(id="dsf:obj0", resource="objects/f.obj", authored_path="a", live_path="a",
               heading_deg=0.0, parts=(), deck_ring=None, deck_top_y=None,
               deck_datum_z=None, zero_y=15.0, floor_zero=True)
    plan = RebakePlan(icao="ZZZZ", pack_name="p", pack_root="/r",
                      units=(Unit(id="u0", anchor=(0.0, 0.0), agl_m=0.0, members=(m,)),),
                      skipped=(), counts={})
    back = RebakePlan.from_dict(plan.to_dict())
    (mm,) = back.units[0].members
    assert mm.zero_y == 15.0 and mm.floor_zero


def test_a_plain_object_read_at_its_floor_is_written_pristine(tmp_path):
    """The writer restores the pristine frame for a plain ``OBJECT`` read
    against its floor exactly as for #1102's MSL rows."""
    from auto_patch_v2.airport import placement_file as PF
    from auto_patch_v2.airport.placement_record import Split
    path = str(tmp_path / _boxes(tmp_path, "conc.obj", [(0.0, 15.0, 4.0, 30.0)]))
    body = types.SimpleNamespace(body_id=0, cut_components=(0,), tris=(), seat=None,
                                 anchor=types.SimpleNamespace(offset=(2.0, 0.0, 1.0)),
                                 new_resource="objects/conc__b0.obj", merged_into="")
    rec = Split(1, "dsf:obj1", "objects/conc.obj", "", 40.0, -3.0, 0.0, (body,))
    m = types.SimpleNamespace(id="dsf:obj1", resource="objects/conc.obj", tilted=(),
                              live_path=path, authored_path=path, zero_y=15.0,
                              floor_zero=True)
    counts = {"kept": 0, "one_body": 0, "split": 0, "files": 0, "write_error": 0}
    splits, kept, whole = [], [], []
    PF._cut_and_file(rec, m, True, counts, splits, kept, whole, always_write=False,
                     tilted_whole=[], landed=True)
    assert len(splits) == 1 and not kept
    (f,) = splits[0].files
    ys = [float(ln.split()[2]) for ln in f.text.splitlines() if ln.split()[:1] == ["VT"]]
    assert min(ys) == 0.0 and max(ys) == 15.0


def test_a_floor_zero_frame_is_never_a_split_level(tmp_path):
    from auto_patch_v2.airport import split_level as SL
    from auto_patch_v2.law import Law
    p = _two_floor(tmp_path)
    objs, _rep, cache = _read(tmp_path, [("dsf:obj0", p, (0.0, 0.0), 0.0, None, "OBJECT")],
                              _witness())
    sls, notes = SL.read_split_levels(objs, cache, Law.for_airport("ZZZZ"),
                                      lambda x, y: Z)
    assert not sls and any("floor_zero frame" in n for n in notes)


def test_the_airside_is_in_the_partition_key():
    from auto_patch_v2.airport import partition_cache as PC
    pv = types.SimpleNamespace(id="p1", outer=[(0, 0), (1, 0), (1, 1)], holes=[])
    a = types.SimpleNamespace(pavements=[pv])
    b = types.SimpleNamespace(pavements=[types.SimpleNamespace(
        id="p1", outer=[(0, 0), (2, 0), (1, 1)], holes=[])])
    page = types.SimpleNamespace(id="dsf:9", outer=[(0, 0), (5, 0), (1, 1)], holes=[])
    c = types.SimpleNamespace(pavements=[pv, page])
    assert PC._airside_digest(a) != PC._airside_digest(b)
    assert PC._airside_digest(a) == PC._airside_digest(c)      # a DSF page is no airside


# ── R3: the frame's lower pad ────────────────────────────────────────────

@pytest.fixture(scope="module")
def law():
    from auto_patch_v2.law import Law
    return Law.for_airport("ZZZZ")


def _seed_split(law, tmp_path, monkeypatch, conforming=(), extra=()):
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.planar import low_level as LL
    from auto_patch_v2.planar import pad_blocks
    from auto_patch_v2.planar.low_extent import AirRegion
    from auto_patch_v2.planar.overlay import Region
    from test_two_pads1214 import _airport, _wall
    monkeypatch.setattr(pad_blocks, "unit_base", lambda P, a: ("flat", "u"))
    air = box(0.0, 100.0, 200.0, 130.0)
    blk = box(0.0, 80.0, 200.0, 100.0)               # the concourse block on the apron
    conc = [_wall(10.0 + 20.0 * i, 99.5, 25.0 + 20.0 * i, 100.0, 0.0, 30) for i in range(8)]
    hall = [_wall(0.0, 0.0, 200.0, 60.0, -15.0, 300)]
    A = _airport(conc + hall + [_wall(*e) for e in extra], tmp_path)
    A.partition.units[0].members[0].floor_zero = True
    reg = Registries()
    reg.held["blk"] = {"unit": "blk"}
    regions = [Region(role="building", ref="blk", polygon=blk, code_number=None,
                      code_letter=None, side="airside", source="cell")]
    for i, g in enumerate(conforming):
        ref = f"conf{i}"
        reg.held[ref] = {"unit": ref, "conforming": True}
        regions.append(Region(role="building", ref=ref, polygon=g, code_number=None,
                              code_letter=None, side="airside", source="cell"))
    counts: dict = {}
    out = LL.low_level_split(regions, [air], A, law, 0.5, counts, reg=reg,
                             air_all=[AirRegion(air, "cell")])
    return out, reg, counts


def test_the_frame_seeds_its_lower_pad_at_the_objects_bottom(law, tmp_path, monkeypatch):
    out, reg, counts = _seed_split(law, tmp_path, monkeypatch)
    ext = {k: v for k, v in reg.landings.items() if v.get("extent_of")}
    assert len(ext) == 1
    (ref, rec), = ext.items()
    assert rec["extent_of"] == "blk" and rec["witness"] == "airside_floor"
    assert "seed" not in rec and rec["y_lo"] == pytest.approx(-15.0)
    assert rec["deck"] is None                     # every landing record carries it
    g = next(r.polygon for r in out if r.ref == ref)
    assert g.area > 0.8 * 200.0 * 60.0
    assert not any(k.endswith("#floor_seed") for k in reg.landings)


def test_a_conforming_pad_of_the_frame_in_its_lower_footprint_is_absorbed(
        law, tmp_path, monkeypatch):
    inside = box(80.0, 10.0, 120.0, 45.0)            # holds the hall's centre
    out, reg, counts = _seed_split(law, tmp_path, monkeypatch, conforming=(inside,))
    (rec,) = [v for v in reg.landings.values() if v.get("extent_of")]
    assert rec["absorbed"] == ["conf0"]
    assert "conf0" not in reg.held and not any(r.ref == "conf0" for r in out)
    ext = next(r.polygon for r in out if reg.landings.get(str(r.ref)) is rec)
    assert ext.contains(inside.buffer(-1.0))


def test_a_mezzanine_over_the_lower_floor_never_lifts_the_level(law, tmp_path, monkeypatch):
    """The frame's lower floor is its level on every piece: walls standing
    at -11 on the hall's structures (KATL Terminal F's curbs) cover more
    of a piece than the hall's own at -15 and must not lift it."""
    out, reg, _c = _seed_split(law, tmp_path, monkeypatch,
                               extra=[(20.0, 5.0, 180.0, 55.0, -11.0, 400)])
    recs = [v for v in reg.landings.values() if v.get("extent_of")]
    assert recs and all(v["y_lo"] == pytest.approx(-15.0) for v in recs)


def test_a_floor_zero_frame_mints_no_pier_fill():
    """A frame read at its airside floor stands its zero on the apron: its
    parts at the zero under its viaduct are no piers on the ground."""
    from auto_patch_v2.planar import pad_fill as PFL
    q = types.SimpleNamespace(base_y=0.0, feet=((0.5, 0.5, 0.0),) * 4, box=(0, 0, 1, 1),
                              rings=(((0.0, 0.0), (0.0, 20.0), (20.0, 20.0), (20.0, 0.0)),))
    deck = types.SimpleNamespace(origin=(0.0, 0.0), heading_deg=0.0, parts=(), floor_zero=True)
    pier = types.SimpleNamespace(origin=(0.0, 0.0), heading_deg=0.0, parts=(q,), floor_zero=True)
    part = types.SimpleNamespace(units=[types.SimpleNamespace(members=[deck, pier])])
    prn = types.SimpleNamespace(unit=0, member=0,
                                contains_many=lambda xs, ys: [True] * len(xs))
    vias = {"d": ("blk", (), (0.0, 0.0, 0.0), prn)}
    blocks = [("blk", box(100.0, 100.0, 110.0, 110.0))]
    assert PFL.pier_fills(vias, part, lambda lon, lat: (lon, lat), blocks, 0.5, 10.0) == []
    pier.floor_zero = deck.floor_zero = False
    assert len(PFL.pier_fills(vias, part, lambda lon, lat: (lon, lat), blocks, 0.5, 10.0)) == 1
