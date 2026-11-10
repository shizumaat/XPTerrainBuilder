"""Twin of the ``Log.txt`` DSF-load witness (``src/O4_XPlane_Log.py``;
flight manager / World spec 2026-11-10 §2.3, §15).

Fixture: ``tests/fixtures/world/xplane_log_sample.txt``, lines copied
unchanged from X-Plane 12.4.4's ``Log.txt`` on the owner's Mac (session of
2026-11-10 16:41Z: the header, part of the scenery-package block, overlay
and mesh DSF loads).  The CYYR World pack flight's own log was rewritten
when X-Plane next started, so its World-pack lines are not in the fixture;
:data:`WORLD_LINES` rebuilds two of them from spec §2.1 (file, µs, tris
as logged; the clock stamp and the tail after ``tris,`` are not).
"""
from __future__ import annotations

import os

import O4_XPlane_Log as L

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "world", "xplane_log_sample.txt")
WORLD_LINES = [
    "0:11:02.000 I/SCN: DSF load time: 6621037 for file Custom Scenery/"
    "zXPTerrainBuilder World/Earth nav data/+50-070/+53-063.dsf "
    "(2205408 tris, 0 skipped for 0.0 m^2)",
    "0:11:05.000 I/SCN: DSF load time: 312 for file Custom Scenery/"
    "zXPTerrainBuilder World/Earth nav data/+50-070/+52-063.dsf "
    "(0 tris, 0 skipped for 0.0 m^2)",
]


def _sample() -> list[str]:
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read().splitlines()


def test_dsf_lines_parse_to_tile_pack_tris_and_time():
    recs = [r for r in map(L.parse_dsf_load, _sample()) if r]
    assert [(r.pack, r.tile, r.tris) for r in recs] == [
        ("Global Airports", (65, -150), 0),
        ("simHeaven_X-WORLD-Pro_America-05-details", (63, -148), 0),
        ("zOrtho4XP_+64-148", (64, -148), 3624014),
        ("zOrtho4XP_+64-149", (64, -149), 245496)]
    assert recs[2].t_s == 25.87 and recs[2].load_us == 4980227
    assert recs[0].overlay and not recs[2].overlay
    assert recs[2].path.endswith("Earth nav data/+60-150/+64-148.dsf")


def test_world_pack_placeholder_and_real_tile():
    real, placeholder = map(L.parse_dsf_load, WORLD_LINES)
    assert real.pack == "zXPTerrainBuilder World" and real.tile == (53, -63)
    assert real.tris == 2205408 and not real.overlay
    assert real.t_s == 662.0
    assert placeholder.tile == (52, -63) and placeholder.overlay
    loads = L.pack_loads([real, placeholder, *map(L.parse_dsf_load,
                                                  _sample()[-2:])],
                         "zXPTerrainBuilder World")
    assert set(loads) == {(53, -63), (52, -63)}


def test_other_lines_are_not_loads():
    for line in ("0:00:01.509 I/INS: Global scenery version: 122013",
                 "3889 Custom Scenery/zOrtho4XP_+64-148/", "",
                 "0:00:25.870 I/SCN: DSF load time: 12 for file "
                 "Custom Scenery/x/Earth nav data/+60-150/apt.dat (0 tris"):
        assert L.parse_dsf_load(line) is None


def test_tail_reads_only_what_was_appended(tmp_path):
    log = tmp_path / L.LOG_NAME
    text = "\n".join(_sample()) + "\n"
    log.write_text(text[:-40], encoding="utf-8", newline="\n")  # half a line
    tail = L.LogTail(str(log))
    first = tail.read()
    assert len(first) == 3
    assert tail.started == "Tue Nov 10 08:41:06 2026"
    assert tail.packages == [
        "Global Scenery/Global Airports",
        "Custom Scenery/simHeaven_X-WORLD-Pro_America-05-details",
        "Custom Scenery/simHeaven_X-WORLD-Pro_America-09-scenery",
        "Custom Scenery/zOrtho4XP_+64-148",
        "Resources/default scenery/1000 world terrain"]
    log.write_text(text + "\n".join(WORLD_LINES) + "\n", encoding="utf-8",
                   newline="\n")
    more = tail.read()
    assert [r.tile for r in more] == [(64, -149), (53, -63), (52, -63)]
    assert tail.read() == [] and tail.restarts == 0


def test_tail_starts_over_when_xplane_restarts(tmp_path):
    log = tmp_path / L.LOG_NAME
    text = "\n".join(_sample()) + "\n"
    log.write_text(text, encoding="utf-8", newline="\n")
    tail = L.LogTail(str(log))
    assert len(tail.read()) == 4
    # a new session: shorter file, new header
    log.write_text("Log.txt for X-Plane 12.5.0\nX-Plane Started on Wed Nov 11 "
                   "09:00:00 2026\n" + WORLD_LINES[1] + "\n", encoding="utf-8",
                   newline="\n")
    again = tail.read()
    assert [r.tile for r in again] == [(52, -63)] and tail.restarts == 1
    assert tail.started == "Wed Nov 11 09:00:00 2026" and tail.packages == []


def test_missing_log_reads_nothing(tmp_path):
    assert L.LogTail(str(tmp_path / "absent.txt")).read() == []
    assert L.log_path("/X") == os.path.join("/X", "Log.txt")
