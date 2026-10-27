"""Twins for the imagery prefetch alongside the vector step (#1002).

Headless and offline: the candidates are read from a synthetic live
terrain folder, the downloads go through a fake fetcher, and the
orchestrator is driven with fake children (no worker processes).
"""

from __future__ import annotations

import os
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO
import O4_Imagery_Prefetch as PREFETCH
import O4_UI_Utils as UI
import pytest
from o4_engine import parallel
from o4_engine.events import ImageryDownloadsDone
from o4_engine.session import EngineSession

LAT, LON = 45, 7


def _imagery(*codes, combined=()):
    providers = {code: {"code": code, "imagery_dir": "normal"}
                 for code in codes}
    return SimpleNamespace(
        providers_dict=providers,
        combined_providers_dict={code: [] for code in combined},
        local_combined_providers_dict={})


def _grid(zoom, count):
    """``count`` texture origins of the tile's grid at ``zoom``."""
    (x0, y0) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, zoom)
    return [(x0 + 16 * i, y0) for i in range(count)]


@pytest.fixture
def tile(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "imagery"))
    monkeypatch.setattr(UI, "red_flag", False)
    build_dir = tmp_path / "tile"
    (build_dir / "terrain").mkdir(parents=True)
    (build_dir / "textures").mkdir()
    return SimpleNamespace(lat=LAT, lon=LON, build_dir=str(build_dir),
                           default_website="NEW", default_zl=16,
                           texture_mode="full_ortho")


def _live(tile, textures, suffix=""):
    for (x, y, zoom, provider) in textures:
        name = FNAMES.dds_file_name_from_attributes(x, y, zoom, provider)
        path = os.path.join(tile.build_dir, "terrain",
                            name[:-4] + suffix + ".ter")
        open(path, "w", encoding="utf-8", newline="\n").close()


# -- candidates ---------------------------------------------------------
def test_live_textures_are_rekeyed_to_the_new_source(tile):
    base = [(x, y, 16, "OLD") for (x, y) in _grid(16, 3)]
    airport = [(x, y, 18, "OLD") for (x, y) in _grid(18, 1)]
    _live(tile, base)
    _live(tile, base[:1], "_sea_overlay")       # same texture, other use
    _live(tile, airport)
    found = PREFETCH.candidates(tile, _imagery("OLD", "NEW"))
    # the highest zoom (the airport cover) first (#1359, RULINGS 2026-10-26y)
    assert found == sorted(
        [(x, y, z, "NEW") for (x, y, z, _) in base + airport],
        key=lambda t: (-t[2], t[1], t[0], t[3]))
    assert found[0][2] == 18


def test_built_textures_and_cached_orthophotos_are_left_out(tile):
    imagery = _imagery("OLD", "NEW")
    base = [(x, y, 16, "OLD") for (x, y) in _grid(16, 3)]
    _live(tile, base)
    (built, cached, wanted) = [(x, y, z, "NEW") for (x, y, z, _) in base]
    open(os.path.join(tile.build_dir, "textures",
                      FNAMES.dds_file_name_from_attributes(*built)),
         "w", encoding="utf-8", newline="\n").close()
    jpeg = PREFETCH._orthophoto_path(tile, cached, imagery)
    os.makedirs(os.path.dirname(jpeg))
    open(jpeg, "w", encoding="utf-8", newline="\n").close()
    assert PREFETCH.candidates(tile, imagery) == [wanted]


def test_a_zone_source_keeps_its_own_code(tile):
    base = [(x, y, 16, "OLD") for (x, y) in _grid(16, 3)]
    zone = [(x, y, 17, "ZONE") for (x, y) in _grid(17, 1)]
    _live(tile, base + zone)
    found = PREFETCH.candidates(tile, _imagery("OLD", "NEW", "ZONE"))
    assert (zone[0][0], zone[0][1], 17, "ZONE") in found
    assert all(t[3] in ("NEW", "ZONE") for t in found)


def test_a_provider_code_ending_in_digits_parses_to_the_tile(tile):
    base = [(x, y, 16, "GO2") for (x, y) in _grid(16, 2)]
    _live(tile, base)
    found = PREFETCH.candidates(tile, _imagery("GO2", "NEW"))
    assert [t[2] for t in found] == [16, 16]


@pytest.mark.parametrize("case", ["never_built", "other_zoom",
                                  "default_xplane", "combined"])
def test_nothing_to_prefetch(tile, case):
    imagery = _imagery("OLD", "NEW", combined=("NEW",)
                       if case == "combined" else ())
    if case != "never_built":
        _live(tile, [(x, y, 16, "OLD") for (x, y) in _grid(16, 3)])
    if case == "other_zoom":
        tile.default_zl = 17
    if case == "default_xplane":
        tile.texture_mode = "default_xplane"
    assert PREFETCH.candidates(tile, imagery) == []


