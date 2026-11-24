"""Imagery downloads independent of the build step (#2254).

A tile's imagery job takes a token late, downloads through the solve, mesh
and masks, and the imagery step reuses every file.  The transfers are real
HTTP against a loopback imagery server; the build steps are simulated.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Imagery_Async as FETCH_ASYNC
import O4_Imagery_Plan as PLAN
import O4_Imagery_Prefetch as PREFETCH
import O4_Imagery_Utils as IMG
import O4_Machine_Slots as SLOTS
import O4_UI_Utils as UI
import pytest
from o4_engine import parallel
from o4_engine.events import ImageryJobDone
from o4_engine.session import EngineSession
from PIL import Image
from shapely.geometry import MultiPolygon, box

LAT, LON = 45, 7
ZOOM = 16
MESH_ZL = 18
CODE = "LOCALJOB"


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (256, 256), (40, 90, 60)).save(out, format="JPEG")
    return out.getvalue()


class _Imagery(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.body = _jpeg()
        self.delay = 0.0
        self.lock = threading.Lock()
        self.gets = []                   # (path, arrival time)

    def paths(self):
        with self.lock:
            return [path for path, _ in self.gets]

    def arrivals(self):
        with self.lock:
            return [at for _, at in self.gets]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        with self.server.lock:
            self.server.gets.append((self.path, time.monotonic()))
        if self.server.delay:
            time.sleep(self.server.delay)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(self.server.body)))
        self.end_headers()
        self.wfile.write(self.server.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    imagery = _Imagery()
    thread = threading.Thread(target=imagery.serve_forever, daemon=True)
    thread.start()
    yield imagery
    imagery.shutdown()
    imagery.server_close()
    thread.join(5)


@pytest.fixture
def tile(tmp_path, monkeypatch, server):
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "imagery"))
    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setattr(FETCH_ASYNC, "fetcher_choice", lambda: "threads",
                        raising=False)
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "4")
    monkeypatch.setitem(IMG.providers_dict, CODE, {
        "code": CODE, "imagery_dir": "normal", "request_type": "tms",
        "grid_type": "webmercator", "tile_size": 256, "max_threads": 4,
        "resolutions": {ZOOM: 1.0}, "top_left_corner": {ZOOM: (0.0, 0.0)},
        "url_template": "http://127.0.0.1:%d/{zoom}/{x}/{y}.jpg"
                        % server.server_address[1],
    })
    build_dir = tmp_path / "tile"
    (build_dir / "terrain").mkdir(parents=True)
    (build_dir / "textures").mkdir()
    PREFETCH._JOBS.clear()
    yield SimpleNamespace(lat=LAT, lon=LON, build_dir=str(build_dir),
                          default_website=CODE, default_zl=ZOOM,
                          mesh_zl=MESH_ZL, texture_mode="full_ortho")
    UI.red_flag = True                   # end whatever a failed test left
    for job in list(PREFETCH._JOBS.values()):
        job.stop(10)
    PREFETCH._JOBS.clear()
    UI.red_flag = False


def _textures(count):
    (x0, y0) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, ZOOM)
    return [(x0 + 16 * i, y0, ZOOM, CODE) for i in range(count)]


def _wait(condition, seconds=30.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def _jpegs(tile):
    found = []
    for root, _dirs, names in os.walk(FNAMES.Imagery_dir):
        found += [os.path.join(root, name) for name in names]
    return found


# -- the job runs through the build, the imagery step reuses every file ---
def test_a_late_token_downloads_through_a_long_solve_and_nothing_twice(
        tile, server):
    textures = _textures(3)
    reports = []
    job = PREFETCH.open_job(
        tile, on_done=lambda d, f: reports.append((d, f)), token=False,
        find=lambda _t: [], plan=lambda _t: list(textures), slots=2)
    time.sleep(0.15)                     # the solve runs; no token yet
    assert server.paths() == [], "no request before the token"
    assert job.fetch_airports({}, find=lambda _t, _d: {}) == {}
    solve_began = time.monotonic()
    assert PREFETCH.grant_token(LAT, LON)
    assert _wait(lambda: reports), "the job drains while the solve runs"
    solve_ended = time.monotonic()
    PREFETCH.vector_ended(tile)          # mesh and masks follow
    assert reports == [(3, 0)]
    assert solve_began <= min(server.arrivals())
    assert max(server.arrivals()) <= solve_ended

    PREFETCH.adopt_job(tile)
    before = len(server.paths())
    assert before == 3 * 16 * 16
    for texture in textures:             # the imagery step
        assert IMG.build_jpeg_ortho(tile, *texture) == 1
    assert len(server.paths()) == before, "no second GET"
    assert len(set(server.paths())) == before, "each part asked for once"
    PREFETCH.end_job(tile, used=set(textures))
    assert PREFETCH._JOBS == {}


def test_the_imagery_step_joins_an_orthophoto_in_flight(tile, server):
    server.delay = 0.02
    (texture,) = _textures(1)
    job = PREFETCH.open_job(tile, find=lambda _t: [texture], plan=None,
                            slots=1)
    assert _wait(lambda: len(server.paths()) > 0)
    PREFETCH.adopt_job(tile)             # still in flight
    assert IMG.build_jpeg_ortho(tile, *texture) == 1
    assert len(server.paths()) == 16 * 16, "joined, not requested again"
    assert len(set(server.paths())) == 16 * 16
    for thread in job._threads:
        thread.join(10)
    PREFETCH.end_job(tile, used={texture})


def test_a_flight_hold_stops_the_job_and_its_own_request_goes_first(
        tile, server, monkeypatch):
    monkeypatch.setattr(SLOTS, "FLIGHT_HOLD_TTL_S", 0.4)
    server.delay = 0.02
    PREFETCH.open_job(tile, find=lambda _t: _textures(4), plan=None, slots=1)
    assert _wait(lambda: len(server.paths()) > 4)
    until = time.monotonic() + 1.0
    SLOTS.hold_net_for_flight()
    time.sleep(0.25)                     # what already held a slot lands
    held_from = time.monotonic()
    while time.monotonic() < until:
        SLOTS.hold_net_for_flight()
        time.sleep(0.05)
    held_to = time.monotonic()
    during = [at for at in server.arrivals() if held_from <= at < held_to]
    assert during == [], "the job makes no request under a flight hold"
    name = SLOTS.net_class("127.0.0.1:%d" % server.server_address[1])
    SLOTS.hold_net_for_flight()
    assert SLOTS.try_take_class(name, 1, 64).count == 0
    with SLOTS.net_priority():
        got = SLOTS.try_take_class(name, 1, 64)
    assert got.count == 1, "the flight's request is admitted"
    got.release()
    time.sleep(0.45)                     # the hold lapses by itself
    resumed_from = len(server.paths())
    assert _wait(lambda: len(server.paths()) > resumed_from), "it resumes"
    # ~1,000 real loopback GETs: ~17 s on an idle machine, past 30 s on a
    # loaded CI runner (run 45270210136), so the drain gets its own clock
    assert _wait(lambda: len(server.paths()) == 4 * 16 * 16, 180), \
        "it finishes the job"


def test_stop_leaves_no_temporaries(tile, server):
    server.delay = 0.01
    job = PREFETCH.open_job(tile, find=lambda _t: _textures(3), plan=None,
                            slots=2)
    assert _wait(lambda: len(server.paths()) > 8)
    UI.red_flag = True
    PREFETCH.end_job(tile)
    assert not any(thread.is_alive() for thread in job._threads)
    left = [p for p in _jpegs(tile)
            if not p.endswith(".jpg") or ".part" in p or ".tmp" in p]
    assert left == []
    for path in _jpegs(tile):
        with Image.open(path) as whole:
            whole.load()                 # a kept orthophoto is whole
    UI.red_flag = False


def test_a_job_downloads_as_many_at_once_as_the_imagery_step(tile,
                                                             monkeypatch):
    import O4_Tile_Utils as TILE
    monkeypatch.setattr(TILE, "max_download_slots", 0)     # Auto
    barrier = threading.Barrier(2, timeout=5)
    seen = []

    def fetch(_tile, texture):
        barrier.wait()
        seen.append(texture)
        return 1

    job = PREFETCH.open_job(tile, fetch=fetch, find=lambda _t: _textures(4),
                            plan=None)
    assert _wait(lambda: len(seen) == 4)
    assert job.failed == 0


def test_unused_orthophotos_are_counted(tile):
    textures = _textures(5)
    job = PREFETCH.Prefetch(tile, [], token=False)
    job.fetched = set(textures)
    assert job.report_unused(set(textures[:4])) == 1
    assert PLAN.unused(textures, textures[:4]) == [textures[4]]


# -- the plan ---------------------------------------------------------------
def _dico(tile, count=4):
    (x0, y0) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, MESH_ZL)
    x0, y0 = x0 - x0 % 64, y0 - y0 % 64
    dico = {}
    for i in range(count):
        for dx in range(0, 64, 16):
            for dy in range(0, 64, 16):
                dico[(x0 + 64 * i + dx, y0 + dy)] = (
                    (x0 + 64 * i) // 4, y0 // 4, ZOOM, CODE)
    return dico


def _block_box(x, y, zoom=MESH_ZL, size=16):
    (north, west) = GEO.gtile_to_wgs84(x, y, zoom)
    (south, east) = GEO.gtile_to_wgs84(x + size, y + size, zoom)
    return box(west - LON, south - LAT, east - LON, north - LAT)


def test_a_texture_wholly_under_masked_water_is_not_predicted(tile):
    dico = _dico(tile)
    textures = sorted(set(dico.values()))
    (x, y, _, _) = textures[1]
    sea = MultiPolygon([_block_box(x * 4, y * 4, size=64).buffer(1e-6)])
    found = PLAN.predicted_textures(tile, IMG, dico, sea)
    assert textures[1] not in found
    assert sorted(found) == [t for t in textures if t != textures[1]]


def test_one_dry_block_keeps_its_texture(tile):
    dico = _dico(tile, 1)
    (block_x, block_y) = min(dico)
    sea = _block_box(block_x, block_y, size=64).difference(
        _block_box(block_x, block_y))
    found = PLAN.predicted_textures(tile, IMG, dico, MultiPolygon([sea]))
    assert found == sorted(set(dico.values()))


def test_a_dry_tile_predicts_every_assigned_texture(tile):
    dico = _dico(tile)
    found = PLAN.predicted_textures(tile, IMG, dico, MultiPolygon())
    assert sorted(found) == sorted(set(dico.values()))


@pytest.mark.parametrize("mode", ["default_xplane", "airport_ortho"])
def test_a_mode_without_a_whole_tile_of_photos_predicts_nothing(tile, mode):
    tile.texture_mode = mode
    assert PLAN.predicted_textures(tile, IMG, {}, MultiPolygon()) == []


def test_the_plan_waits_for_its_layers(tile):
    tile.cover_airports_with_highres = "False"
    assert PLAN.predicted_textures(tile) is None


def test_a_tile_with_a_last_build_keeps_its_own_list(tile):
    texture = _textures(1)[0]
    name = FNAMES.dds_file_name_from_attributes(*texture)[:-4] + ".ter"
    open(os.path.join(tile.build_dir, "terrain", name), "w",
         encoding="utf-8", newline="\n").close()
    asked = []
    assert PREFETCH._first_build_plan(
        tile, IMG, predict=lambda t: asked.append(t) or []) == []
    assert asked == []


def test_a_first_build_drops_what_is_already_here(tile):
    (built, cached, wanted) = _textures(3)
    open(os.path.join(tile.build_dir, "textures",
                      FNAMES.dds_file_name_from_attributes(*built)),
         "w", encoding="utf-8", newline="\n").close()
    (folder, name, _drop) = IMG.imagery_step_source(tile, *cached)
    os.makedirs(folder)
    open(os.path.join(folder, name), "w", encoding="utf-8",
         newline="\n").close()
    assert PREFETCH._first_build_plan(
        tile, IMG, predict=lambda _t: [built, cached, wanted]) == [wanted]


def test_the_plan_waits_for_the_airports_before_it_reads(tile):
    asked = threading.Event()

    def plan(_tile):
        asked.set()
        return []

    job = PREFETCH.open_job(tile, find=lambda _t: [], plan=plan)
    assert not asked.wait(0.15), "the airports file may be half written"
    job.vector_ended()
    assert asked.wait(5)


# -- the parent owns the tokens ---------------------------------------------
class _Child:
    def __init__(self):
        self.tile = None
        self.running_step = None
        self.step_class = None
        self.autopatch_pending = None
        self.step_failed = False
        self.cancelling = False
        self.retired = False
        self.arguments = []
        self.sent = []

    def start_step(self, step_key, build_arguments):
        self.running_step = step_key
        self.arguments.append(build_arguments)
        return True

    def send(self, payload):
        self.sent.append(payload)
        return True

    def retire(self):
        self.retired = True

    def await_stderr_drained(self):
        pass

    def crash_detail(self):
        return "build worker exited unexpectedly"


def _run(tiles, imagery_busy=0):
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None,
                        with_paid_rebuilds=lambda built: built,
                        _announce_rebuild_pending=lambda cancelled: None),
        tiles, "P", 16, "", (True, True, False), len(tiles))
    run._class_active["imagery"] = imagery_busy
    run._maybe_finish = lambda: None     # the run's end reaps real processes
    children = [_Child() for _ in tiles]
    run._children = list(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
    return run, children


def _report(run, child, tile=None, event="ImageryJobDone"):
    (lat, lon) = tile or child.tile
    run._on_child_event(child, {"event": event, "lat": lat, "lon": lon,
                                "downloaded": 1, "failed": 0})


def test_a_freed_token_goes_to_a_job_that_waits():
    limit = parallel.class_limits(1)["imagery"]
    run, (child,) = _run([(40, 1)], imagery_busy=limit)
    assert child.arguments[0]["token_lent"] is False
    assert not child.sent
    with run._lock:
        run._class_active["imagery"] = limit - 1
        run._dispatch_locked()
    assert child.sent == [{"cmd": "imagery_token", "lat": 40, "lon": 1}]
    assert child.prefetch_token and run._class_active["imagery"] == limit
    with run._lock:
        run._dispatch_locked()
    assert len(child.sent) == 1, "one token per job"
    _report(run, child)
    assert not child.prefetch_token
    assert run._class_active["imagery"] == limit - 1
    with run._lock:
        run._dispatch_locked()
    assert len(child.sent) == 1, "a job that reported takes no other"


def test_the_token_survives_the_steps_until_the_imagery_step():
    run, (child,) = _run([(41, 1)])
    assert child.prefetch_token
    run._on_child_event(child, {"event": "RunDone"})
    assert child.running_step == "mesh"
    assert child.prefetch_token and run._class_active["imagery"] == 1
    run._on_child_event(child, {"event": "RunDone"})
    run._on_child_event(child, {"event": "RunDone"})
    assert child.running_step == "imagery"
    assert not child.imagery_job_open, "the step adopts the job"
    assert not child.prefetch_token, "its token came back at the dispatch"
    _report(run, child)                  # the adopted job's late report
    assert child.step_class == "imagery", "that was not the step's own drain"
    _report(run, child, event="ImageryDownloadsDone")
    assert child.step_class == parallel.IMAGERY_TAIL_CLASS


def test_a_report_about_another_tile_changes_nothing():
    run, (child,) = _run([(42, 1)])
    _report(run, child, tile=(42, 2))
    assert child.prefetch_token and run._class_active["imagery"] == 1


def test_a_tile_that_leaves_returns_its_token():
    run, (child,) = _run([(43, 1)])
    child.step_failed = True
    run._on_child_event(child, {"event": "RunDone"})
    assert child.tile is None and not child.prefetch_token
    assert run._class_active["imagery"] == 0


# -- the worker's side ------------------------------------------------------
def test_a_token_with_no_job_to_use_it_comes_straight_back(monkeypatch):
    PREFETCH._JOBS.clear()
    monkeypatch.setenv(SLOTS.ENV_BUILD_WORKER, "1")
    session = EngineSession()
    events = []
    session.subscribe(events.append)
    assert session.imagery_token(44, 1) is True
    done = [e for e in events if isinstance(e, ImageryJobDone)]
    assert [(e.lat, e.lon, e.downloaded) for e in done] == [(44, 1, 0)]


def _plan(*keys):
    return [(key, 0.0, 1.0) for key in keys]


def test_the_job_outlives_the_vector_step_and_ends_at_the_imagery_step(
        tile, monkeypatch):
    original = PREFETCH.open_job
    monkeypatch.setattr(
        PREFETCH, "open_job",
        lambda t, on_done=None, token=True: original(
            t, on_done=on_done, token=token, find=lambda _t: [], plan=None))
    session = EngineSession()
    session._prefetch_imagery = True
    plan = _plan("vector", "mesh", "imagery")
    assert session._run_step(lambda t: 1, "vector", tile, plan) == 1
    assert (LAT, LON) in PREFETCH._JOBS
    assert session._run_step(lambda t: 1, "mesh", tile, plan) == 1
    assert (LAT, LON) in PREFETCH._JOBS
    assert session._run_step(lambda t: 1, "imagery", tile, plan) == 1
    assert (LAT, LON) not in PREFETCH._JOBS


@pytest.mark.parametrize("failure", ["returns", "raises"])
def test_a_failed_step_ends_the_job(tile, monkeypatch, failure):
    original = PREFETCH.open_job
    monkeypatch.setattr(
        PREFETCH, "open_job",
        lambda t, on_done=None, token=True: original(
            t, on_done=on_done, token=token, find=lambda _t: [], plan=None))
    session = EngineSession()
    session._prefetch_imagery = True
    plan = _plan("vector", "mesh", "imagery")
    session._run_step(lambda t: 1, "vector", tile, plan)

    def step(_tile):
        if failure == "raises":
            raise RuntimeError("mesh failed")
        return 0

    if failure == "raises":
        with pytest.raises(RuntimeError):
            session._run_step(step, "mesh", tile, plan)
    else:
        session._run_step(step, "mesh", tile, plan)
    assert (LAT, LON) not in PREFETCH._JOBS
