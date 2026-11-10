"""Twins for the imagery follow job (#1992 local-imagery-cache spec §4,
§8, phase P3b): ``O4_XPlane_WebAPI``, ``O4_Imagery_Follow_Motion``,
``O4_Imagery_Fetch_Slots``, ``o4_engine.imagery_follow`` and the tier
zoom of ``O4_Imagery_Utils.build_jpeg_ortho`` / ``convert_texture``.

The acceptance of spec §14 P3b, offline:

* a fake X-Plane Web API on a local port replays flight 2's outbound
  track (``tests/fixtures/imagery_tier``), with an id reset mid-track;
* a fake lander lands whole files; the job lands the planner's fetches
  in planner order, earliest deadline first;
* every texture name stays a whole DDS throughout (§8 invariant);
* the job survives the id reset (counted as a flight load);
* no fetch starts while a build runs or a Library command holds the
  pause; the job stops cleanly with a final ``stopped`` status;
* the fetch slots are adaptive: one while the buffer holds, more while
  it depletes, back to one after it recovers (owner ruling
  2026-11-10T05:18Z).

Network-free: the server listens on 127.0.0.1; the lander is a stub, and
the tier-zoom twins stub the provider's tile fetch.
"""
from __future__ import annotations

import concurrent.futures as futures
import json
import math
import os
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy
import O4_DDS_Cache as DDSCACHE
import O4_DDS_Encode as DDSENC
import O4_DDS_File as DDS
import O4_DDS_Tiers as TIERS
import O4_File_Names as FNAMES
import O4_Imagery_Fetch_Slots as SLOTS
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Tier_Plan as PLAN
import O4_Imagery_Utils as IMG
import O4_XPlane_WebAPI as WEBAPI
import pytest
from o4_engine import imagery_follow as FOLLOW
from o4_engine.events import ImageryFollowStatus
from O4_Imagery_Follow_Motion import MotionTracker
from PIL import Image

FX = Path(__file__).resolve().parent / "fixtures" / "imagery_tier"
REPLAY = json.loads((FX / "flight2_outbound.replay.json").read_text(
    encoding="utf-8"))
TILE = "+60-136"


# --- a fake X-Plane Web API ------------------------------------------------

#: (key, dataref) the fake X-Plane publishes; the rest read as missing.
_OFFERED = {ref: key for key, ref, _ in WEBAPI.POS_REFS
            if key in ("lat", "lon", "elev_m", "gs_ms", "paused",
                       "local_x", "local_z", "view_x", "view_z")}


class FakeXPlane:
    """The Web API v2 GETs: ids by name, values by id; and its commands:
    ``commands`` (name -> id; empty before a flight is loaded) listed by
    name, activated by POST (``activations``: ``(id, body)``; ``stall_s``
    delays that answer, as a scenery reload does).  ``generation``
    changes every dataref id (a flight load); ``down`` refuses every
    request."""

    def __init__(self):
        self.values = {"lat": 0.0, "lon": 0.0, "elev_m": 0.0, "gs_ms": 0.0,
                       "paused": 0, "local_x": 0.0, "local_z": 0.0,
                       "view_x": 0.0, "view_z": 0.0}
        self.generation = 1
        self.down = False
        self.requests = 0
        self.commands = {WEBAPI.RELOAD_SCENERY: 4711}
        self.activations = []
        self.stall_s = 0.0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                fake.requests += 1
                self._send(*fake.answer(self.path))

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                status, answer = fake.activate(self.path, body)
                try:
                    self._send(status, answer)
                except OSError:          # the client stopped waiting
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.base = WEBAPI.base_url(self.server.server_address[1],
                                    "127.0.0.1")

    def _id(self, key) -> int:
        return self.generation * 1000 + sorted(_OFFERED.values()).index(key)

    def answer(self, path):
        if self.down:
            return 503, {"error": "loading"}
        url = urlparse(path)
        if url.path == "/api/v2/commands":
            name = parse_qs(url.query).get("filter[name]", [""])[0]
            if name not in self.commands:
                return 404, {"error_code": "invalid_command_name"}
            return 200, {"data": [{"id": self.commands[name], "name": name}]}
        if url.path == "/api/v2/datarefs":
            name = parse_qs(url.query).get("filter[name]", [""])[0]
            key = _OFFERED.get(name)
            return 200, {"data": [{"id": self._id(key), "name": name}]
                         if key else []}
        parts = url.path.split("/")
        if len(parts) == 6 and parts[5] == "value":
            ident = int(parts[4])
            for key in _OFFERED.values():
                if self._id(key) == ident:
                    return 200, {"data": self.values[key]}
        return 404, {"error": "unknown id"}

    def activate(self, path, body):
        """``POST /api/v2/command/<id>/activate`` with ``{"duration": s}``."""
        parts = urlparse(path).path.split("/")
        if self.down:
            return 503, {"error": "loading"}
        if (len(parts) != 6 or parts[3] != "command" or parts[5] != "activate"
                or int(parts[4]) not in self.commands.values()):
            return 404, {"error_code": "invalid_command_id"}
        if "duration" not in body:
            return 400, {"error_code": "duration_missing"}
        self.activations.append((int(parts[4]), body))
        time.sleep(self.stall_s)
        return 200, {}

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def xplane():
    fake = FakeXPlane()
    yield fake
    fake.close()


