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
there is no relief to absorb: the row is at cap 0, TWO-SIDED and priced at
the plate's own weight (``pad_flat_rulings``) — the rim stays on the
platform, where the plate held it before the collar existed.

Priced as the groundside terrace law prices a bank (``groundside_ramp_max``
's pattern): a one-sided design penalty at the law's weight, never a hard
row.  A collar carrying more relief than C x ``bank_slope`` shows as that
miss in its family's residual and as a ``cliff`` in the census, never as
an infeasible hard set."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap, is_collar_ref, platform_ref_of, unit_ref_of
from ..model.platform import HELD, datum_vertex_of

__all__ = ["platform_collar_rows", "platform_plane_rows", "frontage_hold_rows",
           "TERRACE_RULING", "HOLD_RULING",
           "platform_level_rows", "platform_contacts", "COLLAR_RULING",
           "PLANE_RULING", "GEN", "collar_faces", "platform_records"]

GEN = "platform_collar"
#: The ruling HEAD (``solve.design.ruling_head``) — named by ``[design]
#: one_way_rulings``.
COLLAR_RULING = "structures.building_pad platform_collar bank"
#: The head of the OWN-rim rows (cap 0, two-sided) — named by
#: ``pad_flat_rulings``: the pad's own rim stays on its plate at the
#: plate's price, as it did before the collar
RIM_RULING = "structures.building_pad platform_collar rim"
#: The head of the BLOCK TERRACE rows (flat-pad spec §2 (5), RULINGS
#: 2026-09-30r): the strip between two flat blocks of one unit, a two-sided
#: 1:3 bank from each floor — priced at the law's weight like the collar
TERRACE_RULING = "structures.building_pad platform_collar terrace"
#: The head of the FRONTAGE HOLD rows (flat-pad spec §1 (2); RULINGS
#: 2026-09-30f / 30r): a held block's welded contact at the block's datum
HOLD_RULING = "structures.building_pad frontage_hold"
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
    n_air = n_own = n_terr = 0
    # the COVERAGE EDGE: a vertex of an edge with no face on one side
    edge_v = {v for e in planar.edges.values()
              if e.left_face is None or e.right_face is None for v in (e.a, e.b)}
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
        src_rim = Source(GEN, RIM_RULING + " (unit-platform spec §1 (3); "
                         "the pad's own rim on its plate)",
                         (f"face:{cfids[0]}", pref + "#collar", f"platform:{pref}"))
        src_terr = Source(GEN, TERRACE_RULING + " (flat-pad spec §2 (5); RULINGS "
                          "2026-09-30r: the pad|pad terrace between two flat "
                          "blocks is a 1:3 bank)",
                          (f"face:{cfids[0]}", pref + "#collar", f"platform:{pref}"))
        terrace: set[int] = set()
        tree = cKDTree([xy[v] for v in inner])
        seen: set[tuple[int, int]] = set()

        def _row(o: int, i: int) -> None:
            nonlocal n_air, n_own, n_terr
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
            elif o in terrace:
                n_terr += 1
                rows.append(Diff(o, i, cap, d, src_terr))
            else:
                # the pad's OWN rim carries no relief to absorb: it stays
                # on the platform (cap 0, the rim follows), exactly where
                # the plate put it before the collar existed
                n_own += 1
                # TWO-SIDED, as the plate priced it (a one-way row lags its
                # leader: MEASURED on the islands twin, a courtyard hole ring
                # stayed 0.26 m on the platform's round-0 value)
                rows.append(Diff(o, i, 0.0, d, src_rim))

        # WHAT AN OUTER VERTEX IS NOT THE COLLAR'S TO GRADE (measured on the
        # HECA replay, lane ``unitplatform2``: 3,528 cap-0 rows missed by up
        # to 16.2 m):
        # * a vertex on the COVERAGE EDGE — a courtyard HOLE of the pad no
        #   region claims, where the DEM governs (a fixed vertex: its
        #   "follower" row turns two-way and drags the PLATFORM to the
        #   courtyard's DEM, which is how the plate bent);
        # * a vertex shared with ANOTHER pad — two pads may sit at different
        #   floors (``step_exemption_pad_to_pad``); T2's ``building281``
        #   abuts ``building68`` 16.4 m higher, and a cap-0 row there is a
        #   contest the plane loses.
        # NEITHER exemption covers a WELDED CONTACT (an airside vertex;
        # issue #95): its value is stage 1's — not the DEM's, not another
        # pad's floor — and its row is ONE-WAY (the platform follows), no
        # cap-0 contest; every contact is the collar's leader (spec §1 (3),
        # RULINGS 2026-09-29m (a) / 29o).  Measured: the apron's corner
        # where its hole stops and the pad rim runs on over uncovered ground
        # (the ``_mixed_rim_cells`` fixture, 2 of 7), and an apron | pad |
        # pad triple point (HECA building170 | building167, 2).
        base = pref.split("#")[0]
        unit = unit_ref_of(pref)
        own_f = set(cfids) | set(pfids)
        keep: list[int] = []
        for o in outer:
            if o in air:
                keep.append(o)             # a welded contact always leads
                continue
            if o in edge_v:
                continue                   # the coverage edge: the DEM's
            inc = [q for q in planar.vertices[o].incident_faces if q not in own_f]
            other = [q for q in inc if planar.faces[q].role == planar.faces[cfids[0]].role
                     and planar.faces[q].ref.split("#")[0] != base]
            if other and all(unit_ref_of(planar.faces[q].ref) == unit for q in other):
                # flat-pad spec §2 (5) (RULINGS 2026-09-30r): a vertex on the
                # TERRACE between two blocks of one unit — the 1:3 bank from
                # each block's floor, two-sided, never the rim's cap 0
                terrace.add(o)
                keep.append(o)
                continue
            if other:
                continue
            keep.append(o)
        outer = keep
        if not outer:
            continue
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
                                     "rows_own_rim_follows": n_own,
                                     "rows_block_terrace": n_terr}
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
    # (E) SPEC-AUTHOR RULINGS 2026-09-29s: a refused plate that fronts
    # airside is one contact-led plane too, over its OWN vertices
    plates = refused_plates(planar, law)
    if not pairs and not plates:
        return []
    vw = view(planar, law)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    n_planes = 0
    sets = [(pref, sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]]
                           for v in r}), f"face:{pfids[0]}")
            for pref, _cfids, pfids in pairs]
    sets += [(ref, own, f"plate:{ref}") for ref, own, _w in plates]
    from .pads import FLAT_RULING
    n_flat = 0
    for pref, vs, tag in sets:
        if len(vs) < 4:
            continue
        if pref in HELD and not tag.startswith("plate:"):
            # flat-pad spec §1 (1) (RULINGS 2026-09-30f/r): a HELD block is
            # FLAT at its datum — every platform vertex equal to the datum
            # column (``model.platform.datum_vertex_of``), hard
            dv = datum_vertex_of(planar, pref)
            if dv is None:
                continue
            src = Source(GEN, PLANE_RULING + " (flat-pad spec §1 (1); RULINGS "
                         "2026-09-30f/r a held block is flat at its datum)",
                         (tag, pref))
            n_flat += 1
            for v in vs:
                if v == dv:
                    continue
                rows.append(Linear(((v, 1.0), (dv, -1.0)), None, 0.0, src))
                rows.append(Linear(((v, -1.0), (dv, 1.0)), None, 0.0, src))
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
                     (tag, pref))
        if tag.startswith("plate:"):
            # (E) a WELDED plate's plane stays SOFT, at the plate's own
            # price (``pad_flat_rulings``): 10y refuted hard coplanarity for
            # a welded pad, and MEASURED here — as hard rows HECA
            # ``building184`` / ``building266`` minted 14 violated hard rows
            # (to 0.67 m) against the 1 % ceiling's contact pairs
            src = Source(GEN, FLAT_RULING + " (plate plane; SPEC-AUTHOR "
                         "RULINGS 2026-09-29s (E) the refused platform's "
                         "contact-led fit)", (tag, pref))
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
    STATS["platform_plane_rows"] = {"planes": n_planes, "flat_blocks": n_flat,
                                    "rows": len(rows)}
    return rows


