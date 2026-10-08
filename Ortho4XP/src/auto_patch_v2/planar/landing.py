"""THE RAMP LANDINGS OF A UNIT'S VIADUCT (owner RULINGS 2026-10-03e, #290).

"Whole viaduct at T3's level; grade the ground to the landings."  The
object stage seats a deck that belongs to a terminal unit — and every
piece of its viaduct — at the unit's level
(``airport/footprint_unit.seat_viaducts``).  Where the deck's ramps come
down to the ground the ground must come UP to them: each LANDING (the
deck's model footprint where its authored surface stands within
``BAND_M`` of its lowest ``y``) becomes a flat groundside pad face at
the block's datum + the deck's authored ``y`` there, inside a COLLAR the
1:3 bank grades the ground through (the platform collar's own rows,
``constraints/platform.platform_collar_rows``, keyed on the ``#collar``
ref spelling), and the level is held in STAGE 2 against the block's
datum column (``constraints/platform.landing_rows``) — a constant after
stage 1, so airside cannot move.

WHICH BLOCK: ONE DERIVATION.  The deck's unit is
``bridge_family.viaduct_units`` — the same function the object stage
asks (there with the §16g plan-wide seat as the unit key, here with the
held platform BLOCK a part's centre stands on): the plurality of the
parts of members sharing the deck's placement frame inside its model
footprint, where that block holds parts outside it too.  A deck no block
claims is free-standing and mints nothing.

THE GATE (spec §56 (10) R-L): a landing is minted only where its level
``y_land >= -BAND_M`` against its unit's pad — the band the law already
defines.  A foot lower than that is a PIER FOOTING under the ground, not a
ramp end (MEASURED: two bridge decks whose lowest authored y is -0.80 /
-2.34 dug the ground 1.7-1.9 m under a terminal and cost 27 relaxed hard
rows); it is counted ``landing_below_unit`` and nothing is minted.

Called once, at the end of ``planar/platform.platform_split`` — after
every block is minted and registered in ``HELD`` and after the split's
ref passes, so neither renames a landing.  The landing ref
``<unit>/landing<k>`` is not a block ref (``model.planar.block_of``)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.planar import COLLAR_SUFFIX, pad_base_ref
from ..model.platform import HELD, LANDING_SEP, LANDINGS

__all__ = ["BAND_M", "landing_regions", "landing_cut"]

#: the landing band: the deck surface within this of its lowest authored
#: ``y`` is a landing (the master's "y <= min + 0.5", lane viaduct290)
BAND_M = 0.5


def _parts(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [q for q in getattr(g, "geoms", ()) if isinstance(q, Polygon)
            and not q.is_empty]


def _prints(part) -> list:
    """The deck model footprints of the pack partition (``bridge_family.
    deck_prints`` over the partition, each deck parsed once)."""
    from ..airport import bridge_family as _bf
    from ..airport.placement_cut import _LineCutter

    def _cutter(ui: int, _mi: int, m):
        u = part.units[ui]
        return _LineCutter(m, 0.0, 0, 0.0, 0.0, 0.0,
                           float(u.anchor[0]), float(u.anchor[1]))
    return _bf.deck_prints(part, _cutter)


def landing_regions(out: list, split_units: _t.Mapping[str, list],
                    air_polys: _t.Sequence[Polygon], airport, law,
                    grid: float, collar_m: float,
                    counts: dict) -> list:
    """The landing + collar regions to add to the pad regions ``out``
    (module docstring), registering each in :data:`LANDINGS`."""
    LANDINGS.clear()
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if part is None or frame is None or not HELD or collar_m <= 0.0:
        return []
    if not any(getattr(m, "deck_kind", "") in ("flag", "signature")
               for u in part.units for m in u.members):
        return []
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    from ..airport import bridge_family as _bf
    from ..model.planar import block_ref
    to_xy = frame.entry()
    # the held BLOCKS in plan: a cut unit's block polygons, a one-block
    # held unit's own pad region(s)
    blocks: list[tuple[str, Polygon]] = []
    for unit, polys in sorted(split_units.items()):
        for k, q in enumerate(polys):
            if block_ref(unit, k) in HELD:
                blocks.append((block_ref(unit, k), q))
    for r in out:
        ref = str(r.ref)
        if (ref in HELD and HELD[ref].get("blocks", 1) == 1
                and ref not in split_units and r.polygon is not None):
            blocks.append((ref, r.polygon))
    if not blocks:
        return []
    tree = STRtree([q for _r, q in blocks])

    def _key(q) -> str:
        b = q.box
        x, y = to_xy(0.5 * (b[1] + b[3]), 0.5 * (b[0] + b[2]))
        pt = Point(x, y)
        for j in tree.query(pt, predicate="intersects"):
            return blocks[int(j)][0]
        return ""

    prints = _prints(part)
    if not prints:
        return []
    vias = _bf.viaduct_units(prints, part, _key, counts)
    if not vias:
        return []
    added: list = []
    recs: list = []
    template = {str(r.ref): r for r in out}
    n_by_unit: dict[str, int] = {}
    # the landing reaches the deck's end edge: its footprint widened by the
    # object stage's own FOOT BAND (``[basin] contact_band_m``) so the
    # ramp's end vertices stand ON the pad, never on its collar's first
    # metre (MEASURED, HECA replay: three end vertices 0.11-0.23 m off the
    # snapped landing read the collar 1.5-5.2 m low)
    reach = float(law.tables.structures.basin.contact_band_m)
    for key, (bref, voters, _fr, p) in sorted(vias.items()):
        pieces = []
        for ring, y in _bf.landing_pieces(p, BAND_M):
            q = Polygon([to_xy(lo, la) for la, lo in ring])
            if not q.is_valid:
                q = q.buffer(0)
            if not q.is_empty and q.area > 0.0:
                pieces.append((q, y))
        if not pieces:
            continue
        unit = str(HELD[bref].get("unit", bref))
        tmpl = template.get(bref) or next(
            (r for r in out if str(r.ref).startswith(bref)), None)
        if tmpl is None:
            continue
        recs.append((key, bref, voters, unit, tmpl, pieces))
    # PASS 1: every landing PLATFORM, before any collar — a landing's bank
    # may never take another landing's footprint (MEASURED, HECA replay:
    # one east landing lost whole to its neighbour's collar)
    # the AIRSIDE and a bank's minimum width around it are never the
    # landing's to take (a welded rim is a stage-1 contact; MEASURED, HECA
    # replay, matched no-landing control: cutting 8 welded vertices off
    # moved stage 1 — taxi 294 nodes <= 0.08 m, apron 46 <= 0.10 m)
    _keep = float(law.tables.emit.design.bank_min_width_m)
    air_u = unary_union(list(air_polys))
    base_hard = unary_union([r.polygon for r in out if r.polygon is not None]
                            + [air_u.buffer(_keep) if _keep > 0.0 else air_u])
    taken = base_hard
    plats: list = []
    for key, bref, voters, unit, tmpl, pieces in recs:
        for comp in _parts(unary_union([q for q, _y in pieces])
                           .buffer(reach, join_style=2)):
            # the level: the deck's FOOT here — the lowest authored y of
            # the pieces in it (the ramp's end lip meets the ground at 0;
            # the rest of the band stands <= ``BAND_M`` over its pad)
            ys = [y for q, y in pieces if q.intersects(comp)]
            if not ys:
                continue
            y_land = min(ys)
            if y_land < -BAND_M:
                # spec §56 (10) R-L: a foot more than the band BELOW its
                # unit's pad is a pier footing under the ground, not a ramp
                # end — a descent is the structure pass's (§39 / §47),
                # never a landing; nothing is minted
                counts["landing_below_unit"] = \
                    counts.get("landing_below_unit", 0) + 1
                continue
            L = comp.difference(taken)
            if grid > 0.0:
                s_ = L.simplify(0.5 * grid, preserve_topology=True)
                L = s_ if not s_.is_empty else L
            Ls = [q for q in _parts(L) if q.area >= max(grid * grid, 1.0)]
            if not Ls:
                counts["landing_taken"] = counts.get("landing_taken", 0) + 1
                continue
            k = n_by_unit.get(unit, 0)
            n_by_unit[unit] = k + 1
            Lu = unary_union(Ls)
            taken = unary_union([taken, Lu])
            plats.append((f"{unit}{LANDING_SEP}{k}", Ls, Lu, y_land, key,
                          bref, voters, unit, tmpl))
    if not plats:
        counts["landings"] = 0
        return []
    # PASS 2: the collars, over what no platform, pad or airside holds
    held_c = taken
    for ref, Ls, Lu, y_land, key, bref, voters, _unit, tmpl in plats:
        C = Lu.buffer(collar_m, join_style=2).difference(held_c)
        cparts = [q for q in _parts(C) if q.area >= max(grid * grid, 1.0)]
        held_c = unary_union([held_c, *cparts])
        added.extend(_dc.replace(tmpl, ref=ref, polygon=q) for q in Ls)
        added.extend(_dc.replace(tmpl, ref=ref + COLLAR_SUFFIX, polygon=q)
                     for q in cparts)
        LANDINGS[ref] = {"block": bref, "y": round(y_land, 4), "deck": key,
                         "voters": voters, "area_m2": round(Lu.area, 1),
                         "collar_m2": round(sum(q.area for q in cparts), 1)}
    counts["landings"] = len(LANDINGS)
    if LANDINGS:
        counts["landing_list"] = "; ".join(
            f"{r} on {v['block']} y {v['y']:+.2f} {v['area_m2']:g} m2"
            for r, v in sorted(LANDINGS.items()))
    return added


#: the groundside roles a landing (and its collar) is cut out of: the LOT
#: a ramp lands on.  A ROAD is never cut — since the road terrace (RULINGS
#: 2026-10-03b) a road bordering airside is a stage-1 participant, and
#: cutting one moved stage 1 (MEASURED, HECA replay vs the matched
#: no-landing control: taxi 294 nodes <= 0.08 m, apron 46 <= 0.10 m with
#: ``service_road`` / ``groundside_pavement`` cut); a road meeting the
#: landing keeps its face and follows by its own frontage rule.
LOT_ROLES = frozenset({"parking_lot"})


def landing_cut(base_regions: list, pad_regions: _t.Sequence, law,
                counts: "dict | None" = None) -> list:
    """The GROUNDSIDE base regions with every landing — its platform AND
    its collar — cut out (owner RULINGS 2026-10-03e: the ground is graded
    up to the landing).  A ramp lands on a lot or a road, and a groundside
    face is senior to a pad at the face claim, so without the cut the lot
    keeps the landing (MEASURED, HECA capture at f9aa1d5d: ``landing0``
    216.7 m2 and ``landing1`` 20.4 m2 wholly ``parking_lot|dsf:pol10``);
    with the platform alone cut, the lot's own hard rows around a 3-6 m
    step made the landing's level rows infeasible and the §5a relaxation
    dropped them (the two landings on ``dsf:pol10`` solved at 96.3 m, not
    99.2).  The collar is the 1:3 bank between them, so it is the lot's
    no longer; the lot meets the bank's toe.  Airside regions are never
    cut (the landing was minted outside them)."""
    if not LANDINGS:
        return base_regions
    from ..law.tables import role_side
    L = unary_union([r.polygon for r in pad_regions
                     if pad_base_ref(r.ref) in LANDINGS
                     and r.polygon is not None])
    if L.is_empty:
        return base_regions
    out: list = []
    n = 0
    for r in base_regions:
        P = r.polygon
        if (P is None or P.is_empty or not P.intersects(L)
                or role_side(law, r.role) != "groundside"
                or r.role not in LOT_ROLES):
            out.append(r)
            continue
        n += 1
        for q in _parts(P.difference(L)):
            out.append(_dc.replace(r, polygon=q))
    if counts is not None:
        counts["landing_cut_regions"] = n
    return out
