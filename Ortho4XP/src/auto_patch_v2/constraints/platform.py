"""THE PLATFORM COLLAR — a §31 (7) bank from the welded rim to the platform
(unit-platform spec §1 (3), §3 P3; owner RULINGS 2026-09-28a (1); issues
#66 / #4 / #10).

A platform pad is two faces (``planar/platform.py``): the PLATFORM, which
the pad's plate prices (one plane, 1 %, levelled by its frontage fit —
``constraints.pads``), and the COLLAR (``<ref>#collar``), the annulus
between the pad rim and the platform.  This is the ONLY new row family:
every OUTER collar vertex (the pad rim, welded to the apron or not) takes
one ``Diff`` at ``emit.design.bank_slope`` (the 1:3 bank — a slope, never
a cliff) against each of its ``_K`` nearest PLATFORM vertices, and every
platform vertex against its nearest outer one, so the ground under the
building falls from the rim to the platform at most 1:3 in every
direction the triangulation can join them.

ONE-WAY, THE RIM LEADS (spec §1 (3); head in ``[design] one_way_rulings``):
where the outer vertex is AIRSIDE (a vertex of a runway / taxi / apron
face — ``pads.airside_vertices``) the platform vertex FOLLOWS — airside is
king and the collar never pulls it (its value is stage 1's anyway, §20b).
Where the outer vertex is the pad's OWN rim (groundside, or bare ground)
there is no relief to absorb: the row is at cap 0 and the OUTER vertex
follows — the rim stays on the platform, where the plate held it before
the collar existed, and the collar never tilts the plate.

Priced as the groundside terrace law prices a bank (``groundside_ramp_max``
's pattern): a one-sided design penalty at the law's weight, never a hard
row.  A collar carrying more relief than C x ``bank_slope`` shows as that
miss in its family's residual and as a ``cliff`` in the census, never as
an infeasible hard set."""
from __future__ import annotations

import math

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap, is_collar_ref, platform_ref_of

__all__ = ["platform_collar_rows", "platform_plane_rows", "COLLAR_RULING",
           "PLANE_RULING", "GEN", "collar_faces"]

GEN = "platform_collar"
#: The ruling HEAD (``solve.design.ruling_head``) — named by ``[design]
#: one_way_rulings``.
COLLAR_RULING = "structures.building_pad platform_collar bank"
#: How many platform vertices each outer collar vertex is tied to: the
#: triangulation joins a rim vertex to a fan of inner ones, and three is a
#: fan (a solver-conditioning constant, not a law value).
_K = 3
#: The statistics ``constraints.generate`` publishes beside the row count.
STATS: dict[str, dict[str, int]] = {}


