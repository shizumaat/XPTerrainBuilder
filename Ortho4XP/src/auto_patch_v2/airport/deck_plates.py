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

__all__ = ["piece_plates", "frame_plates", "split_record", "census_file"]

#: ``Member.deck_kind`` values whose file's hard deck is the frame's deck
_DECK_KINDS = ("flag", "signature")
#: two members share one authored frame when their origins agree to this
#: (degrees, ~1 mm) and their headings to this (degrees)
_SAME_ORIGIN_DEG = 1e-8
_SAME_HEADING_DEG = 1e-6


@_dc.dataclass(frozen=True)
class _Plates:
    """The bands of a deck in plates: ``axis`` the unit plan direction
    ``(ux, uz)`` in the authored frame, ``extents`` each plate's
    ``(lo, hi)`` along it in order, ``cuts`` the band lines between them
    (each gap's middle), ``gaps`` the gap widths along the axis."""

    axis: tuple[float, float]
    extents: tuple[tuple[float, float], ...]
    cuts: tuple[float, ...]
    gaps: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.extents)

    def band_of(self, x: float, z: float) -> int:
        """The band the authored plan point ``(x, z)`` stands in."""
        s = self.axis[0] * float(x) + self.axis[1] * float(z)
        return int(sum(1 for c in self.cuts if s >= c))

    def band(self, k: int) -> tuple[float, float, float, float]:
        """``(ux, uz, lo, hi)`` of band ``k`` -- what ``obj8_split.BodyCut.
        band`` clips to; the outer bands run to infinity."""
        lo = -math.inf if k == 0 else self.cuts[k - 1]
        hi = math.inf if k == len(self.cuts) else self.cuts[k]
        return (self.axis[0], self.axis[1], lo, hi)


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


def _clusters(polys: list, reach_m: float) -> list[list[int]]:
    """Pieces within ``reach_m`` of each other chained into one plate."""
    from ..geom.union_find import find_root
    parent = list(range(len(polys)))
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            if polys[i].distance(polys[j]) <= reach_m:
                parent[find_root(parent, i)] = find_root(parent, j)
    out: dict[int, list[int]] = {}
    for i in range(len(polys)):
        out.setdefault(find_root(parent, i), []).append(i)
    return list(out.values())


def _bands_of(plates: _t.Sequence[np.ndarray], reach_m: float) -> "_Plates | None":
    """The bands of ``plates`` (each an ``(n, 2)`` array of its plan points
    ``(x, z)``), or None where they do not stand in order along one axis
    with every gap along it wider than ``reach_m`` (module doc)."""
    if len(plates) < 2:
        return None
    cen = np.asarray([np.asarray(p, float).mean(axis=0) for p in plates])
    d = cen - cen.mean(axis=0)
    w, vec = np.linalg.eigh(d.T @ d)        # the plates' centres' main axis
    ax = vec[:, int(np.argmax(w))]
    if ax[0] < 0 or (ax[0] == 0 and ax[1] < 0):
        ax = -ax
    ext = sorted((float((np.asarray(p, float) @ ax).min()),
                  float((np.asarray(p, float) @ ax).max())) for p in plates)
    gaps = tuple(b[0] - a[1] for a, b in zip(ext, ext[1:], strict=False))
    if min(gaps) <= reach_m:
        return None
    cuts = tuple(0.5 * (a[1] + b[0]) for a, b in zip(ext, ext[1:], strict=False))
    return _Plates((float(ax[0]), float(ax[1])), tuple(ext), cuts, gaps)


def piece_plates(rings: _t.Sequence[_t.Sequence[tuple[float, float]]],
                 reach_m: float) -> "tuple[int, ...] | None":
    """The plate of each deck PIECE (``rings``: one deck object's piece
    outlines in plan, any one frame) -- the patch half's reading of the
    same rule (``constraints/deck_lines.plate_of``): pieces within
    ``reach_m`` are one plate, and the plates are told apart only where
    they band (:func:`_bands_of`); ``None`` otherwise (one zero for the
    object, as before)."""
    import shapely
    if len(rings) < 2 or reach_m <= 0.0:
        return None
    polys = [shapely.Polygon(r).buffer(0.0) for r in rings]
    if any(p.is_empty for p in polys):
        return None
    groups = _clusters(polys, reach_m)
    if len(groups) < 2:
        return None
    pts = [np.concatenate([np.asarray(rings[i], float) for i in g]) for g in groups]
    p = _bands_of(pts, reach_m)
    if p is None:
        return None
    out = [0] * len(rings)
    for g, grp in zip(pts, groups, strict=True):
        k = p.band_of(*g.mean(axis=0))
        for i in grp:
            out[i] = k
    return tuple(out)


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
    p = _plates_of(str(getattr(m, "authored_path", "") or ""), reach_m)
    if p is None:
        return None
    o = getattr(m, "origin", None)
    st = _stations(m)
    if o is None or not st:
        counts["deck_plates_no_stations"] = counts.get("deck_plates_no_stations", 0) + 1
        return None
    fp = _FramePlates(str(getattr(m, "id", "")), p, (float(o[0]), float(o[1])),
                     float(getattr(m, "heading_deg", 0.0) or 0.0), st)
    if len({fp.band_of_ll(*q) for q in st}) < len(p):
        counts["deck_plates_unseated"] = counts.get("deck_plates_unseated", 0) + 1
        return None
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
    out = []
    for k in range(len(fp.plates)):
        mine = [r for r in read if fp.band_of_ll(r[0], r[1]) == k]
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
        for k, (dk, (la, lo, sz)) in enumerate(seats):
            y0 = float(sz) - (zero + dk)
            a2 = _dc.replace(
                a, lat=la, lon=lo, surface_z=float(sz), y_zero=y0,
                offset=authored_offset(la, lo, y0, record.lat, record.lon, record.heading),
                reason=(f"deck plate {k + 1}/{len(seats)} on its own end lines: zero "
                        f"{zero + dk:.2f} ({dk:+.2f} off the frame's {zero:.2f}; #2112)"
                        f"; was: {a.reason}"))
            bid = b.body_id if k == 0 else next_id
            next_id += 1 if k else 0
            out.append(named_body(m, b, body_id=bid, anchor=a2, band=fp.plates.band(k),
                                  feet=_in_band(fp, k, b.feet),
                                  geom_pts=_in_band(fp, k, b.geom_pts)))
        counts["deck_plate_split_bodies"] = counts.get("deck_plate_split_bodies", 0) + 1
    counts["deck_plate_placements"] = counts.get("deck_plate_placements", 0) + 1
    return _dc.replace(record, bodies=tuple(out))
