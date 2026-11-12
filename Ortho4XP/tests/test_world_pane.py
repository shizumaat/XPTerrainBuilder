"""Twins of the tile pane's World-pack row and the "ours" predicate (owner
2026-11-12T20:23Z, lane ltilepane: a tile fully built in the World pack
read "not built", and the World pack was listed as "Other scenery").

* ``tests/fixtures/world_pane_cases.json`` -- shared with
  ``Tests/SceneryKitTests/WorldPaneTests.swift``: which Custom Scenery
  entries are ours (``O4_Custom_Scenery._is_our_pack`` /
  ``O4WorldPack.isOurs``) and the pane's status words
  (``O4_World_State_Text.pane_status`` / ``O4WorldStateText.paneStatus``);
* the Custom Scenery survey never lists our packs as other scenery;
* ``world_tile_remove``: refused without ``confirm`` and for a tile the
  World pack does not hold; its package first, then the placeholder; the
  Convert work folder's ``originals/`` untouched.

All on ``tmp_path``; X-Plane reads as not running."""
from __future__ import annotations

import json
import os
from pathlib import Path

import O4_Custom_Scenery as CS
import O4_DSF_Binary as DSFB
import O4_World_Pack as WP
import O4_World_State_Text as TEXT
import pytest
from o4_engine import library as LIB
from o4_engine import package_first as FIRST
from o4_engine import world_commands as WORLD
from o4_engine import world_tile_remove as REMOVE

CASES = json.loads((Path(__file__).parent / "fixtures" / "world_pane_cases.json")
                   .read_text(encoding="utf-8"))
HERE_AGENT = "XPTerrainBuilder 1.0.495 (engine 1.50.1903) [world full]"


@pytest.mark.parametrize("case", CASES["packs"], ids=lambda c: c["name"] or "empty")
def test_our_packs_are_never_other_scenery(case):
    assert CS._is_our_pack(case["name"]) is case["ours"]


@pytest.mark.parametrize("case", CASES["pane"],
                         ids=lambda c: (c["world"] or {}).get("state", "none"))
def test_the_pane_says_what_the_world_pack_holds(case):
    assert TEXT.pane_status(case["world"]) == case["status"]
    assert TEXT.pane_detail(case["world"]) == case["detail"]
    assert TEXT.built_in_world(case["world"]) is case["built"]


def _dsf(root: Path, lat: int, lon: int, agent: str = HERE_AGENT) -> Path:
    path = root / WP.dsf_relpath(lat, lon)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(DSFB.placeholder_bytes(lat, lon, agent) + b"\0" * 8192)
    return path


@pytest.fixture
def scenery(tmp_path, monkeypatch):
    """Custom Scenery with the World pack (one full tile, its textures
    hard links of a folder kept in ``originals/``, one placeholder), the
    overlay pack and one third-party ortho pack on the same tile."""
    scenery = tmp_path / "X-Plane 12" / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    _dsf(pack, 30, 31)
    original = tmp_path / "X-Plane 12" / "work" / "originals" / "zOrtho4XP_+30+031"
    (original / "textures").mkdir(parents=True)
    kept = original / "textures" / "1_2_BI16.dds"
    kept.write_bytes(b"DDS ")
    textures = pack / "textures" / WP.tile_name(30, 31)
    textures.mkdir(parents=True)
    os.link(kept, textures / kept.name)
    WP.write_placeholder(str(pack), 30, 32)
    _dsf(scenery / "yXPTerrainBuilder Overlays", 30, 31)
    _dsf(scenery / "zzz_Other Ortho", 30, 31, agent="another tool")
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: False)
    return scenery, kept


def test_the_survey_lists_only_other_tools_packs(scenery):
    root, _kept = scenery
    names = [p.name for p in CS.packs_covering(CS.scan_packs(str(root)), 30, 31)]
    assert names == ["zzz_Other Ortho"]


def test_remove_is_confirmed_and_only_for_a_real_tile(scenery):
    root, _kept = scenery
    with pytest.raises(ValueError, match="never touched"):
        REMOVE._check({"lat": 30, "lon": 31, "scenery_dir": str(root)})
    with pytest.raises(ValueError, match="not built in the World pack"):
        REMOVE._check({"lat": 30, "lon": 32, "scenery_dir": str(root),
                      "confirm": True})
    assert "world_tile_remove" in LIB.COMMANDS


def test_remove_packages_first_then_places_the_placeholder(scenery, monkeypatch):
    root, kept = scenery
    pack = root / WP.PACK_NAME
    order = []

    def package(self, lat, lon, custom_build_dir="", built=False):
        order.append(("package", WP.is_placeholder(str(pack / WP.dsf_relpath(lat, lon)))))
        return {"tile": "+30+031", "action": "packaged", "path": "/p/+30+031.xptb",
                "bytes": 1, "why": ""}
    monkeypatch.setattr(FIRST.Pass, "tile", package)
    done = REMOVE.world_tile_remove(30, 31, scenery_dir=str(root), confirm=True)
    assert order == [("package", False)]          # packaged while still built
    assert WP.world_tiles(str(pack))[(30, 31)] == "placeholder"
    assert done["folders_removed"] is True
    assert kept.read_bytes() == b"DDS "            # originals/ untouched
    assert TEXT.removed_note(done) == TEXT.REMOVED.format(
        tile="+30+031", package="/p/+30+031.xptb")
