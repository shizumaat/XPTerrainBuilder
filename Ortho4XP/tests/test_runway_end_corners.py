"""Twin for ``tools/runway_end_ground.py --corners ICAO`` — the §35
runway-end CORNER read of a shipped patch (RULINGS 2026-09-13q item 1).

Promoted out of lane ``v2rwycorner``'s scratchpad on its second use (tool
discipline, RULINGS ``7e90032``): the scratch version carried its OWN
XML parser, which is the census-wrapper defect in miniature.  The tool
reads the patch through ``check_grade._parse_osm``, the one reader.

What is twinned: the axis fit and the clamped nearest point agree with
the ENGINE's own ``principal_axis`` / end-edge derivation, and the read
prices a hand-built corner against ``end_skirt.max_down_grade × d + q``.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tools"), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runway_end_ground as REG                                   # noqa: E402
from auto_patch_v2.constraints.geometry import principal_axis     # noqa: E402

#: a metre of latitude / longitude at the fixture's latitude
_R = 6378137.0
LAT0, LON0 = 35.2000000, -80.9500000
DLAT = 180.0 / math.pi / _R
DLON = DLAT / math.cos(math.radians(LAT0))


def _ll(x, y):
    """Metres east / north of the origin as lat/lon."""
    return LAT0 + y * DLAT, LON0 + x * DLON


def test_the_axis_fit_is_the_engines(recwarn):
    """The tool must not fit the runway differently from the law that
    priced it — a second axis is a second source of truth."""
    pts = [(0.0, -20.0), (1000.0, -20.0), (1000.0, 20.0), (0.0, 20.0),
           (500.0, 21.0)]
    a, b, unit, length, width = REG._principal_axis(pts)
    ea, eb, ewidth = principal_axis(pts)
    assert a == pytest.approx(ea, abs=1e-6)
    assert b == pytest.approx(eb, abs=1e-6)
    assert width == pytest.approx(ewidth, abs=1e-6)
    assert length == pytest.approx(math.dist(ea, eb), abs=1e-6)
    assert math.hypot(*unit) == pytest.approx(1.0)


def test_the_nearest_point_clamps_t_to_the_segment():
    """§35 (1): a point BESIDE the end edge takes its nearest END, not a
    projection off the edge's line."""
    x, y, wa, wb = REG._nearest_on_segment(-3.0, 3.0, 0.0, 0.0, 0.0, 40.0)
    assert (x, y) == pytest.approx((0.0, 3.0))
    assert (wa, wb) == pytest.approx((1.0 - 3.0 / 40.0, 3.0 / 40.0))
    # beyond the far end: clamped to it, all the weight on that endpoint
    x, y, wa, wb = REG._nearest_on_segment(-3.0, 43.0, 0.0, 0.0, 0.0, 40.0)
    assert (x, y) == pytest.approx((0.0, 40.0))
    assert (wa, wb) == pytest.approx((0.0, 1.0))


def _patch(tmp_path, corner_z):
    """One 1,200 × 40 m runway at 200 m, and a graded strip whose ring
    carries ONE vertex 3 m beyond the south end and 3 m outside the
    width — §35's corner, at 3√2 m from the corner itself."""
    rw = [(0.0, -20.0), (1200.0, -20.0), (1200.0, 20.0), (0.0, 20.0)]
    strip = [(-3.0, 23.0),          # THE CORNER VERTEX
             (-60.0, 60.0), (1260.0, 60.0), (1260.0, -60.0), (-60.0, -60.0)]
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6">']
    nid = -1
    ids = {}
    for tag, ring, zs in (("runway", rw, [200.0] * 4),
                          ("graded_strip", strip,
                           [corner_z] + [200.0] * (len(strip) - 1))):
        ids[tag] = []
        for (x, y), z in zip(ring, zs):
            la, lo = _ll(x, y)
            out.append(f"  <node id='{nid}' lat='{la:.11f}' lon='{lo:.11f}'>"
                       f"<tag k='alt_abs' v='{z:.3f}'/></node>")
            ids[tag].append(nid)
            nid -= 1
    wid = -1000
    for tag in ("runway", "graded_strip"):
        out.append(f"  <way id='{wid}'>")
        for n in ids[tag] + [ids[tag][0]]:
            out.append(f"    <nd ref='{n}'/>")
        out.append(f"    <tag k='role' v='{tag}'/>")
        out.append("    <tag k='ref' v='18/36'/>")
        out.append('  </way>')
        wid -= 1
    out.append('</osm>')
    p = tmp_path / "fixture.patch.osm"
    p.write_text("\n".join(out))
    return p


def test_a_corner_on_the_end_edge_level_is_within_its_bound(tmp_path):
    p = _patch(tmp_path, 200.0)
    out = REG.corners(p, "KCLT")
    assert out["ruleset"] == "faa"
    assert out["total_over_bound"] == 0
    hit = [r for r in out["corners"] if r["population"]]
    assert hit, "the fixture's corner vertex must be in the quadrant"
    # the 3 m-diagonal vertex is the nearest of the quadrant's population
    near = min(r["worst"]["d_m"] for r in hit)
    assert near == pytest.approx(3.0 * math.sqrt(2.0), abs=0.3)


def test_a_dropped_corner_reports_its_excess(tmp_path):
    """The KCLT 18C/36C class in miniature: the corner sits 5 m off the
    end edge 4.2 m away, and the read prices it against cap·d + q."""
    p = _patch(tmp_path, 195.0)
    out = REG.corners(p, "KCLT")
    assert out["total_over_bound"] == 1
    w = next(r["worst"] for r in out["corners"] if r["over_bound"])
    assert w["step_m"] == pytest.approx(5.0, abs=0.01)
    assert w["bound_m"] == pytest.approx(
        out["max_down_grade"] * w["d_m"] + out["instrument_allowance_m"],
        abs=1e-3)
    assert w["excess_m"] == pytest.approx(w["step_m"] - w["bound_m"], abs=1e-3)
