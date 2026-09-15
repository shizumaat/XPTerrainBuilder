"""THE OBJ8 SPLIT WRITER AND THE ANCHOR RULE (spec
``object-placement-spec.md`` §4 / §6; owner RULINGS 2026-09-11b).

The twins are synthetic and hermetic: a hand-built OBJ8 with two boxes,
an ``ATTR_LOD`` bracket over both and an ``ANIM`` block on one box's wall
— exactly the shape §4 names — cut, written, and read back through the
engine's OWN reader (``airport/obj8.parse_obj8``), because "it parses"
means the readers downstream accept it, not that the text looks right.
"""
from __future__ import annotations

import re as _re
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
    # 14at: the name carries the OFFSET THE FILE BAKES beside the body id
    assert [f.resource for f in res.files] == [
        OS.body_resource_name("objects/twobox.obj", 0, (1.0, 2.0, 3.0)),
        OS.body_resource_name("objects/twobox.obj", 1, (-5.0, 0.0, 7.0))]
    assert [f.resource for f in res.files] == [
        f"objects/twobox__b0_{OS.offset_tag((1.0, 2.0, 3.0))}.obj",
        f"objects/twobox__b1_{OS.offset_tag((-5.0, 0.0, 7.0))}.obj"]
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
    ga = obj8.parse_obj8(str(tmp_path / res.files[0].resource.replace("/", "_")))
    xs = sorted({round(float(x), 3) for x in ga.vertices[:, 0]})
    # box A spans x 0..4 authored, minus dx = 1  ->  -1 .. 3, and the four
    # door vertices stay AUTHORED (rule 4) at 0 and 4
    assert -1.0 in xs and 3.0 in xs and 0.0 in xs and 4.0 in xs
    gb = obj8.parse_obj8(str(tmp_path / res.files[1].resource.replace("/", "_")))
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
    the low-side foot and the reason carries the residual.

    AND IT IS NAMED FOR WHAT IT IS ((E), owner RULINGS 2026-09-12ap):
    every foot of this body is authored at y = 0 — dead flat, no authored
    relief anywhere in it — and the 5.56 m is entirely the TERRAIN's fall
    under it.  Printing that as the model's own relief is what sent
    12ao's attribution table the wrong way."""
    def surface(lat, lon):
        return 100.0 + (lat - 40.0) * 111_132.0      # 1 m per 9 µdeg

    g = _geom([(40.00000, -3.0, 0.0, ((40.00000, -3.0, 0.0),)),
               (40.00005, -3.0, 0.0, ((40.00005, -3.0, 0.0),)),
               (40.00010, -3.0, 0.0, ((40.00010, -3.0, 0.0),))])
    a = AR.anchor_for(AR.SKIRTED, g, surface, tol_m=0.3)
    assert a.reason.startswith("low-side foot (no point within 0.3 m")
    assert "terrain spread 5.56 m" in a.reason
    assert "authored relief" not in a.reason
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


# ── §9 / 11e (3): THE WRITE HALF ────────────────────────────

# THE GATE IS GONE (owner RULINGS 2026-09-12s, spec §8): the twin that
# stood here pinned ``[rebake] placement`` defaulting to ``agl`` and the
# ``seat`` arm producing identical bytes.  The seat is DELETED, the key
# with it, and the placement path is the only object stage — there is no
# gate left to pin.


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


def test_rows_near_selects_the_same_rows_BY_PLACE(tmp_path):
    """``--rows-near`` (lane ``v2padcluster``, 2026-09-14; promoted from
    the `v2heca331` scout's `site.py` on its SECOND use) is the SAME
    projection selected by COORDINATE instead of by resource — the owner
    names a defect by place, and the shapeIDs in a report go stale
    between builds while a coordinate does not.

    It changes what is reported, never what is measured; the distance is
    the body's ANCHOR to the point; and the rows come back nearest
    first."""
    RPT, ss, sampler = _split_set_for_rows(tmp_path)
    by_name = RPT.census(ss, sampler, 1.0, rows_of=("bld.obj",))
    b0 = by_name["rows"][0]
    lat, lon = b0["anchor"]

    plain = RPT.census(ss, sampler, 1.0)
    near = RPT.census(ss, sampler, 1.0, near=(lat, lon, 5.0))
    # the MEASUREMENT is untouched
    assert near["bins"] == plain["bins"] == by_name["bins"]
    assert near["feet"] == plain["feet"]
    assert near["worst"] == plain["worst"]

    assert near["rows"], "the body at its own anchor must be selected"
    got = {(r["resource"], r["body"]) for r in near["rows"]}
    assert (b0["resource"], b0["body"]) in got
    # every selected row carries its distance, and they are nearest first
    ds = [r["site_m"] for r in near["rows"]]
    assert ds == sorted(ds) and ds[0] <= 5.0
    assert all(d <= 5.0 for d in ds)

    # a radius of 0 at a point far from everything selects nothing; the
    # census itself still reports its whole population
    far = RPT.census(ss, sampler, 1.0, near=(lat + 1.0, lon + 1.0, 5.0))
    assert far["rows"] == [] and far["bins"] == plain["bins"]

    # ... and the row a place selects is the SAME row the resource
    # selects, field for field (bar the distance the place read adds)
    same = next(r for r in near["rows"]
                if (r["resource"], r["body"]) == (b0["resource"], b0["body"]))
    assert {k: v for k, v in same.items() if k != "site_m"} == b0


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
    a = dict(split_tol_m=0.3, elevated_base_m=_ELEV, bind_ground_m=0.5)
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
    # §16d (4) (RULINGS 2026-09-13m): the placement's two BOXES are two
    # ATOMS and each asks its own carrier question, so each takes its own
    # ground — one file per atom, not one rigid pair at one zero.
    assert ss.counts["footless_own_ground"] == 2
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
    # §16c (7) AMENDS THE REASON, not the answer: the deck and the
    # terminal are in ε-contact, so they are ONE RIGID CLUSTER and the
    # deck rides the cluster's senior — which is the same body the
    # "abuts 1 part contact" fallback used to name, at the same zero.
    assert "§16c (7) bound by contact" in b.anchor.reason
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
    # §16b (3): THE FALLBACK CARRIER IS BOUNDED.  "Nearest" is not
    # evidence about the ground under the carried piece — at LEMD it put
    # T4's roof and its road deck on the PARKING GARAGE across the road,
    # 4 m under the ground beneath them (11ap item 4) — so on a slope
    # where the nearest body's zero stands more than ``split_tol_m`` from
    # the ground under the ROOF, the candidate is refused and the piece
    # takes its own ground.  §16a (2)'s carrier-side test is untouched.
    ss2 = PP.build_splits(plan, surface, write=False, **_elev_args())
    r2 = [s for s in ss2.all if s.resource == "objects/roof.obj"][0]
    assert not r2.bodies[0].merged_into
    assert PP.OWN_GROUND in r2.bodies[0].anchor.reason
    assert ss2.counts.get("carrier_refused_far_from_carried_ground", 0) >= 1
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
    assert bridge[0].files[0].resource == OS.body_resource_name(
        "objects/bridge.obj", 0, bridge[0].files[0].offset)
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
    assert built is not None                    # footless is admitted
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

    §16b (1) SUPERSEDES §16a (1)'s reading of the same strip raised: the
    terrain cut is PRIOR AND UNIVERSAL, so a CARRIED body is divided by
    the ground under its own written geometry too, and §16a (1)'s carrier
    cut then runs inside each piece.  §16a left it whole, and LEMD's
    `green-TEJ3` rode ONE carrier across 2 km — +10.74 m at the owner's
    item 3 and +16.22 m at item 5 (11ap)."""
    ml, _mo = AR._m_per_deg(40.0)
    span = 600.0
    # §16c (1) AMENDS THIS TWIN: the cut's atom is the connected
    # COMPONENT, so the 600 m sheet is authored as SEPARATE panels — the
    # welded one is written whole by law now
    # (``test_no_cut_crosses_a_connected_component``), and what this twin
    # reads is that a scattered resource is still divided by the ground.
    v, tris = [], []
    n = 13
    for k in range(n - 1):
        za = -k * span / (n - 1)
        zb = za - 0.9 * span / (n - 1)   # a GAP: touching panels weld
        i = len(v)
        v += [(0.0, 0.0, za), (20.0, 0.0, za), (0.0, 0.0, zb), (20.0, 0.0, zb)]
        tris += [(i, i + 1, i + 3), (i, i + 3, i + 2)]
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
    assert ss2.counts.get("carried_bodies_uncut", 0) == 0
    assert ss2.counts.get("carried_bodies_cut_by_own_ground") == 1
    assert ss2.counts.get("carried_own_ground_pieces", 0) >= 3
    # and every piece stands on ground of its own within the tolerance
    for s2 in ss2.all:
        for b2 in s2.bodies:
            zs2 = [surface(q[0], q[1]) for q in b2.geom_pts]
            zs2 = [z for z in zs2 if z is not None]
            if len(zs2) > 1:
                assert max(zs2) - min(zs2) <= 1.0


def test_a_fence_never_carries_and_a_mis_anchored_carrier_is_refused():
    """§16 (3): A CARRIER IS A SOLID.  A fence segment's axis-aligned plan
    box contains the garage roof its footprint never touches — which is
    how LEMD's ``PKT4__b1`` came to ride ``LEMDzaun__b5`` 6 m under the
    slab.  A LINE body never carries.

    12j AMENDS IT: the CLASS exclusion is the whole rule and the
    ``carrier_fill_min`` FRACTION is DELETED — it struck the thin wall
    RINGS the T2 roofs actually rest on (`LEMD54` / `LEMD59`, fill
    0.005-0.031, overlapping every roof and passing the ground test)
    before §16c (4) could rank them.  A thin GRASS strip is therefore no
    longer refused by a fraction; what keeps it from carrying a roof is
    the rest-on ranking and, where it is a line object, its class.

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
    args = dict(tol_m=0.3)
    c, why = _PC.carrier_for(frozenset({9}), roof_box, [fence, grass, walls], {},
                             [roof_box], **args)
    assert c is walls and "stands over" in why   # not the fence
    # the same walls, now standing 6 m off the ground under their OWN feet:
    # mis-anchored, refused, and the search goes on
    refusals: dict = {}
    bad = _cand(2, AR.BUILDING, walls_box, [walls_box], 106.0, ground_off=6.0)
    c2, _w = _PC.carrier_for(frozenset({9}), roof_box, [fence, grass, bad], {},
                             [roof_box], refusals=refusals, **args)
    # the GRASS is not refused by a fraction any more, so the search
    # reaches it — and a thin strip 1 km long is exactly what the fill
    # gate existed to stop, so the twin below pins what replaces it
    assert refusals.get("line") == 1 and "fill" not in refusals
    assert c2 is grass


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


def _panels(x0, x1, y, n, z0=-10.0, z1=10.0):
    """The same sheet as ``_strip``, authored as ``n`` SEPARATE quads —
    §16c (1): the cut's atom is the connected COMPONENT, so a sheet the
    cut may divide is one that is authored in pieces.  A welded one is
    written whole (``test_no_cut_crosses_a_connected_component``), and
    under §16c (7) so is one whose pieces stand within
    ``[placement] rigid_reach_m`` — hence the half-panel GAP here."""
    v, t = [], []
    step = (x1 - x0) / n
    for k in range(n):
        a = x0 + step * k
        b = a + 0.5 * step        # a GAP beyond §16c (7)'s rigid reach
        i = len(v)
        v += [(a, y, z0), (a, y, z1), (b, y, z0), (b, y, z1)]
        t += [(i, i + 1, i + 3), (i, i + 3, i + 2)]
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
    return _re.sub(r"__b\d+(?:_[0-9a-f]{8})?\.obj$", ".obj", b.merged_into)


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
    # §16c (1): SEPARATE panels — a WELDED plate is one atom and rides
    # one carrier whole, which is the law this twin's sibling reads
    rv, rt = _panels(-10.0, 50.0, 6.0, 12)
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
    # §16d (4) (RULINGS 2026-09-13m) DIVIDES THE BODY BEFORE THE SEARCH:
    # each ATOM asks its own carrier question, so the division is counted
    # as ``carried_bodies_cut_by_atom`` and §16a (1)'s after-the-fact cut
    # has nothing left to do.  The OUTCOME this twin reads — one piece per
    # carrier, each at that carrier's zero — is asserted above and is
    # unchanged.
    assert ss.counts.get("carried_bodies_cut_by_atom", 0) >= 1
    # ... and the ground under the roof itself was never asked
    assert ss.counts.get("bodies_re_cut_by_triangle", 0) == 0


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
    rv, rt = _panels(-10.0, 90.0, 6.0, 20)      # §16c (1): separate atoms
    roof = _write_obj(tmp_path / "roof.obj", rv, [("", rt)])
    plan = _unit_plan([
        (walls, [(0, 0.0, 0.0, 0.0, 0.0, 10.0),
                 (1, 0.0, 0.0, 40.0, 0.0, 10.0),
                 (2, 0.0, 0.0, 80.0, 0.0, 10.0)], "objects/walls.obj"),
        (roof, [(0, 6.0, 0.0, 40.0, 6.0, 50.0)], "objects/roof.obj"),
    ])
    # §16c (6) AMENDS THIS FIXTURE: the three wall boxes stand 40 m apart
    # and were DECLARED in ε-contact, which now makes them ONE rigid
    # cluster no cut may divide.  They are what they look like — three
    # separate buildings — so the contact is dropped and each is its own
    # body from the start; what the twin reads is unchanged, that the
    # ROOF over them is cut into one piece per carrier.
    surface = _stepped([(-12.0, 12.0, 600.0), (28.0, 52.0, 605.0),
                        (68.0, 92.0, 610.0)])
    ss = PP.build_splits(plan, surface, write=False, **_elev_args())
    w = [s for s in ss.all if s.resource == "objects/walls.obj"][0]
    assert len(w.bodies) == 3                     # the walls' own terrain groups
    r = [s for s in ss.all if s.resource == "objects/roof.obj"][0]
    assert len(r.bodies) == 3, [b.merged_into for b in r.bodies]
    # §16d (4): the division is per ATOM, asked before the search
    assert ss.counts.get("carried_bodies_cut_by_atom", 0) >= 1
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


def test_a_basin_body_is_never_refused_as_a_carrier():
    """RULINGS 2026-09-11al: §16a (2)'s ground test does NOT read a BASIN
    body.

    A basin's zero is its RIM (§14 (2)) — the pit was cut to the object —
    and its floor feet are authored metres BELOW that zero by
    construction, so ``anchor_ground_off``, which reads the feet, refuses
    every pit for a reason that is the basin law working (13 of LEMD's 21
    refused carriers, the worst 6.17 m).  A basin may carry: the T4S
    tower cluster rides its rim.

    Here the basin's floor feet read 7 m below its rim zero.  A BUILDING
    with the same reading is refused; the basin carries the footless
    tower standing over its rim, and the census counts it under
    ``basin carriers`` rather than in the refusal set."""
    def _cand(member, cls, box, z, ground_off):
        return _PC.Candidate(member, f"objects/c{member}.obj",
                             AR.Anchor(cls, 0.5 * (box[0] + box[2]),
                                       0.5 * (box[1] + box[3]), 0.0, "r", z),
                             frozenset({member}), 4, box, part_boxes=[box],
                             group=0, body_class=cls,
                             fill=1.0, ground_off=ground_off)

    pit_box = (40.0040, -3.0010, 40.0050, -3.0000)
    tower_box = (40.0042, -3.0008, 40.0048, -3.0002)
    args = dict(tol_m=0.3)
    # the SAME body, read as a building: mis-anchored on its own feet
    refusals: dict = {}
    bldg = _cand(2, AR.BUILDING, pit_box, 600.0, 7.0)
    c, _w = _PC.carrier_for(frozenset({9}), tower_box, [bldg], {},
                            [tower_box], refusals=refusals, **args)
    assert c is None and refusals.get("zero_off_ground") == 1
    # as a BASIN it is exempt, and carries
    refusals2: dict = {}
    basin = _cand(2, AR.BASIN, pit_box, 600.0, 7.0)
    c2, why = _PC.carrier_for(frozenset({9}), tower_box, [basin], {},
                              [tower_box], refusals=refusals2, **args)
    assert c2 is basin and "stands over" in why
    assert "zero_off_ground" not in refusals2

    # ... and the census counts it as a basin carrier, not a refusal
    def _body(res, cls, box, sz, off):
        return {"new_resource": res, "plan_box": list(box), "surface_z": sz,
                "y_zero": 0.0, "class": cls, "fill": 1.0, "ground_off": off,
                "foot_boxes": [list(box)], "feet": 4}

    splits = [{"unit": "unit:1", "resource": "objects/pit.obj",
               "bodies": [_body("objects/pit__b0.obj", "basin", pit_box,
                                600.0, 7.0)]},
              {"unit": "unit:1", "resource": "objects/tower.obj",
               "bodies": [_body("objects/tower__b0.obj", "building",
                                tower_box, 600.0, 0.0)]}]
    c15 = _PC.census_v15(splits, ground_tol_m=0.3)
    assert c15["refused_as_carrier"] == 0
    assert c15["basin_carriers"] == 1 and c15["basin_carriers_exempt"] == 1
    assert any("basin carriers" in ln for ln in _PC.census_v15_lines(c15))


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

    # §16c (1) AMENDS THIS TWIN: the cut's atom is the connected
    # COMPONENT, so the ribbon is authored as three SEPARATE treads.  The
    # class is unchanged — the ground under them is flat and their FEET
    # are authored over 4 m — and so is what the cut must do.
    v, t = [], []
    for k in range(3):
        x0 = 10.0 * k
        i = len(v)
        v += [(x0, x0 * 0.2, -2.0), (x0, x0 * 0.2, 2.0),
              (x0 + 9.0, (x0 + 9.0) * 0.2, -2.0),
              (x0 + 9.0, (x0 + 9.0) * 0.2, 2.0)]
        t += [(i, i + 1, i + 3), (i, i + 3, i + 2)]
    path = _write_obj(tmp_path / "stair.obj", v, [("", t)])
    ml, mo = AR._m_per_deg(40.0)
    # THREE parts, three components, one foot each — the authored
    # (x, z) -> plan map of ``authored_latlon`` puts x on the LONGITUDE
    # axis; the ε-contact graph welds them into ONE body
    parts = tuple(
        # base_y 0 for all three: the ground under them is FLAT and the
        # PART cut has nothing to divide — what disagrees is their FEET,
        # which is the class this twin reads (the original's one part
        # carried all three feet)
        Part(pid=k, comp=k, lat=40.0, lon=-3.0 + (10.0 * k + 4.5) / mo,
             base_y=0.0, area_m2=40.0,
             box=(40.0 - 2.0 / ml, -3.0 + 10.0 * k / mo,
                  40.0 + 2.0 / ml, -3.0 + (10.0 * k + 9.0) / mo),
             feet=((40.0, -3.0 + 10.0 * k / mo, 10.0 * k * 0.2),))
        for k in range(3))
    part = parts[0]
    m = Member(id="dsf:obj1", resource="objects/stair.obj",
               authored_path=str(path), live_path=str(path),
               heading_deg=0.0, parts=parts)
    plan = RebakePlan(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
                      units=(Unit("u0", (40.0, -3.0), 0.0, (m,)),),
                      contacts=((0, 1), (1, 2)), skipped=(), counts={})
    surface = _flat(600.0)
    # ``elevated_base_m`` is put out of the way so this twin reads the
    # CUT and nothing else: §13 still decides which pieces get files of
    # their own (a piece whose feet are authored metres up is ELEVATED
    # and joins the ground piece it stands over), and that is its own
    # law, twinned above.
    # §16c (6) SUPERSEDES 11ak (2) FOR A CONTACT-BOUND BODY, and this is
    # the reading that says so: the plan's own ε-contact graph links
    # these three treads, so they are ONE rigid cluster — one zero, one
    # carrier — and no cut may divide them by their feet.  The class 11ak
    # named is not gone: it is now REPORTED as the body §16a (2) refuses
    # (its own feet disagree), which is what the refusal set counts.
    ss = PP.build_splits(plan, surface, write=False, contact_eps_m=0.002,
                         **_elev_args(elevated_base_m=10.0,
                                      line_stations_max=64))
    s = ss.all[0]
    assert len(s.bodies) == 1, [b.anchor.reason for b in s.bodies]
    assert ss.counts.get("bodies_re_cut_by_foot", 0) == 0
    # UNBOUND — no contact graph, no reach — the same three treads are
    # three atoms and the terrain/foot reading divides them as before
    import dataclasses as _dcm
    plan2 = _dcm.replace(plan, contacts=())
    ss2 = PP.build_splits(plan2, surface, write=False,
                          **_elev_args(elevated_base_m=10.0,
                                       line_stations_max=64))
    assert len(ss2.all[0].bodies) == 3
    assert sorted(round(b.anchor.surface_z - b.anchor.y_zero, 3)
                  for b in ss2.all[0].bodies) == [596.0, 598.0, 600.0]
    for b in ss2.all[0].bodies:
        assert b.ground_off is not None and b.ground_off <= 0.3, b.anchor.reason
    # ... and the whole body, uncut, is the body the law refuses
    cutter = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0)
    whole = _CUT._whole_body(list(parts), m, plan.units[0], surface, (), (), 0.3)
    assert _PC.anchor_ground_off(whole[1], whole[2], surface) > 0.3
    fg = cutter.foot_groups(list(parts), surface, 0.3, 64)
    assert len(fg) >= 2
    # §16c (1): every piece is a WHOLE number of components — a tread
    # whose two triangles vote for different feet goes to one of them
    # entire, never half each
    seen: set = set()
    for tris_, _feet in fg:
        cs = set(cutter.comp_of(list(tris_)))
        assert not (cs & seen), "a component landed in two foot groups"
        seen |= cs
    # §16c (1) AMENDS 11ak (2) AND THIS IS ITS COST, NAMED: authored as
    # ONE WELDED component the same ribbon cannot be cut at all — the
    # connected component is the atom, a component wider than its
    # terrain stays whole, and the body is then the one §16a (2) REFUSES
    # as a carrier.  Cutting it would tear the solid, which is the
    # defect the owner read at 1.0.320 (RULINGS 2026-09-12d).
    wv, wt = _ramp()
    wpath = _write_obj(tmp_path / "welded.obj", wv, [("", wt)])
    wpart = Part(pid=0, comp=0, lat=40.0, lon=-3.0 + 15.0 / mo, base_y=0.0,
                 area_m2=120.0,
                 box=(40.0 - 2.0 / ml, -3.0, 40.0 + 2.0 / ml,
                      -3.0 + 30.0 / mo),
                 feet=tuple((40.0, -3.0 + x / mo, x * 0.2)
                            for x in (0.0, 10.0, 20.0)))
    wm = Member(id="dsf:obj1", resource="objects/welded.obj",
                authored_path=str(wpath), live_path=str(wpath),
                heading_deg=0.0, parts=(wpart,))
    wplan = RebakePlan(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
                       units=(Unit("u0", (40.0, -3.0), 0.0, (wm,)),),
                       skipped=(), counts={})
    ss2 = PP.build_splits(wplan, surface, write=False,
                          **_elev_args(elevated_base_m=10.0,
                                       line_stations_max=64))
    assert ss2.counts.get("bodies_re_cut_by_foot", 0) == 0
    assert ss2.counts.get("bodies") == 1
    wcut = _CUT._LineCutter(wm, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0)
    assert wcut.foot_groups([wpart], surface, 0.3, 64) == []


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


