"""Custom patches: which tiles carry one, and switching a tile back to the
auto patch (#1229, owner RULINGS 2026-10-26c).

A CUSTOM patch is any ``*.patch.osm`` in a tile's ``Patches/<10°>/<1°>/``
folder that is not ``<ICAO>_auto.patch.osm``
(:func:`O4_File_Names.is_manual_patch_name`) — the patch editor's own
``<ICAO>_edited.patch.osm`` and a hand-made one alike.  It is always
honoured: the build applies it and does not auto-patch that airport
(``O4_Vector_Map.include_patches`` says so in the build log).  Both apps
show it: a band around the tile on the map and a "Custom patch" line in
the tile info, and the tile info offers "Use auto patch", which renames
each custom patch to ``….disabled`` (``.disabled.2`` … when that name is
taken).  Nothing here ever deletes a patch or overwrites a file.

The Qt app calls these functions in process; the Mac app through the
engine's ``custom_patches`` and ``use_auto_patch`` commands
(``o4_engine.patch_commands``).  Nothing a build step imports may import
this module: it is outside the auto-patch code closure, so its wording can
change without staling an airport patch.
"""

from __future__ import annotations

import os

import O4_File_Names as FNAMES

__all__ = ["CUSTOM_PATCH_TITLE", "USE_AUTO_PATCH_TITLE", "SET_ASIDE_SUFFIX",
           "custom_patches", "custom_patch_tiles", "set_aside",
           "use_auto_patch", "info_text", "use_auto_patch_help"]

#: The tile info's label (``BuildPane.customPatchTitle`` in the Mac app).
CUSTOM_PATCH_TITLE = "Custom patch"
#: The tile info's button (``BuildPane.useAutoPatchTitle``).
USE_AUTO_PATCH_TITLE = "Use auto patch"
#: What a custom patch set aside is renamed with; the build reads only
#: names ending ``.patch.osm``.
SET_ASIDE_SUFFIX = ".disabled"


def custom_patches(lat: int, lon: int) -> list[str]:
    """The custom patch file names in the tile's Patches folder, sorted."""
    directory = FNAMES.patch_dir(lat, lon)
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return sorted(name for name in names if FNAMES.is_manual_patch_name(name)
                  and os.path.isfile(os.path.join(directory, name)))


def custom_patch_tiles() -> list[dict]:
    """Every tile with a custom patch: ``[{"lat", "lon", "files"}]``,
    sorted by tile, read from ``Patches/<10°>/<1°>/`` of the data root."""
    out = []
    root = FNAMES.Patch_dir
    try:
        blocks = sorted(os.listdir(root))
    except OSError:
        return out
    for block in blocks:
        try:
            cells = sorted(os.listdir(os.path.join(root, block)))
        except OSError:
            continue
        for cell in cells:
            parsed = FNAMES.parse_tile_key(cell)
            if parsed is None:
                continue
            lat, lon = parsed
            if FNAMES.long_latlon(lat, lon) != os.path.join(block, cell):
                continue
            files = custom_patches(lat, lon)
            if files:
                out.append({"lat": lat, "lon": lon, "files": files})
    return out


def set_aside(path: str) -> str:
    """Rename *path* to ``path + ".disabled"`` (``.disabled.2`` … when that
    name is taken) and return the new path.  Never overwrites: the new
    name is claimed with a hard link, which fails on an existing name;
    a filesystem without hard links gets a plain rename onto a name just
    checked to be free."""
    target = path + SET_ASIDE_SUFFIX
    n = 2
    while True:
        if not os.path.lexists(target):
            try:
                os.link(path, target)
            except FileExistsError:
                pass
            except OSError:
                if not os.path.lexists(target):
                    os.rename(path, target)
                    return target
            else:
                os.unlink(path)
                return target
        target = "%s%s.%d" % (path, SET_ASIDE_SUFFIX, n)
        n += 1


def use_auto_patch(lat: int, lon: int, icao: str | None = None) -> list[str]:
    """Set aside the tile's custom patches (only *icao*'s when given) so
    the next build auto-patches those airports.  Returns the new paths.

    :raises ValueError: when there is nothing to set aside (the user's
        sentence).
    """
    directory = FNAMES.patch_dir(lat, lon)
    names = custom_patches(lat, lon)
    if icao:
        names = [n for n in names if FNAMES.patch_file_icao(n) == icao.upper()]
    if not names:
        raise ValueError("tile %s has no custom patch%s to set aside"
                         % (FNAMES.short_latlon(lat, lon),
                            " for " + icao.upper() if icao else ""))
    return [set_aside(os.path.join(directory, name)) for name in names]


def info_text(files) -> str:
    """The tile info's line for *files* (the Mac app: the same words)."""
    return (", ".join(files) + " — the auto patch does not run for "
            + ("this airport" if len(files) == 1 else "these airports"))


def use_auto_patch_help() -> str:
    """The "Use auto patch" button's hover text (the Mac app: the same)."""
    return ("Renames the custom patch to .disabled (it is never deleted), "
            "so the next build auto-patches the airport.")
