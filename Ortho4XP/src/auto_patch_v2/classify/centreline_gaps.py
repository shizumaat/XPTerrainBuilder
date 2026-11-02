"""THE MISSED-PAVEMENT DETECTOR — a taxi centreline over ground the
classification holds no pavement on (owner RULINGS 2026-10-30e, #1686).

The apt.dat 1202 taxi network is the pack's own statement of where an
aircraft taxis.  Where a taxiway edge of it runs over ground no standing
classified cell covers, a pavement source was missed: a pack page
misread (KIND: ``ConcreteLight.pol`` read as decorative, 23.4 km of
taxiway graded as raw ground), a pack that authors no pavement for that
stretch, or a gap sheet's piece standing where a taxiway should.  This
module NAMES each such gap — its length, its site, and the pack page that
covers it (a §60 gap sheet) when one does; a gap no pack page covers is
where Global Airports' pavement is the source still to pull.

A READING, never a law: nothing downstream reads the report, and the
classification is not changed by it.

"Held" is every classified cell the stage-1 base map stands on — every
cell less the §53 gap pieces and the pad roads (the predicate of
``pipeline/stage_one_map.gap_free``), which follow in the last stage and
never claim zone ground.  The runway edges of the network are not read:
a runway is pavement by its own row-100 record.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from ..model.planar import is_gap_ref

__all__ = ["CentrelineGap", "GapReport", "centreline_pavement_gaps"]

#: a centreline within this of a held cell is on it (the slice's own
#: snapping and the cell-edge tolerance are below a metre)
ON_TOL_M = 1.0
#: a stretch shorter than this is a junction corner, not a missing taxiway
MIN_GAP_M = 10.0


@_dc.dataclass(frozen=True)
class CentrelineGap:
    """One connected stretch of taxi centreline over unheld ground."""

    length_m: float
    #: the stretch's midpoint, ``(lat, lon)``
    site: tuple[float, float]
    #: the 1202 edge names the stretch runs along (``""`` for unnamed)
    names: tuple[str, ...]
    #: descriptions of the gap sheets covering any part of it
    sheet_pages: tuple[str, ...]


@_dc.dataclass(frozen=True)
class GapReport:
    """Every gap, longest first, and the network it was read over."""

    taxi_m: float
    gap_m: float
    gaps: tuple[CentrelineGap, ...]

    def lines(self, icao: str, top: int = 8) -> list[str]:
        """The build log's say-lines: one summary, then the longest gaps."""
        head = (f"[{icao}] taxi centreline over unpaved ground: "
                f"{self.gap_m:.0f} m of {self.taxi_m:.0f} m")
        if not self.gaps:
            return [head + " (RULINGS 2026-10-30e)"]
        paged = sum(g.length_m for g in self.gaps if g.sheet_pages)
        out = [f"{head} in {len(self.gaps)} stretch(es) ({paged:.0f} m under "
               f"a pack gap sheet, {self.gap_m - paged:.0f} m under no pack "
               f"page) — WARNING: a pavement source is missing "
               f"(RULINGS 2026-10-30e)"]
        for g in self.gaps[:top]:
            where = (f"pack page {', '.join(g.sheet_pages)} covers it (a gap "
                     f"sheet)" if g.sheet_pages else
                     "no pack page covers it: Global pavement is the source")
            out.append(f"  {g.length_m:.0f} m at {g.site[0]:.6f}, "
                       f"{g.site[1]:.6f} (taxiway {'/'.join(g.names) or '?'}): "
                       f"{where}")
        return out

    def record(self) -> dict[str, _t.Any]:
        """The report as JSON-ready data."""
        return {"taxi_m": round(self.taxi_m, 1), "gap_m": round(self.gap_m, 1),
                "gaps": [{"length_m": round(g.length_m, 1),
                          "lat": round(g.site[0], 7), "lon": round(g.site[1], 7),
                          "names": list(g.names),
                          "sheet_pages": list(g.sheet_pages)}
                         for g in self.gaps]}


def _held_near(cells, lines) -> Polygon:
    """The union, grown by :data:`ON_TOL_M`, of the cells the stage-1
    base map stands on that lie within :data:`ON_TOL_M` of ``lines``."""
    polys = []
    for c in cells:
        if is_gap_ref(getattr(c, "ref", "")) or \
                (getattr(c, "evidence", None) or {}).get("pad_road"):
            continue
        if len(c.ring) < 3:
            continue
        p = Polygon(c.ring, [h for h in c.holes if len(h) >= 3])
        polys.append(p if p.is_valid else p.buffer(0))
    if not polys:
        return Polygon()
    near = STRtree(polys).query(lines, predicate="dwithin", distance=ON_TOL_M)
    hit = sorted(set(int(i) for i in near[1]))
    return unary_union([polys[i] for i in hit]).buffer(ON_TOL_M) if hit \
        else Polygon()


def _parts(g) -> list[LineString]:
    if g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    return [q for q in getattr(g, "geoms", ()) if q.geom_type == "LineString"]


def centreline_pavement_gaps(airport, cells) -> GapReport:
    """The taxi centreline of ``airport``'s 1202 network (runway edges
    excluded) over ground no held cell of ``cells`` covers."""
    xy = {nid: n.xy for nid, n in airport.taxi_nodes.items()}
    edges = [(LineString([xy[e.a], xy[e.b]]), e.name or "")
             for e in airport.taxi_edges
             if not e.is_runway and e.a in xy and e.b in xy and xy[e.a] != xy[e.b]]
    taxi_m = float(sum(ln.length for ln, _n in edges))
    if not edges:
        return GapReport(0.0, 0.0, ())
    lines = [ln for ln, _n in edges]
    off = unary_union(lines).difference(_held_near(cells, lines))
    merged = linemerge(_parts(off)) if not off.is_empty else off
    sheets = [s for s in getattr(airport, "gap_sheets", ()) if len(s.outer) >= 3]
    sheet_polys = [Polygon(s.outer, [h for h in s.holes if len(h) >= 3]).buffer(0)
                   for s in sheets]
    sheet_tree = STRtree(sheet_polys) if sheets else None
    edge_tree = STRtree(lines)
    to_ll = airport.frame.transformers()[1]
    gaps: list[CentrelineGap] = []
    for part in _parts(merged):
        if part.length < MIN_GAP_M:
            continue
        mid = part.interpolate(0.5, normalized=True)
        lat, lon = to_ll(mid.x, mid.y)
        names = sorted({edges[int(i)][1] for i in edge_tree.query(
            mid, predicate="dwithin", distance=ON_TOL_M)})
        pages = sorted({sheets[int(i)].description or sheets[int(i)].id
                        for i in sheet_tree.query(part, predicate="intersects")}
                       ) if sheet_tree is not None else []
        gaps.append(CentrelineGap(float(part.length), (float(lat), float(lon)),
                                  tuple(names), tuple(pages)))
    gaps.sort(key=lambda g: -g.length_m)
    return GapReport(taxi_m, float(sum(g.length_m for g in gaps)), tuple(gaps))
