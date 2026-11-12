"""The words of a tile's World state in both apps (#2024): the Build map's
legend, the Library's World column and the tile pane's "World pack" row
(its status, and Rebuild / Export Package / Remove from World pack).

The Qt window (``O4_Qt_Map_Legend``, ``O4_Qt_Library``) reads them here;
the Mac app's mirror is ``Sources/SceneryKit/WorldStateText.swift``
(``O4WorldStateText``), and ``tests/test_world_state.py`` requires the
two to say the same.  The states, origins and sources are
``o4_engine.world_state``'s.

Pure: no Qt, no engine session.
"""
from __future__ import annotations

__all__ = ["LEGEND_FULL", "LEGEND_MESH", "LEGEND_DRAPE", "LEGEND_PLACEHOLDER",
           "LEGEND_NOTHING", "LEGEND_OTHER_TOOL", "LEGEND_CUSTOM_PATCH",
           "COLUMN_TITLE", "STATE_WORDS", "MESH_WORDS", "ORIGIN_WORDS",
           "SOURCE_WORDS", "LEAN_ON_DRIVE", "ON_DRIVE", "cell_text",
           "PANE_ROW_TITLE", "PANE_BUILT", "PANE_WHAT", "PANE_MESH",
           "PANE_PLACEHOLDER", "TITLE_IN_WORLD", "REBUILD_BUTTON",
           "REMOVE_BUTTON", "REMOVE_TITLE", "REMOVE_MESSAGE",
           "REMOVE_CONFIRM", "REMOVED", "REMOVED_NO_PACKAGE",
           "pane_status", "pane_detail", "built_in_world", "removed_note",
           "world_dsf"]

# --- The Build map's legend (one row per state on the map, then the
# dotted border of another tool's mesh and the custom-patch band) ---
LEGEND_FULL = "Full: mesh and sharp imagery"
LEGEND_MESH = "Mesh: imagery sharpens in flight"
LEGEND_DRAPE = "Photo drape on X-Plane's mesh"
LEGEND_PLACEHOLDER = "Placeholder: built or draped in flight"
LEGEND_NOTHING = "Unmarked: X-Plane's own scenery"
LEGEND_OTHER_TOOL = "Dotted: another tool's mesh"
#: The orange band (#1229) the owner asked about (2026-11-12, "gold").
LEGEND_CUSTOM_PATCH = "Orange band: custom airport patch, no auto patch"

# --- The Library's World column ---
COLUMN_TITLE = "World"
STATE_WORDS = {
    "full": "Full",
    "drape": "Drape",
    "placeholder": "Placeholder",
    "nothing": "Nothing",
}
#: A mesh whose imagery streams: ``{percent}`` of its textures sharp.
MESH_WORDS = "Mesh, {percent}% sharp"
ORIGIN_WORDS = {
    "xptb": "built here",
    "adopted": "adopted",
    "other": "another tool's",
}
SOURCE_WORDS = {
    "originals": "original folder kept",
    "lean": "low-res copy here",
}
ON_DRIVE = "on {volume}"
LEAN_ON_DRIVE = "low-res copy here, full imagery on {volume}"


# --- The tile pane's "World pack" row (owner 2026-11-12T20:23Z: a tile
# fully built in the World pack must not read "not built") ---
PANE_ROW_TITLE = "World pack"
PANE_BUILT = "Built (in the World pack): {what}"
PANE_WHAT = {
    "full": "mesh + full imagery",
    "drape": "photo drape",
}
PANE_MESH = "mesh, {percent}% sharp"
PANE_PLACEHOLDER = "Placeholder in the World pack: not built yet"
#: The tile title's suffix where the Tiles folder holds no build but the
#: World pack holds the tile (in place of "(not built)").
TITLE_IN_WORLD = "(in the World pack)"
REBUILD_BUTTON = "Rebuild Tile"
REMOVE_BUTTON = "Remove from World Pack…"
REMOVE_TITLE = "Remove tile {tile} from the World pack?"
REMOVE_MESSAGE = ("Its package is written first (Tile_packages), then the "
                  "tile is a placeholder again: X-Plane shows its own "
                  "scenery there until the tile is built again. Its original "
                  "folder (originals/) and its files on other drives are "
                  "never touched.")
