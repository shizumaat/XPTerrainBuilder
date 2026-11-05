"""TILE-SEAM generator (M3a; §38 THE TILE SEAM IS A PIN, owner RULINGS
2026-09-13ah / 13am).

THE LAW.  The graticule line an airport crosses is cut out of the map as
a band ``law.emit.seam.half_width_m`` each side (user 2026-05-10); the
mesh drapes the DEM in the band, and every vertex bounding it — every
role, the runway included (owner 2026-07-26, v1 ``repin_airside_seam_
cutbacks``: "every AIRSIDE cut-back edge … DEM-anchored HARD") — takes
the DEM (user 2026-07-04 "treat the seam like a runway edge"; owner
2026-07-24 "the tile seam at ALL points must be anchored at DEM").  The
production sampler serves each vertex from ITS tile's baked raster, so
that value is the one the neighbouring tile's mesh meets.

A SEAM VERTEX IS A ``Pin`` — the same object as a CIFP threshold (owner
2026-09-13ah, overruling the M3a softening).  Its column is eliminated by
``solve/rows._reduce``, it holds EXACTLY, and everything grades to it.
The M3a implementation minted a PREFERENCE (``Linear.soft``) and the
pipeline ran a fixed-point "seam pass" over the honoured set; measured at
SPLP (13am) that pass OSCILLATED (45 → 28 → 27 → 28 …) and shipped
``27/150 vertices on the DEM; 123 residual, max 3.430 m`` — a 3 m berm
10 m wide along the seam through the runway strip.  Both the preference
and the pass are DELETED: a pin needs no pass.

WHERE THE LAW BETWEEN TWO PINS CANNOT BE MET the FREE vertices between
them yield, never the pin (13ah).  Two mechanisms carry that, and both
live outside this module because they are other generators' law:

* the graded-strip ZONE BAND yields (``constraints/zones.py``
  :func:`zone_bands`, the ``seam_pin_yield`` clause) — the relax arm
  ``zone_bands −1,670 rows → z−dem after −0.000`` named it as what held
  the seam off its DEM;
* the runway chord takes seam pins as KNOTS (``constraints/
  runway_chord.py`` :func:`_with_seam_knots`), exactly as a crossing pin
  is taken, so the end-zone preference absorbs the curvature between a
  threshold and a seam pin.

A grade row between two seam pins prices terrain against terrain and is
exempt (``constraints.seam_exempt``; the census's own reading with
sidecar ``seam_pins``: pin↔pin skips, pin↔free checks at the body cap).

THE SEAM PIN YIELDS TO A SENIOR DATUM, never the reverse: a water pin
(``constraints.water_exempt``, owner 09m (1)) and a CIFP threshold pin
outrank it — one vertex carries ONE equality, and the withdrawal is
counted (``seam_pin_withdrawn_senior``) rather than left to the order the
reduction happens to see the rows in.

THE VALUE IS THE TILE EDGE'S LINE (owner 2026-11-04, LOWS: "yes").  The
mesh builds each tile edge as ``[emit.seam] edge_segments`` equal segments
per degree, every point at the tile DEM (``O4_Vector_Map.GLUE_SEGMENTS``),
and drapes the band between the pins and that edge.  A pin at the dense DEM
against the edge's ~54 m segments put a ±0.24 m, 7.5 % kink across the
3.2 m band (LOWS lon 13.0).  So a pin takes the edge's straight line at its
own station along the seam: the DEM at the two edge points bracketing it
(sampled on the pin's side of the line, its own tile's raster), linearly
between.  The seam stays DEM-locked at every edge point; a pin whose edge
points read no DEM keeps its own sample (:func:`seam_pin_z`).

Single-tile airports (CYXY) have no seam vertices and mint nothing.
"""
from __future__ import annotations

import math

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["seam_pins", "seam_pin_z", "GEN"]

GEN = "seams"
RULING = "tile seam DEM pin (user 2026-07-04; owner 2026-07-24/26; RULINGS 2026-09-13ah)"


def seam_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """A HARD pin on every seam-band vertex at the tile edge's line (§38
    (1); module doc)."""
    return [Pin(vid, z, Source(GEN, RULING, (f"vertex:{vid}",)))
            for vid, z in sorted(seam_pin_z(planar, law, airport).items())]


def seam_pin_z(planar: PlanarMap, law: Law, airport: Airport) -> dict[int, float]:
    """``{vertex: value}`` of every seam pin — what the solve holds and the
    sidecar publishes (``pipeline/publication``), one reading."""
    out: dict[int, float] = {}
    edge = _edge_line(law, airport)
    for vid in planar.seam_vertices:
        v = planar.vertices[vid]
        if v.dem_z is None:
            continue
        z = edge(*v.key) if edge is not None else None
        out[vid] = float(v.dem_z) if z is None else z
    return out


def _edge_line(law: Law, airport: Airport):
    """``(lat, lon) -> z`` on the nearer graticule line's mesh edge, or
    ``None`` without a DEM and frame."""
    dem = getattr(airport, "dem", None)
    frame = getattr(airport, "frame", None)
    if dem is None or frame is None:
        return None
    n = int(law.tables.emit.seam.edge_segments)
    to_xy = frame.transformers()[0]
    eps = 0.01 / n          # a hundredth of a segment: the pin's own tile

    def at(lat: float, lon: float) -> "float | None":
        lat_line, lon_line = round(lat), round(lon)
        k = math.cos(math.radians(lat))
        if abs(lon - lon_line) * k <= abs(lat - lat_line):
            # a meridian seam: the edge runs north-south at ``lon_line``
            side = lon_line + math.copysign(eps, lon - lon_line)
            pts = _bracket(lat, n)
            zs = [dem.z(*to_xy(side, t)) for t in pts]
            s = lat
        else:
            side = lat_line + math.copysign(eps, lat - lat_line)
            pts = _bracket(lon, n)
            zs = [dem.z(*to_xy(t, side)) for t in pts]
            s = lon
        if any(z is None or math.isnan(z) for z in zs):
            return None
        f = (s - pts[0]) * n
        return float(zs[0] + (zs[1] - zs[0]) * f)

    return at


def _bracket(s: float, n: int) -> tuple[float, float]:
    """The two edge points ``k / n`` degrees bracketing ``s``."""
    lo = math.floor(s * n) / n
    return lo, lo + 1.0 / n


