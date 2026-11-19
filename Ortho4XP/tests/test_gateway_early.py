"""#2169 follow-up (owner 2026-11-19T00:21Z): the Gateway question for a
Global Airports airport whose patch needs a deck / road bridge is asked
BEFORE its patch is built, once per airport per run, and a patch built
before an install in the same run is built again.

Headless: a temp X-Plane folder, plain ``.osm`` feeds in ``tmp_path``,
no Gateway (nothing here installs through the network).
"""
from __future__ import annotations

import collections
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_UI_Utils as UI  # noqa: E402
from auto_patch import gateway_stage as GW  # noqa: E402
from auto_patch_v2.airport import apt_dat as APT  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.airport import OsmWay  # noqa: E402
from auto_patch_v2.planar import offer_witness as OW  # noqa: E402

LAW = Law.for_airport("KYYY")
#: a 200 m x 40 m taxiway of apt.dat pavement round the origin (metres)
SQUARE = types.SimpleNamespace(outer=((-100, -20), (100, -20), (100, 20), (-100, 20)),
                               holes=())


def _way(wid, pts, **tags):
    return OsmWay(wid, "airports", tuple(pts), False, tags)


def _airport(*ways):
    return types.SimpleNamespace(osm_ways=ways, pavements=(SQUARE,))


# ── the witness ─────────────────────────────────────────────────────────

def test_a_taxiway_bridge_over_a_road_is_a_deck_candidate():
    ap = _airport(_way(1, [(-90, 0), (90, 0)], aeroway="taxiway", bridge="yes", layer="1"),
                  _way(2, [(0, -300), (0, 300)], highway="service"))
    [note] = OW.offer_notes(ap, LAW)
    assert note.startswith("deck: taxiway bridge 1 over service 2")


def test_a_short_tunnel_offers_and_a_long_one_does_not():
    short = _way(3, [(0, -30), (0, 30)], highway="service", tunnel="yes", layer="-1")
    assert [n.split(" (")[0] for n in OW.offer_notes(_airport(short), LAW)] == [
        "deck: service tunnel 3 under the pavement"]
    cover = float(LAW.tables.structures.deck_gen.max_cover_m)
    long_ = _way(4, [(0, -cover), (0, cover)], highway="service", tunnel="yes")
    assert OW.offer_notes(_airport(long_), LAW) == []


def test_a_road_bridge_on_the_pavement_over_a_lower_road_offers():
    bridge = _way(5, [(-80, 5), (80, 5)], highway="service", bridge="yes", layer="1")
    lower = _way(6, [(0, -300), (0, 300)], highway="primary")
    [note] = OW.offer_notes(_airport(bridge, lower), LAW)
    assert note == "road bridge: service 5 over 6"
    # read twice from two tiles' extracts: one bridge
    again = _way(7, bridge.points, highway="service", bridge="yes", layer="1")
    assert len(OW.offer_notes(_airport(bridge, again, lower), LAW)) == 1


def test_an_airport_with_no_crossing_offers_nothing():
    beside = _way(8, [(300, -300), (300, 300)], highway="primary")
    over = _way(9, [(400, -50), (600, -50)], highway="primary", bridge="yes", layer="1")
    flat = _way(10, [(-90, 0), (90, 0)], aeroway="taxiway")
    assert OW.offer_notes(_airport(beside, over, flat, _way(11, [(0, -300), (0, 300)],
                                                        highway="service")), LAW) == []
    assert OW.offer_notes(types.SimpleNamespace(osm_ways=(), pavements=()), LAW) == []


# ── the early report, once per airport per run ─────────────────────────

GLOBAL_APT = (
    "I\n1200 test\n\n"
    "1    400 0 0 KYYY Bridge Field\n"
    "100 30.00 1 0 0.25 0 2 1 09 44.3010 -123.4030 0 0 2 0 0 0 "
    "27 44.3010 -123.3970 0 0 2 0 0 0\n"
    "110 1 0.25 0.00 Taxiway\n111 44.3008 -123.4010\n111 44.3008 -123.3990\n"
    "111 44.3012 -123.3990\n113 44.3012 -123.4010\n\n"
    "1    100 0 0 KZZZ Plain Field\n"
    "100 30.00 1 0 0.25 0 2 1 09 44.5010 -123.6030 0 0 2 0 0 0 "
    "27 44.5010 -123.5970 0 0 2 0 0 0\n"
    "110 1 0.25 0.00 Apron\n111 44.5000 -123.6010\n111 44.5000 -123.5990\n"
    "111 44.5020 -123.5990\n113 44.5020 -123.6010\n\n99\n")


