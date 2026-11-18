"""A PACK DECK AUTHORED AS DISJOINT PLATES SEATS EACH PLATE ON ITS OWN END
LINES (#2112; owner 2026-11-17T14:57Z: "(a) split them so they can better
follow the terrain").

A pack may author one bridge frame whose hard deck is two or more PLATES
with open ground between them: KBNA's taxiway-L frame is six files on one
row whose ``ATTR_hard_deck`` is two plates 22.8 m apart, each carrying its
own taxiway over the road, read by lidar 1.05 m apart.  Seated as one rigid
frame, both plates stand on the MEAN of their end lines and neither sits
on its own.

THE PLATES.  The deck file's plan-bearing hard-deck triangles, unioned in
plan; two pieces of that union within the RIGID REACH (``[placement]
rigid_reach_m``, §16c (8): solid components of one resource that come
within it are one rigid cluster) are one plate.  A frame is split only
when its deck has two or more plates AND they stand in order along one
axis with every gap along it wider than the reach: the frame is then cut
into BANDS by lines across that axis at each gap's middle.  _Plates that do
not band that way (an L of plates, plates overlapping along the axis) are
left whole and counted by the census.

THE CUT.  Every body of every member of the frame (the deck, its walls,
its ceiling, its parapets, its lights) is cut into one body per band: a
triangle across a band line is CLIPPED there (``obj8_split``, a body's
``band``), so a wall running past both plates is split at the same gap as
the deck.  No tilt (decks never tilt): each band's body is the rigid body
it was, translated.

THE SEAT.  Each band's zero is the frame's own zero moved by its plate's
end-line ground: ``Z_k = Z + (mean ground at band k's stations - mean
ground at all stations)``, the stations being the deck's own seat stations
(``plate_stations`` -- the end lines the design solve held flush) or,
without them, its deck end stations.  Under the hard-deck plate seat
(``airside_deck_seat._plate_zero``: the frame zero IS the mean over all
stations less the deck top) that is exactly each plate's own end lines'
mean less the deck top.  Each band's body is anchored on its band's
station nearest that band's stations' middle.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import functools as _ft
import math
import os
import typing as _t

import numpy as np

from ..geom.plate_bands import Plates as _Plates
from ..geom.plate_bands import piece_plates
from ..geom.plate_bands import plate_bands as _bands_of
from ..geom.plate_bands import plate_clusters as _clusters

__all__ = ["piece_plates", "frame_plates", "split_record", "census_file"]

#: ``Member.deck_kind`` values whose file's hard deck is the frame's deck
_DECK_KINDS = ("flag", "signature")
#: two members share one authored frame when their origins agree to this
#: (degrees, ~1 mm) and their headings to this (degrees)
_SAME_ORIGIN_DEG = 1e-8
_SAME_HEADING_DEG = 1e-6


def _pieces(v: np.ndarray, tris: np.ndarray) -> list:
    """The plan polygons ``(x, z)`` of the deck triangles' union."""
    import shapely
    if not tris.shape[0]:
        return []
    f = v[tris][:, :, [0, 2]]
    a = 0.5 * np.abs(np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0]))
    f = f[a > 1e-6]
    if not f.shape[0]:
        return []
    u = shapely.union_all(shapely.buffer(shapely.polygons(f), 0.01))
    return [g for g in getattr(u, "geoms", [u]) if not g.is_empty]


@_ft.lru_cache(maxsize=512)
def _read(path: str, reach_m: float) -> "tuple[_Plates | None, int]":
    """``(the bands, how many plates)`` of the deck file at ``path``."""
    from . import obj8 as _obj8
    if not path or not os.path.isfile(path):
        return None, 0
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        return None, 0
    v = np.asarray(g.vertices, float)[:, :3]
    polys = _pieces(v, np.asarray(g.hard_deck, dtype=np.int64).reshape(-1, 3))
    groups = _clusters(polys, reach_m)
    if len(groups) < 2:
        return None, len(groups)
    pts = [np.concatenate([np.asarray(polys[i].exterior.coords) for i in grp])
           for grp in groups]
    return _bands_of(pts, reach_m), len(groups)


def _pristine(path: str) -> str:
    if path and not path.endswith(".anchor_bak") and os.path.isfile(path + ".anchor_bak"):
        return path + ".anchor_bak"
    return path


def _plates_of(path: str, reach_m: float) -> "_Plates | None":
    """The bands of the deck file at ``path`` (its pristine ``.anchor_bak``
    when one stands beside it), or None: one plate, no hard deck, or
    plates that do not band (module doc)."""
    if reach_m <= 0.0:
        return None
    return _read(_pristine(str(path or "")), float(reach_m))[0]


