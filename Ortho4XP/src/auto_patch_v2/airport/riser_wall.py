"""THE FILL'S RISERS AS DECLARED WALLS (owner RULINGS 2026-10-20d, 2026-10-27i;
spec ``docs/specs/fill-step-at-road-kerb-spec.md`` §2 (4)-(5)).

A pad fill that runs to its road mints its RISERS at the road's far kerb
(``planar/fill_riser``, at the landing's derivation site): each a strip
``<landing>#strip`` whose geometry and height the landing record carries
(``Registries.landings[ref]["risers"]``).  This module only READS them onto
the map: one ``road_terrace['wall']`` record per riser, of the shape the
pack walls take (``airport/road_ramp.wall_terraces``) —

* ``line`` the riser's ring (every reader reads the wall as a polygon),
* ``upper`` its vertices on the far kerb, ``lower`` its outer vertices,
* ``kerb`` the far-kerb EDGES (``model.planar.drop_edges`` reads them: no
  late station lies on one and no gap piece follows one),
* ``height_m`` the largest predicted kerb level over the DEM, ``retains``
  and ``road_edge`` set —

so the readers that take a wall take this one unchanged: the pair rows
across it are released (``constraints/road_ramp.wall_release``), the
bending is cut (``solve/wall_cut``), the lower side is bounded at the
wall's height (``_wall_step_rows``) and the census is told the step
(``pipeline/publication.wall_terrace_joints``).  Every riser in the map is
a joint.  Nothing here derives a drop."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, MultiLineString, Point, Polygon

from ..law import Law
from ..model.planar import STRIP_SUFFIX, PlanarMap

__all__ = ["riser_walls", "LABEL_PREFIX"]

#: the record label's head: ``fill_riser:<landing ref>#<k>``
LABEL_PREFIX = "fill_riser:"


def _ring_runs(pm: PlanarMap, f) -> list[list[int]]:
    return [list(pm.ring_vertices(c)) for c in (f.ring, *f.holes)]


def _inside(pm: PlanarMap, f) -> Point:
    """A point inside face ``f``."""
    ring = [pm.vertices[v].xy for v in _ring_runs(pm, f)[0]]
    g = Polygon(ring)
    return (g if g.is_valid else g.buffer(0.0)).representative_point()


def riser_walls(pm: PlanarMap, law: Law, counts: dict | None = None
                ) -> list[dict[str, _t.Any]]:
    """One wall record per riser face set of every landing that minted
    risers (module docstring)."""
    lands = getattr(pm.registries, "landings", None) or {}
    recs = {ref: rec["risers"] for ref, rec in lands.items() if rec.get("risers")}
    out: list[dict[str, _t.Any]] = []
    if not recs:
        if counts is not None:
            counts["fill_riser_walls"] = 0
        return out
    tol = float(law.tables.emit.identity.min_distinct_spacing_m)
    V = pm.vertices
    faces: dict[str, list] = {}
    for f in pm.faces.values():
        ref = str(f.ref)
        if ref.endswith(STRIP_SUFFIX) and ref[:-len(STRIP_SUFFIX)] in recs:
            faces.setdefault(ref[:-len(STRIP_SUFFIX)], []).append(f)
    missing = 0
    for ref in sorted(recs):
        for k, r in enumerate(recs[ref]):
            poly = Polygon(r["ring"])
            zone = poly.buffer(tol)
            upper_line = MultiLineString([LineString(c) for c in r["upper"] if len(c) >= 2])
            mine = [f for f in faces.get(ref, ()) if zone.contains(_inside(pm, f))]
            if not mine:
                missing += 1
                continue
            up: list[int] = []
            lo: list[int] = []
            kerb: list[list[int]] = []
            for f in mine:
                for cyc in _ring_runs(pm, f):
                    flags = [upper_line.distance(Point(V[v].xy)) <= tol for v in cyc]
                    for i, v in enumerate(cyc):
                        (up if flags[i] else lo).append(v)
                        j = (i + 1) % len(cyc)
                        if flags[i] and flags[j]:
                            kerb.append([v, cyc[j]])
            up = sorted(set(up))
            lo = sorted(set(lo) - set(up))
            if not up or not lo:
                missing += 1
                continue
            out.append({"line": [tuple(c) for c in r["ring"]],
                        "height_m": float(r["height_m"]),
                        "label": f"{LABEL_PREFIX}{ref}#{k}",
                        "retains": True, "mouth": False, "road_edge": True,
                        "upper": up, "lower": lo, "kerb": kerb,
                        "lots": [], "pairs": []})
    if counts is not None:
        counts["fill_riser_walls"] = len(out)
        counts["fill_riser_unmapped"] = missing
    return out
