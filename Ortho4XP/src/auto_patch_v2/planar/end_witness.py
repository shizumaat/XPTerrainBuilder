"""A BORE END THAT NEEDS A PORTAL WITNESS (owner RULINGS 2026-11-03b (6),
Q345 a, and the owner's answers of 2026-11-03T06:07:15Z; spec
``docs/specs/rail-piece-ends-station-spec.md`` R2 / R6; issues #1738, #1739).

"A deep mapped tunnel is never opened; rail is open only where a pack
trench or station object, or the lidar, shows an open cut."  Answer 3:
inside the airport boundary each end of a SERVICE tunnel needs the same
per-end witness.  So an end of a bore that is

* RAIL (any way carries ``railway``),
* DEEP (its lowest ``layer`` at or under ``[tunnel] deep_layer_max``) where
  no mapped way comes out of the end, or
* a fenced SERVICE bore (``highway=service``, the end inside the airport
  boundary),

is a mouth only where one of these stands AT THAT END (within ``[tunnel.
object] bore_end_tolerance_m``):

1. a pack HARD DECK (``planar/deck_bridge``, ``on_field.deck_polys``) -- the
   ground under a hard-deck bridge is open (11-03b (1));
2. a pack TUNNEL CORRIDOR's footprint (``on_field.corridor_prints``; the
   object then takes the mouth by precedence);
3. a pack part standing below grade (``structure_fence._Portals``, 27z
   witness 3, read per end);
4. a CREDIBLE lidar inset reading a cut along the end's approach
   (``structure_fence._LidarCut``, 27z witness 5);
5. a COMPANION TERRAIN MESH's cut (``airport/terrain_mesh_witness``, answer
   4);
6. a pack PORTAL pinning that end (``on_field.portal_ends``: a roofed,
   hanging or entrance object, ``airport/portal_objects``) -- the author
   stated the opening (owner 2026-11-04 KBUF: the service bores under the
   runway and the parking lot carry ``Road_Tunnel.obj`` /
   ``KBUF_Terminal_Parking_Underpass.obj`` and were refused here).

With none the end is not opened -- no ramp, no trench -- and the refusal is
named beside #1028's.  MEASURED ENGM: the six switch ends R1 already
refuses; the four rail underpasses 2-6 km out read no witness; the north
rail portal reads the hard deck ``Ham3.obj`` over it; ``-766`` (an airside
service tunnel under the terminal front) reads none, where the companion
mesh is flat.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point

from ..law import Law

__all__ = ["EndWitness", "needs_witness"]


def _lowest_layer(bore) -> int | None:
    vals = []
    for w in bore.ways:
        try:
            vals.append(int(str((w.tags or {}).get("layer"))))
        except (TypeError, ValueError):
            pass
    return min(vals) if vals else None


def needs_witness(bore, end, law: Law, fence, surfaces: bool = True) -> str | None:
    """Which per-end rule ``end`` of ``bore`` falls under (``"rail"``,
    ``"deep"``, ``"service"``), or ``None``: today's tests alone.
    ``surfaces``: a mapped way comes out of the end (its approach walked
    one); a DEEP end only asks where none does (spec R2 (a))."""
    tags = [w.tags or {} for w in bore.ways]
    if any("railway" in t for t in tags):
        return "rail"
    lay = _lowest_layer(bore)
    if lay is not None and lay <= law.tables.structures.tunnel.deep_layer_max \
            and not surfaces:
        return "deep"
    if fence is not None and any(t.get("highway") == "service" for t in tags) \
            and fence.covers(Point(end)):
        return "service"
    return None


class EndWitness:
    """The six per-end witnesses over one structures pass (module doc)."""

    def __init__(self, on_field, law: Law) -> None:
        from .structure_fence import _LidarCut, _Portals
        airport = getattr(on_field, "airport", None)
        self._tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
        self._decks = list(getattr(on_field, "deck_polys", ()) or ())
        self._prints = [p for p in (getattr(on_field, "corridor_prints", ()) or ())
                        if p is not None and not p.is_empty]
        self._pins = list(getattr(on_field, "portal_ends", ()) or ())
        self._portals = _Portals(airport, law, ()) if airport is not None else None
        self._lidar = _LidarCut(airport, law) if airport is not None else None
        # read at load (``pipeline/build.pack_stage``), never here
        self._mesh = getattr(airport, "terrain_mesh", None)
        self._reach = 2.0 * float(law.tables.structures.tunnel.mouth_depth_m) \
            / float(law.tables.structures.tunnel.ramp_max_grade)

    def at(self, end, path: _t.Sequence) -> str | None:
        """The witness standing at ``end`` (its approach ``path``), named,
        or ``None``."""
        pt = Point(end)
        for p in self._decks:
            if p.distance(pt) <= self._tol:
                return "a pack hard deck over it"
        for p in self._prints:
            if p.distance(pt) <= self._tol:
                return "a pack tunnel corridor"
        for xy, oid, res in self._pins:
            if pt.distance(Point(xy)) <= self._tol:
                return f"the pack portal {oid} {res.rsplit('/', 1)[-1]}"
        if self._portals is not None:
            got = self._portals.at_end(end)
            if got:
                return got
        if self._lidar is not None and len(path) >= 2:
            ln = LineString(path)
            from shapely.ops import substring
            if self._lidar.cut(substring(ln, 0.0, min(ln.length, self._reach))):
                return "a credible lidar cut on its approach"
        if self._mesh is not None:
            c = self._mesh.at(end, self._tol)
            if c is not None:
                return f"the companion terrain mesh's cut {c.depth_m:.1f} m under its field"
        return None
