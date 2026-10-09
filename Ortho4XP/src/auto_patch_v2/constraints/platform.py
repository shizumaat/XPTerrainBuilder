"""THE UNIT PAD'S ROWS — the flat held plane, the frontage hold, and the
1:3 BANKS inside a footprint (flat-pad spec §1-§4; spec §56 (3); owner
RULINGS 2026-09-30f/r, 2026-10-02ah, 2026-10-07c (6); issue #452).

A unit pad is ONE face (``planar/platform.py``).  HELD, it is FLAT at its
datum column (``model.platform.datum_vertices``): every OWN vertex equal to
the datum, hard (:func:`platform_plane_rows`), and every WELDED contact —
a vertex of the pad's face an airside face also carries — held to it
(:func:`frontage_hold_rows`, ``no_step.hold_interval``), so stage 1 solves
the airside WITH the flat frontage and the apron comes to the pad.  There
is NO COLLAR (spec §56 (3)): the relief a collar was minted to carry is
taken out of the rim by the hold, and a weld the elastic LP releases is a
step at the pad's rim, read after the solve (:func:`platform_records`)
and warned (``pad_warning``).

TWO BANKS REMAIN, both one derivation (:func:`_bank_rows`): the STRIP
between two flat blocks of one cut unit (``<unit>/b<k>#strip``,
:func:`block_strip_rows` — the declared pad|pad terrace) and the bank
around a viaduct ramp LANDING (``<unit>/landing<k>#collar``,
:func:`platform_collar_rows`, #290).  Every OUTER bank vertex takes one
``Diff`` at ``emit.design.bank_slope`` (the 1:3 bank — a slope, never a
cliff) against each of its ``_K`` nearest flat vertices, and every flat
vertex against its nearest outer one.  ONE-WAY where the outer vertex is
AIRSIDE (the flat vertex follows — airside is king); on the bank's OWN rim
the row is the 1:3 bank, both signs, one-way with the FLAT side leading
(RULINGS 2026-10-02v (5)), so the solve places the toe.  Priced as the
groundside terrace law prices a bank: a one-sided design penalty at the
law's weight, never a hard row."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import (PlanarMap, is_bank_ref, is_collar_ref, is_strip_ref,
                            pad_base_ref, platform_ref_of, unit_ref_of)
from ..model.platform import HELD, datum_vertices
from .pad_warning import stamp_warning

__all__ = ["platform_collar_rows", "platform_plane_rows", "frontage_hold_rows",
           "landing_rows", "landing_vertices",
           "TERRACE_RULING", "HOLD_RULING", "HOLD_DATUM_RULING",
           "platform_level_rows", "platform_contacts", "COLLAR_RULING",
           "HOLD_RESIDUAL_RULING", "hold_sets", "hold_row",
           "PLANE_RULING", "GEN", "collar_faces", "platform_records",
           "block_strip_rows", "unit_pad_faces", "flat_held_refs"]

GEN = "platform_collar"
#: The ruling HEAD (``solve.design.ruling_head``) — named by ``[design]
#: one_way_rulings``.
COLLAR_RULING = "structures.building_pad platform_collar bank"
#: The head of the OWN-rim rows (the 1:3 bank, one-way, the platform
#: leading — RULINGS 2026-10-02v (5)) — named by ``pad_flat_rulings`` for
#: its PRICE (the plate's own weight, as before the toe was freed) and by
#: ``one_way_rulings`` for its direction (the plate never follows the rim)
RIM_RULING = "structures.building_pad platform_collar rim"
#: The head of the BLOCK TERRACE rows (flat-pad spec §2 (5), RULINGS
#: 2026-09-30r): the strip between two flat blocks of one unit, a two-sided
#: 1:3 bank from each floor — priced at the law's weight like the collar
TERRACE_RULING = "structures.building_pad platform_collar terrace"
#: The head of the FRONTAGE HOLD rows (flat-pad spec §1 (2); RULINGS
#: 2026-09-30f / 30r): a held block's welded contact at the block's datum
HOLD_RULING = "structures.building_pad frontage_hold"
#: The head of the block DATUM's own row (owner 2026-10-02 round 5, RULINGS
#: 2026-10-02ah (1) restated: "the pad must be seated flat at a level the
#: apron can meet"): a SOFT preference — in no hard register, priced at the
#: law's weight — pulling the free datum column toward the apron's own
#: frontage level (the contacts' pass-1a median).  The welds (contact = D),
#: the pad's flat rows and the apron's caps are the hard set that decides D
#: jointly; a weld is released only when no single D serves the block
HOLD_DATUM_RULING = "structures.building_pad frontage_hold datum"
#: The head of a RESIDUAL contact's hold (flat-pad spec v2 §2 EMPTY (i)):
#: PRICED at the law's weight — deliberately NOT in ``[design]
#: hard_rulings``
HOLD_RESIDUAL_RULING = "structures.building_pad frontage_hold residual"
#: How many platform vertices each outer collar vertex is tied to: the
#: triangulation joins a rim vertex to a fan of inner ones, and three is a
#: fan (a solver-conditioning constant, not a law value).
_K = 3
#: The statistics ``constraints.generate`` publishes beside the row count.
STATS: dict[str, dict[str, int]] = {}


def collar_faces(planar: PlanarMap, law: Law, is_bank=is_collar_ref
                 ) -> list[tuple[str, tuple[int, ...], tuple[int, ...]]]:
    """``(platform ref, its COLLAR face ids, its PLATFORM face ids)`` per
    platform pad whose platform is in the map — ONE derivation (the rows
    here, the census's ``platform_rim_relief``).  A district pad's erosion
    leaves several platform pieces and the collar several faces; all of
    them carry the one ref.  ``is_bank`` picks the bank class: the collars
    (default) or the inter-block strips (``is_strip_ref``, spec §56 (3))."""
    from .pads import rigid_roles
    rigid = set(rigid_roles(law))
    plat: dict[str, list[int]] = {}
    col: dict[str, list[int]] = {}
    for fid in sorted(planar.faces):
        f = planar.faces[fid]
        if f.role not in rigid:
            continue
        if is_bank(f.ref):
            col.setdefault(platform_ref_of(f.ref), []).append(fid)
        elif not is_collar_ref(f.ref) and not is_strip_ref(f.ref):
            plat.setdefault(f.ref, []).append(fid)
    return [(r, tuple(cs), tuple(plat[r])) for r, cs in sorted(col.items())
            if r in plat]


def unit_pad_faces(planar: PlanarMap, law: Law) -> list[tuple[str, tuple[int, ...]]]:
    """``(ref, its face ids)`` per PLANNED unit pad or block in the map —
    every ``model.platform.HELD`` ref that is not a §20 conforming pad
    (spec §56 (3): the pad face itself, there is no collar).  ONE
    derivation: the contacts, the flat rows and the records read it."""
    from .pads import rigid_roles
    rigid = set(rigid_roles(law))
    units = {r for r, h in HELD.items() if not h.get("conforming")}
    by: dict[str, list[int]] = {}
    if units:
        for fid in sorted(planar.faces):
            f = planar.faces[fid]
            if f.role in rigid and str(f.ref) in units:
                by.setdefault(str(f.ref), []).append(fid)
    return [(r, tuple(fs)) for r, fs in sorted(by.items())]


def flat_held_refs(planar: PlanarMap, law: Law) -> frozenset[str]:
    """The unit pads / blocks that are FLAT AT A DATUM (a planned unit with
    a datum column) — the plate over one prices no §30 (6) per-vertex
    relief (``pads._pad_rows``: the hard flat rows carry none, RULINGS 12u)."""
    held = datum_vertices(planar, law)
    return frozenset(r for r, _f in unit_pad_faces(planar, law) if r in held)


def platform_collar_rows(planar: PlanarMap, law: Law,
                         airport: Airport | None = None) -> list[Row]:
    """The collar bank rows (module docstring).  A generator."""
    STATS.clear()
    rows, st = _bank_rows(planar, law, collar_faces(planar, law))
    if st is not None:
        STATS["platform_collar_rows"] = st
    return rows


def block_strip_rows(planar: PlanarMap, law: Law,
                     airport: Airport | None = None) -> list[Row]:
    """Spec §56 (3): the INTER-BLOCK TERRACE STRIP's rows — the 1:3 bank
    between two flat blocks of one cut unit (flat-pad spec §2 (5), RULINGS
    2026-09-30r), keyed on the ``#strip`` ref.  The same derivation the
    collar's rows take (:func:`_bank_rows`): a strip vertex on the chord it
    shares with the next block's strip is a TERRACE row from each floor.
    A generator; it runs after ``platform_collar_rows``."""
    rows, st = _bank_rows(planar, law, collar_faces(planar, law, is_strip_ref))
    if st is not None:
        STATS["block_strip_rows"] = st
    return rows


def _bank_rows(planar: PlanarMap, law: Law,
               pairs: list[tuple[str, tuple[int, ...], tuple[int, ...]]]
               ) -> "tuple[list[Row], dict[str, int] | None]":
    """The 1:3 bank rows of every ``(platform ref, bank faces, platform
    faces)`` pair, and their statistics (``None`` when nothing ran)."""
    from scipy.spatial import cKDTree

    from .pads import airside_vertices
    from .precedence import view
    if not pairs:
        return [], None
    cap = float(law.tables.emit.design.bank_slope)
    if cap <= 0.0:
        return [], None
    vw = view(planar, law)
    air = airside_vertices(planar, law)
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    n_air = n_own = n_terr = n_cov = n_isl = 0
    # the COVERAGE EDGE: a vertex of an edge with no face on one side
    edge_v = {v for e in planar.edges.values()
              if e.left_face is None or e.right_face is None for v in (e.a, e.b)}
    for pref, cfids, pfids in pairs:
        inner = sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]]
                        for v in r})
        cvs = {v for q in cfids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        outer = sorted(cvs - set(inner))
        # THE PAD'S OWN RIM IS THE COLLAR'S EXTERIOR.  A vertex on one of
        # the collar's HOLE rings that is not the platform's is an ISLAND
        # inside the footprint — the courtyard a region DID claim (an
        # apron island; the unclaimed kind is the coverage edge below).
        # The islands rule (RULINGS 2026-09-29d (b)) is that it follows its
        # pad's platform, and there is no rim relief inside a building to
        # place a toe against, so it keeps the cap-0 two-sided row 10-02v
        # (5) took off the OUTER rim.  MEASURED on the islands twin: at the
        # one-way bank the ring lagged its leader onto its own DEM bump
        # (1.31 m, and 0.26 m when the collar was 5 m wide).
        island = {v for q in cfids for r in vw.holes[q] for v in r} - set(inner)
        if len(inner) < 3 or not outer:
            continue
        bref = str(planar.faces[cfids[0]].ref)      # ``<ref>#collar`` / ``#strip``
        src = Source(GEN, COLLAR_RULING + " (unit-platform spec §1 (3); "
                     "§31 (7) the 1:3 bank; RULINGS 2026-09-28a (1))",
                     (f"face:{cfids[0]}", bref, f"platform:{pref}"))
        src_rim = Source(GEN, RIM_RULING + " (unit-platform spec §1 (3); "
                         "the pad's own rim on its plate)",
                         (f"face:{cfids[0]}", bref, f"platform:{pref}"))
        src_terr = Source(GEN, TERRACE_RULING + " (flat-pad spec §2 (5); RULINGS "
                          "2026-09-30r: the pad|pad terrace between two flat "
                          "blocks is a 1:3 bank)",
                          (f"face:{cfids[0]}", bref, f"platform:{pref}"))
        terrace: set[int] = set()
        cover: set[int] = set()
        tree = cKDTree([xy[v] for v in inner])
        seen: set[tuple[int, int]] = set()

        def _row(o: int, i: int) -> None:
            nonlocal n_air, n_own, n_terr, n_cov, n_isl
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
            elif o in cover:
                # the COVERAGE EDGE (issue #223): the 1:3 bank, ONE-WAY with
                # the PLATFORM leading — the rim follows the plate within the
                # bank; the plate never follows the rim.  Its LEVEL inside a
                # slack bank is the §23 ground datum (issue #302:
                # ``solve/design_ground.coverage_edge_collar_vertices``) —
                # without it HECA ``building75``'s rim was a near-null column
                # (bending Σc² 0.0098) whose height the solve path chose.
                # #223 had measured that datum breaking ``test_v2qp``
                # (0.95 m through the plate): the coupling was the datum
                # counting as a SHEET ANCHOR (the pad lost its body datum),
                # which ``design_ground.ground_rim_vertices`` withdraws
                n_cov += 1
                rows.append(Diff(o, i, cap, d, src, follows=(o,)))
            elif o in terrace:
                n_terr += 1
                rows.append(Diff(o, i, cap, d, src_terr))
            elif o in island:
                # an ISLAND ring inside the footprint (the islands rule,
                # RULINGS 2026-09-29d (b)): cap 0, TWO-SIDED, as the plate
                # priced it — it follows its platform and carries no relief
                n_isl += 1
                rows.append(Diff(o, i, 0.0, d, src_rim))
            else:
                # the pad's OWN rim (issue #86, owner RULINGS 2026-10-02v
                # (5)): the 1:3 bank, BOTH SIGNS, ONE-WAY with the PLATFORM
                # leading — never the cap-0 equality that FIXED the toe at
                # the rim.  The collar is minted at the cap, so the bank has
                # the law's widest run; inside it the rim follows the ground
                # objective, and the solve puts the toe where the relief
                # allows in ONE pass (the two-pass re-mint is refused, 29l).
                # The plate still never follows the rim: ``follows=(o,)``,
                # the same direction the coverage edge takes (#223).
                n_own += 1
                rows.append(Diff(o, i, cap, d, src_rim, follows=(o,)))

        # WHAT AN OUTER VERTEX IS NOT THE COLLAR'S TO GRADE (measured on the
        # HECA replay, lane ``unitplatform2``: 3,528 cap-0 rows missed by up
        # to 16.2 m):
        # * a vertex on the COVERAGE EDGE — a courtyard HOLE of the pad no
        #   region claims, where the DEM governs (a fixed vertex: its
        #   "follower" row turns two-way and drags the PLATFORM to the
        #   courtyard's DEM, which is how the plate bent) — NOT a cap-0 rim
        #   row; since issue #223 it keeps the 1:3 bank ONE-WAY, the plate
        #   leading (see the ``edge_v`` branch below).  Since 10-02v (5) the
        #   OWN rim takes that same row, so the 3,528 figure is the count of
        #   the rows the cap-0 equality used to fix, not of a live miss;
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
        base = pad_base_ref(pref)
        unit = unit_ref_of(pref)
        own_f = set(cfids) | set(pfids)
        keep: list[int] = []
        for o in outer:
            if o in air:
                keep.append(o)             # a welded contact always leads
                continue
            inc = [q for q in planar.vertices[o].incident_faces if q not in own_f]
            other = [q for q in inc if planar.faces[q].role == planar.faces[cfids[0]].role
                     and pad_base_ref(planar.faces[q].ref) != base]
            if o in edge_v:
                # the coverage edge: the DEM's level, the collar's SLOPE
                # (issue #223).  The exemption above was written while the
                # terrain beyond the zone was a FIXED value (a two-way cap-0
                # row dragged the plate to it); since 09-09b (3) nothing
                # fixes it, and a vertex with no row at all was held by the
                # bending stencil alone — SPJC building14#collar at
                # -12.02514481, -77.10577155 stood 46.26 m over a 24.7 m
                # platform and a 30.04 m DEM.  It keeps a ONE-WAY bank row
                # (the plate leads) unless it is another pad's rim.
                if not other:
                    cover.add(o)
                    keep.append(o)
                continue
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
    return rows, {"collars": len(pairs),
                  "rows_rim_airside_leads": n_air,
                  "rows_own_rim_follows": n_own,
                  "rows_block_terrace": n_terr,
                  "rows_island_flat": n_isl,
                  "rows_coverage_edge_follows": n_cov}


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
    contacts = _contact_sets(planar, law)
    # (E) SPEC-AUTHOR RULINGS 2026-09-29s: a refused plate that fronts
    # airside is one contact-led plane too, over its OWN vertices
    plates = refused_plates(planar, law)
    if not contacts and not plates:
        return []
    xy = {v: vx.xy for v, vx in planar.vertices.items()}
    rows: list[Row] = []
    n_planes = 0
    sets = [(pref, vs, f"face:{fid}", unit) for pref, vs, _w, fid, unit in contacts]
    sets += [(ref, own, f"plate:{ref}", False) for ref, own, _w in plates]
    from .pads import FLAT_RULING
    n_flat = 0
    held = datum_vertices(planar, law)
    for pref, vs, tag, unit in sets:
        if unit and pref not in held:
            # a planned unit with no datum column (no welded frontage in
            # the map) keeps the §20 plate's own rows
            continue
        if not unit and len(vs) < 4:
            continue
        if pref in held and not tag.startswith("plate:"):
            # flat-pad spec §1 (1) (RULINGS 2026-09-30f/r): a HELD block is
            # FLAT at its datum — every OWN vertex of its face equal to the
            # datum column (``model.platform.datum_vertices``), hard; its
            # welded contacts take the hold row instead
            dv = held[pref]
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


def landing_vertices(planar: PlanarMap) -> dict[str, list[int]]:
    """``{landing ref: its platform vertices}`` (rings and holes; the
    collar excluded) over ``model.platform.LANDINGS`` — ONE reading, the
    level rows and the DEM-datum withdrawal (``pads.pad_datum_withdrawn``)
    ask it."""
    from ..model.platform import LANDINGS
    if not LANDINGS:
        return {}
    out: dict[str, set[int]] = {}
    for f in planar.faces.values():
        r = str(f.ref)
        if r in LANDINGS:
            vs = out.setdefault(r, set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
    return {r: sorted(v) for r, v in out.items()}


def landing_rows(planar: PlanarMap, law: Law,
                 airport: Airport | None = None) -> list[Row]:
    """THE RAMP LANDING IS HELD AT THE DECK'S LEVEL (owner RULINGS
    2026-10-03e, #290): every platform vertex of a landing
    (``planar/landing``) takes a HARD two-sided row ``z_v − z_D = y``
    against its block's DATUM COLUMN ``D`` (``model.platform.
    datum_vertices``) — ``y`` the deck's authored height at the landing.
    The row reaches a groundside vertex, so it is a STAGE-2 row; D is a
    constant there (stage 1's), which makes it one-way by construction:
    the landing follows the block, the block and the airside never follow
    the landing.  The ground around banks to it through the collar's own
    1:3 rows (:func:`platform_collar_rows`, keyed on the ``#collar``
    spelling).  A landing whose block has no datum column holds nothing
    and is counted (``landings_no_datum``)."""
    from ..model.platform import LANDINGS
    STATS.pop("landing_rows", None)
    if not LANDINGS:
        return []
    held = datum_vertices(planar, law)
    rows: list[Row] = []
    n = n_none = 0
    for ref, vs in sorted(landing_vertices(planar).items()):
        rec = LANDINGS[ref]
        dv = held.get(rec["block"])
        if dv is None:
            n_none += 1
            continue
        y = float(rec["y"])
        src = Source(GEN, PLANE_RULING + " (RULINGS 2026-10-03e the ramp "
                     "landing held at its unit's level + the deck's y)",
                     (f"landing:{ref}", ref, f"platform:{rec['block']}"))
        n += 1
        for v in vs:
            if v == dv:
                continue
            rows.append(Linear(((v, 1.0), (dv, -1.0)), None, y, src))
            rows.append(Linear(((v, -1.0), (dv, 1.0)), None, -y, src))
    STATS["landing_rows"] = {"landings": n, "landings_no_datum": n_none,
                             "rows": len(rows)}
    return rows


def _contact_sets(planar: PlanarMap, law: Law
                  ) -> list[tuple[str, list[int], list[int], int, bool]]:
    """``(ref, its FLAT vertices, its WELDED contacts, a face id, is it a
    unit pad)`` — the body of :func:`platform_contacts`.

    A UNIT PAD or block (:func:`unit_pad_faces`; spec §56 (3)): the
    contacts are the vertices of its own face an airside face also carries
    (``pads.airside_vertices`` — 09-01g, one vertex, one value), the flat
    vertices every other vertex of the face but one ANOTHER pad carries
    (two pads may sit at different floors, ``step_exemption_pad_to_pad``:
    HECA ``building281`` abuts ``building68`` 16.4 m higher — an equality
    there is a contest the plane loses — and one a structure RAMP carries
    (``model.platform.structure_vertices``: a wall-corridor / door / tunnel
    ramp's top — the ramp is cut INTO its host pad and its level there is
    the ramp's own law; a wall's top RIM stays flat on the pad;
    MEASURED on the OTHH closing build: with the 25 ramp-top vertices of
    ``building6`` in the flat set the whole terminal settled at the ramps'
    2.61 m, 1.35 m under its frontage, and the apron followed); a block's
    own strip is its own,
    and a BANK face — another block's strip, a landing's collar — is no
    floor: the pad's rim under it stays on the pad's plane).

    A LANDING (``collar_faces``, the ``#collar`` pair): the platform's
    vertices, and the bank's outer vertices that are airside."""
    from ..model.platform import structure_vertices
    from .pads import airside_vertices, rigid_roles
    from .precedence import view
    pairs = collar_faces(planar, law)
    units = unit_pad_faces(planar, law)
    if not pairs and not units:
        return []
    vw = view(planar, law)
    air = airside_vertices(planar, law)
    struct = structure_vertices(planar, law)
    out: list[tuple[str, list[int], list[int], int, bool]] = []
    for pref, cfids, pfids in pairs:
        inner = sorted({v for q in pfids for r in [vw.rings[q], *vw.holes[q]]
                        for v in r})
        cvs = {v for q in cfids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        weld = sorted(v for v in cvs - set(inner) if v in air)
        out.append((pref, inner, weld, pfids[0], False))
    rigid = set(rigid_roles(law))
    for ref, fids in units:
        own_f = set(fids)
        base = pad_base_ref(ref)
        vs = {v for q in fids for r in [vw.rings[q], *vw.holes[q]] for v in r}
        weld = sorted(v for v in vs if v in air)
        flat = [v for v in sorted(vs - set(weld))
                if v not in struct
                and not any(q not in own_f and planar.faces[q].role in rigid
                            and not is_bank_ref(planar.faces[q].ref)
                            and pad_base_ref(planar.faces[q].ref) != base
                            for q in planar.vertices[v].incident_faces)]
        out.append((ref, flat, weld, fids[0], True))
    return out


def platform_contacts(planar: PlanarMap, law: Law
                      ) -> list[tuple[str, list[int], list[int]]]:
    """``(ref, its FLAT vertices, its WELDED contacts)`` per unit pad,
    block and landing (:func:`_contact_sets`).  ONE derivation: the plane
    rows, the hold sets and the sidecar's records read the same set."""
    return [(r, vs, w) for r, vs, w, _f, _u in _contact_sets(planar, law)]


def refused_plates(planar: PlanarMap, law: Law
                   ) -> list[tuple[str, list[int], list[int]]]:
    """(E) SPEC-AUTHOR RULINGS 2026-09-29s: a REFUSED platform
    (``planar/platform.PLATFORMS``: a draped facade's footprint)
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
    held = datum_vertices(planar, law)
    return frozenset(r for r, vs, w in plane_sets(planar, law)
                     if w and len(vs) >= 4 and _basis(xy, vs) is not None
                     and r not in held)


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
    held = datum_vertices(planar, law)
    for pref, vs, weld in plane_sets(planar, law):
        if len(vs) < 4 or not weld or pref in held:
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


def hold_sets(planar: PlanarMap, law: Law
              ) -> list[tuple[str, int, list[int], int, int]]:
    """``(held ref, its datum column, its HELD contacts, welded total,
    ramp contacts)`` per held block with a welded frontage — the welded
    contacts of :func:`platform_contacts` less the RAMP contacts (spec §2
    (2), accepted 30u (c): the apron grades between two blocks' datums
    there, ``samples_ramp``).  ONE derivation: the hold rows
    (:func:`frontage_hold_rows`) and the feasibility interval
    (``no_step.hold_interval``) read the same set."""
    import numpy as np
    held = datum_vertices(planar, law)
    if not held:
        return []
    # flat-pad spec v2 §3: the block's PLATEAU joins its hold set — every
    # vertex of its plateau apron pieces (``model.platform.
    # plateau_vertices``) but one a taxi / runway face or another pad also
    # carries (that vertex is the taxiway's, or the other pad's weld)
    from ..law.tables import is_rigid_role, role_family
    from ..model.platform import plateau_vertices
    plat = plateau_vertices(planar, law)
    foreign: set[int] = set()
    if plat:
        for f in planar.faces.values():
            if not (is_rigid_role(law, f.role)
                    or role_family(law, f.role) in ("taxi", "runway")):
                continue
            for ring in (f.ring, *f.holes):
                foreign.update(planar.ring_vertices(ring))
    out: list[tuple[str, int, list[int], int, int]] = []
    # flat-pad spec v2 §4: a §20 CONFORMING pad's contacts are its own
    # airside rim vertices (the plate IS its ring: 09-01g), no ramp mask
    conf = [r for r in held if HELD[r].get("conforming")]
    if conf:
        from .pads import airside_vertices as _air
        air_v = _air(planar, law)
        rim: dict[str, set[int]] = {}
        for f in planar.faces.values():
            if str(f.ref) in conf:
                vs = rim.setdefault(str(f.ref), set())
                for ring in (f.ring, *f.holes):
                    vs.update(v for v in planar.ring_vertices(ring) if v in air_v)
        for r in conf:
            weld = sorted(rim.get(r, ()))
            if weld:
                out.append((r, held[r], weld, len(weld), 0))
    flat_of: dict[str, set[int]] = {}
    for pref, _vs, weld in platform_contacts(planar, law):
        weld = [o for o in weld if o != held.get(pref)]
        if pref not in held or not weld:
            continue
        h = HELD[pref]
        hx = h.get("samples_xy")
        hr = h.get("samples_ramp")
        n_all = len(weld)
        ramp: set[int] = set()
        if hx is not None and hr is not None and len(hx):
            from scipy.spatial import cKDTree
            _d, j = cKDTree(np.asarray(hx)).query([planar.vertices[o].xy for o in weld])
            j = np.atleast_1d(j)
            ramp = {o for o, jj in zip(weld, j) if bool(hr[int(jj)])}
        hold = [o for o in weld if o not in ramp]
        own = set(weld)
        extra = sorted(v for v in plat.get(pref, ()) if v not in own and v not in foreign)
        if extra:
            h["plateau_vertices"] = extra
        flat_of[pref] = set(_vs)
        out.append((pref, held[pref], hold + extra, n_all, len(ramp)))
    return _with_near_miss(planar, law, out, flat_of)


def _with_near_miss(planar: PlanarMap, law: Law,
                    sets: list[tuple[str, int, list[int], int, int]],
                    flat_of: "dict[str, set[int]] | None" = None
                    ) -> list[tuple[str, int, list[int], int, int]]:
    """THE NEAR-MISS FRONTAGE OF A HELD BLOCK JOINS ITS HOLD SET (#148,
    RULINGS 2026-09-30bd residual; 30bb F4 deleted ``pad_frontage_level``
    for held pads, so the block's ONE level is its datum, 30l (1)).  A
    held block's shared rim was held, but the soft vertices it fronts
    across a sliver (``pads.frontage_contacts``, the ``frontage_near_miss``
    population) were not: the gap could step (HECA 4 -> 10 CRITICAL rows).

    Only the endpoints INSIDE the gap (``d <= frontage_near_miss_m``) join:
    a fired edge's far endpoint (measured up to 40 m from the pad) is not
    a frontage contact but the far end of a sloping edge — it keeps its
    priced ``apron cap · d`` row, never an equality to the datum.

    A near-miss soft endpoint ``e`` joins the block's hold set when the pad
    vertex it binds to (``j``, the nearest pad vertex) is itself ON the
    datum — a held contact or plateau vertex of the block, or any vertex of
    a held §20 conforming plate (its whole plate is the datum, §4), or a
    FLAT vertex of a held unit pad (``flat_of``, spec §56 (3)).  A ``j``
    in a ramp is not on the datum, and ``e``
    keeps its priced near-miss row against ``z_j``.  ``e`` is then read by
    the §2 interval exactly as a welded contact (one set, one derivation):
    a near-miss contact the datum cannot reach makes the block RESIDUAL
    there (priced, ``pad_frontage_infeasible``), never a step.  A vertex
    another block already holds, or a runway-family vertex, is skipped."""
    if not sets:
        return sets
    from ..law.tables import role_family
    from .pads import frontage_contacts
    idx = {pref: k for k, (pref, *_r) in enumerate(sets)}
    on: dict[str, set[int]] = {pref: set(w) | {dv} | set((flat_of or {}).get(pref, ()))
                               for pref, dv, w, _n, _r in sets}
    conf = {pref for pref in idx if HELD[pref].get("conforming")}
    if conf:
        for f in planar.faces.values():
            if str(f.ref) in conf:
                for ring in (f.ring, *f.holes):
                    on[str(f.ref)].update(planar.ring_vertices(ring))
    taken: set[int] = {v for _p, _dv, w, _n, _r in sets for v in w}
    runway: set[int] = set()
    for f in planar.faces.values():
        if role_family(law, f.role) == "runway":
            for ring in (f.ring, *f.holes):
                runway.update(planar.ring_vertices(ring))
    near_m = float(law.tables.structures.building_pad.frontage_near_miss_m)
    add: dict[str, list[int]] = {}
    for e, j, pid, d, _cap, _sf in frontage_contacts(planar, law):
        pref = platform_ref_of(planar.faces[pid].ref)
        if (pref not in idx or d > near_m or e in taken or e in runway
                or j not in on[pref]):
            continue
        taken.add(e)
        add.setdefault(pref, []).append(e)
    out = list(sets)
    for pref, k in idx.items():
        es = sorted(add.get(pref, ()))
        HELD[pref]["near_miss_contacts"] = es
        if es:
            p, dv, w, n_all, n_r = out[k]
            out[k] = (p, dv, list(w) + es, n_all, n_r)
    return out


def hold_row(o: int, dv: int, pref: str, residual: bool = False,
             plateau: bool = False) -> list[Row]:
    """The hold row of contact ``o`` against datum column ``dv``: HARD
    (head :data:`HOLD_RULING`) for a held contact; a RESIDUAL contact of an
    empty interval keeps its hold PRICED at the law's weight (flat-pad spec
    v2 §2 EMPTY (i): head :data:`HOLD_RESIDUAL_RULING`, not in ``[design]
    hard_rulings``) — the apron comes as close as the caps allow."""
    from .pads import _two_sided
    head = HOLD_RESIDUAL_RULING if residual else HOLD_RULING
    what = (f"the PLATEAU of {pref} at its datum (flat-pad spec v2 §3, RULINGS "
            "2026-09-30y addendum)" if plateau else
            "flat-pad spec §1 (2); RULINGS 2026-09-30f/r/y the pad's flat datum "
            "leads its frontage")
    src = Source(GEN, head + f" ({what})",
                 (pref, f"platform:{pref}", "plateau" if plateau else "pavement:welded"))
    return list(_two_sided(((o, 1.0), (dv, -1.0)), src, None))


def frontage_hold_rows(planar: PlanarMap, law: Law,
                       airport: Airport | None = None) -> list[Row]:
    """THE FLAT PAD LEADS ITS FRONTAGE — HARD (flat-pad spec §1 (2); owner
    RULINGS 2026-09-30f / 30r, restated 2026-09-30y, #128).  Every HELD
    contact of a held block (:func:`hold_sets`) takes one HARD two-sided
    row ``z_o − z_D = 0`` (head :data:`HOLD_RULING` in ``[design]
    hard_rulings``) against the block's DATUM COLUMN (``model.platform.
    datum_vertex_of`` — a platform vertex the stage split registers as a
    stage-1 column), so STAGE 1 solves the airside WITH the flat frontage.
    After stage 1 the datum is a constant and the hard flat rows
    (:func:`platform_plane_rows`) put the whole block on it.

    THE DATUM AND ITS INTERVAL ARE NOT DERIVED HERE (flat-pad spec v2 §2,
    RULINGS 2026-09-30as): ``no_step.hold_interval`` computes the
    pair-graph feasibility interval between PASS 1a (stage 1 with these
    rows dropped) and PASS 1b, chooses the datum in it, re-prices a
    residual contact of an empty interval and adds the datum ``Pin`` and
    the runway's flex ``Band`` rows (``solve.design.solve_design``).  The
    route-metric reach band (the former ``no_step.runway_reach_band_values``,
    deleted with it) that bounded the datum here is DELETED — it pinned ``preferred_z``, not solved values,
    on a metric that reached 5 of SPJC's 8 blocks.  A generator."""
    STATS.pop("frontage_hold_rows", None)
    rows: list[Row] = []
    n_b = n_c = n_ramp = 0
    for pref, dv, weld, n_all, n_r in hold_sets(planar, law):
        h = HELD[pref]
        n_ramp += n_r
        h["hold_contacts"] = [(o, None) for o in weld]
        h["welded_total"] = n_all
        if not weld:
            continue
        n_b += 1
        for o in weld:
            rows.extend(hold_row(o, dv, pref))
            n_c += 1
    STATS["frontage_hold_rows"] = {"blocks": n_b, "contacts": n_c,
                                   "contacts_ramp": n_ramp}
    return rows


def platform_records(planar: PlanarMap, law: Law,
                     z: "_t.Sequence[float] | None") -> list[dict]:
    """The sidecar's ``platforms`` key: per UNIT PAD or block
    (:func:`unit_pad_faces`) its ref, the SOLVED plane over its flat
    vertices (level at their centroid, gradient, tilt, residual), its datum
    and how its welded frontage stands against it — held, RELEASED
    (:func:`_datum_record`), warned (``pad_warning``, spec §56 (3)) — and
    its plateau; then the landings (:func:`_landing_records`) and the §20
    conforming pads.  Read off the solved surface.  ``[]`` without a
    surface."""
    import numpy as np

    if z is None:
        return []
    conf = _conforming_records(planar, law, z)
    out: list[dict] = _landing_records(planar, law, z)
    dvs = datum_vertices(planar, law)
    for pref, inner, weld, _fid, unit in _contact_sets(planar, law):
        if not unit:
            continue
        if len(inner) < 3:
            # a pad whose rim is nearly all weld: the plane over its whole face
            inner = sorted({*inner, *weld})
            if len(inner) < 3:
                continue
        fids = [q for q, f in planar.faces.items() if str(f.ref) == pref]
        X = np.array([planar.vertices[v].xy for v in inner], dtype=float)
        Z = np.array([float(z[v]) for v in inner])
        c0 = X.mean(axis=0)
        A = np.c_[X - c0, np.ones(len(X))]
        co, *_ = np.linalg.lstsq(A, Z, rcond=None)
        res = np.abs(A @ co - Z)
        rec: dict = {"ref": pref,
                     "level": round(float(co[2]), 3),
                     "grad": [round(float(co[0]), 6), round(float(co[1]), 6)],
                     "tilt_pct": round(100.0 * math.hypot(co[0], co[1]), 3),
                     "plane_residual_max_m": round(float(res.max()), 3),
                     "platform_vertices": len(inner), "welded": len(weld),
                     "centroid_ll": _ll_of(planar, inner, c0)}
        if pref in HELD:
            # flat-pad spec §1 / §2 (RULINGS 2026-09-30f/r): the block, its
            # unit, the solved datum and how far its welded frontage stands
            # off it (the hold's miss, a step at the pad's rim)
            h = HELD[pref]
            dv = dvs.get(pref)
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
                # spec-author RULINGS 2026-09-30u (c): the HELD contacts and
                # the UNHELD (ramp / residual) ones reported apart — never a
                # silent class
                mg = float(law.tables.structures.building_pad.frontage_hold_margin_m)
                held_v = {v for v, _r in (h.get("hold_contacts") or ())}
                res_v = set(h.get("residual") or ())
                # #148: the near-miss contacts the hold set carries are read
                # beside the welded ones (held / residual alike)
                hw = weld + [v for v in (h.get("near_miss_contacts") or ())
                             if v not in set(weld)]
                hm = np.array([abs(float(z[v]) - D) for v in hw if v in held_v])
                # 30y (4): the UNHELD contacts the census names are the
                # RESIDUAL ones (the reach band excludes the datum); a RAMP
                # contact (spec §2 (2)) is reported apart
                um = [(abs(float(z[v]) - D), v) for v in hw if v in res_v]
                rm = [abs(float(z[v]) - D) for v in hw
                      if v not in held_v and v not in res_v]
                from ..law.tables import design as design_law
                htol = float(design_law(law).hard_tol_m)
                rec.update({"held_within_tol": int((hm <= htol + 1e-6).sum()) if hm.size else 0,
                            "ramp_contacts": len(rm),
                            "ramp_miss_max_m": round(max(rm), 3) if rm else None})
                # 30u (b): the mint's band is a proxy, never a certificate —
                # the SOLVED verdict: every held contact on the datum, or
                # the block is a RESIDUAL (reported, the owner reads it)
                rec["hold_verdict"] = ("held" if hm.size and not int((hm > mg).sum())
                                       and not um else "residual")
                rec.update(_datum_record(planar, z, D, [v for v in hw if v in held_v],
                                         htol, h))
                rec["pad_m2"] = _pad_m2(planar, fids)
                stamp_warning(rec, mg)
                rec.update({"held_contacts": int(hm.size),
                            "held_miss_max_m": round(float(hm.max()), 3) if hm.size else None,
                            "held_over_margin": int((hm > mg).sum()) if hm.size else 0,
                            "unheld_contacts": len(um),
                            "unheld_miss_max_m": (round(max(um)[0], 3) if um else None),
                            "unheld_worst_ll": (list(planar.vertices[max(um)[1]].key)
                                                if um else None)})
            # flat-pad spec v2 §3 / A3: the PLATEAU — its vertices, how many
            # sit on the datum, its tilt (a plane fitted over them) and area
            pv = [v for v in (h.get("plateau_vertices") or ())]
            if pv:
                from ..model.platform import PLATEAUS
                from ..law.tables import design as _dl
                tol_p = float(_dl(law).hard_tol_m)
                P = np.array([planar.vertices[v].xy for v in pv], dtype=float)
                Zp = np.array([float(z[v]) for v in pv])
                Ap = np.c_[P - P.mean(axis=0), np.ones(len(P))]
                cp, *_ = np.linalg.lstsq(Ap, Zp, rcond=None)
                pr = PLATEAUS.get(pref, {})
                rec.update({"plateau_vertices": len(pv),
                            "plateau_within_tol": (int((np.abs(Zp - float(z[dv])) <= tol_p + 1e-6).sum())
                                                   if dv is not None else None),
                            "plateau_tilt_pct": round(100.0 * math.hypot(cp[0], cp[1]), 3),
                            "plateau_area_m2": pr.get("area_m2"),
                            "stand_zone_source": pr.get("source")})
            if "reach_band" in h:
                rec["reach_band"] = h["reach_band"]
                rec["reach_empty"] = bool(h.get("reach_empty"))
                # flat-pad spec v2 §2 / P20: the pair-graph interval, I⁰ and
                # I, which evaluation held the block, the chosen datum and
                # the binding anchors (``no_step.hold_interval``)
                for k in ("reach_band0", "reach_width_m", "reach_gap_m",
                          "reach_gap0_m", "reach_eval", "reach_unreached",
                          "datum_chosen", "reach_lo_binding", "reach_hi_binding"):
                    if k in h:
                        rec[k] = h[k]
        out.append(rec)
    return out + conf


def _landing_records(planar: PlanarMap, law: Law, z) -> list[dict]:
    """The record of every viaduct ramp LANDING (``collar_faces``, the
    ``#collar`` pair, #290): its ref, the bank's width as built, the solved
    plane of its platform and — where a bank vertex is welded to airside —
    the relief the bank carries there."""
    import numpy as np

    from .pads import airside_vertices
    from .precedence import view
    pairs = collar_faces(planar, law)
    if not pairs:
        return []
    vw = view(planar, law)
    air = airside_vertices(planar, law)
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
        if weld:
            W = np.array([planar.vertices[v].xy for v in weld], dtype=float)
            rel = np.array([float(z[v]) for v in weld]) - (np.c_[W - c0, np.ones(len(W))] @ co)
            k = int(np.argmax(np.abs(rel)))
            rec.update({"rim_relief_p50_m": round(float(np.median(np.abs(rel))), 3),
                        "rim_relief_max_m": round(float(abs(rel[k])), 3),
                        "worst_ll": list(planar.vertices[weld[k]].key),
                        "worst_z": round(float(z[weld[k]]), 3)})
        out.append(rec)
    return out


def _datum_record(planar: PlanarMap, z, D: float, held_v, tol: float,
                  h: dict) -> dict:
    """Round 5 (owner 2026-10-02, RULINGS 2026-10-02ah (1)): the block's
    datum against the apron's own level — ``datum_median`` (the contacts'
    pass-1a median the soft preference pulled toward), ``datum_minus_median_m``,
    the welds the solve held (``welded``) and RELEASED (``released`` — a
    contact off D by more than ``hard_tol_m``: the elastic LP found no single
    D for the block), their coordinates and the released contacts' spread,
    and ``needs_split`` — the owner's two-pads-with-a-cliff class, reported
    for the base-profile split, never decided here."""
    import numpy as np
    med = h.get("datum_chosen")
    rel = [(abs(float(z[v]) - D), float(z[v]), v) for v in held_v]
    out_v = [(d, zz, v) for d, zz, v in rel if d > tol + 1e-6]
    zs = [zz for _d, zz, _v in out_v]
    rl = h.get("reach_isect")
    return {"datum_median": med,
            "reach_isect": rl, "reach_isect_empty": bool(h.get("reach_isect_empty")),
            "datum_in_reach_isect": (bool(rl is not None and (rl[0] is None or rl[0] - tol <= D)
                                          and (rl[1] is None or D <= rl[1] + tol))),
            "reach_bands_contacts": h.get("reach_bands_contacts"),
            "misfit_m": h.get("misfit_m"), "weld_widened": h.get("weld_widened"),
            "datum_minus_median_m": (round(D - float(med), 3) if med is not None else None),
            "welded": len(rel) - len(out_v), "released": len(out_v),
            "released_ll": [list(planar.vertices[v].key) for _d, _z, v in
                            sorted(out_v, reverse=True)[:12]],
            "released_spread_m": (round(max(zs) - min(zs), 3) if len(zs) > 1
                                  else (0.0 if zs else None)),
            "released_max_m": (round(max(d for d, _z, _v in out_v), 3) if out_v else 0.0),
            "needs_split": bool(out_v) or bool(h.get("reach_isect_empty"))}


def _conforming_records(planar: PlanarMap, law: Law, z) -> list[dict]:
    """flat-pad spec v2 §4 / A8: the sidecar record of every HELD §20
    CONFORMING pad — its datum, its contacts held within ``hard_tol_m``,
    the tilt of the plane fitted over ALL its vertices, the interval."""
    import numpy as np
    from ..law.tables import design as design_law
    refs = [r for r, h in HELD.items() if h.get("conforming")]
    if not refs:
        return []
    dvs = datum_vertices(planar, law)
    tol = float(design_law(law).hard_tol_m)
    verts: dict[str, set[int]] = {}
    fids: dict[str, list[int]] = {}
    for fid, f in planar.faces.items():
        if str(f.ref) in refs:
            fids.setdefault(str(f.ref), []).append(fid)
            vs = verts.setdefault(str(f.ref), set())
            for ring in (f.ring, *f.holes):
                vs.update(planar.ring_vertices(ring))
    out: list[dict] = []
    for r in sorted(refs):
        h, vs, dv = HELD[r], sorted(verts.get(r, ())), dvs.get(r)
        if dv is None or len(vs) < 3:
            continue
        X = np.array([planar.vertices[v].xy for v in vs], dtype=float)
        Z = np.array([float(z[v]) for v in vs])
        A = np.c_[X - X.mean(axis=0), np.ones(len(X))]
        co, *_ = np.linalg.lstsq(A, Z, rcond=None)
        D = float(z[dv])
        held_v = [v for v, _x in (h.get("hold_contacts") or ())]
        hm = np.array([abs(float(z[v]) - D) for v in held_v]) if held_v else np.zeros(0)
        rec = {"ref": r, "conforming": True, "datum": round(D, 3),
               "vertices": len(vs), "tilt_pct": round(100.0 * math.hypot(co[0], co[1]), 3),
               "held_contacts": int(hm.size),
               "held_within_tol": int((hm <= tol + 1e-6).sum()) if hm.size else 0,
               "held_miss_max_m": round(float(hm.max()), 3) if hm.size else None,
               "unheld_contacts": len(h.get("residual") or ()),
               "hold_verdict": ("held" if hm.size and not h.get("residual")
                                and not int((hm > tol + 1e-6).sum()) else "residual"),
               "centroid_ll": _ll_of(planar, vs, X.mean(axis=0))}
        for k in ("reach_band", "reach_band0", "reach_width_m", "reach_gap_m",
                  "reach_gap0_m", "reach_eval", "reach_empty", "datum_chosen"):
            if k in h:
                rec[k] = h[k]
        rec.update(_datum_record(planar, z, D, held_v, tol, h))
        rec["pad_m2"] = _pad_m2(planar, fids.get(r, ()))
        stamp_warning(rec, float(law.tables.structures.building_pad
                                 .frontage_hold_margin_m))
        out.append(rec)
    return out


def _pad_m2(planar: PlanarMap, fids) -> float:
    """The area of the faces ``fids`` (the pad as the user sees it), m² —
    each face's ring less its holes, by the shoelace
    (``geom.pad_evidence.ring_area`` on frame metres)."""
    from ..geom.pad_evidence import ring_area

    def _a(ring) -> float:
        return ring_area([planar.vertices[v].xy for v in planar.ring_vertices(ring)],
                         1.0, 1.0)
    return round(sum(_a(planar.faces[q].ring) - sum(_a(h) for h in planar.faces[q].holes)
                     for q in fids), 1)


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
