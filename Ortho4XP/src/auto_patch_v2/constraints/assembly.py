"""THE ASSEMBLY POST-PASSES (stage-cache spec §4b.1): everything that reads
ALL of the generators' rows, run once after them — the water and seam
exemptions, the senior structure datum, the EAT pin's withdrawal, the road
ramp on a landing run-out, the 5 % ceiling, the universal pavement cap and
the public road's release to its terrain.

``constraints.generate`` runs the generators and hands their concatenated
rows here; no generator reads another's rows, so these passes are the only
coupling between them (the ``constraints.assembly`` record of §4b.1 keys
on this module's closure, not on every generator's)."""
from __future__ import annotations

import time
import typing as _t

from ..law import Law
from ..model.constraints import Diff, Linear, Offset, Pin, Row, pinned_vertices
from ..model.planar import PlanarMap
from . import (
    ceiling,
    eat,
    pavement_cap,
    public_road_release,
    ramp_runout,
    riser,
    seams,
    structures,
    water,
)

__all__ = ["assemble", "seam_exempt", "water_exempt"]


def assemble(rows: list[Row], counts: dict[str, int], walls: dict[str, float],
             planar: PlanarMap, law: Law,
             only: _t.Container[str] | None = None,
             yielded_out: list[Row] | None = None) -> list[Row]:
    """The post-passes over the generators' ``rows``, in their run order;
    each pass's count and wall seconds are written into ``counts`` /
    ``walls`` (in place).  Returns the assembled rows."""
    # WATER IS A DATUM (owner RULINGS 2026-09-09m (1)): a ground vertex the
    # water pin fixes is no longer an unknown — every OTHER row that would
    # govern it is withdrawn, BEFORE the seam pass (a seam vertex on water
    # takes the water level, not the DEM's).
    rows, n_water = water_exempt(rows)
    counts["water_pin_row_withdrawn"] = n_water
    walls["water_pin_row_withdrawn"] = 0.0
    rows, n_exempt, n_seam_junior = seam_exempt(rows, yielded_out)
    counts["seam_pin_pair_exempt"] = n_exempt
    walls["seam_pin_pair_exempt"] = 0.0
    counts["seam_pin_withdrawn_senior"] = n_seam_junior
    walls["seam_pin_withdrawn_senior"] = 0.0
    # A LOWER LEVEL'S RISER IS A DECLARED STEP (#1214 round 6): no row but
    # its landing row spans it -- the pad ceiling and plane across the
    # strip, a road ribbon crossing it (a #1138 site)
    rows = riser.riser_exempt(rows, planar, counts)
    walls["riser_rows_withdrawn"] = 0.0
    # THE SENIOR STRUCTURE'S DATUM (precedence.toml [structures]): a
    # vertex two structures pin keeps one pin (lane v2hecalemd, LEMD)
    rows, n_junior = structures.reconcile_datums(rows, law)
    counts["structure_datum_withdrawn"] = n_junior
    walls["structure_datum_withdrawn"] = 0.0
    # A NODE THAT IS ALREADY HARD IS NEVER OVERRIDDEN (spec §36; v1's own
    # rule): the EAT rect yields to every other pin family and to a rigid
    # group, rather than winning by generator order in the reduction.
    rows, n_eat = eat.withdraw_against_senior(rows)
    counts["eat_pin_withdrawn_senior"] = n_eat
    walls["eat_pin_withdrawn_senior"] = 0.0
    # #711: a mapped road on a landing's run-out rides it (its §37 ramp
    # rows withdrawn where the strip holds the vertex)
    rows, n_runout = ramp_runout.runout_exempt(rows, planar)
    counts["road_ramp_withdrawn_on_runout"] = n_runout
    walls["road_ramp_withdrawn_on_runout"] = 0.0
    # THE 5 % CEILING (owner RULINGS 2026-09-09b (4)): a POST-PASS over the
    # law set — one hard twin at the ceiling per pavement DIFFERENCE row
    # (``constraints/ceiling.py``), never a second reading of the geometry.
    if only is None or ceiling.GEN in only:
        t0 = time.perf_counter()
        caps = ceiling.pavement_ceiling(rows, planar, law)
        walls[ceiling.GEN] = time.perf_counter() - t0
        counts[ceiling.GEN] = len(caps)
        rows.extend(caps)
    # THE UNIVERSAL PAVEMENT CAP (owner RULINGS 2026-09-29ac, #105): the
    # road cap is the HARD fallback over every pavement pair no row above
    # already caps at or under it — ring edges and welded neighbours alike
    # (``constraints/pavement_cap.py``), after the ceiling so its twins
    # count as "already capped".
    if only is None or pavement_cap.GEN in only:
        t0 = time.perf_counter()
        fb = pavement_cap.pavement_road_cap(rows, planar, law)
        walls[pavement_cap.GEN] = time.perf_counter() - t0
        counts[pavement_cap.GEN] = len(fb)
        rows.extend(fb)
    # A PUBLIC ROAD FOLLOWS ITS TERRAIN (owner RULINGS 2026-10-22h, #1254):
    # LAST, so the ceiling's twins and the fallback yield with the rest
    t0 = time.perf_counter()
    rows, n_pub = public_road_release.terrain_release(rows, planar, law)
    walls[public_road_release.GEN] = time.perf_counter() - t0
    counts[public_road_release.GEN] = n_pub
    return rows


