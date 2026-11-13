"""Twins for the automatic X-Plane overlay of every full tile (#2021,
RULINGS 2026-11-12e): ``O4_Overlay_Pack``, ``O4_Overlay_Utils``'s
``auto_overlay`` / ``background_overlay`` / ``overlay_decision``, the
session's ``with_auto_overlays`` and the adoption hook.

Offline, on a synthetic X-Plane folder in ``tmp_path``: X-Plane's own DSF
of a tile is a header-only DSF (``O4_DSF_Binary.placeholder_bytes``
with its properties rewritten), and a fake ``subprocess.run`` stands in
for DSFTool -- nothing is spawned, the real install is never read.

* a full tile with no covering pack gets its overlay in
  ``yXPTerrainBuilder Overlays`` (a real folder with its marker), whose
  ini row goes directly above the World pack's;
* it is skipped when an ENABLED pack replaces the default road network
  over the whole tile, or already holds the default content (same
  creation agent); an airport overlay, a forest-only pack or a disabled
  pack covers nothing;
* the ini: Overlays then World are the last two rows, an existing row is
  moved there, and the World pack's own filing keeps that order;
* an adopted tile (Convert existing tiles) requests its overlay, and the
  background maker writes it without touching the build-step state.
"""
from __future__ import annotations

import os
import subprocess

import O4_DSF_Binary as DSFB
import O4_File_Names as FNAMES
import O4_Overlay_Pack as OPACK
import O4_Overlay_Utils as OVL
import O4_UI_Utils as UI
import O4_World_Pack as WP
import pytest
from o4_engine import overlay_queue as OVERLAYS
from o4_engine import world_migrate as MIGRATE
from o4_engine.session import plan_steps, with_auto_overlays
from test_world_migrate import xp  # noqa: F401

(LAT, LON) = (43, 5)
DEFAULT_AGENT = "Laminar default scenery 1.0"
DUMP = ("PROPERTY sim/west 5\nPOLYGON_DEF lib/a.for\n"
        "BEGIN_POLYGON 0 255 2\nEND_POLYGON\n")


def _dsf(path, lat, lon, agent, extra=()):
    """A header-only DSF of the tile at ``path``: ``agent`` as its
    creation agent, ``extra`` properties appended."""
    data = DSFB.placeholder_bytes(lat, lon, agent)
    if extra:
        data = DSFB.rewrite(data, props=lambda pairs: pairs + list(extra))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def _pack_dsf(scenery, name, lat=LAT, lon=LON, **kw):
    return _dsf(os.path.join(scenery, name, WP.dsf_relpath(lat, lon)),
                lat, lon, kw.pop("agent", "WorldEditor"), **kw)


