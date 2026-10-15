"""Twins of the DRAPED base slab (owner RULINGS 2026-10-14d (1); lane
drape229): which slabs drape (``airport/slab_drape``), the up faces the
writer keeps (``airport/slab_faces``, the OBJ8 clockwise winding) and the
draped cut itself (``obj8_split``'s drape cut + ``airport/obj8_drape``) —
read back through the engine's own reader (``obj8.parse_obj8``): the
draped triangles are the slab's TOP, its kerb sides and underside are
gone, and the walled part beside it stays solid."""
from __future__ import annotations

import types

import numpy as np
import pytest
from shapely.geometry import box

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_drape as OD
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport import slab_drape as SD
from auto_patch_v2.airport import slab_faces as SF
from auto_patch_v2.law import Law
from auto_patch_v2.model.rebake import Member, Part, Unit

LAW = Law.for_airport("HECA")
DL = OD.drape_law(LAW)


def _slab(L=20.0, W=10.0, h=0.3, x0=0.0):
    """A kerbed plate: 8 vertices, top (2, facing up under the OBJ8
    clockwise winding), bottom (2), four kerb sides (8)."""
    v = [(x0, 0.0, 0.0), (x0 + L, 0.0, 0.0), (x0 + L, 0.0, W), (x0, 0.0, W),
         (x0, h, 0.0), (x0 + L, h, 0.0), (x0 + L, h, W), (x0, h, W)]
    top = [(4, 5, 6), (4, 6, 7)]
    bottom = [(0, 2, 1), (0, 3, 2)]
    sides = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
             (3, 0, 4), (3, 4, 7)]
    return v, top, bottom, sides


def _wall(x0, n0, side=4.0, h=6.0):
    v = [(x0, 0.0, 0.0), (x0 + side, 0.0, 0.0), (x0 + side, 0.0, side), (x0, 0.0, side),
         (x0, h, 0.0), (x0 + side, h, 0.0), (x0 + side, h, side), (x0, h, side)]
    t = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v, [(a + n0, b + n0, c + n0) for a, b, c in t]


def _write(path, verts, tris, lod=""):
    idx = [i for t in tris for i in t]
    out = ["I", "800", "OBJ", "", "TEXTURE\tslab.png", "TEXTURE_NORMAL\tslab_n.png",
           f"POINT_COUNTS\t{len(verts)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t{x / 20:.3f} {z / 10:.3f}"
            for x, y, z in verts]
    out += [f"IDX\t{i}" for i in idx]
    out += ([lod] if lod else []) + ["ATTR_hard", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="latin-1", newline="")
    return str(path)


def _slab_and_wall(tmp_path, lod=""):
    v, top, bottom, sides = _slab()
    wv, wt = _wall(30.0, len(v))
    p = _write(tmp_path / "lot.obj", v + wv, top + bottom + sides + wt, lod)
    comps = obj8.solid_components(obj8.parse_obj8(p))
    order = sorted(range(len(comps)), key=lambda i: comps[i].cx)
    return p, order[0], order[1]


def test_the_winding_reads_the_top_up_and_the_kerb_as_side():
    v, top, bottom, sides = _slab()
    ny, _a = SF.tri_normals_y(np.asarray(v, float), np.asarray(top + bottom + sides))
    assert (ny[:2] > 0.99).all() and (ny[2:4] < -0.99).all()
    assert (np.abs(ny[4:]) < 0.01).all()