def water_exempt(rows: list[Row]) -> tuple[list[Row], int]:
    """THE WATER PIN IS THE VERTEX'S OWN LAW (owner RULINGS 2026-09-09m
    (1); ``constraints/water.py``).

    A ground vertex the water pin fixes "is not an unknown of the sheet",
    so every OTHER row that would GOVERN it is withdrawn:

    * a second ``Pin`` on it (a declared datum) — two equalities on one
      vertex is a contradiction, and water outranks;
    * a one-way row whose governed vertex (``follows``) is pinned — a
      zone band cannot fight the datum it stands in;
    * any row ALL of whose vertices are pinned — it prices water against
      water (the seam-pin precedent, :func:`seam_exempt`).

    A row with ONE pinned vertex and one free one STAYS: that is the
    shoreline, and the shore is a BANK (09m (2)) — the next round's, and
    reported meanwhile, never silently dropped.

    Returns the rows and the number withdrawn.
    """
    pinned = pinned_vertices(rows, water.GEN)
    if not pinned:
        return rows, 0
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, Pin):
            if r.source.generator == water.GEN or r.v not in pinned:
                out.append(r)
            else:
                n += 1
            continue
        follows = getattr(r, "follows", None)
        if isinstance(follows, tuple):
            # a one-way row over a SET of followers (the pad plane's three
            # degrees of freedom, owner RULINGS 2026-09-10y) governs nothing
            # once EVERY follower is pinned
            follows = follows[0] if len(follows) == 1 else (
                next(iter(follows)) if all(v in pinned for v in follows) else None)
        if follows is not None and follows in pinned:
            n += 1
            continue
        if isinstance(r, Linear) and all(v in pinned for v, _c in r.terms):
            n += 1
            continue
        if isinstance(r, (Diff, Offset)) and r.a in pinned and r.b in pinned:
            n += 1
            continue
        out.append(r)
    return out, n


def seam_exempt(rows: list[Row], yielded_out: list[Row] | None = None
                ) -> tuple[list[Row], int, int]:
    """THE SEAM-PIN PAIR EXEMPTION (user 2026-07-04, the census's own
    reading — ``check_grade`` with sidecar ``seam_pins``: "pin↔pin pairs
    skip, pin↔free pairs check at the body cap"): a grade row whose every
    vertex is a seam DEM pin prices terrain against terrain and is
    dropped; a row with one free vertex stays.

    AND THE SENIOR-DATUM WITHDRAWAL (§38 (1); ``constraints/seams.py``
    docstring): the seam pin is a ``Pin`` since 13ah, so a vertex another
    generator ALSO pins would carry two equalities and the reduction's
    row order would decide which one holds.  A CIFP threshold outranks the
    seam (the runway's own regulation value), so the SEAM pin is the one
    withdrawn there — counted, never silent.  (Water is senior to both and
    is settled earlier, in :func:`water_exempt`.)

    AND THE ZONE BAND YIELDS BETWEEN TWO PINS (§38 (2); owner RULINGS
    2026-09-13ah, attributed 13am (6)).  A ONE-WAY row (``follows``) whose
    GOVERNED vertex is a seam pin governs a vertex that has no column: the
    row survives only as a two-way PULL on the pavement it was written to
    follow, which ``one_way_rulings`` exists to forbid ("the adjacent
    ground follows the pavement and never pulls it", 09-09b (2)/(3)).
    Measured at SPLP that pull is exactly what held the seam off its DEM —
    the relax arm ``zone_bands −1,670 rows → z−dem after −0.000`` — and
    with the seam pinned it re-appears as a 2.39 m zone miss and an
    INFEASIBLE runway projection.  So the row YIELDS, on the same clause
    ``water_exempt`` already applies to a water datum ("a zone band cannot
    fight the datum it stands in").  Each yielded row is handed back
    through ``yielded_out`` so the design report can NAME the family, its
    two pins and the demanded-vs-allowed metres (§38 (2), never a silent
    residual).

    Returns the rows, the number of PAIRS dropped and the number of seam
    PINS withdrawn against a senior pin."""
    pinned = pinned_vertices(rows, seams.GEN)
    if not pinned:
        return rows, 0, 0
    senior = {r.v for r in rows
              if isinstance(r, Pin) and r.source.generator != seams.GEN}
    n_junior = 0
    if senior & pinned:
        keep: list[Row] = []
        for r in rows:
            if (isinstance(r, Pin) and r.source.generator == seams.GEN
                    and r.v in senior):
                n_junior += 1
                continue
            keep.append(r)
        rows = keep
        pinned = pinned - senior
    out: list[Row] = []
    n = 0
    for r in rows:
        if isinstance(r, Pin):
            out.append(r)
            continue
        if isinstance(r, Diff) and r.a in pinned and r.b in pinned:
            n += 1
            continue
        if isinstance(r, Linear) and all(v in pinned for v, _c in r.terms):
            n += 1
            continue
        if isinstance(r, Offset) and r.a in pinned and r.b in pinned:
            n += 1
            continue
        # §38 (2) THE ZONE BAND YIELDS: a one-way row whose GOVERNED vertex
        # is a seam pin (the ``water_exempt`` clause, applied to the seam)
        fv = getattr(r, "follows", None)
        fvs = ((int(fv),) if isinstance(fv, int)
               else tuple(int(q) for q in fv) if fv is not None else ())
        if fvs and all(q in pinned for q in fvs):
            if yielded_out is not None:
                yielded_out.append(r)
            n += 1
            continue
        out.append(r)
    return out, n, n_junior
