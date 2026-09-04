"""THE LAW — typed schema and loader for the ``law/*.toml`` tables.

RULINGS 2026-09-03d: v2's ``law/`` is v2's own single source, cross-validated
against v1's census; owner amendment 2026-09-03: the VALUES live in
human-editable TOML, never in Python.  This module holds the SHAPE of the
law (frozen dataclasses, one per table) and the loader that validates the
files — unknown key, missing required key, non-numeric cap, unit sanity,
a family pointing at a parameter that does not exist — and fails loudly.
No numeric value appears here.

Dependency direction: ``law`` imports nothing from the rest of v2.
"""
from __future__ import annotations

import collections.abc as _abc
import dataclasses as _dc
import tomllib
import types as _types
import typing as _t
from pathlib import Path

__all__ = [
    "LawError", "CodeTable", "Rate", "RoleCap", "RunwayLaw", "TaxiLaw",
    "StripLaw", "EndSkirtLaw", "ResaLaw", "RaoaLaw", "DrainageLaw",
    "Ruleset", "CommonLaw", "Resolution", "ZoneClass", "AdjacentGround",
    "Pockets", "Zones", "Tunnel", "Bridge", "BuildingPad", "Basin",
    "RetainingWall", "Structures", "Chords", "Identity", "Materiality",
    "NoStep", "EmitLaw", "RoleSpec", "Authority", "RoleGroup", "Precedence",
    "Family", "LawTables",
    "Law", "TABLE_FILES", "load_tables",
]

#: The six files a law directory must contain (owner amendment 2026-09-03).
TABLE_FILES: tuple[str, ...] = (
    "rulesets.toml", "zones.toml", "structures.toml", "emit.toml",
    "precedence.toml", "families.toml",
)


class LawError(ValueError):
    """A law table is malformed.  The message names file, key path and
    the rule violated; nothing is ever defaulted around it."""


# ── leaf value types ─────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class CodeTable:
    """A value keyed by aerodrome reference code NUMBER (1-4) or code
    LETTER (A-F).  Exactly one of ``by_code`` / ``by_letter`` is set.  A
    class absent from the table means the authority states no number
    (``value()`` returns ``None`` there only when ``default`` is None)."""

    by_code: _t.Mapping[int, float] | None = None
    by_letter: _t.Mapping[str, float] | None = None
    default: float | None = None

    def value(self, code_number: int | None = None,
              code_letter: str | None = None) -> float | None:
        """The class' value, or ``default`` when the class is unkeyed."""
        if self.by_code is not None:
            if code_number is None:
                return self.default
            return self.by_code.get(int(code_number), self.default)
        if self.by_letter is not None:
            if not code_letter:
                return self.default
            return self.by_letter.get(str(code_letter).upper(), self.default)
        return self.default


@_dc.dataclass(frozen=True)
class Rate:
    """A grade-change rate: ``grade`` per ``per_m`` metres."""

    grade: float
    per_m: float

    @property
    def per_metre(self) -> float:
        """The rate as grade change per metre."""
        return self.grade / self.per_m


@_dc.dataclass(frozen=True)
class RoleCap:
    """A role's grade caps (fractions)."""

    longitudinal: float
    transverse: float


# ── rulesets.toml ────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class RunwayLaw:
    """Runway longitudinal / end-zone / curve / transverse law."""

    longitudinal: CodeTable
    end_zone: CodeTable
    end_zone_fraction: float
    max_grade_change: CodeTable
    vertical_curve_k_m: CodeTable
    transverse_max: CodeTable
    transverse_min: float
    end_zone_precision_only_codes: frozenset[int] = frozenset()
    end_zone_max_length_m: float | None = None
    vertical_curve_min_change: CodeTable | None = None


@_dc.dataclass(frozen=True)
class TaxiLaw:
    """Taxiway-family longitudinal and transverse law."""

    longitudinal: CodeTable
    transverse: CodeTable
    transverse_min: float


