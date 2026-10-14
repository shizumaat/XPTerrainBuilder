"""THE DRAPED SLAB IN A CUT FILE (owner RULINGS 2026-10-14d (1); lane
drape229).

A base slab over sloping terrain (``airport/slab_drape``) keeps its file,
its anchor and its rigid neighbours; only its UP-FACING triangles change
how they render: X-Plane OBJ8 draped geometry (``ATTR_draped``, OBJ8
v1000+) is laid on the terrain mesh under it, with the triangles' own
``ST`` coordinates on ``TEXTURE_DRAPED``, so the author's paving follows
the graded ground instead of floating over it or burying in it.  Its SIDE
and BOTTOM faces (kerbs, the slab's thickness) cannot drape and are
dropped.

What this module owns — the FILE-LEVEL spelling — and what it does not:

* :func:`header_lines` — the draped texture and layer lines a body file
  carrying draped triangles adds to its header: ``TEXTURE_DRAPED`` = the
  file's own ``TEXTURE`` (the UVs are authored against it),
  ``TEXTURE_DRAPED_NORMAL 1.0 <TEXTURE_NORMAL>`` where the file has a
  normal map, and ``ATTR_layer_group_draped <group> <offset>`` — the pack
  pavement band of ``[load] object_pavement_layer_groups`` /
  ``object_pavement_max_layer_offset`` (pavement draws there, the pack's
  markings above it).  The seen-on-disk spelling: HECA's own
  ``ground/Concrete_Polygon_1.obj``.
* :func:`block` / :func:`splice` — the draped ``TRIS`` bracketed by
  ``ATTR_draped`` / ``ATTR_no_draped``, put at the head of the body's
  command stream, inside its FIRST ``ATTR_LOD`` bracket where it has one
  (draped geometry belongs to the first LOD, the exporters' rule).

WHICH triangles drape is ``obj8_split``'s walk (the component is the
atom, §16c (1)) reading :func:`up_keys`; the winding convention is
``airport/slab_faces``'s, the one the witness reads.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from .slab_faces import tri_normals_y

__all__ = ["DrapeLaw", "drape_law", "header_lines", "block", "splice", "up_keys"]


class DrapeLaw(_t.NamedTuple):
    """The draped writer's law values (one derivation, :func:`drape_law`)."""

    #: an UP face: ``n_y`` at least this (``[bridge] deck_plate_normal_y_min``)
    ny_min: float
    #: ``ATTR_layer_group_draped`` group and offset (``[load]``)
    layer_group: str
    layer_offset: int


def drape_law(law: _t.Any) -> DrapeLaw:
    """``[bridge] deck_plate_normal_y_min`` and the ``[load]`` pavement
    layer band — the values the witness and the pavement reader use."""
    ld = law.tables.structures.load
    groups = tuple(getattr(ld, "object_pavement_layer_groups", ()) or ("runways",))
    return DrapeLaw(float(law.tables.structures.bridge.deck_plate_normal_y_min),
                    str(groups[0]),
                    int(getattr(ld, "object_pavement_max_layer_offset", 0)))


def up_keys(verts: np.ndarray, tris: np.ndarray, ny_min: float
            ) -> "set[tuple[int, int, int]]":
    """The sorted vertex triples of the triangles of ``tris`` facing UP."""
    t = np.asarray(tris, dtype=np.int64).reshape(-1, 3)
    if not t.shape[0]:
        return set()
    ny, _a = tri_normals_y(verts, t)
    return {tuple(sorted(int(i) for i in row)) for row in t[ny >= ny_min].tolist()}


def _directive(header: _t.Sequence[str], kw: str) -> "list[str] | None":
    for ln in header:
        t = ln.split()
        if t and t[0] == kw:
            return t[1:]
    return None


def header_lines(header: _t.Sequence[str], law: DrapeLaw) -> list[str]:
    """The lines a draped body adds to its file header (module doc);
    ``[]`` where the file names no ``TEXTURE`` (nothing to drape with)."""
    tex = _directive(header, "TEXTURE")
    if not tex:
        return []
    out = [f"TEXTURE_DRAPED\t{' '.join(tex)}"]
    nrm = _directive(header, "TEXTURE_NORMAL")
    if nrm:
        out.append(f"TEXTURE_DRAPED_NORMAL\t1.0 {' '.join(nrm)}")
    out.append(f"ATTR_layer_group_draped\t{law.layer_group}\t{law.layer_offset}")
    return out


def block(start: int, count: int) -> list[str]:
    """The draped command block over ``count`` indices from ``start``."""
    return ["ATTR_draped", f"TRIS\t{start} {count}", "ATTR_no_draped"]


def splice(commands: list[str], lines: _t.Sequence[str]) -> list[str]:
    """``commands`` with ``lines`` at the head of the stream — right after
    its first ``ATTR_LOD`` bracket line where it has one."""
    at = 0
    for i, ln in enumerate(commands):
        if ln.split(None, 1)[:1] == ["ATTR_LOD"]:
            at = i + 1
            break
    return list(commands[:at]) + list(lines) + list(commands[at:])
