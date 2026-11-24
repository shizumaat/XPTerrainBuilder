"""ONE BUILD PER AIRPORT ACROSS TILES (#2206 item 7).

Every tile holding a runway threshold of an airport builds the WHOLE
airport (#2129), and the app builds those tiles at once: LFPG twice,
5,662 s and 5,607 s, KPHX twice in parallel.  ``driver._one_flight_build``
runs such a build as the one flight of its airport (an OS lock beside the
stage cache): the second tile's build waits for the first and reads its
stage records.  An airport one tile builds takes no lock.
"""
import threading
import time

import O4_File_Names as FNAMES
import O4_Machine_Slots as SLOTS
from auto_patch import driver


def _task(tiles):
    return {"icao": "ZZZZ", "threshold_tiles": tiles}


def test_one_tile_airport_takes_no_lock():
    assert driver._airport_flight_path(_task([(33, -112)])) is None
    assert driver._airport_flight_path({"icao": "ZZZZ"}) is None


def test_straddler_lock_is_beside_the_stage_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root", lambda: str(tmp_path))
    path = driver._airport_flight_path(_task([(33, -113), (33, -112)]))
    assert path == str(tmp_path / "o4_airport_flight_ZZZZ.lock")


def test_second_tile_waits_for_the_first(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root", lambda: str(tmp_path))
    built = []
    monkeypatch.setattr(driver._engine_v2, "build_write_verify_one_v2",
                        lambda task, dem: built.append(time.time()) or
                        {"icao": task["icao"], "ok": True, "log_lines": []})
    task = _task([(33, -113), (33, -112)])
    held = SLOTS.try_os_lock(driver._airport_flight_path(task))   # tile A builds
    assert held is not None
    out = {}
    th = threading.Thread(target=lambda: out.update(driver._one_flight_build(task)))
    th.start()
    time.sleep(1.2)
    assert not built, "the second tile built while the first held the airport"
    released = time.time()
    SLOTS.release_os_lock(held)
    th.join(10)
    assert built and built[0] >= released
    assert out["ok"] and out["flight_wait_s"] >= 1.0
    assert "waited" in out["log_lines"][0]


def test_one_tile_airport_builds_at_once(monkeypatch):
    monkeypatch.setattr(driver._engine_v2, "build_write_verify_one_v2",
                        lambda task, dem: {"icao": task["icao"], "ok": True})
    out = driver._one_flight_build(_task([(33, -112)]))
    assert out == {"icao": "ZZZZ", "ok": True}
