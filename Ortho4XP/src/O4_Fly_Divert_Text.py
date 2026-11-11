"""The Fly pane's diversion, reload and offline words and the airport
search of "Divert…" (spec flight-manager-and-world-20261110 §4.3 steps
7-8, §7.5 S6 (b), §11; RULINGS 2026-11-10k Q3/Q4; lane F2).

Pure: no Qt, no engine, no I/O.  The Qt pane (``O4_Qt_Fly_Pane``) reads
it; the Mac app's ``Sources/SceneryKit/FlyDivertText.swift`` holds the
same words and rules, held equal by ``tests/test_fly_pane.py`` and the
shared fixture ``tests/fixtures/fly_pane_cases.json``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

__all__ = [
    "DIVERT_TITLE", "DIVERT_SEARCH", "DIVERT_ALTERNATE", "DIVERT_BUTTON",
    "RELOAD_NOW", "NOT_NOW", "WAIVE_OFFLINE", "SEARCH_LIMIT",
    "divert_matches", "divert_row_label", "reload_line", "waiver_line",
]

DIVERT_TITLE = "Divert to"
DIVERT_SEARCH = "Airport code or name"
DIVERT_ALTERNATE = "The plan's alternate"
DIVERT_BUTTON = "Divert"
RELOAD_NOW = "Reload scenery now"
NOT_NOW = "Not now"
WAIVE_OFFLINE = "Fly with X-Plane's own scenery there"
#: Rows the airport search shows at most.
SEARCH_LIMIT = 12


def divert_matches(query: str, airports: Sequence[Sequence[Any]],
                   limit: int = SEARCH_LIMIT) -> List[list]:
    """The airport search: ``airports`` rows ``[ident, name, lat, lon]``;
    the exact code first, then codes starting with the query, then names
    containing it, each group by code; at most ``limit``."""
    q = (query or "").strip().upper()
    if not q:
        return []
    exact, prefix, named = [], [], []
    for row in airports:
        ident, name = str(row[0]).upper(), str(row[1] or "").upper()
        if ident == q:
            exact.append(list(row))
        elif ident.startswith(q):
            prefix.append(list(row))
        elif q in name:
            named.append(list(row))

    def key(row: list) -> str:
        return str(row[0]).upper()
    return (sorted(exact, key=key) + sorted(prefix, key=key)
            + sorted(named, key=key))[:max(0, int(limit))]


def divert_row_label(row: Sequence[Any]) -> str:
    """"CYQX · Gander International", or the code alone."""
    ident, name = str(row[0]).upper(), str(row[1] or "").strip()
    return "%s · %s" % (ident, name) if name else ident


def _place(status: Dict[str, Any]) -> str:
    return status.get("diverted_to") or "the destination"


def reload_line(status: Optional[Dict[str, Any]]) -> str:
    """The reload in the air (S6 (b)), one line; empty when none waits."""
    state = (status or {}).get("reload") or ""
    if state == "scheduled":
        return "Scenery for %s reloads in 30 s." % _place(status)
    if state == "offered":
        return "Scenery for %s is ready: reload when you choose." % _place(status)
    return ""


def waiver_line(status: Optional[Dict[str, Any]]) -> str:
    """The offline waiver's line (Q3); empty when nothing can be waived."""
    count = len((status or {}).get("waivable") or ())
    if not count:
        return ""
    return "%d tile(s) en route need the internet." % count