def test_the_draped_cut_keeps_the_top_drops_the_kerbs_and_keeps_the_wall(tmp_path):
    p, slab, wall = _slab_and_wall(tmp_path)
    res = OS.split_obj8(p, [OS.BodyCut(0, (slab,)), OS.BodyCut(1, (wall,))],
                        "objects/lot.obj", drape_comps={slab}, drape_law=DL)
    assert not res.kept_whole and len(res.files) == 2
    assert res.counts["drape_tris"] == 2 and res.counts["drape_dropped"] == 10
    by = {f.body_id: f for f in res.files}
    for f in res.files:
        q = tmp_path / f"b{f.body_id}.obj"
        q.write_text(f.text, encoding="latin-1", newline="")
        g = obj8.parse_obj8(str(q))
        if f.body_id == 0:
            # the parse-back twin: draped = the slab's top, solid 0
            assert g.draped.shape[0] == 2 and g.solid.shape[0] == 0
        else:
            assert g.draped.shape[0] == 0 and g.solid.shape[0] == 12
    head = by[0].text.split("POINT_COUNTS")[0]
    assert "TEXTURE_DRAPED\tslab.png" in head
    assert "TEXTURE_DRAPED_NORMAL\t1.0 slab_n.png" in head
    assert f"ATTR_layer_group_draped\t{DL.layer_group}\t{DL.layer_offset}" in head
    assert "TEXTURE_DRAPED" not in by[1].text          # the rigid body is as it was
    # the author's UVs ride the draped vertices
    assert any(ln.split()[-2:] == ["1.000", "1.000"]
               for ln in by[0].text.split("\n") if ln.startswith("VT"))


def test_one_body_with_a_draped_slab_is_written_and_lod_holds_the_block(tmp_path):
    p, slab, wall = _slab_and_wall(tmp_path, lod="ATTR_LOD\t0 2000")
    res = OS.split_obj8(p, [OS.BodyCut(0, (slab, wall))], "objects/lot.obj",
                        allow_single=True, drape_comps={slab}, drape_law=DL)
    (f,) = res.files
    cmds = [ln for ln in f.text.split("\n") if ln and not ln.startswith(("VT", "IDX"))]
    i = cmds.index("ATTR_LOD\t0 2000")
    assert cmds[i + 1] == "ATTR_draped" and cmds[i + 3] == "ATTR_no_draped"
    q = tmp_path / "one.obj"
    q.write_text(f.text, encoding="latin-1", newline="")
    g = obj8.parse_obj8(str(q))
    assert g.draped.shape[0] == 2 and g.solid.shape[0] == 12


def test_no_drape_law_writes_the_pre_drape_bytes(tmp_path):
    p, slab, wall = _slab_and_wall(tmp_path)
    cuts = [OS.BodyCut(0, (slab,)), OS.BodyCut(1, (wall,))]
    a = OS.split_obj8(p, cuts, "objects/lot.obj")
    b = OS.split_obj8(p, cuts, "objects/lot.obj", drape_comps={slab})
    assert [f.text for f in a.files] == [f.text for f in b.files]


def _part(pid, b, h):
    c = b.centroid
    x0, y0, x1, y1 = b.bounds
    ring = tuple((y, x) for x, y in tuple(b.exterior.coords)[:-1])
    return Part(pid, pid, c.y, c.x, 0.0, b.area, (y0, x0, y1, x1),
                feet=((c.y, c.x, 0.0),), rings=(ring,), height_m=h)


def test_a_slab_over_sloping_ground_drapes_and_over_level_ground_stays_rigid():
    """The decision is the GROUND's: relief over the open part above twice
    ``[placement] split_tol_m`` (the foot tolerance either side of a level
    plate) drapes."""
    wall = _part(0, box(0, 0, 40, 40), 12.0)
    slab = _part(1, box(40, 0, 100, 40), 0.3)
    m = Member("dsf:obj7", "ground/lot.obj", "", "", 0.0, (wall, slab))
    part = types.SimpleNamespace(units=(Unit("unit:0", (0.0, 0.0), 0.0, (m,)),))
    ident = lambda lon, lat: (lon, lat)               # noqa: E731 — metres
    to_ll = lambda x, y: (y, x)                       # noqa: E731
    tol = LAW.tables.structures.placement.split_tol_m
    level = lambda lat, lon: 100.0 + 0.004 * lon       # noqa: E731 — 0.24 m
    slope = lambda lat, lon: 100.0 + 0.03 * lon        # noqa: E731 — 1.8 m
    d0, r0 = SD.drape_plan(part, ident, to_ll, LAW, level)
    d1, r1 = SD.drape_plan(part, ident, to_ll, LAW, slope)
    assert d0 == {} and len(r0) == 1 and r0[0].relief_m <= 2 * tol
    assert d1 == {"dsf:obj7": frozenset({1})} and r1[0].relief_m == pytest.approx(1.8, abs=0.05)


