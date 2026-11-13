"""The live preview's mip reads, off the command loop (#2001 follow-up:
the map shows each square at the resolution it is drawn, up to the full
4096 px texture).

A level up to ``O4_Live_Preview.INLINE_MIP_PX`` is read where it is
asked for (~10 ms).  A finer one costs up to ~0.5 s (4096 px: decode
0.43 s, JPEG 0.09 s, measured on a World-pack texture), more than the
transport's read loop may stall, so :func:`mip` queues it for a worker
and replies ``{"pending": true}``; the app asks again and gets it from
the cache.  ``wait=True`` (the Qt window's own background thread) reads
it at once.

Bounds: replies are kept by (path, mtime, size, px) up to
:data:`CACHE_MB` of encoded bytes (``O4_Live_Preview.ByteLRU``); at most
:data:`QUEUE_MAX` levels wait, first asked first read, and one not asked
for again within :data:`ASK_TTL_S` (the map moved on) is dropped unread.
A read that fails answers its next ask with the error once.
"""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict

import O4_Live_Preview as LIVE

__all__ = ["ASK_TTL_S", "CACHE_MB", "QUEUE_MAX", "WORKERS", "mip"]

#: Encoded replies kept, in MB.
CACHE_MB = 96
#: Levels waiting for a worker.
QUEUE_MAX = 8
#: A queued level not asked for again within this many seconds is dropped.
ASK_TTL_S = 2.0
#: Worker threads (each holds one decoded level, 64 MB at 4096 px).
WORKERS = 2

_LOCK = threading.Condition()
_CACHE = LIVE.ByteLRU(CACHE_MB << 20)
_QUEUE: "OrderedDict[tuple, float]" = OrderedDict()   # key -> last asked
_ERRORS: dict = {}
_THREADS: list = []
_PENDING = {"pending": True}


def _key(path: str, px: int) -> tuple:
    st = os.stat(path)
    return (path, st.st_mtime_ns, st.st_size,
            max(LIVE.MIN_MIP_PX, min(LIVE.MAX_MIP_PX, int(px))))


def _store(key: tuple, reply: dict) -> None:
    _CACHE.put(key, reply, len(reply.get("data", "")) + 64)


def mip(path: str, px: int, wait: bool = False) -> dict:
    """``O4_Live_Preview.mip_image`` of ``path`` at ``px``, or
    ``{"pending": True}`` while a worker reads it (the module docstring).
    ``ValueError`` / ``OSError`` for a texture that cannot be read."""
    key = _key(str(path), px)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            return hit
        error = _ERRORS.pop(key, None)
        if error is not None:
            raise error
        if not wait and key[3] > LIVE.INLINE_MIP_PX:
            if key in _QUEUE or len(_QUEUE) < QUEUE_MAX:
                _QUEUE[key] = time.monotonic()
                _start_workers()
                _LOCK.notify()
            return dict(_PENDING)
    reply = LIVE.mip_image(key[0], key[3])
    with _LOCK:
        _store(key, reply)
    return reply


def _start_workers() -> None:
    _THREADS[:] = [t for t in _THREADS if t.is_alive()]
    while len(_THREADS) < WORKERS:
        thread = threading.Thread(target=_work, name="live-preview-mip",
                                  daemon=True)
        _THREADS.append(thread)
        thread.start()


def _next() -> "tuple | None":
    """The oldest queued key still wanted (callers hold ``_LOCK``)."""
    now = time.monotonic()
    while _QUEUE:
        key, asked = _QUEUE.popitem(last=False)
        if now - asked <= ASK_TTL_S:
            return key
    return None


def _work() -> None:
    while True:
        with _LOCK:
            key = _next()
            if key is None:
                _LOCK.wait(timeout=30.0)
                key = _next()
                if key is None:
                    continue
        try:
            reply = LIVE.mip_image(key[0], key[3])
        except (OSError, ValueError) as error:
            with _LOCK:
                _ERRORS[key] = error
            continue
        with _LOCK:
            _store(key, reply)
