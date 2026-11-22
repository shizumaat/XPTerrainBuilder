"""A PACK PLACEMENT ON A GENERATED DECK RIDES IT (owner RULINGS
2026-11-19c; #2167 follow-up, sim read 1.0.561 KJFK: "some red and white
striped barricades marking the edges that sat on the bridges, is it
possible to seat those on our new bridge objects?").

A generated deck (``generated_pack``) replaces a pack bridge; the pack's
own placements on that bridge -- barriers, posts, object strings -- stay
(only the faked-cut placements are hidden).  X-Plane drapes an ``OBJECT``
row and every object of an object string (``.str``) on the TERRAIN, never
on another object, and the terrain under a generated deck is the cut: the
barricades stood in the trench metres under the deck.  So, in the pack
write, after the hides:

* an ``OBJECT`` / ``OBJECT_MSL`` row whose FOOTPRINT stands on a deck
  (the majority of its plan box corners and anchor, ``anchor_rule.
  deck_datum_of``, §49 (2)) is written ``OBJECT_MSL`` at its plan
  position, its lowest point on the deck top: the deck's own plane
  (``deck_z_at``, so a graded deck's grade is followed) at the LOW END of
  its footprint (§49 (6), never floating), less the model's lowest
  vertex;
* an object string crossing a deck is cut at the deck's ring: the pieces
  off every deck stay a string (same definition and spacing); each piece
  on a deck becomes its objects as ``OBJECT_MSL`` rows, ``round(length /
  spacing)`` of them evenly along it (a piece shorter than half a spacing
  stays in the string), each heading along the string plus the ``.str``'s
  minimum rotation, seated as above.  A string whose ``.str`` cannot be
  read, or that names a lateral ``OFFSET`` (its side is not known), is
  left as it is and counted.

The deck top rides the recipe as :func:`deck_top` (``deck_tops``): the
ring and the top's height at each ring vertex -- the deck OBJ8's one plane
(``deck_objects``), plus its zero -- so a record re-applied without the
generator seats the same.  Objects off the decks are never touched.
Nothing here names an airport or a resource.

Build-time impact: one pass over the dump's rows and polygons, an OBJ8
read per resource standing on a deck.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from . import anchor_rule as _ar
from . import dsf_additions as _add
from . import dsf_poly_clip as _clip
from .deck_obj8 import DeckFrame
from .deck_objects import GENERATED_DIR

__all__ = ["deck_top", "ride_text"]

#: the §49 (2) majority a footprint must stand on a deck by
ON_FRACTION = 0.5
#: how far from a deck's box a row or string is looked at (metres)
_REACH_M = 30.0


@_dc.dataclass(frozen=True)
class _Ride:
    """One placement seated on a deck: its resource, plan position, the
    elevation it was written at before (``None``: draped on the terrain)
    and the one it takes, the deck, and ``kind`` ``"row"`` / ``"string"``."""

    resource: str
    lon: float
    lat: float
    old_msl: "float | None"
    new_msl: float
    deck: str
    kind: str


def deck_top(rec: _t.Mapping, frame: DeckFrame, top_y: _t.Callable[[float, float], float]
             ) -> dict:
    """The ``deck_tops`` row of one generated deck: its ring (``[lon,
    lat]``) and the top's elevation at each vertex (``top_y`` in the
    placement ``frame``, plus the deck's zero)."""
    ring = [[float(lo), float(la)] for lo, la in rec["ring"]]
    zero = float(rec["zero_m"])
    return {"object_id": str(rec["object_id"]), "ring": ring,
            "z": [round(zero + float(top_y(*frame.to_local(lo, la))), 4) for lo, la in ring]}


def _faces(tops: _t.Iterable[_t.Mapping]) -> tuple[_ar.DeckFace, ...]:
    """The ``deck_tops`` rows as §49 deck faces (``(lat, lon)`` rings)."""
    return tuple(_ar.DeckFace(str(t["object_id"]),
                              tuple((float(la), float(lo)) for lo, la in t["ring"]),
                              tuple(float(z) for z in t["z"]))
                 for t in tops or () if len(t.get("ring") or ()) >= 3)


class _Model(_t.NamedTuple):
    """An OBJ8's plan box ``(x0, z0, x1, z1)`` and lowest vertex height."""

    box: tuple[float, float, float, float]
    min_y: float


def _model(path: "str | None", memo: dict) -> "_Model | None":
    if not path:
        return None
    if path not in memo:
        try:
            from .obj8 import parse_obj8
            v = parse_obj8(path).vertices
            memo[path] = _Model((float(v[:, 0].min()), float(v[:, 2].min()),
                                 float(v[:, 0].max()), float(v[:, 2].max())),
                                float(v[:, 1].min())) if len(v) else None
        except (OSError, ValueError, IndexError):
            memo[path] = None
    return memo[path]


