"""Twins of the draped World-pack tile (``src/O4_World_Drape.py``,
``world.py drape``): the texture grid covers the tile exactly once, the
UV polygons and ``.pol`` files, the overlay DSF round trip through
DSFTool, and the kit command with the imagery fetch stubbed (no network).
"""
from __future__ import annotations

import importlib.util
import json
import os

import O4_World_Drape as DRAPE
import O4_World_Pack as WP
import pytest

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


def test_default_pol_is_unchanged_and_the_water_copy_keeps_its_alpha():
    x, y = DRAPE.texture_squares(52, -63, 16)[30]
    plain = DRAPE.pol_text("../../textures/+52-063/a.dds", x, y, 16, 512)
    assert "LAYER_GROUP terrain +1" in plain and "NO_ALPHA" in plain
    water = DRAPE.pol_text("../../textures/+52-063/a.dds", x, y, 16, 512,
                           DRAPE.WATER_LAYER_GROUP, alpha=True)
    assert f"LAYER_GROUP {DRAPE.WATER_LAYER_GROUP}" in water
    assert "NO_ALPHA" not in water
    assert water.replace(DRAPE.WATER_LAYER_GROUP, "terrain +1") \
        == plain.replace("NO_ALPHA\n", "")


def _fake_dxt5(path: str, px: int = 512) -> None:
    _fake_dds(path, px)
    with open(path, "r+b") as handle:
        handle.seek(84)
        handle.write(b"DXT5")


@needs_dsftool
def test_water_layer_adds_one_alpha_copy_per_masked_square(tmp_path):
    tex = tmp_path / "tex"
    tex.mkdir()
    squares = _squares(52, -63, 12)
    for i, (x, y) in enumerate(squares):
        make = _fake_dxt5 if i % 2 == 0 else _fake_dds
        make(str(tex / DRAPE.default_dds_name(x, y, 12, "BI")))
    plain = DRAPE.write_drape(52, -63, 12, "BI", str(tex),
                              str(tmp_path / "plain"), _tool())
    assert plain["water"] == 0 and plain["polygons"] == len(squares)
    out = tmp_path / "water"
    counts = DRAPE.write_drape(52, -63, 12, "BI", str(tex), str(out), _tool(),
                               water_layer=DRAPE.WATER_LAYER_GROUP)
    want = len(squares[::2])
    assert counts["water"] == want
    assert counts["polygons"] == len(squares) + want
    res = DRAPE.verify_drape(str(out), 52, -63, _tool())
    assert res["problems"] == [] and res["polygons"] == counts["polygons"]
    pols = sorted(os.listdir(out / "terrain" / "+52-063"))
    assert sum(p.endswith("_water.pol") for p in pols) == want


def test_square_mask_is_opaque_on_land_and_translucent_on_the_lake():
    import O4_World_Drape_Water as WATER
    from shapely.geometry import Polygon
    x, y = DRAPE.texture_squares(52, -63, 16)[30]
    south, west, north, east = DRAPE._bounds(x, y, 16)
    mid_lat, mid_lon = (south + north) / 2, (west + east) / 2
    # a lake over the square's west half, tile-relative degrees
    lake = Polygon([(west - 0.01 + 63, south - 0.01 - 52),
                    (mid_lon + 63, south - 0.01 - 52),
                    (mid_lon + 63, north + 0.01 - 52),
                    (west - 0.01 + 63, north + 0.01 - 52)])
    mask = WATER.square_mask(lake, 52, -63, x, y, 16, 512, 99, 10)
    assert mask.shape == (512, 512)
    assert mask[256, 500] == 255                   # east: land
    assert mask[256, 20] == 99                     # deep in the lake: the grey
    assert 99 < mask[256, 252] <= 255              # the shore feather
    far = Polygon([(0.9, 0.9), (0.95, 0.9), (0.95, 0.95)])
    assert WATER.square_mask(far, 52, -63, x, y, 16, 512, 99, 10) is None
    whole = lake.buffer(0.2)
    flat = WATER.square_mask(whole, 52, -63, x, y, 16, 512, 99, 10)
    assert (flat == 99).all()


