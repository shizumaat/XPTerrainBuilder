"""WHERE DOES GRADED GROUND MEET NATURAL GROUND — the Q4 vote on each
runway's graded zone (#1359; owner RULINGS 2026-10-26q, 2026-10-26w,
2026-10-26z, 2026-10-27a; spec ``docs/specs/multi-source-terrain-spec.md``
§3 Q4, §5, §6.3).

Each runway's zone-2 band (``planar/zones._runway_band``) has four outer
edges: the two sides at the law half-width from the centreline and the two
safety-area ends (``EdgeRead.side``).  Stations every ``q4.station_m`` along each edge carry a
line probe along the outward normal, ``±q4.band_half_m`` about the law edge.
Per station:

* **DEM** — the slope break of the smoothed normal profile
  (``lidar_breaks.slope_breaks``), at least ``q4.slope_change_min_pct``;
* **imagery** — the strongest luminance step of the along-edge median
  profile (``image_provider`` ``graded_edge``; the mowed or graded band's
  edge).

THE RULE.  On a DEM of the lidar class the lidar holds the real fill, so
the image edge is a CHECK (26w): agreement is published, nothing moves.  On
a coarser DEM the image edge SETS the edge (26w): where at least
``q4.edge_agree_frac`` of an edge's reading stations agree within
``q4.agree_m`` of their median, the edge moves to that median — outward
freely (26z), inward only down to the law's standard width and length
(27a: the FAA RSA or ICAO strip for that runway); every place the imagery
asks for less is logged with how much and where.  The answer is ONE move
per edge, to be read at the zone's one derivation site (``planar/overlay.
_runway_records`` → ``planar/zones._runway_band``).  NOT WIRED THERE: the
§8 Q4 bar was missed (image edge within 10 m of the lidar break at 33-70 %
of stations against the 70 % bar, lane ltriang2 2026-10-26), so the
imagery sets nothing yet; ``tools/v2_solve_replay.py --witness`` prints
what this rule would move.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon

from ..law import Law
from ..law.inset_class import dem_source_class
from ..law.tables import FLAT_CLASS_LIDAR, zone2_half_width_m
from . import image_edges_classic  # noqa: F401  (registers the classic method)
from .image_provider import Probes, provider
from .imagery_read import TextureSet
from .lidar_breaks import slope_breaks

__all__ = ["EdgeRead", "EdgeMoves", "read_edges", "edge_moves", "decide_edges", "SIDES"]

SIDES = ("left", "right", "end_a", "end_b")
#: stations per imagery patch (a long diagonal edge pays for its strip);
#: the method reads the whole edge's stations together (a graded edge is a
#: line), so the chunks only bound the patch, never the reading
_CHUNK = 12
#: a road centreline's half-width when a probe is tested against it
_ROAD_HALF_M = 4.0
#: the pavement a probe must clear (the zone yields to pavement: its edge
#: there is the pavement's, and both witnesses read the pavement edge)
_PAVE_CLEAR_M = 5.0


def _pavement(airport) -> "shapely.Geometry":
    """The layout's pavement (apt.dat runways and pavements) and the mapped
    road carriageways, as one geometry."""
    parts = []
    for rw in getattr(airport, "runways", ()):
        try:
            parts.append(Polygon(rw.slab_corners))
        except Exception:                      # pragma: no cover - degenerate
            pass
    for pv in getattr(airport, "pavements", ()):
        try:
            parts.append(Polygon(pv.outer, pv.holes).buffer(0))
        except Exception:                      # pragma: no cover - degenerate
            pass
    for w in getattr(airport, "osm_ways", ()):
        if w.tags.get("highway") and len(w.points) >= 2:
            parts.append(LineString(w.points).buffer(_ROAD_HALF_M))
    return shapely.union_all(parts) if parts else Polygon()


@_dc.dataclass(frozen=True)
class EdgeRead:
    """One edge's stations and what each source read there (offsets in
    metres from the law edge, positive outward; ``None`` = abstain)."""

    ref: str
    side: str
    station_s: tuple[float, ...]
    xy: tuple[tuple[float, float], ...]
    dem: tuple[float | None, ...]
    image: tuple[float | None, ...]


@_dc.dataclass(frozen=True)
class EdgeMoves:
    """Per runway ref, the outward move of each edge (metres, ≥ 0), the
    per-edge records and the loud lines."""

    moves: dict[str, tuple[float, float, float, float]]
    records: list[dict]
    lines: list[str]


def _edges_of(a, b, hw: float, la: float, lb: float, step: float):
    """``{side: (stations s, points, outward normals)}`` of one band."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    L = float(np.hypot(*(b - a)))
    u = (b - a) / L
    n = np.array([-u[1], u[0]])
    s = np.arange(-la, L + lb + 1e-9, step)
    out = {"left": (s, a + np.outer(s, u) + n * hw, np.tile(n, (s.size, 1))),
           "right": (s, a + np.outer(s, u) - n * hw, np.tile(-n, (s.size, 1)))}
    w = np.arange(-hw + step / 2, hw, step)
    out["end_a"] = (w, (a - u * la) + np.outer(w, n), np.tile(-u, (w.size, 1)))
    out["end_b"] = (w, (b + u * lb) + np.outer(w, n), np.tile(u, (w.size, 1)))
    return out


