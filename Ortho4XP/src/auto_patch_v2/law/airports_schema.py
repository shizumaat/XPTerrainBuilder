"""THE LAW BY AIRPORT — which ruleset an identifier resolves to (owner
2026-08-02: :class:`Resolution` / :func:`resolve_ruleset`), a rule by
identifier CLASS, never by airport.

NO PER-AIRPORT TABLE EXISTS (owner RULINGS 2026-10-05e: an airport is a
test case, never the scope of a fix).  The one there was — ``airports.toml``
and its ``Affordances`` (RULINGS 2026-09-10ap: Law C's per-airport switch,
and a per-airport ``group_span_max_m`` no airport ever stated) — is
DELETED: Law C is read at every airport under spec §12h's general rule
(``airport/wall_mouth.py``), and the long span is the pack-wide
``[placement] group_span_max_m`` alone (RULINGS 2026-10-05g).

The schema lives beside ``model`` under the 1,000-line file law (the
``flat_site_schema`` / ``cutout_schema`` precedent); ``model`` re-exports
it, so every caller's import is unchanged.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Resolution", "resolve_ruleset"]


@_dc.dataclass(frozen=True)
class Resolution:
    """How an ICAO identifier selects its ruleset (owner 2026-08-02)."""

    default: str
    faa_first_letters: tuple[str, ...]
    faa_two_letter_prefixes: tuple[str, ...]


def resolve_ruleset(res: Resolution, icao: str | None) -> str:
    """Ruleset key for an ICAO identifier (owner 2026-08-02).  Empty or
    unparseable identifiers take the default."""
    code = str(icao or "").strip().upper()
    if not code:
        return res.default
    if code[0] in res.faa_first_letters:
        return "faa"
    if code[:2] in res.faa_two_letter_prefixes:
        return "faa"
    return res.default
