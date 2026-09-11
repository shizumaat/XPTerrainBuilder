"""THE LAW BY AIRPORT — which ruleset an identifier resolves to (owner
2026-08-02: ``Resolution`` / ``resolve_ruleset``) and which opt-in laws
an airport affords (``airports.toml``; RULINGS 2026-09-10ap, closing
owner question 10ac-1 as (B)).

THE AFFORDANCES.

A law a PACK has to EARN by the owner's sim read of that airport — not a
mechanism, an honest switch.  Today's one key is LAW C (kerb-wall
corridors AND garage ramps, ``airport/wall_corridors.py``): after seven
rounds no witness in the geometry or the map separated OTHH's terminal
kerb corridors from LEMD's cargo-dock foundations, so the law is read
only where an airport's table turns it on.  Law A (door wells) and Law B
(sunken roads, basins) are unconditional and take no key.

Both schemas live beside ``model`` under the 1,000-line file law (the
``flat_site_schema`` / ``cutout_schema`` precedent); ``model``
re-exports them, so every caller's import is unchanged.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Affordances", "NO_AFFORDANCES", "Resolution", "load_airports",
           "resolve_ruleset"]


@_dc.dataclass(frozen=True)
class Resolution:
    """How an ICAO identifier selects its ruleset (owner 2026-08-02)."""

    default: str
    faa_first_letters: tuple[str, ...]
    faa_two_letter_prefixes: tuple[str, ...]


# ── zones.toml ───────────────────────────────────────────────────────────


@_dc.dataclass(frozen=True)
class Affordances:
    """ONE AIRPORT'S AFFORDANCES; every key false for an airport the
    table does not name."""

    #: LAW C — kerb-wall corridors AND garage ramps (spec §6, §12g)
    kerb_wall_corridors: bool = False


#: Every airport ``airports.toml`` does not name.
NO_AFFORDANCES = Affordances()


def load_airports(raw: dict, err, build) -> "dict[str, Affordances]":
    """``airports.toml`` → ICAO (upper case) → :class:`Affordances`.
    ``err`` is the law's error type, ``build`` the model's dataclass
    builder (so an unknown key in an airport's table fails loudly)."""
    out: dict[str, Affordances] = {}
    for k, v in raw.items():
        code = str(k).strip().upper()
        if not code or len(code) > 4 or not code.isalnum():
            raise err(f"airports.{k!r}: not an ICAO identifier")
        out[code] = _t.cast(Affordances, build(Affordances, v, f"airports.{code}"))
    return out


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
