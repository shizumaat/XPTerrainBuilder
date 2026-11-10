"""Twins for converting built ortho tiles to on-demand form (#1992 P1c),
offline on synthetic Custom Scenery folders (one tile with the current
layout and manifest, one with the old layout: a cfg only, intermediates,
a ``.bak``):

* the copy keeps every texture name, each a whole placeholder whose
  levels are the source's own (no re-encode), copies ``terrain/`` and the
  ``.ter``-named borders, leaves out intermediates, and its DSF decodes to
  the source byte for byte;
* the manifest and the index rows name the full source; the swap is one
  atomic exchange, ``scenery_packs.ini`` and the source are untouched;
* a re-run is a no-op; a run killed mid-copy or at the swap leaves the
  entry pointing at a complete tile, and the next run finishes;
* ``revert`` swaps the entry back; a local folder entry is moved aside,
  never deleted;
* the follow job's lander lands from a mounted full source with no
  network, and falls through to the network when the source cannot
  serve the tier.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from types import SimpleNamespace

import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_DSF_Compress as DSFC
import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Convert as CONVERT
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Overlay_Utils as OVL
import O4_Path_Exchange as EXCHANGE
import pytest
from o4_engine import imagery_convert as ICONV
from o4_engine import imagery_follow_land as LAND

HAS_7Z = OVL.resolve_unzip_cmd() is not None
EXCHANGE_OK = sys.platform == "darwin" or sys.platform.startswith("linux")
FULL = 1024                     # fixture textures (4096 in a real tile)
PX = 256                        # placeholder width the twins convert to


def _dds(width: int, fmt: str, seed: int, mips: bool = True) -> bytes:
    count = DDS.full_mip_count(width, width) if mips else 1
    levels = []
    for k, (w, h) in enumerate(DDS.mip_dims(width, width, count)):
        size = DDS.level_size(w, h, fmt)
        levels.append(bytes((seed + k + i) % 251 for i in range(size)))
    return DDS.assemble(width, width, fmt, levels)


def _dsf(seed: int) -> bytes:
    payload = bytes((seed * 7 + i) % 256 for i in range(50_000))
    atom = b"DAEH" + struct.pack("<I", 8 + len(payload)) + payload
    body = b"XPLNEDSF" + struct.pack("<I", 1) + atom
    return body + hashlib.md5(body).digest()


def _write(path, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(path, "wb") as handle:
        handle.write(data)


def _tile(root, lat, lon, provider, zl, *, manifest: bool) -> str:
    tile = FNAMES.short_latlon(lat, lon)
    folder = os.path.join(root, "zOrtho4XP_" + tile)
    names = [f"{y}_{x}_{provider}{zl}.dds" for y, x in
             ((1000, 2000), (1000, 2016), (1016, 2000))]
    for n, name in enumerate(names):
        fmt = "bc3" if n == 1 else "bc1"
        _write(os.path.join(folder, "textures", name), _dds(FULL, fmt, n))
        _write(os.path.join(folder, "terrain", name[:-4] + ".ter"),
               f"A\n800\nTERRAIN\n\nLOAD_CENTER {lat}.5 {lon}.5 4744 4096\n"
               f"BASE_TEX_NOWRAP ../textures/{name}\nNO_ALPHA\n")
    nomip = f"1016_2016_{provider}{zl}.dds"
    _write(os.path.join(folder, "textures", nomip),
           _dds(FULL, "bc1", 9, mips=False))
    _write(os.path.join(folder, "terrain", nomip[:-4] + "_overlay.ter"),
           f"A\n800\nTERRAIN\n\nLOAD_CENTER {lat}.5 {lon}.5 4744 4096\n"
           f"BASE_TEX_NOWRAP ../textures/{nomip}\n"
           "BORDER_TEX ../textures/water_transition.png\nWET\n")
    _write(os.path.join(folder, "textures", "water_transition.png"), b"PNG1")
    _write(os.path.join(folder, "textures", "leftover.png"), b"x" * 999)
    nav = os.path.join(folder, "Earth nav data", "+00+000")
    _write(os.path.join(nav, tile + ".dsf"), _dsf(lat))
    _write(os.path.join(nav, tile + ".dsf.bak"), b"old" * 1000)
    _write(os.path.join(nav, tile + ".dsf.text"), b"PROPERTY x\n" * 99)
    _write(os.path.join(folder, f"Data{tile}.mesh"), b"m" * 5000)
    _write(os.path.join(folder, f"Ortho4XP_{tile}.cfg"), "zoomlevel=16\n")
    _write(os.path.join(folder, "build_logs", "a.log"), "log\n")
    if manifest:
        _write(os.path.join(folder, f"Ortho4XP_{tile}_imagery.json"),
               json.dumps({"provider": provider, "zoomlevel": zl}))
    return folder


def _hashes(folder) -> dict:
    out = {}
    for root, _d, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            with open(path, "rb") as handle:
                out[os.path.relpath(path, folder)] = hashlib.sha256(
                    handle.read()).hexdigest()
    return out


def _isolate(monkeypatch, tmp) -> None:
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda relative: str(tmp / "data" / relative))
    monkeypatch.setattr(CORES, "airport_points", lambda lat, lon: [])
    monkeypatch.setattr(ICONV, "_xplane_running", lambda: False)


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """A library volume with two built tiles (new and old layout), a
    Custom Scenery folder linking both plus a scenery_packs.ini, a data
    root."""
    _isolate(monkeypatch, tmp_path)
    library = tmp_path / "Library"
    new = _tile(str(library), 60, -136, "Arc", 16, manifest=True)
    old = _tile(str(library), 45, 7, "BI", 16, manifest=False)
    scenery = tmp_path / "X-Plane" / "Custom Scenery"
    scenery.mkdir(parents=True)
    for folder in (new, old):
        os.symlink(folder, scenery / os.path.basename(folder))
    ini = ("I\n1000 Version\nSCENERY\n\n"
           "SCENERY_PACK Custom Scenery/zOrtho4XP_+45+007/\n"
           "SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+60-136/\n")
    (scenery / "scenery_packs.ini").write_text(ini, encoding="utf-8",
                                              newline="\n")
    return SimpleNamespace(tmp=tmp_path, scenery=str(scenery), new=new,
                           old=old, ini=ini,
                           before={f: _hashes(f) for f in (new, old)},
                           index=str(tmp_path / "data" / "index.sqlite"),
                           work=str(tmp_path / "X-Plane" / "work"))


def _convert(world, names=None, **kw):
    kw.setdefault("swap", True)
    kw.setdefault("workers", 2)
    kw.setdefault("threads", 2)
    return ICONV.convert(world.scenery, names, px=PX, work_dir=world.work,
                         index=world.index, **kw)


def test_tier_from_file_is_the_sources_own_levels(tmp_path):
    path = str(tmp_path / "t.dds")
    data = _dds(FULL, "bc3", 3)
    _write(path, data)
    assert TIERS.tier_from_file(path, PX) == TIERS.tier_from_dds(data, PX)
    assert TIERS.tier_span(path, PX)[0] == "bc3"
    flat = str(tmp_path / "flat.dds")
    _write(flat, _dds(FULL, "bc1", 1, mips=False))
    assert TIERS.tier_from_file(flat, PX) is None
    assert TIERS.tier_from_file(path, 2 * FULL) is None


def test_plan_lists_what_is_written_and_left_out(world):
    plan = CONVERT.plan_tile(world.old, PX)
    assert len(plan.textures) == 4 and plan.whole_copies == 1
    copied = {r for (r, _s) in plan.copies}
    assert "textures/water_transition.png" in copied
    assert {r for (r, _s) in plan.skipped} >= {
        "textures/leftover.png", "Data+45+007.mesh", "build_logs",
        "Earth nav data/+00+000/+45+007.dsf.bak",
        "Earth nav data/+00+000/+45+007.dsf.text"}
    assert plan.manifest is None and len(plan.dsfs) == 1


def test_dry_run_sizes_without_writing(world):
    result = ICONV.dry_run(world.scenery, widths=(PX, 512),
                           sample_dsf=1 if HAS_7Z else 0)
    totals = result["totals"]
    assert totals["entries"] == 2 and totals["by_kind"] == {"link": 2}
    assert totals["enabled"] == 1               # +60-136 is disabled
    per = DDS.HEADER_BYTES + sum(TIERS.tier_span(
        os.path.join(world.new, "textures", "1000_2000_Arc16.dds"), PX)[2])
    assert totals[f"placeholder_bytes_{PX}"] >= 2 * 3 * per
    assert totals["skipped_bytes"] > 0
    assert {f: _hashes(f) for f in (world.new, world.old)} == world.before
    assert not os.path.exists(world.work)


def _check_copy(world, folder) -> None:
    name = os.path.basename(folder)
    entry = os.path.join(world.scenery, name)
    assert os.path.isdir(entry) and not os.path.islink(entry)
    assert CONVERT.is_converted(entry, folder, PX)
    assert os.path.islink(os.path.join(world.work, name + ".previous"))
    src_tex = sorted(n for n in os.listdir(os.path.join(folder, "textures"))
                     if n.endswith(".dds"))
    out_tex = sorted(n for n in os.listdir(os.path.join(entry, "textures"))
                     if n.endswith(".dds"))
    assert out_tex == src_tex
    for tex in src_tex:
        out = os.path.join(entry, "textures", tex)
        source = os.path.join(folder, "textures", tex)
        assert DDS.is_whole(out)
        want = TIERS.tier_from_file(source, PX)
        if want is None:                        # no mips: copied whole
            with open(source, "rb") as handle:
                want = handle.read()
        with open(out, "rb") as handle:
            assert handle.read() == want
    textures = os.path.join(entry, "textures")
    assert os.path.isfile(os.path.join(textures, "water_transition.png"))
    assert not os.path.exists(os.path.join(textures, "leftover.png"))
    assert not any(n.startswith("Data") for n in os.listdir(entry))
    (dsf,) = [os.path.join(r, f) for r, _d, fs in
              os.walk(os.path.join(entry, "Earth nav data")) for f in fs]
    assert dsf.endswith(".dsf")
    assert DSFC.decodes_to(dsf, dsf.replace(entry, folder))
    assert DSFC.is_compressed(dsf) == HAS_7Z
    tile = name[len("zOrtho4XP_"):]
    with open(os.path.join(entry, f"Ortho4XP_{tile}_imagery.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["on_demand"] and manifest["placeholder_px"] == PX
    assert manifest["full_source"] == folder
    assert manifest["zoomlevel"] == 16 and manifest["placeholder_zl"] == 12
    conn = INDEX.open_index(world.index)
    rows = INDEX.rows(conn, tile=tile)
    conn.close()
    assert len(rows) == 4
    for row in rows:
        assert row["state"] == "low" and row["build_dir"] == entry
        assert row["source_path"] == os.path.join(folder, "textures",
                                                  row["name"])
        assert row["load_size_m"] == 4744
        assert row["placeholder_path"] and os.path.isfile(
            row["placeholder_path"])


@pytest.mark.skipif(not EXCHANGE_OK, reason="no atomic exchange here")
def test_convert_swap_and_rerun(world):
    result = _convert(world)
    assert all("swapped" in r["status"] for r in result["rows"]), result
    for folder in (world.new, world.old):
        _check_copy(world, folder)
    with open(os.path.join(world.scenery, "scenery_packs.ini"),
              encoding="utf-8", newline="") as handle:
        assert handle.read() == world.ini
    assert {f: _hashes(f) for f in (world.new, world.old)} == world.before
    assert sorted(t[1:] for t in ICONV.converted_tiles()) == [
        (45, 7), (60, -136)]
    again = _convert(world)
    assert [r["status"] for r in again["rows"]] == ["already converted"] * 2
    assert again["bytes_written"] == 0


@pytest.mark.skipif(not EXCHANGE_OK, reason="no atomic exchange here")
def test_killed_mid_copy_or_at_swap_leaves_a_complete_entry(world,
                                                            monkeypatch):
    real = CONVERT._placeholder
    calls = {"n": 0}

    def dies(plan, rel, staged):
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyboardInterrupt("killed")
        return real(plan, rel, staged)
    monkeypatch.setattr(CONVERT, "_placeholder", dies)
    with pytest.raises(KeyboardInterrupt):
        _convert(world, workers=1, threads=1)
    entries = [os.path.join(world.scenery, os.path.basename(f))
               for f in (world.new, world.old)]
    # the tile killed mid-copy still links its source; the other worker
    # may have finished: then its entry is a complete, stamped copy
    killed = os.path.join(world.scenery, os.path.basename(world.old))
    assert os.path.islink(killed) and os.path.realpath(killed) == world.old
    other = os.path.join(world.scenery, os.path.basename(world.new))
    if not os.path.islink(other):
        _check_copy(world, world.new)
        ICONV.revert(world.scenery, os.path.basename(other),
                     work_dir=world.work, index=world.index)
    monkeypatch.setattr(CONVERT, "_placeholder", real)

    def refused(entry, incoming, work):
        raise OSError(16, "busy")
    monkeypatch.setattr(ICONV, "_swap", refused)
    rows = _convert(world)["rows"]
    assert all("NOT swapped" in r["status"] for r in rows), rows
    for entry, folder in zip(entries, (world.new, world.old)):
        assert os.path.islink(entry) and os.path.realpath(entry) == folder
    monkeypatch.undo()
    _isolate(monkeypatch, world.tmp)
    rows = _convert(world)["rows"]
    assert all("; swapped" in r["status"] for r in rows), rows
    for folder in (world.new, world.old):
        _check_copy(world, folder)


@pytest.mark.skipif(not EXCHANGE_OK, reason="no atomic exchange here")
def test_revert_and_local_folder_entries(world):
    name = os.path.basename(world.new)
    _convert(world, [name])
    ICONV.revert(world.scenery, name, work_dir=world.work,
                 index=world.index)
    entry = os.path.join(world.scenery, name)
    assert os.path.islink(entry) and os.path.realpath(entry) == world.new
    conn = INDEX.open_index(world.index)
    assert INDEX.rows(conn, tile="+60-136") == []
    conn.close()
    # a local folder entry: converted in place, the full folder moved aside
    local = os.path.join(world.scenery, os.path.basename(world.old))
    os.remove(local)
    os.rename(world.old, local)
    before = _hashes(local)
    (row,) = _convert(world, [os.path.basename(local)])["rows"]
    assert "; swapped" in row["status"], row
    aside = os.path.join(world.work, os.path.basename(local) + ".previous")
    assert _hashes(aside) == before
    conn = INDEX.open_index(world.index)
    rows = INDEX.rows(conn, tile="+45+007")
    conn.close()
    assert rows and all(DDS.is_whole(r["source_path"]) for r in rows)
    assert all(r["source_path"].startswith(aside) for r in rows)


def test_local_root_copy_touches_nothing_else(world):
    root = str(world.tmp / "root")
    rows = _convert(world, swap=False, local_root=root)["rows"]
    assert [r["status"] for r in rows] == ["copied", "copied"]
    assert not os.path.exists(world.work)
    for folder in (world.new, world.old):
        entry = os.path.join(world.scenery, os.path.basename(folder))
        assert os.path.islink(entry) and os.path.realpath(entry) == folder
        assert CONVERT.is_converted(os.path.join(root, os.path.basename(
            folder)), folder, PX)
    again = _convert(world, swap=False, local_root=root)["rows"]
    assert [r["status"] for r in again] == ["copy already done"] * 2


def test_lander_prefers_the_mounted_source(world, monkeypatch, tmp_path):
    import O4_Imagery_Utils as IMG
    called = []
    monkeypatch.setattr(IMG, "build_jpeg_ortho",
                        lambda *a, **k: called.append(a) or False)
    monkeypatch.setattr(LAND.TierLander, "_tile",
                        lambda self, r: SimpleNamespace(lat=60, lon=-136))
    build = tmp_path / "copy"
    name = "1000_2016_Arc16.dds"
    final = build / "textures" / name
    _write(str(final), TIERS.tier_from_file(
        os.path.join(world.new, "textures", name), PX))
    row = {"tile": "+60-136", "name": name, "zl": 16, "provider": "Arc",
           "build_dir": str(build), "dds_cache_key": None,
           "source_path": os.path.join(world.new, "textures", name)}
    lander = LAND.TierLander()
    facts = lander(row, 1)                      # 1024: the whole source
    assert facts["tier_px"] == FULL and facts["network"] is False
    with open(final, "rb") as a, open(row["source_path"], "rb") as b:
        assert a.read() == b.read()
    facts = lander(row, 0)                      # 512: cut from its levels
    assert facts["tier_px"] == 512 and not called
    assert TIERS.texture_header(str(final)) == (512, "bc3")
    with pytest.raises(RuntimeError):           # 4096: past the source
        lander(row, 3)
    assert called                               # fell through to the network
    row["source_path"] = str(tmp_path / "unmounted" / name)
    called.clear()
    with pytest.raises(RuntimeError):
        lander(row, 0)
    assert called and DDS.is_whole(str(final))


def test_exchange_is_atomic_and_probed(tmp_path):
    if not EXCHANGE_OK:
        assert not EXCHANGE.supported(str(tmp_path))
        return
    assert EXCHANGE.supported(str(tmp_path))
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "f").write_text("x", encoding="utf-8", newline="")
    os.symlink(str(tmp_path / "elsewhere"), tmp_path / "link")
    EXCHANGE.exchange(str(tmp_path / "d"), str(tmp_path / "link"))
    assert os.path.islink(tmp_path / "d")
    assert (tmp_path / "link" / "f").read_text(encoding="utf-8") == "x"
    with pytest.raises(FileNotFoundError):
        EXCHANGE.exchange(str(tmp_path / "nope"), str(tmp_path / "d"))
