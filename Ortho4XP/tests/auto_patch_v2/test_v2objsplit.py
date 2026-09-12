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
from auto_patch_v2.airport import placement_carrier as _PC
from auto_patch_v2.airport import placement_cut as _CUT
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
    # ... and with NO ground body at all there is no carrier and no
    # ground: ONE group, never one file each (§13 (1)).  This line used
    # to read ``[[0], [1], [2]]`` — every roof its own file, 226 of
    # LEMD's 274 such files and the owner's 11r read.
    assert PP.coarsen(bodies, 0.3, frozenset({0, 1, 2})) == [[0, 1, 2]]


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


def test_the_write_half_on_a_pack_copy(tmp_path, monkeypatch):
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
    tool = _stand_in_dsftool(tmp_path, PW._dw, monkeypatch)
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
    assert r.counts == {"restore_backups": 1, "restore_restored": 1,
                        "restore_bodies_removed": 0}
    assert baked.read_text() == "I\n800\nOBJ\nVT\t0 0.0 0\t0 1 0\t0 0\n"
    assert (pack / "objects" / "a.obj.anchor_bak").is_file()
    assert (pack / "Earth nav data" / "t.dsf").read_text() == "new"

    again = PW.restore_pack_objects(str(pack))          # idempotent
    assert again.counts == {"restore_backups": 1, "restore_restored": 0,
                            "restore_bodies_removed": 0}


def test_restore_on_a_pack_with_no_backup_restores_nothing(tmp_path):
    """11f (1): idempotent at the other end — a pack v1 never baked."""
    from auto_patch_v2.airport import placement_write as PW

    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    (pack / "objects" / "a.obj").write_text("I\n800\nOBJ\n")
    r = PW.restore_pack_objects(str(pack))
    assert r.counts == {"restore_backups": 0, "restore_restored": 0,
                        "restore_bodies_removed": 0}
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


# ── lane v2planfix: THE SHIPPED PATH'S pads AND rims ─────────────────────
#
# ``engine_v2._place_objects`` called ``build_plan`` with neither ``pads``
# nor ``rims``, so in a SHIPPED build ``classify_body`` could never answer
# ``building`` or ``basin`` — only ``tools/obj8_split_report.py`` supplied
# them.  Both now read ONE derivation,
# ``placement_plan.pads_rims_from_graded``.

_PAD_RING = ((40.0010, -3.6010), (40.0010, -3.6000),
             (40.0020, -3.6000), (40.0020, -3.6010))
_RIM_RING = ((40.0040, -3.6030), (40.0040, -3.6020),
             (40.0050, -3.6020), (40.0050, -3.6030))
#: a point inside each
_IN_PAD = (40.0015, -3.6005)
_IN_RIM = (40.0045, -3.6025)


def _graded_doc():
    """A minimal ``<ICAO>.graded.json`` document carrying one ``building``
    face and one ``structure_rim`` breakline — plus one face and one
    breakline of other kinds, which must NOT be read as either."""
    ring = list(_PAD_RING) + list(_RIM_RING) + [(40.0, -3.61), (40.0, -3.60),
                                                (40.001, -3.60)]
    verts = [[i, la, lo, 100.0] for i, (la, lo) in enumerate(ring)]
    return {
        "schema": "o4.graded_surface/1", "icao": "TEST", "ruleset": "icao",
        "frame": {"origin": [40.0, -3.6], "crs": "ll", "identity_dp": 11},
        "vertices": verts,
        "faces": [{"id": 0, "role": "building", "ref": "building16",
                   "ring": [0, 1, 2, 3], "holes": []},
                  {"id": 1, "role": "apron", "ref": "apron1",
                   "ring": [8, 9, 10], "holes": []}],
        "breaklines": [{"kind": "structure_rim", "ref": "rim7",
                        "vertices": [4, 5, 6, 7]},
                       {"kind": "terrain_edge", "ref": "edge2",
                        "vertices": [8, 9, 10]}],
    }


def test_pads_and_rims_are_derived_once_for_the_engine_and_the_tool(tmp_path):
    """ONE derivation site: the dry-run tool's ``surface_from_graded`` and
    the engine's own reader return IDENTICAL pads and rims from one file
    — and only the ``building`` faces and ``structure_rim`` breaklines."""
    import json as _json

    p = tmp_path / "TEST.graded.json"
    p.write_text(_json.dumps(_graded_doc()))

    pads, rims = PP.pads_rims_from_graded(str(p))
    assert [q.ref for q in pads] == ["building16"]
    assert [q.ref for q in rims] == ["rim7"]
    assert pads[0].ring == _PAD_RING and rims[0].ring == _RIM_RING

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as RPT
    _s, tool_pads, tool_rims = RPT.surface_from_graded(str(p))
    assert tool_pads == pads and tool_rims == rims


def _plan_with_a_building_and_a_basin(tmp_path, icao="TEST"):
    """A pack and a one-unit rebake plan with two placements: one standing
    inside the emitted object PAD at its authored zero (a ``building``),
    one standing inside the emitted structure RIM below its zero (a
    ``basin``).  Nothing here depends on the OBJ8 bytes — the measure-only
    path never cuts a file."""
    from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    nav = pack / "Earth nav data" / "+40-010"
    nav.mkdir(parents=True)
    dsf = nav / "+40-004.dsf"
    dsf.write_text("\n".join([
        "PROPERTY sim/west -4", "OBJECT_DEF objects/bld.obj",
        "OBJECT_DEF objects/pit.obj",
        "OBJECT 0 -3.6005 40.0015 0.0",
        "OBJECT 1 -3.6025 40.0045 0.0"]) + "\n")

    def _member(idx, name, ll, base_y):
        path = pack / "objects" / name
        path.write_text("I\n800\nOBJ\n")
        part = Part(pid=idx, comp=0, lat=ll[0], lon=ll[1], base_y=base_y,
                    area_m2=40.0,
                    box=(ll[0] - 1e-5, ll[1] - 1e-5, ll[0] + 1e-5, ll[1] + 1e-5),
                    feet=((ll[0], ll[1], base_y),))
        return Member(id=f"dsf:obj{idx}", resource="objects/" + name,
                      authored_path=str(path), live_path=str(path),
                      heading_deg=0.0, parts=(part,))

    plan = RebakePlan(
        icao=icao, pack_name="pack", pack_root=str(pack),
        units=(Unit("u0", _IN_PAD, 0.0,
                    (_member(0, "bld.obj", _IN_PAD, 0.0),
                     _member(1, "pit.obj", _IN_RIM, -4.0))),),
        skipped=(), counts={})
    return pack, dsf, plan


def _place(plan, patch_dir, monkeypatch, dsf):
    """Drive ``engine_v2._place_objects`` — the SHIPPED call path — in its
    measure-only arm (no cut, no DSF write, no DSFTool)."""
    from auto_patch import dsf_reader as DSFR
    from auto_patch import engine_v2 as EV2
    from auto_patch_v2.law import Law

    monkeypatch.setattr(DSFR, "ensure_dsf_text_path",
                        lambda src, cache: str(dsf), raising=False)

    class _Tile:
        lat, lon = 40, -4

    return EV2._place_objects(plan, Law.for_airport("TEST"),
                              lambda la, lo: (100.0, False), _Tile(),
                              str(patch_dir), write_enabled=False,
                              measure_only=True)


def test_the_shipped_path_classifies_building_and_basin(tmp_path, monkeypatch):
    """THE DEFECT AND ITS FIX, interventionally: the SAME engine call
    path, run with and without the design surface beside the patch.  With
    it, the two bodies read ``building`` and ``basin``; without it both
    fall through to ``other`` — which is what every shipped build did."""
    import json as _json

    from auto_patch import engine_v2 as EV2

    pack, dsf, plan = _plan_with_a_building_and_a_basin(tmp_path)
    patch_dir = tmp_path / "patch"
    patch_dir.mkdir()

    # ARM A — no <ICAO>.graded.json beside the patch (the shipped state)
    a = _place(plan, patch_dir, monkeypatch, dsf)
    assert a.get("class_other") == 2, a
    assert "class_building" not in a and "class_basin" not in a, a

    # ARM B — the design surface placed beside the patch, as the build now
    # places it (``_place_graded_surface``)
    (patch_dir / "TEST.graded.json").write_text(_json.dumps(_graded_doc()))
    b = _place(plan, patch_dir, monkeypatch, dsf)
    assert b.get("class_building") == 1, b
    assert b.get("class_basin") == 1, b
    assert "class_other" not in b, b

    # and the path the two halves agree on is one function
    assert EV2.graded_surface_path(str(patch_dir), "TEST") == \
        str(patch_dir / "TEST.graded.json")


def test_the_build_places_the_graded_surface_beside_the_patch(tmp_path):
    """``_place_graded_surface`` is the piece that makes the engine's read
    possible at all: the whole-airport surface the pipeline wrote into its
    scratch dir, copied to ``<patch dir>/<ICAO>.graded.json``."""
    from auto_patch import engine_v2 as EV2

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    src = scratch / "TEST.graded.json"
    src.write_text('{"vertices":[],"faces":[],"breaklines":[]}')

    class _Paths:
        graded = src

    patch_dir = tmp_path / "Patches" / "+40-004"
    patch_dir.mkdir(parents=True)
    task = {"auto_patch_file": str(patch_dir / "TEST_auto.patch.osm")}
    dest = EV2._place_graded_surface(task, _Paths(), "TEST")
    assert dest == str(patch_dir / "TEST.graded.json")
    assert os.path.isfile(dest)
    assert PP.pads_rims_from_graded(dest) == ((), ())
    # a pipeline that wrote none is not a failure
    assert EV2._place_graded_surface(task, None, "TEST") is None


def test_pad_hit_is_one_implementation(tmp_path):
    """Lane v2planfix (b): ``planar/structures`` and
    ``planar/wall_corridor_ramps`` carried byte-equal private copies of
    the pad probe.  One function, upstream of both."""
    from auto_patch_v2.planar import structure_geometry as G
    from auto_patch_v2.planar import structures as S
    from auto_patch_v2.planar import wall_corridor_ramps as W

    assert S._pad_hit is G.pad_hit
    assert W._pad_hit is G.pad_hit

    from shapely.geometry import Polygon
    from shapely.strtree import STRtree

    pads = [(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), "building1")]
    tree = STRtree([p for p, _r in pads])
    probe = Polygon([(11, 0), (12, 0), (12, 1), (11, 1)])
    assert G.pad_hit(probe, pads, tree, 2.0) == "building1"
    assert G.pad_hit(probe, pads, tree, 0.5) is None
    assert G.pad_hit(probe, pads, tree, 2.0, exclude=("building1",)) is None
    assert G.pad_hit(probe, pads, None, 2.0) is None


# ── 11m: the object stage is IDEMPOTENT over a written pack ──────────────
# app 1.0.313 wrote LEMD's DSF (3,021 -> 3,934 placements); the next build's
# plan read re-derived from the WRITTEN file and named ``dsf:obj3021`` ...
# ``dsf:obj3933``, which the write half — dumping the pristine backup —
# refused.  The read frame is the pristine DSF and the dump cache is keyed
# on its CONTENT.

def _stand_in_dsftool(tmp_path, module, monkeypatch):
    """``--dsf2text`` / ``--text2dsf`` as a byte copy (the encoder has its
    own twin in ``test_v2dsfagl``); returns the tool path.

    THE ISOLATION IS ``monkeypatch``'S (lane v2canopy5, owner RULINGS
    2026-09-11p (3)).  ``module.subprocess`` IS the stdlib module, so the
    patch is session-wide, and the old helper handed back a restore that
    both callers discarded — each captured its own ``real_run`` AFTER the
    patch was already in place, so its ``finally`` restored the PREVIOUS
    test's fake and the next run shelled out to a deleted tmpdir's
    stand-in.  That is the whole of the order-dependent red; ``monkeypatch``
    undoes the attribute after every test, in any order, at ``-n0``.
    """
    tool = tmp_path / "dsftool.py"
    tool.write_text("import shutil, sys\n"
                    "shutil.copyfile(sys.argv[2], sys.argv[3])\n")
    real_run = module.subprocess.run

    def fake_run(args, **kw):
        return real_run([sys.executable, str(tool)] + list(args[1:]), **kw)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return str(tool)


