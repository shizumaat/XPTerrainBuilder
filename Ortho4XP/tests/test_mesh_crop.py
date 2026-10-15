"""``mesh_crop`` (protocol 1.12, patch-editor spec §2, §5 "Last build") and
the ``build_dir`` of ``terrain_sample`` (§2 amendment (b)): a synthetic
``Data<tile>.mesh`` and ``.alt`` in ``tmp_path`` — never the shared data
repo, never an X-Plane install.
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import mesh_commands as MC  # noqa: E402
from o4_engine import terrain_commands as TC  # noqa: E402

TILE = "+45-123"
BBOX = [45.19, -122.96, 45.21, -122.94]

# two triangles at the box, one far away; elevation column / 100000
VERTS = [(-122.95, 45.20, 100.0), (-122.94, 45.20, 101.0), (-122.95, 45.21, 102.0),
         (-122.10, 45.80, 300.0), (-122.09, 45.80, 301.0), (-122.10, 45.81, 302.0),
         (-122.93, 45.22, 103.0)]
TRIS = [(1, 2, 3), (2, 7, 3), (4, 5, 6)]


def _write_mesh(folder):
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["MeshVersionFormatted 2", "Dimension 3", "", "Vertices", str(len(VERTS))]
    lines += [f"{lon} {lat} {z / 100000.0} 0" for lon, lat, z in VERTS]
    lines += ["Normals", "0", "Triangles", str(len(TRIS))]
    lines += [f"{a} {b} {c} 0" for a, b, c in TRIS]
    path = folder / "Data+45-123.mesh"
    path.write_text("\n".join(lines) + "\n")
    return path


def _arrays(reply):
    v = np.frombuffer(base64.b64decode(reply["vertices_f64_b64"]), "<f8").reshape(-1, 3)
    t = np.frombuffer(base64.b64decode(reply["triangles_u32_b64"]), "<u4").reshape(-1, 3)
    return v, t


def test_the_crop_keeps_the_triangles_touching_the_box(tmp_path):
    folder = tmp_path / "Custom Scenery" / "zOrtho4XP_+45-123"
    path = _write_mesh(folder)
    reply = MC.mesh_crop(TILE, BBOX, str(folder))
    assert reply["mesh_path"] == str(path)
    v, t = _arrays(reply)
    assert len(t) == 2                                  # the far triangle is gone
    assert len(v) == 4 and t.max() == 3                 # re-indexed, compact
    corners = {tuple(np.round(v[i], 6)) for i in t.reshape(-1)}
    assert (-122.93, 45.22, 103.0) in corners           # a touching triangle keeps all corners
    assert np.allclose(sorted(v[:, 2]), [100, 101, 102, 103])   # metres, not /100000
    json.dumps(reply)


def test_without_build_dir_the_default_tiles_folder_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Tile_dir", str(tmp_path / "Tiles"))
    _write_mesh(tmp_path / "Tiles" / "zOrtho4XP_+45-123")
    assert len(_arrays(MC.mesh_crop(TILE, BBOX))[1]) == 2


def test_a_missing_mesh_says_why(tmp_path, monkeypatch):
    folder = tmp_path / "zOrtho4XP_+45-123"
    with pytest.raises(ValueError, match="has not been built"):
        MC.mesh_crop(TILE, BBOX, str(folder))
    dsf = folder / "Earth nav data" / "+40-130"
    dsf.mkdir(parents=True)
    (dsf / "+45-123.dsf").write_bytes(b"XPLNEDSF")
    monkeypatch.setattr(UI, "cleaning_level", 3)
    with pytest.raises(ValueError, match="cleanup level is 3"):
        MC.mesh_crop(TILE, BBOX, str(folder))
    assert not (folder / "Data+45-123.mesh").exists()


def test_terrain_sample_reads_the_built_dem_in_build_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    folder = tmp_path / "Custom Scenery" / "zOrtho4XP_+45-123"
    folder.mkdir(parents=True)
    side = 11
    y = 1 - np.arange(side)[:, None] / (side - 1)
    (700 + 10 * y + 0 * np.arange(side)[None, :]).astype(np.float32).tofile(folder / "Data+45-123.alt")
    (folder / "Data+45-123.alt.frame.json").write_text(json.dumps({
        "schema": "o4.alt.frame/1", "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0,
        "nxdem": side, "nydem": side}))
    reply = TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 100.0, str(folder))
    assert reply["sources"]["frame"] == "production"
    assert reply["sources"]["base"] == str(folder / "Data+45-123.alt")