# -- the background downloads --------------------------------------------
def test_downloads_drain_and_report_once(tile):
    fetched, reports = [], []
    textures = [(i, i, 16, "NEW") for i in range(4)]
    with PREFETCH.alongside(
            tile, on_done=lambda d, f: reports.append((d, f)),
            fetch=lambda t, texture: fetched.append(texture) or
            (texture[0] != 2),
            find=lambda t: textures) as prefetch:
        for thread in prefetch._threads:
            thread.join(5)
    assert fetched == textures, "one at a time, in order"
    assert reports == [(3, 1)]


def test_stop_at_the_step_end_starts_nothing_new(tile):
    gate, started, reports = threading.Event(), [], []

    def fetch(t, texture):
        started.append(texture)
        gate.wait(5)
        return 1

    textures = [(i, i, 16, "NEW") for i in range(5)]
    with PREFETCH.alongside(tile, on_done=lambda d, f: reports.append(d),
                            fetch=fetch, find=lambda t: textures):
        while not started:
            threading.Event().wait(0.01)
        threading.Timer(0.1, gate.set).start()
    assert started == textures[:1], "the one in flight finishes, no more"
    assert reports == [1], "what arrived stays and is reported"


def test_stop_flag_ends_the_prefetch(tile):
    started = []

    def fetch(t, texture):
        started.append(texture)
        UI.red_flag = True
        return 1

    with PREFETCH.alongside(tile, fetch=fetch,
                            find=lambda t: [(i, i, 16, "NEW")
                                            for i in range(3)]) as p:
        for thread in p._threads:
            thread.join(5)
    assert len(started) == 1


def test_nothing_to_fetch_reports_at_the_airport_fetch_or_the_step_end(tile):
    """#1359 (26y): the vector step's airport fetch rides the lent token,
    so with an empty queue the token comes back after that fetch — or at
    the step's end when no fetch comes (no auto-patch)."""
    reports = []
    with PREFETCH.alongside(tile, on_done=lambda d, f: reports.append(d),
                            find=lambda t: []):
        assert reports == [], "held for the airport fetch"
    assert reports == [0]


def test_a_failing_candidate_scan_prefetches_nothing(tile):
    reports = []

    def broken(t):
        raise OSError("unreadable")

    with PREFETCH.alongside(tile, on_done=lambda d, f: reports.append(d),
                            find=broken):
        pass
    assert reports == [0]


def test_an_incomplete_orthophoto_is_not_kept(tmp_path, monkeypatch):
    import O4_Imagery_Utils as IMG
    from PIL import Image

    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setitem(IMG.providers_dict, "FAKE", {
        "code": "FAKE", "grid_type": "webmercator", "tile_size": 1})
    answers = []
    monkeypatch.setattr(
        IMG, "build_texture_from_tilbox",
        lambda *a, **k: (answers.pop(0), Image.new("RGB", (4, 4))))
    file_dir = str(tmp_path / "+45+007" / "FAKE_16")
    answers.append(False)
    assert IMG.download_jpeg_ortho(file_dir, "a.jpg", 0, 0, 16, "FAKE",
                                   require_complete=True) == 0
    assert not os.path.exists(os.path.join(file_dir, "a.jpg"))
    answers.append(True)
    assert IMG.download_jpeg_ortho(file_dir, "a.jpg", 0, 0, 16, "FAKE",
                                   require_complete=True) == 1
    assert sorted(os.listdir(file_dir)) == ["a.jpg"], "no .part left"


# -- the session runs it alongside the vector step only --------------------
@pytest.fixture
def spied(monkeypatch):
    calls = []
    original = PREFETCH.alongside

    def spy(tile, on_done=None, **kw):
        calls.append(tile)
        return original(tile, on_done=on_done, find=lambda t: [])

    monkeypatch.setattr(PREFETCH, "alongside", spy)
    return calls


def _plan(*keys):
    return [(key, 0.0, 1.0) for key in keys]


def test_in_process_vector_step_prefetches_and_reports(spied):
    session = EngineSession()
    events = []
    session.subscribe(events.append)
    session._prefetch_imagery = True
    tile = SimpleNamespace(lat=LAT, lon=LON)
    assert session._run_step(lambda t: 1, "vector", tile,
                             _plan("vector", "imagery")) == 1
    assert spied == [tile]
    done = [e for e in events if isinstance(e, ImageryDownloadsDone)]
    assert [(e.lat, e.lon, e.downloaded) for e in done] == [(LAT, LON, 0)]


