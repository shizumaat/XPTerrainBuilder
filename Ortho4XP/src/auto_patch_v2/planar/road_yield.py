"""THE ROAD BESIDE THE BAND TRUMPS THE BAND (owner 2026-10-19, issue #944).

Owner, verbatim: "if a road runs next to airside ... then we cannot have
our adjacent ground graded strip go into it ... The road trumps adjacent
ground, and per our existing rules if there's no gap it's welded to the
airside, if there's a gap, then it's graded groundside road and there may
be a step/retaining wall between it and the airside."

Measured at the test site (KBUR, 34.196709421, -118.348961910): a 7-lane
secondary road runs beside an apron; its centreline lies 6.7 m outside the
taxiway band's outer edge, so the band reached about 5.5 m into the road's
24.5 m carriageway and graded the road's outer lanes with the strip.
Nothing trimmed it: §19 rule 2 needs a crest, the band subtracts groundside
CELLS only, and a road the patch does not ribbon has no cell.

THE WITNESS IS THE ZONE ENVELOPE, and it keeps this rule clear of the
standing in-band law.  A road whose centreline runs INSIDE an
adjacent-ground band is ribboned by the patch (``classify/ribbon_mint``'s
extent is the same envelope) and grades WITH the zone (RULINGS 2026-09-13ar,
2026-09-29r, owner 2026-09-30b) -- this module does not touch it.  A road
whose centreline runs OUTSIDE every band is a groundside road the core mesh
owns: the band must not enter its carriageway. So the part of each such
centreline outside the envelope is grown by the road's MAPPED half-width
(``airport/road_ways.ribbon_half_width_m``, #949: the way's ``width``, else
``lanes`` x ``tunnel.lane_width_m``; never narrower than the core's
``road_profile.lane_width_m``; the ribbon a patch road gets) plus the stand-
off every groundside cell gets, and that is subtracted from the band at the
single zone derivation site (``planar/zones.zone_regions``,
:func:`road_cut_pieces`). The gap between the band's new edge and the road
terraces, exactly as against a groundside cell (groundside terrace law).

A ROAD THROUGH ZONE 2 IS CUT OUT OF IT TOO (owner RULINGS 2026-10-20c, 39:
"Roads through outer band follow their own ground ... Band stops at road
edge determined by lanes or drawn edge, whichever is larger"; #951).  The
same construction with the INNER bands (the zone-1 lips) as the envelope:
every carriageway whose centreline runs outside the lips is cut from zone 2
by its half-width plus the stand-off (:func:`road_cut_pieces`), and each
piece clipped to the band it cuts is a :class:`BandYield` — the record
``planar/build`` turns into ``PlanarMap.road_yield`` and the DEM shadow
(``planar/road_shadow``) reads."""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import LineString, Polygon

from ..airport.road_ways import ribbon_half_width_m, road_ways
from ..law import Law
from ..model.road_yield import RoadYield

