"""THE OBJ8 SPLIT WRITER AND THE ANCHOR RULE (spec
``object-placement-spec.md`` §4 / §6; owner RULINGS 2026-09-11b).

The twins are synthetic and hermetic: a hand-built OBJ8 with two boxes,
an ``ATTR_LOD`` bracket over both and an ``ANIM`` block on one box's wall
— exactly the shape §4 names — cut, written, and read back through the
engine's OWN reader (``airport/obj8.parse_obj8``), because "it parses"
means the readers downstream accept it, not that the text looks right.
"""
from __future__ import annotations

import math
import os
import sys

import pytest

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport import placement_plan as PP


# ── a synthetic OBJ8 ─────────────────────────────────────────────────────

def _box(x0: float, z0: float, side: float = 4.0, h: float = 3.0):
    """8 vertices and the 12 triangles of a closed box (the one shape a
    welded component reader must see as ONE component)."""
    v = [(x0, 0.0, z0), (x0 + side, 0.0, z0), (x0 + side, 0.0, z0 + side),
         (x0, 0.0, z0 + side), (x0, h, z0), (x0 + side, h, z0),
         (x0 + side, h, z0 + side), (x0, h, z0 + side)]
    t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _write_obj(path, verts, tri_groups, anim=None):
    """``tri_groups`` are ``(lod_line | "", [triangles])``; ``anim`` is a
    list of triangles put inside one ``ANIM_begin``/``ANIM_end`` block
    (emitted last, inside the final LOD bracket)."""
    idx: list[int] = []
    cmds: list[str] = []
    lod = None
    for lod_line, tris in tri_groups:
        if lod_line != lod:
            if lod_line:
                cmds.append(lod_line)
            lod = lod_line
        off = len(idx)
        for t in tris:
            idx.extend(t)
        cmds.append("ATTR_no_blend")
        cmds.append(f"TRIS\t{off} {len(tris) * 3}")
    if anim:
        off = len(idx)
        for t in anim:
            idx.extend(t)
        cmds.append("ANIM_begin")
        cmds.append("ANIM_trans\t0 0 0\t0 5 0\t0 1\tsim/test/door")
        cmds.append(f"TRIS\t{off} {len(anim) * 3}")
        cmds.append("ANIM_end")
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    for x, y, z in verts:
        out.append(f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.0 0.0")
    out.append("")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(x) for x in idx[i:i + 10]))
    for x in idx[len(idx) - len(idx) % 10:]:
        out.append(f"IDX\t{x}")
    out.append("")
    out.extend(cmds)
    path.write_text("\n".join(out) + "\n")
    return path


def _two_boxes(tmp_path, with_anim=True, straddle=False):
    va, ta = _box(0.0, 0.0)
    vb, tb = _box(100.0, 0.0)
    verts = va + vb
    tb = [(a + 8, b + 8, c + 8) for a, b, c in tb]
    anim = None
    if with_anim:
        # a door on box A's north wall: two triangles of A's own face
        anim = [(0, 4, 5), (0, 5, 1)]
        if straddle:
            anim = anim + [(8, 12, 13)]      # ... and one of box B's
    p = _write_obj(tmp_path / "twobox.obj", verts,
                   [("ATTR_LOD\t0 1000", ta + tb)], anim)
    return p, len(ta) + len(tb) + (len(anim) if anim else 0)


def _cuts(path, offsets=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))):
    geom = obj8.parse_obj8(str(path))
    comps = obj8.solid_components(geom)
    assert len(comps) == 2, f"expected two boxes, got {len(comps)} components"
    order = sorted(range(len(comps)), key=lambda i: comps[i].cx)
    return [OS.BodyCut(k, (order[k],), offsets[k]) for k in range(2)]


# ── §4: the cut ──────────────────────────────────────────────────────────

