"""THE PLACEMENT CENSUSES (spec ``object-placement-spec.md`` §14 (4),
§15 (3), §16 (1)/(2); owner RULINGS 2026-09-11v / 11ae / 11ai).

THE INSTRUMENTS, and only the instruments: what ``obj8_split_report`` and
``seat_feet_census --placement-plan`` both print, over the PLACEMENT
PLAN's own rows (``model/placement.Split.to_dict()`` — the shape the app
writes).  ONE implementation of each bar, called by both, because a
second reading of the same population is the census-wrapper defect
(CLAUDE.md).

The law these judge is ``placement_carrier`` next door; the relation a
census measures (what a body STANDS OVER, the ground under a body's own
geometry) is that module's own function, never a copy.  They live apart
because ``placement_carrier`` reached the 1,000-line law, and the split
is law / instrument.
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar
from .placement_carrier import (ground_samples, overlap, stands_over_rank)

__all__ = ["census_v14", "census_v14_lines", "census_v15", "census_v15_lines",
           "census_v16", "census_v16_lines", "census_v16b",
           "census_v16b_lines", "census_population",
           "census_population_lines", "STANDS_OVER_TOL_M", "FOOTLESS_KEPT",
           "KEPT_FOOTLESS", "KEPT_NO_CARRIER", "OWN_GROUND", "THICKNESS_SKIP",
           "LAWFUL_SKIPS", "CARRIED_GROUND_TOL_M", "GEOM_GROUND_TOL_M",
           "CARRIED_OWN_GROUND_TOL_M"]


# ── §14 (4): THE CENSUS ──────────────────────────────────────────────────

#: §13's interim reading: a footless placement left on its unit's shared
#: DATUM row.  §14 (1) supersedes it, and the bar is 0.
KEPT_FOOTLESS = "footless"
#: §14 (1)'s named residual: a footless placement whose UNIT holds no
#: footed body at all, so nothing in the plan reads the ground under it.
#: It keeps its own authored row — which for the one-member unit this
#: class actually is, is its own position, not a shared datum — and is
#: REPORTED by name rather than guessed at.  Not a bar.
KEPT_NO_CARRIER = "footless_no_carrier"
#: §16 (3): the anchor reason of a body written at the ground under its
#: own footprint (``placement_plan.OWN_GROUND``, repeated here because no
#: module may import the other way round).
OWN_GROUND = "footless_own_ground"
FOOTLESS_KEPT = (KEPT_FOOTLESS, KEPT_NO_CARRIER)


def census_v14(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
               kept: _t.Sequence[_t.Mapping[str, _t.Any]],
               *, elevated_base_m: float, split_tol_m: float) -> dict:
    """§14 (4), over the PLACEMENT PLAN's own rows
    (``model/placement.Split.to_dict()`` — the shape the app writes and
    the shape ``obj8_split_report`` renders, so the two instruments are
    one code path and cannot disagree):

    ``footless at datum``   a footless file left on its placement's
                            authored row: the shared-datum point, which
                            for LEMD's unit:25 is 430 m and 15.7 m of
                            height away from the building it belongs to.
    ``footless on ground``  a footless file whose intended zero stands
                            above ``elevated_base_m`` — the writer shifted
                            it so its own lowest vertex lands on the
                            terrain (the footbridge deck 0.03 m under the
                            road).  This is §13's own bar restricted to
                            the footless class.
    ``basin bodies split``  a ``basin`` resource written as more than one
                            file: one rigid object draped piece by piece.
    ``spread``              the widest zero-plane range of any ONE
                            placement — ``surface_z - y_zero`` over its
                            bodies.  A placement whose terrain genuinely
                            differs is LAWFULLY split (§9), so this is
                            reported with the placement that carries it,
                            never silently.

    Bars: 0 / 0 / 0 / <= ``split_tol_m``."""
    at_datum: list[str] = []
    no_carrier: list[str] = []
    #: every BASIN body's zero plane, keyed by the emitted RING it
    #: anchors on when the anchor names one (§14 (2)) and by its own
    #: placement otherwise.  The ring is the physical object: LEMD's pit
    #: is authored as THREE resources on one row, and 11v measured its
    #: scatter ACROSS them (593.30 ... 600.29, 7.0 m).  Per-placement
    #: alone the metric cannot see that.
    basin_ring: dict[str, list[float]] = {}
    on_ground: list[tuple[float, str]] = []
    basin_split: list[str] = []
    spread: list[tuple[float, str]] = []
    for s in splits:
        p = s.get("placement", {})
        plat, plon = p.get("lat"), p.get("lon")
        zeros: list[float] = []
        basins = 0
        res = str(p.get("resource", "?"))
        for b in s.get("bodies", ()):
            off = b.get("authored_offset", (0.0, 0.0, 0.0))
            y0 = float(off[1]) if len(off) > 1 else 0.0
            a = b.get("anchor", {})
            if b.get("class") == "basin":
                basins += 1
            sz = b.get("surface_z")
            zero = None if sz is None else float(sz) - float(b.get("y_zero", y0))
            if zero is not None:
                zeros.append(zero)
                if b.get("class") == "basin":
                    why = str(b.get("anchor_reason", ""))
                    key = (why.split("(", 1)[1].split(")", 1)[0]
                           if why.startswith("basin rim (") else res)
                    basin_ring.setdefault(key, []).append(zero)
            if not b.get("elevated"):
                continue
            # §16 (3): a body anchored on the ground under its OWN
            # footprint is not "left at the datum" — its anchor is its own
            # footprint centroid, and for a symmetric object placed at its
            # own centre that point IS the row.  What §14 bars is a
            # footless file left on the row because nothing carried it.
            if str(b.get("anchor_reason", "")).startswith(OWN_GROUND):
                continue
            if plat is not None and abs(float(a.get("lat", 0.0)) - float(plat)) < 1e-9 \
                    and abs(float(a.get("lon", 0.0)) - float(plon)) < 1e-9:
                at_datum.append(str(b.get("new_resource", "?")))
            if y0 > elevated_base_m:
                on_ground.append((y0, str(b.get("new_resource", "?"))))
        if basins > 1:
            basin_split.append(res)
        if len(zeros) > 1:
            spread.append((max(zeros) - min(zeros), res))
    for k in kept:
        r = str(k.get("reason", ""))
        if r == KEPT_FOOTLESS:
            at_datum.append(str(k.get("resource", "?")))
        elif r == KEPT_NO_CARRIER:
            no_carrier.append(str(k.get("resource", "?")))
    spread.sort(reverse=True)
    basin_spread = sorted(((max(v) - min(v), k) for k, v in basin_ring.items()
                           if len(v) > 1), reverse=True)
    on_ground.sort(reverse=True)
    worst = spread[0] if spread else (0.0, "")
    wbasin = basin_spread[0] if basin_spread else (0.0, "")
    return {"footless_at_datum": len(at_datum),
            "footless_at_datum_names": at_datum[:5],
            "footless_on_ground": len(on_ground),
            "footless_on_ground_names": on_ground[:5],
            "basin_bodies_split": len(basin_split),
            "basin_bodies_split_names": basin_split[:5],
            "footless_no_carrier": len(no_carrier),
            "footless_no_carrier_names": no_carrier[:5],
            "spread_m": worst[0], "spread_resource": worst[1],
            "spread_basin_m": wbasin[0], "spread_basin_resource": wbasin[1],
            "spread_over_tol": sum(1 for d, _r in spread if d > split_tol_m),
            "bars_ok": (not at_datum and not on_ground and not basin_split
                        and worst[0] <= split_tol_m)}


# ── §15 (3): THE RESIDUAL THE EYE READS ──────────────────────────────────

#: §15 (3)'s reporting threshold: a body whose zero stands this far above
#: the zero of the body it STANDS OVER is what the owner reads as
#: floating (11ac: "the roof pieces are floating above the buildings").
STANDS_OVER_TOL_M = 0.5


def _v15_rows(splits: _t.Sequence[_t.Mapping[str, _t.Any]]) -> list[dict]:
    """Every body of the plan as ``{res, idx, box, zero, footed, carried}``
    — the one projection both §15 (3) readings are taken from.  A body
    with no ``plan_box`` (a plan written before §15) or no ``surface_z``
    (OFF-SHEET: its anchor stands on no graded face) carries ``None`` and
    is excluded from every comparison, never guessed at (§15 (5))."""
    rows: list[dict] = []
    for s in splits:
        p = s.get("placement", {})
        bs = list(s.get("bodies", ()))
        for b in bs:
            box = b.get("plan_box")
            sz = b.get("surface_z")
            rows.append({
                "res": str(b.get("new_resource") or p.get("resource", "?")),
                "idx": p.get("index"),
                # THE UNIT, without a new field: every placement of one
                # unit carries that unit's ANCHOR as its row (§14), so
                # the row's own (lat, lon) IS the unit key — and §15 (1)
                # scopes the carrier search to the unit, so the census
                # has to read the same scope or it counts the scoping
                # rather than the defect.
                "unit": (p.get("lat"), p.get("lon")),
                "box": None if not box else tuple(float(q) for q in box),
                # §16 (3): the geometry the relation is measured on, and
                # whether this body is a SOLID at all — read here exactly
                # as the carrier search reads it
                "fboxes": tuple(tuple(float(q) for q in fb)
                                for fb in b.get("foot_boxes", ()) or ()),
                "cls": str(b.get("class", "")),
                "fill": float(b.get("fill", 1.0)),
                # §16a (2): how far this body's own zero stands from the
                # ground under its own feet — the law's third carrier
                # test, read here so the instrument's "beneath" is the
                # law's own candidate set (CLAUDE.md, one relation read
                # ONE way)
                "ground_off": (None if b.get("ground_off") is None
                               else float(b["ground_off"])),
                "zero": None if sz is None
                        else float(sz) - float(b.get("y_zero", 0.0)),
                "feet": int(b.get("feet") or 0),
                # CARRIED means "its zero is somebody else's reading":
                # a body on its OWN ground (§16 (3)'s
                # ``footless_own_ground``) reads the terrain like a
                # footed body and is judged like one
                "carried": bool(b.get("merged_into")),
                # 11ak (1): THE CARRIER THE LAW CHOSE — the file this
                # body was merged into.  The carried-body bar is read
                # against THIS body's zero, never against whatever the
                # footprint happens to lie over (a candidate §16a (2)
                # refused is not the body the law put underneath).
                "carrier": str(b.get("merged_into") or ""),
                # 11ak (3): a carrier KEPT WHOLE has no body file, so
                # ``merged_into`` names its MEMBER RESOURCE
                # (``_carried_file``'s ``carrier_res`` when the carrier
                # was not written).  Without this key the law's carrier
                # cannot be found at all and the census falls back to
                # whatever the footprint lies over — OTHH's 10 remaining
                # carried floats, every one of them a bus-bridge deck on
                # a kept-whole ramp.
                "whole_res": (str(p.get("resource", "")) if len(bs) == 1
                              else ""),
            })
    return rows


def census_v15(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
               kept: _t.Sequence[_t.Mapping[str, _t.Any]] = (),
               *, float_tol_m: float = STANDS_OVER_TOL_M,
               fill_min: float = 0.0, ground_tol_m: float = 0.0) -> dict:
    """§15 (3), over the PLACEMENT PLAN's own rows — the same shape and
    the same code path as :func:`census_v14`.

    A foot census cannot see this class at all: a carried body has NO
    feet, and a body anchored at its own low-side foot reads every foot
    of its own as lawful while standing metres above the walls under it.
    What the eye reads is the difference between the two zeros —

        float = zero - zero_beneath

    — where ``beneath`` is, for a CARRIED body, THE CARRIER THE LAW
    CHOSE (``merged_into``; 11ak (1)), and for a FOOTED one the body of
    another placement with the largest plan overlap under its footprint
    (the same stands-over relation :func:`carrier_for` ranks by, so the
    instrument and the law read the same geometry).  A body standing over
    nothing is not in the class.

    A carried body whose footprint lies over a body the law REFUSES as a
    carrier (§16a (2)) is counted and named separately — ``carried over a
    refused body``, with how far that body's own feet stand off — because
    what that number measures is the REFUSAL, not the placement: the body
    rode whatever the search reached next, by law.

    Bar (§15 (6)): ``stands-over float > 0.5 m`` is ZERO for CARRIED
    bodies — a carried body takes its carrier's zero by construction, so
    any residual is a carrier the law chose wrongly.  A FOOTED body's
    float is REPORTED by name: it reads its own ground, and two footed
    bodies over genuinely different terrain lawfully differ."""
    rows = _v15_rows(splits)
    # §16 (3): what a body STANDS OVER is a SOLID — a line segment, a
    # grass strip or a sign is not something anything stands on, and the
    # carrier search refuses them.  The census reads the same population
    # or it counts the disagreement rather than the defect.
    ground = [r for r in rows if r["feet"] and r["box"] and r["zero"] is not None
              and r["cls"] != _ar.LINE_SEGMENT
              and (fill_min <= 0.0 or r["fill"] >= fill_min)]
    # §16a (2): which of these the LAW REFUSES to let carry anything —
    # its own zero more than ``ground_tol_m`` from the ground under its
    # own feet.
    #
    # THE CENSUS SPLIT (11ak (1)).  A CARRIED body's "beneath" is the
    # carrier THE LAW CHOSE (``merged_into``), not the best-ranked body
    # its footprint happens to lie over: the law refuses a mis-anchored
    # candidate and the body rides whatever the search reached next, so
    # reading the refused one as "beneath" measures the REFUSAL and
    # calls it the placement's float (LEMD: 3 of 4, OTHH 23 of 39,
    # 11aj's own attribution).  The refused body under it is not thrown
    # away — it is counted and named as its own class, ``carried over a
    # refused body``, with how far that body's own feet stand off.
    # A FOOTED body keeps the geometric reading: it takes no carrier,
    # and what it stands over is exactly the question.
    in_unit: dict[_t.Any, list[dict]] = {}
    for g in ground:
        in_unit.setdefault(g["unit"], []).append(g)
    # the law's carrier is resolved over EVERY row that reads a zero,
    # not over the stands-over population: what the law chose is a fact
    # about the plan, and a carrier that is a line body or a kept-whole
    # placement is still the body this one rides.
    by_res: dict[str, dict] = {}
    for r in rows:
        if r["zero"] is not None:
            by_res.setdefault(r["res"], r)
    for r in rows:
        if r["zero"] is not None and r["whole_res"]:
            by_res.setdefault(r["whole_res"], r)
    carried_over: list[tuple[float, str, str]] = []
    footed_over: list[tuple[float, str, str]] = []
    refused_rows: list[tuple[float, str, str]] = []
    n_stands = 0
    cross = 0
    no_law_carrier = 0
    off_sheet = sum(1 for r in rows if r["zero"] is None or not r["box"])
    # A BASIN body is EXEMPT from the refusal (RULINGS 2026-09-11al):
    # its zero is the RIM by §14 (2) and its floor feet are authored
    # below that zero by construction, so the feet test refuses every
    # pit for the wrong reason.  Counted and printed separately as
    # ``basin carriers`` — the law lets them carry, and the number says
    # how many the feet test WOULD have taken out.
    refused = {id(g) for g in ground
               if ground_tol_m > 0.0 and g["ground_off"] is not None
               and g["ground_off"] > ground_tol_m
               and g["cls"] != _ar.BASIN}
    basin_cands = [g for g in ground if g["cls"] == _ar.BASIN]
    basin_exempt = sorted(((g["ground_off"], g["res"]) for g in basin_cands
                           if ground_tol_m > 0.0 and g["ground_off"] is not None
                           and g["ground_off"] > ground_tol_m), reverse=True)
    over_refused = 0
    for r in rows:
        if r["zero"] is None or not r["box"]:
            continue
        best_ov, geo = (0.0, 0.0), None
        for g in in_unit.get(r["unit"], ()):
            if g["idx"] == r["idx"]:
                continue
            ov = stands_over_rank(r["box"], g["box"], r["fboxes"], g["fboxes"])
            if ov > best_ov:
                best_ov, geo = ov, g
        under = geo
        if r["carried"]:
            # the law's own answer, by the file the body was merged into
            law_under = by_res.get(r["carrier"] or "")
            if law_under is not None and law_under["zero"] is not None:
                under = law_under
            elif geo is not None:
                # the carrier is off-sheet, or is not a body of this
                # plan's stands-over population (a carrier whose own
                # file the body joined): the geometric reading stands,
                # and the count says so
                no_law_carrier += 1
            if (geo is not None and id(geo) in refused and geo is not under
                    and r["zero"] - geo["zero"] > float_tol_m):
                # the row the old reading counted as a carried float:
                # the same threshold, the same body, named as what it
                # is.  The two counts therefore ADD to the old one.
                over_refused += 1
                refused_rows.append((r["zero"] - geo["zero"], r["res"],
                                     f"{geo['res']} (own feet off by "
                                     f"{geo['ground_off']:.2f} m)"))
        if under is None:
            # it stands over a body of ANOTHER unit, which §15 (1)'s
            # search cannot reach: reported as its own number, never
            # counted as a float the law could have closed
            cross += any(g["idx"] != r["idx"] and overlap(r["box"], g["box"]) > 0.0
                         for g in ground)
            continue
        n_stands += 1
        f = r["zero"] - under["zero"]
        if f > float_tol_m:
            (carried_over if r["carried"] else footed_over).append(
                (f, r["res"], under["res"]))
    carried_over.sort(reverse=True)
    footed_over.sort(reverse=True)
    refused_rows.sort(reverse=True)
    return {"stands_over": n_stands,
            "stands_over_float_gt": len(carried_over) + len(footed_over),
            "carried_float_gt": len(carried_over),
            "footed_float_gt": len(footed_over),
            "carried_worst": carried_over[:10],
            "footed_worst": footed_over[:10],
            "off_sheet_bodies": off_sheet,
            "stands_over_other_unit_only": cross,
            "float_tol_m": float_tol_m,
            "refused_as_carrier": len(refused),
            "basin_carriers": len(basin_cands),
            "basin_carriers_exempt": len(basin_exempt),
            "basin_carriers_exempt_worst": basin_exempt[:10],
            "carried_over_refused": over_refused,
            "carried_over_refused_worst": refused_rows[:10],
            "carried_no_law_carrier": no_law_carrier,
            "bars_ok": not carried_over}


def census_v15_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_v15`'s bar as the lines both tools print."""
    tol = c.get("float_tol_m", STANDS_OVER_TOL_M)
    out = [f"   §15 bodies standing over a body of another placement: "
           f"{c['stands_over']} of its own UNIT — §15 (1)'s own scope "
           f"({c['off_sheet_bodies']} off-sheet body(ies) excluded; "
           f"{c.get('stands_over_other_unit_only', 0)} stand only over a body "
           f"of ANOTHER unit, which the carrier search cannot reach)",
           f"   §15 stands-over float > {tol:g} m: {c['stands_over_float_gt']} "
           f"— CARRIED {c['carried_float_gt']} (bar 0)"
           + ("" if not c["carried_float_gt"] else
              "   *** §15 (1) VIOLATED (bar 0) ***")
           + f", footed {c['footed_float_gt']} (reported, not barred)"
           + (f" — the carried bar is read against the CARRIER THE LAW "
              f"CHOSE (11ak (1))"
              if c.get("refused_as_carrier") else "")]
    if c.get("basin_carriers"):
        out.append(
            f"   §16a (2) basin carriers (EXEMPT from the refusal, §14 (2)): "
            f"{c['basin_carriers']} basin body(ies) may carry, of which "
            f"{c.get('basin_carriers_exempt', 0)} would have been refused by "
            f"the feet test — a basin's zero is its RIM and its floor feet "
            f"are authored below it")
        for off, res in c.get("basin_carriers_exempt_worst", ()):
            out.append(f"      basin exempt (feet off by {off:.2f} m)  {res}")
    if c.get("refused_as_carrier"):
        out.append(
            f"   §15 carried over a REFUSED body (counted separately, not "
            f"barred): {c['carried_over_refused']} carried body(ies) stand "
            f"over one of the {c['refused_as_carrier']} footed body(ies) "
            f"§16a (2) refuses as a carrier"
            + (f"; {c['carried_no_law_carrier']} carried body(ies) have no "
               f"carrier row in this population and keep the geometric "
               f"reading" if c.get("carried_no_law_carrier") else ""))
    for f, res, under in c.get("carried_worst", ()):
        out.append(f"      carried +{f:.2f} m  {res}  over {under}")
    for f, res, under in c.get("carried_over_refused_worst", ()):
        out.append(f"      beneath refused ({f:+.2f} m)  {res}  over {under}")
    for f, res, under in c.get("footed_worst", ()):
        out.append(f"      footed  +{f:.2f} m  {res}  over {under}")
    return out


