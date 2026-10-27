"""Politeness: how many requests may be in flight against one server.

One bounded semaphore per provider code, sized by the definition's
``fetch_slots`` key, and a wait that honours the Stop button.  The same
count bounds the provider across EVERY process of the build session
(#1236): a held fetch slot also holds one slot of the provider's
``O4_Machine_Slots`` class, so ten tiles fetching insets from one server
are one limit on it, not ten.
"""

import contextlib as _contextlib
import threading

import O4_Machine_Slots as MACHINE_SLOTS
import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError
from elevation_access.definitions import _parse_float

__all__ = [
    "PROVIDER_CONCURRENT_FETCHES",
    "_held_provider_fetch_slot",
    "cell_fetch_class",
    "held_inset_fetch_slot",
    "inset_fetch_key",
    "machine_class",
    "provider_fetch_slots",
]


# Per-provider politeness cap for the concurrent airport fetches: at most
# this many in-flight requests against any single elevation server.
_PROVIDER_CONCURRENT_FETCHES = 2

#: the same cap, public: a base elevation download (``O4_DEM_Utils.
#: http_request``) holds one of this many slots of its server's class
PROVIDER_CONCURRENT_FETCHES = _PROVIDER_CONCURRENT_FETCHES


def machine_class(code):
    """The session-wide slot class of one elevation provider (#1236)."""
    return "net:elevation:%s" % code


def cell_fetch_class(code):
    """The session-wide slot class of one provider's whole-CELL fetches --
    the approach-ring and coastline-band cells of EVERY tile of the
    session (#1327, RULINGS 2026-10-26t).  Its own class, not
    :func:`machine_class`: a cell fetch's strategy may take that class
    itself (``tnm_cog``'s stripped prefetch), and a holder waiting on its
    own class would wait out the bounded class wait."""
    return machine_class(code) + ":cells"


def inset_fetch_key(code):
    """The slot key of one provider's whole-INSET fetches (#1467): the
    per-airport loop holds it around ``fetch_inset``.  Its own key, never
    ``code`` itself: inside that fetch a strategy's worker threads take
    ``code``'s slots for their downloads (``tnm_cog``'s stripped
    prefetch, ``las_tile_index``'s tile downloads), and two airports
    holding both of ``code``'s slots would leave those workers queued
    forever behind their own callers.  One slot class per call path:
    the inset fetch, the ring cell (:func:`cell_fetch_class`) and the
    download each count against their own pool."""
    return "%s:insets" % code


def held_inset_fetch_slot(code):
    """Hold one of the provider's inset-fetch slots (:func:`inset_fetch_key`)
    -- session-wide, honouring Stop, exactly like
    :func:`_held_provider_fetch_slot`."""
    return _held_provider_fetch_slot(inset_fetch_key(code))


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
        # ... and one of the provider's slots for the whole session: the
        # other tiles' fetches count too (bounded wait, ends on Stop).
        with MACHINE_SLOTS.hold_class(
                machine_class(code), int(slots or _PROVIDER_CONCURRENT_FETCHES),
                give_up=lambda: UI.red_flag):
            if UI.red_flag:
                raise TransientFetchError(
                    "stopped with the build while waiting for a %s fetch "
                    "slot" % code)
            yield
    finally:
        slot.release()
