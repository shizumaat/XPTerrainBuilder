"""WATER IS A DATUM — the ground pin (owner RULINGS 2026-09-09m (1);
mechanism 09o (1); spec ``docs/specs/auto-patch-v2/water-datum-spec.md``).

The owner's read of OTHH: "the water is weird with a sharp cliff at the
land/water border and some water being lifted up to terrain level".  The
law: **a ground vertex whose production-frame sample is WATER is PINNED
to the water level and is not an unknown of the sheet** — the design
surface never lifts water.

THE WITNESS IS NOT OURS.  Water is read from
``airport.dem.water_many`` (``airport/dem_production.TileWater``), the
ONE derivation site: the tile's cached coastline + water layers, the
same the mesh's masks are built from.  This generator only asks.

WHICH VERTICES.  The GROUND the design sheet owns: every
``graded_strip`` face's ring and hole vertices — the zone rings and the
gap-interior rings (09g (1): the interior ground IS part of the sheet).
Never a pavement vertex (an apron over water is a deck, not water) and
never a STRUCTURE vertex (a tunnel ramp, a wall band, a basin floor
keeps its generator's datum — the carve-out ``flat_datum`` makes for the
same reason).  The bank foot and its level rings are emit-side and are
the NEXT round's (09o (4)); they read the same witness through the same
``dem`` object.

THE PIN IS THE MODEL'S ``Pin`` (``z[v] == z``), not a preference row:
the reduction takes a pinned vertex out of the free columns, which is
literally what "is not an unknown of the sheet" means.  Its consequence is the post-pass in
``constraints/__init__.water_exempt``: every OTHER row governing a
pinned vertex is dropped, exactly as ``seam_exempt`` drops pin-to-pin
pairs — a zone band that says "no deeper than 2 m below the lip" cannot
be allowed to fight the datum, and a vertex the pin fixes is no longer
an unknown for anything to price.

An airport with no water under its ground mints NOTHING (OTHH: 0 of
43,410 patch nodes stand inside the water polygon — the canal there is
fixed by the inset cut and the mesh precedence, not by this).
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..law.tables import is_structure_role
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap
from .precedence import view

__all__ = ["water_pins", "water_vertices_pinned", "GEN"]

GEN = "water"
RULING = ("water is a datum: a ground vertex sampled on water is pinned to the "
          "water level (owner RULINGS 2026-09-09m (1))")

#: The ground faces the sheet owns (the zone rings and the gap interior).
GROUND_ROLES = ("graded_strip",)

STATS: dict[str, dict] = {}


def _quay_vertices(vw, planar: PlanarMap) -> set[int]:
    """§37 (11) (2): every vertex of an adjacent-ground region that
    REACHES the coastline (``PlanarMap.quay_refs``, published by
    ``planar/zones.zone_regions`` at the ONE zone derivation site)."""
    refs = frozenset(getattr(planar, "quay_refs", ()) or ())
    if not refs:
        return set()
    out: set[int] = set()
    for f in vw.faces_of_role(GROUND_ROLES):
        if f.ref in refs:
            out.update(vw.rings[f.id])
            for h in vw.holes[f.id]:
                out.update(h)
    return out


def water_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One hard pin per ground vertex standing on water (docstring)."""
    STATS["water_pins"] = {"candidates": 0, "wet": 0}
    fn = getattr(airport.dem, "water_many", None)
    if not callable(fn):
        return []
    vw = view(planar, law)
    ground: set[int] = set()
    for f in vw.faces_of_role(GROUND_ROLES):
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            ground.update(ring)
    if not ground:
        return []
    # a pavement or structure vertex keeps its own law
    keep_out = set(vw.pavement_vertices)
    # §37 (11) (2)/(4) THE QUAY IS THE PAVEMENT'S LEVEL (owner RULINGS
    # 2026-09-15f item 2; Fable 2026-09-15i).  A quay is the strip of land
    # between a pavement edge and the coastline too narrow for the band —
    # ONE PLANE at the pavement edge's level, ending at the coastline in a
    # SEA WALL.  Its ring vertices stand ON the coastline, so the witness
    # reads them wet and the pin would put them at 0.00; the post-pass
    # ``constraints/__init__.water_exempt`` would then drop the quay's own
    # band row, and the 6.10 m fall would come back as a 3 m lip slope
    # (measured at VMMC: 10 pinned quay vertices, 11 ``adjacent_ground_
    # step`` rows at 6.10 m).  The DEM's ocean bleed is never the ground
    # on a quay — this is (4) at the pin's own single site.
    keep_out.update(_quay_vertices(vw, planar))
    for fid, f in planar.faces.items():
        if is_structure_role(law, f.role):
            keep_out.update(vw.rings[fid])
            for h in vw.holes[fid]:
                keep_out.update(h)
    cand = sorted(v for v in ground if v not in keep_out)
    STATS["water_pins"]["candidates"] = len(cand)
    if not cand:
        return []
    xs = np.array([vw.xy[v][0] for v in cand], float)
    ys = np.array([vw.xy[v][1] for v in cand], float)
    try:
        wet, level = fn(xs, ys)
    except Exception:                                     # pragma: no cover
        return []
    rows: list[Row] = []
    for v, is_wet, z in zip(cand, np.asarray(wet), np.asarray(level, float)):
        if not bool(is_wet) or not np.isfinite(z):
            continue
        z = float(z)
        rows.append(Pin(v, z, Source(GEN, RULING,
                                    (f"vertex:{v}", f"level:{z:.3f}"))))
    STATS["water_pins"]["wet"] = len(rows)
    return rows


def water_vertices_pinned(rows) -> set[int]:
    """The vertices this generator pinned (for the exemption post-pass)."""
    return {r.v for r in rows
            if isinstance(r, Pin) and r.source.generator == GEN}
