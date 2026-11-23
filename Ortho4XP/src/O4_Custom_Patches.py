"""Custom patches: which tiles carry one, and how each airport uses its
custom patch (#1229, #2179; owner RULINGS 2026-10-26c, 2026-11-23d/f).

A CUSTOM patch is any ``*.patch.osm`` in a tile's ``Patches/<10°>/<1°>/``
folder that is not ``<ICAO>_auto.patch.osm``
(:func:`O4_File_Names.is_manual_patch_name`) — the patch editor's own
``<ICAO>_edited.patch.osm`` and a hand-made one alike.  Both apps show it:
a band around the tile on the map and a "Custom patch" row in the tile
info.

For 1.0 each airport with a hand-made custom patch uses it one of two
ways (``O4_Custom_Patch_Use``, the one reader every build step asks):
"As made" — the patch unchanged, on the elevation it was made for — or
"Our auto patch" — our high-resolution elevation, the custom file kept
but not applied.  An installed custom patch is used as made, with a
warning that higher-resolution elevation needs our auto patch (23f).  A
picker on the Build box's airport row and in the tile info changes it
(:func:`set_use`); nothing is renamed.

Once per custom patch both apps also say which elevation it was built for
— the build's fit (``O4_Custom_Patch_Source``) records it — with "Use our
auto patch" and "Keep as made" as the answers (:func:`_elevation_notices`,
:func:`notice_seen`).

The Qt app calls these functions in process; the Mac app through the
engine's ``custom_patches``, ``custom_patch_use`` and
``custom_patch_notice_seen`` commands (``o4_engine.patch_commands``).
Nothing a build step imports may import this module: it is outside the
auto-patch code closure, so its wording can change without staling an
airport patch.
"""

from __future__ import annotations

import os
import re

import O4_Airport_Fit as AIRPORT_FIT
import O4_Custom_Patch_Use as CUSTOM_USE
import O4_File_Names as FNAMES

__all__ = ["CUSTOM_PATCH_TITLE", "USE_AUTO_PATCH_TITLE", "SET_ASIDE_SUFFIX",
           "KEEP_CUSTOM_PATCH_TITLE", "AS_MADE_TITLE", "AUTO_PATCH_TITLE",
           "AS_MADE_HELP", "AUTO_PATCH_HELP", "AS_MADE_WARNING",
           "custom_patches", "custom_patch_tiles", "set_aside",
           "airport_uses", "set_use", "use_title",
           "info_text", "notice_seen",
           "FIT_KEY", "unmodified_airports", "stand_down_new", "fit_state",
           "airport_fits",
           "fit_confirm_text"]

#: The tile info's label (``BuildPane.customPatchTitle`` in the Mac app).
CUSTOM_PATCH_TITLE = "Custom patch"
#: The custom-patch notice's two answers (#2179; ``O4CustomPatchText.
#: useAutoPatchTitle`` / ``keepTitle``): the first sets the airport to
#: "Our auto patch", the other keeps it as made; the notice is not shown
#: again either way.
USE_AUTO_PATCH_TITLE = "Use our auto patch"
KEEP_CUSTOM_PATCH_TITLE = "Keep as made"
#: The two ways an airport uses its custom patch (RULINGS 2026-11-23d),
#: the picker's labels and hover texts in both apps
#: (``O4CustomPatchText.asMadeTitle`` …).
AS_MADE_TITLE = "As made"
AUTO_PATCH_TITLE = "Our auto patch"
AS_MADE_HELP = ("Uses the patch unchanged, on the elevation it was made "
                "for. The airport keeps its author's shape and its "
                "scenery package is used unmodified.")
AUTO_PATCH_HELP = ("Grades the airport to the slope rules on our "
                   "high-resolution elevation. Your patch is kept, not "
                   "used.")
#: Under an airport used as made (owner RULINGS 2026-11-23f).
AS_MADE_WARNING = ("Higher-resolution elevation is available for this "
                   "airport, but it requires our auto patch.")
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
    "notices", "airports"}]`` (:func:`_elevation_notices`,
    :func:`airport_uses`), sorted by tile, read from
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
                            "notices": _elevation_notices(lat, lon),
                            "airports": airport_uses(lat, lon)})
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


# ── How each airport uses its custom patch (#2179, RULINGS 2026-11-23d/f)
def use_title(mode: str) -> str:
    """The picker's label of a mode."""
    return AUTO_PATCH_TITLE if mode == CUSTOM_USE.AUTO_PATCH else AS_MADE_TITLE


def airport_uses(lat: int, lon: int) -> list[dict]:
    """The picker's rows for the tile, one per airport with a hand-made
    custom patch, sorted: ``{"icao", "tile": [lat, lon], "files", "use",
    "chosen", "warning"}`` — ``use`` its mode, ``chosen`` False while it
    takes the default (As made), ``warning`` :data:`AS_MADE_WARNING` while
    it is used as made, else ""."""
    directory = FNAMES.patch_dir(lat, lon)
    files = CUSTOM_USE.custom_files(directory)
    return [{"icao": icao, "tile": [lat, lon], "files": files[icao],
             "use": mode, "chosen": chosen,
             "warning": AS_MADE_WARNING if mode == CUSTOM_USE.AS_MADE else ""}
            for (icao, (mode, chosen)) in sorted(
                CUSTOM_USE.uses(directory).items())]


