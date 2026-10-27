"""THE LAW AS DATA — typed accessors over the loaded tables.

Every question a generator, emitter or verifier asks of the law is a
function here over a :class:`~auto_patch_v2.law.model.Law`; the answers
come from the TOML tables (owner amendment 2026-09-03) — this module holds
NO numeric value and NO mechanism (plan §1 row 3).  Each accessor's
docstring cites the ruling it serves.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from pathlib import Path

from .model import (Cockpit, Declared, Family, FlatPack, FlatSite, Law, RunwayEnds,
                    RoleCap, ZoneClass, load_tables, resolve_ruleset)
from .reference_code import INSTRUMENT, PRECISION

__all__ = [
    "footprint_touch_m",
    "DEFAULT_LAW_DIR", "load_default", "law_tables_digest", "resolve_ruleset", "role_cap",
    "role_family", "role_side", "is_value_role", "is_rigid_role", "is_structure_role",
    "pavement_roles", "pavement_fallback_cap", "authority_rank",
    "senior_role", "zone_class", "zone2_half_width_m", "zone_bounds", "generator_slack_m",
    "runway_zone_edge_offset_m", "zone_edge_offset_m", "runway_safety_area_length_m",
    "runway_end_zone_length_m", "EndProfile", "runway_end_profile", "end_profile_noise_m", "family", "families_for_role",
    "chord_cap_m", "identity_dp", "input_quantum_m", "materiality_m", "snap_margin_m",
    "gap_standoff_m",
    "Cockpit", "cockpit", "cliff_grade", "rolled_on_roles",
    "is_governed", "governed_roles", "ungoverned_roles", "tiers", "role_tier",
    "role_preferred_cap",
    "runway_transverse_max", "runway_transverse_bound", "runway_shoulder_cap",
    "runway_vertical_curve_bound", "strip_transverse_bound",
    "taxi_half_width_m", "airside_rate_per_m",
    "runway_end_zone_cap", "runway_end_zone_grade_change", "runway_mean_slope_max",
    "flat_site", "flat_datum_group", "flat_declared", "flat_pack", "runway_ends",
    "flat_source_class", "flat_relief_floor_m", "design",
    "design_weight", "sliver_area_factor", "group_span_max_m",
    "bend_class", "apron_roles", "PadAdmission", "pad_admission",
]

#: The DEM source classes the flat-site detector knows (flat_site.toml
#: ``[detector]`` ``relief_floor_m`` keys + the lidar short-circuit).
FLAT_CLASS_LIDAR = "lidar"
FLAT_CLASS_FINE = "fine"
FLAT_CLASS_COARSE = "coarse"

#: The checked-in law directory.
DEFAULT_LAW_DIR: Path = Path(__file__).resolve().parent


def load_default() -> Law:
    """The checked-in tables bound to the default ruleset."""
    tables = load_tables(DEFAULT_LAW_DIR)
    return Law(tables=tables, ruleset_key=tables.resolution.default)


def law_tables_digest(law_dir: str | Path | None = None) -> dict:
    """The law tables a build solves under, hashed — PROVENANCE for the
    harness's ``frame.json``, the tile build's ``[provenance]`` line and
    the artifact-ledger variant key.  Sorted ``name + bytes`` over every
    ``.toml`` under ``law_dir`` (default: the checked-in directory), so a
    reader can name WHICH tables without a checkout.  ``sha256`` is
    ``None`` when the directory holds no table at all — a frozen engine
    whose datas omitted the tables reads as exactly that, never as the
    shipped law."""
    import hashlib
    d = Path(law_dir) if law_dir is not None else DEFAULT_LAW_DIR
    files = sorted(q for q in d.glob("*.toml")) if d.is_dir() else []
    h = hashlib.sha256()
    for q in files:
        h.update(q.name.encode()); h.update(b"\0"); h.update(q.read_bytes()); h.update(b"\0")
    return {"dir": str(d), "files": [q.name for q in files],
            "sha256": h.hexdigest() if files else None}


def group_span_max_m(law: Law) -> float:
    """THE LONG SPAN (owner RULINGS 2026-09-11i; spec §11 (4)) — ONE
    derivation site: ``[placement] group_span_max_m``, the pack-wide
    value at every airport (RULINGS 2026-10-05g (2)).  A group longer
    than this is the HECA railway class: the only group an infeasible
    pad may RELEASE.  0 disarms the exception."""
    return float(law.tables.structures.placement.group_span_max_m)


# ── roles ────────────────────────────────────────────────────────────────

def role_family(law: Law, role: str) -> str:
    """``runway`` / ``taxi`` / ``common`` / ``none`` for ``role``; an
    unregistered role is an error (v2 emits only registered roles)."""
    try:
        return law.tables.precedence.roles[role].family
    except KeyError:
        raise KeyError(f"role {role!r} is not registered in precedence.toml")


def role_side(law: Law, role: str) -> str:
    """The census partition of ``role`` (airside is king, RULINGS :16)."""
    return law.tables.precedence.roles[role].side


def is_value_role(law: Law, role: str) -> bool:
    """Whether faces of ``role`` carry their own graded elevation."""
    return law.tables.precedence.roles[role].value


def is_rigid_role(law: Law, role: str) -> bool:
    """Whether faces of ``role`` are rigid flat groups (pads, 03h)."""
    return bool(getattr(law.tables.precedence.roles[role], "rigid", False))


def is_structure_role(law: Law, role: str) -> bool:
    """Whether faces of ``role`` carry a STRUCTURE datum (precedence.toml
    ``structure = true``): no site-wide preference prices their vertices
    (RULINGS 2026-09-05k-2 amendment)."""
    return bool(getattr(law.tables.precedence.roles[role], "structure", False))


def pavement_roles(law: Law) -> tuple[str, ...]:
    """THE DESIGNED SURFACE ITSELF — every VALUE role that is not a
    structure (RULINGS 2026-09-08t answer 1: the zone ramp measures its
    distance from here and such a vertex never takes a DEM fit).  ONE
    derivation site: ``solve.design.pavement_roles`` delegates here, and
    ``constraints.pads`` reads it to tell the PAVEMENT a pad fronts from
    the pad itself (a rigid role is a value role too)."""
    return tuple(r for r in law.tables.precedence.roles
                 if is_value_role(law, r) and not is_structure_role(law, r))



def pavement_fallback_cap(law: Law) -> float:
    """THE UNIVERSAL PAVEMENT CAP (owner RULINGS 2026-09-29ac, issue #105)
    — ONE derivation site.  The ROAD grade cap, "the steepest cap in the
    law", is the FALLBACK ceiling of every :func:`pavement_roles` class: a
    class cap lower than it still applies, and where none is applied (a
    step, a cliff judged as if welded, a corridor read as ground, an exit
    mouth) this binds.  It is ``[common] road_max_grade`` itself — the
    fallback is a reference to the road cap, never a second copy of it —
    read by the engine's hard row family (``constraints/pavement_cap.py``)
    and the census family ``pavement_over_road_cap`` alike."""
    return float(law.tables.common.road_max_grade)


def bend_class(law: Law, role: str) -> str:
    """The BENDING CLASS of ``role`` (``design_schema.BEND_CLASSES``, RULINGS
    2026-09-08v): ``runway`` / ``taxi`` for the two named families,
    ``road`` for the road cross-section's roles, ``apron`` for every other
    role that carries its own value, ``strip`` for the rest (the graded
    strip, the clearances, the cuts — the ground the blend happens in).

    IT LIVES IN THE LAW LAYER because two packages read it and neither may
    import the other (M0 §1): ``solve/design_roles.py`` prices the bending
    row by it, and ``constraints/apron_trend.py`` forms the apron BODIES it
    fits the ground's 2-D trend under (owner RULINGS 2026-09-10ar).  ``design_roles``
    re-exports both names, so every existing importer is unchanged."""
    if role in law.tables.precedence.runway_family.members:
        return "runway"
    if role in law.tables.precedence.taxi_family.members:
        return "taxi"
    if role in law.tables.families["road_cross_section"].roles:
        return "road"
    return "apron" if is_value_role(law, role) else "strip"


def apron_roles(law: Law) -> frozenset[str]:
    """The roles of an APRON BODY — every role the bending term prices at
    ``bend_apron`` (a value role that is not the runway family, the taxi
    family or the road cross-section).  These are the bodies the PER-BODY
    DATUM sits on (RULINGS 2026-09-09p (3)) and the bodies the 2-D trend
    values (RULINGS 2026-09-10ar); the runway family is excluded because the threshold
    chord and its pins ARE its datum, and a structure's own surface is not
    a body at all."""
    return frozenset(r for r in pavement_roles(law)
                     if bend_class(law, r) == "apron")


def airside_stage_roles(law: Law) -> frozenset[str]:
    """§20b STAGE 1's ROLES — AIRSIDE PAVEMENT (owner RULINGS 2026-09-13dh,
    ordered 2026-09-14an): the runway family, the taxi family and the apron.

    ONE derivation from the law tables, never a hand list: every
    :func:`pavement_roles` role (a VALUE role that is not a structure) whose
    ``role_side`` is ``airside`` and that is not RIGID.  The rigid exclusion
    is the PAD (``building``): a pad is airside by ``role_side`` and is
    exactly what must conform in stage 2.  The strip / clearance / boundary
    family is airside too and is not pavement, so it conforms as well — the
    ground blends to an airside that is already fixed.

    IT LIVES IN THE LAW LAYER because two packages read it and neither may
    import the other (M0 §1): ``solve/design_roles`` splits the staged solve
    by it, and ``constraints/apron_trend`` fits the AIRSIDE apron's trend
    over the airside alone (issue #67).  ``design_roles`` re-exports it."""
    return frozenset(r for r in pavement_roles(law)
                     if role_side(law, r) == "airside"
                     and not is_rigid_role(law, r))


def role_cap(law: Law, role: str, code_number: int | None = None,
             code_letter: str | None = None) -> RoleCap | None:
    """Longitudinal and transverse caps for ``role`` under the airport's
    ruleset (Appendix A §2; RULINGS 2026-08-21b/c/d).  ``None`` for a
    role with no within-shape rule (boundary, walls, strips, cuts)."""
    fam = role_family(law, role)
    rs = law.ruleset
    if fam == "none":
        return None
    if fam == "runway":
        lon = rs.runway.longitudinal.value(code_number, code_letter)
        tr = rs.runway.transverse_max.value(code_number, code_letter)
    elif fam == "taxi":
        lon = rs.taxi.longitudinal.value(code_number, code_letter)
        tr = rs.taxi.transverse.value(code_number, code_letter)
    else:
        return law.tables.common.roles[role]
    if lon is None or tr is None:
        return None
    return RoleCap(longitudinal=lon, transverse=tr)


def role_preferred_cap(law: Law, role: str) -> RoleCap | None:
    """THE PREFERENCE TIER (owner RULINGS 2026-09-06w): the caps ``role``
    PREFERS where its table states two tiers (``common.roles.<role> = {
    preferred, max }`` — the apron and the pad), ``None`` for an untiered
    role.  :func:`role_cap` answers the HARD cap; the generators price
    every apron row hard at it and carry this one as a ``Diff.soft``
    preference."""
    fam = role_family(law, role)
    if fam != "common":
        return None
    rc = law.tables.common.roles.get(role)
    return None if rc is None else rc.preferred


def taxi_half_width_m(law: Law, code_letter: str | None) -> float | None:
    """Half the letter's taxiway pavement width (``rulesets.<authority>.
    taxi.width_m``, Annex 14 §3.9.3 / AC 150/5300-13B by ADG); ``None``
    where the authority states no width.  The law key of round 1 (RULINGS
    2026-09-06t); its corridor reading was withdrawn by 06v.  Read by
    :func:`zone_edge_offset_m`: the taxiway strip is a centreline figure
    (RULINGS 2026-10-15l (1)), reached from the edge past this half-width."""
    tbl = law.ruleset.taxi.width_m
    if tbl is None:
        return None
    w = tbl.value(None, code_letter)
    return None if w is None else float(w) / 2


def airside_rate_per_m(law: Law, role: str, code_letter: str | None = None,
                       turn_cos: float | None = None) -> float:
    """THE AIRSIDE GRADE-CHANGE RATE along a ring of ``role`` (grade change
    per metre; owner RULINGS 2026-10-15l (1), audit row 2): a TAXI-family
    face reads its own letter's vertical curve (``<ruleset>.taxi.curve_k_m``
    — Annex 14 §3.9.9; AC 150/5300-13B §4.14.1 (3)(b)), every other
    airside ring the strip's
    ``arc_rate`` (the runway family's; the apron's is engine-invented,
    audit §3).  ``turn_cos`` is the cosine of the turn at the station: a
    triple turning by more than ``emit.no_step.rate_profile_turn_max_deg``
    is a ring corner, not the taxiway's profile, and keeps the strip rate.
    ONE accessor: the generator (``constraints.no_step.no_step_rate``), v2
    verify (``verify.no_step``) and the census read it."""
    k = law.ruleset.taxi.curve_k_m
    turn = law.tables.emit.no_step.rate_profile_turn_max_deg
    corner = (turn_cos is not None and turn is not None
              and turn_cos < math.cos(math.radians(float(turn))))
    if k is not None and not corner and role_family(law, role) == "taxi":
        km = k.value(None, code_letter)
        if km:
            return float(law.tables.common.vertical_curve_k_grade_unit) / float(km)
    return float(law.ruleset.strip.arc_rate.per_metre)


def runway_end_zone_cap(law: Law, code_number: int | None,
                        code_letter: str | None, cat_ii_iii: bool = False
                        ) -> float | None:
    """The END-ZONE longitudinal cap at one runway END (``<ruleset>.runway.
    end_zone``), or ``None``: at a code in ``end_zone_precision_only_codes``
    (ICAO code 3, Annex 14 §3.1.14: Cat II/III only; audit row 13) only at
    an end the witness reads Cat II/III (``RunwayEnd.cat_ii_iii``, RULINGS
    2026-10-15m (2))."""
    rs = law.ruleset.runway
    cap = rs.end_zone.value(code_number, code_letter)
    if cap is None:
        return None
    if code_number in rs.end_zone_precision_only_codes and not cat_ii_iii:
        return None
    return float(cap)


def runway_end_zone_grade_change(law: Law, code_number: int | None,
                                 code_letter: str | None) -> float | None:
    """The largest grade change inside a runway END ZONE (FAA AC
    150/5300-13B §3.16.1 C/D/E standard 2: none — audit §4 M2), or ``None``
    where the authority states no such rule (the curve bound governs)."""
    t = law.ruleset.runway.end_zone_max_grade_change
    return None if t is None else t.value(code_number, code_letter)


def runway_mean_slope_max(law: Law, code_number: int | None,
                          code_letter: str | None = None) -> float | None:
    """THE MEAN RUNWAY SLOPE cap (Annex 14 §3.1.13; audit §4 M1): the
    highest minus the lowest centreline elevation over the runway length;
    ``None`` where the authority states none (FAA)."""
    t = law.ruleset.runway.mean_slope_max
    return None if t is None else t.value(code_number, code_letter)


def runway_transverse_max(law: Law, code_letter: str | None,
                          code_number: int | None = None) -> float | None:
    """The runway TRANSVERSE MAXIMUM (``rulesets.<authority>.runway
    .transverse_max`` by code letter; ICAO §3.1.18, FAA likewise): the
    steepest lawful fall from the crown ridge to an edge — and, RULINGS
    2026-09-05o, the steepest lawful rise above it.  ``None`` only where
    the authority states no value."""
    return law.ruleset.runway.transverse_max.value(code_number, code_letter)


def runway_shoulder_cap(law: Law, code_letter: str | None,
                        code_number: int | None = None) -> float | None:
    """The SHOULDER's transverse maximum as the table states it
    (``rulesets.<authority>.runway.shoulder_transverse_max``, Annex 14
    §3.2.4; §40 (2) as amended, owner RULINGS 2026-09-13dd), never below
    the runway's own ``transverse_max`` for the code.  Read by
    :func:`runway_transverse_bound` beyond the half-width and by the
    ``runway_step`` allowance (``verify.runway.runway_step``), which keeps
    the table cap (RULINGS 2026-09-30ak)."""
    cap = law.ruleset.runway.transverse_max.value(code_number, code_letter)
    shoulder = law.ruleset.runway.shoulder_transverse_max
    if cap is None:
        return shoulder
    return max(cap, shoulder)


def runway_transverse_bound(law: Law, lateral_m: float, half_width_m: float,
                            code_letter: str | None,
                            code_number: int | None = None,
                            shoulder_cap: float | None = None) -> float | None:
    """THE ONE READING of the lawful transverse fall (or rise, 05o) of a
    runway-family vertex at lateral distance ``d = lateral_m`` from its
    own ridge, in METRES (§40 (2) as amended by 2026-09-13dd; RULINGS
    2026-09-30ak, issue #134):

        bound(d) = cap_rw · min(d, half) + cap_sh · max(0, d − half)

    — the runway's cross-fall (``transverse_max``, §3.1.18) over its own
    half-width, the SHOULDER's (:func:`runway_shoulder_cap`, Annex 14
    §3.2.4, FAA AC 150/5300-13B) only for the distance BEYOND it: the
    shoulder is flush with the runway edge and takes its own slope FROM
    the edge.  CONTINUOUS in ``d`` — the cap it replaces
    (``lateral_m <= half_width_m`` picking one of two slopes for the
    whole ``d``) was a step function, and the generator's planar frame
    and the verify's emitted crown spine, a centimetre apart, priced one
    KASE vertex a fifth of a metre apart (issue #134).  The generator
    (``constraints.runway_profile.runway_transverse``) and the v2 verify
    (``verify.runway.runway_transverse``) both call it; no side predicate.

    ``half_width_m <= 0`` (no runway geometry) prices the whole ``d`` at
    the runway cap; ``None`` where the authority states no runway cap.
    ``shoulder_cap`` replaces the shoulder's slope where a taxi route
    crosses it (owner RULINGS 2026-10-16a (i): the taxiway's law governs
    the pavement it crosses; ``constraints/shoulder_crossing``)."""
    cap = law.ruleset.runway.transverse_max.value(code_number, code_letter)
    if cap is None:
        return None
    d = max(0.0, float(lateral_m))
    if half_width_m <= 0.0 or d <= half_width_m:
        return cap * d
    sh = runway_shoulder_cap(law, code_letter, code_number) if shoulder_cap is None \
        else max(cap, float(shoulder_cap))
    return cap * half_width_m + sh * (d - half_width_m)


def authority_rank(law: Law, role: str) -> int:
    """Precedence rank (lower wins); unnamed roles tail (RULINGS
    2026-08-03 "emitters emit, never grade")."""
    order = law.tables.precedence.order
    return order.index(role) if role in order else len(order)


def senior_role(law: Law, roles: "list[str] | tuple[str, ...]") -> str:
    """The role that owns a value shared by ``roles``."""
    return min(roles, key=lambda r: authority_rank(law, r))


# ── seniority: governed tiers (RULINGS 2026-09-03i, 2026-09-04i, 04q-3) ──

def is_governed(law: Law, role: str, code_number: int | None = None,
                code_letter: str | None = None) -> bool:
    """Whether the law states a grade cap for ``role`` (03i: SENIORITY
    FOLLOWS FROM BEING GOVERNED)."""
    return role_cap(law, role, code_number, code_letter) is not None


def governed_roles(law: Law) -> tuple[str, ...]:
    """The governed tier in the tables' stated order (03i)."""
    reg = law.tables.precedence.roles
    order = law.tables.precedence.order
    gov = [r for r in order if is_governed(law, r)]
    gov += sorted(r for r in reg if r not in order and is_governed(law, r))
    return tuple(gov)


def ungoverned_roles(law: Law) -> tuple[str, ...]:
    """Every registered role with no cap — junior by omission (03i)."""
    return tuple(sorted(r for r in law.tables.precedence.roles
                        if not is_governed(law, r)))


def tiers(law: Law) -> tuple[tuple[str, ...], ...]:
    """THE LAW-ORDERED TIERS (RULINGS 2026-09-04i: "the LAW's priority
    order decides which governed surface yields"), a function of
    ``precedence.toml`` alone — which is why it lives here (04q-3:
    ``solve/`` reads the law, never a generator):

    * tier 0 .. n-2: the GOVERNED, non-rigid roles in ``[authority]
      order``; members of a DECLARED family (``[runway_family]``,
      ``[taxi_family]``) share their family's tier, at the position of
      the family's first member (a runway crossing yields with the
      runway, a stub with the parallel); a governed role the order omits
      follows the named ones, alphabetically (``tunnel_ramp``);
    * tier n-1 (the LAST): every ungoverned role (no cap) and every RIGID
      role (a pad: one flat value levelled by its contact, 03h/03i) —
      junior by omission, so a new capless surface class is junior with no
      code change.

    The solver holds tier 0 HARD and prices tier k ≥ 1 as a preference
    charged ``tier_ratio`` times more than tier k+1 (``solve/tiers.py``).
    """
    p = law.tables.precedence
    fam_of: dict[str, str] = {}
    for name, grp in (("runway_family", p.runway_family), ("taxi_family", p.taxi_family)):
        for r in grp.members:
            fam_of[r] = name
    governed = [r for r in governed_roles(law) if not is_rigid_role(law, r)]
    out: list[list[str]] = []
    fam_tier: dict[str, int] = {}
    for r in governed:
        fam = fam_of.get(r)
        if fam is not None and fam in fam_tier:
            out[fam_tier[fam]].append(r)
            continue
        if fam is not None:
            fam_tier[fam] = len(out)
        out.append([r])
    last = sorted(r for r in p.roles if r not in governed)
    out.append(last)
    return tuple(tuple(t) for t in out)


def role_tier(law: Law, role: str) -> int:
    """The tier index of ``role`` (see :func:`tiers`)."""
    for k, t in enumerate(tiers(law)):
        if role in t:
            return k
    raise KeyError(f"role {role!r} is not registered in precedence.toml")


# ── adjacent-ground zones (RULINGS 2026-08-01) ───────────────────────────

def zone_class(law: Law, role: str) -> ZoneClass | None:
    """The zone-2 class next to a face of ``role``: runway family or taxi
    family; other roles have no graded strip."""
    fam = role_family(law, role)
    ag = law.tables.zones.adjacent_ground
    if fam == "runway":
        return ag.runway
    if fam == "taxi":
        return ag.taxi
    return None


def zone2_half_width_m(law: Law, role: str, code_number: int | None = None,
                       code_letter: str | None = None, status: int = 0) -> float | None:
    """Zone 2's half-width FROM THE CENTRELINE (the table figure): runway
    strips key by code number (ICAO) or the FAA RSA table (FAA); taxi strips
    by letter (ICAO Annex 14 §3.11.4 graded portion; FAA AC 150/5300-13B
    §4.5.3 TSA).  Beyond it is zone 3 = the DEM.  The zone's reach from the
    PAVEMENT EDGE is :func:`zone_edge_offset_m`.

    ``status`` is the runway's instrument status (``reference_code.
    runway_status``; #811): ICAO reads §3.4.8's instrument table on an
    instrument runway, FAA App. G's "lower than 3/4 mile" table on a
    precision one; a class without the table reads its own."""
    zc = zone_class(law, role)
    if zc is None:
        return None
    if law.ruleset.authority == "FAA" and zc.half_width_faa_m is not None:
        return _by_status(zc.half_width_faa_m, zc.half_width_faa_precision_m,
                          status, code_number, code_letter, at=PRECISION)
    return _by_status(zc.half_width_m, zc.half_width_instrument_m,
                      status, code_number, code_letter)


def runway_zone_edge_offset_m(law: Law, code_number: int | None,
                              code_letter: str | None, runway_half_m: float,
                              status: int = 0) -> float | None:
    """THE RUNWAY ZONE'S OUTER EDGE, as an offset from the PAVEMENT EDGE
    (owner RULINGS 2026-10-15c (1) "From the centreline"): the zone-2
    half-width is a CENTRELINE figure (``zones.toml`` FAA RSA by letter,
    ICAO strip by code), so the band reaches ``max(lip_width_m, half-width
    − runway_half_m)`` beyond the edge — never less than the lip.  Before
    the ruling the band was buffered by the whole half-width from the edge
    (KBJC 12L: wider than its RSA by the runway's width).  ``None`` where
    the class states no strip.  ``status``: :func:`zone2_half_width_m`'s."""
    hw = zone2_half_width_m(law, "runway", code_number, code_letter, status)
    if hw is None:
        return None
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    return max(lip, float(hw) - max(0.0, float(runway_half_m)))


def zone_edge_offset_m(law: Law, role: str, code_number: int | None = None,
                       code_letter: str | None = None,
                       pavement_half_m: float | None = None,
                       status: int = 0) -> float | None:
    """THE ZONE'S OUTER EDGE as an offset from the PAVEMENT EDGE — the ONE
    accessor every reader of a zone's reach goes through (spec
    ``regulation-conformance-20261015`` §2.A).  Both families state the
    zone-2 half-width from the CENTRELINE (:func:`zone2_half_width_m`), so
    the band reaches ``max(lip_width_m, half-width − pavement half-width)``:

    * runway family — :func:`runway_zone_edge_offset_m` over the runway's own
      ``pavement_half_m`` (``None``: 0, the centreline figure, an upper bound
      for a caller that does not know the runway);
    * taxi family — the taxiway's pavement half-width is the LETTER's
      (``rulesets.<authority>.taxi.width_m`` / 2, :func:`taxi_half_width_m`;
      RULINGS 2026-10-15l (1), audit row 3: Annex 14 §3.11.4, AC §4.5.3).
      ``pavement_half_m`` overrides it.

    ``None`` where the role has no graded strip or the class states none.
    ``status``: the runway's instrument status (:func:`zone2_half_width_m`;
    the taxi family states none)."""
    fam = role_family(law, role)
    if fam == "runway":
        return runway_zone_edge_offset_m(law, code_number, code_letter,
                                         pavement_half_m or 0.0, status)
    hw = zone2_half_width_m(law, role, code_number, code_letter)
    if hw is None:
        return None
    pave = pavement_half_m if pavement_half_m is not None else (
        taxi_half_width_m(law, code_letter) or 0.0)
    lip = float(law.tables.zones.adjacent_ground.lip_width_m)
    return max(lip, float(hw) - max(0.0, float(pave)))


def runway_safety_area_length_m(law: Law, code_number: int | None = None,
                                code_letter: str | None = None,
                                status: int = 0) -> float:
    """THE GRADED AREA'S LENGTH beyond each runway end, measured from the
    runway END with the blast pad inside it (owner RULINGS 2026-10-15c (2)
    "Full safety-area length"): FAA — the RSA length by design group
    (``[faa.end_skirt] rsa_length_m``: AC 150/5300-13B App. G dim R through
    the letter proxy); ICAO — the strip's end length plus the RESA
    (``strip.end_length_m`` + ``end_skirt.corridor_length_m``; Annex 14
    §3.5.3 measures the RESA from the strip's end; master 2026-10-15 Q1),
    each read BY CODE AND INSTRUMENT STATUS (RULINGS 2026-10-15k (1);
    ``status`` is the runway's ``reference_code.runway_status`` — the FAA
    length on a precision runway is App. G's "lower than 3/4 mile", #811;
    a ``bool`` instrument flag reads as status 0 / 1)."""
    rs = law.ruleset
    sk = rs.end_skirt
    if sk.rsa_length_m is not None:
        v = _by_status(sk.rsa_length_m, sk.rsa_length_precision_m, status,
                       code_number, code_letter, at=PRECISION)
        if v:
            return float(v)
    strip_end = _by_status(rs.strip.end_length_m, rs.strip.end_length_instrument_m,
                           status, code_number, code_letter) or 0.0
    resa = _by_status(sk.corridor_length_m, sk.corridor_length_instrument_m,
                      status, code_number, code_letter) or 0.0
    return float(strip_end) + float(resa)


def _by_status(table, status_table, status: int,
               code_number: int | None, code_letter: str | None,
               at: int = INSTRUMENT) -> float | None:
    """A value the standard states by INSTRUMENT STATUS (RULINGS
    2026-10-15k; #811): ``status_table`` on a runway whose status
    (``reference_code.runway_status``; a ``bool`` reads 0 / 1) reaches
    ``at`` — instrument, or precision — where the ruleset carries one,
    else the table itself; ``None`` with neither."""
    t = status_table if int(status) >= at and status_table is not None else table
    return None if t is None else t.value(code_number, code_letter)


def zone_bounds(law: Law, role: str, d_m: float,
                code_number: int | None = None,
                code_letter: str | None = None,
                band_max_down: float | None = None,
                half_m: float | None = None,
                status: int = 0
                ) -> tuple[float | None, float | None]:
    """Signed ``(floor, ceiling)`` offset from the pavement-edge elevation
    at lateral distance ``d_m`` — the accumulated two-zone corridor, or
    ``(None, None)`` in zone 3 (the DEM, never graded).  Pure arithmetic
    over the tables; this is the ONE derivation site of the corridor
    (RULINGS 2026-08-30l: trim at the derivation, not per consumer).

    ``band_max_down`` overrides the class's zone-2 fall: §37 (11) (7)'s
    NATURAL shore falls at up to the bank slope (owner RULINGS
    2026-09-27a (7)); the lip and the ceiling are unchanged.  ``status``:
    the runway's instrument status, read where ``half_m`` is not given
    (:func:`zone2_half_width_m`)."""
    ag = law.tables.zones.adjacent_ground
    zc = zone_class(law, role)
    # ``half_m``: the zone's outer bound FROM THE EDGE where the caller knows
    # the pavement (a runway's :func:`runway_zone_edge_offset_m`); the table
    # half-width otherwise
    half = half_m if half_m is not None else zone2_half_width_m(
        law, role, code_number, code_letter, status)
    if zc is None or half is None or d_m > half:
        return (None, None)
    faa = law.ruleset.authority == "FAA"
    # THE LIP BY AUTHORITY (audit row 9): the FAA taxiway lip is 5 +/- 0.5 %
    # (AC §4.14.2 item 4) where the class states it; the shared lip else
    lip_lo = zc.lip_min_down_faa if faa and zc.lip_min_down_faa is not None else ag.lip_min_down
    lip_hi = zc.lip_max_down_faa if faa and zc.lip_max_down_faa is not None else ag.lip_max_down
    lip = min(d_m, ag.lip_width_m)
    floor = -lip_hi * lip
    ceil = -lip_lo * lip
    band = max(0.0, d_m - ag.lip_width_m)
    # THE BAND BY AUTHORITY (RULINGS 2026-10-15l (2) / (4); ``zones.toml``):
    # FAA falls 1.5 % to the AAC's maximum (Table 3-6 S-3); ICAO is bounded
    # in MAGNITUDE only where the class states a rise (Annex 14 §3.4.15)
    if faa and zc.band_max_down_faa is not None:
        bmax = zc.band_max_down_faa.value(code_number, code_letter)
    else:
        bmax = zc.band_max_down.value(code_number, code_letter)
    rise = None if faa or zc.band_max_up is None else zc.band_max_up.value(code_number, code_letter)
    if band_max_down is not None:
        bmax = max(float(band_max_down), bmax or 0.0)
    if band > 0 and bmax is not None:
        floor -= bmax * band
        ceil = ceil + rise * band if rise is not None else ceil - zc.band_min_down * band
    return (floor, ceil)


def runway_vertical_curve_bound(law: Law, spacing_m: float,
                                code_number: int | None = None,
                                code_letter: str | None = None) -> float | None:
    """THE VERTICAL-CURVE BOUND (RULINGS 2026-09-06b law 1; spec
    ``heca-read-20260906-spec.md`` §2): the largest lawful change of
    grade (a fraction) between two consecutive runway profile chords
    whose mean spacing is ``spacing_m`` — ``min(max_grade_change,
    spacing / vertical_curve_k_m × common.vertical_curve_k_grade_unit)``
    by code (Annex 14 §3.1.15/16: K is metres per 1 % of change), raised
    to ``vertical_curve_min_change`` where the authority states that no
    curve is needed under it (FAA AAC A/B).  ``None`` where the authority
    states neither number."""
    rs = law.ruleset.runway
    mgc = rs.max_grade_change.value(code_number, code_letter)
    k = rs.vertical_curve_k_m.value(code_number, code_letter)
    bound: float | None = mgc
    if k is not None and k > 0.0:
        kb = spacing_m / k * law.tables.common.vertical_curve_k_grade_unit
        bound = kb if bound is None else min(bound, kb)
    if bound is None:
        return None
    if rs.vertical_curve_min_change is not None:
        mc = rs.vertical_curve_min_change.value(code_number, code_letter)
        if mc is not None:
            bound = max(bound, mc)
    return bound


def strip_transverse_bound(law: Law, d_m: float, code_number: int | None = None,
                           code_letter: str | None = None,
                           half_m: float | None = None) -> float | None:
    """THE STRIP TIE (RULINGS 2026-09-06b law 2; spec §3): how far (m) a
    graded-strip vertex ``d_m`` off a runway-family edge may stand from
    the edge, EITHER way — the runway zone class's own transverse cap
    accumulated over the corridor (``zones.adjacent_ground.lip_max_down``
    over zone 1, ``zones.adjacent_ground.runway.band_max_down`` by code
    over zone 2: the magnitude of :func:`zone_bounds`' floor, the ONE
    derivation site of the corridor, 08-30l).  ``None`` in zone 3."""
    floor, _ceil = zone_bounds(law, "runway", d_m, code_number, code_letter,
                               half_m=half_m)
    return None if floor is None else -floor


@_dc.dataclass(frozen=True)
class EndProfile:
    """THE GROUND BEYOND A RUNWAY END as ONE profile keyed by the distance
    ``d`` (m) beyond the pavement end along the extended centre line
    (owner RULINGS 2026-10-12q (1) (a)-(c); audit
    ``docs/findings/runway-end-law-audit-20261012.md``).  The ONE
    derivation the planar break, the generator, the verify reader and the
    harness census all read:

    * ``segments``: the FALLING side — ``(length_m, max_down)`` in order,
      the last with an infinite length.  ICAO: the strip's own cap over
      ``strip.end_length_m`` then the RESA's ``end_skirt.max_down_grade``;
      FAA: the near-end 3 % over ``end_skirt.near_zone_m`` then 5 %.
    * ``hold_m``: the RISING side is held to ZERO this far (FAA §3.16.5
      item 2 "any slope being downward"; 0 where no such rule).
    * ``climb_slope`` / ``climb_setback_m``: beyond ``hold_m`` the ground
      may not stand above the take-off climb / departure surface with NO
      tail height (``[<ruleset>.eat]``; the master's note on (c)).
      ``None`` = the authority states no surface: rising ground unbound.
    * ``approach``: the end's APPROACH SURFACES (owner RULINGS
      2026-10-15m (1); FAA only) as ``(slope, inner edge beyond the END)``
      — the inner edge is the table's distance from the threshold less the
      end's displaced length.  The rising side is held under the LOWEST of
      them and the climb surface.
    * ``rate``: grade change per metre, FAA only (``rate_provisional``
      false); ``None`` where the text is qualitative (ICAO).
    * ``break_m``: where the first segment ends — the planar stage breaks
      the zone-2 end band there so both slopes are expressible.
    """

    segments: tuple[tuple[float, float], ...]
    hold_m: float
    climb_slope: float | None
    climb_setback_m: float
    rate: float | None
    approach: tuple[tuple[float, float], ...] = ()
    #: the THRESHOLD's height over the end (``model.threshold_datum``):
    #: every approach surface starts at the threshold's elevation
    approach_datum_m: float = 0.0

    @property
    def break_m(self) -> float | None:
        if len(self.segments) < 2:
            return None
        return self.segments[0][0]

    def fall_m(self, d_m: float) -> float:
        """How far BELOW the runway end the ground may stand at ``d_m``."""
        d = max(0.0, float(d_m))
        out = 0.0
        for length, cap in self.segments:
            take = min(d, length)
            out += take * cap
            d -= take
            if d <= 0.0:
                break
        return out

    def rise_m(self, d_m: float) -> float | None:
        """How far ABOVE the runway end the ground may stand at ``d_m``;
        ``None`` = unbound (no climb surface in the table)."""
        d = max(0.0, float(d_m))
        if d <= self.hold_m:
            return 0.0
        lims = [max(0.0, d - edge) * slope + self.approach_datum_m
                for slope, edge in self.approach]
        if self.climb_slope is not None:
            lims.append(max(0.0, d - self.climb_setback_m) * self.climb_slope)
        return min(lims) if lims else None

    def down_cap_at(self, d_m: float) -> float:
        """The down-grade cap in force at ``d_m`` (the segment's)."""
        d = max(0.0, float(d_m))
        for length, cap in self.segments:
            if d < length:
                return cap
            d -= length
        return self.segments[-1][1]


def runway_end_profile(law: Law, code_number: int | None = None,
                       code_letter: str | None = None,
                       instrument: bool = False,
                       approach_class: str | None = None,
                       displaced_m: float = 0.0,
                       datum_m: float = 0.0) -> EndProfile:
    """:class:`EndProfile` for a runway of this class under the law's
    ruleset — the strip's end length (by code and instrument status,
    RULINGS 2026-10-15k (1)) and cap where the authority states them, else
    the end skirt's near zone; the skirt's max down-grade beyond; the climb
    surface from the ruleset's ``eat`` table BY CODE (15k (2)); and, for
    the END whose ``approach_class`` (``RunwayEnd.approach``) and displaced
    threshold length are given, the authority's approach surfaces for that
    class (``end_skirt.approach_surface``, RULINGS 2026-10-15m (1); audit
    row 5), its inner edge at the THRESHOLD's elevation (``datum_m`` =
    z_thr - z_end, ``model.threshold_datum``).  ``approach_class=None``
    reads no approach surface (a reader with no published class)."""
    rs = law.ruleset
    sk = rs.end_skirt
    segs: list[tuple[float, float]] = []
    hold = 0.0
    end_len = _by_status(rs.strip.end_length_m, rs.strip.end_length_instrument_m,
                         instrument, code_number, code_letter)
    strip_cap = rs.strip.longitudinal.value(code_number, code_letter)
    if end_len and strip_cap is not None:
        segs.append((float(end_len), float(strip_cap)))
    elif sk.near_zone_m and sk.near_max_down_grade is not None:
        segs.append((float(sk.near_zone_m), float(sk.near_max_down_grade)))
        hold = float(sk.near_zone_m)
    segs.append((math.inf, float(sk.max_down_grade)))
    eat = rs.eat
    rate = None if sk.rate_provisional else sk.rate.per_metre
    surfaces = (sk.approach_surface or {}).get(str(approach_class), ()) \
        if approach_class is not None else ()
    disp = max(0.0, float(displaced_m or 0.0))
    return EndProfile(tuple(segs), hold,
                      None if eat is None else float(eat.slope.value(code_number, code_letter)),
                      0.0 if eat is None else float(eat.setback_m.value(code_number, code_letter)),
                      rate,
                      tuple((float(a.slope), float(a.from_threshold_m) - disp) for a in surfaces),
                      float(datum_m or 0.0) if surfaces else 0.0)


def end_profile_noise_m(law: Law, *, reader: bool = False) -> float:
    """THE RUNWAY-END PROFILE'S TOLERANCE — the ONE key
    ``emit.instrument.strip_edge_noise_m`` (#620: the owner's open choice
    between today's value and pricing the first strip length at the cap
    exactly, which is this key at 0).  A READER (``reader=True``) forgives
    the key itself, never less than the per-node rounding a pair of
    emitted altitudes carries; the GENERATOR prices its rows with the key
    less that same rounding envelope, never below zero — the envelope
    the solver's held residual (``design.hard_tol_m``) and the two emitted
    altitudes' rounding are sized under, so a row the solve holds at its
    tolerance reads inside the reader's forgiveness.  Less the materiality
    floor alone, a row held at the solver's tolerance read as a breach
    (lane rwyzone15c phase 4, measured at CYXY: two end pairs held within
    the tolerance read a few millimetres over the reader's bound)."""
    ins = law.tables.emit.instrument
    if reader:
        return max(float(ins.strip_edge_noise_m), float(ins.rounding_noise_m))
    return generator_slack_m(law, float(ins.strip_edge_noise_m))


def generator_slack_m(law: Law, reader_allowance_m: float) -> float:
    """THE GENERATOR'S SLACK under a reader's allowance (lane rwyzone15c
    phases 4 / 8): the allowance less ``emit.instrument.rounding_noise_m``,
    never below zero.  That envelope is what the solver's held residual
    (``design.hard_tol_m``) and two emitted altitudes' rounding are sized
    under, so a row the solve holds at its tolerance reads inside the
    reader's allowance.  Less the materiality floor alone, rows the solve
    held a few centimetres over the generator's bound read as breaches
    (CYXY: the end profile).  ONE helper for every family that prices its
    rows this way.  NOT applied to the strip's longitudinal / arc rows:
    their residuals are strip ground far under the visual tolerance
    (owner RULINGS 2026-09-12y, restated on #763 phase 8)."""
    return max(0.0, float(reader_allowance_m) - float(law.tables.emit.instrument.rounding_noise_m))


def runway_end_zone_length_m(law: Law, runway_length_m: float) -> float:
    """Length of each runway end zone: the fraction of length, bounded by
    the authority's absolute cap when it states one (FAA 762 m)."""
    rw = law.ruleset.runway
    n = runway_length_m * rw.end_zone_fraction
    if rw.end_zone_max_length_m is not None:
        n = min(n, rw.end_zone_max_length_m)
    return n


# ── families ─────────────────────────────────────────────────────────────

def family(law: Law, key: str) -> Family:
    """One registered law family."""
    return law.tables.families[key]


def families_for_role(law: Law, role: str) -> tuple[Family, ...]:
    """Every family whose ``roles`` covers ``role`` (by name, by side,
    by family group, or ``all``)."""
    p = law.tables.precedence
    words = {role, "all", p.roles[role].side}
    if role in p.taxi_family.members:
        words.add("taxi_family")
    if role in p.runway_family.members:
        words.add("runway_family")
    return tuple(f for f in law.tables.families.values()
                 if words & set(f.roles))


# ── emit constants ───────────────────────────────────────────────────────

def chord_cap_m(law: Law, role: str) -> float:
    """Maximum ring chord for ``role``: the apron interior spacing for
    aprons (RULINGS 2026-08-24b/c), the pavement cap otherwise."""
    ch = law.tables.emit.chords
    if role == "apron":
        return min(ch.pavement_max_chord_m, ch.apron_interior_spacing_m)
    return ch.pavement_max_chord_m


def identity_dp(law: Law) -> int:
    """Decimal places of the canonical lat/lon identity key."""
    return law.tables.emit.identity.coordinate_dp


def input_quantum_m(law: Law) -> float:
    """§46 (4) THE INPUT QUANTUM: the grid a coordinate entering the
    airport's metric frame from OUTSIDE is snapped to, once, at
    :meth:`~...model.frame.Frame.entry`.  ``0.0`` disables it (a
    measurement arm only)."""
    return float(law.tables.emit.identity.input_quantum_m)


def snap_margin_m(law: Law) -> float:
    """The identity snap's half-diagonal: how far a vertex can move when
    the planar build snaps it to the ``min_distinct_spacing_m`` lattice.
    A stand-off that must hold AFTER the snap (the pad set-back, the zone
    band's groundside cut-back — RULINGS 2026-09-04u, lot 87) is applied
    as its law value PLUS this margin (measured CYXY: a set-back gap
    narrower than the lattice diagonal noded to one shared vertex; a pad
    knife carrying the margin beside a zone cut-back without it left a
    sub-metre zone sliver whose noding minted a cross_shape pair)."""
    return law.tables.emit.identity.min_distinct_spacing_m * math.sqrt(2) / 2


def gap_standoff_m(law: Law) -> float:
    """THE STAND-OFF of a gap piece from a standing cell it does not weld to
    (spec §53 (12)): the pad set-back + the snap margin + one identity cell.
    ONE derivation, here because the mint (``classify/gap_mint``) and the
    follow reach beside a pad (``constraints/gap_follow.reach_m``, spec §62
    (3) rule 1) both read it and neither layer may import the other."""
    return float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law) + float(law.tables.emit.identity.min_distinct_spacing_m)


