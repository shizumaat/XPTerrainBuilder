"""AN UNTAGGED CLOSED WAY IN A USER PATCH IS IGNORED (owner 2026-11-17).

LPPD's user patch carried an untagged closed way (5.54 km2, 1.2 km2 of
it over the sea).  ``include_patches`` seeded it as patch pavement: the
ring took ``PATCH_RING_MARKER``, its interior INTERP_ALT seeds, the sea
seeds were withheld inside it and the seawall admitted it -- the sea dried
and rose up to 57 m behind walls.  Owner: "if there were no tags it was
just completely ignored, I would lean toward that handling".

Twin: a synthetic rectangle over the sea round one tagged ring.  The
rectangle is never inserted, never in ``patches_area``, never seeded;
the sea between the two keeps its seeds.  An auto patch is unaffected.
Headless: patch files in ``tmp_path``, a flat stand-in DEM.
"""
from __future__ import annotations

import sys
from pathlib import Path

from shapely import geometry

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402
from test_patch_pavement_is_land import _Tile  # noqa: E402  (sibling twin)

LAT, LON = 30, 30
TAGGED = [(0.0010, 0.0010), (0.0030, 0.0010), (0.0030, 0.0030), (0.0010, 0.0030)]
BAND = [(0.0002, 0.0002), (0.0040, 0.0002), (0.0040, 0.0040), (0.0002, 0.0040)]
IN_BAND = (0.0036, 0.0036)                       # inside BAND, outside TAGGED


def _patch(path: Path, band_tags=()) -> None:
    rows = ["<?xml version='1.0' encoding='UTF-8'?>", "<osm version='0.6'>"]
    ways, nid = [], -10
    for ring, tags in ((TAGGED, (("cst_alt_abs", "75"),)), (BAND, band_tags)):
        refs = []
        for x, y in ring:
            rows.append(f"  <node id='{nid}' lat='{LAT + y:.10f}' lon='{LON + x:.10f}' />")
            refs.append(nid)
            nid -= 2
        ways.append((refs + refs[:1], tags))
    for k, (refs, tags) in enumerate(ways):
        rows.append(f"  <way id='{-100 - 2 * k}'>")
        rows += [f"    <nd ref='{r}' />" for r in refs]
        rows += [f"    <tag k='{a}' v='{b}' />" for a, b in tags]
        rows.append("  </way>")
    rows.append("</osm>")
    path.write_text("\n".join(rows), encoding="utf-8", newline="")


def _include(tmp_path, monkeypatch, name, band_tags=()):
    pdir = tmp_path / "patches"
    pdir.mkdir()
    _patch(pdir / name, band_tags)
    monkeypatch.setattr(VMAP.FNAMES, "patch_dir", lambda lat, lon: str(pdir))
    said = []
    monkeypatch.setattr(VMAP.UI, "loud_warning", lambda msg, *a, **k: said.append(msg))
    vm = VECT.Vector_Map()
    area, _lst, _graded = VMAP.include_patches(vm, _Tile(LAT, LON))
    return vm, area, said


def _marked(vm) -> int:
    return sum(1 for e in vm.edges_dico if vm.data_edges[e])


def test_untagged_user_ring_is_ignored_and_the_sea_keeps_its_seeds(tmp_path, monkeypatch):
    vm, area, said = _include(tmp_path, monkeypatch, "XXXX.patch.osm")
    marks = [vm.data_edges[e] for e in vm.edges_dico]
    assert marks == [VMAP.PATCH_RING_MARKER] * 4          # the tagged ring only
    assert len(vm.seeds["INTERP_ALT"]) == 1
    assert set(vm.data_nodes.values()) == {75.0}            # the band never meshed
    assert not area.contains(geometry.Point(IN_BAND))
    assert abs(area.area - geometry.Polygon(TAGGED).area) < 1e-12
    sea = geometry.MultiPolygon([geometry.box(0.0, 0.0, 0.005, 0.005)])
    seeds = VMAP.sea_seed_areas(sea, None, patch_pavement_area=area)
    assert seeds.contains(geometry.Point(IN_BAND))          # SEA kept in the band
    (msg,) = said
    assert "XXXX.patch.osm way " in msg and "near 30.00210,30.00210: untagged closed way, " \
        "0.15 km2, ignored." in msg


def test_a_height_tag_keeps_the_ring(tmp_path, monkeypatch):
    vm, area, said = _include(tmp_path, monkeypatch, "XXXX.patch.osm",
                              (("var_alt_rel", "0"),))
    assert _marked(vm) == 8 and not said
    assert area.contains(geometry.Point(IN_BAND))


def test_an_auto_patch_is_unaffected(tmp_path, monkeypatch):
    vm, area, said = _include(tmp_path, monkeypatch, "XXXX_auto.patch.osm")
    assert _marked(vm) == 8 and not said
    assert area.contains(geometry.Point(IN_BAND))
