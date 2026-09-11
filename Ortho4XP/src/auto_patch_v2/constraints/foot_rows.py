"""THE FOOT ROWS — a body on BARE GROUND goes to the terrain, and the
terrain takes its feet (owner RULINGS 2026-09-11q; spec
``object-placement-spec.md`` §11b).

Round 5 minted a flat PAD from each bare-ground body's own plan footprint
and measured it WORSE at the owner's own site: a rigid plane cut into
sloping ground steps wherever an unpadded neighbour straddles its edge
(LEMD's three rows' worst body 1.94 -> 3.33 m, ``pad_flat`` verify rows
39 -> 98, HECA's released T3 bodies +1.5 -> +8.7 m).  The colonnade's
columns carry 2.63 m of authored relief BECAUSE the real ground slopes
there; a flat pad fights the authoring.

So a body whose anchor stands on no graded face, whose feet touch no OSM
building pad and no pavement, gets NO PAD ENTITY at all.  Instead:

* its LEVEL is the least-squares fit of ``dem(foot) - (y_foot - y_zero)``
  over its ground-contact feet (``model/ground_fit.ground_fit``, the ONE
  expression — :func:`derive` prices the same fit for
  ``Group.infeasible``);
* each foot gets ONE target row ``z(foot) = level + (y_foot - y_zero)``,
  priced at ``[design] ground_datum`` — a GROUND target, not ``pad_flat``
  and not ``law``.  The sheet blends between the feet as it does
  everywhere on adjacent ground, a neighbour's feet carry their own rows,
  and there is no pad edge to straddle;
* FEASIBILITY is the fit's own residual: ``max |dem(foot) -
  target(foot)|`` against ``bank_slope`` x the distance to the nearest
  other foot.  Beyond it the body is INFEASIBLE — no rows, the low-side
  anchor of §9, and the residual REPORTED (HECA's
  ``road_train/metal_titles.obj b0`` is that class).

NO PAD, NO RIM, NO CONSUMER (spec §11a (4) holds by construction): this
module publishes target rows and a report, and touches no pad polygon, no
pad level and no pad consumer.

**THE ROW IS A LAW-SHAPED ``Linear`` PRICED AS A DATUM.**  The rows reach
the solve the way every airport-derived target does — through the
``ConstraintSet`` — as a two-sided ``Linear`` (``lo = hi = target``) whose
ruling HEAD is registered in ``[design] ground_datum_rulings``, so
``solve/design`` prices it at ``ground_datum`` (3.0) instead of ``law``
(300).  One register, no literals: the same shape as ``hard_rulings`` /
``one_way_rulings`` / ``pad_flat_rulings``.

**THE ROW IS THE SURFACE AT THE FOOT, not at a vertex.**  A foot stands
inside a face, and what the object will read there is the emitted sheet
interpolated over that face's triangle — so the row carries the
triangle's three vertices at their BARYCENTRIC weights.  A foot inside
no face of the design sheet gets
NO row and is reported (``feet_off_sheet``): there is nothing there to
constrain, and the DEM is what the object will stand on.

**PAVEMENT IS SENIOR** (09af-1, §11b (1)): a body with a foot on apron or
taxiway takes no rows at all — the pavement law owns that surface, the
object goes to the terrain, and the body is reported with its role and
residual rather than graded to.

Reads the planar map, the law, ``Airport.groups`` and ``Airport.dem``.
No mesh, no environment, no pack.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import MultiPoint, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.ground_fit import GroundFit, ground_fit
from ..model.planar import PlanarMap

#: this module's generator name and the ruling its rows carry — the HEAD
#: ``[design] ground_datum_rulings`` prices at ``ground_datum``
GEN = "foot_rows"
RULING = "structures.placement foot_row (RULINGS 2026-09-11q, spec §11b)"

#: the generator's own statistics, published beside its row count by
#: ``constraints.generate`` as ``foot_rows.<stat>``
STATS: dict[str, dict[str, int]] = {}

#: the last reading's per-body verdicts, for the report and the twins —
#: a diagnostic, never read by a row
VERDICTS: list["BodyVerdict"] = []

__all__ = ["FootTarget", "BodyVerdict", "foot_targets", "foot_rows", "GEN",
           "RULING", "STATS", "VERDICTS"]


def foot_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE GENERATOR (module doc): one two-sided ``Linear`` per foot of
    every feasible bare-ground body, priced at ``ground_datum``."""
    targets, verdicts, counts = foot_targets(planar, law, airport)
    STATS["foot_rows"] = dict(counts)
    VERDICTS[:] = verdicts
    out: list[Row] = []
    for t in targets:
        # TWO ONE-SIDED ROWS, never a ``lo == hi`` Linear: ``solve/rows.
        # _law_sides`` reads an equal-bounds row as the LAW'S OWN
        # equality, and a foot row is a DATUM (``constraints/pads.
        # _two_sided``, the same reasoning at the pad's weight).
        src = Source(GEN, RULING, (t.gid,))
        out.append(Linear(t.terms, None, t.z, src))
        out.append(Linear(tuple((v, -c) for v, c in t.terms), None, -t.z, src))
    return out


