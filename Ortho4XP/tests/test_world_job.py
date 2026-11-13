"""Twin of build-ahead in track mode (``src/o4_engine/world_job.py``,
``world_job_run.py``) and of the swap rules it adds (S3 with the 60 s
margin, S5 merge swap, S7 follow hold); flight manager / World spec
2026-11-10 §7.5, §8.5, §10, §15.  All offline, on ``tmp_path``."""
from __future__ import annotations

import os
import shutil
import time

import O4_World_Pack as WP
import pytest
from o4_engine import imagery_follow as FOLLOW
from o4_engine import world_commands as WORLD
from o4_engine import world_job as JOB
from o4_engine import world_job_run as RUN
from o4_engine import world_publish as PUBLISH
from o4_engine.events import BuildDone

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE_DSF = os.path.join(HERE, "fixtures", "mesh_dsf", "full_ortho.dsf")
CYYR = (53.30427, -60.447077)


class Builder:
    def __init__(self, refuse=()):
        self.started, self.finished, self.refuse = [], [], set(refuse)

    def start(self, tile, kind, deadline_in_s, klass):
        if tile in self.refuse:
            return False
        self.started.append((tile, kind, round(deadline_in_s), klass))
        return True

    def poll(self, now):
        done, self.finished = self.finished, []
        return done


class Publisher:
    def __init__(self):
        self.calls = []

    def settle(self, tile, kind, held):
        self.calls.append((tile, held))
        return "staged" if held else "swapped"


def _job(wanted=lambda tile: True, **kw):
    builder, publisher = Builder(), Publisher()
    job = JOB.WorldJob(builder=builder, publisher=publisher, wanted=wanted,
                       **kw)
    return job, builder, publisher


def _west(job, t0, t1, lat=53.3, lon=-60.45, gs=150.0):
    """Fly west along ``lat`` at ``gs`` from ``t0`` to ``t1`` (at ``lon``
    at time 0)."""
    m_per_deg = 111_320.0 * 0.5976
    for t in range(t0, t1):
        job.tick(float(t), {"lat": lat, "lon": lon - gs * t / m_per_deg})


def test_parked_the_ring_is_built_nearest_first_on_the_parked_slots():
    job, builder, _ = _job(capacity=4)              # parked: 4 - 2 = 2
    job.flight_loaded(*CYYR)
    for t in range(3):
        job.tick(float(t), {"lat": CYYR[0], "lon": CYYR[1]})
    assert [s[0][1] for s in builder.started] == [-63, -63]
    assert all(s[1:] == ("drape", s[2], "P1") for s in builder.started)
    status = job.status(2.0)
    assert status["state"] == "building" and status["slots"] == 2
    assert status["queue"] == len(job.jobs) - 2
    assert [row[1:3] for row in status["building"]] == [["drape", "building"]] * 2
    # The map's rows (WorldStatus.jobs): FlightStatus.jobs' shape.
    rows = {tuple(r[0]): r[1:] for r in status["jobs"]}
    assert len(rows) == len(job.jobs)
    assert rows[builder.started[0][0]] == ["ahead", "drape", "building"]
    assert {r[3] for r in status["jobs"]} == {"building", "queued"}


def test_flying_the_job_builds_the_column_ahead_by_its_deadline():
    """Westbound at 150 m/s from lon -60.45: column -064 enters at lon
    -61.65, 80 km (533 s) on; its deadline is that less 60 s and the
    swap.  (A 2,000 s tile so the column is in the horizon at once.)"""
    job, builder, _ = _job(wanted=lambda tile: tile[1] == -64, cores=18,
                           capacity=16, estimate_s={"drape": 300.0})
    job.flight_loaded(53.3, -60.45)
    _west(job, 0, 12)
    started = {s[0]: s[2] for s in builder.started}
    assert set(started) == {(52, -64), (53, -64), (54, -64)}
    assert all(460 <= d <= 475 for d in started.values()), started
    assert job.slots() == 3 and job.gs_ms == pytest.approx(150, rel=0.02)


