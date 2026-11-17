"""THE ROAD CLEARANCE LAW, read by the planar stage and the constraint
generators alike (``constraints`` reads only ``geom`` / ``law`` / ``model``):
a way's mapped carriageway width, the clearance a generated deck or road
bridge holds over it, and the deck line between a bridge's two end levels.
Re-exported where they were born (``airport/road_ways``,
``planar/structure_approach``, ``planar/road_bridge_clear``)."""
from __future__ import annotations

import typing as _t

if _t.TYPE_CHECKING:
    from ..law import Law

__all__ = ["mapped_width_m", "carriageway_width_m", "design_clearance_m", "deck_at"]


def mapped_width_m(tags, lane_width_m: float, default_lanes: int) -> float:
    """THE WAY'S MAPPED CARRIAGEWAY WIDTH — the one reading of what the map
    says about a road's width: its ``width`` tag, else ``lanes`` x
    ``lane_width_m`` (``default_lanes`` where neither parses).  The
    structures read it through :func:`carriageway_width_m`; the at-grade
    ribbon through ``airport/road_ways.ribbon_half_width_m``."""
    tags = tags or {}
    w = tags.get("width")
    if w:
        try:
            return max(1.0, float(str(w).replace("m", "").strip()))
        except ValueError:
            pass
    lanes = tags.get("lanes")
    try:
        n = int(lanes) if lanes else int(default_lanes)
    except ValueError:
        n = int(default_lanes)
    return max(1, n) * float(lane_width_m)


def carriageway_width_m(tags: _t.Mapping[str, str], law: "Law") -> float:
    """The way's stated ``width``, else ``lanes × lane_width_m`` (a
    railway counts as ``default_lanes``) — :func:`mapped_width_m` at the ``[tunnel]`` lane law."""
    tn = law.tables.structures.tunnel
    return mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)


def design_clearance_m(tags: _t.Mapping[str, str], law: "Law") -> float:
    """THE CLEARANCE A GENERATED DECK OR ROAD BRIDGE HOLDS OVER A ROAD
    (owner 2026-11-17T19:08Z "Accept 4.2m clearance for small roads"):
    ``[bridge] clearance_minimum_m`` over a ``small_road_classes`` highway,
    ``[tunnel] clearance_m`` over every other road and rail."""
    st = law.tables.structures
    hw = str((tags or {}).get("highway", "") or "")
    if hw and hw in tuple(getattr(st.bridge, "small_road_classes", ()) or ()):
        return float(st.bridge.clearance_minimum_m)
    return float(st.tunnel.clearance_m)


def deck_at(levels: tuple[float, float], length: float, s: float) -> float:
    """The deck's level ``s`` along a bridge ``length`` long, straight
    between its two end levels."""
    w = 0.0 if length <= 1e-9 else min(1.0, max(0.0, s / length))
    return levels[0] + w * (levels[1] - levels[0])