@_dc.dataclass(frozen=True)
class FootTarget:
    """ONE foot's target row: ``Σ c·z = z_target`` over the vertices of
    the triangle the foot stands in, priced at ``[design] ground_datum``
    by ``solve/design.assemble``."""

    gid: str
    terms: tuple[tuple[int, float], ...]
    z: float
    #: the DEM under the foot and the metres the row asks the terrain to
    #: move — the report's numbers, never used in the row itself
    dem_z: float
    role: str


@_dc.dataclass(frozen=True)
class BodyVerdict:
    """One group's reading — every body is reported, rows or not."""

    gid: str
    #: ``bare`` (rows fired), ``infeasible``, ``pavement``, ``padded``,
    #: ``no_dem``, ``off_sheet`` (bare, feasible, but no foot in a face)
    verdict: str
    feet: int
    rows: int
    level: float | None
    residual_m: float
    limit_m: float
    relief_m: float
    #: the roles the feet stand on, most common first
    roles: tuple[str, ...]
    #: the ANCHOR foot (§11b (4)): the foot whose target is lowest — the
    #: low-side foot, the one the split writer anchors the body at — and
    #: the metres the DEM there stands from its target
    anchor_lat: float = 0.0
    anchor_lon: float = 0.0
    anchor_residual_m: float = 0.0


def foot_targets(planar: PlanarMap, law: Law, airport: Airport
                 ) -> tuple[list[FootTarget], list[BodyVerdict], dict[str, int]]:
    """``(rows, verdicts, counters)`` — the module doc.  Empty where no
    pack was read, where the law is disarmed (``bank_slope`` 0) or where
    the airport carries no DEM sampler."""
    groups = getattr(airport, "groups", None)
    dem = getattr(airport, "dem", None)
    counts = {"bodies": 0, "bare": 0, "infeasible": 0, "pavement": 0,
              "padded": 0, "no_dem": 0, "rows": 0, "feet_off_sheet": 0}
    if groups is None or not getattr(groups, "groups", ()) or dem is None:
        return [], [], counts
    bank = float(law.tables.emit.design.bank_slope)
    if bank <= 0.0:
        return [], [], counts

    to_xy, _to_ll = airport.frame.transformers()
    index = _FaceIndex(planar, law)

    rows: list[FootTarget] = []
    verdicts: list[BodyVerdict] = []
    for g in groups.groups:
        if not g.feet:
            continue
        counts["bodies"] += 1
        pts = [to_xy(f.lon, f.lat) for f in g.feet]
        roles = [index.role_at(p) for p in pts]
        kinds = {index.kind(r) for r in roles}
        if "pavement" in kinds:
            verdicts.append(_verdict(g, "pavement", roles, None, 0))
            counts["pavement"] += 1
            continue
        if "rigid" in kinds:
            # the body stands on an OSM pad: the PAD law owns it, with
            # the relief offsets of §11a (2) (``constraints/pad_relief``)
            verdicts.append(_verdict(g, "padded", roles, None, 0))
            counts["padded"] += 1
            continue
        fit = ground_fit(g.feet, g.y_zero, _sampler(dem, to_xy), bank)
        if fit is None:
            verdicts.append(_verdict(g, "no_dem", roles, None, 0))
            counts["no_dem"] += 1
            continue
        if not fit.feasible:
            # §11b (3): the terrain cannot carry this body's relief and
            # stay a bank.  No rows, the low-side anchor of §9, REPORTED.
            verdicts.append(_verdict(g, "infeasible", roles, fit, 0))
            counts["infeasible"] += 1
            continue
        fired = 0
        for j, i in enumerate(fit.keep):
            terms = index.terms_at(pts[i])
            if terms is None:
                counts["feet_off_sheet"] += 1
                continue
            rows.append(FootTarget(g.gid, terms, fit.targets[j], fit.dem[j],
                                   roles[i] or ""))
            fired += 1
        counts["rows"] += fired
        counts["bare"] += 1
        verdicts.append(_verdict(g, "bare" if fired else "off_sheet",
                                 roles, fit, fired))
    return rows, verdicts, counts