def test_two_bodies_two_files_lod_and_anim_whole(tmp_path):
    """§4.2/§4.3/§4.4: two files, each parses, the triangles are conserved,
    the vertices are offset exactly, the LOD bracket is replayed in both
    and the ANIM block lands WHOLE in the body that owns it."""
    p, total = _two_boxes(tmp_path)
    res = OS.split_obj8(str(p), _cuts(p, ((1.0, 2.0, 3.0), (-5.0, 0.0, 7.0))),
                        "objects/twobox.obj")
    assert res.kept_whole == "", res.kept_whole
    assert len(res.files) == 2
    assert [f.resource for f in res.files] == ["objects/twobox__b0.obj",
                                               "objects/twobox__b1.obj"]
    assert sum(f.tris for f in res.files) == total
    # body 0 is the box the ANIM door belongs to: 12 box triangles + 2 door
    a, b = res.files
    assert (a.tris, b.tris) == (14, 12)
    assert (a.anim_blocks, b.anim_blocks) == (1, 0)
    assert a.lods == ("ATTR_LOD\t0 1000",) and b.lods == ("ATTR_LOD\t0 1000",)

    for f in res.files:
        q = tmp_path / f.resource.replace("/", "_")
        q.write_text(f.text)
        g = obj8.parse_obj8(str(q))
        assert g.solid.shape[0] == f.tris, f.resource
        assert g.vertices.shape[0] == f.vertices

    # §4.3: every vertex a body uses OUTSIDE an animation is translated
    ga = obj8.parse_obj8(str(tmp_path / "objects_twobox__b0.obj"))
    xs = sorted({round(float(x), 3) for x in ga.vertices[:, 0]})
    # box A spans x 0..4 authored, minus dx = 1  ->  -1 .. 3, and the four
    # door vertices stay AUTHORED (rule 4) at 0 and 4
    assert -1.0 in xs and 3.0 in xs and 0.0 in xs and 4.0 in xs
    gb = obj8.parse_obj8(str(tmp_path / "objects_twobox__b1.obj"))
    assert round(float(gb.vertices[:, 0].min()), 3) == 105.0     # 100 - (-5)

    # rule 4: the block is whole and carries its compensating translation
    text = res.files[0].text
    assert text.count("ANIM_begin") == 1 and text.count("ANIM_end") == 1
    assert "sim/test/door" in text
    lines = [ln.split()[0] for ln in text.splitlines() if ln.strip()]
    i = lines.index("ANIM_begin")
    assert lines[i + 1] == "ANIM_trans"
    comp = text.splitlines()[[n for n, ln in enumerate(text.splitlines())
                              if ln.startswith("ANIM_begin")][0] + 1]
    assert comp.split()[1:4] == ["-1.000", "-2.000", "-3.000"]


def test_body_straddling_an_anim_block_is_kept_whole(tmp_path):
    """§4.4: an animation whose triangles belong to two bodies cannot be
    cut at block granularity without tearing one — the placement stays
    exactly as authored, reason ``anim``."""
    p, _ = _two_boxes(tmp_path, straddle=True)
    res = OS.split_obj8(str(p), _cuts(p), "objects/twobox.obj")
    assert res.kept_whole == "anim"
    assert res.files == ()


def test_one_body_is_kept_whole(tmp_path):
    """A file that already IS one body is never rewritten (§2 ``kept``)."""
    v, t = _box(0.0, 0.0)
    p = _write_obj(tmp_path / "one.obj", v, [("", t)])
    res = OS.split_obj8(str(p), [OS.BodyCut(0, (0,), (0.0, 0.0, 0.0))],
                        "objects/one.obj")
    assert res.kept_whole == "one_body"