def platform_contacts(planar: PlanarMap, law: Law
                      ) -> list[tuple[str, list[int], list[int]]]:
    """``(platform ref, its PLATFORM vertices, its WELDED contacts)`` per
    minted platform — the welded contact being an OUTER collar vertex that
    is airside (``pads.airside_vertices``), exactly the leaders
    :func:`platform_collar_rows` keeps.  ONE derivation: the level rows
    here and the sidecar's ``platform_rim_relief`` read the same set."""
    from .pads import airside_vertices
    from .precedence import view
    pairs = collar_faces(planar, law)
    if not pairs:
        return []
    vw = view(planar, law)
    air = airside_vertices(planar, law)
    out = []
    for pref, cfids, pfids in pairs:
        inner = sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]]
                        for v in r})
        cvs = {v for q in cfids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        weld = sorted(v for v in cvs - set(inner) if v in air)
        out.append((pref, inner, weld))
    return out


def refused_plates(planar: PlanarMap, law: Law
                   ) -> list[tuple[str, list[int], list[int]]]:
    """(E) SPEC-AUTHOR RULINGS 2026-09-29s: a REFUSED platform
    (``planar/platform.PLATFORMS``, ``under_min_area`` / ``eroded_away``)
    that fronts airside is a plain welded plate and takes the SAME
    contact-led fit.  ``(ref, its OWN plate vertices, its WELDED
    contacts)``: the contacts are the plate's airside rim vertices (the 23a
    weld — one vertex, one value, stage 1's), the plane is carried by the
    plate's own vertices only — never an airside vertex (a hard plane
    through a weld is 10y's refuted identity) and never a vertex shared
    with another pad or a pavement face.  The min-area is unchanged."""
    from ..model.platform import PLATFORMS
    from .pads import airside_vertices, rigid_roles
    from .precedence import view
    refused = {p.ref for p in PLATFORMS if p.refused}
    if not refused:
        return []
    rigid = set(rigid_roles(law))
    vw = view(planar, law)
    air = airside_vertices(planar, law)
    by_ref: dict[str, list[int]] = {}
    for fid in sorted(planar.faces):
        f = planar.faces[fid]
        if f.role in rigid and str(f.ref) in refused:
            by_ref.setdefault(str(f.ref), []).append(fid)
    out = []
    for ref, fids in sorted(by_ref.items()):
        own_f = set(fids)
        vs = {v for q in fids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        weld = sorted(v for v in vs if v in air)
        own = []
        for v in sorted(vs - set(weld)):
            if any(q not in own_f and planar.faces[q].role in rigid
                   for q in planar.vertices[v].incident_faces):
                continue
            own.append(v)
        # a plane needs three well-spread OWN points (``_basis``); a plate
        # whose own vertices are collinear (its rim all weld but one edge)
        # carries no contact-led plane and keeps today's plate
        xy = {v: planar.vertices[v].xy for v in own}
        if len(weld) >= 3 and len(own) >= 4 and _basis(xy, own) is not None:
            out.append((ref, own, weld))
    return out


def plane_sets(planar: PlanarMap, law: Law
               ) -> list[tuple[str, list[int], list[int]]]:
    """Every CONTACT-LED plane (29s (A) + (E)): the minted platforms and
    the refused plates that front airside — ONE list both the hard plane
    rows and the level rows read."""
    return [*platform_contacts(planar, law), *refused_plates(planar, law)]


def contact_led_refs(planar: PlanarMap, law: Law) -> frozenset[str]:
    """The refs whose plane is CONTACT-LED (:func:`plane_sets` with at
    least one welded contact) — the plate rows (``pads._pad_rows``)
    release their cap-0 zero-tilt target on exactly these.  A platform
    with NO welded contact keeps it: with nothing leading, a released
    tilt is free and the solve parks it anywhere under the 1 % ceiling
    (MEASURED on the HECA replay: ``building5`` / ``building123`` /
    ``building283`` came out at exactly 1.000 %)."""
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    return frozenset(r for r, vs, w in plane_sets(planar, law)
                     if w and len(vs) >= 4 and _basis(xy, vs) is not None
                     and r not in HELD)


def platform_level_rows(planar: PlanarMap, law: Law,
                        airport: Airport | None = None) -> list[Row]:
    """THE PLATFORM'S PLANE IS CONTACT-LED (SPEC-AUTHOR RULINGS 2026-09-29s
    (A), implementing owner 29p (2)+(4); issue #96).  Every WELDED collar
    contact contributes ONE one-way level row against the platform plane
    EVALUATED AT THAT CONTACT: the plane through the three basis vertices
    :func:`platform_plane_rows` uses (the hard plane rows make every
    platform vertex lie on it), extrapolated to the contact by its
    barycentric coordinates — ``l1 z_a + l2 z_b + l3 z_c - z_o = 0``.  The
    contact LEADS (airside is king, 23a / 29p (1)); the platform's
    vertices follow.  Priced as §20's frontage level row
    (``pads.LEVEL_RULING``: one-way, the pad plate's weight, the plane
    withdrawn from every DEM datum mean), so the rows together are the
    least-squares fit of the plane to its contacts — LEVEL AND TILT, the
    tilt bounded by the hard 1 % ceiling (the cap-0 zero-tilt target no
    longer prices a platform, ``pads._pad_rows``).

    MEASURED (scout ``pads96`` on #96): with the cap-0 flat target and no
    per-contact row, HECA ``building4`` came out one flat plane at
    100.638 m, tilt 0, over a frontage rising 7 m W->E — the pad 3.37 m
    below the apron at the owner's site and 3.69 m above it at T3's west
    end, which the collar's slack 1:3 bank rows could not see."""
    from .pads import GEN_LEVEL, LEVEL_RULING, _two_sided
    STATS.pop("platform_level_rows", None)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    n_pl = n_c = 0
    for pref, vs, weld in plane_sets(planar, law):
        if len(vs) < 4 or not weld or pref in HELD:
            continue
        bs = _basis(xy, vs)
        if bs is None:
            continue
        a, b, c = bs
        (x1, y1), (x2, y2), (x3, y3) = xy[a], xy[b], xy[c]
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if det == 0.0:
            continue
        n_pl += 1
        src = Source(GEN_LEVEL, LEVEL_RULING + " (platform contact; SPEC-AUTHOR "
                     "RULINGS 2026-09-29s (A): the plane is contact-led)",
                     (pref, f"platform:{pref}", "pavement:welded"))
        fol = tuple(vs)
        for o in weld:
            x, y = xy[o]
            l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det
            l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det
            l3 = 1.0 - l1 - l2
            rows.extend(_two_sided(((a, l1), (b, l2), (c, l3), (o, -1.0)),
                                   src, fol))
            n_c += 1
    STATS["platform_level_rows"] = {"platforms": n_pl, "contacts": n_c}
    return rows


def frontage_hold_rows(planar: PlanarMap, law: Law,
                       airport: Airport | None = None) -> list[Row]:
    """THE FLAT PAD LEADS ITS FRONTAGE (flat-pad spec §1 (2); owner RULINGS
    2026-09-30f, 30r).  Every WELDED contact of a HELD block
    (:func:`platform_contacts`) takes one two-sided row ``z_o − z_D = 0``
    against the block's DATUM COLUMN (``model.platform.datum_vertex_of`` —
    a platform vertex the stage split registers as a stage-1 column,
    ``solve/design_roles.airside_stage_vertices``), so STAGE 1 solves the
    airside WITH the flat frontage: the solver redistributes the relief into
    the apron body and the taxiways within their hard caps, and the datum
    settles where the block's frontage can best be held.  After stage 1 the
    datum is a constant and the hard flat rows (:func:`platform_plane_rows`)
    put the whole block on it.

    PRICED, NOT HARD (lane ``flatpad111b`` deviation from spec §1 (2),
    reported for the spec author): the mint-time test reads the DEM, and on
    HECA the DEM at the taxi edges is itself 1.5 %-inconsistent (6,416 of
    138,075 pairs at T3), so a hard hold would be a demand the proxy cannot
    certify; as a law-weight row the hold is met wherever the caps admit it
    and the miss is reported per block (``platforms[].hold_residual_max_m``)
    — ``[design] hard_rulings`` naming the head makes it hard with no code
    change.  A generator."""
    from .pads import _two_sided
    STATS.pop("frontage_hold_rows", None)
    if not HELD:
        return []
    rows: list[Row] = []
    n_b = n_c = 0
    for pref, _vs, weld in platform_contacts(planar, law):
        if pref not in HELD or not weld:
            continue
        dv = datum_vertex_of(planar, pref)
        if dv is None:
            continue
        n_b += 1
        src = Source(GEN, HOLD_RULING + " (flat-pad spec §1 (2); RULINGS "
                     "2026-09-30f/r the pad's flat datum leads its frontage)",
                     (pref, f"platform:{pref}", "pavement:welded"))
        for o in weld:
            rows.extend(_two_sided(((o, 1.0), (dv, -1.0)), src, None))
            n_c += 1
    STATS["frontage_hold_rows"] = {"blocks": n_b, "contacts": n_c}
    return rows


def platform_records(planar: PlanarMap, law: Law,
                     z: "_t.Sequence[float] | None") -> list[dict]:
    """The sidecar's ``platforms`` key (unit-platform spec §3 P21, §4 (5)):
    per MINTED platform its ref, collar width C, the SOLVED plane (level at
    the platform's centroid, gradient, tilt, residual — the plane every
    piece lies on) and THE RELIEF THE COLLAR CARRIES — every welded
    (airside) outer collar vertex against that plane: p50, max, where, and
    the collar width the §31 (7) bank would need (``max / bank_slope``,
    clamped to ``bank_min_width_m``; over ``platform_collar_max_m`` the
    spec would refuse the platform).  Read off the solved surface; the
    census's ``platform_rim_relief`` prices exactly this.  ``[]`` without
    a platform or a surface."""
    import numpy as np

    from .pads import airside_vertices
    from .precedence import view
    pairs = collar_faces(planar, law)
    if not pairs or z is None:
        return []
    vw = view(planar, law)
    air = airside_vertices(planar, law)
    bs = float(law.tables.emit.design.bank_slope)
    cmin = float(law.tables.emit.design.bank_min_width_m)
    cmax = float(law.tables.structures.building_pad.platform_collar_max_m)
    out: list[dict] = []
    for pref, cfids, pfids in pairs:
        inner = sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]] for v in r})
        cvs = {v for q in cfids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        if len(inner) < 3:
            continue
        X = np.array([planar.vertices[v].xy for v in inner], dtype=float)
        Z = np.array([float(z[v]) for v in inner])
        c0 = X.mean(axis=0)
        A = np.c_[X - c0, np.ones(len(X))]
        co, *_ = np.linalg.lstsq(A, Z, rcond=None)
        res = np.abs(A @ co - Z)
        weld = sorted(v for v in cvs - set(inner) if v in air)
        rec: dict = {"ref": pref, "collar_m": collar_width(planar, cfids, pfids),
                     "level": round(float(co[2]), 3),
                     "grad": [round(float(co[0]), 6), round(float(co[1]), 6)],
                     "tilt_pct": round(100.0 * math.hypot(co[0], co[1]), 3),
                     "plane_residual_max_m": round(float(res.max()), 3),
                     "platform_vertices": len(inner), "welded": len(weld),
                     "centroid_ll": _ll_of(planar, inner, c0)}
        if pref in HELD:
            # flat-pad spec §1 / §2 (RULINGS 2026-09-30f/r): the block, its
            # unit, the solved datum and how far its welded frontage stands
            # off it (the hold's miss, carried by the collar)
            h = HELD[pref]
            dv = datum_vertex_of(planar, pref)
            rec.update({"unit": h["unit"], "block": h["k"], "blocks": h["blocks"],
                        "block_verdict": h["verdict"],
                        "datum_pred": (None if h["datum_pred"] is None
                                       else round(float(h["datum_pred"]), 3))})
            if dv is not None:
                D = float(z[dv])
                rec["datum"] = round(D, 3)
                if weld:
                    miss = np.array([abs(float(z[v]) - D) for v in weld])
                    k = int(np.argmax(miss))
                    rec.update({"hold_residual_p50_m": round(float(np.median(miss)), 3),
                                "hold_residual_max_m": round(float(miss[k]), 3),
                                "hold_within_m": int((miss <= float(law.tables.structures
                                                                   .building_pad
                                                                   .frontage_hold_margin_m)).sum()),
                                "hold_worst_ll": list(planar.vertices[weld[k]].key)})
        if weld:
            W = np.array([planar.vertices[v].xy for v in weld], dtype=float)
            rel = np.array([float(z[v]) for v in weld]) - (np.c_[W - c0, np.ones(len(W))] @ co)
            k = int(np.argmax(np.abs(rel)))
            mx = float(abs(rel[k]))
            rec.update({"rim_relief_p50_m": round(float(np.median(np.abs(rel))), 3),
                        "rim_relief_max_m": round(mx, 3),
                        "worst_ll": list(planar.vertices[weld[k]].key),
                        "worst_z": round(float(z[weld[k]]), 3),
                        "collar_needed_m": round(max(cmin, mx / bs), 2),
                        "over_collar_max": bool(mx / bs > cmax)})
        out.append(rec)
    return out


def collar_width(planar: PlanarMap, cfids, pfids) -> float:
    """C as built: the least distance from a platform vertex to the pad's
    OUTER ring (the collar's own outer ring) — what the mint's erosion
    left, read back off the map."""
    from shapely.geometry import LineString, Point
    outer = []
    for q in cfids:
        f = planar.faces[q]
        ring = planar.ring_vertices(f.ring)
        if len(ring) >= 2:
            outer.append(LineString([planar.vertices[v].xy for v in (*ring, ring[0])]))
    inner = {v for q in pfids for v in planar.ring_vertices(planar.faces[q].ring)}
    if not outer or not inner:
        return 0.0
    return round(min(min(g.distance(Point(planar.vertices[v].xy)) for g in outer)
                     for v in inner), 2)


def _ll_of(planar: PlanarMap, vs, xy) -> list:
    """The canonical lat/lon of the vertex of ``vs`` nearest ``xy`` (the
    frame's own identity — no projection here)."""
    v = min(vs, key=lambda q: (planar.vertices[q].xy[0] - xy[0]) ** 2
            + (planar.vertices[q].xy[1] - xy[1]) ** 2)
    return list(planar.vertices[v].key)