@needs_dsftool
def test_kit_drape_water_alpha_is_staged_apart_and_swaps_in_from_water(
        tmp_path, monkeypatch):
    world = _world_module()
    kit = tmp_path / "kit"
    assert world.main(["--kit", str(kit), "make-kit", "--center", "+52-063",
                       "--radius", "0", "--xplane", str(tmp_path)]) == 0
    assert (kit / "O4_World_Drape_Water.py").is_file()
    seen = []

    def fake_engine(k, tile, argv, log_name, *rest, **kw):
        seen.append(argv)
        lat, lon, parent = int(argv[1]), int(argv[2]), argv[3]
        tex = os.path.join(parent, f"zOrtho4XP_{tile}", "textures")
        os.makedirs(tex, exist_ok=True)
        squares = _squares(lat, lon, 12)
        for x, y in squares:
            _fake_dxt5(os.path.join(tex, DRAPE.default_dds_name(x, y, 12, "BI")))
        log = os.path.join(k.build_root, log_name)
        os.makedirs(k.build_root, exist_ok=True)
        with open(log, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"textures": tex, "squares": len(squares),
                                     "dds": len(squares)}) + "\n")
        return 0, log

    monkeypatch.setattr(world, "run_engine", fake_engine)
    assert world.main(["--kit", str(kit), "drape", "+52-063", "--zl", "12",
                       "--water-alpha", "--no-swap", "--no-webapi"]) == 0
    assert "--water-alpha" in seen[0] and seen[0][3].endswith("work-water")
    staged = kit / "drapes" / "water" / "+52-063"
    pols = os.listdir(staged / "terrain" / "+52-063")
    water = [p for p in pols if p.endswith("_water.pol")]
    assert water and len(water) * 2 == len(pols)
    body = (staged / "terrain" / "+52-063" / water[0]).read_text(encoding="utf-8")
    assert f"LAYER_GROUP {DRAPE.WATER_LAYER_GROUP}" in body
    dsf = kit / WP.PACK_NAME / WP.dsf_relpath(52, -63)
    assert WP.is_placeholder(str(dsf))                  # --no-swap
    assert world.main(["--kit", str(kit), "verify"]) == 0
    assert world.main(["--kit", str(kit), "swapin", "+52-063", "--from",
                       "water", "--force", "--no-webapi"]) == 0
    assert DRAPE.is_drape(str(dsf))


# ─── the fly-over kind (RULINGS 2026-11-11j, lane ldrape2) ─────────────────

def test_the_water_copy_draws_on_airports_minus_one_at_135():
    """11j (1)/(2): above X-Plane 12's water (``airports -1``, measured on
    the owner's flight; ``beaches +1`` stays under it), open water at
    135/255 — one constant, no setting."""
    import O4_World_Drape_Water as WATER
    assert DRAPE.WATER_LAYER_GROUP == "airports -1"
    assert DRAPE.LAYER_GROUP == "terrain +1"
    assert WATER.OPEN_WATER_ALPHA == 135


def test_write_masks_puts_135_on_open_water_and_255_on_land(tmp_path,
                                                            monkeypatch):
    """The masks the DDS alpha is imprinted from: the lake's deep water at
    :data:`OPEN_WATER_ALPHA`, land opaque, the 120 m feather between;
    written on a thread beside the download (``start_masks``)."""
    import threading

    import numpy
    import O4_World_Drape_Water as WATER
    from PIL import Image
    from shapely.geometry import Polygon

    class Tile:
        lat, lon, build_dir = 52, -63, str(tmp_path)
        inland_shore_feather_m = 120.0
    (tmp_path / "textures").mkdir()
    x, y = DRAPE.texture_squares(52, -63, 16)[30]
    south, west, north, east = DRAPE._bounds(x, y, 16)
    mid_lon = (west + east) / 2
    lake = Polygon([(west - 0.01 + 63, south - 0.01 - 52),
                    (mid_lon + 63, south - 0.01 - 52),
                    (mid_lon + 63, north + 0.01 - 52),
                    (west - 0.01 + 63, north + 0.01 - 52)])
    out = WATER._write_masks(Tile(), [(x, y)], 16, "BI", 512,
                            water=lambda: (lake, 1.5))
    assert out["masked"] == 1 and out["water_fetch_s"] == 1.5
    mask = numpy.array(Image.open(tmp_path / "textures" / f"{y}_{x}_ZL16.png"))
    assert mask[256, 20] == 135 and mask[256, 500] == 255
    assert 135 < mask[256, 250] < 255                # the shore feather
    none = WATER._write_masks(Tile(), [(x, y)], 16, "BI", 512,
                             water=lambda: (None, 0.5))
    assert none["water_data"] is False and none["masked"] == 0
    # on a thread beside the download; a join past its wait gives None
    gate = threading.Event()
    monkeypatch.setattr(WATER, "_inland", lambda tile: gate.wait(5) and lake)
    monkeypatch.setattr(WATER, "_sea", lambda tile: None)
    join = WATER.start_masks(Tile(), [(x, y)], 16, "BI", 512)
    assert join(0.1) is None
    gate.set()
    assert join(10)["masked"] == 1


