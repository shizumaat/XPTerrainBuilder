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
import math
import os
import typing as _t

from shapely.ops import unary_union

from ..law import Law
from ..law.reference_code import is_instrument, runway_code_letter, runway_code_number
from .runway_strip import strip_band
from ..model.frame import XY
from . import approach as _approach
from . import cifp as _cifp
from . import flat_site as _flat
from . import pack_pavement as _pack_pavement
from .dem_production import ProductionDem, TileWater
from .load import _own_extent, _ring, _vector_to_xy, join_cifp, read_apt

__all__ = ["FlatSiteInputs", "site_inputs", "decide"]


@_dc.dataclass(frozen=True)
class _End:
    xy: XY
    threshold_elev_m: float | None
    #: the end's approach class (``approach.end_approach``), which the
    #: strip's width reads through the runway's status
    approach: str | None = None


@_dc.dataclass(frozen=True)
class _Runway:
    ends: tuple[_End, _End]
    width_m: float
    instrument: bool = False
    code_number: int | None = None
    code_letter: str | None = None


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
    #: the pack :func:`load.read_apt` selected — where DEM prep reads the
    #: pack's draped pavement pages (``pack_pavement``, #1208)
    pack_root: str = ""
    pack_name: str = ""


def _runway(law: Law, rw: _t.Any, i: int, recs: _t.Mapping, approaches: _t.Mapping,
            to_xy: _t.Callable[[float, float], XY]) -> _Runway:
    """One apt.dat runway as the detector and the strip band read it: the
    ends' CIFP threshold elevations and approach classes (the loader's own
    ``approach.end_approach`` reading) and the reference code."""
    ends = []
    for k, (_d, lat, lon, _disp, _over) in enumerate(rw.ends):
        rec = recs[(i, k)]
        cls, _cat = _approach.end_approach(
            approaches.get(rec.designator) if rec is not None else None,
            *(getattr(rw, f, (0, 0))[k]
              for f in ("markings", "approach_lights", "tdz_lights")))
        ends.append(_End(to_xy(lon, lat), rec.elevation_m if rec else None, cls))
    (ax, ay), (bx, by) = ends[0].xy, ends[1].xy
    return _Runway(tuple(ends), rw.width_m,
                   any(is_instrument(e.approach) for e in ends),
                   runway_code_number(law, math.hypot(bx - ax, by - ay)),
                   runway_code_letter(law, rw.width_m))


def site_inputs(icao: str, xplane_root: str, cifp_path: str | None, law: Law,
                apt_dat_path: str | None = None) -> FlatSiteInputs:
    """The airport as the detector reads it, from v2's own readers (module
    doc).  An end the CIFP join leaves unmatched has no threshold
    elevation, so a CIFP record with no apt.dat runway never counts in S1."""
    sel, _block, apt, _bres, frame = read_apt(icao, xplane_root, law, apt_dat_path)
    to_xy = _vector_to_xy(frame)
    cifp = (_cifp.read_cifp_runways(cifp_path)
            if cifp_path and os.path.isfile(cifp_path) else {})
    tol = float(law.tables.emit.identity.cifp_threshold_join_m)
    recs, _missing, _joins = join_cifp(icao, apt.runways, cifp, to_xy, tol)
    approaches = (_cifp.read_cifp_approach_runways(cifp_path) if cifp else {})
    runways = tuple(_runway(law, rw, i, recs, approaches, to_xy)
                    for i, rw in enumerate(apt.runways))
    pavements = tuple(_Poly(_ring(p.rings[0], to_xy),
                            tuple(_ring(h, to_xy) for h in p.rings[1:]))
                      for p in apt.pavements)
    boundaries = tuple(_Poly(_ring(b.rings[0], to_xy),
                             tuple(_ring(h, to_xy) for h in b.rings[1:]))
                       for b in apt.boundaries)
    return FlatSiteInputs(icao.upper(), frame, runways, pavements, boundaries,
                          pack_root=sel.root, pack_name=sel.name)


