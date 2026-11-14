"""THE KNIFE: every cell of a classification cut FLUSH at a region the
planar map takes for itself -- a pit's rim (``planar/basins``), a storey
shell's pad (``planar/storey_pad``) -- so no standing cell lies under it
and none is re-noded along it.

The runway family and the structures are never cut (a pit or a pad yields
to them before it is minted); a building pad only where the caller says
pads are cut; a cell's largest remaining piece keeps its ref, the others
take ``<ref>#<j>``.  A §53 gap piece stands off the knife by the mint's
stand-off (``structure_approach.cut_gap_cells``), and is cut LAST, so every
standing and new cell keeps the base map's place (spec §60 (9) R1b, §53
(18)): ONE knife for every structure."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon

from ..classify.roles import Cell
from ..geom.parts import polygon_parts_with_area
from ..model.planar import is_gap_ref
from .structure_approach import cut_gap_cells

__all__ = ["knife_cells"]


def knife_cells(cells: _t.Sequence[Cell], polys: _t.Sequence[Polygon], knife, law,
                runway_roles: _t.Collection[str], *, cut_pads: bool, mark: str,
                new_cells: _t.Sequence[Cell] = ()) -> tuple[list[Cell], int]:
    """``(cells, number cut)``: ``cells`` (with their ``polys``) cut at
    ``knife`` (module docstring), ``new_cells`` after the standing ones and
    before the gap pieces, every id renumbered; each cut piece's evidence
    carries ``mark``."""
    out: list[Cell] = []
    n_cut = 0

    def _cut(c: Cell, p: Polygon, blade) -> None:
        nonlocal n_cut
        if c.role in runway_roles or c.kind == "structure" or blade is None \
                or not p.intersects(blade):
            out.append(c)
            return
        if c.role == "building" and not cut_pads:
            out.append(c)
            return
        rest_p = p.difference(blade)
        n_cut += 1
        for j, part in enumerate(polygon_parts_with_area(rest_p)):
            if part.area < 0.25:
                continue
            out.append(Cell(len(out), c.role, c.ref if j == 0 else f"{c.ref}#{j}",
                            tuple(part.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in part.interiors),
                            c.code_number, c.code_letter, c.side, c.kind,
                            dict(c.evidence, **{mark: 1.0})))

    for c, p in zip(cells, polys, strict=True):
        if not is_gap_ref(c.ref):
            _cut(c, p, knife)
    out.extend(new_cells)
    cut_gap_cells([c for c in cells if is_gap_ref(c.ref)], knife, law, _cut)   # LAST
    return [_dc.replace(c, id=i) for i, c in enumerate(out)], n_cut