def test_start_water_overlaps_and_gives_up_at_its_wait(monkeypatch):
    """The water read runs on threads (inland and sea at once) while the
    photos download; past the wait the joiner answers ``(None, None)``."""
    import threading
    import time

    import O4_World_Drape_Water as WATER
    from shapely.geometry import box
    gate = threading.Event()
    monkeypatch.setattr(WATER, "_inland", lambda tile: box(0, 0, .1, .1))
    monkeypatch.setattr(WATER, "_sea", lambda tile: gate.wait(5) and box(.5, .5, 1, 1))
    t0 = time.time()
    join = WATER._start_water(object())
    assert join(0.2) == (None, None) and time.time() - t0 < 2
    gate.set()
    area, seconds = join()
    assert area.area == pytest.approx(0.01 + 0.25) and seconds >= 0


@needs_dsftool
def test_the_world_jobs_drape_has_both_polygon_sets(tmp_path, monkeypatch):
    """``world_job_run.drape_tile``, the build-ahead/corridor path: the
    user's ``drape_photo_px`` picks the fetch tier, the fetch asks for the
    water masks (bounded wait), and the staged tile carries the opaque
    photo on ``terrain +1`` plus the alpha copy on ``airports -1`` for
    every masked square, read back by DSFTool; the build folder goes."""
    import O4_World_Drape_Fetch as FETCH
    from o4_engine import world_commands as WORLD
    from o4_engine import world_job_run as RUN
    calls = []
    build = tmp_path / "World_build" / "zOrtho4XP_+52-063"

    def fake_fetch(engine, lat, lon, parent, zl, provider, drop, **kw):
        calls.append((zl, provider, drop, kw))
        tex = build / "textures"
        tex.mkdir(parents=True)
        for i, (x, y) in enumerate(_squares(lat, lon, zl)):
            make = _fake_dxt5 if i % 3 else _fake_dds   # 2 of 3 touch water
            make(str(tex / DRAPE.default_dds_name(x, y, zl, provider)), 1024)
        return {"tile": str(build), "textures": str(tex)}
    monkeypatch.setattr(FETCH, "fetch", fake_fetch)
    from o4_engine import world_drape_process as DRAPE_PROCESS
    process = []                        # the work, here (twins below)
    monkeypatch.setattr(DRAPE_PROCESS, "run", lambda **kw: process.append(
        sorted(kw)) or DRAPE_PROCESS.fetch_drape(**kw))
    monkeypatch.setattr(RUN, "_settings", lambda: {"drape_photo_px": 1024})
    monkeypatch.setattr(WORLD, "staging_root", lambda: str(tmp_path / "staging"))
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "data_path", lambda *p: str(tmp_path.joinpath(*p)))
    assert RUN.drape_tile((52, -63), "BI", 12)
    (zl, provider, drop, kw), = calls
    assert (zl, provider, drop) == (12, "BI", FETCH.PX_DROPS[1024])
    blend = kw.pop("blend")             # #2018: made when the fetch asks
    assert kw == {"water_alpha": True, "water_wait_s": RUN.WATER_WAIT_S}
    assert callable(blend)
    assert len(process) == 1            # the fetch went to its process
    assert not build.exists()
    staged = tmp_path / "staging" / "+52-063"
    # the staged tile carries its World pack record (#2018)
    record = json.loads((staged / "XPTerrainBuilder_imagery.json").read_text(
        encoding="utf-8"))
    assert (record["provider"], record["zl"], record["kind"]) == ("BI", 12, "drape")
    squares = _squares(52, -63, 12)
    water = len([s for i, s in enumerate(squares) if i % 3])
    res = DRAPE.verify_drape(str(staged), 52, -63, _tool())
    assert res["problems"] == [] and res["polygons"] == len(squares) + water
    pols = sorted((staged / "terrain" / "+52-063").iterdir())
    layers = [next(line for line in p.read_text(encoding="utf-8").splitlines()
                   if line.startswith("LAYER_GROUP")) for p in pols]
    assert layers.count("LAYER_GROUP airports -1") == water
    assert layers.count("LAYER_GROUP terrain +1") == len(squares)
    assert all("NO_ALPHA" not in p.read_text(encoding="utf-8")
               for p in pols if p.name.endswith("_water.pol"))


def _child_pid(**_kw) -> int:
    print("CHILD-STDOUT")               # never onto the engine's protocol
    return os.getpid()


def test_a_drape_fetches_in_a_process_of_its_own(capfd):
    """#2037: a drape's fetch and convert held the engine's interpreter
    lock beside the follow job; ``world_drape_process.run`` answers from
    another process, whose printed lines go to standard error (the
    engine's standard output is the protocol stream it inherits)."""
    from o4_engine import world_drape_process as DRAPE_PROCESS
    pid = DRAPE_PROCESS.run(task=_child_pid, lat=1)
    assert isinstance(pid, int) and pid != os.getpid()
    out, err = capfd.readouterr()
    assert "CHILD-STDOUT" not in out and "CHILD-STDOUT" in err