def materiality_m(law: Law) -> float:
    """The elevation residual floor (owner 2026-08-02)."""
    return law.tables.emit.materiality.elevation_m


def cockpit(law: Law) -> Cockpit:
    """THE COCKPIT FRAME (owner RULINGS 2026-09-12x/12y; design-surface-spec
    §31, object-placement-spec §17) — ONE derivation site for the three
    numbers every census's COCKPIT block classifies with.

    ``tools/check_grade.py`` (and through it the harness census and the
    pytest fixtures) and the object stage's placement censuses all read
    HERE.  A second copy of those three numbers anywhere — this docstring
    included — is the census-wrapper defect applied to a reading rule."""
    return law.tables.emit.cockpit


def cliff_grade(law: Law) -> float:
    """§31 (7) THE CLIFF (owner RULINGS 2026-09-12af) — ONE derivation site.

    A SPANNED step-family row is a slope and is REPORT (12ad); a row whose
    implied grade ``|dz| / span`` exceeds THIS is a CUT or a RISE and comes
    back as the defect it is.  The number is not written in ``[cockpit]``:
    that key holds a DOTTED LAW PATH at the design surface's own bank slope
    — "an embankment / cut slope a pilot reads as ground, not a wall", the
    steepest thing this engine builds as natural ground — and this resolves
    it.  Change the bank and the cliff line follows; there is no second
    copy to forget."""
    from .cockpit_schema import value_at
    return float(value_at(law.tables, law.tables.emit.cockpit.cliff_grade))


