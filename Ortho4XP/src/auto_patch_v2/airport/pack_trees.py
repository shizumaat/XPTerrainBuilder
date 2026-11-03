"""OLD FLAT TREES that are not library forests, and their X-Plane 12 3D
upgrade (issue #1710; the offer, the record and the Undo are issue
#1360's, :mod:`.pack_forests`).

Owner (2026-10-30, 2026-11-02): KIDA's trees are 80 pack-local OBJ files
of flat crossed quads; EPWA ships its own flat ``vegetation/
forest_mix_full.for``.  Neither had an X-Plane 12 3D equivalent in the
#1360 map, which names only X-Plane's own flat forests.  Any pack:

* A FLAT TREE OBJECT — :func:`flat_trees`: a pack-local OBJ whose file or
  texture name has a tree word (:data:`.pack_trees_map.TREE_WORDS`), that
  is made ONLY of quads (every pair of triangles has four vertices;
  nothing draped, nothing animated), nearly all of them upright
  (:data:`UPRIGHT_MIN`).  Its trees are
  read from the file: the quads whose plan centres lie within
  :data:`TREE_RADIUS_M` are one tree (a crossed billboard), its height
  the quads' vertical extent.  The species is the name's
  (:data:`.pack_trees_map.NAME_FAMILY`); a name with none is a conifer
  when its billboards are narrow (:data:`CONIFER_ASPECT`), broadleaf
  otherwise, and shrubs under :data:`SHRUB_M`.  A real 3D tree (a mesh,
  not quads) is never one.
* THE UPGRADE OF ONE — :func:`convert_objects`: X-Plane 12 exports no 3D
  tree object, only per-species 3D FORESTS, so each placement of the
  object becomes POINT forests (one point per tree, parameter
  :data:`POINT_FOREST`) of that species at the size nearest each tree's
  height; the object's definition and its rows leave the DSF.
* A PACK'S OWN FLAT ``.for`` — :func:`local_forest_target`: tree type
  from its ``TREE`` rows (narrow billboards are conifers; a mix of both
  is ``mixed``), sparse from ``SPACING``, and nothing for ground cover
  (grass: every tree under :data:`GROUND_COVER_M`).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import re
import typing as _t

import numpy as np

from .obj8 import _to_frame, parse_obj8, resolve_resource
from .pack_art import MissingDef, declared_definitions, omit_definitions
from .pack_trees_map import FAMILIES, LOCAL_FOREST, NAME_FAMILY, TREE_WORDS

__all__ = ["FlatTrees", "flat_trees", "local_forest_target",
           "convert_objects", "body_base", "POINT_FOREST"]

#: quads whose plan centres are this close are one tree
TREE_RADIUS_M = 1.0
#: a quad whose height is under this share of its width lies flat (a
#: billboard stands up)
UPRIGHT_SHARE = 0.25
#: the share of a flat tree object's quads that must stand up
UPRIGHT_MIN = 0.95
#: billboard width / height under which an unnamed tree is a conifer
CONIFER_ASPECT = 0.55
#: an unnamed broadleaf whose median tree is lower than this is shrubs
SHRUB_M = 3.0
#: a ``.for`` whose trees are all lower than this is ground cover
GROUND_COVER_M = 1.5
#: a ``.for`` whose mean spacing exceeds this is sparse
SPARSE_SPACING_M = 10.0
#: DSF polygon parameter of a point forest at full density (512 + 255)
POINT_FOREST = 767
#: X-Plane's earth radius, metres (local frame -> degrees)
EARTH_R = 6378145.0

_WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])")
_BODY = re.compile(r"__b\d+(?:_[0-9a-f]+)?\.obj$", re.IGNORECASE)


@_dc.dataclass(frozen=True)
class FlatTrees:
    """The trees of one flat tree object: ``family`` (a
    :data:`.pack_trees_map.FAMILIES` key) and ``(x, z, height)`` each."""

    family: str
    trees: tuple[tuple[float, float, float], ...]


def _name_words(path: str) -> set[str]:
    """The lower-cased words of a file name's stem (``KIDA_Veg_Fir_01``
    -> kida, veg, fir; ``TreeOak`` -> tree, oak)."""
    stem = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]
    return {w.lower() for w in _WORD.findall(stem)}


def body_base(path: str) -> str:
    """The original's path of a split body this writer minted
    (``obj8_split``: ``<stem>__b<k>[_<tag>].obj``); others unchanged."""
    return _BODY.sub(".obj", path)


def _texture(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                tok = raw.split()
                if tok and tok[0] == "TEXTURE" and len(tok) > 1:
                    return tok[1]
                if tok and tok[0] in ("POINT_COUNTS", "VT"):
                    break
    except OSError:
        pass
    return ""


def _quads(path: str) -> np.ndarray | None:
    """Per quad ``(cx, cz, ymin, ymax, width)``; ``None`` unless the
    file is ONLY quads (no drape, no animation)."""
    try:
        g = parse_obj8(path)
    except Exception:
        return None
    m = g.solid.shape[0]
    if (not m or m % 2 or g.draped.shape[0]
            or (g.animated.shape[0] and g.animated.any())):
        return None
    s = np.sort(g.solid.reshape(-1, 6), axis=1)
    if not np.all(1 + (np.diff(s, axis=1) != 0).sum(axis=1) == 4):
        return None
    p = g.vertices[s]                                  # (q, 6, 3)
    lo, hi = p.min(axis=1), p.max(axis=1)
    width = np.maximum(hi[:, 0] - lo[:, 0], hi[:, 2] - lo[:, 2])
    return np.column_stack([(lo[:, 0] + hi[:, 0]) / 2, (lo[:, 2] + hi[:, 2]) / 2,
                            lo[:, 1], hi[:, 1], width])


def _cluster(q: np.ndarray) -> list[list[float]]:
    """Trees ``[x, z, ymin, ymax]`` from upright quads."""
    cells: dict[tuple[int, int], list[int]] = {}
    trees: list[list[float]] = []
    r2 = TREE_RADIUS_M ** 2
    for cx, cz, y0, y1, _w in q.tolist():
        i, j = math.floor(cx / TREE_RADIUS_M), math.floor(cz / TREE_RADIUS_M)
        hit = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for k in cells.get((i + di, j + dj), ()):
                    t = trees[k]
                    if (t[0] - cx) ** 2 + (t[1] - cz) ** 2 <= r2:
                        hit = k
                        break
                if hit is not None:
                    break
            if hit is not None:
                break
        if hit is None:
            cells.setdefault((i, j), []).append(len(trees))
            trees.append([cx, cz, y0, y1])
        else:
            t = trees[hit]
            t[2], t[3] = min(t[2], y0), max(t[3], y1)
    return trees


def _family(words: _t.Iterable[str], q: np.ndarray, heights: list[float]) -> str:
    for w in sorted(words):
        if w in NAME_FAMILY:
            return NAME_FAMILY[w]
    aspect = float(np.median(q[:, 4] / np.maximum(q[:, 3] - q[:, 2], 1e-6)))
    if aspect < CONIFER_ASPECT:
        return NAME_FAMILY["conifer"]
    if heights and float(np.median(heights)) < SHRUB_M:
        return NAME_FAMILY["shrub"]
    return NAME_FAMILY["broadleaf"]


def flat_trees(path: str) -> FlatTrees | None:
    """THE CHECK for one object file: its trees and species, or ``None``
    when it is not a flat tree object (module doc).  Memoised on the
    file's size and time: every build of the pack asks again."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _MEMO:
        _MEMO[key] = _read_trees(path)
    return _MEMO[key]


