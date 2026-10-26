""""Set elevation…" on the selected patch shapes (issue #1357; the Mac
app's ``SceneryKit/PatchShapeElevation.swift``).

Pure functions of the document, tested headless:

* :func:`plan` — what one Set elevation touches: every node of the selected
  shapes, outer rings and their holes (the ``gap_interior_ring`` rings
  :func:`O4_Qt_Preview3D_Shapes.assemble` pairs with them), split into the
  nodes only they use and the nodes they share with other shapes, the
  neighbouring shapes those shared nodes belong to, and the mean
  ``alt_abs`` that prefills the field;
* :func:`to_metres` / :func:`from_metres` — the field's display units;
* :func:`summary` — the dialog's first line;
* :func:`apply` — ``patch_edit.set_alt`` on the plan's nodes.
"""
from __future__ import annotations

import typing as _t

from o4_engine import patch_edit as PE
from O4_Qt_Preview3D_Shapes import assemble, is_gap_ring

__all__ = ["FEET_PER_METRE", "UNITS", "ElevationPlan", "plan", "to_metres",
           "from_metres", "summary", "apply"]

#: International foot (the Mac's ``PatchNodeInspector.feetPerMetre``).
FEET_PER_METRE = 1 / 0.3048
UNITS = ("m", "ft")


class ElevationPlan(_t.NamedTuple):
    """The selected shapes' nodes and who else uses them."""
    #: The selected way ids plus the holes paired with them.
    ways: frozenset
    #: Nodes no other shape uses.
    own: frozenset
    #: Nodes some other shape uses too.
    shared: frozenset
    #: The other shapes (way ids) that hold a shared node.
    neighbours: frozenset
    #: Mean ``alt_abs`` of the nodes that carry one (None: all from the mesh).
    mean_alt: float | None

    def targets(self, include_shared: bool = True) -> list[int]:
        """The nodes Apply sets, sorted."""
        return sorted(self.own | self.shared if include_shared else self.own)


def _holes(doc: PE.PatchDoc, way_ids: set[int]) -> set[int]:
    """The gap-ring ways :func:`assemble` pairs with the surfaces in
    ``way_ids`` (a nested surface is its own shape, never a hole here)."""
    gaps = {tuple(w.refs[:-1]): w.id for w in doc.ways if is_gap_ring(w)}
    if not gaps:
        return set()
    return {gaps[h] for s in assemble(doc) if s.way_id in way_ids
            for h in s.holes if h in gaps}


def plan(doc: PE.PatchDoc, way_ids: _t.Iterable[int]) -> ElevationPlan:
    """What Set elevation does to the shapes ``way_ids``."""
    picked = set(way_ids)
    ways = picked | _holes(doc, picked)
    mine = {r for w in doc.ways if w.id in ways for r in w.refs if r in doc.nodes}
    neighbours = {w.id for w in doc.ways if w.id not in ways and mine.intersection(w.refs)}
    shared = {r for w in doc.ways if w.id in neighbours for r in w.refs} & mine
    alts = [doc.nodes[n][3] for n in sorted(mine) if doc.nodes[n][3] is not None]
    return ElevationPlan(frozenset(ways), frozenset(mine - shared), frozenset(shared),
                         frozenset(neighbours), sum(alts) / len(alts) if alts else None)


def to_metres(value: float, unit: str) -> float:
    """A field value in ``unit`` ("m" or "ft") as metres."""
    return value / FEET_PER_METRE if unit == "ft" else value


def from_metres(alt: float, unit: str) -> float:
    return alt * FEET_PER_METRE if unit == "ft" else alt


def summary(p: ElevationPlan, include_shared: bool = True) -> str:
    """"N shared nodes, M neighbouring shapes affected"."""
    def n(count, word):
        return "%s %s%s" % (format(count, ","), word, "" if count == 1 else "s")
    if not include_shared:
        return ("%s left as they are; no neighbouring shapes affected."
                % n(len(p.shared), "shared node"))
    return "%s, %s affected." % (n(len(p.shared), "shared node"),
                                 n(len(p.neighbours), "neighbouring shape"))


def apply(doc: PE.PatchDoc, p: ElevationPlan, alt: float,
          include_shared: bool = True) -> PE.PatchDoc:
    """Set ``alt`` (metres MSL) on the plan's nodes."""
    return PE.set_alt(doc, p.targets(include_shared), alt)