def census_file(path: str, reach_m: float) -> dict:
    """One deck file's reading for the census: its plates, whether they
    band, the gaps along the axis."""
    p, n = _read(_pristine(str(path)), float(reach_m))
    return {"plates": n, "banded": p is not None,
            "gaps_m": [round(g, 2) for g in (p.gaps if p else ())],
            "extents": [[round(a, 2), round(b, 2)] for a, b in (p.extents if p else ())]}


@_dc.dataclass(frozen=True)
class _FramePlates:
    """A frame whose deck is in plates: the deck member's ``plates``, its
    authored frame (``origin`` (lat, lon), ``heading`` degrees) and its
    seat stations ``(lat, lon)``."""

    deck_id: str
    plates: _Plates
    origin: tuple[float, float]
    heading: float
    stations: tuple[tuple[float, float], ...]
    #: per band, whether it is KEPT (owner RULINGS 2026-11-18i: a deck cut to
    #: its spans keeps its span bands and drops the at-grade rest); ``()``
    #: keeps every band (#2112)
    keep: tuple[bool, ...] = ()

    def kept(self, k: int) -> bool:
        return not self.keep or bool(self.keep[k])

    def to_frame(self, lat: float, lon: float) -> tuple[float, float]:
        """``(x, z)`` of a world point in the deck's authored frame
        (``placement_file.authored_offset``'s map)."""
        from .anchor_rule import _m_per_deg
        ml, mo = _m_per_deg(self.origin[0])
        e = (float(lon) - self.origin[1]) * mo
        n = (float(lat) - self.origin[0]) * ml
        h = math.radians(self.heading)
        c, s = math.cos(h), math.sin(h)
        return e * c - n * s, -e * s - n * c

    def band_of_ll(self, lat: float, lon: float) -> int:
        return self.plates.band_of(*self.to_frame(lat, lon))

    def shares_frame(self, m: _t.Any) -> bool:
        """Is member ``m`` authored in this deck's frame (one row)?"""
        o = getattr(m, "origin", None)
        if o is None:
            return False
        return (abs(float(o[0]) - self.origin[0]) <= _SAME_ORIGIN_DEG
                and abs(float(o[1]) - self.origin[1]) <= _SAME_ORIGIN_DEG
                and abs(float(getattr(m, "heading_deg", 0.0) or 0.0) - self.heading)
                <= _SAME_HEADING_DEG)


def _stations(m: _t.Any) -> tuple[tuple[float, float], ...]:
    st = getattr(m, "plate_stations", None) or getattr(m, "deck_end_stations", None) or ()
    return tuple((float(q[0]), float(q[1])) for q in st)


def frame_plates(members: _t.Sequence[_t.Any], reach_m: float,
                 counts: "dict | None" = None) -> "_FramePlates | None":
    """The frame's deck in plates (module doc), or None: no deck member or
    more than one, a deck in one plate, plates that do not band, or a band
    with no seat station."""
    counts = {} if counts is None else counts
    decks = [m for m in members if str(getattr(m, "deck_kind", "") or "") in _DECK_KINDS]
    if len(decks) != 1 or reach_m <= 0.0:
        return None
    m = decks[0]
    o = getattr(m, "origin", None)
    st = _stations(m)
    if getattr(m, "deck_spans", ()) and o is not None and st:
        return _span_plates(m, (float(o[0]), float(o[1])), st, counts)
    p = _plates_of(str(getattr(m, "authored_path", "") or ""), reach_m)
    if p is None:
        return None
    if o is None or not st:
        counts["deck_plates_no_stations"] = counts.get("deck_plates_no_stations", 0) + 1
        return None
    fp = _FramePlates(str(getattr(m, "id", "")), p, (float(o[0]), float(o[1])),
                     float(getattr(m, "heading_deg", 0.0) or 0.0), st)
    if len({fp.band_of_ll(*q) for q in st}) < len(p):
        counts["deck_plates_unseated"] = counts.get("deck_plates_unseated", 0) + 1
        return None
    return fp


#: how far a kept span band reaches past its abutment line, metres
SPAN_SEAT_M = 0.5