__all__ = ["road_carriageways", "road_cut_pieces", "BandYield",
           "road_yield_records", "road_cut_outlines", "road_cut_ground"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


@_dc.dataclass(frozen=True)
class BandYield:
    """One carriageway's cut out of the bands: the yielded ``polygon``, the
    carriageway's ``axis`` there and ``half`` (its half-width).  A cut out
    of one band's zone 2 (``through``) is clipped to that band's zone-2
    extent and carries the band's key — the family, code number / letter
    and, for a runway band, its runway; a road BESIDE the bands (#944)
    carries none."""

    polygon: Polygon
    axis: LineString
    half: float
    family: str | None = None
    code_number: int | None = None
    code_letter: str | None = None
    runway_ref: str | None = None
    through: bool = False

    def footprint(self) -> Polygon:
        """The carriageway itself: the axis grown (flat ends) by the
        half-width — the road's edge by its lanes."""
        return self.axis.buffer(self.half, cap_style="flat", **_MITRE)


def road_carriageways(osm_ways, law: Law,
                      highways=None) -> tuple[tuple[LineString, float], ...]:
    """Every at-grade mapped road (``airport/road_ways``) of a ribbon class
    (``highways``: ``rules.osm_roads.ribbon_highways``; ``None`` reads the
    shipped table) as ``(centreline, carriageway half-width)``."""
    if highways is None:
        from ..classify.rules import load_rules
        orr = load_rules().osm_roads
        if not orr.enabled:
            return ()
        highways = orr.ribbon_highways
    allowed = set(highways)
    out: list[tuple[LineString, float]] = []
    for w, line in road_ways(osm_ways):
        tags = w.tags or {}
        if tags.get("highway") not in allowed:
            continue
        out.append((line, ribbon_half_width_m(tags, law)))
    return tuple(out)


def road_cut_pieces(carriageways, envelope, standoff_m: float, extent=None,
                    cap_style: str = "flat"
                    ) -> list[tuple[LineString, float, Polygon]]:
    """``(axis, half-width, cut)`` per stretch of a road's centreline OUTSIDE
    ``envelope`` and within reach of ``extent`` (default: the envelope
    itself), the cut being that stretch grown by its half-width plus
    ``standoff_m`` — flat ends, or ``"square"`` ones (a road through zone 2:
    a way ENDING in the band stands off it there too, and the square end at
    a crossing reaches into the envelope, which the zone-2 cut never
    touches)."""
    if not carriageways or envelope is None or envelope.is_empty:
        return []
    extent = envelope if extent is None or extent.is_empty else extent
    reach = extent.buffer(max(h for _l, h in carriageways) + standoff_m, **_MITRE)
    pieces = []
    for line, half in carriageways:
        if not line.intersects(reach):
            continue
        outside = line.intersection(reach).difference(envelope)
        if outside.is_empty or outside.length <= 0.0:
            continue
        # a stretch that has just CROSSED out of a band cuts the band
        # beside it too: that ground is the road's carriageway, not the
        # band's (a notch-free variant -- the crossing's in-band growth
        # withheld -- was measured worse at KBUR: hairline 318 -> 377)
        pieces.append((outside, half,
                       outside.buffer(half + standoff_m, cap_style=cap_style, **_MITRE)))
    return pieces


def road_yield_records(yields, faces, face_vs, vertices_xy, tol_m: float
                       ) -> tuple[RoadYield, ...]:
    """Per :class:`BandYield`, the :class:`~..model.road_yield.RoadYield`
    record of the vertices standing in its cut (within ``tol_m``: the
    identity snap), keyed by the band it was cut from: the mapped-road
    RIBBON's, and the ZONE-1 lip's where the road crosses it — the lip is
    welded to the road there (13ar), so inside the road's reach it is the
    road's kerb, never a band vertex holding the lip's floor two metres off
    a road in its own cut (#951 iteration 2, KLAX taxiway F 33.934549,
    -118.396285: a free lip corner at 32.24 m 2.0 m from the kerb at
    27.97 m)."""
    if not yields:
        return ()
    from shapely import points
    from shapely.strtree import STRtree

    from ..model.planar import is_osm_ribbon_ref
    rib = sorted({v for fid, f in faces.items()
                  if is_osm_ribbon_ref(f.ref) or _is_zone1_ref(f.ref)
                  for v in face_vs.get(fid, ())})
    if not rib:
        return ()
    tree = STRtree(points([vertices_xy[v] for v in rib]))
    out = []
    for y in yields:
        if not y.through:
            continue
        hit = tree.query(y.polygon, predicate="dwithin", distance=tol_m)
        kerb = frozenset(rib[int(i)] for i in hit)
        if kerb:
            out.append(RoadYield(kerb, y.family, y.code_number, y.code_letter,
                                 y.runway_ref))
    return tuple(out)


def _is_zone1_ref(ref) -> bool:
    """A runway / taxi band's zone-1 (lip) face ref."""
    from ..model.road_yield import is_band_zone_ref
    return is_band_zone_ref(ref) and ":zone1#" in str(ref)


def road_cut_outlines(yields) -> tuple:
    """Every cut's carriageway footprint (:meth:`BandYield.footprint`) as
    ``(exterior, holes)`` coordinate rings — the road's edge by its lanes,
    which ``pipeline/band_road_wall`` unions with the drawn road faces."""
    out = []
    for y in yields:
        g = y.footprint()
        for p in getattr(g, "geoms", (g,)):
            if p.geom_type == "Polygon" and not p.is_empty:
                out.append((tuple(p.exterior.coords),
                            tuple(tuple(h.coords) for h in p.interiors)))
    return tuple(out)


def road_cut_ground(yields, faces, dem, spacing_m: float, tol_m: float) -> tuple:
    """``(x, y, z)`` every ``spacing_m`` along each cut's carriageway edge
    (:meth:`BandYield.footprint`) where NO patch face stands (beyond
    ``tol_m``), ``z`` the DEM there: the road the core mesh draws, which the
    band's wall stands above or below although the patch has no vertex of
    it (a road beside the band, #944; past a ribbon's end)."""
    if not yields or dem is None:
        return ()
    import numpy as np
    from shapely.strtree import STRtree
    pts = []
    for y in yields:
        g = y.footprint()
        for ring in getattr(g.boundary, "geoms", (g.boundary,)):
            n = max(2, int(ring.length // spacing_m) + 1)
            pts.extend(ring.interpolate(k * ring.length / n) for k in range(n))
    if not pts:
        return ()
    polys = [p for p in faces if p is not None and not p.is_empty]
    if polys:
        hit = STRtree(polys).query(pts, predicate="dwithin", distance=tol_m)
        covered = set(int(i) for i in hit[0])
        pts = [p for i, p in enumerate(pts) if i not in covered]
    if not pts:
        return ()
    xs = np.array([p.x for p in pts])
    ys = np.array([p.y for p in pts])
    many = getattr(dem, "z_many", None)
    zs = (np.asarray(many(xs, ys), dtype=float) if callable(many)
          else np.array([dem.z(float(x), float(y)) for x, y in zip(xs, ys, strict=True)]))
    return tuple((float(x), float(y), float(z)) for x, y, z in zip(xs, ys, zs, strict=True)
                 if np.isfinite(z))