def _footprint(lon: float, lat: float, hdg: float, m: "_Model | None"
               ) -> list[tuple[float, float]]:
    """``(lat, lon)`` of the anchor and the plan box's corners, placed."""
    pts = [(lat, lon)]
    if m is not None:
        f = DeckFrame(lon, lat, hdg)
        x0, z0, x1, z1 = m.box
        pts += [(b, a) for a, b in (f.to_lonlat(x, z) for x in (x0, x1) for z in (z0, z1))]
    return pts


def _seat(pts: _t.Sequence[tuple[float, float]], decks: _t.Sequence[_ar.DeckFace],
          m: "_Model | None", deck: "_ar.DeckFace | None" = None
          ) -> "tuple[_ar.DeckFace, float] | None":
    """``(deck, msl)``: the footprint's deck (``deck``, else its §49
    majority) and the zero putting the model's lowest point on the deck
    top at the footprint's low end; ``None`` off every deck."""
    if deck is None:
        r = _ar.deck_datum_of(pts, decks, ON_FRACTION)
        if r is None:
            return None
        deck = r[0]
    zs = [z for z in (_ar.deck_z_at(deck, la, lo) for la, lo in pts) if z is not None]
    if not zs:
        return None
    return deck, min(zs) - (m.min_y if m is not None else 0.0)


def _near(decks: _t.Sequence[_ar.DeckFace]) -> _t.Callable[..., bool]:
    """A fast ``(lat0, lon0, lat1, lon1) -> bool``: the box overlaps a
    deck's box grown by ``_REACH_M``."""
    r = _REACH_M / 111_320.0
    boxes = [(min(p[0] for p in d.ring) - r, min(p[1] for p in d.ring) - 2 * r,
              max(p[0] for p in d.ring) + r, max(p[1] for p in d.ring) + 2 * r)
             for d in decks]
    return lambda la0, lo0, la1, lo1: any(b[0] <= la1 and la0 <= b[2] and b[1] <= lo1
                                          and lo0 <= b[3] for b in boxes)


def _rows(lines: list[str], defs: _t.Sequence[str], decks, near, resolve, memo,
          rides: list[_Ride]) -> None:
    """Re-seat in place every object row whose footprint stands on a deck."""
    for i, ln in enumerate(lines):
        t = ln.split()
        if not t or t[0] not in ("OBJECT", "OBJECT_MSL"):
            continue
        msl = t[0] == "OBJECT_MSL"
        if len(t) < (6 if msl else 5):
            continue
        res = defs[int(t[1])]
        lon, lat, hdg = float(t[2]), float(t[3]), float(t[-1])
        if GENERATED_DIR in res or not near(lat, lon, lat, lon):
            continue
        m = _model(resolve(res), memo)
        s = _seat(_footprint(lon, lat, hdg, m), decks, m)
        if s is None:
            continue
        lines[i] = f"OBJECT_MSL {t[1]} {t[2]} {t[3]} {s[1]:.4f} {t[-1]}"
        rides.append(_Ride(res, lon, lat, float(t[4]) if msl else None, round(s[1], 4),
                          s[0].ref, "row"))


def _str_spec(path: "str | None") -> "tuple[float, list[tuple[float, str]]] | None":
    """An object string's ``(OFFSET, [(minimum rotation, object path)])``."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            rows = [ln.split() for ln in fh]
        offset, objs = 0.0, []
        for r in rows:
            if r[:1] == ["OFFSET"] and len(r) >= 2:
                offset = float(r[1])
            elif r[:1] == ["OBJECT"] and len(r) >= 4:
                objs.append((float(r[1]), " ".join(r[3:])))
    except (OSError, ValueError):
        return None
    return (offset, objs) if objs else None


def _metres(lat: float) -> tuple[float, float]:
    """Metres per degree of latitude and of longitude at ``lat``."""
    return 111_320.0, 111_320.0 * math.cos(math.radians(lat))


def _bearing(line: LineString, s: float) -> float:
    """The heading (degrees from north) of ``line`` (lon/lat) at ``s``."""
    a, b = line.interpolate(max(0.0, s - 1e-7)), line.interpolate(min(line.length, s + 1e-7))
    ml, mo = _metres(a.y)
    return math.degrees(math.atan2((b.x - a.x) * mo, (b.y - a.y) * ml)) % 360.0


def _on_deck(line: LineString, decks, polys, spacing: float) -> list[tuple]:
    """``(deck, piece, n objects)`` of every piece of ``line`` on a deck
    long enough to hold one object at ``spacing``."""
    ml, mo = _metres(line.centroid.y)
    cut = []
    for d in decks:
        on = line.intersection(polys[d.ref])
        for piece in getattr(on, "geoms", [on]):
            if piece.is_empty or piece.geom_type != "LineString":
                continue
            metres = LineString([(x * mo, y * ml) for x, y in piece.coords]).length
            n = round(metres / spacing)
            if n >= 1:
                cut.append((d, piece, n))
    return cut


def _string_rest(line: LineString, cut, head: _t.Sequence[str], ncoords: int) -> list[str]:
    """The string's pieces off the decks, each its own string."""
    rest = line.difference(unary_union([c[1].buffer(1e-9) for c in cut]))
    out: list[str] = []
    for p in getattr(rest, "geoms", [rest]):
        if p.is_empty or len(p.coords) < 2:
            continue
        out += [f"BEGIN_POLYGON {head[1]} {head[2]} {ncoords}", "BEGIN_WINDING"]
        out += [_clip.point_row(x, y, ncoords) for x, y in p.coords]
        out += ["END_WINDING", "END_POLYGON"]
    return out


