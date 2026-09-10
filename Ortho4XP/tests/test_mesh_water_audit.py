"""Known-answer twins for ``tools/mesh_region_tris.py --water-audit``.

The water round's acceptance instrument (owner RULINGS 2026-09-09m;
mechanism 09o), so its numbers are load-bearing evidence and need a mesh
whose answer is computable by hand: three water triangles — one flat at
0.000, one carrying a 3.962 m step (the OTHH plateau's signature), one
inland — and one land triangle that must not be counted.

The MEDIT z column is metres / 100000 (``_read_mesh_attributed``).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mesh_region_tris as MRT  # noqa: E402

LAT, LON = 25.2557, 51.6168
D = 0.0005


def _write(path, tris):
    """``tris`` = [(attribute, [(lon, lat, z_m), x3]), ...]."""
    verts, faces = [], []
    for attr, corners in tris:
        base = len(verts) + 1
        verts.extend(corners)
        faces.append((base, base + 1, base + 2, attr))
    lines = ["MeshVersionFormatted 1", "Dimension 3", "Vertices",
             str(len(verts))]
    lines += [f"{lo:.9f} {la:.9f} {z / 100000.0:.12f} 0" for lo, la, z in verts]
    lines += ["Triangles", str(len(faces))]
    lines += [f"{a} {b} {c} {t}" for a, b, c, t in faces]
    lines += ["End", ""]
    Path(path).write_text("\n".join(lines))


def _tri(lon, lat, zs):
    return [(lon, lat, zs[0]), (lon + D, lat, zs[1]), (lon, lat + D, zs[2])]


@pytest.fixture
def mesh(tmp_path):
    p = tmp_path / "Data+25+051.mesh"
    _write(p, [
        (2, _tri(LON, LAT, (0.0, 0.0, 0.0))),                 # SEA, flat
        (10, _tri(LON + 0.01, LAT, (0.0, 3.962, 3.962))),     # SEA|INTERP_ALT
        (9, _tri(LON + 0.02, LAT, (12.5, 12.5, 12.5))),       # WATER inland
        (8, _tri(LON + 0.03, LAT, (7.0, 7.0, 7.0))),          # LAND (patch)
    ])
    return p


def test_the_water_census_is_hand_computable(mesh, tmp_path, capsys):
    out = tmp_path / "w.json"
    MRT.main(["--mesh", str(mesh), "--water-audit", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["triangles_tile"] == 4
    assert d["water_triangles"] == 3          # the attr-8 land one is out
    assert d["water_attributes"] == {"2": 1, "10": 1, "9": 1}
    f = d["frame"]
    assert f["vertices"] == 9
    assert f["vertices_at_zero"] == 4         # 3 + the stepped one's low corner
    assert f["vertices_not_zero"] == 5
    assert [3.962, 2] in f["vertices_not_zero_top"]
    assert f["triangles_stepped"] == 1        # only the 3.962 step exceeds 1 m
    assert f["max_step_m"] == pytest.approx(3.962)


def test_the_step_flag_is_a_reporting_threshold(mesh, tmp_path):
    out = tmp_path / "w2.json"
    MRT.main(["--mesh", str(mesh), "--water-audit", "--water-step-flag", "5",
              "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["step_flag_m"] == 5.0
    assert d["frame"]["triangles_stepped"] == 0
    assert d["frame"]["max_step_m"] == pytest.approx(3.962)


def test_near_restricts_to_the_site(mesh, tmp_path):
    out = tmp_path / "w3.json"
    MRT.main(["--mesh", str(mesh), "--water-audit",
              "--near", str(LAT), str(LON), "200", "--json", str(out)])
    d = json.loads(out.read_text())
    assert d["near"]["triangles"] == 1        # only the flat SEA one is within
    assert d["near"]["vertices_at_zero"] == 3
    assert d["near"]["triangles_stepped"] == 0


def test_the_water_bit_mask_is_the_engine_s_own():
    """A second spelling of the attribute table would be a second law."""
    import O4_Vector_Utils as VECT
    attrs = VECT.Vector_Map.dico_attributes
    assert MRT.WATER_BITS == (attrs["WATER"] | attrs["SEA"]
                              | attrs["SEA_EQUIV"])
