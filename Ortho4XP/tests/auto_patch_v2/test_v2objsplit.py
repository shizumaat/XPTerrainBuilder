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