_MEMO: dict[tuple[str, int, int], FlatTrees | None] = {}


def _read_trees(path: str) -> FlatTrees | None:
    words = _name_words(path)
    tex = _texture(path)
    if not (words | _name_words(tex)) & TREE_WORDS:
        return None
    q = _quads(path)
    if q is None:
        return None
    upright = q[:, 3] - q[:, 2] >= np.maximum(UPRIGHT_SHARE * q[:, 4], 0.05)
    if upright.mean() < UPRIGHT_MIN:
        return None
    q = q[upright]
    trees = _cluster(q)
    if not trees:
        return None
    heights = [t[3] - t[2] for t in trees]
    fam = _family(sorted(words) + sorted(_name_words(tex)), q, heights)
    return FlatTrees(fam, tuple((t[0], t[1], t[3] - t[2]) for t in trees))


def _size_for(family: str, height: float) -> str:
    """The family member whose height is nearest ``height`` (by ratio)."""
    sizes = FAMILIES[family]
    h = max(height, 0.1)
    return min(sizes, key=lambda s: abs(math.log(h / s[1])))[0]


# ── a pack's own .for ────────────────────────────────────────────────────

def local_forest_target(path: str) -> str:
    """The X-Plane 12 3D forest for a pack's own flat ``.for``; ``""``
    for ground cover or an unreadable file (module doc)."""
    spacing: list[float] = []
    rows: list[tuple[float, float, float]] = []       # (freq, aspect, max h)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                tok = raw.split()
                if not tok:
                    continue
                try:
                    if tok[0] == "SPACING" and len(tok) >= 3:
                        spacing = [float(tok[1]), float(tok[2])]
                    elif tok[0] == "TREE" and len(tok) >= 9:
                        w, h = float(tok[3]), float(tok[4])
                        rows.append((max(float(tok[6]), 0.0),
                                     w / h if h > 0 else 1.0, float(tok[8])))
                except ValueError:
                    continue
    except OSError:
        return ""
    if not rows:
        return ""
    total = sum(r[0] for r in rows) or float(len(rows))
    wt = [(r[0] or 1.0) / total for r in rows]
    if max(r[2] for r in rows) < GROUND_COVER_M:
        return ""
    tall = sum(w * r[2] for w, r in zip(wt, rows, strict=True))
    coni = sum(w for w, r in zip(wt, rows, strict=True) if r[1] < CONIFER_ASPECT)
    kind = ("shrb" if tall < SHRUB_M + 1.0 else "coni" if coni >= 0.75
            else "broad" if coni <= 0.25 else "mixed")
    sparse = bool(spacing) and sum(spacing) / 2 > SPARSE_SPACING_M
    return LOCAL_FOREST[(kind, sparse)]