@pytest.mark.parametrize("key,plan,stepwise,allowed", [
    ("mesh", ("vector", "mesh", "imagery"), False, True),
    ("vector", ("vector", "mesh"), False, True),       # no imagery built
    ("vector", ("vector",), True, False),               # child, no token
])
def test_no_prefetch_outside_its_case(spied, key, plan, stepwise, allowed):
    session = EngineSession()
    session._stepwise_run = stepwise
    session._prefetch_imagery = allowed
    session._run_step(lambda t: 1, key, SimpleNamespace(lat=1, lon=2),
                      _plan(*plan))
    assert spied == []


def test_child_with_a_lent_token_prefetches(spied):
    session = EngineSession()
    session._stepwise_run = True
    session._prefetch_imagery = True
    session._run_step(lambda t: 1, "vector", SimpleNamespace(lat=1, lon=2),
                      _plan("vector"))
    assert len(spied) == 1


# -- the orchestrator lends an imagery token ------------------------------
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

    def start_step(self, step_key, build_arguments):
        self.running_step = step_key
        self.arguments.append(build_arguments)
        return True

    def send(self, payload):
        return True


def _vector_run(tiles, flags=(True, True, False), imagery_busy=0):
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        tiles, "P", 16, "", flags, len(tiles))
    run._class_active["imagery"] = imagery_busy
    children = [_Child() for _ in tiles]
    run._children = list(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
    return run, children


def _drained(run, child):
    run._on_child_event(child, {
        "event": "ImageryDownloadsDone", "lat": child.tile[0],
        "lon": child.tile[1], "downloaded": 2, "failed": 0})


def test_vector_step_borrows_an_imagery_token_and_drain_returns_it():
    run, (child,) = _vector_run([(30, 1)])
    assert child.arguments[0].get("prefetch") is True
    assert run._class_active["imagery"] == 1
    _drained(run, child)
    assert run._class_active["imagery"] == 0
    assert child.running_step == "vector", "the step itself goes on"
    _drained(run, child)
    assert run._class_active["imagery"] == 0, "no double release"


def test_step_end_or_crash_returns_the_lent_token():
    run, (child,) = _vector_run([(30, 1)])
    with run._lock:
        run._release_step_resources_locked(child)
    assert run._class_active["imagery"] == 0
    run, (child,) = _vector_run([(30, 2)])
    run._on_child_exit(child)
    assert run._class_active["imagery"] == 0


def test_no_token_lent_when_the_imagery_class_is_full():
    limit = parallel.class_limits(8)["imagery"]
    run, (child,) = _vector_run([(31, 1)], imagery_busy=limit)
    assert child.running_step == "vector", "the step itself is not held"
    assert "prefetch" not in child.arguments[0]
    assert run._class_active["imagery"] == limit


def test_no_token_lent_for_a_build_without_imagery():
    run, (child,) = _vector_run([(32, 1)], flags=(True, False, False))
    assert "prefetch" not in child.arguments[0]
    assert run._class_active["imagery"] == 0


# -- the airport's own photos first (#1359, owner RULINGS 2026-10-26y) ----
def _airport_tile(tile):
    tile.mesh_zl = 18
    return tile


def _boundary_at(lat_off, lon_off, half_deg=0.002):
    from shapely.geometry import box
    return box(lon_off - half_deg, lat_off - half_deg, lon_off + half_deg, lat_off + half_deg)


def test_airport_textures_are_the_assignment_over_the_boundary(tile):
    """The textures the ortho assignment gives the mesh blocks under the
    airport's boundary (plus the margin), plain sources only, highest zoom
    first; a far block is not the airport's."""
    tile = _airport_tile(tile)
    (bx, by) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, 18)
    near = {(bx + dx, by + dy): (bx + dx, by + dy, 18, "NEW")
            for dx in (-16, 0, 16) for dy in (-16, 0, 16)}
    near[(bx, by)] = (bx // 4 // 16 * 16, by // 4 // 16 * 16, 16, "MIX")
    far = {(bx + 160, by): (bx + 160, by, 18, "NEW")}
    found = PREFETCH.airport_textures(
        tile, {"ZZZZ": {"boundary": _boundary_at(0.5, 0.5)}},
        imagery=_imagery("NEW", combined=("MIX",)), ortho_dico={**near, **far})
    got = found["ZZZZ"]
    assert (bx + 160, by, 18, "NEW") not in got
    assert all(t[3] == "NEW" for t in got)          # the combined source is left out
    assert got == sorted(got, key=lambda t: (-t[2], t[1], t[0], t[3]))
    assert got and set(got) <= set(near.values())


def test_the_patch_waits_for_the_airport_photos(tile, monkeypatch):
    """``fetch_airport_imagery`` downloads every missing airport texture
    before it returns and hands back the cached paths; a failed download is
    simply absent (the witness abstains there)."""
    import O4_Imagery_Utils as IMG
    monkeypatch.setattr(IMG, "providers_dict", _imagery("NEW").providers_dict)
    (bx, by) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, 18)
    ok, bad = (bx, by, 18, "NEW"), (bx + 16, by, 18, "NEW")
    fetched = []

    def fetch(_tile, texture):
        fetched.append(texture)
        if texture == bad:
            return 0
        path = PREFETCH._orthophoto_path(tile, texture, IMG)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        return 1

    got = PREFETCH.fetch_airport_imagery(
        tile, {"ZZZZ": {}}, fetch=fetch, find=lambda _t, _d: {"ZZZZ": [ok, bad]})
    assert sorted(fetched) == sorted([ok, bad])
    assert got == {"ZZZZ": (PREFETCH._orthophoto_path(tile, ok, IMG),)}
    # a second call finds it cached and downloads nothing more
    fetched.clear()
    PREFETCH.fetch_airport_imagery(
        tile, {"ZZZZ": {}}, fetch=fetch, find=lambda _t, _d: {"ZZZZ": [ok]})
    assert fetched == []


