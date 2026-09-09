"""THE RIGID BODY (RULINGS 2026-09-09b (5)).

An object's CONNECTED geometry moves as ONE rigid body — one delta per
connected component of the OBJ8 mesh — and per-vertex deltas exist only
BETWEEN disconnected components.  A horizontal plane is never split from
the walls that carry it.

``airport/contact.py`` makes one PART per genuine solid component and
``emit/clusters.py`` gives each part one delta, so the first half already
holds.  What was missing is COMPLETENESS: the seat mints deltas only for
the THICKNESS-GATED components (the witness gate, RULINGS 2026-08-26
§2.1 — a part with no vertical extent is ground paint, never a floor
witness), so every floor and ceiling PLANE came out of the seat with no
delta at all and ``object_rebake.apply`` — which always rewrites from
``.anchor_bak`` — left it at its authored y while its walls moved.
Measured on the owner's own 1.0.296 rebake results: HECA 15,729 stranded
components over 190 of 391 written members (15,716 of them flat, the
object moving up to 45 m away); OTHH 44, all flat, +3.816 … +13.142 m,
the interchange drainage basins.

Pure geometry over numpy; no I/O, no law values.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from .obj8 import Component, ObjGeometry

__all__ = ["complete_component_deltas"]


def complete_component_deltas(geom: ObjGeometry, comps: _t.Sequence[Component],
                              delta_by_comp: _t.Mapping[int, float],
                              held: _t.Collection[int] = (),
                              ) -> dict[int, float]:
    """Every component of ``geom`` with a delta (RULINGS 2026-09-09b (5)).

    An object's CONNECTED geometry moves as one rigid body — one delta
    per connected component — and per-vertex deltas exist only BETWEEN
    disconnected components.  The seat mints a delta only for the
    THICKNESS-GATED components (``rebake_plan``'s witness gate, 08-26
    §2.1: a decal never founds a seat), so a horizontal floor or ceiling
    plane — y-extent 0.0 — came out of the seat with none and stayed at
    its authored y while the walls it sits on moved (HECA: 15,716 such
    planes, up to 45 m of separation; OTHH: the 44 planes of the
    interchange drainage basins).  A plane is never split from the walls
    that carry it: a component the seat gave no delta takes the delta of
    the NEAREST component that has one — the minimum 3-D distance
    between their authored vertex sets, ties by lowest component index.

    ``held`` names the components the seat RULED to stay — a facility
    cluster (05p), a cluster under ``min_delta_m`` (08d d), an A3-refused
    cluster, a structure seat that stays.  Those decisions stand, and
    they CARRY: a held component is never given a delta, and a free
    component whose nearest carrier is a held one stays with it.  Only a
    component the seat never CONSIDERED follows at all.

    Returns a new mapping covering every index of ``comps`` except the
    held ones; the input is not modified.  ``{}`` in, ``{}`` out
    (nothing founds a carrier).
    """
    out = {int(k): float(v) for k, v in delta_by_comp.items() if 0 <= int(k) < len(comps)}
    stay = {int(i) for i in held if 0 <= int(i) < len(comps)} - set(out)
    free = [i for i in range(len(comps)) if i not in out and i not in stay]
    if not out or not free:
        return out
    from scipy.spatial import cKDTree
    carriers = sorted(set(out) | stay)
    v = geom.vertices
    pts_list, owner_list = [], []
    for ci in carriers:
        idx = np.unique(comps[ci].tris.reshape(-1))
        pts_list.append(v[idx])
        owner_list.append(np.full(idx.shape[0], ci, dtype=np.int64))
    tree = cKDTree(np.concatenate(pts_list))
    owner = np.concatenate(owner_list)
    # ONE query for every free vertex in the file (HECA's 1,485-component
    # terminal sheets are 733 free components each: per-component queries
    # cost 2.3 s over the airport, one batched query 0.2 s)
    q_pts, spans = [], []
    at = 0
    for ci in free:
        idx = np.unique(comps[ci].tris.reshape(-1))
        if idx.size == 0:
            continue
        q_pts.append(v[idx])
        spans.append((ci, at, at + idx.shape[0]))
        at += idx.shape[0]
    if not q_pts:
        return out
    dist, near = tree.query(np.concatenate(q_pts), k=1)
    carrier = owner[near]
    for ci, lo, hi in spans:
        d = dist[lo:hi]
        # the nearest carrier; a tie in distance resolves to the lowest
        # component index so the write is deterministic
        best = float(d.min())
        host = int(carrier[lo:hi][d <= best + 1e-9].min())
        if host in out:
            out[ci] = out[host]
        # else: the nearest carrier is HELD — this component stays with it
    return out