REMOVE_CONFIRM = "Remove"
REMOVED = "Tile {tile} is a placeholder again; its package: {package}"
REMOVED_NO_PACKAGE = "Tile {tile} is a placeholder again; no package was written: {why}"

#: The states the pane calls built (a real tile in the World pack).
_BUILT_STATES = ("full", "mesh_lowres", "drape")


def built_in_world(world) -> bool:
    """Does the World pack hold a real tile (not a placeholder) here?
    ``world``: a ``WorldTile.fields()`` dict or ``None``."""
    return bool(world) and world.get("state") in _BUILT_STATES


def world_dsf(info, world) -> str:
    """What "Show in Finder" reveals in the World pack (#2027): the tile's
    DSF there (``WorldTile.dsf``) when its build folder holds no DSF of
    its own (an adopted or converted tile keeps only its records in
    Tiles/), else ``""`` (the build folder).  ``info``: the scan's
    ``TileInfo`` or ``None``; ``world``: a ``WorldTile`` or ``None``.
    Mac: ``O4WorldTile.revealDSF``."""
    dsf = getattr(world, "dsf", "") or ""
    if not dsf or (info is not None and getattr(info, "dsf_present", False)):
        return ""
    return dsf


def pane_status(world) -> str:
    """The pane's status line: "Built (in the World pack): mesh + full
    imagery" / "…: mesh, 40% sharp" / "…: photo drape", or the placeholder
    line; ``""`` when the World pack holds nothing of the tile."""
    state = (world or {}).get("state", "")
    if state == "mesh_lowres":
        what = PANE_MESH.format(percent=int(round(100 * float(world.get("sharp") or 0))))
        return PANE_BUILT.format(what=what)
    if state in PANE_WHAT:
        return PANE_BUILT.format(what=PANE_WHAT[state])
    return PANE_PLACEHOLDER if state == "placeholder" else ""


def pane_detail(world) -> str:
    """Who made it and where its own files live: "built here · original
    folder kept"; ``""`` for none."""
    if not world:
        return ""
    parts = [ORIGIN_WORDS.get(world.get("origin", ""), ""),
             _source_text(world.get("source", ""), world.get("volume", ""))]
    return " · ".join(p for p in parts if p)


def removed_note(reply) -> str:
    """The pane's note after ``world_tile_remove`` (Mac:
    ``O4WorldTileRemoved.note``)."""
    package = reply.get("package") or {}
    if package.get("path"):
        return REMOVED.format(tile=reply.get("tile", ""), package=package["path"])
    return REMOVED_NO_PACKAGE.format(tile=reply.get("tile", ""),
                                     why=package.get("why", ""))


def _source_text(source: str, volume: str) -> str:
    if source == "lean" and volume:
        return LEAN_ON_DRIVE.format(volume=volume)
    if source == "drive":
        return ON_DRIVE.format(volume=volume) if volume else ""
    return SOURCE_WORDS.get(source, "")


def cell_text(world) -> str:
    """The World column's cell of a Library row's ``world`` dict
    (``WorldTile.fields``): "Mesh, 12% sharp · adopted · low-res copy
    here, full imagery on <drive>"; ``""`` for none."""
    if not world:
        return ""
    state = world.get("state", "")
    if state == "mesh_lowres":
        head = MESH_WORDS.format(percent=int(round(100 * float(world.get("sharp") or 0))))
    else:
        head = STATE_WORDS.get(state, "")
    parts = [head, ORIGIN_WORDS.get(world.get("origin", ""), ""),
             _source_text(world.get("source", ""), world.get("volume", ""))]
    return " · ".join(p for p in parts if p)
