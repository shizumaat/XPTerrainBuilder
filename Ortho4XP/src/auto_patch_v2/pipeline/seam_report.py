"""§38 (2) THE FAMILY UNMET BETWEEN TWO SEAM PINS IS NAMED.

Owner RULINGS 2026-09-13ah: where a hard family cannot be met between two
seam pins "the FREE vertices between them yield … and a family that
cannot be met between two pins is NAMED in the design report with its
pins and the demanded vs allowed metres — never a moved pin, never a
silent residual."

``constraints.seam_exempt`` hands back every row the seam pin made yield
(the graded-strip zone band; see its docstring for why the row could only
survive as a pull on the pavement it was written to follow).  This module
reads those rows at the SOLVED surface and reports the ones the surface
still misses: how much the row DEMANDS of its governed vertex against how
much its own bound ALLOWS.  A row the solved surface meets anyway is
counted and not named — the yield cost nothing there.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import Linear, Row
from ..model.planar import PlanarMap

__all__ = ["seam_yield_block"]

#: How many rows the line names before it stops (the worst first).
NAME_CAP = 6


def _value(row: Row, z: _t.Sequence[float]) -> float | None:
    if not isinstance(row, Linear):
        return None
    try:
        return sum(c * float(z[v]) for v, c in row.terms)
    except (IndexError, TypeError):
        return None


def _miss(row: Linear, val: float) -> float:
    """Metres the value stands outside the row's own bound (0 inside)."""
    hi = float("inf") if row.hi is None else float(row.hi)
    lo = float("-inf") if row.lo is None else float(row.lo)
    return max(0.0, val - hi, lo - val)


def seam_yield_block(pm: PlanarMap, law: Law, yielded: _t.Sequence[Row],
                     z: _t.Sequence[float] | None) -> dict[str, _t.Any]:
    """``{rows, unmet, worst_m, by_family, named}`` over the yielded rows."""
    tol = float(law.tables.emit.materiality.elevation_m)
    by_family: dict[str, int] = {}
    rows_out: list[dict[str, _t.Any]] = []
    for r in yielded:
        head = r.source.ruling.split(" (")[0].strip() or r.source.generator
        by_family[head] = by_family.get(head, 0) + 1
        if z is None or not isinstance(r, Linear):
            continue
        val = _value(r, z)
        if val is None:
            continue
        miss = _miss(r, val)
        if miss <= tol:
            continue
        fv = getattr(r, "follows", None)
        pin = int(fv) if isinstance(fv, int) else (
            int(next(iter(fv))) if fv else r.terms[0][0])
        hi = None if r.hi is None else round(float(r.hi), 3)
        lo = None if r.lo is None else round(float(r.lo), 3)
        v = pm.vertices.get(pin)
        rows_out.append({
            "pin": pin,
            "lat": None if v is None else round(float(v.key[0]), 7),
            "lon": None if v is None else round(float(v.key[1]), 7),
            "family": head,
            "generator": r.source.generator,
            "demanded_m": round(val, 3),
            "allowed_lo_m": lo, "allowed_hi_m": hi,
            "miss_m": round(miss, 3),
            "feet": [int(q) for q, _c in r.terms if q != pin],
        })
    rows_out.sort(key=lambda d: -d["miss_m"])
    named = [
        f"{d['family']} at pin {d['pin']}"
        + (f" ({d['lat']}, {d['lon']})" if d["lat"] is not None else "")
        + f": demanded {d['demanded_m']:+.3f} m, allowed "
        + ("−inf" if d["allowed_lo_m"] is None else f"{d['allowed_lo_m']:+.3f}")
        + " … "
        + ("+inf" if d["allowed_hi_m"] is None else f"{d['allowed_hi_m']:+.3f}")
        + f" m (miss {d['miss_m']:.3f} m)"
        for d in rows_out[:NAME_CAP]]
    return {"rows": len(yielded), "unmet": len(rows_out),
            "worst_m": rows_out[0]["miss_m"] if rows_out else 0.0,
            "by_family": dict(sorted(by_family.items())),
            "named": named, "unmet_rows": rows_out[:NAME_CAP]}
