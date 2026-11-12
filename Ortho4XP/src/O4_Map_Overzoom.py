"""Map overzoom past the imagery source's finest level (issue #1315).

The rule both map canvases follow -- the Qt map (:mod:`O4_Qt_Map`) and
the macOS app's (``Sources/SceneryKit/MapOverzoom.swift``, the Swift
half) -- twinned on ``tests/fixtures/map_overzoom_cases.json``.  Pure
arithmetic, no Qt.

The map zooms to :data:`MAX_VIEW_ZL` whatever the source offers.  A
view tile finer than the source's ``max_zl`` is drawn from its deepest
available ancestor: :func:`ancestor` names that tile and the sub-square
of it to crop and scale up.  No URL above ``max_zl`` is ever requested,
and the zoom badge says ``overzoom xN`` (:func:`badge_text`).

Below a source's ``min_zl`` (#2017: its coarsest zoom serving the
same capture as full zoom; Bing's older, greener capture at ZL12 and
coarser) :func:`floor_zoom` raises the fetched zoom to that floor when
it is at most :data:`MAX_FLOOR_STEPS` finer than the view -- four times
the tiles, never more; a coarser view keeps its own zoom.
"""

from typing import NamedTuple, Optional

__all__ = [
    "MAX_VIEW_ZL",
    "MAX_FLOOR_STEPS",
    "Ancestor",
    "floor_zoom",
    "ancestor",
    "overzoom_factor",
    "badge_text",
]

#: The map's zoom ceiling, independent of any imagery source: deep
#: enough (about 1 cm a pixel) to edit patch nodes at fine scale.
MAX_VIEW_ZL = 24
#: How many zoom levels finer than the view the map fetches to reach a
#: source's floor: 1 (four times the tiles of the view's own zoom).
MAX_FLOOR_STEPS = 1


class Ancestor(NamedTuple):
    """The tile ``(z, x, y)`` that draws a view tile, and the sub-square
    of it the view tile covers, as fractions of the ancestor's side:
    left ``sub_x``, top ``sub_y``, side ``sub_size`` (1.0 = the whole
    tile, when the view tile is itself available)."""

    z: int
    x: int
    y: int
    sub_x: float
    sub_y: float
    sub_size: float


def ancestor(z: int, x: int, y: int, max_z: int) -> Ancestor:
    """The tile at ``min(z, max_z)`` covering view tile ``(z, x, y)``."""
    depth = max(0, z - max_z)
    if depth == 0:
        return Ancestor(z, x, y, 0.0, 0.0, 1.0)
    span = 1 << depth
    ax, ay = x >> depth, y >> depth
    return Ancestor(z - depth, ax, ay,
                    (x - (ax << depth)) / span,
                    (y - (ay << depth)) / span,
                    1.0 / span)


def floor_zoom(z: int, max_z: int, min_z: Optional[int] = None) -> int:
    """The zoom the map fetches where it would fetch ``z`` (the view's
    zoom capped at the source's ``max_z``, :func:`ancestor`): the
    source's floor ``min_z`` when that is at most :data:`MAX_FLOOR_STEPS`
    finer (a tile drawn from 2 x 2 finer ones), else ``z``."""
    if min_z is not None and z < min_z <= min(z + MAX_FLOOR_STEPS, max_z):
        return min_z
    return z


def overzoom_factor(view_zl: int, max_zl: int) -> int:
    """How many times the source's finest tiles are scaled up (1 = not)."""
    return 1 << max(0, view_zl - max_zl)


def badge_text(view_zl: int, source: Optional[str],
               max_zl: Optional[int]) -> str:
    """The zoom badge: the view's ZL, and past the source's ceiling the
    overzoom factor and the ceiling it scales up from."""
    if max_zl is None or view_zl <= max_zl:
        return "ZL %d" % view_zl
    return "ZL %d · overzoom ×%d (%s max ZL %d)" % (
        view_zl, overzoom_factor(view_zl, max_zl), source or "source",
        max_zl)