# ── §14a THE BASIN BODY FOLLOWS ITS RING (RULINGS 2026-09-11ap item 6) ───

def test_the_basin_ring_is_cut_into_arcs_that_agree_within_the_tolerance():
    """§14a (1): ``arcs_of`` walks the ring ONCE and cuts it where the
    apron steps.

    Every arc is at most ``tol_m`` wide, and its RIM POINT — the piece's
    zero — is within half of that of every node it covers, which is what
    makes the bar of §14a (4) reachable at all.  ``tol_m <= 0`` disarms
    the cut and restores §14 (2)'s single rim point."""
    from auto_patch_v2.airport import basin_ring as BR

    ml, mo = AR._m_per_deg(40.0)
    n = 12
    ring = tuple((40.0 + math.cos(2 * math.pi * k / n) * 30.0 / ml,
                  -3.0 + math.sin(2 * math.pi * k / n) * 30.0 / mo)
                 for k in range(n))
    # a ring that steps: half of it at 100.0, half 1.5 m higher
    z = [100.0 if k < 6 else 101.5 for k in range(n)]
    arcs = BR.arcs_of(z, ring, 0.3, 64)
    assert len(arcs) == 2
    assert sum(len(a.nodes) for a in arcs) == n
    for a in arcs:
        zs = [z[j] for j in a.nodes]
        assert max(zs) - min(zs) <= 0.3
        assert max(abs(a.z - q) for q in zs) <= 0.15 + 1e-9
        assert (a.lat, a.lon) in ring
    assert [a.index for a in arcs] == [0, 1] and arcs[0].total == 2
    # disarmed
    assert len(BR.arcs_of(z, ring, 0.0, 64)) == 1
    assert BR.arcs_of(z, ring[:3], 0.3, 64) == ()


def test_the_basin_ring_bar_reads_the_wall_base_against_the_apron():
    """§14a (4): the ``spread`` bar re-defined — ``max |wall base − ring
    z|`` over the ring's own nodes, which is the gap the owner reads.

    §14's reading (the pit's bodies against EACH OTHER) was 0.01 m at
    LEMD while the wall stood 1.13 m off the apron.  A node on an arc no
    piece was cut to reads the pit's single piece; one on an arc the pit
    has NO WALL on is reported beside the bar, never inside it."""
    from auto_patch_v2.airport import basin_ring as BR

    ml, mo = AR._m_per_deg(40.0)
    n = 12
    ring = tuple((40.0 + math.cos(2 * math.pi * k / n) * 30.0 / ml,
                  -3.0 + math.sin(2 * math.pi * k / n) * 30.0 / mo)
                 for k in range(n))
    z = [100.0 if k < 6 else 101.5 for k in range(n)]
    # BEFORE: one piece at one zero over a ring that spans 1.5 m
    before = BR.ring_bar(z, ring, {}, 100.0, 0.3, 64)
    assert before["covered"] == n and before["over_tol"] == 6
    assert abs(before["worst"] - 1.5) < 1e-9
    # AFTER: a piece per arc
    arcs = BR.arcs_of(z, ring, 0.3, 64)
    after = BR.ring_bar(z, ring, {k: a.z for k, a in enumerate(arcs)},
                        100.0, 0.3, 64)
    assert after["over_tol"] == 0 and after["worst"] <= 0.3
    # an arc the pit has NO WALL on is reported, not barred
    part = BR.ring_bar(z, ring, {0: arcs[0].z}, 100.0, 0.3, 64,
                       wall_arcs={0})
    assert part["over_tol"] == 0 and part["fallback"] == len(arcs[1].nodes)
    assert abs(part["fallback_worst"] - 1.5) < 1e-9


def test_the_basin_ring_wire_agrees_with_its_readers():
    """§14a's ONE wire between the cut, which reads geometry, and the
    bars, which read the plan: the anchor REASON and the ``counts`` key.

    A reader that spelled either differently would report a pit that
    follows its ring as one that does not — silently, because both halves
    look right on their own (the census-wrapper defect, CLAUDE.md)."""
    from auto_patch_v2.airport import basin_ring as BR
    from auto_patch_v2.constraints.foot_rows import BASIN_WALL_REF

    assert BR.BASIN_WALL_REF == BASIN_WALL_REF
    assert BR.is_basin_ring("basin_wall:0@851")
    assert not BR.is_basin_ring("tunnel_wall@935")

    ref = "basin_wall:0@851"
    ring = ((40.0, -3.0), (40.001, -3.0), (40.001, -3.001))
    arc = BR.Arc(2, 6, (0, 1), ring[0][0], ring[0][1], 598.4)
    a = BR.arc_anchor(2, (None, None, arc), AR.Anchor(
        AR.BASIN, 40.0, -3.0, 0.0, "x", 598.0), AR.RimRing(ref, ring), lambda la, lo: 598.4)
    assert BR.arc_index_of(a.reason) == 2
    assert BR.ring_ref_of(a.reason) == ref
    assert BR.bind_key_of(a.reason) == f"{ref}#arc2"
    whole = AR.Anchor(AR.BASIN, 40.0, -3.0, 0.0,
                      f"basin rim ({ref}): the object's zero is the rim", 598.4)
    inner = BR.arc_anchor(-1, (arc,), whole, AR.RimRing(ref, ring),
                                   lambda la, lo: 598.4)
    assert BR.arc_index_of(inner.reason) is None
    assert BR.bind_key_of(inner.reason) == f"{ref}#interior"
    assert BR.bind_key_of(whole.reason) == f"{ref}#rim"
    # a TUNNEL ring keys on nothing: §6's tunnel row is untouched by §14a
    assert BR.bind_key_of("basin rim (tunnel_wall@935): the object's zero "
                          "is the rim") == ""
    # the FLOOR mark, and the counts key
    marked = _CUT._floor_member(([], AR.OTHER, whole, (), False, ()), ref)
    assert BR.bind_key_of(marked[2].reason) == f"{ref}#floor"
    counts = {BR.wall_arc_key(ref, 0): 1, BR.wall_arc_key(ref, 4): 1,
              "placements": 3}
    assert BR.wall_arcs_of(counts, ref) == {0, 4}
    assert BR.wall_arcs_of({"placements": 3}, ref) is None
    # a WRITTEN plan keeps the split half's tally under ``provenance``;
    # a tool reading the top-level ``counts`` alone loses the wall arcs
    # and reports a pit that follows its ring as one that does not
    doc = {"counts": {"new_resources": 7}, "provenance": {"counts": counts}}
    assert BR.wall_arcs_of(BR.plan_counts(doc), ref) == {0, 4}


def test_a_member_standing_in_the_pit_is_a_floor_body_not_a_rim_one():
    """§14a (2): the pit's SHELL rides the rim; a body that merely STANDS
    IN the ring does not.

    What tells them apart is the RIM PLANE: the shell is authored into
    the pit, a thing standing in it is authored at the rim like anything
    else on the ground.  (Read on containment alone the pit's own wall
    comes out "inside" — LEMD's ``LEMDzaun`` 60 % by ray casting — and
    the wall would be sent to the floor.)"""
    from auto_patch_v2.airport import basin_ring as BR

    tol = 0.3
    # the shell: authored into the pit, wholly interior
    assert BR.member_kind(1.0, -7.03, tol) == BR.RING
    assert BR.member_kind(1.0, -1.85, tol) == BR.RING
    # the slab at the rim plane, mostly interior: a FLOOR body
    assert BR.member_kind(0.76, -0.08, tol) == BR.FLOOR
    assert BR.member_kind(0.51, 0.0, tol) == BR.FLOOR
    # ... but not one mostly OUTSIDE the ring
    assert BR.member_kind(0.50, -0.08, tol) == BR.RING
    assert BR.member_kind(0.08, 0.0, tol) == BR.RING


def _m_per_deg_cold(lat: float) -> tuple[float, float]:
    """The formula behind ``anchor_rule._m_per_deg``, unmemoised."""
    import math
    r = math.radians(lat)
    return (111_132.954 - 559.822 * math.cos(2 * r) + 1.175 * math.cos(4 * r),
            111_412.84 * math.cos(r) - 93.5 * math.cos(3 * r))


def test_m_per_deg_memo_is_exact_and_order_independent():
    """RULINGS 2026-09-13df chip (lane ``memokey``): ``_m_per_deg`` used to
    key on ``int(lat * 1e4)`` and store the FIRST caller's value, so
    ``union_area_m2`` sampling a slab midpoint at 40.00009 N left key
    400000 holding 85393.88093 where a cold call at 40.0 gives
    85393.93697 — and ``test_a_basin_wall_follows_its_ring_...`` flipped
    serially after ``test_v2connector``.  Now the value under a key is
    the formula AT THE KEY'S LATITUDE: whoever asks first, every caller
    that lands on a key reads the same number, and the number is what a
    cold call at that latitude reads."""
    memo = AR._MPD
    saved = dict(memo)
    try:
        # the same key (round(lat * 1e4) == 400000), asked in both orders,
        # and a neighbour key: every reading is the cold formula at the
        # key's own latitude, never at the caller's.
        pairs = [(40.0, 40.00004), (40.00004, 40.0), (40.0, 40.00009),
                 (40.00009, 40.0), (-12.0322, -12.03215)]
        for first, second in pairs:
            memo.clear()
            a1 = AR._m_per_deg(first)
            b1 = AR._m_per_deg(second)
            memo.clear()
            b2 = AR._m_per_deg(second)
            a2 = AR._m_per_deg(first)
            assert a1 == a2 and b1 == b2, (first, second, a1, a2, b1, b2)
            for lat, got in ((first, a1), (second, b1)):
                key_lat = round(lat * AR._MPD_KEYS_PER_DEG) / AR._MPD_KEYS_PER_DEG
                assert got == _m_per_deg_cold(key_lat), (lat, got, key_lat)
        # the precedent, verbatim: the midpoint caller first, then 40.0 —
        # the fixture's 50 m ring node reads 50.0 either way.
        memo.clear()
        AR._m_per_deg(40.00009)
        _ml, mo = AR._m_per_deg(40.0)
        memo.clear()
        assert (_ml, mo) == AR._m_per_deg(40.0)
        assert mo == _m_per_deg_cold(40.0)[1]
        assert not ((50.0 / mo) * mo < 50.0)
    finally:
        memo.clear()
        memo.update(saved)