def _one_pack(tmp_path):
    """A pack with two placements — one MSL to convert, one to split."""
    from auto_patch_v2.model import placement as PM
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    nav = pack / "Earth nav data"
    nav.mkdir()
    dsf = nav / "+40-004.dsf"
    dsf.write_text("\n".join(
        ["PROPERTY sim/west -4", "OBJECT_DEF objects/a.obj",
         "OBJECT_DEF objects/b.obj",
         "OBJECT_MSL 0 -3.5 40.5 601.0 12.5",
         "OBJECT 1 -3.6 40.6 90.0"]) + "\n")
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
    return pack, dsf, plan


def test_pristine_dsf_path_is_the_backup_when_there_is_one(tmp_path):
    """(a) the ONE resolver: backup present -> the backup; absent -> the
    live file; a backup path resolves to itself (never doubled)."""
    from auto_patch_v2.airport import dsf_write as DW

    dsf = tmp_path / "+40-004.dsf"
    dsf.write_text("written")
    assert DW.pristine_dsf_path(str(dsf)) == str(dsf)
    bak = tmp_path / "+40-004.dsf.anchor_bak"
    bak.write_text("authored")
    assert DW.pristine_dsf_path(str(dsf)) == str(bak)
    assert DW.pristine_dsf_path(str(bak)) == str(bak)
    assert DW.pristine_dsf_path("") == ""


def test_dump_cache_is_keyed_by_content_not_by_path(tmp_path):
    """(b) two same-named DSFs with different content get different cache
    files, and a REWRITTEN live DSF whose backup is unchanged still hits
    the SAME entry — the 11m defect was a cache name that did not move
    when the file under it did."""
    from auto_patch import dsf_reader as DR
    from auto_patch_v2.airport import dsf as D
    from auto_patch_v2.airport import dsf_write as DW

    cache = str(tmp_path / "cache")
    one = tmp_path / "one" / "+40-004.dsf"
    two = tmp_path / "two" / "+40-004.dsf"
    for p, body in ((one, b"AAAA"), (two, b"BBBB")):
        p.parent.mkdir(parents=True)
        p.write_bytes(body)
    n1 = DR._default_pack_text_cache_path(cache, str(one))
    n2 = DR._default_pack_text_cache_path(cache, str(two))
    assert n1 != n2 and os.path.basename(n1) != "+40-004.dsf.text"
    # the same bytes at a different path ARE the same dump
    three = tmp_path / "three" / "+40-004.dsf"
    three.parent.mkdir(parents=True)
    three.write_bytes(b"AAAA")
    assert os.path.basename(DR._default_pack_text_cache_path(
        cache, str(three))) == os.path.basename(n1)
    # the v2 twin of the tag (``airport/dsf.text_dump_tag``) agrees
    assert os.path.basename(n1) == f"+40-004.dsf.{D.text_dump_tag(str(one))}.text"

    # the write case: the live file changes, the backup does not
    before = DR._default_pack_text_cache_path(
        cache, DW.pristine_dsf_path(str(one)))
    (tmp_path / "one" / "+40-004.dsf.anchor_bak").write_bytes(b"AAAA")
    one.write_bytes(b"AAAA plus 913 new placements")
    after = DR._default_pack_text_cache_path(
        cache, DW.pristine_dsf_path(str(one)))
    # SAME entry in the only sense that matters: the same CONTENT tag, so
    # the dump the plan reads is the dump of the pack as installed.  (The
    # file is named for what was dumped, so the backup's name carries the
    # suffix — it is dumped once, when the backup first appears.)
    assert after.split(".")[-2] == before.split(".")[-2]
    assert DR.dsf_content_tag(str(one)) != DR.dsf_content_tag(
        str(tmp_path / "one" / "+40-004.dsf.anchor_bak"))


def test_apply_plan_twice_is_byte_identical(tmp_path, monkeypatch):
    """(c) THE LANE'S TARGET: the same plan applied twice over one pack
    leaves the same DSF bytes, the same file list and the same counts —
    no ``__b<N>__b<M>``, provenance rewritten."""
    import hashlib

    from auto_patch_v2.airport import placement_write as PW

    pack, dsf, plan = _one_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, PW._dw, monkeypatch)

    class _F:
        def __init__(self, res):
            self.resource = res
            self.text = f"I\n800\nOBJ\n{PW.CUT_MARK}b body {res}\n"

    def _files():
        return [_F("objects/b__b0.obj"), _F("objects/b__b1.obj")]

    def _sha(p):
        return hashlib.sha256(open(p, "rb").read()).hexdigest()

    def _objs():
        return sorted(p.name for p in (pack / "objects").iterdir())

    first = PW.apply_plan(plan, _files(), tool,
                          patch_dir=str(tmp_path / "patch"))
    sha1, objs1 = _sha(dsf), _objs()
    prov = pack / "Earth nav data" / "o4_placement_provenance.json"
    import json as _json
    assert _json.loads(prov.read_text())["body_files"] == [
        "objects/b__b0.obj", "objects/b__b1.obj"]
    assert first.counts["restore_bodies_removed"] == 0

    second = PW.apply_plan(plan, _files(), tool,
                           patch_dir=str(tmp_path / "patch"))

    assert _sha(dsf) == sha1
    assert _objs() == objs1 == ["b__b0.obj", "b__b1.obj"]
    assert not any("__b0__b" in n or "__b1__b" in n for n in _objs())
    assert dict(second.counts) | {"restore_bodies_removed": 0} == \
        dict(first.counts) | {"restore_bodies_removed": 0}
    # the previous write's bodies were removed before this one wrote them
    assert second.counts["restore_bodies_removed"] == 2
    assert _json.loads(prov.read_text())["body_files"] == [
        "objects/b__b0.obj", "objects/b__b1.obj"]
    # the backup is still the PRISTINE pack, not the first write's output
    assert not second.dsf.backup_created
    assert (pack / "Earth nav data" / "+40-004.dsf.anchor_bak").read_text(
        ).count("OBJECT") == 4          # 2 OBJECT_DEF + OBJECT_MSL + OBJECT


def test_a_stale_body_file_from_a_bigger_previous_plan_is_removed(tmp_path):
    """§10 (1) + 11m: a plan that cuts FEWER bodies than the last one
    leaves no surplus ``__b<k>.obj`` behind — and an authored object the
    provenance happens to name is never touched (no ``CUT_MARK``)."""
    from auto_patch_v2.airport import placement_write as PW

    pack = tmp_path / "pack"
    nav = pack / "Earth nav data"
    (pack / "objects").mkdir(parents=True)
    nav.mkdir()
    dsf = nav / "+40-004.dsf"
    dsf.write_text("PROPERTY sim/west -4\n")
    (pack / "objects" / "b__b7.obj").write_text(
        f"I\n800\nOBJ\n{PW.CUT_MARK}b body 7\n")
    (pack / "objects" / "authored.obj").write_text("I\n800\nOBJ\n")
    (nav / "o4_placement_provenance.json").write_text(
        '{"body_files": ["objects/b__b7.obj", "objects/authored.obj",'
        ' "../escape.obj"]}')

    r = PW.restore_pack_objects(str(pack), dsf_path=str(dsf))
    assert r.counts["restore_bodies_removed"] == 1
    assert not (pack / "objects" / "b__b7.obj").exists()
    assert (pack / "objects" / "authored.obj").is_file()


def test_the_plan_read_over_a_written_pack_sees_the_pristine_placements(
        tmp_path, monkeypatch):
    """(d) THE DEFECT ITSELF: after a write the live DSF carries 3 rows
    and the plan read must still see the pristine 2 — every id below the
    pristine placement count, so ``edit_dump`` accepts the plan."""
    from auto_patch_v2.airport import dsf as D
    from auto_patch_v2.airport import placement_write as PW

    pack, dsf, plan = _one_pack(tmp_path)
    tool = _stand_in_dsftool(tmp_path, PW._dw, monkeypatch)

    class _F:
        def __init__(self, res):
            self.resource = res
            self.text = f"I\n800\nOBJ\n{PW.CUT_MARK}b body {res}\n"

    PW.apply_plan(plan, [_F("objects/b__b0.obj"), _F("objects/b__b1.obj")],
                  tool, patch_dir=str(tmp_path / "patch"))
    live = D.read_dump(str(dsf))
    pristine_path = PW._dw.pristine_dsf_path(str(dsf))
    pristine = D.read_dump(pristine_path)
    assert len(live.placements) == 3 and len(pristine.placements) == 2
    assert pristine_path.endswith(".anchor_bak")
    # the ids a plan built on the pristine frame carries
    assert max(range(len(pristine.placements))) < len(pristine.placements)
    # and the write half accepts them (it dumps the same frame)
    text = open(pristine_path).read()
    PW._dw.edit_dump(text, plan)                    # no ValueError


# ── §7's NAMED ROWS (lane v2canopy4): one instrument, read by name ───
# The owner names three LEMD rows (OldTerminal_FSX-LEMD38 / -LEMD84 /
# -LEMD60).  Reporting them needed a per-body read; a SECOND pass over
# the same population is the census-wrapper defect, so ``--rows`` is a
# projection of the SAME census pass and the twin holds it to that.


def _split_set_for_rows(tmp_path):
    """A SplitSet over the pad/basin fixture plus its graded sampler."""
    import json as _json

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as RPT

    g = tmp_path / "TEST.graded.json"
    g.write_text(_json.dumps(_graded_doc()))
    sampler, pads, rims = RPT.surface_from_graded(str(g))
    _pack, _dsf, plan = _plan_with_a_building_and_a_basin(tmp_path)
    ss = PP.build_splits(plan, sampler, pads, rims, write=False)
    return RPT, ss, sampler


def test_named_rows_are_a_projection_of_the_one_census_pass(tmp_path):
    """``rows_of`` changes WHAT IS REPORTED, never what is measured: the
    bins, feet and worst list are identical with and without it, and each
    named row's worst |Δ| is the worst the same pass recorded for that
    body."""
    RPT, ss, sampler = _split_set_for_rows(tmp_path)

    plain = RPT.census(ss, sampler, 1.0)
    named = RPT.census(ss, sampler, 1.0, rows_of=("bld.obj",))
    assert plain["bins"] == named["bins"]
    assert plain["feet"] == named["feet"]
    assert plain["worst"] == named["worst"]
    assert plain["rows"] == []

    assert named["rows"] and all("bld.obj" in r["resource"] for r in named["rows"])
    for r in named["rows"]:
        if r["worst_abs"] is None:
            continue
        mine = [d for d, who, _la, _lo in named["worst"]
                if who.startswith(r["resource"] + f" b{r['body']} ")]
        assert mine and math.isclose(r["worst_abs"], max(mine), abs_tol=1e-9)
        assert r["within_0_3"] is (r["worst_abs"] < 0.3)

    # and the verdict FLIPS when the surface under the feet does: a
    # ground 2 m below the anchor's own height is a 2 m float, OVER 0.3.
    sunk = RPT.census(ss, lambda la, lo: sampler(la, lo) - 2.0, 1.0,
                      rows_of=("bld.obj",))
    assert sunk["rows"] and all(
        r["within_0_3"] is False and math.isclose(r["worst"], -2.0, abs_tol=1e-6)
        for r in sunk["rows"] if r["worst_abs"] is not None)


