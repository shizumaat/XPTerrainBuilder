"""Measure -- the dry run of Convert existing tiles (``world_migrate``,
``world_migrate_size``) -- on its own worker PROCESS, at background
priority, with its result kept (owner 2026-11-12T19:08Z):

    "Can we recognize if there's any per tile ortho packs installed and
    then automatically kickoff the measure process in the background so
    when the user opens settings it's already done? Also, it appears to
    have hung ... I'm not getting any display of data, budgets, or
    caches."

Why a process.  Measure reads the headers of every tile folder (thousands
on another drive) on threads of the engine; the Storage rows' scan
(``storage.storage_scan``) walks the data folder on another thread of
the SAME interpreter.  Every file call releases the interpreter lock and
must win it back from threads that parse between their reads; measured
on this machine, 8 threads reading and parsing slowed a 15,000-``stat``
walk 160-fold (0.007 s to 1.1 s), one busy thread 1,000-fold.  Data,
budget and caches stayed empty while Measure ran.  In its own process
Measure shares nothing with the commands the apps wait on.

* :func:`measure` -- the dry run (``world_migrate.run_command``) in a
  spawned child (the frozen engine re-entered through
  ``multiprocessing.freeze_support``, as the work pool is), its
  ``WorldMigrateProgress`` relayed to ``emit``; ``background`` puts the
  child in the system's background band (``O4_Machine_Slots
  .background_priority``: CPU and disk reads yield to a build).  The
  header cache (``world_tile_facts``) and the last measure's seconds per
  tile make a second Measure of the same tiles take seconds.  A full
  measure's result is KEPT (:func:`state`), with when it was taken and
  the Custom Scenery stamp it was taken at;
* :func:`stop` -- Cancel: the child stops after the tiles in hand;
* :func:`live` -- the running count, from memory (a window following it);
* :func:`state` -- the kept result, ``measured_at``, ``stale`` (Custom
  Scenery, its ``scenery_packs.ini`` or the journal changed since),
  ``wanted`` (a ``zOrtho4XP_`` entry in Custom Scenery, or a tile the
  journal could adopt again), ``running`` with the live count, and
  ``auto``: start one now (wanted, not running, none kept or stale).
  ENGINE COMMAND ``world_measure_state``; both apps read it at their
  start, when Settings ▸ Storage opens and after a Convert step;
* :func:`start_auto` -- the Qt window's start: :func:`measure` in the
  background on a daemon thread when :func:`state` says ``auto``.

No tile or airport is named here.
"""
from __future__ import annotations

import json
import os
import queue as _queue
import threading
import time
from typing import Any, Callable, Dict, Optional

import O4_File_Names as FNAMES
import O4_Machine_Slots as SLOTS

__all__ = ["STORE_NAME", "measure", "stop", "state", "running", "live",
           "start_auto", "world_measure_state"]

STORE_NAME = "world_measure.json"
_PREFIX = "zOrtho4XP_"
_RUN = threading.Lock()
_LIVE: Dict[str, Any] = {"stop": None, "started_at": None, "progress": None,
                         "scenery": "", "background": False}
_LIVE_LOCK = threading.Lock()


def _store_path() -> str:
    return os.path.join(FNAMES.data_path("logs"), STORE_NAME)


