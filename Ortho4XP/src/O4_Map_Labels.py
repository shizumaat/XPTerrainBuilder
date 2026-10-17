"""What the map labels, and where (issue #817).

The rules both map canvases follow -- the Qt map (:mod:`O4_Qt_Map`) and
the macOS app's (``Sources/SceneryKit/MapLabelLayout.swift``, the Swift
half) -- twinned on ``tests/fixtures/map_label_cases.json``.  Pure
geometry and text, no Qt: a canvas hands in screen points and draws what
comes back.

Every zoom here is a MAP SCALE in screen pixels per degree of longitude
(the macOS camera's ``scale``; the Qt map's ``256 * 2**zoom / 360``).

Airports (Google Maps-style):

* a mark appears once its size class's :data:`MARK_MIN_SCALE` is reached
  (large airports from far out, heliports only close in); a custom-pack
  airport is always marked;
* a label is allowed from its class's :data:`LABEL_MIN_SCALE` (a custom
  airport one class earlier), at :func:`label_font_size`, which grows a
  point per doubling of the scale from 12 to 16;
* :func:`place_airport_labels` places them in rank order -- class, then
  custom before default, then longest runway, then code -- and drops any
  label whose box would overlap one already placed.

Tiles: from :data:`TILE_LABEL_MIN_SCALE` on, every tile shows its
coordinate top-left and, where ortho is installed, :func:`imagery_label`
bottom-left, each on a translucent pill.
"""

import math
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

__all__ = [
    "MARK_MIN_SCALE",
    "LABEL_MIN_SCALE",
    "LABEL_FONT_MIN",
    "LABEL_FONT_MAX",
    "TILE_LABEL_MIN_SCALE",
    "TILE_LABEL_FONT",
    "MAX_AIRPORT_LABELS",
    "LabelCandidate",
    "LabelBox",
    "mark_visible",
    "label_allowed",
    "label_font_size",
    "mark_radius",
    "label_box",
    "place_airport_labels",
    "imagery_label",
    "scale_for_slippy_zoom",
]

# Screen px per degree of longitude from which a size class (index; 0 =
# largest, O4_Airport_Rank) is marked, and from which it may be labelled.
MARK_MIN_SCALE = (4.0, 8.0, 14.0, 26.0, 52.0)
LABEL_MIN_SCALE = (10.0, 20.0, 40.0, 70.0, 120.0)

# Airport label point size: LABEL_FONT_MIN at the first labelled scale,
# one point more per doubling, never above LABEL_FONT_MAX.
LABEL_FONT_MIN = 12.0
LABEL_FONT_MAX = 16.0

# Tile coordinate / imagery labels: from this scale on, at this size.
TILE_LABEL_MIN_SCALE = 72.0
TILE_LABEL_FONT = 10.0

# Labels placed per frame at most: past this the map is unreadable anyway,
# and a cap keeps a dense viewport's frame time bounded.
MAX_AIRPORT_LABELS = 300

# A monospaced glyph's advance as a fraction of the point size, and the
# pill's padding (px): enough to size a box without measuring text, the
# SAME estimate on both canvases so both drop the same labels.
_GLYPH_ADVANCE = 0.62
_PILL_PAD_X = 4.0
_PILL_PAD_Y = 2.0
# Gap between a mark's top and its label's box.
_LABEL_GAP = 3.0
# Collision grid cell (px).
_CELL = 64.0


class LabelCandidate(NamedTuple):
    """One airport on screen: its code, screen point, size class
    (O4_Airport_Rank), longest runway and whether a custom pack ships
    it."""

    code: str
    x: float
    y: float
    size_class: int
    runway_m: int
    custom: bool


class LabelBox(NamedTuple):
    """A label's screen box (top-left origin) and point size."""

    x: float
    y: float
    width: float
    height: float
    font_size: float


def _gate(table: Sequence[float], size_class: int) -> float:
    return table[min(max(int(size_class), 0), len(table) - 1)]


def mark_visible(size_class: int, custom: bool, scale: float) -> bool:
    """Whether an airport is marked at ``scale``."""
    return custom or scale >= _gate(MARK_MIN_SCALE, size_class)


def label_allowed(size_class: int, custom: bool, scale: float) -> bool:
    """Whether an airport may be labelled at ``scale`` (placement may
    still drop it); a custom airport uses the next-larger class's gate."""
    effective = int(size_class) - 1 if custom else int(size_class)
    return scale >= _gate(LABEL_MIN_SCALE, max(effective, 0))


