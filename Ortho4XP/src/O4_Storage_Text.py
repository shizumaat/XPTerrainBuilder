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
           "BUDGET_DEFAULT", "BUDGET_FIELD", "BUDGET_SET", "BUDGET_USE_DEFAULT",
           "BUDGET_OVER_DEFAULT", "BUDGET_FIT", "DOWNGRADE_TITLE",
           "DOWNGRADE_TEXT", "DOWNGRADE_FLOOR", "DOWNGRADE_OK", "CACHES_TITLE",
           "CACHES_CLEAR", "CACHES_DETAILS", "CACHES_DETAILS_TITLE",
           "CLEAR_ALL_TITLE", "CLEAR_ALL_TEXT", "FOLDER_TITLE",
           "ONDEMAND_FLOOR_WARNING", "INSTALLED_TITLE", "INSTALLED_LOCAL",
           "INSTALLED_LINKED", "INSTALLED_UNMOUNTED", "INSTALLED_NONE",
           "INSTALLED_HELP", "size_text", "budget_lines", "installed_lines",
           "ondemand_warning", "cleanup_warning", "default_line",
           "over_default_line", "needs_downgrade", "downgrade_text",
           "clear_all_text"]

#: The help of the "Caches" and "Your tiles and patches" rows.
CACHES_HELP = ("Files in the app's own data folder that builds download or "
               "rebuild. Tiles installed in X-Plane are not counted here.")
KEPT_HELP = ("The built tiles, patches, overlays and elevation files inside "
             "the app's own data folder only. Tiles installed elsewhere are "
             "in Installed ortho tiles.")
BUDGET_TITLE = "Disk budget"
BUDGET_LINE = ("Using {used} of {budget}; {floor} is never cleared. "
               "Recommended at least {recommended}.")
BUDGET_UNSET = ("Using {used} of the default {budget}; {floor} is never "
                "cleared.")
BUDGET_UNDER_FLOOR = ("The budget is below what is never cleared ({floor}). "
                      "Raise it to at least {recommended}.")
BUDGET_HELP = ("More space keeps downloads and rebuild data, so tiles rebuild "
               "in minutes instead of re-downloading. Never cleared: your built tiles' scenery files and low-res "
               "imagery, your airport patches and your own elevation files. "
               "The recommended minimum adds room to work: half of that, at "
               "least 50 GB. Over the budget, what is cheapest to rebuild "
               "goes first, oldest first; favorites go last.")
#: Library > Disk budget (RULINGS 2026-11-11a): the default when none is
#: set is the larger of 200 GB and the recommended minimum.
BUDGET_DEFAULT = "Default {base} · recommended {recommended}"
BUDGET_FIELD = "Budget (GB)"
BUDGET_SET = "Set"
BUDGET_USE_DEFAULT = "Use Default"
BUDGET_OVER_DEFAULT = ("Over the default budget by {over}. Nothing is "
                       "cleared until you set a budget or fit this one.")
BUDGET_FIT = "Fit to Budget…"
#: A budget lowered below what is in use (owner 2026-11-11): asked first.
DOWNGRADE_TITLE = "Downgrade scenery to low res to fit the new budget?"
DOWNGRADE_TEXT = ("{used} is in use and the budget is {budget}: about {free} "
                  "is cleared to fit. Caches go first, then the oldest sharp "
                  "imagery is made low res (favorites last). Your tiles and "
                  "patches stay.")
DOWNGRADE_FLOOR = (" Even at low res your tiles need {floor}, more than this "
                   "budget.")
DOWNGRADE_OK = "Downgrade"
#: The Caches line (one total, Clear, Details; the list in its own window).
CACHES_TITLE = "Caches"
CACHES_CLEAR = "Clear…"
CACHES_DETAILS = "Details…"
CACHES_DETAILS_TITLE = "Storage Details"
CLEAR_ALL_TITLE = "Clear every cache?"
CLEAR_ALL_TEXT = ("This frees up to {bytes}. Downloads come back when a build "
                  "needs them; sharp imagery is made low res, never deleted. "
                  "Built tiles and patches stay.")
FOLDER_TITLE = "Data folder"
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
    chosen = budget.get("budget_set", bool(budget.get("budget_bytes")))
    line = BUDGET_LINE if chosen else BUDGET_UNSET
    warning = BUDGET_UNDER_FLOOR if budget.get("under_floor") else ""
    return line.format(**values), warning.format(**values)


def default_line(budget: Mapping) -> str:
    """"Default 200 GB · recommended N" (RULINGS 2026-11-11a)."""
    return BUDGET_DEFAULT.format(base=size_text(budget.get("default_base_bytes")),
                                 recommended=size_text(budget.get("recommended_bytes")))


def over_default_line(budget: Mapping) -> str:
    """With no budget set and more in use than the default: the line
    that says nothing is cleared until the user chooses; else ""."""
    if budget.get("budget_set", True) or not budget.get("over_budget"):
        return ""
    over = int(budget.get("used_bytes") or 0) - int(budget.get("budget_bytes") or 0)
    return BUDGET_OVER_DEFAULT.format(over=size_text(over))


def needs_downgrade(budget: Mapping, new_bytes: int) -> bool:
    """A budget of ``new_bytes`` is below what is in use: ask first."""
    return int(new_bytes) < int(budget.get("used_bytes") or 0)


def downgrade_text(budget: Mapping, new_bytes: int) -> str:
    """The confirmation of a budget below what is in use, with the bytes
    a clearing frees (down to ``low_water`` of the budget)."""
    used = int(budget.get("used_bytes") or 0)
    low = float(budget.get("low_water") or 0.9)
    floor = int(budget.get("floor_bytes") or 0)
    text = DOWNGRADE_TEXT.format(used=size_text(used), budget=size_text(new_bytes),
                                 free=size_text(max(0, used - int(low * new_bytes))))
    if new_bytes < floor:
        text += DOWNGRADE_FLOOR.format(floor=size_text(floor))
    return text


def clear_all_text(cache_bytes) -> str:
    """The Caches line's Clear… confirmation."""
    return CLEAR_ALL_TEXT.format(bytes=size_text(cache_bytes))


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