# ── the rewrite ──────────────────────────────────────────────────────────

def _tile_box(lines: _t.Sequence[str]) -> tuple[float, float, float, float] | None:
    want = {"sim/west": 0, "sim/south": 1, "sim/east": 2, "sim/north": 3}
    box = [math.nan] * 4
    for raw in lines:
        tok = raw.split()
        if tok[:1] == ["PROPERTY"] and len(tok) >= 3 and tok[1] in want:
            try:
                box[want[tok[1]]] = float(tok[2])
            except ValueError:
                pass
        elif tok[:1] and tok[0].endswith("_DEF"):
            break
    return None if any(math.isnan(v) for v in box) else tuple(box)


def _placements(lines: _t.Sequence[str], wanted: _t.Mapping[int, str]
                ) -> dict[str, list[tuple[float, float, float]]]:
    out: dict[str, list[tuple[float, float, float]]] = {p: [] for p in wanted.values()}
    for raw in lines:
        tok = raw.split()
        if len(tok) >= 5 and tok[0] in ("OBJECT", "OBJECT_MSL", "OBJECT_AGL"):
            try:
                i = int(tok[1])
                if i in wanted:
                    out[wanted[i]].append((float(tok[2]), float(tok[3]), float(tok[4])))
            except ValueError:
                continue
    return out


def _points(place: tuple[float, float, float], trees: FlatTrees, box
            ) -> dict[str, list[tuple[float, float]]]:
    lon0, lat0, heading = place
    k_lat = 180.0 / (math.pi * EARTH_R)
    k_lon = k_lat / max(math.cos(math.radians(lat0)), 1e-6)
    out: dict[str, list[tuple[float, float]]] = {}
    for x, z, h in trees.trees:
        e, n = _to_frame((0.0, 0.0), heading, x, z)
        lon, lat = lon0 + e * k_lon, lat0 + n * k_lat
        if box is not None and not (box[0] <= lon <= box[2] and box[1] <= lat <= box[3]):
            continue
        out.setdefault(_size_for(trees.family, h), []).append((lon, lat))
    return out


def convert_objects(edited: str, pristine: str, families: _t.Mapping[str, str],
                    pack_root: str) -> tuple[str, int, int]:
    """THE REWRITE (pure but for reading the object files): ``edited``
    with every placement of each object ``families`` names (declared
    path -> family) — read from the PRISTINE rows, so a split body the
    placement write made of it is the same tree — turned into point
    forests, and the object's definitions (its bodies too) gone.
    Returns the text, the objects converted and the trees placed."""
    if not families:
        return edited, 0, 0
    trees: dict[str, FlatTrees] = {}
    for path in families:
        phys = resolve_resource(path.replace("\\", "/").replace(":", "/"),
                                pack_root, None)
        ft = flat_trees(phys) if phys else None
        if ft is not None:
            trees[path] = FlatTrees(families[path], ft.trees)
    if not trees:
        return edited, 0, 0
    plines = pristine.splitlines()
    pdecl = declared_definitions(plines)["object"]
    places = _placements(plines, {i: p for i, p in enumerate(pdecl) if p in trees})
    edecl = declared_definitions(edited.splitlines())["object"]
    gone = [MissingDef("object", i, p) for i, p in enumerate(edecl)
            if p in trees or body_base(p) in trees]
    text, _counts = omit_definitions(edited, gone)
    lines = text.splitlines(keepends=True)
    box = _tile_box(lines)
    polys = list(declared_definitions(lines)["polygon"])
    blocks: list[str] = []
    new_defs: list[str] = []
    placed = 0
    for path in sorted(trees):
        for place in places.get(path, ()):
            for target, pts in sorted(_points(place, trees[path], box).items()):
                if target not in polys:
                    polys.append(target)
                    new_defs.append(f"POLYGON_DEF {target}\n")
                blocks.append(f"BEGIN_POLYGON {polys.index(target)} {POINT_FOREST} 2\n"
                              "BEGIN_WINDING\n")
                blocks.extend(f"POLYGON_POINT {lon:.9f} {lat:.9f}\n" for lon, lat in pts)
                blocks.append("END_WINDING\nEND_POLYGON\n")
                placed += len(pts)
    at = _after_definitions(lines)
    return "".join(lines[:at] + new_defs + blocks + lines[at:]), len(trees), placed


def _after_definitions(lines: _t.Sequence[str]) -> int:
    """The line index just after the dump's last ``*_DEF`` row."""
    last = 0
    for k, raw in enumerate(lines):
        kw = raw.split(None, 1)[0] if raw.strip() else ""
        if kw.endswith("_DEF"):
            last = k + 1
        elif kw in ("OBJECT", "OBJECT_MSL", "OBJECT_AGL", "BEGIN_POLYGON",
                    "BEGIN_SEGMENT", "BEGIN_SEGMENT_CURVED", "BEGIN_PATCH"):
            break
    return last
