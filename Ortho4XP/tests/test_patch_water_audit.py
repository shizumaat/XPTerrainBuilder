"""``tools/patch_water_audit.py`` — the EMIT-side shore acceptance
(owner RULINGS 2026-09-09z (3); spec §18).

The trap the tool exists to close: a ring that FOLLOWS the water line is
a HOLE of the banked region, and counting ring polygons naively reports
its area twice — at OTHH 3,218 m² of "bank over water" where the true
region covers 0.0 m².  The twin is that arithmetic, on a synthetic patch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import patch_water_audit as PWA  # noqa: E402

LAT, LON = 25, 51
#: a square bank with a square pond cut out of it, in tile-relative degrees
BANK = [(0.010, 0.010), (0.020, 0.010), (0.020, 0.020), (0.010, 0.020)]
POND = [(0.014, 0.014), (0.016, 0.014), (0.016, 0.016), (0.014, 0.016)]


def _osm(path, rings):
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' generator='twin'>"]
    nid = 0
    ways = []
    for ring in rings:
        ids = []
        for (x, y) in ring:
            nid -= 1
            lines.append(f"  <node id='{nid}' lat='{LAT + y:.9f}' "
                         f"lon='{LON + x:.9f}' />")
            ids.append(nid)
        ways.append(ids)
    wid = -10000
    for k, ids in enumerate(ways):
        wid -= 1
        lines.append(f"  <way id='{wid}'>")
        for v in ids + [ids[0]]:
            lines.append(f"    <nd ref='{v}' />")
        lines.append("    <tag k='o4_feature' v='bank_foot' />")
        lines.append(f"    <tag k='ref' v='bank:{k}' />")
        lines.append("  </way>")
    lines.append("</osm>")
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture()
def patch(tmp_path, monkeypatch):
    from shapely.geometry import Polygon

    class _Tile:
        def __init__(self, *a):
            pass

        def read_from_config(self):
            return None

    monkeypatch.setattr(PWA, "_M_PER_DEG", 111120.0)
    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP
    monkeypatch.setattr(CFG, "Tile", _Tile)
    monkeypatch.setattr(VMAP, "cached_tile_water",
                        lambda tile: (None, Polygon(POND)))
    path = tmp_path / "TWIN_auto.patch.osm"
    _osm(path, [BANK, POND])
    return str(path)


def test_a_ring_on_the_water_line_is_a_hole_not_a_violation(patch):
    out = PWA.patch_water_audit(patch, LAT, LON)
    assert out["bank_rings"] == 2
    assert out["exterior_rings"] == 1 and out["hole_rings"] == 1
    assert out["banked_over_water_m2"] == 0.0
    assert out["banked_region_m2"] > 0.0
    # and the naive read the tool exists to refuse would have counted the
    # pond twice: its area is a real part of the exterior ring's polygon
    assert out["banked_region_m2"] < 0.010 * 0.010 * PWA._M_PER_DEG ** 2


def test_a_bank_standing_in_water_is_reported(patch, tmp_path):
    """The arm that must FAIL loudly: a bank ring drawn straight across
    the pond, with no hole cut."""
    path = tmp_path / "BAD_auto.patch.osm"
    _osm(path, [BANK])
    out = PWA.patch_water_audit(str(path), LAT, LON)
    assert out["hole_rings"] == 0
    assert out["banked_over_water_m2"] > 1000.0
