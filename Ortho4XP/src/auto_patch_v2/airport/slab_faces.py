"""THE FACES OF A SLAB COMPONENT (owner RULINGS 2026-10-14d; lane drape229).

The base-slab witness (``geom/base_slab``) reads parts by their plan rings
and heights; two of the 14d rules need the component's own FACES, read off
the authored file the partition was read from (``Member.authored_path``,
the pristine ``.anchor_bak`` where one exists):

* :func:`face_facts` — the share of the component's face area that is
  SIDE faces, the authored ``y`` range of its up-facing PLATE faces
  and the share of their area that stands CLEAR of the component's own
  foot (``geom.base_slab.FaceFacts``, the witness's rules 5, 6 and 7);
* :func:`tri_normals_y` — each triangle's ``n_y``, which the draped
  writer reads for the faces it re-emits (``airport/obj8_drape.up_keys``).

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

__all__ = ["face_facts", "faces_for", "witness_faces", "tri_normals_y"]


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


def face_facts(path: str, comp: int, ny_min: float,
               elev_m: float = 0.0) -> "FaceFacts | None":
    """Rules 5, 6 and 7's facts for component ``comp`` of the file at
    ``path``; ``None`` where the file or the component cannot be read.
    ``elev_m`` (``[bridge] deck_min_elevation_m``; 0 reads no elevation)
    is how far over the component's lowest authored ``y`` an up face's
    centroid must stand to count as ELEVATED (rule 7)."""
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
    up_m2 = float(area[up].sum())
    lifted = 0.0
    if elev_m > 0.0 and up_m2 > 0.0:
        foot = float(v[tris.reshape(-1), 1].min())
        cy = v[tris[up]][:, :, 1].mean(axis=1)
        lifted = float(area[up][cy >= foot + elev_m].sum()) / up_m2
    return FaceFacts(side, float(ys.max() - ys.min()), lifted)


@functools.lru_cache(maxsize=8)
def faces_for(ny_min: float, elev_m: float = 0.0) -> _t.Callable:
    """The witness's face reader at one law — ONE object per value pair,
    so ``geom.base_slab``'s memo (keyed on the reader's identity) is shared
    by every caller that reads the same law."""
    def faces(member: _t.Any, comp: int) -> "FaceFacts | None":
        return face_facts(str(getattr(member, "authored_path", "") or ""),
                          int(comp), float(ny_min), float(elev_m))
    # the thin plates the partition dropped (#712), read by the same owner
    # of the OBJ8 reader: ``geom/base_slab`` asks ``faces.plates``
    from .slab_plates import thin_plates
    faces.plates = thin_plates
    return faces


def witness_faces(lw: _t.Any) -> "_t.Callable | None":
    """THE face reader every caller of the base-slab witness passes
    (``law.tables.SlabLaw`` in hand), so the gap mint, the pad mint and
    the census read ONE witness; None where the plate witness is
    disarmed."""
    ny = float(getattr(lw, "plate_ny_min", 0.0) or 0.0)
    elev = float(getattr(lw, "deck_elev_m", 0.0) or 0.0)
    return faces_for(ny, elev) if ny > 0.0 and lw.armed else None


register_face_reader(witness_faces)
