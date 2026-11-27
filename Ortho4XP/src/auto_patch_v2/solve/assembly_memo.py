"""THE SHEET'S GEOMETRY, ONCE PER STAGED SOLVE (#2206).

``solve/design_assemble.assemble`` runs once per stage solve -- stage 0, every
stage-1 pass (a retarget, pass 1b, a pin-yield trial), the stage-2 shadow,
stage 2 and the follower pass: seven at KATL.  Part of what it builds reads
only the MAP and the stage's SHEET (which faces it triangulates), never the
stage's reduction, its drop set's values or its constraint set: each face's
triangulation (``rows._face_triangles``), the sheet's wall cut
(``wall_cut.wall_cut_edges``) and its cotangent Laplacian with the vertex
areas (``rows._cotangent_laplacian``).

Inside :func:`scoped` (``solve/design.solve_design``) they are computed once
per INPUT IDENTITY and handed back while they are the latest of their kind;
outside a scope they are computed every time.  The key is the identity of
every object the functions read, and the memo holds those objects, so an id
is never reused while it is remembered; every input is immutable
(``PlanarMap``, ``Face``, ``Vertex`` and ``Edge`` are frozen dataclasses), so
a hit is the answer a fresh read gives, bit for bit.  Callers only read it.

ONE SLOT PER KIND (the sheet; the faces of one map): the stage solves run in
order and never go back -- stage 0 and stage 1 on the ribbon-free map, stage
2 and the follower pass on the full one -- so an older answer is never asked
for again.  MEASURED KATL: the sheet misses at stage 0, the first stage-1
pass and stage 2, and hits on the other three stage-1 passes and the
follower pass.  The law rows' one-sided sides (``rows._law_sides``) are NOT
held: every stage's set carries new ``diffs`` / ``linears`` tuples (pass 1b
is ``ConstraintSet.from_rows``), so they missed at every stage of six
airports while holding them cost up to 1.8 GB of peak memory (OMDB).  The
memo dies with the scope; nothing outlives the solve.
"""
from __future__ import annotations

import contextlib
import functools
import typing as _t

__all__ = ["scoped", "sheet_geometry"]

#: the open scope's memo: kind -> ``(inputs, extra, answer)``, its one slot;
#: ``None`` outside a scope (every call computes)
_MEMO: "dict[str, tuple[tuple, _t.Any, _t.Any] | None] | None" = None


@contextlib.contextmanager
def _scope() -> _t.Iterator[None]:
    """Memoise until the block exits (a nested scope shares the outer one)."""
    global _MEMO
    if _MEMO is not None:
        yield
        return
    _MEMO = {}
    try:
        yield
    finally:
        _MEMO = None


def scoped(fn: _t.Callable) -> _t.Callable:
    """``fn`` run inside :func:`_scope` (signature kept for ``inspect``)."""
    @functools.wraps(fn)
    def run(*args: _t.Any, **kwargs: _t.Any) -> _t.Any:
        with _scope():
            return fn(*args, **kwargs)
    return run


def _held(kind: str, objs: tuple, extra: _t.Hashable,
          compute: _t.Callable[[], _t.Any]) -> _t.Any:
    """``compute()`` -- or the answer held in ``kind``'s one slot when it
    was computed from the same ``objs`` (by identity) and ``extra``."""
    memo = _MEMO
    if memo is None:
        return compute()
    hit = memo.get(kind)
    if hit is None or hit[1] != extra or len(hit[0]) != len(objs) or any(
            a is not b for a, b in zip(hit[0], objs, strict=True)):
        memo[kind] = None                 # the old answer goes before the new is built
        hit = memo[kind] = (objs, extra, compute())
    return hit[2]


def _face_triangles_of(planar: _t.Any, fid: int) -> list[tuple[int, int, int]]:
    """``rows._face_triangles``, held per face for the map's last sheet
    reader (one map's table at a time: a new map's ``vertices`` / ``edges``
    starts a new one)."""
    from .rows import _face_triangles
    table = _held("faces", (planar.vertices, planar.edges), None, dict)
    face = planar.faces[fid]
    hit = table.get(fid)
    if hit is None or hit[0] is not face:
        hit = table[fid] = (face, _face_triangles(planar, fid))
    return hit[1]


def sheet_geometry(planar: _t.Any, sheet_faces: _t.Sequence[int], n: int
                   ) -> tuple[list[tuple[int, int, int]], _t.Any, _t.Any]:
    """The sheet's triangles (face by face, in ``sheet_faces`` order), its
    cotangent Laplacian as CSR with the wall-cut edges skipped, and the
    vertex areas -- what ``assemble`` sections 1 and 4 read.  Read-only."""
    from .rows import _cotangent_laplacian
    from .wall_cut import wall_cut_edges
    reads = (planar.vertices, planar.edges, planar.faces,
             getattr(planar, "road_terrace", None), getattr(planar, "plate_under", None))

    def compute():
        tris: list[tuple[int, int, int]] = []
        for fid in sheet_faces:
            tris.extend(_face_triangles_of(planar, fid))
        L, area = _cotangent_laplacian(planar, tris, n, wall_cut_edges(planar, tris))
        return tris, L.tocsr(), area
    return _held("sheet", reads, (tuple(sheet_faces), n), compute)

