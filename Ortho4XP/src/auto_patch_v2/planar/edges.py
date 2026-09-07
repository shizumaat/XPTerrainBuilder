"""THE EDGE TABLE the planar builders walk rings into: an undirected edge
exists ONCE per vertex pair (I2), gets ``left_face`` from the face walking
it forward and ``right_face`` from the face walking it backward (I3), and
every vertex learns the faces incident to it (I5).  Shared by ``build``
(the arrangement's polygons) and ``terraces`` (the re-assembly after the
joint split) so the walk is stated once."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..model.planar import Edge, EdgeKind

__all__ = ["EdgeTable"]


class EdgeTable:
    """Rings of VERTEX IDS walked into edges; the face is on the LEFT of
    every directed ring edge."""

    def __init__(self) -> None:
        self.by_pair: dict[tuple[int, int], Edge] = {}
        self.edges: list[Edge] = []
        self.incident: dict[int, set[int]] = {}

    def walk(self, vs: _t.Sequence[int], fid: int) -> tuple[int, ...]:
        """Ring edges in walking order for the open ring ``vs``."""
        ids: list[int] = []
        seq = list(vs)
        for a, b in zip(seq, seq[1:] + seq[:1]):
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            e = self.by_pair.get(key)
            if e is None:
                e = Edge(len(self.edges), key[0], key[1], None, None, EdgeKind.BOUNDARY)
                self.edges.append(e)
            e = _dc.replace(e, left_face=fid) if (a, b) == key else _dc.replace(e, right_face=fid)
            self.by_pair[key] = e
            self.edges[e.id] = e
            ids.append(e.id)
            self.incident.setdefault(a, set()).add(fid)
            self.incident.setdefault(b, set()).add(fid)
        return tuple(ids)

    def edge_id(self, a: int, b: int) -> int | None:
        e = self.by_pair.get((a, b) if a < b else (b, a))
        return None if e is None else e.id
