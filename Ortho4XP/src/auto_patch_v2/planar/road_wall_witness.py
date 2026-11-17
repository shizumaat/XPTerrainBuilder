"""THE WALL THAT LINES A ROAD CUT — the witness the zone-2 road shadow needs
(owner 2026-11-17T12:53Z, #2122 item 3, option (a); refines 19ad, #951).

``planar/road_shadow`` lifts a band vertex beside a zone-2 road to the DEM
past the road's cut.  That is right only where something HOLDS the cut at
the road: a wall the band stands on top of.  Where none lines the road the
ground beside it is a natural bank, and the band follows its own ground
down to the road (NZWN -41.316911, 174.807320: three band vertices 1-3 m
from the kerb lifted 2.2-2.6 m onto a bank, a near-vertical 2.5-3 m step).

A vertex is WITNESSED (:meth:`RoadWitness.lines`) when, on its cross-section
from the road's axis to the vertex, there stands

* a PACK wall or fence: a line facade the pack draws as a fence, barrier or
  wall (``classify/fence_division.fence_lines``, the one pack-fence reader)
  or a wall-class pack component (``planar/shore.pack_shore_walls``, the one
  wall classifier);
* a MAPPED retaining wall: an OSM way ``barrier=retaining_wall`` /
  ``wall=retaining_wall`` (the shore feed's tags, ``planar/shore``);

or the road's axis there runs in a MAPPED cut: an open ``cutting=*`` way's
carriageway (``classify/pad_cut_corridor.cutting_corridors``, grown by the
identity snap margin).  A witness beyond the vertex holds nothing between it
and the road: the vertex stands at the wall's foot, on the road's side, and
a wall is not grown — MEASURED NZWN: a vertex 0.2 m short of the pack fence
(-41.316998, 174.807352) lifted 1.8 m under a grown wall drew the step 2.8 m
from the fence instead of at it."""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

from ..law import Law
from ..law.tables import snap_margin_m

__all__ = ["RoadWitness", "road_witness", "MAPPED_RETAINING"]

#: the OSM tags that map a retaining wall (a subset of ``planar/shore``'s
#: ``SHORE_WALL_TAGS``: a free-standing ``barrier=wall`` retains nothing)
MAPPED_RETAINING = {"barrier": "retaining_wall", "wall": "retaining_wall"}


@_dc.dataclass
class RoadWitness:
    """The walls and the mapped cuts of an airport (frame xy)."""

    walls: object = None
    cuts: object = None
    tol: float = 0.0

    def __post_init__(self):
        self._walls = prep(self.walls) if self.walls is not None else None
        self._cuts = prep(self.cuts.buffer(self.tol)) if self.cuts is not None else None

    def lines(self, foot: Point, p: Point) -> bool:
        """A wall stands between the road's axis at ``foot`` and ``p``, or
        the road runs in a mapped cut at ``foot`` (module docstring)."""
        if self._cuts is not None and self._cuts.contains(foot):
            return True
        return self._walls is not None and self._walls.intersects(LineString([foot, p]))


def road_witness(airport, law: Law) -> RoadWitness:
    """Every wall witness and mapped cut of ``airport`` (module docstring)."""
    from ..classify.fence_division import fence_lines
    from ..classify.pad_cut_corridor import cutting_corridors
    from ..classify.rules import load_rules
    from .shore import pack_shore_walls
    walls = [ln for _i, ln in fence_lines(airport, load_rules())]
    walls += [w.poly for w in pack_shore_walls(airport)]
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if len(w.points) >= 2 and any(tags.get(k) == v for k, v in MAPPED_RETAINING.items()):
            walls.append(LineString(w.points))
    cuts = cutting_corridors(airport, law, covered=False)
    return RoadWitness(unary_union(walls) if walls else None,
                       None if cuts is None or cuts.is_empty else cuts,
                       snap_margin_m(law))