def census_v14_lines(c: _t.Mapping[str, _t.Any], *, elevated_base_m: float,
                     split_tol_m: float) -> list[str]:
    """:func:`census_v14`'s four bars as the lines both tools print."""
    def _bar(n: int) -> str:
        return "" if not n else "   *** §14 VIOLATED (bar 0) ***"
    out = [f"   §14 footless at datum: {c['footless_at_datum']} (bar 0)"
           + _bar(c["footless_at_datum"]),
           f"   §14 footless on ground: {c['footless_on_ground']} "
           f"(bar 0, [rebake] elevated_base_m {elevated_base_m:g} m)"
           + _bar(c["footless_on_ground"]),
           f"   §14 basin bodies split: {c['basin_bodies_split']} (bar 0)"
           + _bar(c["basin_bodies_split"]),
           f"   §14 spread (widest zero-plane range of one placement): "
           f"{c['spread_m']:.2f} m (bar <= {split_tol_m:g} m) "
           f"{c['spread_resource']}; {c['spread_over_tol']} placement(s) over "
           f"— a placement whose terrain genuinely differs is LAWFULLY "
           f"split (§9), so read the rigid classes beside it:",
           f"   §14 spread of a BASIN RING (11v: 7.0 m over LEMD36+37+SWbaume): "
           f"{c['spread_basin_m']:.2f} m (bar <= {split_tol_m:g} m) "
           f"{c['spread_basin_resource']}",
           f"   §14 footless with no footed body in their unit (their own "
           f"authored row, reported not barred): {c['footless_no_carrier']}"]
    for name in c.get("footless_at_datum_names", ()):
        out.append(f"      at datum: {name}")
    for y, name in c.get("footless_on_ground_names", ()):
        out.append(f"      on ground: +{y:.2f} m  {name}")
    for name in c.get("basin_bodies_split_names", ()):
        out.append(f"      basin split: {name}")
    return out


