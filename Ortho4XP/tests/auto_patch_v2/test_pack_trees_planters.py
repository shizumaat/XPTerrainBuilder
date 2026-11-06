"""Twins of the #1920 follow-up (owner 2026-11-06: "use xp12 resources
where possible if they meet the height requirements"): a pack's own low
grass, reeds and shrubs map to X-Plane 12 GROUND planters no taller than
their class (``pack_trees.local_forest_target``,
``pack_trees_map.PLANTERS`` / ``LOW_CLASS``), keep the pack's plant count
(``pack_trees_density``), and only grass stands on the strips
(``pack_forests.clear_strips``).

Synthetic ``tmp_path`` files, plus one twin that re-reads the INSTALLED
X-Plane 12 library when there is one (skipped otherwise; CI-safe).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from auto_patch_v2.airport import pack_trees as PT
from auto_patch_v2.airport import pack_trees_density as PD
from auto_patch_v2.airport.pack_trees_map import GRASS_M, LOW_CLASS, PLANTERS
from conftest import xplane_root

GRASS = "lib/vegetation/planters/ground/grass_green_1.for"
SHRUB = "lib/vegetation/planters/ground/shrubs_red_1.for"


def _for(path: Path, rows, spacing="3 3") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("A\n800\nFOREST\nTEXTURE t.png\nSCALE_X 2048\n"
                    f"SCALE_Y 2048\nSPACING {spacing}\n" + "".join(
                        f"TREE 0 0 {w} {h} 0 {f} {lo} {hi} 2 1\n"
                        for w, h, f, lo, hi in rows), encoding="utf-8")
    return str(path)


# ── THE MAP ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,rows,want", [
    ("grass.for", [(450, 128, 70, 0.6, 1.6)], GRASS),            # named grass
    ("reed_tall.for", [(316, 231, 5, 1.9, 3.2)], GRASS),         # named reeds
    ("cover.for", [(300, 60, 100, 0.1, 0.9)], GRASS),            # under 1.5 m
    ("shrubs.for", [(600, 600, 100, 3, 3.8)], SHRUB),              # named shrubs
    ("oleander.for", [(600, 600, 100, 1.8, 2.0)], SHRUB),        # unnamed, low
    ("palmtree_short.for", [(600, 600, 100, 3.5, 3.5)], ""),     # a low TREE
    ("young_fir.for", [(600, 600, 100, 2, 3)], ""),              # species word
    ("hedge.for", [(200, 618, 100, 2, 3)], ""),                  # conifer shape
    ("reed.for", [(400, 400, 100, 6, 6)], ""),                   # giant cane
])
def test_low_vegetation_takes_ground_cover_of_its_class(tmp_path, name, rows,
                                                         want):
    assert PT.local_forest_target(_for(tmp_path / name, rows)) == want


def test_a_target_never_stands_taller_than_its_class():
    for cls, (cap, order) in LOW_CLASS.items():
        assert order, cls
        for p in order:
            assert p.startswith("lib/vegetation/planters/ground/"), \
                "raised planters (planters/high) never stand on open ground"
            assert PLANTERS[p][0] <= cap, (cls, p)
    assert LOW_CLASS["grass"][0] <= GRASS_M
    # the shrub class is under the lowest source that is not grass
    assert LOW_CLASS["shrub"][0] <= PT.GROUND_COVER_M


def test_a_class_with_no_planter_low_enough_keeps_its_own_file(
        tmp_path, monkeypatch):
    monkeypatch.setitem(LOW_CLASS, "shrub", (0.5, (SHRUB,)))
    p = _for(tmp_path / "shrubs.for", [(600, 600, 100, 2, 3)])
    assert PT.local_forest_target(p) == ""


# ── THE INSTALLED LIBRARY (pinned table == what X-Plane ships) ───────────

_LIB = os.path.join(xplane_root(), "Resources", "default scenery",
                    "1200 forests")


def _exports() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    with open(os.path.join(_LIB, "library.txt"), encoding="utf-8",
              errors="replace") as fh:
        for raw in fh:
            tok = raw.split()
            if tok[:1] == ["EXPORT"] and len(tok) >= 3:
                out.setdefault(tok[1], []).append(tok[2])
            elif tok[:1] == ["EXPORT_SEASON"] and len(tok) >= 4:
                out.setdefault(tok[2], []).append(tok[3])
    return out


@pytest.mark.skipif(not os.path.isfile(os.path.join(_LIB, "library.txt")),
                    reason="no X-Plane 12 install: the pinned table stands")
@pytest.mark.parametrize("vpath", sorted(PLANTERS))
def test_the_pinned_planters_are_what_the_install_ships(vpath):
    height, spacing, plants = PLANTERS[vpath]
    files = _exports().get(vpath)
    assert files, f"{vpath} is not exported by this install"
    for rel in files:                                   # every season
        text = Path(_LIB, rel).read_text(encoding="utf-8", errors="replace")
        assert "SHADER_3D" in text
        assert not re.search(r"^\s*OBJECT|\.obj\b", text, re.M | re.I), \
            "plant meshes only: no object, pot or box"
        rows = [ln.split() for ln in text.splitlines() if ln.startswith("TREE")]
        assert max(float(r[8]) for r in rows) <= height + 1e-6, rel
        sp = [ln.split() for ln in text.splitlines()
              if ln.startswith("SPACING")][0]
        assert (float(sp[1]), float(sp[2])) == pytest.approx(spacing), rel
        names = {re.sub(r"\d*(_\d+[a-z]?)?$", "", r[-1]) for r in rows}
        assert names <= set(plants), (rel, names - set(plants))
    sumrows = Path(_LIB, files[0]).read_text(errors="replace").splitlines()
    assert max(float(ln.split()[8]) for ln in sumrows
               if ln.startswith("TREE")) == pytest.approx(height)


# ── THE PLANT COUNT ──────────────────────────────────────────────────────

def test_a_planter_keeps_the_packs_plant_count(tmp_path):
    _for(tmp_path / "Veg" / "grass.for", [(450, 128, 70, 0.6, 1.6)], "3 3")
    dump = ("POLYGON_DEF Veg/grass.for\nPOLYGON_DEF lib/g8/broad.for\n"
            "BEGIN_POLYGON 0 255 2\nEND_POLYGON\n"
            "BEGIN_POLYGON 0 600 2\nEND_POLYGON\n"        # a point forest
            "BEGIN_POLYGON 1 255 2\nEND_POLYGON\n")
    text, n = PD.keep_plant_count(dump, {"Veg/grass.for": GRASS}, str(tmp_path))
    # 0.5 x 0.5 planter cell over a 3 x 3 pack cell: 255 / 36 -> 7
    assert n == 1 and "BEGIN_POLYGON 0 7 2\n" in text
    assert "BEGIN_POLYGON 0 600 2\n" in text and "BEGIN_POLYGON 1 255 2\n" in text


def test_a_sparse_pack_never_falls_below_one(tmp_path):
    _for(tmp_path / "reed.for", [(400, 400, 100, 2, 2.2)], "20 20")
    text, n = PD.keep_plant_count("POLYGON_DEF reed.for\nBEGIN_POLYGON 0 10 2\n",
                                  {"reed.for": GRASS}, str(tmp_path))
    assert n == 1 and "BEGIN_POLYGON 0 1 2" in text
