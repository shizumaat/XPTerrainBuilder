"""THE BAND'S RISER BESIDE A ROAD INSIDE IT (owner RULINGS 2026-10-19a / 19i
/ 19k, issues #951 / #949; spec ``docs/specs/band-road-wall-joint-spec.md``).

A mapped-road ribbon inside a runway or taxiway safety-area band shares its
kerb with the band (spec-author 30e (4)).  Where the road sits below the
band (19a: "typically cut below"), the band's edge against it is a
retaining wall (19i), not a slope.  The mesh can only build a wall where a
line of BAND-level vertices stands close beside the road-level kerb, so the
band yields a RISER: the strip of it within ``identity.weld_spacing_m`` of
the ribbon, its own face (role ``graded_strip``, the zone's ref plus
``model.planar.RISER_SUFFIX``).  Its kerb side is the ribbon's own kerb
(shared vertices: no second edge beside it, so no hairline — the stand-off
of #988 minted them); its far side is a band line one weld spacing off.
The solve cuts the design energy across the riser (``solve/wall_cut``) and
the pair rows across it are released (``constraints/band_riser``), so the
riser is as steep as one weld spacing allows.

It is cut in the ribbons' own pass (``planar/ribbons._ribbons_pass_c``),
never at the zone derivation site: pass A stays the arrangement WITHOUT the
ribbons, so the airside is identical with and without them (RULINGS
2026-09-30aa rules 2, 9-10), and the riser keeps off the finished airside
by the rim band."""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.ops import unary_union

from ..law import Law
from ..model.band_riser import RISER_SUFFIX

__all__ = ["riser_geometry", "apply_risers", "riser_lines"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)
#: the zone families that are a SAFETY-AREA band (19a: "a runway or
#: taxiway safety-area band"); an apron's zone keeps the 10-03b terrace
_BAND_FAMILIES = ("runway", "taxi")


def _is_band_zone(r) -> bool:
    parts = str(r.ref).split(":")
    return r.source == "zone" and len(parts) > 1 and parts[1] in _BAND_FAMILIES


def riser_geometry(ribs, regions, air, rim_band: float, law: Law):
    """The band ground within one weld spacing of the ribbons ``ribs``,
    inside a runway / taxi zone region, off the finished airside ``air`` by
    ``rim_band``.  ``None`` where there is none."""
    zone = [r.polygon for r in regions if _is_band_zone(r)]
    polys = [r.polygon for r in ribs if not r.polygon.is_empty]
    if not zone or not polys:
        return None
    w = float(law.tables.emit.identity.weld_spacing_m)
    rib_u = unary_union(polys)
    zone_u = unary_union(zone)
    reach = rib_u.buffer(w, **_MITRE)
    if not reach.intersects(zone_u):
        return None
    riser = reach.difference(rib_u).intersection(zone_u)
    if air is not None:
        riser = riser.difference(air.buffer(float(rim_band), **_MITRE))
    riser = shapely.set_precision(riser, 0.0)
    return None if riser.is_empty or riser.area <= 0.0 else riser


def apply_risers(regions, riser):
    """``regions`` with every band zone region split into its riser part(s)
    (ref + ``RISER_SUFFIX``) and the rest."""
    if riser is None:
        return list(regions)
    out = []
    for r in regions:
        if _is_band_zone(r) and r.polygon.intersects(riser):
            for g, ref in ((r.polygon.difference(riser), r.ref),
                           (r.polygon.intersection(riser), r.ref + RISER_SUFFIX)):
                for p in shapely.get_parts(g):
                    if p.geom_type == "Polygon" and p.area > 0.0:
                        out.append(_dc.replace(r, polygon=p, ref=ref))
            continue
        out.append(r)
    return out


def riser_lines(riser) -> list:
    """The riser's rings as lines for the noding."""
    from shapely.geometry import LineString
    out = []
    for p in shapely.get_parts(riser):
        if p.geom_type != "Polygon":
            continue
        for ring in (p.exterior, *p.interiors):
            if len(ring.coords) >= 2:
                out.append(LineString(ring.coords))
    return out