def test_named_rows_carry_the_bodys_own_anchor_and_a_0_3_verdict(tmp_path):
    """Each row reports the body's anchor (the point the drape lands on),
    its reason, and the 0.3 m verdict the owner's bar is read against."""
    RPT, ss, sampler = _split_set_for_rows(tmp_path)
    rows = RPT.census(ss, sampler, 1.0, rows_of=("bld.obj", "pit.obj"))["rows"]
    assert {os.path.basename(r["resource"]) for r in rows} == {"bld.obj",
                                                               "pit.obj"}
    for r in rows:
        assert r["reason"]
        assert r["anchor"][0] and r["anchor"][1]
        assert r["within_0_3"] in (True, False, None)


# ── §13 (owner RULINGS 2026-09-11r/s): AN ELEVATED BODY NEVER HAS A
# FILE OF ITS OWN ────────────────────────────────────────────────────────
# The owner's LEMD read: roofs, road decks and tower parts sit on the
# ground.  218 of 1,092 split bodies had been written as their own file
# with their own anchor, which put a vertex 69 m up ON THE TERRAIN — and
# the foot census read them as perfect, because their lowest vertex WAS
# on the ground.  These twins hold the three halves of the law: the roof
# joins its carrier, the tower is never segmented, the footless object is
# kept whole.

_ELEV = 0.5        # [rebake] elevated_base_m


def _elev_args(**kw):
    a = dict(split_tol_m=0.3, elevated_base_m=_ELEV)
    a.update(kw)
    return a


def _member_plan(path, parts, icao="TEST", lat=40.0, lon=-3.0, heading=0.0,
                 resource=None, span_m=0.0):
    """A one-member plan whose PARTS are given as
    ``(comp, base_y, dlat_m, feet_y)`` — one part per body (no contacts,
    so ``_bodies_of`` puts each in its own body: 10u's gap class)."""
    from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

    ml, _mo = AR._m_per_deg(lat)
    ps = []
    for pid, (comp, base_y, dlat_m, foot_y) in enumerate(parts):
        la = lat + dlat_m / ml
        ps.append(Part(pid=pid, comp=comp, lat=la, lon=lon, base_y=base_y,
                       area_m2=16.0,
                       box=(la, lon, la, lon + span_m / _mo),
                       feet=((la, lon, foot_y),)))
    m = Member(id="dsf:obj1",
               resource=resource or ("objects/" + os.path.basename(str(path))),
               authored_path=str(path), live_path=str(path),
               heading_deg=heading, parts=tuple(ps))
    return RebakePlan(icao=icao, pack_name="pack",
                      pack_root=os.path.dirname(str(path)),
                      units=(Unit("u0", (lat, lon), 0.0, (m,)),), skipped=(),
                      counts={})


def test_a_roof_above_its_walls_is_carried_by_the_walls_file(tmp_path):
    """§13 (1), 10u's gap class: a roof authored as a SEPARATE component
    just above the walls is its own body, and the coarsening used to hand
    it its own file and its own anchor — which drapes the roof on the
    ground.  It must join its CARRIER at its authored offset: one file,
    the walls' anchor, the roof's height above them intact."""
    path, _t = _two_boxes(tmp_path, with_anim=False)
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0),        # the walls
                               (1, 3.5, 2.0, 3.5)])       # the roof, 3.5 m up
    ss = PP.build_splits(plan, _flat(100.0), write=False, **_elev_args())
    assert ss.counts["elevated_own_files"] == 0
    assert ss.counts["bodies_elevated"] == 1
    # one FILE, and it is the walls' — not two
    assert ss.counts["kept"] == 1 and ss.counts["one_body"] == 1
    body = ss.whole[0].bodies[0]
    assert body.elevated_members == 1
    assert abs(body.anchor.y_zero) <= _ELEV     # the file's zero is the ground's
    # the roof's own vertices are NOT feet (§13 (3))
    assert all(abs(f[2]) <= _ELEV for f in body.feet)


def test_a_sixty_metre_tower_part_is_never_cut_into_line_segments(tmp_path):
    """§13 (1): 'a 65 m tower "line segment" is not a fence'.  LEMD's
    ``Terminal4sBlue-ZNTWR`` read line-shaped and was segmented at 65 m
    and 57 m, each segment its own file on its own mid-foot anchor.  A
    ground fence beside it still segments."""
    n = 81
    verts = []
    for i in range(n):                      # a 400 m ground fence, comp 0
        verts += [(i * 5.0, 0.0, 0.0), (i * 5.0, 2.0, 0.0)]
    for i in range(n):                      # the same shape 60 m up, comp 1
        verts += [(i * 5.0, 60.0, 40.0), (i * 5.0, 62.0, 40.0)]
    tris = []
    for base in (0, 2 * n):
        for i in range(n - 1):
            a, b, c, d = base + 2 * i, base + 2 * i + 1, base + 2 * i + 2, \
                base + 2 * i + 3
            tris += [(a, b, d), (a, d, c)]
    path = _write_obj(tmp_path / "tower.obj", verts, [("", tris)])
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0), (1, 60.0, 40.0, 60.0)],
                        span_m=400.0)
    ss = PP.build_splits(plan, _flat(100.0), write=False,
                         **_elev_args(split_tol_m=0.0, line_segment_m=100.0,
                                      line_stations_max=64, line_ratio=20.0,
                                      line_max_h=6.0, foot_band_m=1.0))
    assert ss.counts["elevated_own_files"] == 0
    # the GROUND fence still segments; the tower contributes none
    assert ss.counts["line_bodies_segmented"] == 1
    assert ss.counts["line_segments"] >= 3
    # ... and the tower rides in one of those files, not its own
    assert sum(b.elevated_members for s in ss.all for b in s.bodies) == 1
    assert all(b.anchor.y_zero <= _ELEV for s in ss.splits for b in s.bodies)


def test_a_footless_placement_with_no_carrier_stands_on_its_own_ground(tmp_path):
    """§16 (3), superseding §14 (1)'s ``footless_no_carrier`` KEEP: a
    unit holding no footed body at all offers nothing to carry a footless
    placement — and leaving it on its authored row leaves it on the
    pack's shared datum.  It is written at the ground under its OWN
    footprint with its authored y kept (``footless_own_ground``), so a
    body authored 12 m up renders 12 m over the ground it stands on."""
    path, _t = _two_boxes(tmp_path, with_anim=False)
    plan = _member_plan(path, [(0, 12.0, 0.0, 12.0), (1, 40.0, 2.0, 40.0)])
    ss = PP.build_splits(plan, _flat(100.0), write=False, **_elev_args())
    assert ss.counts["footless"] == 1 and ss.counts["footless_carried"] == 0
    assert ss.counts["footless_no_carrier"] == 1
    assert ss.counts["footless_own_ground"] == 1
    assert ss.counts["elevated_own_files"] == 0
    body = ss.all[0].bodies[0]
    assert body.anchor.y_zero == 0.0            # the AUTHORED y is kept
    assert body.anchor.offset[1] == 0.0         # nothing shifted onto the ground
    assert body.anchor.surface_z == 100.0
    assert PP.OWN_GROUND in body.anchor.reason
    # ... and never the unit's datum row
    assert (body.anchor.lat, body.anchor.lon) != plan.units[0].anchor


def test_a_plan_that_writes_an_elevated_body_alone_fails_the_census(tmp_path):
    """§13 (3): the INSTRUMENT.  The feet histogram cannot catch this
    class — the writer shifts an elevated body so its own lowest vertex
    lands on the terrain, and every foot then reads perfect — so the
    census reports the class by name, and its bar is zero."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import seat_feet_census as SFC

    def _plan(dy, kept_reason):
        return {"icao": "TEST",
                "provenance": {"counts": {"elevated_base_m": _ELEV}},
                "splits": [{"placement": {"index": 1},
                            "bodies": [{"new_resource": "objects/roof__b3.obj",
                                        "authored_offset": [0.0, dy, 0.0],
                                        "elevated_members": 0}]}],
                "kept": [{"index": 2, "resource": "objects/sign.obj",
                          "reason": kept_reason}]}

    out = []
    SFC.print = lambda *a, **k: out.append(" ".join(str(x) for x in a))  # noqa
    try:
        SFC._print_elevated(_plan(69.55, "footless"))
        bad = "\n".join(out)
        out.clear()
        SFC._print_elevated(_plan(0.0, "one_body"))
        good = "\n".join(out)
    finally:
        del SFC.print
    assert "elevated bodies as own files: 1" in bad and "VIOLATED" in bad
    assert "+69.55 m  objects/roof__b3.obj" in bad
    assert "footless placements with no carrier (their own ground): 1" in bad
    assert "elevated bodies as own files: 0" in good and "VIOLATED" not in good
    assert "footless placements with no carrier (their own ground): 0" in good


def test_the_carrier_is_the_ground_body_with_the_largest_plan_overlap():
    """§13 (1): the carrier is the ground body the elevated one stands
    OVER — the largest plan overlap — and only where nothing overlaps
    does the nearest one take it."""
    def _b(i, lat, lon, n=3):
        return (i, AR.Anchor(AR.OTHER, lat, lon, 0.0, "surface at the body's zero",
                             100.0 + i), n)
    # two ground bodies 1 m apart in zero plane (so they never coarsen);
    # the elevated body's box covers the SECOND, but the FIRST is nearer
    bodies = [_b(0, 40.0000, -3.0000), _b(1, 40.0100, -3.0000),
              (2, AR.Anchor(AR.OTHER, 40.0002, -3.0, 9.0, "r", 100.0), 1)]
    boxes = [(39.9999, -3.0001, 40.0001, -2.9999),
             (40.0099, -3.0001, 40.0101, -2.9999),
             (40.0098, -3.0001, 40.0102, -2.9999)]
    assert PP.coarsen(bodies, 0.3, frozenset({2}), boxes) == [[0], [1, 2]]
    # with no overlap at all the NEAREST ground body carries it
    boxes[2] = (40.0001, -3.0001, 40.0003, -2.9999)
    assert PP.coarsen(bodies, 0.3, frozenset({2}), boxes) == [[0, 2], [1]]


def test_is_elevated_reads_the_lowest_vertex_and_the_anchors_zero():
    """§13 (1) has two readings of one sentence and a body fails it
    either way; BELOW the zero plane is lawful (basins, skirts)."""
    ground = AR.Anchor(AR.OTHER, 40.0, -3.0, 0.2, "r", 100.0)
    roof = AR.Anchor(AR.OTHER, 40.0, -3.0, 32.7, "r", 100.0)
    basin = AR.Anchor(AR.BASIN, 40.0, -3.0, -4.0, "r", 100.0)
    assert PP.is_elevated(0.0, ground, _ELEV) is False
    assert PP.is_elevated(9.0, ground, _ELEV) is True      # lowest vertex up
    assert PP.is_elevated(0.0, roof, _ELEV) is True        # anchor's zero up
    assert PP.is_elevated(-4.0, basin, _ELEV) is False     # below is lawful
    assert PP.is_elevated(9.0, roof, 0.0) is False         # disarmed


# ── §14 (owner RULINGS 2026-09-11u/v): A FOOTLESS BODY IS CARRIED; A
# BASIN IS ONE FILE ──────────────────────────────────────────────────────
# The owner's LEMD read: a pedestrian bridge that should hang off the
# terminal lies on the road, and the basin's wall stands BELOW the apron
# it rings.  §13 kept a footless placement whole — on the pack's shared
# DATUM row, 15.7 m under its own building — and §6's rim anchor was
# accepted and unused, so every basin body draped on the floor of its own
# trench.  These twins hold the three halves of §14 and its census.

def _unit_plan(members, icao="TEST", lat=40.0, lon=-3.0, contacts=(),
               abutments=()):
    """A ONE-UNIT plan whose members are
    ``(path, [(comp, base_y, dlat_m, dlon_m, foot_y, half_m)], resource)``
    — the shared-datum case §14 is about: every member on ONE row at
    ``(lat, lon)``, each part a square of side ``2 * half_m`` in plan so
    the PLAN OVERLAP of §14 (3) is a real reading and not a point.  Part
    ids are allocated across the whole unit, as a pack's are."""
    from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

    ml, mo = AR._m_per_deg(lat)
    ms = []
    pid = 0
    for mi, (path, parts, resource) in enumerate(members):
        ps = []
        for comp, base_y, dlat_m, dlon_m, foot_y, half in parts:
            la = lat + dlat_m / ml
            lo = lon + dlon_m / mo
            ps.append(Part(pid=pid, comp=comp, lat=la, lon=lo, base_y=base_y,
                           area_m2=4.0 * half * half,
                           box=(la - half / ml, lo - half / mo,
                                la + half / ml, lo + half / mo),
                           feet=((la, lo, foot_y),)))
            pid += 1
        ms.append(Member(id=f"dsf:obj{mi + 1}", resource=resource,
                         authored_path=str(path), live_path=str(path),
                         heading_deg=0.0, parts=tuple(ps)))
    return RebakePlan(icao=icao, pack_name="pack",
                      pack_root=os.path.dirname(str(members[0][0])),
                      units=(Unit("u0", (lat, lon), 0.0, tuple(ms)),), skipped=(),
                      counts={}, contacts=tuple(contacts),
                      abutments=tuple(abutments))