def test_attribute_state_is_re_emitted_per_body(tmp_path):
    """§4.2 rule 1: the state in force at a body's first command is
    written into that body's file, not inherited from a stream it no
    longer shares."""
    va, ta = _box(0.0, 0.0)
    vb, tb = _box(100.0, 0.0)
    tb = [(a + 8, b + 8, c + 8) for a, b, c in tb]
    idx: list[int] = []
    cmds = ["ATTR_shiny_rat\t0.500", "ATTR_no_blend"]
    for tris in (ta, tb):
        off = len(idx)
        for t in tris:
            idx.extend(t)
        cmds.append(f"TRIS\t{off} {len(tris) * 3}")
    out = ["I", "800", "OBJ", "TEXTURE\tt.dds",
           f"POINT_COUNTS\t{len(va) + len(vb)} 0 0 {len(idx)}", ""]
    for x, y, z in va + vb:
        out.append(f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.0 0.0")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(x) for x in idx[i:i + 10]))
    for x in idx[len(idx) - len(idx) % 10:]:
        out.append(f"IDX\t{x}")
    out.extend(cmds)
    p = tmp_path / "state.obj"
    p.write_text("\n".join(out) + "\n")
    res = OS.split_obj8(str(p), _cuts(p), "objects/state.obj")
    assert res.kept_whole == ""
    for f in res.files:
        assert "ATTR_shiny_rat" in f.text and "ATTR_no_blend" in f.text


def test_point_counts_and_index_rows_are_lawful(tmp_path):
    """``POINT_COUNTS`` counts the body's OWN tables, and an ``IDX`` row
    carries exactly one index (a short ``IDX`` row with several is not
    OBJ8 and X-Plane drops the object silently)."""
    p, _ = _two_boxes(tmp_path, with_anim=False)
    res = OS.split_obj8(str(p), _cuts(p), "objects/twobox.obj")
    for f in res.files:
        pc = [ln for ln in f.text.splitlines() if ln.startswith("POINT_COUNTS")][0]
        n_vt, n_line, n_light, n_idx = (int(x) for x in pc.split()[1:5])
        assert n_vt == sum(1 for ln in f.text.splitlines() if ln.startswith("VT"))
        assert n_line == 0 and n_light == 0
        assert n_idx == f.tris * 3
        for ln in f.text.splitlines():
            if ln.startswith("IDX\t"):
                assert len(ln.split()) == 2, ln
            elif ln.startswith("IDX10"):
                assert len(ln.split()) == 11, ln
        assert "# o4 split of twobox body" in f.text


# ── §9 / 11e (2): the GENERIC anchor rule ────────────────────────────────

def _geom(parts, origin=(40.0, -3.0)):
    return AR.BodyGeometry(tuple(parts), origin[0], origin[1])


def _flat(z=100.0):
    return lambda lat, lon: z


def test_anchor_pit_object_lands_on_its_rim():
    """11e (2): a pit authored with its RIM at y = 0 and its floor 7 m
    down, over a basin cut 7 m down, reads ONE zero plane from both rings
    — and the vertex whose ground IS that plane is the rim."""
    grade, floor = 600.0, 593.0

    def surface(lat, lon):
        return grade if lat < 40.00005 else floor

    g = _geom([(40.0000, -3.0, 0.0, ((40.0000, -3.0, 0.0),)),
               (40.0001, -3.0, -7.0, ((40.0001, -3.0, -7.0),))])
    a = AR.anchor_for(AR.BASIN, g, surface, tol_m=0.3)
    assert a.reason == "surface at the body's zero"
    assert a.lat == pytest.approx(40.0000) and a.y_zero == pytest.approx(0.0)
    assert a.surface_z == grade


def test_anchor_tunnel_object_lands_on_its_floor_ring():
    """11e (2): a tunnel whose ZERO is its road level — the floor ring at
    y = 0 over the cut floor, its wall crests 5 m up at grade — anchors on
    the FLOOR ring, by the same rule and with no class of its own."""
    floor, grade = 588.0, 593.0

    def surface(lat, lon):
        return floor if lat < 40.00005 else grade

    g = _geom([(40.0000, -3.0, 0.0, ((40.0000, -3.0, 0.0),)),
               (40.0001, -3.0, 5.0, ((40.0001, -3.0, 5.0),))])
    a = AR.anchor_for(AR.OTHER, g, surface, tol_m=0.3)
    assert a.y_zero == pytest.approx(0.0)
    assert a.lat == pytest.approx(40.0000) and a.surface_z == floor


def test_anchor_with_no_point_at_its_zero_takes_the_low_side_foot():
    """11e (2): authored relief beyond the body's skirt — every foot reads
    a different zero plane, so none of them IS the body's; the anchor is
    the low-side foot and the reason carries the residual."""
    def surface(lat, lon):
        return 100.0 + (lat - 40.0) * 111_132.0      # 1 m per 9 µdeg

    g = _geom([(40.00000, -3.0, 0.0, ((40.00000, -3.0, 0.0),)),
               (40.00005, -3.0, 0.0, ((40.00005, -3.0, 0.0),)),
               (40.00010, -3.0, 0.0, ((40.00010, -3.0, 0.0),))])
    a = AR.anchor_for(AR.SKIRTED, g, surface, tol_m=0.3)
    assert a.reason.startswith("low-side foot (no point within 0.3 m")
    assert "authored relief 5.56 m" in a.reason
    assert a.lat == pytest.approx(40.00000)          # the LOW side
    assert a.surface_z == pytest.approx(100.0)


def test_anchor_off_surface_is_reported_never_guessed():
    g = _geom([(40.0, -3.0, 4.0, ()), (40.002, -3.0, 1.0, ())])
    a = AR.anchor_for(AR.OTHER, g, lambda la, lo: None, tol_m=0.3)
    assert a.surface_z is None
    assert a.reason == "no design surface under any foot: the lowest component"
    assert a.lat == pytest.approx(40.002) and a.y_zero == pytest.approx(1.0)


def test_anchor_deck_is_merged_into_the_building_it_abuts():
    """11a survives §9: an elevated deck takes no anchor of its own."""
    g = _geom([(40.0, -3.0, 5.0, ((40.0, -3.0, 5.0),))])
    a = AR.anchor_for(AR.DECK, g, _flat(), merged_into="objects/T4.obj")
    assert a.body_class == AR.DECK
    assert a.reason == "kerb (merged into objects/T4.obj)"


# ── §9 / 11e (1): BODY COARSENING ────────────────────────────────────────

def _body(i, z, y, n_feet=1, cls=AR.OTHER, lat=40.0, lon=-3.0):
    return (i, AR.Anchor(cls, lat, lon, y, "surface at the body's zero", z), n_feet)


def test_two_bodies_on_the_same_ground_become_one_file():
    """11e (1): their zero planes agree within the tolerance, so the split
    does not exist — one file, the SENIOR body's anchor."""
    g = PP.coarsen([_body(0, 100.0, 0.0, 3), _body(1, 100.2, 0.2, 9)], 0.3)
    assert g == [[0, 1]]
    # senior = the most ground-contact vertices (body 1 here)
    assert max(g[0], key=lambda i: (3, 9)[i]) == 1


def test_two_bodies_one_metre_apart_stay_two_files():
    """... and where the terrain DOES differ under the object, the split
    is exactly what is kept."""
    assert PP.coarsen([_body(0, 100.0, 0.0, 3), _body(1, 101.0, 0.0, 9)], 0.3) \
        == [[0], [1]]


def test_coarsening_is_senior_first_never_a_chain():
    """Three bodies 0.25 m apart must not chain into one group spanning
    0.5 m: every member agrees with the anchor the group TAKES."""
    bodies = [_body(0, 100.0, 0.0, 1), _body(1, 100.25, 0.0, 9),
              _body(2, 100.5, 0.0, 1)]
    groups = PP.coarsen(bodies, 0.3)
    assert groups == [[0, 1, 2]]        # all three agree with the senior (1)
    bodies[1] = _body(1, 100.0, 0.0, 9)
    assert PP.coarsen(bodies, 0.3) == [[0, 1], [2]]


def test_an_elevated_body_never_founds_a_group_of_its_own():
    """11e (1) with the seat law's elevated rule: a mezzanine body has no
    terrain under it to differ — it joins the nearest ground group."""
    bodies = [_body(0, 100.0, 0.0, 5, lat=40.0), _body(1, 130.0, 0.0, 1, lat=40.01),
              _body(2, 105.0, 0.0, 5, lat=40.02)]
    assert PP.coarsen(bodies, 0.3, frozenset({1})) == [[0, 1], [2]]
    # ... and with no ground body at all they coarsen among themselves
    assert PP.coarsen(bodies, 0.3, frozenset({0, 1, 2})) == [[0], [1], [2]]


def test_off_surface_bodies_are_one_group():
    bodies = [_body(0, None, 0.0, 2), _body(1, None, 0.0, 1),
              _body(2, 100.0, 0.0, 3)]
    assert PP.coarsen(bodies, 0.3) == [[0, 1], [2]]


def test_classify_orders_structure_over_shape():
    assert AR.classify_body(skirted=True, basin_member=True, line=True, deck=True,
                            plate=True, has_pad=True) == AR.BASIN
    assert AR.classify_body(skirted=True, basin_member=False, line=True, deck=True,
                            plate=True, has_pad=True) == AR.DECK
    assert AR.classify_body(skirted=True, basin_member=False, line=True, deck=False,
                            plate=False, has_pad=True) == AR.LINE_SEGMENT
    assert AR.classify_body(skirted=True, basin_member=False, line=False, deck=False,
                            plate=False, has_pad=True) == AR.SKIRTED
    assert AR.classify_body(skirted=False, basin_member=False, line=False, deck=False,
                            plate=False, has_pad=True) == AR.BUILDING
    assert AR.classify_body(skirted=False, basin_member=False, line=False, deck=False,
                            plate=False, has_pad=False) == AR.OTHER


# ── the authored frame ───────────────────────────────────────────────────

@pytest.mark.parametrize("heading", [0.0, 37.5, 90.0, 180.0, 269.2])
def test_authored_offset_inverts_the_placement_affine(heading):
    """§4.3's offset must be the placement map INVERTED — if it is not,
    every split body lands rotated off its own anchor."""
    lat0, lon0 = 40.4622735, -3.5552834
    x, z = 137.0, -42.0
    ml, mo = AR._m_per_deg(lat0)
    h = math.radians(heading)
    east = x * math.cos(h) - z * math.sin(h)
    north = -(x * math.sin(h) + z * math.cos(h))
    lat, lon = lat0 + north / ml, lon0 + east / mo
    dx, dy, dz = PP.authored_offset(lat, lon, 1.5, lat0, lon0, heading)
    assert dx == pytest.approx(x, abs=1e-3)
    assert dz == pytest.approx(z, abs=1e-3)
    assert dy == 1.5


# ── the join with §2's model (lane v2dsfagl) ─────────────────────────────

def test_split_records_translate_into_the_placement_model():
    """§2 is the interface the two lanes meet at: this lane's bodies must
    land in ``model/placement.py``'s own records, anchor and offset
    intact, with no second copy of either model."""
    from auto_patch_v2.model import placement as PM
    a = AR.Anchor(AR.BUILDING, 40.5, -3.5, 1.25, "pad point (building16)",
                  601.0, (12.0, 1.25, -8.0))
    body = PP.Body(0, AR.BUILDING, (3, 4), a, "objects/x__b0.obj")
    s = PP.Split(2950, "dsf:obj2950", "objects/x.obj", "/tmp/x.obj",
                 40.4, -3.4, 269.2, (body,))
    ss = PP.SplitSet((s,), (PP.Kept(7, "dsf:obj7", "objects/y.obj", "anim"),), {})
    splits, kept = PP.to_placement_records(ss)
    assert isinstance(splits[0], PM.Split) and isinstance(kept[0], PM.Kept)
    assert splits[0].placement.index == 2950
    b = splits[0].bodies[0]
    assert (b.anchor.lat, b.anchor.lon) == (40.5, -3.5)
    assert b.anchor.heading_deg == 269.2
    assert b.authored_offset == (12.0, 1.25, -8.0)
    assert b.anchor_reason == "pad point (building16)"
    assert kept[0].reason == "anim"


# ── §9 / 11e (3): THE GATE AND THE WRITE HALF ────────────────────────────

def test_the_gate_defaults_to_agl_and_seat_runs_the_old_path_unchanged():
    """``[rebake] placement`` is the ONE permitted gate: ``agl`` by
    default, and under ``seat`` the pre-11b seat is not merely reachable —
    it produces the SAME bytes, because nothing in the seat reads the new
    law at all."""
    import dataclasses as dc
    import json as _json

    from auto_patch.engine_v2 import object_stage_is_placement
    from auto_patch_v2.emit import rebake as R
    from auto_patch_v2.law import Law

    law = Law.for_airport("OTHH")
    assert law.tables.structures.rebake.placement == "agl"
    assert object_stage_is_placement(law) is True

    def _with(mode):
        rb = dc.replace(law.tables.structures.rebake, placement=mode)
        st = dc.replace(law.tables.structures, rebake=rb)
        return dc.replace(law, tables=dc.replace(law.tables, structures=st))

    seat_law = _with("seat")
    assert object_stage_is_placement(seat_law) is False
    assert object_stage_is_placement(_with("agl")) is True

    part = R.Part(1, 0, 0.001, 1e-5, 0.0, 100.0, (0.0, 0.0, 2e-3, 2e-5))
    member = R.Member("m", "objects/m.obj", "m", "m", 0.0, (part,))
    plan = R.RebakePlan("OTHH", "p", "/p", (R.Unit("unit:1", (0.0, 0.0), 0.0,
                                                   (member,)),), (), {}, ())

    def sample(lat, lon):
        return (7.0, False)

    a = _json.dumps(R.seat(plan, sample, seat_law).to_dict(), sort_keys=True)
    b = _json.dumps(R.seat(plan, sample, _with("agl")).to_dict(), sort_keys=True)
    assert a == b


def test_the_write_half_on_a_pack_copy(tmp_path):
    """11e (3): the cut files, the DSF, its backup, the provenance and the
    plan — and the WRITTEN DSF dumped back must list every new placement
    on its own new ``OBJECT_DEF``, with no row left carrying an elevation.
    A hand-built dump stands in for DSFTool (the encoder is v2dsfagl's own
    twin); what is tested here is the ORDER and the products."""
    from auto_patch_v2.airport import dsf as D
    from auto_patch_v2.airport import placement_write as PW
    from auto_patch_v2.model import placement as PM

    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    nav = pack / "Earth nav data"
    nav.mkdir()
    dsf = nav / "+40-004.dsf"
    dump = ["PROPERTY sim/west -4", "OBJECT_DEF objects/a.obj",
            "OBJECT_DEF objects/b.obj",
            "OBJECT_MSL 0 -3.5 40.5 601.0 12.5",
            "OBJECT 1 -3.6 40.6 90.0"]
    dsf.write_text("\n".join(dump) + "\n")

    # a DSFTool stand-in: --dsf2text copies the text, --text2dsf copies back
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import shutil, sys\n"
        "shutil.copyfile(sys.argv[2], sys.argv[3])\n")

    real_run = PW._dw.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    PW._dw.subprocess.run = fake_run
    try:
        split = PM.Split(
            placement=PM.PlacementRef(1, "objects/b.obj", -3.6, 40.6, 90.0),
            bodies=(PM.Body("b0", "other", (0,), PM.Anchor(-3.61, 40.61, 90.0),
                            "surface at the body's zero", "objects/b__b0.obj"),
                    PM.Body("b1", "other", (1,), PM.Anchor(-3.62, 40.62, 90.0),
                            "surface at the body's zero", "objects/b__b1.obj")))
        plan = PM.PlacementPlan(
            icao="LEMD", pack_name="pack", pack_root=str(pack), dsf_path=str(dsf),
            dsf_backup_path=str(dsf) + ".anchor_bak",
            provenance=PM.Provenance("", "", ""),
            conversions=(PM.Conversion(0, "objects/a.obj", -3.5, 40.5, 12.5,
                                       "OBJECT_MSL", 601.0),),
            splits=(split,), kept=())

        class _F:
            def __init__(self, res):
                self.resource = res
                self.text = f"I\n800\nOBJ\n{PW.CUT_MARK}b body 0 offset 0 0 0\n"

        files = [_F("objects/b__b0.obj"), _F("objects/b__b1.obj")]
        seen: list[str] = []
        res = PW.apply_plan(plan, files, str(tool), patch_dir=str(tmp_path / "patch"),
                            refresh_dump=lambda p: seen.append(p) or p)
    finally:
        PW._dw.subprocess.run = real_run

    assert len(res.files_written) == 2
    assert all(os.path.isfile(p) for p in res.files_written)
    assert os.path.isfile(str(dsf) + ".anchor_bak") and res.dsf.backup_created
    assert res.dsf.report.ok, res.dsf.report.findings
    assert seen == [str(dsf)]                       # §3.6: the cache refresh
    assert os.path.basename(res.plan_path) == "o4_v2_placement_LEMD.json"
    assert os.path.isfile(os.path.join(str(nav), PM.PROVENANCE_FILENAME))

    back = D.read_dump(str(dsf))
    assert [p.kind for p in back.placements] == ["OBJECT"] * 3
    got = {p.def_path for p in back.placements}
    assert {"objects/b__b0.obj", "objects/b__b1.obj", "objects/a.obj"} <= got


