"""The spatial index beside the map, and the GeoJSON view.

``PlanarIndex`` keeps an STRtree over face polygons (the producers'
cached geometry — the map itself stays plain data); ``to_geojson`` writes
faces and breaklines in lat/lon for viewing (QGIS, geojson.io).
"""
from __future__ import annotations

import json

import numpy as np
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..model.frame import Frame
from ..model.planar import PlanarMap

__all__ = ["PlanarIndex", "face_polygon", "to_geojson"]


def _cycle_xy(pm: PlanarMap, cycle: tuple[int, ...]) -> list[tuple[float, float]]:
    """The vertex coordinates of an edge cycle, in walking order."""
    out: list[tuple[float, float]] = []
    prev: int | None = None
    for i, eid in enumerate(cycle):
        e = pm.edges[eid]
        if prev is None:
            nxt = pm.edges[cycle[(i + 1) % len(cycle)]]
            start = e.a if e.b in (nxt.a, nxt.b) else e.b
            out.append(pm.vertices[start].xy)
            prev = e.b if start == e.a else e.a
        else:
            prev = e.b if prev == e.a else e.a
        out.append(pm.vertices[prev].xy)
    return out


def face_polygon(pm: PlanarMap, fid: int) -> Polygon:
    """The face as a shapely polygon (frame metres)."""
    f = pm.faces[fid]
    return Polygon(_cycle_xy(pm, f.ring), [_cycle_xy(pm, h) for h in f.holes])


class PlanarIndex:
    """STRtree over the faces."""

    def __init__(self, pm: PlanarMap) -> None:
        self.pm = pm
        self.ids = list(pm.faces)
        self.polys = [face_polygon(pm, f) for f in self.ids]
        self.tree = STRtree(self.polys) if self.polys else None

    def faces_at(self, x: float, y: float) -> tuple[int, ...]:
        """Face ids containing the point."""
        if self.tree is None:
            return ()
        from shapely.geometry import Point
        p = Point(x, y)
        return tuple(self.ids[int(j)] for j in self.tree.query(p, predicate="intersects"))

    def faces_intersecting(self, geom) -> tuple[int, ...]:
        if self.tree is None:
            return ()
        return tuple(self.ids[int(j)] for j in self.tree.query(geom, predicate="intersects"))


def to_geojson(pm: PlanarMap, frame: Frame) -> tuple[dict, dict]:
    """``(faces, breaklines)`` FeatureCollections in WGS84."""
    from pyproj import Transformer
    inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)
    xs = np.array([v.xy[0] for v in pm.vertices.values()])
    ys = np.array([v.xy[1] for v in pm.vertices.values()])
    lon, lat = inv.transform(xs, ys)
    ll = {vid: (float(lon[i]), float(lat[i])) for i, vid in enumerate(pm.vertices)}

    def cycle_ll(cycle: tuple[int, ...]) -> list[list[float]]:
        pts = _cycle_vids(pm, cycle)
        return [[round(ll[v][0], 8), round(ll[v][1], 8)] for v in pts + [pts[0]]]

    faces = {"type": "FeatureCollection", "features": []}
    for f in pm.faces.values():
        faces["features"].append({
            "type": "Feature",
            "properties": {"id": f.id, "role": f.role, "ref": f.ref,
                           "side": f.side, "code_number": f.code_number,
                           "code_letter": f.code_letter},
            "geometry": {"type": "Polygon",
                         "coordinates": [cycle_ll(f.ring)] + [cycle_ll(h) for h in f.holes]}})
    lines = {"type": "FeatureCollection", "features": []}
    for b in pm.breaklines.values():
        vs = b.vertices(pm)
        lines["features"].append({
            "type": "Feature",
            "properties": {"id": b.id, "kind": b.kind, "ref": b.ref,
                           "edges": len(b.edges)},
            "geometry": {"type": "LineString",
                         "coordinates": [[round(ll[v][0], 8), round(ll[v][1], 8)]
                                         for v in vs]}})
    return faces, lines


def _cycle_vids(pm: PlanarMap, cycle: tuple[int, ...]) -> list[int]:
    out: list[int] = []
    prev: int | None = None
    for i, eid in enumerate(cycle):
        e = pm.edges[eid]
        if prev is None:
            nxt = pm.edges[cycle[(i + 1) % len(cycle)]]
            start = e.a if e.b in (nxt.a, nxt.b) else e.b
            out.append(start)
            prev = e.b if start == e.a else e.a
        else:
            prev = e.b if prev == e.a else e.a
        out.append(prev)
    return out[:-1] if len(out) > 1 and out[0] == out[-1] else out


def dump_geojson(path: str, collection: dict) -> None:
    with open(path, "w") as fh:
        json.dump(collection, fh)