def read_edges(airport, law: Law, records: _t.Sequence[tuple],
               textures: TextureSet | None) -> list[EdgeRead]:
    """Every runway band edge's stations, DEM and imagery reads.
    ``records`` are ``planar/overlay._runway_records``' tuples."""
    q = law.tables.terrain_witness.q4
    prov = provider(law.tables.terrain_witness.image.provider)
    byid = {r.id: r for r in getattr(airport, "runways", ())}
    pave = _pavement(airport).buffer(_PAVE_CLEAR_M)
    shapely.prepare(pave)
    offs = np.arange(-q.band_half_m, q.band_half_m + 1e-9, 1.0)
    ioffs = np.arange(-q.band_half_m, q.band_half_m + 1e-9, q.m_per_px)
    out: list[EdgeRead] = []
    for rec in records:
        ref, a, b = rec[0], rec[1], rec[2]
        rw = byid.get(ref)
        if rw is None:
            continue
        ins = int(rec[6]) if len(rec) >= 7 else 0
        hw = zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter, ins)
        if not hw or hw <= 0:
            continue
        la = float(rec[4]) if len(rec) >= 6 and rec[4] is not None else None
        lb = float(rec[5]) if len(rec) >= 6 and rec[5] is not None else None
        if la is None or lb is None:
            from ..law.tables import runway_safety_area_length_m
            rsa = runway_safety_area_length_m(law, rw.code_number, rw.code_letter, ins)
            la, lb = (rsa, rsa) if la is None else (la, lb)
        for side, (s, xy, nrm) in _edges_of(a, b, hw, la, lb, q.station_m).items():
            if not s.size:
                continue
            # a probe that crosses pavement abstains for both witnesses
            clear = ~shapely.intersects(pave, shapely.linestrings(
                [[(x - nx * q.band_half_m, y - ny * q.band_half_m),
                  (x + nx * q.band_half_m, y + ny * q.band_half_m)]
                 for (x, y), (nx, ny) in zip(xy, nrm, strict=True)]))
            dem_at, _chg = slope_breaks(airport.dem, xy, nrm, offs, q.along_half_m,
                                        q.smooth_m, q.slope_change_min_pct)
            dem_at = [d if c else None for d, c in zip(dem_at, clear, strict=True)]
            img: list[float | None] = [None] * s.size
            if textures is not None and len(textures):
                img = _image_reads(airport, textures, prov, xy, nrm, ioffs, q, clear)
            out.append(EdgeRead(ref, side, tuple(float(v) for v in s),
                                tuple((float(x), float(y)) for x, y in xy),
                                tuple(dem_at), tuple(img)))
    return out


