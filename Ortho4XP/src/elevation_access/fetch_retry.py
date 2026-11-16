"""Retrying a transient inset fetch: backoff, one provider-wide pause, Stop.

A rate limit (HTTP 429), a server error (5xx) or a stalled transfer says
"come back later", never "no data here" -- and never "use a coarser
source this time" either (#2098: a 429 storm on +51-001 handed EGTF and
EGLB to FABDEM 30 m after GDAL's own two 5 s retries).  So before the
per-airport loop gives a provider up for the run, the whole fetch is
asked again after each of :data:`RETRY_DELAYS_S` (with +-25 % jitter).

The wait PAUSES THE PROVIDER (``O4_Http_Pushback.pause_host``, keyed on
the provider code): every other airport's next asking of that provider
waits it out too, so a throttling server sees the whole tile back off,
not one worker.  The sleep honours Stop; a raise that is not transient
(a crash, a missing capability) is never retried.
"""

import random

import O4_Http_Pushback as PUSHBACK
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.failures import (
    error_message_indicates_transient_network_failure,
)

__all__ = [
    "RETRY_DELAYS_S",
    "retry_transient",
]

#: Seconds to wait before each further asking of a provider whose fetch
#: raised a transient failure; then the run gives it up.  Minutes, not
#: seconds: the Environment Agency WCS answers a burst by STALLING every
#: connection from the address for minutes (measured 2026-11-15: a
#: GetCapabilities hung past 120 s right after a 429), so a 30 s retry
#: only stalls again.
RETRY_DELAYS_S = (60.0, 180.0, 300.0)


def _is_transient_fetch_error(error) -> bool:
    """Is ``error`` a failure worth asking again (never a capability)?"""
    if isinstance(error, ProviderUnavailable):
        return False
    return isinstance(error, TransientFetchError) or (
        error_message_indicates_transient_network_failure(error))


def _provider_pause_key(code) -> str:
    """The ``O4_Http_Pushback`` host key of one elevation provider."""
    return "https://elevation-provider-%s/" % str(code).lower()


def retry_transient(attempt, code, label, delays=None):
    """``attempt()``, asked again after each of ``delays`` on a transient raise.

    Returns what ``attempt`` returns; re-raises the last error when the
    delays are spent, when the error is not transient, or on Stop.
    ``label`` names the airport in the retry line.
    """
    delays = RETRY_DELAYS_S if delays is None else tuple(delays)
    key = _provider_pause_key(code)
    for number in range(len(delays) + 1):
        if not PUSHBACK.wait_for_host(key):
            raise TransientFetchError(
                "stopped with the build while %s rested" % code)
        try:
            return attempt()
        except Exception as error:
            if (number >= len(delays) or UI.red_flag
                    or not _is_transient_fetch_error(error)):
                raise
            wait = float(delays[number]) * random.uniform(0.75, 1.25)
            PUSHBACK.pause_host(key, wait)
            UI.vprint(
                1,
                "    [insets] %s: %s failed on transport (%s) - asking "
                "again in %.0f s (retry %d of %d); %s is paused for every "
                "airport meanwhile."
                % (label, code, str(error).splitlines()[0][:200], wait,
                   number + 1, len(delays), code))
    raise AssertionError("unreachable")  # pragma: no cover
