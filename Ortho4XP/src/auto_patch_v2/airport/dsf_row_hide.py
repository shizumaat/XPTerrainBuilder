"""HIDE PLACEMENT ROWS of a DSF dump by resource and anchor: the one row
hide the pack writes use (the generated decks' ``hides``, spec 2123; the
overlapping structures the user hid, #2145 ``pack_overlap_choice``).

A row is named by its resource and its anchor within ``tol_deg``: an
``OBJECT*`` row's position, or a polygon's (facade's) FIRST point.  The
rows name the PRISTINE placements; one the object stage split is written
as its bodies (their own files and anchors), so :func:`through_splits`
names those too (#2167, MEASURED KJFK 1.0.560: the four faked-cut
placements under the generated decks were split, and the hide matched
none of them).  :func:`drop_segments` leaves a whole road network out
(RULINGS 2026-11-19i: our overlay where another pack replaces the default
roads over the tile).  The
definition stays declared (the write drops an unused one).  One pass over
the text for any number of rows.
"""
from __future__ import annotations

import typing as _t

__all__ = ["TOL_DEG", "hide_rows", "through_splits", "drawn_rows", "pieces_within",
           "drawn_pieces", "drop_segments"]

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


def through_splits(rows: _t.Iterable[_t.Sequence], splits: _t.Iterable,
                   tol_deg: float = TOL_DEG, pack_root: str = "") -> list[tuple]:
    """``rows`` (each ``(resource, lon, lat)``) plus the row of every body
    of each split (``model.placement.Split``) whose original placement one
    of them names -- by its DSF definition, which a library export may
    name for the pack file the split records (``obj8.same_resource`` in
    ``pack_root``: MEASURED KRDU 1.0.570, the hide named
    ``KRDU/F3R8/STH_TML.obj``, the split ``F3R8_Summer/STH_TML.obj``, and its
    renamed bodies stayed drawn)."""
    rows = [tuple(r) for r in rows]
    if not rows:
        return rows
    by_res: dict[str, list[tuple[float, float]]] = {}
    for res, lon, lat in rows:
        by_res.setdefault(str(res), []).append((float(lon), float(lat)))
    out = list(rows)
    for sp in splits:
        p = sp.placement
        if any(_hit(at, float(p.lon), float(p.lat), tol_deg) and _same(res, str(p.resource),
                                                                       pack_root)
               for res, at in by_res.items()):
            out += [(b.new_resource, b.anchor.lon, b.anchor.lat) for b in sp.bodies]
    return out


def _inside(ring, lon: float, lat: float) -> bool:
    from shapely.geometry import Point, Polygon
    return len(ring) >= 3 and Polygon(ring).buffer(0.0).covers(Point(lon, lat))


def pieces_within(pieces: _t.Iterable[_t.Sequence], splits: _t.Iterable,
                  tol_deg: float = TOL_DEG, pack_root: str = "") -> list[tuple]:
    """The rows of the bodies, standing within each PIECE-WISE hide's plan
    (``(resource, lon, lat, within)``, ``within`` a lon/lat ring), of the
    split of the placement it names (as :func:`through_splits` names it):
    the object keeps its pieces at its other sites (owner RULINGS
    2026-11-20u: a hide takes only what stands on the deck).  A placement
    the object stage did not split hides nothing (:func:`drawn_pieces`
    names it)."""
    pieces = list(pieces)
    out: list[tuple] = []
    for sp in splits if pieces else ():
        p = sp.placement
        for res, lon, lat, within in pieces:
            if _hit([(float(lon), float(lat))], float(p.lon), float(p.lat), tol_deg) \
                    and _same(str(res), str(p.resource), pack_root):
                out += [(b.new_resource, b.anchor.lon, b.anchor.lat) for b in sp.bodies
                        if _inside(within, float(b.anchor.lon), float(b.anchor.lat))]
    return out


