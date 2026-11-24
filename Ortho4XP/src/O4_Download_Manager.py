"""The engine's download manager: each shared resource fetched ONCE across
every process of the machine (issue #2258).

A request names a :class:`Resource` by key.  :func:`fetch` returns when the
file is installed, the transfer failed, or the caller stopped.

* SINGLE FLIGHT.  The transfer runs under an OS lock on the resource's lock
  file (``O4_Machine_Slots.try_os_lock``).  Taking it is atomic, so there is
  no check-then-create window, and the system drops it when the holder dies,
  however it dies.  A second caller finds the lock held, JOINS, and is woken
  by the file landing.  It shares a failure of the flight it waited for; a
  flight that was stopped or crashed is taken over by one of its waiters.
* ATOMIC INSTALL.  Bytes go to ``<target>.tmp-<pid>-<thread>``, are checked
  (length, the resource's own validator) and move with one ``os.replace``.
* STALE TEMPORARIES.  Every exit removes its own temporary.  What a killed
  process left is removed by the next flight of that resource and by
  :func:`sweep_stale_temporaries` at engine start.
* LIMITS.  A transfer holds one slot of its server's class and one of the
  total class (``O4_Machine_Slots`` named classes, shared by the session's
  processes).  A wait for them ends only at the slot or at Stop.
* REQUEST COUNT.  ``.download_manager/<key>.json`` beside the target (or
  in the resource's ``state_dir``) keeps each resource's request count and
  last outcome (:func:`request_counts`).
* CALLER TRANSFERS.  A resource whose bytes come from more than one GET
  (an Overpass query with its server rotation, a base DEM archive with
  its redirect and outcome law) passes ``transfer``: the manager keeps
  the single flight, the install and Stop, and the transfer holds its
  own server's limit (:func:`server_slot`).
* LOCKS ALONE.  :func:`hold_flight` is the single-flight wait without a
  file to install: a work section (a base cell with its fallbacks, a
  tile's airport-inset pass) that one process at a time may run.

A joiner's wait is marked ``O4_Step_Wait.waiting``, and so is a wait for
a server slot, so that neither holds a scheduler slot: these limits are
what bound the server.  No GUI-toolkit imports (core-module rule).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import O4_File_Lock as FILE_LOCK
import O4_File_Names as FNAMES
import O4_Held_File as HELD
import O4_Machine_Slots as SLOTS
import O4_Step_Wait as STEP_WAIT
import requests

__all__ = ["FAILED", "INVALID", "READY", "STOPPED", "Resource", "Result",
           "Watcher", "fetch", "hold_flight", "in_flight", "request_counts",
           "server_slot", "sweep_stale_temporaries", "write_body"]

READY = "ready"
FAILED = "failed"
INVALID = "invalid"      # the server answered with something else
STOPPED = "stopped"

#: Transfers at once to one server, and in total, across the session.  The
#: server figure is the concurrency the OSM class allowed this path before.
SERVER_LIMIT = 4
TOTAL_LIMIT = 8
TOTAL_CLASS = "download-total"

#: How often a joiner looks for the file, the lock and Stop.
POLL_SECONDS = 0.25
#: Stop is checked between chunks: at 400 KB/s this is under a second.
CHUNK_BYTES = 1 << 18
HTTP_TIMEOUT_SECONDS = 60
#: A sweep without the flight lock leaves a temporary this recently written
#: (a live transfer on another machine sharing the folder writes at least
#: once per read timeout) ...
SWEEP_GRACE_SECONDS = 2 * HTTP_TIMEOUT_SECONDS
#: ... and treats one this old as abandoned whoever its pid now names.
ABANDONED_SECONDS = 3600.0

_STATE_FOLDER = ".download_manager"
_TEMPORARY = re.compile(r"^(?P<target>.+)\.tmp-(?P<pid>\d+)-\d+$")


@dataclass(frozen=True)
class Resource:
    """One file to fetch: ``key`` identifies it to every process.

    ``shares_failure``: a caller that waited on a flight which failed
    fails with it; ``False`` makes it fly once more itself (a transfer
    whose failure carries an exception the caller must raise).
    ``state_dir``: where the flight lock and the state live, when not in
    ``.download_manager`` beside the target (resources in different
    folders that share one key share one flight only through it)."""

    key: str
    url: str
    target: str
    is_valid: Callable[[str], bool] = os.path.isfile
    shares_failure: bool = True
    state_dir: Optional[str] = None


@dataclass(frozen=True)
class Result:
    """How a :func:`fetch` ended.  ``joined``: it waited on another
    caller's flight; ``transferred``: this call made the request."""

    status: str
    joined: bool = False
    transferred: bool = False
    received: int = 0
    error: Optional[BaseException] = None

    @property
    def ok(self) -> bool:
        return self.status == READY


