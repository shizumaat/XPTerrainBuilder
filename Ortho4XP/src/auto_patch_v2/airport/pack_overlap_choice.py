"""WHICH PACK KEEPS A STRUCTURE TWO PACKS BOTH DRAW (issue #2145): the
user's answer per pack pair and the rows it hides.

Two stores beside the other pack answers (``pack_choice``):

* :data:`pack_choice.PRIORITY_CHOICES` — per pair (:func:`pair_key`), the
  name of the pack whose structures stay (the WINNER), or :data:`BOTH`
  (hide nothing).  No answer hides nothing: the offer pre-selects the
  airport pack (owner 2026-11-17T19:15Z "Default would be to prefer the
  airport pack"), the user's answer is what writes.
  A drape pair (:func:`drape_key`, RULINGS 2026-11-19h) is one per tile:
  the airport pack winning hides the lower pack's draped polygons inside
  the airport (``pack_overlap_drapes``).
* :data:`pack_choice.OVERLAP_FOUND` — per pair, the last detection
  (``src/auto_patch/overlap_stage.py``): the tile, the airport pack, and each
  side's overlapping rows (``pack_overlap.HideRow``), so the answer works
  outside a build.

:func:`overlap_hides` is what every pack write reads
(``dsf_write._write_pack``: the rows join the generated recipe's
``overlap_hides`` and leave the written DSF, ``dsf_row_hide``): the
LOSING pack's rows of every answered pair on that tile.  The winning
pack's rows are :func:`kept_rows` — the structures the overlay re-seat
(#2144) adjusts to the terrain.
"""
from __future__ import annotations

import json
import os
import re
import typing as _t

from . import pack_choice as _PC
from .pack_overlap import HideRow

__all__ = ["BOTH", "STORE", "FOUND", "pair_key", "drape_key", "remember_found",
           "found", "winner", "overlap_hides", "kept_rows"]

#: the answer that keeps both packs' structures
BOTH = "both"


def _any(value: object) -> bool:
    return isinstance(value, str) and bool(value)


STORE = _PC.Store(_PC.PRIORITY_CHOICES, _any)
FOUND = _PC.Store(_PC.OVERLAP_FOUND, _any)

_TILE = re.compile(r"^([+-]\d{2})([+-]\d{3})\.dsf", re.IGNORECASE)


def pair_key(scenery_dir: str, a: str, b: str) -> str:
    """The stores' key of a pack pair (an absolute path, as the per-pack
    stores key theirs; order-free)."""
    x, y = sorted((a, b))
    return os.path.join(os.path.abspath(scenery_dir), f"{x} | {y}")


#: the key segment of a drape pair (RULINGS 19h): a lower pack's draped
#: polygons inside a custom airport, one key per tile (its rows are that
#: tile's DSF's)
DRAPE_MARK = "draped polygons"


def drape_key(scenery_dir: str, lat: int, lon: int, a: str, b: str) -> str:
    """The stores' key of a drape pair on one tile (order-free)."""
    x, y = sorted((a, b))
    return os.path.join(os.path.abspath(scenery_dir),
                        f"{DRAPE_MARK} {int(lat):+03d}{int(lon):+04d}", f"{x} | {y}")


def _scenery_of(key: str) -> str:
    """The Custom Scenery folder a structure or drape pair's key names."""
    head = os.path.dirname(key)
    if os.path.basename(head).startswith(DRAPE_MARK + " "):
        head = os.path.dirname(head)
    return head


def remember_found(key: str, lat: int, lon: int, airport: str,
                   packs: _t.Sequence[str],
                   rows: _t.Sequence[_t.Sequence[HideRow]]) -> None:
    """Remember a pair's detection (module doc)."""
    FOUND.remember(key, json.dumps(
        {"lat": int(lat), "lon": int(lon), "airport": airport,
         "packs": list(packs),
         "rows": {p: [list(r) for r in rs] for p, rs in zip(packs, rows, strict=True)}},
        sort_keys=True))


def found(key: str) -> dict:
    """A pair's remembered detection, ``{}`` when none."""
    try:
        doc = json.loads(FOUND.choice(key) or "{}")
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def winner(key: str) -> str:
    """The pack the user keeps for the pair, :data:`BOTH`, or ``""`` (not
    answered)."""
    return STORE.choice(key)


def _pairs_of(pack_name: str, scenery_dir: str, lat: int, lon: int
              ) -> _t.Iterator[tuple[str, dict]]:
    keys = _PC.read_all(_PC.store_path(_PC.OVERLAP_FOUND), _any)
    root = os.path.normcase(os.path.abspath(scenery_dir))
    for key in keys:
        if os.path.normcase(_scenery_of(key)) != root:
            continue
        doc = found(key)
        if (pack_name in (doc.get("packs") or ())
                and (doc.get("lat"), doc.get("lon")) == (lat, lon)):
            yield key, doc


def _rows(doc: dict, pack_name: str) -> list[HideRow]:
    return [HideRow(str(r[0]), float(r[1]), float(r[2]))
            for r in (doc.get("rows") or {}).get(pack_name) or ()]


def _tile_of(dsf_path: str) -> tuple[int, int] | None:
    m = _TILE.match(os.path.basename(dsf_path))
    return (int(m.group(1)), int(m.group(2))) if m else None


def overlap_hides(pack_root: str, dsf_path: str) -> list[HideRow]:
    """The rows of the pack's tile DSF the user's answers hide: its side
    of every pair on that tile whose answer names the OTHER pack."""
    tile = _tile_of(dsf_path)
    if tile is None or not pack_root:
        return []
    name = os.path.basename(os.path.normpath(pack_root))
    out: list[HideRow] = []
    for key, doc in _pairs_of(name, os.path.dirname(os.path.normpath(pack_root)),
                              *tile):
        w = winner(key)
        if w and w != BOTH and w != name:
            out += _rows(doc, name)
    return sorted(set(out))


def kept_rows(pack_root: str, lat: int, lon: int) -> list[HideRow]:
    """The rows of the pack that WON an answered pair on the tile: the
    structures #2144's overlay re-seat adjusts to the terrain."""
    name = os.path.basename(os.path.normpath(pack_root))
    out: list[HideRow] = []
    for key, doc in _pairs_of(name, os.path.dirname(os.path.normpath(pack_root)),
                              lat, lon):
        if winner(key) == name:
            out += _rows(doc, name)
    return sorted(set(out))
