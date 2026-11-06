"""Which scenery pack's ground does X-Plane draw on one of our tiles?

X-Plane draws, for each tile, the FIRST base-mesh DSF it meets in its
load order (``scenery_packs.ini``, highest first); every pack below it is
not drawn there at all, while overlays stack on top (#1729).  Two cases
matter to a tile we build:

* **hidden by** — a pack ABOVE our tile ships a base mesh for the same
  tile: X-Plane shows that pack's ground and none of ours (its imagery,
  its graded airports).  Always reported.
* **hides** — a pack BELOW our tile ships a base mesh for the tile,
  covers at most :data:`LOCAL_MESH_TILES` tiles and is not photo scenery:
  a mesh made for one place (an airport's own terrain), which our tile
  now hides.  A regional mesh, or another ortho, under an ortho tile is
  the usual set-up and is not reported.

:func:`tile_mesh_order` answers for one tile (the ``tile_mesh_order``
command, the Qt tile pane and the build's closing warnings);
:func:`apply_mesh_order` makes the user's choice in ``scenery_packs.ini``
(move our tile above the pack, below it, or disable the pack).  The
words both apps show are :func:`warning_lines` (the Mac app's
``TileMeshOrder.swift`` repeats them).
"""

from __future__ import annotations

import os

import O4_Custom_Scenery as PACKS
import O4_DSF_Header as HEADER
import O4_File_Names as FNAMES
import O4_Scenery_Packs as SP

__all__ = ["LOCAL_MESH_TILES", "ACTIONS", "drawn_mesh_dsf", "tile_mesh_order",
           "apply_mesh_order", "warning_lines", "degraded_rows",
           "HIDDEN_BY_DETAIL", "HIDES_DETAIL"]

#: A base-mesh pack covering at most this many tiles is made for one place.
LOCAL_MESH_TILES = 4

#: ``apply_mesh_order`` actions: our tile above the pack, below it, or the
#: pack disabled.
ACTIONS = ("raise", "lower", "disable")


