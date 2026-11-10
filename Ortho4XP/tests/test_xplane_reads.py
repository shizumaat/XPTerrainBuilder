"""Twins for the X-Plane read recorder (#1992 P1b, tools/xplane_reads/).

Fixtures (tests/fixtures/xplane_reads/), real data with the kit's folder
rewritten to ``/fixture/``:
  fs_usage_trim.txt      fs_usage -w lines: one X-Plane load of a test-pack
                         DDS (open, lseek, mmap, 9 PgIn, close) and the
                         recorder's own self-test (pread with O= flag bits)
  flight2_trim.jsonl.gz  flight 2's log cut to the test-pack loads,
                         positions and the DDS headers (801 loads)
The tools are standard library only and run under /usr/bin/python3 3.9;
these twins import them with no engine on the path.
"""
from __future__ import annotations

import datetime
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent
TOOL = ENGINE / "tools" / "xplane_reads"
FX = Path(__file__).resolve().parent / "fixtures" / "xplane_reads"
PACK = "/fixture/zOrtho4XP_+60-136_swaptest"
sys.path.insert(0, str(TOOL))

import analyse_reads as AR  # noqa: E402
import reads_fs_usage as FS  # noqa: E402
import reads_textures as TX  # noqa: E402
import reads_thresholds as TH  # noqa: E402


def _lines():
    return FX.joinpath("fs_usage_trim.txt").read_text(
        encoding="utf-8").splitlines()


def _line(needle: str) -> str:
    return next(x for x in _lines() if needle in x)


# -- fs_usage line parsing ---------------------------------------------------

def test_pread_offset_has_the_flag_bits_masked():
    """fs_usage printed a pread at 0x800080 as O=0x01000000800080."""
    ev = FS.parse_line(_line("O=0x01000000800080"))
    assert ev["call"] == "pread"
    assert ev["F"] == 8 and ev["B"] == 0x10000
    assert ev["O"] == 0x800080
    assert ev["pname"] == "Python" and ev["proc"] == "Python.27655402"


def test_page_in_line_carries_disk_block_bytes_device_and_path():
    ev = FS.parse_line(_line("D=0x0b9b7de4"))
    assert ev["call"] == "PgIn[A]"
    assert (ev["D"], ev["B"], ev["dev"]) == (0x0b9b7de4, 0x4000,
                                             "/dev/disk3s1")
    assert ev["path"] == PACK + "/textures/18912_8128_Arc16.dds"
    assert ev["pname"] == "X-Plane"


def test_open_line_path_and_fd():
    ev = FS.parse_line(_line("open              F=229      (R___"))
    assert ev["F"] == 229
    assert ev["path"].endswith("textures/18912_8128_Arc16.dds")


def _tracker(scope="tile"):
    out = []
    tr = FS.Tracker(out.append, FS.Scope(scope, [PACK], []), None,
                    probe=False, evict=False)
    return tr, out


def _feed(tr, lines):
    clock = FS.TodClock(datetime.datetime(2026, 11, 10))
    for ln, text in enumerate(lines, 1):
        FS.feed_text(tr, clock, text, ln)


def test_fd_table_is_per_process():
    """Another process closing the same fd number must not end X-Plane's
    load (the master's fix: fds keyed by (process name, fd)).  The Python
    close line is synthetic: X-Plane's own close with the process swapped."""
    lines = _lines()
    i_open = next(i for i, x in enumerate(lines)
                  if "open " in x and "F=229" in x and "18912_8128" in x)
    xp_close = next(x for x in lines[i_open:] if "close" in x
                    and "F=229" in x)
    other = xp_close.replace("X-Plane.27647963", "Python.27655402")
    seq = lines[:i_open + 1] + [other] + lines[i_open + 1:]
    tr, out = _tracker()
    _feed(tr, seq)
    closes = [r for r in out if r["kind"] == "close"
              and r["path"].endswith("18912_8128_Arc16.dds")]
    assert len(closes) == 1
    assert closes[0]["proc"] == "X-Plane"
    assert closes[0]["ln"] == seq.index(xp_close) + 1