def _ini(scenery, *rows):
    with open(os.path.join(scenery, "scenery_packs.ini"), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write("I\n1000 Version\nSCENERY\n\n" + "".join(
            row + "\n" for row in rows))


def _rows(scenery):
    with open(os.path.join(scenery, "scenery_packs.ini"),
              encoding="utf-8") as handle:
        return [line.strip() for line in handle
                if line.startswith("SCENERY_PACK")]


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Custom Scenery with a World pack row, X-Plane's own DSF of the tile
    in the Global Scenery beside it, and a fake DSFTool."""
    scenery = tmp_path / "X-Plane" / "Custom Scenery"
    scenery.mkdir(parents=True)
    _ini(str(scenery), "SCENERY_PACK Custom Scenery/Some Mesh/",
         "SCENERY_PACK Custom Scenery/zXPTerrainBuilder World/")
    global_scenery = tmp_path / "X-Plane" / "Global Scenery"
    _dsf(str(global_scenery / "X-Plane 12 Global Scenery"
             / WP.dsf_relpath(LAT, LON)), LAT, LON, DEFAULT_AGENT)
    monkeypatch.setattr(OVL, "custom_overlay_src", "")
    monkeypatch.setattr(OVL, "custom_overlay_src_alternate", "")
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_path / "tmp"))
    monkeypatch.setattr(UI, "engine_session", None)
    monkeypatch.setattr(UI, "is_working", 0)

    def run(argv, **kwargs):
        with open(argv[3], "wb") as handle:
            handle.write(DUMP.encode() if argv[1] == "-dsf2text"
                         else b"XPLNEDSF-overlay")
        return subprocess.CompletedProcess(argv, 0, "converted\n", "")
    monkeypatch.setattr(OVL.DSFTOOL.subprocess, "run", run)
    return str(scenery)


# ---------------------------------------------------------------- the build


def test_every_full_tile_plans_its_overlay_step():
    assert with_auto_overlays(True, True, False)
    assert not with_auto_overlays(True, False, False)
    assert not with_auto_overlays(False, True, False)
    assert with_auto_overlays(False, False, True)
    keys = [k for k, _b, _w in plan_steps(True, True, with_auto_overlays(
        True, True, False))]
    assert keys[-1] == "overlays"


def test_a_full_tile_without_a_covering_pack_gets_its_overlay(world):
    assert OVL.auto_overlay(LAT, LON, world) == 1
    with open(OPACK.dsf_path(world, LAT, LON), "rb") as handle:
        assert handle.read() == b"XPLNEDSF-overlay"
    pack = os.path.join(world, OPACK.PACK_NAME)
    assert os.path.isdir(pack) and not os.path.islink(pack)
    assert os.path.isfile(os.path.join(pack, OPACK.MARKER))
    assert _rows(world)[-2:] == [
        "SCENERY_PACK Custom Scenery/yXPTerrainBuilder Overlays/",
        "SCENERY_PACK Custom Scenery/zXPTerrainBuilder World/"]
    assert UI.is_working == 0
    # nothing left in the step's work folder
    assert os.listdir(FNAMES.Tmp_dir) == []


def test_a_tile_with_nothing_to_copy_or_nowhere_to_go_is_skipped(
        world, tmp_path):
    assert OVL.overlay_decision(LAT + 1, LON, world)["state"] == "no_source"
    assert OVL.auto_overlay(LAT + 1, LON, world) == 1
    assert OVL.overlay_decision(LAT, LON, "")["state"] == "no_scenery"
    assert not os.path.exists(os.path.join(world, OPACK.PACK_NAME))


# ---------------------------------------------------------- the covering rule


def _network(lat=LAT, lon=LON):
    return ("sim/exclude_net", f"{lon}.000000000/{lat}.000000000/"
                               f"{lon + 1}.000000000/{lat + 1}.000000000")


def test_an_enabled_pack_replacing_the_road_network_covers_the_tile(world):
    _pack_dsf(world, "Roads Everywhere",
              extra=[("sim/exclude_for", f"{LON}.1/{LAT}.1/{LON}.2/{LAT}.2"),
                     _network()])
    decision = OVL.overlay_decision(LAT, LON, world)
    assert decision["state"] == "covered"
    assert decision["pack"] == "Roads Everywhere"
    assert OVL.auto_overlay(LAT, LON, world) == 1
    assert not os.path.exists(os.path.join(world, OPACK.PACK_NAME))


def test_an_extracted_default_overlay_covers_the_tile(world):
    _pack_dsf(world, "Old Overlays", agent=DEFAULT_AGENT)
    assert OVL.overlay_decision(LAT, LON, world)["pack"] == "Old Overlays"


@pytest.mark.parametrize("name, extra, agent", [
    # an airport's overlay: a few small exclusion boxes
    ("Airport Overlay", [("sim/exclude_obj", f"{LON}.1/{LAT}.1/{LON}.2/{LAT}.2"),
                         ("sim/exclude_net", f"{LON}.1/{LAT}.1/{LON}.2/{LAT}.2")],
     "WorldEditor"),
    # forests only, over the whole tile: roads and buildings still needed
    ("Forests Only", [("sim/exclude_for", f"{LON}/{LAT}/{LON + 1}/{LAT + 1}")],
     "Forest tool"),
])
def test_an_airport_or_forest_overlay_covers_nothing(world, name, extra, agent):
    _pack_dsf(world, name, extra=extra, agent=agent)
    assert OVL.overlay_decision(LAT, LON, world)["state"] == "build"


def test_a_disabled_or_base_mesh_pack_covers_nothing(world):
    _pack_dsf(world, "Roads Off", extra=[_network()])
    with open(os.path.join(world, "scenery_packs.ini"), "a",
              encoding="utf-8", newline="\n") as handle:
        handle.write("SCENERY_PACK_DISABLED Custom Scenery/Roads Off/\n")
    mesh = DSFB.rewrite(DSFB.placeholder_bytes(LAT, LON, DEFAULT_AGENT),
                        props=lambda pairs: [p for p in pairs
                                             if p[0] != "sim/overlay"])
    path = os.path.join(world, "A Mesh", WP.dsf_relpath(LAT, LON))
    os.makedirs(os.path.dirname(path))
    with open(path, "wb") as handle:
        handle.write(mesh)
    assert OVL.overlay_decision(LAT, LON, world)["state"] == "build"


def test_our_own_packs_never_cover(world):
    _pack_dsf(world, OPACK.PACK_NAME, agent=DEFAULT_AGENT)
    _pack_dsf(world, WP.PACK_NAME, extra=[_network()])
    assert OVL.overlay_decision(LAT, LON, world)["state"] == "build"


# ------------------------------------------------------------------- the ini


def test_the_overlays_row_goes_directly_above_the_world_row():
    lines = ["I", "1000 Version", "SCENERY", "",
             "SCENERY_PACK Custom Scenery/yXPTerrainBuilder Overlays/",
             "SCENERY_PACK Custom Scenery/Ortho/",
             "SCENERY_PACK Custom Scenery/zXPTerrainBuilder World/",
             "SCENERY_PACK Custom Scenery/A Mesh/", ""]
    assert WP.ini_install(lines) is False
    assert lines[-4:] == [
        "SCENERY_PACK Custom Scenery/A Mesh/",
        "SCENERY_PACK Custom Scenery/yXPTerrainBuilder Overlays/",
        "SCENERY_PACK Custom Scenery/zXPTerrainBuilder World/", ""]
    assert OPACK.ini_install(lines) is False
    assert lines[-3:-1] == [
        "SCENERY_PACK Custom Scenery/yXPTerrainBuilder Overlays/",
        "SCENERY_PACK Custom Scenery/zXPTerrainBuilder World/"]


def test_without_a_world_row_the_overlays_row_is_last_until_world_comes():
    lines = ["I", "1000 Version", "SCENERY", "",
             "SCENERY_PACK Custom Scenery/A Mesh/", ""]
    assert OPACK.ini_install(lines) is True
    assert lines[-2] == "SCENERY_PACK Custom Scenery/yXPTerrainBuilder Overlays/"
    WP.ini_install(lines)
    assert lines[-3:-1] == [
        "SCENERY_PACK Custom Scenery/yXPTerrainBuilder Overlays/",
        "SCENERY_PACK Custom Scenery/zXPTerrainBuilder World/"]


def test_the_pack_is_never_a_link(tmp_path):
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    (tmp_path / "elsewhere").mkdir()
    os.symlink(str(tmp_path / "elsewhere"), scenery / OPACK.PACK_NAME)
    with pytest.raises(ValueError, match="never a link"):
        OPACK.install(str(scenery))


# --------------------------------------------------------------- adoption


def test_convert_requests_the_overlay_of_every_adopted_tile(xp, monkeypatch):  # noqa: F811
    asked = []
    monkeypatch.setattr(OVERLAYS, "request",
                        lambda lat, lon, scenery: asked.append(
                            (lat, lon, scenery)))
    out = MIGRATE.migrate(xp["scenery"], index=xp["index"])
    assert out["adopted"] == 2
    assert sorted(asked) == [(45, 7, xp["scenery"]), (46, 8, xp["scenery"])]


def test_the_background_maker_writes_the_overlay_beside_a_build(world):
    UI.is_working = 1                       # a build step is running
    assert OVL.background_overlay(LAT, LON, world) == "built"
    assert UI.is_working == 1               # its state untouched
    with open(OPACK.dsf_path(world, LAT, LON), "rb") as handle:
        assert handle.read() == b"XPLNEDSF-overlay"
    assert os.listdir(FNAMES.Tmp_dir) == []


def test_a_request_with_nothing_to_make_queues_nothing(world, monkeypatch):
    logged = []
    monkeypatch.setattr(OVERLAYS, "_log", lambda *a: logged.append(a))
    assert OVERLAYS.request(LAT + 1, LON, world) == "no_source"
    assert logged == [(LAT + 1, LON, "no_source")]
    assert OVERLAYS._JOBS.empty()


def test_the_mac_app_names_and_protects_the_same_pack():
    """``O4WorldPack.overlaysPackName`` is the same literal, and the Mac
    reconcile never removes its row (``PackActions.protectedNames``)."""
    import re
    from pathlib import Path
    kit = Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
    wire = (kit / "WorldWire.swift").read_text(encoding="utf-8")
    said = re.search(r'static let overlaysPackName = "([^"]+)"', wire)
    assert said and said.group(1) == OPACK.PACK_NAME
    actions = (kit / "PackActions.swift").read_text(encoding="utf-8")
    assert "O4WorldPack.overlaysPackName" in actions[
        actions.index("func protectedNames"):]