def label_font_size(scale: float) -> float:
    """Airport label point size at ``scale``: 12 at the first labelled
    scale, +1 per doubling, at most 16 (rounded to a half point so a
    slow zoom does not re-lay text every frame)."""
    base = LABEL_MIN_SCALE[0]
    size = LABEL_FONT_MIN + math.log2(max(scale, base) / base)
    size = min(max(size, LABEL_FONT_MIN), LABEL_FONT_MAX)
    return math.floor(size * 2.0 + 0.5) / 2.0


def mark_radius(scale: float) -> float:
    """An airport mark's radius (px) at ``scale``: the sectional sizes."""
    if scale > 26.0:
        return 5.0
    return 3.5 if scale > 8.0 else 2.2


def label_box(x: float, y: float, code: str, font_size: float,
              mark_radius: float) -> LabelBox:
    """The box of ``code``'s label, centred over the mark at (x, y)."""
    width = len(code) * _GLYPH_ADVANCE * font_size + 2 * _PILL_PAD_X
    height = font_size + 2 * _PILL_PAD_Y
    return LabelBox(x - width / 2.0, y - mark_radius - _LABEL_GAP - height,
                    width, height, font_size)


def _rank(c: LabelCandidate) -> Tuple[int, int, int, str]:
    return (int(c.size_class), 0 if c.custom else 1, -int(c.runway_m), c.code)


def _overlaps(a: LabelBox, b: LabelBox) -> bool:
    return (a.x < b.x + b.width and b.x < a.x + a.width
            and a.y < b.y + b.height and b.y < a.y + a.height)


def place_airport_labels(candidates: Sequence[LabelCandidate], scale: float,
                         mark_radius: float,
                         limit: int = MAX_AIRPORT_LABELS
                         ) -> Tuple[List[int], List[Tuple[int, LabelBox]]]:
    """Which candidates are marked, and which are labelled where.

    Returns ``(marks, labels)``: ``marks`` the indexes (into
    ``candidates``) of every marked airport, in input order; ``labels``
    ``(index, box)`` pairs in rank order, no two boxes overlapping.
    """
    marks = [i for i, c in enumerate(candidates)
             if mark_visible(c.size_class, c.custom, scale)]
    font = label_font_size(scale)
    order = sorted((i for i in marks
                    if label_allowed(candidates[i].size_class,
                                     candidates[i].custom, scale)),
                   key=lambda i: _rank(candidates[i]))
    grid: Dict[Tuple[int, int], List[LabelBox]] = {}
    labels: List[Tuple[int, LabelBox]] = []
    for i in order:
        if len(labels) >= limit:
            break
        c = candidates[i]
        box = label_box(c.x, c.y, c.code, font, mark_radius)
        cells = _cells(box)
        if any(_overlaps(box, other)
               for cell in cells for other in grid.get(cell, ())):
            continue
        for cell in cells:
            grid.setdefault(cell, []).append(box)
        labels.append((i, box))
    return marks, labels


def _cells(box: LabelBox) -> List[Tuple[int, int]]:
    x0 = int(math.floor(box.x / _CELL))
    x1 = int(math.floor((box.x + box.width) / _CELL))
    y0 = int(math.floor(box.y / _CELL))
    y1 = int(math.floor((box.y + box.height) / _CELL))
    return [(cx, cy) for cx in range(x0, x1 + 1) for cy in range(y0, y1 + 1)]


def imagery_label(provider: Optional[str], zl: Optional[int],
                  has_zones: bool = False) -> str:
    """A tile's bottom-left imagery label: ``BI ZL16``, ``BI ZL16 +zones``
    with zones; an unknown part reads ``?`` and an unknown whole
    ``imagery ?`` -- never nothing (#817)."""
    provider = (provider or "").strip()
    if not provider and not zl:
        text = "imagery ?"
    else:
        text = "%s ZL%s" % (provider[:4] if provider else "?",
                            int(zl) if zl else "?")
    return text + " +zones" if has_zones else text


def scale_for_slippy_zoom(zoom: float) -> float:
    """The map scale (px per degree of longitude) of a slippy-map zoom
    level -- how the Qt map, which zooms in slippy levels, reads the
    gates above."""
    return 256.0 * (2.0 ** zoom) / 360.0
