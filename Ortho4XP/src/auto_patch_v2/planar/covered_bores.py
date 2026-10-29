"""A COVERED ROAD IS A BORE WHERE A CUT OR A TRENCH OBJECT SAYS SO (owner
2026-10-28, RULINGS 2026-10-28s (5), Q255 a; amends 2026-09-11aq A; issue
#1028, spec ``eddf-tunnel-mouths-spec.md`` E2).

11aq A admits only ``tunnel=yes`` as a bore.  A road mapped ``covered=yes``
under an apron is the same road in a tunnel when the ground shows it:

* the credible survey reads a cut at one of its mapped ends — R1's own
  clearance (``lidar_road.end_clearance``: the cover over the way's first
  stretch inside the end less the surveyed road at it) of at least
  ``[channel] object_min_depth_m``; or
* a pack trench object (``airport/trench_objects``) stands at one of its
  ends.

The test reads a CHAIN of covered ways (``structure_approach.chains``: a
covered road split into several ways has its ends at the chain's ends, not
at the joints mid-cover).  An admitted chain's ways enter the bore set as
copies tagged ``tunnel=yes`` (and ``o4_covered``, the witness); everything
downstream — R1 at each end, the slide, 31h's duals — is the bore law's.
MEASURED EDDF: the 2 + 2-lane tertiary dual under the taxiway bridges east
of the runway 25R threshold is ``covered=yes`` along 207 m; the survey
reads 104 m at its ends under a 111 m cover, and only the 40 m under the
taxiway bridge was bored (§34 (5)), reading "no cut".
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import Point

from ..airport.trench_objects import covered_candidates
from ..law import Law
from ..model.airport import OsmWay
from .lidar_road import end_clearance
from .structure_approach import carriageway_width_m, chains

__all__ = ["covered_bore_ways"]


def covered_bore_ways(airport, law: Law, credible: bool, trenches: _t.Sequence = (),
                      start_m: float = 0.0) -> tuple[list[OsmWay], list[str]]:
    """``(the admitted covered ways as bore ways, one note per chain read)``
    (module doc).  ``start_m`` is the cap's stand-off inside the end (R1's)."""
    cands = covered_candidates(getattr(airport, "osm_ways", ()))
    if not cands:
        return [], []
    tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
    need = float(law.tables.structures.channel.object_min_depth_m)
    out: list[OsmWay] = []
    notes: list[str] = []
    for b in chains(cands):
        ids = "+".join(str(w.id) for w in b.ways)
        why = ""
        for end in (b.points[0], b.points[-1]):
            t = next((t for t in trenches if t.outline.distance(Point(end)) <= tol), None)
            if t is not None:
                why = f"the pack trench object {t.object_id} stands at its end"
                break
            if credible:
                width = max(carriageway_width_m(w.tags, law) for w in b.ways)
                c = end_clearance(airport, law, b.points, end, width, start_m)
                if not math.isnan(c) and c >= need:
                    why = (f"the survey reads a {c:.2f} m cut at its end "
                           f"(>= object_min_depth_m {need})")
                    break
        if not why:
            continue
        notes.append(f"covered road {ids}: a bore — {why} (RULINGS 2026-10-28s (5), Q255 a)")
        out.extend(_dc.replace(w, tags={**w.tags, "tunnel": "yes", "o4_covered": "yes"})
                   for w in b.ways)
    return out, notes
