"""A FENCE IS A DIVISION (owner RULINGS 2026-11-13s (2), #1338; owner
18:02Z: "fence lines are another clear indicator of a division, a fence
cannot cross airside, so a fence can be airside on one side and groundside
on the other, or groundside on both, but never airside on both sides of a
fence").

THE FENCES (:func:`fence_lines`): every pack LINE facade
(``Airport.edge_lines``) that ``airport/line_solidity.kind_of`` reads as a
wire fence, a low barrier or a solid wall standing on its zero
(``line_solidity.ON_TOP``) — the scenery pack's fences only, never OSM
(owner RULINGS 2026-11-13y (1): "Just use fences in the scenery pack, not
OSM").

A barrier INSIDE ONE PAGE the pack drew airside is no division (13y (1):
"aprons may have concrete or other types of barriers, and I guess do
sometimes have areas of construction fenced off"): :func:`split_at_fences`
never cuts a page born airside, and :func:`airside_both_sides` does not
count a station whose two probes land in the same born-airside page.

A fence RUNS ALONG an edge within ``[edge_lines] host_reach_m`` of it (the
one tolerance the engine already has for "a line object marks this paved
edge", ``classify/edge_line_mint``, #2054) and within §27's own
``_MOUTH_TRANSVERSE_DEG`` of its direction — a fence that CROSSES an edge
runs along none of it.  Three readers:

* :func:`split_at_fences` cuts a §27 candidate face a fence CROSSES into
  its pieces, so the flip can take the airside piece and leave the one
  beyond the fence (KCRW ``dsf:pol45``: one lot page, eleven fences through
  it, flipped whole); :func:`rejoin_unsplit` puts back whole every face
  whose pieces all ended in one role, so a fence changes no geometry where
  it divides nothing;
* §27 (``airside_edge.airside_edge_flip``) drops the run of a contact a
  fence runs along (:class:`_FenceBand`) — airside never propagates across
  a fence;
* :func:`airside_both_sides` is the DEFECT CHECK: a fence station whose
  probes either side (``[edge_lines] step_probe_m`` off the line) both land
  in airside pavement of two different pages (or of a page made airside by
  §27), summed into runs of ``[edge_lines] min_run_m``."""
from __future__ import annotations

import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import split, unary_union
from shapely.strtree import STRtree

from ..airport.line_solidity import ON_TOP, kind_of
from ..law import Law
from ..law.tables import role_side
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["fence_lines", "fence_band", "born_airside_pages",
           "split_at_fences", "rejoin_unsplit", "airside_both_sides"]


def fence_lines(airport, rules: Rules) -> list[tuple[str, LineString]]:
    """``(id, line)`` of every fence of ``airport`` (module doc), in the frame."""
    out: list[tuple[str, LineString]] = []
    for el in tuple(getattr(airport, "edge_lines", ()) or ()):
        if kind_of(el, rules.service) not in ON_TOP or len(el.points) < 2:
            continue
        pts = list(el.points) + ([el.points[0]] if el.closed else [])
        out.append((el.id, LineString(pts)))
    return [(i, ln) for i, ln in out if ln.length > 0.0]


def _unit(ax: float, ay: float, bx: float, by: float) -> tuple[float, float] | None:
    n = math.hypot(bx - ax, by - ay)
    return None if n <= 0.0 else ((bx - ax) / n, (by - ay) / n)


class _FenceBand:
    """The fences of an airport as §27 reads them: :meth:`along` is the
    part of a contact a fence RUNS ALONG (module doc)."""

    __slots__ = ("lines", "tree", "geom", "reach", "cos_min")

    def __init__(self, lines: _t.Sequence[LineString], reach: float, max_deg: float):
        self.lines = list(lines)
        self.tree = STRtree(self.lines)
        self.reach = float(reach)
        self.geom = unary_union([ln.buffer(self.reach, cap_style="flat") for ln in self.lines])
        self.cos_min = math.cos(math.radians(max_deg))

    def _parallel(self, seg: LineString) -> bool:
        """``seg`` runs within the angle of the fence nearest its middle."""
        c = list(seg.coords)
        d = _unit(*c[0], *c[-1])
        if d is None:
            return False
        mid = seg.interpolate(0.5, normalized=True)
        j = self.tree.nearest(mid)
        ln = self.lines[int(j)]
        s = ln.project(mid)
        a, b = ln.interpolate(max(0.0, s - 1.0)), ln.interpolate(min(ln.length, s + 1.0))
        f = _unit(a.x, a.y, b.x, b.y)
        return f is not None and abs(d[0] * f[0] + d[1] * f[1]) >= self.cos_min

    def along(self, contact):
        """The run of ``contact`` (a line geometry) a fence runs along."""
        near = contact.intersection(self.geom)
        segs = [LineString([p, q]) for g in getattr(near, "geoms", [near])
                if g.geom_type == "LineString"
                for p, q in zip(g.coords, list(g.coords)[1:], strict=False)]
        keep = [s for s in segs if s.length > 0.0 and self._parallel(s)]
        return unary_union(keep) if keep else None


