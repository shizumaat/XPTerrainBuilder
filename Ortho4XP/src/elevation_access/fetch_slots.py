"""Politeness: how many requests may be in flight against one server.

One bounded semaphore per provider code, sized by the definition's
``fetch_slots`` key, and a wait that honours the Stop button.
"""

import contextlib as _contextlib
import threading

import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError
from elevation_access.definitions import _parse_float

__all__ = [
    "_held_provider_fetch_slot",
    "provider_fetch_slots",
]


# Per-provider politeness cap for the concurrent airport fetches: at most
# this many in-flight requests against any single elevation server.
_PROVIDER_CONCURRENT_FETCHES = 2


_provider_fetch_slots: dict = {}


_provider_fetch_slots_lock = threading.Lock()


def _provider_fetch_slot(code, slots=None):
    """The provider's politeness semaphore.  ``slots`` (a definition's
    ``fetch_slots`` key, #130) sizes it the first time the provider is
    seen; every provider without the key keeps
    :data:`_PROVIDER_CONCURRENT_FETCHES`."""
    with _provider_fetch_slots_lock:
        slot = _provider_fetch_slots.get(code)
        if slot is None:
            slot = threading.BoundedSemaphore(
                int(slots) if slots else _PROVIDER_CONCURRENT_FETCHES)
            _provider_fetch_slots[code] = slot
        return slot


def provider_fetch_slots(definition):
    """``fetch_slots`` of a definition (parallel connections to its
    server), else the module default."""
    value = _parse_float((definition or {}).get("fetch_slots"),
                         default=None)
    if value is None or value < 1:
        return _PROVIDER_CONCURRENT_FETCHES
    return int(value)


@_contextlib.contextmanager
def _held_provider_fetch_slot(code, slots=None):
    """Hold one of the provider's fetch slots, honoring Stop while queued.

    A bare ``with semaphore:`` blocks uninterruptibly — with several
    tiles fetching, airports queue behind the concurrency cap for
    MINUTES, and a Stop click could not reach them (field report
    2026-07-23: the app's graceful-stop window expired waiting on
    exactly this, and the engine was hard-killed).  The wait polls the
    red flag and raises TRANSIENT on Stop, so a cancelled airport is
    retried next run, never recorded as a durable answer.
    """
    slot = _provider_fetch_slot(code, slots)
    while not slot.acquire(timeout=0.5):
        if UI.red_flag:
            raise TransientFetchError(
                "stopped with the build while waiting for a %s fetch slot"
                % code)
    try:
        yield
    finally:
        slot.release()
