"""A LOT THAT MEETS THE APRON ACROSS A UNIT'S STOREY (owner answer 47,
2026-10-20, #1099 / #1101: "A lot that touches the apron only across that
object-witnessed storey stays groundside under §27").

MEASURED LPHR (38.521557, −28.716632): the forecourt ``pav2`` shared 68 m
of edge with the apron at the terminal's west corner and §27 made it apron,
8.96 m under its ground; along exactly that edge the terminal's own
parapet (``lphr_tps_06``, 68 m x 1 m) stands at y +6.0 over a floor at 0 —
the forecourt is a storey up and the parapet is its retaining wall.

Three pieces, one witness (``airport.unit_storey``):

* :func:`storey_band` — the weld-widened plan footprint of every unit's
  upper storey, read against the airside as classified.  §27's
  ``airside_edge_flip`` drops a contact's run inside it.
* :func:`storey_height` — the storey the dropped run stands under: the
  most common authored rise (``base y`` − the unit's floor) of the upper
  parts along it.  Published on the lot as ``airside_edge_storey_y``; the
  lot's pad reads it (``planar/low_level`` mints the pad's UPPER LEVEL at
  that height, and ``roles._cut_back_groundside`` welds the lot to the pad
  rather than holding it off as a §28 (6) hillside — the lot meets the
  upper level, never the airside floor).
* :func:`knife_storeys` — the lot is cut back from the apron along the
  dropped run by the pad set-back (``groundside_cutback_m`` + the snap
  margin): the storey is a riser, and two levels never share a vertex
  (the §28 (6) knife's form, RULINGS 2026-10-09j "if there's any gap the
  road can climb or descend and leave a steep wall")."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import role_side, snap_margin_m
from .evidence import polygon_parts

__all__ = ["STOREY_M_KEY", "STOREY_Y_KEY", "STOREY_UNCONFIRMED_KEY", "StoreyBand",
           "ground_confirms", "knife_storeys", "storey_band", "storey_height"]

#: evidence: metres of a lot's apron contact §27 read as across a storey
STOREY_M_KEY = "airside_edge_storey_m"
#: evidence: that storey's authored rise over its unit's airside floor (m)
STOREY_Y_KEY = "airside_edge_storey_y"
#: evidence: a storey rise the lot's ground does not confirm (reported)
STOREY_UNCONFIRMED_KEY = "airside_edge_storey_unconfirmed_y"


@_dc.dataclass(frozen=True)
class StoreyBand:
    """The storeys, the union of their weld-widened footprints and the
    airside pavement they were read against."""

    geom: _t.Any
    storeys: tuple
    weld_m: float
    air: _t.Any = None
    #: the airport's DEM (``z(x, y)``), the ground witness of a storey
    dem: _t.Any = None
    #: how far from the run the ground is read (``[design] pad_frontage_m``)
    reach_m: float = 0.0


def storey_band(airport, law: Law, cells, final) -> "StoreyBand | None":
    """THE STOREY BAND (module docstring), or ``None`` where no unit
    standing at airside pavement carries an upper storey."""
    if airport is None:
        return None
    from ..airport.unit_storey import upper_storeys
    air = unary_union([Polygon(c.ring, c.holes) for c in cells
                       if c.role != "building" and c.side == "airside"]
                      + [f[2] for f in final
                         if f[0] != "building" and role_side(law, f[0]) == "airside"])
    st = upper_storeys(airport, law, air)
    if not st:
        return None
    from ..law.tables import design as design_law
    weld = float(law.tables.emit.identity.weld_spacing_m)
    return StoreyBand(unary_union([s.footprint for s in st]).buffer(weld), tuple(st),
                      weld, air, getattr(airport, "dem", None),
                      float(design_law(law).pad_frontage_m))


def storey_height(band: StoreyBand, run, to_xy) -> "float | None":
    """The authored rise of the storey the contact ``run`` stands under
    (module docstring), or ``None``."""
    from ..airport.unit_storey import part_footprint
    zone = run.buffer(band.weld_m)
    rise = [round(p.base_y - s.floor_y, 1) for s in band.storeys
            if s.footprint.buffer(band.weld_m).intersects(zone) for p in s.parts
            if (g := part_footprint(p, to_xy)) is not None and g.intersects(zone)]
    return float(min(_st.multimode(rise))) if rise else None


def _median_dem(dem, g, step: float = 2.0) -> "float | None":
    """The median DEM over ``g`` on a ``step`` grid (at most ~400 samples)."""
    import math

    from shapely.geometry import Point
    if dem is None or g is None or g.is_empty:
        return None
    x0, y0, x1, y1 = g.bounds
    h = max(step, math.sqrt(max(g.area, 1.0) / 400.0))
    zs = []
    y = y0 + 0.5 * h
    while y < y1:
        x = x0 + 0.5 * h
        while x < x1:
            if g.contains(Point(x, y)):
                try:
                    z = float(dem.z(x, y))
                except Exception:  # noqa: BLE001 -- off the raster
                    z = float("nan")
                if z == z:
                    zs.append(z)
            x += h
        y += h
    return _st.median(zs) if zs else None


def ground_confirms(band: StoreyBand, lot, run, rise: float) -> "bool | None":
    """Whether the lot's own ground stands at least half the storey ``rise``
    above the airside pavement along ``run`` (module docstring): the DEM
    median over the lot against the median over the airside within the
    lot's mean depth off the run (its area over the run's length, at least
    the band's ``reach_m``).  ``None`` where either side has no ground to
    read (no verdict: the storey stands as read)."""
    if (band.dem is None or band.air is None or lot is None or run is None
            or run.is_empty or run.length <= 0.0):
        return None
    reach = max(float(band.reach_m), float(lot.area) / float(run.length))
    z_lot = _median_dem(band.dem, lot)
    z_air = _median_dem(band.dem, band.air.intersection(run.buffer(reach)))
    if z_lot is None or z_air is None:
        return None
    return z_lot - z_air >= 0.5 * float(rise)


def knife_storeys(final: list[list], cuts: _t.Mapping[int, _t.Any], law: Law,
                  min_area_m2: float, band: "StoreyBand | None" = None) -> int:
    """Cut every lot in ``cuts`` (``final`` index -> the contact run §27
    dropped) back from the apron along it (module docstring) — and along
    the rest of its airside contact, the short runs §27 never counted (the
    lot meets the airside nowhere: its level is the storey's, MEASURED
    LPHR: a 2 m run past the parapet's end held the forecourt at the apron
    against its pad's upper level); a piece under ``min_area_m2`` is
    dropped.  Returns the lots cut."""
    knife = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    n = 0
    extra: list[list] = []
    for i, run in sorted(cuts.items()):
        f = final[i]
        weld = float(law.tables.emit.identity.weld_spacing_m)
        if band is not None and band.air is not None:
            run = run.union(f[2].boundary.intersection(band.air.boundary.buffer(weld)))
        cut = run.buffer(weld + knife, join_style="mitre", mitre_limit=2.0)
        parts = sorted((p for p in polygon_parts(f[2].difference(cut))
                        if p.area >= min_area_m2), key=lambda p: -p.area)
        if not parts:
            continue
        n += 1
        final[i] = [f[0], f[1], parts[0], *f[3:]]
        extra.extend([f[0], f"{f[1]}#{k}", p, *f[3:]] for k, p in enumerate(parts[1:], 1))
    final.extend(extra)
    return n