def test_a_footless_deck_abutting_a_footed_building_rides_its_anchor(tmp_path):
    """§14 (1) (a), the owner's footbridge: a deck authored 5 m up, on the
    unit's shared datum row, abutting the terminal it hangs off.  Written
    alone it lands on the road; kept whole it drapes at the datum.  It
    takes the CARRIER's anchor and the CARRIER's ``y_zero`` — one zero
    plane for the two of them — and names it in ``merged_into``."""
    (tmp_path / "deck_dir").mkdir()
    a_path, _t = _two_boxes(tmp_path, with_anim=False)
    b_path, _t2 = _two_boxes(tmp_path / "deck_dir", with_anim=False)
    plan = _unit_plan([
        # the terminal: two ground bodies 220 m north, on terrain at 616
        (a_path, [(0, 0.0, 200.0, 0.0, 0.0, 8.0),
                  (1, 0.0, 240.0, 0.0, 0.0, 8.0)], "objects/terminal.obj"),
        # the footbridge: ONE body, every vertex 5 m up, beside it
        (b_path, [(0, 5.0, 260.0, 0.0, 5.0, 6.0)], "objects/bridge.obj"),
    ], contacts=((1, 2),))          # the deck's part abuts the terminal's

    def surface(lat, lon):
        return 616.0 if (lat - 40.0) * 111_000.0 > 100.0 else 595.8

    ss = PP.build_splits(plan, surface, write=False, **_elev_args())
    bridge = [s for s in ss.all if s.resource == "objects/bridge.obj"][0]
    assert len(bridge.bodies) == 1              # a rigid span is one file
    b = bridge.bodies[0]
    assert b.elevated is True and b.merged_into.startswith("objects/terminal")
    assert "abuts 1 part contact" in b.anchor.reason
    # the CARRIER's anchor and the CARRIER's zero, never the datum and
    # never the deck's own lowest vertex
    assert b.anchor.surface_z == 616.0 and b.anchor.y_zero == 0.0
    assert (b.anchor.lat, b.anchor.lon) != (plan.units[0].anchor)
    assert b.anchor.offset[1] == 0.0            # not shifted onto the ground
    assert ss.counts["footless_carried"] == 1 and ss.counts["footless"] == 1
    assert ss.counts["footless_no_carrier"] == 0


def test_a_footless_roof_with_no_abutment_takes_the_nearest_footed_body(tmp_path):
    """§14 (1) (b): with no contact and no abutment in the unit's graph,
    the carrier is the NEAREST footed body of the unit in plan — not the
    first, and not the largest."""
    (tmp_path / "far").mkdir()
    (tmp_path / "roof").mkdir()
    near, _t = _two_boxes(tmp_path, with_anim=False)
    far, _t2 = _two_boxes(tmp_path / "far", with_anim=False)
    roof, _t3 = _two_boxes(tmp_path / "roof", with_anim=False)
    plan = _unit_plan([
        (far, [(0, 0.0, 400.0, 0.0, 0.0, 20.0)], "objects/far.obj"),
        (near, [(0, 0.0, 100.0, 0.0, 0.0, 6.0)], "objects/near.obj"),
        (roof, [(0, 14.0, 120.0, 0.0, 14.0, 6.0)], "objects/roof.obj"),
    ])

    def surface(lat, lon):
        return 600.0 + (lat - 40.0) * 111_000.0 * 0.02

    ss = PP.build_splits(plan, _flat(600.0), write=False, **_elev_args())
    r = [s for s in ss.all if s.resource == "objects/roof.obj"][0]
    assert r.bodies[0].merged_into.startswith("objects/near")
    assert "nearest footed body of the unit" in r.bodies[0].anchor.reason
    # §16a (2): ON A SLOPE THE NEAREST BODY IS STILL THE CARRIER.  §16 (3)
    # refused it here — the ground under the ROOF stood 0.4 m off the
    # nearest body's zero — and that is the reading 11aj deletes: a
    # carried body lives in its carrier's frame, and the ground under
    # itself is never compared.  What disqualifies a carrier is that IT
    # is mis-anchored, read on ITS OWN feet, and this one is not.
    ss2 = PP.build_splits(plan, surface, write=False, **_elev_args())
    r2 = [s for s in ss2.all if s.resource == "objects/roof.obj"][0]
    assert r2.bodies[0].merged_into.startswith("objects/near")
    assert ss2.counts.get("carrier_refused_zero_off_ground", 0) == 0


def test_a_basin_resource_is_one_file_anchored_on_its_rim(tmp_path):
    """§14 (2) + §6's basin row, WIRED: a pit authored as a floor plate
    7 m down and a wall ring at grade, cut to a trench 7 m deep, is ONE
    file whose zero is THE RIM — so its parapet stands its authored
    height ABOVE the apron instead of 1.35 m below it (the owner's 11u
    read).  ``rims`` excluded the interior of its own ring from the
    anchor search; before §14 both bodies anchored down on the floor."""
    path, _t = _two_boxes(tmp_path, with_anim=False)
    rim_z, floor_z = 597.64, 590.07
    ml, mo = AR._m_per_deg(40.0)
    d = 30.0
    ring = tuple((40.0 + q[0] * d / ml, -3.0 + q[1] * d / mo)
                 for q in ((-1, -1), (-1, 1), (1, 1), (1, -1)))
    rims = (AR.RimRing("basin_wall:0@853", ring),)
    plan = _unit_plan([(path, [(0, -7.03, 0.0, 0.0, -7.03, 10.0),   # the floor
                               (1, -7.00, 20.0, 0.0, -7.00, 4.0)],  # the wall
                        "objects/pit.obj")])

    inner = tuple((40.0 + q[0] * (d - 2.0) / ml, -3.0 + q[1] * (d - 2.0) / mo)
                  for q in ((-1, -1), (-1, 1), (1, 1), (1, -1)))

    def surface(lat, lon):
        # the trench floor strictly inside the ring, the apron AT the rim
        # on the ring itself and outside it
        return floor_z if AR._inside(inner, lat, lon) else rim_z

    ss = PP.build_splits(plan, surface, (), rims, write=False, **_elev_args())
    pit = ss.all[0]
    assert len(pit.bodies) == 1                 # never split (§14 (2))
    b = pit.bodies[0]
    assert b.body_class == AR.BASIN
    assert "basin rim (basin_wall:0@853)" in b.anchor.reason
    # the anchor stands ON the ring, never inside the trench
    assert (b.anchor.lat, b.anchor.lon) in ring
    assert not AR._inside(inner, b.anchor.lat, b.anchor.lon)
    # THE BAR: the object's zero IS the rim, so a parapet authored +2.99
    # renders 2.99 m above the apron
    assert b.anchor.y_zero == 0.0
    zero = b.anchor.surface_z - b.anchor.y_zero
    assert abs(zero - rim_z) < 0.01
    assert abs((zero + 2.99) - (rim_z + 2.99)) < 0.01


def test_plan_overlap_binds_bodies_the_contact_graph_left_apart(tmp_path):
    """§14 (3) AS §15 (2) LEAVES IT.  The plan-overlap union welds bodies
    the contact graph left apart — the floor under the walls, the ledge
    inside the wall — but the bond now holds only WITHIN A TERRAIN GROUP:
    a bound group whose members' intended zeros span more than
    ``split_tol_m`` is re-cut by §9's own rule, because a rigid body is
    never wider than the terrain it can stand on (LEMD's
    ``green-LEMD03__b0``: 1,384 x 590 m over 5.80 m of surface, lifting
    the garage roof 8.68 m).  The one exemption is the BASIN, whose pit
    was cut TO the object — see
    ``test_a_basin_resource_is_one_file_anchored_on_its_rim``."""
    (tmp_path / "apart").mkdir()
    over, _t = _two_boxes(tmp_path, with_anim=False)
    apart, _t2 = _two_boxes(tmp_path / "apart", with_anim=False)

    def surface(lat, lon):
        return 600.0 if (lat - 40.0) * 111_000.0 < 50.0 else 610.0

    # two parts at the SAME place, terrain equal — but authored 4 m apart
    # in y, so their zero planes differ by 4 m and §9 splits them
    p_over = _unit_plan([(over, [(0, 0.0, 0.0, 0.0, 0.0, 10.0),
                                 (1, -4.0, 3.0, 0.0, -4.0, 10.0)],
                          "objects/pit.obj")])
    ss = PP.build_splits(p_over, surface, write=False, **_elev_args())
    assert len(ss.all[0].bodies) == 2               # §15 (2): re-cut
    assert ss.counts["groups_re_cut"] == 1
    # ... and where the two DO read one terrain the bond holds: the
    # contact graph had them apart, the plan overlap makes them one file
    p_same = _unit_plan([(over, [(0, 0.0, 0.0, 0.0, 0.0, 10.0),
                                 (1, 0.0, 3.0, 0.0, 0.0, 10.0)],
                          "objects/ledge.obj")])
    ss_same = PP.build_splits(p_same, surface, write=False, **_elev_args())
    assert len(ss_same.all[0].bodies) == 1
    assert ss_same.all[0].bodies[0].components == (0, 1)
    # the same two, 200 m apart in plan over terrain that differs: split
    p_apart = _unit_plan([(apart, [(0, 0.0, 0.0, 0.0, 0.0, 10.0),
                                   (1, 0.0, 200.0, 0.0, 0.0, 10.0)],
                           "objects/two.obj")])
    ss2 = PP.build_splits(p_apart, surface, write=False, **_elev_args())
    assert len(ss2.all[0].bodies) == 2


