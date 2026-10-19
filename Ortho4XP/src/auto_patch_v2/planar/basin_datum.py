"""THE RIM TOPS OUT AT THE AUTHOR'S GROUND TOO — a basin witness whose
shell stands up out of the ground it was placed on is a thing standing up,
never a pit (issue #942).

04i rule 1 reads a witness's rim against the LOCAL ground — the DEM under
the component's centroid — and admits what rises above that band as a
PROTRUSION up to ``rim_protrusion_max_fraction`` of the component's face
area (RULINGS 2026-09-06f: a tower in the pit).  Rule 5b (RULINGS
2026-09-09ag) already reads the FLOOR against a second reference, the
placement's own render datum, because one ground sample is not the
author's frame.  The rim is read the same way here, against THE AUTHOR'S
GROUND: the ground at the placement's anchor, or its render datum where a
lift stands it above that (a sink — a negative ``OBJECT_AGL`` — is the
author setting the shell down into the ground, so the anchor's ground
governs; a lift never relaxes the gate, as 5b's datum never does).  A pit
is a hole modelled under that ground, so its shell tops out there; a
component with more than ``rim_protrusion_max_fraction`` of its face area
above it + ``contact_band_m`` is not a pit, whatever the DEM under its
centroid says.

Measured (lane c942, captures of main 7e5ae9cc): every basin witness of
OTHH (the Drainage / Dewatering pits), LEMD (the T4S pit, LEMD85's tower
included) and VHHH (the sea barriers and tunnel shells; ``sea.obj``, sunk
4.4 m, 2.4 %) holds 0.0-2.4 % of its face area above it; KSEZ's three
rock formations (``South_Airport_Ridge`` and ``South_Island_Range_LOD00``,
``OBJECT_MSL`` placed on the ground at their anchors, ``Devils_Bridge``
sunk 2.5 m) hold 93.5 / 94.5 / 67.7 % — terrain skins over 74-175 m of
relief, read against centroid grounds 22-175 m over their datums, which
admitted them as covered pits 42-95 m deep.  KSEZ's ``basin:1`` then put
the trench floor 63 m under the DEM (``basin.floor = rim - body_depth``
off a ring with 87 m of relief): the solve's ``off_ground`` refusal, and
the airport shipped unpatched.

The test is applied where the region pass takes its members, so it
refuses BASINS only: the placement keeps its witness for every other
reader of ``PlacedObject.witnesses`` (rule 1's derivation in ``obj8`` is
unchanged).  No new law number: the band and the fraction are rule 1's.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import typing as _t

from ..airport import obj8

__all__ = ["standing_out_of_ground"]


def standing_out_of_ground(witnessed: _t.Sequence["obj8.PlacedObject"],
                      cache: "obj8.ResourceCache", band_m: float, max_fraction: float
                      ) -> tuple[list["obj8.PlacedObject"], list[str]]:
    """``(the placements with the witnesses that top out at the author's
    ground, one refusal line per witness that does not)``.  A placement
    left with no witness is dropped from the list."""
    kept: list = []
    refused: list[str] = []
    for o in witnessed:
        g = cache.geometry(o.resolved) if o.resolved else None
        if g is None:
            kept.append(o)
            continue
        comps = cache.components(o.resolved)
        # the author's ground in the object's own y: the anchor's ground,
        # or the datum (y = 0) where a lift stands it above that
        plane = max(0.0, float(o.anchor_z) - o.base_z) + band_m
        ok = []
        for w in o.witnesses:
            frac = obj8.area_fraction_above(g.vertices, comps[w.comp_index], plane) \
                if 0 <= w.comp_index < len(comps) else 0.0
            if frac <= max_fraction:
                ok.append(w)
                continue
            refused.append(
                f"{o.id} {os.path.basename(o.path)}#{w.comp_index}: {frac:.0%} of its face area "
                f"stands above the ground it was placed on + contact_band_m {band_m} (> "
                f"rim_protrusion_max_fraction {max_fraction:.0%}; over its datum: that ground "
                f"{plane - band_m:+.1f} m, top {w.z_top - o.base_z:+.1f} m, floor "
                f"{w.z_min - o.base_z:+.1f} m, the centroid's ground "
                f"{w.ground_z - o.base_z:+.1f} m) — a shell standing up out of its ground "
                f"(a rock, a hill, a building over real relief), never a pit (issue #942: "
                f"04i rule 1 read against the author's ground, as 09ag rule 5b reads the "
                f"floor against the datum)")
        if len(ok) == len(o.witnesses):
            kept.append(o)
        elif ok:
            kept.append(_dc.replace(o, witnesses=tuple(ok)))
    return kept, refused