def test_a_tile_that_cannot_be_built_in_time_is_late_and_not_started():
    job, builder, _ = _job(wanted=lambda tile: tile[1] == -64, cores=18,
                           estimate_s={"drape": 2000.0})
    job.flight_loaded(53.3, -60.45)
    _west(job, 0, 12)
    assert not builder.started
    assert {j.state for j in job.jobs.values()} == {"late"}
    assert "faster than tiles can be built" in job.reason
    drape, builder, _ = _job(wanted=lambda tile: tile[1] == -64, cores=18,
                             kind="drape", estimate_s={"drape": 37.0})
    drape.flight_loaded(53.3, -60.45)
    _west(drape, 0, 12)
    assert not builder.started                      # beyond its horizon yet
    _west(drape, 12, 60)
    assert len(builder.started) == 3 and builder.started[0][1] == "drape"


def test_a_failed_build_is_tried_twice_never_a_third_time():
    job, builder, _ = _job(capacity=3)              # one parked slot
    job.flight_loaded(*CYYR)
    job.tick(0.0, {"lat": CYYR[0], "lon": CYYR[1]})
    tile = builder.started[-1][0]
    for t in (1.0, 2.0):
        builder.finished.append((tile, False))
        job.tick(t, {"lat": CYYR[0], "lon": CYYR[1]})
    assert job.jobs[tile].state == "failed" and job.jobs[tile].attempts == 2
    assert [s[0] for s in builder.started].count(tile) == 2


def test_s3_a_tile_in_or_near_the_window_or_witnessed_is_held():
    loads = set()
    job, _b, _p = _job(loads=lambda: set(loads))
    job.flight_loaded(*CYYR)
    job.tick(0.0, {"lat": CYYR[0], "lon": CYYR[1]})
    assert job.held((53, -60))                      # in the window
    assert job.held((53, -63)) is False             # 13.6 km out, parked
    assert job.held((55, -66)) is False
    loads.add((55, -66))
    job.tick(1.0, {"lat": CYYR[0], "lon": CYYR[1]})
    assert job.held((55, -66))                      # the witness says loaded


def test_finished_tiles_swap_when_s3_allows_spaced_unless_urgent():
    job, builder, publisher = _job(capacity=16)
    job.flight_loaded(*CYYR)
    job.tick(0.0, {"lat": CYYR[0], "lon": CYYR[1]})
    far = [s[0] for s in builder.started if s[0][0] == 55][:2]
    builder.finished += [(tile, True) for tile in far]
    job.tick(1.0, {"lat": CYYR[0], "lon": CYYR[1]})
    states = sorted(job.jobs[t].state for t in far)
    assert states == ["staged", "swapped"]          # one swap per 10 s
    job.tick(11.5, {"lat": CYYR[0], "lon": CYYR[1]})
    assert {job.jobs[t].state for t in far} == {"swapped"}
    assert job.status(12.0)["last_swap"][1] == "drape"
    assert len(job.swaps) == 2 and job.swaps[1][1] - job.swaps[0][1] >= 10


def test_a_flight_load_elsewhere_forgets_the_window():
    job, _b, _p = _job()
    job.flight_loaded(*CYYR)
    job.forget_window()
    assert not job.tracker.cols and job.motion.motion() is None


def test_a_jump_forgets_the_window():
    job, _b, _p = _job()
    job.flight_loaded(*CYYR)
    job.tick(0.0, {"lat": CYYR[0], "lon": CYYR[1]})
    job.tick(1.0, {"lat": 47.0, "lon": 8.0})        # 1,000 km in a second
    assert job.motion.jumps == 1
    assert job.tracker.cols == {7, 8} or job.tracker.cols == {8}


# -- the engine side ---------------------------------------------------


