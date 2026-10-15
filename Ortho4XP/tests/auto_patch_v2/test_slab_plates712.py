"""Issue #712 twin (owner RULINGS 2026-10-10o (B), 2026-10-14d): a paved
plate thinner than the partition's thickness gate is no part, so the
base-slab witness never saw it — HECA's ``Seasonal_Terminal/asphalt_3.obj``
plate rode its terminal's level over ground nothing graded.  The thin
plates are read (``airport/slab_plates``) and judged by the witness's own
rules; a floor its own parts cover is never re-read.  Hermetic."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import box, mapping

from auto_patch_v2.airport import slab_plates as SP
from auto_patch_v2.airport.slab_faces import witness_faces
from auto_patch_v2.geom import base_slab as bs
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import base_slab_law

LAW = Law.for_airport("HECA")
LW = base_slab_law(LAW)


def to_xy(lon, lat):                       # a metre frame: lon = x, lat = y
    return (lon, lat)


def _obj(path, boxes):
    """An OBJ8 of closed boxes ``[(x0, x1, z0, z1, y0, y1)]``."""
    vt, idx = [], []
    for x0, x1, z0, z1, y0, y1 in boxes:
        b = len(vt)
        for y in (y0, y1):
            vt += [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        for a, c, d, e in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2),
                           (2, 6, 7, 3), (3, 7, 4, 0)):
            idx += [b + a, b + c, b + d, b + a, b + d, b + e]
    lines = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    lines += [f"IDX {i}" for i in idx]
    lines += [f"TRIS 0 {len(idx)}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _part(comp, b, h):
    from auto_patch_v2.model.rebake import Part
    c = b.centroid
    x0, y0, x1, y1 = b.bounds
    ring = tuple((y, x) for x, y in tuple(b.exterior.coords)[:-1])
    return Part(comp, comp, c.y, c.x, 0.0, b.area, (y0, x0, y1, x1),
                feet=((c.y, c.x, 0.0),), rings=(ring,), height_m=h)


def _member(tmp_path, plate_y1=0.3, plane=True):
    # comp 0: a 12 m terminal 40 x 40 m; comp 1: a 0.3 m paved plate 60 x 40 m
    # east of it (OBJ8 z points south: the frame's north is -z)
    path = _obj(tmp_path / "asphalt.obj",
                [(0, 40, -40, 0, 0.0, 12.0), (40.2, 100, -40, 0, 0.0, plate_y1)])
    prof = {"planes": [{"y": 0.15, "area_m2": 2400.0,
                        "polygon": mapping(box(40.2, -40, 100, 0))}]} if plane else {}
    m = types.SimpleNamespace(id="dsf:obj9", resource="Terminal/asphalt.obj",
                              authored_path=path, origin=(0.0, 0.0), heading_deg=0.0,
                              parts=(_part(0, box(0, 0, 40, 40), 12.0),),
                              base_profile=prof)
    u = types.SimpleNamespace(id="unit:0", anchor=(0.0, 0.0), members=(m,))
    return u, m


def test_a_thin_plate_beside_its_terminal_is_read_and_admitted(tmp_path):
    u, m = _member(tmp_path)
    got = SP.thin_plates(u, m, to_xy, LW)
    assert [q.comp for q in got] == [1]
    assert got[0].height_m == pytest.approx(0.3)
    assert got[0].poly_xy.area == pytest.approx(59.8 * 40, rel=1e-3)
    assert got[0].poly_xy.bounds == pytest.approx((40.2, 0, 100, 40), abs=1e-3)
    slabs = bs.base_slabs(types.SimpleNamespace(units=(u,)), to_xy, LW, witness_faces(LW))
    assert [(s.member, s.comp) for s in slabs] == [("dsf:obj9", 1)]
    assert slabs[0].open.area == pytest.approx(59.8 * 40, rel=1e-3)


def test_a_member_whose_base_plane_its_parts_cover_is_never_parsed(tmp_path):
    u, m = _member(tmp_path, plane=False)
    assert SP.thin_plates(u, m, to_xy, LW) == []
    u, m = _member(tmp_path)
    m.base_profile["planes"][0]["polygon"] = mapping(box(0, -40, 40, 0))   # under its walls
    assert SP.thin_plates(u, m, to_xy, LW) == []


def test_a_raised_plate_is_no_base_slab(tmp_path):
    from auto_patch_v2.airport.slab_faces import _components
    _components.cache_clear()
    u, m = _member(tmp_path)
    path = _obj(tmp_path / "raised.obj",
                [(0, 40, -40, 0, 0.0, 12.0), (40.2, 100, -40, 0, 1.5, 1.8)])
    m.authored_path = path
    assert SP.thin_plates(u, m, to_xy, LW) == []
