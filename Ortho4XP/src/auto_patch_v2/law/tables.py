"""THE LAW AS DATA — typed accessors over the loaded tables.

Every question a generator, emitter or verifier asks of the law is a
function here over a :class:`~auto_patch_v2.law.model.Law`; the answers
come from the TOML tables (owner amendment 2026-09-03) — this module holds
NO numeric value and NO mechanism (plan §1 row 3).  Each accessor's
docstring cites the ruling it serves.
"""
from __future__ import annotations

import math

from pathlib import Path

from .model import (Declared, Family, FlatSite, Law, RoleCap, ZoneClass,
                    load_tables, resolve_ruleset)

__all__ = [
    "DEFAULT_LAW_DIR", "load_default", "law_tables_digest", "resolve_ruleset", "role_cap",
    "role_family", "role_side", "is_value_role", "is_rigid_role", "is_structure_role", "authority_rank",
    "senior_role", "zone_class", "zone2_half_width_m", "zone_bounds",
    "runway_end_zone_length_m", "family", "families_for_role",
    "chord_cap_m", "identity_dp", "materiality_m", "snap_margin_m",
    "is_governed", "governed_roles", "ungoverned_roles", "tiers", "role_tier",
    "tier_of_roles",
    "runway_transverse_max",
    "flat_site", "flat_datum_group", "flat_datum_weight", "flat_declared",
    "flat_source_class", "flat_relief_floor_m",
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


def runway_transverse_max(law: Law, code_letter: str | None,
                          code_number: int | None = None) -> float | None:
    """The runway TRANSVERSE MAXIMUM (``rulesets.<authority>.runway
    .transverse_max`` by code letter; ICAO §3.1.18, FAA likewise): the
    steepest lawful fall from the crown ridge to an edge — and, RULINGS
    2026-09-05o, the steepest lawful rise above it.  ``None`` only where
    the authority states no value."""
    return law.ruleset.runway.transverse_max.value(code_number, code_letter)


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


def tier_of_roles(roles: "tuple[str, ...] | list[str]", tier_of: "dict[str, int]",
                  lowest: int) -> int:
    """The tier a VALUE shared by ``roles`` belongs to: the most SENIOR
    (smallest) tier among them, ``lowest`` when there are none — a shared
    vertex is owned by its senior surface (``senior_role``)."""
    best = lowest
    for r in roles:
        k = tier_of[r]
        if k < best:
            best = k
    return best


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
                       code_letter: str | None = None) -> float | None:
    """Outer bound of zone 2 from the pavement edge.  Runway strips key
    by code number (ICAO) or the FAA RSA table (FAA); taxi strips by
    letter.  Beyond it is zone 3 = the DEM."""
    zc = zone_class(law, role)
    if zc is None:
        return None
    if law.ruleset.authority == "FAA" and zc.half_width_faa_m is not None:
        return zc.half_width_faa_m.value(code_number, code_letter)
    return zc.half_width_m.value(code_number, code_letter)


def zone_bounds(law: Law, role: str, d_m: float,
                code_number: int | None = None,
                code_letter: str | None = None
                ) -> tuple[float | None, float | None]:
    """Signed ``(floor, ceiling)`` offset from the pavement-edge elevation
    at lateral distance ``d_m`` — the accumulated two-zone corridor, or
    ``(None, None)`` in zone 3 (the DEM, never graded).  Pure arithmetic
    over the tables; this is the ONE derivation site of the corridor
    (RULINGS 2026-08-30l: trim at the derivation, not per consumer)."""
    ag = law.tables.zones.adjacent_ground
    zc = zone_class(law, role)
    half = zone2_half_width_m(law, role, code_number, code_letter)
    if zc is None or half is None or d_m > half:
        return (None, None)
    lip = min(d_m, ag.lip_width_m)
    floor = -ag.lip_max_down * lip
    ceil = -ag.lip_min_down * lip
    band = max(0.0, d_m - ag.lip_width_m)
    bmax = zc.band_max_down.value(code_number, code_letter)
    if band > 0 and bmax is not None:
        floor -= bmax * band
        ceil -= zc.band_min_down * band
    return (floor, ceil)


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


def materiality_m(law: Law) -> float:
    """The elevation residual floor (owner 2026-08-02)."""
    return law.tables.emit.materiality.elevation_m


# ── the flat-site datum (RULINGS 2026-09-05k-2) ──────────────────────────

def flat_site(law: Law) -> FlatSite:
    """flat_site.toml: the detector's constants, the datum's pricing and
    the declared register."""
    return law.tables.flat_site


def flat_datum_group(law: Law) -> str:
    """The ``Weights.preference`` group the datum rows ride in (below the
    law ladder, above the seam — ``[datum] preference``)."""
    return law.tables.flat_site.datum.preference


def flat_datum_weight(law: Law) -> float:
    """The charge per metre of relief of one datum row (``[datum] weight``)."""
    return law.tables.flat_site.datum.weight


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
