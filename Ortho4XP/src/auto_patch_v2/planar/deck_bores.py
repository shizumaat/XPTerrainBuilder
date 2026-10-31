"""A HARD DECK STARTS ITS OWN TRENCH, AND ITS ROADS ARE ITS LANES (owner
RULINGS 2026-10-30a (2), 2026-10-30b, 2026-10-30f (1), 2026-10-30g;
``planar/deck_bridge``'s sibling).

Every hard-deck bridge (``planar/deck_bridge.DeckBridge``) is read before
the solve (30f (1)), and the road under it passes completely under the
deck at the floor 30g sets (30a (2)).  Two readings follow from the deck
itself, never from the aeroway way drawn over it:

* THE DECK BORES THE ROAD UNDER IT WHEN NOTHING ELSE DOES
  (:func:`deck_bores`).  The §34 (5) underpass reads the crossing off the
  aeroway ``bridge=yes`` way and its pavement cell
  (``structure_underpass.underpass_bores``); where that cell is too wide
  to read (more than ``DECK_CELL_MAX_RATIO`` carriageways) the clip falls
  back to the way's centreline ribbon, ``carriageway − rim stand-off`` —
  1.4 m for a taxiway with no ``width`` — and a road crossing it leaves a
  2.8 m piece, under ``underpass_min_span_m``: no bore, no trench.
  MEASURED kiahdeck2 (KIAH): taxiway way −41 on ``KIAH_Bridge2`` obj24615
  ("0 road(s) bored") over the trunk's two carriageways, and way −414 on
  ``KIAH_Bridge1`` obj24550 over the primary's west carriageway.  The
  deck's own ring states where the road is covered: every mapped road that
  passes under it — crossing its midline with its carriageway between the
  deck's end lines — and that no bore (mapped, covered or §34 (5)) already
  runs under there, is bored over the ring less the rim stand-off.
* THE CARRIAGEWAYS UNDER ONE DECK ARE ONE CUT ONLY WHERE THEY ARE ONE ROAD
  (:func:`deck_lanes`).  ``structures`` gives the mouths under one deck
  side one key so ``merge_duals`` makes them one corridor whatever their
  separation (the edge bridge's Q214 rule, 2026-10-28d (4)).  Under a deck
  with no walls the cut is the road width banked up to the deck (30b), and
  two carriageways standing farther apart than
  ``dual_carriageway_max_separation_m`` are not one road: their mean axis
  runs down the median, and the pavement crossing over it reads as a
  pavement tracing it.  MEASURED kiahdeck2: obj24549's primary
  carriageways 120 m apart, one 129 m-wide corridor along the median whose
  half widths jumped 64.5 / 49 m between 12 m stations — refused "the
  approach bends tighter than the corridor".  Each such carriageway is its
  own LANE: its own corridor, the deck's bank split between neighbouring
  lanes halfway across the median (:func:`lane_band`).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import OsmWay
from .deck_bridge import DeckBridge, across_dir, mid_line, project_span
from .structure_approach import carriageway_width_m

__all__ = ["deck_bores", "deck_lanes", "lane_band"]

XY = tuple[float, float]


def deck_bores(decks: _t.Sequence[DeckBridge], roads: _t.Sequence[OsmWay],
               bored: _t.Sequence[OsmWay], law: Law, tag: str
               ) -> tuple[list[OsmWay], dict[int, LineString], list[str]]:
    """``(the bores the decks start, each one's parent road line, one note
    per deck that started one)`` (module doc).  ``roads`` are the mapped
    roads a bore may follow (``structure_underpass.bore_roads``), ``bored``
    every bore way already standing; ``tag`` marks a synthesised bore with
    the deck's object id."""
    tn = law.tables.structures.tunnel
    grid = max(law.tables.emit.identity.min_distinct_spacing_m, 0.1)
    inset = tn.wall_gap_m + tn.wall_band_width_m + grid
    lines = [LineString(w.points) for w in bored if len(w.points) >= 2]
    tree = STRtree(lines) if lines else None
    out: list[OsmWay] = []
    parents: dict[int, LineString] = {}
    notes: list[str] = []
    for db in decks:
        clip = db.polygon.buffer(-inset, join_style="mitre")
        if clip.is_empty:
            continue
        mid = _midline(db)
        n = across_dir(db)
        u_lo, u_hi = project_span(db.ring, n)
        got: list[str] = []
        for w in roads:
            road = LineString(w.points)
            if not road.intersects(clip):
                continue
            half = carriageway_width_m(w.tags, law) / 2.0
            x = road.intersection(clip)
            for g in getattr(x, "geoms", [x]):
                if g.geom_type != "LineString" or g.length < tn.underpass_min_span_m:
                    continue
                c = g.intersection(mid)
                if c.is_empty or c.geom_type != "Point":
                    continue                    # it does not pass under the deck
                u = c.x * n[0] + c.y * n[1]
                if u - half - tn.wall_gap_m < u_lo or u + half + tn.wall_gap_m > u_hi:
                    continue                    # its carriageway meets an end line
                if _already_bored(c, half, clip, lines, tree, tn.underpass_min_span_m):
                    continue
                pts = tuple((float(px), float(py)) for px, py in g.coords)
                sw = OsmWay(w.id, w.kind, pts, False,
                            {**dict(w.tags), "tunnel": tn.admitted_values[0],
                             tag: db.object_id})
                out.append(sw)
                parents[id(sw)] = road
                got.append(str(w.id))
        if got:
            notes.append(f"{db.object_id}: the deck bores {len(got)} road(s) no bore runs "
                         f"under ({', '.join(got)}; RULINGS 2026-10-30a (2) / 30f (1))")
    return out, parents, notes


