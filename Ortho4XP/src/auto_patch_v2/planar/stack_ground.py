"""THE DECK STACK'S GROUND IS GRADED GROUND OF ITS OWN (#1971; spec
``docs/specs/interchange-levels-v2-20261113.md`` §3.2; owner RULINGS
2026-11-13g, 2026-11-11b, 2026-10-29a Q299 (a)).

A deck stack (``airport/deck_stack``) states areas, not points: the walls'
caps beside the trench, the ground under each deck, the ground round the
decks' ends.  Where the patch has no face there the core mesh draws the
lidar, which is the real road, the real embankment or a bank metres off the
walls' top.  So the stack's ground is graded ground: ``graded_strip``
pieces under ``model/planar.STACK_GROUND_PREFIX`` (a zone region's family,
no zone class — the form of ``planar/fill_bank`` and ``planar/wall_slope``),
from ``airport/deck_stack.ground_footprint``:

* ``<stack>:cap#k`` the walls' crest plates off the floor (held at the
  walls' top, R2);
* ``<stack>:shadow:<deck>#<piece>#k`` each deck's rectangle less the caps
  (held under the plate, R3; at its end edge flush with it, R1);
* ``<stack>:apron:<deck>#<piece><end>#k`` the bank beyond each end line,
  the plate's width for ``L_e`` (its first ``abutment_sample_step_m``, the
  slab, held at the plate's top, R1: the ground beside the road keeps the
  deck's level as the road does, then comes off it);
* ``<stack>:bank#k`` what joins those to the lidar (its toe pinned on the
  DEM, R4).

Each piece welds to the zone bands, stands off every cell, road ribbon and
structure keep-out (the floor and its void band among them) by the zones'
groundside stand-off, and carries a vertex every ``vertex_m``.  Nothing is
minted on airside pavement: a piece the airside cut is noted.  No stack: no
piece.  No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import shapely
import shapely.prepared

from ..airport.deck_ends import ground_footprint
from ..geom.deck_ground import end_aprons
from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..model.planar import STACK_GROUND_PREFIX

__all__ = ["stack_ground_pieces", "deck_end_road_zone"]


def _areal(g):
    """``g``'s polygons alone (an overlay on shared edges may leave lines)."""
    return shapely.union_all([q for q in shapely.get_parts(g) if q.geom_type == "Polygon"])


def stack_ground_pieces(airport, taken: _t.Sequence, apart: _t.Sequence, cut_m: float,
                        hairline_m: float, vertex_m: float, law=None, airside=(),
                        notes: "list | None" = None) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per stack-ground piece (module docstring): the
    stack's ground footprint less ``taken`` (the zone bands, welded), less
    every polygon of ``apart`` grown by ``cut_m``; each ring carries a vertex
    at least every ``vertex_m``.  ``airside``: the airside cells (a piece
    they cut is noted).  ``[]`` without a stack."""
    stacks = tuple(getattr(airport, "deck_stacks", ()) or ())
    if not stacks or law is None:
        return []
    fps = [(st, ground_footprint(st, law)) for st in stacks]
    near = shapely.prepared.prep(shapely.union_all([fp["outline"] for _st, fp in fps])
                                 .buffer(cut_m + 1.0))

    def _near(gs) -> list:
        return [g for g in gs if g is not None and not g.is_empty and near.intersects(g)]
    knife = canonical_union(_near(taken) + [
        g.buffer(cut_m, join_style="mitre", mitre_limit=2.0) for g in _near(apart)])
    air = canonical_union(_near(airside))
    out: list[tuple[str, _t.Any]] = []
    for st, fp in fps:
        parts = [(f"{st.id}:cap", fp["caps"])]
        parts += [(f"{st.id}:shadow:{d.object_id}#{d.piece}", g) for d, g in fp["shadows"]]
        parts += [(f"{st.id}:apron:{d.object_id}#{d.piece}{side}", g)
                  for d, side, _top, g, _slab in fp["aprons"]]
        parts.append((f"{st.id}:bank", fp["bank"]))
        claimed = None
        own_air = air.difference(fp["keep"].buffer(2.0 * cut_m)) if not air.is_empty else air
        for name, g in parts:
            if g is None or g.is_empty:
                continue
            if claimed is not None:
                g = g.difference(claimed)
            g = _areal(g)
            claimed = g if claimed is None else claimed.union(g)
            if notes is not None and not own_air.is_empty and g.intersects(own_air.buffer(cut_m)):
                notes.append(f"{name}: cut back from the airside")
            k = 0
            for part in shapely.get_parts(fixed_difference(g, knife)):
                if part.geom_type != "Polygon" or part.area < 1.0 \
                        or is_hairline(part, hairline_m):
                    continue
                out.append((f"{STACK_GROUND_PREFIX}{name}#{k}", shapely.segmentize(part, vertex_m)))
                k += 1
    return out


def deck_end_road_zone(airport, law) -> tuple[_t.Any, float]:
    """``(zone, step)``: where a road's ribbon carries a vertex every
    ``step`` (``[bridge] abutment_sample_step_m``) -- every deck end's
    apron (``geom/deck_ground.end_aprons``, the plate's width for ``L_e``
    beyond the end line), so the road comes off the deck on its own ramp
    and not on one chord to the next way node 12-35 m out (v2 §3.4: KDEN
    round 2, the road 0.26 m off the plate one step outside the end line).
    ``(None, step)`` without a stack."""
    step = float(law.tables.structures.bridge.abutment_sample_step_m) if law is not None else 0.0
    stacks = tuple(getattr(airport, "deck_stacks", ()) or ())
    if not stacks or law is None:
        return None, step
    zone = shapely.union_all([a for st in stacks for a in end_aprons(st, law)])
    return (None if zone.is_empty else zone), step
