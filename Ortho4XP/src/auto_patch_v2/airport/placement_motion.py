"""§17 CRITICAL MOTION, object stage (owner RULINGS 2026-09-12am (2);
``object-placement-spec.md`` §17, ``design-surface-spec.md`` §31 (1)).

Owner, 12y: "Pavement 0.05 m ... any step or ridge over 5 cm on runway,
taxiway or apron is critical".  §17 says the same of an OBJECT that
STANDS ON that pavement — a sign, a light, a marker, a stand's gear: the
aircraft rolls where it stands, so its float or burial is judged at
``[cockpit] motion_step_m`` and not at the 0.5 m the eye needs.

Until 12am the object stage could not read this at all (12ad/12ak: "the
object stage cannot read motion — no pavement role per body").  What was
missing was ONE reading, and it is here: the ROLE of the graded face
under each FOOT (``placement_boxes.GradedRoles``, built from the same
parsed ``<ICAO>.graded.json`` the surface sampler is built from), joined
to §7's own float at that foot.  Nothing else is new — the float is
:func:`foot_float`, the one expression §7's feet census and this module
both call, so the two instruments cannot drift.

THE POPULATION is every WRITTEN body's ground-contact feet within the
foot band (``[basin] contact_band_m``, the band the plan itself picks a
part's feet with — §7's own scope).  A body with at least one foot on a
ROLLED-ON face (``law.tables.rolled_on_roles``, derived from
``precedence.toml``) is ON PAVEMENT; that body's feet ON PAVEMENT are
judged at the motion threshold, and its feet on grass, on a pad or on no
face at all are not (they are §7's and §31 (3)'s, visual only).

This module exists apart from ``placement_census`` for the 1,000-line
file law, as §16c (5)'s seams do and §17's classification does; all three
are re-exported through ``placement_census``, the census front door.
"""
from __future__ import annotations

import typing as _t

__all__ = ["foot_float", "feet_in_band", "ground_contact_feet",
           "census_motion", "census_motion_lines", "MotionBody"]


class MotionBody(_t.TypedDict, total=False):
    """One written body as this census reads it — the projection every
    caller can build from what it already holds (a ``Body`` record, or a
    plan row plus the pack's own feet)."""

    res: str
    cls: str
    anchor_lat: float
    anchor_lon: float
    anchor_z: "float | None"
    y_zero: float
    feet: _t.Sequence[_t.Tuple[float, float, float]]


def foot_float(z_foot: float, z_anchor: float, y_foot: float,
               y_zero: float = 0.0) -> float:
    """§7's ONE reading of a foot, signed.

        float = surface(foot) - (surface(anchor) + y_foot - y_zero)

    An AGL placement's origin lands on the surface under its ANCHOR, so
    the foot renders at ``surface(anchor) + y_foot - y_zero``.  The sign
    is the read (memory ``band-lawful-displacement`` / the skirt law):
    POSITIVE is the ground standing OVER the foot — BURIED, and on
    pavement that is a ridge the nose gear meets; NEGATIVE is the foot
    standing over its ground — FLOATING, the defect the eye reads."""
    return float(z_foot) - (float(z_anchor) + float(y_foot) - float(y_zero))


def feet_in_band(feet: _t.Sequence[_t.Tuple[float, float, float]],
                 band_m: float) -> list:
    """A body's GROUND-CONTACT feet: those within ``band_m`` of its own
    lowest foot (``[basin] contact_band_m``).  §7's own scope, in one
    place, because a census over a different population than the report
    beside it is the census-wrapper defect (CLAUDE.md)."""
    fs = list(feet or ())
    if not fs:
        return []
    floor = min(f[2] for f in fs)
    return [f for f in fs if f[2] - floor <= float(band_m)]


