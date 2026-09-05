"""OBJ8 keyword lines may be indented (XPlane2Blender under an LOD):
HECA's pack reads TRIS from column 1 (2026-09-04, 479 unseated buildings)."""
from auto_patch_v2.airport import obj8


def _obj(indent: bytes) -> bytes:
    body = [b"I", b"800", b"OBJ", b"", b"POINT_COUNTS 8 0 0 36"]
    cube = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1), (-1, 2, -1), (1, 2, -1), (1, 2, 1), (-1, 2, 1)]
    for x, y, z in cube:
        body.append(f"VT {x} {y} {z} 0 1 0 0 0".encode())
    tris = [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1, 1, 5, 6, 1, 6, 2, 2, 6, 7, 2, 7, 3, 3, 7, 4, 3, 4, 0]
    for i in range(0, 30, 10):
        body.append(b"IDX10 " + " ".join(map(str, tris[i:i + 10])).encode())
    for t in tris[30:]:
        body.append(b"IDX " + str(t).encode())
    body.append(indent + b"ATTR_LOD 0 3000")
    body.append(indent + b"TRIS\t0 36")
    return b"\r\n".join(body) + b"\r\n"


def test_indented_tris_lines_are_read(tmp_path):
    for indent in (b"", b"\t", b"    "):
        p = tmp_path / f"cube_{len(indent)}.obj"
        p.write_bytes(_obj(indent))
        g = obj8.parse_obj8(str(p))
        assert g.vertices.shape[0] == 8, indent
        assert len(g.solid) == 12, (indent, len(g.solid))     # 12 triangles
        assert len(obj8.solid_components(g)) == 1