def _real(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _drawn_order(custom_scenery_dir: str, lat: int, lon: int,
                 build_dir: str):
    """``(ours, meshes)``: the index of our tile in the tile's load order
    (``None`` when X-Plane does not load it) and ``[(index, name)]`` of
    the other packs whose DSF for the tile is a base mesh."""
    ours_dsf = _real(FNAMES.dsf_file(build_dir, lat, lon)) if build_dir else ""
    ours, meshes = None, []
    for index, name in enumerate(SP.load_order(custom_scenery_dir)):
        dsf = FNAMES.dsf_file(os.path.join(custom_scenery_dir, name), lat, lon)
        if not os.path.isfile(dsf):
            continue
        if ours_dsf and _real(dsf) == ours_dsf:
            if ours is None:
                ours = index
        elif HEADER.dsf_is_overlay(dsf) is False:
            meshes.append((index, name))
    return ours, meshes


def drawn_mesh_dsf(custom_scenery_dir: str, lat: int, lon: int) -> str | None:
    """The base-mesh DSF X-Plane draws on the tile: the first one in the
    load order (``tools/drawn_check.py``, #1903), or ``None``."""
    for name in SP.load_order(custom_scenery_dir):
        dsf = FNAMES.dsf_file(os.path.join(custom_scenery_dir, name), lat, lon)
        if os.path.isfile(dsf) and HEADER.dsf_is_overlay(dsf) is False:
            return dsf
    return None


def _is_local_mesh(custom_scenery_dir: str, name: str) -> bool:
    """A mesh made for one place: few tiles, and not photo scenery (one
    ortho pack per tile is the usual way orthos ship)."""
    root = os.path.realpath(os.path.join(custom_scenery_dir, name))
    return (len(PACKS.pack_tiles(root)) <= LOCAL_MESH_TILES
            and PACKS.pack_kind(name, root) != "ortho")


def tile_mesh_order(custom_scenery_dir: str = "", lat=0, lon=0,
                    build_dir: str = "", **_ignored) -> dict:
    """The ``tile_mesh_order`` command and the Qt pane's call.

    :returns: ``{"lat", "lon", "checked", "hidden_by", "hides"}`` —
        ``checked`` is ``False`` when X-Plane does not load our tile from
        this Custom Scenery folder (not installed, or disabled); the two
        lists name packs, highest in the load order first.
    """
    lat, lon = int(lat), int(lon)
    custom_scenery_dir = str(custom_scenery_dir or "")
    reply = {"lat": lat, "lon": lon, "checked": False,
             "hidden_by": [], "hides": []}
    if not custom_scenery_dir or not os.path.isdir(custom_scenery_dir):
        return reply
    ours, meshes = _drawn_order(custom_scenery_dir, lat, lon,
                                str(build_dir or ""))
    if ours is None:
        return reply
    reply["checked"] = True
    reply["hidden_by"] = [name for index, name in meshes if index < ours]
    reply["hides"] = [name for index, name in meshes if index > ours
                      and _is_local_mesh(custom_scenery_dir, name)]
    return reply


# ── the user's choice, written into scenery_packs.ini ─────────────────────
def _row_index(lines: list, name: str):
    """The index of the first ini row naming pack ``name``, or ``None``."""
    for index, line in enumerate(lines):
        tokens = line.strip().split(None, 1)
        if (len(tokens) == 2 and tokens[0].startswith("SCENERY_PACK")
                and SP.pack_name_from_ini_path(tokens[1]) == name):
            return index
    return None


def _our_name(custom_scenery_dir: str, lat: int, lon: int,
              build_dir: str):
    """The Custom Scenery entry X-Plane loads our tile's DSF from."""
    ours_dsf = _real(FNAMES.dsf_file(build_dir, lat, lon))
    for name in SP.load_order(custom_scenery_dir):
        dsf = FNAMES.dsf_file(os.path.join(custom_scenery_dir, name), lat, lon)
        if os.path.isfile(dsf) and _real(dsf) == ours_dsf:
            return name
    return None


def _edit_rows(lines: list, action: str, ours, theirs: int) -> None:
    """Move our row above / below theirs, or disable theirs, in place."""
    if action == "disable":
        rest = lines[theirs].strip().split(None, 1)[1]
        lines[theirs] = "SCENERY_PACK_DISABLED " + rest
        return
    row = lines.pop(ours)
    if ours < theirs:
        theirs -= 1
    lines.insert(theirs if action == "raise" else theirs + 1, row)


def apply_mesh_order(custom_scenery_dir: str = "", lat=0, lon=0,
                     build_dir: str = "", action: str = "",
                     pack: str = "", **_ignored) -> dict:
    """Make the user's choice for ``pack`` on our tile and answer the
    tile's order afresh (:func:`tile_mesh_order`).

    ``action``: ``raise`` (our tile's row just above the pack's),
    ``lower`` (just below it) or ``disable`` (the pack's row
    ``SCENERY_PACK_DISABLED``).  Raises ``ValueError`` with the user's
    sentence when the ini cannot be changed that way.
    """
    lat, lon = int(lat), int(lon)
    if action not in ACTIONS:
        raise ValueError("Unknown scenery order change: %r." % action)
    ini = os.path.join(str(custom_scenery_dir or ""), SP.INI_FILENAME)
    try:
        lines, newline = SP.read_ini_lines(ini)
    except OSError:
        raise ValueError("scenery_packs.ini could not be read.") from None
    ours_name = _our_name(custom_scenery_dir, lat, lon, str(build_dir or ""))
    ours = _row_index(lines, ours_name) if ours_name else None
    theirs = _row_index(lines, str(pack or ""))
    if theirs is None or (ours is None and action != "disable"):
        raise ValueError("X-Plane has not listed that scenery yet; start "
                         "X-Plane once, then try again.")
    _edit_rows(lines, action, ours, theirs)
    try:
        SP.write_ini_lines(ini, lines, newline)
    except OSError as exc:
        raise ValueError("scenery_packs.ini could not be written (%s)."
                         % exc.strerror) from None
    return tile_mesh_order(custom_scenery_dir, lat, lon, build_dir)


# ── words ────────────────────────────────────────────────────────────────
def _names(packs: list) -> str:
    first = "“%s”" % packs[0]
    return first if len(packs) == 1 else "%s and %d more" % (
        first, len(packs) - 1)


#: The explanations under the tile pane's lines (the Mac app: the same).
HIDDEN_BY_DETAIL = (
    "That scenery ships its own ground for this tile and is above it in "
    "X-Plane's scenery order, so X-Plane shows its ground and none of this "
    "tile's imagery or graded airports. Move this tile above it, or "
    "disable that scenery.")
HIDES_DETAIL = (
    "That scenery ships its own ground for a small part of this tile, such "
    "as an airport, and is below this tile in X-Plane's scenery order, so "
    "X-Plane shows this tile instead. To show its ground, move this tile "
    "below it; this tile is then not shown.")


def warning_lines(reply: dict) -> list:
    """``[(kind, line, detail)]`` for the tile pane, ``kind`` being
    ``hidden_by`` or ``hides``; empty while all is well."""
    out = []
    hidden_by = list(reply.get("hidden_by") or [])
    hides = list(reply.get("hides") or [])
    if hidden_by:
        out.append(("hidden_by", "Hidden in X-Plane by " + _names(hidden_by),
                    HIDDEN_BY_DETAIL))
    if hides:
        out.append(("hides", "Hides the ground of " + _names(hides),
                    HIDES_DETAIL))
    return out


def degraded_rows(custom_scenery_dir: str, lat: int, lon: int,
                  build_dir: str) -> list:
    """The build's closing warnings for the tile (``O4_Tile_Failures.
    from_degraded`` rows): one per pack named."""
    try:
        reply = tile_mesh_order(custom_scenery_dir, lat, lon, build_dir)
    except Exception:                                  # never ends a build
        return []
    return ([{"code": "scenery_hidden_by_mesh", "pack": name}
             for name in reply["hidden_by"]]
            + [{"code": "scenery_hides_mesh", "pack": name}
               for name in reply["hides"]])