def drawn_pieces(text: str, pieces: _t.Iterable[_t.Sequence], splits: _t.Iterable = (),
                 tol_deg: float = TOL_DEG) -> list[tuple[str, float, float]]:
    """:func:`drawn_rows` for the piece-wise hides: a body of the split
    standing within the hide's plan still drawn, or -- no split of it
    written -- the placement's own row (its pieces on the deck drawn)."""
    out: list[tuple[str, float, float]] = []
    splits = list(splits or ())
    for res, lon, lat, within in pieces:
        mine = [sp for sp in splits if _name(str(sp.placement.resource)) == _name(str(res))
                and _hit([(float(lon), float(lat))], float(sp.placement.lon),
                         float(sp.placement.lat), tol_deg)]
        rows = [(b.new_resource, b.anchor.lon, b.anchor.lat) for sp in mine for b in sp.bodies
                if _inside(within, float(b.anchor.lon), float(b.anchor.lat))] if mine \
            else [(res, lon, lat)]
        out += drawn_rows(text, rows)
    return out


def _same(def_path: str, resource: str, pack_root: str) -> bool:
    if def_path == resource:
        return True
    from .obj8 import same_resource
    return same_resource(def_path, resource, pack_root or None)


def drawn_rows(text: str, rows: _t.Iterable[_t.Sequence], splits: _t.Iterable = (),
               tol_deg: float = TOL_DEG) -> list[tuple[str, float, float]]:
    """The OBJECT rows of ``text`` (a written DSF dump) that still draw a
    hidden placement of ``rows`` (each ``(resource, lon, lat)``), as
    ``(definition, lon, lat)``: its own row, or a row of a body of a split
    of it -- the split's original read by its anchor and its file NAME
    (``a/b/STH_TML.obj`` and ``c/STH_TML.obj`` name one placement), not by
    :func:`through_splits`'s resolution, so a resolution miss reads here
    (the written-pack read of census ``pack_bridge_under_deck``)."""
    rows = [(str(r), float(lo), float(la)) for r, lo, la in rows]
    if not rows:
        return []
    want = {(r, lo, la) for r, lo, la in rows}
    by_name: dict[str, list[tuple[float, float]]] = {}
    for r, lo, la in rows:
        by_name.setdefault(_name(r), []).append((lo, la))
    for sp in splits or ():
        p = sp.placement
        if _hit(by_name.get(_name(str(p.resource)), ()), float(p.lon), float(p.lat), tol_deg):
            want |= {(str(b.new_resource), float(b.anchor.lon), float(b.anchor.lat))
                     for b in sp.bodies}
    lines = text.split("\n")
    defs = [ln.split(None, 1)[1].strip() for ln in lines if ln.startswith("OBJECT_DEF ")]
    at: dict[str, list[tuple[float, float]]] = {}
    for r, lo, la in want:
        at.setdefault(r, []).append((lo, la))
    out = []
    for ln in lines:
        toks = ln.split(None, 4)
        if not toks or toks[0] not in _OBJECT_ROWS or len(toks) < 4:
            continue
        try:
            k, lon, lat = int(toks[1]), float(toks[2]), float(toks[3])
        except ValueError:
            continue
        if 0 <= k < len(defs) and _hit(at.get(defs[k], ()), lon, lat, tol_deg):
            out.append((defs[k], lon, lat))
    return out


def _name(resource: str) -> str:
    return resource.replace("\\", "/").rsplit("/", 1)[-1].lower()


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


def drop_segments(text: str) -> tuple[str, int]:
    """``text`` without its road network's segments (every ``BEGIN_SEGMENT``
    .. ``END_SEGMENT`` block; the ``NETWORK_DEF`` stays declared); returns
    ``(text, segments removed)``."""
    if "\nBEGIN_SEGMENT" not in text and not text.startswith("BEGIN_SEGMENT"):
        return text, 0
    keep: list[str] = []
    inside = False
    n = 0
    for ln in text.split("\n"):
        if inside:
            inside = not ln.startswith("END_SEGMENT")
            continue
        if ln.startswith("BEGIN_SEGMENT"):
            inside, n = True, n + 1
            continue
        keep.append(ln)
    return "\n".join(keep), n
