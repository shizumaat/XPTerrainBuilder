"""H1 — THE SILENT TILE-BUILD DEATH must fail LOUDLY.

The incident (docs/POSTMORTEM-20260831.md, Task C): on 2026-08-30 the
owner's app tile build of +30+031 died at 22:38:40 mid "Decimating
emitted geometry".  ``build_airport_pavement`` had already recorded its
phase times; the patch write in ``driver._build_write_verify_one`` never
ran.  The failure reached the console log and stopped there — the tile
step meshed the STALE patch already on disk, finished with exit 0, and
the owner flew Aug-29 geometry believing it was the day's build.

The twins below pin every leg of the closure:

1.  a WORKER KILLED mid-task (a real ``SIGKILL`` of a real pool child)
    is attributed to its airport and raises;
2.  a PATCH-WRITE failure (``{"stage": "write"}``) raises, named;
3.  a worker that reports SUCCESS but left no patch on disk — the exact
    mismatch of the incident — is caught by the manifest verification;
4.  a STALE patch (present, but not rewritten by this pass) is caught
    too: that is literally the file that flew;
5.  the failure reaches the JSONL protocol as an ``AutoPatchFailed``
    event and makes the tile's ``BuildDone`` say ``ok=false`` with the
    airport named;
6.  a HEALTHY pass is unchanged — no exception, no event, and the
    patches it wrote are byte-for-byte what it wrote.
"""
import json
import os
import signal
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from auto_patch import driver as DRIVER          # noqa: E402
import O4_UI_Utils as UI                          # noqa: E402


# ── fixtures ────────────────────────────────────────────────────────────


class _Tile:
    """The only attribute ``_run_build_tasks`` reads off the tile."""

    dem = None
    lat = 30
    lon = 31


def _task(tmp_path, icao, **overrides):
    task = {
        "icao": icao,
        "xp_root": str(tmp_path),
        "taxiway_data": None,
        "boundary": None,
        "tile_lat": 30,
        "tile_lon": 31,
        "auto_patch_file": str(tmp_path / (icao + "_auto.patch.osm")),
        "verify_log_path": str(tmp_path / (icao + ".part")),
        "freshness": None,
    }
    task.update(overrides)
    return task


def _write_patch_pair(task, body="<osm/>"):
    """What a healthy build leaves behind: the patch and its sidecar."""
    path = task["auto_patch_file"]
    with open(path, "w") as handle:
        handle.write(body)
    with open(path + ".axes.json", "w") as handle:
        json.dump({"axes": []}, handle)


def _run(tasks, tmp_path):
    return DRIVER._run_build_tasks(
        tasks, _Tile(), [], str(tmp_path / "verify.log"))


@pytest.fixture(autouse=True)
def _serial(monkeypatch):
    """Serial path by default — the parallel twin opts back in."""
    monkeypatch.setattr(DRIVER, "_cfg_parallel_override", None, raising=False)
    from auto_patch import config as CFG
    monkeypatch.setattr(CFG, "PARALLEL_AIRPORTS", False, raising=False)


@pytest.fixture
def captured_events(monkeypatch):
    """Every ``UI.auto_patch_failed`` notification this pass emitted."""
    seen = []
    monkeypatch.setattr(
        UI, "auto_patch_failed",
        lambda icao, stage, error: seen.append((icao, stage, error)))
    return seen


# ── 1. the killed worker ────────────────────────────────────────────────


class _SigkillOnUnpickle:
    """Kills the process that unpickles it, HARD.

    Rides in the task dict, so the child dies while unpickling the work
    item — after the pool is up, mid-task, exactly as the owner's worker
    died.  A ``SIGKILL`` escapes Python entirely: the worker's own
    ``except Exception`` never runs, so nothing carries the airport's
    name back.  That is the attribution this twin defends.
    """

    def __reduce__(self):
        return (_sigkill_self, ())


def _sigkill_self():
    os.kill(os.getpid(), signal.SIGKILL)
    return None                                   # unreachable


