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
    assert all(s[1:] == ("light", s[2], "P1") for s in builder.started)
    status = job.status(2.0)
    assert status["state"] == "building" and status["slots"] == 2
    assert status["queue"] == len(job.jobs) - 2
    assert [row[1:3] for row in status["building"]] == [["light", "building"]] * 2


def test_flying_the_job_builds_the_column_ahead_by_its_deadline():
    """Westbound at 150 m/s from lon -60.45: column -064 enters at lon
    -61.65, 80 km (533 s) on; its deadline is that less 60 s and the
    swap."""
    job, builder, _ = _job(wanted=lambda tile: tile[1] == -64, cores=18,
                           capacity=16)
    job.flight_loaded(53.3, -60.45)
    _west(job, 0, 12)
    started = {s[0]: s[2] for s in builder.started}
    assert set(started) == {(52, -64), (53, -64), (54, -64)}
    assert all(460 <= d <= 475 for d in started.values()), started
    assert job.slots() == 3 and job.gs_ms == pytest.approx(150, rel=0.02)


def test_a_tile_that_cannot_be_built_in_time_is_late_and_not_started():
    job, builder, _ = _job(wanted=lambda tile: tile[1] == -64, cores=18,
                           estimate_s={"light": 2000.0})
    job.flight_loaded(53.3, -60.45)
    _west(job, 0, 12)
    assert not builder.started
    assert {j.state for j in job.jobs.values()} == {"late"}
    assert "faster than tiles can be built" in job.reason
    drape, builder, _ = _job(wanted=lambda tile: tile[1] == -64, cores=18,
                             kind="drape")
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
    assert job.status(12.0)["last_swap"][1] == "light"
    assert len(job.swaps) == 2 and job.swaps[1][1] - job.swaps[0][1] >= 10


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


def test_a_published_build_takes_the_kind_its_profile_makes(monkeypatch):
    published = []
    monkeypatch.setattr(PUBLISH, "_publish_built",
                        lambda where, build, lat, lon, kind:
                        published.append((lat, lon, kind)))

    class Session:
        _stepwise_run = False

        def __init__(self):
            self.subscribers = []

        def subscribe(self, callback):
            self.subscribers.append(callback)

        def tile_overrides(self, lat, lon):
            return {"profile": "light"} if lon == -64 else {}

        def tile_build_dir(self, lat, lon):
            return "/build"

    session = Session()
    PUBLISH.watch(session, scenery_dir=lambda: "/scenery")
    for lon in (-64, -65):
        session.subscribers[0](BuildDone(lat=53, lon=lon, ok=True))
    deadline = time.time() + 10
    while len(published) < 2 and time.time() < deadline:
        time.sleep(0.02)
    assert published == [(53, -64, "light"), (53, -65, "full")]


def test_the_session_builder_queues_a_light_build_by_deadline():
    calls, subscribers = [], []

    class Session:
        def subscribe(self, callback):
            subscribers.append(callback)

        def enqueue_build(self, tiles, provider, zoomlevel, folder, **kw):
            calls.append((tiles, provider, zoomlevel, kw))
            return True

    builder = RUN._SessionBuilder(Session(), "BI", 16)
    before = time.time()
    assert builder.start((53, -64), "light", 600.0, "P1")
    tiles, provider, zoomlevel, kw = calls[0]
    assert tiles == [(53, -64)] and (provider, zoomlevel) == ("BI", 16)
    assert kw["overrides"] == {"profile": "light"} and kw["klass"] == "P1"
    assert kw["missing_art"] == "leave"
    assert before + 599 <= kw["deadline"] <= time.time() + 601
    subscribers[0](BuildDone(lat=53, lon=-64, ok=True))
    subscribers[0](BuildDone(lat=10, lon=10, ok=True))   # not the job's
    assert builder.poll(0.0) == [((53, -64), True)] and builder.poll(0.0) == []
    assert not builder.start((53, -65), "drape", 60.0, "P1")   # no drape fn


def test_the_commands_refuse_what_is_not_there(tmp_path, monkeypatch):
    monkeypatch.setattr(RUN, "_settings", lambda: {})
    with pytest.raises(ValueError, match="flight"):
        RUN.world_job_start(object(), mode="flight")
    with pytest.raises(ValueError, match="kind"):
        RUN.world_job_start(object(), kind="heavy")
    assert RUN.world_job_start(object(), scenery_dir=str(tmp_path),
                               if_enabled=True) == {"status": "off"}
    with pytest.raises(ValueError, match="not installed"):
        RUN.world_job_start(object(), scenery_dir=str(tmp_path))
    assert RUN.autostart(object()) in (None, {"status": "off"})
    assert RUN.world_job_stop() == {"status": "stopped", "swapped": 0,
                                    "late": 0}
