"""HIDE PLACEMENT ROWS of a DSF dump by resource and anchor: the one row
hide the pack writes use (the generated decks' ``hides``, spec 2123; the
overlapping structures the user hid, #2145 ``pack_overlap_choice``).

A row is named by its resource and its anchor within ``tol_deg``: an
``OBJECT*`` row's position, or a polygon's (facade's) FIRST point.  The
definition stays declared (the write drops an unused one).  One pass over
the text for any number of rows.
"""
from __future__ import annotations

import typing as _t

__all__ = ["TOL_DEG", "hide_rows"]

#: how close an anchor must be to name a row (degrees, ~0.2 m)
TOL_DEG = 2e-6

_OBJECT_ROWS = ("OBJECT", "OBJECT_MSL", "OBJECT_AGL")


def _wanted(defs: _t.Sequence[str], rows) -> dict[str, list[tuple[float, float]]]:
    """``{definition index: [anchors]}`` of the rows asked for."""
    by_res: dict[str, list[tuple[float, float]]] = {}
    for res, lon, lat in rows:
        by_res.setdefault(str(res), []).append((float(lon), float(lat)))
    return {str(k): by_res[p] for k, p in enumerate(defs) if p in by_res}


def _hit(anchors, lon: float, lat: float, tol: float) -> bool:
    return any(abs(lon - a) <= tol and abs(lat - b) <= tol for a, b in anchors)


def hide_rows(text: str, rows: _t.Iterable[_t.Sequence], tol_deg: float = TOL_DEG
              ) -> tuple[str, int]:
    """``text`` without the placements ``rows`` names (each ``(resource,
    lon, lat)``); returns ``(text, rows removed)``."""
    rows = list(rows)
    if not rows:
        return text, 0
    lines = text.split("\n")
    objs = _wanted([ln.split(None, 1)[1].strip() for ln in lines
                    if ln.startswith("OBJECT_DEF ")], rows)
    polys = _wanted([ln.split(None, 1)[1].strip() for ln in lines
                     if ln.startswith("POLYGON_DEF ")], rows)
    if not objs and not polys:
        return text, 0
    keep: list[str] = []
    held: list[str] | None = None        # the polygon being read
    anchors = None
    n = 0
    for ln in lines:
        if held is not None:
            held.append(ln)
            if anchors is not None and ln.startswith("POLYGON_POINT"):
                t = ln.split()
                if not _hit(anchors, float(t[1]), float(t[2]), tol_deg):
                    keep += held                 # not this one: keep it whole
                    held = None
                    continue
                anchors = None                   # first point matched
            if ln.startswith("END_POLYGON"):
                if anchors is None:
                    n += 1                       # matched: dropped whole
                else:
                    keep += held
                held = None
            continue
        toks = ln.split(None, 4)
        if toks and toks[0] in _OBJECT_ROWS and len(toks) >= 4 and toks[1] in objs:
            try:
                if _hit(objs[toks[1]], float(toks[2]), float(toks[3]), tol_deg):
                    n += 1
                    continue
            except ValueError:
                pass
        elif toks and toks[0] == "BEGIN_POLYGON" and len(toks) > 1 and toks[1] in polys:
            held, anchors = [ln], polys[toks[1]]
            continue
        keep.append(ln)
    if held:
        keep += held
    return "\n".join(keep), n