def test_killed_worker_is_named_and_fatal(tmp_path, monkeypatch,
                                          captured_events):
    from auto_patch import config as CFG
    monkeypatch.setattr(CFG, "PARALLEL_AIRPORTS", True, raising=False)
    monkeypatch.setattr(CFG, "parallel_airports_worker_count",
                        lambda n: 2, raising=False)
    tasks = [_task(tmp_path, "KAAA", boundary=_SigkillOnUnpickle()),
             _task(tmp_path, "KBBB", boundary=_SigkillOnUnpickle())]

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run(tasks, tmp_path)

    named = {f["icao"] for f in raised.value.failures}
    # THE REGRESSION: before H1 a hard worker death produced a result
    # with ``icao: None``, which fell out of the results map and left the
    # airport reported as an anonymous "missing" — or, in the tile, as
    # nothing at all.  Both airports must be named.
    assert named == {"KAAA", "KBBB"}, raised.value.failures
    # Proof the POOL path ran and the child really died: a serial
    # fallback would have reached the real builder and reported stage
    # "build" instead.
    assert {f["stage"] for f in raised.value.failures} == {"worker"}, \
        raised.value.failures
    assert {icao for icao, _stage, _error in captured_events} == named
    assert not os.path.exists(tasks[0]["auto_patch_file"])


# ── 2. the patch-write failure ──────────────────────────────────────────


def test_write_failure_is_named_and_fatal(tmp_path, monkeypatch,
                                          captured_events):
    def _fail_write(task):
        return {"icao": task["icao"], "ok": False, "stage": "write",
                "error": "No space left on device",
                "auto_patch_file": task["auto_patch_file"]}

    monkeypatch.setattr(DRIVER, "_build_write_verify_one", _fail_write)
    tasks = [_task(tmp_path, "HECA")]

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run(tasks, tmp_path)

    assert raised.value.failures == [
        {"icao": "HECA", "stage": "write",
         "error": "No space left on device"}]
    assert "HECA" in str(raised.value)
    assert "write" in str(raised.value)
    assert captured_events == [("HECA", "write", "No space left on device")]


# ── 3. the incident's exact mismatch: success reported, no patch ────────


def test_success_without_a_patch_is_caught_by_the_manifest(
        tmp_path, monkeypatch, captured_events):
    """Phase times recorded, ``to_osm`` never ran, result says OK.

    A worker killed after ``build_airport_pavement`` returned but before
    ``layout.to_osm`` leaves precisely this state on disk.  The check
    must read the DISK, never the result.
    """
    def _lying_success(task):
        return {"icao": task["icao"], "ok": True, "summary": "0 shapes",
                "build_s": 1.0, "verify_s": 0.0, "verify_err": None,
                "verify_log_path": task["verify_log_path"],
                "object_pad_records": [], "provenance_log": None}

    monkeypatch.setattr(DRIVER, "_build_write_verify_one", _lying_success)

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([_task(tmp_path, "HECA")], tmp_path)

    (failure,) = raised.value.failures
    assert failure["icao"] == "HECA"
    assert failure["stage"] == "manifest"
    assert "HECA_auto.patch.osm" in failure["error"]
    assert captured_events and captured_events[0][1] == "manifest"


def test_missing_sidecar_alone_is_fatal(tmp_path, monkeypatch,
                                        captured_events):
    """A patch with no ``.axes.json`` degrades every census silently."""
    def _patch_without_sidecar(task):
        with open(task["auto_patch_file"], "w") as handle:
            handle.write("<osm/>")
        return {"icao": task["icao"], "ok": True, "summary": "1 shape",
                "build_s": 1.0, "verify_s": 0.0, "verify_err": None,
                "verify_log_path": task["verify_log_path"],
                "object_pad_records": [], "provenance_log": None}

    monkeypatch.setattr(DRIVER, "_build_write_verify_one",
                        _patch_without_sidecar)

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([_task(tmp_path, "HECA")], tmp_path)

    (failure,) = raised.value.failures
    assert failure["stage"] == "manifest"
    assert "axes.json" in failure["error"]


# ── 4. the stale patch — the file that actually flew ────────────────────


def test_stale_patch_left_on_disk_is_fatal(tmp_path, monkeypatch,
                                           captured_events):
    task = _task(tmp_path, "HECA")
    _write_patch_pair(task, body="<osm><!-- Aug 29 --></osm>")
    old = 1_600_000_000                    # long before this pass started
    os.utime(task["auto_patch_file"], (old, old))
    os.utime(task["auto_patch_file"] + ".axes.json", (old, old))

    def _lying_success(t):
        return {"icao": t["icao"], "ok": True, "summary": "0 shapes",
                "build_s": 1.0, "verify_s": 0.0, "verify_err": None,
                "verify_log_path": t["verify_log_path"],
                "object_pad_records": [], "provenance_log": None}

    monkeypatch.setattr(DRIVER, "_build_write_verify_one", _lying_success)

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as raised:
        _run([task], tmp_path)

    (failure,) = raised.value.failures
    assert failure["stage"] == "manifest"
    assert "stale" in failure["error"]
    # The stale file is still there — this pass refuses to CALL it the
    # build's output, which is the whole point.
    assert "Aug 29" in open(task["auto_patch_file"]).read()


