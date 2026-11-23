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
* REQUEST COUNT.  ``.download_manager/<key>.json`` beside the target keeps
  each resource's GET count and last outcome (:func:`request_counts`).

Callers wrap the call in ``O4_Step_Wait.waiting`` so that neither a joiner
nor a transfer holds a scheduler slot: these limits are what bound the
server.  No GUI-toolkit imports (core-module rule).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import O4_File_Lock as FILE_LOCK
import O4_File_Names as FNAMES
import O4_Held_File as HELD
import O4_Machine_Slots as SLOTS
import requests

__all__ = ["FAILED", "INVALID", "READY", "STOPPED", "Resource", "Result",
           "Watcher", "fetch", "in_flight", "request_counts",
           "sweep_stale_temporaries"]

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
    """One file to fetch: ``key`` identifies it to every process."""

    key: str
    url: str
    target: str
    is_valid: Callable[[str], bool] = os.path.isfile


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
    return os.path.join(os.path.dirname(resource.target), _STATE_FOLDER,
                        "%s-%s" % (safe[:64], digest))


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
          total_limit: int = TOTAL_LIMIT) -> Result:
    """Make ``resource.target`` present, transferring it at most once.

    ``refresh``: a valid target does not satisfy the request; a transfer
    that finishes after this call began does.  ``open_stream`` replaces
    ``requests.get``.  Never raises for a network or file failure."""
    watch = watcher or Watcher()
    limits = (server_limit, total_limit)
    try:
        return _join_or_lead(resource, refresh, should_stop or _never, watch,
                             open_stream or requests.get, limits)
    except OSError as error:           # the store's folder cannot be used
        return Result(FAILED, error=error)
    finally:
        watch.finished()


def _join_or_lead(resource, refresh, stop, watch, open_stream,
                  limits) -> Result:
    """Wait for the file or the flight lock; the holder flies."""
    asked_at = time.time()
    stem = _state_stem(resource)
    os.makedirs(os.path.dirname(stem), exist_ok=True)
    joined = False
    while True:
        if not refresh and _is_valid(resource, resource.target):
            return Result(READY, joined=joined)
        if stop():
            return Result(STOPPED, joined=joined)
        flight = SLOTS.try_os_lock(stem + ".lock")
        if flight is not None:
            break
        if not joined:
            joined = True
            watch.joined()
        time.sleep(POLL_SECONDS)
    try:
        return _fly(resource, stem, refresh, asked_at, joined, stop, watch,
                    open_stream, limits)
    finally:
        SLOTS.release_os_lock(flight)


def _fly(resource, stem, refresh, asked_at, joined, stop, watch, open_stream,
         limits) -> Result:
    """The flight, under its lock: settle what a previous flight decided,
    else transfer within the limits."""
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
        if (state.get("outcome") in (FAILED, INVALID)
                and state.get("url") == resource.url):
            return Result(state["outcome"], joined=joined)
    watch.leading()
    wait = {"timeout_s": math.inf, "poll_s": POLL_SECONDS, "give_up": stop}
    with SLOTS.hold_class(SLOTS.net_class(resource.url), limits[0],
                          **wait) as server, \
            SLOTS.hold_class(TOTAL_CLASS, limits[1], **wait) as total:
        if not server.count or not total.count:
            return Result(STOPPED, joined=joined)
        state.update(key=resource.key, url=resource.url, outcome="running",
                     requests=int(state.get("requests", 0)) + 1,
                     pid=os.getpid(), started_at=time.time())
        _write_state(state_path, state)
        result = _transfer(resource, stop, watch, open_stream, joined)
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


def _transfer(resource, stop, watch, open_stream, joined) -> Result:
    """Stream to a private temporary and install it; the temporary is gone
    on every exit."""
    temporary = "%s.tmp-%d-%d" % (resource.target, os.getpid(),
                                  threading.get_ident())
    received = 0
    try:
        with open_stream(resource.url, stream=True,
                         timeout=HTTP_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            total = _content_length(response)
            watch.started(total)
            with open(temporary, "wb") as output:
                for chunk in response.iter_content(CHUNK_BYTES):
                    if stop():
                        return Result(STOPPED, joined, True, received)
                    output.write(chunk)
                    received += len(chunk)
                    watch.chunk(len(chunk), received, total)
        if stop():
            return Result(STOPPED, joined, True, received)
        if total and received != total:
            raise OSError("the transfer ended at %d of %d bytes"
                          % (received, total))
        if not _is_valid(resource, temporary):
            return Result(INVALID, joined, True, received)
        HELD.retrying_a_held_file(
            lambda: os.replace(temporary, resource.target))
        return Result(READY, joined, True, received)
    except Exception as error:
        return Result(FAILED, joined, True, received, error)
    finally:
        with contextlib.suppress(OSError):
            os.remove(temporary)


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
