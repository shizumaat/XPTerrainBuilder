"""X-Plane's ``Log.txt`` as a witness of which DSFs it has loaded (flight
manager / World spec 2026-11-10, §2.3).

X-Plane writes one line per DSF it loads::

    0:00:25.870 I/SCN: DSF load time: 432299 for file Custom Scenery/
        zOrtho4XP_+65-148/Earth nav data/+60-150/+65-148.dsf (394894 tris, ...)

(one line in the file).  Tailing it tells the engine, with no plugin and no
sudo, which of our tiles X-Plane has loaded in this session and whether it
read a mesh tile (``tris`` > 0) or an overlay: a World-pack placeholder
loads as ``0 tris`` [measured on the CYYR World pack flight], as every
overlay pack does (simHeaven, drape tiles).  It records no unloads; the
window tracker (``O4_World_Window``) covers those.  X-Plane rewrites the
file at each start: :class:`LogTail` notices and starts over.

The block "I found the following scenery packages" lists the packs this
session read (``LogTail.packages``): a pack added after X-Plane started
is not in it, and needs a restart.

Pure: standard library only; :class:`LogTail` reads the file it is given
and nothing else.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, NamedTuple

__all__ = [
    "LOG_NAME", "DsfLoad", "parse_dsf_load", "parse_started", "pack_loads",
    "log_path", "LogTail",
]

LOG_NAME = "Log.txt"

_DSF_LOAD = re.compile(
    r"^\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)\s+\S+\s+DSF load time:\s*(\d+)\s+"
    r"for file (?P<path>(?P<pack>.+?)/Earth nav data/[+-]\d\d[+-]\d\d\d/"
    r"(?P<lat>[+-]\d\d)(?P<lon>[+-]\d\d\d)\.dsf)\s+\((?P<tris>\d+) tris")
_STARTED = re.compile(r"X-Plane Started on (.+?)\s*$")
_PACKAGES_HEAD = "I found the following scenery packages"
_PACKAGE_ROW = re.compile(r"^\s*\d+\s+(.+?)/?\s*$")


class DsfLoad(NamedTuple):
    """One DSF load: ``t_s`` = the line's stamp in seconds (X-Plane's
    clock since it started), ``load_us`` = load time in µs, ``pack`` = the
    pack folder's name (``zXPTerrainBuilder World``), ``path`` = the file
    as logged, ``lat``/``lon`` = the tile, ``tris`` = mesh triangles."""
    t_s: float
    load_us: int
    pack: str
    path: str
    lat: int
    lon: int
    tris: int

    @property
    def tile(self) -> tuple[int, int]:
        return self.lat, self.lon

    @property
    def overlay(self) -> bool:
        """No mesh: a placeholder, a drape or any overlay pack (0 tris)."""
        return self.tris == 0


def parse_dsf_load(line: str) -> DsfLoad | None:
    """The :class:`DsfLoad` of one ``Log.txt`` line, or ``None``."""
    m = _DSF_LOAD.match(line)
    if not m:
        return None
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return DsfLoad(round(h * 3600 + mi * 60 + s, 3), int(m.group(4)),
                   m.group("pack").rstrip("/").rsplit("/", 1)[-1],
                   m.group("path"), int(m.group("lat")), int(m.group("lon")),
                   int(m.group("tris")))


def parse_started(line: str) -> str | None:
    """``Tue Nov 10 08:41:06 2026`` (local time, as written) from the
    header line ``X-Plane Started on …``, or ``None``."""
    m = _STARTED.search(line)
    return m.group(1) if m else None


def pack_loads(records: Iterable[DsfLoad], pack: str) -> dict:
    """``{(lat, lon): DsfLoad}``: the latest load of each of ``pack``'s
    tiles (the pack folder's name)."""
    return {r.tile: r for r in records if r.pack == pack}


def log_path(xplane_dir: str) -> str:
    """Where X-Plane writes its log: ``<X-Plane>/Log.txt``."""
    return os.path.join(xplane_dir, LOG_NAME)


class LogTail:
    """Reads what X-Plane appended to ``Log.txt`` since the last call.

    :meth:`read` returns the new :class:`DsfLoad` records; ``packages`` and
    ``started`` hold the session's pack list and start stamp once seen.
    When X-Plane has started again (the file is shorter, or its first bytes
    differ) the tail starts over from the top and ``restarts`` counts it."""

    _HEAD = 256

    def __init__(self, path: str) -> None:
        self.path = path
        self.offset = 0
        self.head = b""
        self.restarts = 0
        self.started: str | None = None
        self.packages: list[str] = []
        self._part = b""
        self._in_packages = False

    def read(self) -> list[DsfLoad]:
        """New DSF loads since the last call ([] when the file is absent)."""
        try:
            with open(self.path, "rb") as f:
                head = f.read(self._HEAD)
                size = os.fstat(f.fileno()).st_size
                if self.offset and (size < self.offset
                                    or head[:len(self.head)] != self.head):
                    self._restart()
                f.seek(self.offset)
                data = f.read()
        except OSError:
            return []
        if len(self.head) < self._HEAD:
            self.head = head
        self.offset += len(data)
        data = self._part + data
        cut = data.rfind(b"\n") + 1
        self._part = data[cut:]
        out = []
        for raw in data[:cut].splitlines():
            line = raw.decode("utf-8", errors="replace")
            rec = parse_dsf_load(line)
            if rec is not None:
                out.append(rec)
            else:
                self._note(line)
        return out

    def _restart(self) -> None:
        self.offset, self.head, self._part = 0, b"", b""
        self.started, self.packages, self._in_packages = None, [], False
        self.restarts += 1

    def _note(self, line: str) -> None:
        if self.started is None:
            self.started = parse_started(line)
        if _PACKAGES_HEAD in line:
            self.packages, self._in_packages = [], True
        elif self._in_packages:
            m = _PACKAGE_ROW.match(line)
            if m:
                self.packages.append(m.group(1))
            else:
                self._in_packages = False