# ── §16: the population, and the ground under the body's own geometry ────

#: §16 (1): the skip classes the AGL switch cannot place, and therefore
#: the only ones a plan may leave outside its population — an ANIM block
#: the cut refuses to straddle, a file no reader parses, a stock library
#: resource (converted, never split).  Matched on the skip's own text,
#: which is the only thing the plan carries.
LAWFUL_SKIPS = ("stock library resource", "unreadable OBJ8", "ANIM",
                "resolves outside the pack", "OBJECT_MSL")
#: §16 (1)'s bar class: the SEAT-era thickness gate (08-26 §2.1).  Under
#: ``placement = agl`` a resource with no genuine solid is a FOOTLESS
#: body, not a skip — left outside the plan it keeps the pack's shared
#: datum row and renders where the datum is (LEMD's garage roof-top
#: pavilions, 15.8 m under the slab).
THICKNESS_SKIP = "no genuine solid component"


def census_population(skipped: _t.Sequence[_t.Sequence[str]]) -> dict:
    """§16 (1), over the REBAKE plan's own ``skipped`` list: how many
    resources are outside the plan population and why.

    ``rows on the datum outside the plan`` is the bar (0) and counts the
    THICKNESS class alone; every other class is reported beside it, named
    — the multi-anchor drop (I-4) is a different law and §16 (1) does not
    name it, so it is reported and never barred."""
    gate: list[str] = []
    lawful: list[str] = []
    other: dict[str, int] = {}
    other_names: dict[str, str] = {}
    for row in skipped:
        res, why = (str(row[0]), str(row[1])) if len(row) > 1 else (str(row[0]), "")
        if why.startswith(THICKNESS_SKIP):
            gate.append(res)
        elif any(k in why for k in LAWFUL_SKIPS):
            lawful.append(res)
        else:
            key = why.split("(")[0].split(":")[0].strip()[:60]
            key = "placed at N anchors — one file cannot carry per-placement " \
                  "offsets" if key.startswith("placed at") else key
            other[key] = other.get(key, 0) + 1
            other_names.setdefault(key, res)
    return {"datum_rows_outside_plan": len(gate),
            "datum_rows_outside_plan_names": gate[:8],
            "lawful_skips": len(lawful),
            "other_skips": dict(sorted(other.items(), key=lambda kv: -kv[1])),
            "other_skip_example": other_names,
            "bars_ok": not gate}


