"""The words of a tile's World state in both apps (#2024): the Build map's
legend and the Library's World column.

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
           "SOURCE_WORDS", "LEAN_ON_DRIVE", "ON_DRIVE", "cell_text"]

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