@_dc.dataclass(frozen=True)
class StripLaw:
    """Graded runway strip: abeam slope and its rate of change."""

    longitudinal: CodeTable
    arc_rate: Rate
    arc_rate_provisional: bool


@_dc.dataclass(frozen=True)
class EndSkirtLaw:
    """Ground beyond the runway end."""

    max_down_grade: float
    rate: Rate
    rate_provisional: bool
    near_zone_m: float | None = None
    near_max_down_grade: float | None = None


@_dc.dataclass(frozen=True)
class ResaLaw:
    """End-corridor transverse law."""

    transverse_max: float
    transverse_near_min: CodeTable | None = None
    transverse_near_max: CodeTable | None = None


@_dc.dataclass(frozen=True)
class RaoaLaw:
    """Radio-altimeter operating area (ICAO only)."""

    length_m: float
    half_width_m: float
    max_grade_change: Rate


@_dc.dataclass(frozen=True)
class DrainageLaw:
    """Drainage minimum; both ``None`` = the authority states none."""

    apron_min_grade: float | None = None
    apron_max_grade_change: float | None = None


@_dc.dataclass(frozen=True)
class Ruleset:
    """One authority's tables."""

    name: str
    authority: str
    runway: RunwayLaw
    taxi: TaxiLaw
    strip: StripLaw
    end_skirt: EndSkirtLaw
    resa: ResaLaw
    drainage: DrainageLaw
    raoa: RaoaLaw | None = None
    key: str = ""


@_dc.dataclass(frozen=True)
class CommonLaw:
    """Authority-independent caps."""

    roles: _t.Mapping[str, RoleCap]
    apron_fan_ramp_max: float
    road_transverse_axis_min_deg: float
    runway_crown_transverse: float


@_dc.dataclass(frozen=True)
class Resolution:
    """How an ICAO identifier selects its ruleset (owner 2026-08-02)."""

    default: str
    faa_first_letters: tuple[str, ...]
    faa_two_letter_prefixes: tuple[str, ...]


# ── zones.toml ───────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class ZoneClass:
    """Zone-2 geometry for one pavement family."""

    half_width_m: CodeTable
    band_min_down: float
    band_max_down: CodeTable
    half_width_faa_m: CodeTable | None = None


@_dc.dataclass(frozen=True)
class AdjacentGround:
    """The two graded zones and the DEM beyond (RULINGS 2026-08-01)."""

    beyond_zone2: str
    lip_width_m: float
    lip_min_down: float
    lip_max_down: float
    ungraded_max_up: float
    runway: ZoneClass
    taxi: ZoneClass


@_dc.dataclass(frozen=True)
class Pockets:
    """Enclosed pockets between graded zones."""

    fill: bool
    drainage_spine: bool


@_dc.dataclass(frozen=True)
class Zones:
    """zones.toml."""

    adjacent_ground: AdjacentGround
    pockets: Pockets


# ── structures.toml ──────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Tunnel:
    """Tunnel ramp / wall / bore law (RULINGS 2026-09-01c/e, 2026-09-03b)."""

    bore_datum_m: float
    wall_gap_m: float
    crest: str
    ramp_max_grade: float
    bore_cut_clearance_m: float
    ramp_cuts_runway_family: bool
    ramp_crosses_pad: bool


@_dc.dataclass(frozen=True)
class Bridge:
    """Bridge deck law (RULINGS 2026-08-28; memory othh-bridge-deck-datum-r12)."""

    clearance_m: float
    clearance_minimum_m: float
    deck_datum: str
    mapped_deck_cuttable: bool
    terrain_deck_without_object: bool
    floor_below_object_deck_m: float


@_dc.dataclass(frozen=True)
class BuildingPad:
    """Building pad law (RULINGS 2026-09-01g/i)."""

    weld_to_touching_pavement: bool
    footprint_outside_pad_m: float
    groundside_cutback_m: float
    min_area_m2: float
    in_basin_sits_at_floor: bool
    step_exemption_pad_to_pad: bool


@_dc.dataclass(frozen=True)
class Basin:
    """Basin facility law (RULINGS 2026-08-26)."""

    floor: str


