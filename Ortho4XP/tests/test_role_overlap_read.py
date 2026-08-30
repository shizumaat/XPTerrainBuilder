"""ROLE OVERLAP READ — twins for ``tools/role_overlap_read.py``
(promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its
second use, RULINGS ``7e90032``).

The tool answers the question a ruling of the form "the spine must stop
at groundside pavement" is adjudicated on: the SQUARE METRES one emitted
role/ref class stands on another's footprint.  A census cannot — a face
lying flat on a lot breaks no grade law and prices zero rows.

These twins pin what makes it trustworthy:
  * the area it reports is the real intersection area, in the metre
    frame the SIDECAR declares;
  * the ROLE:REF selector is exact — a way of the right role and the
    wrong ref is not in the population;
  * a stack under the floor is not a stack;
  * it prices nothing and counts no defects — the report carries areas
    and populations only;
  * a patch with no sidecar is REFUSED (no anchor, no metre frame);
  * this index row exists.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import role_overlap_read as ROR                           # noqa: E402

ANCHOR = (30.12, 31.40)


def _ll(x, y):
    lat = ANCHOR[0] + y / 111320.0
    lon = ANCHOR[1] + x / (111320.0 * math.cos(math.radians(ANCHOR[0])))
    return lat, lon


def _patch(tmp_path, name, rings, *, sidecar=True):
    """One emitted patch from ``(tags, ring_in_metres)`` pairs."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    nid = [-1]
    ways = []
    for tags, pts in rings:
        nids = []
        for (x, y) in pts:
            lat, lon = _ll(x, y)
            out.append(f"  <node id='{nid[0]}' lat='{lat:.11f}' "
                       f"lon='{lon:.11f}'>\n"
                       f"    <tag k='alt_abs' v='100.00' />\n  </node>\n")
            nids.append(nid[0])
            nid[0] -= 1
        nids.append(nids[0])
        ways.append((nids, tags))
    wid = -900
    for nids, tags in ways:
        out.append(f"  <way id='{wid}'>\n")
        for n in nids:
            out.append(f"    <nd ref='{n}' />\n")
        for k, v in sorted(tags.items()):
            out.append(f"    <tag k='{k}' v='{v}' />\n")
        out.append("  </way>\n")
        wid -= 1
    out.append("</osm>\n")
    p = tmp_path / name
    p.write_text("".join(out))
    if sidecar:
        (tmp_path / (name + ".axes.json")).write_text(json.dumps(
            {"anchor": list(ANCHOR), "ruleset": "icao"}))
    return p


def _square(half, cx=0.0, cy=0.0):
    return [(cx - half, cy - half), (cx + half, cy - half),
            (cx + half, cy + half), (cx - half, cy + half)]


_STRIP = ({"role": "graded_strip", "ref": "gap_fill_spine",
           "shapeID": "3190"}, _square(50.0))          # 100 x 100 m
_LOT = ({"role": "groundside_pavement", "ref": "groundside",
         "shapeID": "2813"}, _square(20.0))            # 40 x 40 m, inside


def test_the_area_reported_is_the_real_overlap(tmp_path):
    """HECA 3190-over-2813 in miniature: the lot stands wholly inside
    the strip, so the strip covers ALL of it — 1,600 m², 16 % of its
    own 10,000 m²."""
    p = _patch(tmp_path, "a.osm", [_STRIP, _LOT])
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert r["over_ways"] == 1 and r["on_ways"] == 1
    assert r["stacked"] == 1
    assert 1590.0 < r["area_m2"] < 1610.0
    row = r["rows"][0]
    assert row["shapeID"] == "3190"
    assert 9950.0 < row["own_area_m2"] < 10050.0
    assert 0.155 < row["over_frac"] < 0.165
    assert row["on"][0]["shapeID"] == "2813"


def test_the_ref_selector_is_exact(tmp_path):
    """A graded_strip of the WRONG ref (an adjacent_ground band) is not
    the population the ruling is about, whatever it covers."""
    band = ({"role": "graded_strip", "ref": "adjacent_ground",
             "shapeID": "9001"}, _square(50.0))
    p = _patch(tmp_path, "b.osm", [band, _LOT])
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert r["over_ways"] == 0
    assert r["stacked"] == 0 and r["area_m2"] == 0.0
    # ... and the same patch read for the band's own ref DOES see it.
    r2 = ROR.read(p, over="graded_strip:adjacent_ground",
                  on="groundside_pavement")
    assert r2["stacked"] == 1


def test_a_stack_under_the_floor_is_not_a_stack(tmp_path):
    """The floor is the emit rounding, not a law threshold: a 9 m²
    corner clip is not a face standing on a lot."""
    lot = ({"role": "groundside_pavement", "ref": "groundside",
            "shapeID": "2814"}, _square(2.0, cx=49.0, cy=49.0))
    p = _patch(tmp_path, "c.osm", [_STRIP, lot])
    assert ROR.read(p, over="graded_strip:gap_fill_spine",
                    on="groundside_pavement")["stacked"] == 1
    assert ROR.read(p, over="graded_strip:gap_fill_spine",
                    on="groundside_pavement",
                    min_area_m2=10.0)["stacked"] == 0


def test_it_prices_no_law(tmp_path):
    """MEASUREMENT ONLY: the report carries populations and areas — no
    row count, no violation, no grade.  Defect counts come from
    ``harness/census.py`` and nowhere else."""
    p = _patch(tmp_path, "d.osm", [_STRIP, _LOT])
    r = ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert set(r) == {"patch", "anchor", "over", "on", "min_area_m2",
                      "over_ways", "on_ways", "stacked", "area_m2", "rows"}
    for k in ("rows", "violations", "families", "grade"):
        assert k not in set(r) - {"rows"}


def test_a_patch_with_no_sidecar_is_refused(tmp_path):
    p = _patch(tmp_path, "e.osm", [_STRIP, _LOT], sidecar=False)
    with pytest.raises(SystemExit) as ei:
        ROR.read(p, over="graded_strip:gap_fill_spine",
                 on="groundside_pavement")
    assert "sidecar" in str(ei.value)


def test_the_tool_is_in_the_index():
    """RULINGS ``7e90032``: a tool absent from ``tools/INDEX.md`` is
    treated as absent, and every new tool lands with its index entry in
    the same commit."""
    index = _ROOT.parent / "tools" / "INDEX.md"
    if not index.exists():                      # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    assert "role_overlap_read.py" in index.read_text()
