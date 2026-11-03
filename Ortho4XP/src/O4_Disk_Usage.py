"""What a file really costs on disk: the bytes deleting it gives back.

``du`` and ``st_blocks`` count an APFS clone at full size, and a hard link
once per name, so neither says what deleting a file frees (#338, measured
2026-10-04: a lane's 30 GB cache overlay held 0-130 MB of its own).  The
number that does is the file's PRIVATE size (``getattrlist``
``ATTR_CMNEXT_PRIVATESIZE``: the bytes no other file shares).

:func:`private_bytes` is that number where the filesystem can say it (macOS,
APFS).  :func:`freeable_bytes` is what the Storage settings and the harness
report: 0 for a name whose inode another name still holds (a DDS cache entry
hard-linked into a built tile's ``textures/``), else the private size, else
the allocated size, else the apparent size (Windows has no ``st_blocks``).

Standard library only; never raises.
"""
from __future__ import annotations

import ctypes
import os
import stat
import struct
import sys

__all__ = ["private_bytes", "freeable_bytes"]

_FSOPT_NOFOLLOW = 0x1
_FSOPT_ATTR_CMN_EXTENDED = 0x20
_ATTR_CMNEXT_PRIVATESIZE = 0x8


class _AttrList(ctypes.Structure):
    _fields_ = [("bitmapcount", ctypes.c_ushort), ("reserved", ctypes.c_ushort),
                ("commonattr", ctypes.c_uint32), ("volattr", ctypes.c_uint32),
                ("dirattr", ctypes.c_uint32), ("fileattr", ctypes.c_uint32),
                ("forkattr", ctypes.c_uint32)]


def _libsystem():
    """libSystem with ``getattrlist``, or None off macOS.  Cached."""
    if not hasattr(_libsystem, "lib"):
        lib = None
        if sys.platform == "darwin":
            try:
                lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            except OSError:
                lib = None
        _libsystem.lib = lib                        # type: ignore[attr-defined]
    return _libsystem.lib                           # type: ignore[attr-defined]


def private_bytes(path) -> int | None:
    """Bytes of ``path`` NO other file shares — what deleting it frees.

    0 for an untouched clone, the full allocation for a real copy.  None
    where the filesystem cannot say (not macOS, or not APFS): the caller
    reports "not measurable" rather than guessing.  Never raises.
    """
    lib = _libsystem()
    if lib is None:
        return None
    request = _AttrList(5, 0, 0, 0, 0, 0, _ATTR_CMNEXT_PRIVATESIZE)
    buf = ctypes.create_string_buffer(32)
    try:
        rc = lib.getattrlist(os.fsencode(str(path)), ctypes.byref(request),
                             buf, len(buf),
                             _FSOPT_ATTR_CMN_EXTENDED | _FSOPT_NOFOLLOW)
    except Exception:
        return None
    if rc != 0:
        return None
    length, size = struct.unpack_from("=Iq", buf.raw)
    return size if length >= 12 else None


def freeable_bytes(path, st: os.stat_result | None = None) -> int:
    """What deleting the one name ``path`` frees, in bytes (see the module
    docstring); 0 for a symlink or a path that cannot be read."""
    try:
        st = st if st is not None else os.lstat(path)
    except OSError:
        return 0
    if stat.S_ISLNK(st.st_mode) or getattr(st, "st_nlink", 1) > 1:
        return 0
    size = private_bytes(path)
    if size is not None:
        return size
    blocks = getattr(st, "st_blocks", None)         # none on Windows
    return blocks * 512 if blocks is not None else st.st_size