def test_the_write_half_refuses_to_overwrite_an_authored_object(tmp_path):
    """§4.5: the split names are NEW names only."""
    from auto_patch_v2.airport import placement_write as PW

    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    (pack / "objects" / "a.obj").write_text("I\n800\nOBJ\n")

    class _F:
        resource = "objects/a.obj"
        text = "cut"

    with pytest.raises(ValueError, match="authored object"):
        PW.write_files(str(pack), [_F()])


# ── 11f (1): THE RESTORE BEFORE THE WRITE ────────────────────────────────

def test_restore_puts_every_anchor_bak_back_and_counts_it(tmp_path):
    """11f (1): the pack's baked objects are the PRISTINE bytes again
    before a single file is written, the backups are KEPT (the split
    reads them), and only what actually differed is rewritten."""
    from auto_patch_v2.airport import placement_write as PW

    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    baked = pack / "objects" / "a.obj"
    baked.write_text("I\n800\nOBJ\nVT\t0 -7.5 0\t0 1 0\t0 0\n")      # v1's bake
    (pack / "objects" / "a.obj.anchor_bak").write_text(
        "I\n800\nOBJ\nVT\t0 0.0 0\t0 1 0\t0 0\n")                    # authored
    (pack / "objects" / "b.obj").write_text("I\n800\nOBJ\n")         # never baked
    # the DSF's own backup is §3's, not this pass's
    (pack / "Earth nav data").mkdir()
    (pack / "Earth nav data" / "t.dsf").write_text("new")
    (pack / "Earth nav data" / "t.dsf.anchor_bak").write_text("old")

    r = PW.restore_pack_objects(str(pack))
    assert r.counts == {"restore_backups": 1, "restore_restored": 1}
    assert baked.read_text() == "I\n800\nOBJ\nVT\t0 0.0 0\t0 1 0\t0 0\n"
    assert (pack / "objects" / "a.obj.anchor_bak").is_file()
    assert (pack / "Earth nav data" / "t.dsf").read_text() == "new"

    again = PW.restore_pack_objects(str(pack))          # idempotent
    assert again.counts == {"restore_backups": 1, "restore_restored": 0}


