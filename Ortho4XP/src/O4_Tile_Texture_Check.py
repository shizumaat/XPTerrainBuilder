"""Does an INSTALLED tile have every texture its terrain files name?

X-Plane stops loading a tile (``REN_terrain.cpp``, "Failed to find
resource '../textures/…dds'") when one of its ``terrain/*.ter`` files names
a texture its ``textures/`` folder lacks.  The build already refuses to
activate a scenery file in that state (:func:`O4_Tile_Staging.
missing_textures`, #901); this module asks the same question of a tile
that is ALREADY installed, whose textures may have gone since: moved to
the Trash, deleted by hand, lost with a drive.  Both apps show the answer
on the active tile and offer to rebuild it (the Qt app in process, the Mac
app through the engine's ``tile_texture_check`` command).

:func:`terrain_texture_names` is the cheap half: the textures the terrain
folder's FILE NAMES name (Ortho4XP's writer names ``<tex>.ter``,
``<tex>_sea.ter``, ``<tex>_water.ter`` and their ``_overlay`` forms after
``<tex>.dds``).  The imagery-source audit reads it so that a texture the
tile's terrain uses is never offered as unused, whatever the tile cfg
says (2026-10-25: a tile cfg reset to the source of a 2017 build made
the tile's real textures look "left over", and they went to the Trash).

Standard library only; no UI import.
"""

from __future__ import annotations

import os
import types

import O4_Tile_Staging as STAGING

__all__ = ["terrain_texture_names", "missing_textures", "tile_texture_check",
           "warning_text", "detail_text", "SAMPLE_SIZE"]

#: How many missing names a reply carries; the count is always whole.
SAMPLE_SIZE = 20
#: Terrain-file name suffixes that still name the base texture.
_TER_SUFFIXES = ("_overlay", "_sea", "_water")


def terrain_texture_names(build_dir: str):
    """The ``.dds`` names ``build_dir/terrain``'s file names stand for, or
    ``None`` when that folder cannot be listed (no call can be made then).

    Names only — one directory listing — so a sweep over a whole install
    stays cheap."""
    try:
        names = os.listdir(os.path.join(build_dir, STAGING.LIVE))
    except OSError:
        return None
    textures = set()
    for name in names:
        if not name.endswith(".ter"):
            continue
        stem = name[:-4]
        for suffix in _TER_SUFFIXES:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        textures.add(stem + ".dds")
    return frozenset(textures)


def missing_textures(build_dir: str) -> list:
    """The textures ``build_dir``'s live terrain files name that are not on
    disk, sorted: the build's own rule (#901), read from the files."""
    tile = types.SimpleNamespace(build_dir=build_dir, terrain_staging=None)
    return STAGING.missing_textures(tile)


def tile_texture_check(build_dir: str = "", **_ignored) -> dict:
    """The ``tile_texture_check`` command and the Qt pane's call.

    :returns: ``{"build_dir", "checked", "missing_count", "missing"}`` —
        ``checked`` is ``False`` when the tile has no terrain folder (there
        is nothing to check); ``missing`` holds at most
        :data:`SAMPLE_SIZE` names.
    """
    build_dir = str(build_dir or "")
    checked = bool(build_dir) and os.path.isdir(
        os.path.join(build_dir, STAGING.LIVE))
    missing = missing_textures(build_dir) if checked else []
    return {"build_dir": build_dir, "checked": checked,
            "missing_count": len(missing), "missing": missing[:SAMPLE_SIZE]}


def warning_text(missing_count: int) -> str:
    """The tile pane's one line (the Mac pane: the same words)."""
    return "%s missing — X-Plane cannot load this tile" % (
        "1 texture" if missing_count == 1
        else "%s textures" % format(missing_count, ","))


def detail_text(reply: dict) -> str:
    """The explanation under that line, naming the first missing files."""
    shown = list(reply.get("missing") or [])[:3]
    more = int(reply.get("missing_count", 0)) - len(shown)
    names = ", ".join(shown) + (" and %s more" % format(more, ",")
                                if more > 0 else "")
    return ("This tile's terrain files name textures its textures folder "
            "does not have (%s). They may have been moved to the Trash or "
            "deleted; put them back from the Trash, or rebuild the tile with "
            "the imagery it was built with." % names)
