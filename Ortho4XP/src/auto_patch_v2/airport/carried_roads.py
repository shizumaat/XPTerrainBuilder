"""THE DECK'S OWN ROAD: AN UNTAGGED ROAD UNDER A PACK DECK, MAPPED TWICE
WITH A LOWER ROAD, IS CARRIED BY THE DECK (owner RULINGS 2026-11-10f (1),
#1905).

"Where OSM maps two roads at the same place under a pack deck with no level
tags, the forecourt ground is at the LOWER (arrivals) level with the deck
standing over it; an untagged road under a deck print is the deck's own
road (carried), not ground."  MEASURED SBSP (GloballArt terminal,
-23.6257, -46.6597): ``small_roads:-8899`` (``highway=unclassified``, no
level tag) runs 322 m under the departures deck ``BR_SBSP-Textura_4.obj#6``
and 150 m of it within 0.46-0.63 m of ``small_roads:-8134``
(``layer=-1``, ``covered=yes``) — the departures kerb road on the deck and
the arrivals road beneath it, one place mapped twice.  As ground, the two
ribbons stood at both levels half a metre apart.

THE WITNESS is the map and the pack, never a name.  A mapped road ``A`` is
CARRIED over its run inside a pack deck piece (``bridge_family.
deck_components`` of every deck print) when

* ``A`` carries no level tag (``layer``, ``level``, ``bridge``,
  ``tunnel``, ``covered``) — the map says nothing of its level;
* another road ``B`` running inside the same piece says it lies LOWER
  (``layer < 0``, ``covered=yes`` or any ``tunnel``) — the map places ``B``
  under ``A``; and
* ``A`` runs within ``[bridge] carried_twin_max_m`` of ``B`` for at least
  ``[bridge] carried_twin_min_run_m`` inside the piece — one place.

Where both twins are untagged no witness says which is the deck's, and
nothing is carried (counted ``carried_twin_untold``).  A carried road mints
no ground ribbon over its run inside the piece (``classify/ribbon_mint``);
the deck object carries it there."""
from __future__ import annotations

import typing as _t
import weakref

from shapely.geometry import LineString, Point

__all__ = ["carried_runs", "is_level_tagged", "is_tagged_lower"]

#: the station step along a road the deck piece is read at (metres)
_STEP_M = 1.0
#: ``id(airport) -> (weak reference, its runs)``
_MEMO: dict[int, tuple] = {}

_LEVEL_KEYS = ("layer", "level", "bridge", "tunnel", "covered")


def is_level_tagged(tags: _t.Mapping[str, str]) -> bool:
    """The map states something of the road's level (module doc)."""
    return any(str(tags.get(k, "")).strip() not in ("", "no", "0") for k in _LEVEL_KEYS)


def is_tagged_lower(tags: _t.Mapping[str, str]) -> bool:
    """The map places the road below the ground's own level."""
    try:
        if float(str(tags.get("layer", "0")).split(";")[0]) < 0.0:
            return True
    except ValueError:
        pass
    if str(tags.get("covered", "")).strip() == "yes":
        return True
    return str(tags.get("tunnel", "no")).strip() not in ("", "no")


