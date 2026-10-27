"""``cursor_elevation`` (#1308 part 3) over a small synthetic mesh, and the
Qt readout's text.  No network, no corpus."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import pytest  # noqa: E402
from o4_engine import elevation_commands as EC  # noqa: E402


def _write_mesh(path, z):
    """One flat triangle over the south-west half of +45-123 at ``z`` m,
    in the ``.mesh`` text format ``auto_patch.mesh_sampler`` reads."""
    e = z / 100000.0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("MeshVersionFormatted 1\nDimension 3\nVertices\n3\n")
        f.write("-123 45 %r 0\n-122 45 %r 0\n-123 46 %r 0\n" % (e, e, e))
        f.write("Triangles\n1\n1 2 3 0\nEnd\n")


def _settle(**kw):
    for _ in range(200):
        r = EC.cursor_elevation(**kw)
        if not r["pending"]:
            return r
        time.sleep(0.02)
    raise AssertionError("still pending")


@pytest.fixture(autouse=True)
def _clean_cache():
    EC._MESH.clear(), EC._DEM.clear(), EC._LOADING.clear()
    yield
    EC._MESH.clear(), EC._DEM.clear(), EC._LOADING.clear()


def test_mesh_answers_and_dem_falls_back(tmp_path, monkeypatch):
    from o4_engine import terrain_source as TS

    class Dem:
        def z(self, la, lo):
            return np.full(len(la), 61.25)

    monkeypatch.setattr(TS, "authored_source", lambda *a, **k: Dem())
    monkeypatch.setattr(TS, "tile_config", lambda *a, **k: None)
    _write_mesh(FNAMES.mesh_file(str(tmp_path), 45, -123), 123.44)
    first = EC.cursor_elevation(45.2, -122.8, build_dir=str(tmp_path))
    assert first["pending"] and first["source"] is None     # never loads inline
    assert _settle(lat=45.2, lon=-122.8, build_dir=str(tmp_path)) == {
        "elevation_m": pytest.approx(123.44), "source": "mesh", "pending": False}
    # outside the mesh: the DEM, marked
    assert _settle(lat=45.7, lon=-122.2, build_dir=str(tmp_path)) == {
        "elevation_m": 61.25, "source": "dem", "pending": False}
    # a tile with no mesh: the DEM
    other = tmp_path / "none"
    other.mkdir()
    assert _settle(lat=45.2, lon=-122.8, build_dir=str(other))["source"] == "dem"


def test_bad_point_refused():
    with pytest.raises(ValueError):
        EC.cursor_elevation(95, 0)


def test_qt_readout_text():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from O4_Qt_Cursor_Readout import elevation_text
    from O4_Qt_Patch_Panel import node_lat_lon
    assert node_lat_lon(45.5, -122.25) == "45.500000000, -122.250000000"
    assert elevation_text({"elevation_m": 123.44, "source": "mesh"}) == "123.4 m"
    assert elevation_text({"elevation_m": 61.25, "source": "dem"}) == "61.2 m (DEM)"
    assert elevation_text({"elevation_m": None, "pending": True}) is None


def test_engine_table_has_the_command():
    from unittest import mock

    from o4_engine import jsonl
    assert jsonl._build_handlers(mock.MagicMock())["cursor_elevation"] is EC.cursor_elevation