def frontage_roles(law: Law) -> frozenset[str]:
    """THE FACES A BUILDING PAD FRONTS — every AIRSIDE pavement an aircraft
    rolls on (:func:`rolled_on_roles`: the runway and taxi families, the
    apron and its stands), ONE accessor for the platform mint
    (``planar/platform.platform_split``) and the flat-pad block planner
    (``planar/pad_blocks.plan_blocks``).  Until 2026-10-02 (issue #223) the
    planner read ``apron_roles`` alone while the mint read every rolled-on
    role, so SPJC ``building14`` — fronting pav40's JUNCTION cell, the
    apron body 57 m away — minted a platform the planner never held (the
    29 s contact-led tilt, half a percent — the figure is spelled out
    because this file carries no numerals a reader could mistake for law:
    see ``test_no_numeric_literal_in_law_python_still_holds``)."""
    return rolled_on_roles(law)


def rolled_on_roles(law: Law) -> frozenset[str]:
    """THE SURFACES THE AIRCRAFT ROLLS ON (§31 (1)), derived from
    ``precedence.toml`` — never a literal list.

    The runway family and the taxi family by their own registers, plus the
    APRON-class bodies that are AIRSIDE and not RIGID: that is the apron
    itself and its stands (a stand is apron pavement in v2's role register).
    A rigid role is a PAD, not pavement — a building floor is not something
    an aircraft rolls on — and the groundside apron-class roles (service
    road, service junction, groundside pavement, car park) are landside by
    ``role_side``, which §31 (3) rules VISUAL ONLY.

    A new pavement role added to ``precedence.toml`` joins this set with no
    code change; a new rigid or groundside class stays out of it."""
    p = law.tables.precedence
    out = set(p.runway_family.members) | set(p.taxi_family.members)
    out |= {r for r in apron_roles(law)
            if role_side(law, r) == "airside" and not is_rigid_role(law, r)}
    return frozenset(out)


