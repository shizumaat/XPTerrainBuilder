"""The two imagery menus of the Qt window, built from the engine's one
source list (#1345, ``O4_Imagery_Sources.imagery_sources``).

:func:`menu_entries` is pure and is the rule the Mac app follows too
(``ImageryMenu.entries`` in ``Sources/SceneryKit/ImagerySources.swift``);
``tests/test_imagery_menu_parity.py`` and ``ImagerySourcesTests.swift``
read the same fixture, so the two menus cannot drift:

* the Build box lists the sources a build may download; the map's
  picker lists them all;
* sections follow the list: "Combined", then each region (the Mac
  menus head them; the Qt combos keep them contiguous);
* an ``offline`` source (launch status check) is disabled and labelled
  "<name> (offline)", its reason the tooltip;
* in the map picker a source the map cannot draw is disabled, its
  reason the tooltip.

Item TEXT stays the source code for every selectable item, so the
window's ``currentText()`` / ``findText(code)`` reads are unchanged; the
code is also the item's data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from PySide6.QtCore import Qt

__all__ = ["apply_status", "fill_combo", "menu_entries", "offered_codes"]

#: The section of combined sources.
COMBINED_SECTION = "Combined"


def menu_entries(rows: List[Dict[str, Any]], statuses: Mapping[str, Tuple[str, str]],
                 for_map: bool) -> List[Dict[str, Any]]:
    """One entry per menu item: ``code``, ``label``, ``enabled``,
    ``tooltip`` and ``section``, in menu order."""
    entries = []
    for row in rows:
        if not for_map and not row.get("buildable", True):
            continue
        status, reason = statuses.get(row["code"], ("unknown", ""))
        label = row.get("name") or row["code"]
        enabled, tooltip = True, ""
        if status == "offline":
            label += " (offline)"
            enabled, tooltip = False, reason
        elif for_map and not row.get("previewable"):
            enabled, tooltip = False, row.get("reason", "")
        entries.append({
            "code": row["code"],
            "label": label,
            "enabled": enabled,
            "tooltip": tooltip,
            "section": COMBINED_SECTION if row.get("combined") else row.get("region", ""),
        })
    return entries


def _set_item(combo, index, entry):
    combo.setItemText(index, entry["label"] if not entry["enabled"] else entry["code"])
    combo.setItemData(index, entry["tooltip"] or None, Qt.ItemDataRole.ToolTipRole)
    item = combo.model().item(index)
    if item is not None:
        item.setEnabled(entry["enabled"])


def fill_combo(combo, entries: List[Dict[str, Any]]) -> None:
    """Refill ``combo`` with ``entries`` in order (sections stay
    contiguous; no separator items, so every item is a source), keeping
    the current code when it is still offered."""
    current = combo.currentData() or combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    for entry in entries:
        combo.addItem(entry["code"], entry["code"])
        _set_item(combo, combo.count() - 1, entry)
    if current:     # a first fill keeps Qt's own choice, the first item
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 and _enabled(combo, index) else -1)
    combo.blockSignals(False)


def _enabled(combo, index) -> bool:
    item = combo.model().item(index)
    return item is None or item.isEnabled()


def offered_codes(combo) -> List[str]:
    """The codes the user can pick (nothing disabled)."""
    codes = [combo.itemData(i) or combo.itemText(i) for i in range(combo.count())
             if _enabled(combo, i)]
    return [code for code in codes if code]


def apply_status(combo, entries: List[Dict[str, Any]]) -> None:
    """Update ``combo``'s items in place from fresh ``entries`` (a status
    landed): label, tooltip and enabled flag; the selection is kept."""
    by_code = {entry["code"]: entry for entry in entries}
    for index in range(combo.count()):
        entry = by_code.get(combo.itemData(index))
        if entry is not None:
            _set_item(combo, index, entry)
