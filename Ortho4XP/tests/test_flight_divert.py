"""Twin of the flight's diversion, the one reload in the air, the notices
and the offline waiver (spec flight-manager-and-world-20261110 §4.3 steps
7-8, §5.3 ``FlightNotice``, §7.5 S5 and S6 (b), §8.6, §11; owner RULINGS
2026-11-10k Q3/Q4; lane F2): ``src/o4_engine/flight_divert.py``,
``flight_air_reload.py``, ``flight_notices.py``, ``flight_swap_reload.py``
and their use in ``flight_manager.FlightManager``.

The end-to-end cases replay the CYYR World pack flight (W0's fixture,
``tools/flight_schedule_replay.py --flight --divert [--approach]``): a
diversion halfway that is in place before X-Plane loads its area, and a
late one whose airport waits staged until the one offered reload near
the ground.  Hermetic: tmp_path, no network, no X-Plane, no build.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE
import O4_World_Pack as WP
import pytest
from o4_engine import flight_divert as DIVERT
from o4_engine import flight_record as RECORD
from o4_engine import flight_swap_reload as SWAP
from o4_engine import world_commands as WORLD
from o4_engine.events import CAPABILITIES, FlightNotice
from o4_engine.flight_air_reload import LOW_AGL_M, NEAR_KM, AirReload
from o4_engine.flight_manager import FlightManager
from o4_engine.flight_notices import CODES, Board, notice

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))

import flight_schedule_replay as R  # noqa: E402

CYYR = (53.30427, -60.447077)
DEST = (53.15, -63.9)              # in +53-064, the tile built on the fly
WHEN = datetime(2026, 11, 10, tzinfo=timezone.utc)
ALT = FP.Waypoint("ALT", 52.5, -62.5)


@pytest.fixture(scope="module")
def recording():
    with open(R.FIXTURE, encoding="utf-8") as f:
        flight = json.load(f)
    with open(R.KIT, encoding="utf-8") as f:
        kit = json.load(f)
    return flight, kit


def _plan(alternate=ALT):
    return FP.FlightPlan([FP.Waypoint("DEP", *CYYR), FP.Waypoint("DEST", *DEST)],
                         source="test", alternate=alternate)


# ------------------------------------------------------------ the target

def test_the_target_is_the_alternate_an_airport_a_place_or_an_ident():
    plan = _plan()
    assert DIVERT.divert_target("alternate", plan) == (ALT, True)
    point, alt = DIVERT.divert_target({"ident": "cyqx", "lat": 48.9,
                                       "lon": -54.5}, plan)
    assert (point.ident, point.lat, point.lon, alt) == ("CYQX", 48.9, -54.5,
                                                        False)
    assert DIVERT.divert_target({"ident": "ALT", "lat": 52.5, "lon": -62.5},
                                plan)[1] is True
    assert DIVERT.divert_target([47.6, -52.7], plan)[0][1:3] == (47.6, -52.7)
    found = DIVERT.divert_target("cyyt", plan, lambda i: (47.6, -52.7)
                                 if i == "CYYT" else None)
    assert found[0].ident == "CYYT"
    with pytest.raises(ValueError, match="No airport ZZZZ"):
        DIVERT.divert_target("zzzz", plan, lambda i: None)
    with pytest.raises(ValueError, match="no alternate"):
        DIVERT.divert_target("alternate", _plan(alternate=None))
    with pytest.raises(ValueError, match="no position"):
        DIVERT.divert_target({"ident": "X", "lat": "?", "lon": 1}, plan)


def _job(tile, role="enroute", kind="drape", state="queued"):
    return SCHEDULE.Job(tile=tile, role=role, kind=kind, klass=SCHEDULE.P1,
                        deadline_s=100.0, est_s=(10.0, 20.0), state=state)


def test_the_old_destination_stops_unless_the_new_leg_needs_it():
    old = [_job((53, -64), "destination", "full", "building"),
           _job((53, -63), state="queued"), _job((53, -62), state="swapped"),
           _job((52, -63), state="building")]
    new = [_job((52, -64), "destination", "full")]
    cancelled = []
    merged = {j.tile: j for j in DIVERT.merge_after_divert(
        old, new, (53, -64), cancelled.append)}
    assert cancelled == [(53, -64)]
    assert merged[(53, -64)].state == "shed"
    assert merged[(53, -64)].role == "enroute"      # one destination
    assert merged[(53, -63)].state == "shed"        # not needed any more
    assert merged[(53, -62)].state == "swapped"
    assert merged[(52, -63)].state == "building"    # finishes, is published
    assert merged[(52, -64)].state == "queued"
    # the new leg still crosses the old destination: its build goes on
    cancelled.clear()
    kept = DIVERT.merge_after_divert(old, new + [_job((53, -64), kind="drape")],
                                     (53, -64), cancelled.append)
    assert not cancelled
    row = next(j for j in kept if j.tile == (53, -64))
    assert (row.kind, row.state) == ("full", "building")
    # an intermediate tile under the new destination is built full
    under = DIVERT.merge_after_divert(
        [_job((52, -64), state="swapped")], new, (53, -64), cancelled.append)
    assert next(j for j in under if j.tile == (52, -64)).state == "queued"


# ------------------------------------------------------- S6 (b) and notices

def test_the_air_reload_is_offered_never_sent_by_itself():
    """Owner 2026-11-12T14:34Z: "Never ask x-plane to reload unless the
    user requests it." -- near the ground the reload is offered once;
    no tick ever sends it; the pilot's press does, once."""
    air = AirReload()
    assert air.step(0.0, needed=True, near=False) == ""
    assert air.step(1.0, needed=True, near=True) == "offer"
    assert air.state == "offered"
    for t in range(2, 3600, 60):
        assert air.step(float(t), True, True) == ""     # never "send"
    assert air.press()
    air.sent()
    assert air.step(4000.0, True, True) == "" and air.state == "sent"
    assert not air.press()
    gone = AirReload()
    gone.step(0.0, True, True)
    assert gone.step(1.0, False, True) == "" and gone.state == ""


