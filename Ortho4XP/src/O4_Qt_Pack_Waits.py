"""The pack commands pressed that the engine has not answered yet (#2200).

Owner 2026-11-20: "an active dialog should take precedence over any
builds".  Pack choices… shows "Checking packs…" (the button disabled)
from the press until the tile's ``PackOverlaps`` event arrives; Apply
says on the console that the answer is being applied and the outcome
arrives as one line; a Modified-airports row button pressed again while
its pack's answer is pending is ignored, and a refusal is one line.

Parity with the mac app: ``Sources/XPTerrainBuilder/PackCommandWaits.swift``
(``PackCommandWaits``, ``PackWaitCopy``) — the copy below is VERBATIM
and ``tests/test_qt_pack_waits.py`` reads the Swift file to pin it.
Toolkit-free: the window owns the widgets.
"""
from __future__ import annotations

import os

import O4_File_Names as FNAMES

__all__ = ["CHECKING", "PackWaits", "overlaps_key", "pack_key", "checking_line",
           "applying_line", "outcome_line", "refused_line", "refusal"]

CHECKING = "Checking packs…"


def checking_line(tile: str) -> str:
    return f"Pack choices: reading the packs on {tile}…"


def applying_line(tile: str) -> str:
    return f"Pack choices: applying your answer on {tile}…"


def _applied_line(tile: str, files: int) -> str:
    if files == 0:
        return f"Pack choices on {tile}: applied (no pack needed rewriting)."
    return (f"Pack choices on {tile}: applied ({files} pack DSF"
            f"{'' if files == 1 else 's'} rewritten).")


def _failed_line(tile: str, error: str) -> str:
    return f"Pack choices on {tile}: could not be applied ({error})."


def refused_line(reason: str) -> str:
    return f"The engine refused the pack command: {reason}"


def outcome_line(event) -> str:
    """The console line of a ``PackOverlaps`` answer's outcome, ``""`` for
    a question."""
    tile = FNAMES.short_latlon(int(event.lat), int(event.lon))
    state = getattr(event, "state", "")
    if state in ("chosen", "undone"):
        return _applied_line(tile, len(getattr(event, "files", None) or ()))
    if state == "failed":
        return _failed_line(tile, getattr(event, "error", ""))
    return ""


def refusal(reply) -> str:
    """A command reply's refusal reason, ``""`` when it was taken."""
    if isinstance(reply, dict) and reply.get("status") == "refused":
        return str(reply.get("reason") or "refused")
    return ""


def overlaps_key(lat: int, lon: int) -> str:
    return "overlaps|" + FNAMES.short_latlon(int(lat), int(lon))


def pack_key(pack_path: str) -> str:
    return "pack|" + os.path.basename(os.path.normpath(pack_path or ""))


class PackWaits:
    """The keys still waiting (:func:`overlaps_key` / :func:`pack_key`)."""

    def __init__(self) -> None:
        self.keys: set[str] = set()

    def start(self, key: str) -> bool:
        """Start the wait; ``False`` when it was already waiting."""
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    def end(self, key: str) -> None:
        self.keys.discard(key)

    def waiting(self, key: str) -> bool:
        return key in self.keys