def test_default_xplane_textures_no_airport(tile):
    tile.texture_mode = "default_xplane"
    assert PREFETCH.airport_textures(tile, {"ZZZZ": {"boundary": _boundary_at(0.5, 0.5)}},
                                     imagery=_imagery("NEW"), ortho_dico={}) == {}


def test_the_session_hands_the_vector_step_the_airport_fetch(spied):
    """#1359 (26y): every vector step — prefetching or not — gets the
    airport photo fetch; the vector step reads it, never imports it."""
    import O4_Vector_Map as VMAP
    session = EngineSession()
    session._prefetch_imagery = False
    seen = []

    def step(t):
        seen.append(getattr(t, "airport_imagery_fetch", None))
        return 1

    tile = SimpleNamespace(lat=1, lon=2)
    session._run_step(step, "vector", tile, _plan("vector"))
    # no token lent: the cache-only fetch
    assert seen[0].func is PREFETCH.fetch_airport_imagery
    assert seen[0].keywords == {"download": False}
    # the vector step's side: no hook, no photos; a failing hook, no photos
    assert VMAP._airport_imagery(SimpleNamespace(), {}) == {}

    def boom(_dico):
        raise RuntimeError("offline")
    assert VMAP._airport_imagery(SimpleNamespace(airport_imagery_fetch=boom), {}) == {}


# -- the airport fetch rides the prefetch's imagery token (#1359, 26y) -----
def test_without_a_token_the_airport_fetch_downloads_nothing(tile, monkeypatch):
    """A worker child its parent lent no imagery token (or a run that
    builds no imagery) reads the airport photos already cached only."""
    import O4_Imagery_Utils as IMG
    monkeypatch.setattr(IMG, "providers_dict", _imagery("NEW").providers_dict)
    fetched = []
    (bx, by) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, 18)
    got = PREFETCH.fetch_airport_imagery(
        tile, {"ZZZZ": {}}, fetch=lambda t, x: fetched.append(x) or 1,
        find=lambda _t, _d: {"ZZZZ": [(bx, by, 18, "NEW")]}, download=False)
    assert fetched == [] and got == {}


def test_the_token_comes_back_only_after_the_airport_fetch(tile, monkeypatch):
    """The prefetch's report (which hands the lent token back) waits for
    its queue AND the vector step's airport fetch; the airport downloads
    are counted in it."""
    import O4_Imagery_Utils as IMG
    monkeypatch.setattr(IMG, "providers_dict", _imagery("NEW").providers_dict)
    reports = []
    (bx, by) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, 18)

    def fetch(_tile, texture):
        path = PREFETCH._orthophoto_path(tile, texture, IMG)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        return 1

    prefetch = PREFETCH.Prefetch(tile, [], fetch=fetch,
                                 on_done=lambda d, f: reports.append((d, f))).start()
    assert reports == []                       # queue empty, token still lent
    got = prefetch.fetch_airports(
        {"ZZZZ": {}}, find=lambda _t, _d: {"ZZZZ": [(bx, by, 18, "NEW")]})
    assert reports == [(1, 0)] and list(got) == ["ZZZZ"]
    prefetch.stop()
    assert reports == [(1, 0)]                 # reported once


def test_the_session_hands_the_token_holder_the_downloading_fetch(spied):
    session = EngineSession()
    session._prefetch_imagery = True
    seen = []
    session._run_step(lambda t: seen.append(t.airport_imagery_fetch) or 1, "vector",
                      SimpleNamespace(lat=LAT, lon=LON), _plan("vector", "imagery"))
    assert getattr(seen[0], "__func__", None) is PREFETCH.Prefetch.fetch_airports
