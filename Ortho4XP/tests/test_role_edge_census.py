"""ROLE EDGE CENSUS — twins for ``tools/role_edge_census.py`` (promoted
2026-09-12 from the ``v2lemd320t`` scout's `census_gs.py` on its second
use, RULINGS ``7e90032``).

The tool answers the question owner RULINGS 2026-09-12c is adjudicated
on: the METRES one groundside shape's boundary shares with airside
pavement.  A census cannot — a lot welded flat along 828 m of apron
breaks no grade law and prices zero rows — and `role_overlap_read.py`
cannot either, since two faces that merely share a boundary overlap by
0 m².

These twins pin what makes it trustworthy:
  * the shared edge IS the node-identity join (the planar weld's own
    output), never a proximity match;
  * the airside-pavement set excludes `building` (§27 (1));
  * metres shared with a `service_road` / `service_junction` are
    reported APART — that is the owner's exemption channel, and folding
    it into the airside metres would flip the very lots 12c exempts;
  * the sliver split (area / perimeter) and the LOT-class population;
  * it prices nothing and counts no defects;
  * this index row exists.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import role_edge_census as REC                            # noqa: E402

ANCHOR = (30.12, 31.40)


def _patch(tmp_path, name, rings):
    """One emitted patch from ``(tags, ring_in_metres)`` pairs.  Nodes at
    the SAME coordinate are the SAME node — what the planar weld emits,
    and what the census joins on."""
    out = ["<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"]
    seen: dict[tuple[float, float], int] = {}
    nid = [-1]
    body = []
    for tags, pts in rings:
        nids = []
        for (x, y) in pts:
            key = (round(x, 6), round(y, 6))
            if key not in seen:
                lat = ANCHOR[0] + y / 111320.0
                lon = ANCHOR[1] + x / (111320.0 * math.cos(math.radians(ANCHOR[0])))
                out.append(f"  <node id='{nid[0]}' lat='{lat:.11f}' "
                           f"lon='{lon:.11f}'>\n"
                           f"    <tag k='alt_abs' v='100.00' />\n  </node>\n")
                seen[key] = nid[0]
                nid[0] -= 1
            nids.append(seen[key])
        nids.append(nids[0])
        body.append((nids, tags))
    wid = -900
    for nids, tags in body:
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
    return p


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _by_shape(rows):
    return {r["shapeID"]: r for r in rows}


def test_the_shared_edge_is_the_node_identity_join(tmp_path):
    """An apron and a lot sharing one 100 m welded edge: 100 m, and the
    lot's own area and perimeter alongside it."""
    p = _patch(tmp_path, "a.osm", [
        ({"role": "apron", "ref": "pav171", "shapeID": "75"},
         _rect(0, 0, 100, 100)),
        ({"role": "groundside_pavement", "class": "parking_lot",
          "ref": "pav137", "shapeID": "81"}, _rect(0, 100, 100, 160)),
    ])
    rows = _by_shape(REC.census(p))
    assert set(rows) == {"81"}                     # the apron is not groundside
    r = rows["81"]
    assert r["airside_pav_m"] == pytest.approx(100.0, rel=0.01)
    assert r["area_m2"] == pytest.approx(6_000.0, rel=0.01)
    assert r["perim_m"] == pytest.approx(320.0, rel=0.01)
    assert r["radius_m"] == pytest.approx(18.75, rel=0.02)
    assert r["service_m"] == 0.0 and r["building_m"] == 0.0
    # a lot that merely lies NEAR the apron, sharing no node, shares nothing
    p2 = _patch(tmp_path, "b.osm", [
        ({"role": "apron", "ref": "pav171", "shapeID": "75"},
         _rect(0, 0, 100, 100)),
        ({"role": "groundside_pavement", "class": "parking_lot",
          "ref": "pav137", "shapeID": "81"}, _rect(0, 100.5, 100, 160)),
    ])
    assert _by_shape(REC.census(p2))["81"]["airside_pav_m"] == 0.0


def test_service_road_metres_are_reported_apart_and_buildings_are_not_pavement(tmp_path):
    """§27 (1): a lot reaching airside ONLY through a service road has
    0 airside metres — the owner's exemption channel — and a `building`
    edge is not airside pavement however the law sides the role."""
    p = _patch(tmp_path, "c.osm", [
        ({"role": "apron", "ref": "pav171", "shapeID": "75"},
         _rect(0, 0, 100, 100)),
        ({"role": "service_road", "ref": "route3", "shapeID": "90"},
         _rect(0, 100, 100, 110)),
        ({"role": "building", "ref": "b1", "shapeID": "99"},
         _rect(0, 170, 100, 200)),
        ({"role": "groundside_pavement", "class": "parking_lot",
          "ref": "pav137", "shapeID": "81"}, _rect(0, 110, 100, 170)),
    ])
    rows = _by_shape(REC.census(p))
    assert rows["81"]["airside_pav_m"] == 0.0
    assert rows["81"]["service_m"] == pytest.approx(100.0, rel=0.01)
    assert rows["81"]["building_m"] == pytest.approx(100.0, rel=0.01)
    assert "building" not in REC.AIRSIDE_PAVEMENT
    # the road itself is groundside too, and ITS airside metres are real
    assert rows["90"]["airside_pav_m"] == pytest.approx(100.0, rel=0.01)


def test_the_sliver_split_and_the_lot_class_population(tmp_path, capsys):
    """A 200 x 0.8 m weld sliver shares 200 m and is an emit artefact
    (radius 0.4 m); the CLI reports it apart from the substantive shapes
    and names the LOT-class population §27 acts on."""
    p = _patch(tmp_path, "d.osm", [
        ({"role": "apron", "ref": "pav171", "shapeID": "75"},
         _rect(0, 0, 200, 100)),
        ({"role": "groundside_pavement", "ref": "sliver", "shapeID": "300"},
         _rect(0, 100, 200, 100.8)),
        ({"role": "groundside_pavement", "class": "parking_lot",
          "ref": "pav3", "shapeID": "271"}, _rect(0, -60, 200, 0)),
    ])
    rows = _by_shape(REC.census(p))
    assert rows["300"]["radius_m"] < 1.0 and rows["271"]["radius_m"] > 1.0
    assert REC.main([str(p), "--detail"]) == 0
    txt = capsys.readouterr().out
    assert "SUBSTANTIVE (area/perimeter >= 1 m): 1 shapes" in txt
    assert "slivers excluded: 1" in txt
    assert "LOT-class (§27's population): 1 shapes" in txt
    # it prices no law: no grade, no cap, no defect count anywhere
    assert "grade" not in txt and "DEFECT" not in txt
    assert set(rows["271"]) == {"shapeID", "ref", "role", "cls", "area_m2",
                                "perim_m", "airside_pav_m", "service_m",
                                "building_m", "radius_m", "neighbours"}


def test_the_tool_is_in_the_index():
    """RULINGS ``7e90032``: a tool absent from ``tools/INDEX.md`` is
    treated as absent, and every new tool lands with its index entry in
    the same commit."""
    index = _ROOT.parent / "tools" / "INDEX.md"
    if not index.exists():                      # a lane worktree mirror
        pytest.skip("no repo-root tools/INDEX.md in this checkout")
    assert "role_edge_census.py" in index.read_text()