def _image_reads(airport, textures, prov, xy, nrm, ioffs, q, clear) -> list[float | None]:
    """The image edge at every clear station: the textures are resampled
    in patches of ``_CHUNK`` stations and stitched into one strip patch per
    edge, then the method reads all the edge's clear stations at once."""
    img: list[float | None] = [None] * len(xy)
    sel = [i for i in range(len(xy)) if clear[i]]
    if not sel:
        return img
    reach = q.band_half_m + q.along_half_m + 2.0
    pts = xy[sel]
    lo = pts.min(axis=0) - reach
    hi = pts.max(axis=0) + reach
    patch = textures.patch(airport.frame.crs, lo[0], lo[1], hi[0], hi[1], q.m_per_px,
                           corridor=(tuple(xy[0]), tuple(xy[-1]), reach))
    if patch is None:
        return img
    ev = prov.edges(patch, Probes(pts, nrm[sel], ioffs, q.along_half_m), "graded_edge")
    for i, e in zip(sel, ev, strict=True):
        img[i] = e.offset_m
    return img


def _landmark(rw, side: str, s0: float, s1: float) -> str:
    """Where an edge stretch is, by runway end (the owner reads by landmark)."""
    e0, e1 = rw.ends[0].name, rw.ends[1].name
    if side == "end_a":
        return f"across the safety-area end beyond RWY {e0}'s end"
    if side == "end_b":
        return f"across the safety-area end beyond RWY {e1}'s end"
    hand = "left" if side == "left" else "right"
    return (f"the {hand} side of RWY {e0}/{e1} looking from the {e0} end, "
            f"{s0:.0f}–{s1:.0f} m from the {e0} end")


def edge_moves(airport, law: Law, records: _t.Sequence[tuple],
               textures: TextureSet | None) -> EdgeMoves:
    """THE RULE (module docstring) over every runway band."""
    reads = read_edges(airport, law, records, textures) if textures is not None else []
    return decide_edges(airport, law, reads)


def decide_edges(airport, law: Law, reads: _t.Sequence[EdgeRead]) -> EdgeMoves:
    """THE RULE on edge reads already taken (module docstring)."""
    q = law.tables.terrain_witness.q4
    try:
        klass = dem_source_class(airport.dem, law)[0]
    except Exception:                          # pragma: no cover - fixtures
        klass = None
    sets = klass != FLAT_CLASS_LIDAR
    byid = {r.id: r for r in getattr(airport, "runways", ())}
    moves: dict[str, list[float]] = {}
    recs: list[dict] = []
    lines: list[str] = []
    for er in reads:
        img = [v for v in er.image if v is not None]
        agree = [abs(i - d) <= q.agree_m for i, d in zip(er.image, er.dem, strict=True)
                 if i is not None and d is not None]
        med = float(np.median(img)) if img else None
        near = sum(1 for v in img if abs(v - med) <= q.agree_m) if img else 0
        consistent = bool(img) and near >= q.edge_agree_frac * len(img)
        ask = med if consistent else None
        # 26w: the imagery SETS the edge on a coarse DEM; 26z: in or out;
        # 27a: never inside the standard width or length
        move = max(0.0, ask) if (ask is not None and sets) else 0.0
        rw = byid[er.ref]
        rec = {"question": "q4", "runway": er.ref, "side": er.side, "dem_class": klass,
               "role": "sets" if sets else "check", "stations": len(er.station_s),
               "image_read": len(img), "dem_read": sum(1 for d in er.dem if d is not None),
               "image_median_m": None if med is None else round(med, 2),
               "consistent": consistent,
               "agree_with_dem": None if not agree else round(sum(agree) / len(agree), 3),
               "move_m": round(move, 2)}
        recs.append(rec)
        moves.setdefault(er.ref, [0.0, 0.0, 0.0, 0.0])[SIDES.index(er.side)] = move
        where = _landmark(rw, er.side, er.station_s[0], er.station_s[-1])
        if sets and ask is not None and ask < 0.0:
            rec["narrower_asked_m"] = round(-ask, 2)
            lines.append(f"[witness] {airport.icao} Q4 (#1359, RULINGS 2026-10-27a): the imagery "
                         f"shows the graded edge {-ask:.1f} m inside the standard width "
                         f"at {where}; "
                         f"kept at the standard width")
        elif move > 0.0:
            lines.append(f"[witness] {airport.icao} Q4 (#1359, RULINGS 2026-10-26w/26z): the "
                         f"graded zone widens {move:.1f} m to the imagery edge at {where} "
                         f"({near}/{len(img)} stations agree; DEM {klass or 'unknown'})")
    return EdgeMoves({k: tuple(v) for k, v in moves.items()}, recs, lines)
