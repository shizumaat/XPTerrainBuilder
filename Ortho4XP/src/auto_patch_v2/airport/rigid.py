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
                              contact_tol_m: float = 0.0,
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
    that carry it.

    THE CARRIER IS THE COMPONENT IT TOUCHES (RULINGS 2026-09-09z (4)):
    a free component's carrier is the considered component its geometry
    is IN CONTACT with — a carrier vertex within ``contact_tol_m``
    (``emit.identity.min_distinct_spacing_m``, the identity spacing:
    two points closer than it are the same point to every emit law) of
    one of its own — and, where several touch, the one it touches MOST
    (the number of its own vertices in contact with that carrier; ties
    by lowest component index).  ``solid_components`` welds by rounded
    position, so a genuinely SHARED vertex is contact at distance 0 and
    is counted by the same test.  Only when NOTHING touches does the
    carrier fall back to the nearest by distance (a canopy standing off
    its mast, ties again by lowest index).  ``contact_tol_m = 0.0``
    keeps the pre-09z pure-nearest rule (the default: the law value is
    the caller's, never this module's).

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
    q_all = np.concatenate(q_pts)
    dist, near = tree.query(q_all, k=1)
    carrier = owner[near]
    # THE CONTACT TEST (09z (4)): every (free vertex, carrier vertex)
    # pair within the identity spacing, in ONE C-level call — the pair
    # list is short because distinct components never share a position
    # (``solid_components`` welds to the millimetre), so only genuine
    # abutments appear.  Counting is then numpy: HECA's 15.7 k free
    # components cost 0.3 s over the airport against the 0.2 s the k=1
    # query already spends.
    touch_lo = touch_hi = None
    if contact_tol_m > 0.0:
        pairs = cKDTree(q_all).sparse_distance_matrix(
            tree, float(contact_tol_m), output_type="ndarray")
        if pairs.size:
            # one vote per (free vertex, carrier component) pair
            fv = pairs["i"].astype(np.int64)
            cc = owner[pairs["j"].astype(np.int64)]
            # np.unique(axis=0) returns the pairs sorted by (vertex,
            # component), which is the grouping the spans below read
            votes = np.unique(np.stack([fv, cc], axis=1), axis=0)
            touch_lo = np.searchsorted(votes[:, 0], np.arange(q_all.shape[0]), "left")
            touch_hi = np.searchsorted(votes[:, 0], np.arange(q_all.shape[0]), "right")
            touch_owner = votes[:, 1]
    for ci, lo, hi in spans:
        host = None
        if touch_lo is not None:
            a, b = int(touch_lo[lo]), int(touch_hi[hi - 1])
            if b > a:
                # the carrier this component touches MOST; a tie in the
                # contact count resolves to the lowest component index
                who, n = np.unique(touch_owner[a:b], return_counts=True)
                host = int(who[np.lexsort((who, -n))[0]])
        if host is None:
            d = dist[lo:hi]
            # nothing touches: the nearest carrier; a tie in distance
            # resolves to the lowest component index so the write is
            # deterministic
            best = float(d.min())
            host = int(carrier[lo:hi][d <= best + 1e-9].min())
        if host in out:
            out[ci] = out[host]
        # else: the carrier is HELD — this component stays with it (09z
        # (4): a held carrier holds its planes)
    return out