def _span_plates(m: _t.Any, origin: tuple[float, float],
                 st: tuple[tuple[float, float], ...], counts: dict) -> "_FramePlates | None":
    """The frame's bands of a deck CUT TO ITS SPANS (owner RULINGS
    2026-11-18i, ``Member.deck_spans``): a band line across the axis at
    each abutment, the span bands kept, the at-grade bands between and
    beyond dropped; ``None`` where a span band holds no seat station."""
    a, b, spans = m.deck_spans
    fp0 = _FramePlates(str(getattr(m, "id", "")), _Plates((1.0, 0.0), ((0.0, 0.0),), (), ()),
                       origin, float(getattr(m, "heading_deg", 0.0) or 0.0), st)
    ax, az = fp0.to_frame(*a)
    bx, bz = fp0.to_frame(*b)
    L = math.hypot(bx - ax, bz - az)
    if L <= 0.0 or not spans:
        return None
    ux, uz = (bx - ax) / L, (bz - az) / L
    s0 = ux * ax + uz * az
    # each span band reaches SPAN_SEAT_M past its abutments, so the seat
    # stations on its end lines stand inside it
    cuts = tuple(s0 + float(q) for sa, sb in spans
                 for q in (sa - SPAN_SEAT_M, sb + SPAN_SEAT_M))
    edges = (-math.inf, *cuts, math.inf)
    p = _Plates((ux, uz), tuple(zip(edges[:-1], edges[1:], strict=True)), cuts, ())
    keep = tuple(k % 2 == 1 for k in range(len(cuts) + 1))
    fp = _dc.replace(fp0, plates=p, keep=keep)
    if any(keep[k] and not any(fp.band_of_ll(*q) == k for q in st) for k in range(len(keep))):
        counts["deck_spans_unseated"] = counts.get("deck_spans_unseated", 0) + 1
        return None
    counts["deck_span_frames"] = counts.get("deck_span_frames", 0) + 1
    return fp


def _band_seats(fp: _FramePlates, surface: _t.Any
                ) -> "list[tuple[float, tuple[float, float, float]]] | None":
    """Per band ``(delta_k, seat (lat, lon, z))``: the band's end-line ground
    less the frame's, and its station nearest its stations' middle; None
    where a band's stations read no surface."""
    read = [(la, lo, surface(la, lo)) for la, lo in fp.stations]
    read = [(la, lo, float(z)) for la, lo, z in read if z is not None]
    if not read:
        return None
    mean_all = sum(r[2] for r in read) / len(read)
    # the frame zero (``airside_deck_seat._plate_zero``) is the mean over
    # every station; a dropped band holds none (RULINGS 2026-11-18i)
    out = []
    for k in range(len(fp.plates)):
        mine = [r for r in read if fp.band_of_ll(r[0], r[1]) == k]
        if not fp.kept(k):
            out.append((0.0, None))
            continue
        if not mine:
            return None
        cla = sum(r[0] for r in mine) / len(mine)
        clo = sum(r[1] for r in mine) / len(mine)
        seat = min(mine, key=lambda r: (r[0] - cla) ** 2 + (r[1] - clo) ** 2)
        out.append((sum(r[2] for r in mine) / len(mine) - mean_all, seat))
    return out


def _in_band(fp: _FramePlates, k: int, pts: _t.Sequence) -> tuple:
    return tuple(q for q in pts if fp.band_of_ll(q[0], q[1]) == k)


def split_record(record: _t.Any, m: _t.Any, fp: "_FramePlates | None",
                 surface: _t.Any, counts: dict) -> _t.Any:
    """``record`` (one member's ``Split``) with every body cut into one body
    per band of ``fp``, each at its band's zero on its band's seat station
    (module doc); unchanged where ``fp`` is None, the member is not in the
    deck's frame, or the stations read no ground.  A body whose anchor
    reads no surface stays whole."""
    if fp is None or not record.bodies:
        return record
    if not fp.shares_frame(m):
        counts["deck_plates_member_off_frame"] = counts.get("deck_plates_member_off_frame", 0) + 1
        return record
    seats = _band_seats(fp, surface)
    if seats is None:
        counts["deck_plates_no_ground"] = counts.get("deck_plates_no_ground", 0) + 1
        return record
    from .placement_file import authored_offset, named_body
    next_id = max(b.body_id for b in record.bodies) + 1
    out = []
    for b in record.bodies:
        a = b.anchor
        if a.surface_z is None or b.band is not None:
            out.append(b)
            continue
        zero = float(a.surface_z) - float(a.y_zero)
        first = True
        for k, (dk, seat) in enumerate(seats):
            if seat is None:
                counts["deck_span_bands_dropped"] = counts.get("deck_span_bands_dropped", 0) + 1
                continue
            la, lo, sz = seat
            y0 = float(sz) - (zero + dk)
            a2 = _dc.replace(
                a, lat=la, lon=lo, surface_z=float(sz), y_zero=y0,
                offset=authored_offset(la, lo, y0, record.lat, record.lon, record.heading),
                reason=(f"deck plate {k + 1}/{len(seats)} on its own end lines: zero "
                        f"{zero + dk:.2f} ({dk:+.2f} off the frame's {zero:.2f}; #2112)"
                        f"; was: {a.reason}"))
            bid = b.body_id if first else next_id
            next_id += 0 if first else 1
            first = False
            out.append(named_body(m, b, body_id=bid, anchor=a2, band=fp.plates.band(k),
                                  feet=_in_band(fp, k, b.feet),
                                  geom_pts=_in_band(fp, k, b.geom_pts)))
        counts["deck_plate_split_bodies"] = counts.get("deck_plate_split_bodies", 0) + 1
    counts["deck_plate_placements"] = counts.get("deck_plate_placements", 0) + 1
    return _dc.replace(record, bodies=tuple(out))