# ── the flat-site datum (RULINGS 2026-09-05k-2) ──────────────────────────

def flat_site(law: Law) -> FlatSite:
    """flat_site.toml: the detector's constants, the datum's pricing and
    the declared register."""
    return law.tables.flat_site


def flat_pack(law: Law) -> FlatPack:
    """flat_pack.toml: the flat-pack witness's constants and the terrace
    phase gate (owner direction 2026-10-20, answers 59-66)."""
    return law.tables.flat_pack


def runway_ends(law: Law) -> RunwayEnds:
    """runway_ends.toml: THE RUNWAY-END PIN RULE's tolerances and the
    cross-check order (owner RULINGS 2026-10-25a / 26a / 26e)."""
    return law.tables.runway_ends


def flat_datum_group(law: Law) -> str:
    """The ``Weights.preference`` group the datum rows ride in (below the
    law ladder, above the seam — ``[datum] preference``)."""
    return law.tables.flat_site.datum.preference


def flat_declared(law: Law, icao: str) -> Declared | None:
    """The owner's declaration for ``icao`` (option (c)), or ``None`` —
    the ONE declared register; the tile-cfg keys are retired."""
    return law.tables.flat_site.declared.get(str(icao or "").strip().upper())


def flat_source_class(law: Law, pixel_m: float | None) -> str | None:
    """The DEM source class of a pixel size: ``lidar`` at or under
    ``lidar_credible_max_m`` (never flat by statistics), ``fine`` at or
    under ``fine_source_max_m``, ``coarse`` above; ``None`` = unknown
    pixel (the base tier, whose 1- and 3-arcsec postings are both coarse,
    is stated by the caller as :data:`FLAT_CLASS_COARSE`)."""
    if pixel_m is None:
        return None
    det = law.tables.flat_site.detector
    p = float(pixel_m)
    if not p > 0.0:
        return None
    if p <= det.lidar_credible_max_m:
        return FLAT_CLASS_LIDAR
    if p <= det.fine_source_max_m:
        return FLAT_CLASS_FINE
    return FLAT_CLASS_COARSE