# --- O4_XPlane_WebAPI --------------------------------------------------------


def test_the_reader_survives_an_id_reset_and_counts_it(xplane):
    reader = WEBAPI.PositionReader(xplane.base)
    xplane.values.update(lat=60.5, lon=-135.5)
    first = reader.read()
    assert first["lat"] == 60.5 and reader.resolved
    assert "sim/graphics/view/view_type" in reader.missing
    assert reader.read()["lon"] == -135.5 and not reader.resolved
    xplane.generation = 2                       # a flight load: new ids
    xplane.down = True
    assert reader.read() is None and reader.down_since is not None
    xplane.down = False
    assert reader.read()["lat"] == 60.5
    assert reader.resets == 1
    down, errors = reader.recovered()
    assert errors == 1 and down >= 0
    assert reader.recovered() is None


def test_the_camera_is_the_aircraft_moved_by_the_view_offset():
    rec = {"lat": 60.0, "lon": -136.0, "local_x": 100.0, "local_z": 50.0,
           "view_x": 1100.0, "view_z": -950.0}       # 1 km east, 1 km north
    lat, lon = WEBAPI.camera_position(rec)
    assert lat == pytest.approx(60.0 + 1000 / 111_320.0)
    assert lon == pytest.approx(-136.0 + 1000 / (111_320.0 * 0.5), rel=1e-4)
    assert WEBAPI.camera_position({"lat": 1.0, "lon": 2.0}) == (1.0, 2.0)


