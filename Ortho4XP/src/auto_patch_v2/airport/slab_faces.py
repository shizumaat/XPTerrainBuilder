"""THE FACES OF A SLAB COMPONENT (owner RULINGS 2026-10-14d; lane drape229).

The base-slab witness (``geom/base_slab``) reads parts by their plan rings
and heights; two of the 14d rules need the component's own FACES, read off
the authored file the partition was read from (``Member.authored_path``,
the pristine ``.anchor_bak`` where one exists):

* :func:`face_facts` — the share of the component's face area that is
  SIDE faces and the authored ``y`` range of its up-facing PLATE faces
  (``geom.base_slab.FaceFacts``, the witness's rules 5 and 6);
* :func:`up_faces` — which of the component's triangles face UP, the set
  the draped writer re-emits (``airport/obj8_split``'s drape cut).

ONE winding convention for both: X-Plane OBJ8 triangles face the viewer
CLOCKWISE, so the outward normal of ``(a, b, c)`` is ``(c − a) × (b − a)``
(read on the HECA ``T23/T3_road`` sheet — a single-sided road, every face
visible from above, every normal up under this convention and down under
the other).  A PLATE face has ``|n_y| ≥ [bridge] deck_plate_normal_y_min``
(the near-horizontal reading the deck and floor plates already use); an
UP face has ``n_y`` at least that.

Pure reads, cached per (file, threshold): a candidate slab is a handful of
files per airport.
"""
from __future__ import annotations

import functools
import typing as _t

import numpy as np

from ..geom.base_slab import FaceFacts, register_face_reader
from . import obj8 as _obj8

__all__ = ["face_facts", "up_faces", "faces_for", "witness_faces", "tri_normals_y"]


def tri_normals_y(v: np.ndarray, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(n_y, area)`` per triangle of ``tris`` (``(m, 3)`` vertex indices
    into ``v``) under the OBJ8 clockwise winding (module doc)."""
    a, b, c = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    n = np.cross(c - a, b - a)
    two_a = np.linalg.norm(n, axis=1)
    ny = np.where(two_a > 0.0, n[:, 1] / np.where(two_a > 0.0, two_a, 1.0), 0.0)
    return ny, 0.5 * two_a


@functools.lru_cache(maxsize=64)
def _components(path: str) -> "tuple[np.ndarray, list] | None":
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError, IndexError):
        return None
    return g.vertices, _obj8.solid_components(g)


def _comp(path: str, comp: int) -> "tuple[np.ndarray, np.ndarray] | None":
    got = _components(path) if path else None
    if got is None or not 0 <= int(comp) < len(got[1]):
        return None
    v, comps = got
    return v, np.asarray(comps[int(comp)].tris, dtype=np.int64).reshape(-1, 3)


def face_facts(path: str, comp: int, ny_min: float) -> "FaceFacts | None":
    """Rules 5 and 6's facts for component ``comp`` of the file at
    ``path``; ``None`` where the file or the component cannot be read."""
    got = _comp(path, comp)
    if got is None or not got[1].shape[0]:
        return None
    v, tris = got
    ny, area = tri_normals_y(v, tris)
    total = float(area.sum())
    if total <= 0.0:
        return None
    side = float(area[np.abs(ny) < ny_min].sum()) / total
    up = ny >= ny_min
    ys = v[tris[up].reshape(-1), 1] if up.any() else np.zeros(1)
    return FaceFacts(side, float(ys.max() - ys.min()))


def up_faces(path: str, comp: int, ny_min: float) -> "frozenset[tuple[int, int, int]]":
    """The up-facing triangles of component ``comp`` as sorted authored
    vertex triples — the keys ``obj8_split`` files triangles by."""
    got = _comp(path, comp)
    if got is None:
        return frozenset()
    v, tris = got
    ny, _area = tri_normals_y(v, tris)
    return frozenset(tuple(sorted(int(i) for i in t)) for t in tris[ny >= ny_min])


@functools.lru_cache(maxsize=8)
def faces_for(ny_min: float) -> _t.Callable:
    """The witness's face reader at one threshold — ONE object per value,
    so ``geom.base_slab``'s memo (keyed on the reader's identity) is shared
    by every caller that reads the same law."""
    def faces(member: _t.Any, comp: int) -> "FaceFacts | None":
        return face_facts(str(getattr(member, "authored_path", "") or ""),
                          int(comp), float(ny_min))
    return faces


def witness_faces(lw: _t.Any) -> "_t.Callable | None":
    """THE face reader every caller of the base-slab witness passes
    (``law.tables.SlabLaw`` in hand), so the gap mint, the pad mint and
    the census read ONE witness; None where the plate witness is
    disarmed."""
    ny = float(getattr(lw, "plate_ny_min", 0.0) or 0.0)
    return faces_for(ny) if ny > 0.0 and lw.armed else None


register_face_reader(witness_faces)