def flat_relief_floor_m(law: Law, source_class: str | None) -> float | None:
    """S2's p95−p5 floor for a source class; ``None`` for lidar (the
    short-circuit) and for an unknown class."""
    rf = law.tables.flat_site.detector.relief_floor_m
    if source_class == FLAT_CLASS_FINE:
        return rf.fine
    if source_class == FLAT_CLASS_COARSE:
        return rf.coarse
    return None


# ── the priority model (RULINGS 2026-09-08d; spec heca-v1-parity) ─────────

def design(law: Law):
    """``emit.toml [design]``: THE DESIGN SURFACE's objective weights
    (owner RULINGS 2026-09-08t; ``solve/design.py``)."""
    return law.tables.emit.design


def design_weight(law: Law, term: str) -> float:
    """The weight of one objective term (``law/design_schema.DESIGN_TERMS``)."""
    return law.tables.emit.design.weight(term)


def sliver_area_factor(law: Law) -> float:
    """``emit.toml [terrace] sliver_area_factor`` (08d change 4 (a))."""
    return float(law.tables.emit.terrace.sliver_area_factor)


def groundside_ramp_max(law: Law) -> float:
    """``emit.toml [terrace] groundside_ramp_max`` (08d change 4 (b))."""
    return float(law.tables.emit.terrace.groundside_ramp_max)


