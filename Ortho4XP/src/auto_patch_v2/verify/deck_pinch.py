"""A DECK'S FLOOR IS NEVER PINCHED TO ITS PAVEMENT -- family
``deck_floor_pinch`` (#2239 / #2241, spec cyyz-decks-r3 R5; owner sim read
2026-11-26T15:02Z: "the road envelope under/through the bridge must stay
clear").

A trench floor (``tunnel_ramp``) stands at its cut's level; the airside
pavement on a deck's end line stands at the deck's.  A vertex that is BOTH
-- a floor vertex the arrangement welded to a stage-1 airside ring because
the two rings stood closer than it can keep apart (``[cutout]
ring_floor_m``), or one carrying a deck's end-edge weld row
(``constraints/deck_edge_weld``) -- loses its floor rows
(``constraints/structures`` ``off_airside``) and holds the floor up at the
deck: a wedge across the road under it.  MEASURED (CYYZ capture
frames/lcyyz): the M deck's side b v3914 and v10835-7, the FA deck's
v14767-8; the T deck's -10718 at 167.46 m, a ~15 m wedge.

Every such vertex is one PRESENCE row.  :func:`pinch_records` derives them
off the solved map (the publication's ``deck_floor_pinch``, and
``tools/deck_probe.py --pinch``); :func:`deck_floor_pinch` is v2 verify's
reader; the census reads the same records
(``check_grade_lib/families/deck_floor_pinch``).  Nothing here names a
pack or an airport."""
from __future__ import annotations

import typing as _t

from .frame import Patch, Row, row

__all__ = ["FAMILY_DECK_FLOOR_PINCH", "deck_floor_pinch", "pinch_records"]

FAMILY_DECK_FLOOR_PINCH = "deck_floor_pinch"

#: the trench floor's roles (``constraints/edge_deck._FLOOR_ROLES``)
_FLOOR = frozenset({"tunnel_ramp"})
#: a deck end-edge weld row's input tag (``constraints/edge_deck._edge_rows``)
_WELD_TAG = "edge v"


def _welded(rows: _t.Iterable) -> set[int]:
    """The vertices an end-edge weld row governs (its first term)."""
    out: set[int] = set()
    for r in rows:
        src = getattr(r, "source", None)
        terms = getattr(r, "terms", None)
        if src is None or not terms or src.generator != "edge_deck":
            continue
        if any(str(i).startswith(_WELD_TAG) for i in src.inputs):
            out.add(int(terms[0][0]))
    return out


def _deck_of(xy, decks) -> str:
    """The object id of the deck whose ring stands nearest ``xy``."""
    from shapely.geometry import Point, Polygon
    best, oid = None, ""
    for db in decks:
        if len(getattr(db, "ring", ()) or ()) < 3:
            continue
        d = Polygon(db.ring).exterior.distance(Point(xy))
        if best is None or d < best:
            best, oid = d, str(db.object_id)
    return oid


def pinch_records(planar, law, rows: _t.Iterable, to_ll=None) -> list[dict]:
    """``[{deck, v, why, x, y[, lat, lon]}, ...]``: every trench-floor
    vertex that is a stage-1 airside vertex (``why`` "airside") or carries
    a deck end-edge weld row ("edge_weld"), module doc."""
    from ..model.platform import stage_air_vertices
    air = stage_air_vertices(planar, law)
    weld = _welded(rows)
    decks = tuple(getattr(planar, "decks", ()) or ())
    out: list[dict] = []
    for v in sorted(planar.vertices):
        if not _FLOOR & set(planar.roles_at(v)):
            continue
        why = "airside" if v in air else "edge_weld" if v in weld else None
        if why is None:
            continue
        x, y = planar.vertices[v].xy
        rec = {"deck": _deck_of((x, y), decks), "v": int(v), "why": why,
               "x": round(float(x), 3), "y": round(float(y), 3)}
        if to_ll is not None:
            lat, lon = to_ll(x, y)
            rec["lat"], rec["lon"] = float(lat), float(lon)
        out.append(rec)
    return out


def deck_floor_pinch(p: Patch) -> list[Row]:
    """One row per published record (module doc)."""
    out: list[Row] = []
    for r in p.publication.get(FAMILY_DECK_FLOOR_PINCH) or ():
        if r.get("lat") is None:
            continue
        lat, lon = float(r["lat"]), float(r["lon"])
        xy = p.to_m(lat, lon)
        out.append(row(FAMILY_DECK_FLOOR_PINCH, ("tunnel_ramp",), p.side("tunnel_ramp"), 0.0,
                       None, None, None, xy, xy, str(r.get("deck")), str(r.get("why")),
                       lat=lat, lon=lon))
    return out