class Watcher:
    """What a caller hears about its request; every method optional."""

    def joined(self) -> None:
        """Another caller is fetching this resource; this one waits."""

    def leading(self) -> None:
        """This caller makes the transfer."""

    def started(self, total_bytes: int) -> None:
        """The server answered; 0 when it named no length."""

    def chunk(self, size: int, received: int, total_bytes: int) -> None:
        """``size`` more bytes are on disk."""

    def finished(self) -> None:
        """The request ended, however it ended."""


def _state_stem(resource: Resource) -> str:
    """``<folder>/<readable key>-<hash>``: the lock and state share it."""
    safe = "".join(c if c.isalnum() or c in "._-" else "_"
                   for c in resource.key)
    digest = hashlib.sha1(resource.key.encode("utf-8")).hexdigest()[:8]
    folder = resource.state_dir or os.path.join(
        os.path.dirname(resource.target), _STATE_FOLDER)
    return os.path.join(folder, "%s-%s" % (safe[:64], digest))


def _write_state(path: str, state: dict) -> None:
    """Atomic and best effort: bookkeeping never fails a download."""
    temporary = "%s.tmp-%d-%d" % (path, os.getpid(), threading.get_ident())
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(state, handle)
        HELD.retrying_a_held_file(lambda: os.replace(temporary, path))
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(temporary)


def _is_valid(resource: Resource, path: str) -> bool:
    try:
        return bool(resource.is_valid(path))
    except Exception:
        return False


def _never() -> bool:
    return False


def fetch(resource: Resource, *, refresh: bool = False,
          should_stop: Optional[Callable[[], bool]] = None,
          watcher: Optional[Watcher] = None,
          open_stream: Optional[Callable] = None,
          server_limit: int = SERVER_LIMIT,
          total_limit: int = TOTAL_LIMIT,
          transfer: Optional[Callable[[str, Callable[[], bool]],
                                      object]] = None) -> Result:
    """Make ``resource.target`` present, transferring it at most once.

    ``refresh``: a valid target does not satisfy the request; a transfer
    that finishes after this call began does.  ``open_stream`` replaces
    ``requests.get``.  ``transfer(temporary, should_stop)`` replaces the
    whole GET: it writes the bytes to ``temporary`` and returns
    :data:`READY` (or True), :data:`FAILED` (or False / None) or
    :data:`STOPPED`; what it raises is the result's ``error``, and it
    holds its own server limit (no slot is taken for it here).  Never
    raises for a network or file failure."""
    watch = watcher or Watcher()
    if transfer is None:
        move = _streamed(resource.url, watch, open_stream or requests.get,
                         (server_limit, total_limit))
    else:
        move = _made(transfer)
    try:
        return _join_or_lead(resource, refresh, should_stop or _never, watch,
                             move)
    except OSError as error:           # the store's folder cannot be used
        return Result(FAILED, error=error)
    finally:
        watch.finished()


def _wait_for_flight(lock_path: str, stop, ready=None, on_join=None):
    """The flight lock's descriptor once held; :data:`READY` when
    ``ready()`` comes true first, :data:`STOPPED` at Stop.  The wait holds
    no scheduler slot.  ``OSError``: the lock file cannot be opened."""
    flight = SLOTS.try_os_lock(lock_path)
    if flight is not None:
        return flight
    if on_join is not None:
        on_join()
    with STEP_WAIT.waiting():
        while True:
            time.sleep(POLL_SECONDS)
            if ready is not None and ready():
                return READY
            if stop():
                return STOPPED
            flight = SLOTS.try_os_lock(lock_path)
            if flight is not None:
                return flight


@contextlib.contextmanager
def hold_flight(lock_path: str,
                should_stop: Optional[Callable[[], bool]] = None):
    """Run the block as the one flight of ``lock_path`` across every
    process: yields True once this caller holds it, False when Stop came
    first (the block must then do nothing).  A holder that dies releases
    it; the wait has no time limit and holds no scheduler slot.

    The lock file exists only while it is held (it is coordination state
    inside a cache, so its name ends in ``.lock``, the one name the
    shared-repo guard allows): the holder removes it, and a caller that
    locked a file removed meanwhile locks the new one instead.  A lock
    file that cannot be opened at all runs the block unlocked (True), as
    an advisory lock must."""
    stop = should_stop or _never
    try:
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        flight = _hold_current(lock_path, stop)
    except OSError:
        yield True
        return
    if flight == STOPPED:
        yield False
        return
    try:
        yield True
    finally:
        _release_flight(lock_path, flight)