def _sheet(tmp_path, name, lift):
    """A single-sided road sheet 60 m x 10 m whose TOP stands ``lift`` m
    over its zero between x = 10 and x = 50 and ramps down to it at both
    ends (issue #669's departures roadway: KCLT ``techos_1`` comp 8), with
    four 1 m square piers under the lifted span when ``lift`` > 0; a
    sheet with ``lift`` 0 is a ground plate.  Returns ``(path, comp of
    the sheet)``."""
    xs = (0.0, 10.0, 50.0, 60.0)
    ys = (0.0, lift, lift, 0.0)
    v = [(x, y, z) for x, y in zip(xs, ys) for z in (0.0, 10.0)]
    t = []
    for i in range(3):                    # up under the OBJ8 clockwise winding
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        t += [(a, c, d), (a, d, b)]
    if lift > 0.0:
        for px in (15.0, 25.0, 35.0, 45.0):
            pv, pt = _wall(px, len(v), side=1.0, h=lift - 0.5)
            v += pv
            t += pt
    p = _write(tmp_path / name, v, t)
    comps = obj8.solid_components(obj8.parse_obj8(p))
    sheet = next(i for i, c in enumerate(comps) if 0 in np.asarray(c.tris))
    return p, sheet


def test_an_elevated_deck_reads_clear_of_its_foot_and_a_ground_sheet_does_not(tmp_path):
    """Rule 7's fact (issue #669): the share of the sheet's up-facing area
    standing ``[bridge] deck_min_elevation_m`` over its own lowest ``y``."""
    elev = LAW.tables.structures.bridge.deck_min_elevation_m
    ny = LAW.tables.structures.bridge.deck_plate_normal_y_min
    p, c = _sheet(tmp_path, "deck.obj", 6.0)
    ff = SF.face_facts(p, c, ny, elev)
    assert ff.elevated_share > 0.75 and ff.top_relief_m == pytest.approx(6.0)
    g, cg = _sheet(tmp_path, "ground.obj", 0.0)
    assert SF.face_facts(g, cg, ny, elev).elevated_share == 0.0
    assert SF.face_facts(p, c, ny).elevated_share == 0.0       # disarmed


def test_an_elevated_deck_on_piers_never_drapes_and_a_ground_sheet_still_does(tmp_path):
    """Issue #669: an elevated sloped deck on piers over sloping ground is
    marked ELEVATED and stays rigid (the gap mint still reads it); a ground
    sheet over the same ground drapes."""
    slope = lambda lat, lon: 100.0 + 0.03 * lon        # noqa: E731 — 1.8 m
    ident = lambda lon, lat: (lon, lat)               # noqa: E731 — metres
    to_ll = lambda x, y: (y, x)                       # noqa: E731
    got = {}
    for name, lift in (("deck.obj", 6.0), ("ground.obj", 0.0)):
        path, comp = _sheet(tmp_path, name, lift)
        wall = _part(0, box(0, 0, 40, 40), 12.0)
        slab = Part(comp, comp, 20.0, 70.0, 0.0, 2400.0, (0.0, 40.0, 40.0, 100.0),
                    feet=((20.0, 70.0, 0.0),),
                    rings=(tuple((y, x) for x, y in tuple(box(40, 0, 100, 40).exterior.coords)[:-1]),),
                    height_m=0.3)
        m = Member("dsf:" + name, "pack/" + name, path, path, 0.0, (wall, slab))
        part = types.SimpleNamespace(units=(Unit("unit:0", (0.0, 0.0), 0.0, (m,)),))
        got[name] = SD.drape_plan(part, ident, to_ll, LAW, slope)
    d, rows = got["deck.obj"]
    assert d == {} and len(rows) == 1 and rows[0].elevated and not rows[0].drape
    assert rows[0].relief_m > 2 * LAW.tables.structures.placement.split_tol_m
    d, rows = got["ground.obj"]
    assert d == {"dsf:ground.obj": frozenset({rows[0].comp})}
    assert not rows[0].elevated and rows[0].drape
