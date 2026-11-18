"""The app's storage cleanup, read back for the shared-repo audit (#2093).

The app's engine logs every file its storage manager deletes or moves to
a storage tier in ``<data root>/logs/storage.log``
(``o4_engine.storage.LOG_NAME``), one dated line each::

    2026-11-17T05:29:03Z deleted 0 bytes /…/OSM_data/x.osm.pbf
        (osm_extracts, automatic cleanup)
    2026-11-17T05:29:03Z moved 4096 bytes /…/Elevation_data/f.json
        to /Volumes/… (elevation, automatic cleanup)

(each on one line)

When the app's data root IS the shared corpus, those files vanish from
under a harness build.  :func:`cleanup_paths` names the ones logged inside
a build's window, so ``shared_repo_guard.report_unauthorised_writes``
labels them "external: app automatic cleanup" instead of a SIDE EFFECT
of the build (measured 2026-11-17T05:29:03Z: 39 regional extracts and 5
elevation footprints).  Standard library only; never raises.
"""
from __future__ import annotations

import calendar
import os
import re
import time
from pathlib import Path

__all__ = ["LOG", "cleanup_paths"]

#: The log, relative to the data repo.
LOG = Path("logs") / "storage.log"
_LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (?:deleted|moved) "
                   r"\d+ bytes (.+?)(?: to .+)? \(\w+, (.*)\)$")
#: Log stamps are whole seconds; the window is widened by this much.
_SLACK = 2.0
_CHUNK = 1 << 20


def _stamp(text: str) -> float:
    return float(calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")))


def _tail_lines(path: Path, since: float) -> list:
    """The log's whole lines from the last one stamped before ``since``
    on (read backwards in chunks: the log grows without bound)."""
    try:
        with open(path, "rb") as log:
            end = pos = log.seek(0, os.SEEK_END)
            lines: list = []
            while pos > 0:
                pos = max(0, pos - _CHUNK)
                log.seek(pos)
                lines = log.read(end - pos).split(b"\n")[1 if pos else 0:]
                if lines and _before(lines[0], since):
                    break
    except OSError:
        return []
    return [line.decode("utf-8", "replace") for line in lines]


def _before(line: bytes, since: float) -> bool:
    try:
        return _stamp(line[:20].decode("ascii")) < since
    except (ValueError, UnicodeDecodeError):
        return False


def cleanup_paths(repo, since: float, until: float) -> dict:
    """``{relative posix path: reason}`` of the files under ``repo`` the
    app's storage manager deleted or moved between ``since`` and
    ``until`` (epoch seconds), from ``repo/logs/storage.log``."""
    repo = Path(repo)
    roots = {str(repo), os.path.realpath(repo)}
    out: dict = {}
    for line in _tail_lines(repo / LOG, since - _SLACK):
        match = _LINE.match(line)
        if not match:
            continue
        try:
            when = _stamp(match.group(1))
        except ValueError:
            continue
        if not since - _SLACK <= when <= until + _SLACK:
            continue
        path = match.group(2)
        for root in roots:
            if path.startswith(root + os.sep):
                rel = Path(os.path.relpath(path, root)).as_posix()
                out[rel] = match.group(3)
                break
    return out