def _sampler(dem, to_xy) -> _t.Callable[[float, float], float | None]:
    def at(lat: float, lon: float) -> float | None:
        x, y = to_xy(lon, lat)
        try:
            z = dem.z(x, y)
        except Exception:
            return None
        if z is None:
            return None
        z = float(z)
        return None if z != z else z
    return at


def _verdict(g, kind: str, roles: list[str | None],
             fit: GroundFit | None, fired: int) -> BodyVerdict:
    order: dict[str, int] = {}
    for r in roles:
        order[r or "<none>"] = order.get(r or "<none>", 0) + 1
    lo_lat = lo_lon = 0.0
    lo_res = 0.0
    if fit is not None and fit.targets:
        j = min(range(len(fit.targets)), key=lambda i: fit.targets[i])
        # ``targets`` is over the feet that carried a DEM sample
        # (``fit.keep``); the anchor is the LOWEST of them (§11b (4))
        lo_lat, lo_lon = g.feet[fit.keep[j]].lat, g.feet[fit.keep[j]].lon
        lo_res = float(fit.dem[j] - fit.targets[j])
    return BodyVerdict(
        gid=g.gid, verdict=kind, feet=len(g.feet), rows=fired,
        level=None if fit is None else fit.level,
        residual_m=0.0 if fit is None else fit.residual_m,
        limit_m=0.0 if fit is None else fit.limit_m,
        relief_m=g.relief_m,
        roles=tuple(k for k, _n in sorted(order.items(), key=lambda kv: -kv[1])),
        anchor_lat=lo_lat, anchor_lon=lo_lon, anchor_residual_m=lo_res)


class _FaceIndex:
    """Point -> (face role, the triangle's barycentric row).  ONE
    STRtree over the map's face polygons; each face is triangulated on
    first use (``model/planar.face_triangles``)."""

    def __init__(self, planar: PlanarMap, law: Law) -> None:
        from .pads import rigid_roles
        from ..law.tables import pavement_roles
        self.pm = planar
        self._rigid = frozenset(rigid_roles(law))
        self._pav = frozenset(pavement_roles(law)) - self._rigid
        from .precedence import view
        vw = view(planar, law)
        polys: list[Polygon] = []
        fids: list[int] = []
        for fid, f in planar.faces.items():
            ring = vw.rings[fid]
            if len(ring) < 3:
                continue
            poly = Polygon([vw.xy[v] for v in ring],
                           [[vw.xy[v] for v in h] for h in vw.holes[fid]
                            if len(h) >= 3])
            if not poly.is_valid:
                poly = poly.buffer(0.0)
            if poly.is_empty or not isinstance(poly, Polygon):
                continue
            polys.append(poly)
            fids.append(fid)
        self._polys = polys
        self._fids = fids
        self._at = {fid: i for i, fid in enumerate(fids)}
        self._vw = vw
        self._tree = STRtree(polys) if polys else None
        self._tris: dict[int, list[tuple[int, int, int]]] = {}

    def kind(self, role: str | None) -> str:
        if role is None:
            return "none"
        if role in self._rigid:
            return "rigid"
        return "pavement" if role in self._pav else "ground"

    def _face_at(self, p: tuple[float, float]) -> int | None:
        if self._tree is None:
            return None
        pt = Point(p)
        for j in self._tree.query(pt):
            if self._polys[int(j)].covers(pt):
                return self._fids[int(j)]
        return None

    def role_at(self, p: tuple[float, float]) -> str | None:
        fid = self._face_at(p)
        return None if fid is None else self.pm.faces[fid].role

    def terms_at(self, p: tuple[float, float]
                 ) -> tuple[tuple[int, float], ...] | None:
        """The barycentric row of the triangle ``p`` falls in, or
        ``None`` (outside every face, or a face that does not
        triangulate)."""
        fid = self._face_at(p)
        if fid is None:
            return None
        tris = self._tris.get(fid)
        if tris is None:
            tris = _triangles(self._vw, fid, self._polys[self._at[fid]])
            self._tris[fid] = tris
        xy = self.pm.vertices
        for a, b, c in tris:
            w = _bary(p, xy[a].xy, xy[b].xy, xy[c].xy)
            if w is None:
                continue
            return ((a, w[0]), (b, w[1]), (c, w[2]))
        return None