def test_the_v14_census_fails_a_plan_that_leaves_a_footless_body_loose():
    """§14 (4): the four bars, in the ONE implementation both tools call
    (``placement_carrier.census_v14``).  A footless file left on its
    placement's own row is AT THE DATUM; one whose intended zero stands
    above ``elevated_base_m`` was shifted ONTO THE GROUND; a basin
    resource written as two files is SPLIT; and the widest zero-plane
    range of one rigid ring is the SPREAD 11v measured at 7.0 m."""
    from auto_patch_v2.airport import placement_carrier as PC

    def _body(res, *, lat, lon, dy=0.0, cls="other", elev=False, sz=None,
              y0=0.0, why=""):
        return {"body_id": "b0", "class": cls, "new_resource": res,
                "anchor": {"lat": lat, "lon": lon, "heading": 0.0},
                "anchor_reason": why, "authored_offset": [0.0, dy, 0.0],
                "elevated": elev, "surface_z": sz, "y_zero": y0}

    bad = [{"placement": {"index": 1, "resource": "objects/deck.obj",
                          "lat": 40.0, "lon": -3.0},
            "bodies": [_body("objects/deck__b0.obj", lat=40.0, lon=-3.0,
                             elev=True)]},
           {"placement": {"index": 2, "resource": "objects/roof.obj",
                          "lat": 40.0, "lon": -3.0},
            "bodies": [_body("objects/roof__b0.obj", lat=40.1, lon=-3.0,
                             dy=4.5, elev=True)]},
           {"placement": {"index": 3, "resource": "objects/pit.obj",
                          "lat": 40.0, "lon": -3.0},
            "bodies": [_body("objects/pit__b0.obj", lat=40.0, lon=-3.0,
                             cls="basin", sz=590.6, y0=0.0,
                             why="basin rim (basin_wall:0@853)"),
                       _body("objects/pit__b1.obj", lat=40.0, lon=-3.0,
                             cls="basin", sz=597.6, y0=0.0,
                             why="basin rim (basin_wall:0@853)")]}]
    c = PC.census_v14(bad, [{"resource": "objects/sign.obj",
                             "reason": "footless"}],
                      elevated_base_m=_ELEV, split_tol_m=0.3)
    assert c["footless_at_datum"] == 2          # the deck's body and the sign
    assert c["footless_on_ground"] == 1
    assert c["basin_bodies_split"] == 1
    assert abs(c["spread_basin_m"] - 7.0) < 0.01    # 11v's own scatter
    assert c["bars_ok"] is False
    lines = "\n".join(PC.census_v14_lines(c, elevated_base_m=_ELEV,
                                          split_tol_m=0.3))
    assert lines.count("VIOLATED") == 3

    good = [{"placement": {"index": 1, "resource": "objects/deck.obj",
                           "lat": 40.0, "lon": -3.0},
             "bodies": [_body("objects/deck__b0.obj", lat=40.1, lon=-3.1,
                              elev=True, sz=616.2, y0=0.0)]},
            {"placement": {"index": 3, "resource": "objects/pit.obj",
                           "lat": 40.0, "lon": -3.0},
             "bodies": [_body("objects/pit__b0.obj", lat=40.0, lon=-3.0,
                              cls="basin", sz=597.6, y0=0.0,
                              why="basin rim (basin_wall:0@853)")]}]
    c2 = PC.census_v14(good, [{"resource": "objects/sign.obj",
                               "reason": "footless_no_carrier"}],
                       elevated_base_m=_ELEV, split_tol_m=0.3)
    assert (c2["footless_at_datum"], c2["footless_on_ground"],
            c2["basin_bodies_split"], c2["spread_basin_m"]) == (0, 0, 0, 0.0)
    assert c2["footless_no_carrier"] == 1 and c2["bars_ok"] is True
    assert "VIOLATED" not in "\n".join(
        PC.census_v14_lines(c2, elevated_base_m=_ELEV, split_tol_m=0.3))


def test_a_carried_placement_is_actually_written_as_one_file(tmp_path):
    """§14 (1)'s writer half, and the silent floor under it: the OBJ8 cut
    REFUSED to emit a single file (``kept_whole = "one_body"``, "the
    object already IS one body"), which was true while a one-body cut
    changed nothing.  A CARRIED placement is one body and MUST move — its
    row goes to the carrier's anchor and its vertices take the carrier's
    offset — so the refusal silently returned every carried footbridge to
    the datum while the §14 census, reading the plan, reported it carried.
    ``allow_single`` is the caller saying the move is the point."""
    (tmp_path / "deck_dir").mkdir()
    a_path, _t = _two_boxes(tmp_path, with_anim=False)
    b_path, _t2 = _two_boxes(tmp_path / "deck_dir", with_anim=False)
    plan = _unit_plan([
        (a_path, [(0, 0.0, 200.0, 0.0, 0.0, 8.0),
                  (1, 0.0, 240.0, 0.0, 0.0, 8.0)], "objects/terminal.obj"),
        (b_path, [(0, 5.0, 260.0, 0.0, 5.0, 6.0)], "objects/bridge.obj"),
    ], contacts=((1, 2),))

    def surface(lat, lon):
        return 616.0 if (lat - 40.0) * 111_000.0 > 100.0 else 595.8

    ss = PP.build_splits(plan, surface, write=True, **_elev_args())
    bridge = [s for s in ss.splits if s.resource == "objects/bridge.obj"]
    assert bridge, "the carried placement was returned to the datum as kept"
    assert len(bridge[0].files) == 1
    assert bridge[0].files[0].resource == "objects/bridge__b0.obj"
    assert "one_body" not in [k.reason for k in ss.kept]
    # and the single cut file still parses through the engine's own reader
    p = tmp_path / "cut.obj"
    p.write_text(bridge[0].files[0].text, encoding="latin-1")
    g = obj8.parse_obj8(str(p))
    assert g.solid.shape[0] + g.draped.shape[0] == bridge[0].files[0].tris


def test_a_one_body_placement_whose_row_reads_other_terrain_is_written(tmp_path):
    """§14 (1) read on the case §14 (3) creates.  A one-body placement is
    KEPT — row untouched — and on a SHARED-DATUM row that row is the
    datum: at LEMD 73 of 104 such keeps drape more than 3 m (worst
    31.0 m) from where their own anchor says their zero is.  The keep is
    admitted only where the row and the anchor read the SAME surface."""
    path, _t = _two_boxes(tmp_path, with_anim=False)
    plan = _unit_plan([(path, [(0, 0.0, 400.0, 0.0, 0.0, 8.0)],
                        "objects/hangar.obj")])

    # the authored row (40.0, -3.0) reads 595.8; the hangar's own ground,
    # 400 m north, reads 616.0
    def steep(lat, lon):
        return 616.0 if (lat - 40.0) * 111_000.0 > 100.0 else 595.8

    ss = PP.build_splits(plan, steep, write=True, **_elev_args())
    assert [s.resource for s in ss.splits] == ["objects/hangar.obj"]
    assert ss.counts["one_body_off_row"] == 1
    # ... and where the row DOES read the body's own surface, it is kept
    ss2 = PP.build_splits(plan, _flat(616.0), write=True, **_elev_args())
    assert ss2.splits == () and [k.reason for k in ss2.kept] == ["one_body"]


# ── §15 (owner RULINGS 2026-09-11ae): STANDS-OVER IS THE CARRIER; THE
# BINDING RE-CUTS; DUPLICATE ROWS ARE ONE PLACEMENT ──────────────────────
# The owner's 1.0.316 LEMD read: hangar roofs floating over their
# buildings, a garage roof 8.65 m up, a terminal roof "slightly
# floating".  Every one is a HEIGHT defect and none is a missing file:
# the roof took a carrier 250 m away inside its own placement, a rigid
# body was bound 1,384 m wide across 5.80 m of terrain, and a resource
# with two identical rows had one of them replaced and one left drawing
# the whole un-split object at the datum.

def test_a_roof_resource_rides_the_walls_of_ANOTHER_resource(tmp_path):
    """§15 (1): the carrier is what the body STANDS OVER, across the
    whole unit and every resource alike.  The pack names its roofs as
    their own resources (``TEJ*``), so the walls a roof rides are almost
    never its own file — and its own file's ground body may be hundreds
    of metres away, which is exactly how LEMD's ``LEMD38`` roof took a
    carrier 250 m off and floated 6.11 m."""
    (tmp_path / "roof_dir").mkdir()
    walls, _t = _two_boxes(tmp_path, with_anim=False)
    roof, _t2 = _two_boxes(tmp_path / "roof_dir", with_anim=False)
    plan = _unit_plan([
        # the ROOF resource: its own ground body 250 m north (on terrain
        # at 616), and the roof plate 9 m up over the hangar at the origin
        (roof, [(0, 0.0, 250.0, 0.0, 0.0, 8.0),
                (1, 9.0, 0.0, 0.0, 9.0, 10.0)], "objects/tej.obj"),
        # the HANGAR: walls on the ground at the origin (terrain 595.8)
        (walls, [(0, 0.0, 0.0, 0.0, 0.0, 10.0)], "objects/hangar.obj"),
    ])

    def surface(lat, lon):
        return 616.0 if (lat - 40.0) * 111_000.0 > 100.0 else 595.8

    ss = PP.build_splits(plan, surface, write=False, **_elev_args())
    tej = [s for s in ss.all if s.resource == "objects/tej.obj"][0]
    carried = [b for b in tej.bodies if b.merged_into]
    assert len(carried) == 1, "the roof did not leave its own placement"
    # the hangar is a one-body placement KEPT on its own (correct) row,
    # so the carried file names the resource itself and says so
    assert carried[0].merged_into == "objects/hangar.obj"
    assert carried[0].merged_into_written is False
    assert "stands over" in carried[0].anchor.reason
    assert "carrier kept whole" in carried[0].anchor.reason
    # ONE zero plane for the two of them: the hangar's, not its own
    # resource's ground body 250 m north
    assert carried[0].anchor.surface_z == 595.8
    assert ss.counts["elevated_ride_other_file"] == 1


def test_a_bound_group_wider_than_its_terrain_is_re_cut(tmp_path):
    """§15 (2): §14 (3)'s plan-overlap bond welds bodies that overlap in
    plan whatever the terrain does, and at LEMD that made ONE rigid body
    1,384 x 590 m whose feet span 5.80 m of surface — its low-side anchor
    then lifted the garage roof 8.68 m over the garage's own walls.  A
    rigid body is never wider than the terrain it can stand on."""
    path, _t = _two_boxes(tmp_path, with_anim=False)
    # three parts in a plan-overlapping CHAIN (each box touches the next)
    # over ground that climbs 5 m from end to end
    plan = _unit_plan([(path, [(0, 0.0, 0.0, 0.0, 0.0, 12.0),
                               (1, 0.0, 20.0, 0.0, 0.0, 12.0),
                               (2, 0.0, 40.0, 0.0, 0.0, 12.0)],
                        "objects/terminal.obj")])

    def ramp(lat, lon):
        return 595.0 + (lat - 40.0) * 111_132.954 * 0.125

    ss = PP.build_splits(plan, ramp, write=False, **_elev_args())
    bodies = [b for s in ss.all for b in s.bodies]
    zeros = [b.anchor.surface_z - b.anchor.y_zero for b in bodies]
    assert len(bodies) >= 2, "the 5 m chain was welded into one rigid body"
    assert max(zeros) - min(zeros) > 0.3      # they read DIFFERENT ground
    assert ss.counts["groups_re_cut"] == 1
    # ... and over FLAT ground the bond holds: one body, one file
    flat = PP.build_splits(plan, _flat(595.0), write=False, **_elev_args())
    assert sum(len(s.bodies) for s in flat.all) == 1
    assert flat.counts["groups_re_cut"] == 0


def test_duplicate_rows_of_one_resource_are_one_placement(tmp_path):
    """§15 (4): rows of one resource identical in lon/lat/heading are ONE
    placement to the split.  LEMD's pristine DSF carries two rows for 19
    ``Airport_Cargo`` resources on the shared datum; the plan reads the
    resource once, the writer replaced ONE row, and the other went on
    drawing the whole un-split object at the datum point."""
    from auto_patch_v2.airport import dsf_write as DW
    from auto_patch_v2.model import placement as PM

    text = ("OBJECT_DEF objects/a.obj\n"
            "OBJECT_DEF objects/b.obj\n"
            "OBJECT 0 -3.564788 40.492764 0.000000\n"
            "OBJECT 1 -3.560000 40.490000 12.000000\n"
            "OBJECT 0 -3.564788 40.492764 0.000000\n")
    lines = text.splitlines(keepends=True)
    assert DW.duplicate_rows(lines) == {0: [2]}
    assert DW.duplicate_rows(lines, {1}) == {}      # no split names row 0

    plan = PM.PlacementPlan(
        icao="TEST", pack_name="p", pack_root=str(tmp_path),
        dsf_path=str(tmp_path / "x.dsf"), dsf_backup_path="",
        provenance=PM.Provenance("", "", "", {}),
        splits=(PM.Split(placement=PM.PlacementRef(0, "objects/a.obj",
                                                   -3.564788, 40.492764, 0.0),
                         bodies=(PM.Body(body_id="b0", body_class="other",
                                         components=(0,),
                                         anchor=PM.Anchor(-3.5, 40.5, 0.0),
                                         anchor_reason="r",
                                         new_resource="objects/a__b0.obj"),)),))
    out = DW.edit_dump(text, plan)
    rows = [r for r in out.splitlines() if r.startswith("OBJECT ")]
    # the body row replaced the FIRST; the duplicate is gone, and the
    # unrelated placement is untouched
    assert sum(1 for r in rows if r.split()[1] == "0") == 0
    assert any(r.startswith("OBJECT 2 ") for r in rows)     # the new def
    assert sum(1 for r in rows if "40.490000" in r) == 1
    assert len(rows) == 2


