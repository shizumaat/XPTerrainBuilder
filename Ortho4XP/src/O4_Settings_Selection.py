"""What the Settings window shows for the map selection (#1549).

Owner rulings RULINGS 2026-10-28i and 28j, in one rule both apps read
(the Mac app mirrors it in ``Sources/SceneryKit/SettingsSelection.swift``;
``tests/test_settings_selection.py`` holds the two to the same words):

* No tile selected: the window shows the global defaults, and an edit
  changes the defaults for NEW tiles only (28j 3).
* One tile, or several that agree: the window shows their value, and an
  edit applies to every selected tile.
* Several tiles that disagree on a setting: that control shows
  :data:`CONFLICT_TEXT`, and any per-tile change asks
  (:func:`confirm_text`) before it applies to all of them.
* A never-built tile counts as having the current global defaults (28j 2):
  a tile with no saved value for a setting inherits the global one.
* Only the per-tile build settings follow the selection (zoom, cover,
  imagery, airport options); app-wide settings stay global (28j 1) —
  :func:`edits_tiles`.
* The preset cards compare the selection's values
  (:func:`preset_values`): a conflicting key matches no preset.

The values come from where each app already reads them (the tile cfg's
sparse overrides through ``O4_Settings_Model``, the tile's recorded zoom);
this module only decides what they add up to.  Nothing a build step
imports may import it.
"""

from __future__ import annotations

__all__ = [
    "CONFLICT", "CONFLICT_TEXT", "CONFIRM_TITLE", "CONFIRM_BUTTON",
    "TILES_NOTE", "tile_value", "selection_zoom", "edits_tiles",
    "any_conflict", "preset_values", "scope_text", "confirm_text",
]


class _Conflict:
    """The selected tiles disagree: there is no one value to show."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "CONFLICT"


#: The merged value of a setting the selected tiles disagree on.
CONFLICT = _Conflict()

#: The words both apps show (SettingsSelection.swift has the same ones).
CONFLICT_TEXT = "Conflicting values"
CONFIRM_TITLE = "Apply to all selected tiles?"
CONFIRM_BUTTON = "Apply to All"
#: The preset cards' note while tiles are selected (the defaults' note is
#: ``O4_Settings_Presets.SECTION_NOTE``).
TILES_NOTE = "Applies to the selected tiles. With no tile selected it sets the defaults for new tiles."


def merge(values, same=None):
    """One value for the selection: the shared value, :data:`CONFLICT`
    when two differ, ``None`` for an empty selection.  *same* compares two
    values (default ``==``)."""
    same = same or (lambda a, b: a == b)
    values = list(values)
    if not values:
        return None
    first = values[0]
    for value in values[1:]:
        if not same(first, value):
            return CONFLICT
    return first


def tile_value(overrides_by_tile, name, inherited, same=None):
    """The selection's value of one tile setting.

    :param overrides_by_tile: one ``{name: value}`` per selected tile —
        the tile's own saved values; a never-built tile has none.
    :param inherited: the global effective value (what a tile without its
        own value uses, 28j 2).
    """
    return merge((overrides.get(name, inherited)
                  for overrides in overrides_by_tile), same)


def selection_zoom(recorded, default):
    """The selection's detail level: each tile's recorded zoom, a tile
    without one (never built) the default.  An empty selection is the
    default itself."""
    recorded = list(recorded)
    if not recorded:
        return int(default)
    return merge(int(default) if zl is None else int(zl) for zl in recorded)


def edits_tiles(scope, tile_count):
    """Whether an edit of a setting of *scope* writes the selected tiles
    (``"tile"`` with a selection) rather than the global layer."""
    return scope == "tile" and tile_count > 0


def any_conflict(values):
    """Whether any merged value of *values* (an iterable) is a conflict."""
    return any(value is CONFLICT for value in values)


def preset_values(current):
    """*current* (preset key -> merged value) as the preset cards compare
    it: a conflicting key becomes ``""``, which matches no preset."""
    return {name: ("" if value is CONFLICT else str(value))
            for name, value in current.items()}


def scope_text(tile_names, conflicting=False):
    """What the window is editing: the defaults, a tile, or N tiles."""
    if not tile_names:
        return "Editing the global defaults for new tiles"
    if len(tile_names) == 1:
        text = "Editing tile %s" % tile_names[0]
    else:
        text = "Editing %d tiles" % len(tile_names)
    return text + (" · " + CONFLICT_TEXT.lower() if conflicting else "")


def confirm_text(tile_count):
    """The confirmation a change asks for when the tiles disagree."""
    return ("The %d selected tiles have different settings. "
            "Apply this change to all of them?" % tile_count)