# ── 5. the protocol: the app hears about it ─────────────────────────────


def test_failure_reaches_the_jsonl_protocol_and_builddone():
    """``AutoPatchFailed`` on the wire; ``BuildDone.error`` names it.

    The event class name IS the wire name (``type(self).__name__``) and
    ``Sources/SceneryKit/OrthoEngineClient.swift`` matches it as a string
    literal — asserted here so a rename cannot pass silently.
    """
    from o4_engine import events as EVENTS
    from o4_engine.session import EngineSession

    assert EVENTS.AutoPatchFailed.__name__ == "AutoPatchFailed"

    emitted = []
    session = EngineSession.__new__(EngineSession)
    session._current_step = ((30, 31), "vector", 0.0, 1.0)
    session._autopatch_failures = []
    session._emit = emitted.append

    session.autopatch_failed("HECA", "manifest", "wrote no patch")

    (event,) = emitted
    assert type(event).__name__ == "AutoPatchFailed"
    assert (event.airport, event.stage, event.lat, event.lon) == (
        "HECA", "manifest", 30, 31)
    from o4_engine.jsonl import serialize_event
    payload = serialize_event(event)
    assert payload["event"] == "AutoPatchFailed"
    assert payload["airport"] == "HECA"
    assert payload["stage"] == "manifest"
    assert payload["error"] == "wrote no patch"

    text = session._take_autopatch_failure_text()
    assert "HECA" in text and "manifest" in text
    # Drained: the next tile does not inherit this tile's failure.
    assert session._take_autopatch_failure_text() is None


def test_swift_client_matches_the_event_name():
    """The cross-language literal, checked from the Python side."""
    swift = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))),
        "Sources", "SceneryKit", "OrthoEngineClient.swift")
    if not os.path.isfile(swift):
        pytest.skip("Swift client not present in this checkout")
    assert '"AutoPatchFailed"' in open(swift).read()


def test_parallel_forwards_the_failure_event():
    """A child build's diagnosis must survive the child→parent hop."""
    from o4_engine import parallel as PARALLEL
    assert "AutoPatchFailed" in PARALLEL._FORWARDED_EVENT_TYPES
    rebuilt = PARALLEL._rebuild_event({
        "event": "AutoPatchFailed", "airport": "HECA",
        "stage": "worker", "error": "killed", "lat": 30, "lon": 31})
    assert rebuilt is not None
    assert rebuilt.airport == "HECA" and rebuilt.stage == "worker"


# ── 6. the healthy pass is untouched ────────────────────────────────────


def test_healthy_pass_raises_nothing_and_preserves_its_bytes(
        tmp_path, monkeypatch, captured_events):
    bodies = {"KAAA": "<osm>A</osm>", "KBBB": "<osm>B</osm>"}

    def _healthy(task):
        _write_patch_pair(task, body=bodies[task["icao"]])
        return {"icao": task["icao"], "ok": True, "summary": "3 runway",
                "build_s": 2.0, "verify_s": 0.1, "verify_err": None,
                "verify_log_path": task["verify_log_path"],
                "object_pad_records": [], "provenance_log": None}

    monkeypatch.setattr(DRIVER, "_build_write_verify_one", _healthy)
    tasks = [_task(tmp_path, "KAAA"), _task(tmp_path, "KBBB")]
    built = []

    assert DRIVER._run_build_tasks(
        tasks, _Tile(), built, str(tmp_path / "verify.log")) is None
    assert built == ["KAAA", "KBBB"]
    assert captured_events == []
    for task in tasks:
        assert open(task["auto_patch_file"]).read() == bodies[task["icao"]]
        assert os.path.isfile(task["auto_patch_file"] + ".axes.json")


def test_no_tasks_is_still_a_no_op(tmp_path):
    assert DRIVER._run_build_tasks(
        [], _Tile(), [], str(tmp_path / "verify.log")) is None