def _osm(path, ways):
    """A plain ``.osm`` extract: ``ways`` = ``[(id, [(lat, lon), ...], tags)]``."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6">']
    nid = 0
    for wid, pts, tags in ways:
        refs = []
        for lat, lon in pts:
            nid += 1
            out.append(f'<node id="{nid}" lat="{lat}" lon="{lon}"/>')
            refs.append(nid)
        out.append(f'<way id="{wid}">' + "".join(f'<nd ref="{r}"/>' for r in refs)
                   + "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items()) + "</way>")
    out.append("</osm>")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))


@pytest.fixture
def xp(tmp_path, monkeypatch):
    root = tmp_path / "X-Plane 12"
    ga = root / "Global Scenery" / "Global Airports" / "Earth nav data"
    ga.mkdir(parents=True)
    (ga / "apt.dat").write_text(GLOBAL_APT, encoding="utf-8", newline="")
    (root / "Custom Scenery").mkdir()
    osm_root = tmp_path / "OSM_data"
    from auto_patch_v2.airport import osm as OSM
    _osm(OSM.feed_path(str(osm_root), 44, -124, "airports"), [
        (1, [(44.3010, -123.4008), (44.3010, -123.3992)],
         {"aeroway": "taxiway", "bridge": "yes", "layer": "1"})])
    _osm(OSM.feed_path(str(osm_root), 44, -124, "airport_small_roads"), [
        (2, [(44.2990, -123.4000), (44.3030, -123.4000)], {"highway": "service"}),
        (3, [(44.4990, -123.6040), (44.5030, -123.6040)], {"highway": "service"})])
    from auto_patch_v2.airport import pack_choice as PC
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / "prefs" / name))
    seen: list = []
    monkeypatch.setattr(UI, "gateway_airports", lambda **f: seen.append(f))
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    monkeypatch.setattr(GW, "_codes_of_tile", lambda root, lat, lon: ["KYYY", "KZZZ"])
    APT._SELECTION.clear()
    GW.begin_run()
    yield types.SimpleNamespace(root=str(root), osm=str(osm_root), events=seen,
                                tmp=tmp_path)
    GW.begin_run()


def test_the_early_report_asks_before_the_patch_and_once_per_run(xp):
    rows = GW.gateway_early([(44, -124)], lambda la, lo: xp.root, xp.osm)
    assert [(r["icao"], r["reason"], r["name"]) for r in rows] == [
        ("KYYY", "bridges", "Bridge Field")]
    assert [(e["state"], e["lat"], e["lon"]) for e in xp.events] == [("found", 44, -124)]
    # the airport's second tile, and its built tile's report: not asked again
    assert GW.gateway_early([(45, -124)], lambda la, lo: xp.root, xp.osm) == []
    patches = xp.tmp / "Patches"
    _graded(patches, "KYYY", {"offer": ["generated deck ...: REFUSED -- ..."]})
    import unittest.mock as M

    import O4_File_Names as FNAMES
    with M.patch.object(FNAMES, "patch_dir", lambda lat, lon: str(patches)):
        assert GW.gateway_stage(44, -124, xp.root, ["KYYY"]) == []
    assert len(xp.events) == 1
    # a new run asks again
    GW.begin_run()
    assert [r["icao"] for r in GW.gateway_early([(44, -124)], lambda la, lo: xp.root,
                                                xp.osm)] == ["KYYY"]


def test_no_feeds_on_disk_leaves_the_build_time_offer(xp, tmp_path):
    assert GW.gateway_early([(44, -124)], lambda la, lo: xp.root,
                            str(tmp_path / "none")) == []
    assert xp.events == []


def test_two_tiles_report_one_airport_once(xp, tmp_path):
    import unittest.mock as M

    import O4_File_Names as FNAMES
    for tile in ("a", "b"):
        _graded(tmp_path / tile, "KYYY", {"offer": ["x"]})
    dirs = {(30, -96): str(tmp_path / "a"), (29, -96): str(tmp_path / "b")}
    with M.patch.object(FNAMES, "patch_dir", lambda lat, lon: dirs[(lat, lon)]):
        first = GW.gateway_stage(30, -96, xp.root, ["KYYY"])
        second = GW.gateway_stage(29, -96, xp.root, ["KYYY"])
    assert [r["icao"] for r in first] == ["KYYY"] and second == []
    assert len(xp.events) == 1


# ── the same run builds a stale patch again ─────────────────────────────

def _graded(patch_dir, icao, generated):
    from auto_patch_v2.model.rebake import graded_surface_path
    os.makedirs(patch_dir, exist_ok=True)
    with open(graded_surface_path(str(patch_dir), icao), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump({"provenance": {"generated": generated}}, fh)


def test_an_install_names_the_tiles_built_before_it_once(xp, tmp_path, monkeypatch):
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: str(tmp_path / f"{lat}{lon}"))
    _graded(tmp_path / "30-96", "KYYY", {"offer": ["x"]})
    _graded(tmp_path / "29-96", "KYYY", {"offer": []})
    assert GW.stale_patches(30, -96) == []          # nothing installed yet
    monkeypatch.setattr(GW, "_install", lambda root, icao, fetch=None: {
        "pack": f"{icao} Gateway Airport", "pack_root": "/p", "scenery_id": 7,
        "flatten": "", "files": []})
    GW.gateway_choice(xp.root, "install", 30, -96, items=["KYYY"])
    assert GW.stale_patches(30, -96) == ["KYYY"]
    assert GW.stale_patches(30, -96) == []          # once per tile and airport
    assert GW.stale_patches(29, -96) == []          # built against the pack


def test_the_session_requeues_a_stale_tile_in_the_same_run(monkeypatch):
    from o4_engine import session as S
    session = S.EngineSession()
    item = ((30, -96), "BI", 16, "", [("vector", None, None)])
    session._building = True
    session._parallel = None
    session._run_items = {(30, -96): item}
    session._work_queue = collections.deque()
    monkeypatch.setattr(session, "_eta_add_tiles", lambda *a, **k: None)
    monkeypatch.setattr(UI, "vprint", lambda *a, **k: None)
    monkeypatch.setattr(GW, "stale_patches",
                        lambda lat, lon: ["KYYY"] if (lat, lon) == (30, -96) else [])
    session._gateway_repatch([(30, -96), (29, -96)])
    assert list(session._work_queue) == [item]
    session._gateway_repatch([(30, -96)])           # queued already: once
    assert list(session._work_queue) == [item]

    calls = []
    session._parallel = types.SimpleNamespace(repatch=lambda *a: calls.append(a))
    session._gateway_repatch([(30, -96)])
    assert calls and calls[0][:2] == ((30, -96), ["KYYY"])


def test_the_parallel_run_reselects_the_tile():
    from o4_engine import parallel as P
    seen = []
    run = types.SimpleNamespace(
        _lock=__import__("threading").Lock(),
        _reselect_tile_locked=lambda tile, icaos, line: seen.append((tile, icaos, line)),
        _dispatch_locked=lambda: seen.append("dispatch"))
    P.ParallelBuildRun.repatch(run, (30, -96), ["KYYY"], "why")
    assert seen == [((30, -96), ["KYYY"], "why"), "dispatch"]


def test_an_install_command_repatches_the_live_run(monkeypatch):
    import time

    from o4_engine import session as S
    from o4_engine import xplane_root as PO
    session = S.EngineSession()
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: "/xp")
    monkeypatch.setattr(GW, "gateway_choice", lambda *a, **k: {"state": "installed"})
    monkeypatch.setattr(session, "_live_run_cells", lambda: {(30, -96), (29, -96)})
    got = []
    monkeypatch.setattr(session, "_gateway_repatch", got.append)
    session.gateway_airports("install", 30, -96, items=["KYYY"])
    deadline = time.time() + 10
    while not got and time.time() < deadline:
        time.sleep(0.01)
    assert got == [[(29, -96), (30, -96)]]


def test_a_run_start_resets_the_run_and_asks_early(monkeypatch):
    from o4_engine import session as S
    began, early = [], []
    monkeypatch.setattr(GW, "begin_run", lambda: began.append(1))
    monkeypatch.setattr(S, "_offer_gateway_early", early.append)
    from o4_engine import storage_room
    monkeypatch.setattr(S, "_note_storage_session", lambda tiles: None)
    monkeypatch.setattr(storage_room, "before_run", lambda *a, **k: None)
    session = S.EngineSession()
    for name in ("_build_worker", "_prepare_in_process_eta", "_seed_work_queue"):
        monkeypatch.setattr(session, name, lambda *a, **k: None)
    session._building = True
    session._start_run([(44, -124)], "BI", 16, "", True, False, False, 1, None,
                       None, None, None, None, None)
    assert began == [1] and early == [[(44, -124)]]
    # a worker child (one step) never asks
    began.clear(), early.clear()
    session._start_run([(44, -124)], "BI", 16, "", True, False, False, 1, ["vector"],
                       None, None, None, None, None)
    assert began == [] and early == []