def test_the_recorder_reads_through_the_engine_module():
    """One implementation: the recorder's poller is this module's."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                           / "tools" / "xplane_reads"))
    import record_reads as RR
    assert RR.poll_positions is WEBAPI.poll_positions
    assert RR.POS_REFS is WEBAPI.POS_REFS


# --- motion from position deltas ------------------------------------------


def test_speed_and_track_come_from_position_deltas_not_the_dataref():
    tracker = MotionTracker(square_m=4744.0)
    # 200 m/s due east at 60 N; the groundspeed dataref would say 25.
    step = 200.0 / (111_320.0 * 0.5)
    for i in range(8):
        m = tracker.add(float(i), 60.0, -136.0 + i * step)
    assert m.groundspeed_ms == pytest.approx(200.0, rel=0.01)
    assert m.track_deg == pytest.approx(90.0, abs=0.5)
    assert tracker.jumps == 0


def test_a_camera_jump_restarts_the_history():
    tracker = MotionTracker(square_m=4744.0)
    tracker.add(0.0, 60.0, -136.0)
    tracker.add(1.0, 60.0, -135.999)
    m = tracker.add(2.0, 61.0, -136.0)              # 111 km in 1 s
    assert tracker.jumps == 1 and tracker.jumped
    assert m.groundspeed_ms == 0.0 and m.lat == 61.0


# --- the adaptive buffer (owner ruling 2026-11-10T05:18Z) -------------------


def test_buffer_is_the_tightest_slack_at_the_current_slots():
    assert SLOTS.buffer_s([], 5.0, 1) == math.inf
    assert SLOTS.buffer_s([20.0, 22.0], 5.0, 1) == 12.0     # 22 - 10
    assert SLOTS.buffer_s([20.0, 22.0], 5.0, 2) == 17.0     # 22 - 5
    assert SLOTS.buffer_s([3.0], [5.0], 1) == -2.0


def test_slots_one_steady_more_while_depleting_back_to_one_after():
    slots = SLOTS.FetchSlots(max_slots=4)
    t = 0.0
    for _ in range(30):                     # a queue keeping up: one slot
        assert slots.update(25.0, t) == 1
        t += 1.0
    seen = []
    buffer = 25.0
    for _ in range(20):                     # depleting 2 s every second
        buffer -= 2.0
        seen.append(slots.update(buffer, t))
        t += 1.0
    assert seen[0] == 1                     # still above HIGH_S: no alarm
    assert max(seen) >= 3 and seen == sorted(seen)
    # never more than one change per STEP_S
    changes = [i for i in range(1, len(seen)) if seen[i] != seen[i - 1]]
    assert all(b - a >= SLOTS.STEP_S
               for a, b in zip(changes, changes[1:], strict=False))
    grown = seen[-1]
    # recovered: held at HIGH_S or more, the slots step back down to one
    shrink = []
    for _ in range(200):
        t += 1.0
        shrink.append(slots.update(25.0, t))
    assert shrink[0] == grown
    assert shrink[-1] == 1 and shrink == sorted(shrink, reverse=True)
    first_drop = next(i for i, n in enumerate(shrink) if n < grown)
    assert first_drop + 1 >= SLOTS.RECOVER_S


def test_thresholds_scale_with_the_lead():
    slots = SLOTS.for_lead(60.0)
    assert slots.low_s == 2 * SLOTS.LOW_S and slots.high_s == 2 * SLOTS.HIGH_S


def test_a_low_buffer_alone_adds_a_slot_and_a_steady_middle_keeps_it():
    slots = SLOTS.FetchSlots(max_slots=2)
    assert slots.update(2.0, 0.0) == 2          # below LOW_S: at risk
    assert slots.update(2.0, 10.0) == 2         # at the ceiling
    for t in range(11, 100):
        assert slots.update(10.0, float(t)) == 2   # between LOW and HIGH


# --- the follow job over flight 2 ----------------------------------------


def _index_rows(tmp_path, squares=None, tiers=None):
    """One index row per square (flight 2's unless given); each texture a
    whole 512 px placeholder... as a tiny whole DDS (the job reads headers
    only through the lander).  ``tiers`` (name -> tier) are already
    upgraded."""
    build = tmp_path / "build"
    textures = build / "textures"
    textures.mkdir(parents=True)
    path = tmp_path / "index.sqlite"
    conn = INDEX.open_index(str(path))
    for name, lat, lon, size in squares or REPLAY["squares"]:
        _whole_dds(textures / name, 0)
        tier = (tiers or {}).get(name, 0)
        INDEX.upsert(conn, {"tile": TILE, "name": name, "zl": 16,
                            "provider": "Arc", "build_dir": str(build),
                            "centre_lat": lat, "centre_lon": lon,
                            "load_size_m": size,
                            "state": "upgraded" if tier else "low",
                            "tier_px": PLAN.TIER_WIDTH[tier]})
    conn.close()
    return str(path), textures


def _whole_dds(final, seed) -> None:
    """Land a tiny whole DDS at ``final`` (partial name, os.replace)."""
    rng = numpy.random.default_rng(seed)
    pixels = rng.integers(0, 255, (16, 16, 3), dtype=numpy.uint8)
    partial = DDS.partial_name(str(final))
    DDSENC.encode_texture(pixels, "bc1", partial)
    assert DDS.land(partial, str(final))


class FakeLander:
    """Lands a whole file at once; records the order."""

    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)
        self.guard = threading.Lock()

    def __call__(self, row, tier):
        with self.guard:
            self.calls.append((row["name"], tier))
        if row["name"] in self.fail:
            raise RuntimeError("provider refused")
        final = os.path.join(row["build_dir"], "textures", row["name"])
        _whole_dds(final, len(self.calls))
        return {"tier_px": PLAN.TIER_WIDTH[tier], "full_bytes": 1000,
                "jpeg_path": None, "dds_cache_key": None, "network": True}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _settle(job):
    """Wait for the fetches in flight (the stub lands at once)."""
    futures.wait([f.future for f in job._inflight.values()], timeout=10)


def _job(xplane, tmp_path, **kw):
    index_path, textures = _index_rows(tmp_path)
    events = []
    clock = Clock()
    lander = kw.pop("lander", FakeLander())
    job = FOLLOW.FollowJob(events.append,
                           reader=WEBAPI.PositionReader(xplane.base),
                           lander=lander, index_path=index_path,
                           clock=clock, log_path=str(tmp_path / "od.log"),
                           **kw)
    return job, events, clock, lander, textures, index_path


def _fly(job, xplane, clock, positions, each=None):
    for i, (t, lat, lon, alt, gs) in enumerate(positions):
        clock.t = t
        xplane.values.update(lat=lat, lon=lon, elev_m=alt, gs_ms=gs)
        if each is not None:
            each(i)
        job.tick()
        _settle(job)


def test_the_job_follows_flight_2_in_planner_order(xplane, tmp_path):
    job, events, clock, lander, textures, index_path = _job(xplane, tmp_path)
    job.open()
    broken = []
    stop = threading.Event()

    def invariant():                 # §8: every name a whole DDS, always
        names = [n for n, *_ in REPLAY["squares"]]
        while not stop.is_set():
            for name in names:
                if not DDS.is_whole(str(textures / name)):
                    broken.append(name)
            time.sleep(0.02)

    watcher = threading.Thread(target=invariant, daemon=True)
    watcher.start()
    order_ok, dispatched = [], []

    def reset_ids(i):                # a flight load mid-track
        if i == 150:
            xplane.generation, xplane.down = 2, True
        elif i == 153:
            xplane.down = False

    def check_order():
        due, squares = [], set()
        for f in job.last_plan:          # one file per square in flight
            if f.due and f.square not in squares:
                squares.add(f.square)
                due.append(f)
        order_ok.append(job.last_dispatched == due[:len(job.last_dispatched)])
        dispatched.extend(job.last_dispatched)

    positions = REPLAY["pos"]
    for i, (t, lat, lon, alt, gs) in enumerate(positions):
        clock.t = t
        xplane.values.update(lat=lat, lon=lon, elev_m=alt, gs_ms=gs)
        reset_ids(i)
        job.tick()
        check_order()
        _settle(job)
    job._harvest(clock.t)
    stop.set()
    watcher.join(5)
    job.close()

    assert not broken, broken[:5]
    assert all(order_ok)
    assert job.reader.resets == 1
    assert job.counts["landed"] >= 20
    # what started, landed, in the order it started (slots > 1 run the
    # stub concurrently, so its own call order may interleave)
    assert [(f.square, f.tier) for f in dispatched] == [
        (lnd["square"], lnd["tier"]) for lnd in job.landings]
    assert sorted(lander.calls) == sorted(
        (lnd["square"].split("/", 1)[1], lnd["tier"]) for lnd in job.landings)
    # each square only ever climbs, and lands at most one file per tier
    seen = {}
    for lnd in job.landings:
        assert lnd["tier"] > seen.get(lnd["square"], 0)
        seen[lnd["square"]] = lnd["tier"]
    # the index knows what landed
    conn = INDEX.open_index(index_path)
    upgraded = INDEX.rows(conn, state="upgraded")
    assert len(upgraded) == len(seen)
    assert not INDEX.rows(conn, state="upgrading")
    assert any(r["last_near_at"] for r in INDEX.rows(conn))
    conn.close()
    assert isinstance(events[-1], ImageryFollowStatus)
    assert events[-1].state == "stopped" and events[-1].flight_loads == 1
    assert (tmp_path / "od.log").read_text(encoding="utf-8").count(
        "square=") == job.counts["landed"]


def test_no_fetch_starts_while_a_build_runs(xplane, tmp_path):
    building = {"on": False}
    job, events, clock, lander, _t, _i = _job(
        xplane, tmp_path, busy=lambda: building["on"])
    job.open()
    positions = REPLAY["pos"]
    _fly(job, xplane, clock, positions[:60])
    before = len(lander.calls)
    building["on"] = True
    _fly(job, xplane, clock, positions[60:200])
    assert len(lander.calls) == before
    assert job.state == "paused" and "build" in job.reason
    assert any(e.state == "paused" for e in events)
    building["on"] = False
    with FOLLOW.paused("library_delete"):
        _fly(job, xplane, clock, positions[200:220])
        assert len(lander.calls) == before
    assert FOLLOW.pause_count() == 0
    _fly(job, xplane, clock, positions[220:])
    assert len(lander.calls) > before
    job.close()


def test_landings_over_110_percent_of_the_cap_start_a_sweep(xplane, tmp_path,
                                                           monkeypatch):
    from o4_engine import imagery_downgrade as DOWN
    calls = []

    def sweep(conn, cap, *, camera=None, in_session=False, now=None,
              abort=None):
        calls.append((getattr(cap, "cap", cap), in_session, camera is not None))
        return {"ran": True, "downgraded": 0}

    monkeypatch.setattr(DOWN, "sweep", sweep)
    job, _e, clock, _l, _t, _i = _job(xplane, tmp_path, cap_bytes=5000)
    job.open()
    _fly(job, xplane, clock, REPLAY["pos"][:200])
    assert job.counts["landed"] > 0
    assert calls and all(c == (5000, True, True) for c in calls)
    assert len(calls) <= 200 / FOLLOW.SWEEP_EVERY_S + 1
    job.close()


def test_failures_mark_failed_and_offline_pauses(xplane, tmp_path):
    names = {n for n, *_ in REPLAY["squares"]}
    lander = FakeLander(fail=names)             # the provider refuses all
    job, events, clock, _l, _t, index_path = _job(xplane, tmp_path,
                                                  lander=lander)
    job.open()
    _fly(job, xplane, clock, REPLAY["pos"][:120])
    assert job.counts["failed"] >= FOLLOW.OFFLINE_AFTER
    assert any(e.reason.startswith("Offline") for e in events)
    assert job.counts["landed"] == 0
    job.close()


def test_waiting_without_x_plane_then_a_clean_threaded_stop(tmp_path):
    index_path, _textures = _index_rows(tmp_path)
    events = []
    job = FOLLOW.FollowJob(
        events.append, lander=FakeLander(), index_path=index_path,
        reader=WEBAPI.PositionReader(WEBAPI.base_url(9, "127.0.0.1"),
                                     timeout=0.2),
        period_s=0.05).start()
    deadline = time.time() + 5
    while not any(e.state == "waiting" for e in events):
        assert time.time() < deadline, "TIMED_OUT"
        time.sleep(0.02)
    counts = job.stop(timeout=5)
    assert not job.running and counts["state"] == "stopped"
    assert events[-1].state == "stopped"


def test_the_commands_start_one_job_and_stop_it(tmp_path, monkeypatch):
    from o4_engine import imagery_commands as CMDS
    index_path, _textures = _index_rows(tmp_path)
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda relative: str(tmp_path / "data" / relative))
    events = []
    first = CMDS.start_imagery_follow(events.append, port=9,
                                      index_path=index_path)
    assert first == {"status": "started"}
    assert CMDS.start_imagery_follow(events.append, port=9,
                                     index_path=index_path) == {
        "status": "running"}
    stopped = CMDS.stop_imagery_follow()
    assert stopped["status"] == "stopped"
    assert CMDS.stop_imagery_follow() == {"status": "idle"}


def test_the_status_event_carries_the_wire_fields():
    event = ImageryFollowStatus(state="following", slots=2, buffer_s=12.5)
    assert type(event).__name__ == "ImageryFollowStatus"
    from o4_engine.events import CAPABILITIES
    assert "imagery_follow" in CAPABILITIES
    kit = Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
    client = (kit / "OrthoEngineClient.swift").read_text(encoding="utf-8")
    assert 'case "ImageryFollowStatus":' in client
    assert '"imagery_follow_start"' in client
    assert '"imagery_follow_stop"' in client
    parse = (kit / "ImageryFollowStatus.swift").read_text(encoding="utf-8")
    import dataclasses
    for field in dataclasses.fields(ImageryFollowStatus):
        if field.name not in ("seq", "ts"):
            assert f'"{field.name}"' in parse, field.name


# --- tier zoom in download and convert ------------------------------------

PROVIDER = "FAKETIER"
TEXTURE = (35552, 18752)


@pytest.fixture()
def tier_build(monkeypatch, tmp_path):
    provider = {"code": PROVIDER, "grid_type": "webmercator",
                "imagery_dir": "normal", "color_filters": "none"}
    monkeypatch.setitem(IMG.providers_dict, PROVIDER, provider)
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    monkeypatch.setattr(FNAMES, "data_path",
                        lambda relative: str(tmp_path / "data" / relative))
    calls, stored = [], []

    def fake_tilbox(tilbox, zoomlevel, provider_, progress=None):
        calls.append((list(tilbox), zoomlevel))
        side = 256 * (tilbox[2] - tilbox[0])
        return True, Image.new("RGB", (side, side), (90, 120, 60))

    monkeypatch.setattr(IMG, "build_texture_from_tilbox", fake_tilbox)
    monkeypatch.setattr(DDSCACHE, "store",
                        lambda key, final: stored.append(key))
    build_dir = tmp_path / "build"
    (build_dir / "textures").mkdir(parents=True)
    tile = types.SimpleNamespace(
        lat=60, lon=-136, build_dir=str(build_dir), mask_zl=14,
        default_zl=16, default_website=PROVIDER, texture_mode="full_ortho",
        imagery_on_demand=True, placeholder_zl_drop=3,
        imprint_masks_to_dds=False, sea_nodata_fill=False,
        color_harmonization=False)
    return tile, calls, stored


def test_a_2048_tier_is_fetched_at_its_zoom_and_stored_nowhere(tier_build):
    tile, calls, stored = tier_build
    attrs = (*TEXTURE, 16, PROVIDER)
    assert IMG.build_jpeg_ortho(tile, *attrs, drop=1) == 1
    x15, y15 = TEXTURE[0] // 2, TEXTURE[1] // 2
    assert calls == [([x15, y15, x15 + 8, y15 + 8], 15)]     # 64 requests
    IMG.convert_texture(tile, *attrs, drop=1)
    final = os.path.join(tile.build_dir, "textures",
                         FNAMES.dds_file_name_from_attributes(*attrs))
    assert TIERS.texture_header(final) == (2048, "bc1")
    assert DDS.is_whole(final) and stored == []
    kept = os.path.join(FNAMES.data_path("Imagery_on_demand"), "placeholders")
    assert not os.path.exists(kept)


def test_the_full_tier_of_an_on_demand_tile_enters_the_dds_cache(tier_build):
    tile, calls, stored = tier_build
    attrs = (*TEXTURE, 16, PROVIDER)
    assert IMG.build_jpeg_ortho(tile, *attrs, drop=0) == 1
    assert calls == [([*TEXTURE, TEXTURE[0] + 16, TEXTURE[1] + 16], 16)]
    IMG.convert_texture(tile, *attrs, drop=0)
    final = os.path.join(tile.build_dir, "textures",
                         FNAMES.dds_file_name_from_attributes(*attrs))
    assert TIERS.texture_header(final)[0] == 4096
    assert len(stored) == 1


def test_the_lander_lands_a_tier_and_reports_its_facts(tier_build,
                                                       monkeypatch):
    from o4_engine import imagery_follow_land as LAND
    tile, _calls, _stored = tier_build
    lander = LAND.TierLander()
    monkeypatch.setattr(lander, "_tile", lambda row: tile)
    name = FNAMES.dds_file_name_from_attributes(*TEXTURE, 16, PROVIDER)
    row = {"tile": TILE, "name": name, "zl": 16, "provider": PROVIDER,
           "build_dir": tile.build_dir, "dds_cache_key": None}
    assert LAND.texture_corner(name) == TEXTURE
    facts = lander(row, 1)
    assert facts["tier_px"] == 1024 and facts["network"]
    assert facts["full_bytes"] > 0 and facts["jpeg_path"].endswith(".jpg")


# --- the Terminal shell (tools/imagery_follow.py) --------------------------


def test_the_terminal_shell_names_tiles_and_prints_a_status_line():
    import importlib.util
    path = Path(__file__).resolve().parent.parent / "tools" / "imagery_follow.py"
    spec = importlib.util.spec_from_file_location("imagery_follow_tool", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.tile_of("/x/zOrtho4XP_+60-136") == (60, -136)
    assert tool.tile_of("/x/custom", "-05+012") == (-5, 12)
    with pytest.raises(SystemExit):
        tool.tile_of("/x/custom")
    text = tool.line(ImageryFollowStatus(state="paused", reason="Offline",
                                         slots=2, buffer_s=-1.0))
    assert "paused" in text and "buffer     -" in text and "(Offline)" in text
