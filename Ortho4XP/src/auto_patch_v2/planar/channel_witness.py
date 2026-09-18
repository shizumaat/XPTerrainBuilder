"""§45 (1) (c) THE PACK'S WALL / FLOOR WITNESSES — who states that a
corridor is cut, and how deep (spec §45 (1) (c) / (3) (i) / (7) / (10) (i),
AMENDED by owner RULINGS 2026-09-17t) — lanes ``v2channel`` / ``v2channelfp``.

Its own module beside ``planar/channel.py`` for that file's 1,000-line
budget, and because the witness set is ONE question asked by four
consumers: the corridor WIDTH ((10) (i), ``channel_geometry._walls_half``),
the FLOOR DATUM ((3) (i), ``channel_floor``), the DECK pieces ((12), a
witnessing plate's roofed stretches) and §45 (7)'s exclusion of the
witness from the basin / sunken-road / tunnel-object passes.  They read
the SAME set because they call the SAME function — which is why a false
witness at HECA set the floor, the width and the datum at once, and why
one test here retired all three (RULINGS 2026-09-17t).
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.airport import Airport
from .channel_geometry import _across, _along, _dem

if _t.TYPE_CHECKING:                          # the candidate lives in
    from .channel import _Cand                # ``channel``, which imports THIS

__all__ = ["_pack_witnesses", "_pack_ids", "_res_of", "_depth_under_crest"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def _pack_witnesses(cand: "_Cand", objects: _t.Sequence, half_m: float,
                    crest_est: float, min_depth_m: float,
                    min_area_m2: float = 1.0,
                    pit_shells: _t.AbstractSet[str] = frozenset(),
                    dropped: list[str] | None = None,
                    min_length_m: float = 0.0,
                    corridor_half_m: float | None = None,
                    off_axis: list[tuple[str, str]] | None = None) -> list[str]:
    """§45 (1) (c): the pack's wall / floor objects along the axis.

    The 05k-1 authority — seat = floor, plate = crest, hull = footprint —
    read through the placement reading the basin pass already made
    (``planar/basins.read_objects``), so nothing re-parses an OBJ8.  A
    placement whose plan runs inside the corridor band and whose deepest
    GENUINE solid stands ``object_min_depth_m`` under the corridor's
    crest is the channel's witness.  It is NOT a basin seed, a sunken
    road, a tunnel-object corridor or a door well (§45 (7)).

    §45 (1) (c) AMENDED (owner RULINGS 2026-09-17t, fix A; scout
    ``hecachannel``): A PACK WITNESS IS A WALL OR FLOOR **ALONG** THE
    CORRIDOR.  Two tests, both at this one derivation site — the width
    (:func:`channel_geometry._walls_half`), the floor (§45 (3) (i)) and
    §45 (7)'s exclusion all read the set this function returns, so the
    false positive dies once here and not four times downstream:

      * the below-grade footprint stands within the ROAD'S OWN
        ``half_base`` — the carriageways ⊕ ``lane_width_m`` of §45 (10)
        (iii) — and NOT within the 120 m ``corridor_max_half_width_m``
        SEARCH cap.  HECA ``channel:2``: three
        ``Airport/Jetway/EGCC_Jetway_metal_03.obj`` AIRBRIDGES standing
        90+ m off a 7.0 m ``highway=service`` way (−13192) read as a
        4.28 m below-grade solid (the model's own rotunda stub runs to
        y = −4.2753, so it reads flush on any apron) and witnessed a
        channel they are nowhere near.  That one reading supplied a flat
        97.32 floor over 1,990 m, set the half-width to 92.0 m from the
        jetways' own off-axis offset, and flipped the datum to ``pack``
        — which SKIPS the (13) (c) guard that refused the way's five
        neck-only siblings.  Airside cost: taxiway ``pav65`` emitted
        6.31–7.39 m under the DEM.
      * it RUNS ALONG the axis: its along-axis extent reaches
        ``corridor_min_length_m`` (50 m) or is at least its own extent
        ACROSS the axis.  A trench wall is long and thin along the
        corridor; a point object beside the road is not.  LGAV's
        ``Trench/Trench_07/08.obj`` run 2 km along the axis and keep
        their witness; the jetways (a ~20 m rotunda) do not.

    The SEARCH stays at ``half_m`` (the caller's cap) so that a drop can
    be NAMED — a placement refused before the depth test is a silent
    nothing, which is what cost the round-5 arm two airport loads — and
    the ruled test is ``corridor_half_m``, applied after it."""
    band = cand.line.buffer(half_m, **_MITRE)
    on_corridor = (cand.line.buffer(corridor_half_m, **_MITRE)
                   if corridor_half_m is not None else None)
    dropped = dropped if dropped is not None else []
    out: list[str] = []
    for o in objects or ():
        # THE FOOTPRINT, NEVER THE BBOX — the round-1 defect, attributed
        # before it was changed (§45 (12); RULINGS 2026-09-15s).
        # ``plan_bbox`` is the resource's plan EXTENT: at LGAV
        # ``Trench_03``'s is 7,984,284 m2 (2.5 x 3.2 km) and
        # ``Trench_06``'s 8,800,700 m2, so EVERY candidate band on the
        # field intersected them and five separate "channels" all read
        # one floor.  Worse, the number they read — 63.43 — came from
        # ``train_powercable.obj``, whose ``below_grade`` is a
        # ZERO-AREA MultiPolygon straddling the axis and whose
        # ``solid_min_z`` is the family's lowest: the floor of LGAV's
        # trench was the power cable.  So the witness is the object's
        # own below-grade footprint WITH REAL AREA, and an object that
        # states no footprint states no width and no floor.
        # §45 (13) (d) A BASIN'S OWN SHELL IS NEVER A CHANNEL'S WALL
        # (owner RULINGS 2026-09-15ac).  The object side is decided by the
        # object's own KIND, at the one derivation site the basin pass
        # already owns — ``airport/basin_witness.basin_member_ids``: a
        # placement carrying a basin FLOOR WITNESS is a PIT SHELL whose
        # rim tops out at grade (§24 (1)), not a trench wall running along
        # an axis.  Basins are built AFTER channels, so (13) (b)'s
        # "already claimed" set does not exist for objects and the kind
        # test is what stands in its place.  Measured at LEMD round 4:
        # ``channel:5`` (way −5989, neck + pack, ONE deck) took
        # ``dsf:obj7`` / ``dsf:obj10`` — two of ``basin:0``'s three
        # members ``Ground-FSX-LEMD36/37/85`` — and §24's owner-accepted
        # T4S basin then fell to "overlaps a tunnel structure".
        bb = getattr(o, "below_grade", None)
        z = getattr(o, "solid_min_z", None)
        if bb is None or z is None or getattr(bb, "area", 0.0) <= min_area_m2:
            continue
        try:
            if not band.intersects(bb):
                continue
        except Exception:                     # pragma: no cover
            continue
        if _depth_under_crest(o, crest_est) < min_depth_m:
            continue
        oid = str(getattr(o, "id", ""))
        # §45 (1) (c) AMENDED, fix A's SECOND test: A WALL OR FLOOR RUNS
        # ALONG THE CORRIDOR.  Measured on the object's OWN below-grade
        # footprint (the same geometry the band and the width read), by
        # the same overlap rule §45 (10) already states for a width: the
        # along-axis span reaches ``corridor_min_length_m``, or the thing
        # is at least as long as it is wide.  HECA's jetway rotundas fail
        # both; LGAV's 2 km ``Trench_07``/``Trench_08`` walls and its
        # 4,077 x 149 m ``Trench_06`` plate pass on the first.
        if on_corridor is not None or min_length_m > 0.0:
            pts = [p for g in getattr(bb, "geoms", [bb])
                   if getattr(g, "geom_type", "") == "Polygon"
                   for p in g.exterior.coords]
            along = _along(cand.line, pts)
            across = _across(cand.line, pts)
            why = ""
            if on_corridor is not None and not on_corridor.intersects(bb):
                why = (f"stands off the corridor (nearest {bb.distance(cand.line):.0f} m "
                       f"from the way, half-base {corridor_half_m:.1f} m)")
            elif min_length_m > 0.0 and along < min_length_m and along < across:
                why = (f"does not run along the axis (along {along:.0f} m, across "
                       f"{across:.0f} m, [channel] corridor_min_length_m "
                       f"{min_length_m:.0f})")
            if why:
                if off_axis is not None:
                    off_axis.append((oid, why))
                continue
        if oid in pit_shells:
            # the test above is (13) (d)'s, and it runs HERE — after the
            # footprint / band / depth tests — for one reason only: so the
            # drop is REPORTABLE.  A placement refused before those tests
            # is a silent nothing, and the LGAV round-5 arm then cost two
            # full airport loads to learn WHICH object went (the answer:
            # Trench_07 / Trench_08).  Same rule, named.
            dropped.append(oid)
            continue
        out.append(oid)
    return out


def _res_of(o) -> str:
    """The placement's RESOURCE as the pack names it — ``resource`` when
    the reading carries one, else the placed ``path`` (``obj8`` states
    the path; the LGAV round-5 note read ``?`` for all three)."""
    for k in ("resource", "path"):
        v = getattr(o, k, None)
        if v:
            return str(v)
    return "?"


def _depth_under_crest(o, crest_est: float) -> float:
    """HOW FAR THIS PLACEMENT'S DEEPEST GENUINE SOLID STANDS UNDER THE
    GROUND OVER IT (§45 (1) (c)/(7)) — the ONE reading both the witness
    test and §45 (7)'s exclusion ask.

    ``obj8`` already measures it per component against the LOCAL terrain
    (``solid_min_depth_m``, negative below), and that is what is used.
    The scalar corridor mean is only the fallback, and the round-2 arm
    measured why it cannot be the rule: LGAV's axis is 1,954 m long over
    12.6 m of relief, so its mean DEM reads 67.48 while the DEM along it
    runs 64.32…76.96.  Against that mean ``Trench_07`` (its own local
    depth −11.03 m) read 1.02 m and ``Trench_08`` (−8.19 m) read −2.17 m
    — both refused by ``object_min_depth_m`` 3.0, which is why the trench
    did not witness its own channel."""
    d = getattr(o, "solid_min_depth_m", None)
    if d is not None:
        return -float(d)
    z = getattr(o, "solid_min_z", None)
    if z is None or math.isnan(crest_est):
        return 0.0
    return float(crest_est) - float(z)


def _pack_ids(grp: list["_Cand"], objects: _t.Sequence, half_m: float,
              airport: Airport, law: Law, axis_fn, ss,
              pit_shells: _t.AbstractSet[str] = frozenset(),
              dropped: list[str] | None = None,
              corridor_half_m: float | None = None,
              off_axis: list[tuple[str, str]] | None = None) -> list[str]:
    """§45 (1) (c) / (10) (i): the pack placements that witness THIS
    channel — read once, so the width (i), the floor (3) (i), the deck
    pieces (12) and §45 (7)'s exclusion all name the SAME set.

    ``half_m`` stays the SEARCH radius (the cap) and ``corridor_half_m``
    — the road's own ``half_base`` — is the RULED test since owner
    RULINGS 2026-09-17t (fix A): a witness stands ON the corridor, and
    the 120 m cap is the widest a corridor may END UP, never the band a
    wall may be found in.  See :func:`_pack_witnesses`."""
    ch = law.tables.structures.channel
    zs = [_dem(airport, axis_fn(s)) for s in ss]
    good = [z for z in zs if not math.isnan(z)]
    crest = (sum(good) / len(good)) if good else float("nan")
    out: list[str] = []
    for c in grp:
        for i in _pack_witnesses(c, objects, half_m, crest, ch.object_min_depth_m,
                                 pit_shells=pit_shells, dropped=dropped,
                                 min_length_m=ch.corridor_min_length_m,
                                 corridor_half_m=corridor_half_m,
                                 off_axis=off_axis):
            if i not in out:
                out.append(i)
    return out
