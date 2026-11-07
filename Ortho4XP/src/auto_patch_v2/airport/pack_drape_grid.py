"""MACHINE-TILED PHOTO GRIDS: which draped photos a pack's tiling makes
safe to hide (owner RULINGS 2026-11-07a (3)).

Owner (2026-11-07): "limit the draped photo removal to only include
polygons that form a grid of similarly named images that extend outside
the airport boundary.  Often they have some sort of machine generated
file name."  Hiding every opaque draped photo over an airport
(``pack_drapes`` witness (1)-(6)) turned large areas of one pack white:
it used its photos as the base and detail layers of its own ground art.
This module is the extra REQUIRED condition; a definition is hidden only
when ALL of these hold:

1. it is a PHOTO LAYER (witness (1)-(4): the pack's own draped,
   non-wrapping, image-mapped north-up ``.pol``, no surface, not
   weather-transparent) of a MACHINE-NAMED FAMILY: its ``.pol`` or image
   shares, with at least :data:`MIN_TILES` - 1 other layers of its
   folder, the stem left when the numbers are taken out (``Ortho1`` …
   ``Ortho18``, ``KDAL_Photoreal23+2k+4k``), or both are hash-like names
   of one length (``7JF26B82``);
2. its polygons TILE A GRID with the family: edge-adjacent tiles (shared
   edges within :data:`EDGE_TOL` of the tile size), at least
   :data:`MIN_TILES` connected tiles of one size (within
   :data:`SIZE_TOL`), with the smaller tiles that close it at its edges;
3. the grid EXTENDS OUTSIDE THE AIRPORT: some tile leaves the airport's
   boundary (row 130), or — with no boundary — the box of its runways,
   pavement and the pack's own other draped art grown by
   :data:`MARGIN_M`;
4. its WHOLE STACK qualifies: every photo layer whose footprint overlaps
   it (a see-through blend or detail layer over it, a base photo under
   it) is itself a member of a grid that passes (1)-(3) — a stack is
   hidden whole or kept whole, never the images without the blend layers
   laid over them — and at least one member passes the whole witness
   (over the airport, photo-sized, opaque);
5. the stack is ONE LAYER DEEP: its photo layers draw at one draw order.
   A photo laid over another photo (a see-through detail grid over an
   opaque base grid, both under the pack's own pavement) is the pack's
   own blended ground art and is kept whole.

MEASURED 2026-11-07 over the installed packs' cached dumps: of 3,514
definitions passing (1)-(6) in 99 DSFs, 3,122 in 72 DSFs pass; (5)
differs from (1)-(4) at one pack only, the one whose hiding turned white.
"""
from __future__ import annotations

import math
import os
import re
import typing as _t

__all__ = ["MIN_TILES", "SIZE_TOL", "EDGE_TOL", "MARGIN_M", "STACK_SHARE",
           "Layer", "hidden_stacks"]

#: the fewest tiles that make a grid
MIN_TILES = 4
#: how far (share of the median) a regular tile's size may differ
SIZE_TOL = 0.10
#: how far (share of the tile size) two shared edges may miss each other:
#: a tile turned by the grid convergence (up to ``pack_drapes.NORTH_UP_DEG``)
#: widens its box by up to sin(3 deg) ~ 5 % of the other side
EDGE_TOL = 0.06
#: how far (metres) the airport's box grows when it has no boundary
MARGIN_M = 250.0

Box = tuple[float, float, float, float]          # lon0, lat0, lon1, lat1

_HASH = re.compile(r"[A-Za-z0-9]{6,}")
#: WED's sub-tile suffix of a split orthophoto (``KDAL_Photoreal23+2k+4k``)
_SUBTILE = re.compile(r"(\+\d+k)+$")
_NUMBER = re.compile(r"\d+")