def test_each_notice_posts_once_and_counts_post_again_when_they_grow():
    board = Board()
    assert board.post("ready", origin="CYYR", destination="CYYT")
    assert not board.post("ready")
    assert board.post("tile_late", key=1, count=1)
    assert not board.post("tile_late", key=1, count=1)
    assert board.post("tile_late", key=3, count=3)
    out = board.drain()
    assert [n["code"] for n in out] == ["ready", "tile_late", "tile_late"]
    assert out[0]["title"] == "Departure ready"
    assert out[0]["text"] == "Your flight from CYYR to CYYT is ready for departure."
    assert board.drain() == []
    assert notice("diversion_ready", destination="CYQX")["title"] == "Diversion ready"
    assert notice("destination_ready", destination="CYYT",
                  margin_s=600)["title"] == "Destination ready"
    assert "X-Plane's own scenery" in notice("offline", count=2)["text"]
    assert set(CODES) >= {"ready", "destination_ready", "diversion_ready",
                          "offline", "reload_offered", "arrived"}
    wire = FlightNotice(flight="f", **notice("ready"))
    assert type(wire).__name__ == "FlightNotice" and wire.severity == "info"
    assert "flight_notices" in CAPABILITIES


# ------------------------------------------------- the CYYR flight replayed

def test_a_diversion_in_time_is_ready_before_its_area_loads(recording):
    """Diverted 600 s into the recording to an airport in +53-065: its
    full build (600 s) goes first (P0) and is swapped in before X-Plane
    opens the tile -- no reload in the air; "Diversion ready" is posted."""
    result = R.replay_flight(*recording, DEST, full_s=600.0, divert={
        "at_s": 600.0, "lat": 53.2, "lon": -64.3, "ident": "DIVA"})
    assert result["ok"], result
    div = result["diverted"]
    assert (div["tile"], div["role"], div["kind"], div["klass"]) == (
        "+53-065", "destination", "full", "P0")
    assert div["state"] == "swapped" and div["margin_s"] > 0
    assert result["reloads_air"] == []
    codes = [c for _t, c in result["notices"]]
    assert codes.count("diversion_ready") == 1 and "reload_offered" not in codes