def test_restore_on_a_pack_with_no_backup_restores_nothing(tmp_path):
    """11f (1): idempotent at the other end — a pack v1 never baked."""
    from auto_patch_v2.airport import placement_write as PW

    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    (pack / "objects" / "a.obj").write_text("I\n800\nOBJ\n")
    r = PW.restore_pack_objects(str(pack))
    assert r.counts == {"restore_backups": 0, "restore_restored": 0}
    assert (pack / "objects" / "a.obj").read_text() == "I\n800\nOBJ\n"


# ── 11f (2): THE SEGMENT CUT of a one-component line object ──────────────

def _fence(tmp_path, length_m: float, name: str = "fence.obj", step: float = 5.0,
           h: float = 2.0):
    """A fence as ONE component: a continuous vertical strip along +x,
    every panel sharing its neighbour's posts (so the welded reader sees
    one component) — the LEMDzaun shape, at any length."""
    n = int(length_m / step) + 1
    verts = []
    for i in range(n):
        verts.append((i * step, 0.0, 0.0))
        verts.append((i * step, h, 0.0))
    tris = []
    for i in range(n - 1):
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        tris.append((a, b, d))
        tris.append((a, d, c))
    return _write_obj(tmp_path / name, verts, [("", tris)]), n


def _fence_plan(path, length_m, icao="TEST", heading=0.0, lat=40.0, lon=-3.0):
    """A one-member, one-part rebake plan over ``path``."""
    from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

    ml, mo = AR._m_per_deg(lat)
    part = Part(pid=0, comp=0, lat=lat, lon=lon + 0.5 * length_m / mo, base_y=0.0,
                area_m2=length_m * 2.0,
                box=(lat, lon, lat, lon + length_m / mo),
                feet=((lat, lon, 0.0),))
    m = Member(id="dsf:obj1", resource="objects/" + os.path.basename(str(path)),
               authored_path=str(path), live_path=str(path), heading_deg=heading,
               parts=(part,))
    return RebakePlan(icao=icao, pack_name="pack", pack_root=os.path.dirname(str(path)),
                      units=(Unit("u0", (lat, lon), 0.0, (m,)),), skipped=(), counts={})