def _triangles(vw, fid: int, poly: Polygon) -> list[tuple[int, int, int]]:
    """A triangulation of one face — its ring and hole vertices'
    Delaunay, keeping the triangles whose centroid lies inside the face
    (a concave face and a face with holes triangulate correctly).

    DEVIATION, REPORTED (round 6): this is the same SHAPE as
    ``solve/rows._face_triangles`` and cannot share code with it — the
    layering law (``tests/auto_patch_v2/test_model.test_dependency_
    direction``) lets ``constraints`` import only ``law`` and ``model``,
    ``solve`` only ``law`` and ``model``, and ``model`` may import
    neither ``shapely`` nor ``numpy``.  The two are answers to different
    questions (the solver's is the domain it integrates curvature over;
    this one is "where in the face is this point"), so they are not
    required to agree — but a shared home for them is the owner's call,
    not the lane's."""
    import shapely
    ring = vw.rings[fid]
    ids = list(dict.fromkeys([*ring, *(v for h in vw.holes[fid] for v in h)]))
    if len(ids) < 3:
        return []
    xy = {v: vw.xy[v] for v in ids}
    of_pt = {(round(x, 6), round(y, 6)): v for v, (x, y) in xy.items()}
    try:
        tri = shapely.delaunay_triangles(
            MultiPoint([xy[v] for v in ids]), only_edges=False)
    except Exception:
        return []
    out: list[tuple[int, int, int]] = []
    for g in shapely.get_parts(tri):
        if not poly.contains(g.representative_point()):
            continue
        vs = [of_pt.get((round(x, 6), round(y, 6)))
              for x, y in list(g.exterior.coords)[:3]]
        if all(v is not None for v in vs):
            out.append((vs[0], vs[1], vs[2]))
    return out


#: a point this far outside a triangle in barycentric units still counts
#: as inside it — a numeric tolerance on the walk, not a law value
_BARY_EPS = 1e-9


def _bary(p: tuple[float, float], a: tuple[float, float],
          b: tuple[float, float], c: tuple[float, float]
          ) -> tuple[float, float, float] | None:
    """``p``'s barycentric weights in triangle ``abc``, or ``None`` when
    ``p`` lies outside it (or the triangle is degenerate)."""
    v0x, v0y = b[0] - a[0], b[1] - a[1]
    v1x, v1y = c[0] - a[0], c[1] - a[1]
    den = v0x * v1y - v1x * v0y
    if den == 0.0:
        return None
    px, py = p[0] - a[0], p[1] - a[1]
    wb = (px * v1y - v1x * py) / den
    wc = (v0x * py - px * v0y) / den
    wa = 1.0 - wb - wc
    if wa < -_BARY_EPS or wb < -_BARY_EPS or wc < -_BARY_EPS:
        return None
    return (wa, wb, wc)


def targets_report(rows: _t.Sequence[FootTarget],
                   verdicts: _t.Sequence[BodyVerdict],
                   counts: _t.Mapping[str, int]) -> dict[str, float]:
    """The one line a build prints."""
    out = {k: float(v) for k, v in counts.items()}
    if rows:
        moved = [abs(r.z - r.dem_z) for r in rows]
        out["move_max_m"] = round(max(moved), 3)
        out["move_mean_m"] = round(sum(moved) / len(moved), 3)
    inf = [v for v in verdicts if v.verdict == "infeasible"]
    if inf:
        out["infeasible_worst_m"] = round(max(v.residual_m for v in inf), 3)
    return out