def _strings(lines: list[str], pdefs: _t.Sequence[str], decks, near, resolve, memo,
             rides: list[_Ride], counts: dict) -> tuple[list[str], list[tuple]]:
    """The dump with every object string a deck cuts split, and the
    ``OBJECT_MSL`` rows of its on-deck pieces' objects."""
    polys = {d.ref: Polygon([(lo, la) for la, lo in d.ring]) for d in decks}
    out: list[str] = []
    add: list[tuple] = []
    pos = 0
    for start, end, head, wind in _clip.blocks(lines):
        path = pdefs[int(head[1])]
        if not path.endswith(".str") or not wind or len(wind[0]) < 2:
            continue
        las, los = [float(p[2]) for p in wind[0]], [float(p[1]) for p in wind[0]]
        if not near(min(las), min(los), max(las), max(los)):
            continue
        param, ncoords = int(head[2]), int(head[3])
        line = LineString(_clip.flatten(wind[0], False, ncoords >= 4))
        cut = _on_deck(line, decks, polys, float(param)) if param > 0 else []
        if not cut:
            continue
        spec = _str_spec(resolve(path))
        if spec is None or spec[0] != 0.0:
            counts["deck_strings_refused"] = counts.get("deck_strings_refused", 0) + 1
            continue
        here = os.path.dirname(path.lstrip("/"))
        k = 0
        for d, piece, n in cut:
            for j in range(n):
                s = (j + 0.5) * piece.length / n
                q = piece.interpolate(s)
                rot, rel = spec[1][k % len(spec[1])]
                k += 1
                res = f"{here}/{rel}" if here else rel
                hdg = (_bearing(piece, s) + rot) % 360.0
                m = _model(resolve(res), memo)
                z = _seat(_footprint(q.x, q.y, hdg, m), decks, m, deck=d)
                if z is not None:
                    add.append((res, q.x, q.y, round(z[1], 4), round(hdg, 6)))
                    rides.append(_Ride(res, q.x, q.y, None, round(z[1], 4), d.ref, "string"))
        out += lines[pos:start] + _string_rest(line, cut, head, ncoords)
        pos = end
        counts["deck_strings"] = counts.get("deck_strings", 0) + 1
    out += lines[pos:]
    return out, add


def ride_text(text: str, tops: _t.Iterable[_t.Mapping], pack_root: str = ""
              ) -> tuple[str, dict, list[_Ride]]:
    """The dump ``text`` with every pack placement standing on a generated
    deck (``tops``: the recipe's ``deck_tops``) seated on its top (module
    doc); ``pack_root`` resolves the models and the ``.str`` files (without
    it a row seats by its anchor alone and no string is cut).  Returns
    ``(text, counts, rides)``."""
    decks = _faces(tops)
    counts: dict = {}
    rides: list[_Ride] = []
    if not decks:
        return text, counts, rides
    from .obj8 import resolve_resource

    def resolve(rel: str) -> "str | None":
        return resolve_resource(rel, pack_root, None) if pack_root else None

    near = _near(decks)
    memo: dict = {}
    lines = text.split("\n")
    odefs = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("OBJECT_DEF ")]
    pdefs = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("POLYGON_DEF ")]
    _rows(lines, odefs, decks, near, resolve, memo, rides)
    lines, add = _strings(lines, pdefs, decks, near, resolve, memo, rides, counts)
    text = "\n".join(lines)
    if add:
        text, _idx = _add.add_objects(text, add)
    counts["deck_riders"] = sum(1 for r in rides if r.kind == "row")
    counts["deck_string_objects"] = len(add)
    return text, counts, rides
