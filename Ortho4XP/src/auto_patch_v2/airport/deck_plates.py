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
    #: RULINGS 2026-11-18i (b): the grade a kept SPAN band may take between
    #: its two end lines (the taxiway longitudinal cap, ``Member.
    #: deck_spans``); ``None`` keeps every band flat
    grade_cap: "float | None" = None
    #: per seat station, its deck top off the stations' mean (``Member.
    #: deck_spans``): a station's ground less it is the frame zero's reading
    #: there (``()``: one top everywhere, #2112)
    station_tops: tuple[float, ...] = ()

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
    if not decks or reach_m <= 0.0:
        return None
    m = decks[0]
    o = getattr(m, "origin", None)
    st = _stations(m)
    # RULINGS 2026-11-18i: a frame CUT TO ITS SPANS is cut whole, however
    # many hard decks it holds -- every one carries the one cut (MEASURED
    # frames/lkrdu: KRDU STH_TML obj140 and its bridge decks NewC2_RP obj142
    # are two flag decks of one frame; read as "more than one deck", the
    # frame was seated whole at one zero and no at-grade band dropped)
    if getattr(m, "deck_spans", ()) and o is not None and st and all(
            tuple(getattr(q, "deck_spans", ()) or ()) == tuple(m.deck_spans) for q in decks):
        return _span_plates(m, (float(o[0]), float(o[1])), st, counts)
    if len(decks) != 1:
        return None
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
    a, b, spans, *rest = m.deck_spans
    cap = rest[:1]
    tops = tuple(rest[1]) if len(rest) > 1 and len(rest[1]) == len(st) else ()
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
    fp = _dc.replace(fp0, plates=p, keep=keep,
                     grade_cap=float(cap[0]) if cap and cap[0] is not None else None,
                     station_tops=tops)
    if any(keep[k] and not any(fp.band_of_ll(*q) == k for q in st) for k in range(len(keep))):
        counts["deck_spans_unseated"] = counts.get("deck_spans_unseated", 0) + 1
        return None
    counts["deck_span_frames"] = counts.get("deck_span_frames", 0) + 1
    return fp


def _band_seats(fp: _FramePlates, surface: _t.Any, counts: "dict | None" = None
                ) -> "list[tuple[float, tuple[float, float, float] | None, tuple]] | None":
    """Per band ``(delta_k, seat (lat, lon, z), warp)``: the band's end-line
    ground less the frame's, its station nearest its stations' middle and
    its grade (:func:`_span_grade`); None where a band's stations read no
    surface."""
    # each station's ground less its deck top off the mean (18i (b)): the
    # frame zero's reading there, so a band's zero and grade are its deck's
    off = fp.station_tops or (0.0,) * len(fp.stations)
    read = [(la, lo, surface(la, lo), t) for (la, lo), t in zip(fp.stations, off, strict=True)]
    read = [(la, lo, float(z) - float(t), float(z)) for la, lo, z, t in read if z is not None]
    if not read:
        return None
    mean_all = sum(r[2] for r in read) / len(read)
    # the frame zero (``airside_deck_seat._plate_zero``) is the mean over
    # every station; a dropped band holds none (RULINGS 2026-11-18i)
    out = []
    for k in range(len(fp.plates)):
        mine = [r for r in read if fp.band_of_ll(r[0], r[1]) == k]
        if not fp.kept(k):
            out.append((0.0, None, ()))
            continue
        if not mine:
            return None
        cla = sum(r[0] for r in mine) / len(mine)
        clo = sum(r[1] for r in mine) / len(mine)
        la, lo, _zr, z = min(mine, key=lambda r: (r[0] - cla) ** 2 + (r[1] - clo) ** 2)
        seat = (la, lo, z)
        mean_k = sum(r[2] for r in mine) / len(mine)
        out.append((mean_k - mean_all, seat, _span_grade(fp, k, mine, mean_k, counts)))
    return out


def _span_grade(fp: _FramePlates, k: int, mine: list, mean_k: float,
                counts: "dict | None") -> tuple:
    """A KEPT SPAN TAKES ITS OWN GRADE (owner RULINGS 2026-11-18i (b), #2157
    KRDU): band ``k`` of a deck cut to its spans, its stations ``mine``
    ``(lat, lon, z)`` split at the band's middle into its two end lines,
    is WARPED (``obj8_warp.Track``, ``("track", ((x, z, D), ...))`` in the
    authored frame, ``D`` off the band's zero ``mean_k``) straight between
    the two lines' ground, so each end line seats on its own and the piers
    stay vertical.  The cap ``fp.grade_cap`` holds the PAVEMENT's grade
    (each end line's ground, ``r[3]``), never the bend off the authored
    deck (owner 2026-11-18T23:04Z, RULINGS 2026-11-18i (7)): a pavement
    grade over it is held to it about the middle and counted
    (``deck_span_over_cap``), the bend is what that leaves; end lines whose
    bend is under the weld (``_GRADE_MIN_M``) stay flat; ``()`` for a flat
    band."""
    if fp.grade_cap is None or not fp.keep:
        return ()
    ux, uz = fp.plates.axis
    lo, hi = fp.plates.band(k)[2:]
    mid = 0.5 * (lo + hi)
    pts = [(*fp.to_frame(r[0], r[1]), r[2], r[3]) for r in mine]
    ends = [[q for q in pts if (ux * q[0] + uz * q[1] < mid) == first] for first in (True, False)]
    if not all(ends):
        return ()
    (xa, za, ga, pa), (xb, zb, gb, pb) = ([sum(q[i] for q in e) / len(e) for i in range(4)]
                                          for e in ends)
    run = abs(ux * (xb - xa) + uz * (zb - za))
    if run <= 0.0 or abs(gb - ga) <= _GRADE_MIN_M:
        return ()
    if abs(pb - pa) > fp.grade_cap * run:
        if counts is not None:
            counts["deck_span_over_cap"] = counts.get("deck_span_over_cap", 0) + 1
        m, rise = 0.5 * (pa + pb), math.copysign(fp.grade_cap * run, pb - pa)
        ga, gb = ga + (m - 0.5 * rise) - pa, gb + (m + 0.5 * rise) - pb
    if counts is not None:
        counts["deck_span_graded"] = counts.get("deck_span_graded", 0) + 1
    return (("track", ((round(xa, 4), round(za, 4), round(ga - mean_k, 4)),
                       (round(xb, 4), round(zb, 4), round(gb - mean_k, 4)))),)


#: end lines whose ground differs by no more than this stay flat (the
#: weld, ``[structures.bridge] deck_flush_m``'s order), metres
_GRADE_MIN_M = 0.04


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
    seats = _band_seats(fp, surface, counts)
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
        for k, (dk, seat, warp) in enumerate(seats):
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
                        + (f"; graded {warp[0][1][0][2]:+.2f} -> {warp[0][1][1][2]:+.2f} "
                           "between its end lines (RULINGS 2026-11-18i (b))" if warp else "")
                        + f"; was: {a.reason}"))
            bid = b.body_id if first else next_id
            next_id += 0 if first else 1
            first = False
            out.append(named_body(m, b, body_id=bid, anchor=a2, band=fp.plates.band(k),
                                  feet=_in_band(fp, k, b.feet),
                                  geom_pts=_in_band(fp, k, b.geom_pts),
                                  **({"warp": warp} if warp else {})))
        counts["deck_plate_split_bodies"] = counts.get("deck_plate_split_bodies", 0) + 1
    counts["deck_plate_placements"] = counts.get("deck_plate_placements", 0) + 1
    return _dc.replace(record, bodies=tuple(out))