def ground_contact_feet(feet: _t.Sequence[_t.Tuple[float, float, float]],
                        band_m: float, contact_tol_m: float) -> list:
    """(B), owner RULINGS 2026-09-12ap: THE FEET §17 JUDGES A BODY AT.

    ``[basin] contact_band_m`` (1 m) is the band the PLAN picks a part's
    feet with, and it is shared law that stays as it is — but a metre is
    a storey of authored model.  12ap measured the difference: of the 561
    feet §17 read as floating over the visual threshold on the 1.0.320
    LEMD frame, **360** were vertices standing at their own AUTHORED
    height over a body that is correctly seated — a sign panel, a
    handrail, a canopy lip inside the metre.  The model authored them
    there; nothing in the placement put them there, and reading them as
    float measures the pack.

    What TOUCHES THE GROUND is the narrower set: the in-band feet within
    ``[placement] split_tol_m`` of the body's LOWEST foot — the same
    tolerance the cut already treats as one ground.  ``contact_tol_m``
    above ``band_m`` reads as the band itself (the band is the outer
    scope; this only ever narrows it)."""
    fs = feet_in_band(feet, band_m)
    tol = float(contact_tol_m)
    if not fs or tol <= 0.0 or tol >= float(band_m):
        return fs
    floor = min(f[2] for f in fs)
    return [f for f in fs if f[2] - floor <= tol]


