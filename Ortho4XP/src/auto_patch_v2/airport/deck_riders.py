"""A BRIDGE AUTHORED AS SEVERAL FILES ON ONE ROW SEATS AS ONE BRIDGE (#2086).

Owner RULINGS 2026-10-22d (a free-standing bridge's deck sits flush with the
terrain at its ends, its supports sinking or floating as they must) and
2026-10-22m ("they should always move as a group") read a frame — one plan
unit, every row at one anchor spelling — as a bridge when EVERY member of
it is a deck (``placement_family.frame_is_bridge``).  A pack may author one
bridge as two files: the deck surface (a ``signature`` deck: its plate and
its mapped bridge way) and the structure carrying it — parapets, sides,
piers — which the signature pass names a member of the deck's FAMILY with
no plate of its own ("seats with its deck", ``deck_signature._apply``).
Read member by member, that frame is not all-deck, so the deck took the
generic low-side foot and the structure took its OWN low-side foot: LEMG's
motorway viaduct (1.0.519) drew its structure 13-19 m over the ground and
its deck 16 m under the structure, its ends buried up to 1.3 m.

THE RIDER WITNESS.  A plateless family member RIDES a deck of its own frame
when EVERY one of its parts' plan centroids stands on that deck's model
footprint, within §16e (3)'s contact reach (``bridge_family.CONTACT_M``, the
same polygon and reach that names a body's ``bridge_of``).  A frame whose
every member is a deck or a rider is a bridge: its decks take the
free-standing deck-top datum (22d) and each rider takes the datum of the
deck it rides, so the whole frame takes ONE zero.  A terminal's frame whose
family members stand beside its decks (measured over the shared plans:
6-91 % of their family parts off every deck print) is not a bridge and
reads as before.

The relation is per frame, never partial: one family part off every deck
leaves the whole frame to today's reading (lane ``v2bridgecontact`` measured
a PARTIALLY bound bridge worse than an unbound one, ``bridge_family``).
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import functools as _ft
import typing as _t

from .bridge_family import CONTACT_M, DeckPrint
from .placement_family import DECK_VERDICTS

__all__ = ["FAMILY_KIND", "FrameDatums", "end_tops", "riding_frames", "objects_ride",
           "frame_datum", "with_end_tops"]

#: ``Member.deck_kind`` of a member of an accepted deck family that has no
#: plate of its own (``deck_signature._apply``)
FAMILY_KIND = "family"


def _kind(m: _t.Any) -> str:
    return str(getattr(m, "deck_kind", "") or "")


def _deck_ridden(m: _t.Any, prints: _t.Sequence[DeckPrint]) -> "int | None":
    """The member index of the deck every part of ``m`` stands on, or None."""
    parts = tuple(getattr(m, "parts", ()) or ())
    if not parts:
        return None
    lats = [float(p.lat) for p in parts]
    lons = [float(p.lon) for p in parts]
    for pr in prints:
        if all(pr.contains_many(lats, lons, CONTACT_M)):
            return int(pr.member)
    return None


def _frame_seats(kinds: _t.Sequence[str], ridden: _t.Callable[[int], "int | None"]
                 ) -> dict[int, int]:
    """THE RIDER WITNESS over one frame (module doc): ``member -> the member
    whose datum it takes`` (a deck its own, a rider its deck's) when the
    frame holds a deck and a plateless family member and nothing else, and
    every family member rides one of its decks (``ridden(mi)``: the deck's
    index, or None); ``{}`` otherwise."""
    if (FAMILY_KIND not in kinds or not any(k in DECK_VERDICTS for k in kinds)
            or any(k not in DECK_VERDICTS and k != FAMILY_KIND for k in kinds)):
        return {}
    seats: dict[int, int] = {}
    for mi, k in enumerate(kinds):
        deck = mi if k in DECK_VERDICTS else ridden(mi)
        if deck is None:
            return {}
        seats[mi] = deck
    return seats


def riding_frames(plan: _t.Any, prints: _t.Sequence[DeckPrint]
                  ) -> dict[tuple[int, int], int]:
    """``(unit, member) -> the member whose datum it takes`` (its own index
    for a deck, its deck's for a rider) over every frame that holds a
    plateless deck-family member and is otherwise all decks, every such
    member riding one of the frame's own decks (module doc).  Frames
    ``frame_is_bridge`` already reads are not listed."""
    by_unit: dict[int, list[DeckPrint]] = {}
    for pr in prints:
        by_unit.setdefault(int(pr.unit), []).append(pr)
    out: dict[tuple[int, int], int] = {}
    for ui, u in enumerate(getattr(plan, "units", ()) or ()):
        ms = tuple(getattr(u, "members", ()) or ())
        own = by_unit.get(ui, [])
        seats = _frame_seats([_kind(m) for m in ms],
                             lambda mi, ms=ms, own=own: _deck_ridden(ms[mi], own))
        out.update({(ui, mi): d for mi, d in seats.items()})
    return out


def _placed(o: _t.Any, tris: _t.Any, cache: _t.Any):
    """``tris`` of placement ``o``'s geometry as frame faces ``(n, 3, 3)``."""
    from .bridge_witness import placed_faces
    g = cache.geometry(o.resolved) if getattr(o, "resolved", None) else None
    if g is None:
        return None
    return placed_faces(g.vertices[:, :3], tris if tris is not None else g.solid,
                        o.xy, float(o.heading_deg or 0.0))


def objects_ride(objects: _t.Sequence[_t.Any], kinds: _t.Sequence[str], cache: _t.Any
                 ) -> bool:
    """THE RIDER WITNESS on PACK placements (the pack stage's frames and the
    deck signature's families, before a plan exists): is this frame — the
    placements ``objects`` with their deck verdicts ``kinds`` — a deck and
    the structure riding it (:func:`riding_frames`' rule)?  A part is a
    genuine component (``ResourceCache.genuine``, the plan's parts) at its
    area-weighted plan centroid; a deck's footprint is every solid triangle
    of its model, within :data:`CONTACT_M`."""
    import numpy as np
    import shapely

    if FAMILY_KIND not in kinds:
        return False
    trees: dict[int, _t.Any] = {}

    def tree(mi: int):
        if mi not in trees:
            f = _placed(objects[mi], None, cache)
            trees[mi] = None if f is None or not len(f) else shapely.STRtree(
                shapely.polygons(f[:, :, :2]))
        return trees[mi]

    decks = [mi for mi, k in enumerate(kinds) if k in DECK_VERDICTS]

    def ridden(mi: int) -> "int | None":
        o = objects[mi]
        comps = cache.genuine(o.resolved) if getattr(o, "resolved", None) else []
        pts = []
        for c in comps:
            f = _placed(o, c.tris, cache)
            if f is None or not len(f):
                continue
            a = 0.5 * np.abs(np.cross(f[:, 1, :2] - f[:, 0, :2], f[:, 2, :2] - f[:, 0, :2]))
            cen = f[:, :, :2].mean(axis=1)
            w = float(a.sum())
            pts.append((cen * a[:, None]).sum(axis=0) / w if w > 0.0
                       else f[:, :, :2].reshape(-1, 2).mean(axis=0))
        if not pts:
            return None
        pp = shapely.points(np.asarray(pts))
        for d in decks:
            t = tree(d)
            if t is None:
                continue
            hit = t.query(pp, predicate="dwithin", distance=CONTACT_M)
            if len(np.unique(hit[0])) == len(pts):
                return d
        return None
    return bool(_frame_seats(list(kinds), ridden))


#: the deck's own vertices this far beyond the nearest one to an end line
#: are read as its end (a vertex pair of one end edge differs by a rounding)
_END_BAND_M = 1.0


def end_tops(deck: _t.Any, ends: _t.Sequence, origin: tuple[float, float]
             ) -> "tuple[float, ...] | None":
    """The deck top AT each end line: the highest of the deck file's own
    vertices nearest the end line's midpoint (within ``_END_BAND_M`` of the
    nearest) — of its HARD DECK's vertices where the file declares one
    (#2090: a parapet 0.85 m over KDEN's Parking_Hill deck is no deck top).
    A deck authored on a grade meets each end at its own height (LEMG's
    viaduct: -0.25 at one end, -1.53 at the other, +1.28 at its crown).
    None where the file does not parse."""
    import math

    import numpy as np

    from .rebake_plan import _mpd
    v = _vertices(str(getattr(deck, "authored_path", "") or ""))
    if v is None:
        return None
    h = math.radians(float(getattr(deck, "heading_deg", 0.0) or 0.0))
    c, sn = math.cos(h), math.sin(h)
    east, north = v[:, 0] * c - v[:, 2] * sn, -(v[:, 0] * sn + v[:, 2] * c)
    ml, mo = _mpd(float(origin[0]))
    out = []
    for a, b in ends[:2]:
        mx = (0.5 * (float(a[1]) + float(b[1])) - float(origin[1])) * mo
        my = (0.5 * (float(a[0]) + float(b[0])) - float(origin[0])) * ml
        d = np.hypot(east - mx, north - my)
        out.append(float(v[d <= float(d.min()) + _END_BAND_M, 1].max()))
    return tuple(out)


@_ft.lru_cache(maxsize=256)
def _vertices(path: str) -> _t.Any:
    """The OBJ8 file's deck vertices ``(x, y, z)`` (parsed once a process):
    its hard deck's where it declares one, else all; None where it does not
    parse."""
    import os

    import numpy as np

    from . import obj8 as _obj8
    if not path or not os.path.isfile(path):
        return None
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        return None
    v = np.asarray(g.vertices, float)[:, :3]
    hd = getattr(g, "hard_deck", None)
    if hd is not None and len(hd):
        v = v[np.unique(np.asarray(hd, dtype=np.int64).reshape(-1))]
    return v if len(v) else None


def with_end_tops(datum: _t.Any, deck: _t.Any, origin: tuple[float, float]) -> _t.Any:
    """``datum`` with the deck top AT each of its end lines (#2090): a FREE
    deck's published tops (``Member.deck_end_tops``), else :func:`end_tops`
    off the deck's own file; unchanged where it has no two end lines, carries
    its tops already, or the file does not parse.  A deck authored on a grade
    meets each end at its own height (KDEN's outer train bridge: 8.0 and 1.0
    at its ends, 16.0 at its crown — seated by its crown, its high end stood
    8 m under its ground)."""
    import dataclasses as _dc
    if datum is None or len(getattr(datum, "ends", ()) or ()) < 2 or datum.tops:
        return datum
    pub = tuple(getattr(deck, "deck_end_tops", ()) or ())
    tops = (tuple(float(t) for t in pub[:2]) if len(pub) >= 2
            else end_tops(deck, datum.ends, origin))
    return datum if tops is None else _dc.replace(datum, tops=tops)


class FrameDatums:
    """The ONE datum of each riding frame's bridge, read once per deck: the
    deck's free-standing deck-top datum (22d) with the deck top AT each end
    line (:func:`end_tops`; 22m then sets the end flush), handed to every
    member of the frame that rides that deck."""

    def __init__(self, plan: _t.Any, rides: _t.Mapping[tuple[int, int], int],
                 step_m: float, walk_max_m: float, tol_m: float) -> None:
        self._plan, self._rides = plan, rides
        self._kw = {"abutment_step_m": step_m, "abutment_walk_max_m": walk_max_m,
                    "level_tol_m": tol_m, "free_standing": True}
        self._step = float(step_m)
        self._memo: dict[tuple[int, int], _t.Any] = {}

    def of(self, ui: int, mi: int) -> _t.Any:
        """The datum member ``mi`` of unit ``ui`` takes, or None (not a
        rider frame, or its deck carries no datum: today's reading)."""
        d = self._rides.get((ui, mi))
        if d is None:
            return None
        key = (ui, d)
        if key not in self._memo:
            self._memo[key] = self._read(self._plan.units[ui], self._plan.units[ui].members[d])
        return self._memo[key]

    def _read(self, u: _t.Any, deck: _t.Any) -> _t.Any:
        return frame_datum(deck, (float(u.anchor[0]), float(u.anchor[1])), **self._kw)


def frame_datum(deck: _t.Any, origin: tuple[float, float], **kw: _t.Any) -> _t.Any:
    """THE ONE DATUM of a riding frame's bridge, off its deck (a plan member,
    or the pack stage's member-shaped view): the free-standing deck-top
    datum (``anchor_rule.datum_of``, ``kw`` its arguments) with the deck top
    AT each end line (:func:`end_tops`); None where the deck carries none."""
    from . import anchor_rule as _ar
    return with_end_tops(_ar.datum_of(deck, **kw), deck, origin)
