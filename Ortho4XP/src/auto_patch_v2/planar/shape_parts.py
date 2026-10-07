"""A GAP PART IS ONE SHAPE BY KIND, AND ITS KNIVES ARE ITS ONLY JOINTS
(spec §55 (15) rule A+C; owner RULINGS 2026-10-04u, 06d) — the labels of the
§55 gap parts, beside ``planar/shapes`` as the apron law
(``shape_airside``) and the mouth weld (``shape_mouths``) are.

THE DEFECT this replaces.  08k labels standing pavement: the pavement
UNION is eroded by half the mouth and a vertex takes the nearest surviving
body, because the map must FIND a standing apron's terraces.  A gap part's
identity is already decided — by the CUT, from the pair test over its
stations (§55 (2)) — and 08k re-decided it from the wrong population: two
parts across a 0.75 m knife welded to one apron were one body with it (no
joint possible along the knife), and a part narrower than the mouth at a
neck was split into two bodies, a contour cut through its one face and
every row across it withdrawn (MEASURED at HECA, §55 (15): 668 of 760
knife step rows with one label on both rims; 112 of 132 contours inside
one part; a 4.95 m step over 3.2 m at a neck).

THE RULE.  (1) A gap part's faces are left OUT of the pavement union
(``planar.shapes._label_pavement``): the standing faces are labelled as on
the map without the part.  (2) After the standing labelling every STEP
PART (``model.planar.gap_step_part``: a lot and its ramp are one) mints
ONE label, taken by every vertex of its faces that is not network and that
no standing face labelled — a WELDED RIM vertex keeps the standing label.
(3) The shape of a gap-part FACE is its own step part's, by kind, never
the vertex majority (a sliver along an apron would take the apron's shape
and the body datum would drop the part's own vertices).  (4) A pair inside
one part is one shape whatever labels its rim carries
(``model.planar.shares_gap_part``, read by ``straddles`` and
``declarable_pairs``)."""
from __future__ import annotations

import typing as _t

from ..model.planar import NO_SHAPE, PlanarMap, face_vertex_set, gap_step_part

__all__ = ["label_gap_parts", "part_shape_of_face"]


def label_gap_parts(pm: PlanarMap, label: dict[int, int],
                    N: _t.AbstractSet[int]) -> dict[int, int]:
    """Rule 2: mint one label per step part INTO ``label`` and return
    ``{gap-part face id: its step part's label}`` (empty without a gap
    face: a sheet-free map takes no branch).  Parts in ref order, so the
    labels are deterministic."""
    faces = sorted((key, fid) for fid, f in pm.faces.items()
                   if (key := gap_step_part(f.ref)) is not None)
    if not faces:
        return {}
    first = max(label.values(), default=NO_SHAPE) + 1
    of_part: dict[str, int] = {}
    out: dict[int, int] = {}
    for key, fid in faces:
        lab = of_part.setdefault(key, first + len(of_part))
        out[fid] = lab
        for v in sorted(face_vertex_set(pm, pm.faces[fid])):
            if v not in N:
                label.setdefault(v, lab)        # a welded rim vertex keeps the standing label
    return out


def part_shape_of_face(part_label: _t.Mapping[int, int], label: _t.Mapping[int, int],
                       find: _t.Callable[[int], int]) -> dict[int, int]:
    """Rule 3: ``{gap-part face id: its shape}`` through the welds
    (``find``).  A part none of whose vertices carries its label (every one
    welded or network) has no shape of its own and is left to the vertex
    majority."""
    carried = set(label.values())
    return {fid: s for fid, lab in part_label.items() if (s := find(lab)) in carried}