def _ring_fixture(tmp_path):
    """A pit whose CUT RING follows a stepped apron (§24 (1)): a 112 x 18 m
    rectangle whose western half stands at 100.0 and eastern half 1.5 m
    higher, with the pit's wall standing on the ring at each end and a
    slab authored AT THE RIM PLANE deep inside it."""
    ml, mo = AR._m_per_deg(40.0)

    def _b(x0, z0, y0, y1, side=4.0):
        v = [(x0, y0, z0), (x0 + side, y0, z0), (x0 + side, y0, z0 + side),
             (x0, y0, z0 + side), (x0, y1, z0), (x0 + side, y1, z0),
             (x0 + side, y1, z0 + side), (x0, y1, z0 + side)]
        t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
             (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
        return v, t

    # the WALL: two boxes authored 7 m into the pit, straddling the ring's
    # northern edge at lon +0..4 m (west arc) and +100..104 m (east arc)
    va, ta = _b(0.0, 0.0, -7.0, 0.0)
    vb, tb = _b(100.0, 0.0, -7.0, 0.0)
    pit = _write_obj(tmp_path / "pit.obj", va + vb,
                     [("", ta + [(a + 8, b + 8, c + 8) for a, b, c in tb])])
    # the SLAB: authored at the rim plane, wholly inside the ring
    vs, ts = _b(50.0, 8.0, -0.08, 1.0)
    slab = _write_obj(tmp_path / "slab.obj", vs, [("", ts)])

    # the ring: north edge at lat -2 m, south edge at lat -20 m
    nodes = []
    for lon_m in range(-2, 112, 4):
        nodes.append((2.0, float(lon_m)))
    for lon_m in range(110, -6, -4):
        nodes.append((20.0, float(lon_m)))
    ring = tuple((40.0 - a / ml, -3.0 + b / mo) for a, b in nodes)
    z = tuple(100.0 if b < 50.0 else 101.5 for _a, b in nodes)
    rims = (AR.RimRing("basin_wall:0@777", ring, z),)

    def surface(lat, lon):
        a = (40.0 - lat) * ml
        b = (lon + 3.0) * mo
        if 3.0 <= a <= 19.0 and -1.0 <= b <= 111.0:
            return 93.0                       # the trench floor
        return 100.0 if b < 50.0 else 101.5   # the apron, at the ring's level

    plan = _unit_plan([(pit, [(0, -7.0, -3.0, 2.0, -7.0, 2.0),
                              (1, -7.0, -3.0, 102.0, -7.0, 2.0)],
                        "objects/pit.obj"),
                       (slab, [(0, -0.08, -10.0, 52.0, -0.08, 2.0)],
                        "objects/slab.obj")])
    # ``_unit_plan`` places a part at ``lat + dlat_m / ml``, so the ring's
    # own offsets are taken the same way round
    return plan, rims, surface, ring, z


def test_a_basin_wall_follows_its_ring_and_a_slab_inside_takes_the_floor(tmp_path):
    """§14a (1) + (2) END TO END, and the bar of §14a (4).

    §14 (2) wrote every basin body at ONE rim point, so on a ring that
    follows the apron (§24 (1); LEMD's T4 pit runs 597.68 … 599.52) the
    wall base stood +0.71 m above the apron on one arc and −1.13 m below
    it on another — the owner's "small gap between wall and apron", read
    while the §14 ``spread`` bar said 0.01.  Here the ring steps 1.5 m:
    the wall is cut into one piece per ARC and each rides its own arc's
    level, and the slab authored AT THE RIM PLANE inside the ring — the
    loose white one in LEMD's garden — takes the ground under its own
    footprint instead of the rim."""
    from auto_patch_v2.airport import basin_ring as BR

    plan, rims, surface, ring, z = _ring_fixture(tmp_path)
    ss = PP.build_splits(plan, surface, (), rims, write=False, **_elev_args())
    pit = [s for s in ss.all if s.resource == "objects/pit.obj"][0]
    slab = [s for s in ss.all if s.resource == "objects/slab.obj"][0]

    # (1) THE WALL IS CUT BY THE RING'S STATIONS
    arcs = BR.arcs_of(z, ring, 0.3, 64)
    assert len(arcs) == 2
    zeros = sorted(round(b.anchor.surface_z - b.anchor.y_zero, 2)
                   for b in pit.bodies)
    assert zeros == [100.0, 101.5]
    for b in pit.bodies:
        assert b.body_class == AR.BASIN
        assert BR.arc_index_of(b.anchor.reason) is not None
        assert BR.ring_ref_of(b.anchor.reason) == "basin_wall:0@777"

    # (2) A MEMBER INSIDE THE RING IS A FLOOR BODY
    assert all(b.body_class != AR.BASIN for b in slab.bodies)
    assert all("basin rim" not in b.anchor.reason for b in slab.bodies)
    assert all(abs(b.anchor.surface_z - 93.0) < 0.01 for b in slab.bodies)

    # (4) THE BAR: the wall base within 0.3 m of the apron at EVERY node
    from auto_patch_v2.airport import placement_census as PC
    _sp, _kp = PP.to_placement_records(ss)
    c = PC.census_v14([q.to_dict() for q in _sp], [q.to_dict() for q in _kp],
                      elevated_base_m=_ELEV, split_tol_m=0.3, rims=rims,
                      arc_cap=64, counts=ss.counts)
    assert c["basin_rings"] == 1
    assert c["basin_ring_nodes_over_tol"] == 0
    assert c["spread_basin_ring_m"] <= 0.3
    # and the pre-§14a reading of the same ring is the defect it replaces
    before = BR.ring_bar(z, ring, {}, 100.0, 0.3, 64)
    assert before["over_tol"] > 0 and before["worst"] >= 1.5 - 1e-9


# ── §16b: the own-geometry cut is PRIOR; the census reads what is WRITTEN ──

def test_the_16b_census_reads_the_written_geometry_not_the_plan_box():
    """§16b (4): both bars are read on ``geom_pts`` — the body's own
    written triangles — and never on ``geom_box``.

    LEMD's ``Terminal4_green-TEJ3`` is the case: its plan member carries
    ONE part of four triangles, the writer gives it every triangle no
    body owns (``obj8_split``'s nearest rule) and the file spans
    2,342 m, so the box every §16 number read said 0.22 m of ground
    while the eye read +16.22 m (11ap)."""
    def _body(res, pts, sz, carrier=None):
        return {"new_resource": res, "surface_z": sz, "y_zero": 0.0,
                "geom_box": [40.0, -3.0, 40.0002, -2.9998],
                "foot_boxes": [[40.0, -3.0, 40.0002, -2.9998]],
                "geom_pts": [list(p) for p in pts],
                "merged_into": carrier, "elevated": bool(carrier),
                "class": "other"}

    # the ground falls 4 m across the body's own written geometry
    def surface(la, lo):
        return 100.0 + (la - 40.0) * 111_320.0 * 0.02

    wide = _body("wide.obj", [(40.0, -3.0, 0.0), (40.0018, -3.0, 0.0)], 100.0)
    tight = _body("tight.obj", [(40.0, -3.0, 0.0), (40.00001, -3.0, 0.0)], 100.0)
    # a CARRIED piece riding a zero 4 m off the ground under itself
    off = _body("off.obj", [(40.0018, -3.0, 0.0)], 100.0, "w.obj")
    on = _body("on.obj", [(40.0018, -3.0, 0.0)], 104.0, "w.obj")
    splits = [{"placement": {"index": 1}, "bodies": [wide, tight, off, on]}]
    c = _PC.census_v16b(splits, surface, split_tol_m=0.3)
    assert c["geom_span_gt"] == 1 and c["geom_span_worst"][0][1] == "wide.obj"
    assert c["carried_own_ground_gt"] == 1
    assert c["carried_own_ground_worst"][0][1] == "off.obj"
    assert c["bars_ok"] is False
    assert "VIOLATED" in "\n".join(_PC.census_v16b_lines(c))
    ok = _PC.census_v16b([{"placement": {"index": 1}, "bodies": [tight, on]}],
                         surface, split_tol_m=0.3)
    assert ok["geom_span_gt"] == 0 and ok["carried_own_ground_gt"] == 0
    assert ok["bars_ok"] is True
    assert "VIOLATED" not in "\n".join(_PC.census_v16b_lines(ok))
    # a body publishing no written geometry is counted apart, never guessed
    none = dict(tight, geom_pts=[])
    n = _PC.census_v16b([{"placement": {"index": 1}, "bodies": [none]}],
                        surface, split_tol_m=0.3)
    assert n["no_geom_pts"] == 1 and n["bodies_read"] == 0


def test_a_basin_body_is_exempt_from_both_16b_bars():
    """§14 (2) / 11al: the pit was cut TO the object, so a basin's own
    ground spans the pit's depth by construction and a body riding its
    RIM stands over the floor.  Both are counted apart from the bars."""
    def surface(la, lo):
        return 100.0 + (la - 40.0) * 111_320.0 * 0.02

    pit = {"new_resource": "pit.obj", "surface_z": 100.0, "y_zero": 0.0,
           "class": "basin", "merged_into": None,
           "geom_pts": [[40.0, -3.0, 0.0], [40.0018, -3.0, 0.0]]}
    tower = {"new_resource": "tower.obj", "surface_z": 100.0, "y_zero": 0.0,
             "class": "other", "merged_into": "pit.obj",
             "geom_pts": [[40.0018, -3.0, 0.0]]}
    c = _PC.census_v16b([{"placement": {"index": 1}, "bodies": [pit, tower]}],
                        surface, split_tol_m=0.3)
    assert c["geom_span_gt"] == 0 and c["carried_own_ground_gt"] == 0
    assert c["basin_wide"] == 1 and c["basin_carried"] == 1
    assert c["bars_ok"] is True
    assert "BASIN exemptions" in "\n".join(_PC.census_v16b_lines(c))


def test_coarsening_joins_only_bodies_contiguous_in_plan():
    """§16b (1): §9 joined bodies whose intended zeros agreed with NO
    distance limit — LEMD's 80 taxi signs over 835 x 2,319 m became files
    by height alone, and ``SENRG__b10`` took its zero from a sign 1,590 m
    away (+4.58 m at the owner's gate 5).  Zero agreement is necessary
    and not sufficient: the bodies must also be within
    ``[placement] coarsen_reach_m`` of each other."""
    ml, mo = AR._m_per_deg(40.0)

    def _b(i, lat):
        return (i, AR.Anchor(AR.OTHER, lat, -3.0, 0.0, "", 100.0), 4)

    near = [_b(0, 40.0), _b(1, 40.0 + 10.0 / ml)]          # 10 m apart
    far = [_b(0, 40.0), _b(1, 40.0 + 1500.0 / ml)]         # 1.5 km apart
    boxes_near = [(40.0, -3.0, 40.0, -3.0),
                  (40.0 + 10.0 / ml, -3.0, 40.0 + 10.0 / ml, -3.0)]
    boxes_far = [(40.0, -3.0, 40.0, -3.0),
                 (40.0 + 1500.0 / ml, -3.0, 40.0 + 1500.0 / ml, -3.0)]
    assert len(_PC.coarsen(near, 0.3, boxes=boxes_near, reach_m=30.0)) == 1
    assert len(_PC.coarsen(far, 0.3, boxes=boxes_far, reach_m=30.0)) == 2
    # and with the reach disarmed the pre-11ap reading stands
    assert len(_PC.coarsen(far, 0.3, boxes=boxes_far, reach_m=0.0)) == 1
    # the gap itself is read between the BOXES, 0 where they touch
    assert _PC.box_gap_m(boxes_far[0], boxes_far[1]) == pytest.approx(1500.0,
                                                                     abs=5.0)
    assert _PC.box_gap_m((40.0, -3.0, 40.001, -2.999),
                         (40.0005, -2.9995, 40.002, -2.998)) == 0.0


def test_the_coarsening_never_joins_across_a_terrain_group():
    """§16b (1): §9's coarsening acts WITHIN a terrain group.  Two pieces
    the own-geometry cut divided have different authored y, so their
    ZEROS can agree to the centimetre — and without this the very next
    pass puts them back in one file and the cut is undone (measured:
    LEMD's wide-body count did not move until the grounds were read)."""
    a = (0, AR.Anchor(AR.OTHER, 40.0, -3.0, 0.0, "", 100.0), 4)
    b = (1, AR.Anchor(AR.OTHER, 40.0001, -3.0, 0.0, "", 100.0), 4)
    boxes = [(40.0, -3.0, 40.0, -3.0), (40.0001, -3.0, 40.0001, -3.0)]
    assert len(_PC.coarsen([a, b], 0.3, boxes=boxes, reach_m=30.0,
                           grounds=[100.0, 100.0])) == 1
    assert len(_PC.coarsen([a, b], 0.3, boxes=boxes, reach_m=30.0,
                           grounds=[100.0, 104.0])) == 2


def test_the_fallback_carrier_is_bounded_by_the_ground_under_the_piece():
    """§16b (3): "nearest" says nothing about the ground under the
    carried piece.  A candidate reached by a FALLBACK is accepted only
    when its zero stands within ``split_tol_m`` of that ground; the
    stands-over path never asks (standing over the body IS the
    evidence)."""
    a = AR.Anchor(AR.OTHER, 40.0, -3.0, 0.0, "", 100.0)
    cand = _PC.Candidate(0, "objects/garage__b0.obj", a, frozenset({1}), 8,
                         (40.0, -3.0, 40.0002, -2.9998),
                         part_boxes=((40.0, -3.0, 40.0002, -2.9998),),
                         group=0, body_class=AR.OTHER, fill=1.0,
                         ground_off=0.0)
    far_box = (40.01, -3.0, 40.0102, -2.9998)      # no overlap: the fallback
    refusals: dict[str, int] = {}
    got = _PC.carriers_for(frozenset({9}), far_box, [cand], {}, (),
                           tol_m=0.3, refusals=refusals,
                           carried_ground=lambda: 104.0)
    assert got == [] and refusals.get("far_from_carried_ground") == 1
    # the same candidate, with the ground under the piece at its own zero
    ok = _PC.carriers_for(frozenset({9}), far_box, [cand], {}, (),
                          tol_m=0.3,
                          carried_ground=lambda: 100.0)
    assert ok and ok[0][0] is cand
    # and a candidate the body STANDS OVER is never asked
    over = _PC.carriers_for(frozenset({9}), (40.0, -3.0, 40.0002, -2.9998),
                            [cand], {}, ((40.0, -3.0, 40.0002, -2.9998),),
                            tol_m=0.3,
                            carried_ground=lambda: 104.0)
    assert over and over[0][0] is cand


def test_the_candidate_index_offers_the_same_carriers_as_the_full_scan():
    """§16b (speed): the plan index only decides which candidates a
    search LOOKS at — the ranking, and the carrier it answers with, are
    unchanged."""
    def _cand(i, lat, lon):
        a = AR.Anchor(AR.OTHER, lat, lon, 0.0, "", 100.0)
        box = (lat, lon, lat + 0.0002, lon + 0.0002)
        return _PC.Candidate(i, f"objects/c{i}__b0.obj", a, frozenset({i}), 8,
                             box, part_boxes=(box,), group=0,
                             body_class=AR.OTHER, fill=1.0, ground_off=0.0)

    cands = [_cand(i, 40.0 + 0.001 * i, -3.0) for i in range(40)]
    index = _PC.CandidateIndex(cands, 40.0)
    for i in (0, 7, 39):
        box = (40.0 + 0.001 * i, -3.0, 40.0 + 0.001 * i + 0.0001, -2.99995)
        full = _PC.carriers_for(frozenset({99}), box, cands, {}, (box,),
                                tol_m=0.3)
        fast = _PC.carriers_for(frozenset({99}), box, cands, {}, (box,),
                                tol_m=0.3,
                                solid_cands=cands, index=index)
        assert [c.resource for c, _w in full] == [c.resource for c, _w in fast]


def test_the_contiguity_reach_is_never_below_the_line_station():
    """§16b (1) as amended (Fable): `[placement] coarsen_reach_m` is at
    least `line_segment_m`.

    §10 cuts a line object into stations THAT far apart on purpose — a
    reach shorter than one station makes every station its own file by
    construction, which is a file count and not a law (measured at 30 m:
    LEMD's line-segment files 300 -> 1,755, the airport 1,371 -> 4,050).
    What forbids a body taking its zero from one a kilometre away is the
    TERRAIN-GROUP test beside the reach, not the reach."""
    from auto_patch_v2.law import Law
    pl = Law.load().tables.structures.placement
    assert pl.coarsen_reach_m >= pl.line_segment_m > 0.0


# ── §16c: THE CONNECTED COMPONENT IS THE ATOM (RULINGS 2026-09-12b/12d) ──
# The owner's 1.0.320 read: hangar vaults sliced, a canopy in seven
# pieces over 11 m, the T4 approach deck in 39 with a 16.29 m seam.  ONE
# mechanism: the cut's atom was the authored TRIANGLE, so a terrain-group
# boundary fell INSIDE a welded solid and the halves were written at two
# zeros.  2,554 torn seams on the written frame, 1,994 over 0.3 m.

def test_no_cut_crosses_a_connected_component(tmp_path):
    """§16c (1): a welded strip over falling ground is ONE file.

    The same fixture `test_a_scattered_roof_body_is_cut_into_terrain_groups`
    uses, read under §16c: the strip is ONE component, so the terrain cut
    has nothing to divide and the body stays whole — a component wider
    than its terrain is written whole, at one zero."""
    ml, _mo = AR._m_per_deg(40.0)
    span = 600.0
    v, tris = [], []
    n = 13
    for k in range(n):
        z0 = -k * span / (n - 1)
        v += [(0.0, 0.0, z0), (20.0, 0.0, z0)]
    for k in range(n - 1):
        a, b, c2, d = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        tris += [(a, b, d), (a, d, c2)]
    path = _write_obj(tmp_path / "tej3.obj", v, [("", tris)])
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0)], span_m=0.0)
    p0 = plan.units[0].members[0].parts[0]
    plan = _dc_replace_part(plan, box=(40.0 - span / ml, p0.lon, 40.0, p0.lon))

    def surface(lat, lon):
        return 600.0 + (lat - 40.0) * ml * 0.005

    ss = PP.build_splits(plan, surface, write=False,
                         **_elev_args(line_stations_max=64, foot_band_m=1.0))
    assert ss.counts.get("terrain_triangle_groups", 0) == 0
    assert sum(len(s.bodies) for s in ss.all) == 1


def test_split_obj8_never_assigns_a_triangle_across_a_component(tmp_path):
    """§16c (1): the WRITER's own half.  A component no body owns goes
    WHOLE to the nearest body — never triangle by triangle, which is what
    tore `HANG3`'s vault into ten files over fourteen seams."""
    # two separated 2-triangle plates: body 0 owns the first, and the
    # second (an unowned component) must land ENTIRELY in one file
    v = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 0.0, 4.0), (0.0, 0.0, 4.0),
         (50.0, 0.0, 0.0), (54.0, 0.0, 0.0), (54.0, 0.0, 4.0), (50.0, 0.0, 4.0),
         (90.0, 0.0, 0.0), (94.0, 0.0, 0.0), (94.0, 0.0, 4.0)]
    tris = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (8, 9, 10)]
    path = _write_obj(tmp_path / "two.obj", v, [("", tris)])
    from auto_patch_v2.airport import obj8 as _o8
    from auto_patch_v2.airport import obj8_split as _os
    comps = _o8.solid_components(_o8.parse_obj8(str(path)))
    assert len(comps) == 3
    res = _os.split_obj8(str(path),
                         [_os.BodyCut(0, (0,), (0.0, 0.0, 0.0)),
                          _os.BodyCut(1, (2,), (0.0, 0.0, 0.0))],
                         "objects/two.obj")
    assert res.kept_whole == "" and len(res.files) == 2
    # every file's triangle count is a whole number of COMPONENTS: the
    # unowned middle plate (2 triangles) joined the body nearest its own
    # centroid WHOLE, so the counts are 2 + (1 + 2) and never 3 + 2
    # split through the middle plate
    assert sorted(f.tris for f in res.files) == [2, 3]


def test_the_carrier_is_what_the_body_rests_on():
    """§16c (4): among the candidates a body plan-overlaps, the carrier
    is the one whose TOP lies nearest BELOW the body's base plane; the
    overlap breaks ties only.  A 129,113 m2 floor slab 17 m below a roof
    lost to the 158 m2 wall the roof rests on (LEMD's T2 roofs)."""
    big = AR.Anchor(AR.OTHER, 40.0, -3.0, 0.0, "", 100.0)
    small = AR.Anchor(AR.OTHER, 40.0, -3.0, 0.0, "", 100.0)
    box = (40.0, -3.0, 40.0010, -2.9990)
    wall = (40.0004, -2.9996, 40.0006, -2.9994)
    floor = _PC.Candidate(0, "objects/floor__b0.obj", big, frozenset({1}), 8,
                          box, part_boxes=(box,), group=0,
                          body_class=AR.OTHER, fill=1.0, ground_off=0.0,
                          top_y=1.0, part_tops=(1.0,))
    walls = _PC.Candidate(1, "objects/wall__b0.obj", small, frozenset({2}), 8,
                          wall, part_boxes=(wall,), group=0,
                          body_class=AR.OTHER, fill=1.0, ground_off=0.0,
                          top_y=18.0, part_tops=(18.0,))
    roof = (40.0003, -2.9997, 40.0007, -2.9993)
    got = _PC.carriers_for(frozenset({9}), roof, [floor, walls], {}, (roof,),
                           tol_m=0.3, base_y=18.05)
    assert got and got[0][0] is walls and "rests on it" in got[0][1]
    # 12n: NEAREST IN ABSOLUTE DISTANCE, above or below.  A roof let INTO
    # a PARAPET rests on walls whose top stands ABOVE its base — under
    # the first wording ("nearest below") those walls ranked last and
    # LEMD's T2 roofs went to bodies 6 m off.
    para = _PC.carriers_for(frozenset({9}), roof, [floor, walls], {},
                            (roof,), tol_m=0.3, base_y=17.6)
    assert para and para[0][0] is walls, para[0][1]
    # without the body's base plane the ranking is the old largest-overlap
    old = _PC.carriers_for(frozenset({9}), roof, [floor, walls], {}, (roof,),
                           tol_m=0.3)
    assert old and old[0][0] is floor


def test_the_bounded_fallback_reads_the_contact_ground_not_the_median():
    """§16c (2): a 1 km deck slab's MEDIAN footprint ground is the
    underpass floor 15 m below its piers.  What bounds the fallback is
    where the piece TOUCHES — its own feet, else where it stands over a
    footed body of the unit."""
    # a piece spanning a trench: the median of its footprint reads 600,
    # the ground where its supports stand reads 616
    pier = (40.0000, -3.0000, 40.0001, -2.9999)

    def surface(lat, lon):
        return 616.0 if lat < 40.00015 else 600.0

    gboxes = [pier, (40.0002, -3.0, 40.0005, -2.9999),
              (40.0006, -3.0, 40.0009, -2.9999)]
    box = _PC.hull_of(gboxes)

    class _C:
        part_boxes = (pier,)

    med = _PC.ground_under(surface, _PC.foot_boxes(gboxes), box)
    con = _PC.contact_ground(surface, [], (), gboxes, box, [_C()])
    assert med == 600.0 and con == 616.0
    # a piece with its OWN feet reads those first
    raw = [([], "", None, ((40.0, -3.0, 0.0),), False, (), (), None)]
    assert _PC.contact_ground(surface, raw, [0], gboxes, box, [_C()]) == 616.0


def test_the_torn_seam_census_reads_the_written_files(tmp_path):
    """§16c (5): THE BAR INSTRUMENT IS THE WRITTEN FRAME.  Two sibling
    files of one placement sharing an AUTHORED vertex are two halves of
    one solid, written at two zeros; §10's line segments and §14a's basin
    arcs are the only lawful ones and are counted apart."""
    from auto_patch_v2.airport import placement_census as _PCE
    root = tmp_path / "pack"
    (root / "objects").mkdir(parents=True)
    # two files sharing the authored vertex (10, 0, 0) once their own
    # offsets are added back
    (root / "objects" / "a__b0.obj").write_text(
        "I\n800\nOBJ\n\nVT 0 0 0 0 1 0 0 0\nVT 5 0 0 0 1 0 0 0\n")
    (root / "objects" / "a__b1.obj").write_text(
        "I\n800\nOBJ\n\nVT 0 0 0 0 1 0 0 0\nVT 9 0 0 0 1 0 0 0\n")
    splits = [{"placement": {"resource": "objects/a.obj"}, "bodies": [
        {"body_id": "b0", "class": "other", "new_resource": "objects/a__b0.obj",
         "authored_offset": [5.0, 0.0, 0.0], "surface_z": 100.0, "y_zero": 0.0,
         "anchor_reason": "surface at the body's zero"},
        {"body_id": "b1", "class": "other", "new_resource": "objects/a__b1.obj",
         "authored_offset": [1.0, 0.0, 0.0], "surface_z": 101.2, "y_zero": 0.0,
         "anchor_reason": "surface at the body's zero"}]}]
    c = _PCE.census_torn_seams(splits, str(root))
    assert c["rigid_seams"] == 1 and c["station_seams"] == 0
    assert c["rigid_seams_gt"] == 1 and abs(c["worst"][0][0] + 1.2) < 1e-6
    assert "*** §16c (1) VIOLATED" in "\n".join(_PCE.census_torn_seams_lines(c))
    # the SAME pair as §10 line segments is lawful and counted apart
    for b in splits[0]["bodies"]:
        b["class"] = AR.LINE_SEGMENT
    c2 = _PCE.census_torn_seams(splits, str(root))
    assert c2["rigid_seams"] == 0 and c2["station_seams"] == 1
    assert "VIOLATED" not in "\n".join(_PCE.census_torn_seams_lines(c2))