def test_a_late_diversion_waits_staged_for_one_reload_near_the_ground(recording):
    """Diverted 1500 s in to an airport in +52-064, a tile X-Plane loaded
    already: the full build is staged, never swapped under X-Plane; on
    the approach (inside 20 km, below 3,000 ft) the reload is offered and
    sent when the (replayed) pilot presses it -- once, for that tile only
    (S6 (b)); en-route tiles are never reloaded and no loaded tile was
    swapped."""
    result = R.replay_flight(*recording, DEST, full_s=600.0, approach=True,
                             divert={"at_s": 1500.0, "lat": 52.95,
                                     "lon": -63.6, "ident": "DIVB"})
    assert result["loaded_swaps"] == []
    assert [names for _t, names in result["reloads_air"]] == [["+52-064"]]
    notices = dict((c, t) for t, c in result["notices"])
    sent = result["reloads_air"][0][0]
    assert notices["destination_late"] <= notices["reload_offered"] <= sent + 0.1
    assert notices["diversion_ready"] >= sent
    assert result["diverted"]["state"] == "swapped"
    late = [r for r in result["tiles"] if r["tile"] in result["late"]]
    assert all(r["state"] == "late" and r["swapped_s"] is None for r in late)
    assert result["state"] in ("flying", "arrived")


def test_the_reload_comes_only_near_the_airport_and_low(recording):
    """The same diversion without the approach (the recording ends at
    3,000 m above the ground): the airport stays staged, offered never."""
    result = R.replay_flight(*recording, DEST, full_s=600.0, divert={
        "at_s": 1500.0, "lat": 52.95, "lon": -63.6, "ident": "DIVB"})
    assert result["reloads_air"] == []
    codes = [c for _t, c in result["notices"]]
    assert "reload_offered" not in codes
    assert result["diverted"]["state"] in ("building", "staged")
    assert NEAR_KM == 20.0 and LOW_AGL_M == pytest.approx(914.4)


# ------------------------------------------------------- manager details

class _Builder:
    def __init__(self):
        self.started, self.done, self.cancelled = [], [], []

    def start(self, tile, kind, due, klass):
        self.started.append((tuple(tile), kind, klass))
        return True

    def poll(self, now):
        done, self.done = self.done, []
        return done


class _Publisher:
    @staticmethod
    def settle(tile, kind, held):
        return "staged" if held else "swapped"


def _manager(facts=None, plan=None):
    plan = plan or _plan()
    record = RECORD.from_plan(plan, "none", WHEN, cruise_kt=290)
    base = {"world_installed": True, "budget_fits": True, "network_ok": True,
            "all_on_disk": True, "prefetch_done": True}
    base.update(facts or {})
    builder = _Builder()
    manager = FlightManager(
        record, plan, builder=builder, publisher=_Publisher(),
        facts=lambda: base, state_of=lambda t: "placeholder",
        estimate=lambda t, k, r: SCHEDULE.job_estimate(
            k, {"full": 900.0}.get(k), known=True), parked_slots=2)
    return manager, builder, base


def test_a_diversion_before_takeoff_changes_the_destination():
    manager, builder, _facts = _manager()
    manager.tick(0.0, None)
    old = FP.tile_of(*DEST)
    name = manager.divert(1.0, ALT, True, cancel=builder.cancelled.append)
    assert name == "ALT"
    status = manager.status(1.0)
    assert status["diverted_to"] == "ALT"
    dest = [j for j in manager.jobs if j.role == "destination"]
    assert [(j.tile, j.kind, j.klass) for j in dest] == [
        ((52, -63), "full", SCHEDULE.P0)]
    assert manager.record.destination["ident"] == "ALT"
    assert manager.record.notes[-1]["diverted_to"] == "ALT"
    assert manager.plan.alternate is None          # diverted to it
    assert any(j.tile == old and j.state in ("shed", "building", "queued")
               for j in manager.jobs) or old not in {j.tile for j in manager.jobs}
    assert any(j.role == "departure" for j in manager.jobs)