def collar_faces(planar: PlanarMap, law: Law
                 ) -> list[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """``(platform ref, its COLLAR face ids, its PLATFORM face ids)`` per
    platform pad whose platform is in the map — ONE derivation (the rows
    here, the census's ``platform_rim_relief``).  A district pad's erosion
    leaves several platform pieces and the collar several faces; all of
    them carry the one ref."""
    from .pads import rigid_roles
    rigid = set(rigid_roles(law))
    plat: dict[str, list[int]] = {}
    col: dict[str, list[int]] = {}
    for fid in sorted(planar.faces):
        f = planar.faces[fid]
        if f.role not in rigid:
            continue
        if is_collar_ref(f.ref):
            col.setdefault(platform_ref_of(f.ref), []).append(fid)
        else:
            plat.setdefault(f.ref, []).append(fid)
    return [(r, tuple(cs), tuple(plat[r])) for r, cs in sorted(col.items())
            if r in plat]


def platform_collar_rows(planar: PlanarMap, law: Law,
                         airport: Airport | None = None) -> list[Row]:
    """The collar bank rows (module docstring).  A generator."""
    from scipy.spatial import cKDTree

    from .pads import airside_vertices
    from .precedence import view
    STATS.clear()
    pairs = collar_faces(planar, law)
    if not pairs:
        return []
    cap = float(law.tables.emit.design.bank_slope)
    if cap <= 0.0:
        return []
    vw = view(planar, law)
    air = airside_vertices(planar, law)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    n_air = n_own = 0
    for pref, cfids, pfids in pairs:
        inner = sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]]
                        for v in r})
        cvs = {v for q in cfids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        outer = sorted(cvs - set(inner))
        if len(inner) < 3 or not outer:
            continue
        src = Source(GEN, COLLAR_RULING + " (unit-platform spec §1 (3); "
                     "§31 (7) the 1:3 bank; RULINGS 2026-09-28a (1))",
                     (f"face:{cfids[0]}", pref + "#collar", f"platform:{pref}"))
        tree = cKDTree([xy[v] for v in inner])
        seen: set[tuple[int, int]] = set()

        def _row(o: int, i: int) -> None:
            nonlocal n_air, n_own
            key = (o, i)
            if key in seen or o == i:
                return
            d = math.hypot(xy[o][0] - xy[i][0], xy[o][1] - xy[i][1])
            if d <= 0.0:
                return
            seen.add(key)
            if o in air:
                n_air += 1
                rows.append(Diff(o, i, cap, d, src, follows=(i,)))
            else:
                # the pad's OWN rim carries no relief to absorb: it stays
                # on the platform (cap 0, the rim follows), exactly where
                # the plate put it before the collar existed
                n_own += 1
                rows.append(Diff(o, i, 0.0, d, src, follows=(o,)))

        k = min(_K, len(inner))
        for o in outer:
            _d, js = tree.query(xy[o], k=k)
            for j in ([js] if k == 1 else js):
                _row(o, inner[int(j)])
        otree = cKDTree([xy[v] for v in outer])
        for i in inner:
            _d, j = otree.query(xy[i])
            _row(outer[int(j)], i)
    STATS["platform_collar_rows"] = {"collars": len(pairs),
                                     "rows_rim_airside_leads": n_air,
                                     "rows_own_rim_follows": n_own}
    return rows


#: The ruling HEAD of the platform's PLANE rows — named by ``[design]
#: hard_rulings``: a platform is ONE plane (spec §1 (1)), a law, not a
#: weight contest.
PLANE_RULING = "structures.building_pad platform plane"


def _basis(xy: dict[int, tuple[float, float]], vs: list[int]
           ) -> "tuple[int, int, int] | None":
    """Three well-spread vertices of ``vs`` (the farthest from the centroid,
    the farthest from it, the farthest from their line) — the plane's three
    degrees of freedom.  ``None`` where ``vs`` is collinear."""
    cx = sum(xy[v][0] for v in vs) / len(vs)
    cy = sum(xy[v][1] for v in vs) / len(vs)
    a = max(vs, key=lambda v: (xy[v][0] - cx) ** 2 + (xy[v][1] - cy) ** 2)
    b = max(vs, key=lambda v: (xy[v][0] - xy[a][0]) ** 2 + (xy[v][1] - xy[a][1]) ** 2)
    ax, ay = xy[a]
    bx, by = xy[b]
    L = math.hypot(bx - ax, by - ay)
    if L <= 0.0:
        return None
    c = max(vs, key=lambda v: abs((bx - ax) * (xy[v][1] - ay) - (by - ay) * (xy[v][0] - ax)))
    h = abs((bx - ax) * (xy[c][1] - ay) - (by - ay) * (xy[c][0] - ax)) / L
    if h < 1.0:
        return None
    return a, b, c


def platform_plane_rows(planar: PlanarMap, law: Law,
                        airport: Airport | None = None) -> list[Row]:
    """THE PLATFORM IS ONE PLANE (unit-platform spec §1 (1); RULINGS
    2026-09-28a (1)): every platform vertex of a ref — ALL its pieces, a
    district pad's erosion leaves several — lies on the plane through three
    basis vertices of the platform, a HARD equality (``[design]
    hard_rulings``).  Like the 1 % ceiling it carries NO authored relief
    (RULINGS 2026-09-12u: a hard row stating the relief makes it a DEMAND on
    the surface — measured here too, 2,395 violated hard rows); §30 (6)'s
    relief stays in the plate's soft target.  The plate's own rows stay: the
    cap-0 flat target keeps the tilt at zero wherever it can be and the
    hard 1 % ceiling bounds it; the frontage fit sets the level; the
    collar's bank rows pull as a least-squares fit.

    WHY A HARD PLANE HERE (and not the plate's pairwise target alone).
    MEASURED on the HECA capture (lane ``unitplatform2``): with the plate
    alone the collar's ~1,800 bank rows at the law's weight bent T3's
    platform 8.3 m across its 14 pieces (one piece 93.7..99.8) — the
    pairwise 1 % ceiling allows 8 m over 800 m and the cap-0 pairs are a
    target.  10y refuted hard coplanarity for a pad WELDED to its frontage
    (the identity transmitted a basin wall's pull 100x harder than a level
    row); a platform shares no vertex with anything but its own collar, so
    what it transmits here is the collar's own least-squares fit — the
    level the spec asks for."""
    from .precedence import view
    pairs = collar_faces(planar, law)
    if not pairs:
        return []
    vw = view(planar, law)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    n_planes = 0
    for pref, _cfids, pfids in pairs:
        vs = sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]] for v in r})
        if len(vs) < 4:
            continue
        bs = _basis(xy, vs)
        if bs is None:
            continue
        a, b, c = bs
        (x1, y1), (x2, y2), (x3, y3) = xy[a], xy[b], xy[c]
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if det == 0.0:
            continue
        n_planes += 1
        src = Source(GEN, PLANE_RULING + " (unit-platform spec §1 (1); "
                     "RULINGS 2026-09-28a (1) one platform per unit)",
                     (f"face:{pfids[0]}", pref))
        for v in vs:
            if v in (a, b, c):
                continue
            x, y = xy[v]
            l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det
            l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det
            l3 = 1.0 - l1 - l2
            terms = ((v, 1.0), (a, -l1), (b, -l2), (c, -l3))
            rows.append(Linear(terms, None, 0.0, src))
            rows.append(Linear(tuple((q, -k) for q, k in terms), None, 0.0, src))
    STATS["platform_plane_rows"] = {"planes": n_planes, "rows": len(rows)}
    return rows