def test_an_off_sheet_anchor_is_excluded_from_every_comparison(tmp_path):
    """§15 (5): the tool samples the GRADED SURFACE, the shipped plan
    samples the MESH.  A body whose anchor stands on no graded face reads
    NO surface here — it is marked off-sheet, excluded from the census's
    bins and from the §15 (3) bar, and never guessed at."""
    from auto_patch_v2.airport import placement_carrier as PC
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as OSR

    path, _t = _two_boxes(tmp_path, with_anim=False)
    plan = _unit_plan([(path, [(0, 0.0, 0.0, 0.0, 0.0, 8.0)],
                        "objects/hangar.obj")])
    ss = PP.build_splits(plan, lambda la, lo: None, write=False, **_elev_args())
    cen = OSR.census(ss, lambda la, lo: None, 1.0, rows_of=("hangar",))
    assert cen["bins"].get("off-sheet") and "off-surface" not in cen["bins"]
    assert cen["rows"][0]["off_sheet"] == cen["rows"][0]["feet"]
    assert cen["rows"][0]["within_0_3"] is None     # no verdict, not a pass
    import dataclasses as _dc
    wh, _kp = PP.to_placement_records(_dc.replace(ss, splits=ss.all))
    v15 = PC.census_v15([q.to_dict() for q in wh])
    assert v15["off_sheet_bodies"] == 1
    assert v15["stands_over"] == 0 and v15["carried_float_gt"] == 0


def test_the_v15_census_fails_a_carried_body_left_above_what_it_stands_on():
    """§15 (3): the residual the EYE reads, and why no foot census can see
    it — a CARRIED body has no feet at all, and a body anchored at its own
    low-side foot reads every foot of its own as lawful while standing
    metres above the walls under it.  The bar is 0 for carried bodies; a
    FOOTED one's float is reported, never barred (two footed bodies over
    genuinely different terrain lawfully differ)."""
    from auto_patch_v2.airport import placement_carrier as PC

    def _b(res, box, sz, y0, feet, elevated=False, carrier="objects/hangar__b0.obj"):
        # CARRIED is "its zero is its CARRIER's reading" (§16 (3)): the
        # census reads ``merged_into``, so a body on its own ground is
        # judged like a footed one
        return {"new_resource": res, "plan_box": list(box), "surface_z": sz,
                "y_zero": y0, "feet": feet, "elevated": elevated,
                "merged_into": carrier if elevated else None}

    walls = {"placement": {"index": 1, "lat": 40.0, "lon": -3.0},
             "bodies": [_b("objects/hangar__b0.obj",
                           (40.0, -3.0, 40.001, -2.999), 100.0, 0.0, 8)]}
    roof = {"placement": {"index": 2, "lat": 40.0, "lon": -3.0},
            "bodies": [_b("objects/tej__b0.obj",
                          (40.0, -3.0, 40.0005, -2.9995), 106.11, 0.0, 0, True)]}
    bad = PC.census_v15([walls, roof])
    assert bad["stands_over"] == 1 and bad["carried_float_gt"] == 1
    assert bad["bars_ok"] is False
    assert round(bad["carried_worst"][0][0], 2) == 6.11
    assert "VIOLATED" in "\n".join(PC.census_v15_lines(bad))

    # §16 (3): the SAME body standing on its OWN ground (no carrier) is
    # not in the carried class — it read the terrain itself
    own = {"placement": {"index": 3, "lat": 40.0, "lon": -3.0},
           "bodies": [_b("objects/tej__b1.obj", (40.0, -3.0, 40.0005, -2.9995),
                         106.11, 0.0, 0, True, carrier=None)]}
    mine = PC.census_v15([walls, own])
    assert mine["carried_float_gt"] == 0 and mine["footed_float_gt"] == 1

    roof["bodies"][0]["surface_z"] = 100.0          # carried at the walls' zero
    good = PC.census_v15([walls, roof])
    assert good["carried_float_gt"] == 0 and good["bars_ok"] is True
    assert "VIOLATED" not in "\n".join(PC.census_v15_lines(good))

    # a body of ANOTHER unit (another row) is out of §15 (1)'s reach and
    # is reported as its own number, never as a float the law could
    # close.  It is read on a body the law gave NO carrier: 11ak (1)
    # resolves a carried body's beneath by IDENTITY (``merged_into``),
    # and the carrier the law chose is in the body's own unit by
    # construction — so a carried body is never out of the reading's
    # reach, whatever its row says.
    roof["placement"]["lat"] = 41.0
    roof["bodies"][0]["surface_z"] = 106.11
    roof["bodies"][0]["merged_into"] = None
    other = PC.census_v15([walls, roof])
    assert other["stands_over"] == 0 and other["carried_float_gt"] == 0
    assert other["stands_over_other_unit_only"] == 1


# ── §16 (owner RULINGS 2026-09-11ai; lane ``v2skipped``) ─────────────────


def _dc_replace_part(plan, **kw):
    """``plan`` with its single member's single part's fields replaced."""
    import dataclasses as dc
    u = plan.units[0]
    m = u.members[0]
    p = dc.replace(m.parts[0], **kw)
    return dc.replace(plan, units=(dc.replace(
        u, members=(dc.replace(m, parts=(p,)),)),))

def _panel(path, y=9.0, x0=0.0, z0=0.0, side=8.0):
    """A roof PANEL: one horizontal sheet at ``y``, no thickness at all —
    the class the seat-era gate dropped ("no genuine solid component")."""
    v = [(x0, y, z0), (x0 + side, y, z0), (x0 + side, y, z0 + side), (x0, y, z0 + side)]
    return _write_obj(path, v, [("", [(0, 1, 2), (0, 2, 3)])])


def test_a_roof_only_resource_enters_the_plan_and_is_carried(tmp_path):
    """§16 (1): NO THICKNESS GATE under ``placement = agl``.  A resource
    with no genuine solid component (LEMD's garage roof-top pavilions,
    ``Terminal4_green-TEJ1``) was SKIPPED by the seat-era rule and never
    entered the plan population at all — so it kept the pack's shared
    datum row and rendered 15.8 m under the slab it stands on.  It is now
    admitted as a FOOTLESS body, and its parts carry NO FEET: a thin panel
    is not a ground contact."""
    from auto_patch_v2.airport import obj8 as _o8
    from auto_patch_v2.airport import pack_partition as PZ
    from auto_patch_v2.law import Law

    law = Law.load()
    path = _panel(tmp_path / "tej1.obj")
    cache = _o8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    o = _o8.PlacedObject(id="dsf:obj1", path="objects/tej1.obj", resolved=str(path),
                         xy=(0.0, 0.0), heading_deg=0.0, agl_m=0.0, kind="OBJECT",
                         anchor_z=0.0, below_grade=None, plan_bbox=None,
                         solid_min_z=None, solid_min_depth_m=None, hard_deck=None,
                         deck_top_z=None)
    counts, skipped, no_solid = PZ.counts_zero(), {}, set()
    built = PZ._build_member(o, cache, law, PZ.Screen(), (), str(tmp_path),
                             counts, skipped, no_solid)
    assert law.tables.structures.rebake.placement == "agl"
    assert built is not None                    # the gate is not applied
    assert skipped == {} and counts["no_parts"] == 0
    assert o.path in no_solid                   # ... and it is FOOTLESS
    assert counts["no_solid_admitted"] == 1


def test_a_scattered_roof_body_is_cut_into_terrain_groups(tmp_path):
    """§16 (2): EVERY GROUND BODY IS RE-CUT BY TERRAIN — including a body
    authored as ONE welded component, which the part cut cannot divide.
    LEMD's ``Terminal4_green-TEJ3`` is a roof-panel resource scattered
    over 1 x 2 km of terminal: one body, one zero, and its own ground
    spanning 5.02 m.  The cut is by TRIANGLE, over the ground under
    each.

    §16a (1) draws the line this twin now stands on both sides of: the
    cut is for a body that STANDS ON THE GROUND.  A CARRIED body — the
    same strip, raised — is never cut by the ground under itself; its
    pieces are its carrier's."""
    ml, _mo = AR._m_per_deg(40.0)
    span = 600.0
    v, tris = [], []
    n = 13                                      # ONE welded strip, 600 m long
    for k in range(n):
        z0 = -k * span / (n - 1)
        v += [(0.0, 0.0, z0), (20.0, 0.0, z0)]
    for k in range(n - 1):
        a, b, c2, d = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        tris += [(a, b, d), (a, d, c2)]
    path = _write_obj(tmp_path / "tej3.obj", v, [("", tris)])
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0)], span_m=0.0)
    # the ground falls 1 m per panel northwards
    m0 = plan.units[0].members[0]
    p0 = m0.parts[0]
    plan = _dc_replace_part(plan, box=(40.0 - span / ml, p0.lon, 40.0, p0.lon))

    def surface(lat, lon):
        return 600.0 + (lat - 40.0) * ml * 0.005

    ss = PP.build_splits(plan, surface, write=False,
                         **_elev_args(line_stations_max=64, foot_band_m=1.0))
    assert ss.counts.get("bodies_re_cut_by_triangle") == 1
    assert ss.counts.get("terrain_triangle_groups", 0) >= 3
    # every group's own ground is within the tolerance of its own anchor
    for s in ss.all:
        for b in s.bodies:
            zs = _PC.ground_samples(surface, b.foot_boxes, b.geom_box)
            if zs and b.anchor.surface_z is not None:
                assert max(abs(z - b.anchor.surface_z) for z in zs) <= 1.0
    # §16a (1): THE SAME STRIP, ELEVATED, IS NOT CUT BY ITS OWN GROUND.
    # Nothing about the terrain under a carried body may divide it — the
    # garage pavilions cut that way landed -1.27 ... +3.70 m against the
    # slab they stand on.
    hi = _member_plan(_write_obj(tmp_path / "tej3hi.obj",
                                 [(x, y + 9.0, z) for x, y, z in v],
                                 [("", tris)]),
                      [(0, 9.0, 0.0, 9.0)], span_m=0.0)
    p1 = hi.units[0].members[0].parts[0]
    hi = _dc_replace_part(hi, box=(40.0 - span / ml, p1.lon, 40.0, p1.lon))
    ss2 = PP.build_splits(hi, surface, write=False,
                          **_elev_args(line_stations_max=64, foot_band_m=1.0))
    assert ss2.counts.get("bodies_re_cut_by_triangle", 0) == 0
    assert ss2.counts.get("carried_bodies_uncut") == 1


