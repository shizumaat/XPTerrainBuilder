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
   non-wrapping, image-mapped north-up ``.pol``, no paved surface, not
   weather-transparent) of a MACHINE-NAMED FAMILY: its ``.pol`` or image
   shares, with at least :data:`MIN_TILES` - 1 other layers of its
   folder, the stem left when the numbers are taken out (``Ortho1`` …
   ``Ortho18``, ``KDAL_Photoreal23+2k+4k``), or both are hash-like names
   of one length (``7JF26B82``);
2. its polygons TILE A GRID with the family: edge-adjacent tiles (shared
   edges within :data:`EDGE_TOL` of the tile size), at least
   :data:`MIN_TILES` connected tiles of one size (within
   :data:`SIZE_TOL`), with the smaller tiles that close it at its edges;
3. the grid (a photo grid of (5), not a detail grid) EXTENDS OUTSIDE
   THE AIRPORT: some tile leaves the airport's
   boundary (row 130), or — with no boundary — the box of its runways,
   pavement and the pack's own other draped art grown by
   :data:`MARGIN_M`;
4. the grid — with every grid stacked on it (a tile of one overlapping
   a tile of the other: a see-through mask grid over its photos, a base
   grid under them), each of which passes (1)-(3) too — LIES OVER THE
   AIRPORT: at least one of their tiles passes the whole witness (over
   the airport, photo-sized, opaque).  They are then hidden WHOLE — every
   tile, over the airport or not (issue #1960: a 21-tile grid lost only
   the 9 tiles that touched the airport);
5. a stack MORE THAN ONE LAYER DEEP (its tiles draw at more than one
   draw order) is a photo grid under a DETAIL-TEXTURE grid: the grids at
   the stack's lowest draw order are the photos and are hidden; a grid
   drawn over them is the pack's detail texture and stays (owner RULINGS
   2026-11-09a (11), #1946: "hide the grid, keep the detail textures").
   A layer of no grid (a tyre-mark, oil or dirt decal on the runway —
   WED gives those a ``LOAD_CENTER`` too — or a single photo of the
   airport) is in no stack: hiding the grid under it leaves it over our
   imagery, as the pack's own art (#1960: one oil decal held 12 tiles of
   a grid).

THE PACK'S WHOLE PHOTO SET (owner RULINGS 2026-11-09a (10), #1968: "if
we're hiding photos, hide them all so our ortho imagery shows"): when any
grid passes (1)-(5), every photo of the pack on the tile goes with it
(:func:`pack_photos`) — every grid that is not a detail grid, over the
airport or not, and every photo layer of a hidden grid's family at its
draw order that tiles no grid of its own (a tile whose clipped shape
reads turned off north, a stray tile).