@_dc.dataclass(frozen=True)
class PadAdmission:
    """§16g (10) (12): the four ``[placement]`` numbers the two PAD-ADMISSION
    gates are judged at (issue #101, owner RULINGS 2026-10-02v (3)) — ONE
    reading, so the MINT (``classify/evidence._cluster_pads``) and the CENSUS
    (``constraints/cluster_pad.cluster_polys``) cannot be judging a cluster at
    different thresholds.  ``geom/cluster_outlines`` takes this; the
    MEASUREMENT's own two keys (``tall_member_min_extent_m``, and the same two
    evidence numbers) are read by ``planar/cluster.clusters`` where the
    cluster is derived."""

    min_tall_base_fill: float
    building_evidence: bool
    evidence_min_height_m: float
    evidence_min_coverage: float

    @property
    def armed(self) -> bool:
        return self.min_tall_base_fill > 0.0 or self.building_evidence


def pad_admission(law: Law) -> PadAdmission:
    """``structures.toml [placement]``'s pad-admission gates — ONE
    derivation site."""
    p = law.tables.structures.placement
    return PadAdmission(
        min_tall_base_fill=float(getattr(p, "min_tall_base_fill", 0.0)),
        building_evidence=bool(getattr(p, "building_evidence", False)),
        evidence_min_height_m=float(getattr(p, "evidence_min_height_m", 0.0)),
        evidence_min_coverage=float(getattr(p, "evidence_min_coverage", 0.0)))


