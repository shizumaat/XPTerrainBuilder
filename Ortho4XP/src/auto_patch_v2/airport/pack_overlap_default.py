"""THE ONE ANSWER FOR EVERY TILE'S OVERLAPPING PACKS (issue #2190).

Owner (2026-11-20T01:00Z): for packages that cover everywhere, a
condensed question -- "always prefer the airports and hide all other
overlays that conflict, or keep everything for the whole tile, and a
checkbox to use as the default for all tiles", with the per-airport list
one step away.

* :data:`PREFER` / :data:`KEEP_ALL` -- the two condensed answers.
* :func:`mode` / :func:`set_mode` -- the default for all tiles, stored
  once beside the per-pair answers (``pack_choice.store_path``); ``""``
  is none (every build asks).  A pair's own answer always overrides it.
* :func:`winners` -- what each condensed answer gives one ``PackOverlaps``
  row: the row's ``"prefer"`` / ``"keep"`` fields.  ``""`` where the
  answer cannot decide the pair: two airport packs (a same-airport pair,
  or a structure pair whose two packs both carry a runway) -- those are
  still asked.

Nothing here names an airport or a pack.
"""
from __future__ import annotations

import typing as _t

from . import pack_choice as _PC
from .pack_overlap_choice import BOTH

__all__ = ["PREFER", "KEEP_ALL", "MODES", "mode", "set_mode", "winners"]

#: prefer the airport pack: the other pack's conflicting copies hidden
PREFER = "prefer_airports"
#: keep every pack's copies on the whole tile
KEEP_ALL = "keep_all"
MODES = (PREFER, KEEP_ALL)

#: the default's file; its one entry is keyed by the file's own path (a
#: ``pack_choice.Store`` keys by an absolute path, and the default has no pack)
_STORE = _PC.Store("pack_overlap_default.json", lambda v: v in MODES)


def _key() -> str:
    return _PC.store_path(_STORE.name)


def mode() -> str:
    """The default for all tiles: a :data:`MODES` entry, ``""`` none."""
    return _STORE.choice(_key())


def set_mode(value: str) -> None:
    """Store (or, with ``""``, forget) the default for all tiles."""
    if value and value not in MODES:
        raise ValueError(f"{value!r} is not one of {MODES}")
    _STORE.remember(_key(), value)


def winners(row: _t.Mapping, is_airport: _t.Callable[[str], bool]
            ) -> dict[str, str]:
    """``{"prefer", "keep"}``: the ``winner`` each condensed answer gives
    ``row`` (module doc); ``is_airport(name)`` says whether a pack
    carries a runway."""
    kind = row.get("kind") or ""
    packs = list(row.get("packs") or ())
    if kind == "duplicate" or len(packs) != 2:
        return {"prefer": "", "keep": ""}
    if kind == "drapes":
        return {"prefer": str(row.get("default") or ""), "keep": BOTH}
    own = [p for p in packs if is_airport(p)]
    return {"prefer": own[0] if len(own) == 1 else "", "keep": BOTH}
