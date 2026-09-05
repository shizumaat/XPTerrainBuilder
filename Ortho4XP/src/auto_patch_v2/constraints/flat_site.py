"""THE FLAT-SITE DATUM generator (RULINGS 2026-09-05k-2, option (b);
spec ``flat-site-datum-spec.md`` §3.2; ``law/flat_site.toml [datum]``).

At a flat site (``Airport.flat_site`` a ``flat_candidate`` or a
``flat_declared`` verdict with a datum) every GOVERNED vertex inside the
verdict's region — pavement ∪ boundary ⊕ margin — whose faces are not
of the RUNWAY family carries one soft ``Linear`` row ``z_i = Z0`` in its
OWN preference group ``<[datum] preference>:<vertex>`` (``flat_datum:
1234``, exactly as the seam's ``seam:<vertex>``): the assembler gives one
slack column per GROUP, so a shared group would let every row relax by
the largest single relief for free (measured OTHH 2026-09-05: one bare
``flat_datum`` group escalated 5.1 m at a tunnel mouth and freed all
15,687 rows); the prefix before ``:`` carries the weight.  Ranked below
the law ladder and above the seam, so the hard law rows outrank it (a
real gradient at a spread-< 5 m site still fans lawfully from the pinned
thresholds — v1's behaviour) and the seam's DEM values yield to it.  The
runway family keeps its CIFP pins (``runway_pins_hard``, 08-25: the datum
NEVER pins pavement); no hard row is minted anywhere.  A vertex the
runway family shares with a taxiway is the runway's (``senior_role``)
and gets no row.

A not-flat, lidar-credible or no-data site mints nothing (CYXY: zero
rows, a byte-identical patch).
"""
from __future__ import annotations

from shapely import contains_xy
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import flat_datum_group, role_family
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["flat_datum", "region_geometry"]

GEN = "flat_site"
RULING = "flat-site datum preference (RULINGS 2026-09-05k-2 (b); law/flat_site.toml [datum])"


def region_geometry(region) -> Polygon | MultiPolygon | None:
    """The verdict's ``(outer, holes)`` rings as one shapely geometry."""
    polys = []
    for outer, holes in region or ():
        if len(outer) < 3:
            continue
        p = Polygon(list(outer), [list(h) for h in holes if len(h) >= 3])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    u = unary_union(polys)
    return None if u.is_empty else u


def flat_datum(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One soft ``z = Z0`` row per governed, non-runway vertex inside the
    flat region (module docstring)."""
    fv = airport.flat_site
    if fv is None or not fv.substitutes:
        return []
    geom = region_geometry(fv.region)
    if geom is None:
        return []
    fs = law.tables.flat_site
    vw = view(planar, law)
    group = flat_datum_group(law)
    z0 = float(fv.z0_m)
    runway_v: set[int] = set()
    if fs.datum.runway_pins_hard:
        for fid, f in planar.faces.items():
            if role_family(law, f.role) == "runway":
                runway_v.update(vw.rings[fid])
                for h in vw.holes[fid]:
                    runway_v.update(h)
    cand = sorted(v for v in vw.pavement_vertices if v not in runway_v)
    if not cand:
        return []
    xs = [vw.xy[v][0] for v in cand]
    ys = [vw.xy[v][1] for v in cand]
    inside = contains_xy(geom, xs, ys)
    src = Source(GEN, RULING, (f"verdict:{fv.verdict}", f"source:{fv.source}",
                               f"z0:{z0:.3f}"))
    rows: list[Row] = []
    for v, ok in zip(cand, inside):
        if ok:
            rows.append(Linear(((v, 1.0),), z0, z0, src, f"{group}:{v}", None))
    return rows