def _read_store() -> dict:
    try:
        with open(_store_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _key(scenery_dir: str) -> str:
    return os.path.realpath(scenery_dir)


def scenery_stamp(scenery_dir: str) -> list:
    """What a measure depends on: Custom Scenery's entries, its
    ``scenery_packs.ini`` and the migration journal."""
    from .world_migrate import _JOURNAL, work_dir_for
    from .world_tile_facts import file_stamp
    return [file_stamp(scenery_dir),
            file_stamp(os.path.join(scenery_dir, "scenery_packs.ini")),
            file_stamp(os.path.join(work_dir_for(scenery_dir), _JOURNAL))]


def _wanted(scenery_dir: str) -> bool:
    """A ``zOrtho4XP_`` entry in Custom Scenery, or a tile the journal
    could adopt again (``world_adopt._pending``, journal only)."""
    try:
        if any(n.startswith(_PREFIX) for n in os.listdir(scenery_dir)):
            return True
    except OSError:
        return False
    from . import world_adopt as ADOPT
    from . import world_retire as RETIRE
    from .world_migrate import Journal, work_dir_for
    records = Journal(work_dir_for(scenery_dir)).records
    return next(ADOPT._pending(records, RETIRE.KEEP_ALL, ()), None) is not None


def running() -> bool:
    """Is a Measure running in this engine?"""
    return _RUN.locked()


def live() -> Dict[str, Any]:
    """The running Measure's ``running``, ``started_at`` and ``progress``
    (``{phase, done, total, tile}``), read from memory: what a window
    following it polls."""
    with _LIVE_LOCK:
        started, count = _LIVE["started_at"], _LIVE["progress"]
    busy = running()
    return {"running": busy, "started_at": started if busy else None,
            "progress": dict(count) if busy and count else None}


def state(scenery_dir: str = "") -> Dict[str, Any]:
    """The kept measure of ``scenery_dir`` and whether to start one (module
    doc): ``{"result", "measured_at", "stale", "wanted", "running",
    "started_at", "progress", "auto"}``."""
    from . import world_commands as WORLD
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    kept = _read_store().get(_key(scenery_dir)) if scenery_dir else None
    kept = kept if isinstance(kept, dict) else {}
    result = kept.get("result")
    stale = bool(result) and kept.get("stamp") != scenery_stamp(scenery_dir)
    wanted = bool(scenery_dir) and os.path.isdir(scenery_dir) and _wanted(scenery_dir)
    now = live()
    busy = now["running"]
    return {"result": result, "measured_at": kept.get("measured_at"),
            "stale": stale, "wanted": wanted, **now,
            "background": bool(_LIVE["background"]) if busy else False,
            "auto": wanted and not busy and (not result or stale)}


def world_measure_state(scenery_dir: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``world_measure_state`` (capability
    ``world_measure``): :func:`state`; synchronous (one small file, a
    folder listing and three ``stat``)."""
    return state(scenery_dir)


def _keep(scenery_dir: str, stamp: list, result: Dict[str, Any]) -> None:
    from .storage_installed import write_json
    data = _read_store()
    data[_key(scenery_dir)] = {"result": result,
                               "measured_at": result["measured_at"],
                               "stamp": stamp}
    write_json(_store_path(), data)


def _rates(scenery_dir: str) -> Optional[dict]:
    """The kept measure's seconds per tile (the sample is not run again)."""
    kept = _read_store().get(_key(scenery_dir)) or {}
    totals = (kept.get("result") or {}).get("totals") or {}
    rates = totals.get("seconds_per_tile")
    return dict(rates) if isinstance(rates, dict) and rates else None


# ----------------------------------------------------------- the child


def _watch(stop_event) -> None:
    """In the child: Cancel asked, or the engine gone -> stop."""
    import multiprocessing as mp

    from . import world_migrate as MIGRATE
    parent = mp.parent_process()
    while not stop_event.wait(0.25):
        if parent is not None and not parent.is_alive():
            os._exit(0)
    MIGRATE.stop()


def _child(out, stop_event, kwargs: dict) -> None:
    """The measure in the spawned process; ``out`` receives
    ``("progress", phase, done, total, tile)`` then ``("result", dict)``
    or ``("error", text)``."""
    if kwargs.pop("background", False):
        SLOTS.background_priority()
    threading.Thread(target=_watch, args=(stop_event,), daemon=True,
                     name="o4-measure-watch").start()
    from .world_tile_facts import TileFacts
    facts = TileFacts(kwargs.pop("facts_path", None))

    def emit(event) -> None:
        if type(event).__name__ == "WorldMigrateProgress":
            out.put(("progress", event.phase, event.done, event.total,
                     event.tile))
    try:
        runner = kwargs.pop("runner", None)
        if runner:                          # the twins' stand-in
            import importlib
            module, _, name = runner.partition(":")
            result = getattr(importlib.import_module(module), name)(
                emit=emit, **kwargs)
        else:
            from . import world_migrate as MIGRATE
            result = MIGRATE.run_command(True, emit=emit, facts=facts,
                                         **kwargs)
        out.put(("result", result))
    except Exception as error:              # the sentence goes to the app
        out.put(("error", str(error) or repr(error)))
    finally:
        facts.save()


# ------------------------------------------------------------ the parent


def _relay(emit, message) -> None:
    from .events import WorldMigrateProgress
    _tag, phase, done, total, tile = message
    with _LIVE_LOCK:
        _LIVE["progress"] = {"phase": phase, "done": done, "total": total,
                             "tile": tile}
    if emit:
        emit(WorldMigrateProgress(phase=phase, done=int(done),
                                  total=int(total), tile=tile or ""))


def _run_child(kwargs: dict, emit, stop_event) -> Dict[str, Any]:
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    out = ctx.Queue()
    child = ctx.Process(target=_child, args=(out, stop_event, kwargs),
                        daemon=True, name="o4-world-measure")
    child.start()
    answer = None
    try:
        while answer is None:
            try:
                message = out.get(timeout=0.5)
            except _queue.Empty:
                if not child.is_alive():
                    try:                     # the last words, if any
                        message = out.get(timeout=1.0)
                    except _queue.Empty:
                        raise ValueError(
                            "Measure stopped unexpectedly (exit code %s)."
                            % child.exitcode) from None
                else:
                    continue
            if message[0] == "progress":
                _relay(emit, message)
            else:
                answer = message
    finally:
        child.join(timeout=10)
        if child.is_alive():
            child.terminate()
    if answer[0] == "error":
        raise ValueError(answer[1])
    return answer[1]


def measure(scenery_dir: str = "", emit: Optional[Callable[[Any], None]] = None,
            *, tiles=None, workers: int = 4, background: bool = False,
            runner: Optional[str] = None, **extra) -> Dict[str, Any]:
    """The dry run on its own process (module doc); its result with
    ``measured_at`` (epoch seconds), kept when it measured every entry.
    One at a time: a second call while one runs raises ``ValueError``.
    ``runner`` (``"module:function"``) stands in for the dry run in the
    child, with ``extra`` its own arguments (the twins)."""
    from . import world_commands as WORLD
    from .world_tile_facts import default_path
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not scenery_dir or not os.path.isdir(scenery_dir):
        raise ValueError(f"No Custom Scenery folder ({scenery_dir!r}).")
    if not _RUN.acquire(blocking=False):
        raise ValueError("Measure is already running.")
    import multiprocessing as mp
    stop_event = mp.get_context("spawn").Event()
    with _LIVE_LOCK:
        _LIVE.update(stop=stop_event, started_at=time.time(), progress=None,
                     scenery=scenery_dir, background=bool(background))
    try:
        stamp = scenery_stamp(scenery_dir)
        kwargs = {"scenery_dir": scenery_dir, "tiles": tiles,
                  "workers": max(1, int(workers)),
                  "rates": _rates(scenery_dir), "background": bool(background),
                  "facts_path": default_path()}
        if runner:
            kwargs.update(extra, runner=runner)
        result = _run_child(kwargs, emit, stop_event)
        result["measured_at"] = time.time()
        if not tiles:
            _keep(scenery_dir, stamp, result)
        return result
    finally:
        with _LIVE_LOCK:
            _LIVE.update(stop=None, started_at=None, progress=None,
                         background=False)
        _RUN.release()


def stop() -> None:
    """Cancel the running Measure (it stops after the tiles in hand)."""
    with _LIVE_LOCK:
        event = _LIVE["stop"]
    if event is not None:
        event.set()


def start_auto(scenery_dir: str = "",
               done: Optional[Callable[[Any], None]] = None) -> bool:
    """:func:`measure` in the background on a daemon thread when
    :func:`state` says ``auto``; ``done(result or exception)`` after.
    True when it started."""
    try:
        if not state(scenery_dir)["auto"]:
            return False
    except (OSError, ValueError):
        return False

    def work() -> None:
        try:
            outcome: Any = measure(scenery_dir, background=True)
        except Exception as error:          # kept for the caller
            outcome = error
        if done:
            done(outcome)
    threading.Thread(target=work, daemon=True, name="o4-world-measure").start()
    return True