def _intervals(flags: list[bool], step: float, length: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    start = None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((max(0.0, (start - 0.5) * step), min(length, (i - 0.5) * step)))
            start = None
    return out


def _stations(line: LineString, step: float) -> list[Point]:
    n = max(1, int(line.length // step))
    return [line.interpolate(i * step) for i in range(n + 1)]


def carried_runs(airport, law, counts: "dict | None" = None
                 ) -> dict[tuple[str, int], list[tuple[float, float]]]:
    """``{(feed, way id): [(s0, s1), ...]}`` — the arclength runs, along
    the way's own centreline ``LineString(w.points)``, that a pack deck
    carries (module doc).  Memoised on the airport object."""
    held = _MEMO.get(id(airport))
    if held is not None and held[0]() is airport:
        if counts is not None:
            for k, v in held[2].items():
                counts[k] = counts.get(k, 0) + v
        return held[1]
    tally: dict[str, int] = {}
    runs = _derive(airport, law, tally)
    try:
        _MEMO[id(airport)] = (weakref.ref(airport, _forget), runs, tally)
    except TypeError:
        pass
    if counts is not None:
        for k, v in tally.items():
            counts[k] = counts.get(k, 0) + v
    return runs


def _forget(ref) -> None:
    for k, held in list(_MEMO.items()):
        if held[0] is ref:
            del _MEMO[k]


def _derive(airport, law, tally: dict) -> dict:
    br = law.tables.structures.bridge
    twin_m = float(getattr(br, "carried_twin_max_m", 0.0))
    run_m = float(getattr(br, "carried_twin_min_run_m", 0.0))
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if twin_m <= 0.0 or part is None or frame is None:
        return {}
    roads = [w for w in getattr(airport, "osm_ways", ()) or ()
             if (w.tags or {}).get("highway") and len(w.points) >= 2]
    untagged = [w for w in roads if not is_level_tagged(w.tags or {})]
    lower = [w for w in roads if is_tagged_lower(w.tags or {})]
    if not untagged or not lower:
        return {}
    from .bridge_family import deck_components
    from .partition_prints import partition_prints
    from .road_ways import ribbon_half_width_m
    prints = partition_prints(part)
    if not prints:
        return {}
    to_ll = frame.transformers()[1]
    lines = {id(w): LineString(w.points) for w in untagged + lower}
    out: dict[tuple[str, int], list[tuple[float, float]]] = {}
    for p in prints:
        for piece in deck_components(p):
            la0, lo0, la1, lo1 = piece.box
            box = _xy_box(to_ll, frame, la0, lo0, la1, lo1)
            near = [w for w in untagged + lower
                    if lines[id(w)].distance(box) <= ribbon_half_width_m(w.tags, law)]
            under = [w for w in near if is_tagged_lower(w.tags or {})]
            if not under:
                continue
            for w in near:
                if is_level_tagged(w.tags or {}):
                    continue
                got = _carried(w, lines[id(w)], [lines[id(b)] for b in under],
                               piece, box, to_ll, twin_m, run_m,
                               ribbon_half_width_m(w.tags, law))
                if got:
                    out.setdefault((str(w.kind), int(w.id)), []).extend(got)
                    tally["carried_roads"] = tally.get("carried_roads", 0) + 1
                    tally["carried_road_m"] = round(
                        tally.get("carried_road_m", 0.0) + sum(b - a for a, b in got), 1)
    return {k: sorted(v) for k, v in out.items()}


def _xy_box(to_ll, frame, la0, lo0, la1, lo1):
    from shapely.geometry import box as _box
    to_xy = frame.transformers()[0]
    xs, ys = zip(*(to_xy(lo, la) for la, lo in ((la0, lo0), (la0, lo1), (la1, lo0), (la1, lo1))))
    return _box(min(xs), min(ys), max(xs), max(ys))


def _carried(w, line: LineString, lows: list[LineString], piece, box, to_ll,
             twin_m: float, run_m: float, half_m: float) -> list[tuple[float, float]]:
    """``w``'s runs on ``piece`` — its centreline within its own
    carriageway half-width ``half_m`` of the deck: a kerb road runs ALONG
    the deck's edge, in and out of its print by a metre (SBSP: -8899
    0.0-1.7 m outside for 30-60 m at a time) — when it twins a lower road
    there for ``run_m`` (module doc), else ``[]``.  ``box`` is the piece's
    plan box: only stations within ``half_m`` of it are read."""
    lows = [lo for lo in lows if line.distance(lo) <= twin_m]
    if not lows:
        return []
    st = _stations(line, _STEP_M)
    reach = box.buffer(half_m)
    inbox = [reach.contains(p) for p in st]
    twin = [f and any(lo.distance(p) <= twin_m for lo in lows)
            for p, f in zip(st, inbox, strict=True)]
    if _STEP_M * sum(twin) < run_m:
        return []
    idx = [i for i, f in enumerate(inbox) if f]
    ll = [to_ll(st[i].x, st[i].y) for i in idx]
    hit = piece.contains_many([a for a, _b in ll], [b for _a, b in ll], half_m)
    inside = [False] * len(st)
    for i, h in zip(idx, hit, strict=True):
        inside[i] = bool(h)
    if _STEP_M * sum(1 for i, t in enumerate(twin) if t and inside[i]) < run_m:
        return []
    return _intervals(inside, _STEP_M, line.length)
