"""Twin of ``tools/road_necks.py`` (#1918 R4): a road vertex facing a
chord of its own ring with no vertex opposite is a neck row; the arm's
station at the foot re-reads it."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "src")]

import road_necks as rn  # noqa: E402

LAT0, LON0 = 10.0, 20.0


def _ll(x, y):
    return LAT0 + y / 111120.0, LON0 + x / (111120.0 * math.cos(math.radians(LAT0)))


def _patch(tmp: Path, name: str, pts, ref="small_roads:-2") -> Path:
    """One closed ``service_road`` ring of ``(x, y, z)`` points."""
    nodes = "".join(
        "<node id='-%d' lat='%.11f' lon='%.11f'><tag k='alt_abs' v='%.3f'/></node>\n"
        % (i + 1, *_ll(x, y), z) for i, (x, y, z) in enumerate(pts))
    nds = "".join("<nd ref='-%d'/>" % (i + 1) for i in [*range(len(pts)), 0])
    way = ("<way id='-1'>%s<tag k='role' v='service_road'/><tag k='ref' v='%s'/></way>"
           % (nds, ref))
    p = tmp / name
    p.write_text("<?xml version='1.0'?>\n<osm version='0.6'>\n%s%s\n</osm>\n" % (nodes, way))
    return p


#: a 30 m road whose north kerb carries a pad tip 1.3 m over its south chord
ROAD = [(0.0, 0.0, 70.0), (30.0, 0.0, 70.0), (30.0, 7.0, 71.0), (16.0, 7.0, 71.0),
        (15.0, 1.3, 71.0), (14.0, 7.0, 71.0), (0.0, 7.0, 71.0)]


def test_a_station_at_the_foot_rereads_the_neck(tmp_path):
    ctl = _patch(tmp_path, "ctl.osm", ROAD)
    arm = _patch(tmp_path, "arm.osm", [ROAD[0], (15.0, 0.0, 70.95), *ROAD[1:]])
    n0, w0, origin = rn.load(ctl)
    rows = rn.neck_rows(n0, w0)
    tip = [r for r in rows if abs(r["dz"]) > 0.5]
    assert len(tip) == 1 and abs(tip[0]["dz"] - 1.0) < 1e-3 and abs(tip[0]["d"] - 1.3) < 1e-3
    n1, w1, _o = rn.load(arm, origin)
    read = rn.reread(rows, n1, w1)
    s = rn.summary(read, {"small_roads:-2"})
    assert s["pad_roads"]["control>0.5"] == 1 and s["pad_roads"]["arm>0.5"] == 0
    assert s["other_roads"]["rows"] == 0
    cls = rn.classes(read, w0, {"small_roads:-2"})
    assert sum(c[3] for c in cls.values()) == 1 and all(k.startswith("v free") for k in cls)


def test_an_unchanged_arm_reads_the_same_neck(tmp_path):
    ctl = _patch(tmp_path, "ctl.osm", ROAD)
    n0, w0, _o = rn.load(ctl)
    read = rn.reread(rn.neck_rows(n0, w0), n0, w0)
    s = rn.summary(read, set())
    assert s["other_roads"]["control>0.5"] == s["other_roads"]["arm>0.5"] == 1
    assert s["other_roads"]["changed_0.05"] == 0 and s["pad_roads"]["rows"] == 0
