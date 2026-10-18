"""Terrain files of a build IN PROGRESS: staged beside the tile's live
``terrain`` folder and installed only when the build completes (#598).

The scenery file X-Plane reads names its terrain files by path
(``terrain/<texture>.ter``).  The imagery step used to delete the live
folder first and rewrite it file by file, so from its first second the
previous scenery file pointed at nothing — and, measured on 80 real tiles
that hold two generations of scenery file, 19 still had references missing
after the next build had finished (a changed imagery source or zoom level
changes every name).  A build stopped or killed anywhere therefore left a
tile X-Plane could not load.

Owner ruling 2026-10-12h (3): the previous scenery stays until a build
COMPLETES.  So a build writes its terrain files into a folder of its own
(:func:`begin`, :func:`terrain_dir`); the completed build moves them in
(:func:`install` — additive, every file the previous scenery file names is
still there), activates its scenery file, and only then removes what the
new file does not name (:func:`prune`).

Standard library only; no UI import.
"""

from __future__ import annotations

import os
import shutil

import O4_File_Names as FNAMES
import O4_Held_File as HELD

__all__ = ["staging_dir", "begin", "terrain_dir", "install", "prune",
           "missing_textures"]

LIVE = "terrain"


def staging_dir(tile) -> str:
    """This tile's staging folder.  Named for the tile: a grouped build
    directory is shared by several tiles, each with its own build."""
    return os.path.join(
        tile.build_dir,
        "terrain_staged_" + FNAMES.short_latlon(tile.lat, tile.lon))


def begin(tile) -> str:
    """Start a build's staging folder empty (a stopped build's leftover is
    discarded) and point the tile's terrain writes at it."""
    path = staging_dir(tile)
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    tile.terrain_staging = path
    return path


def terrain_dir(tile) -> str:
    """Where this tile's terrain files are written NOW: the staging folder
    of a build in progress, else the live folder."""
    return (getattr(tile, "terrain_staging", None)
            or os.path.join(tile.build_dir, LIVE))


def missing_textures(tile) -> list:
    """The ``.dds`` textures this build's terrain files name that are not on
    disk, sorted (#901).  X-Plane stops on a terrain file whose texture is
    missing, so a scenery file naming one is never activated."""
    folder = terrain_dir(tile)
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".ter"))
    except OSError:
        return []
    live = os.path.join(tile.build_dir, LIVE)
    missing = set()
    for name in names:
        try:
            with open(os.path.join(folder, name), encoding="utf-8",
                      errors="replace") as handle:
                refs = [line.split()[-1] for line in handle
                        if line.rstrip().lower().endswith(".dds")]
        except OSError:
            continue
        for ref in refs:
            path = os.path.normpath(os.path.join(live, ref))
            if not os.path.isfile(path):
                missing.add(os.path.basename(path))
    return sorted(missing)


def install(tile) -> set:
    """Move every staged file into the live folder; the names moved.

    Additive: nothing is removed, so the scenery file still active keeps
    every file it names until :func:`prune`.  Raises ``OSError`` on a
    refused move; the files already moved stay (same names, new text).
    """
    staged = getattr(tile, "terrain_staging", None)
    tile.terrain_staging = None
    if not staged or not os.path.isdir(staged):
        return set()
    live = os.path.join(tile.build_dir, LIVE)
    os.makedirs(live, exist_ok=True)
    names = set(os.listdir(staged))
    for name in sorted(names):
        HELD.retrying_a_held_file(
            lambda name=name: os.replace(os.path.join(staged, name),
                                         os.path.join(live, name)))
    shutil.rmtree(staged, ignore_errors=True)
    return names


def prune(tile, keep) -> None:
    """Remove the live terrain files the completed build did not write.
    Leftovers only: a file that will not go is left."""
    live = os.path.join(tile.build_dir, LIVE)
    try:
        names = os.listdir(live)
    except OSError:
        return
    for name in names:
        if name in keep:
            continue
        try:
            os.remove(os.path.join(live, name))
        except OSError:
            pass