@_dc.dataclass(frozen=True)
class RetainingWall:
    """Where a wall may exist at all (RULINGS 2026-08-07, 2026-08-21d)."""

    allowed_outside_carves: bool
    in_runway_strip: bool


@_dc.dataclass(frozen=True)
class Structures:
    """structures.toml."""

    tunnel: Tunnel
    bridge: Bridge
    building_pad: BuildingPad
    basin: Basin
    retaining_wall: RetainingWall


# ── emit.toml ────────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Chords:
    """Chord density."""

    pavement_max_chord_m: float
    apron_interior_spacing_m: float
    station_spacing_m: float


@_dc.dataclass(frozen=True)
class Identity:
    """Canonical vertex identity."""

    coordinate_dp: int
    min_distinct_spacing_m: float


@_dc.dataclass(frozen=True)
class Materiality:
    """Residual floors and the step threshold."""

    elevation_m: float
    grade: float
    step_m: float


@_dc.dataclass(frozen=True)
class NoStep:
    """Airside no-step window (RULINGS 2026-08-27)."""

    window_m: float
    k: int


@_dc.dataclass(frozen=True)
class EmitLaw:
    """emit.toml."""

    chords: Chords
    identity: Identity
    materiality: Materiality
    no_step: NoStep


# ── precedence.toml / families.toml ──────────────────────────────────────

@_dc.dataclass(frozen=True)
class RoleSpec:
    """One emitted role."""

    family: str
    side: str
    value: bool
    aeroway: str


@_dc.dataclass(frozen=True)
class Authority:
    """The total order of value authority (lower index wins)."""

    order: tuple[str, ...]


@_dc.dataclass(frozen=True)
class RoleGroup:
    """A named group of roles a family may address as one word."""

    members: tuple[str, ...]


@_dc.dataclass(frozen=True)
class Precedence:
    """precedence.toml — the total authority order and the role register."""

    authority: Authority
    roles: _t.Mapping[str, RoleSpec]
    taxi_family: RoleGroup
    runway_family: RoleGroup

    @property
    def order(self) -> tuple[str, ...]:
        """Shorthand for ``authority.order``."""
        return self.authority.order


@_dc.dataclass(frozen=True)
class Family:
    """One law family (families.toml)."""

    measures: str
    parameter: str
    roles: tuple[str, ...]
    pairs: str
    ruling: str
    solver: str
    key: str = ""


@_dc.dataclass(frozen=True)
class LawTables:
    """Everything the six files hold, validated."""

    resolution: Resolution
    common: CommonLaw
    rulesets: _t.Mapping[str, Ruleset]
    zones: Zones
    structures: Structures
    emit: EmitLaw
    precedence: Precedence
    families: _t.Mapping[str, Family]


# ── the loader ───────────────────────────────────────────────────────────

_GRADE_WORDS = ("grade", "longitudinal", "transverse", "down", "up",
                "fan_ramp", "crown", "materiality")
_ROLE_FAMILIES = ("runway", "taxi", "common", "none")
_SIDES = ("airside", "groundside")
_PAIRS = ("within", "cross", "steps")
_SOLVERS = ("edge", "pin", "flat", "band", "offset", "construction",
            "diagnostic")
_DATUMS = {"beyond_zone2": ("dem",), "crest": ("dem",),
           "deck_datum": ("deck_top",), "floor": ("declared",)}


def _sane(path: str, name: str, value: float) -> None:
    """Unit sanity: grades are fractions in [0, 0.2]; metres, counts and
    degrees are non-negative."""
    if name.endswith(("_m", "_m2", "_deg", "per_m")) or name == "k":
        if value < 0:
            raise LawError(f"{path}: {name} must be >= 0, got {value}")
        return
    if any(w in name for w in _GRADE_WORDS) or name in ("default",):
        if not 0.0 <= value <= 0.2:
            raise LawError(
                f"{path}: {name}={value} is not a grade fraction in [0, 0.2]"
                " (a fraction, never a percentage)")