def test_components_in_contact_are_one_rigid_body(tmp_path):
    """§16c (6) (RULINGS 2026-09-12h): components of ONE resource that
    TOUCH — within `[placement] contact_eps_m`, or linked by the plan's
    own ε-contact graph — are ONE atom: one zero, one carrier.

    OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart
    that `obj8.solid_components`' millimetre key reads as separate; §16c
    (1) then wrote them at two zeros with a 2.70 m seam."""
    # two 4 m plates a HAIR apart over ground that steps between them
    v = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 0.0, 4.0), (0.0, 0.0, 4.0),
         (4.0016, 0.0, 0.0), (60.0, 0.0, 0.0), (60.0, 0.0, 4.0),
         (4.0016, 0.0, 4.0)]
    tris = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
    path = _write_obj(tmp_path / "touch.obj", v, [("", tris)])
    from auto_patch_v2.airport import obj8 as _o8
    assert len(_o8.solid_components(_o8.parse_obj8(str(path)))) == 2
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0)], span_m=0.0)
    surface = _stepped([(-1.0, 5.0, 600.0), (10.0, 70.0, 610.0)])
    # DISARMED: the two components are two atoms at two zeros
    off = PP.build_splits(plan, surface, write=False,
                          **_elev_args(line_stations_max=64, foot_band_m=1.0))
    assert off.counts["bodies"] == 2
    # ARMED at 2 mm: they TOUCH, so they are one rigid body at one zero
    on = PP.build_splits(plan, surface, write=False, contact_eps_m=0.002,
                         **_elev_args(line_stations_max=64, foot_band_m=1.0))
    assert on.counts["bodies"] == 1
    # and the law ships armed
    from auto_patch_v2.law import Law
    assert Law.load().tables.structures.placement.contact_eps_m > 0.0


def test_the_plans_contact_graph_binds_components_whatever_the_distance(tmp_path):
    """§16c (6), the other half: components the PLAN's own ε-contact
    graph already calls touching bind whether or not the distance test
    fires."""
    v, tris = [], []
    for k in range(3):                      # three plates 20 m apart
        i = len(v)
        x = 20.0 * k
        v += [(x, 0.0, 0.0), (x + 4.0, 0.0, 0.0), (x + 4.0, 0.0, 4.0),
              (x, 0.0, 4.0)]
        tris += [(i, i + 1, i + 2), (i, i + 2, i + 3)]
    path = _write_obj(tmp_path / "apart.obj", v, [("", tris)])
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0)], span_m=0.0)
    m = plan.units[0].members[0]
    loose = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0,
                             contact_eps_m=0.002)
    assert len(set(loose.comp_cluster())) == 3
    bound = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0,
                             contact_eps_m=0.002,
                             contact_pairs=((0, 1), (1, 2)))
    assert len(set(bound.comp_cluster())) == 1


def test_the_report_tool_arms_the_shared_repo_write_guard():
    """RULINGS 2026-09-12j: a lane replay is a MEASUREMENT and must cost
    the shared data repo ZERO writes.

    `tools/obj8_split_report.py` armed nothing until round 3: an OTHH
    `--admit-skipped` run created
    `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` (3.25 MB)
    and rewrote `o4_dsf_object_positions_+25+051.cache` in the shared repo
    with BOTH lane-local cache env vars exported, and nothing refused or
    reported it.  What is twinned is the WIRING — that the entry runs
    inside `shared_repo_guard`'s guard and its before/after audit, from
    the ONE implementation `harness/build_airport.py` arms (a second copy
    is the census-wrapper defect)."""
    import ast
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    src = (root / "tools" / "obj8_split_report.py").read_text()
    tree = ast.parse(src)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.dump(main)
    # the guard, its snapshot audit and the refusal report all come from
    # shared_repo_guard, and main() is the entry that arms them
    assert "shared_repo_guard" in ast.dump(tree)
    for name in ("SharedRepoWriteGuard", "shared_repo_snapshot",
                 "snapshot_diff", "report_unauthorised_writes",
                 "require_no_unauthorised_writes"):
        assert name in body, name
    # nothing here is authorised: the guard is built with an EMPTY scope
    assert "With(" in body and "Try(" in body
    # and the real work is one level down, so the audit wraps all of it
    assert any(isinstance(n, ast.FunctionDef) and n.name == "_main"
               for n in tree.body)


def test_the_rigid_reach_chains_solids_and_never_a_line_object(tmp_path):
    """§16c (7) (RULINGS 2026-09-12j): SOLID components of one resource
    within `[placement] rigid_reach_m` chain into ONE rigid cluster —
    LEMD's `HANG3` vault arcs stand 1.507-1.853 m from its spines with
    ZERO ε-contacts, and written at their own zeros a continuous arcing
    roof steps.  A LINE object is EXCLUDED: §10 cuts a fence into
    stations on purpose and chaining its posts re-assembles the run."""
    # three plates 1 m apart: one rigid object under the 2 m reach
    v, tris = [], []
    for k in range(3):
        i = len(v)
        x = 5.0 * k
        v += [(x, 0.0, 0.0), (x + 4.0, 0.0, 0.0), (x + 4.0, 0.0, 4.0),
              (x, 0.0, 4.0)]
        tris += [(i, i + 1, i + 2), (i, i + 2, i + 3)]
    path = _write_obj(tmp_path / "vault.obj", v, [("", tris)])
    plan = _member_plan(path, [(0, 0.0, 0.0, 0.0)], span_m=0.0)
    m = plan.units[0].members[0]
    far = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0,
                           contact_eps_m=0.002, rigid_reach_m=0.0)
    assert len(set(far.comp_cluster())) == 3          # the reach disarmed
    near = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0,
                            contact_eps_m=0.002, rigid_reach_m=2.0)
    assert len(set(near.comp_cluster())) == 1         # ONE rigid cluster
    # a LINE object of the same shape is never chained: the line law's
    # own verdict (`is_line_object`) gates the reach
    line = _CUT._LineCutter(m, 0.0, 0, 0.3, 4.0, 3.0, 40.0, -3.0,
                            contact_eps_m=0.002, rigid_reach_m=2.0)
    line._is_line = True
    assert len(set(line.comp_cluster())) == 3
    # and the law ships the reach armed, above the contact tolerance
    from auto_patch_v2.law import Law
    pl = Law.load().tables.structures.placement
    assert pl.rigid_reach_m > pl.contact_eps_m > 0.0


def test_the_16b_float_bar_excludes_a_footed_body():
    """§16c (3) (RULINGS 2026-09-12j): A SKIRT IS NOT A FLOAT.

    `zero - ground under the geometry` is a float only for a body with no
    feet that takes a carrier's zero.  LEMD's `green-STRT4` deck has
    `y_zero` -1.668 — a skirt 1.67 m BELOW its zero plane — so the same
    subtraction read a correctly seated deck as +1.11 m afloat.  A footed
    body's number is `ground_off`."""
    from auto_patch_v2.airport import placement_census as _PCE

    def _body(bid, feet):
        return {"body_id": bid, "class": "other",
                "new_resource": f"objects/x__b{bid}.obj",
                "merged_into": "objects/carrier__b0.obj", "feet": feet,
                "surface_z": 100.0, "y_zero": -1.7,
                "geom_pts": [[40.0, -3.0, 0.0]]}

    splits = [{"placement": {"resource": "objects/x.obj"},
               "bodies": [_body(0, 0), _body(1, 6)]}]
    c = _PCE.census_v16b(splits, lambda la, lo: 100.0, split_tol_m=0.3)
    # the FOOTLESS one floats 1.7 m and is the bar; the FOOTED one is out
    assert c["carried_own_ground_gt"] == 1
    assert c["footed_carried_excluded"] == 1
    assert "FOOTED body(ies)" in "\n".join(_PCE.census_v16b_lines(c))


# ── §16c (7)-(8): the unit binds by contact (owner RULINGS 2026-09-12q) ──

def _t2_block(tmp_path, contacts):
    """Two members of one unit standing on ground that differs by 0.5 m:
    a WALL with feet and a second walled body beside it, plus a ROOF
    authored 8 m up over the second."""
    (tmp_path / "wall_dir").mkdir(exist_ok=True)
    (tmp_path / "roof_dir").mkdir(exist_ok=True)
    a_path, _n = _two_boxes(tmp_path / "wall_dir", with_anim=False)
    b_path, _n2 = _two_boxes(tmp_path / "roof_dir", with_anim=False)
    return _unit_plan([
        (a_path, [(0, 0.0, 0.0, 0.0, 0.0, 12.0)], "objects/wallA.obj"),
        (a_path, [(0, 0.0, 40.0, 0.0, 0.0, 12.0)], "objects/wallB.obj"),
        (b_path, [(0, 8.0, 40.0, 0.0, 8.0, 12.0)], "objects/roof.obj"),
    ], contacts=contacts), a_path, b_path


def _stepped_surface(lat, lon):
    """0.5 m of fall between the two walls — enough that §9 gives them
    two files and two zeros of their own."""
    return 600.0 if (lat - 40.0) * 111_000.0 < 20.0 else 600.5


def test_the_unit_binds_by_contact(tmp_path):
    """§16c (7): two MEMBERS of one unit whose parts the plan's ε-contact
    graph links are ONE RIGID BODY at ONE zero — the senior footed
    body's — and the roof of one of them rides that zero too.

    Measured at LEMD: the T2 block's walls stood at 602.89 ... 603.35
    and `LEMD47` at three zeros 1.19 m apart, each roof inheriting
    whichever the carrier ranking handed it (RULINGS 2026-09-12q)."""
    plan, _a, _b = _t2_block(tmp_path, contacts=((0, 1), (1, 2)))
    ss = PP.build_splits(plan, _stepped_surface, write=False, **_elev_args())
    zeros = {}
    for sp in ss.all:
        for bd in sp.bodies:
            zeros[sp.resource] = bd.anchor.surface_z - bd.anchor.y_zero
    assert len(set(round(v, 3) for v in zeros.values())) == 1, zeros
    assert ss.counts.get("bodies_bound_by_unit_contact", 0) >= 1
    # ... and WITHOUT the contact the two walls keep their own readings
    plan2, _a2, _b2 = _t2_block(tmp_path, contacts=())
    ss2 = PP.build_splits(plan2, _stepped_surface, write=False, **_elev_args())
    z2 = {sp.resource: bd.anchor.surface_z - bd.anchor.y_zero
          for sp in ss2.all for bd in sp.bodies}
    assert len(set(round(v, 3) for v in z2.values())) > 1, z2


def test_a_cluster_never_grows_wider_than_a_building(tmp_path):
    """§16c (7): the chain is BOUNDED in plan.  The unit's contact graph
    is not a building — unbounded it chained LEMD's fences and grass
    mats over 1,190 m and collapsed 10.46 m of honest terrain reading
    onto one zero — so a union whose cluster would exceed
    ``UNIT_CLUSTER_SPAN_MAX_M`` is refused."""
    from auto_patch_v2.airport import placement_atom as ATOM
    far = ATOM.UNIT_CLUSTER_SPAN_MAX_M * 2.0 / 111_000.0
    near = ATOM.RigidNode(0, frozenset([1]), (40.0, -3.0, 40.0005, -2.9995),
                          footprint_m2=100.0, footed=True, bindable=True,
                          zero=600.0, feet=8)
    away = ATOM.RigidNode(1, frozenset([2]),
                          (40.0 + far, -3.0, 40.0005 + far, -2.9995),
                          footprint_m2=10.0, footed=True, bindable=True,
                          zero=610.0, feet=2)
    senior, census = ATOM.unit_rigid([near, away], [(1, 2)])
    assert senior == [-1, -1] and census == []
    close = ATOM.RigidNode(1, frozenset([2]), (40.0004, -3.0, 40.0009, -2.9995),
                           footprint_m2=10.0, footed=True, bindable=True,
                           zero=610.0, feet=2)
    senior2, census2 = ATOM.unit_rigid([near, close], [(1, 2)])
    assert senior2[1] == 0 and senior2[0] == -1      # the senior is the
    assert census2 and census2[0][1] == 2            # body with the feet


def test_a_line_object_and_a_basin_never_join_a_unit_cluster():
    """§16c (7): §10 cuts a fence into stations ON PURPOSE and each reads
    its own ground; §14 (2) makes a basin's zero its RIM.  Neither binds
    — bound, LEMD's `LEMDzaun` came onto one zero across 10.46 m of real
    relief and the pits at LEMD03/36/85 split into 8 torn seams."""
    from auto_patch_v2.airport import placement_atom as ATOM
    a = ATOM.RigidNode(0, frozenset([1]), (40.0, -3.0, 40.0005, -2.9995),
                       footprint_m2=100.0, footed=True, bindable=True,
                       zero=600.0, feet=8)
    fence = ATOM.RigidNode(1, frozenset([2]), (40.0002, -3.0, 40.0007, -2.9995),
                           footprint_m2=10.0, footed=True, bindable=False,
                           zero=610.0, feet=2)
    senior, _c = ATOM.unit_rigid([a, fence], [(1, 2)])
    assert senior == [-1, -1]


def test_an_elevated_body_joins_its_own_members_footed_cluster():
    """§16c (7) rule (a), AND THE FIELD ORDER THAT KILLED IT (owner
    RULINGS 2026-09-12am (1)).

    A member is ONE authored object: its ELEVATED bodies ride the footed
    body of their own member whether or not the plan records a contact
    between them — a roof welded into its own walls often shares no PART
    with them.  ``bind_unit`` built its nodes POSITIONALLY and put the
    footprint where ``footed`` is declared, so every node read
    ``footed`` true, a member's ``feet_i`` held all of its bodies and
    NOTHING was ever unioned by this rule.  LEMD's `LEMD47` was the
    residue: its footed walls carry no ε-contact at all (all 114 with
    `LEMD48` are on its elevated parts) and the resource was written at
    two zeros 0.804 m apart, over §31's 0.5 m visual threshold.

    So: no contacts, one member, one footed body and one elevated — the
    elevated body's senior IS the footed one."""
    from auto_patch_v2.airport import placement_atom as ATOM
    walls = ATOM.RigidNode(7, frozenset([1]), (40.0, -3.0, 40.0005, -2.9995),
                           footprint_m2=100.0, footed=True, bindable=True,
                           zero=600.0, feet=16)
    roof = ATOM.RigidNode(7, frozenset([2]), (40.0, -3.0, 40.0005, -2.9995),
                          footprint_m2=90.0, footed=False, bindable=True,
                          zero=None)
    senior, census = ATOM.unit_rigid([walls, roof], ())
    assert senior[1] == 0 and senior[0] == -1, senior
    assert census and census[0][1] == 2
    # ... and the same through ``bind_unit``, which is where the swap
    # was: ONE member, a footed part and an elevated part OVER it (the
    # rule's own plan-overlap test), NO contacts at all — the two are
    # separate components 100 m apart in the authored file, so §16c (8)
    # does not weld them either.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        import pathlib
        p, _n = _two_boxes(pathlib.Path(td), with_anim=False)
        plan = _unit_plan([(p, [(0, 0.0, 0.0, 0.0, 0.0, 12.0),
                                (1, 8.0, 0.0, 0.0, 8.0, 12.0)],
                            "objects/one.obj")], contacts=())
        ss = PP.build_splits(plan, _stepped_surface, write=False,
                             **_elev_args())
        zs = {round(bd.anchor.surface_z - bd.anchor.y_zero, 3)
              for sp in ss.all for bd in sp.bodies
              if bd.anchor.surface_z is not None}
        assert len(zs) == 1, zs
        assert ss.counts.get("bodies_bound_to_cluster_by_contact", 0) >= 1
    # the swapped reading is what the defect was: a node whose `footed`
    # is truthy is a FOOTED body, and two of one member never union
    import dataclasses as _dc0
    roof_as_footed = _dc0.replace(roof, footed=True, zero=601.0)
    senior2, _c2 = ATOM.unit_rigid([walls, roof_as_footed], ())
    assert senior2 == [-1, -1], senior2


def test_a_bind_across_members_holds_only_while_the_ground_agrees():
    """(A), owner RULINGS 2026-09-12ap.

    §16c (7) hands a bound body the senior's zero WHOLE, with no height
    test at all, and 12ap measured what that costs: 41 of LEMD's 76 sunk
    bodies were anchored more than 2 m from their own feet — the
    `TABOX`/`TABOXzwei`/`TAPSL` row of 12 GSE boxes bound over 154 m of
    apron, each ~1.9 m INTO it.  A box a metre under its apron is a
    visible burial.  So a FOOTED body of ANOTHER MEMBER keeps the cluster
    only while its own zero stands within ``bind_ground_m``
    (``[cockpit] visual_m`` 0.5) of the senior's, and beyond it keeps its
    own anchor and is COUNTED.

    §16d (5) (owner RULINGS 2026-09-13m) MAKES THE BOUND
    MEMBER-AGNOSTIC.  12ap wrote it as ``member != top.member`` on the
    reading that within one member 12z's own veto already stands — it
    does not: a NATIVE pack authors one master model per MATERIAL, so a
    member spans the whole airport and a same-member bind is a bind
    across a kilometre (KCLT's hangar wall `005_ALB__b9` sank 5.04 m into
    its pad on one)."""
    from auto_patch_v2.airport import placement_atom as ATOM
    box = (40.0, -3.0, 40.0005, -2.9995)
    near = (40.0004, -3.0, 40.0009, -2.9995)
    senior_n = ATOM.RigidNode(0, frozenset([1]), box, footprint_m2=100.0,
                              footed=True, bindable=True, zero=600.0, feet=8)
    agrees = ATOM.RigidNode(1, frozenset([2]), near, footprint_m2=10.0,
                            footed=True, bindable=True, zero=600.4, feet=2)
    sunk = ATOM.RigidNode(1, frozenset([2]), near, footprint_m2=10.0,
                          footed=True, bindable=True, zero=601.9, feet=2)
    # unarmed (``bind_ground_m`` 0) the old reading stands
    assert ATOM.unit_rigid([senior_n, sunk], [(1, 2)])[0][1] == 0
    # armed: 0.4 m of disagreement binds, 1.9 m does not
    cnt: dict = {}
    assert ATOM.unit_rigid([senior_n, agrees], [(1, 2)],
                           bind_ground_m=0.5, counts=cnt)[0][1] == 0
    assert not cnt.get("bind_refused_for_ground")
    sen, _c = ATOM.unit_rigid([senior_n, sunk], [(1, 2)],
                              bind_ground_m=0.5, counts=cnt)
    assert sen == [-1, -1], sen
    assert cnt["bind_refused_for_ground"] == 1
    assert cnt["bind_refused_worst_m"] == pytest.approx(1.9, abs=1e-6)
    # §16d (5): AND INSIDE ONE MEMBER TOO — the same pair, one resource,
    # is refused for exactly the same disagreement
    import dataclasses as _dc0
    same = _dc0.replace(sunk, member=0)
    cnt2: dict = {}
    assert ATOM.unit_rigid([senior_n, same], [(1, 2)],
                           bind_ground_m=0.5, counts=cnt2)[0][1] == -1
    assert cnt2["bind_refused_for_ground"] == 1
    # an ELEVATED body has no ground of its own and is never refused:
    # it is the class §16c (7) exists for
    roof = ATOM.RigidNode(1, frozenset([2]), near, footprint_m2=10.0,
                          footed=False, bindable=True, zero=None)
    assert ATOM.unit_rigid([senior_n, roof], [(1, 2)],
                           bind_ground_m=0.5, counts={})[0][1] == 0