class SlabLaw(_t.NamedTuple):
    """The base-slab witness's law values (``[placement] base_slab_*``;
    ``geom/base_slab`` reads them duck-typed, like :class:`PadAdmission`)."""

    max_height_m: float
    base_y_max_m: float
    min_m2: float
    open_min_share: float
    tall_min_m: float
    touch_m: float
    #: OWNER-PENDING (lane slab229 report): the slab's open part also leaves
    #: the pads it lies under.  Off, a slab is pavement only where no pad
    #: stands (the measured HECA pad moves of the ON arm await the owner).
    leaves_pads: bool = False
    #: owner RULINGS 2026-10-14d (lane drape229): the PLATE witness — at
    #: most this share of a slab component's face area is SIDE faces
    #: (``[placement] base_slab_max_side_share``; 0 disarms)
    max_side_share: float = 0.0
    #: ...the drape side's LEVEL plate: its up-facing faces' authored y
    #: range within this (``[placement] split_tol_m``, the foot tolerance;
    #: 0 admits nothing that touches no wall)
    level_m: float = 0.0
    #: ...and CLEARLY A LOT OR ROAD: its open piece holds a disc this wide
    #: (``emit.road_profile.lane_width_m``, the gap mint's own floor)
    lane_m: float = 0.0
    #: what makes a face a PLATE face (``[bridge]
    #: deck_plate_normal_y_min``, the near-horizontal normal)
    plate_ny_min: float = 0.0
    #: rule 7 (issue #669): an up face stands CLEAR of the slab's foot this
    #: high (``[bridge] deck_min_elevation_m``)...
    deck_elev_m: float = 0.0
    #: ...and a slab with more than this share of its up-facing area
    #: clear is an ELEVATED DECK, never draped
    #: (``[placement] base_slab_elevated_share_max``; 0 disarms)
    elevated_share_max: float = 0.0

    @property
    def armed(self) -> bool:
        return self.min_m2 > 0.0 and self.max_height_m > 0.0


