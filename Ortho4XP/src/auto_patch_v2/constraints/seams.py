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

Single-tile airports (CYXY) have no seam vertices and mint nothing.
"""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["seam_pins", "seam_vertices_pinned"]

GEN = "seams"
RULING = "tile seam DEM pin (user 2026-07-04; owner 2026-07-24/26; RULINGS 2026-09-13ah)"


def seam_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """A HARD DEM pin on every seam-band vertex (§38 (1))."""
    rows: list[Row] = []
    for vid in sorted(planar.seam_vertices):
        v = planar.vertices[vid]
        if v.dem_z is None:
            continue
        rows.append(Pin(vid, float(v.dem_z),
                        Source(GEN, RULING, (f"vertex:{vid}",))))
    return rows


def seam_vertices_pinned(rows) -> set[int]:
    """The vertices the seam generator pinned (for the pair exemption)."""
    return {r.v for r in rows
            if isinstance(r, Pin) and r.source.generator == GEN}
