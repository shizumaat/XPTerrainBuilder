"""Twin: a World or flight ``full`` build is on demand whatever the
user's switch -- high resolution at its airports and within sight of
them (the cores, fetched before the tile is published), 512 px
placeholders elsewhere; a flight's departure counts ready only with its
cores landed.  The Build pane keeps the user's switch (owner
2026-11-12T16:34Z, lane lcore)."""
from __future__ import annotations

import os
import threading
import time

import O4_Config_Utils as CFG
import O4_Imagery_Placeholder as PLACEHOLDER
import O4_Imagery_Regions as REGIONS
from o4_engine import flight_job_run as FLIGHT
from o4_engine import imagery_after_build as AFTER
from o4_engine import world_commands as WORLD
from o4_engine import world_job_run as RUN
from o4_engine import world_publish as PUBLISH
from o4_engine.events import BuildDone


def _switched_off(tmp_path):
    tile = CFG.Tile(53, -64, str(tmp_path) + os.sep)
    region = REGIONS.setting_name(REGIONS.region_of(53, -64))
    tile.imagery_on_demand = False
    setattr(tile, region, False)
    tile.texture_mode = "full_ortho"
    return tile, region


def test_a_world_full_build_is_on_demand_with_the_switch_off(tmp_path):
    tile, region = _switched_off(tmp_path)
    assert "imagery_on_demand" in CFG.BUILD_OVERRIDE_KEYS
    tile.apply_build_overrides(RUN.FULL_OVERRIDES)
    assert tile.imagery_on_demand is True and getattr(tile, region) is False
    # its region's switch off too: the World build asked for it
    assert PLACEHOLDER.drop(tile) in PLACEHOLDER.ALLOWED_DROPS   # 512 px
    # the tile's cfg never learns the override
    assert tile._build_override_saved == {"imagery_on_demand": False}


def test_a_build_pane_build_with_the_switch_off_is_full_imagery(tmp_path):
    tile, _region = _switched_off(tmp_path)
    tile.apply_build_overrides({"auto_patch": True})   # the pane's toggles
    assert PLACEHOLDER.drop(tile) == 0


def test_the_session_builder_asks_on_demand_for_a_full_build():
    calls = []

    class Session:
        def subscribe(self, callback):
            pass

        def enqueue_build(self, tiles, *args, **kw):
            calls.append(kw)
            return True

    builder = RUN._SessionBuilder(Session(), "BI", 16, drape=lambda t: True)
    assert builder.start((53, -64), "full", 600.0, "P0")
    assert calls[0]["overrides"] == {"imagery_on_demand": True}
    calls[0]["overrides"]["imagery_on_demand"] = False   # a copy each time
    assert RUN.FULL_OVERRIDES == {"imagery_on_demand": True}


def test_a_built_tile_lands_its_cores_before_it_is_published(monkeypatch):
    order, seen_busy = [], []
    release = threading.Event()

    def sharpen(where, build, lat, lon):
        seen_busy.append(PUBLISH.publishing(lat, lon))
        release.wait(5)
        order.append(("cores", lat, lon))

    monkeypatch.setattr(PUBLISH, "_sharpen", sharpen)
    monkeypatch.setattr(PUBLISH, "_publish_built",
                        lambda where, build, lat, lon:
                        order.append(("publish", lat, lon)) or None)

    class Session:
        _stepwise_run = False

        def __init__(self):
            self.subscribers = []

        def subscribe(self, callback):
            self.subscribers.append(callback)

        def tile_build_dir(self, lat, lon):
            return "/build"

    session = Session()
    PUBLISH.watch(session, scenery_dir=lambda: "/scenery")
    session.subscribers[0](BuildDone(lat=12, lon=34, ok=True))
    assert PUBLISH.publishing(12, 34)          # queued: not yet waited on
    release.set()
    deadline = time.time() + 10
    while PUBLISH.publishing(12, 34) and time.time() < deadline:
        time.sleep(0.02)
    assert order == [("cores", 12, 34), ("publish", 12, 34)]
    assert seen_busy == [True] and not PUBLISH.publishing(12, 34)


def test_the_cores_cover_a_named_airport_the_build_graded_none(monkeypatch):
    handed = []
    monkeypatch.setattr(WORLD, "managed", lambda where: True)
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    monkeypatch.setattr(PUBLISH, "_on_demand", lambda *a: True)
    monkeypatch.setattr(AFTER, "sharpen", lambda tiles, extra=None:
                        handed.append((tiles, extra)) or {"landed": 3})
    PUBLISH.add_core_point(56, 78, ("DEP", 56.5, 78.5))
    PUBLISH.add_core_point(56, 78, ("DEP", 56.5, 78.5))      # once
    assert PUBLISH._sharpen("/s", "/b", 56, 78) == {"landed": 3}
    assert handed == [([("/b", 56, 78)],
                       {(56, 78): [("DEP", 56.5, 78.5)]})]
    monkeypatch.setattr(PUBLISH, "_on_demand", lambda *a: False)
    assert PUBLISH._sharpen("/s", "/b", 56, 78) is None     # full imagery


def test_core_wants_takes_an_extra_airport_once(monkeypatch):
    import O4_Imagery_OnDemand_Cores as CORES
    import O4_Imagery_OnDemand_Index as INDEX
    got = []
    monkeypatch.setattr(CORES, "airport_points", lambda la, lo: [
        ("GRD", 1.0, 2.0)])
    monkeypatch.setattr(CORES, "base_zoom", lambda *a: 16)
    monkeypatch.setattr(INDEX, "rows", lambda conn, tile: [{"tier_px": 512}])
    monkeypatch.setattr(CORES, "core_tier", lambda row, points, zl:
                        got.append(list(points)) or None)
    AFTER.core_wants(None, "/b", 1, 2, [("GRD", 1.0, 2.0),
                                         ("DEP", 1.5, 2.5)])
    assert got == [[("GRD", 1.0, 2.0), ("DEP", 1.5, 2.5)]]


def test_the_departure_is_not_ready_while_its_cores_land(tmp_path,
                                                          monkeypatch):
    """``_PackPublisher.settle`` keeps a tile in the publish worker
    ``pending`` and never times it out there (PENDING_S counts only after
    the worker is done with it)."""
    clock = [0.0]
    monkeypatch.setattr(WORLD, "staging_root", lambda: str(tmp_path / "st"))
    pub = RUN._PackPublisher(str(tmp_path), lambda la, lo: "/b",
                             clock=lambda: clock[0])
    monkeypatch.setattr(PUBLISH, "publishing", lambda la, lo: True)
    for clock[0] in (0.0, RUN.PENDING_S * 3):
        assert pub.settle((53, -64), "full", held=False) == "pending"
    monkeypatch.setattr(PUBLISH, "publishing", lambda la, lo: False)
    assert pub.settle((53, -64), "full", held=False) == "pending"
    clock[0] += RUN.PENDING_S + 1
    assert pub.settle((53, -64), "full", held=False) == "failed"


def test_the_countdown_counts_the_core_fetch(monkeypatch):
    monkeypatch.setattr(FLIGHT, "_build_seconds", lambda *a: (100.0, 200.0))
    c_lo, c_hi = AFTER.core_seconds(1)
    assert 10.0 < c_lo < c_hi < 300.0          # ~183 MB at 8 / 2 MB/s
    seconds = FLIGHT.estimate("BI", 16)
    assert seconds((53, -64), "full", "departure") == (100.0 + c_lo,
                                                       200.0 + c_hi)
    assert AFTER.core_seconds(0) == (0.0, 0.0)
