"""Issue #2250: a pack's orthophotos laid as DRAPED OBJ8 OBJECTS (FlyTampa
LGKR's ``x-obj_groundpoly_<a1..f1>.obj``) are photo layers of the same
witness and grid rule as ``.pol`` photos, hidden as ``object``
definitions.  Synthetic pack in ``tmp_path``; no airport, no corpus."""
from __future__ import annotations

import math
import struct

from auto_patch_v2.airport import pack_art as PA
from auto_patch_v2.airport import pack_drape_grid as G
from auto_patch_v2.airport import pack_drape_objects as PO
from auto_patch_v2.airport import pack_drapes as PD

APT = ("I\n1100 test\n\n1      12 0 0 OTST Test Field\n"
       "100 30.00 1 0 0.25 0 2 0 09 25.00100 51.00000 0 0 1 0 0 0 "
       "27 25.00100 51.01000 0 0 1 0 0 0\n99\n")
LON0, LAT0, D = 51.004, 25.000, 0.004
KX = 111_320.0 * math.cos(math.radians(LAT0))
KY = 110_540.0


def _dds(opaque: bool, size: int = 64) -> bytes:
    head = bytearray(128)
    head[:4] = b"DDS "
    struct.pack_into("<IIII", head, 4, 124, 0x1007, size, size)
    struct.pack_into("<II", head, 76, 32, 0x4)
    head[84:88] = b"DXT1" if opaque else b"DXT5"
    return bytes(head) + (b"\xff" * 16 if opaque else bytes(16)) * ((size // 4) ** 2)


def _obj(root, name: str, texture: str, quad: tuple[float, float, float, float], *,
         head: str = "", draped: bool = True) -> str:
    """A draped OBJ8 laying ``texture`` (u east, v north) on one quad
    ``(lon0, lat0, lon1, lat1)``, in the frame of the row at (LON0, LAT0)."""
    w, s, e, n = quad
    pts = [(w, s, 0, 0), (e, s, 1, 0), (e, n, 1, 1), (w, n, 0, 1)]
    vt = [f"VT {(lo - LON0) * KX:.3f} 0 {-(la - LAT0) * KY:.3f} 0 1 0 {u} {v}"
          for lo, la, u, v in pts]
    body = ["I", "800", "OBJ", head + f"TEXTURE_DRAPED ../tex/{texture}",
            "POINT_COUNTS 4 0 0 6", *vt, "IDX 0", "IDX 1", "IDX 2", "IDX 0", "IDX 2", "IDX 3"]
    body += (["ATTR_draped"] if draped else []) + ["TRIS 0 6"]
    (root / "ground").mkdir(parents=True, exist_ok=True)
    (root / "ground" / name).write_text("\n".join(body) + "\n", encoding="utf-8")
    (root / "tex").mkdir(exist_ok=True)
    (root / "tex" / texture).write_bytes(_dds(True))
    return "ground/" + name


def _pack(tmp_path):
    root = tmp_path / "Custom Scenery" / "Photo Pack"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text(APT, encoding="utf-8")
    return root


def _dump(paths) -> list[str]:
    rows = [f"OBJECT_DEF {p}\n" for p in paths]
    rows += [f"OBJECT_MSL {i} {LON0:.9f} {LAT0:.9f} 0.000000 0.000000\n"
             for i in range(len(paths))]
    return rows


def _found(root, paths):
    areas = [b for b, _ok in PD.airport_boxes(str(root / "Earth nav data" / "apt.dat"))]
    return PD.draped_orthos(str(root), _dump(paths), areas)


def test_a_photo_grid_laid_as_draped_objects_is_hidden_whole(tmp_path):
    root = _pack(tmp_path)
    grid = [_obj(root, f"groundpoly_{r}{c + 1}.obj", f"photo_{r}{c + 1}.dds",
                 (LON0 + D * c, LAT0 + D * k, LON0 + D * (c + 1), LAT0 + D * (k + 1)))
            for k, r in enumerate("ab") for c in range(3)]
    skid = _obj(root, "skids.obj", "skids.dds", (51.002, 25.0005, 51.003, 25.0015))
    shed = _obj(root, "shed.obj", "shed.dds", (51.002, 25.0005, 51.003, 25.0015),
                head="TEXTURE shed.dds\n")
    found = _found(root, [skid, shed] + grid)
    assert [(m.kind, m.index, m.path, m.uses) for m in found] == [
        ("object", 2 + k, p, 1) for k, p in enumerate(grid)], \
        "the six photo tiles, not the decal nor a 3-D object"
    text = "".join(_dump([skid, shed] + grid))
    out, counts = PA.omit_definitions(text, found)
    assert counts == {"object_defs": 6, "object_uses": 6}
    assert out.count("OBJECT_MSL") == 2 and "groundpoly" not in out


def test_an_object_drawn_partly_undraped_is_no_photo(tmp_path):
    root = _pack(tmp_path)
    path = _obj(root, "pad_a1.obj", "pad.dds", (51.0, 25.0, 51.004, 25.004), draped=False)
    assert PO._photo_object(str(root / path)) is None


def _layer(i: int, path: str, layer: float = 0.0):
    return G.Layer(i, path, "", ((0.0, 0.0, 1.0, 1.0),), True, layer)


def test_lettered_grid_cells_are_one_family_only_where_rows_are_short():
    """LGKR's a1..f1 (rows of one to three tiles) are one family; a pack
    whose lettered rows are families already keeps them (KTIW's 60 cm and
    30 cm grids share the cell key and stay apart)."""
    short = [_layer(k, f"g/x-obj_groundpoly_{c}.obj")
             for k, c in enumerate(("a1", "a2", "b1", "c1", "c2"))]
    assert [len(f) for f in G._families(short)] == [5]
    rows = [_layer(k, f"o/K_{res}cm_XP_{r}{c}.pol")
            for k, (res, r, c) in enumerate((res, r, c) for res, r in (("60", "A"), ("30", "E"))
                                            for c in range(1, 5))]
    assert sorted(len(f) for f in G._families(rows)) == [4, 4]
    assert not G._cell_keys("g/asphalt.obj", "") and not G._cell_keys("g/concrete.obj", "")