class Layer(_t.NamedTuple):
    """One photo-layer definition (``pack_drapes`` witness (1)-(4))."""
    index: int
    path: str                 # the DSF's resource path
    texture: str              # the .pol's image name
    boxes: tuple[Box, ...]    # its placed polygons
    witness: bool             # passes the whole witness (5)-(6) too
    layer: float              # its LAYER_GROUP offset (0 when unknown)


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name.replace("\\", "/")))[0]


def _family_keys(path: str, texture: str) -> set[str]:
    """The machine-name keys of one layer (witness (1)): its folder plus,
    for each name, the stem with WED's sub-tile suffix taken off and every
    number made ``#`` (``KDAL_Photoreal23+2k+4k`` and ``KDAL_Photoreal28``
    are ``kdal_photoreal#``), and the length of a hash-like name (letters
    and digits, at least two of each: ``7JF26B82``)."""
    folder = os.path.dirname(path.replace("\\", "/")).lower()
    keys: set[str] = set()
    for tag, name in (("pol", _stem(path)), ("img", _stem(texture))):
        name = _SUBTILE.sub("", name)
        if not name:
            continue
        keys.add(f"{folder}|{tag}|{_NUMBER.sub('#', name.lower())}")
        if (_HASH.fullmatch(name) and sum(c.isdigit() for c in name) >= 2
                and sum(c.isalpha() for c in name) >= 2):
            keys.add(f"{folder}|{tag}|hash{len(name)}")
    return keys


