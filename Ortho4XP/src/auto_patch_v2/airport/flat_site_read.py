"""THE BUILD READS DEM PREP'S FLAT-SITE DECISION (issue #932, owner option
B; ``docs/specs/auto-patch-v2/flat-site-datum-spec.md`` §6).

DEM prep decided the flat site ONCE, on the raw raster, with the v2
detector (``airport/flat_site_prep.py``), and kept the record on the DEM
object; the production sampler hands it back
(``ProductionDem.flat_site_decision``).  The build's ``flat_site`` stage
rebuilds the verdict from that record and NEVER re-measures it.  What it
still does:

* S4 (the pack's seats) — measured here, after the planar stage read the
  objects, as a REPORT on ``signals["s4"]``; it never gated;
* THE MISMATCH RULE — a record that substituted a plateau requires the
  composed DEM to carry it: the median ``|DEM − Z0|`` over the record's
  HELD ground (pavement and the runway strips — the one ground the plateau
  holds at Z0 whatever the DEM says;
  elsewhere it only fills, RULINGS 2026-10-26r) at most
  :data:`PLATEAU_TOL_M`, and the record's frame the build's frame;
  otherwise :class:`~.dem_production.ColdDemFrame` (the frame is not the
  one DEM prep decided on).

With NO record (flat-site mode off, an airport outside the tile's airport
dictionary, an authored or fixture frame) the build measures with the same
detector on the frame it holds, and the line says so.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..law import Law
from ..law.tables import flat_site
from ..model.airport import FlatVerdict
from . import flat_site as _flat
from .dem_production import ColdDemFrame

__all__ = ["PLATEAU_TOL_M", "verdict_for_build", "check_plateau"]

#: The plateau is a CONSTANT raster at Z0 (``O4_Airport_Elevation_Insets.
#: _flat_site_inset``); bilinear reads of it are Z0 to float noise.  A
#: mechanism tolerance for "the plateau is there", never a law value.
PLATEAU_TOL_M = 0.05


def _region_geom(fv: FlatVerdict):
    from shapely.geometry import MultiPolygon, Polygon
    polys = [Polygon(o, list(h)) for o, h in fv.region if len(o) >= 3]
    if not polys:
        return None
    g = polys[0] if len(polys) == 1 else MultiPolygon(polys)
    return g if g.is_valid else g.buffer(0)


def check_plateau(icao: str, dem: _t.Any, fv: FlatVerdict, rec: _t.Mapping) -> float | None:
    """The median ``|DEM − Z0|`` over the record's HELD ground (apt.dat
    pavements ∪ runways ∪ the pack's pavement pages ∪ the runway strips,
    margin 0 — the record's ``held``, the ground the plateau covers whole;
    a record without it, the GATE), or raise :class:`ColdDemFrame`.
    ``None`` when the composed DEM has no sample there to judge (nothing
    to contradict)."""
    geom = _region_geom(fv)
    core = rec.get("held") or rec.get("gate")
    if core:
        g = _region_geom(_flat.from_record({"verdict": fv.verdict, "region": core}))
        geom = g if g is not None else geom
    if geom is None or geom.is_empty or fv.z0_m is None:
        return None
    _x, _y, z = _flat._samples(dem, geom)
    if z.size == 0:
        return None
    off = float(np.median(np.abs(z - float(fv.z0_m))))
    if not math.isfinite(off) or off > PLATEAU_TOL_M:
        raise ColdDemFrame(
            f"{icao}: DEM prep decided a flat site ({fv.verdict}, Z0 {fv.z0_m:.2f} m) "
            f"and baked its plateau, but the composed DEM reads a median "
            f"{off:.2f} m off Z0 over its held ground (tolerance {PLATEAU_TOL_M} m) "
            f"— the frame is not the one DEM prep decided on (issue #932)")
    return round(off, 4)


def verdict_for_build(airport: _t.Any, law: Law, *, objects: _t.Iterable = (),
                      land=None) -> tuple[FlatVerdict, str]:
    """``(verdict, how)`` for the build's ``flat_site`` stage (module doc);
    ``how`` is the clause the stage's log line carries."""
    fn = getattr(airport.dem, "flat_site_decision", None)
    rec = fn() if callable(fn) else None
    if rec is None:
        return (_flat.detect(airport, law, objects=objects, land=land),
                "measured in the build: DEM prep decided nothing for this airport")
    icao = str(airport.icao).upper()
    origin = tuple(float(v) for v in (rec.get("origin") or ()))
    if origin != tuple(float(v) for v in airport.frame.origin):
        raise ColdDemFrame(
            f"{icao}: DEM prep decided the flat site in frame {origin} but the "
            f"build's frame is {tuple(airport.frame.origin)} — one pack, one frame "
            f"(issue #932)")
    fv = _flat.from_record(rec)
    det = flat_site(law).detector
    s4 = _flat.seat_consensus(objects, fv.z0_m,
                              below_grade_base_y_m=det.below_grade_base_y_m,
                              consensus_max_m=det.seat_consensus_max_m,
                              spread_max_m=det.seat_spread_max_m)
    signals = dict(fv.signals, s4=s4, decided_in="dem_prep",
                   plateau=rec.get("plateau"))
    if fv.substitutes and rec.get("plateau") is True:
        signals["plateau_offset_m"] = check_plateau(icao, airport.dem, fv, rec)
    fv = FlatVerdict(fv.verdict, fv.auto_verdict, fv.z0_m, fv.source, fv.region,
                     signals)
    return fv, "decided in DEM prep"
