"""THE ONE FLAT-SITE DECISION, made in DEM prep (issue #932, owner option B;
``docs/specs/auto-patch-v2/flat-site-datum-spec.md`` §6).

DEM prep (``auto_patch/flat_site_mode.flat_site_substitutions``) calls
:func:`decide` per tile airport on the RAW raster — after the airport
smoothing and the cached-inset bake, before the substitution — and the
record it returns is what the bake substitutes on AND what the build reads
(``airport/flat_site_read.py``).  Everything is v2's: the pack
``pack.select_pack`` picks and the frame ``load.read_apt`` builds (one
site with the build's load), runway ends JOINED to CIFP
(``load.join_cifp``), pavement ∪ runways ∪ boundary, the detector
(``airport/flat_site.detect``) under ``law/flat_site.toml`` with its
``[declared]`` table, the water cut, and the production sampler
(``ProductionDem.over_prep``).  S4 has no objects here (``no_data``); the
build measures it as a report.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

from ..law import Law
from ..model.frame import XY
from . import cifp as _cifp
from . import flat_site as _flat
from .dem_production import ProductionDem, TileWater
from .load import _ring, _vector_to_xy, join_cifp, read_apt

__all__ = ["FlatSiteInputs", "site_inputs", "decide"]


@_dc.dataclass(frozen=True)
class _End:
    xy: XY
    threshold_elev_m: float | None


@_dc.dataclass(frozen=True)
class _Runway:
    ends: tuple[_End, _End]
    width_m: float


@_dc.dataclass(frozen=True)
class _Poly:
    outer: tuple[XY, ...]
    holes: tuple[tuple[XY, ...], ...]


@_dc.dataclass(frozen=True)
class FlatSiteInputs:
    """What :func:`flat_site.detect` reads of an airport — the build's
    :class:`~auto_patch_v2.model.airport.Airport` carries the same names."""

    icao: str
    frame: _t.Any
    runways: tuple[_Runway, ...]
    pavements: tuple[_Poly, ...]
    boundaries: tuple[_Poly, ...]
    dem: _t.Any = None


def site_inputs(icao: str, xplane_root: str, cifp_path: str | None, law: Law,
                apt_dat_path: str | None = None) -> FlatSiteInputs:
    """The airport as the detector reads it, from v2's own readers (module
    doc).  An end the CIFP join leaves unmatched has no threshold
    elevation, so a CIFP record with no apt.dat runway never counts in S1."""
    _sel, _block, apt, _bres, frame = read_apt(icao, xplane_root, law, apt_dat_path)
    to_xy = _vector_to_xy(frame)
    cifp = (_cifp.read_cifp_runways(cifp_path)
            if cifp_path and os.path.isfile(cifp_path) else {})
    tol = float(law.tables.emit.identity.cifp_threshold_join_m)
    recs, _missing, _joins = join_cifp(icao, apt.runways, cifp, to_xy, tol)
    runways = tuple(
        _Runway(tuple(_End(to_xy(lon, lat),
                           recs[(i, k)].elevation_m if recs[(i, k)] else None)
                      for k, (_d, lat, lon, _disp, _over) in enumerate(rw.ends)),
                rw.width_m)
        for i, rw in enumerate(apt.runways))
    pavements = tuple(_Poly(_ring(p.rings[0], to_xy),
                            tuple(_ring(h, to_xy) for h in p.rings[1:]))
                      for p in apt.pavements)
    boundaries = tuple(_Poly(_ring(b.rings[0], to_xy),
                             tuple(_ring(h, to_xy) for h in b.rings[1:]))
                       for b in apt.boundaries)
    return FlatSiteInputs(icao.upper(), frame, runways, pavements, boundaries)


def decide(site: FlatSiteInputs, tile_dem: _t.Any, tile_lat: int, tile_lon: int,
           water: TileWater | None, law: Law,
           out: _t.Callable[[str], None] = print) -> dict:
    """The decision record for ``site`` on DEM prep's raster ``tile_dem``:
    :func:`flat_site.record` plus ``origin`` (the frame), ``region`` (the
    dilated, water-cut rings the datum covers), ``gate`` (the margin-0 gate
    extent, water-cut — the ground the plateau must cover) and
    ``region_ll`` (the region's rings in ``(lon, lat)``, for the bake's
    rectangle) and ``gate_ll`` (the gate's, for the bake's off-site relief
    rule, ``auto_patch/flat_site_relief.py``).  The bake adds ``plateau``."""
    dem = ProductionDem.over_prep(site.frame, site.icao, tile_dem, tile_lat,
                                  tile_lon, water, out=out)
    site = _dc.replace(site, dem=dem)
    # §37 (11) (4): the airport's OWN surfaces are land for the water cut —
    # here the apt.dat runways ∪ pavements (the classification the build
    # reads does not exist yet in DEM prep)
    land = _flat.region_polygon(_dc.replace(site, boundaries=()), 0.0)
    fv = _flat.detect(site, law, land=land)
    rec = _flat.record(fv)
    gate = _flat.region_polygon(site, 0.0)
    if gate is not None:
        gate, _cut = _flat._cut_water(dem, gate, land)
    _to_xy, to_ll = site.frame.transformers()

    def _ll(rings):
        return [[[list(reversed(to_ll(x, y))) for x, y in outer],
                 [[list(reversed(to_ll(x, y))) for x, y in h] for h in holes]]
                for outer, holes in rings]

    gate_rings = (_flat._rings(gate) if gate is not None
                  and not gate.is_empty else ())
    rec.update(origin=list(site.frame.origin),
               region=[[list(map(list, o)), [list(map(list, h)) for h in hs]]
                       for o, hs in fv.region],
               gate=[[list(map(list, o)), [list(map(list, h)) for h in hs]]
                     for o, hs in gate_rings],
               region_ll=_ll(fv.region),
               # #1137: the airport's OWN surfaces in (lon, lat) — the
               # ground the bake keeps at Z0 whatever the DEM says there.
               gate_ll=_ll(gate_rings))
    return rec
