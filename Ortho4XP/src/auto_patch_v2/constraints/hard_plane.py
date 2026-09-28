"""§42 (1b) THE HARD GROUND PLANE IS GRADED LEVEL (owner RULINGS 2026-09-27a
(5); spec ``docs/specs/hard-plane-apron-spec.md``; issue #20).

A pack object that is a HARD, zero-thickness plane at Y = 0 with no draped
layer (NLWF ``pavement/vele_apron.obj``) is admitted as pavement by
``airport/object_pavement`` under ``[load] object_pavement_hard_planes``;
its bodies carry the pavement-id prefix ``HARD_PLANE_PREFIX``.  X-Plane
draws such an object LEVEL at its anchor — it cannot tilt — so the ground
under it is ONE level: every vertex of every hard-plane face is one ``Flat``
group, the §09p (3) body datum does not apply to it (``solve/design`` drops
these vertices from the DEM plane fit, as it drops a fronting pad's), and
the level is the one its runway-edge frontage gives through the ordinary
airside rows (no-step, within-shape) — no DEM datum.

A vertex the plane shares with a RUNWAY-family face is left out of the
group: the runway is fixed before the apron (§20b) and its edge is not
level to the millimetre, so the weld is carried by the no-step rows across
that edge, never by making the runway's own vertices one unknown.
"""
from __future__ import annotations

from ..airport.object_pavement import is_hard_plane_ref
from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Flat, Row, Source
from ..model.planar import PlanarMap

__all__ = ["hard_plane_level", "hard_plane_vertices", "GEN"]

GEN = "hard_plane_level"
RULING = ("a hard Y=0 ground plane is graded LEVEL at its runway-edge frontage, "
          "no DEM datum (owner RULINGS 2026-09-27a (5))")

_RUNWAY_FAMILY = ("runway", "runway_crossing")

STATS: dict[str, dict] = {}


def hard_plane_vertices(planar: PlanarMap) -> set[int]:
    """Every ring and hole vertex of every hard-plane face."""
    out: set[int] = set()
    for f in planar.faces.values():
        if not is_hard_plane_ref(getattr(f, "ref", None)):
            continue
        out.update(planar.ring_vertices(f.ring))
        for h in f.holes:
            out.update(planar.ring_vertices(h))
    return out


def hard_plane_level(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """ONE ``Flat`` over the hard plane's vertices (module docstring)."""
    vs = hard_plane_vertices(planar)
    STATS[GEN] = {"vertices": len(vs), "runway_shared": 0}
    if len(vs) < 2:
        return []
    runway: set[int] = set()
    for f in planar.faces.values():
        if f.role in _RUNWAY_FAMILY:
            runway.update(planar.ring_vertices(f.ring))
            for h in f.holes:
                runway.update(planar.ring_vertices(h))
    group = tuple(sorted(vs - runway))
    front = sorted(vs & runway)
    STATS[GEN]["runway_shared"] = len(front)
    if len(group) < 2:
        return []
    src = Source(GEN, RULING, (f"vertices:{len(group)}", f"frontage:{len(front)}"))
    # THE LEVEL IS THE FRONTAGE'S through the ordinary airside rows across
    # the shared runway edge (no-step, within-shape) — no DEM datum pulls
    # it.  An explicit hard "level == mean(frontage)" row was tried and is
    # NOT enforced by the staged solve (measured NLWF: 0.090 m residual
    # with "0 hard violated"), so it is not minted: the residual is
    # reported instead (plane 5.01 m against a 4.86-4.98 m frontage).
    return [Flat(group, src)]