def test_a_fence_never_carries_and_a_mis_anchored_carrier_is_refused():
    """§16 (3): A CARRIER IS A SOLID.  A fence segment's axis-aligned plan
    box contains the garage roof its footprint never touches — which is
    how LEMD's ``PKT4__b1`` came to ride ``LEMDzaun__b5`` 6 m under the
    slab.  A LINE body never carries; nor does one filling less than
    ``[placement] carrier_fill_min`` of its own box.

    §16a (2): and the GROUND CHECK IS ON THE CARRIER — a candidate whose
    own zero stands further than the tolerance from the ground under ITS
    OWN feet (``Candidate.ground_off``) is refused, because it is itself
    mis-anchored and would carry its error.  The ground under the CARRIED
    body is not an input to the search at all."""
    def _cand(member, cls, box, part_boxes, z, ground_off=0.0):
        return _PC.Candidate(member, f"objects/c{member}.obj",
                             AR.Anchor(cls, 0.5 * (box[0] + box[2]),
                                       0.5 * (box[1] + box[3]), 0.0, "r", z),
                             frozenset({member}), 4, box, part_boxes=part_boxes,
                             group=0, body_class=cls,
                             fill=_PC.fill_of(box, part_boxes),
                             ground_off=ground_off)

    big = (40.0, -3.0, 40.01, -2.99)            # a 1 km box
    thin = [(40.0, -3.0, 40.01, -2.99999)]      # ... holding one thin strip
    fence = _cand(0, AR.LINE_SEGMENT, big, [big], 100.0)
    grass = _cand(1, AR.OTHER, big, thin, 100.0)
    walls_box = (40.0040, -3.0010, 40.0050, -3.0000)
    walls = _cand(2, AR.BUILDING, walls_box, [walls_box], 106.0)
    roof_box = (40.0042, -3.0008, 40.0048, -3.0002)
    args = dict(fill_min=0.2, tol_m=0.3)
    c, why = _PC.carrier_for(frozenset({9}), roof_box, [fence, grass, walls], {},
                             [roof_box], **args)
    assert c is walls and "stands over" in why   # not the fence, not the grass
    # the same walls, now standing 6 m off the ground under their OWN feet:
    # mis-anchored, refused, and the search goes on
    refusals: dict = {}
    bad = _cand(2, AR.BUILDING, walls_box, [walls_box], 106.0, ground_off=6.0)
    c2, _w = _PC.carrier_for(frozenset({9}), roof_box, [fence, grass, bad], {},
                             [roof_box], refusals=refusals, **args)
    assert c2 is None and refusals.get("zero_off_ground") == 1
    assert refusals.get("line") == 1 and refusals.get("fill") == 1


def test_the_16_census_reads_the_ground_under_the_bodys_own_geometry():
    """§16 (2)'s instrument: ``float = zero - ground_under_geometry``, the
    ground read under the body's OWN parts (``geom_box`` / ``foot_boxes``)
    and never under its carrier's box — which is the reading that lets a
    roof ride a fence 6 m below it and call the result lawful.  The
    population census (§16 (1)) bars the thickness-gate class alone."""
    def _body(res, box, sz, carrier=None):
        return {"new_resource": res, "geom_box": list(box), "surface_z": sz,
                "y_zero": 0.0, "foot_boxes": [list(box)],
                "merged_into": carrier, "elevated": bool(carrier)}

    box = (40.0, -3.0, 40.0002, -2.9998)
    good = {"placement": {"index": 1}, "bodies": [_body("a.obj", box, 106.0, "w.obj")]}
    bad = {"placement": {"index": 2}, "bodies": [_body("b.obj", box, 100.0, "f.obj")]}
    c = _PC.census_v16([good, bad], lambda la, lo: 106.0)
    # §16a (3): the number is INFORMATION ONLY — §16 (3) barred it at 0,
    # and that is the reading 11aj deletes.  THE bar for a carried body
    # is §15 (3)'s ``zero - zero_beneath``.
    assert c["carried_ground_gt"] == 1 and c["bars_ok"] is True
    assert c["carried_worst"][0][1] == "b.obj"
    assert "INFORMATION ONLY" in "\n".join(_PC.census_v16_lines(c))
    assert "VIOLATED" not in "\n".join(_PC.census_v16_lines(c))
    ok = _PC.census_v16([good], lambda la, lo: 106.0)
    assert ok["carried_ground_gt"] == 0 and ok["bars_ok"] is True

    pop = _PC.census_population([
        ("objects/roof.obj", "no genuine solid component: nothing to seat"),
        ("objects/lib.obj", "stock library resource (shared, never baked)"),
        ("objects/many.obj", "placed at 12 anchors — one file cannot carry "
                             "per-placement offsets (I-4)")])
    assert pop["datum_rows_outside_plan"] == 1 and pop["bars_ok"] is False
    assert pop["lawful_skips"] == 1 and sum(pop["other_skips"].values()) == 1
    assert "VIOLATED" in "\n".join(_PC.census_population_lines(pop))


# ── §16a: a carried body lives in its carrier's frame (RULINGS 11aj) ─────

def _strip(x0, x1, y, n, z0=-10.0, z1=10.0):
    """ONE WELDED sheet from ``x0`` to ``x1`` at height ``y``, ``n`` quads
    long — the shape a roof-panel resource actually is (LEMD's
    ``green-TEJ3`` is one welded component over 1 x 2 km), and the shape
    no PART cut can divide."""
    v, t = [], []
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        v += [(x, y, z0), (x, y, z1)]
    for k in range(n):
        a, b, c, d = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        t += [(a, b, d), (a, d, c)]
    return v, t


def _stepped(levels):
    """A surface that steps with LONGITUDE: ``levels`` is
    ``[(east_m_from, east_m_to, z), ...]`` about (40.0, -3.0)."""
    _ml, mo = AR._m_per_deg(40.0)

    def surface(lat, lon):
        e = (lon - (-3.0)) * mo
        for a, b, z in levels:
            if a <= e <= b:
                return z
        return levels[-1][2]
    return surface


def _carrier_of(b):
    """The body a carried file rides, named without its body suffix (a
    carrier KEPT WHOLE keeps its own resource name)."""
    return b.merged_into.replace("__b0.obj", ".obj")


def test_a_carried_roof_over_two_buildings_is_cut_into_one_piece_per_carrier(tmp_path):
    """§16a (1): A CARRIED BODY IS CUT WHERE ITS CARRIER IS CUT — one
    piece per carrier group it stands over, each riding THAT group's zero
    at the authored offset.  A welded roof spanning two buildings 10 m
    apart in height is two pieces, not one rigid plate at one of the
    two."""
    va, ta = _box(-2.0, -2.0)
    a_path = _write_obj(tmp_path / "a.obj", va, [("", ta)])
    vb, tb = _box(38.0, -2.0)
    b_path = _write_obj(tmp_path / "b.obj", vb, [("", tb)])
    rv, rt = _strip(-10.0, 50.0, 6.0, 12)
    roof = _write_obj(tmp_path / "roof.obj", rv, [("", rt)])
    plan = _unit_plan([
        (a_path, [(0, 0.0, 0.0, 0.0, 0.0, 10.0)], "objects/a.obj"),
        (b_path, [(0, 0.0, 0.0, 40.0, 0.0, 10.0)], "objects/b.obj"),
        (roof, [(0, 6.0, 0.0, 20.0, 6.0, 30.0)], "objects/roof.obj"),
    ])
    surface = _stepped([(-12.0, 12.0, 600.0), (28.0, 52.0, 610.0)])
    ss = PP.build_splits(plan, surface, write=False, **_elev_args())
    r = [s for s in ss.all if s.resource == "objects/roof.obj"][0]
    assert len(r.bodies) == 2, [b.merged_into for b in r.bodies]
    assert sorted(_carrier_of(b) for b in r.bodies) == \
        ["objects/a.obj", "objects/b.obj"]
    zeros = sorted(b.anchor.surface_z - b.anchor.y_zero for b in r.bodies)
    assert zeros == pytest.approx([600.0, 610.0], abs=1e-6)
    assert ss.counts.get("carried_bodies_cut_by_carrier") == 1
    assert ss.counts.get("carrier_pieces") == 2
    # ... and the ground under the roof itself was never asked
    assert ss.counts.get("bodies_re_cut_by_triangle", 0) == 0
    assert ss.counts.get("carried_bodies_uncut") == 1


def test_a_carried_roof_follows_its_walls_own_terrain_re_cut(tmp_path):
    """§16a (1), the case 11aj is named for: walls the terrain re-cut into
    THREE groups carry the roof over them in three pieces, each on its
    own group's zero.  §16 (2) cut the roof by the ground under ITSELF
    instead, and LEMD's garage pavilions then read -1.27 ... +3.70 m
    against the slab they stand on."""
    verts, tris = [], []
    for k, x0 in enumerate((-2.0, 38.0, 78.0)):
        v, t = _box(x0, -2.0)
        tris += [(a + 8 * k, b + 8 * k, c + 8 * k) for a, b, c in t]
        verts += v
    walls = _write_obj(tmp_path / "walls.obj", verts, [("", tris)])
    rv, rt = _strip(-10.0, 90.0, 6.0, 20)
    roof = _write_obj(tmp_path / "roof.obj", rv, [("", rt)])
    plan = _unit_plan([
        (walls, [(0, 0.0, 0.0, 0.0, 0.0, 10.0),
                 (1, 0.0, 0.0, 40.0, 0.0, 10.0),
                 (2, 0.0, 0.0, 80.0, 0.0, 10.0)], "objects/walls.obj"),
        (roof, [(0, 6.0, 0.0, 40.0, 6.0, 50.0)], "objects/roof.obj"),
    ], contacts=((0, 1), (1, 2)))          # ONE welded body of three parts
    surface = _stepped([(-12.0, 12.0, 600.0), (28.0, 52.0, 605.0),
                        (68.0, 92.0, 610.0)])
    ss = PP.build_splits(plan, surface, write=False, **_elev_args())
    w = [s for s in ss.all if s.resource == "objects/walls.obj"][0]
    assert ss.counts.get("bodies_re_cut_by_terrain") == 1
    assert len(w.bodies) == 3                     # the walls' own terrain groups
    r = [s for s in ss.all if s.resource == "objects/roof.obj"][0]
    assert len(r.bodies) == 3, [b.merged_into for b in r.bodies]
    assert ss.counts.get("carrier_pieces") == 3
    # each piece stands at the zero of the wall group under it — the bar
    # §16a (3) makes THE bar, ``zero - zero_beneath``, read here directly
    wall_zero = {b.new_resource: b.anchor.surface_z - b.anchor.y_zero
                 for b in w.bodies}
    for b in r.bodies:
        assert b.merged_into in wall_zero
        assert (b.anchor.surface_z - b.anchor.y_zero) == \
            pytest.approx(wall_zero[b.merged_into], abs=1e-6)
    assert sorted(round(b.anchor.surface_z - b.anchor.y_zero, 3)
                  for b in r.bodies) == [600.0, 605.0, 610.0]


def test_the_carried_bar_is_zero_beneath_and_the_ground_reading_is_information():
    """§16a (3): ``zero - zero_beneath`` is THE bar for a carried body
    (:func:`census_v15`); ``zero - ground_under_geometry``
    (:func:`census_v16`) is printed for information only.

    The two disagree wherever walls stand on sloping ground — the walls
    anchor at their low-side foot, so a roof lawfully ON them reads
    metres from the ground under itself.  This is the body that is
    LAWFUL by the bar and loud by the other reading."""
    box = (40.0, -3.0, 40.0002, -2.9998)
    walls = {"new_resource": "w.obj", "class": AR.BUILDING, "plan_box": list(box),
             "geom_box": list(box), "foot_boxes": [list(box)], "fill": 1.0,
             "surface_z": 600.0, "y_zero": 0.0, "feet": 8, "merged_into": None}
    roof = {"new_resource": "r.obj", "class": AR.BUILDING, "plan_box": list(box),
            "geom_box": list(box), "foot_boxes": [list(box)], "fill": 1.0,
            "surface_z": 600.0, "y_zero": 0.0, "feet": 0,
            "merged_into": "w.obj", "elevated": True}
    splits = [{"placement": {"index": 1, "lat": 40.0, "lon": -3.0},
               "bodies": [walls]},
              {"placement": {"index": 2, "lat": 40.0, "lon": -3.0},
               "bodies": [roof]}]
    v15 = _PC.census_v15(splits, ())
    assert v15["carried_float_gt"] == 0 and v15["bars_ok"] is True
    # the ground under the roof's own geometry stands 4 m below the walls'
    # zero: LOUD in §16's reading, and not a bar
    v16 = _PC.census_v16(splits, lambda la, lo: 596.0)
    assert v16["carried_ground_gt"] == 1 and v16["bars_ok"] is True


