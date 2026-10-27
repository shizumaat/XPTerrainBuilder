"""The preview asks stay cheap, quiet and few (1.0.433 sluggishness).

The Airports card (#818, asked on every selection change) and the boundary
preflight (every Build / Queue press) run the build's own tile selection.
In 1.0.433 each ask re-read every CIFP file, walked every Custom Scenery
pack per airport, printed the selector's ``[pav-builder]`` lines into the
build console, and piled up one thread per selection change while a build
ran.  These twins hold the four fixes: the selection caches answer from
memory until a file moves, the asks print nothing, a newer card supersedes
an older one, and the read loop's patch commands answer promptly while
card threads run.  Synthetic installs only: no corpus, no network.
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

RWY = ("RWY:RW{d},+0432,      ,02277, ,    , ,   ;{lat},{lon},0000;\n")


def _cifp_file(path, lat="N47300000", lon="W122300000"):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(RWY.format(d="14", lat=lat, lon=lon))
        fh.write(RWY.format(d="32", lat=lat, lon=lon))


def _bump(path):
    """Move a file's stat identity the way an edit does."""
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))


# ── the caches answer the file, never a stale copy ────────────────────
def test_cifp_thresholds_are_parsed_once_and_reread_when_the_file_moves(
        tmp_path, monkeypatch):
    from auto_patch_v2.airport import cifp

    path = str(tmp_path / "KAAA.dat")
    _cifp_file(path)
    reads = []
    real = cifp.read_cifp_runways
    # Only THIS file's reads count: a window another test left open may
    # still be reading the install on a thread of its own.
    monkeypatch.setattr(cifp, "read_cifp_runways",
                        lambda p: (p == path and reads.append(p)) or real(p))
    first = cifp.read_threshold_dicts(path)
    first["RW14"]["lat"] = 0.0                       # a caller's edit …
    second = cifp.read_threshold_dicts(path)
    assert len(reads) == 1                           # … parsed once
    assert second["RW14"]["lat"] == pytest.approx(47.5)   # … never shared
    _cifp_file(path, lat="N48000000")
    _bump(path)
    assert cifp.read_threshold_dicts(path)["RW14"]["lat"] == pytest.approx(48.0)
    assert len(reads) == 2


def test_the_cifp_listing_follows_the_directory(tmp_path):
    from auto_patch_v2.airport import cifp

    _cifp_file(str(tmp_path / "KAAA.dat"))
    assert set(cifp.discover_cifp_airports(str(tmp_path))) == {"KAAA"}
    _cifp_file(str(tmp_path / "KBBB.dat"))
    _bump(str(tmp_path))
    assert set(cifp.discover_cifp_airports(str(tmp_path))) == {"KAAA", "KBBB"}