@pytest.fixture
def pack(tmp_path, monkeypatch):
    scenery = tmp_path / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    (pack / "Earth nav data").mkdir(parents=True)
    staging = tmp_path / "World_staging"
    monkeypatch.setattr(WORLD, "staging_root", lambda: str(staging))
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    WP.write_placeholder(str(pack), 53, -64)
    return str(scenery), str(pack), str(staging)


def _stage(staging, lat, lon, names=("a.ter",), dsf=FIXTURE_DSF):
    tile = WP.tile_name(lat, lon)
    root = os.path.join(staging, tile)
    for sub in ("terrain", "textures"):
        os.makedirs(os.path.join(root, sub, tile), exist_ok=True)
    for name in names:
        sub = "terrain" if name.endswith(".ter") else "textures"
        with open(os.path.join(root, sub, tile, name), "w", encoding="utf-8",
                  newline="\n") as h:
            h.write(name + "@" + os.path.basename(staging))
    dest = os.path.join(root, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(dsf, dest)
    return root


def test_the_publisher_swaps_a_staged_tile_holding_only_its_follow(pack,
                                                                  monkeypatch):
    scenery, path, staging = pack
    after, held_during = [], []
    monkeypatch.setattr(PUBLISH, "_after_swap",
                        lambda *a: after.append(a[2:]))
    swap = WP.swap_staged

    def watched(*a, **kw):
        held_during.append(FOLLOW.held_tiles())
        return swap(*a, **kw)
    monkeypatch.setattr(WP, "swap_staged", watched)
    clock = {"t": 0.0}
    pub = RUN._PackPublisher(scenery, lambda lat, lon: "/build",
                            clock=lambda: clock["t"])
    assert pub.settle((53, -64), "light", held=False) == "pending"
    clock["t"] = RUN.PENDING_S + 1
    assert pub.settle((53, -64), "light", held=False) == "failed"
    _stage(staging, 53, -64)
    assert pub.settle((53, -64), "light", held=True) == "staged"
    assert WP.is_placeholder(os.path.join(path, WP.dsf_relpath(53, -64)))
    assert pub.settle((53, -64), "light", held=False) == "swapped"
    assert not WP.is_placeholder(os.path.join(path, WP.dsf_relpath(53, -64)))
    assert held_during == [{"+53-064"}] and after == [(53, -64)]
    assert FOLLOW.held_tiles() == set()
    assert pub.settle((53, -64), "light", held=True) == "swapped"


def test_s5_a_merge_swap_never_removes_a_name(pack):
    _scenery, path, staging = pack
    tile = "+53-064"
    first = _stage(staging + "1", 53, -64, names=("a.ter", "x.dds"))
    WP.swap_in(path, first, 53, -64)
    texture = os.path.join(path, "textures", tile, "x.dds")
    held_open = open(texture, encoding="utf-8")   # X-Plane maps it
    second = _stage(staging + "2", 53, -64, names=("a.ter", "y.dds"))
    done = WP.swap_in(path, second, 53, -64, merge=True)
    assert os.path.isfile(texture)                  # the old name stays
    assert done["stale"] == [os.path.join("textures", tile, "x.dds")]
    with open(os.path.join(path, "terrain", tile, "a.ter"),
              encoding="utf-8") as h:
        assert h.read().endswith("2")               # replaced in one rename
    assert os.path.isfile(os.path.join(path, "textures", tile, "y.dds"))
    assert held_open.read().startswith("x.dds")
    held_open.close()
    assert WP._remove_stale(path, done["stale"]) == 1
    assert not os.path.exists(texture)


class CoreBuilder(Builder):
    """``Builder`` that records a drape's ``core``."""

    def start(self, tile, kind, deadline_in_s, klass, core=None):
        if not super().start(tile, kind, deadline_in_s, klass):
            return False
        self.started[-1] += (core,)
        return True


class MergePublisher(Publisher):
    def settle(self, tile, kind, held, merge=False, fresh=False):
        self.calls.append((tile, held, merge))
        return "staged" if held else "swapped"


CYWG = (49.9100, -97.2399)                 # on +49-098, a placeholder


def _parked_job(kinds):
    builder, publisher = CoreBuilder(), MergePublisher()
    job = JOB.WorldJob(builder=builder, publisher=publisher,
                       wanted=lambda tile: kinds.get(tile) == "placeholder",
                       kind_of=kinds.get, loads=lambda: {(49, -98)},
                       capacity=4)
    job.flight_loaded(*CYWG)
    return job, builder, publisher


def test_a_parked_aircraft_gets_its_own_held_tile_with_its_core():
    """RULINGS 2026-11-12c (3), the owner's CYWG case (#2019): parked on
    +49-098, a placeholder X-Plane has loaded.  The ring leaves held tiles
    out, but the aircraft's own tile is built at once (P0, deadline now)
    as a drape with its core at the aircraft; it is swapped in although
    X-Plane holds it -- merged (S5) -- and only then; once, not again."""
    kinds = {(49, -98): "placeholder", (49, -97): "placeholder"}
    job, builder, publisher = _parked_job(kinds)
    parked = {"lat": CYWG[0], "lon": CYWG[1], "agl_m": 0.4}
    job.tick(0.0, parked)
    own = [s for s in builder.started if s[0] == (49, -98)]
    assert own and own[0][1:4] == ("drape", 0, "P0")
    assert own[0][4] == pytest.approx(CYWG)
    assert builder.started[0][0] == (49, -98)        # first, before the ring
    assert job.held((49, -98))                       # X-Plane holds it
    builder.finished.append(((49, -98), True))
    job.tick(1.0, parked)
    assert ((49, -98), False, True) in publisher.calls   # swapped, merged
    assert job.jobs[(49, -98)].state == "swapped"
    kinds[(49, -98)] = "drape"
    for t in range(2, 6):
        job.tick(float(t), parked)
    assert len([s for s in builder.started if s[0] == (49, -98)]) == 1


def test_a_drape_without_its_core_is_cored_once_and_no_reload_is_sent(
        monkeypatch):
    """Parked on a drape tile: re-draped once with its core; the
    publisher's merge only OFFERS a reload (12c (4))."""
    import O4_XPlane_WebAPI as WEBAPI
    monkeypatch.setattr(WEBAPI, "reload_scenery", lambda base=None: (
        _ for _ in ()).throw(AssertionError("reload without the user")))
    job, builder, _publisher = _parked_job({(49, -98): "drape"})
    job.tick(0.0, {"lat": CYWG[0], "lon": CYWG[1], "agl_m": 0.0})
    assert [s[0] for s in builder.started] == [(49, -98)]
    assert builder.started[0][4] == pytest.approx(CYWG)


def test_here_reports_the_aircrafts_own_tile_as_it_is_built():
    """#2020: ``WorldStatus.here`` -- the aircraft's tile, its pack kind,
    its build with elapsed and estimate, and the core it carries."""
    kinds = {(49, -98): "placeholder", (49, -97): "placeholder"}
    job, builder, _publisher = _parked_job(kinds)
    assert job.status(0.0)["here"] is None            # no position yet
    parked = {"lat": CYWG[0], "lon": CYWG[1], "agl_m": 0.4}
    job.tick(0.0, parked)
    job.tick(30.0, parked)
    here = job.status(30.0)["here"]
    assert here["tile"] == "+49-098" and here["on_ground"]
    assert (here["kind"], here["job"], here["core"]) == (
        "placeholder", "building", True)
    assert here["elapsed_s"] == 30
    assert here["estimate_s"] == round(job.estimate()[1])
    builder.finished.append(((49, -98), True))
    kinds[(49, -98)] = "drape"
    job.tick(31.0, parked)
    here = job.here(31.0)
    assert (here["kind"], here["job"], here["elapsed_s"], here["estimate_s"],
            here["core"]) == ("drape", "swapped", 0, 0, True)


def test_airborne_far_away_nothing_held_is_built():
    """In the air (AGL 3,000 m) over the same tile: no parked exception --
    the held tile is left alone."""
    job, builder, publisher = _parked_job({(49, -98): "placeholder"})
    job.tick(0.0, {"lat": CYWG[0], "lon": CYWG[1], "agl_m": 3000.0})
    assert all(s[0] != (49, -98) for s in builder.started)
    assert job.spawn is None and not publisher.calls


def test_the_merge_swap_offers_a_reload_and_keeps_old_names(pack, monkeypatch):
    """``_PackPublisher.settle(merge=True)``: the held tile merged in (no
    old name removed), staging gone, ``reload_offer`` "tiles"; nothing
    sent."""
    from o4_engine import reload_offer as RELOAD
    monkeypatch.setattr(RELOAD, "_STATE", {"offer": ""})
    sent = []
    monkeypatch.setattr(RELOAD, "send", lambda base=None: sent.append(base))
    scenery, path, staging = pack
    first = _stage(staging + "1", 53, -64, names=("a.ter", "x.dds"))
    WP.swap_in(path, first, 53, -64)
    root = _stage(staging, 53, -64, names=("a.ter", "y.dds"))
    pub = RUN._PackPublisher(scenery, lambda lat, lon: "/build")
    assert pub.settle((53, -64), "drape", False, merge=True,
                      fresh=True) == "swapped"
    assert os.path.isfile(os.path.join(path, "textures", "+53-064", "x.dds"))
    assert os.path.isfile(os.path.join(path, "textures", "+53-064", "y.dds"))
    assert not os.path.exists(root)
    assert RELOAD.current() == "tiles" and sent == []


def test_a_published_session_build_is_a_full_tile(monkeypatch):
    """Drapes never go through the session (RULINGS 2026-11-11j): what
    the session builds is published as ``full``."""
    published = []
    monkeypatch.setattr(PUBLISH, "_publish_built",
                        lambda where, build, lat, lon:
                        published.append((lat, lon)) or {"tile": "t",
                                                         "state": "staged"})
    monkeypatch.setattr(PUBLISH, "_swap_waiting", lambda *a, **k: [])
    monkeypatch.setattr(WORLD, "status_event", lambda *a, **k: None)

    class Session:
        _stepwise_run = False

        def __init__(self):
            self.subscribers = []

        def subscribe(self, callback):
            self.subscribers.append(callback)

        def _emit(self, event):
            pass

        def tile_build_dir(self, lat, lon):
            return "/build"

    session = Session()
    PUBLISH.watch(session, scenery_dir=lambda: "/scenery")
    for lon in (-64, -65):
        session.subscribers[0](BuildDone(lat=53, lon=lon, ok=True))
    deadline = time.time() + 10
    while len(published) < 2 and time.time() < deadline:
        time.sleep(0.02)
    assert published == [(53, -64), (53, -65)]


def test_the_session_builder_queues_a_full_build_by_deadline():
    calls, subscribers, emitted = [], [], []

    class Session:
        def subscribe(self, callback):
            subscribers.append(callback)

        def _emit(self, event):
            emitted.append(event)

        def enqueue_build(self, tiles, provider, zoomlevel, folder, **kw):
            calls.append((tiles, provider, zoomlevel, kw))
            return True

    builder = RUN._SessionBuilder(Session(), "BI", 16)
    before = time.time()
    assert builder.start((53, -64), "full", 600.0, "P1")
    # #2030: the queue notice that gives the build its Activity row
    [notice] = emitted
    assert (type(notice).__name__, notice.lat, notice.lon, notice.state,
            notice.label) == ("TileState", 53, -64, "queued", "queued")
    tiles, provider, zoomlevel, kw = calls[0]
    assert tiles == [(53, -64)] and (provider, zoomlevel) == ("BI", 16)
    assert kw["overrides"] == {"imagery_on_demand": True}
    assert kw["klass"] == "P1"
    assert kw["missing_art"] == "leave"
    assert before + 599 <= kw["deadline"] <= time.time() + 601
    subscribers[0](BuildDone(lat=53, lon=-64, ok=True))
    subscribers[0](BuildDone(lat=10, lon=10, ok=True))   # not the job's
    assert builder.poll(0.0) == [((53, -64), True)] and builder.poll(0.0) == []
    assert not builder.start((53, -65), "drape", 60.0, "P1")   # no drape fn
    assert len(emitted) == 1              # a drape has no row


def test_the_commands_refuse_what_is_not_there(tmp_path, monkeypatch):
    from o4_engine import flight_record as RECORD
    monkeypatch.setattr(RUN, "_settings", lambda: {})
    monkeypatch.setattr(WORLD, "scenery_dir_or_default",
                        lambda scenery_dir="": scenery_dir or str(tmp_path))
    monkeypatch.setattr(RECORD, "flights_dir",
                        lambda data_root=None: str(tmp_path / "Flights"))
    with pytest.raises(ValueError, match="unknown mode"):
        RUN.world_job_start(object(), mode="glide")
    with pytest.raises(ValueError, match="World pack"):       # F1b's mode
        RUN.world_job_start(object(), mode="flight", flight="x",
                            scenery_dir=str(tmp_path))
    assert RUN.world_job_start(object(), scenery_dir=str(tmp_path),
                               if_enabled=True) == {"status": "off"}
    with pytest.raises(ValueError, match="not installed"):
        RUN.world_job_start(object(), scenery_dir=str(tmp_path))
    assert RUN.autostart(object()) == {"status": "off"}
    assert RUN.world_job_stop() == {"status": "stopped", "swapped": 0,
                                    "late": 0}


def test_the_job_runs_in_the_engine_and_reports_world_status(pack,
                                                             monkeypatch):
    """The command starts the job on its thread: positions from the shared
    feed, a parked ring queued through the session, ``WorldStatus`` with
    the job's fields; stop joins it."""
    import O4_Machine_Slots as SLOTS
    from o4_engine import position_feed as FEED

    scenery, path, _staging = pack                  # a placeholder +53-064
    with open(os.path.join(path, WP.MARKER), "w", encoding="utf-8",
              newline="\n") as h:
        h.write("{}")
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: False)
    monkeypatch.setattr(RUN, "_settings", lambda: {"default_website": "BI"})
    monkeypatch.setattr(SLOTS, "session_capacity", lambda: 3)

    class Feed:
        resets = 0

        def read(self):
            return {"lat": CYYR[0], "lon": CYYR[1], "frame_s": 0.02}
    monkeypatch.setattr(FEED, "shared", lambda base=None: Feed())
    events, builds = [], []

    class Session:
        _emit = events.append

        def subscribe(self, callback):
            pass

        def enqueue_build(self, tiles, *args, **kw):
            raise AssertionError("track mode builds drapes, never a session build")

        def tile_build_dir(self, lat, lon):
            return "/build"

    monkeypatch.setattr(RUN, "drape_tile",
                        lambda tile, provider, zl: builds.append(
                            (tile, provider, zl)) or False)
    assert RUN.world_job_start(Session(), scenery_dir=scenery) == {
        "status": "started"}
    assert RUN.world_job_start(Session(), scenery_dir=scenery) == {
        "status": "running"}
    deadline = time.time() + 15
    while not (builds and events) and time.time() < deadline:
        time.sleep(0.1)
    stopped = RUN.world_job_stop()
    assert stopped["status"] == "stopped"
    # The history is unknown (no flight load seen, no witness): the union
    # of the plausible windows holds column -063, so the ring starts at -064.
    assert builds[0] == ((53, -64), "BI", 16)
    status = events[-1]
    assert type(status).__name__ == "WorldStatus" and status.installed is False
    assert status.state == "off"                     # no ini row: the pack's own