def _hold_current(lock_path: str, stop):
    """:func:`_wait_for_flight` until the descriptor held is the file
    the path names now (a holder that left removed the one it held)."""
    while True:
        flight = _wait_for_flight(lock_path, stop)
        if flight == STOPPED:
            return flight
        try:
            held, named = os.fstat(flight), os.stat(lock_path)
            if (held.st_dev, held.st_ino) == (named.st_dev, named.st_ino):
                return flight
        except OSError:
            pass
        SLOTS.release_os_lock(flight)


def _release_flight(lock_path: str, flight) -> None:
    """Remove the lock file, then let it go.  Windows refuses to remove
    a file another process has open, so there the file goes after."""
    if sys.platform != "win32":
        with contextlib.suppress(OSError):
            os.remove(lock_path)
    SLOTS.release_os_lock(flight)
    if sys.platform == "win32":
        with contextlib.suppress(OSError):
            os.remove(lock_path)


@contextlib.contextmanager
def server_slot(url: str, should_stop: Optional[Callable[[], bool]] = None,
                server_limit: int = SERVER_LIMIT,
                total_limit: int = TOTAL_LIMIT):
    """One slot of ``url``'s server class and one of the total class for
    the block, waited for until free or Stop (never past a time limit):
    yields True when both are held.  The wait holds no scheduler slot."""
    wait = {"timeout_s": math.inf, "poll_s": POLL_SECONDS,
            "give_up": should_stop or _never}
    with contextlib.ExitStack() as stack:
        with STEP_WAIT.waiting():
            server = stack.enter_context(SLOTS.hold_class(
                SLOTS.net_class(url), server_limit, **wait))
            total = (stack.enter_context(SLOTS.hold_class(
                TOTAL_CLASS, total_limit, **wait)) if server.count else None)
        yield bool(server.count and total is not None and total.count)


def _join_or_lead(resource, refresh, stop, watch, move) -> Result:
    """Wait for the file or the flight lock; the holder flies."""
    asked_at = time.time()
    stem = _state_stem(resource)
    joined = []

    def ready() -> bool:
        return not refresh and _is_valid(resource, resource.target)

    def join() -> None:
        joined.append(True)
        watch.joined()

    if ready():
        return Result(READY)
    if stop():
        return Result(STOPPED)
    os.makedirs(os.path.dirname(stem), exist_ok=True)
    flight = _wait_for_flight(stem + ".lock", stop, ready, join)
    if isinstance(flight, str):
        return Result(flight, joined=True)
    try:
        return _fly(resource, stem, refresh, asked_at, bool(joined), stop,
                    watch, move)
    finally:
        SLOTS.release_os_lock(flight)


def _fly(resource, stem, refresh, asked_at, joined, stop, watch,
         move) -> Result:
    """The flight, under its lock: settle what a previous flight decided,
    else transfer."""
    _remove_stale_temporaries(os.path.dirname(resource.target),
                              os.path.basename(resource.target), 0.0)
    if not refresh and _is_valid(resource, resource.target):
        return Result(READY, joined=joined)
    state_path = stem + ".json"
    state = FNAMES.read_json_dict(state_path)
    if float(state.get("finished_at", 0)) >= asked_at:
        # A flight ended after this request began, so this caller waited
        # for it: it shares that answer.  A stopped one answers nothing.
        if state.get("outcome") == READY and _is_valid(resource,
                                                       resource.target):
            return Result(READY, joined=joined)
        if (resource.shares_failure
                and state.get("outcome") in (FAILED, INVALID)
                and state.get("url") == resource.url):
            return Result(state["outcome"], joined=joined)
    watch.leading()

    def begin() -> None:
        state.update(key=resource.key, url=resource.url, outcome="running",
                     requests=int(state.get("requests", 0)) + 1,
                     pid=os.getpid(), started_at=time.time())
        _write_state(state_path, state)

    result = _install(resource, stop, joined, move, begin)
    if result.transferred:
        state.update(outcome=result.status, finished_at=time.time(),
                     received=result.received,
                     error=str(result.error)[:200] if result.error else "")
        _write_state(state_path, state)
    return result


def _content_length(response) -> int:
    """The body's length on disk, 0 when the response does not say it (or
    says it of an encoded body)."""
    headers = getattr(response, "headers", None) or {}
    if headers.get("Content-Encoding"):
        return 0
    try:
        return max(0, int(headers.get("Content-Length", 0)))
    except (TypeError, ValueError):
        return 0


