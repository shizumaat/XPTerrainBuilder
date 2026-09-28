"""§42 (1b) THE HARD GROUND PLANE — its identity and vertex set (owner
RULINGS 2026-09-27a (5); spec ``docs/specs/hard-plane-apron-spec.md``;
issue #20).

ONE derivation site, in the ``model`` layer so every consumer may read it
(issue #84: ``solve/design`` may not import ``constraints``, and
``constraints`` may not import ``airport`` — ``tests/auto_patch_v2/
test_model.py::test_dependency_direction``).  ``airport/object_pavement``
mints the prefix onto hard-plane bodies and re-exports it;
``constraints/hard_plane`` mints the level row over these vertices;
``solve/design`` drops them from the body-datum plane fit.
"""
from __future__ import annotations

from .planar import PlanarMap

__all__ = ["HARD_PLANE_PREFIX", "is_hard_plane_ref", "hard_plane_vertices"]

#: §42 (1b): the pavement-id prefix of a HARD-PLANE body (a sub-prefix of
#: ``classify/sources.OBJECT_PAVEMENT_PREFIX``, so every object-pavement
#: gate reads it exactly as any other object pavement).
HARD_PLANE_PREFIX = "dsf:objpavhp"


def is_hard_plane_ref(ref: str | None) -> bool:
    """§42 (1b): does this pavement / cell / face ref name a hard plane?"""
    return bool(ref) and str(ref).startswith(HARD_PLANE_PREFIX)


def hard_plane_vertices(planar: PlanarMap) -> set[int]:
    """Every ring and hole vertex of every hard-plane face."""
    out: set[int] = set()
    for f in planar.faces.values():
        if not is_hard_plane_ref(getattr(f, "ref", None)):
            continue
        out.update(planar.ring_vertices(f.ring))
        for h in f.holes:
            out.update(planar.ring_vertices(h))
    return out
