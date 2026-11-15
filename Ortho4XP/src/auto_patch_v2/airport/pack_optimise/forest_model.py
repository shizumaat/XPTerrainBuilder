"""WHAT A FOREST DRAWS (issue #1937, "Optimise pack" step ``grass``): a
``.for`` file read as the triangles one of its plants costs at a
distance, the draw runs it opens and the ground a plant hides.

One model reads a pack's own flat grass and X-Plane 12's 3D planter
alike:

* a ``TREE`` row is one plant kind, its share its ``frequency``; the
  ``MESH_3D`` rows under it are its 3D meshes, each drawn within its
  ``MESH`` row's ``near``-``far`` (triangles = indices / 3; with two in
  range the heavier is counted);
* beyond its meshes (from 0 for a file without any) a plant is its
  billboard, ``2 x quads`` triangles, out to the file's ``LOD``;
* a draw run is one drawable (a mesh, or a file's billboards) drawn at
  some distance of a polygon;
* the ground a plant hides seen from the side is its card, ``height x
  height x w / h`` (the ``TREE`` row's texture box at its mean height).

The model is a dict in the recipe (:meth:`ForestModel.to_dict`), so a
later write and the estimate read the planter the user accepted without
the install.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["Tree", "ForestModel", "read_forest"]


@_dc.dataclass(frozen=True)
class Tree:
    """One plant kind: its share of the plants, its meshes ``(name,
    near, far, triangles)``, its billboard's triangles, where its
    billboard starts and its card (m²)."""
    share: float
    meshes: tuple[tuple[str, float, float, int], ...]
    card_tris: int
    card_near: float
    card_m2: float

    def tris_at(self, d: float, lod: float) -> int:
        """Triangles one plant of this kind draws at ``d`` metres."""
        if d >= lod:
            return 0
        live = [n for _m, near, far, n in self.meshes if near <= d < far]
        if live:
            return max(live)
        return self.card_tris if d >= self.card_near else 0


@_dc.dataclass(frozen=True)
class ForestModel:
    """A ``.for`` file as drawn (module doc): its ``LOD``, the ground one
    plant stands on at full density (``SPACING`` x x z, m²) and its
    plant kinds."""
    lod: float
    cell_m2: float
    trees: tuple[Tree, ...]

    def tris_at(self, d: float) -> float:
        """Mean triangles one plant draws at ``d`` metres."""
        return sum(t.share * t.tris_at(d, self.lod) for t in self.trees)

    def card_m2(self) -> float:
        """Mean card of one plant (m²)."""
        return sum(t.share * t.card_m2 for t in self.trees)

    def runs_in(self, near: float, far: float) -> int:
        """The drawables drawn somewhere between ``near`` and ``far``
        metres (module doc)."""
        if near >= self.lod:
            return 0
        far = min(far, self.lod)
        names = {m for t in self.trees for m, a, b, _n in t.meshes
                 if a <= far and near < b}
        cards = any(t.card_tris and t.card_near <= far for t in self.trees)
        return len(names) + int(cards)

    def bands(self) -> tuple[list[float], list[float]]:
        """``(cuts, triangles)``: the distances where what a plant draws
        changes (0 .. ``LOD``) and its mean triangles between each two."""
        cuts = sorted({0.0, self.lod, *(x for t in self.trees
                                        for _m, a, b, _n in t.meshes
                                        for x in (a, b)),
                       *(t.card_near for t in self.trees)})
        cuts = [c for c in cuts if c <= self.lod]
        return cuts, [self.tris_at((a + b) / 2.0)
                      for a, b in zip(cuts, cuts[1:], strict=False)]

    def tris_of(self, d: np.ndarray) -> np.ndarray:
        """:meth:`tris_at` of every distance in ``d``."""
        cuts, tris = self.bands()
        i = np.searchsorted(np.asarray(cuts), d, side="right") - 1
        ok = (i >= 0) & (i < len(tris))
        return np.where(ok, np.asarray(tris + [0.0])[np.clip(i, 0, len(tris))], 0.0)

    def view_weight(self) -> float:
        """Triangles one plant costs summed over every camera around it,
        per m² of camera ground (``∫ tris(d) 2πd dd``): what one m² of
        this forest at one plant per m² costs the view."""
        cuts, tris = self.bands()
        return sum(n * math.pi * (b * b - a * a)
                   for a, b, n in zip(cuts, cuts[1:], tris, strict=False))

    def to_dict(self) -> dict[str, _t.Any]:
        return {"lod": self.lod, "cell": round(self.cell_m2, 6),
                "trees": [[round(t.share, 6), [list(m) for m in t.meshes],
                           t.card_tris, t.card_near, round(t.card_m2, 6)]
                          for t in self.trees]}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "ForestModel":
        trees = tuple(Tree(float(s), tuple((str(m[0]), float(m[1]), float(m[2]),
                                            int(m[3])) for m in meshes),
                           int(ct), float(cn), float(cm))
                      for s, meshes, ct, cn, cm in d["trees"])
        return cls(float(d["lod"]), float(d["cell"]), trees)


def _rows(path: str) -> list[list[str]] | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return [ln.split() for ln in fh if ln.split()]
    except OSError:
        return None


def read_forest(path: str) -> ForestModel | None:
    """The model of the ``.for`` at ``path``; ``None`` when unreadable,
    treeless or without ``SPACING``/``LOD``."""
    rows = _rows(path)
    if rows is None:
        return None
    lod = cell = 0.0
    mesh: dict[str, tuple[float, float, int]] = {}
    kinds: list[tuple[float, float, int, list[str]]] = []
    try:
        for tok in rows:
            kw = tok[0]
            if kw == "LOD" and len(tok) >= 2:
                lod = float(tok[1])
            elif kw == "SPACING" and len(tok) >= 3:
                cell = float(tok[1]) * float(tok[2])
            elif kw == "MESH" and len(tok) >= 6:
                mesh[tok[1]] = (float(tok[2]), float(tok[3]), int(tok[5]) // 3)
            elif kw == "TREE" and len(tok) >= 10:
                w, h = float(tok[3]), float(tok[4])
                height = (float(tok[7]) + float(tok[8])) / 2.0
                card = height * height * (w / h if h > 0 else 1.0)
                kinds.append((max(float(tok[6]), 0.0), card,
                              2 * max(int(float(tok[9])), 1), []))
            elif kw == "MESH_3D" and len(tok) >= 2 and kinds:
                kinds[-1][3].append(tok[1])
    except ValueError:
        return None
    if not kinds or lod <= 0 or cell <= 0:
        return None
    total = sum(k[0] for k in kinds) or float(len(kinds))
    trees = []
    for freq, card, card_tris, names in kinds:
        ms = tuple((n, *mesh[n]) for n in names if n in mesh)
        trees.append(Tree((freq or total / len(kinds)) / total, ms, card_tris,
                          max((m[2] for m in ms), default=0.0), card))
    return ForestModel(lod, cell, tuple(trees))
