"""The Qt Settings window's selection behaviour (#1549, RULINGS 2026-10-28i/j).

A mixin of :class:`O4_Qt_Settings.SettingsWindow`: what the selected
tiles add up to (one value, or :data:`O4_Settings_Selection.CONFLICT`),
the confirmation a change asks for while they disagree, the detail level
the selection shows, and the preset cards' view of the selection.  The
rule itself is :mod:`O4_Settings_Selection` (the Mac app's
``SettingsSelection.swift``); this module is the Qt presentation of it.

The window it mixes into owns ``tiles``, ``prefs``, ``_global_vals``,
``_overrides_by_tile``, ``rows``, ``detail_combo`` and ``preset_cards``.
"""

import O4_File_Names as FNAMES
import O4_Settings_Model as SM
import O4_Settings_Presets as PRESETS
import O4_Settings_Selection as SEL
from PySide6.QtWidgets import QMessageBox

__all__ = ["SelectionEdits"]


class SelectionEdits:
    """Selection-aware reads and confirmations for the Settings window."""

    def _init_selection(self, tile_zooms, selection_zl):
        #: Each selected tile's recorded detail level (None: never built).
        self._tile_zooms = dict(tile_zooms or {})
        #: The detail level chosen for this selection (session only, the
        #: next build of these tiles uses it); None: the recorded ones.
        self.selection_zl = selection_zl
        #: Where a detail-level choice made here went: "defaults" (no
        #: selection: the zoom for new tiles), "tiles", or None.
        self.zoom_target = None

    # -- what the selection shows ---------------------------------------
    def _default_zl(self):
        return int(self.prefs.get(PRESETS.ZOOM_PREF, PRESETS.default_zoom()))

    def _tile_merged(self, name):
        """The selected tiles' value of one tile setting, or CONFLICT."""
        return SEL.tile_value(
            self._overrides_by_tile.values(), name, self._global_vals[name],
            same=lambda a, b: SM.values_equivalent(name, str(a), str(b)))

    def _selection_zoom(self):
        """The detail level the window shows: the default with no
        selection, else the selection's (a choice made here first)."""
        if not self.tiles:
            return self._default_zl()
        if self.selection_zl is not None:
            return int(self.selection_zl)
        return SEL.selection_zoom(
            (self._tile_zooms.get(tuple(tile)) for tile in self.tiles),
            self._default_zl())

    def _selection_conflicts(self):
        """Whether the selected tiles disagree on any per-tile setting."""
        if len(self.tiles) < 2:
            return False
        if self._selection_zoom() is SEL.CONFLICT:
            return True
        return SEL.any_conflict(
            self._tile_merged(setting.name) for setting in SM.settings()
            if setting.scope == "tile")

    def _confirm_selection_change(self):
        """Ask before a change lands on tiles that disagree (28i)."""
        if not self._selection_conflicts():
            return True
        answer = QMessageBox.question(
            self, SEL.CONFIRM_TITLE, SEL.confirm_text(len(self.tiles)))
        return answer == QMessageBox.Yes

    def _scope_text(self):
        return SEL.scope_text(
            [FNAMES.short_latlon(*tile) for tile in self.tiles],
            self._selection_conflicts())

    # -- the detail level -----------------------------------------------
    def _show_selection_zoom(self):
        zoom = self._selection_zoom()
        self.detail_combo.blockSignals(True)
        if zoom is SEL.CONFLICT:
            self.detail_combo.setPlaceholderText(SEL.CONFLICT_TEXT)
            self.detail_combo.setCurrentIndex(-1)
            self.detail_combo.setToolTip(
                SEL.CONFLICT_TEXT + ": the selected tiles use different "
                "detail levels.")
        else:
            self.detail_combo.setCurrentText(str(zoom))
        self.detail_combo.blockSignals(False)

    def _choose_zoom(self, zoomlevel):
        """A detail level chosen here: the selection's, or the default
        for new tiles when nothing is selected (28j 3)."""
        self.zoom_chosen = True
        if self.tiles:
            self.selection_zl = int(zoomlevel)
            self.zoom_target = "tiles"
        else:
            self.prefs[PRESETS.ZOOM_PREF] = int(zoomlevel)
            self.zoom_target = "defaults"

    # -- the preset cards -----------------------------------------------
    def _selection_preset_current(self):
        """The preset keys' values for the selection; a conflicting key
        matches no card."""
        current = {PRESETS.ZOOM_PREF: self._selection_zoom()}
        for name in PRESETS.PRESET_KEYS[1:]:
            current[name] = self._tile_merged(name)
        return SEL.preset_values(current)