MEASURED 2026-11-07 over the installed packs' cached dumps: of 3,514
definitions passing (1)-(6) in 99 DSFs, 3,122 in 72 DSFs pass; (5)
differs from (1)-(4) at one pack only, the one whose hiding turned white.
Re-measured 2026-11-09 on the five Beta 8 packs (issues #1943 #1960 #1968):
the grid-whole reading hides 21 of 21 tiles at one pack (was 9), 8 of 8
at its neighbour (was 2), 18 of 18 at another (was 2); the blended pack
keeps all 66 (before (5) and the whole-set rule of RULINGS 2026-11-09a).
"""
from __future__ import annotations

import math
import os
import re
import typing as _t

__all__ = ["MIN_TILES", "SIZE_TOL", "EDGE_TOL", "MARGIN_M", "STACK_SHARE",
           "Layer", "hidden_stacks", "grid_indices", "grid_boxes", "pack_photos"]

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


def _grids(family: _t.Sequence[Layer]) -> list[set[int]]:
    """Witness (2): the grids of the family, as definition-index sets —
    each at least :data:`MIN_TILES` edge-adjacent tiles of one size, with
    the smaller tiles that close it at its edges (a grid clipped to its
    extent); grids sharing a definition are one."""
    tiles = [(ly.index, b) for ly in family for b in ly.boxes]
    out: list[set[int]] = []
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
            members = {cls[k][0] for k in comp}
            members.update(i for i, b in tiles
                           if b[2] - b[0] <= w * (1 + SIZE_TOL)
                           and b[3] - b[1] <= h * (1 + SIZE_TOL)
                           and any(_adjacent(b, g, tx, ty) for g in grid))
            out.append(members)
    return _merged(out)


def _merged(sets: list[set[int]]) -> list[set[int]]:
    """The sets with every two that share a member joined."""
    out: list[set[int]] = []
    for s in sets:
        s = set(s)
        for o in [o for o in out if o & s]:
            s |= o
            out.remove(o)
        out.append(s)
    return out


def grid_indices(layers: _t.Sequence[Layer]) -> set[int]:
    """The definition indices of every machine-named photo grid (witness
    (1)-(2)), whether it is hidden or kept: the photo rule's own, which
    no other detector may take (``pack_ground_sheets``)."""
    return {i for fam in _families(layers) for g in _grids(fam) for i in g}


def grid_boxes(layers: _t.Sequence[Layer]) -> dict[int, Box]:
    """``{definition index: the box of its whole grid}`` for every layer of
    a machine-named photo grid (witness (1)-(2)): the extent the photo is
    a tile of, which ``pack_drapes`` witness (5) reads as the photo's size
    when its own tile is small (issue #2036)."""
    by_index = {ly.index: ly for ly in layers}
    out: dict[int, Box] = {}
    for fam in _families(layers):
        for g in _grids(fam):
            bs = [b for i in g for b in by_index[i].boxes]
            box = (min(b[0] for b in bs), min(b[1] for b in bs),
                   max(b[2] for b in bs), max(b[3] for b in bs))
            out.update((i, box) for i in g)
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


def _area(box: Box, ground_art: _t.Sequence[Box]) -> Box:
    """An unbounded airport's area: its box and the pack's other draped
    art that touches it, grown by :data:`MARGIN_M`."""
    boxes = [box] + [g for g in ground_art if g[0] <= box[2] and box[0] <= g[2]
                     and g[1] <= box[3] and box[1] <= g[3]]
    return _grow((min(b[0] for b in boxes), min(b[1] for b in boxes),
                  max(b[2] for b in boxes), max(b[3] for b in boxes)), MARGIN_M)


class _Grids(_t.NamedTuple):
    """The photo layers' grids and how they stack (witness (1), (2), (5))."""
    grids: list[set[int]]          # definition indices of each grid
    grid_of: dict[int, int]        # definition index -> its grid
    stacks: list[list[int]]        # grid tiles joined by overlap
    detail: set[int]               # the grids drawn over a lower grid


def _grid_structure(layers: _t.Sequence[Layer]) -> _Grids:
    by_index = {ly.index: ly for ly in layers}
    grids = [g for fam in _families(layers) for g in _grids(fam)]
    grid_of = {i: k for k, g in enumerate(grids) for i in g}
    stacks = [[ly.index for ly in st] for st in _stacks(
        [ly for ly in layers if ly.index in grid_of])]
    detail: set[int] = set()
    for st in stacks:                                        # (5)
        base = min(by_index[i].layer for i in st)
        detail |= {grid_of[i] for i in st if by_index[i].layer > base}
    return _Grids(grids, grid_of, stacks, detail)


def hidden_stacks(layers: _t.Sequence[Layer], airport: _t.Sequence[Box],
                  bounded: bool | _t.Sequence[bool],
                  ground_art: _t.Sequence[Box]) -> set[int]:
    """THE RULE: the definition indices of every whole photo grid that
    passes (1)-(5) (a detail grid over it stays).  ``airport``: the
    airports' boxes (a boundary where ``bounded`` — one flag, or one per
    box — else its runways and pavement); ``ground_art``: the pack's own
    non-photo draped polygons' boxes, which widen an unbounded airport
    they touch."""
    if not airport:
        return set()
    flags = ([bounded] * len(airport) if isinstance(bounded, bool)
             else list(bounded))
    areas = [a if ok else _area(a, ground_art)
             for a, ok in zip(airport, flags, strict=True)]
    by_index = {ly.index: ly for ly in layers}
    gs = _grid_structure(layers)
    grids, grid_of = gs.grids, gs.grid_of
    out: set[int] = set()
    for cluster in _components(len(grids), lambda a, b: any(
            grid_of[i] == a for st in gs.stacks for i in st
            if any(grid_of[j] == b for j in st))):
        members = set().union(*(grids[k] for k in cluster))
        photos = [k for k in cluster if k not in gs.detail]  # (5)
        if not all(any(not any(_inside(b, a) for a in areas)
                       for i in grids[k] for b in by_index[i].boxes)
                   for k in photos):
            continue                                         # (3)
        if not any(by_index[i].witness for i in members):
            continue                                         # (4)
        out |= set().union(*(grids[k] for k in photos))
    return out


def pack_photos(layers: _t.Sequence[Layer], kin: _t.Sequence[Layer],
                hidden: _t.Collection[int]) -> set[int]:
    """THE WHOLE SET (RULINGS 2026-11-09a (10)): with ``hidden``
    (:func:`hidden_stacks`) not empty, every grid of ``layers`` that is
    not a detail grid, and every layer of ``layers`` + ``kin`` (the
    pack's photo layers whose image reads turned off north, witness (1)-(3)
    only) in no grid that shares a family key and the draw order of a
    hidden layer; ``set()`` when nothing is hidden."""
    if not hidden:
        return set()
    gs = _grid_structure(layers)
    out = set(hidden).union(*(g for k, g in enumerate(gs.grids)
                              if k not in gs.detail))
    every = {ly.index: ly for ly in (*layers, *kin)}
    keys = {(k, every[i].layer) for i in out if i in every
            for k in _family_keys(every[i].path, every[i].texture)}
    out |= {ly.index for ly in every.values() if ly.index not in gs.grid_of
            and any((k, ly.layer) in keys
                    for k in _family_keys(ly.path, ly.texture))}
    return out
