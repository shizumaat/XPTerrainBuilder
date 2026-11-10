"""The macOS file-cache calls of the X-Plane read recorder (#1992): which
pages of a file are resident (mincore), dropping them (msync
MS_INVALIDATE), the file's disk extents (fcntl F_LOG2PHYS_EXT), and a
snapshot of size + DDS header.  Read-only on the files; no root needed.

Importable on any platform (the parser twins run on Windows and Linux CI):
libc and fcntl are reached only when a probe is made.
"""
from __future__ import annotations

import mmap
import os
import struct

from reads_textures import dds_header

try:
    import fcntl
except ImportError:                 # Windows: no extents, no probes
    fcntl = None

PAGE = mmap.PAGESIZE
F_LOG2PHYS_EXT = 65
F_NOCACHE = 48
PROT_READ, MAP_SHARED, MS_INVALIDATE = 1, 1, 2
_LIBC = None


def _libc():
    """libc with the four calls typed (macOS / Linux); built on first use."""
    global _LIBC
    if _LIBC is None:
        import ctypes
        lib = ctypes.CDLL(None, use_errno=True)
        lib.mmap.restype = ctypes.c_void_p
        lib.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, ctypes.c_longlong]
        lib.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        lib.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                ctypes.c_char_p]
        lib.msync.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        _LIBC = lib
    return _LIBC


def ranges_of(idx: list[int]) -> list[list[int]]:
    """[3,4,5,9] -> [[3,6],[9,10]] (page ranges, end exclusive)."""
    out: list[list[int]] = []
    for i in idx:
        if out and out[-1][1] == i:
            out[-1][1] = i + 1
        else:
            out.append([i, i + 1])
    return out


def cache_probe(path: str, evict: bool) -> tuple[list[list[int]], int] | None:
    """(resident page ranges, page count) of a file; then optionally drop
    its cached pages (msync MS_INVALIDATE) so the next load reads from disk
    and shows up again.  Read-only: the file is never written.  None if the
    file cannot be mapped."""
    import ctypes
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            return [], 0
        lib = _libc()
        addr = lib.mmap(None, size, PROT_READ, MAP_SHARED, fd, 0)
        if addr in (None, ctypes.c_void_p(-1).value):
            return None
        try:
            npg = (size + PAGE - 1) // PAGE
            vec = ctypes.create_string_buffer(npg)
            if lib.mincore(addr, size, vec) != 0:
                return None
            res = ranges_of([i for i, b in enumerate(vec.raw) if b & 1])
            if evict:
                lib.msync(addr, size, MS_INVALIDATE)
            return res, npg
        finally:
            lib.munmap(addr, size)
    finally:
        os.close(fd)


def extents(path: str, size: int, cap: int = 64) -> list[list[int]] | None:
    """[[file_offset, device_byte_offset, length], ...] of a file on disk
    (fcntl F_LOG2PHYS_EXT, macOS).  Lets the analysis turn a page-in's disk
    block D= back into a file offset."""
    if fcntl is None:
        return None
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    out: list[list[int]] = []
    try:
        off = 0
        while off < size and len(out) < cap:
            buf = struct.pack("=Iqq", 0, size - off, off)
            _fl, contig, dev = struct.unpack(
                "=Iqq", fcntl.fcntl(fd, F_LOG2PHYS_EXT, buf))
            if contig <= 0:
                break
            out.append([off, dev, contig])
            off += contig
    except OSError:
        return out or None
    finally:
        os.close(fd)
    return out


def snapshot(path: str) -> dict | None:
    """Size + DDS header (+ disk extents) of a file on disk right now."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            blob = f.read(148)
    except OSError:
        return None
    info = dds_header(blob, size) if path.lower().endswith(".dds") else None
    info = info or {"size": size}
    if path.lower().endswith(".dds"):
        info["extents"] = extents(path, size)
        try:
            st = os.stat(path)
            info["dev"], info["ino"] = st.st_dev, st.st_ino
        except OSError:
            pass
    return info
