"""THE TILE SEAM OUTRANKS A CIFP THRESHOLD (owner RULINGS 2026-10-26b,
issue #1346).

The owner, verbatim: "Like SPLP, or any airport on a tile boundary, the
tile boundary has to trump everything to ensure a smooth edge, so it would
allow cifp to move if required".

THE CONFLICT.  A §38 seam vertex is a ``Pin`` at its own tile's DEM sample,
and a CIFP threshold is a ``Pin`` at the published threshold elevation.
Where a runway crosses a tile seam near a threshold whose CIFP value
stands off the DEM, no lawful runway joins the two.  Measured at PANC
15/33, lon −150: the RWY 33 displaced threshold is 36.881 m over a DEM of
36.335 m, 8.8 m across the runway from a seam pin at 36.270 m.  Stage 1
was hard-infeasible (vertical curve, transverse maximum), and the built
ridge stepped 1.0 m over 11.9 m (``docs/findings/l1346-panc-tile-edge.md``).

THE RULE, at ONE derivation site (:func:`seam_thresholds`).  A CIFP
threshold is SEAM-YIELDING when a §38 seam pin on its own runway family
lies nearer than the shortest run in which that runway's vertical curve
can turn through the threshold's datum difference:

    reach = sqrt(2 · R · |z_cifp − DEM|),   R = 1 / (grade change per metre)

where the grade change per metre is ``tables.runway_vertical_curve_bound``
at a 1 m spacing (Annex 14 §3.1.15/16).  Inside that reach no lawful
profile can join the threshold to the seam, so the conflict is the
seam's, not some other row's.  ``runway_profile`` mints such a threshold's
``Pin`` under :data:`RULING`, whose head is in ``[design]
yielding_pin_rulings``.  The solve then holds the pin unless the pin is in
conflict itself; if it is, the pin is released to a design target at the
CIFP value (``solve/pin_yield.yield_pins``, issue #778), so the threshold
moves JUST ENOUGH to be lawful against the seam pins and the runway
family's caps.  ``runway_yield`` does not raise the runway's cap for the
(seam pin, seam-yielding threshold) span: the threshold yields, not the
cap.  The yield is NEVER silent.  ``pipeline/emit_stage.with_threshold_yield``
reads the release, records ``PlanarMap.threshold_seam_yield``, says one
loud line, and the sidecar publishes ``threshold_seam_yield``.

A runway that crosses no seam mints nothing new, so every single-tile
airport reads exactly as before.
"""
from __future__ import annotations

import dataclasses as _dc
import math

from ..law import Law
from ..law.tables import runway_vertical_curve_bound
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import RUNWAY_FAMILY, _axis, _end_vertex, ridge_chains

__all__ = ["SeamThreshold", "RULING", "RULING_HEAD", "seam_thresholds",
           "yield_records"]

#: The ruling head of a seam-yielding threshold ``Pin``.  It is listed in
#: ``[design] yielding_pin_rulings`` (``law/emit.toml``).
RULING_HEAD = "runway.threshold yields to the tile seam"
RULING = f"{RULING_HEAD} (owner RULINGS 2026-10-26b; issue #1346)"


@_dc.dataclass(frozen=True)
class SeamThreshold:
    """One CIFP threshold that the tile seam outranks: the threshold's
    ridge vertex, its runway end, its CIFP value, the DEM under it, the
    nearest seam pin of its own runway family (vertex, value, and plan
    distance), and the vertical-curve reach that the distance falls inside."""

    v: int
    runway: str
    end: str
    cifp_m: float
    dem_m: float
    seam_v: int
    seam_z_m: float
    seam_d_m: float
    reach_m: float


def _family_vertices(vw, rid: str) -> set[int]:
    """Every vertex of a runway-family face belonging to runway ``rid``
    (a ``runway_crossing`` face names both runways, ``a+b``)."""
    out: set[int] = set()
    for f in vw.faces_of_role(RUNWAY_FAMILY):
        refs = [f.ref] if f.role == "runway" else str(f.ref).split("+")
        if rid in refs:
            out.update(vw.face_vertices(f.id))
    return out


def seam_thresholds(planar: PlanarMap, law: Law, airport: Airport
                    ) -> dict[int, SeamThreshold]:
    """Threshold vertex -> :class:`SeamThreshold`, for every CIFP threshold
    that the tile seam outranks (module docstring).  Empty when the map
    carries no seam vertex."""
    seam = planar.seam_vertices
    if not seam:
        return {}
    vw = view(planar, law)
    chains = ridge_chains(vw)
    out: dict[int, SeamThreshold] = {}
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        pins = [v for v in _family_vertices(vw, rw.id) & set(seam)
                if planar.vertices[v].dem_z is not None]
        rate = runway_vertical_curve_bound(law, 1.0, rw.code_number, rw.code_letter)
        if not pins or not rate or rate <= 0.0:
            continue
        _a, ux, uy = _axis(rw)
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            if end.threshold_elev_m is None:
                continue
            v = _end_vertex(vw, all_ids, rw, end, ux, uy)
            dem = planar.vertices[v].dem_z
            if dem is None or v in seam:
                continue
            cifp = float(end.threshold_elev_m)
            reach = math.sqrt(2.0 * abs(cifp - float(dem)) / rate)
            p = min(pins, key=lambda q: vw.dist(v, q))
            d = vw.dist(v, p)
            if d < reach:
                out[v] = SeamThreshold(
                    v=v, runway=rw.id, end=end.name, cifp_m=cifp,
                    dem_m=float(dem), seam_v=p,
                    seam_z_m=float(planar.vertices[p].dem_z), seam_d_m=d,
                    reach_m=reach)
    return out


def yield_records(planar: PlanarMap, law: Law, airport: Airport,
                  pin_yield, z=None, tol_m: float = 0.0
                  ) -> dict[int, tuple[float, float, float, str]]:
    """Vertex -> ``(CIFP value, built value, distance to the seam, end)``
    for every seam-yielding threshold the solve released (``pin_yield``,
    the ``DesignReport.pin_yield`` records) and that the built surface
    ``z`` holds more than ``tol_m`` off its CIFP value."""
    st = seam_thresholds(planar, law, airport)
    out: dict[int, tuple[float, float, float, str]] = {}
    for r in pin_yield or ():
        v = int(r["v"])
        rec = st.get(v)
        if rec is None:
            continue
        zb = float(z[v]) if z is not None and len(z) > v else float(r["z_m"])
        if abs(zb - rec.cifp_m) > tol_m:
            out[v] = (rec.cifp_m, zb, rec.seam_d_m, f"{rec.runway} RWY {rec.end}")
    return out
