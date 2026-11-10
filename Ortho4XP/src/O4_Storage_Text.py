"""The words of Settings > Storage's budget and installed-tiles lines in
both apps (RULINGS 2026-11-10d; owner feedback on 1.0.480).

The Qt window (``O4_Qt_Settings_Storage``) reads them here; the Mac
app's mirror is ``Sources/SceneryKit/StorageText.swift``
(``O4StorageText``), and ``tests/test_storage_text_parity.py`` requires
the two to say the same.  The engine's figures come from
``o4_engine.storage_budget.status`` and
``o4_engine.storage_installed.installed_tiles`` (``storage_scan``'s
``budget`` and ``installed``).

Pure: no Qt, no engine session.
"""
from __future__ import annotations

from typing import List, Mapping, Tuple

import O4_Imagery_OnDemand_Text as ONDEMAND_TEXT

__all__ = ["CACHES_HELP", "KEPT_HELP", "BUDGET_TITLE", "BUDGET_LINE",
           "BUDGET_UNSET", "BUDGET_UNDER_FLOOR", "BUDGET_HELP",
           "ONDEMAND_FLOOR_WARNING", "INSTALLED_TITLE", "INSTALLED_LOCAL",
           "INSTALLED_LINKED", "INSTALLED_UNMOUNTED", "INSTALLED_NONE",
           "INSTALLED_HELP", "size_text", "budget_lines", "installed_lines",
           "ondemand_warning", "cleanup_warning"]

#: The help of the "Caches" and "Your tiles and patches" rows.
CACHES_HELP = ("Files in the app's own data folder that builds download or "
               "rebuild. Tiles installed in X-Plane are not counted here.")
KEPT_HELP = ("The built tiles, patches, overlays and elevation files inside "
             "the app's own data folder only. Tiles installed elsewhere are "
             "in Installed ortho tiles.")
BUDGET_TITLE = "Disk budget"
BUDGET_LINE = ("Using {used} of {budget}; {floor} is never cleared. "
               "Recommended at least {recommended}.")
BUDGET_UNSET = ("No disk budget set: using {used}. Recommended at least "
                "{recommended} ({floor} is never cleared).")
BUDGET_UNDER_FLOOR = ("The budget is below what is never cleared ({floor}). "
                      "Raise it to at least {recommended}.")
BUDGET_HELP = ("Never cleared: your built tiles' scenery files and low-res "
               "imagery, your airport patches and your own elevation files. "
               "The recommended minimum adds room to work: half of that, at "
               "least 50 GB. Over the budget, what is cheapest to rebuild "
               "goes first, oldest first; favorites go last.")
#: The on-demand row with no disk budget set: its tiles do not fit the
#: sharp imagery limit even at low resolution.
ONDEMAND_FLOOR_WARNING = ("Your on-demand tiles need {floor} even at low "
                          "resolution, more than the {cap} limit.")
INSTALLED_TITLE = "Installed ortho tiles"
INSTALLED_LOCAL = "{count} folder(s) on this disk: {bytes}"
INSTALLED_LINKED = "{count} linked to {volume}{unmounted}, not measured"
INSTALLED_UNMOUNTED = " (not connected)"
INSTALLED_NONE = "Set the Custom Scenery folder to measure them."
INSTALLED_HELP = ("The zOrtho4XP_ entries of X-Plane's Custom Scenery folder. "
                  "Folders on this disk are measured; entries linked to "
                  "another drive are counted, not measured.")


#: ``12.3 MB`` / ``1.25 GB`` (decimal), the same in both apps.
size_text = ONDEMAND_TEXT.size_text


def budget_lines(budget: Mapping) -> Tuple[str, str]:
    """``(line, warning)`` of ``storage_scan``'s ``budget`` (the warning
    is "" unless the budget is under the floor)."""
    values = {"used": size_text(budget.get("used_bytes")),
              "budget": size_text(budget.get("budget_bytes")),
              "floor": size_text(budget.get("floor_bytes")),
              "recommended": size_text(budget.get("recommended_bytes"))}
    line = (BUDGET_LINE if budget.get("budget_bytes") else BUDGET_UNSET)
    warning = BUDGET_UNDER_FLOOR if budget.get("under_floor") else ""
    return line.format(**values), warning.format(**values)


def installed_lines(installed: Mapping) -> List[str]:
    """The lines of ``storage_scan``'s ``installed``."""
    if not installed.get("measured"):
        return [INSTALLED_NONE]
    lines = [INSTALLED_LOCAL.format(count=int(installed.get("local_count", 0)),
                                    bytes=size_text(installed.get("local_bytes")))]
    for group in installed.get("linked", ()):
        lines.append(INSTALLED_LINKED.format(
            count=int(group.get("count", 0)), volume=group.get("volume", ""),
            unmounted="" if group.get("mounted") else INSTALLED_UNMOUNTED))
    return lines


def ondemand_warning(store: Mapping) -> str:
    """The on-demand row's warning ("" unless ``over_at_floor``)."""
    if not store.get("over_at_floor"):
        return ""
    return ONDEMAND_FLOOR_WARNING.format(floor=size_text(store.get("floor_bytes")),
                                         cap=size_text(store.get("cap_bytes")))


def cleanup_warning(done: Mapping) -> str:
    """The warning after an automatic cleanup (``storage_auto_clean``'s
    reply; run after every build): the budget under the floor, else the
    on-demand tiles over the sharp imagery limit even low-res; ""."""
    budget = done.get("budget") or {}
    if budget.get("under_floor"):
        return budget_lines(budget)[1]
    return ondemand_warning(done.get("ondemand_floor") or {})
