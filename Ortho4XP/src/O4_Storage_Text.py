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
           "BUDGET_FIELD", "BUDGET_USE_DEFAULT",
           "BUDGET_HELD", "BUDGET_CONFIRM", "DOWNGRADE_TITLE",
           "DOWNGRADE_TEXT", "DOWNGRADE_FLOOR", "DOWNGRADE_OK", "CACHES_TITLE",
           "CACHES_CLEAR", "CACHES_DETAILS", "CACHES_DETAILS_TITLE",
           "CLEAR_ALL_TITLE", "CLEAR_ALL_TEXT", "FOLDER_TITLE",
           "TIERS_TITLE", "TIERS_HELP", "TIERS_NONE", "TIERS_ABSENT",
           "TIERS_USED",
           "ONDEMAND_FLOOR_WARNING", "INSTALLED_TITLE", "INSTALLED_LOCAL",
           "INSTALLED_LINKED", "INSTALLED_UNMOUNTED", "INSTALLED_NONE",
           "INSTALLED_HELP", "WORLD_FOREIGN", "WORLD_PACK_MISSING",
           "size_text", "budget_lines", "installed_lines",
           "ondemand_warning", "cleanup_warning",
           "held_line", "needs_downgrade", "downgrade_text",
           "clear_all_text", "BUDGET_MIN_END", "BUDGET_MAX_END",
           "BUDGET_CLAMPED", "BUDGET_FOLLOWED", "BAR_PLACEHOLDERS",
           "BAR_TILES", "BAR_CACHES",
           "BAR_PACKAGES", "BAR_OTHER", "BAR_LEGEND", "PREVIEW_FITS",
           "PREVIEW_CLEARS", "PREVIEW_THEN", "PREVIEW_CACHES",
           "PREVIEW_IMAGERY", "PREVIEW_AIRPORTS", "PREVIEW_FAVORITES",
           "PREVIEW_REBUILD", "PREVIEW_AIRPORTS_KEPT", "end_labels",
           "range_notice", "bar_parts", "preview_text"]

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
BUDGET_FIELD = "Budget (GB)"
BUDGET_USE_DEFAULT = "Use Default"
#: Unconfirmed (RULINGS 2026-11-11h (1)): the default is sized to the
#: current install; Confirm records it as the budget.
BUDGET_HELD = ("Until you confirm a budget, the default holds everything "
               "installed now ({held}), so nothing is cleared. Confirm it or "
               "set your own.")
BUDGET_CONFIRM = "Confirm"
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
#: Settings ▸ Storage ▸ Storage tiers (RULINGS 2026-11-12g,
#: ``o4_engine.storage_tiers``): one row per other drive.
TIERS_TITLE = "Storage tiers"
TIERS_HELP = ("Sharp imagery the disk budget makes low res again moves to a "
              "drive with a size here, and comes back from it while the drive "
              "is connected. Without the drive it is downloaded again. 0 GB: "
              "not used.")
TIERS_NONE = "No other drive is connected."
TIERS_ABSENT = "Not connected: its imagery is downloaded again."
TIERS_USED = "{used} used, {free} free"
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

#: The slider's ends (#2022, owner 2026-11-12): plain words, measured.
BUDGET_MIN_END = ("Minimum: what's always kept — world placeholders and "
                  "your airport packages ({bytes})")
BUDGET_MAX_END = "Most: as much as fits while keeping 50 GB free ({bytes})"
#: A budget set outside the slider's range (``storage_range.clamp``).
BUDGET_CLAMPED = ("Your budget of {chosen} is below what is always kept, so "
                  "{budget} applies.")
BUDGET_FOLLOWED = ("Your budget of {chosen} no longer fits on this disk with "
                   "50 GB free, so it follows the disk down to {budget}.")
#: The stacked usage bar's legend, left to right (``storage_range.BAR_PARTS``).
BAR_PLACEHOLDERS = "World placeholders"
BAR_TILES = "Tiles and mesh"
BAR_PACKAGES = "Packages"
#: The Caches line's figure, the same bytes (owner 2026-11-12).
BAR_CACHES = "Caches"
BAR_OTHER = "Patches and other files"
BAR_LEGEND = "{label} {bytes}"
#: The line under the slider while it moves: what a clearing at that
#: budget would do (``storage_range.ladder``, cheapest first).
PREVIEW_FITS = "Nothing is cleared: the {used} in use fits."
PREVIEW_CLEARS = "Frees about {free}: {steps}."
PREVIEW_THEN = ", then "
PREVIEW_CACHES = "caches go first"
PREVIEW_IMAGERY = "distant imagery goes back to low res"
PREVIEW_AIRPORTS = "airport imagery goes back to low res"
PREVIEW_FAVORITES = "favorites go back to low res"
PREVIEW_REBUILD = "older airport tiles become packages"
PREVIEW_AIRPORTS_KEPT = " Airports keep full resolution."

