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
        if not r["pending"] and not r["base_pending"]:
            return r
        time.sleep(0.02)
    raise AssertionError("still pending")


def _clear():
    for cache in (EC._MESH, EC._DEM, EC._LOADING, EC._ALT, EC._INSETS):
        cache.clear()


@pytest.fixture(autouse=True)
def _clean_cache(tmp_path, monkeypatch):
    # never the corpus: the inset directory and the .hgt live in tmp
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    _clear()
    yield
    _clear()


def _subset(reply, **want):
    return {k: reply[k] for k in want} == want


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
    hit = _settle(lat=45.2, lon=-122.8, build_dir=str(tmp_path))
    assert _subset(hit, source="mesh", pending=False, base_m=61.25, base_built=False)
    assert hit["elevation_m"] == pytest.approx(123.44) == hit["mesh_m"]
    # outside the mesh: the DEM, marked
    assert _subset(_settle(lat=45.7, lon=-122.2, build_dir=str(tmp_path)),
                   elevation_m=61.25, source="dem", pending=False, mesh_m=None)
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
    # #2119: the base, named, beside the mesh (the Swift twin's strings)
    assert elevation_text({"elevation_m": 162.97, "source": "mesh", "mesh_m": 162.97,
                           "base_m": 160.068, "base_label": "lidar 1 m"}) \
        == "160.1 m (lidar 1 m), mesh 163.0 m"
    assert elevation_text({"elevation_m": 189.0, "source": "dem", "mesh_m": None,
                           "base_m": 189.0, "base_label": "DEM 90 m"}) == "189.0 m (DEM 90 m)"


def test_engine_table_has_the_command():
    from unittest import mock

    from o4_engine import jsonl
    assert jsonl._build_handlers(mock.MagicMock())["cursor_elevation"] is EC.cursor_elevation


# ── #2119: the base elevation the build reads ─────────────────────────────

def _write_alt(folder, lat, lon, side, z_of):
    """A built ``.alt`` over the tile's unit square (frame sidecar
    beside it), posts ``z_of(row, col)``; row 0 is north."""
    import json
    rows, cols = np.mgrid[0:side, 0:side]
    path = os.path.join(folder, "Data" + FNAMES.short_latlon(lat, lon) + ".alt")
    z_of(rows, cols).astype("<f4").tofile(path)
    with open(path + ".frame.json", "w") as fh:
        json.dump({"schema": "o4.alt.frame/1", "x0": 0.0, "x1": 1.0, "y0": 0.0,
                   "y1": 1.0, "nxdem": side, "nydem": side, "epsg": 4326,
                   "tile_lat": lat, "tile_lon": lon}, fh)
    return path


def _write_inset(lat, lon, icao, bbox, pixel_m, extra=None):
    import json
    d = FNAMES.airport_inset_directory(lat, lon)
    os.makedirs(d, exist_ok=True)
    tif = os.path.join(d, f"{icao}_prov.tif")
    with open(tif, "wb") as fh:
        fh.write(b"not read by the footprint index")
    with open(tif[:-4] + ".json", "w") as fh:
        json.dump({"bounding_box_wgs84": list(bbox), "native_resolution_m": pixel_m,
                   **(extra or {})}, fh)


def _write_hgt(lat, lon, side):
    d = os.path.join(FNAMES.Elevation_dir, FNAMES.round_latlon(lat, lon))
    os.makedirs(d, exist_ok=True)
    np.zeros((side, side), ">i2").tofile(
        os.path.join(d, FNAMES.hem_latlon(lat, lon) + ".hgt"))


def test_alt_points_read_the_mesh_bilinear(tmp_path):
    """Four posts read from disk equal ``_BakedTile.sample`` over the
    whole raster — the mesh's own query."""
    from auto_patch_v2.airport.dem_production import _BakedTile
    from o4_engine.base_elevation import AltPoints
    path = _write_alt(str(tmp_path), 45, -123, 11,
                      lambda r, c: 100.0 + 3.0 * r - 2.0 * c + 0.25 * r * c)
    reader = AltPoints(path, 45, -123)
    raw = np.fromfile(path, dtype="<f4").reshape(11, 11)
    baked = _BakedTile(45, -123, raw, 0.0, 1.0, 0.0, 1.0)
    for lat, lon in [(45.0, -123.0), (45.37, -122.81), (45.999, -122.001), (46.0, -122.0)]:
        want = float(baked.sample(np.array([lat]), np.array([lon]))[0])
        assert reader.z(lat, lon) == pytest.approx(want, abs=1e-9)
    assert reader.z(46.5, -122.5) is None


def test_base_from_the_build_named_by_the_inset(tmp_path, monkeypatch):
    """A built tile answers its ``.alt`` (not the mesh, not the DEM),
    labelled by the inset under the point; the tile DEM's posting labels
    the rest."""
    from o4_engine import terrain_source as TS
    monkeypatch.setattr(TS, "tile_config", lambda *a, **k: None)
    monkeypatch.setattr(TS, "authored_source",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no DEM")))
    _write_alt(str(tmp_path), 45, -123, 5, lambda r, c: 150.0 + 0 * r)
    _write_mesh(FNAMES.mesh_file(str(tmp_path), 45, -123), 153.0)
    _write_inset(45, -123, "ZZZA", (-122.9, 45.1, -122.7, 45.3), 1.0)
    _write_inset(45, -123, "ZZZB", (-122.3, 45.6, -122.1, 45.8), 30.0)
    _write_hgt(45, -123, 1201)
    r = _settle(lat=45.2, lon=-122.8, build_dir=str(tmp_path))
    assert _subset(r, base_m=150.0, base_label="lidar 1 m", base_built=True,
                   source="mesh")
    assert r["mesh_m"] == pytest.approx(153.0)
    assert _settle(lat=45.7, lon=-122.2, build_dir=str(tmp_path))["base_label"] == "DEM 30 m"
    assert _settle(lat=45.4, lon=-122.5, build_dir=str(tmp_path))["base_label"] == "DEM 90 m"


def test_base_unbuilt_reads_the_covering_inset(tmp_path, monkeypatch):
    """No build: the tile DEM with the covering inset's airport (the
    sampler the 3D preview's authored frame uses), else the bare DEM."""
    from o4_engine import terrain_source as TS
    asked = []

    class Dem:
        def __init__(self, z):
            self.z = lambda la, lo: np.full(len(la), z)

    def authored(lat, lon, icao, root, cfg):
        asked.append(icao)
        return Dem(160.5 if icao else 165.0)

    monkeypatch.setattr(TS, "tile_config", lambda *a, **k: None)
    monkeypatch.setattr(TS, "authored_source", authored)
    _write_inset(45, -123, "ZZZA", (-122.9, 45.1, -122.7, 45.3), 2.0,
                 {"dem_class": "fine"})
    _write_hgt(45, -123, 3601)
    r = _settle(lat=45.2, lon=-122.8, build_dir=str(tmp_path))
    assert _subset(r, base_m=160.5, base_label="DEM 2 m", base_built=False,
                   elevation_m=165.0, source="dem", mesh_m=None)
    assert _settle(lat=45.5, lon=-122.5, build_dir=str(tmp_path))["base_label"] == "DEM 30 m"
    assert sorted(set(asked)) == ["", "ZZZA"]