def _num(path: str, name: str, raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise LawError(f"{path}.{name}: expected a number, got {raw!r}")
    _sane(path, name, float(raw))
    return float(raw)


def _code_table(path: str, name: str, raw: object) -> CodeTable:
    """A bare number is "one value for every class" (default only)."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return CodeTable(default=_num(path, name, raw))
    if not isinstance(raw, dict):
        raise LawError(f"{path}.{name}: a table needs by_code/by_letter"
                       " or a single number")
    extra = set(raw) - {"by_code", "by_letter", "default"}
    if extra:
        raise LawError(f"{path}.{name}: unknown key(s) {sorted(extra)}")
    if ("by_code" in raw) == ("by_letter" in raw):
        raise LawError(f"{path}.{name}: exactly one of by_code/by_letter")
    default = _num(path, name, raw["default"]) if "default" in raw else None
    if "by_code" in raw:
        bc = {}
        for k, v in raw["by_code"].items():
            if not str(k).isdigit() or not 1 <= int(k) <= 4:
                raise LawError(f"{path}.{name}: code number {k!r} not 1..4")
            bc[int(k)] = _num(path, name, v)
        return CodeTable(by_code=bc, default=default)
    bl = {}
    for k, v in raw["by_letter"].items():
        if str(k).upper() not in "ABCDEF" or len(str(k)) != 1:
            raise LawError(f"{path}.{name}: code letter {k!r} not A..F")
        bl[str(k).upper()] = _num(path, name, v)
    return CodeTable(by_letter=bl, default=default)


def _rate(path: str, name: str, raw: object) -> Rate:
    if not isinstance(raw, dict) or set(raw) != {"grade", "per_m"}:
        raise LawError(f"{path}.{name}: a rate is {{grade = G, per_m = D}}")
    per_m = _num(path, "per_m", raw["per_m"])
    if per_m <= 0:
        raise LawError(f"{path}.{name}: per_m must be > 0")
    return Rate(_num(path, "grade", raw["grade"]), per_m)


def _is_optional(tp: object) -> tuple[bool, object]:
    if _t.get_origin(tp) in (_t.Union, _types.UnionType):
        args = [a for a in _t.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return True, args[0]
    return False, tp


def _convert(path: str, name: str, tp: object, raw: object) -> object:
    """Coerce one TOML value to the annotated type, validating."""
    origin = _t.get_origin(tp)
    if tp is float:
        return _num(path, name, raw)
    if tp is int:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise LawError(f"{path}.{name}: expected an integer")
        _sane(path, name, float(raw))
        return raw
    if tp is bool:
        if not isinstance(raw, bool):
            raise LawError(f"{path}.{name}: expected true/false")
        return raw
    if tp is str:
        if not isinstance(raw, str):
            raise LawError(f"{path}.{name}: expected a string")
        if name in _DATUMS and raw not in _DATUMS[name]:
            raise LawError(f"{path}.{name}: {raw!r} not in {_DATUMS[name]}")
        return raw
    if tp is CodeTable:
        return _code_table(path, name, raw)
    if tp is Rate:
        return _rate(path, name, raw)
    if origin is tuple:
        if not isinstance(raw, list):
            raise LawError(f"{path}.{name}: expected a list")
        (elem, _ell) = _t.get_args(tp)
        return tuple(_convert(path, name, elem, r) for r in raw)
    if origin is frozenset:
        if not isinstance(raw, list):
            raise LawError(f"{path}.{name}: expected a list")
        (elem,) = _t.get_args(tp)
        return frozenset(_convert(path, name, elem, r) for r in raw)
    if origin in (_abc.Mapping, dict):
        if not isinstance(raw, dict):
            raise LawError(f"{path}.{name}: expected a table")
        _k, vt = _t.get_args(tp)
        return {k: _convert(f"{path}.{name}", k, vt, v)
                for k, v in raw.items()}
    if _dc.is_dataclass(tp):
        return _build(tp, raw, f"{path}.{name}")
    raise LawError(f"{path}.{name}: unsupported schema type {tp!r}")


def _build(cls: type, data: object, path: str) -> object:
    """Construct dataclass ``cls`` from ``data`` — every key must be a
    field, every field without a default must be present."""
    if not isinstance(data, dict):
        raise LawError(f"{path}: expected a table for {cls.__name__}")
    hints = _t.get_type_hints(cls)
    fields = {f.name: f for f in _dc.fields(cls)}
    unknown = set(data) - set(fields)
    if unknown:
        raise LawError(f"{path}: unknown key(s) {sorted(unknown)} "
                       f"(allowed: {sorted(fields)})")
    kw: dict[str, object] = {}
    for name, f in fields.items():
        optional, inner = _is_optional(hints[name])
        if name not in data:
            if f.default is _dc.MISSING and \
                    f.default_factory is _dc.MISSING:  # type: ignore[misc]
                raise LawError(f"{path}: missing required key {name!r}")
            continue
        kw[name] = _convert(path, name, inner if optional else hints[name],
                            data[name])
    return cls(**kw)


def _read(law_dir: Path, name: str) -> dict:
    p = law_dir / name
    if not p.is_file():
        raise LawError(f"law table missing: {p}")
    with p.open("rb") as fh:
        try:
            return tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise LawError(f"{p}: {exc}") from exc


def _check_cross_refs(t: LawTables) -> None:
    """Rules that span files: role registers agree, every family's
    parameter resolves, enumerations are in range."""
    roles = set(t.precedence.roles)
    for r in t.precedence.order:
        if r not in roles:
            raise LawError(f"precedence.authority.order: unknown role {r!r}")
    if len(set(t.precedence.order)) != len(t.precedence.order):
        raise LawError("precedence.authority.order: duplicate role")
    for r, spec in t.precedence.roles.items():
        if spec.family not in _ROLE_FAMILIES:
            raise LawError(f"precedence.roles.{r}.family {spec.family!r}")
        if spec.side not in _SIDES:
            raise LawError(f"precedence.roles.{r}.side {spec.side!r}")
        if spec.family == "common" and r not in t.common.roles:
            raise LawError(f"precedence.roles.{r}: family common but no "
                           "cap in rulesets.common.roles")
        if spec.value != (spec.family != "none"):
            raise LawError(f"precedence.roles.{r}: value must be true iff "
                           "family != none")
    for r in t.common.roles:
        if r not in roles:
            raise LawError(f"rulesets.common.roles.{r}: not a registered role")
    for grp in (t.precedence.taxi_family.members,
                t.precedence.runway_family.members):
        for r in grp:
            if r not in roles:
                raise LawError(f"precedence family member {r!r} unknown")
    if t.resolution.default not in t.rulesets:
        raise LawError(f"rulesets.resolution.default {t.resolution.default!r}"
                       " is not a ruleset")
    role_words = roles | {"all", "airside", "groundside", "taxi_family",
                          "runway_family"}
    for key, fam in t.families.items():
        if fam.pairs not in _PAIRS:
            raise LawError(f"families.{key}.pairs {fam.pairs!r}")
        if fam.solver not in _SOLVERS:
            raise LawError(f"families.{key}.solver {fam.solver!r}")
        for r in fam.roles:
            if r not in role_words:
                raise LawError(f"families.{key}.roles: unknown {r!r}")
        if not resolves(t, fam.parameter):
            raise LawError(f"families.{key}.parameter {fam.parameter!r} "
                           "does not resolve in the loaded tables")


def resolves(tables: LawTables, dotted: str) -> bool:
    """Whether a families.toml ``parameter`` path names a value in the
    tables.  ``ruleset.X`` must resolve in at least ONE ruleset (an
    authority stating no number is a lawful no-op, not a missing key);
    ``roles.*.X`` in every role cap; anything else walks attributes /
    mappings."""
    parts = dotted.split(".")
    if parts[0] == "ruleset":
        return any(_walk(rs, parts[1:]) for rs in tables.rulesets.values())
    if parts[:2] == ["roles", "*"]:
        return all(_walk(c, parts[2:]) for c in tables.common.roles.values())
    return _walk(tables, parts)


def _walk(obj: object, parts: list[str]) -> bool:
    for p in parts:
        if isinstance(obj, _t.Mapping):
            if p not in obj:
                return False
            obj = obj[p]
        elif _dc.is_dataclass(obj) and hasattr(obj, p):
            obj = getattr(obj, p)
        else:
            return False
    return obj is not None


def load_tables(law_dir: str | Path) -> LawTables:
    """Load and validate the six tables under ``law_dir``."""
    d = Path(law_dir)
    rs_raw = _read(d, "rulesets.toml")
    known = {"resolution", "common"}
    resolution = _build(Resolution, rs_raw.get("resolution"),
                        "rulesets.resolution")
    common = _build(CommonLaw, rs_raw.get("common"), "rulesets.common")
    rulesets: dict[str, Ruleset] = {}
    for key, raw in rs_raw.items():
        if key in known:
            continue
        rs = _build(Ruleset, raw, f"rulesets.{key}")
        rulesets[key] = _dc.replace(rs, key=key)
    if not rulesets:
        raise LawError("rulesets.toml: no ruleset tables")
    fam_raw = _read(d, "families.toml")
    families = {k: _dc.replace(_build(Family, v, f"families.{k}"), key=k)
                for k, v in fam_raw.items()}
    if not families:
        raise LawError("families.toml: no families")
    tables = LawTables(
        resolution=resolution, common=common, rulesets=rulesets,
        zones=_build(Zones, _read(d, "zones.toml"), "zones"),
        structures=_build(Structures, _read(d, "structures.toml"),
                          "structures"),
        emit=_build(EmitLaw, _read(d, "emit.toml"), "emit"),
        precedence=_build(Precedence, _read(d, "precedence.toml"),
                          "precedence"),
        families=families)
    _check_cross_refs(tables)
    return tables


# ── the Law bound to one airport ─────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Law:
    """The tables plus the ruleset that governs ONE airport.  Every
    consumer (constraint generators, emit, verify) reads through this."""

    tables: LawTables
    ruleset_key: str

    @property
    def ruleset(self) -> Ruleset:
        """The governing authority's tables."""
        return self.tables.rulesets[self.ruleset_key]

    @staticmethod
    def default_dir() -> Path:
        """The checked-in law directory (this package)."""
        return Path(__file__).resolve().parent

    @classmethod
    def load(cls, law_dir: str | Path | None = None, *,
             ruleset: str | None = None) -> "Law":
        """Load the tables (default: the checked-in directory) and bind
        ``ruleset`` (default: the resolution default)."""
        tables = load_tables(law_dir or cls.default_dir())
        key = ruleset or tables.resolution.default
        if key not in tables.rulesets:
            raise LawError(f"unknown ruleset {key!r} "
                           f"({sorted(tables.rulesets)})")
        return cls(tables=tables, ruleset_key=key)

    @classmethod
    def for_airport(cls, icao: str, ruleset: str | None = None,
                    law_dir: str | Path | None = None) -> "Law":
        """The law for ``icao``: ``ruleset`` if given, else resolved from
        the identifier exactly as v1's ``config.resolve_ruleset`` (owner
        2026-08-02: FAA within the USA, ICAO everywhere else)."""
        tables = load_tables(law_dir or cls.default_dir())
        key = ruleset or resolve_ruleset(tables.resolution, icao)
        if key not in tables.rulesets:
            raise LawError(f"unknown ruleset {key!r}")
        return cls(tables=tables, ruleset_key=key)


def resolve_ruleset(res: Resolution, icao: str | None) -> str:
    """Ruleset key for an ICAO identifier (owner 2026-08-02).  Empty or
    unparseable identifiers take the default."""
    code = str(icao or "").strip().upper()
    if not code:
        return res.default
    if code[0] in res.faa_first_letters:
        return "faa"
    if code[:2] in res.faa_two_letter_prefixes:
        return "faa"
    return res.default
