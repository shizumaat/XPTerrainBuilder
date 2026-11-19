"""THE DRAPED POLYGONS A LOWER PACK LAYS INSIDE A CUSTOM AIRPORT
(RULINGS 2026-11-19h; the #2145 offer's drape rows).

Owner (2026-11-19T01:35Z): "Offer to hide overlapping pack polygons,
yes" -- answering: at KORD a worldwide overlay pack below the custom
airport in ``scenery_packs.ini`` drapes 2,660 ``.pol`` (its own pavement,
shaped to the Gateway layout) under the airport pack's; the airport's
exclusion boxes catch only a few.

THE READING (pure: dump lines in, rows out; no pack is written here):
every ``BEGIN_POLYGON`` of a ``.pol`` definition (a draped polygon --
never a facade, a line or a forest) whose first winding lies INSIDE the
airport's region (``sibling_riders.airport_region``: apt.dat row 130,
else its pavements' hull): its representative point (a point always
inside the polygon) is inside the region.  A polygon outside the region
is never named; one crossing its edge counts where most of it lies.
Each polygon is a :class:`pack_overlap.HideRow` (its definition and
first point), the key ``dsf_row_hide`` matches.

Nothing here names an airport or a pack.
"""
from __future__ import annotations

import collections
import typing as _t

from shapely.geometry import Polygon
from shapely.prepared import prep

from .pack_overlap import HideRow

__all__ = ["draped_rows", "summary"]


def _polygons(lines: _t.Iterable[str]) -> _t.Iterator[tuple[str, list]]:
    """``(definition, first winding)`` of every draped ``.pol`` polygon."""
    defs: list[str] = []
    cur: str | None = None
    ring: list = []
    first = False
    for ln in lines:
        c = ln[:6]
        if c == "POLYGO":
            if first and ln.startswith("POLYGON_POINT"):
                t = ln.split()
                ring.append((float(t[1]), float(t[2])))
            elif ln.startswith("POLYGON_DEF"):
                defs.append(ln.split(None, 1)[1].strip())
        elif c == "BEGIN_":
            if ln.startswith("BEGIN_POLYGON"):
                d = defs[int(ln.split()[1])]
                cur = d if d.lower().endswith(".pol") else None
                ring, first = [], False
            elif ln.startswith("BEGIN_WINDING") and cur is not None:
                first = not ring
        elif c == "END_WI":
            first = False
        elif c == "END_PO":
            if cur is not None and len(ring) >= 3:
                yield cur, ring
            cur = None


def draped_rows(lines: _t.Iterable[str], region: _t.Any) -> list[HideRow]:
    """The draped polygons of a DSF dump inside ``region`` (a lon/lat
    shapely geometry; module doc), in file order."""
    if region is None or region.is_empty:
        return []
    w, s, e, n = region.bounds
    inside = prep(region)
    out: list[HideRow] = []
    for res, ring in _polygons(lines):
        if not any(w <= lo <= e and s <= la <= n for lo, la in ring):
            continue
        poly = Polygon(ring).buffer(0)
        if not poly.is_empty and inside.contains(poly.representative_point()):
            out.append(HideRow(res, ring[0][0], ring[0][1]))
    return out


def summary(lower: str, airport: str, idents: str, rows: _t.Sequence[HideRow]) -> str:
    """One line for the offer: who drapes how many polygons where."""
    names = collections.Counter(r.resource.rsplit("/", 1)[-1] for r in rows)
    top = ", ".join(f"{d} {k}" for d, k in names.most_common(3))
    n = len(rows)
    return (f"{lower} drapes {n:,} ground polygon{'s' if n != 1 else ''} inside "
            f"{idents}'s boundary, under {airport}'s own layout"
            + (f" ({top})" if top else "") + ".")
