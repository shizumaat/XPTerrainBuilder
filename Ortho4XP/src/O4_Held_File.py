"""Bounded retries for a file another process HOLDS open (Windows only).

POSIX lets a process rename over, or unlink, a file that another process
has open; Win32 does not.  It refuses with ``ERROR_ACCESS_DENIED`` (5) or
``ERROR_SHARING_VIOLATION`` (32) for as long as any handle is open, and
neither refusal says the operation was wrong.  Two engine sites meet it:

* the OSM clip's atomic ``os.replace`` onto a destination that a racing
  cutter -- or Windows' own indexer, over a freshly created file --
  momentarily holds (#205, measured as the single windows-latest failure
  of PR #202, and the origin of this policy);
* the bathymetry band's ``os.remove`` of ``fetch.lock``, which a waiter
  inside ``_acquire_band_lock``'s poll loop opens for its staleness read
  (#230 / #249, measured as an intermittent windows-latest red);
* the same lock's exclusive CREATE right after its owner released it: a
  file deleted while some other handle (Defender, the indexer) still has
  it open stays "delete pending" under its name until that handle
  closes, and ``CreateFile(CREATE_NEW)`` on that name is refused with
  ``ERROR_ACCESS_DENIED``.  ``os.open`` goes through the C runtime, which
  reports it as a bare ``EACCES`` with no ``winerror`` (#884, measured on
  windows-latest as the waiter's thread dying with ``PermissionError``).

No holder in either case lasts: the condition is transient by nature, so
the remedy is a bounded retry with a doubling backoff around the ONE
call, and each attempt is still the same single atomic operation, so
whatever guarantee that operation bought is unchanged.  Every other
failure -- ``EXDEV``, a missing source, a shared-repo write guard's
refusal -- raises on the FIRST attempt: a retry loop must never wait out
a refusal that will not clear.

The POLICY (which error codes, how many attempts, how long to back off,
and whether to retry at all) lives here once.  The OPERATION stays at
its call site, passed in as a callable, so each site's own twins keep
patching their own module's ``os`` and the shared-repo write guard --
which wraps the attributes of :mod:`os` itself -- still sees the call.

Standard library only, and no UI import, so any core module may import
this freely.
"""

from __future__ import annotations

import errno
import os
import sys
import time
from typing import Callable, TypeVar

T = TypeVar("T")

#: Windows error codes for "someone else holds this file".  Both are
#: transient; neither says the operation is wrong.
WINDOWS_HELD_FILE_ERRORS = (5, 32)

#: Attempts at the operation, the first one included.
HELD_FILE_ATTEMPTS = 6

#: Backoff before the second attempt, doubling up to the cap below: the
#: whole bound is 0.05 + 0.1 + 0.2 + 0.4 + 0.8 = 1.55 s -- a holder's
#: lifetime, and nothing like the minutes of work (an osmium clip) or the
#: half hour of waiting (a band lock's stale window) that giving up costs.
HELD_FILE_FIRST_BACKOFF_S = 0.05
HELD_FILE_MAX_BACKOFF_S = 0.8

#: Only Windows can refuse for a held file, so only there is a retry
#: anything but a swallowed error.  A module-level flag, not an inline
#: ``sys.platform`` test, so the twins can exercise the Windows path on
#: the runner they have.
RETRY_HELD_FILE = sys.platform == "win32"


def is_held_file_error(error: OSError) -> bool:
    """Is ``error`` Windows refusing because another process holds it?"""
    return getattr(error, "winerror", None) in WINDOWS_HELD_FILE_ERRORS


def is_held_name_on_create(error: OSError) -> bool:
    """Is ``error`` Windows refusing an EXCLUSIVE CREATE because the name
    is still held -- a file deleted while another handle is open stays
    "delete pending" until that handle closes?

    For an ``os.open(..., O_CREAT | O_EXCL)`` only: the C runtime turns
    ``ERROR_ACCESS_DENIED`` into a bare ``EACCES`` with no ``winerror``,
    which in general could be any permission failure -- so this is never
    the default predicate.  At an exclusive create of a file the caller
    owns the directory of, it is the held name; a genuine permission
    failure still raises after the bounded attempts.
    """
    return is_held_file_error(error) or (
        getattr(error, "winerror", None) is None
        and error.errno == errno.EACCES
    )


def retrying_a_held_file(
    operation: Callable[[], T],
    is_held: Callable[[OSError], bool] = is_held_file_error,
) -> T:
    """Call ``operation()``, retrying ONLY a held-file refusal.

    The bounded, doubling backoff of the constants above is spent only on
    ``is_held`` (:func:`is_held_file_error` unless the call site passes a
    narrower-context predicate such as :func:`is_held_name_on_create`),
    and only on Windows; the last attempt raises like any other, so a
    holder that never lets go is reported rather than waited out forever.
    Anything else raises on the first attempt, untouched.
    """
    backoff = HELD_FILE_FIRST_BACKOFF_S
    for attempt in range(1, HELD_FILE_ATTEMPTS + 1):
        try:
            return operation()
        except OSError as error:
            if (not RETRY_HELD_FILE or not is_held(error)
                    or attempt == HELD_FILE_ATTEMPTS):
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2, HELD_FILE_MAX_BACKOFF_S)
    raise AssertionError(            # pragma: no cover - unreachable
        "retrying_a_held_file fell out of its bounded loop")


def remove_retrying_a_held_file(path: str) -> None:
    """``os.remove(path)``, retrying a HELD file (see the module docstring).

    The caller's own ``os`` is not used here, so a twin that patches
    ``os.remove`` on ITS module will not see this call; a site whose twins
    do that passes its own operation to :func:`retrying_a_held_file`
    instead.  Nothing in the engine needs that today for a remove, and
    the shared-repo write guard wraps :mod:`os` itself, so its refusals
    arrive here unchanged -- on the first attempt, like any non-held
    error.
    """
    retrying_a_held_file(lambda: os.remove(path))