def _install(resource, stop, joined, move, begin) -> Result:
    """Run ``move`` into a private temporary and install what it wrote;
    the temporary is gone on every exit.  ``begin()`` is called by the
    move once its request is about to be made."""
    temporary = "%s.tmp-%d-%d" % (resource.target, os.getpid(),
                                  threading.get_ident())
    begun = []

    def started() -> None:
        begun.append(True)
        begin()

    received = 0
    try:
        (status, received) = move(temporary, stop, started)
        if status != READY:
            return Result(status, joined, bool(begun), received)
        if stop():
            return Result(STOPPED, joined, True, received)
        if not _is_valid(resource, temporary):
            return Result(INVALID, joined, True, received)
        HELD.retrying_a_held_file(
            lambda: os.replace(temporary, resource.target))
        return Result(READY, joined, True, received)
    except Exception as error:
        return Result(FAILED, joined, bool(begun), received, error)
    finally:
        with contextlib.suppress(OSError):
            os.remove(temporary)


def _streamed(url, watch, open_stream, limits):
    """The manager's own move: one GET within the server's and the total
    limit, streamed with Stop between chunks."""
    def move(temporary, stop, begin):
        with server_slot(url, stop, *limits) as held:
            if not held or stop():
                return (STOPPED, 0)
            begin()
            return _stream(url, temporary, stop, watch, open_stream)
    return move


def _stream(url, temporary, stop, watch, open_stream):
    with open_stream(url, stream=True,
                     timeout=HTTP_TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        return write_body(response, temporary, stop, watch)


def write_body(response, path: str,
               should_stop: Optional[Callable[[], bool]] = None,
               watcher: Optional[Watcher] = None):
    """Stream a ``stream=True`` response's body to ``path``, looking at
    Stop between chunks: ``(READY or STOPPED, bytes written)``.  A body
    shorter than the length the server named raises ``OSError``."""
    stop = should_stop or _never
    watch = watcher or Watcher()
    total = _content_length(response)
    watch.started(total)
    received = 0
    with open(path, "wb") as output:
        for chunk in response.iter_content(CHUNK_BYTES):
            if stop():
                return (STOPPED, received)
            output.write(chunk)
            received += len(chunk)
            watch.chunk(len(chunk), received, total)
    if total and received != total:
        raise OSError("the transfer ended at %d of %d bytes"
                      % (received, total))
    return (READY, received)


def _made(transfer):
    """A caller's transfer as a move: its answer normalised to a status,
    what it wrote counted."""
    def move(temporary, stop, begin):
        begin()
        answer = transfer(temporary, stop)
        if answer is True:
            answer = READY
        elif answer in (False, None):
            answer = FAILED
        try:
            received = os.path.getsize(temporary)
        except OSError:
            received = 0
        return (answer, received)
    return move


def in_flight(resource: Resource) -> bool:
    """Is some process fetching ``resource`` right now?"""
    path = _state_stem(resource) + ".lock"
    if not os.path.exists(path):
        return False
    try:
        flight = SLOTS.try_os_lock(path)
    except OSError:
        return False
    if flight is None:
        return True
    SLOTS.release_os_lock(flight)
    return False


def _temporary_is_stale(path: str, pid: int, grace: float, now: float) -> bool:
    try:
        age = now - os.path.getmtime(path)
    except OSError:
        return False
    if age > ABANDONED_SECONDS:
        return True
    return age >= grace and not FILE_LOCK.process_is_running(pid)


def _remove_stale_temporaries(directory: str, target_name: Optional[str],
                              grace: float) -> int:
    """Remove the dead transfers' temporaries in ``directory`` (of one
    target's name when given); the count removed."""
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    now = time.time()
    removed = 0
    for name in names:
        match = _TEMPORARY.match(name)
        if match is None or int(match.group("pid")) == os.getpid():
            continue
        if target_name is not None and match.group("target") != target_name:
            continue
        path = os.path.join(directory, name)
        if _temporary_is_stale(path, int(match.group("pid")), grace, now):
            with contextlib.suppress(OSError):
                os.remove(path)
                removed += 1
    return removed


def sweep_stale_temporaries(directory: str) -> int:
    """Remove what killed transfers left in ``directory`` (engine start);
    a live transfer's temporary is kept.  The count removed."""
    return sum(_remove_stale_temporaries(folder, None, SWEEP_GRACE_SECONDS)
               for folder in (directory,
                              os.path.join(directory, _STATE_FOLDER)))


def request_counts(directory: str) -> dict:
    """``{resource key: GET requests made}`` for the targets in
    ``directory``, across every process and run."""
    folder = os.path.join(directory, _STATE_FOLDER)
    try:
        names = os.listdir(folder)
    except OSError:
        return {}
    counts = {}
    for name in names:
        if name.endswith(".json"):
            state = FNAMES.read_json_dict(os.path.join(folder, name))
            if "key" in state:
                counts[state["key"]] = int(state.get("requests", 0))
    return counts
