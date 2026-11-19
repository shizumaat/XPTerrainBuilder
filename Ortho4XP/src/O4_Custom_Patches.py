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

Once per custom patch (owner 2026-11-19T13:42Z, #2179) both apps say which
elevation it was built for — the build's fit (``O4_Patch_Rebase``)
records it — and that the auto patch gives this airport higher-resolution
elevation, with "Use auto patch" and "Keep custom patch" as the answers
(:func:`_elevation_notices`, :func:`notice_seen`).

The Qt app calls these functions in process; the Mac app through the
engine's ``custom_patches``, ``use_auto_patch`` and
``custom_patch_notice_seen`` commands
(``o4_engine.patch_commands``).  Nothing a build step imports may import
this module: it is outside the auto-patch code closure, so its wording can
change without staling an airport patch.
"""

from __future__ import annotations

import os
import re

import O4_File_Names as FNAMES

__all__ = ["CUSTOM_PATCH_TITLE", "USE_AUTO_PATCH_TITLE", "SET_ASIDE_SUFFIX",
           "KEEP_CUSTOM_PATCH_TITLE",
           "custom_patches", "custom_patch_tiles", "set_aside",
           "use_auto_patch", "info_text", "use_auto_patch_help",
           "notice_seen",
           "FIT_KEY", "unmodified_airports", "stand_down_new", "fit_state",
           "fit_confirm_text"]

#: The tile info's label (``BuildPane.customPatchTitle`` in the Mac app).
CUSTOM_PATCH_TITLE = "Custom patch"
#: The tile info's button (``BuildPane.useAutoPatchTitle``).
USE_AUTO_PATCH_TITLE = "Use auto patch"
#: The custom-patch notice's other button (#2179; ``O4CustomPatchText.
#: keepTitle``): the patch stays, the notice is not shown again.
KEEP_CUSTOM_PATCH_TITLE = "Keep custom patch"
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
    """Every tile with a custom patch: ``[{"lat", "lon", "files",
    "notices"}]`` (:func:`_elevation_notices`), sorted by tile, read from
    ``Patches/<10°>/<1°>/`` of the data root."""
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
                out.append({"lat": lat, "lon": lon, "files": files,
                            "notices": _elevation_notices(lat, lon)})
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


# ── Which elevation a custom patch was built for (owner 2026-11-19T13:42Z,
# #2179) ─────────────────────────────────────────────────────────────────
#: The tile's record of the notices the user has answered, in its build
#: folder: ``{file name: [mtime_ns, size]}``.
_NOTICES_SEEN = "custom_patch_notices_seen.json"
_BASE_SOURCE = re.compile(r"^base elevation \((.*)\)$")


def _source_text(source: str) -> str:
    """The user's words for an elevation source the build's fit named
    (``O4_Patch_Rebase``): the base raster by its name and resolution —
    Viewfinderpanoramas called the Ortho4XP default — an inset by its file
    name."""
    base = _BASE_SOURCE.match(source or "")
    if base:
        name = base.group(1)
        if name.lower().startswith("viewfinder"):
            return name + " (the Ortho4XP default)"
        return name
    if source == "build DEM":
        return "this tile's high-resolution elevation"
    return source or "an unknown elevation source"


def _notice_text(file: str, source: str) -> str:
    """The notice both apps show once per custom patch (the Mac app shows
    the engine's text as is)."""
    return ("This custom patch (%s) was built for %s. For higher-resolution "
            "elevation data at this airport, use the auto patch."
            % (file, _source_text(source)))


def _read_json(path: str) -> dict:
    import json

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _elevation_notices(lat: int, lon: int, custom_build_dir: str = "") -> list:
    """``[{"icao", "file", "source", "text"}]``: each custom patch of the
    tile whose elevation source a build identified (``O4_Patch_Rebase.
    SOURCES_RECORD``, for the file as it is now) and whose notice the user
    has not answered (:func:`notice_seen`), sorted by file."""
    import O4_Patch_Rebase as REBASE

    folder = FNAMES.build_dir(lat, lon, custom_build_dir)
    found = _read_json(os.path.join(folder, REBASE.SOURCES_RECORD))
    seen = _read_json(os.path.join(folder, _NOTICES_SEEN))
    out = []
    for (name, stamp) in sorted(_signature(lat, lon).items()):
        row = found.get(name)
        if (isinstance(row, dict) and row.get("signature") == stamp
                and seen.get(name) != stamp):
            source = str(row.get("source") or "")
            out.append({"icao": FNAMES.patch_file_icao(name), "file": name,
                        "source": source, "text": _notice_text(name, source)})
    return out


def notice_seen(lat: int, lon: int, file: str,
                custom_build_dir: str = "") -> None:
    """Remember that the user answered *file*'s notice: it is not shown
    again until the file changes."""
    import json

    stamp = _signature(lat, lon).get(file)
    if stamp is None:
        raise ValueError("tile %s has no custom patch %s"
                         % (FNAMES.short_latlon(lat, lon), file))
    folder = FNAMES.build_dir(lat, lon, custom_build_dir)
    path = os.path.join(folder, _NOTICES_SEEN)
    seen = _read_json(path)
    seen[file] = stamp
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        json.dump(seen, handle, sort_keys=True)


# ── "Fit custom airport buildings" and a custom patch (owner RULINGS
# 2026-11-18l, #2172) ─────────────────────────────────────────────────────
#: The tile setting the Build card's "Fit custom airport buildings to the
#: new ground" switch and Settings' row edit.
FIT_KEY = "modify_custom_airports"
#: The tile's record of the custom patches a build has seen, in its build
#: folder: ``{file name: [mtime_ns, size]}``.
_SEEN_RECORD = "custom_patches_seen.json"


def _unmodified_files(lat: int, lon: int) -> dict:
    """``{file: ICAO}`` of the custom patches whose airport's pack is used
    unmodified (RULINGS 2026-11-18k): every custom patch but the patch
    editor's own ``<ICAO>_edited.patch.osm``."""
    out = {}
    for name in custom_patches(lat, lon):
        icao = FNAMES.patch_file_icao(name)
        if icao and name != FNAMES.edited_patch_name(icao):
            out[name] = icao
    return out


def unmodified_airports(lat: int, lon: int) -> list[str]:
    """The ICAOs of the tile's custom patches (2026-11-18k), sorted."""
    return sorted(set(_unmodified_files(lat, lon).values()))


def _signature(lat: int, lon: int) -> dict:
    directory = FNAMES.patch_dir(lat, lon)
    out = {}
    for name in _unmodified_files(lat, lon):
        try:
            st = os.stat(os.path.join(directory, name))
        except OSError:
            continue
        out[name] = [st.st_mtime_ns, st.st_size]
    return out


def _seen(tile) -> dict:
    return _read_json(os.path.join(tile.build_dir, _SEEN_RECORD))


def _new_airports(tile) -> list[str]:
    """The airports whose custom patch this tile's builds have not seen
    (newly installed, or changed since the last build), sorted."""
    seen = _seen(tile)
    return sorted({FNAMES.patch_file_icao(name)
                   for (name, stamp) in _signature(tile.lat, tile.lon).items()
                   if seen.get(name) != stamp})


def stand_down_new(tile) -> list[str]:
    """At a build's start: a custom patch the tile has not seen turns its
    "Fit custom airport buildings" OFF (in memory and in the tile cfg),
    logged in one line naming the airports; the patches are recorded as
    seen.  Returns the new airports.  A per-build switch the user turns on
    afterwards (``Tile.apply_build_overrides``) still wins."""
    import json

    signature = _signature(tile.lat, tile.lon)
    if signature == _seen(tile):
        return []
    new = _new_airports(tile)
    if new and getattr(tile, FIT_KEY, False):
        import O4_Settings_Model as SM
        import O4_UI_Utils as UI

        setattr(tile, FIT_KEY, False)
        SM.write_tile(tile.lat, tile.lon, tile.custom_build_dir,
                      {FIT_KEY: False})
        UI.vprint(0, "Custom patch new for %s: \"Fit custom airport buildings "
                     "to the new ground\" is turned off for this tile — the "
                     "airport's pack is used unmodified." % ", ".join(new))
    os.makedirs(tile.build_dir, exist_ok=True)
    with open(os.path.join(tile.build_dir, _SEEN_RECORD), "w",
              encoding="utf-8", newline="") as handle:
        json.dump(signature, handle, sort_keys=True)
    return new


def fit_state(tile) -> tuple[list[str], bool]:
    """``(custom-patch airports, fit)`` for a configured tile: what its
    next build fits — off when a custom patch is new to it."""
    fit = bool(getattr(tile, FIT_KEY, False)) and not _new_airports(tile)
    return (unmodified_airports(tile.lat, tile.lon), fit)


def fit_confirm_text(icaos) -> str:
    """The question both apps ask before the switch is turned on for tiles
    with custom patches, or "" when there are none."""
    if not icaos:
        return ""
    return ("Custom patches are installed for %s. Fitting buildings to the "
            "new ground will also modify these airports' scenery packages. "
            "Continue?" % ", ".join(icaos))
