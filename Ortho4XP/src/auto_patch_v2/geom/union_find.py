"""UNION-FIND: the root of an element's set, with path halving.

ONE ``find`` for every disjoint-set forest in v2 (lane ``v2trim``, owner
RULINGS 2026-10-04c (2)); it replaced the same four-line closure written
out in fifteen functions.  The forest itself stays where it is built — a
``parent`` list or dict mapping every element to itself or to another
element of its set — and so does each caller's UNION, because which root
survives a union decides the order the sets come out in, and that order is
each caller's own.

``geom`` imports nothing of v2.
"""
from __future__ import annotations

import typing as _t

__all__ = ["find_root"]

K = _t.TypeVar("K", bound=_t.Hashable)


def find_root(parent: _t.Any, a: K) -> K:
    """The root of ``a``'s set in ``parent`` (a list indexed by element, or
    a dict keyed by it; every element must already be present).  Halves the
    path it walks, so repeated calls stay near-constant; the root returned
    does not depend on that compression."""
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a