#: ``(budget key, legend)`` of the bar, left to right.
_BAR = (("placeholders", BAR_PLACEHOLDERS), ("tiles", BAR_TILES),
        ("packages", BAR_PACKAGES), ("caches", BAR_CACHES),
        ("other", BAR_OTHER))
#: ``(ladder step, words)`` in the order a clearing takes them.
_STEPS = (("caches", PREVIEW_CACHES), ("imagery", PREVIEW_IMAGERY),
          ("airport_imagery", PREVIEW_AIRPORTS),
          ("favorites", PREVIEW_FAVORITES), ("rebuild", PREVIEW_REBUILD))


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


def held_line(budget: Mapping) -> str:
    """Unconfirmed: the default holds the current install (RULINGS
    2026-11-11h (1)) and the invitation to confirm it; else ""."""
    if budget.get("budget_set", True):
        return ""
    return BUDGET_HELD.format(held=size_text(budget.get("held_bytes")))


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

#: The World folder that is not the app's own (``world_commands._foreign_target``):
#: onboarding offers nothing, Convert existing tiles refuses with this.
WORLD_FOREIGN = ("Your World folder is a link to {target}, not a folder "
                 "XPTerrainBuilder made. Remove the link or restore it before "
                 "converting tiles.")
#: Converted tiles the World pack lacks (``world_migrate.missing_from_pack``):
#: the result of a run and the World pack's status say so, Undo is the way back.
WORLD_PACK_MISSING = ("{count} tiles that Convert existing tiles moved are "
                      "missing from the World pack (was its folder moved or "
                      "deleted?). Undo… in Convert existing tiles puts them "
                      "back in their own packs.")


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


def end_labels(budget: Mapping) -> Tuple[str, str]:
    """The slider's two end labels, with the measured figures."""
    return (BUDGET_MIN_END.format(bytes=size_text(budget.get("minimum_bytes"))),
            BUDGET_MAX_END.format(bytes=size_text(budget.get("maximum_bytes"))))


def range_notice(budget: Mapping) -> str:
    """The notice of a budget set outside the range (raised to the
    minimum, or followed down to the disk's maximum); else ""."""
    template = {"minimum": BUDGET_CLAMPED,
                "followed": BUDGET_FOLLOWED}.get(budget.get("clamped") or "")
    if not template:
        return ""
    return template.format(chosen=size_text(budget.get("chosen_bytes")),
                           budget=size_text(budget.get("budget_bytes")))


def bar_parts(budget: Mapping) -> List[Tuple[str, int, str]]:
    """``(key, bytes, legend)`` of the stacked bar, left to right."""
    parts = budget.get("breakdown") or {}
    out = []
    for key, label in _BAR:
        nbytes = int(parts.get(key) or 0)
        out.append((key, nbytes, BAR_LEGEND.format(label=label,
                                                   bytes=size_text(nbytes))))
    return out


def preview_text(budget: Mapping, new_bytes: int) -> str:
    """What the sweep would do at a budget of ``new_bytes``, in one
    sentence: the steps of the budget's ``ladder`` a clearing down to
    ``low_water`` of it reaches, cheapest first."""
    used = int(budget.get("used_bytes") or 0)
    if int(new_bytes) >= used:
        return PREVIEW_FITS.format(used=size_text(used))
    over = used - int(float(budget.get("low_water") or 0.9) * int(new_bytes))
    ladder = budget.get("ladder") or {}
    steps, left = [], over
    for step, words in _STEPS:
        nbytes = int(ladder.get(step) or 0)
        if left <= 0:
            break
        if nbytes > 0:
            steps.append(step)
            left -= nbytes
    words = dict(_STEPS)
    text = PREVIEW_CLEARS.format(
        free=size_text(over),
        steps=PREVIEW_THEN.join(words[s] for s in steps) or PREVIEW_CACHES)
    if "airport_imagery" not in steps:
        text += PREVIEW_AIRPORTS_KEPT
    return text
