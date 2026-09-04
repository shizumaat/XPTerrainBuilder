"""EXPLAIN a classification verdict (owner 2026-09-04j, deliverable 6):
for a coordinate or a shipped patch's ``shapeID``, the v2 cell(s) there
with the role, the evidence record the verdict used, the source
polygons under it with their own records (``sources.py``), and the
centrelines that touch it.  Pure reporting over ``Classification``;
the CLI is ``python -m auto_patch_v2 explain ICAO --shape N | --at
LAT,LON``.
"""
from __future__ import annotations

import typing as _t
import xml.etree.ElementTree as ET

from shapely.geometry import Point, Polygon

from ..model.airport import Airport
from .evidence import Evidence
from .roles import Cell, Classification

__all__ = ["shape_polygon", "explain_at", "explain_polygon", "render"]


def shape_polygon(patch_path: str, shape_id: int, airport: Airport
                  ) -> tuple[Polygon, dict[str, str]] | None:
    """The ring of way ``shapeID=N`` in a shipped patch (the role-carrying
    way, not its interior rings), in the airport frame, with its tags."""
    root = ET.parse(patch_path).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.iter("node")}
    to_xy, _to_ll = airport.frame.transformers()
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if tags.get("shapeID") != str(shape_id) or "role" not in tags:
            continue
        pts = [nodes[nd.get("ref")] for nd in w.findall("nd")]
        xy = [to_xy(lon, lat) for lat, lon in pts]
        if len(xy) < 3:
            continue
        poly = Polygon(xy)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly, tags
    return None


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.3g}" if abs(v) < 1000 else f"{v:,.0f}"
    return str(v)


def _cell_lines(c: Cell, poly: Polygon, overlap: float | None, cl: Classification,
                ev: Evidence, airport: Airport) -> list[str]:
    out = [f"cell {c.id}: role={c.role} side={c.side} kind={c.kind} ref={c.ref} "
           f"area={poly.area:,.0f} m2" + (f" overlap={overlap:,.0f} m2" if overlap else "")
           + (f" letter={c.code_letter}" if c.code_letter else "")]
    out.append("  evidence: " + ", ".join(f"{k}={_fmt(v)}" for k, v in c.evidence.items()))
    src = {r.id: r for r in cl.sources}
    seen: list[str] = []
    for sid, g in ev.pavement_polys:
        a = g.intersection(poly).area
        if a < 1.0:
            continue
        r = src.get(sid)
        seen.append(sid)
        if r is None:
            out.append(f"  source {sid}: overlap {a:,.0f} m2")
            continue
        out.append(f"  source {sid} [{r.cls}]: overlap {a:,.0f}/{r.area_m2:,.0f} m2, "
                   f"width {r.width_m:.1f} m, road {r.road_m:.0f} m (osm {r.osm_road_m:.0f}, "
                   f"through {r.through_m:.0f}, pieces {r.road_pieces}, aisle {r.aisle_m:.0f}), "
                   f"taxi {r.taxi_m:.0f} m, startups {r.startups}, parking cover "
                   f"{r.parking_cover:.0%}, apron cover {r.apron_cover:.0%}"
                   + (f", desc {r.description!r}" if r.description else ""))
        out.append(f"      -> {r.reason}")
    probe = poly.buffer(1.0)
    taxi = [f"taxi{ch.id}" + ("(network)" if ch.runway_network else "")
            + (f"/{','.join(sorted(ch.names))}" if ch.names else "")
            for ch in ev.taxi_chains if ch.line.intersects(probe)]
    roads = [f"route{ch.id}" for ch in ev.truck_chains if ch.line.intersects(probe)]
    osm = [f"osm{ch.id}" + ("(aisle)" if ch.aisle else "")
           for ch in ev.road_chains if ch.line.intersects(probe)]
    starts = [s.name for s in airport.startups if poly.contains(Point(s.xy))]
    out.append(f"  centrelines: taxi {taxi or '-'}; 1206 {roads or '-'}; OSM roads {osm or '-'}; "
               f"startups inside {starts or '-'}")
    return out


def explain_polygon(poly: Polygon, cl: Classification, ev: Evidence, airport: Airport,
                    min_overlap_m2: float = 25.0) -> list[str]:
    """Every cell overlapping ``poly`` by at least ``min_overlap_m2``."""
    out: list[str] = []
    for c in cl.cells:
        cp = Polygon(c.ring, c.holes)
        if not cp.intersects(poly):
            continue
        a = cp.intersection(poly).area
        if a >= min_overlap_m2:
            out += _cell_lines(c, cp, a, cl, ev, airport)
    return out or ["no cell overlaps the shape by >= %g m2" % min_overlap_m2]


def explain_at(xy: tuple[float, float], cl: Classification, ev: Evidence,
               airport: Airport) -> list[str]:
    """The cell containing ``xy`` (or the nearest one)."""
    p = Point(xy)
    best: tuple[float, Cell, Polygon] | None = None
    for c in cl.cells:
        cp = Polygon(c.ring, c.holes)
        d = cp.distance(p)
        if best is None or d < best[0]:
            best = (d, c, cp)
        if d == 0.0:
            break
    if best is None:
        return ["no cells"]
    d, c, cp = best
    head = [] if d == 0.0 else [f"(no cell contains the point; nearest is {d:.1f} m away)"]
    return head + _cell_lines(c, cp, None, cl, ev, airport)


def render(lines: _t.Iterable[str]) -> str:
    return "\n".join(lines)