def _families(layers: _t.Sequence[Layer]) -> list[list[Layer]]:
    """The layers joined by a shared key (union-find), MIN_TILES or more."""
    parent = list(range(len(layers)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first: dict[str, int] = {}
    for i, ly in enumerate(layers):
        for k in _family_keys(ly.path, ly.texture):
            if k in first:
                parent[find(i)] = find(first[k])
            else:
                first[k] = i
    groups: dict[int, list[Layer]] = {}
    for i, ly in enumerate(layers):
        groups.setdefault(find(i), []).append(ly)
    return [g for g in groups.values() if len(g) >= MIN_TILES]


def _adjacent(a: Box, b: Box, tx: float, ty: float) -> bool:
    def run(lo0: float, hi0: float, lo1: float, hi1: float) -> float:
        return min(hi0, hi1) - max(lo0, lo1)
    side = abs(a[2] - b[0]) <= tx or abs(b[2] - a[0]) <= tx
    if side and run(a[1], a[3], b[1], b[3]) >= 0.5 * min(a[3] - a[1], b[3] - b[1]):
        return True
    stack = abs(a[3] - b[1]) <= ty or abs(b[3] - a[1]) <= ty
    return stack and run(a[0], a[2], b[0], b[2]) >= 0.5 * min(a[2] - a[0], b[2] - b[0])


def _size_classes(tiles: list[tuple[int, Box]]) -> list[list[tuple[int, Box]]]:
    """The tiles grouped by size: each within :data:`SIZE_TOL` of its
    class's first (largest) tile in both directions."""
    order = sorted(tiles, key=lambda t: -(t[1][2] - t[1][0]) * (t[1][3] - t[1][1]))
    classes: list[list[tuple[int, Box]]] = []
    for t in order:
        w, h = t[1][2] - t[1][0], t[1][3] - t[1][1]
        for c in classes:
            cw, ch = c[0][1][2] - c[0][1][0], c[0][1][3] - c[0][1][1]
            if abs(w - cw) <= cw * SIZE_TOL and abs(h - ch) <= ch * SIZE_TOL:
                c.append(t)
                break
        else:
            classes.append([t])
    return classes


def _components(n: int, linked: _t.Callable[[int, int], bool]) -> list[list[int]]:
    """The connected components of ``range(n)`` under ``linked``."""
    seen: set[int] = set()
    out: list[list[int]] = []
    for s in range(n):
        if s in seen:
            continue
        comp, todo = [], [s]
        seen.add(s)
        while todo:
            k = todo.pop()
            comp.append(k)
            for j in range(n):
                if j not in seen and linked(k, j):
                    seen.add(j)
                    todo.append(j)
        out.append(comp)
    return out


def _grid_members(family: _t.Sequence[Layer]) -> set[int]:
    """Witness (2): the definition indices of the family whose tiles join
    a regular grid — at least :data:`MIN_TILES` edge-adjacent tiles of one
    size — with the smaller tiles that close it at its edges (a grid
    clipped to its extent)."""
    tiles = [(ly.index, b) for ly in family for b in ly.boxes]
    out: set[int] = set()
    for cls in _size_classes(tiles):
        if len(cls) < MIN_TILES:
            continue
        w, h = cls[0][1][2] - cls[0][1][0], cls[0][1][3] - cls[0][1][1]
        tx, ty = w * EDGE_TOL, h * EDGE_TOL
        for comp in _components(len(cls), lambda a, b, cls=cls, tx=tx, ty=ty:
                                _adjacent(cls[a][1], cls[b][1], tx, ty)):
            if len(comp) < MIN_TILES:
                continue
            grid = [cls[k][1] for k in comp]
            out.update(cls[k][0] for k in comp)
            out.update(i for i, b in tiles
                       if b[2] - b[0] <= w * (1 + SIZE_TOL)
                       and b[3] - b[1] <= h * (1 + SIZE_TOL)
                       and any(_adjacent(b, g, tx, ty) for g in grid))
    return out


def _grow(box: Box, metres: float) -> Box:
    dlat = metres / 110_540.0
    dlon = metres / (111_320.0 * max(math.cos(math.radians((box[1] + box[3]) / 2)), 1e-6))
    return (box[0] - dlon, box[1] - dlat, box[2] + dlon, box[3] + dlat)


def _inside(b: Box, area: Box) -> bool:
    return area[0] <= b[0] and area[1] <= b[1] and b[2] <= area[2] and b[3] <= area[3]


#: the share of the smaller footprint two layers must share to be stacked
#: (two neighbouring tiles turned off north share a sliver of their boxes)
STACK_SHARE = 0.25


def _overlap(a: Box, b: Box) -> bool:
    """The two boxes share :data:`STACK_SHARE` of the smaller one."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return False
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h > STACK_SHARE * small


def _stacks(layers: _t.Sequence[Layer]) -> list[list[Layer]]:
    """The layers joined by overlapping footprints."""
    return [[layers[k] for k in comp] for comp in _components(
        len(layers), lambda a, b: any(_overlap(x, y) for x in layers[a].boxes
                                      for y in layers[b].boxes))]


def hidden_stacks(layers: _t.Sequence[Layer], airport: _t.Sequence[Box],
                  bounded: bool,
                  ground_art: _t.Sequence[Box]) -> set[int]:
    """THE RULE: the definition indices of every whole stack that passes
    (1)-(5).  ``airport``: the airport's boxes (its boundary when
    ``bounded``, else its runways and pavement); ``ground_art``: the
    pack's own non-photo draped polygons' boxes, which widen
    an unbounded airport."""
    if not airport:
        return set()
    if bounded:
        areas = list(airport)
    else:
        boxes = list(airport) + list(ground_art)
        areas = [_grow((min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes)),
                       MARGIN_M)]
    by_index = {ly.index: ly for ly in layers}
    passing: set[int] = set()
    for fam in _families(layers):
        members = _grid_members(fam)
        boxes = [b for i in members for b in by_index[i].boxes]
        if members and any(not any(_inside(b, a) for a in areas) for b in boxes):
            passing |= members                               # (1)-(3)
    out: set[int] = set()
    for stack in _stacks(layers):
        idx = {ly.index for ly in stack}
        if not idx <= passing or not any(ly.witness for ly in stack):
            continue                                         # (4)
        if len({ly.layer for ly in stack}) > 1:
            continue                                         # (5)
        out |= idx
    return out