def _line_args(seg_m=100.0):
    return dict(split_tol_m=0.0, line_segment_m=seg_m, line_stations_max=64,
                line_ratio=20.0, line_max_h=6.0, foot_band_m=1.0)


def test_a_one_component_fence_is_cut_into_segments_anchored_at_their_mid_feet(tmp_path):
    """11f (2): the perimeter-fence class.  One component, one body, one
    anchor before — now one body per station, each anchored on a foot of
    ITS OWN segment, near the segment's middle, and every triangle of the
    fence lands in exactly one file."""
    path, _n = _fence(tmp_path, 400.0)
    plan = _fence_plan(path, 400.0)
    ss = PP.build_splits(plan, lambda la, lo: 100.0, write=True, **_line_args())

    assert len(ss.splits) == 1, ss.counts
    s = ss.splits[0]
    assert ss.counts["line_bodies_segmented"] == 1
    assert ss.counts["line_segments"] == 4          # 400 m / 100 m stations
    assert len(s.bodies) == 4 and len(s.files) == 4
    assert {b.body_class for b in s.bodies} == {AR.LINE_SEGMENT}
    for b in s.bodies:
        assert "mid-foot" in b.anchor.reason
        # the anchor is a foot OF THIS SEGMENT, and no further from the
        # segment's own feet than half a segment
        lons = [f[1] for f in b.feet]
        assert min(lons) <= b.anchor.lon <= max(lons)
        assert (b.anchor.lat, b.anchor.lon) in [(f[0], f[1]) for f in b.feet]
    # the segments partition the fence: every triangle exactly once
    assert sum(f.tris for f in s.files) == 2 * (int(400.0 / 5.0))
    # each cut file parses back with the triangles it claims
    for f in s.files:
        p = tmp_path / os.path.basename(f.resource)
        p.write_text(f.text)
        g = obj8.parse_obj8(str(p))
        assert g.solid.shape[0] + g.draped.shape[0] == f.tris


