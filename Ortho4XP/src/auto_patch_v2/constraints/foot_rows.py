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
* FEASIBILITY is read between NEIGHBOURING feet (11x (2)):
  ``|(target_a - target_b) - (dem_a - dem_b)|`` against ``bank_slope`` x
  their own spacing, over the feet's neighbour graph
  (``model/ground_fit.neighbour_pairs``).  Beyond it the body is
  INFEASIBLE — no rows, the low-side anchor of §9, and the residual
  REPORTED (HECA's ``road_train/metal_titles.obj b0`` is that class).
  Round 6's nearest-foot SCALAR is deleted: it bought 33 m of licence
  for feet 100 m apart and refused 0.17 m to feet half a metre apart.

NO PAD, NO RIM, NO CONSUMER (spec §11a (4) holds by construction): this
module publishes target rows and a report, and touches no pad polygon, no
pad level and no pad consumer.

**THE ROW IS A LAW-SHAPED ``Linear`` PRICED AS THE PAD.**  The rows reach
the solve the way every airport-derived target does — through the
``ConstraintSet`` — as a two-sided ``Linear`` (``lo = hi = target``) whose
ruling HEAD is registered in ``[design] foot_row_rulings``, so
``solve/design`` prices it at ``pad_flat`` (3000) instead of ``law``
(300).  A foot row IS the PAD law's target for a body with no pad
polygon (owner RULINGS 2026-09-11ab): at ``ground_datum`` (3.0) — the
ADJACENT GROUND's datum price — the body's own placement was the
cheapest row in the sheet, and round 7 missed 715 of 1,434 rows, worst
5.70 m.  One register, no literals: the same shape as ``hard_rulings`` /
``one_way_rulings`` / ``pad_flat_rulings``, and kept DISTINCT from the
latter so the report counts foot rows and pad planes apart.

**THE ROW IS THE SURFACE AT THE FOOT, not at a vertex.**  A foot stands
inside a face, and what the object will read there is the emitted sheet
interpolated over that face's triangle — so the row carries the
triangle's three vertices at their BARYCENTRIC weights.

**ALL OR NOTHING, PER BODY (owner RULINGS 2026-09-11x (1)).**  A body's
rows fire only when EVERY one of its feet stands on a face of the design
sheet and the fit is feasible; otherwise NONE of them do and the body is
reported ``off_sheet`` or ``infeasible``.  A PARTIAL profile — some feet
pulled to the fit, the rest left on the raw DEM — is round 5's flat-pad
STEP in new clothes: it tilts the body against its own authoring.  Off
the sheet the law is the raw DEM and the SPLIT adapts the object to it
(§9/§13/§14, 09af-1), which is a whole answer; half a profile is not.

A body one of whose feet the DEM does not sample is ``no_dem`` for the
same reason: the fit would then be over a subset and the rows a partial
profile.

**PAVEMENT IS SENIOR** (09af-1, §11b (1)): a body with a foot on apron or
taxiway takes no rows at all — the pavement law owns that surface, the
object goes to the terrain, and the body is reported with its role and
residual rather than graded to.

**A FOOT ON A STRUCTURE CUT STATES NO GROUND ROW** (owner RULINGS
2026-09-13bs, spec §11b (7)): a foot whose surface sample lands on a
STRUCTURE face — ``tunnel_ramp``, ``tunnel_trench`` (a basin floor is
one), ``wall_corridor_ramp``, ``door_ramp``, ``garage_ramp``,
``retaining_wall``, the bridge cuts — stands on a surface §33 / §34
STATE, not on ground.  The body takes a ``cut`` verdict, is counted and
reported, and emits NO ``Linear``: the object RIDES the cut, exactly as
§16a rules for a carried body ("cut where its carrier is cut") and
§16c (3) for a foot over a structure cut.  The self-referential case is
the one that minted the defect: OTHH's ``tunnel south west 2#b0`` was
re-seated to the ground (3.962) and its eight foot rows then demanded
that the ramp ITS OWN WALLS CUT stand at that ground every few metres —
the ramp sagged +3.31 m off its design line between the nails, 12 of 21
monotone rows violated, and the whole design solve fell from OPTIMAL to
``feasible`` with two hard rows violated.  An object standing at a
trench EDGE keeps its crest plate (§16e (1)) and rides the cut with its
feet.  The role set is ONE list — ``law.tables.is_structure_role``
(``precedence.toml`` ``structure = true``), the same register
``pavement_roles`` subtracts — never a literal tuple here.

**A BASIN BODY IS §14's** (owner RULINGS 2026-09-11x (3)): a body
authored BELOW its own zero standing inside an emitted basin rim is the
PIT, not something on the ground, and the basin law owns its level.  It
is counted (``basin``) and takes no foot row.  Round 6's worst body at
the owner's site (``OldTerminal_FSX-LEMD84`` b3, +7.88 m) was one of
these — a foot row was pulling the terrain towards a trench floor.

Reads the planar map, the law, ``Airport.groups`` and ``Airport.dem``.
No mesh, no environment, no pack.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..geom import face_triangles
from ..law import Law
from ..law.tables import is_value_role, role_side
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.ground_fit import GroundFit, ground_fit
from ..model.planar import PlanarMap
from .structures import WALL_ROLE

#: the ref prefix ``planar/basins`` mints for a pit's void face — with
#: :data:`.structures.WALL_ROLE` the pair that says "this ring is a
#: basin's rim" (11x (3))
BASIN_WALL_REF = "basin_wall:"

#: this module's generator name and the ruling its rows carry — the HEAD
#: ``[design] foot_row_rulings`` prices at ``pad_flat`` (11ab)
GEN = "foot_rows"
RULING = "structures.placement foot_row (RULINGS 2026-09-11q, spec §11b)"
#: §34 (13) (3) (a) AN OBJECT'S FOOT NEVER HOLDS AIRSIDE PAVEMENT (Fable
#: 2026-09-15; RULINGS 2026-09-15ad; owner 15e item 7).  A foot row is
#: stated over the TRIANGLE the foot stands in, and a triangle on the
#: adjacent ground reaches the pavement's own kerb columns — one node,
#: one value (09-01g), so the graded strip SHARES its kerb vertices with
#: the junction it borders.  At LEMD ``pav157``'s far edge v6622 that put
#: **14 binding rows, sum |dual| 42,656** — the heaviest family on the
#: vertex, an order of magnitude over everything else — from TWO 2.23 m
#: bodies of ONE pack placement (``LEMD_OBJ-Airport_Munoza-LEMD69`` b2
#: and b4, 4 feet each, relief 0.001 m, y_zero −1.198 / −1.200: the
#: taxiway's own edge furniture) onto the junction's crossfall.
#:
#: RULED: such a row is ONE-WAY toward the object.  The foot FOLLOWS the
#: pavement — airside is king — and the object stage re-seats the body on
#: the solved design surface afterwards anyway, so nothing is lost by
#: letting the pavement move first.  The row keeps its bare-ground
#: columns as followers and treats the airside ones as GIVEN.  The head
#: is registered in ``[design] one_way_rulings``; ``follows`` is set only
#: on the rows that touch airside pavement, so every other foot row is
#: two-sided exactly as §11b states it.

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
    every feasible bare-ground body, priced at ``pad_flat`` (11ab)."""
    targets, verdicts, counts = foot_targets(planar, law, airport)
    STATS["foot_rows"] = dict(counts)
    VERDICTS[:] = verdicts
    # §34 (13) (3) (a): the AIRSIDE PAVEMENT columns — a value role on the
    # airside (runway / taxi / apron families).  The graded strip is
    # airside but is NOT a value role: it traces a lawful bound and owns
    # no level, so a foot row over it stays two-sided.
    # EVERY AIRSIDE VALUE ROLE, the runway family included — the ruling's
    # own words, and the narrowing was MEASURED AND REJECTED.  Excluding
    # the runway family (taxi + apron only) halves the runway movement
    # (394 → 196 vertices, 5.086 → 3.277 m) but does NOT reach the bar of
    # zero, and it LOSES the law: the owner's raw pair reads **2.585 %**
    # against the 1.985 % junction cap instead of **1.160 %**.  It gives
    # up the fix without buying the bar, so the scope stays as ruled and
    # the runway movement is reported as the price.
    airside = {v for v, vx in planar.vertices.items()
               if any(is_value_role(law, planar.faces[f].role)
                      and role_side(law, planar.faces[f].role) == "airside"
                      for f in vx.incident_faces if f in planar.faces)}
    n_one_way = 0
    out: list[Row] = []
    for t in targets:
        # TWO ONE-SIDED ROWS, never a ``lo == hi`` Linear: ``solve/rows.
        # _law_sides`` reads an equal-bounds row as the LAW'S OWN
        # equality, and a foot row is a DATUM (``constraints/pads.
        # _two_sided``, the same reasoning at the pad's weight).
        src = Source(GEN, RULING, (t.gid,))
        # §34 (13) (3) (a): a foot row touching AIRSIDE PAVEMENT governs
        # only its bare-ground columns; the pavement's are GIVEN.
        fv = None
        if any(v in airside for v, _c in t.terms):
            free = tuple(v for v, _c in t.terms if v not in airside)
            # ALL-OR-NOTHING PER BODY STILL HOLDS (owner RULINGS
            # 2026-09-11x (1)): a triangle EVERY corner of which is
            # pavement has nothing left to follow, so its row stays
            # two-sided rather than vanishing — dropping it would fire
            # some of a body's feet and not others, which §11b forbids.
            if free:
                fv = free
                n_one_way += 1
        out.append(Linear(t.terms, None, t.z, src, follows=fv))
        out.append(Linear(tuple((v, -c) for v, c in t.terms), None, -t.z, src,
                          follows=fv))
    STATS["foot_rows"] = {**STATS.get("foot_rows", {}),
                          "one_way_at_airside": n_one_way}
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
    #: ``bare`` (rows fired — EVERY foot), ``off_sheet`` (a foot stands
    #: on no face of the sheet), ``infeasible``, ``basin`` (§14's, 11x
    #: (3)), ``cut`` (a foot on a STRUCTURE-CUT face — §11b (7), 13bs),
    #: ``pavement``, ``padded``, ``no_dem`` (a foot the DEM does
    #: not sample)
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
    #: the feet of this body that stood on no face of the design sheet —
    #: ``off_sheet``'s own number, 0 for every body that fired
    feet_off_sheet: int = 0


def foot_targets(planar: PlanarMap, law: Law, airport: Airport
                 ) -> tuple[list[FootTarget], list[BodyVerdict], dict[str, int]]:
    """``(rows, verdicts, counters)`` — the module doc.  Empty where no
    pack was read, where the law is disarmed (``bank_slope`` 0) or where
    the airport carries no DEM sampler."""
    groups = getattr(airport, "groups", None)
    dem = getattr(airport, "dem", None)
    counts = {"bodies": 0, "bare": 0, "off_sheet": 0, "infeasible": 0,
              "basin": 0, "cut": 0, "cut_feet": 0, "pavement": 0,
              "padded": 0, "no_dem": 0,
              "rows": 0, "feet_off_sheet": 0, "partial": 0}
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
        if index.basin_body(g.feet, pts):
            # §14 OWNS THE PIT (11x (3)): a body authored below its own
            # zero inside an emitted basin rim is the basin's, and its
            # level is the basin's floor law — never a ground target
            verdicts.append(_verdict(g, "basin", roles, None, 0))
            counts["basin"] += 1
            continue
        if "cut" in kinds:
            # §11b (7) (RULINGS 2026-09-13bs): a foot on a STRUCTURE-CUT
            # face stands on a surface §33 / §34 state.  The object rides
            # it (§16a / §16c (3)); it does not ask the cut to stand at
            # the ground it was cut out of.
            verdicts.append(_verdict(g, "cut", roles, None, 0))
            counts["cut"] += 1
            counts["cut_feet"] += len(g.feet)
            continue
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
        if fit is None or len(fit.keep) != len(g.feet):
            # ALL OR NOTHING (11x (1)): a fit over a SUBSET of the feet
            # would mint a partial profile exactly as an off-sheet foot
            # would
            verdicts.append(_verdict(g, "no_dem", roles, None, 0))
            counts["no_dem"] += 1
            continue
        # THE SHEET FIRST, THE FIT SECOND — so ``off_sheet`` is a
        # COMPLETE count of the bodies the sheet does not reach, and
        # ``infeasible`` is read over the bodies it does
        terms = [index.terms_at(p) for p in pts]
        missing = sum(1 for t in terms if t is None)
        if missing:
            counts["feet_off_sheet"] += missing
            counts["off_sheet"] += 1
            verdicts.append(_verdict(g, "off_sheet", roles, fit, 0,
                                     off_sheet=missing))
            continue
        if not fit.feasible:
            # §11b (3): the terrain cannot carry this body's relief
            # between two of its feet and stay a bank.  No rows, the
            # low-side anchor of §9, REPORTED.
            verdicts.append(_verdict(g, "infeasible", roles, fit, 0))
            counts["infeasible"] += 1
            continue
        for j, i in enumerate(fit.keep):
            t = terms[i]
            assert t is not None                 # checked above, per body
            rows.append(FootTarget(g.gid, t, fit.targets[j], fit.dem[j],
                                   roles[i] or ""))
        fired = len(fit.keep)
        counts["rows"] += fired
        counts["bare"] += 1
        counts["partial"] += int(fired != len(g.feet))   # 0 by construction
        verdicts.append(_verdict(g, "bare", roles, fit, fired))
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
             fit: GroundFit | None, fired: int, *,
             off_sheet: int = 0) -> BodyVerdict:
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
        anchor_lat=lo_lat, anchor_lon=lo_lon, anchor_residual_m=lo_res,
        feet_off_sheet=off_sheet)


class _FaceIndex:
    """Point -> (face role, the triangle's barycentric row).  ONE
    STRtree over the map's face polygons; each face is triangulated on
    first use (``model/planar.face_triangles``)."""

    def __init__(self, planar: PlanarMap, law: Law) -> None:
        from .pads import rigid_roles
        from ..law.tables import is_structure_role, pavement_roles
        self.pm = planar
        self._rigid = frozenset(rigid_roles(law))
        self._pav = frozenset(pavement_roles(law)) - self._rigid
        # §11b (7): the STRUCTURE-CUT roles, taken from the ONE register
        # ``precedence.toml`` states them in (``structure = true``) — the
        # same one ``pavement_roles`` subtracts, never a literal tuple
        self._cut = frozenset(r for r in law.tables.precedence.roles
                              if is_structure_role(law, r))
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
        # THE BASIN RIMS (11x (3)): the EXTERIOR ring of every emitted
        # basin void face — the same ring ``emit/graded`` publishes as
        # the ``structure_rim`` breakline that ``airport/placement_plan.
        # _rim_of`` reads when it classes a body ``basin``, read here
        # pre-emit off the map it is minted from.  Holes are DROPPED on
        # purpose: the floor faces inside the void are the pit too.
        self._rims: list[Polygon] = []
        for f in vw.faces_of_role((WALL_ROLE,)):
            if not str(f.ref).startswith(BASIN_WALL_REF):
                continue                 # a tunnel / corridor wall, not a pit
            ring = vw.rings[f.id]
            if len(ring) < 3:
                continue
            poly = Polygon([vw.xy[v] for v in ring])
            if not poly.is_valid:
                poly = poly.buffer(0.0)
            if isinstance(poly, Polygon) and not poly.is_empty:
                self._rims.append(poly)
        self._rim_tree = STRtree(self._rims) if self._rims else None

    def basin_body(self, feet, pts) -> bool:
        """§14's class (11x (3)), read the way ``airport/placement_plan.
        _rim_of`` reads it: a foot authored BELOW the object's own zero
        standing inside an emitted basin rim.  Containment alone is NOT
        the test — a terminal whose ground floor sits over a cut pit is
        not the pit (the LEMD ``Terminal4sBlue-LEMD35`` precedent)."""
        if self._rim_tree is None:
            return False
        for f, p in zip(feet, pts):
            if float(f.y) >= 0.0:
                continue
            pt = Point(p)
            for j in self._rim_tree.query(pt):
                if self._rims[int(j)].covers(pt):
                    return True
        return False

    def kind(self, role: str | None) -> str:
        if role is None:
            return "none"
        if role in self._cut:
            # §11b (7): a STRUCTURE face — the cut is stated by §33 / §34
            # and the object rides it (RULINGS 2026-09-13bs)
            return "cut"
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
            # THE ONE TRIANGULATION (11x (4)): ``geom`` is the leaf both
            # this layer and ``solve/rows`` may import — no copy here.
            tris = face_triangles(self._vw.xy, self._vw.rings[fid],
                                  self._vw.holes[fid])
            self._tris[fid] = tris
        xy = self.pm.vertices
        for a, b, c in tris:
            w = _bary(p, xy[a].xy, xy[b].xy, xy[c].xy)
            if w is None:
                continue
            return ((a, w[0]), (b, w[1]), (c, w[2]))
        return None


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
