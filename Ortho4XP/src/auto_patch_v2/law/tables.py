"""THE LAW AS DATA — typed accessors over the loaded tables.

Every question a generator, emitter or verifier asks of the law is a
function here over a :class:`~auto_patch_v2.law.model.Law`; the answers
come from the TOML tables (owner amendment 2026-09-03) — this module holds
NO numeric value and NO mechanism (plan §1 row 3).  Each accessor's
docstring cites the ruling it serves.
"""
from __future__ import annotations

from pathlib import Path

from .model import (Family, Law, RoleCap, ZoneClass, load_tables,
                    resolve_ruleset)

__all__ = [
    "DEFAULT_LAW_DIR", "load_default", "resolve_ruleset", "role_cap",
    "role_family", "role_side", "is_value_role", "authority_rank",
    "senior_role", "zone_class", "zone2_half_width_m", "zone_bounds",
    "runway_end_zone_length_m", "family", "families_for_role",
    "chord_cap_m", "identity_dp", "materiality_m",
]

#: The checked-in law directory.
DEFAULT_LAW_DIR: Path = Path(__file__).resolve().parent


def load_default() -> Law:
    """The checked-in tables bound to the default ruleset."""
    tables = load_tables(DEFAULT_LAW_DIR)
    return Law(tables=tables, ruleset_key=tables.resolution.default)


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


def authority_rank(law: Law, role: str) -> int:
    """Precedence rank (lower wins); unnamed roles tail (RULINGS
    2026-08-03 "emitters emit, never grade")."""
    order = law.tables.precedence.order
    return order.index(role) if role in order else len(order)


def senior_role(law: Law, roles: "list[str] | tuple[str, ...]") -> str:
    """The role that owns a value shared by ``roles``."""
    return min(roles, key=lambda r: authority_rank(law, r))


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


def materiality_m(law: Law) -> float:
    """The elevation residual floor (owner 2026-08-02)."""
    return law.tables.emit.materiality.elevation_m
