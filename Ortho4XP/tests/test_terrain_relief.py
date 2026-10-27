"""``terrain_relief`` (#1320, owner Q134: hillshade plus contours) over
synthetic relief: the raster on a plane plus a hill and on a slope, the
command over a sampler stub and its JSON-lines round trip.  No network,
no corpus."""
import base64
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from o4_engine import elevation_commands as EC  # noqa: E402
from o4_engine import relief as R  # noqa: E402
from o4_engine import relief_commands as RC  # noqa: E402


def _hill(n=201, height=10.0, base=100.0, cell_m=1.0):
    """A plane at ``base`` m with a cone ``height`` m tall in the middle,
    radius a third of the grid."""
    yy, xx = np.mgrid[0:n, 0:n] * cell_m
    c = (n - 1) * cell_m / 2
    r = np.hypot(xx - c, yy - c)
    return base + np.clip(height * (1 - r / (n * cell_m / 3)), 0, None)


def test_plane_plus_hill_contours_one_per_metre():
    pic = R.relief_rgba(_hill(), 1.0, 1.0, 1.0)
    assert pic.rgba.shape == (201, 201, 4) and pic.rgba.dtype == np.uint8
    # the cone rises from 100 m to 110 m: a line at 101 .. 110 m
    assert sorted(pic.levels) == [float(v) for v in range(101, 111)]
    assert pic.min_m == 100.0 and pic.max_m == pytest.approx(110.0)
    index = np.all(pic.rgba[..., :3] == R.INDEX_RGB, axis=-1)
    minor = np.all(pic.rgba[..., :3] == R.CONTOUR_RGB, axis=-1)
    assert index.any() and minor.any() and minor.sum() > index.sum()
    # the plane far from the hill: no line, flat shade sin(45 deg)
    assert not (index[:20, :20].any() or minor[:20, :20].any())
    assert abs(int(pic.rgba[5, 5, 0]) - round(255 * np.sin(np.radians(45)))) <= 1


def test_half_metre_contours():
    pic = R.relief_rgba(_hill(), 1.0, 1.0, 0.5)
    assert len(pic.levels) == 20


def test_hillshade_monotone_on_a_slope():
    # rising toward the west (faces east, away from a north-west sun),
    # steeper eastward: darker eastward, never lighter
    x = np.arange(200, dtype=float)
    z = np.tile(-0.002 * x ** 2, (50, 1))
    shade = R.hillshade(z, 1.0, 1.0)[25, 1:-1]
    assert np.all(np.diff(shade) <= 1e-12) and shade[0] > shade[-1] + 0.2
    # the same slope facing the sun is lighter than flat
    assert R.hillshade(np.tile(0.3 * x, (5, 1)), 1.0, 1.0)[2, 100] > np.sin(np.radians(45))


def test_nan_is_transparent():
    z = _hill(51)
    z[:10] = np.nan
    pic = R.relief_rgba(z, 1.0, 1.0, 1.0)
    assert (pic.rgba[:10, :, 3] == 0).all() and (pic.rgba[20:, :, 3] == 255).all()


def test_default_step():
    assert R.contour_step(1.0, 100, 110) == 1.0
    assert R.contour_step(0.2, 100, 110) == 0.5
    # 1,000 m of relief would be 1,000 lines: coarsened 1-2-5
    assert R.contour_step(5.0, 0, 1000) == 10.0
    assert R.contour_step(5.0, None, None) == 1.0


# ─── the command ───────────────────────────────────────────────────────────

class _Hit:
    def __init__(self, z):
        self.elevation_metres = z


class _HillSampler:
    """A mesh stub: a 10 m cone at the box centre over a 100 m plane;
    nothing (the DEM's part) west of ``west_edge``."""

    def __init__(self, centre, west_edge=None):
        self.centre, self.west_edge = centre, west_edge

    def sample_many(self, la, lo):
        dy = (la - self.centre[0]) * 111320.0
        dx = (lo - self.centre[1]) * 111320.0 * np.cos(np.radians(self.centre[0]))
        z = 100 + np.clip(10 * (1 - np.hypot(dx, dy) / 150.0), 0, None)
        return [None if self.west_edge is not None and x < self.west_edge else _Hit(v)
                for x, v in zip(lo, z, strict=True)]