def _midline(db: DeckBridge) -> LineString:
    """The deck's midline (``deck_bridge.mid_line``) as a segment across the
    whole deck: the line a road under it crosses."""
    (rx, ry), off = mid_line(db)
    n = across_dir(db)
    lo, hi = project_span(db.ring, n)
    a, b = lo - 1.0, hi + 1.0
    return LineString([(rx * off + n[0] * a, ry * off + n[1] * a),
                       (rx * off + n[0] * b, ry * off + n[1] * b)])


def _already_bored(c: Point, half: float, clip, lines, tree, min_span: float) -> bool:
    """Whether a standing bore runs under the deck within ``half`` of the
    road's crossing ``c`` over at least ``min_span``."""
    if tree is None:
        return False
    near = c.buffer(max(half, 1.0))
    for j in tree.query(near, predicate="intersects"):
        if lines[int(j)].intersection(clip).length >= min_span:
            return True
    return False


def deck_lanes(mouths: _t.Sequence, deck_of: _t.Mapping[int, "DeckBridge | None"],
               sep_m: float) -> tuple[dict[int, int], dict[int, list[float]]]:
    """``(lane index per mouth id, every lane's centre per deck id)``: the
    mouths under one deck, ordered across the road (``across_dir``), split
    into lanes wherever two neighbours stand more than ``sep_m`` apart
    (module doc).  Keyed by ``id()`` of the mouth and of the deck."""
    by_deck: dict[int, list[tuple[float, int]]] = {}
    for m in mouths:
        db = deck_of.get(id(m))
        if db is None:
            continue
        n = across_dir(db)
        by_deck.setdefault(id(db), []).append((m.xy[0] * n[0] + m.xy[1] * n[1], id(m)))
    lane_of: dict[int, int] = {}
    centres: dict[int, list[float]] = {}
    for key, us in by_deck.items():
        us.sort()
        lanes: list[list[float]] = [[us[0][0]]]
        lane_of[us[0][1]] = 0
        for (u0, _a), (u1, mid) in zip(us, us[1:], strict=False):
            if u1 - u0 > sep_m:
                lanes.append([])
            lanes[-1].append(u1)
            lane_of[mid] = len(lanes) - 1
        centres[key] = [0.5 * (min(ln) + max(ln)) for ln in lanes]
    return lane_of, centres


def lane_band(db: DeckBridge, centres: _t.Sequence[float], lane: int
              ) -> "tuple[float, float] | None":
    """``(lo, hi)`` across the road (``across_dir``) of lane ``lane``'s share
    of ``db``: halfway to each neighbouring lane; ``None`` for a deck with
    one lane."""
    if len(centres) < 2:
        return None
    lo = -float("inf") if lane == 0 else 0.5 * (centres[lane - 1] + centres[lane])
    hi = float("inf") if lane == len(centres) - 1 else 0.5 * (centres[lane] + centres[lane + 1])
    return lo, hi
