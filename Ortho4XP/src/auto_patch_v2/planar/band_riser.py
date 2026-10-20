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

from ..geom.proportions import inscribed_width_m
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


def riser_geometry(ribs, regions, air, rim_band: float, law: Law, keep_out=None):
    """The band ground within one weld spacing of the ribbons ``ribs``,
    inside a runway / taxi zone region, off the finished airside ``air`` by
    ``rim_band`` and off every other cell ``keep_out`` (a tunnel ramp or
    trench, a lot: round 3, KLAX 33.94033, -118.39618 — riser lines noded
    through a tunnel trench re-cut it, and the roads inside it surfaced as
    ribbons 3 m under the band).  ``None`` where there is none."""
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
    if keep_out is not None and not keep_out.is_empty:
        riser = riser.difference(keep_out)
    keep_off = air.buffer(float(rim_band), **_MITRE) if air is not None else None
    if keep_off is not None:
        riser = riser.difference(keep_off)
    # THE BAND LEFT NARROWER THAN A STRIP beside the riser is the riser's
    # too (a median between two carriageways, a sliver between the riser
    # and a zone edge): a second line within a strip width of the first
    # would mint a hairline and an island the solve decouples from both
    # (KBUR iteration 1: hairline_pair 333 -> 445, 82 strip_seam_tear rows
    # off such islands).  No new line is drawn: the part's own ring is
    # already noded.  A part reaching the airside keep-off stays band: its
    # riser line would end on the rim.
    w_strip = float(law.tables.emit.terrace.strip_min_width_m)
    rest = zone_u.difference(rib_u).difference(riser)
    for p in shapely.get_parts(rest):
        if p.geom_type != "Polygon" or p.is_empty or p.area <= 0.0:
            continue
        if p.distance(riser) > 1e-6 or (keep_off is not None
                                         and p.distance(keep_off) <= 1e-6):
            continue                 # never toward the finished airside (30aa)
        per = p.length
        if per > 0.0 and 2.0 * p.area / per < w_strip \
                and inscribed_width_m(p) < w_strip:
            riser = riser.union(p)
    # A MEDIAN IS ROAD GROUND, NOT A WALL (round 3, KLAX 33.94033,
    # -118.39618: a riser between two carriageways 1.5 m apart carried a band
    # vertex the cut decoupled from both roads; it stood 3 m over them and the
    # census read the spike as road-to-road steps, `pavement_over_road_cap`
    # 0 -> 5).  The band ground within one weld spacing of TWO different
    # mapped roads yields to them: it stays zone, a sliver
    # ``overlay.dissolve_sliver_zones`` gives to a ribbon (as #988's median).
    median = _median(ribs, w)
    if median is not None and not riser.is_empty:
        riser = riser.difference(median)
        riser = unary_union([q for q in shapely.get_parts(riser)
                             if q.geom_type == "Polygon" and q.area >= w * w])
    riser = shapely.set_precision(riser, 0.0)
    return None if riser.is_empty or riser.area <= 0.0 else riser


def _median(ribs, w: float):
    """The overlap of the one-weld-spacing reaches of two DIFFERENT mapped
    roads (a ribbon's ref less its ``#k`` piece suffix), or ``None``."""
    from shapely.strtree import STRtree
    reach = [(str(r.ref).split("#", 1)[0], r.polygon.buffer(w, **_MITRE))
             for r in ribs if not r.polygon.is_empty]
    if len(reach) < 2:
        return None
    tree = STRtree([g for _r, g in reach])
    parts = []
    for i, (ra, ga) in enumerate(reach):
        for j in tree.query(ga, predicate="intersects"):
            j = int(j)
            if j > i and reach[j][0] != ra:
                parts.append(ga.intersection(reach[j][1]))
    m = unary_union(parts) if parts else None
    return None if m is None or m.is_empty else m


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
