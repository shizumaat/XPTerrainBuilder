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
           "LEGEND_OTHER_TOOL", "LEGEND_CUSTOM_PATCH",
           "COLUMN_TITLE", "STATE_WORDS", "MESH_WORDS", "ORIGIN_WORDS",
           "SOURCE_WORDS", "LEAN_ON_DRIVE", "ON_DRIVE", "cell_text",
           "PANE_ROW_TITLE", "PANE_BUILT", "PANE_WHAT", "PANE_MESH",
           "PANE_PLACEHOLDER", "TITLE_IN_WORLD", "REBUILD_BUTTON",
           "REMOVE_BUTTON", "REMOVE_TITLE", "REMOVE_MESSAGE",
           "REMOVE_CONFIRM", "REMOVED", "REMOVED_NO_PACKAGE",
           "pane_status", "pane_detail", "built_in_world", "removed_note",
           "world_dsf", "PHOTO_WORDS", "photo_text",
           "LEGEND_OFF", "PANE_OFF", "USE_HERE", "USE_NOTES", "use_offered",
           "use_on", "use_note", "WAITING_NOTE", "RELOAD_NOTE", "waiting_note"]

# --- The map key's World-state sentences (``O4_Map_Key_Text``, #2031:
# the Build and Fly views say the same; another tool's tile is dotted,
# the custom-patch band orange) ---
LEGEND_FULL = "Full: mesh and sharp imagery"
LEGEND_MESH = "Mesh only: imagery sharpens in flight"
LEGEND_DRAPE = "Photo drape on X-Plane's mesh"
LEGEND_PLACEHOLDER = "Placeholder: built or draped in flight"
#: A tile the user turned XPTerrainBuilder off on (#2100): crossed out.
LEGEND_OFF = "Crossed out: XPTerrainBuilder turned off, X-Plane's own scenery"
LEGEND_OTHER_TOOL = "Dotted: a tile another tool built"
#: The orange band (#1229) the owner asked about (2026-11-12, "gold").
LEGEND_CUSTOM_PATCH = "Orange band: custom airport patch, no auto patch"

# --- The Library's World column (a tile with no build, World state
# "nothing", says nothing: RULINGS 2026-11-13a) ---
COLUMN_TITLE = "World"
STATE_WORDS = {
    "full": "Full",
    "drape": "Drape",
    "placeholder": "Placeholder",
    "off": "Off",
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
#: The photo provider that draws a World tile (#2018): the tile pane's
#: detail and the map's cursor readout.
PHOTO_WORDS = "photo: {provider}"
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
PANE_OFF = ("XPTerrainBuilder is off here: X-Plane shows its own scenery "
            "(the built tile is kept)")
#: The tile title's suffix where the Tiles folder holds no build but the
#: World pack holds the tile (in place of "(not built)").
TITLE_IN_WORLD = "(in the World pack)"
REBUILD_BUTTON = "Rebuild Tile"
REMOVE_BUTTON = "Remove from World Pack…"
REMOVE_TITLE = "Remove tile {tile} from the World pack?"
REMOVE_MESSAGE = ("Its package is written first (XPTerrainBuilder_packages), then the "
                  "tile is a placeholder again: X-Plane shows its own "
                  "scenery there until the tile is built again. Its original "
                  "folder (originals/) and its files on other drives are "
                  "never touched.")
REMOVE_CONFIRM = "Remove"
REMOVED = "Tile {tile} is a placeholder again; its package: {package}"
REMOVED_NO_PACKAGE = "Tile {tile} is a placeholder again; no package was written: {why}"

# --- The map's tile menu: "Use XPTerrainBuilder here" on or off (#2100,
# ``o4_engine.world_tile_use``; the note after each, by its reply's state) ---
USE_HERE = "Use XPTerrainBuilder here"
USE_NOTES = {
    "on": "XPTerrainBuilder is on again for tile {tile}.",
    "off": "XPTerrainBuilder is off for tile {tile}: X-Plane shows its own scenery there.",
    "turning_off": "Tile {tile} turns off once X-Plane lets go of it (fly away or quit X-Plane).",
    "turning_on": "Tile {tile} turns on once X-Plane lets go of it.",
}

# --- The tile pane's note on a built tile not yet in the pack, or in over
# the version X-Plane loaded (#2175, RULINGS 2026-11-19e; the engine's
# ``WorldTilesWaiting``) ---
WAITING_NOTE = "{tile} is waiting for X-Plane to finish loading it"
RELOAD_NOTE = ("{tile} is in the World pack; X-Plane shows it at its next "
               "load, or reload scenery now")

#: The states the pane calls built (a real tile in the World pack).
_BUILT_STATES = ("full", "mesh_lowres", "drape")


def built_in_world(world) -> bool:
    """Does the World pack hold a real tile (not a placeholder) here?
    ``world``: a ``WorldTile.fields()`` dict or ``None``."""
    return bool(world) and world.get("state") in _BUILT_STATES


def use_offered(world) -> bool:
    """Does the tile menu offer "Use XPTerrainBuilder here" (the World
    pack holds the tile: built, a placeholder or off)?  ``world``: a
    ``WorldTile.fields()`` dict or ``None``.  Mac:
    ``O4WorldStateText.useOffered``."""
    return bool(world) and world.get("state") not in ("", "nothing", None)


def use_on(world) -> bool:
    """Is the menu item checked (not turned off)?  Mac: ``useOn``."""
    return (world or {}).get("state") != "off"


def use_note(reply) -> str:
    """The note after ``world_tile_use`` (Mac: ``O4WorldTileUse.note``)."""
    words = USE_NOTES.get(reply.get("state", ""), "")
    return words.format(tile=reply.get("tile", ""))


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
    if state == "off":
        return PANE_OFF
    return PANE_PLACEHOLDER if state == "placeholder" else ""


def photo_text(world) -> str:
    """"photo: FRorth" -- the provider drawing a World tile (#2018);
    ``""`` when none is known.  ``world``: a ``WorldTile.fields()`` dict
    or ``None``.  Mac: ``O4WorldStateText.photoText``."""
    provider = (world or {}).get("provider") or ""
    return PHOTO_WORDS.format(provider=provider) if provider else ""


def pane_detail(world) -> str:
    """Who made it, its photo and where its own files live: "built here ·
    photo: BI · original folder kept"; ``""`` for none."""
    if not world:
        return ""
    parts = [ORIGIN_WORDS.get(world.get("origin", ""), ""), photo_text(world),
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


def waiting_note(tile: str, waiting, reload) -> str:
    """The tile pane's note for tile ``tile`` (``+41-088``) from a
    ``WorldTilesWaiting``'s ``waiting`` and ``reload`` names; ``""`` for
    none.  Mac: ``O4WorldStateText.waitingNote``."""
    if tile in tuple(waiting or ()):
        return WAITING_NOTE.format(tile=tile)
    if tile in tuple(reload or ()):
        return RELOAD_NOTE.format(tile=tile)
    return ""