def test_the_rest_on_carrier_is_not_refused_for_its_own_ground():
    """§16c (8): §16a (2) refuses a candidate whose own zero stands off
    the ground under its own feet — but not the one the body RESTS ON.
    LEMD's `tej2` was sent to a body 14.6 m away because `P2PK`, whose
    top meets its base, is 0.42 m off its own feet."""
    from auto_patch_v2.airport import placement_carrier as PC
    box = (40.0, -3.0, 40.001, -2.999)

    def _cand(member, top, off):
        a = AR.Anchor("building", 40.0005, -2.9995, 0.0, "r", 600.0, (0, 0, 0))
        return PC.Candidate(member, f"objects/c{member}.obj", a,
                            frozenset([member]), 4, box, part_boxes=(box,),
                            ground_off=off, group=0, body_class="building",
                            fill=1.0, top_y=top, part_tops=(top,))

    rests_on = _cand(1, 10.0, 0.42)          # what the roof sits on
    far = _cand(2, 4.0, 0.0)                 # 6 m below it, lawfully anchored
    out = PC.carriers_for(frozenset([9]), box, [rests_on, far], {}, (box,),
                          tol_m=0.3, base_y=10.2)
    assert out and out[0][0].member == 1, [c.member for c, _r in out]
    # and the refusal STANDS for a candidate the body does not rest on
    out2 = PC.carriers_for(frozenset([9]), box, [_cand(1, 14.0, 0.42), far],
                           {}, (box,), tol_m=0.3, base_y=10.2)
    assert out2 and out2[0][0].member == 2


# ── §17 CRITICAL MOTION, the object stage's pavement reading ─────────────
# (owner RULINGS 2026-09-12am (2); spec §17, design-surface-spec §31 (1))

def _roles_doc(role="apron", ring=((40.0, -3.0), (40.0, -2.998),
                                    (40.002, -2.998), (40.002, -3.0)),
                z=600.0, extra=()):
    """A minimal ``<ICAO>.graded.json`` document: one face per entry."""
    verts, faces = [], []
    for k, (rl, rg) in enumerate(((role, ring),) + tuple(extra)):
        ids = []
        for la, lo in rg:
            ids.append(len(verts))
            verts.append([len(verts), la, lo, z])
        faces.append({"id": k, "ref": f"f{k}", "role": rl, "ring": ids,
                      "holes": [], "side": "airside"})
    return {"vertices": verts, "faces": faces, "breaklines": []}


def test_the_graded_face_role_under_a_point_is_the_senior_one():
    """§17: the roles index answers WHAT the surface is under a foot, and
    where two faces overlap the SENIOR one owns the point (12ak's own
    rule for a shared vertex, ``precedence.toml``'s authority order)."""
    from auto_patch_v2.airport import placement_boxes as PB
    pad = ((40.0005, -2.9995), (40.0005, -2.9990), (40.0010, -2.9990),
           (40.0010, -2.9995))
    d = _roles_doc(extra=(("building", pad),))
    rank = {"runway": 0, "apron": 8, "building": 9}
    gr = PB.graded_roles_from_doc(d, rank=lambda r: rank.get(r, 99))
    assert gr.role(40.001, -2.999) == "apron"        # apron only
    assert gr.role(40.0007, -2.9993) == "apron"      # BOTH: apron is senior
    assert gr.role(41.0, -3.0) is None               # on no face at all
    # the batch and the scalar path are the same reading
    pts = [(40.001, -2.999), (40.0007, -2.9993), (41.0, -3.0)]
    assert gr.roles_many([p[0] for p in pts], [p[1] for p in pts]) == \
        [gr.role(*p) for p in pts]


def test_the_roles_index_and_the_pads_read_ONE_parsed_document():
    """§17 is a SIBLING of ``pads_rims_from_graded_doc``, not a second
    parser: both are built from the one dict the caller already holds."""
    from auto_patch_v2.airport import placement_boxes as PB
    d = _roles_doc(extra=(("building", ((40.003, -3.0), (40.003, -2.999),
                                         (40.004, -2.999))),))
    pads, _rims = PP.pads_rims_from_graded_doc(d)
    gr = PB.graded_roles_from_doc(d)
    assert [p.ref for p in pads] == ["f1"]
    assert {f[0] for f in gr.faces} == {"apron", "building"}


def _motion_surface(z=600.0):
    def s(la, lo):
        return z
    return s


def test_census_motion_judges_only_the_feet_on_rolled_on_pavement():
    """§17: a body with a foot on an apron face is ON PAVEMENT and its
    float there is priced at ``motion_step_m``; a foot on grass, on a pad
    or on no face is not this census's (it is §7's and §31 (3)'s)."""
    from auto_patch_v2.airport import placement_census as PC

    class _Roles:
        def roles_many(self, las, los):
            return ["apron" if la < 40.001 else "graded_strip" for la in las]

    bodies = [{"res": "sign.obj", "cls": "other", "anchor_z": 600.0,
               "y_zero": 0.0,
               "feet": ((40.0000, -3.0, 0.0),      # on apron, dead on
                        (40.0005, -3.0, 0.4),      # on apron, 0.4 m float
                        (40.0020, -3.0, 3.0))}]    # on grass: not motion
    c = PC.census_motion(bodies, _motion_surface(), _Roles(),
                         rolled_on={"apron"}, motion_step_m=0.05,
                         band_m=100.0)
    assert c["bodies_on_pavement"] == 1 and c["feet_on_pavement"] == 2
    assert c["motion_feet_gt"] == 1 and c["motion_bodies_gt"] == 1
    assert c["worst"][0][1] == pytest.approx(-0.4)     # FLOATING, signed
    assert c["motion_floating"] == 1 and c["motion_buried"] == 0
    assert c["by_role"] == (("apron", 1),)


def test_the_motion_float_is_section_7s_own_expression():
    """ONE reading: ``foot_float`` is what §17 and §7 both call, so the
    two instruments cannot drift (CLAUDE.md's census-wrapper defect)."""
    from auto_patch_v2.airport import placement_census as PC
    # surface(foot) - (surface(anchor) + y_foot - y_zero)
    assert PC.foot_float(601.0, 600.0, 0.5, 0.0) == pytest.approx(0.5)
    assert PC.foot_float(599.0, 600.0, 0.5, 0.5) == pytest.approx(-1.0)
    assert PC.feet_in_band(((0, 0, 0.0), (0, 0, 0.2), (0, 0, 9.0)), 0.5) == \
        [(0, 0, 0.0), (0, 0, 0.2)]


def test_section_17_judges_at_the_ground_contact_feet_not_the_whole_band():
    """(B), owner RULINGS 2026-09-12ap.

    ``contact_band_m`` (1 m) is the band the PLAN picks a part's feet
    with and it is shared law that does not move — but a metre is a
    storey of authored model, and 12ap measured that 360 of the 561 feet
    §17 read as FLOATING over the visual threshold were vertices standing
    at their own AUTHORED height over a correctly seated body.  §17
    judges the feet that TOUCH: the in-band feet within ``split_tol_m``
    of the body's lowest.  The wider reading is still taken and printed,
    so the report states its own attribution."""
    from auto_patch_v2.airport import placement_census as PC
    feet = ((0, 0, 0.0), (0, 0, 0.2), (0, 0, 0.9), (0, 0, 9.0))
    assert PC.ground_contact_feet(feet, 1.0, 0.3) == \
        [(0, 0, 0.0), (0, 0, 0.2)]
    # the band stays the outer scope; a tolerance at or above it is it
    assert PC.ground_contact_feet(feet, 1.0, 1.0) == PC.feet_in_band(feet, 1.0)
    assert PC.ground_contact_feet(feet, 1.0, 0.0) == PC.feet_in_band(feet, 1.0)

    class _Roles:
        def roles_many(self, las, los):
            return ["apron"] * len(list(las))

    # one body, seated dead on its ground, with a sign panel authored
    # 0.9 m up inside the band: judged, it is clean; over the whole band
    # it reads 0.9 m of "float" that nothing placed there.
    body = [{"res": "sign.obj", "cls": "other", "anchor_lat": 40.0,
             "anchor_lon": -3.0, "anchor_z": 600.0, "y_zero": 0.0,
             "reason": "surface at the body's zero", "feet": feet[:3]}]
    c = PC.census_motion(body, lambda la, lo: 600.0, _Roles(),
                         rolled_on={"apron"}, motion_step_m=0.05,
                         band_m=1.0, contact_tol_m=0.3, visual_m=0.5)
    assert c["feet_read"] == 3 and c["feet_in_band"] == 3
    assert c["float_gt_visual"] == 0
    assert c["band_float_gt_visual"] == 1        # the authored panel
    assert c["motion_feet_gt"] == 1              # the 0.2 m vertex only


def test_the_replay_sampler_never_reads_across_a_graded_hole(tmp_path):
    """(E), owner RULINGS 2026-09-12ap.

    A face with a HOLE says, in the document itself, that the ground
    inside that ring is not its own.  A Delaunay over the emitted
    VERTICES knows none of that and spans the ring with triangles
    reaching from the apron down to the trench floor: LEMD read
    **592.22 m at a point whose ROLE is apron**, six metres outside the
    hole, and that fabricated ramp was 12ap's two worst pavement feet
    (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` -5.08).  A point
    in such a simplex reads the nearest vertex on ITS OWN SIDE of the
    ring instead."""
    import json as _json
    # a 40 m apron square at 600 m with a hole, and a 590 m floor in it
    def _v(i, la, lo, z):
        return [i, la, lo, z]
    ring = [(40.0000, -3.0000), (40.0004, -3.0000),
            (40.0004, -2.9996), (40.0000, -2.9996)]
    hole = [(40.00015, -2.99985), (40.00025, -2.99985),
            (40.00025, -2.99975), (40.00015, -2.99975)]
    flr = [(40.000155, -2.999845), (40.000245, -2.999845),
           (40.000245, -2.999755), (40.000155, -2.999755)]
    vs, faces = [], []
    for k, (la, lo) in enumerate(ring):
        vs.append(_v(k, la, lo, 600.0))
    for k, (la, lo) in enumerate(hole):
        vs.append(_v(4 + k, la, lo, 600.0))
    for k, (la, lo) in enumerate(flr):
        vs.append(_v(8 + k, la, lo, 590.0))
    faces.append({"role": "apron", "ref": "pav1", "ring": [0, 1, 2, 3],
                  "holes": [[4, 5, 6, 7]]})
    faces.append({"role": "tunnel_trench", "ref": "pit", "ring": [8, 9, 10, 11],
                  "holes": []})
    p = tmp_path / "TEST.graded.json"
    p.write_text(_json.dumps({"vertices": vs, "faces": faces,
                              "breaklines": []}))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import obj8_split_report as RPT
    s, _p, _r = RPT.surface_from_graded(str(p), 0.3)
    assert s.holes_struck > 0
    # on the apron, just outside the hole: the apron, never a ramp
    assert s(40.000145, -2.99980) == pytest.approx(600.0, abs=1e-6)
    # inside the pit: the floor
    assert s(40.000200, -2.99980) == pytest.approx(590.0, abs=1e-6)
    # and the whole apron reads flat, with nothing between the two levels
    for k in range(9):
        z = s(40.00000 + k * 0.000015, -2.99980)
        assert z is None or z in (pytest.approx(600.0, abs=1e-6),
                                  pytest.approx(590.0, abs=1e-6)), (k, z)


def test_a_basin_bodys_floor_feet_are_not_motion():
    """§14 (2) / RULINGS 2026-09-11al: a pit's zero is its RIM and its
    floor feet are authored the depth below it BY CONSTRUCTION.  Read as
    motion they were LEMD's worst ten (+7.69 m 'on the apron')."""
    from auto_patch_v2.airport import placement_census as PC

    class _Roles:
        def roles_many(self, las, los):
            return ["apron"] * len(list(las))

    bodies = [{"res": "pit.obj", "cls": AR.BASIN, "anchor_z": 600.0,
               "y_zero": 0.0, "feet": ((40.0, -3.0, 7.0),)}]
    c = PC.census_motion(bodies, _motion_surface(), _Roles(),
                         rolled_on={"apron"}, motion_step_m=0.05,
                         band_m=100.0, exempt_classes={AR.BASIN})
    assert c["motion_feet_gt"] == 0
    assert c["exempt_feet_gt"] == 1 and c["exempt_bodies_gt"] == 1


def test_the_cockpit_block_prints_motion_when_it_is_read_and_says_so_when_not():
    """§17 in the block: handed a motion census it prints CRITICAL
    motion; handed none it names the instrument limit rather than
    printing a zero (12ad/12ak's own wording, now conditional)."""
    from auto_patch_v2.airport import placement_carrier as PC
    silent = PC.cockpit_block()
    assert silent["motion_read"] is False and silent["critical_motion_n"] == 0
    assert "NOT TAKEN" in "\n".join(PC.cockpit_block_lines(silent))
    m = {"motion_step_m": 0.05, "bodies_read": 9, "bodies_on_pavement": 3,
         "feet_on_pavement": 12, "motion_feet_gt": 2, "motion_bodies_gt": 1,
         "motion_buried": 1, "motion_floating": 1,
         "worst": ((0.44, -0.44, "sign.obj", 40.0, -3.0, "apron", "other"),)}
    c = PC.cockpit_block(motion=m)
    assert c["motion_read"] and c["critical_motion_n"] == 2
    txt = "\n".join(PC.cockpit_block_lines(c))
    assert "CRITICAL motion: 2 foot(feet) on 1 body(ies)" in txt
    assert "sign.obj" in txt and "40.0000000,-3.0000000" in txt and "apron" in txt


def test_a_body_all_of_whose_feet_stand_on_pavement_keeps_the_median():
    """§17 / 12am (2): 11e (2)'s low-side foot pays the body's whole
    relief as float at its high corner.  Where the aircraft ROLLS the bar
    is 0.05 m, so the relief is SHARED — the median foot — and the
    low-side rule stands everywhere else."""
    ring = [(40.0000, -3.0000, 0.0, ((40.0000, -3.0000, 0.0),)),
            (40.0010, -3.0000, 0.0, ((40.0010, -3.0000, 0.0),)),
            (40.0020, -3.0000, 0.0, ((40.0020, -3.0000, 0.0),))]
    geom = AR.BodyGeometry(tuple(ring), 40.001, -3.0)

    def surface(la, lo):                 # 1 m of fall across the body
        return 600.0 + (la - 40.0) * 500.0

    class _Roles:
        def __init__(self, role):
            self.role = role

        def roles_many(self, las, los):
            return [self.role] * len(list(las))

    on = AR.anchor_for(AR.OTHER, geom, surface, tol_m=0.3,
                       roles=_Roles("apron"), rolled_on={"apron"})
    assert "median foot" in on.reason and on.lat == pytest.approx(40.0010)
    off = AR.anchor_for(AR.OTHER, geom, surface, tol_m=0.3,
                        roles=_Roles("graded_strip"), rolled_on={"apron"})
    assert "low-side foot" in off.reason and off.lat == pytest.approx(40.0000)
    # and with NO roles at all the low-side rule stands: no reading is no
    # evidence (a caller with no graded surface)
    bare = AR.anchor_for(AR.OTHER, geom, surface, tol_m=0.3)
    assert "low-side foot" in bare.reason


def test_the_anchor_rule_reads_the_roles_off_the_sampler():
    """The sampler CARRIES the roles (``surface.roles`` beside
    ``surface.many``), so no caller between ``build_splits`` and the one
    place that builds it has to grow an argument — and the shipped engine
    path and the dry-run tool attach the same pair."""
    geom = AR.BodyGeometry(
        ((40.0000, -3.0, 0.0, ((40.0000, -3.0, 0.0),)),
         (40.0020, -3.0, 0.0, ((40.0020, -3.0, 0.0),))), 40.001, -3.0)

    def surface(la, lo):
        return 600.0 + (la - 40.0) * 500.0

    class _Roles:
        def roles_many(self, las, los):
            return ["runway"] * len(list(las))

    surface.roles = _Roles()
    surface.rolled_on = frozenset({"runway"})
    assert "median foot" in AR.anchor_for(AR.OTHER, geom, surface,
                                          tol_m=0.3).reason


# ── §16e (4): the instrument's own box ───────────────────────────────────

