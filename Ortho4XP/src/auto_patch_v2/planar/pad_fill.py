"""THE PAD FILL — the ground under a pad unit's off-pad plates and pier
prints is filled to the pad's level (owner RULINGS 2026-10-19ap, #712;
owner Q33 2026-10-20 "flatten it all", #1003; RULINGS 2026-10-03e;
spec ``docs/specs/pad-fill-region-spec.md``).

19ap: *where a paved slab stands above the lot below it, the ground is
filled up to the slab and finished with banks; the slab is not draped
down to the lower ground.*  MEASURED at HECA (#712, 30.1096365,
31.3889978): ``Seasonal_Terminal/side_walk.obj`` is ONE feetless plate,
y 0.15, 15,761 m2 of outline — 7,155 m2 on the held block ``building5``,
the rest over the lot ``gap:3`` (rim down to 88.8 m) and ground no face
grades.  A component is never cut apart, so it rides the block (§16f (4):
the pad is the evidence) and its off-block part floats.  #1003 (30.112939,
31.397394): the T3 road viaduct's ground prints (``T23/Plastic.obj``
strips and pier bases, feet at the objects' zero) stand in ``gap:5/s0``,
which ramps 101.85 -> 94.1 m away from the block the viaduct is seated on.

Two witnesses, both read off the pack partition at the landing mint:

1. :func:`plate_fills` — A PLATE RIDING A BLOCK: a component at the
   objects' zero, thin, a level plate by its own faces (base-slab rules
   5-7), never a deck member, lying on a held block by at least
   ``base_slab_min_m2``.  Its off-block part is ground at the block's
   datum + its ``base_y``.
2. :func:`pier_fills` — A VIADUCT'S GROUND PRINTS: for a deck of a block
   (``bridge_family.viaduct_units``, the 10-03e relation), every voter part
   with feet at its zero (``|y| <= band``) that stands off the block.
   Prints closer than two bank widths are one fill (two fills at one level
   cannot bank down and up between them); its extent is the convex hull of
   the group, at the block's datum + the group's lowest foot y.

Each fill becomes a RAMP LANDING (``planar/landing``): its level rows, its
1:3 collar and its lot cut are the landing's own.  Only shape is decided
here; the caller cuts what is taken and registers the result."""
from __future__ import annotations

import typing as _t

from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

__all__ = ["Fill", "plate_fills", "pier_fills"]


class Fill(_t.NamedTuple):
    """One fill before it is cut: its block, its extent (planar metres),
    its authored ``y`` over the block, what it is and where it came from."""

    block: str
    extent: _t.Any
    y: float
    kind: str
    source: str
    voters: int = 1


def _block_index(blocks: _t.Sequence[tuple[str, Polygon]]):
    return STRtree([q for _r, q in blocks]) if blocks else None


def plate_fills(partition: _t.Any, to_xy, lw: _t.Any, faces: "_t.Callable | None",
                blocks: _t.Sequence[tuple[str, Polygon]]) -> list[Fill]:
    """Witness 1 (module doc): one :class:`Fill` per plate riding a block,
    its extent the plate's outline OFF every block.  ``lw`` is the
    base-slab law (``law.tables.base_slab_law``); ``faces`` its face
    reader (``airport/slab_faces.witness_faces``) — no reader, no plate
    (a plate is only read level by its faces)."""
    from ..airport.placement_family import member_is_deck
    from ..geom.base_slab import _elevated, _plate, _ring_poly
    if partition is None or faces is None or not blocks or not lw.armed:
        return []
    tree = _block_index(blocks)
    allb = unary_union([q for _r, q in blocks])
    plates = getattr(faces, "plates", None)
    out: list[Fill] = []
    for u in getattr(partition, "units", ()) or ():
        for m in u.members:
            if member_is_deck(m):
                continue
            parts = list(m.parts)
            if plates is not None:
                parts.extend(plates(u, m, to_xy, lw))
            for q in parts:
                if (getattr(q, "line", False) or getattr(q, "scatter", False)
                        or abs(float(q.base_y)) > lw.base_y_max_m
                        or float(getattr(q, "height_m", 0.0)) > lw.max_height_m
                        or float(getattr(q, "area_m2", 0.0)) < lw.min_m2):
                    continue
                g = _ring_poly(q, to_xy)
                if g is None or g.area < lw.min_m2:
                    continue
                on = [(r, g.intersection(b).area)
                      for r, b in (blocks[int(j)] for j in tree.query(g, predicate="intersects"))]
                on = [t for t in on if t[1] >= lw.min_m2]
                if not on:
                    continue
                ff = faces(m, int(q.comp))
                # rules 5-7: a level plate (touches=False asks for the level
                # reading), not an elevated deck
                if ff is None or not _plate(ff, lw, False) or _elevated(ff, lw):
                    continue
                off = g.difference(allb)
                if off.is_empty or off.area < lw.min_m2:
                    continue
                bref = max(on, key=lambda t: (t[1], t[0]))[0]
                out.append(Fill(bref, off, float(q.base_y), "plate",
                                f"{m.id}#{int(q.comp)}"))
    return out