def census_motion(bodies: _t.Sequence[_t.Mapping[str, _t.Any]],
                  surface, roles, *,
                  rolled_on: _t.AbstractSet[str],
                  motion_step_m: float,
                  band_m: float,
                  visual_m: float = 0.5,
                  contact_tol_m: float = 0.0,
                  exempt_classes: _t.AbstractSet[str] = frozenset(),
                  want_rows: bool = False,
                  top: int = 10) -> dict:
    """§17: every written body's feet, and what the graded face under
    each of them IS.

    ``surface`` is the design surface (``surface(lat, lon)``, with the
    vectorised ``surface.many`` used when it has one — the same sampler
    the plan was built on, never a second one); ``roles`` answers
    ``roles_many(lats, lons)`` with the SENIOR face role under each point
    (:class:`placement_boxes.GradedRoles`).

    ``exempt_classes`` are body classes whose feet are authored off
    their own zero BY CONSTRUCTION and are therefore counted apart, never
    as motion: the BASIN class, whose zero is its RIM (§14 (2)) and whose
    floor feet are authored the pit's depth below it — the same exemption
    §16a (2) grants it as a carrier (RULINGS 2026-09-11al).  Reading a
    pit floor as "7.69 m of motion on the apron" measures the law.

    Returns the count of bodies ON PAVEMENT, the feet over
    ``motion_step_m`` on such a face (CRITICAL MOTION), the worst by
    absolute height with resource / coordinate / role / sign, the same by
    resource, and the population lines a report needs (feet read, feet
    off-sheet, bodies whose anchor reads no surface)."""
    rolled = frozenset(rolled_on)
    step = float(motion_step_m)
    vis = float(visual_m)
    las: list[float] = []
    los: list[float] = []
    ys: list[float] = []
    owner: list[int] = []
    rows = []
    n_band = 0
    contact: list[bool] = []
    for b in bodies:
        za = b.get("anchor_z")
        _all = b.get("feet") or ()
        # BOTH SETS ARE SAMPLED, ONE IS JUDGED.  (B) narrows §17's
        # judgement to the ground-contact feet; the wider band is still
        # READ, so the report can say in its own numbers how much of the
        # old count was the model's authored relief and how much the
        # placement's — the attribution 12ap had to take by hand.
        fsb = feet_in_band(_all, band_m)
        fs = ground_contact_feet(_all, band_m, contact_tol_m)
        _floor = min((f[2] for f in fsb), default=0.0)
        _tol = (float(band_m) if contact_tol_m <= 0.0
                else min(float(contact_tol_m), float(band_m)))
        n_band += len(fsb)
        i = len(rows)
        rows.append({"res": str(b.get("res") or "?"),
                     "cls": str(b.get("cls") or ""),
                     "why": str(b.get("reason") or ""),
                     "za": None if za is None else float(za),
                     "y0": float(b.get("y_zero") or 0.0),
                     "n_feet": len(fs)})
        if want_rows:
            rows[i].update({
                "anchor_lat": float(b.get("anchor_lat") or 0.0),
                "anchor_lon": float(b.get("anchor_lon") or 0.0),
                "feet": []})
        if za is None:
            continue
        for f in fsb:
            las.append(float(f[0]))
            los.append(float(f[1]))
            ys.append(float(f[2]))
            owner.append(i)
            contact.append(f[2] - _floor <= _tol)
    many = getattr(surface, "many", None)
    zs = (list(many(las, los)) if many is not None
          else [surface(la, lo) for la, lo in zip(las, los)])
    rls = roles.roles_many(las, los)

    on_pav: set[int] = set()
    over: list[tuple] = []
    feet_pav = 0
    feet_off = 0
    by_res: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_cls: dict[str, int] = {}
    by_why: dict[str, int] = {}
    exempt_feet = 0
    exempt_bodies: set[int] = set()
    buried = floated = 0
    # §31 (3) beside §17: what the EYE reads at a foot on pavement.  A
    # foot the ground stands OVER is BURIED and invisible; a foot ABOVE
    # its ground FLOATS, and 11e (2)'s low-side rule trades the second
    # for the first BY CONSTRUCTION.  Any rule that moves an anchor has
    # to be read against this pair, or it buys a motion count with a
    # visible hovering object.
    vis_float = vis_buried = 0
    bands: dict[str, int] = {}
    # THE COUNTERFACTUAL (§17 step 3, "measure before adopting"): the
    # floats of every body ALL of whose in-band feet stand on rolled-on
    # pavement, kept per body so the MEDIAN-anchor arm can be read
    # without re-running the plan.  Anchoring a body at the median of its
    # feet shifts every one of its floats by that median — the pavement
    # is graded flat to 1.5 %, so 5 cm of burial one side and 5 cm of
    # float the other reads better than 10 cm of float on the high side.
    per_body: dict[int, list[float]] = {}
    all_pav: dict[int, bool] = {}
    band_float = band_buried = band_feet = 0
    for k, i in enumerate(owner):
        z = zs[k]
        r = rows[i]
        role = None if z is None else rls[k]
        if want_rows:
            r["feet"].append({
                "lat": las[k], "lon": los[k], "y": ys[k],
                "z": None if z is None else float(z),
                "role": None if role is None else str(role),
                "pav": role in rolled, "contact": bool(contact[k]),
                "d": (None if z is None else
                      foot_float(z, r["za"], ys[k], r["y0"]))})
        if z is None:
            if contact[k]:
                feet_off += 1
            continue
        if role not in rolled:
            if contact[k]:
                all_pav[i] = False
            continue
        # the WIDE reading, for the attribution line only: what the same
        # float over the whole 1 m band says.  (B)'s own difference.
        if rows[i]["cls"] not in exempt_classes:
            band_feet += 1
            _dw = foot_float(z, r["za"], ys[k], r["y0"])
            if _dw > vis:
                band_buried += 1
            elif -_dw > vis:
                band_float += 1
        if not contact[k]:
            continue
        all_pav.setdefault(i, True)
        feet_pav += 1
        on_pav.add(i)
        d = foot_float(z, r["za"], ys[k], r["y0"])
        per_body.setdefault(i, []).append(d)
        if r["cls"] in exempt_classes:
            if abs(d) > step:
                exempt_feet += 1
                exempt_bodies.add(i)
            continue
        if abs(d) > step:
            over.append((abs(d), d, r["res"], las[k], los[k], str(role),
                         r["cls"]))
            by_res[r["res"]] = by_res.get(r["res"], 0) + 1
            by_role[str(role)] = by_role.get(str(role), 0) + 1
            by_cls[r["cls"] or "?"] = by_cls.get(r["cls"] or "?", 0) + 1
            why = (r["why"] or "?").split("(")[0].strip() or "?"
            by_why[why] = by_why.get(why, 0) + 1
            a = abs(d)
            key = ("0.05-0.1" if a <= 0.1 else "0.1-0.3" if a <= 0.3
                   else "0.3-1" if a <= 1.0 else ">1")
            bands[key] = bands.get(key, 0) + 1
            if d > 0:
                buried += 1
                vis_buried += 1 if d > vis else 0
            else:
                floated += 1
                vis_float += 1 if -d > vis else 0
    med_feet = med_bodies = med_pop_bodies = med_pop_feet = 0
    now_feet = 0
    worst_now: list[float] = []
    worst_med: list[float] = []
    for i, ds in per_body.items():
        if not all_pav.get(i) or rows[i]["cls"] in exempt_classes:
            continue
        med_pop_bodies += 1
        med_pop_feet += len(ds)
        now_feet += sum(1 for d in ds if abs(d) > step)
        q = sorted(ds)
        m = (q[len(q) // 2] if len(q) % 2
             else 0.5 * (q[len(q) // 2 - 1] + q[len(q) // 2]))
        n = sum(1 for d in ds if abs(d - m) > step)
        med_feet += n
        med_bodies += 1 if n else 0
        worst_now.append(max(abs(d) for d in ds))
        worst_med.append(max(abs(d - m) for d in ds))
    over.sort(key=lambda q: (-q[0], q[2]))
    bodies_over = sorted({q[2] for q in over})
    return {"ruling": "2026-09-12am (2)",
            "motion_step_m": step,
            "band_m": float(band_m),
            "contact_tol_m": float(contact_tol_m),
            "feet_in_band": n_band,
            "band_feet_on_pavement": band_feet,
            "band_float_gt_visual": band_float,
            "band_buried_gt_visual": band_buried,
            "rows": tuple(rows) if want_rows else (),
            "rolled_on": tuple(sorted(rolled)),
            "bodies_read": len(rows),
            "bodies_off_sheet": sum(1 for r in rows if r["za"] is None),
            "feet_read": len(owner),
            "feet_off_sheet": feet_off,
            "bodies_on_pavement": len(on_pav),
            "feet_on_pavement": feet_pav,
            "motion_feet_gt": len(over),
            "motion_bodies_gt": len(bodies_over),
            "motion_buried": buried,
            "motion_floating": floated,
            "worst": tuple(over[:top]),
            "by_resource": tuple(sorted(by_res.items(),
                                        key=lambda q: (-q[1], q[0]))[:top]),
            "by_role": tuple(sorted(by_role.items(),
                                    key=lambda q: (-q[1], q[0]))),
            "by_class": tuple(sorted(by_cls.items(),
                                     key=lambda q: (-q[1], q[0]))),
            "by_anchor_reason": tuple(sorted(by_why.items(),
                                             key=lambda q: (-q[1], q[0]))),
            "exempt_classes": tuple(sorted(exempt_classes)),
            "visual_m": vis,
            "float_gt_visual": vis_float,
            "buried_gt_visual": vis_buried,
            "bands": tuple(sorted(bands.items())),
            # the median-anchor arm, over the bodies the fix would touch
            "median_arm_bodies": med_pop_bodies,
            "median_arm_feet": med_pop_feet,
            "median_arm_now_gt": now_feet,
            "median_arm_feet_gt": med_feet,
            "median_arm_bodies_gt": med_bodies,
            "median_arm_worst_now_m": (round(max(worst_now), 3)
                                       if worst_now else 0.0),
            "median_arm_worst_med_m": (round(max(worst_med), 3)
                                       if worst_med else 0.0),
            "median_arm_worst_sum_now_m": round(sum(worst_now), 1),
            "median_arm_worst_sum_med_m": round(sum(worst_med), 1),
            "median_arm_worst_gt_now": sum(1 for q in worst_now if q > step),
            "median_arm_worst_gt_med": sum(1 for q in worst_med if q > step),
            "exempt_feet_gt": exempt_feet,
            "exempt_bodies_gt": len(exempt_bodies),
            "bars_ok": not over}


def census_motion_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_motion`'s reading as the lines both tools print."""
    out = [f"   §17 bodies STANDING ON rolled-on pavement: "
           f"{c['bodies_on_pavement']} of {c['bodies_read']} written body(ies) "
           f"({c['feet_on_pavement']} foot(feet) of {c['feet_read']} on "
           f"{'/'.join(c['rolled_on'])}; {c['feet_off_sheet']} foot(feet) "
           f"off-sheet, {c['bodies_off_sheet']} body(ies) whose anchor reads "
           f"no surface)",
           f"   §17 judged at the GROUND-CONTACT feet ((B), RULINGS "
           f"2026-09-12ap): within {c.get('contact_tol_m', 0):g} m of the "
           f"body's lowest foot — {c['feet_read']} of "
           f"{c.get('feet_in_band', c['feet_read'])} foot(feet) inside "
           f"[basin] contact_band_m {c['band_m']:g} m (shared law, "
           f"unchanged); a vertex authored higher inside the metre is the "
           f"MODEL's relief, not a placement float",
           f"   §17 CRITICAL MOTION (> {c['motion_step_m']:g} m at a foot on "
           f"pavement): {c['motion_feet_gt']} foot(feet) on "
           f"{c['motion_bodies_gt']} body(ies) — {c['motion_buried']} buried, "
           f"{c['motion_floating']} floating"]
    for a, d, res, la, lo, role, cls in c.get("worst", ()):
        out.append(f"      motion {d:+.2f} m  {res}  at {la:.7f},{lo:.7f} "
                   f"on {role} ({cls or 'body'})")
    if c.get("by_resource"):
        out.append("   §17 by resource: " + ", ".join(
            f"{n}x {r}" for r, n in c["by_resource"]))
    if c.get("by_role"):
        out.append("   §17 by face role: " + ", ".join(
            f"{n}x {r}" for r, n in c["by_role"]))
    if c.get("float_gt_visual") is not None:
        out.append(f"   §17 of those, what the EYE reads at the foot "
                   f"(> {c.get('visual_m', 0.5):g} m): FLOATING "
                   f"{c['float_gt_visual']} (a visible gap), BURIED "
                   f"{c['buried_gt_visual']} (invisible, 11e (2)'s own trade)")
    if c.get("band_feet_on_pavement"):
        out.append(
            f"   §17 (B)'s own difference — the SAME float read at every "
            f"in-band vertex, not only the ground-contact feet: "
            f"{c['band_feet_on_pavement']} foot(feet) on pavement, over "
            f"{c.get('visual_m', 0.5):g} m FLOATING "
            f"{c['band_float_gt_visual']} and BURIED "
            f"{c['band_buried_gt_visual']}; the difference from the judged "
            f"counts above is the MODEL's authored relief inside the metre, "
            f"never a placement float")
    if c.get("bands"):
        out.append("   §17 by size: " + ", ".join(
            f"{n} in {b} m" for b, n in c["bands"]))
    if c.get("median_arm_bodies"):
        out.append(
            f"   §17 the MEDIAN-anchor arm (bodies whose feet ALL stand on "
            f"rolled-on pavement): {c['median_arm_bodies']} body(ies), "
            f"{c['median_arm_feet']} foot(feet) — over the threshold now "
            f"{c['median_arm_now_gt']}, anchored at the MEDIAN of their feet "
            f"{c['median_arm_feet_gt']} on {c['median_arm_bodies_gt']} "
            f"body(ies); the WORST foot per body: max "
            f"{c.get('median_arm_worst_now_m', 0):.2f} -> "
            f"{c.get('median_arm_worst_med_m', 0):.2f} m, summed "
            f"{c.get('median_arm_worst_sum_now_m', 0):.1f} -> "
            f"{c.get('median_arm_worst_sum_med_m', 0):.1f} m, bodies whose "
            f"worst is over the threshold "
            f"{c.get('median_arm_worst_gt_now', 0)} -> "
            f"{c.get('median_arm_worst_gt_med', 0)}")
    if c.get("by_class"):
        out.append("   §17 by body class: " + ", ".join(
            f"{n}x {r}" for r, n in c["by_class"]))
    if c.get("by_anchor_reason"):
        out.append("   §17 by anchor rule: " + ", ".join(
            f"{n}x {r}" for r, n in c["by_anchor_reason"]))
    if c.get("exempt_classes"):
        out.append(f"   §17 EXEMPT by construction "
                   f"({'/'.join(c['exempt_classes'])}: the zero is the RIM "
                   f"and the floor feet are authored below it, §14 (2) / "
                   f"RULINGS 2026-09-11al): {c.get('exempt_feet_gt', 0)} "
                   f"foot(feet) on {c.get('exempt_bodies_gt', 0)} body(ies) "
                   f"over the threshold, counted apart")
    return out