def decide(site: FlatSiteInputs, tile_dem: _t.Any, tile_lat: int, tile_lon: int,
           water: TileWater | None, law: Law,
           out: _t.Callable[[str], None] = print,
           mod_cache_root: str | None = None,
           xplane_root: str | None = None) -> dict:
    """The decision record for ``site`` on DEM prep's raster ``tile_dem``:
    :func:`flat_site.record` plus ``origin`` (the frame), ``region`` (the
    dilated, water-cut rings the datum covers), ``gate`` (the margin-0 gate
    extent, water-cut), ``region_ll`` (the region's rings in ``(lon,
    lat)``), ``footprint_ll`` (the region before its water cut — the
    plateau's footprint, #1144) and ``held`` / ``held_ll``
    (apt.dat pavements ∪ runways ∪, at a substituting site, the pack's
    draped pavement pages read from ``mod_cache_root`` and each runway's
    graded strip, ``airport.runway_strip.strip_band``; margin 0:
    the ground the plateau keeps at Z0 whatever the DEM says — elsewhere it
    only fills, ``auto_patch/flat_site_relief.py``, RULINGS 2026-10-26r).
    The bake adds ``plateau``."""
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
    held = land
    if fv.substitutes:
        # RULINGS 2026-10-27d: pavement stays flat — ALL of it the build
        # grades as pavement, the pack's draped ``.pol`` pages included.
        pages = _pack_pavement.pavement_pages(
            site.pack_root, site.pack_name, tile_lat, tile_lon, _to_xy,
            _own_extent(site.runways, site.pavements, site.boundaries,
                        law.tables.emit.identity.dsf_pavement_admission_m),
            mod_cache_root, xplane_root)
        # RULINGS 2026-10-27v (2): the runway strips stay graded, as the
        # strip law requires — held with the pavement, not kept on the
        # real ground.  THE SAMPLING STENCIL: the build reads the raster
        # bilinearly and emits the strip's outer edge from the pavement
        # ring, so a strip-edge vertex can sit just outside the band and
        # read the restored ground beside it (VHHH 07R: a zone-2 vertex
        # 0.6 m outside the 75 m band read 2.7 m of kept terrace).  The
        # strip is held one DEM post diagonal wider.  Pavement is NOT
        # grown: a road beside an apron grades by its own rules on the
        # real ground (27v (1)), and one post would hold it flat.
        post = getattr(dem, "posting_m", None)
        step = post() if callable(post) else None
        grow = float(step) * math.sqrt(2.0) if step else 0.0
        strips = [b.buffer(grow) if grow else b
                  for b in (strip_band(rw, law) for rw in site.runways)
                  if b is not None]
        if pages or strips:
            held = unary_union(([land] if land is not None else [])
                               + pages + strips)
            out(f"[flat-site] {site.icao}: {len(pages)} draped pavement "
                f"page(s) of the pack and {len(strips)} runway strip(s) "
                f"join apt.dat's pavement at Z0")
    held_rings = (_flat._rings(held) if held is not None
                  and not held.is_empty else ())
    # #1144: the plateau's FOOTPRINT — the same (pavement ∪ runways ∪
    # boundary) ⊕ margin as ``region``, but NOT water-cut: the bake cuts
    # its own water (``flat_site_mode.water_beside_site``), and the
    # detector's coastline would drop reclaimed land inside the boundary.
    footprint = _flat.region_polygon(site, _flat.flat_site(law).detector.margin_m)
    footprint_rings = (_flat._rings(footprint) if footprint is not None
                       and not footprint.is_empty else ())
    rec.update(origin=list(site.frame.origin),
               region=[[list(map(list, o)), [list(map(list, h)) for h in hs]]
                       for o, hs in fv.region],
               gate=[[list(map(list, o)), [list(map(list, h)) for h in hs]]
                     for o, hs in gate_rings],
               region_ll=_ll(fv.region),
               footprint_ll=_ll(footprint_rings),
               # RULINGS 2026-10-27d / 27v: pavement and the runway strips
               # — the only ground the plateau keeps at Z0 whatever the DEM
               # says.
               held=[[list(map(list, o)), [list(map(list, h)) for h in hs]]
                     for o, hs in held_rings],
               held_ll=_ll(held_rings))
    return rec