def test_offline_tiles_en_route_may_be_left_to_xplane():
    """Q3: corridor tiles whose data could not be fetched block the
    network row with their count; the pilot's waiver leaves the en-route
    ones to X-Plane's own scenery (shed) and the row is done; the
    departure or destination are never waived."""
    manager, _builder, facts = _manager({"all_on_disk": False,
                                         "network_ok": False,
                                         "prefetch_done": False})
    enroute = sorted(j.tile for j in manager.jobs if j.role == "enroute")[:2]
    facts["offline_tiles"] = enroute
    manager.tick(0.0, None)
    status = manager.status(0.0)
    row = next(i for i in status["items"] if i[0] == "network")
    assert row[1] == "blocked" and "2 tile(s) en route" in row[3]
    assert sorted(status["waivable"]) == sorted(WP.tile_name(*t) for t in enroute)
    assert [n["code"] for n in manager.notices()] == ["offline"]
    assert manager.waive() == 2
    manager.tick(1.0, None)
    status = manager.status(1.0)
    assert next(i for i in status["items"] if i[0] == "network")[1] == "done"
    assert all(manager._job(t).state == "shed" for t in enroute)
    assert status["waivable"] == ()
    # the destination cannot be waived
    manager2, _b, facts2 = _manager({"all_on_disk": False, "network_ok": False,
                                     "prefetch_done": False,
                                     "offline_tiles": [FP.tile_of(*DEST)]})
    manager2.waive()
    manager2.tick(0.0, None)
    status2 = manager2.status(0.0)
    row2 = next(i for i in status2["items"] if i[0] == "network")
    assert row2[1] == "blocked" and "destination" in row2[3]
    assert status2["waivable"] == ()


# ------------------------------------------------- rule S5 on a tmp pack

def _tile_files(root, tile, names, dsf=b"DSF"):
    lat, lon = tile
    name = WP.tile_name(lat, lon)
    for sub, files in names.items():
        folder = os.path.join(root, sub, name)
        os.makedirs(folder, exist_ok=True)
        for f in files:
            with open(os.path.join(folder, f), "wb") as handle:
                handle.write(f.encode())
    dsf_path = os.path.join(root, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf_path), exist_ok=True)
    with open(dsf_path, "wb") as handle:
        handle.write(dsf)


def test_stale_names_go_only_after_the_witness_shows_the_reload(tmp_path,
                                                                monkeypatch):
    """S5: the merge keeps every old name; they are removed only once
    Log.txt shows a load of the tile NEWER than the one before the
    reload."""
    scenery = tmp_path / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    staging = tmp_path / "staging"
    tile = (52, -64)
    _tile_files(str(pack), tile, {"terrain": ["a.ter", "old.ter"],
                                  "textures": ["a.dds", "old.dds"]})
    _tile_files(str(staging / WP.tile_name(*tile)), tile,
                {"terrain": ["a.ter", "new.ter"], "textures": ["a.dds"]},
                dsf=b"NEW")
    from o4_engine import world_publish as PUBLISH
    monkeypatch.setattr(WORLD, "staging_root", lambda: str(staging))
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    monkeypatch.setattr(PUBLISH, "_after_swap", lambda *a: None)
    stamps = {tile: 100.0}
    sent = []
    reloader = SWAP.MergeReload(str(scenery), lambda lat, lon: "",
                                lambda: sent.append(1) or True,
                                lambda: dict(stamps))
    assert reloader([tile]) is True and sent == [1]
    terrain = pack / "terrain" / WP.tile_name(*tile)
    assert sorted(os.listdir(terrain)) == ["a.ter", "new.ter", "old.ter"]
    with open(pack / WP.dsf_relpath(*tile), "rb") as handle:
        assert handle.read() == b"NEW"
    assert reloader.sweep({tile: 100.0}) == 0        # not reloaded yet
    assert reloader.sweep({}) == 0
    assert (terrain / "old.ter").exists()
    assert reloader.sweep({tile: 812.5}) == 2         # old.ter, old.dds
    assert sorted(os.listdir(terrain)) == ["a.ter", "new.ter"]
    assert reloader.pending == {}
