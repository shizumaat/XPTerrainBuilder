"""S6 THE RIGID BUILDING UNIT — CONTENTS (spec
``pack-read-once-fast-spec.md`` §F.2 / F.9 R1, issue #30; owner RULINGS
2026-09-18q/18t; issue #10 [HECA-5]).

Owner (verbatim, §F): *"for a given freestanding building (with some space
all around it), it could have thousands of components, interiors, people,
chairs, you name it, that don't matter other than they need to stay in
their same relative position to their surrounding building if we reseat
it."*  And F.9: *"Anything that intersects the building ... is just
treated as part of that building and moves with it."*

§16g (10) (4) (RULINGS 2026-09-14ah) made only a WALLED body (tallest
component >= ``[placement] chain_min_height_m``) a LINK of a footprint
unit, and — because the unit was then the walled bodies alone — every
LEAF (a glass pane, a door leaf, a floor slab, a window frame, a chair)
was seated on its OWN ground or its own carrier.  MEASURED on the
hecabodies closing plan (HECA, 22,032 plan bodies): 13,762 leaves, 11,874
of them inside a walled host's outline, and **3,091 of those seated apart
from their host (2,573 by more than 0.5 m, 994 by more than 2 m)** —
``black_glass_NOANPHA`` 794, ``door`` 457, ``metal`` 444: the windows and
the doors the owner reads as missing, and the upper levels read as
separated.

THE RULE, ONE DERIVATION.  A leaf body is CONTENTS of a host when at least
``[placement] contents_min_fraction`` of its plan footprint lies inside
the host's outline widened by ``footprint_touch_m`` — the host being a
§16g unit's WALLED bodies (their component rings, union) or a walled body
that chains with nothing.  Contents JOIN the host's unit: one zero, the
unit's.  They never LINK (§16g (10) (4) stands: the chain is computed over
the walled bodies first and the contents are attached to its result, so no
two units can merge through a leaf) and they add nothing to the unit's
datum (F.4: "the unit's seat is its HOSTS' ... feet only") — the caller
keeps them out of the unit's datum boxes.

Refused as contents, whatever the plan cover (§48 (1) (c)/(d) adopted
unchanged): a DECK member (its own datum law, §16e), a body authored below
``-contents_below_m`` of its own zero (a below-grade facility is never
contents).  A leaf that lies inside NO host keeps §16g (10) (4)'s reading:
its own ground or its carrier (18q Q2 for a free scatter piece).

Name-free: nothing here reads a resource name (F.9: "no object-type
recognition of any kind")."""
from __future__ import annotations

import typing as _t

import shapely
from shapely.geometry import Polygon, box as _box
from shapely.ops import unary_union

__all__ = ["attach_contents", "CONTENTS_BELOW_M"]

#: §48 (1) (d): ``basin.admission_depth_m`` — a body authored lower than
#: this under its own zero is a below-grade facility and is never contents.
CONTENTS_BELOW_M = 2.5


def _poly(rings: _t.Sequence, boxes: _t.Sequence, ml: float, mo: float):
    """A body's plan footprint in metres: the union of its component
    rings, or of its part boxes where it carries no ring."""
    gs = []
    for r in rings:
        if len(r) < 3:
            continue
        g = Polygon([(b * mo, a * ml) for a, b in r])
        if not g.is_valid:
            g = g.buffer(0)
        if not g.is_empty:
            gs.append(g)
    if not gs:
        gs = [_box(b[1] * mo, b[0] * ml, b[3] * mo, b[2] * ml) for b in boxes]
    if not gs:
        return None
    return unary_union(gs) if len(gs) > 1 else gs[0]


def attach_contents(shims: _t.Sequence[_t.Any],
                    clusters: _t.Sequence[_t.Sequence[int]],
                    walled_ix: _t.Sequence[int], leaves: _t.Sequence[int],
                    touch_m: float, min_fraction: float, counts: "dict | None",
                    *, is_deck: _t.Callable[[int], bool],
                    base_y: _t.Callable[[int], "float | None"],
                    ml: float, mo: float
                    ) -> "tuple[dict[int, int], list[int]]":
    """``(leaf shim index -> host key, walled singletons that host
    contents)``.

    A host key ``k >= 0`` is the index of a cluster in ``clusters``; a key
    ``-1 - s`` names the walled SINGLETON shim ``s`` (a walled body that
    chains with nothing — it becomes a unit of its own only because it
    holds contents).  The best host is the one covering the largest share
    of the leaf; ties go to the larger host outline, then the lower key —
    deterministic, never by name."""
    if min_fraction <= 0.0 or not leaves or not walled_ix:
        return {}, []
    in_cluster = {i for cl in clusters for i in cl}
    hosts: list[tuple[int, _t.Any]] = []
    for k, cl in enumerate(clusters):
        gs = [_poly(shims[i].rings, shims[i].part_boxes, ml, mo) for i in cl
              if shims[i].walled]
        gs = [g for g in gs if g is not None]
        if gs:
            hosts.append((k, unary_union(gs)))
    for s in walled_ix:
        if s in in_cluster:
            continue
        g = _poly(shims[s].rings, shims[s].part_boxes, ml, mo)
        if g is not None:
            hosts.append((-1 - s, g))
    if not hosts:
        return {}, []
    grown = [g.buffer(touch_m) if touch_m > 0.0 else g for _k, g in hosts]
    areas = [g.area for g in grown]
    tree = shapely.STRtree(grown)
    out: dict[int, int] = {}
    n_deck = n_below = n_free = 0
    for i in leaves:
        if is_deck(i):
            n_deck += 1
            continue
        by = base_y(i)
        if by is not None and by < -CONTENTS_BELOW_M:
            n_below += 1
            continue
        g = _poly(shims[i].rings, shims[i].part_boxes, ml, mo)
        if g is None or g.area <= 0.0:
            continue
        best = None
        for j in sorted(int(x) for x in tree.query(g)):
            f = grown[j].intersection(g).area / g.area
            if f < min_fraction:
                continue
            key = (-f, -areas[j], hosts[j][0])
            if best is None or key < best[0]:
                best = (key, hosts[j][0])
        if best is None:
            n_free += 1
            continue
        out[i] = best[1]
    singles = sorted({-1 - k for k in out.values() if k < 0})
    if counts is not None:
        counts["contents_bodies"] = len(out)
        counts["contents_in_units"] = sum(1 for k in out.values() if k >= 0)
        counts["contents_in_walled_singletons"] = sum(
            1 for k in out.values() if k < 0)
        counts["contents_host_singletons"] = len(singles)
        counts["contents_refused_deck"] = n_deck
        counts["contents_refused_below_grade"] = n_below
        counts["contents_leaves_free"] = n_free
    return out, singles
