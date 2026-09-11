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


# ── §6: the anchor rule ──────────────────────────────────────────────────

def _geom(parts, origin=(40.0, -3.0)):
    return AR.BodyGeometry(tuple(parts), origin[0], origin[1])


def _flat(z=100.0):
    return lambda lat, lon: z


def test_anchor_building_lands_inside_its_pad():
    pad = AR.PadRing("building16", ((40.0, -3.0), (40.0, -2.999),
                                    (40.001, -2.999), (40.001, -3.0)))
    g = _geom([(40.0005, -2.9995, 0.0, ((40.0005, -2.9995, 0.0),))])
    a = AR.anchor_for(AR.BUILDING, g, _flat(), pads=(pad,))
    assert a.body_class == AR.BUILDING
    assert a.reason == "pad point (building16)"
    assert AR._inside(pad.ring, a.lat, a.lon)
    assert a.y_zero == 0.0


def test_anchor_skirted_takes_the_low_side_foot():
    """10ag: among the body's ground components the one whose DESIGN
    SURFACE is lowest, and that component's own lowest foot."""
    def surface(lat, lon):
        return 100.0 if lat < 40.0005 else 108.0
    g = _geom([(40.0000, -3.0, -1.0, ((40.0000, -3.0, -1.0), (40.0000, -3.0, -0.5))),
               (40.0010, -3.0, -1.0, ((40.0010, -3.0, -1.0),))])
    a = AR.anchor_for(AR.SKIRTED, g, surface)
    assert a.reason == "low-side foot"
    assert a.lat == pytest.approx(40.0000)
    assert a.surface_z == 100.0
    assert a.y_zero == pytest.approx(-1.0)


def test_anchor_basin_lands_on_the_emitted_rim():
    rim = AR.RimRing("basin_wall:3", ((40.0, -3.0), (40.0, -2.999),
                                      (40.001, -2.999), (40.001, -3.0)))
    far = AR.RimRing("basin_wall:9", ((41.0, -3.0), (41.0, -2.999),
                                      (41.001, -2.999), (41.001, -3.0)))
    g = _geom([(40.0005, -2.9995, -7.05, ((40.0005, -2.9995, -7.05),)),
               (40.0006, -2.9994, 0.0, ((40.0006, -2.9994, 0.0),))],
              origin=(40.5, -3.0))
    a = AR.anchor_for(AR.BASIN, g, _flat(), rims=(rim, far))
    assert a.body_class == AR.BASIN and a.reason.startswith("rim point (basin_wall:3")
    assert (a.lat, a.lon) in rim.ring
    # the object's zero is its RIM, not its floor plate 7.05 m down
    assert a.y_zero == 0.0


def test_anchor_line_segment_is_the_mid_foot():
    g = _geom([(40.0, -3.0, 0.0, ((40.0, -3.0, 0.0), (40.001, -3.0, 0.3),
                                  (40.002, -3.0, 0.6)))])
    a = AR.anchor_for(AR.LINE_SEGMENT, g, _flat())
    assert a.reason == "segment mid-foot"
    assert a.lat == pytest.approx(40.001)
    assert a.y_zero == pytest.approx(0.3)


def test_anchor_deck_is_merged_into_the_building_it_abuts():
    g = _geom([(40.0, -3.0, 5.0, ((40.0, -3.0, 5.0),))])
    a = AR.anchor_for(AR.DECK, g, _flat(), merged_into="objects/T4.obj")
    assert a.body_class == AR.DECK
    assert a.reason == "kerb (merged into objects/T4.obj)"


def test_anchor_other_is_the_lowest_component_centroid():
    g = _geom([(40.0, -3.0, 4.0, ()), (40.002, -3.0, 1.0, ())])
    a = AR.anchor_for(AR.OTHER, g, _flat())
    assert a.reason == "centroid of the lowest component"
    assert a.lat == pytest.approx(40.002) and a.y_zero == pytest.approx(1.0)


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
