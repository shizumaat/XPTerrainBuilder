"""Tiles of the World pack the user turned XPTerrainBuilder off on (#2100,
owner 2026-11-15T19:19Z: "we need a way in the UI for users to be able to
disable specific tiles if they don't want to use XPTerrainBuilder there").

Turning a tile off puts the pack's placeholder over its DSF (X-Plane falls
through to its default mesh there) and moves the tile's own files -- its
DSF, ``terrain/<tile>/``, ``textures/<tile>/`` and its imagery record --
into ``<pack>/`` :data:`KEPT_DIR` ``/<tile>/``, laid out like the pack
itself.  X-Plane reads a pack's ``Earth nav data`` only, so it never
opens the kept files, and turning the tile back on moves them back with
no rebuild (the DSF last, in one ``os.replace``).  The set of tiles off
is ONE small file in the pack (:data:`SET_FILE`).

Same held-by-X-Plane rule as a publish (``O4_World_Pack.publish``, rules
S3/S4): while X-Plane may hold the tile's files (the caller's ``held``
predicate, ``O4_World_Pack.held_by_xplane``) nothing moves; the tile is
:data:`TURNING_OFF` (or :data:`TURNING_ON`) and :func:`apply_pending`
completes it once X-Plane lets go.  A tile in the set -- in any of the
three states -- is never published into the pack: a build of it the user
asks for lands in the kept folder instead (``O4_World_Pack.swap_in``),
so turning it on shows the newest build.  The engine's readers of the
pack's tiles respect the set through :func:`off_tiles` /
:func:`kept_home` (``O4_World_Pack.world_tiles`` says :data:`OFF`).

A placeholder tile can be turned off too: nothing moves, but no flight or
build-ahead job builds it while it is off.

Standard library plus ``O4_World_Pack`` and ``O4_World_Imagery_Record``.
No tile or airport is named here.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
from typing import Callable

import O4_World_Imagery_Record as IREC
import O4_World_Pack as WP

__all__ = ["SET_FILE", "KEPT_DIR", "OFF", "TURNING_OFF", "TURNING_ON",
           "STATES", "ON", "off_tiles", "is_off", "kept_root", "kept_home",
           "turn_off", "turn_on", "apply_pending", "forget"]

#: The set of tiles off, in the pack's root (X-Plane ignores it).
SET_FILE = "XPTerrainBuilder_off.json"
#: The kept tiles' folder in the pack: ``<KEPT_DIR>/<tile>/`` holds a
#: tile's files in the pack's own layout.
KEPT_DIR = "XPTerrainBuilder_off"
#: Off: the placeholder in the pack, the tile's files kept.
OFF = "off"
#: Asked off while X-Plane may hold the tile: still drawn until it lets go.
TURNING_OFF = "turning_off"
#: Asked on while X-Plane may hold the placeholder: kept until it lets go.
TURNING_ON = "turning_on"
STATES = (OFF, TURNING_OFF, TURNING_ON)
#: What :func:`turn_on` answers once the tile is on.
ON = "on"

Held = Callable[[int, int], bool]


def _set_path(pack: str) -> str:
    return os.path.join(pack, SET_FILE)


def off_tiles(pack: str) -> dict:
    """``{(lat, lon): state}`` of the tiles off (any of :data:`STATES`);
    ``{}`` when the pack has no set or it cannot be read."""
    try:
        with open(_set_path(pack), encoding="utf-8") as handle:
            tiles = json.load(handle).get("tiles") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for name, state in tiles.items():
        with contextlib.suppress(ValueError):
            if state in STATES:
                out[WP.parse_tile(name)] = state
    return out


def _write(pack: str, tiles: dict) -> None:
    path = _set_path(pack)
    if not tiles:
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)
        return
    body = {"version": 1,
            "tiles": {WP.tile_name(*key): state
                      for key, state in sorted(tiles.items())}}
    partial = path + ".partial"
    with open(partial, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(body, handle, indent=1)
    os.replace(partial, path)


def _set_state(pack: str, lat: int, lon: int, state: "str | None") -> None:
    tiles = off_tiles(pack)
    if state is None:
        tiles.pop((lat, lon), None)
    else:
        tiles[(lat, lon)] = state
    _write(pack, tiles)


def is_off(pack: str, lat: int, lon: int) -> bool:
    """Is the tile in the set (off, or turning off or on)?"""
    return (int(lat), int(lon)) in off_tiles(pack)


def kept_root(pack: str, lat: int, lon: int) -> str:
    """The tile's kept folder (the pack's layout inside it)."""
    return os.path.join(pack, KEPT_DIR, WP.tile_name(lat, lon))


def kept_home(pack: str, lat: int, lon: int) -> str:
    """Where a build of the tile is published while it is off: its kept
    folder; ``""`` for a tile that is on."""
    return kept_root(pack, lat, lon) if is_off(pack, lat, lon) else ""


def _move(src: str, dest: str) -> None:
    """``src`` (a file or folder) renamed to ``dest``, an earlier ``dest``
    removed first; nothing when ``src`` is absent."""
    if not os.path.lexists(src):
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    _remove(dest)
    os.rename(src, dest)


def _remove(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)


def _own_files(root: str, lat: int, lon: int) -> list:
    """The tile's own DSF, folders and imagery record under a pack-shaped
    ``root``, the DSF first."""
    tile = WP.tile_name(lat, lon)
    return [os.path.join(root, WP.dsf_relpath(lat, lon)),
            os.path.join(root, "terrain", tile),
            os.path.join(root, "textures", tile),
            IREC.record_path(root, lat, lon)]


def _park(pack: str, lat: int, lon: int) -> None:
    """The tile's files into its kept folder, the placeholder over its DSF
    first (X-Plane never reads a DSF whose files are gone).  A kept DSF
    already there is a NEWER build (published while the tile was turning
    off): the pack's older files are dropped instead of kept (they are
    hard links of the build folder, ``O4_World_Pack._place_dir``)."""
    dsf, *folders = _own_files(pack, lat, lon)
    if not os.path.isfile(dsf) or WP.is_placeholder(dsf):
        return
    kept_dsf, *kept_folders = _own_files(kept_root(pack, lat, lon), lat, lon)
    newer = os.path.isfile(kept_dsf)
    if not newer:
        os.makedirs(os.path.dirname(kept_dsf), exist_ok=True)
        _remove(kept_dsf + ".partial")
        WP._link_or_copy(dsf, kept_dsf + ".partial")
        os.replace(kept_dsf + ".partial", kept_dsf)
    WP.write_placeholder(pack, lat, lon)
    for src, dest in zip(folders, kept_folders):
        if newer:
            _remove(src)
        else:
            _move(src, dest)


def _restore(pack: str, lat: int, lon: int) -> None:
    """The kept files back into the pack, the DSF last (one
    ``os.replace`` over the placeholder); the kept folder removed."""
    kept = kept_root(pack, lat, lon)
    kept_dsf, *kept_folders = _own_files(kept, lat, lon)
    if os.path.isfile(kept_dsf):
        WP._share_folder(kept, pack)
        dsf, *folders = _own_files(pack, lat, lon)
        for src, dest in zip(kept_folders, folders):
            _move(src, dest)
        os.makedirs(os.path.dirname(dsf), exist_ok=True)
        os.replace(kept_dsf, dsf)
    shutil.rmtree(kept, ignore_errors=True)
    with contextlib.suppress(OSError):
        os.rmdir(os.path.join(pack, KEPT_DIR))


def turn_off(pack: str, lat: int, lon: int, held: Held) -> str:
    """Turn XPTerrainBuilder off on the tile: :data:`OFF` (done) or
    :data:`TURNING_OFF` (``held(lat, lon)``: X-Plane may hold its files).
    Raises ``ValueError`` when the pack has no DSF of the tile."""
    lat, lon = int(lat), int(lon)
    state = off_tiles(pack).get((lat, lon))
    if state in (OFF, TURNING_OFF):
        return state
    if state == TURNING_ON:                # nothing moved back yet
        _set_state(pack, lat, lon, OFF)
        return OFF
    dsf = os.path.join(pack, WP.dsf_relpath(lat, lon))
    if not os.path.isfile(dsf):
        raise ValueError("The World pack holds no tile %s."
                         % WP.tile_name(lat, lon))
    if not WP.is_placeholder(dsf) and held(lat, lon):
        _set_state(pack, lat, lon, TURNING_OFF)
        return TURNING_OFF
    _park(pack, lat, lon)
    _set_state(pack, lat, lon, OFF)
    return OFF


def turn_on(pack: str, lat: int, lon: int, held: Held) -> str:
    """Turn XPTerrainBuilder back on: :data:`ON` (its kept files back in
    the pack, or none to restore) or :data:`TURNING_ON` (``held``: X-Plane
    may hold the placeholder's files)."""
    lat, lon = int(lat), int(lon)
    state = off_tiles(pack).get((lat, lon))
    if state is None:
        return ON
    if state == TURNING_OFF:               # nothing moved yet
        _set_state(pack, lat, lon, None)
        return ON
    kept_dsf = os.path.join(kept_root(pack, lat, lon), WP.dsf_relpath(lat, lon))
    if os.path.isfile(kept_dsf) and held(lat, lon):
        _set_state(pack, lat, lon, TURNING_ON)
        return TURNING_ON
    _restore(pack, lat, lon)
    _set_state(pack, lat, lon, None)
    return ON


def apply_pending(pack: str, held: Held) -> list:
    """Complete every tile turning off or on that ``held`` now lets go;
    ``[(tile name, OFF or ON)]``."""
    done = []
    for (lat, lon), state in sorted(off_tiles(pack).items()):
        if state == OFF or held(lat, lon):
            continue
        if state == TURNING_OFF:
            _park(pack, lat, lon)
            _set_state(pack, lat, lon, OFF)
            done.append((WP.tile_name(lat, lon), OFF))
        else:
            _restore(pack, lat, lon)
            _set_state(pack, lat, lon, None)
            done.append((WP.tile_name(lat, lon), ON))
    return done


def forget(pack: str, lat: int, lon: int) -> None:
    """The tile out of the set and its kept folder removed (Undo of
    Convert gives the tile back its own pack).  The kept files are hard
    links of the tile's own folder: removing them unlinks, never
    follows."""
    if not is_off(pack, lat, lon):
        return
    shutil.rmtree(kept_root(pack, lat, lon), ignore_errors=True)
    _set_state(pack, int(lat), int(lon), None)