def test_one_xplane_load_and_the_self_test_read():
    tr, out = _tracker()
    _feed(tr, _lines())
    xp = [r for r in out if r.get("proc") == "X-Plane"]
    kinds = [r["kind"] for r in xp]
    assert kinds.count("open") == 1 and kinds.count("close") == 1
    assert kinds.count("disk") == 9
    assert all(r["path"].endswith("18912_8128_Arc16.dds")
               for r in xp if r["kind"] in ("open", "disk", "close"))
    opened = next(r for r in xp if r["kind"] == "open")
    assert opened["tile"] is True
    reads = [r for r in out if r["kind"] == "read"]
    assert any(r["offset"] == 0x800080 and r["offset_known"] for r in reads)
    # the drm prefs file X-Plane opens next on the same fd is not tracked
    assert not any("X-Plane_drm" in str(r.get("path")) for r in out
                   if r["kind"] != "sample")


def test_from_text_cli_writes_the_records(tmp_path):
    out = tmp_path / "parsed.jsonl"
    done = subprocess.run(
        [sys.executable, str(TOOL / "record_reads.py"), "--from-text",
         str(FX / "fs_usage_trim.txt"), "--pack", PACK, "--scope", "tile",
         "--date", "2026-11-10", "--out", str(out)],
        capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    recs = [json.loads(x) for x in out.read_text(encoding="utf-8")
            .splitlines()]
    assert recs[0]["kind"] == "meta" and recs[0]["packs"] == [PACK]
    kinds = [r["kind"] for r in recs]
    assert kinds.count("open") == 1 and kinds.count("disk") == 9
    assert recs[-1]["kind"] == "summary"


def test_recording_needs_a_pack(tmp_path):
    done = subprocess.run(
        [sys.executable, str(TOOL / "record_reads.py"), "--minutes", "1",
         "--out", str(tmp_path / "x.jsonl")], capture_output=True,
        timeout=120)
    assert done.returncode == 2 and b"--pack" in done.stderr


# -- mip from resident pages -------------------------------------------------

DXT1_4096 = {"width": 4096, "height": 4096, "mips": 13, "header": 128,
             "block": 8, "pixel": None}


def test_mip_ranges_of_a_4096_dxt1():
    m = TX.mip_ranges(DXT1_4096)
    assert m[0][1:3] == (128, 128 + 8 * 1024 * 1024)
    assert m[1][1] == m[0][2] and m[1][2] - m[1][1] == 8 * 512 * 512
    assert len(m) == 13


@pytest.mark.parametrize("mip", [0, 1, 2, 3, 4])
def test_resident_pages_name_the_finest_mip(mip):
    """Pages covering mip k..12 (plus the header page) -> finest = k."""
    ps = 16384
    start = TX.mip_ranges(DXT1_4096)[mip][1]
    size = TX.mip_ranges(DXT1_4096)[-1][2]
    pages = [[0, 1], [start // ps, (size + ps - 1) // ps]]
    assert TX.resident_finest(DXT1_4096, pages, ps) == mip


def test_flight2_resident_pages_read_as_mip3():
    """Flight 2's first load: pages [[0,8],[672,683]] of a 4096 DXT1."""
    assert TX.resident_finest(DXT1_4096, [[0, 8], [672, 683]], 16384) == 3


def test_load_center_size_from_the_name_matches_the_ter():
    """The flight-2 pack's .ter files say 4744 (ZL16 at 61 N) and 1195."""
    assert TX.square_size_m(TX.parse_name("18656_8000_Arc16.dds")) == 4744
    s, src = TX.load_center_of("/nowhere/textures/18656_8000_Arc16.dds",
                               TX.parse_name("18656_8000_Arc16.dds"))
    assert (s, src) == (4744, "name")


def test_ter_load_center_is_read(tmp_path):
    (tmp_path / "terrain").mkdir()
    (tmp_path / "textures").mkdir()
    (tmp_path / "terrain" / "18656_8000_Arc16.ter").write_text(
        "A\n800\nTERRAIN\n\nLOAD_CENTER 60.99442 -136.01074 4800 4096\n",
        encoding="utf-8", newline="\n")
    dds = tmp_path / "textures" / "18656_8000_Arc16.dds"
    got = TX.load_center_of(str(dds), TX.parse_name(dds.name))
    assert got == (4800, "ter")


# -- the analysis on flight 2 (spec section 2.5) -----------------------------

@pytest.fixture(scope="module")
def flight2():
    ev = AR.load(str(FX / "flight2_trim.jsonl.gz"))
    A = AR.analyse(ev, "camera", "centre")
    return [L for L in A["loads"] if L["tile"]]


def test_flight2_every_load_has_mip_evidence(flight2):
    assert len(flight2) == 801
    assert all(L["finest"] is not None for L in flight2)


def test_flight2_band_table_reproduces_the_spec(flight2):
    (_, heads, _), *rows = AR.band_table(flight2)
    assert heads == ["mip 0", "mip 1", "mip 2", "mip 3", "? mip"]
    got = {label: cells[:4] for label, cells, _mb in rows}
    assert got == {
        "0-2 km": ["12/9", "", "", ""],
        "2-5 km": ["2/2", "13/10", "", ""],
        "5-10 km": ["88/66", "2/2", "16/16", ""],
        "10-20 km": ["1/1", "142/98", "", "20/20"],
        "20-40 km": ["", "", "229/151", ""],
        "40-80 km": ["", "", "", "276/222"],
    }


def test_flight2_reload_steps(flight2):
    steps = AR.reload_steps(AR.by_texture(flight2))
    assert (steps["finer"], steps["coarser"], steps["same"]) == (399, 123, 37)


@pytest.mark.parametrize("zl,mip,n,med,in_s", [
    (16, 0, 83, 7.8, 1.63), (16, 1, 122, 13.3, 2.80), (16, 2, 161, 24.6, 5.14),
    (18, 0, 7, 2.0, 1.64), (18, 1, 10, 3.2, 2.69), (18, 2, 16, 5.7, 4.76)])
def test_flight2_step_up_thresholds(flight2, zl, mip, n, med, in_s):
    v = TH.thresholds(flight2)[("step_up", zl, mip)]
    assert v["n"] == n
    assert round(v["med"], 1) == med
    assert round(v["med_S"], 2) == in_s
    assert v["S_src"] == "name"


def test_flight2_entry_mip3_is_about_ten_s(flight2):
    th = TH.thresholds(flight2)
    z16, z18 = th[("entry", 16, 3)], th[("entry", 18, 3)]
    assert 46.5 < z16["med"] < 48.0 and z16["n"] == 245
    assert round(z18["med"], 1) == 11.2 and z18["n"] == 20
    assert 9.0 < z16["med_S"] < 10.5 and 9.0 < z18["med_S"] < 10.5


def test_the_report_prints_every_section():
    done = subprocess.run(
        [sys.executable, str(TOOL / "analyse_reads.py"),
         str(FX / "flight2_trim.jsonl.gz")], capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    text = done.stdout.decode("utf-8")
    for head in ("1. loads by distance", "2. textures loaded", "3. timeline",
                 "4. re-loads", "5. .ter opens", "6. checks",
                 "7. thresholds", "8. frame time"):
        assert head in text, head
    assert "c_0 = 1.63" in text


# -- frame time (U10) --------------------------------------------------------

def test_frame_stats_names_the_worst_samples_and_nearby_loads():
    pos = [{"t": float(t), "frame_s": 0.02} for t in range(10)]
    pos[5]["frame_s"] = 0.25
    loads = [{"t": 5.4}, {"t": 5.9}, {"t": 9.0}]
    st = TH.frame_stats(pos, loads, worst=1)
    assert st["n"] == 10 and st["max"] == 0.25
    assert st["worst"] == [(5.0, 0.25, 2)]
    assert TH.frame_stats([{"t": 1.0}], loads) == {}


def test_the_recorder_asks_for_the_frame_period():
    import record_reads as RR
    assert ("frame_s", "sim/time/framerate_period", False) in RR.POS_REFS


def test_tools_stay_standard_library_only():
    """The owner runs them with /usr/bin/python3: no engine, no venv."""
    import ast
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    if not stdlib:
        pytest.skip("sys.stdlib_module_names needs python 3.10")
    local = {p.stem for p in TOOL.glob("*.py")}
    for path in TOOL.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0:
                names = [n.module]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                if top not in local and top != "__future__":
                    assert top in stdlib, f"{path.name} imports {top}"


def test_fixture_is_trimmed_and_carries_no_home_folder():
    assert (FX / "flight2_trim.jsonl.gz").stat().st_size < 200_000
    with gzip.open(FX / "flight2_trim.jsonl.gz", "rt", encoding="utf-8") as f:
        assert "/Users/" not in f.read()