def _pack(root, name, icao):
    nav = os.path.join(root, "Custom Scenery", name, "Earth nav data")
    os.makedirs(nav, exist_ok=True)
    with open(os.path.join(nav, "apt.dat"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("I\n1100 Version\n\n1 100 0 0 %s Field\n"
                 "1302 datum_lat 47.5\n1302 datum_lon -122.5\n"
                 "110 1 0.25 0.00 Pavement\n99\n" % icao)
    return os.path.join(nav, "apt.dat")


def test_the_apt_dat_selection_follows_the_install(tmp_path):
    from auto_patch_v2.airport import apt_dat

    root = str(tmp_path)
    second = _pack(root, "B pack", "KAAA")
    assert apt_dat.find_apt_dat(root, "KAAA") == second
    assert apt_dat.find_apt_dat(root, "KAAA") == second       # from the map
    first = _pack(root, "A pack", "KAAA")                      # a pack added
    _bump(os.path.join(root, "Custom Scenery"))
    assert apt_dat.find_apt_dat(root, "KAAA") == first
    ini = os.path.join(root, "Custom Scenery", "scenery_packs.ini")
    with open(ini, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("I\n1000 Version\nSCENERY\n\n"
                 "SCENERY_PACK_DISABLED Custom Scenery/A pack/\n"
                 "SCENERY_PACK Custom Scenery/B pack/\n")
    assert apt_dat.find_apt_dat(root, "KAAA") == second        # disabled


def test_the_pack_airports_follow_their_apt_dat(tmp_path):
    import O4_Custom_Scenery as SCENERY

    path = _pack(str(tmp_path), "A pack", "KAAA")
    content = os.path.dirname(os.path.dirname(path))
    assert [a.icao for a in SCENERY._pack_airports(content)] == ["KAAA"]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("I\n1100 Version\n\n1 100 0 0 KBBB Other\n"
                 "1302 datum_lat 47.5\n1302 datum_lon -122.5\n99\n")
    _bump(path)
    assert [a.icao for a in SCENERY._pack_airports(content)] == ["KBBB"]


# ── the asks print nothing ────────────────────────────────────────────
def _narrating_selector(*_a, **_kw):
    import O4_UI_Utils as UI

    UI.vprint(1, "  [pav-builder] KAAA: apt.dat /somewhere/apt.dat")
    UI.lvprint(1, "  [pav-builder] KAAA: logged too")
    return []


def test_the_airports_card_writes_nothing_to_the_console(monkeypatch, capsys):
    from auto_patch import selection
    from o4_engine import build_airports as BA
    import O4_UI_Utils as UI

    monkeypatch.setattr(selection, "select_patch_airports", _narrating_selector)
    monkeypatch.setattr(UI, "log", False)
    monkeypatch.setattr("O4_Settings_Model.resolve_cifp_dir", lambda *a: "/cifp")
    BA.build_airports([(47, -123)], scenery_dir="")
    assert "[pav-builder]" not in capsys.readouterr().out
    _narrating_selector()                       # a build thread still prints
    assert "[pav-builder]" in capsys.readouterr().out


def test_the_boundary_preflight_writes_nothing_to_the_console(monkeypatch, capsys):
    from auto_patch import selection
    from o4_engine import session as S
    import O4_UI_Utils as UI

    monkeypatch.setattr(UI, "log", False)
    events = []
    sess = S.EngineSession.__new__(S.EngineSession)
    sess._boundary_request_lock = threading.Lock()
    sess._boundary_request_id = 0
    sess._emit = events.append
    monkeypatch.setattr(sess, "_boundary_preflight",
                        lambda rid, cells: _narrating_selector()
                        or S.BoundaryAirportsReady(request_id=rid), raising=False)
    monkeypatch.setattr(selection, "select_patch_airports", _narrating_selector)
    sess.boundary_airports(tiles=[[47, -123]])
    deadline = time.monotonic() + 10
    while not events and time.monotonic() < deadline:
        time.sleep(0.01)
    assert events, "TIMED_OUT waiting for BoundaryAirportsReady"
    assert "[pav-builder]" not in capsys.readouterr().out


def test_quiet_is_per_thread():
    import O4_UI_Utils as UI

    seen = []
    with UI.quiet_thread():
        assert UI.thread_is_quiet()
        other = threading.Thread(target=lambda: seen.append(UI.thread_is_quiet()))
        other.start()
        other.join()
    assert seen == [False] and not UI.thread_is_quiet()


# ── a newer card supersedes an older one ──────────────────────────────
def test_a_newer_card_stops_the_older_one(monkeypatch):
    from o4_engine import build_airports as BA

    gate = threading.Event()
    read = []

    def slow_tile(lat, lon, folder=""):
        read.append((lat, lon))
        gate.wait(5)
        return []

    monkeypatch.setattr(BA, "tile_airports", slow_tile)
    monkeypatch.setattr(BA, "airport_packs", lambda *a, **k: [])
    events = []
    BA.start_build_airports(events.append, tiles=[[1, 1], [2, 2], [3, 3]],
                            request=1)
    BA.start_build_airports(events.append, tiles=[[4, 4]], request=2)
    gate.set()
    deadline = time.monotonic() + 10
    while len(events) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(events) == 2, "TIMED_OUT"
    by_request = {e.request: e for e in events}
    assert "superseded" in by_request[1].error
    assert not by_request[2].error
    assert (2, 2) not in read and (3, 3) not in read   # stopped at its next tile


# ── the read loop answers while cards read ────────────────────────────
def test_patch_list_answers_promptly_while_cards_read(tmp_path, monkeypatch):
    """A card over a 3,000-file CIFP install, three at once, warm after the
    first: ``patch_list`` (a read-loop command) must answer within 2 s."""
    from auto_patch import selection
    from o4_engine import patch_commands as PC

    cifp_dir = tmp_path / "CIFP"
    cifp_dir.mkdir()
    for n in range(3000):
        _cifp_file(str(cifp_dir / ("K%03d.dat" % n)), lat="N10000000")

    class Tile:
        lat, lon = 47, -123

    selection.select_patch_airports(Tile(), str(cifp_dir), "All")   # warm
    stop = threading.Event()

    def card():
        while not stop.is_set():
            selection.select_patch_airports(Tile(), str(cifp_dir), "All")

    workers = [threading.Thread(target=card, daemon=True) for _ in range(3)]
    for worker in workers:
        worker.start()
    patches = tmp_path / "Patches"
    monkeypatch.setattr(PC, "_patch_dir", lambda tile: str(patches))
    patches.mkdir()
    try:
        worst = 0.0
        for _ in range(5):
            t0 = time.monotonic()
            PC.patch_list("+47-123")
            worst = max(worst, time.monotonic() - t0)
    finally:
        stop.set()
        for worker in workers:
            worker.join(10)
    assert worst < 2.0, worst