def fence_band(lines: _t.Sequence[tuple[str, LineString]], rules: Rules) -> _FenceBand | None:
    """The :class:`_FenceBand` of ``lines`` (reach ``[edge_lines]
    host_reach_m``, angle §27's ``_MOUTH_TRANSVERSE_DEG``); ``None`` with
    no fence."""
    if not lines:
        return None
    from .airside_edge import _MOUTH_TRANSVERSE_DEG
    return _FenceBand([ln for _i, ln in lines], rules.edge_lines.host_reach_m,
                     _MOUTH_TRANSVERSE_DEG)


def page_of(ref) -> str:
    """The pavement page a face or cell ref names (a cut piece
    ``<ref>#<k>`` is its page's)."""
    return str(ref).partition("#")[0]


def born_airside_pages(final: _t.Sequence[list], law: Law) -> set[str]:
    """The pages (:func:`page_of`) a face of ``final`` is AIRSIDE in before
    §27 flips anything: the pages the pack drew airside."""
    return {page_of(f[1]) for f in final if role_side(law, f[0]) == "airside"}


def split_at_fences(final: list[list], lines: _t.Sequence[tuple[str, LineString]],
                    roles: _t.Collection[str], rules: Rules,
                    airside_pages: _t.Collection[str] = ()) -> dict[int, tuple]:
    """Cut every ``final`` face of a role in ``roles`` that a fence CROSSES
    (divides into two or more pieces of at least ``[cells] min_area_m2``)
    along it.  Each fence is read on past its ends by ``[edge_lines]
    host_reach_m`` (the reach it runs along an edge within): a gate's gap
    or a fence stopping short of the paved edge still divides (KCRW
    ``dsf:pol45``: its fences stand 0.2-10 m in from the lot's rim and
    divide it only so read). the largest piece keeps the entry, the rest are appended as
    ``<ref>#<k>`` (the next free serial of the ref, ``pad_road_exit``'s
    numbering), same role and evidence.  A piece under the floor stays
    with the piece it shares most boundary with.  Returns the cut faces:
    ``final`` index -> ``(the whole face, [indices of its other pieces])``,
    for :func:`rejoin_unsplit`.  A face of a page in ``airside_pages``
    (:func:`born_airside_pages`) is never cut: a barrier inside a page the
    pack drew airside divides nothing (13y (1))."""
    if not lines:
        return {}
    reach = float(rules.edge_lines.host_reach_m)
    lines = [(i, _extended(ln, reach)) for i, ln in lines]
    tree = STRtree([ln for _i, ln in lines])
    grid, floor = float(rules.cells.snap_grid_m), float(rules.cells.min_area_m2)
    serial: dict[str, int] = {}
    for f in final:
        base, _h, k = str(f[1]).partition("#")
        serial[base] = max(serial.get(base, 0), (int(k) if k.isdigit() else 0) + 1)
    groups: dict[int, tuple] = {}
    extra: list[list] = []
    for i, f in enumerate(final):
        if f[0] not in roles or page_of(f[1]) in airside_pages:
            continue
        hits = tree.query(f[2], predicate="intersects")
        if len(hits) == 0:
            continue
        cut = unary_union([lines[int(j)][1] for j in hits])
        try:
            pieces = polygon_parts(split(f[2], cut))
        except (ValueError, shapely.errors.ShapelyError):
            continue
        pieces = _fold_small(pieces, floor)
        if len(pieces) < 2:
            continue
        pieces = sorted((shapely.set_precision(p, grid) for p in pieces), key=lambda p: -p.area)
        groups[i] = (f[2], list(range(len(final) + len(extra),
                                      len(final) + len(extra) + len(pieces) - 1)))
        final[i] = [f[0], f[1], pieces[0], *f[3:]]
        base = page_of(f[1])
        for p in pieces[1:]:
            k = serial.get(base, 1)
            serial[base] = k + 1
            extra.append([f[0], f"{base}#{k}", p, f[3], dict(f[4], fence_split=1.0), *f[5:]])
    final.extend(extra)
    return groups


def rejoin_unsplit(final: list[list], groups: dict[int, tuple],
                   keep: _t.Collection[int] = ()) -> int:
    """Put back whole each :func:`split_at_fences` face whose pieces all
    carry one role (the fence divided nothing), unless a piece is in
    ``keep`` (one ``storey_edge.knife_storeys`` has cut).  Index-free
    afterwards: the dropped pieces leave ``final``.  Returns the faces that
    stay split."""
    drop: set[int] = set()
    split_left = 0
    for i, (whole, extra) in groups.items():
        members = [i, *extra]
        if len({final[j][0] for j in members}) == 1 and not set(members) & set(keep):
            final[i] = [final[i][0], final[i][1], whole, *final[i][3:]]
            drop.update(extra)
        else:
            split_left += 1
    final[:] = [f for j, f in enumerate(final) if j not in drop]
    return split_left