def test_the_placement_census_hands_the_mesh_sampler_its_own_bbox_order():
    """§16e (4): ``seat_feet_census --placement-plan --mesh`` passed its
    bbox as ``(lat, lon)`` to a sampler that takes ``(lon, lat)``.

    The twin is end to end over the mesh fixture the sampler's own tests
    use: a plan row standing on the fixture's centre vertex must be
    ANSWERED by a sampler built from :func:`plan_bounds`.  Spelled the
    wrong way round, the box lands at lon 50 / lat 10, the sampler
    retains no triangle and every row of the census reads ``None``."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "tools"))
    import seat_feet_census as SFC
    from auto_patch.mesh_sampler import MeshElevationSampler

    mesh = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fixtures", "mesh", "synthetic_fan_three_triangles.mesh")
    plan = {"splits": [{"placement": {"index": 1},
                        "bodies": [{"new_resource": "objects/a__b0.obj",
                                    "anchor": {"lon": 10.0005, "lat": 50.0005,
                                               "heading": 0.0}}]}],
            "conversions": [{"resource": "objects/b.obj",
                             "lon": 10.0002, "lat": 50.0002, "heading": 0.0}]}
    _defs, plc = SFC.placement_plan_rows(plan)
    assert [(round(p[1], 4), round(p[2], 4)) for p in plc] == \
        [(10.0005, 50.0005), (10.0002, 50.0002)]      # (def, LON, LAT, hdg)
    bounds = SFC.plan_bounds(plc)
    assert bounds == (10.0002, 50.0002, 10.0005, 50.0005)
    z = MeshElevationSampler(mesh, bounds).elevation_at_or_none(50.0005, 10.0005)
    assert z is not None and abs(z - 250.0) < 1e-6
    # ... and the transposed spelling retains NO TRIANGLE, which is the
    # defect: at OTHH the census died on this very line
    swapped = (bounds[1], bounds[0], bounds[3], bounds[2])
    with pytest.raises(ValueError, match="no mesh triangles"):
        MeshElevationSampler(mesh, swapped)


# ── §16e: THE DECK TOP AND THE CREST PLATE ARE DATUMS ────────────────────

def _member_like(**kw):
    """A stand-in for ``model.rebake.Member`` — ``anchor_rule.datum_of``
    reads its member by attribute on purpose, so a twin need not build a
    whole plan to state the law."""
    import types
    base = dict(plate_y=None, plate_stations=(), plate_clearance_m=0.0,
                deck_top_y=None, deck_datum_z=None, deck_kind="",
                deck_end_stations=(), parts=())
    base.update(kw)
    return types.SimpleNamespace(**base)


def _geom_at(lat, lon, y=0.0):
    return AR.BodyGeometry(((lat, lon, y, ((lat, lon, y),)),), lat, lon)


def test_the_crest_plate_is_the_datum():
    """§16e (1): a member carrying ``plate_y > 0`` anchors at a wall-band
    STATION with ``y_zero = plate_y`` — the crest at the ground there —
    and the rule keys on ``plate_y``, never on the classification: OTHH's
    tunnel walls class BASIN (they stand inside their own emitted
    ``tunnel_wall`` ring) and §14 (2)'s rim anchor stood their crests
    +5 … +10 m over the rim."""
    ground = {(0.0, 0.0): 10.0, (0.0, 1e-4): 12.0, (0.0, 2e-4): 11.0}
    surface = lambda la, lo: ground.get((round(la, 8), round(lo, 8)), 50.0)  # noqa
    m = _member_like(plate_y=5.0, plate_stations=tuple(ground))
    d = AR.datum_of(m)
    assert d is not None and d.y == 5.0 and d.label == "crest plate"
    a = AR.anchor_for(AR.BASIN, _geom_at(0.5, 0.5), surface, tol_m=0.3, datum=d)
    # the MEDIAN station (11.0), and the crest lands ON it
    assert a.datum is True and a.y_zero == 5.0 and a.surface_z == 11.0
    assert (a.lat, a.lon) == (0.0, 2e-4)
    assert abs((a.surface_z - a.y_zero + 5.0) - 11.0) < 1e-9
    # §24 (2): the clearance comes off the datum, not the ground
    d2 = AR.datum_of(_member_like(plate_y=5.0, plate_clearance_m=0.5,
                                  plate_stations=tuple(ground)))
    assert d2.y == 4.5


def test_a_floor_plate_basin_is_not_a_crest_datum():
    """§16e (1): ``plate_y <= 0`` is a FLOOR-plate basin — LEMD's pits,
    OTHH's 8 drainage basins — whose zero is its RIM by §14 (2).  The
    datum is the CREST plate and nothing else, so those read no datum at
    all and every anchor they take is the one they took before."""
    st = ((0.0, 0.0), (0.0, 1e-4))
    assert AR.datum_of(_member_like(plate_y=-3.82, plate_stations=st)) is None
    assert AR.datum_of(_member_like(plate_y=-13.14, plate_stations=st)) is None
    assert AR.datum_of(_member_like(plate_y=5.0)) is None      # no stations
    rim = AR.RimRing("basin_wall:1", ((-1.0, -1.0), (-1.0, 1.0),
                                      (1.0, 1.0), (1.0, -1.0)))
    g = _geom_at(0.0, 0.0, -7.0)
    with_datum = AR.anchor_for(AR.BASIN, g, lambda la, lo: 100.0, (), (rim,),
                               tol_m=0.3,
                               datum=AR.datum_of(_member_like(plate_y=-3.82,
                                                              plate_stations=st)))
    without = AR.anchor_for(AR.BASIN, g, lambda la, lo: 100.0, (), (rim,),
                            tol_m=0.3)
    assert with_datum == without and "basin rim" in without.reason


def test_the_deck_top_is_the_datum_of_a_span_over_water():
    """§16e (2): a deck member whose ring stands over NO graded face
    (``deck_datum_z`` None) and whose components reach no ground within
    the ring anchors so that its TOP lands at the ground at the END
    LINES, and a station ON WATER is discarded (R12 amendment 1: the mesh
    is a datum at 0.00 over the canal)."""
    import types
    st = ((0.0, 0.0), (0.0, 1e-4), (0.0, 2e-4))
    m = _member_like(deck_kind="flag", deck_top_y=3.58, deck_end_stations=st)
    d = AR.datum_of(m)
    assert d is not None and d.y == 3.58 and d.label == "deck top"
    # ... a flyover with land under its ring is UNTOUCHED
    assert AR.datum_of(_member_like(deck_kind="flag", deck_top_y=9.56,
                                    deck_datum_z=3.96,
                                    deck_end_stations=st)) is None
    # ... and a deck whose own components reach the ground is not one
    assert AR.datum_of(_member_like(
        deck_kind="flag", deck_top_y=3.58, deck_end_stations=st,
        parts=(types.SimpleNamespace(feet=((0.0, 0.0, 0.0),)),))) is None

    zs = {(0.0, 0.0): 0.0, (0.0, 1e-4): 3.90, (0.0, 2e-4): 3.96}

    def surface(la, lo):
        return zs[(round(la, 8), round(lo, 8))]
    surface.water = lambda la, lo: zs[(round(la, 8), round(lo, 8))] == 0.0
    a = AR.anchor_for(AR.DECK, _geom_at(0.5, 0.5, 9.0), surface, tol_m=0.3,
                      datum=d)
    assert a.datum is True and a.y_zero == 3.58 and a.surface_z == 3.96
    assert "1 on water" in a.reason
    # the deck TOP renders at the land, and the feet land where they may
    assert abs((a.surface_z - a.y_zero) + 3.58 - 3.96) < 1e-9
    # a caller that hands no water bit reads every sample as land
    bare = AR.anchor_for(AR.DECK, _geom_at(0.5, 0.5, 9.0),
                         lambda la, lo: zs[(round(la, 8), round(lo, 8))],
                         tol_m=0.3, datum=d)
    assert bare.surface_z == 3.90 and bare.datum is True


def test_a_datum_body_is_never_elevated_and_never_kept_on_its_row():
    """§16e: the two gates that threw the datum away at the last step.

    ``is_elevated`` reads a ``y_zero`` above ``elevated_base_m`` as a roof
    set on the ground — and a crest plate's ``y_zero`` is +5 … +10 m BY
    CONSTRUCTION, so every wall was handed to a carrier or to "its own
    ground" after the datum had chosen its anchor (measured on the OTHH
    1.0.326 frame: all nine walls, crest +2.71 … +10.78 m over the band).
    The keep test is the same sentence on the row."""
    flat = AR.Anchor(AR.OTHER, 0.0, 0.0, 5.0, "", 10.0)
    on_datum = _dc_replace(flat, datum=True)
    assert _PC.is_elevated(0.0, flat, 0.5) is True
    assert _PC.is_elevated(0.0, on_datum, 0.5) is False
    assert _PC.is_elevated(9.0, on_datum, 0.5) is False


def _dc_replace(a, **kw):
    import dataclasses
    return dataclasses.replace(a, **kw)


def test_the_keep_test_reads_the_zero_a_datum_body_would_lose():
    """§16e: ``keep_off_row`` — §14's row test with §16e's case added.

    Two surfaces agreeing says nothing for a DATUM body: OTHH's `tunnel
    middle - east` reads the same ground at its wall band (2.62) as at
    its row, so §14's reading KEPT it, X-Plane draped its zero on the
    ground and its crest stood +5 m over the rim."""
    plain = AR.Anchor(AR.OTHER, 0.0, 0.0, 0.0, "", 100.0)
    assert AR.keep_off_row(100.0, plain, 0.3) is False
    assert AR.keep_off_row(101.0, plain, 0.3) is True
    assert AR.keep_off_row(None, plain, 0.3) is False      # no reading
    assert AR.keep_off_row(100.0, None, 0.3) is False      # no body
    crest = AR.Anchor(AR.BASIN, 0.0, 0.0, 5.0, "", 100.0, datum=True)
    assert AR.keep_off_row(100.0, crest, 0.3) is True


def test_a_flag_decks_end_lines_come_from_its_ring():
    """§16e (2): a SIGNATURE deck's plate hands its ends over; a FLAG
    deck — every bridge OTHH's pack authors — has none, so the ends are
    derived from the RING: the two extreme cross-sections of its
    principal axis."""
    from auto_patch_v2.airport import rebake_plan as RP
    # a 100 m x 10 m deck in lat/lon (about 9e-4 x 9e-5 degrees)
    ring = ((0.0, 0.0), (0.0, 1e-3), (1e-4, 1e-3), (1e-4, 0.0))
    ends = RP.ring_ends(ring)
    assert ends is not None
    lons = {round(p[1], 8) for e in ends for p in e}
    assert lons == {0.0, 1e-3}                  # the two SHORT sides
    for a, b in ends:
        assert round(a[1], 8) == round(b[1], 8)  # each end line runs across
        assert {round(a[0], 8), round(b[0], 8)} == {0.0, 1e-4}
    st = RP.end_line_stations(ends, 2.0)
    assert len(st) >= 12 and all(round(p[1], 8) in (0.0, 1e-3) for p in st)
    assert RP.ring_ends(((0.0, 0.0), (0.0, 1.0))) is None


# ── §16d THE PLAN BOXES WHAT THE WRITER WRITES (RULINGS 2026-09-13h) ─────

def _plate_object(tmp_path, name="plate.obj"):
    """A building at the origin PLUS the FS2XPlane origin plate: a
    one-sided zero-thickness 10 x 10 m quad at y = -5, which the plan's
    thickness gate never admits as a part and the writer emits anyway."""
    v = [(0.0, 0.0, 0.0), (8.0, 0.0, 0.0), (8.0, 6.0, 0.0), (0.0, 6.0, 0.0),
         (0.0, 0.0, 8.0), (8.0, 0.0, 8.0), (8.0, 6.0, 8.0), (0.0, 6.0, 8.0)]
    t = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
         (0, 1, 5), (0, 5, 4), (3, 2, 6), (3, 6, 7)]
    # the plate, 500 m away in z and 5 m down — its own component
    base = len(v)
    v += [(-5.0, -5.0, 500.0), (5.0, -5.0, 500.0),
          (5.0, -5.0, 510.0), (-5.0, -5.0, 510.0)]
    t += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return _write_obj(tmp_path / name, v, [("", t)])


def _building_comp(path):
    """The index of the BUILDING's component (the one with thickness) —
    ``solid_components`` orders by welded-vertex label, not by authoring
    order, so the test asks rather than assumes."""
    g = obj8.parse_obj8(str(path))
    cs = obj8.solid_components(g)
    return max(range(len(cs)), key=lambda i: cs[i].max_y - cs[i].min_y)


def test_16d_1_a_component_beyond_the_reach_is_its_own_body(tmp_path):
    """§16d (1): the plate is 500 m from the building's parts, so it is
    NOT the building's — it becomes its own footless body, and every
    body's ``geom_box`` contains its own written triangles."""
    path = _plate_object(tmp_path)
    plan = _member_plan(path, [(_building_comp(path), 0.0, 0.0, 0.0)],
                        span_m=8.0)
    ss = PP.build_splits(plan, _flat(100.0), write=True,
                         coarsen_reach_m=100.0, **_elev_args())
    assert ss.counts["orphan_components_own_body"] >= 1
    bodies = [b for s in ss.splits for b in s.bodies] or \
             [b for s in ss.whole for b in s.bodies]
    assert len(bodies) >= 2
    plate = [b for b in bodies if PP.OWN_GROUND in (b.anchor.reason or "")]
    assert plate, [b.anchor.reason for b in bodies]
    # its authored y is KEPT: the plate renders 5 m under its own ground
    assert abs(plate[0].anchor.y_zero) < 1e-6


def test_16d_1_every_written_triangle_lies_inside_its_body_box(tmp_path):
    """§16d (1)'s BAR, as a twin: the triangles ``obj8_split`` puts in a
    body's file all lie inside the ``geom_box`` the plan published for
    it.  This is the property ``placement_seams.census_outside_box``
    reads on a written pack (LEMD 390 bodies -> 0)."""
    path = _plate_object(tmp_path, "plate2.obj")
    plan = _member_plan(path, [(_building_comp(path), 0.0, 0.0, 0.0)],
                        span_m=8.0)
    ss = PP.build_splits(plan, _flat(100.0), write=True,
                         coarsen_reach_m=100.0, **_elev_args())
    geom = obj8.parse_obj8(str(path))
    v = geom.vertices
    for s in ss.splits:
        for b in s.bodies:
            box = b.geom_box
            assert box, b.new_resource
            tris = list(b.tris)
            for ci in b.cut_components:
                tris.extend(tuple(int(q) for q in row)
                            for row in obj8.solid_components(geom)[ci]
                            .tris.tolist())
            for tri in tris:
                for i in tri:
                    la, lo = _CUT.authored_latlon(
                        float(v[i, 0]), float(v[i, 2]),
                        s.lat, s.lon, s.heading)
                    assert box[0] - 1e-7 <= la <= box[2] + 1e-7, b.new_resource
                    assert box[1] - 1e-7 <= lo <= box[3] + 1e-7, b.new_resource


def test_16d_2_the_nearest_footed_fallback_is_capped(tmp_path):
    """§16d (2): a footed body a kilometre away is not this body's
    ground.  Uncapped the search took it (35 binds at LEMD, 19 over
    100 m, one 3,323 m); capped at ``coarsen_reach_m`` the body takes its
    own ground instead."""
    cands = [_PC.Candidate(0, "far.obj",
                           AR.Anchor(AR.OTHER, 41.0, -3.0, 0.0, "far", 100.0),
                           frozenset({99}), 4,
                           (41.0, -3.0, 41.0001, -2.9999), ground_off=0.0)]
    box = (40.0, -3.0, 40.0001, -2.9999)
    far = _PC.carriers_for(frozenset({1}), box, cands, {}, (),
                           tol_m=0.3, solid_cands=cands)
    assert far and "nearest footed body" in far[0][1]
    capped = _PC.carriers_for(frozenset({1}), box, cands, {}, (),
                              tol_m=0.3, solid_cands=cands, reach_m=100.0)
    assert capped == []


def test_16d_3_the_cockpit_coordinate_is_the_bodys_not_the_row(tmp_path):
    """§16d (3): at a SHARED-DATUM pack every body sits on one of two
    placement rows, so naming the worst row by its row sent the owner to
    the wrong place.  The coordinate is the centre of the body's own
    written geometry."""
    from auto_patch_v2.airport import placement_cockpit as PCK
    splits = [{"placement": {"resource": "objects/src.obj",
                             "lat": 40.4928202, "lon": -3.5647927},
               "bodies": [{"new_resource": "objects/src__b0.obj",
                           "geom_box": (40.40, -3.60, 40.41, -3.59)},
                          {"new_resource": "objects/src__b1.obj",
                           "geom_box": (40.50, -3.50, 40.51, -3.49)}]}]
    at = PCK._cockpit_coords(splits)
    la, lo = at["objects/src__b0.obj"]
    assert abs(la - 40.405) < 1e-9 and abs(lo + 3.595) < 1e-9
    la, lo = at["objects/src__b1.obj"]
    assert abs(la - 40.505) < 1e-9 and abs(lo + 3.495) < 1e-9
    # the PLACEMENT's own row is the hull of its bodies' geometry, never
    # the shared datum
    la, lo = at["objects/src.obj"]
    assert abs(la - 40.455) < 1e-9


# ── §16d (4)–(6) (owner RULINGS 2026-09-13m) ─────────────────────────────

def test_16d_4_each_atom_of_a_carried_body_finds_its_own_carrier(tmp_path):
    """§16d (4): a roof resource of separate plates over buildings at two
    heights is TWO pieces at two zeros — the atom asks its own question,
    before the search, not after it.  (The pre-13m route asked once for
    the whole body and cut the answer; at KCLT a native pack's master
    roof model spans 1,774 m and 5,295 carried bodies were left uncut.)"""
    va, ta = _box(-2.0, -2.0)
    a_path = _write_obj(tmp_path / "a4.obj", va, [("", ta)])
    vb, tb = _box(38.0, -2.0)
    b_path = _write_obj(tmp_path / "b4.obj", vb, [("", tb)])
    rv, rt = _panels(-10.0, 50.0, 6.0, 12)
    roof = _write_obj(tmp_path / "roof4.obj", rv, [("", rt)])
    plan = _unit_plan([
        (a_path, [(0, 0.0, 0.0, 0.0, 0.0, 10.0)], "objects/a4.obj"),
        (b_path, [(0, 0.0, 0.0, 40.0, 0.0, 10.0)], "objects/b4.obj"),
        (roof, [(0, 6.0, 0.0, 20.0, 6.0, 30.0)], "objects/roof4.obj"),
    ])
    surface = _stepped([(-12.0, 12.0, 600.0), (28.0, 52.0, 610.0)])
    ss = PP.build_splits(plan, surface, write=False, **_elev_args())
    r = [s for s in ss.all if s.resource == "objects/roof4.obj"][0]
    assert len(r.bodies) == 2
    assert sorted(round(b.anchor.surface_z - b.anchor.y_zero, 3)
                  for b in r.bodies) == [600.0, 610.0]
    assert ss.counts.get("carried_bodies_cut_by_atom", 0) >= 1


def test_16d_5_the_ground_bound_holds_inside_one_member_too():
    """§16d (5): the 12ap bound tested `member != top.member`, so a
    same-member bind across a kilometre was never checked — KCLT's
    `005_ALB__b9` sank 5.04 m into its pad on one."""
    from auto_patch_v2.airport import placement_atom as ATOM
    box = (40.0, -3.0, 40.0005, -2.9995)
    near = (40.0004, -3.0, 40.0009, -2.9995)
    senior_n = ATOM.RigidNode(0, frozenset([1]), box, footprint_m2=100.0,
                              footed=True, bindable=True, zero=600.0, feet=8)
    sunk_same = ATOM.RigidNode(0, frozenset([2]), near, footprint_m2=10.0,
                               footed=True, bindable=True, zero=605.0, feet=2)
    cnt: dict = {}
    sen, _c = ATOM.unit_rigid([senior_n, sunk_same], [(1, 2)],
                              bind_ground_m=0.5, counts=cnt)
    assert sen == [-1, -1]
    assert cnt["bind_refused_for_ground"] == 1


def test_16d_6_a_body_anchors_on_the_pad_it_stands_on():
    """§16d (6): a body whose ground contacts lie MOSTLY on a `building`
    pad reads only the contacts ON it.  KCLT's terminal spilled 133 of
    213 bodies' anchors onto the apron beside its one pad, and their
    zeros spread 13 m against the pad's own 1.19 m of relief."""
    pad = AR.PadRing("building80", ((40.0000, -3.0010), (40.0000, -2.9990),
                                    (40.0010, -2.9990), (40.0010, -3.0010)))

    def surface(la, lo):
        # the pad at 600, the apron beside it 6 m lower
        return 600.0 if -3.0010 <= lo <= -2.9990 else 594.0

    # three contacts on the pad, one spilled onto the apron
    geom = AR.BodyGeometry(
        ((40.0002, -3.0005, 0.0, ((40.0002, -3.0005, 0.0),)),
         (40.0004, -3.0002, 0.0, ((40.0004, -3.0002, 0.0),)),
         (40.0006, -3.0000, 0.0, ((40.0006, -3.0000, 0.0),)),
         (40.0008, -2.9980, 0.0, ((40.0008, -2.9980, 0.0),))),
        40.0004, -3.0000)
    off = AR.anchor_for(AR.OTHER, geom, surface, (), tol_m=0.3)
    on = AR.anchor_for(AR.OTHER, geom, surface, (pad,), tol_m=0.3)
    assert "on pad building80" in on.reason
    assert on.surface_z == 600.0
    # the pad's own contacts agree, so the body takes ONE zero plane and
    # no low-side residual; without the pad the apron contact drags it
    assert "low-side foot" in off.reason
    assert off.surface_z == 594.0


# ── §16e (3)/(5)/(6) (Fable 2026-09-13; RULINGS 2026-09-13v) ─────────────

def test_the_deck_end_line_datum_walks_landward_to_the_graded_ground():
    """§16e (6): the datum is the graded face the deck CONNECTS TO, not
    the bank under the end line.

    OTHH's ``Bridge_01`` end lines stand on the canal bank — the mesh
    reads 1.89 … 3.23 at one end and 2.55 … 3.96 at the other, the pooled
    median is 3.23 and the deck seated 0.73 m BELOW the road at 3.96 that
    drives onto it.  Each end line shifts LANDWARD, away from the span,
    until it is DRY and LEVEL, which is where it has left the bank."""
    # two end lines 20 m apart in latitude; LANDWARD is away from the
    # other end.  The bank rises over the first 14 m of each walk and is
    # UNEVEN across the line while it does (the reading the walk leaves).
    M = 111_132.954
    ends = (((0.0, 0.0), (0.0, 2e-5)), ((-2e-4, 0.0), (-2e-4, 2e-5)))

    def surface(la, lo):
        d = la * M if la >= -1e-4 else (-2e-4 - la) * M
        d = max(d, 0.0)
        if d >= 14.0:
            return 3.96
        return 1.9 + (d / 14.0) * 2.06 + (0.5 if lo > 1e-5 else 0.0)

    # ...and one station of the NEAR end line itself is over water
    surface.water = lambda la, lo: abs(la) < 1e-9 and lo > 1.5e-5

    d = AR.Datum(3.575, tuple(p for e in ends for p in e), "deck top",
                 ends=ends, step_m=5.0, walk_max_m=60.0, level_tol_m=0.3)
    a = AR.anchor_for(AR.DECK, _geom_at(-1e-4, 1e-5, 9.0), surface,
                      tol_m=0.3, datum=d)
    assert a.datum is True and a.y_zero == 3.575
    # the deck top lands ON the graded road, not on the bank
    assert abs(a.surface_z - 3.96) < 1e-6
    assert "landward walk 15 m / 15 m" in a.reason
    # ...and with the walk DISARMED (no ends, no step) the pooled median
    # of the end lines stands, which is §16e (2) exactly
    d0 = AR.Datum(3.575, tuple(p for e in ends for p in e), "deck top")
    a0 = AR.anchor_for(AR.DECK, _geom_at(-1e-4, 1e-5, 9.0), surface,
                       tol_m=0.3, datum=d0)
    assert a0.surface_z < 3.0 and "landward walk" not in a0.reason


def test_the_landward_walk_keeps_its_stations_when_it_never_finds_land():
    """§16e (6): a walk that never meets dry, level ground keeps the
    ORIGINAL stations — no reading is no evidence."""
    ends = (((0.0, 0.0), (0.0, 2e-5)), ((-2e-4, 0.0), (-2e-4, 2e-5)))
    surface = lambda la, lo: 0.0                                    # noqa: E731
    surface.water = lambda la, lo: True
    d = AR.Datum(3.5, tuple(p for e in ends for p in e), "deck top",
                 ends=ends, step_m=5.0, walk_max_m=20.0, level_tol_m=0.3)
    pts, note = AR._walked_stations(d, surface, surface.water)
    # the BASE lines, un-shifted (the walk subdivides them at ``step_m``)
    assert note.count("-") == 2
    assert {round(q[0], 8) for q in pts} == {0.0, -2e-4}


def test_a_bridge_is_named_by_contact_with_the_decks_model_footprint():
    """§16e (3): the deck's FOOTPRINT POLYGON is its mesh projected to
    plan — not its ring, which is a bbox.  A point in the bbox but off
    the polygon belongs to no bridge."""
    from auto_patch_v2.airport import bridge_family as BF
    # an L-shaped deck: two triangles filling the lower-left of its bbox
    tris = ((((0.0, 0.0), (0.0, 1e-3), (1e-3, 0.0))),
            (((0.0, 1e-3), (1e-3, 0.0), (2e-4, 1e-3))))
    p = BF.DeckPrint(key="deck_a", unit=0, member=0, under_y=8.0,
                     box=(0.0, 0.0, 1e-3, 1e-3), tris=tris)
    p.index()
    assert p.contains(1e-4, 1e-4) is True            # inside the polygon
    assert p.contains(9e-4, 9e-4) is False           # inside the BBOX only
    # ...and the 0.5 m reach admits a body just proud of the plate
    assert p.contains(-3e-6, 5e-4, 0.5) is True
    assert p.contains(-3e-5, 5e-4, 0.5) is False
    assert BF.bridge_of_point((p,), 1e-4, 1e-4) is p
    assert BF.bridge_of_point((p,), 9e-4, 9e-4) is None


def test_two_containing_decks_go_to_the_underside_nearest_the_body_top():
    """§16e (3): where two deck footprints both contain the body, the
    deck whose UNDERSIDE is nearest the body's TOP wins (absolute
    vertical distance — §16c (4)'s own rest-on reading).  OTHH's
    Bridge_02/03/06 are an INTERCHANGE and their footprints overlap."""
    from auto_patch_v2.airport import bridge_family as BF
    square = (((0.0, 0.0), (0.0, 1e-3), (1e-3, 1e-3)),
              ((0.0, 0.0), (1e-3, 1e-3), (1e-3, 0.0)))
    lo = BF.DeckPrint("low", 0, 0, 4.0, (0.0, 0.0, 1e-3, 1e-3), square)
    hi = BF.DeckPrint("high", 0, 1, 12.0, (0.0, 0.0, 1e-3, 1e-3), square)
    lo.index(); hi.index()
    assert BF.bridge_of_point((lo, hi), 5e-4, 5e-4, 11.5).key == "high"
    assert BF.bridge_of_point((lo, hi), 5e-4, 5e-4, 3.6).key == "low"
    # with no top to read, the LOWER underside wins
    assert BF.bridge_of_point((lo, hi), 5e-4, 5e-4, None).key == "low"


def test_the_bridge_census_reads_the_plans_own_rows():
    """§16e (3)'s bars, over the placement plan's own shape — the census
    ``seat_feet_census`` and ``obj8_split_report`` both print."""
    from auto_patch_v2.airport import bridge_family as BF
    assert BF.bridge_tag("Buildings/Bridges Bus/OTHH_Bridge_02_CLUTTER.obj") \
        == "Bridge_02"
    assert BF.bridge_tag("Buildings/Terminal/T4.obj") == ""

    def body(res, cls="other", sz=4.0, y0=0.0, mi=None, of=None):
        return {"new_resource": res, "class": cls, "surface_z": sz,
                "y_zero": y0, "merged_into": mi, "bridge_of": of,
                "anchor_reason": "", "geom_pts": []}
    splits = [
        {"placement": {"resource": "x/OTHH_Bridge_01_LOD0_000.obj"},
         "bodies": [body("x/B1_deck.obj", "deck", 3.96, 3.575,
                         of="x/OTHH_Bridge_01_LOD0_000.obj")]},
        {"placement": {"resource": "x/OTHH_Bridge_01_CLUTTER.obj"},
         "bodies": [body("x/B1_c0.obj", sz=4.0, y0=0.0),
                    body("x/B1_c1.obj", sz=9.0, y0=0.0)]},
        {"placement": {"resource": "x/OTHH_Bridge_02_CLUTTER.obj"},
         "bodies": [body("x/B2_c0.obj", mi="x/B1_c0.obj")]},
    ]
    c = BF.census_bridges(splits)
    assert c["total"] == 4 and c["published"] == 1 and c["agree"] == 1
    assert c["by_tag"]["Bridge_01"]["deck_top"] == 3.96
    # the CLUTTER placement's two bodies stand 5 m apart
    assert round(c["spreads"][0][0], 2) == 5.0
    assert c["spreads"][0][1] == "Bridge_01"
    # ...and the Bridge_02 body carried by a Bridge_01 file is the cross
    assert [q[0] for q in c["cross"]] == ["Bridge_02"]
    lines = BF.census_bridges_lines(c)
    assert any("CROSS-BRIDGE carriers (BAR 0): 1" in q for q in lines)
    assert any("Bridge_01" in q for q in lines)


def test_a_partless_deck_member_is_a_body():
    """§16e (5): a deck member whose partition found no genuine solid
    (``parts 0``: OTHH's ``Bridge_04`` / ``Bridge_05``, a 0.14 m-thick
    plate) is ADMITTED as one body whose footprint is the model's
    DECLARED BOUNDS — the §16 (1) population class, not a skip.

    A partless member with NO datum is untouched: it has no height the
    law could put anywhere."""
    from auto_patch_v2.airport import placement_body as PB

    class _Comp:
        def __init__(self):
            import numpy as np
            self.tris = np.asarray([[0, 1, 2]], dtype=np.int64)
            self.min_y, self.max_y = 4.51, 4.65
            self.cx, self.cz = 0.0, 0.0

    class _Cut:
        lat, lon = 25.25, 51.62

        def __init__(self, ok=True):
            import numpy as np
            self._ok = ok
            self._comps = [_Comp()] if ok else []
            self._geom = type("G", (), {"vertices": np.asarray(
                [[0.0, 4.51, 0.0], [10.0, 4.65, 0.0], [0.0, 4.6, 10.0]])})()

        def _read(self):
            return self._ok

    m = _member_like(deck_kind="flag", deck_top_y=4.65,
                     deck_end_stations=((25.25, 51.62),))
    m.id = "dsf:obj14031"
    m.heading_deg = 0.0
    parts = PB._declared_parts(m, _Cut())
    assert len(parts) == 1
    p = parts[0]
    assert p.comp == 0 and p.feet == () and p.base_y == 4.51
    assert p.pid < 0                      # never a pid the plan published
    assert p.box[0] <= _Cut.lat <= p.box[2] and p.area_m2 > 0.0
    # the file that cannot be read contributes nothing
    assert PB._declared_parts(m, _Cut(ok=False)) == []


# ── §16f AN OBJECT FAMILY STAYS TOGETHER (RULINGS 2026-09-13af) ──────────

def _fam_cand(member, box, z, cls=None, group=0):
    """One footed candidate at plan ``box`` whose zero plane is ``z``."""
    import auto_patch_v2.airport.placement_carrier as _PC0
    return _PC0.Candidate(member, f"objects/m{member}.obj",
                          AR.Anchor(cls or AR.BUILDING,
                                    0.5 * (box[0] + box[2]),
                                    0.5 * (box[1] + box[3]), 0.0, "r", z),
                          frozenset({member}), 4, box, part_boxes=[box],
                          group=group, body_class=cls or AR.BUILDING,
                          fill=1.0, ground_off=0.0)


class _FamStaged:
    """The two fields ``bind_families`` reads off a staged member."""

    def __init__(self, mi, resource, feet):
        import types
        self.mi = mi
        self.m = types.SimpleNamespace(resource=resource)
        # ONE raw body per member, group 0: (parts, class, anchor, feet, ...)
        self.raw = [([], AR.BUILDING, AR.Anchor(AR.BUILDING, feet[0][0],
                                                feet[0][1], 0.0, "r", 0.0),
                     tuple(feet), False, (), (), None)]
        self.groups = [[0]]
        self.ground_off = [0.0]


def test_16f_1_a_family_is_a_connected_plan_cluster_of_two_members():
    """§16f (1)(b): the family is the CONNECTED PLAN CLUSTER, and it is
    read at the BODY footprint — two members whose footprints touch are
    one family; a third standing apart is not in it (§16f (2): it is cut
    to its own ground)."""
    from auto_patch_v2.airport import placement_family as FAM
    walls = _fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0)
    roof = _fam_cand(1, (40.0005, -3.0005, 40.0015, -2.9985), 103.0)
    away = _fam_cand(2, (40.0100, -3.0100, 40.0110, -3.0090), 90.0)
    cl, adj = FAM._clusters([walls, roof, away], 0.002)
    assert cl == [[0, 1]] and adj == {0: {1}, 1: {0}}                      # the far member is not in it
    # ... and one member's own two bodies are NOT a family by themselves
    solo = _fam_cand(0, (40.0005, -3.0005, 40.0015, -2.9985), 103.0, group=1)
    assert FAM._clusters([walls, solo], 0.002)[0] == []


def test_16f_1_two_placement_rows_do_not_make_a_family():
    """The LEMD trap named in the ruling: a shared-datum pack puts 2,035
    of 2,109 bodies on two rows.  The ROW (the unit) is only condition
    (a); nothing binds without the plan cluster."""
    from auto_patch_v2.airport import placement_family as FAM
    apart = [_fam_cand(i, (40.0 + 0.01 * i, -3.0, 40.001 + 0.01 * i, -2.999),
                       100.0 + i) for i in range(4)]
    assert FAM._clusters(apart, 0.002)[0] == []
    counts: dict = {}
    assert FAM.bind_families(apart, [], lambda la, lo: 100.0, (), counts,
                             unit_id="unit:1", contact_eps_m=0.002) == []
    assert not counts.get("families")


def test_16f_2_the_family_takes_one_zero_plane_on_its_pad():
    """§16f (2): the family's bodies take ONE zero — the pad their
    contacts mostly stand on — and every member's own zero IS that plane
    afterwards, whatever the ground under it does."""
    from auto_patch_v2.airport import placement_family as FAM
    pad = AR.PadRing("building80", ((39.999, -3.001), (40.003, -3.001),
                                    (40.003, -2.997), (39.999, -2.997)))
    # a surface that RISES 6 m across the complex: the defect the owner read
    def surface(la, lo):
        return 100.0 + 6000.0 * (la - 40.0)

    a = _fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0)
    b = _fam_cand(1, (40.0005, -3.0005, 40.0015, -2.9985), 106.0)
    st = [_FamStaged(0, "objects/walls.obj",
                     [(40.0000, -3.0000, 0.0), (40.0010, -2.9990, 0.0)]),
          _FamStaged(1, "objects/roof.obj",
                     [(40.0005, -3.0005, 0.0), (40.0015, -2.9985, 0.0)])]
    counts: dict = {}
    cands = [a, b]      # mutated in place, as ``bind_unit`` mutates it
    fams = FAM.bind_families(cands, st, surface, (pad,), counts,
                             unit_id="unit:9", contact_eps_m=0.002)
    assert len(fams) == 1 and fams[0].pad == "building80"
    assert counts["bodies_bound_to_family"] == 2
    zeros = [c.anchor.surface_z - c.anchor.y_zero for c in cands]
    assert max(zeros) - min(zeros) < 1e-9      # ONE plane, exactly
    assert all(c.anchor.family == fams[0].id for c in cands)


def test_16f_3_a_partial_cluster_is_reported_and_not_bound():
    """§16f (3): FEASIBILITY IS MEASURED.  A cluster holding a small
    fragment of its unit is a PARTIAL family — OTHH's bridge clutter
    beside the deck plate (§16e (3) WITHDRAWN) and KCLT's unit:3, eight
    separate hangars — and a partly-bound family is worse than an unbound
    one, so it is reported per body and never bound."""
    from auto_patch_v2.airport import placement_family as FAM
    pair = [_fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0),
            _fam_cand(1, (40.0005, -3.0005, 40.0015, -2.9985), 103.0)]
    fragments = [_fam_cand(2 + i,
                           (40.05 + 0.01 * i, -3.0, 40.051 + 0.01 * i, -2.999),
                           100.0) for i in range(6)]
    cands = pair + fragments
    counts: dict = {}
    assert FAM.bind_families(cands, [], lambda la, lo: 100.0, (), counts,
                             unit_id="unit:3", contact_eps_m=0.002) == []
    assert counts.get("family_partial_clusters") == 1
    assert not counts.get("families")


def test_16f_4_one_plane_per_pad_and_the_pads_own_plane():
    """§16f (4) (RULINGS 2026-09-13aq (i)): a family over TWO pads is TWO
    planes, each the median of ITS OWN pad's graded ring — so one pad is
    one plane however many families stand on it and whichever unit the
    walk reaches first (KCLT's two terminal rows read 221.78 and 221.45
    off their own contacts and the 0.33 m between them was the pad's
    relief sampled twice)."""
    from auto_patch_v2.airport import placement_family as FAM
    west = AR.PadRing("building1", ((39.9995, -3.0010), (40.0012, -3.0010),
                                    (40.0012, -2.9993), (39.9995, -2.9993)),
                      (100.0, 100.0, 100.0, 100.0))
    east = AR.PadRing("building2", ((39.9995, -2.9992), (40.0020, -2.9992),
                                    (40.0020, -2.9970), (39.9995, -2.9970)),
                      (108.0, 108.0, 108.0, 108.0))

    def surface(la, lo):
        return 108.0 if lo > -2.9992 else 100.0

    a = _fam_cand(0, (40.0000, -3.0008, 40.0008, -2.9998), 100.0)
    b = _fam_cand(1, (40.0004, -3.0000, 40.0010, -2.9988), 100.0)
    c = _fam_cand(2, (40.0006, -2.9990, 40.0014, -2.9980), 108.0)
    st = [_FamStaged(0, "objects/w.obj", [(40.0002, -3.0006, 0.0),
                                          (40.0006, -3.0002, 0.0)]),
          _FamStaged(1, "objects/m.obj", [(40.0006, -2.9998, 0.0),
                                          (40.0008, -2.9996, 0.0)]),
          _FamStaged(2, "objects/e.obj", [(40.0008, -2.9988, 0.0),
                                          (40.0012, -2.9984, 0.0)])]
    cands = [a, b, c]
    counts: dict = {}
    fams = FAM.bind_families(cands, st, surface, (west, east), counts,
                             unit_id="unit:4", contact_eps_m=0.002,
                             bind_ground_m=0.5)
    planes = {f.pad: f.zero_z for f in fams}
    assert planes == {"building1": 100.0, "building2": 108.0}
    assert {c.anchor.family for c in cands} == {"unit:4#0@building1",
                                                "unit:4#0@building2"}
    # the two west members are one plane, the east one its own: the step
    # falls at the pad frontage the design surface already terraces
    zs = [c.anchor.surface_z - c.anchor.y_zero for c in cands]
    assert zs[0] == zs[1] == 100.0 and zs[2] == 108.0


def test_16f_5_pavement_is_king_over_the_family():
    """§16f (5) (RULINGS 2026-09-13aq (ii)): a member whose ground
    contacts are ALL on rolled-on pavement is CUT APART from its family
    and stays on that pavement — an object never moves the aircraft.
    Round 1 held a KCLT terminal wall +2.99 m over the apron."""
    from auto_patch_v2.airport import placement_family as FAM

    class _Roles:
        def roles_many(self, las, los):
            return ["apron"] * len(las)

    def surface(la, lo):
        return 100.0
    surface.roles = _Roles()
    surface.rolled_on = frozenset({"apron"})

    pad = AR.PadRing("building7", ((39.999, -3.001), (40.003, -3.001),
                                   (40.003, -2.997), (39.999, -2.997)),
                     (100.0, 100.0, 100.0, 100.0))
    a = _fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0)
    b = _fam_cand(1, (40.0005, -3.0005, 40.0015, -2.9985), 100.0)
    st = [_FamStaged(0, "objects/wall.obj", [(40.0000, -3.0000, 0.0)]),
          _FamStaged(1, "objects/roof.obj", [(40.0005, -3.0005, 0.0)])]
    counts: dict = {}
    assert FAM.bind_families([a, b], st, surface, (pad,), counts,
                             unit_id="unit:5", contact_eps_m=0.002,
                             bind_ground_m=0.5) == []
    assert counts["family_bodies_on_pavement"] == 2
    # ... and with no roles on the surface the reading is no evidence
    bare = lambda la, lo: 100.0            # noqa: E731
    c2 = [_fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0),
          _fam_cand(1, (40.0005, -3.0005, 40.0015, -2.9985), 100.0)]
    assert FAM.bind_families(c2, st, bare, (pad,), {},
                             unit_id="unit:5", contact_eps_m=0.002,
                             bind_ground_m=0.5)


def test_16f_4_the_ground_bound_holds_at_the_pad_join():
    """§16f (4) + §16d (5): a member the pad group would pick up BY
    CONTACT while its own ground stands further than ``bind_ground_m``
    below the pad's plane is CUT TO ITS OWN GROUND — measured, those are
    the members that came out +4.44 (KCLT), +8.92 (LEMD) and +12.21 m
    (OTHH) above their own ground when the join was unbounded."""
    from auto_patch_v2.airport import placement_family as FAM
    pad = AR.PadRing("building9", ((39.9995, -3.0010), (40.0012, -3.0010),
                                   (40.0012, -2.9993), (39.9995, -2.9993)),
                     (100.0, 100.0, 100.0, 100.0))

    def surface(la, lo):
        return 100.0 if lo <= -2.9993 else 92.0        # a 8 m drop off the pad

    on1 = _fam_cand(0, (40.0000, -3.0008, 40.0008, -2.9999), 100.0)
    on2 = _fam_cand(1, (40.0002, -3.0006, 40.0009, -2.9997), 100.0)
    off = _fam_cand(2, (40.0006, -2.9998, 40.0014, -2.9985), 92.0)
    st = [_FamStaged(0, "objects/a.obj", [(40.0002, -3.0006, 0.0)]),
          _FamStaged(1, "objects/b.obj", [(40.0004, -3.0004, 0.0)]),
          _FamStaged(2, "objects/c.obj", [(40.0010, -2.9990, 0.0)])]
    cands = [on1, on2, off]
    counts: dict = {}
    fams = FAM.bind_families(cands, st, surface, (pad,), counts,
                             unit_id="unit:8", contact_eps_m=0.002,
                             bind_ground_m=0.5)
    assert len(fams) == 1 and fams[0].bodies == 2
    assert counts["family_bodies_off_the_pad_plane"] == 1
    assert cands[2].anchor.family == ""          # cut to its own ground


# ── §16g THE FOOTPRINT UNIT (owner RULINGS 2026-09-13bo) ─────────────────

def test_16g_1_two_bodies_that_touch_are_one_unit_whatever_their_row():
    """§16g (1): overlap or touch within ``footprint_touch_m`` binds, and
    §16f (1)'s shared-authored-datum condition is DROPPED — a deck and a
    pier standing half a metre apart are one unit though no vertex is
    shared and no row is."""
    from auto_patch_v2.airport import placement_family as FAM
    deck = _fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0)
    # 0.3 m clear of the deck in plan: the 2 mm contact test sees nothing
    pier = _fam_cand(1, (40.0010 + 0.3 / 111132.0, -3.0000,
                         40.0016, -2.9995), 100.0)
    away = _fam_cand(2, (40.0100, -3.0100, 40.0110, -3.0090), 90.0)
    assert FAM._clusters([deck, pier, away], 0.002, min_members=1)[0] == []
    cl, _adj = FAM._clusters([deck, pier, away], 0.5, min_members=1)
    assert cl == [[0, 1]]                       # the far body seats alone
    # and two bodies of ONE member bind too (min_members=1, 13bo)
    solo = _fam_cand(0, (40.0005, -3.0005, 40.0015, -2.9985), 103.0, group=1)
    assert FAM._clusters([deck, solo], 0.5, min_members=1)[0] == [[0, 1]]


def test_16g_2_the_unit_datum_is_deck_then_pad_then_ground():
    """§16g (2): ONE zero per unit, by priority.  The same three bodies
    read three ways — with a DECK member in the unit, with a pad under it,
    and with neither."""
    from auto_patch_v2.airport import footprint_unit as FU
    import types
    pad = AR.PadRing("building80", ((39.999, -3.001), (40.003, -3.001),
                                    (40.003, -2.997), (39.999, -2.997)),
                     (100.0,) * 4)

    def surface(la, lo):
        return 100.0 + 6000.0 * (la - 40.0)     # rises 6 m across the unit

    def arm(pads, deck):
        a = _fam_cand(0, (40.0000, -3.0000, 40.0010, -2.9990), 100.0)
        b = _fam_cand(1, (40.0008, -3.0005, 40.0016, -2.9985), 104.8)
        st = [_FamStaged(0, "objects/a.obj", [(40.0004, -2.9996, 0.0)]),
              _FamStaged(1, "objects/b.obj", [(40.0012, -2.9992, 0.0)])]
        if deck:
            st[0].m = types.SimpleNamespace(resource="objects/a.obj",
                                            deck_kind="flag", deck_ring=None)
        cands = [a, b]
        counts: dict = {}
        got = FU.bind_footprint_units(cands, st, surface, pads, counts,
                                      unit_id="unit:1", touch_m=0.5,
                                      visual_m=0.5, cluster_min_m2=0.0,
                                      connector_span_m=0.0)
        zs = [c.anchor.surface_z - c.anchor.y_zero for c in cands]
        return got, zs, counts

    got, zs, counts = arm((pad,), True)
    assert zs[0] == zs[1] and counts["unit_datum_deck"] == 1
    assert got[0].zero_z == 100.0               # the deck's own zero leads
    got, zs, counts = arm((pad,), False)
    assert zs[0] == zs[1] == 100.0 and counts["unit_datum_pad"] == 1
    assert got[0].pad == "building80"
    got, zs, counts = arm((), False)
    assert zs[0] == zs[1] and counts["unit_datum_ground"] == 1
    # one zero per unit in every arm — that is the whole of §16g (2)
    assert got[0].spread_before_m > 0.0


def test_16g_3_only_a_long_connector_with_a_step_is_cut():
    """§16g (3) AS AMENDED BY §16g (6) (owner RULINGS 2026-09-13cn): the
    HECA elevated-rail class and nothing else — span, end-ground step AND
    a TOPOLOGY.  A long body over flat ground stays rigid, and a long body
    whose every contact chains into ONE unit is that unit's member however
    long it is (the SPJC viaduct)."""
    from auto_patch_v2.airport import footprint_unit as FU
    box = (40.0000, -3.0000, 40.0000 + 300.0 / 111132.0, -2.9990)
    long_ = _fam_cand(0, box, 100.0)
    short = _fam_cand(1, (40.0000, -2.9992, 40.0006, -2.9985), 100.0)
    ends = [(box[0], -2.9995, 0.0, 100.0), (box[2], -2.9995, 0.0, 104.0)]
    two = ("fu:0:1", "fu:0:9")
    assert FU._is_connector(long_, ends, 200.0, 0.5, ends=two) is True
    # one unit and OPEN GROUND at the other end is also a connector
    assert FU._is_connector(long_, ends, 200.0, 0.5,
                            ends=("", "fu:0:9")) is True
    flat = [(box[0], -2.9995, 0.0, 100.0), (box[2], -2.9995, 0.0, 100.1)]
    assert FU._is_connector(long_, flat, 200.0, 0.5, ends=two) is False
    assert FU._is_connector(short, ends, 200.0, 0.5, ends=two) is False
    assert FU._is_connector(long_, ends, 0.0, 0.5, ends=two) is False
    # §16g (6): EVERY CONTACT INTO ONE UNIT -> a MEMBER, not a connector
    assert FU._is_connector(long_, ends, 200.0, 0.5,
                            ends=("fu:0:1", "fu:0:1")) is False
    # and with no partition to witness the topology, nothing is a connector
    assert FU._is_connector(long_, ends, 200.0, 0.5) is False


# ── §16g round 2 (owner RULINGS 2026-09-13bw) ────────────────────────────

class _PPart:
    def __init__(self, pid, box, line=False):
        self.pid = pid
        self.box = box
        self.line = line
        self.lat = 0.5 * (box[0] + box[2])
        self.lon = 0.5 * (box[1] + box[3])
        self.base_y = 0.0
        self.feet = ()
        self.comp = 0
        self.area_m2 = 1.0


class _PMember:
    def __init__(self, resource, parts, deck_datum_z=None):
        self.id = resource
        self.resource = resource
        self.parts = tuple(parts)
        self.deck_datum_z = deck_datum_z
        self.deck_ring = None
        self.deck_kind = ""


class _PUnit:
    def __init__(self, uid, members):
        self.id = uid
        self.members = tuple(members)


class _PPlan:
    def __init__(self, units, contacts=()):
        self.units = tuple(units)
        self.contacts = tuple(contacts)


def test_16g_1_the_unit_is_derived_PLAN_WIDE_across_placement_units():
    """§16g (1) as ruled in 13bw: a deck on one placement row and its
    piers on another are ONE unit.  Round 1 derived the relation inside
    the per-``Unit`` loop and could not see across — which is why OTHH's
    `Bridge_02` / `Bridge_03` came out at 1.52 / 1.93 m of spread."""
    from auto_patch_v2.airport import footprint_unit as FU
    d = 0.3 / 111132.0
    deck = _PMember("objects/deck.obj",
                    [_PPart(1, (40.0000, -3.0000, 40.0010, -2.9990))])
    pier = _PMember("objects/pier.obj",
                    [_PPart(2, (40.0010 + d, -3.0000, 40.0016, -2.9995))])
    away = _PMember("objects/away.obj",
                    [_PPart(3, (40.0100, -3.0100, 40.0110, -3.0090))])
    plan = _PPlan([_PUnit("unit:0", [deck]), _PUnit("unit:1", [pier, away])])
    units = FU.plan_units(plan, 0.5)
    assert len(units) == 1, units
    assert set(units[0].members) == {"objects/deck.obj", "objects/pier.obj"}
    assert units[0].pids == frozenset({1, 2})       # the far member alone
    # and at §16f's millimetres nothing binds at all
    assert FU.plan_units(plan, 0.002) == []


def test_16g_2_the_plan_wide_datum_is_deck_then_pad_then_ground():
    """§16g (2) read PLAN-WIDE, AS AMENDED BY §16g (7) (owner RULINGS
    2026-09-14c item 1): a deck's datum is no longer the UNIT's — it is
    LENT, per body, to the bodies whose footprint polygons touch the deck
    (``PlanUnit.deck_pids``, overlaid in ``plan_wide_seats``), so what
    ``plan_unit_datums`` computes is the datum for everything else.  A
    deck reached by a BOX chain was handing 96.20 to 1,509 HECA bodies.
    13bo's piers still take the deck — they touch it — and the twin now
    reads that through the lending set."""
    from auto_patch_v2.airport import footprint_unit as FU
    d = 0.3 / 111132.0
    pad = AR.PadRing("building80", ((39.998, -3.002), (40.004, -3.002),
                                    (40.004, -2.996), (39.998, -2.996)),
                     (100.0,) * 4)

    def surface(la, lo):
        return 90.0

    def arm(deck_z, pads):
        deck = _PMember("objects/deck.obj",
                        [_PPart(1, (40.0000, -3.0000, 40.0010, -2.9990))],
                        deck_datum_z=deck_z)
        pier = _PMember("objects/pier.obj",
                        [_PPart(2, (40.0010 + d, -3.0000, 40.0016, -2.9995))])
        plan = _PPlan([_PUnit("unit:0", [deck]), _PUnit("unit:1", [pier])])
        units = FU.plan_units(plan, 0.5)
        return FU.plan_unit_datums(units, plan, surface, pads, 0.0)[units[0].id]

    # the deck no longer decides the UNIT's datum — the unit reads its pad
    assert arm(5.5, (pad,)) == (100.0, "building80", "pad")
    assert arm(None, (pad,)) == (100.0, "building80", "pad")
    assert arm(None, ()) == (90.0, "", "ground")


def test_16g_5_a_multi_anchor_placement_is_seated_by_its_dsf_row():
    """§16g (5) (owner 2026-09-11a/b, RULINGS 2026-09-13bw): a resource
    the plan DROPPED because one file cannot carry N seats is seated on
    the ROW — the unit's plane where it stands inside one, the surface
    where it does not.  A resource the plan HOLDS, a stock library object
    and a single-anchor row are all left alone."""
    from auto_patch_v2.airport import footprint_unit as FU
    import types

    def P(i, path, lat, lon):
        return types.SimpleNamespace(def_path=path, lat=lat, lon=lon,
                                     heading_deg=90.0, kind="OBJECT",
                                     elevation=None)

    rows = [P(0, "objects/seat.obj", 40.0005, -2.9995),   # inside the unit
            P(1, "objects/seat.obj", 40.0500, -2.9000),   # out on the field
            P(2, "objects/wall.obj", 40.0005, -2.9995),   # the plan holds it
            P(3, "objects/wall.obj", 40.0006, -2.9994),
            P(4, "objects/solo.obj", 40.0005, -2.9995)]   # one anchor only
    dump = types.SimpleNamespace(placements=rows)
    wall = _PMember("objects/wall.obj",
                    [_PPart(1, (40.0000, -3.0000, 40.0010, -2.9990))])
    plan = _PPlan([_PUnit("unit:0", [wall])])
    # THE TERRAIN IS ALREADY THE DATUM (the cluster pad under the
    # terminal): the row is LEFT ALONE and X-Plane's drape does it.
    unit = [(40.0000, -3.0000, 40.0010, -2.9990, 222.28, "cluster_pad")]
    assert FU.msl_seats_for_dump(dump, plan, unit, lambda la, lo: 222.28,
                                 "", frozenset()) == ()
    c = FU.multi_anchor_census(dump, plan, (), frozenset(), unit)
    assert c["multi_anchor_rows"] == 2 and c["multi_anchor_on_ground"] == 2
    assert c["multi_anchor_dropped"] == 0 and c["multi_anchor_in_a_unit"] == 1
    # THE ANCHOR STANDS OVER APRON BESIDE THE PAD — RE-FOUNDED at owner
    # RULINGS 2026-09-14bo.  13cb wrote the row at the unit's DATUM
    # (222.28) wherever the anchor fell; measured at LEMD that sank seven
    # vehicles 0.75-1.14 m into an apron 1 m above the unit plane.  A row
    # is now seated AT ITS OWN FEET unless it stands ON the unit's pad —
    # and with no authored offset the drape already puts it there, so the
    # row is LEFT ALONE.
    seats = FU.msl_seats_for_dump(dump, plan, unit, lambda la, lo: 219.10,
                                  "", frozenset())
    assert seats == ()
    c = FU.multi_anchor_census(dump, plan, seats, frozenset(), unit)
    assert c["multi_anchor_object_msl"] == 0 and c["multi_anchor_on_ground"] == 2
    # AND THE AUTHORED OFFSET RIDES: a second-floor passenger authored
    # +4.20 m AGL floats at the unit plane + 4.20, never on the ground
    rows[0].kind = "OBJECT_AGL"
    rows[0].elevation = 4.20
    seats = FU.msl_seats_for_dump(dump, plan, unit, lambda la, lo: 222.28,
                                  "", frozenset())
    assert [round(m.elevation, 2) for m in seats] == [226.48]
    # an OBJECT_MSL row is the pack's ABSOLUTE and needs the ground the
    # pack was authored on; with none known it is left alone, not guessed
    rows[0].kind = "OBJECT_MSL"
    rows[0].elevation = 300.0
    assert FU.msl_seats_for_dump(dump, plan, unit, lambda la, lo: 222.28,
                                 "", frozenset()) == ()
    seats = FU.msl_seats_for_dump(dump, plan, unit, lambda la, lo: 222.28,
                                  "", frozenset(), authored_ground=295.0)
    assert [round(m.elevation, 2) for m in seats] == [227.28]


# ── 14at: THE SPLIT FILE IS KEYED ON THE OFFSET IT BAKES ────────────────
# (owner RULINGS 2026-09-14at; the owner's missing OTHH tunnel wall at
# 25.2697569, 51.6055534).  ``body_resource_name`` named the written file
# on resource + body id ONLY, while ``authored_offset`` is per PLACEMENT:
# OTHH's ``tunnels/tunnel1.obj`` stands at two anchors 38.7 m apart, both
# placements wrote ``tunnels/tunnel1__b0.obj``, the file baked the first
# placement's translation and the second wall rendered 38.7 m from its
# own DSF row.

def test_the_split_file_name_is_a_function_of_the_baked_offset_alone():
    """The tag is computed from the three doubles and NOTHING else — not
    from the placement's position among its siblings.  That is why it is
    a hash: an index over "the resource's distinct offsets" is a function
    of the POPULATION, so an unrelated placement appearing or going away
    would rename another placement's file (and strand the previous
    write's own body files, which provenance names)."""
    a = (9.048629, 9.549746, -50.10389)
    b = (-8.884837, 9.549746, -84.422043)
    assert OS.offset_tag(a) == OS.offset_tag(tuple(a))
    assert OS.offset_tag(a) == OS.offset_tag([9.048629, 9.549746, -50.10389])
    assert OS.offset_tag(a) != OS.offset_tag(b)
    # the exact doubles: the file bakes them exactly, so a micron is a
    # different file (the §16e memo trap moved 94 offsets by ~8 microns)
    assert OS.offset_tag(a) != OS.offset_tag((a[0] + 1e-9, a[1], a[2]))
    res = "Objects/tunnels/tunnel1.obj"
    assert OS.body_resource_name(res, 0, a) != OS.body_resource_name(res, 0, b)
    assert OS.body_resource_name(res, 0, a) == \
        f"Objects/tunnels/tunnel1__b0_{OS.offset_tag(a)}.obj"
    # ``offset=None`` is the untagged BODY SLOT id — never a file name
    assert OS.body_resource_name(res, 0) == "Objects/tunnels/tunnel1__b0.obj"
    assert OS.body_resource_name(res, 1, a) != OS.body_resource_name(res, 0, a)


def _tunnel_pair(tmp_path, *, same_offset):
    """Two placements of ONE resource, the OTHH shape: the same object
    file placed twice, at two anchors (or at one)."""
    path, _total = _two_boxes(tmp_path, with_anim=False)
    res = "objects/tunnel1.obj"
    d = 0.0 if same_offset else 40.0
    plan = _unit_plan([
        (path, [(0, 0.0, 0.0, 0.0, 0.0, 8.0),
                (1, 0.0, 0.0, 100.0, 0.0, 8.0)], res),
        (path, [(0, 0.0, d, 0.0, 0.0, 8.0),
                (1, 0.0, d, 100.0, 0.0, 8.0)], res),
    ])
    surface = _stepped([(-12.0, 12.0, 600.0), (88.0, 112.0, 610.0)])
    return PP.build_splits(plan, surface, write=True, **_elev_args())


def test_two_placements_of_one_resource_at_two_offsets_get_two_files(tmp_path):
    """14at: each placement's file bakes ITS OWN offset and its DSF row
    points at that file.  Before the fix both wrote one name and the
    second placement rendered on the first's translation."""
    ss = _tunnel_pair(tmp_path, same_offset=False)
    rows = [s for s in ss.all if s.resource == "objects/tunnel1.obj"]
    assert len(rows) == 2, [s.resource for s in ss.all]
    names = set()
    for s in rows:
        assert s.files, f"placement {s.index} wrote no file"
        for f in s.files:
            body = [b for b in s.bodies if b.body_id == f.body_id][0]
            # the row's name IS the file's name IS the offset it bakes
            assert body.new_resource == f.resource
            assert f.resource == OS.body_resource_name(
                "objects/tunnel1.obj", f.body_id, body.anchor.offset)
            assert tuple(f.offset) == tuple(body.anchor.offset)
            names.add(f.resource)
    # two placements x their bodies, every file distinct
    assert len(names) == sum(len(s.files) for s in rows)
    # ...and the two placements' b0 files are NOT the same file
    b0 = {s.index: [f.resource for f in s.files if f.body_id == 0][0]
          for s in rows}
    assert len(set(b0.values())) == 2, b0


def test_two_placements_with_the_same_offset_still_share_one_file(tmp_path):
    """No file explosion: the name is the offset, so placements that bake
    the SAME translation keep ONE file between them."""
    ss = _tunnel_pair(tmp_path, same_offset=True)
    rows = [s for s in ss.all if s.resource == "objects/tunnel1.obj"]
    assert len(rows) == 2
    per_row = [{f.resource for f in s.files} for s in rows]
    assert per_row[0] and per_row[0] == per_row[1], per_row
