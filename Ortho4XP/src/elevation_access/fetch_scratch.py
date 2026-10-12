"""Where an airport inset is FETCHED before the finished raster lands.

Issue #583.  Every access strategy cuts its working files beside the path
it is asked to write (``<destination>.rung2``, ``.tnm0.zip``,
``.prefetch3.tif``, ``.las4.part``, ...), most of them through GDAL.  When
that path was the inset cache itself, a fetch wrote dozens of files into
the cache directory before it had an answer: a killed build left them
there for good, and under the harness's shared-repo write guard -- which
sees Python writes only -- 74 of them (166 MB) reached the shared corpus
and the guard then refused their removal.

So the fetch loop asks for a path HERE, the strategy works beside THAT,
and only the finished raster is moved onto the cache -- one Python-level
rename, which a write guard can refuse at the call:

* :func:`scratch_destination` -- a private folder per fetch, under the
  engine's temporary directory (``O4_INSET_SCRATCH_DIR`` overrides it);
* :func:`land` -- move the finished raster onto the cache;
* :func:`discard` -- drop the folder, whatever is left in it;
* :func:`sweep_stale` -- remove what a killed run left: old scratch
  folders, and the scratch files earlier engines left BESIDE the cached
  insets of one tile.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid

import O4_File_Names as FNAMES

__all__ = [
    "SCRATCH_ENV",
    "STALE_SCRATCH_S",
    "discard",
    "land",
    "scratch_destination",
    "scratch_root",
    "stale_inset_siblings",
    "sweep_stale",
]

#: Overrides the scratch root (a lane or a test names its own folder).
SCRATCH_ENV = "O4_INSET_SCRATCH_DIR"

#: Age past which scratch belongs to no running fetch.  The longest fetch
#: the caps allow (3 GB of lidar tiles at the 0.3 MB/s a county server
#: gives) is under three hours; a day leaves room for a paused machine.
STALE_SCRATCH_S = 24 * 3600.0

#: The names that sit beside ``<ICAO>_<provider>.tif`` in an inset cache
#: and are NOT fetch scratch: GDAL's statistics sidecar and the engine's
#: lock files.
_KEPT_SIBLING_SUFFIXES = (".aux.xml", ".lock")


def scratch_root() -> str:
    """The folder every fetch's private scratch folder is made in."""
    override = os.environ.get(SCRATCH_ENV)
    if override:
        return override
    return os.path.join(FNAMES.Tmp_dir or tempfile.gettempdir(),
                        "inset_fetch")


def scratch_destination(destination: str) -> str:
    """A path to fetch ``destination`` at: the same file name (strategies
    read the airport out of it) in a new private folder."""
    folder = os.path.join(scratch_root(), "%s.%d.%s" % (
        os.path.basename(os.path.dirname(destination)) or "inset",
        os.getpid(), uuid.uuid4().hex[:8]))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, os.path.basename(destination))


def land(scratch_path: str, destination: str) -> None:
    """Move the finished raster onto ``destination``.

    A rename when both are on one volume.  Across volumes the bytes are
    copied to ``<destination>.landing`` first and renamed from there, so
    a reader never opens a half-copied raster."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    try:
        os.replace(scratch_path, destination)
        return
    except OSError:
        if not os.path.isfile(scratch_path):
            raise
    landing = destination + ".landing"
    try:
        shutil.copyfile(scratch_path, landing)
        os.replace(landing, destination)
    finally:
        if os.path.isfile(landing):
            os.remove(landing)


def discard(scratch_path: str) -> None:
    """Remove the private folder :func:`scratch_destination` made."""
    shutil.rmtree(os.path.dirname(scratch_path), ignore_errors=True)


def _newest_mtime(path: str) -> float:
    """The newest modification time in ``path`` (a file or a folder)."""
    if not os.path.isdir(path):
        return os.path.getmtime(path)
    stamps = []
    for (folder, _dirs, files) in os.walk(path):
        for name in files:
            try:
                stamps.append(os.path.getmtime(os.path.join(folder, name)))
            except OSError:
                pass
    # A folder's own time moves when an entry is added or removed; its
    # files say when anything was last WRITTEN.  Empty: the folder's.
    return max(stamps) if stamps else os.path.getmtime(path)


def stale_inset_siblings(inset_directory: str, now: float | None = None,
                         older_than_s: float = STALE_SCRATCH_S) -> list:
    """The stale fetch scratch BESIDE the cached insets of one tile.

    Engines before #583 fetched beside the cache; a build killed
    mid-fetch left ``<ICAO>_<provider>.tif.refetch``, ``.rung2``,
    ``.tnm0.zip`` ... there, and nothing ever removed them.  Scratch is
    any entry named ``<raster>.tif.<more>`` (but GDAL's ``.aux.xml`` and
    a ``.lock``) not modified for ``older_than_s``."""
    now = time.time() if now is None else now
    try:
        names = sorted(os.listdir(inset_directory))
    except OSError:
        return []
    stale = []
    for name in names:
        (stem, marker, rest) = name.partition(".tif.")
        if not marker or not stem or not rest:
            continue
        if name.endswith(_KEPT_SIBLING_SUFFIXES):
            continue
        path = os.path.join(inset_directory, name)
        try:
            if now - _newest_mtime(path) > older_than_s:
                stale.append(path)
        except OSError:
            pass
    return stale


def _remove(path: str) -> bool:
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True
    except OSError:
        return False


def sweep_stale(inset_directory: str | None = None, *,
                now: float | None = None,
                older_than_s: float = STALE_SCRATCH_S) -> list:
    """Remove what a killed fetch left; returns the paths removed.

    Always: the private scratch folders under :func:`scratch_root` not
    touched for ``older_than_s``.  With ``inset_directory``: that tile's
    :func:`stale_inset_siblings` too (the caller passes it only where it
    may write the cache)."""
    now = time.time() if now is None else now
    stale = []
    root = scratch_root()
    try:
        names = sorted(os.listdir(root))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(root, name)
        try:
            if now - _newest_mtime(path) > older_than_s:
                stale.append(path)
        except OSError:
            pass
    if inset_directory:
        stale.extend(stale_inset_siblings(inset_directory, now, older_than_s))
    return [path for path in stale if _remove(path)]
