"""Twins of the draped World-pack tile (``src/O4_World_Drape.py``,
``world.py drape``): the texture grid covers the tile exactly once, the
UV polygons and ``.pol`` files, the overlay DSF round trip through
DSFTool, and the kit command with the imagery fetch stubbed (no network).
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

import O4_World_Drape as DRAPE
import O4_World_Pack as WP

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tool():
    try:
        return WP.dsftool_path(ENGINE)
    except FileNotFoundError:
        return None


needs_dsftool = pytest.mark.skipif(_tool() is None, reason="no DSFTool")


def _fake_dds(path: str, px: int = 512) -> None:
    head = bytearray(128)
    head[:4] = b"DDS "
    head[12:16] = px.to_bytes(4, "little")
    head[16:20] = px.to_bytes(4, "little")
    with open(path, "wb") as handle:
        handle.write(bytes(head))


def _squares(lat, lon, zl):
    return [sq for sq in DRAPE.texture_squares(lat, lon, zl)
            if DRAPE.drape_quad(lat, lon, *sq, zl)]


@pytest.mark.parametrize("zl", [12, 16])
def test_squares_cover_the_tile_exactly_once(zl):
    quads = [DRAPE.drape_quad(52, -63, x, y, zl) for x, y in _squares(52, -63, zl)]
    area = sum((q[1][0] - q[0][0]) * (q[2][1] - q[1][1]) for q in quads)
    assert area == pytest.approx(1.0, abs=1e-9)
    for q in quads:
        assert all(-63 <= x <= -62 and 52 <= y <= 53 and 0 <= s <= 1
                   and 0 <= t <= 1 for x, y, s, t in q)
    if zl == 16:
        assert len(quads) == 228      # the +52-063 drape built 2026-11-10


def test_inner_square_maps_the_whole_texture_north_up():
    x, y = DRAPE.texture_squares(52, -63, 16)[30]
    quad = DRAPE.drape_quad(52, -63, x, y, 16)
    st = [(round(s, 6), round(t, 6)) for _, _, s, t in quad]
    assert st == [(0, 0), (1, 0), (1, 1), (0, 1)]   # SW, SE, NE, NW


def test_pol_and_dsf_text():
    x, y = DRAPE.texture_squares(52, -63, 16)[30]
    pol = DRAPE.pol_text("../../textures/+52-063/a.dds", x, y, 16, 512)
    for want in ("DRAPED_POLYGON", "TEXTURE_NOWRAP ../../textures/+52-063/a.dds",
                 "LAYER_GROUP terrain +1", "NO_ALPHA", "LOAD_CENTER 52."):
        assert want in pol
    assert pol.split("LOAD_CENTER")[1].split()[3] == "512"
    quad = DRAPE.drape_quad(52, -63, x, y, 16)
    text = DRAPE.drape_dsf_text(52, -63, [("terrain/+52-063/a.pol", quad)],
                                exclude=("for",))
    for want in ("PROPERTY sim/overlay 1", DRAPE.DRAPE_AGENT,
                 "PROPERTY sim/exclude_for -63/52/-62/53",
                 "POLYGON_DEF terrain/+52-063/a.pol",
                 "BEGIN_POLYGON 0 65535 4"):
        assert want in text
    with pytest.raises(ValueError):
        DRAPE.drape_dsf_text(52, -63, [], exclude=("trees",))


@needs_dsftool
def test_write_and_verify_round_trip(tmp_path):
    tex = tmp_path / "tex"
    tex.mkdir()
    squares = _squares(52, -63, 12)
    for x, y in squares[1:]:                       # the first one missing
        _fake_dds(str(tex / DRAPE.default_dds_name(x, y, 12, "BI")))
    out = tmp_path / "stage"
    counts = DRAPE.write_drape(52, -63, 12, "BI", str(tex), str(out), _tool(),
                               exclude=("obj",))
    assert counts["missing"] == 1
    assert counts["polygons"] == len(squares) - 1
    res = DRAPE.verify_drape(str(out), 52, -63, _tool())
    assert res["problems"] == [] and res["overlay"] and res["agent"]
    assert res["polygons"] == res["pols_checked"] == counts["polygons"]
    assert res["excludes"] == ["obj"]
    dsf = os.path.join(out, WP.dsf_relpath(52, -63))
    assert DRAPE.is_drape(dsf) and not WP.is_placeholder(dsf)
    assert WP.dsf_header(dsf)["md5_ok"]


def _world_module():
    spec = importlib.util.spec_from_file_location(
        "world_pack_tool", os.path.join(ENGINE, "tools", "world_pack.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@needs_dsftool
def test_kit_drape_command_swaps_a_verified_drape_in(tmp_path, monkeypatch):
    world = _world_module()
    kit = tmp_path / "kit"
    assert world.main(["--kit", str(kit), "make-kit", "--center", "+52-063",
                       "--radius", "0", "--xplane", str(tmp_path)]) == 0
    assert (kit / "O4_World_Drape_Fetch.py").is_file()

    def fake_engine(k, tile, argv, log_name, *rest, **kw):
        lat, lon, parent = int(argv[1]), int(argv[2]), argv[3]
        tex = os.path.join(parent, f"zOrtho4XP_{tile}", "textures")
        os.makedirs(tex, exist_ok=True)
        squares = _squares(lat, lon, 12)
        for x, y in squares:
            _fake_dds(os.path.join(tex, DRAPE.default_dds_name(x, y, 12, "BI")))
        log = os.path.join(k.build_root, log_name)
        os.makedirs(k.build_root, exist_ok=True)
        with open(log, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"textures": tex, "squares": len(squares),
                                     "dds": len(squares)}) + "\n")
        return 0, log

    monkeypatch.setattr(world, "run_engine", fake_engine)
    assert world.main(["--kit", str(kit), "drape", "+52-063", "--zl", "12",
                       "--no-webapi"]) == 0
    dsf = kit / WP.PACK_NAME / WP.dsf_relpath(52, -63)
    assert DRAPE.is_drape(str(dsf))
    assert world.main(["--kit", str(kit), "verify"]) == 0
    log = [json.loads(line) for line in open(kit / "world_log.jsonl", encoding="utf-8")]
    assert [r["event"] for r in log][-2:] == ["swapin", "drape_done"]