def _extended(line: LineString, d: float) -> LineString:
    """``line`` read on ``d`` past each end along its end segment."""
    c = list(line.coords)

    def past(p, q):
        u = _unit(q[0], q[1], p[0], p[1])
        return p if u is None else (p[0] + u[0] * d, p[1] + u[1] * d)
    return LineString([past(c[0], c[1]), *c, past(c[-1], c[-2])])


def _fold_small(pieces: list[Polygon], floor: float) -> list[Polygon]:
    """``pieces`` with each one under ``floor`` m2 unioned into the big
    piece it shares the longest boundary with."""
    big = [p for p in pieces if p.area >= floor]
    if len(big) < 2:
        return big
    for p in (q for q in pieces if q.area < floor):
        k = max(range(len(big)), key=lambda j: big[j].boundary.intersection(p.boundary).length)
        big[k] = big[k].union(p)
    return big


def _probe(line: LineString, s: float, d: float) -> tuple[Point, Point]:
    """The two points ``d`` off ``line`` either side of station ``s``."""
    p = line.interpolate(s)
    a = line.interpolate(max(0.0, s - 0.5))
    b = line.interpolate(min(line.length, s + 0.5))
    tx, ty = b.x - a.x, b.y - a.y
    n = (tx * tx + ty * ty) ** 0.5 or 1.0
    nx, ny = -ty / n * d, tx / n * d
    return Point(p.x + nx, p.y + ny), Point(p.x - nx, p.y - ny)


def _runs(marks: list[tuple[float, bool]], min_run: float) -> list[tuple[float, float]]:
    """Consecutive marking stations ``(s, marked)`` as ``(s0, s1)`` runs at
    least ``min_run`` long."""
    runs, start, last = [], None, None
    for s, hit in marks:
        if hit:
            start = s if start is None else start
            last = s
        elif start is not None:
            runs.append((start, last))
            start = None
    if start is not None:
        runs.append((start, last))
    return [(s0, s1) for s0, s1 in runs if s1 - s0 >= min_run]


def airside_both_sides(cells: _t.Sequence, lines: _t.Sequence[tuple[str, LineString]],
                       law: Law, rules: Rules) -> dict[str, _t.Any]:
    """THE DEFECT CHECK (module doc) over classified ``cells``: how many
    fences, and how many metres of them, stand with airside pavement on
    BOTH sides.  A station marks when both probes lie in a non-building
    airside cell and the two are not one BORN-AIRSIDE page (same
    :func:`page_of`, neither made airside by §27's ``airside_edge_flip``):
    a barrier inside one apron page is no division (13y (1)).  Consecutive
    marking stations at least ``min_run_m`` long count.  Returns
    ``fence_lines``, ``fence_airside_both`` (fences),
    ``fence_airside_both_m``, ``fence_inside_airside_page`` (fences with
    such a run inside one born-airside page, not counted) and
    ``fence_airside_both_sites`` (fence id and the frame point of each
    fence's first run)."""
    out: dict[str, _t.Any] = {"fence_lines": len(lines), "fence_airside_both": 0,
                              "fence_airside_both_m": 0.0, "fence_inside_airside_page": 0,
                              "fence_airside_both_sites": []}
    air_cells = [c for c in cells if c.role != "building" and role_side(law, c.role) == "airside"]
    geoms = [Polygon(c.ring, c.holes) for c in air_cells]
    geoms = [g if g.is_valid else g.buffer(0.0) for g in geoms]
    keep = [k for k, g in enumerate(geoms) if not g.is_empty]
    air_cells, geoms = [air_cells[k] for k in keep], [geoms[k] for k in keep]
    if not lines or not geoms:
        return out
    tree = STRtree(geoms)
    cfg = rules.edge_lines
    step, d = float(cfg.station_m), float(cfg.step_probe_m)

    def cell_at(p: Point):
        return next((air_cells[int(j)] for j in tree.query(p) if geoms[int(j)].covers(p)), None)

    def born_page(c) -> str | None:
        return None if c.evidence.get("airside_edge_flip") else page_of(c.ref)

    for fid, line in lines:
        marks, inner = [], []
        for k in range(int(line.length // step) + 1):
            s = min(line.length, k * step)
            a, b = (cell_at(p) for p in _probe(line, s, d))
            both = a is not None and b is not None
            same = both and born_page(a) is not None and born_page(a) == born_page(b)
            marks.append((s, both and not same))
            inner.append((s, same))
        runs = _runs(marks, float(cfg.min_run_m))
        out["fence_inside_airside_page"] += int(bool(_runs(inner, float(cfg.min_run_m))))
        if runs:
            out["fence_airside_both"] += 1
            out["fence_airside_both_m"] += round(sum(s1 - s0 for s0, s1 in runs), 1)
            p = line.interpolate(runs[0][0])
            out["fence_airside_both_sites"].append((fid, round(p.x, 1), round(p.y, 1)))
    return out