def set_use(lat: int, lon: int, icao: str, mode: str) -> dict:
    """Use *icao*'s custom patch *mode* (``"as_made"``, ``"auto_patch"``,
    or ``"default"``) for the tile's next builds; returns its row
    (:func:`airport_uses`).  Nothing is renamed.

    :raises ValueError: for an airport without a custom patch in the tile,
        or an unknown mode (the user's sentence)."""
    icao = str(icao).strip().upper()
    directory = FNAMES.patch_dir(lat, lon)
    if icao not in CUSTOM_USE.custom_files(directory):
        raise ValueError("tile %s has no custom patch for %s"
                         % (FNAMES.short_latlon(lat, lon), icao or "?"))
    CUSTOM_USE.set_use(directory, icao, mode)
    return next(row for row in airport_uses(lat, lon) if row["icao"] == icao)


def info_text(files) -> str:
    """The tile info's line for *files* (the Mac app: the same words)."""
    return ", ".join(files)


# ── Which elevation a custom patch was built for (owner 2026-11-19T13:42Z,
# #2179) ─────────────────────────────────────────────────────────────────
#: The tile's record of the notices the user has answered, in its build
#: folder: ``{file name: [mtime_ns, size]}``.
_NOTICES_SEEN = "custom_patch_notices_seen.json"
_BASE_SOURCE = re.compile(r"^base elevation \((.*)\)$")


def _source_text(source: str) -> str:
    """The user's words for an elevation source the build's fit named
    (``O4_Custom_Patch_Source``): the base raster by its name and resolution —
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
    return ("This custom patch (%s) was built for %s and is used as made. "
            % (file, _source_text(source)) + AS_MADE_WARNING)


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
    tile used as made whose elevation source a build identified
    (``O4_Custom_Patch_Source.SOURCES_RECORD``, for the file as it is now)
    and whose notice the user has not answered (:func:`notice_seen`),
    sorted by file."""
    import O4_Custom_Patch_Source as REBASE

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
# 2026-11-18l, #2172; per airport since #2182, ``O4_Airport_Fit``) ─────────
#: The tile setting each airport's own value falls back to.
FIT_KEY = AIRPORT_FIT.FIT_KEY
#: The tile's record of the custom patches a build has seen, in its build
#: folder: ``{file name: [mtime_ns, size]}``.
_SEEN_RECORD = "custom_patches_seen.json"


def _unmodified_files(lat: int, lon: int) -> dict:
    """``{file: ICAO}`` of the custom patches whose airport's pack is used
    unmodified (RULINGS 2026-11-18k): every custom patch but the patch
    editor's own ``<ICAO>_edited.patch.osm``, of an airport that uses it
    as made (#2179: an airport on our auto patch is fitted as any other)."""
    return {name: icao for (icao, names) in CUSTOM_USE.as_made_files(
        FNAMES.patch_dir(lat, lon)).items() for name in names}


def unmodified_airports(lat: int, lon: int) -> list[str]:
    """The ICAOs of the tile's custom patches used as made (2026-11-18k),
    sorted."""
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
    """At a build's start: a custom patch the tile has not seen turns
    "Fit custom airport buildings" OFF for ITS airport (the airport's own
    value, ``O4_Airport_Fit``; #2182: the tile's other airports keep
    theirs), logged in one line naming the airports; the patches are
    recorded as seen.  Returns the new airports.  A per-build switch the
    user turns on afterwards (``Tile.apply_build_overrides``) still wins."""
    import json

    signature = _signature(tile.lat, tile.lon)
    if signature == _seen(tile):
        return []
    new = _new_airports(tile)
    turned = [icao for icao in new if AIRPORT_FIT.fits(tile, icao)]
    own = AIRPORT_FIT.read(tile.build_dir)
    for icao in new:
        if own.get(icao) is not False:   # off as its own value, not the tile's
            AIRPORT_FIT.set_fit(tile.build_dir, icao, False)
    if turned:
        import O4_UI_Utils as UI

        UI.vprint(0, "Custom patch new for %s: \"Fit custom airport buildings "
                     "to the new ground\" is turned off for %s — the "
                     "airport's pack is used unmodified; the tile's other "
                     "airports keep their own setting." % (
                         ", ".join(turned),
                         "this airport" if len(turned) == 1 else "these airports"))
    os.makedirs(tile.build_dir, exist_ok=True)
    with open(os.path.join(tile.build_dir, _SEEN_RECORD), "w",
              encoding="utf-8", newline="") as handle:
        json.dump(signature, handle, sort_keys=True)
    return new


def airport_fits(tile, icaos) -> dict:
    """``{ICAO: fit}`` for a configured tile's next build: each airport's
    own value (``O4_Airport_Fit.fits``) — off when its custom patch is new
    to the tile (the build's :func:`stand_down_new` will turn it off)."""
    new = set(_new_airports(tile))
    return {icao: icao not in new and AIRPORT_FIT.fits(tile, icao)
            for icao in sorted(set(icaos))}


def fit_state(tile) -> tuple[list[str], bool]:
    """``(custom-patch airports, fit)`` for a configured tile: whether its
    next build fits any of the airports it knows (its custom patches' and
    those with a value of their own; else the tile's setting).  The Build
    card reads each pack airport's own value (:func:`airport_fits`); this
    is its answer when no pack is listed."""
    custom = unmodified_airports(tile.lat, tile.lon)
    known = set(custom) | set(AIRPORT_FIT.read(tile.build_dir))
    if not known:
        return (custom, AIRPORT_FIT.any_fits(tile))
    return (custom, any(airport_fits(tile, known).values()))


def fit_confirm_text(icaos) -> str:
    """The question both apps ask before the switch is turned on for tiles
    with custom patches, or "" when there are none."""
    if not icaos:
        return ""
    return ("Custom patches are installed for %s. Fitting buildings to the "
            "new ground will also modify these airports' scenery packages. "
            "Continue?" % ", ".join(icaos))