def test_a_short_one_component_wall_is_one_body(tmp_path):
    """11f (2) the other way: a 30 m wall is shorter than one station —
    no segment cut, and the placement stays whole exactly as before."""
    path, _n = _fence(tmp_path, 30.0, name="wall.obj")
    plan = _fence_plan(path, 30.0)
    ss = PP.build_splits(plan, lambda la, lo: 100.0, write=True, **_line_args())
    assert not ss.splits and len(ss.kept) == 1
    assert ss.kept[0].reason == "one_body"
    assert "line_segments" not in ss.counts


def test_segments_of_one_component_are_cut_by_triangle_not_by_component(tmp_path):
    """The cutter's body definition (11f (2)): two segments of the SAME
    component share the vertices of the panel they meet at, and a vertex
    VOTE cannot separate them — the triangle map is senior."""
    path, _n = _fence(tmp_path, 200.0, name="two.obj")
    geom = obj8.parse_obj8(str(path))
    comps = obj8.solid_components(geom)
    assert len(comps) == 1
    tris = comps[0].tris
    left = [tuple(int(q) for q in t) for t in tris.tolist()
            if geom.vertices[t].mean(axis=0)[0] < 100.0]
    right = [tuple(int(q) for q in t) for t in tris.tolist()
             if geom.vertices[t].mean(axis=0)[0] >= 100.0]
    res = OS.split_obj8(str(path), [OS.BodyCut(0, (), (0.0, 0.0, 0.0), tuple(left)),
                                    OS.BodyCut(1, (), (100.0, 0.0, 0.0), tuple(right))])
    assert not res.kept_whole and len(res.files) == 2
    assert [f.tris for f in res.files] == [len(left), len(right)]
    assert res.counts["segment"] == len(tris)
