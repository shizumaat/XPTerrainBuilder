"""A PAD UNDER A UNIT'S UPPER STOREY IS HELD AT THAT STOREY'S LEVEL (owner
RULINGS 2026-11-13aa (1), #2068; spec ``docs/specs/2068-upper-pad-spec.md``
§1 Planar; the mirror of ``planar/group_low``).

A tower stands on a hill behind its terminal: every part of the terminal's
pack unit over the tower's pad is authored a storey over the unit's floor
(a plinth and walled bodies at y +4.7 over a floor at 0), and the ground
under the pad stands that storey over the apron the floor meets.  The
classifier read it (``airport/unit_storey.upper_pads``) and put the storey
on the pad's cell (``classify/storey_edge.UPPER_Y_KEY`` / ``UPPER_FLOOR_KEY``
/ ``UPPER_UNIT_KEY``); the road §27 had pulled down round it was cut back
to its arm (``storey_edge.arm_storeys``).

THE LEVEL IS TIED TO THE UNIT'S BLOCK.  The nearest held, non-conforming
block of the same unit (``low_level.unit_share``, as
``planar/station_level``) carries the unit's datum column; the whole pad
(``low_level.level_cut`` with ``whole``: ``pad_frontage_m`` off the
airside, a riser's width off the other pads, its ``#strip``) is minted
``<block>/p<k>`` and registered in ``Registries.landings`` with ``kind``
``upper_level``, ``y`` = the storey's base less the block's top level and
``witness`` :data:`GROUP_UP`; ``constraints/platform.landing_rows`` holds
it rigid at ``z = D_block + y``.  The object stage reads it through the
``/p<k>`` fold (``airport/placement_read``): the unit stays one body at
its one zero, the plinth on the level.  A pad the classifier read is
taken whether or not the block planner held it (its road cut back to the
arm, it fronts no airside any more); a held pad whose whole area became
the level loses its held record.

Refused (counted with the reason): no held block of the unit, a block
whose top level is not the unit's floor (within ``split_level.BAND_M``),
no level left off the airside.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..model.planar import STRIP_SUFFIX
from ..model.registries import GROUP_UP

__all__ = ["GROUP_UP", "plan_group_up", "upper_pad_reads"]



def upper_pad_reads(cells) -> dict[str, tuple[float, float, int, tuple[str, ...]]]:
    """``{pad ref: (storey base y_p, unit floor t, unit, its arms' refs)}``
    of the pads the classifier read under an upper storey
    (``classify/storey_edge``; an arm is a road cut back to climb to its
    pad, ``ARM_PAD_KEY``)."""
    from ..classify.storey_edge import ARM_PAD_KEY, UPPER_FLOOR_KEY, UPPER_UNIT_KEY, UPPER_Y_KEY
    arms: dict[str, list[str]] = {}
    for c in cells:
        if ARM_PAD_KEY in (c.evidence or {}):
            arms.setdefault(str(c.evidence[ARM_PAD_KEY]), []).append(str(c.ref))
    return {c.ref: (float(c.evidence[UPPER_Y_KEY]), float(c.evidence[UPPER_FLOOR_KEY]),
                    int(c.evidence[UPPER_UNIT_KEY]), tuple(sorted(arms.get(c.ref, ()))))
            for c in cells if c.role == "building" and UPPER_Y_KEY in (c.evidence or {})}


def _refuse(counts: dict, ref: str, why: str) -> None:
    got = counts.get("upper_pads_refused")
    counts["upper_pads_refused"] = f"{got}; {ref}: {why}" if got else f"{ref}: {why}"


def plan_group_up(out: list, upper: _t.Mapping[str, tuple], air_polys, tree, airport,
                  law, grid: float, counts: dict, reg, skip: _t.AbstractSet[str] = frozenset()
                  ) -> dict[str, list]:
    """``{pad ref: its regions}`` for every upper pad of ``out`` (module
    docstring) — the level ``<block>/p<k>``, its strip and the pad's
    remainder; each level registered in ``reg.landings``.  ``skip`` the
    pads another reading holds (the storey shells)."""
    from ..airport.split_level import BAND_M
    from .low_level import UP_KIND, level_cut, unit_share
    from .station_level import block_top, next_plane
    if not upper or airport is None or getattr(airport, "frame", None) is None:
        return {}
    held = reg.held
    to_xy = airport.frame.entry()
    pads: dict[str, list] = {}
    blocks: dict[str, list] = {}
    for r in out:
        ref = str(r.ref)
        if r.polygon is None:
            continue
        if ref in upper and ref not in skip:
            pads.setdefault(ref, []).append(r)
        elif ref in held and not held[ref].get("conforming") and ref not in upper:
            blocks.setdefault(ref, []).append(r.polygon)
    block_union = {k: unary_union(v) for k, v in blocks.items()}
    done: dict[str, list] = {}
    for ref, regs in sorted(pads.items()):
        y_p, t, ui = upper[ref][:3]
        P = unary_union([r.polygon for r in regs])
        cand = [k for k, B in block_union.items() if unit_share(B, airport, to_xy)[0] == ui]
        if not cand:
            _refuse(counts, ref, "no held block of its unit")
            continue
        block = min(cand, key=lambda k: (block_union[k].distance(P), k))
        top = block_top(block_union[block], airport, air_polys, tree, law, to_xy, Polygon())
        if top is None or abs(top - t) > BAND_M:
            _refuse(counts, ref, f"block {block} top {top} is not the unit's floor {t:+.2f}")
            continue
        air = unary_union([air_polys[int(j)] for j in
                           tree.query(P.buffer(50.0), predicate="intersects")])
        others = unary_union([r.polygon for r in out if str(r.ref) != ref
                              and r.polygon is not None and r.polygon.intersects(P.buffer(1.0))])
        cut = level_cut(P, P, air if not air.is_empty else Polygon(), others, law, grid, 0.0,
                        whole=True)
        if cut is None:
            _refuse(counts, ref, "no level left off the airside")
            continue
        H, L, S = cut
        lv = next_plane(block, reg)
        tmpl = regs[0]
        done[ref] = ([_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(H)]
                     + [_dc.replace(tmpl, ref=lv, polygon=q) for q in nonempty_polygon_parts(L)]
                     + [_dc.replace(tmpl, ref=lv + STRIP_SUFFIX, polygon=q)
                        for q in nonempty_polygon_parts(S)])
        reg.landings[lv] = {"block": block, "y": round(y_p - top, 3), "deck": None,
                            "kind": UP_KIND, "pad": ref, "witness": GROUP_UP,
                            "y_p": round(y_p, 3), "top_y": round(top, 3),
                            "area_m2": round(L.area, 1),
                            "arms": tuple(upper[ref][3:4][0]) if len(upper[ref]) > 3 else ()}
        if H.is_empty:
            held.pop(ref, None)
    counts["upper_pads"] = "; ".join(
        f"{k} on {v['block']} for {v['pad']} +{v['y']:.2f} {v['area_m2']:g} m2"
        for k, v in sorted(reg.landings.items()) if v.get("witness") == GROUP_UP)
    return done