def _foot_ys(q, band: float) -> list[float]:
    return [float(f[2]) for f in (getattr(q, "feet", ()) or ())
            if len(f) >= 3 and abs(float(f[2])) <= band]


def _print(q, to_xy):
    from ..geom.base_slab import _ring_poly
    g = _ring_poly(q, to_xy)
    if g is not None and not g.is_empty:
        return g
    pts = [to_xy(float(f[1]), float(f[0])) for f in (getattr(q, "feet", ()) or ())]
    h = MultiPoint(pts).convex_hull if len(set(pts)) >= 3 else None
    return h if h is not None and h.area > 0.0 else None


def pier_fills(vias: _t.Mapping[str, tuple], partition: _t.Any, to_xy,
               blocks: _t.Sequence[tuple[str, Polygon]], band: float,
               join_m: float) -> list[Fill]:
    """Witness 2 (module doc): ``vias`` is ``bridge_family.viaduct_units``'s
    ``{deck key: (block, voters, frame, print)}``; ``band`` the landing band
    (``landing.BAND_M``); ``join_m`` the distance under which two prints are
    one fill (two bank widths)."""
    from ..airport import bridge_family as _bf
    if not vias or partition is None or not blocks:
        return []
    allb = unary_union([q for _r, q in blocks])
    out: list[Fill] = []
    for key, (bref, _voters, frame, p) in sorted(vias.items()):
        prints: list[tuple[Polygon, float]] = []
        for ui, u in enumerate(partition.units):
            for mi, m in enumerate(u.members):
                if _bf.frame_of(m) != frame or (ui, mi) == (p.unit, p.member):
                    continue
                for q in m.parts:
                    b = q.box
                    if not p.contains(0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3])):
                        continue
                    ys = _foot_ys(q, band)
                    if not ys or abs(float(getattr(q, "base_y", 0.0))) > band:
                        continue
                    g = _print(q, to_xy)
                    if g is None:
                        continue
                    off = g.difference(allb)
                    if off.is_empty or off.area <= 0.0:
                        continue
                    prints.append((off, min(ys)))
        if not prints:
            continue
        # one fill per group of prints within ``join_m`` of each other
        tree = STRtree([g for g, _y in prints])
        seen: set[int] = set()
        for i in range(len(prints)):
            if i in seen:
                continue
            grp, todo = [i], [i]
            seen.add(i)
            while todo:
                k = todo.pop()
                for j in tree.query(prints[k][0], predicate="dwithin", distance=join_m):
                    j = int(j)
                    if j not in seen:
                        seen.add(j)
                        grp.append(j)
                        todo.append(j)
            hull = unary_union([prints[j][0] for j in grp]).convex_hull
            out.append(Fill(bref, hull.difference(allb), min(prints[j][1] for j in grp),
                            "piers", str(key), len(grp)))
    return out

