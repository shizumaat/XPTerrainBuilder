"""THE ROAD TERRACE'S SECOND WITNESS (owner RULINGS 2026-10-03b, #100) —
REPORT ONLY this round: no rule reads it.

"A boundary-fence / wall object authored along the road at one elevation
is the pack author declaring that terrace; where present it confirms the
level and marks the wall line."  For every pack LINE object running along
a BORDERED run of a mapped-road ribbon (``PlanarMap.road_terrace``'s
``foot``), one sidecar record ``road_terrace_witness``:

* the object (its def path / resource and kind),
* where it runs: its first / last point and length, and the share of its
  stations standing within ``[service] retaining_wall_reach_m`` of a
  bordered ribbon vertex (the SAME reach and the SAME along-share
  ``retaining_wall_along_fraction`` the §47 retaining-wall reader uses —
  one meaning of "runs along a road"),
* the elevation the object stands at — a DSF FACADE carries no authored
  height in the DSF (X-Plane seats it on the terrain), so the record gives
  the DEM along it (min / max / at its first node) and, for an OBJ8 wall-
  class component, its own base and solid height,
* the pavement level the terrace gave the road beside it (the solved z of
  those bordered vertices: mean / min / max) and the AGREEMENT in metres
  (``road_mean - dem_min``, ``road_mean - dem_at_first``) — the reading
  the next round rules on.

Sources: the pack DSF's facades whose def path names a fence or a wall
(``airport/dsf.read_dump``, the build's own dump) and the wall-class OBJ8
components (``classify/retaining_wall.wall_class_components``, the one
classifier; it excludes fences by name, so fences come from the facades).
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["terrace_witness", "WITNESS_WORDS"]

#: def-path words that name a line object as a fence / wall (a facade is
#: read only when its basename carries one)
WITNESS_WORDS = ("fence", "wall")
#: station spacing along a line object (m)
_STEP_M = 5.0


def _lines_from_dump(dump_path: str | None, to_xy) -> list[tuple[str, str, list]]:
    if not dump_path:
        return []
    import os
    if not os.path.isfile(dump_path):
        return []
    from ..airport import dsf as _dsf

    def accept(p: str) -> bool:
        b = p.replace("\\", "/").rsplit("/", 1)[-1].lower()
        return b.endswith(".fac") and any(w in b for w in WITNESS_WORDS)
    dump = _dsf.read_dump(dump_path, accept)
    out = []
    for poly in dump.polygons:
        if not accept(poly.def_path):
            continue
        for w in poly.windings:
            pts = [to_xy(lon, lat) for lon, lat in w]
            if len(pts) >= 2:
                out.append((poly.def_path, "facade", pts))
    return out


def _lines_from_walls(airport, cfg) -> list[tuple[str, str, list, float]]:
    from ..classify.retaining_wall import wall_class_components
    out = []
    for c in wall_class_components(airport, cfg):
        for g in c.pieces:
            rect = g.minimum_rotated_rectangle
            cs = list(rect.exterior.coords)
            if len(cs) < 5:
                continue
            e = sorted(((cs[i], cs[i + 1]) for i in range(4)),
                       key=lambda ab: -math.dist(*ab))
            (a0, a1), (b0, b1) = e[0], e[1]
            mid = [((a0[0] + b1[0]) / 2, (a0[1] + b1[1]) / 2),
                   ((a1[0] + b0[0]) / 2, (a1[1] + b0[1]) / 2)]
            out.append((f"{c.resource}#comp{c.comp}", "obj8_wall", mid, c.height_m))
    return out


def terrace_witness(pm, airport, z: _t.Sequence[float] | None, rules,
                    dump_path: str | None = None) -> list[dict[str, _t.Any]]:
    """The ``road_terrace_witness`` records (module docstring).  Empty
    before a solve or when no ribbon run is bordered."""
    terr = getattr(pm, "road_terrace", None) or {}
    foot = terr.get("foot") or {}
    if not z or not foot or airport is None:
        return []
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    from ..model.planar import is_osm_ribbon_ref
    cfg = rules.service
    reach = float(cfg.retaining_wall_reach_m)
    share_min = float(cfg.retaining_wall_along_fraction)
    # the BORDERED RUN as ribbon ring edges whose two ends are both bordered
    # (a ribbon's long kerb edges carry no vertex between their ends)
    segs: list[tuple[int, int]] = []
    for f in pm.faces.values():
        if not is_osm_ribbon_ref(f.ref):
            continue
        ring = list(pm.ring_vertices(f.ring))
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if a in foot and b in foot and a != b:
                segs.append((a, b))
    if not segs:
        return []
    tree = STRtree([LineString([pm.vertices[a].xy, pm.vertices[b].xy]) for a, b in segs])
    to_xy = airport.frame.entry()
    to_ll = airport.frame.transformers()[1]
    dem = getattr(airport, "dem", None)
    cands: list[tuple[str, str, list, float | None]] = [
        (p, k, pts, None) for p, k, pts in _lines_from_dump(dump_path, to_xy)]
    cands.extend(_lines_from_walls(airport, cfg))
    out: list[dict[str, _t.Any]] = []
    for path, kind, pts, height in cands:
        ln = LineString(pts)
        if ln.length <= 0.0:
            continue
        n = max(2, int(ln.length // _STEP_M) + 1)
        near: set[int] = set()
        hits = 0
        dems: list[float] = []
        for i in range(n):
            q = ln.interpolate(i / (n - 1), normalized=True)
            if dem is not None:
                dems.append(float(dem.z(q.x, q.y)))
            js = tree.query(Point(q.x, q.y), predicate="dwithin", distance=reach)
            for j in js:
                near.update(segs[int(j)])
            if len(js):
                hits += 1
        share = hits / n
        if share < share_min or not near:
            continue
        zs = [float(z[v]) for v in near]
        road = sum(zs) / len(zs)
        rec: dict[str, _t.Any] = {
            "object": path, "kind": kind,
            "from": list(to_ll(*pts[0])), "to": list(to_ll(*pts[-1])),
            "length_m": round(ln.length, 1), "along_share": round(share, 3),
            "road_m": {"mean": round(road, 2), "min": round(min(zs), 2),
                       "max": round(max(zs), 2), "vertices": len(zs)},
            "refs": sorted({foot[v][3] for v in near}),
        }
        if dems:
            rec["dem_m"] = {"min": round(min(dems), 2), "max": round(max(dems), 2),
                            "first": round(dems[0], 2)}
            rec["agreement_m"] = {"road_minus_dem_min": round(road - min(dems), 2),
                                  "road_minus_dem_first": round(road - dems[0], 2)}
        if height is not None:
            rec["height_m"] = round(float(height), 2)
        out.append(rec)
    return out
