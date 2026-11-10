"""Swap two directory entries in ONE atomic step (#1992 P1c: a Custom
Scenery entry is replaced by its converted copy with no moment at which
the name is missing or half-written).

:func:`exchange` swaps what the names ``a`` and ``b`` point at: after it,
``a`` is what ``b`` was and ``b`` what ``a`` was -- a symlink and a
directory included.  macOS: ``renamex_np(RENAME_SWAP)`` (APFS, HFS+);
Linux: ``renameat2(RENAME_EXCHANGE)`` (ext4, btrfs, xfs, tmpfs).  Both
names must be on one volume.  Anywhere else, or on a filesystem without
the call, :class:`ExchangeUnsupported` is raised and NOTHING moved: a
caller never falls back to two renames, which would leave a moment with
no entry.

:func:`supported` probes the call on two scratch entries in a folder.

Standard library only (``ctypes``).
"""
from __future__ import annotations

import contextlib
import ctypes
import errno
import os
import sys
import uuid

__all__ = ["ExchangeUnsupported", "exchange", "supported"]

_RENAME_SWAP = 0x2              # <stdio.h> on macOS
_RENAME_EXCHANGE = 0x2          # <linux/fs.h>
_AT_FDCWD = -100
_UNSUPPORTED = {errno.ENOTSUP, errno.EINVAL, errno.ENOSYS,
                getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}


class ExchangeUnsupported(OSError):
    """This platform or filesystem has no atomic exchange."""


def _libc():
    return ctypes.CDLL(None, use_errno=True)


def _call(a: bytes, b: bytes) -> int:
    libc = _libc()
    if sys.platform == "darwin":
        return libc.renamex_np(a, b, ctypes.c_uint(_RENAME_SWAP))
    if sys.platform.startswith("linux"):
        try:
            renameat2 = libc.renameat2
        except AttributeError:
            raise ExchangeUnsupported(errno.ENOSYS,
                                      "libc has no renameat2") from None
        return renameat2(_AT_FDCWD, a, _AT_FDCWD, b,
                         ctypes.c_uint(_RENAME_EXCHANGE))
    raise ExchangeUnsupported(errno.ENOSYS,
                              f"no atomic exchange on {sys.platform}")


def exchange(a: str, b: str) -> None:
    """Swap the entries ``a`` and ``b`` atomically (both must exist, on
    one volume).  ``ExchangeUnsupported`` when the platform or filesystem
    cannot; another ``OSError`` for any other refusal.  Never moves one
    without the other."""
    if not (os.path.lexists(a) and os.path.lexists(b)):
        raise FileNotFoundError(errno.ENOENT, "both entries must exist",
                                a if not os.path.lexists(a) else b)
    if _call(os.fsencode(a), os.fsencode(b)) != 0:
        code = ctypes.get_errno()
        kind = ExchangeUnsupported if code in _UNSUPPORTED else OSError
        raise kind(code, os.strerror(code), a)


def supported(folder: str) -> bool:
    """Can :func:`exchange` swap two entries in ``folder``?  Probed with a
    scratch file and a scratch symlink that are removed again."""
    token = uuid.uuid4().hex[:8]
    one = os.path.join(folder, f".exchange-probe-{token}-a")
    two = os.path.join(folder, f".exchange-probe-{token}-b")
    try:
        with open(one, "w", encoding="ascii", newline=""):
            pass
        os.symlink(one, two)
        exchange(one, two)
        return os.path.islink(one) and not os.path.islink(two)
    except OSError:
        return False
    finally:
        for path in (one, two):
            with contextlib.suppress(OSError):
                os.remove(path)
