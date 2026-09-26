"""THE JETWAY STRIP — data only (spec ``docs/specs/jetway-strip-spec.md``
§1-§2; owner RULINGS 2026-09-18t Q3, issues #31/#32).

"UNDER THE JETWAYS THE APRON STRIP IS LEVEL WITH THE TERMINAL — a NEW
AIRSIDE LAW, solved airside-first; nothing groundside pulls it."

The REGION is derived once, in ``constraints/jetway_strip.py`` (the pad
edges that carry a rider anchor, the apron within ``[design]
jetway_strip_m`` of them, minus the §30 (4) strike set), and handed to
``solve/project_strip.py`` as these records: ``solve`` may import
``model`` but never ``constraints``, so the relation travels here, exactly
as ``Airport.clusters`` carries the cluster relation.

No numpy, no shapely, no I/O here.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

XY = tuple[float, float]

__all__ = ["RiderAnchor", "JetwayStrip", "StripSet", "STRUCK_KINDS"]

#: Why a vertex inside (or beside) a strip is never moved by the strip:
#: ``taxi`` a vertex the taxi / runway family carries; ``coupled`` an
#: apron vertex a taxi-family no-step row pairs with a taxi vertex (13cc
#: (i)); ``pad`` a vertex another pad owns; ``pin`` a pinned vertex (the
#: runway thresholds, the §38 seam).  The first three are the §30 (4)
#: strike set (``constraints.jetway_strip.strike_set``, one derivation).
STRUCK_KINDS = ("taxi", "coupled", "pad", "pin")


@_dc.dataclass(frozen=True)
class RiderAnchor:
    """One RIDER (spec §1 (1)) as the design surface sees it: a placement
    the plan holds no geometry for, standing within ``reach_m`` of a 23a
    pad's outline.  ``obj_id`` is the ``DsfObject.id``; ``host_ref`` the
    pad face ref it rides; ``gap_m`` its plan distance to that outline."""

    obj_id: str
    path: str
    xy: XY
    host_ref: str
    host_face: int
    gap_m: float
    reach_m: float


@_dc.dataclass(frozen=True)
class JetwayStrip:
    """One pad's strip (spec §1 (2)).  ``vertices`` take ONE level (§2
    (1)); ``struck`` are the vertices inside the region the strip never
    moves, with the reason; ``region`` the plan region's outer rings (the
    rider edges buffered D along their outward normals)."""

    id: str
    pad_ref: str
    pad_face: int
    riders: tuple[str, ...]
    rider_edges: tuple[tuple[XY, XY], ...]
    region: tuple[tuple[XY, ...], ...]
    vertices: tuple[int, ...]
    struck: tuple[tuple[int, str], ...] = ()


@_dc.dataclass(frozen=True)
class StripSet:
    """Every strip of one airport, plus what the TRANSITION (§2 (3)) may
    touch: ``movable`` the apron vertices a transition may move (every
    apron vertex outside the strike set), ``fixed`` the vertices it never
    moves (the clamps, with the reason).  ``counts`` is the say-line."""

    strips: tuple[JetwayStrip, ...] = ()
    riders: tuple[RiderAnchor, ...] = ()
    movable: frozenset[int] = frozenset()
    fixed: _t.Mapping[int, str] = _dc.field(default_factory=dict)
    counts: _t.Mapping[str, _t.Any] = _dc.field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.strips)