def base_slab_law(law: "Law | None") -> SlabLaw:
    """``structures.toml [placement] base_slab_*`` — the base-slab witness
    (``geom.base_slab``; owner RULINGS 2026-10-10o (B), issue #229) — ONE
    derivation site: the pad mint, the pad census and the gap mint read
    it.  No law in hand (a reader called without one) is the DISARMED
    witness: no slab is read."""
    if law is None:
        return SlabLaw(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)
    p = law.tables.structures.placement
    return SlabLaw(
        max_height_m=float(getattr(p, "base_slab_max_height_m", 0.0)),
        base_y_max_m=float(getattr(p, "base_slab_base_y_max_m", 0.0)),
        min_m2=float(getattr(p, "base_slab_min_m2", 0.0)),
        open_min_share=float(getattr(p, "base_slab_open_min_share", 0.0)),
        tall_min_m=float(p.chain_min_height_m),
        touch_m=float(p.footprint_touch_m),
        leaves_pads=bool(getattr(p, "base_slab_leaves_pads", False)),
        max_side_share=float(getattr(p, "base_slab_max_side_share", 0.0)),
        level_m=float(p.split_tol_m),
        lane_m=float(law.tables.emit.road_profile.lane_width_m),
        plate_ny_min=float(law.tables.structures.bridge.deck_plate_normal_y_min),
        deck_elev_m=float(law.tables.structures.bridge.deck_min_elevation_m),
        elevated_share_max=float(getattr(p, "base_slab_elevated_share_max", 0.0)))


def footprint_touch_m(law: Law) -> float:
    """§16g (7) (1) / (10) (2): ``[placement] footprint_touch_m`` — ONE
    read of the tolerance a cluster is CHAINED with and its outline is
    CLOSED with (``geom.cluster_outlines`` rule 2)."""
    return float(law.tables.structures.placement.footprint_touch_m)