def test_the_mis_anchoring_test_reads_each_foots_own_authored_height():
    """§16a (2)'s reading: the ground under a body's own FEET says its
    zero is ``surface(foot) - y_foot``, not ``surface(foot)``.

    A building on a slope whose feet were AUTHORED to that slope is
    correctly anchored and carries; one whose zero stands 6 m off what
    its own feet read is mis-anchored and is refused.  Reading the raw
    surface instead made the first look like the second — measured at
    LEMD: 313 footed bodies refused as carriers instead of 117, and 49
    roofs over them more than 0.5 m off the walls they stand on."""
    ml, _mo = AR._m_per_deg(40.0)

    def slope(lat, lon):
        return 600.0 + (lat - 40.0) * ml * 0.05        # 5 % northwards

    # feet authored to the slope: (lat, lon, y) with y matching the fall
    feet = tuple((40.0 + d / ml, -3.0, d * 0.05) for d in (0.0, 20.0, 40.0))
    good = AR.Anchor(AR.BUILDING, 40.0, -3.0, 0.0, "low-side foot", 600.0)
    assert _PC.anchor_ground_off(good, feet, slope) == pytest.approx(0.0, abs=1e-6)
    # the same body whose file says its zero is 6 m higher: mis-anchored
    bad = AR.Anchor(AR.BUILDING, 40.0, -3.0, -6.0, "low-side foot", 600.0)
    assert _PC.anchor_ground_off(bad, feet, slope) == pytest.approx(6.0, abs=1e-6)
    # off-sheet, or footless: no reading is no evidence
    assert _PC.anchor_ground_off(good, (), slope) is None
    assert _PC.anchor_ground_off(
        AR.Anchor(AR.BUILDING, 40.0, -3.0, 0.0, "r", None), feet, slope) is None


# ── 11ak: the census split, the foot re-cut, the deck over a road ────────

def test_the_carried_bar_is_read_against_the_carrier_the_law_chose():
    """11ak (1): a CARRIED body's ``beneath`` is the carrier the LAW
    CHOSE, and a REFUSED body under it is its own class.

    The body below is a roof on walls at 600 whose footprint also lies
    over a mis-anchored body at 593 — one §16a (2) REFUSES as a carrier.
    The law therefore put the roof on the walls, by law; reading the
    refused body as "beneath" reports +7 m of float that no placement
    decision produced (LEMD 3 of 4 carried floats, OTHH 23 of 39, 11aj's
    own attribution).  The refused body is not thrown away: it is
    counted and named, with how far its own feet stand off."""
    big = (40.0, -3.0, 40.0004, -2.9996)
    small = (40.0, -3.0, 40.0002, -2.9998)
    walls = {"new_resource": "w.obj", "class": AR.BUILDING, "plan_box": list(big),
             "foot_boxes": [list(big)], "fill": 1.0, "surface_z": 600.0,
             "y_zero": 0.0, "feet": 8, "merged_into": None, "ground_off": 0.0}
    bad = {"new_resource": "bad.obj", "class": AR.BUILDING,
           "plan_box": list(small), "foot_boxes": [list(small)], "fill": 1.0,
           "surface_z": 593.0, "y_zero": 0.0, "feet": 8, "merged_into": None,
           "ground_off": 2.0}
    roof = {"new_resource": "r.obj", "class": AR.BUILDING,
            "plan_box": list(small), "foot_boxes": [list(small)], "fill": 1.0,
            "surface_z": 600.0, "y_zero": 0.0, "feet": 0,
            "merged_into": "w.obj", "elevated": True}
    splits = [{"placement": {"index": 1, "lat": 40.0, "lon": -3.0},
               "bodies": [walls]},
              {"placement": {"index": 2, "lat": 40.0, "lon": -3.0},
               "bodies": [bad]},
              {"placement": {"index": 3, "lat": 40.0, "lon": -3.0},
               "bodies": [roof]}]
    # the mis-anchored body is the one the FOOTPRINT reading picks (it
    # covers the roof exactly, and of two bodies over one the smaller is
    # what it stands on) — which is why the pre-11ak census reported
    # +7 m of float here.  The FOOTED body beside it reads that way
    # still: it takes no carrier, and what it stands over is the
    # question.
    footed = dict(roof, new_resource="f.obj", merged_into=None, feet=4,
                  elevated=False, ground_off=0.0)
    fs = splits[:2] + [{"placement": {"index": 4, "lat": 40.0, "lon": -3.0},
                        "bodies": [footed]}]
    assert _PC.census_v15(fs, (), ground_tol_m=0.3)["footed_worst"][0][2] \
        == "bad.obj"
    # the law's own reading: the carrier it chose, and the refused body
    # counted as what it is
    c = _PC.census_v15(splits, (), ground_tol_m=0.3)
    assert c["carried_float_gt"] == 0 and c["bars_ok"] is True
    assert c["refused_as_carrier"] == 1
    assert c["carried_over_refused"] == 1
    assert c["carried_over_refused_worst"][0][1] == "r.obj"
    assert "own feet off by 2.00 m" in c["carried_over_refused_worst"][0][2]
    lines = "\n".join(_PC.census_v15_lines(c))
    assert "carried over a REFUSED body" in lines


def _ramp(x1=30.0, slope=0.2, n=30, half_z=2.0):
    """ONE WELDED ribbon rising with ``x`` — the shape of a body whose own
    FEET are authored over metres of relief while the ground under it
    barely moves (LEMD's ``green-PKT4``, 7.4 m of authored fall on 0.5 m
    of terrain).  One component, so no PART cut can divide it."""
    v, t = [], []
    for k in range(n + 1):
        x = x1 * k / n
        v += [(x, x * slope, -half_z), (x, x * slope, half_z)]
    for k in range(n):
        a, b, c, d = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        t += [(a, b, d), (a, d, c)]
    return v, t


def test_a_body_whose_own_feet_are_off_the_ground_is_re_cut_by_its_feet(tmp_path):
    """11ak (2) / §16 (2): A FOOTED BODY MIS-ANCHORED ON ITS OWN FEET IS
    RE-CUT BY THEM.

    Neither §16 (2) cut can see this class: the ground under the body is
    FLAT, so the part cut reads one zero and the triangle cut's own
    pre-test never fires, while the body's FEET are authored over 4 m and
    §6 drops the whole body to its low-side foot.  That is exactly the
    body §16a (2) then refuses as a carrier — LEMD 117 of them, and the
    roofs over them ride whatever the search reaches next.

    Cut by its feet, each piece anchors on feet that meet the ground."""
    from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

    v, t = _ramp()
    path = _write_obj(tmp_path / "stair.obj", v, [("", t)])
    ml, mo = AR._m_per_deg(40.0)
    # ONE part, ONE component, THREE feet — the authored (x, z) -> plan
    # map of ``authored_latlon`` puts x on the LONGITUDE axis
    feet = tuple((40.0, -3.0 + x / mo, x * 0.2)
                 for x in (0.0, 10.0, 20.0))
    part = Part(pid=0, comp=0, lat=40.0, lon=-3.0 + 15.0 / mo, base_y=0.0,
                area_m2=120.0,
                box=(40.0 - 2.0 / ml, -3.0, 40.0 + 2.0 / ml, -3.0 + 30.0 / mo),
                feet=feet)
    m = Member(id="dsf:obj1", resource="objects/stair.obj",
               authored_path=str(path), live_path=str(path),
               heading_deg=0.0, parts=(part,))
    plan = RebakePlan(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
                      units=(Unit("u0", (40.0, -3.0), 0.0, (m,)),), skipped=(),
                      counts={})
    surface = _flat(600.0)
    # ``elevated_base_m`` is put out of the way so this twin reads the
    # CUT and nothing else: §13 still decides which pieces get files of
    # their own (a piece whose feet are authored metres up is ELEVATED
    # and joins the ground piece it stands over), and that is its own
    # law, twinned above.
    ss = PP.build_splits(plan, surface, write=False,
                         **_elev_args(elevated_base_m=10.0,
                                      line_stations_max=64))
    assert ss.counts.get("bodies_re_cut_by_foot") == 1
    assert ss.counts.get("terrain_foot_groups") == 3
    s = ss.all[0]
    assert len(s.bodies) == 3, [b.anchor.reason for b in s.bodies]
    # every piece now stands where its own feet say it does, so §16a (2)
    # accepts every one of them as a carrier
    assert sorted(round(b.anchor.surface_z - b.anchor.y_zero, 3)
                  for b in s.bodies) == [596.0, 598.0, 600.0]
    for b in s.bodies:
        assert b.ground_off is not None and b.ground_off <= 0.3, b.anchor.reason
    # ... and the whole body, uncut, is the body the law refuses
    cutter = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0)
    whole = _CUT._whole_body([part], m, plan.units[0], surface, (), (), 0.3)
    assert _PC.anchor_ground_off(whole[1], whole[2], surface) > 0.3
    assert len(cutter.foot_groups([part], surface, 0.3, 64)) == 3


def test_a_deck_on_a_kept_whole_carrier_names_that_carrier(tmp_path):
    """11ak (3), OTHH's bus-bridge decks: the carrier is a placement
    written WHOLE, so ``merged_into`` names its MEMBER RESOURCE and not a
    body file — and a census that resolves the law's carrier only among
    body files finds nothing and falls back to whatever the deck's
    footprint lies over.  That is the whole of OTHH's residual: every one
    of the ten was a deck on a ramp, measured against the road body on
    the ground beside it (+4.36 m of float no placement decision made).

    Not the shared-zero collapse: the deck IS cut across its carriers —
    the collapse only drops a candidate standing within ``split_tol_m``
    of one already kept, and a ramp's groups stand metres apart."""
    box = (40.0, -3.0, 40.0004, -2.9996)
    # the deck stands over BOTH, and of two bodies that cover it the
    # SMALLER is what the footprint reading picks: the road
    small = (40.0, -3.0, 40.0002, -2.9998)
    # the ramp: ONE body, kept whole, its file named without a __b suffix
    ramp = {"new_resource": "ramp__b0.obj", "class": AR.BUILDING,
            "plan_box": list(box), "foot_boxes": [list(box)], "fill": 1.0,
            "surface_z": 600.0, "y_zero": -4.36, "feet": 8,
            "merged_into": None, "ground_off": 0.0}
    road = {"new_resource": "road__b0.obj", "class": AR.BUILDING,
            "plan_box": list(small), "foot_boxes": [list(small)], "fill": 1.0,
            "surface_z": 600.0, "y_zero": 0.0, "feet": 8, "merged_into": None,
            "ground_off": 0.0}
    deck = {"new_resource": "deck__b3.obj", "class": AR.BUILDING,
            "plan_box": list(small), "foot_boxes": [list(small)], "fill": 1.0,
            "surface_z": 600.0, "y_zero": -4.36, "feet": 0,
            "merged_into": "objects/ramp.obj", "elevated": True}
    splits = [{"placement": {"index": 1, "lat": 40.0, "lon": -3.0,
                             "resource": "objects/ramp.obj"},
               "bodies": [ramp]},
              {"placement": {"index": 2, "lat": 40.0, "lon": -3.0,
                             "resource": "objects/road.obj"},
               "bodies": [road]},
              {"placement": {"index": 3, "lat": 40.0, "lon": -3.0,
                             "resource": "objects/deck.obj"},
               "bodies": [deck]}]
    c = _PC.census_v15(splits, (), ground_tol_m=0.3)
    assert c["carried_float_gt"] == 0 and c["bars_ok"] is True
    assert c["carried_no_law_carrier"] == 0
    # ... and with the kept-whole key gone the census cannot name the
    # carrier and reports the deck as 4.36 m over the ROAD beside it
    blind = [dict(s, placement={k: v for k, v in s["placement"].items()
                                if k != "resource"}) for s in splits]
    b = _PC.census_v15(blind, (), ground_tol_m=0.3)
    assert b["carried_float_gt"] == 1
    assert b["carried_worst"][0][2] == "road__b0.obj"
    assert b["carried_no_law_carrier"] == 1
