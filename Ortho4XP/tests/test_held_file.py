"""The Windows held-file retry policy, and the band lock release on it.

``src/O4_Held_File.py`` holds the policy PR #218 introduced for the OSM
clip's atomic replace (#205) and nothing else: which Win32 refusals are
transient, how many attempts, how long the backoff, and whether to retry
at all.  These twins pin the policy itself, and then the second caller it
was promoted for -- ``O4_Bathymetry_Band._release_band_lock`` (#230,
#249), whose bare ``os.remove`` of ``fetch.lock`` went red at random on
the windows-latest leg because the waiter it is racing holds that very
file open for its staleness read.

The clip side's own twins live in ``tests/test_osm_extract_filter.py``
and read the same constants from here, so the policy cannot drift from
either caller.

Hermetic: ``tmp_path`` only, the refusal injected rather than provoked
(a POSIX runner cannot produce ERROR_SHARING_VIOLATION), and the backoff
recorded rather than slept.
"""

from __future__ import annotations

import errno
import os
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
)

import O4_Bathymetry_Band as BATHYBAND  # noqa: E402
import O4_Held_File as HELD  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402


def _held_file_error(path, winerror=32):
    """The OSError Windows raises while another process holds ``path``."""
    error = PermissionError(
        errno.EACCES,
        "The process cannot access the file because it is being used by"
        " another process",
        path,
    )
    error.winerror = winerror
    return error


@pytest.fixture()
def windows(monkeypatch):
    """The policy under a simulated Windows, with the backoff recorded."""
    sleeps = []
    monkeypatch.setattr(HELD.time, "sleep", sleeps.append)
    monkeypatch.setattr(HELD, "RETRY_HELD_FILE", True)
    return sleeps


# =====================================================================
# The policy
# =====================================================================
@pytest.mark.parametrize("winerror", list(HELD.WINDOWS_HELD_FILE_ERRORS))
def test_a_held_file_is_retried_until_the_holder_lets_go(windows, winerror):
    refusals = [_held_file_error("f", winerror=winerror) for _ in range(2)]
    attempts = []

    def _operation():
        attempts.append(1)
        if refusals:
            raise refusals.pop(0)
        return "done"

    assert HELD.retrying_a_held_file(_operation) == "done"
    assert len(attempts) == 3
    # the bounded, doubling backoff, nothing more
    assert windows == [HELD.HELD_FILE_FIRST_BACKOFF_S,
                       HELD.HELD_FILE_FIRST_BACKOFF_S * 2]


def test_a_file_held_forever_raises_after_the_bounded_attempts(windows):
    attempts = []

    def _operation():
        attempts.append(1)
        raise _held_file_error("f")

    with pytest.raises(PermissionError):
        HELD.retrying_a_held_file(_operation)
    assert len(attempts) == HELD.HELD_FILE_ATTEMPTS
    assert len(windows) == HELD.HELD_FILE_ATTEMPTS - 1
    assert max(windows) <= HELD.HELD_FILE_MAX_BACKOFF_S
    # A holder's lifetime, not a wait a build can feel.
    assert sum(windows) < 2.0


@pytest.mark.parametrize("error_number", [errno.ENOENT, errno.EACCES])
def test_a_failure_that_is_not_a_held_file_raises_at_once(
        windows, error_number):
    """A retry loop must never wait out an error that will not clear --
    a missing file, or a shared-repo write guard's refusal."""
    attempts = []

    def _operation():
        attempts.append(1)
        raise OSError(error_number, "no")

    with pytest.raises(OSError):
        HELD.retrying_a_held_file(_operation)
    assert len(attempts) == 1
    assert windows == []


def test_the_retry_is_windows_only(windows, monkeypatch):
    """Off Windows the same refusal is a real failure, not a wait."""
    monkeypatch.setattr(HELD, "RETRY_HELD_FILE", False)
    attempts = []

    def _operation():
        attempts.append(1)
        raise _held_file_error("f")

    with pytest.raises(PermissionError):
        HELD.retrying_a_held_file(_operation)
    assert len(attempts) == 1
    assert windows == []


def test_the_flag_follows_the_platform():
    assert HELD.RETRY_HELD_FILE == (sys.platform == "win32")


def test_the_remove_helper_goes_through_the_same_policy(windows, tmp_path):
    victim = tmp_path / "fetch.lock"
    victim.write_text("owner", encoding="utf-8", newline="")
    refusals = [_held_file_error(str(victim))]
    real_remove = os.remove

    def _remove(path, **kwargs):
        if refusals:
            raise refusals.pop(0)
        return real_remove(path, **kwargs)

    windows_os = HELD.os
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(windows_os, "remove", _remove)
        HELD.remove_retrying_a_held_file(str(victim))
    assert not victim.exists()
    assert windows == [HELD.HELD_FILE_FIRST_BACKOFF_S]


# =====================================================================
# The caller the policy was promoted for (#230, #249)
# =====================================================================
def _band_lock(tmp_path):
    """A band directory holding a live-looking lock, as a fetch leaves it."""
    band_directory = str(tmp_path / "N00E000_bathymetry_band")
    os.makedirs(band_directory, exist_ok=True)
    lock_path = BATHYBAND._band_lock_path(band_directory)
    with open(lock_path, "w", encoding="utf-8", newline="") as lock_file:
        lock_file.write('{"pid": 1, "host": "somewhere"}')
    return band_directory, lock_path


def test_the_band_release_retries_a_lock_the_waiter_holds_open(
        windows, tmp_path, monkeypatch):
    """#230's mechanism: the waiter in ``_acquire_band_lock``'s poll loop
    has ``fetch.lock`` OPEN for its staleness read, and Win32 refuses the
    unlink for as long as that handle lives.  The release must outlast
    the read, not give the lock up."""
    band_directory, lock_path = _band_lock(tmp_path)
    refusals = [_held_file_error(lock_path) for _ in range(2)]
    real_remove = os.remove

    def _remove(path, **kwargs):
        if refusals:
            raise refusals.pop(0)
        return real_remove(path, **kwargs)

    monkeypatch.setattr(BATHYBAND.os, "remove", _remove)
    BATHYBAND._release_band_lock(band_directory)
    assert not os.path.isfile(lock_path), (
        "the lock must be GONE: a release that swallowed the refusal left"
        " a live-owner lock no waiter judges stale")
    assert len(windows) == 2


def test_a_lock_held_past_the_bound_is_reported_and_not_raised(
        windows, tmp_path, monkeypatch):
    """The release runs in a ``finally``: it must not replace the build's
    own failure with a cleanup's.  But a lock that never goes away is a
    half hour of another build's waiting, so it is not silent either."""
    band_directory, lock_path = _band_lock(tmp_path)

    def _remove(path, **kwargs):
        raise _held_file_error(lock_path)

    monkeypatch.setattr(BATHYBAND.os, "remove", _remove)
    said = []
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *args: said.append(" ".join(
                            str(a) for a in args)))
    BATHYBAND._release_band_lock(band_directory)    # no exception
    assert os.path.isfile(lock_path)
    assert len(said) == 1 and "fetch lock" in said[0]
    assert lock_path in said[0]


def test_an_already_released_lock_is_silent(tmp_path, monkeypatch):
    """A waiter that stole it as stale, or a double release: nothing to
    report, and nothing to retry (a missing file is not a held one)."""
    band_directory = str(tmp_path / "N00E000_bathymetry_band")
    os.makedirs(band_directory, exist_ok=True)
    said = []
    monkeypatch.setattr(UI, "vprint",
                        lambda level, *args: said.append(args))
    BATHYBAND._release_band_lock(band_directory)
    assert said == []