def census_population_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_population`'s bar as the line both tools print."""
    out = [f"   §16 rows on the datum outside the plan (the seat-era "
           f"thickness gate): {c['datum_rows_outside_plan']} (bar 0)"
           + ("" if not c["datum_rows_outside_plan"]
              else "   *** §16 (1) VIOLATED (bar 0) ***"),
           f"   §16 lawful skips (ANIM / unparsable / stock library / outside "
           f"the pack / MSL): {c['lawful_skips']}"]
    for name in c.get("datum_rows_outside_plan_names", ()):
        out.append(f"      outside the plan: {name}")
    for k, v in c.get("other_skips", {}).items():
        out.append(f"      other skip class (reported, not barred): {v}  {k}")
    return out


#: §16 (2)'s reporting threshold for a CARRIED body: how far its carrier's
#: zero may stand from the ground under its own geometry.  11ai measured
#: 54 of LEMD's carried bodies over this.
CARRIED_GROUND_TOL_M = 1.0
#: §16 (4)'s reporting threshold for a FILE: how far the ground under its
#: own geometry may depart from the ground at the row it is placed on.
#: 11ai measured 138 of LEMD's 1,042 files over this.
GEOM_GROUND_TOL_M = 3.0


def census_v16(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
               surface: _t.Callable[[float, float], "float | None"],
               *, carried_tol_m: float = CARRIED_GROUND_TOL_M,
               geom_tol_m: float = GEOM_GROUND_TOL_M) -> dict:
    """§16 (2): the float the EYE reads on the body's OWN GEOMETRY.

    §15 (3) compares a body's zero with the zero of the FOOTED BODY under
    it, which says nothing where there is no body under it — a roof panel
    over bare apron, a pavilion on a garage slab the plan holds no body
    for.  §16 (2) reads the GROUND instead:

        float = zero - ground_under_geometry

    where ``ground_under_geometry`` is the design surface under the
    body's own parts hull (``geom_box``, :func:`ground_at_box`) — never
    the carrier's box, which is exactly how a roof came to ride a fence
    segment 6 m below it.  Two numbers are reported:

    ``carried ground float``  a CARRIED body (its zero is its carrier's)
                              whose carrier's zero stands more than
                              ``carried_tol_m`` from the ground under its
                              own geometry.  §16a (3): INFORMATION ONLY.
                              §16 (3) barred it at 0, and that is the
                              reading 11aj deletes — walls on sloping
                              ground anchor at their low-side foot, so a
                              roof lawfully on its walls reads metres
                              from the ground under itself.  THE BAR for
                              a carried body is §15 (3)'s
                              ``zero - zero_beneath``.
    ``own-geometry ground``   any body whose ground, read under its own
                              geometry, departs more than ``geom_tol_m``
                              from the ground at the row it is placed on
                              (its anchor's) — the body is wider than the
                              terrain it stands on, which §16 (2)'s
                              re-cut exists to close.
    """
    carried: list[tuple[float, str]] = []
    wide: list[tuple[float, str]] = []
    n = off_sheet = 0
    for s in splits:
        for b in s.get("bodies", ()):
            box = b.get("geom_box") or b.get("plan_box")
            sz = b.get("surface_z")
            if not box or sz is None:
                off_sheet += 1
                continue
            # §16b (4): THE WRITTEN GEOMETRY where the plan publishes it
            # — ``geom_box`` is the hull of the PART boxes, which for a
            # carried body the cut left whole is its CARRIER's patch.
            pts = b.get("geom_pts") or ()
            if pts:
                zs = [float(z) for z in
                      (surface(float(q[0]), float(q[1])) for q in pts)
                      if z is not None]
            else:
                fb = tuple(tuple(float(q) for q in x)
                           for x in b.get("foot_boxes", ()) or ())
                zs = ground_samples(surface, fb, tuple(float(q) for q in box))
            if not zs:
                off_sheet += 1
                continue
            g = sorted(zs)[len(zs) // 2]
            n += 1
            zero = float(sz) - float(b.get("y_zero", 0.0))
            res = str(b.get("new_resource") or s.get("placement", {})
                      .get("resource", "?"))
            if b.get("merged_into"):
                d = zero - g
                if abs(d) > carried_tol_m:
                    carried.append((d, res))
            # the ROW this file is placed on is its anchor: the surface
            # there is the height X-Plane drapes its origin to
            d2 = max(abs(z - float(sz)) for z in zs)
            if d2 > geom_tol_m:
                wide.append((d2, res))
    carried.sort(key=lambda q: -abs(q[0]))
    wide.sort(reverse=True)
    return {"bodies_read": n, "off_sheet": off_sheet,
            "carried_ground_gt": len(carried), "carried_worst": carried[:10],
            "geom_ground_gt": len(wide), "geom_worst": wide[:10],
            "carried_tol_m": carried_tol_m, "geom_tol_m": geom_tol_m,
            # §16a (3): neither number is a bar — §15 (3)'s
            # ``zero - zero_beneath`` is THE bar for a carried body
            "bars_ok": True}


#: §16b (4): how far a CARRIED piece's zero may stand from the ground
#: under its OWN WRITTEN GEOMETRY.  The bar is 0 bodies over it: after
#: §16b (1) the piece is no wider than one terrain group, and after
#: §16b (2)/(3) the carrier it rides stands on that same group's ground.
CARRIED_OWN_GROUND_TOL_M = 0.5


def census_v16b(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                surface: _t.Callable[[float, float], "float | None"],
                *, split_tol_m: float,
                float_tol_m: float = CARRIED_OWN_GROUND_TOL_M) -> dict:
    """§16b (4): THE CENSUS READS THE WRITTEN GEOMETRY.

    Every §16 / §16a number was read on the plan's ``geom_box`` — for a
    body the cut left whole that is the box of the patch its CARRIER
    covers (124 m for ``Terminal4_green-TEJ3``, whose written file spans
    2,342 m and reads +16.22 m over the ground at the owner's item 5).
    These two bars are read on the body's own written triangles
    (``geom_pts``, one sample per cell of plan, the lowest thing the file
    puts over that patch), and both are ZERO:

    ``carried piece float over its own ground``  a CARRIED body whose
        zero stands more than ``float_tol_m`` from the ground under its
        OWN geometry.  §16a (3) made this information only because a
        carried body was cut by its carrier and a carrier on sloping
        ground anchors at its low-side foot; §16b (1)'s prior terrain cut
        and §16b (3)'s bounded fallback close that, so it is a bar again.

    ``body wider than its terrain group``  ANY body whose own-geometry
        ground spans more than ``split_tol_m`` — a rigid body wider than
        the terrain it stands on, which is items 1 and 2's class (a sign
        body 2,319 m long, 30 roof plates over 1.8 km).

    A body publishing no ``geom_pts`` (a plan written before §16b) or
    reading no surface under any of them is OFF-SHEET and counted apart,
    never guessed at (§15 (5))."""
    carried: list[tuple[float, str]] = []
    wide: list[tuple[float, str]] = []
    n = off_sheet = no_geom = 0
    span_sum = 0.0
    for s in splits:
        for b in s.get("bodies", ()):
            pts = b.get("geom_pts") or ()
            sz = b.get("surface_z")
            if not pts:
                no_geom += 1
                continue
            if sz is None:
                off_sheet += 1
                continue
            zs = []
            for q in pts:
                z = surface(float(q[0]), float(q[1]))
                if z is not None:
                    zs.append(float(z))
            if not zs:
                off_sheet += 1
                continue
            n += 1
            res = str(b.get("new_resource") or s.get("placement", {})
                      .get("resource", "?"))
            span = max(zs) - min(zs)
            span_sum = max(span_sum, span)
            if span > split_tol_m:
                wide.append((span, res))
            zero = float(sz) - float(b.get("y_zero", 0.0))
            g = sorted(zs)[len(zs) // 2]
            if b.get("merged_into"):
                d = zero - g
                if abs(d) > float_tol_m:
                    carried.append((d, res))
    carried.sort(key=lambda q: -abs(q[0]))
    wide.sort(reverse=True)
    return {"bodies_read": n, "off_sheet": off_sheet, "no_geom_pts": no_geom,
            "carried_own_ground_gt": len(carried),
            "carried_own_ground_worst": carried[:10],
            "geom_span_gt": len(wide), "geom_span_worst": wide[:10],
            "geom_span_max_m": span_sum,
            "float_tol_m": float_tol_m, "split_tol_m": split_tol_m,
            "bars_ok": not carried and not wide}


def census_v16b_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_v16b`'s two bars as the lines both tools print."""
    out = [f"   §16b read on the WRITTEN GEOMETRY of {c['bodies_read']} "
           f"body(ies) ({c['off_sheet']} off-sheet, {c['no_geom_pts']} with no "
           f"geometry published):",
           f"   §16b carried piece float over its OWN ground > "
           f"{c['float_tol_m']:g} m: {c['carried_own_ground_gt']} (bar 0)"
           + ("" if not c["carried_own_ground_gt"]
              else "   *** §16b (4) VIOLATED (bar 0) ***"),
           f"   §16b body wider than its terrain group (own-geometry ground "
           f"spans > {c['split_tol_m']:g} m): {c['geom_span_gt']} (bar 0; "
           f"widest {c['geom_span_max_m']:.2f} m)"
           + ("" if not c["geom_span_gt"]
              else "   *** §16b (4) VIOLATED (bar 0) ***")]
    for d, res in c.get("carried_own_ground_worst", ()):
        out.append(f"      carried {d:+.2f} m over its own ground  {res}")
    for d, res in c.get("geom_span_worst", ()):
        out.append(f"      own ground spans {d:.2f} m  {res}")
    return out


def census_v16_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_v16`'s two numbers as the lines both tools print."""
    out = [f"   §16 float = zero - ground_under_geometry over "
           f"{c['bodies_read']} body(ies) ({c['off_sheet']} off-sheet):",
           f"   §16 CARRIED bodies whose carrier's zero is over "
           f"{c['carried_tol_m']:g} m from the ground under their own "
           f"geometry: {c['carried_ground_gt']} (§16a (3): INFORMATION "
           f"ONLY — the bar for a carried body is §15 (3)'s "
           f"zero - zero_beneath)",
           f"   §16 files whose own-geometry ground departs over "
           f"{c['geom_tol_m']:g} m from the ground at their row: "
           f"{c['geom_ground_gt']} (reported; §16 (2)'s re-cut closes it)"]
    for d, res in c.get("carried_worst", ()):
        out.append(f"      carried {d:+.2f} m over its own ground  {res}")
    for d, res in c.get("geom_worst", ()):
        out.append(f"      own ground {d:.2f} m from the row  {res}")
    return out
