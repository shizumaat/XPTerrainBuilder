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
  road can climb or descend and leave a steep wall").
* :func:`arm_storeys` — a pad under a unit's UPPER storey
  (``airport.unit_storey.upper_pads``, RULINGS 2026-11-13aa (1), #2068):
  the road §27 flipped to apron round it is cut at its neck back to the
  road it was born, its ARM, welded to the pad's level; the pad's cell
  carries the storey (``UPPER_Y_KEY`` / ``UPPER_UNIT_KEY``)."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import role_side, snap_margin_m
from .evidence import polygon_parts

__all__ = ["ARM_PAD_KEY", "STOREY_M_KEY", "STOREY_Y_KEY", "STOREY_UNCONFIRMED_KEY",
           "StoreyBand", "UPPER_FLOOR_KEY", "UPPER_UNIT_KEY", "UPPER_Y_KEY", "arm_storeys",
           "ground_confirms", "knife_storeys", "storey_band", "storey_height"]

#: evidence: metres of a lot's apron contact §27 read as across a storey
STOREY_M_KEY = "airside_edge_storey_m"
#: evidence: that storey's authored rise over its unit's airside floor (m)
STOREY_Y_KEY = "airside_edge_storey_y"
#: evidence: a storey rise the lot's ground does not confirm (reported)
STOREY_UNCONFIRMED_KEY = "airside_edge_storey_unconfirmed_y"
#: evidence: the upper pad a road's ARM climbs to (:func:`arm_storeys`)
ARM_PAD_KEY = "storey_arm_pad"
#: pad evidence: the storey's authored base ``y_p``, the unit's floor
#: ``t`` and the unit (``airport.unit_storey.upper_pads``)
UPPER_Y_KEY = "upper_storey_y"
UPPER_FLOOR_KEY = "upper_storey_floor"
UPPER_UNIT_KEY = "upper_storey_unit"
#: what §27's flip wrote on a face (dropped from an arm cut back)
_FLIP_KEYS = ("airside_edge_m", "airside_edge_flip", "airside_edge_round",
              "airside_edge_was")


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


def _median_dem(dem, g) -> "float | None":
    """The median DEM over ``g`` (``airport.unit_storey.dem_samples``)."""
    from ..airport.unit_storey import dem_samples
    zs = dem_samples(dem, g)
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


def _arm(face, pad, others, weld: float, opening: float):
    """The ARM of ``face`` (spec 2068 §1 Classify): the face less every
    other airside within its mean width ``2A/P``, opened by ``opening``,
    the parts within ``weld`` of ``pad``."""
    R = 2.0 * face.area / face.length
    far = face.difference(others.buffer(R)) if not others.is_empty else face
    far = far.buffer(-opening, join_style="mitre").buffer(opening, join_style="mitre")
    arm = [p for p in polygon_parts(far.intersection(face)) if p.distance(pad) <= weld]
    return unary_union(arm) if arm else None


def arm_storeys(final: list[list], cells, pads, airport, law: Law,
                min_area_m2: float) -> dict[str, dict]:
    """A PAD UNDER AN UPPER STOREY KEEPS ITS ROAD (module docstring): each
    face of ``final`` §27 flipped from a road role that touches an upper
    pad among ``pads`` (``(ref, polygon)``) is cut: its arm goes back to
    the role it was born as ``<ref>#<k>`` with ``ARM_PAD_KEY``, the rest
    keeps the flip.  Returns ``{pad ref: its evidence}`` for every upper
    pad."""
    from ..airport.unit_storey import upper_pads
    from .airside_edge import _ROAD_ROLES
    if airport is None or not pads:
        return {}
    air_g = [Polygon(c.ring, c.holes) for c in cells
             if c.role != "building" and c.side == "airside"]
    ups = upper_pads(airport, law, unary_union(
        air_g + [f[2] for f in final
                 if f[0] != "building" and role_side(law, f[0]) == "airside"]), pads)
    if not ups:
        return {}
    from ..law.tables import design as design_law
    weld = float(law.tables.emit.identity.weld_spacing_m)
    opening = 0.5 * float(design_law(law).pad_frontage_m)
    extra: list[list] = []
    for up in ups:
        for i, f in enumerate(final):
            if (f[0] != "apron" or f[4].get("airside_edge_was") not in _ROAD_ROLES
                    or f[2].distance(up.polygon) > weld):
                continue
            others = unary_union(air_g + [g[2] for j, g in enumerate(final) if j != i
                                          and g[0] != "building"
                                          and role_side(law, g[0]) == "airside"])
            arm = _arm(f[2], up.polygon, others, weld, opening)
            if arm is None:
                continue
            born = str(f[4]["airside_edge_was"])
            ev = {k: v for k, v in f[4].items() if k not in _FLIP_KEYS}
            ev = dict(ev, kind=str(ev.get("source_class") or born), **{ARM_PAD_KEY: up.ref})
            rest = sorted((p for p in polygon_parts(f[2].difference(arm))
                           if p.area >= min_area_m2), key=lambda p: -p.area)
            arms = [p for p in polygon_parts(arm) if p.area >= min_area_m2]
            if not rest or not arms:
                continue
            final[i] = [f[0], f[1], rest[0], *f[3:]]
            used = {str(g[1]) for g in final + extra}
            names = (f"{f[1]}#{k}" for k in range(1, 10 ** 6) if f"{f[1]}#{k}" not in used)
            extra.extend([f[0], next(names), p, *f[3:]] for p in rest[1:])
            extra.extend([born, next(names), p, f[3], ev, ev["kind"]] for p in arms)
    final.extend(extra)
    return {up.ref: {UPPER_Y_KEY: up.y, UPPER_FLOOR_KEY: up.floor_y,
                     UPPER_UNIT_KEY: float(up.unit)} for up in ups}