@pytest.fixture
def stub(monkeypatch):
    for cache in (EC._MESH, EC._DEM, EC._LOADING, RC._RELIEF):
        cache.clear()
    box = [45.500, -122.600, 45.504, -122.594]
    centre = (45.502, -122.597)
    state = {"sampler": _HillSampler(centre)}
    monkeypatch.setattr(EC, "_mesh_sampler", lambda *a: (state["sampler"], False))
    monkeypatch.setattr(EC, "_dem_source",
                        lambda *a: (lambda la, lo: np.full(len(la), 100.0), False))
    monkeypatch.setattr(EC, "_stamp", lambda path: (1, 1))
    yield box, state
    for cache in (EC._MESH, EC._DEM, EC._LOADING, RC._RELIEF):
        cache.clear()


def _settle(**kw):
    for _ in range(500):
        r = RC.terrain_relief(**kw)
        if not r["pending"]:
            return r
        time.sleep(0.01)
    raise AssertionError("still pending")


def _png(reply):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(reply["png_b64"])))


def test_command_draws_the_hill(stub):
    box, _ = stub
    first = RC.terrain_relief("+45-123", box, 160, 120)
    assert first["pending"] and first["png_b64"] is None     # never draws inline
    r = _settle(tile="+45-123", bbox=box, px_w=160, px_h=120)
    image = _png(r)
    assert image.size == (160, 120) and image.mode == "RGBA"
    assert r["source"] == "mesh" and r["bbox"] == box
    assert r["legend"]["contour_m"] == 1.0
    assert r["legend"]["min_m"] == pytest.approx(100.0)
    assert 109.0 < r["legend"]["max_m"] <= 110.0
    # cached: the same answer at once
    assert RC.terrain_relief("+45-123", box, 160, 120) is r


def test_command_mixes_dem_where_the_mesh_ends(stub):
    box, state = stub
    state["sampler"] = _HillSampler((45.502, -122.597), west_edge=-122.598)
    r = _settle(tile="+45-123", bbox=box, px_w=60, px_h=40, contour_m=2)
    assert r["source"] == "mixed" and r["legend"]["contour_m"] == 2.0


def test_box_clipped_to_tile_and_refusals(stub):
    r = _settle(tile="+45-123", bbox=[45.99, -122.01, 46.5, -121.5], px_w=10, px_h=10)
    assert r["bbox"] == [45.99, -122.01, 46.0, -122.0]
    with pytest.raises(ValueError, match="terrain_relief"):
        RC.terrain_relief("+45-123", [47, -122, 47.1, -121.9], 10, 10)
    with pytest.raises(ValueError, match="px_w"):
        RC.terrain_relief("+45-123", [45.1, -122.9, 45.2, -122.8], 0, 10)
    with pytest.raises(ValueError, match="tile key"):
        RC.terrain_relief("nowhere", [45.1, -122.9, 45.2, -122.8], 10, 10)
    with pytest.raises(ValueError, match="contour_m"):
        RC.terrain_relief("+45-123", [45.1, -122.9, 45.2, -122.8], 10, 10, contour_m=-1)


def test_rows_even_in_mercator():
    lats, lons = RC.pixel_centres((45.0, -123.0, 46.0, -122.0), 4, 4)
    assert lats[0] > lats[-1] and lons[0] < lons[-1]
    merc = np.log(np.tan(np.pi / 4 + np.radians(lats) / 2))
    assert np.allclose(np.diff(merc), np.diff(merc)[0])


def test_engine_table_and_worker_process_have_the_command():
    from unittest import mock

    from o4_engine import command_process, jsonl
    assert jsonl._build_handlers(mock.MagicMock())["terrain_relief"] is RC.terrain_relief
    assert "terrain_relief" in command_process.COMMANDS
    assert command_process._handler("terrain_relief") is RC.terrain_relief


def test_jsonl_round_trip(stub):
    """Through the transport itself: the pending reply, then the picture."""
    from o4_engine import jsonl
    box, _ = stub
    ask = {"cmd": "terrain_relief", "tile": "+45-123", "bbox": box, "px_w": 32, "px_h": 24}
    _settle(tile="+45-123", bbox=box, px_w=32, px_h=24)      # drawn and cached
    reply = next(iter(RC._RELIEF.values()))
    commands = [dict(ask, id=1), {"cmd": "shutdown", "id": 2}]
    out = io.StringIO()
    jsonl.serve(io.StringIO("\n".join(json.dumps(c) for c in commands) + "\n"), out)
    replies = {o["reply"]: o for o in map(json.loads, out.getvalue().splitlines()) if "reply" in o}
    back = replies[1]["result"]
    assert replies[1]["ok"] and back == json.loads(json.dumps(reply))
    assert set(back) == {"pending", "png_b64", "width", "height", "bbox", "source", "legend"}
    assert set(back["legend"]) == {"min_m", "max_m", "contour_m"}
    assert _png(back).size == (32, 24)
