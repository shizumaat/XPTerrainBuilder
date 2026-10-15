"""``terrain_sample`` (protocol 1.12, patch-editor spec §2): the DEM grid
under the 3D preview — shape, row order, the sample cap, the missing-DEM
refusal, and one round trip through the JSON-lines transport.  A synthetic
``.hgt`` in ``tmp_path``; never the shared data repo.
"""
import base64
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine import terrain_commands as TC  # noqa: E402

TILE = "+45-123"
N = 121          # 1/120° pixels: the plane below is integral on every pixel


def _plane(lat, lon):
    """The synthetic terrain: exact under bilinear sampling."""
    return 100.0 + 120.0 * (lat - 45.0) + 240.0 * (lon + 123.0)


@pytest.fixture
def elevation_root(tmp_path, monkeypatch):
    root = tmp_path / "Elevation_data"
    block = root / "+40-130"
    block.mkdir(parents=True)
    i = np.arange(N)[:, None]           # row 0 = NORTH edge (SRTM order)
    j = np.arange(N)[None, :]
    z = 100 + (N - 1 - i) * 1 + j * 2   # = _plane at the pixel corners
    z.astype(">i2").tofile(block / "N45W123.hgt")
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(root))
    yield root
    UI.engine_session = None
    UI.red_flag = False


def _grid(reply):
    z = np.frombuffer(base64.b64decode(reply["elev_f32_b64"]), dtype="<f4")
    return z.reshape(reply["rows"], reply["cols"])


def test_grid_shape_and_south_first_rows(elevation_root):
    bbox = [45.2, -122.8, 45.21, -122.785]
    reply = TC.terrain_sample(TILE, "ZZZZ", bbox, 50.0)
    rows, cols = reply["rows"], reply["cols"]
    # corners on the bbox corners, step at most the spacing asked
    assert reply["bbox"] == bbox
    assert reply["dlat"] * (rows - 1) == pytest.approx(0.01)
    assert reply["dlon"] * (cols - 1) == pytest.approx(0.015)
    assert reply["dlat"] * 111320.0 <= 50.0 + 1e-9
    m_lon = 111320.0 * math.cos(math.radians(45.205))
    assert reply["dlon"] * m_lon <= 50.0 + 1e-9
    assert (rows, cols) == (int(math.ceil(0.01 * 111320 / 50)) + 1,
                            int(math.ceil(0.015 * m_lon / 50)) + 1)
    z = _grid(reply)
    lats = bbox[0] + np.arange(rows) * reply["dlat"]
    lons = bbox[1] + np.arange(cols) * reply["dlon"]
    expect = _plane(lats[:, None], lons[None, :])
    assert np.allclose(z, expect, atol=1e-3)
    assert (np.diff(z[:, 0]) > 0).all()          # row 0 is the SOUTH edge
    assert reply["sources"]["base"].endswith("N45W123.hgt")
    assert reply["sources"]["inset"] is None


def test_refuses_over_the_sample_cap(elevation_root):
    with pytest.raises(ValueError, match="4,000,000"):
        TC.terrain_sample(TILE, "ZZZZ", [45.0, -123.0, 45.5, -122.5], 5.0)


def test_missing_dem_names_the_tile_and_never_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "empty"))
    with pytest.raises(ValueError) as err:
        TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 5.0)
    text = str(err.value)
    assert TILE in text and "N45W123.hgt" in text and "refresh" in text
    assert not (tmp_path / "empty").exists()


def test_bad_arguments_are_sentences(elevation_root):
    with pytest.raises(ValueError, match="tile key"):
        TC.terrain_sample("45-123", "ZZZZ", [45.2, -122.8, 45.21, -122.79], 5.0)
    with pytest.raises(ValueError, match="empty"):
        TC.terrain_sample(TILE, "ZZZZ", [45.21, -122.8, 45.2, -122.79], 5.0)
    with pytest.raises(ValueError, match="spacing_m"):
        TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 0)


def test_round_trip_through_the_transport(elevation_root):
    commands = "\n".join([
        json.dumps({"cmd": "terrain_sample", "id": 1, "tile": TILE, "icao": "ZZZZ",
                    "bbox": [45.2, -122.8, 45.201, -122.799], "spacing_m": 5.0}),
        json.dumps({"cmd": "terrain_sample", "id": 2, "tile": TILE, "icao": "ZZZZ",
                    "bbox": [45.0, -123.0, 45.5, -122.5], "spacing_m": 5.0}),
        json.dumps({"cmd": "shutdown", "id": 3}),
    ]) + "\n"
    out = io.StringIO()
    jsonl.serve(io.StringIO(commands), out)
    replies = {o["reply"]: o for o in map(json.loads, out.getvalue().splitlines())
               if "reply" in o}
    assert replies[1]["ok"] is True
    result = replies[1]["result"]
    assert _grid(result).shape == (result["rows"], result["cols"])
    assert replies[2]["ok"] is False and "limit" in replies[2]["error"]
