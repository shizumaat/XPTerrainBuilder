"""THE GENERATED STRUCTURES OF ONE TILE'S DSF (issue #2178).

An airport's generated decks and road bridges (``generated_pack.recipe``)
are made ONCE per airport, and an airport on two tiles writes its pack's
DSF of EACH tile with that one recipe.  ``DSFTool --text2dsf`` refuses an
object placed outside the DSF's tile (``ERROR: could not place object
LON, LAT``) and then refuses the WHOLE file, so a deck anchored on the
neighbour tile failed every placement of the airport on both tiles
(MEASURED 1.0.561: a two-tile airport, no deck and no placement on
either).  Two rules, both general:

* :func:`for_tile` -- the recipe as one tile's DSF carries it: a deck
  object only where its ANCHOR lies on the tile (the neighbour tile's
  write places the rest), a road chain CLIPPED to the tile (a segment
  crossing the edge ends on it, at the point and level both tiles
  compute alike, so the two halves meet); the regions and hides stay
  whole (a page or row a region does not reach is left alone), and so
  does the record the write keeps -- a re-applied record is filtered the
  same way;
* :func:`drop_off_tile_objects` -- defence in depth before the encoder:
  any ``OBJECT*`` row still outside the tile is left out and counted,
  never a failure of the whole write.

Nothing here names an airport.  Build-time impact: one pass over the
dump's lines, microseconds per chain.
"""
from __future__ import annotations

import typing as _t

from . import split_guard as _sg

__all__ = ["for_tile", "drop_off_tile_objects"]

_OBJECT_ROWS = ("OBJECT", "OBJECT_MSL", "OBJECT_AGL")

Box = _t.Sequence[float]


def _crossings(a: _t.Sequence, b: _t.Sequence, box: Box) -> "tuple[float, float] | None":
    """The ``(t0, t1)`` part of the segment ``a`` -> ``b`` inside ``box``
    (Liang-Barsky), ``None`` when none of it is."""
    w, s, e, n = box
    ax, ay = float(a[0]), float(a[1])
    dx, dy = float(b[0]) - ax, float(b[1]) - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - w), (dx, e - ax), (-dy, ay - s), (dy, n - ay)):
        if p == 0.0:
            if q < 0.0:
                return None
            continue
        if p < 0.0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
        if t0 > t1:
            return None
    return t0, t1


def _at(a: _t.Sequence, b: _t.Sequence, t: float) -> list:
    """The junction at ``t`` on ``a`` -> ``b``: an end keeps its own
    level, a point between takes the higher one (both tiles alike)."""
    if t <= 0.0:
        return [float(a[0]), float(a[1]), int(a[2])]
    if t >= 1.0:
        return [float(b[0]), float(b[1]), int(b[2])]
    return [float(a[0]) + t * (float(b[0]) - float(a[0])),
            float(a[1]) + t * (float(b[1]) - float(a[1])), max(int(a[2]), int(b[2]))]


def _clip_chain(junctions: _t.Sequence[_t.Sequence], box: Box) -> list[list[list]]:
    """The pieces of the chain ``junctions`` (``[lon, lat, level]``) on
    the tile ``box``, in order, each of two junctions or more."""
    pieces: list[list[list]] = []
    cur: list[list] = []
    for a, b in zip(junctions[:-1], junctions[1:], strict=False):
        got = _crossings(a, b, box)
        if got is None or got[0] >= got[1]:
            pieces.append(cur)
            cur = []
            continue
        if not cur:
            cur = [_at(a, b, got[0])]
        cur.append(_at(a, b, got[1]))
        if got[1] < 1.0:                    # the chain leaves the tile here
            pieces.append(cur)
            cur = []
    pieces.append(cur)
    return [c for c in pieces if len(c) >= 2]


def for_tile(rec: _t.Mapping, box: "Box | None") -> tuple[dict, dict]:
    """``(the recipe one tile's DSF carries, counts)`` (module doc); the
    recipe as it is, and no counts, when ``box`` is ``None``."""
    if not rec or box is None:
        return dict(rec or {}), {}
    decks = [d for d in rec.get("decks") or ()
             if _sg.inside(box, float(d["lat"]), float(d["lon"]))]
    chains: list[dict] = []
    clipped = elsewhere = 0
    for c in rec.get("chains") or ():
        js = [list(j) for j in c["junctions"]]
        if all(_sg.inside(box, float(j[1]), float(j[0])) for j in js):
            chains.append(dict(c, junctions=js))
            continue
        pieces = _clip_chain(js, box)
        clipped += bool(pieces)
        elsewhere += not pieces
        chains.extend(dict(c, junctions=p) for p in pieces)
    counts = {"decks_other_tile": len(rec.get("decks") or ()) - len(decks),
              "chains_other_tile": elsewhere, "chains_clipped": clipped}
    return dict(rec, decks=decks, chains=chains), counts


def drop_off_tile_objects(text: str, box: "Box | None") -> tuple[str, int]:
    """``text`` without its ``OBJECT*`` rows outside ``box``, and how many
    were left out (module doc)."""
    if box is None:
        return text, 0
    keep: list[str] = []
    gone = 0
    for ln in text.split("\n"):
        t = ln.split(None, 4)
        if len(t) >= 4 and t[0] in _OBJECT_ROWS:
            try:
                off = not _sg.inside(box, float(t[3]), float(t[2]))
            except ValueError:
                off = False
            if off:
                gone += 1
                continue
        keep.append(ln)
    return ("\n".join(keep) if gone else text), gone
