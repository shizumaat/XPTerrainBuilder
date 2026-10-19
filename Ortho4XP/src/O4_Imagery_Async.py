"""The async HTTP/2 imagery path: the ``O4_IMAGERY_FETCHER`` chooser and the prefetch.

imagery-fetch-spec section 5 (RULINGS 2026-10-17c; owner 17a Q4). The threaded ``requests``
fetcher in ``O4_Imagery_Utils`` stays the default; ``O4_IMAGERY_FETCHER=async`` routes the
parts of a webmercator texture through the ported ``O4_Imagery_Fetch.Fetcher`` (curl_cffi,
libcurl multi, HTTP/2 over TLS, per-host AIMD window, hedging, Retry-After).

How the two paths share ONE answer-handling code: the async path only PREFETCHES. Each part
then runs through the unchanged ``get_and_paste_wmts_part`` → ``get_wmts_image`` →
``http_request_to_image`` chain with a :class:`PartSession` whose first ``get`` returns the
prefetched answer (:class:`PrefetchedResponse`, shaped like the ``requests`` response that
chain reads). Placeholder tests, status handling, the parent-zoom fallback, the
``(success, image)`` contract and the white square are therefore the threaded path's own
code. A part's SECOND request (a parent tile after a placeholder, a retry after a 429 the
fetcher's budget gave up on) goes to the threaded path's ``requests`` session.

One event loop, on one daemon thread, serves the whole process: a curl_cffi session is bound
to the loop it was made on, and a long-lived loop keeps the HTTP/2 connections alive from one
texture to the next. Fetchers are pooled per (provider code, cap): a texture takes an idle
one, so the AIMD window and the 429 pause a provider taught the previous texture carry over.
Two textures downloading at the same time take two fetchers (E's ``fetch_many`` admits one
run at a time), so the in-flight bound per provider is (concurrent textures) x
``max_threads`` — the same bound the threaded path has today. Pause state is per fetcher,
not shared between two concurrent textures (the threaded path's ``O4_Http_Pushback`` host
pause is not consulted here).

Nothing here knows a tile or a provider format; ``O4_Imagery_Utils`` builds the requests.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Callable, Sequence
from typing import Any

import requests
from requests.structures import CaseInsensitiveDict

FETCHER_ENV = "O4_IMAGERY_FETCHER"
"""``async`` or ``threads`` (default). Any other value reads as ``threads``."""

CANCEL_POLL_S = 0.2
"""How often the ``should_stop`` predicate (``UI.red_flag``) is read during a prefetch."""

__all__ = [
    "FETCHER_ENV",
    "PartSession",
    "PrefetchedResponse",
    "async_available",
    "fetch_parts",
    "fetcher_choice",
]


def fetcher_choice() -> str:
    """``"async"`` (the default, owner RULINGS 2026-10-17e) when curl_cffi imports, else ``"threads"``.

    ``O4_IMAGERY_FETCHER=threads`` opts back into the threaded fetcher; any other value,
    unset included, is ``async``.
    """
    if os.environ.get(FETCHER_ENV, "").strip().lower() == "threads":
        return "threads"
    return "async" if async_available() else "threads"


_available: list[bool] = []


def async_available() -> bool:
    """True when curl_cffi (and so ``O4_Imagery_Fetch``) imports; printed once when it does not."""
    if not _available:
        try:
            import O4_Imagery_Fetch  # noqa: F401  (imports curl_cffi)

            _available.append(True)
        except ImportError as exc:
            print(
                "WARNING:",
                FETCHER_ENV + "=async needs curl_cffi (" + str(exc) + "); using the threaded fetcher.",
            )
            _available.append(False)
    return _available[0]


class PrefetchedResponse:
    """The parts of a ``requests.Response`` that ``http_request_to_image`` reads.

    ``o4_prefetched`` tells that function the transfer was already metered.
    """

    o4_prefetched = True

    def __init__(self, status_code: int, headers: dict[str, str], content: bytes) -> None:
        self.status_code = status_code
        self.headers = CaseInsensitiveDict(headers)
        self.content = content

    def __str__(self) -> str:
        return "<Response [%d]>" % self.status_code


class PartSession:
    """A session for ONE part: its first ``get`` is the prefetched answer, later ones go on.

    The first ``get`` of a part is, by construction of ``get_wmts_image``, that part's own
    tile request (its ``{switch:}`` server may differ, the tile does not), so the answer is
    served without comparing URLs. A transport failure the fetcher gave up on is raised as
    ``requests.ConnectionError``, which the threaded chain handles as it handles its own.
    """

    def __init__(self, first: Any, fallback: requests.Session) -> None:
        self._first = first
        self._fallback = fallback

    def get(self, url: str, timeout: float | None = None, headers: dict | None = None) -> Any:
        first, self._first = self._first, None
        if isinstance(first, BaseException):
            raise first
        if first is not None:
            return first
        if headers:
            return self._fallback.get(url, timeout=timeout, headers=headers)
        return self._fallback.get(url, timeout=timeout)


def answer_of(result: Any) -> Any:
    """The first-``get`` answer of a ``FetchResult``: a response, or the exception to raise."""
    if result.status:
        return PrefetchedResponse(result.status, result.headers, result.body)
    return requests.exceptions.ConnectionError(result.detail or result.error or "no answer")


# --- the process-wide loop and the fetcher pool -------------------------------------------------

_loop_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_idle: dict[tuple[str, int, float | None], list[Any]] = {}


def _event_loop() -> asyncio.AbstractEventLoop:
    """The one loop every prefetch runs on, started on first use on a daemon thread."""
    global _loop
    with _loop_lock:
        if _loop is None:
            loop = asyncio.new_event_loop()
            threading.Thread(
                target=loop.run_forever, name="o4-imagery-fetch", daemon=True
            ).start()
            _loop = loop
        return _loop


def _checkout(group: str, cap: int, timeout_s: float | None = None) -> Any:
    from O4_Imagery_Fetch import Fetcher

    with _loop_lock:
        pool = _idle.get((group, cap, timeout_s))
        if pool:
            return pool.pop()
    if timeout_s is None:
        return Fetcher(max_in_flight=cap, start_in_flight=cap)
    return Fetcher(max_in_flight=cap, start_in_flight=cap, timeout_s=timeout_s)


def _checkin(group: str, cap: int, fetcher: Any, timeout_s: float | None = None) -> None:
    with _loop_lock:
        _idle.setdefault((group, cap, timeout_s), []).append(fetcher)


async def _watch(should_stop: Callable[[], bool], cancel: asyncio.Event) -> None:
    while not should_stop():
        await asyncio.sleep(CANCEL_POLL_S)
    cancel.set()


def fetch_parts(
    parts: Sequence[tuple[Any, str, dict[str, str]]],
    group: str,
    cap: int,
    should_stop: Callable[[], bool] = lambda: False,
    on_result: Callable[[Any], None] | None = None,
    timeout_s: float | None = None,
) -> dict[Any, Any]:
    """Fetch ``(key, url, headers)`` parts; returns ``{key: FetchResult}`` in part order.

    ``group`` is the AIMD host group (the provider code), ``cap`` the provider's
    ``max_threads``: the window never exceeds it. ``should_stop`` is polled every
    :data:`CANCEL_POLL_S`; when it turns true the run is cancelled and the parts not yet
    answered come back with ``error="SYS_CANCELLED"``. ``on_result`` runs on the loop thread
    as each part completes (the download meter's feed). ``timeout_s`` is the provider's
    ``timeout=`` (seconds); None keeps the fetcher's default.
    """
    from O4_Imagery_Fetch import FetchRequest

    if not parts:
        return {}
    cap = max(1, int(cap))
    requests_ = [FetchRequest(key, url, dict(headers or {}), group) for key, url, headers in parts]
    fetcher = _checkout(group, cap, timeout_s)

    async def run() -> list[Any]:
        cancel = asyncio.Event()
        watcher = asyncio.create_task(_watch(should_stop, cancel))
        try:
            return await fetcher.fetch_many(
                requests_, on_result=on_result, cancel=cancel, keep_results=True
            )
        finally:
            watcher.cancel()

    try:
        results = asyncio.run_coroutine_threadsafe(run(), _event_loop()).result()
    finally:
        _checkin(group, cap, fetcher, timeout_s)
    return {r.key: r for r in results}
