"""THE LAW — typed schema and loader for the ``law/*.toml`` tables
(RULINGS 2026-09-03d; owner amendment 2026-09-03: the VALUES live in
TOML, never in Python).  The SHAPE of the law (frozen dataclasses, one per
table) and the loader that validates the files — unknown / missing key,
non-numeric cap, unit sanity, a family pointing at a parameter that does
not exist — and fails loudly.  No numeric value appears here; ``law``
imports nothing from the rest of v2.
"""
from __future__ import annotations

import collections.abc as _abc
import dataclasses as _dc
import tomllib
import types as _types
import typing as _t
from pathlib import Path

# flat_site.toml's schema + its own checks live beside this module (the
# 1,000-line file law; RULINGS 2026-09-05k-2) and are re-exported here.
from .flat_site_schema import (Declared, FlatDatum, FlatDetector, FlatSite,  # noqa: F401
                               ReliefFloor, check_flat_site as _check_flat_site)
# the [rebake] schema (06g: the contact-cluster law's keys) likewise
from .rebake_schema import Placement, Rebake  # noqa: F401
# the [cutout] schema (06b (1), 09-08a; the door / sunken-road ramp laws 09-08b/c)
from .cutout_schema import Cutout, check_cutout as _check_cutout  # noqa: F401
# the [basin] schema (the below-grade facility law; 11t §24) likewise
from .basin_schema import Basin  # noqa: F401
# the [tunnel.object] schema (05k-1/05n/06c/06f/09w; the THIN-PLATE wall
# class of spec §33 (2)) likewise — the 1,000-line file law
from .tunnel_object_schema import TunnelObject  # noqa: F401
# the unit-sanity register (grades are fractions; RULINGS 2026-09-08n bound)
from .units import sane as _sane  # noqa: F401
from .model_types import CodeTable, Rate, RoleCap  # noqa: F401
from .role_cap_schema import role_cap_from_table as _role_cap_schema  # noqa: F401
# the END-AROUND TAXIWAY schema (spec §36) likewise beside this module
from .eat_schema import EatRecognition, EatSurface  # noqa: F401
from .terrace_schema import Terrace, check_terrace as _check_terrace  # noqa: F401
from .design_schema import Design, check_design as _check_design  # noqa: F401
from .cockpit_schema import COCKPIT_CLASSES, Cockpit, check_cockpit as _check_cockpit  # noqa: E501,F401  the [cockpit] frame, 12x/12y
# the per-airport affordances (RULINGS 2026-09-10ap) likewise
from .airports_schema import (Affordances, NO_AFFORDANCES, Resolution,  # noqa: F401
                              load_airports as _load_airports, resolve_ruleset)

__all__ = ["LawError", "CodeTable", "Rate", "RoleCap", "RunwayLaw", "TaxiLaw", "StripLaw",
    "EndSkirtLaw", "ResaLaw", "RaoaLaw", "DrainageLaw", "EatSurface", "EatRecognition",
    "Ruleset", "CommonLaw", "Resolution",
    "ZoneClass", "AdjacentGround", "Pockets", "Zones", "Tunnel", "TunnelObject", "Bridge",
    "BuildingPad", "Skirt", "Basin", "RetainingWall", "Rebake", "Placement",
    "Structures", "ReliefFloor",
    "FlatDetector", "FlatDatum", "Declared", "FlatSite", "Chords", "Identity", "Materiality",
    "NoStep", "Transect", "WithinShape", "Instrument", "Cockpit", "Terrace", "Design",
    "EmitLaw", "RoleSpec", "Authority", "RoleGroup", "Precedence", "Family", "LawTables",
    "Law", "Affordances", "NO_AFFORDANCES", "TABLE_FILES", "load_tables",
    "COCKPIT_CLASSES"]

#: The eight files a law directory must contain (owner amendment
#: 2026-09-03; ``flat_site.toml`` per RULINGS 2026-09-05k-2,
#: ``airports.toml`` — the per-airport affordances — per 2026-09-10ap).
TABLE_FILES: tuple[str, ...] = ("rulesets.toml", "zones.toml", "structures.toml", "emit.toml",
                                "precedence.toml", "families.toml", "flat_site.toml",
                                "airports.toml")


class LawError(ValueError):
    """A law table is malformed.  The message names file, key path and
    the rule violated; nothing is ever defaulted around it."""


# ── leaf value types (``model_types``, under the 1,000-line file law) ───

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
    #: §40 (2) as amended (owner RULINGS 2026-09-13dd): the cap on a
    #: SHOULDER vertex — one beyond the runway's own half-width, pavement
    #: that joined the runway body under §40 (1).  ICAO Annex 14 §3.2.4.
    #: REQUIRED, and stated in ``rulesets.toml`` like every other cap: no
    #: cap value lives in Python (``test_no_numeric_literal_in_law_python``).
    shoulder_transverse_max: float
    end_zone_precision_only_codes: frozenset[int] = frozenset()
    end_zone_max_length_m: float | None = None
    vertical_curve_min_change: CodeTable | None = None


@_dc.dataclass(frozen=True)
class TaxiLaw:
    """Taxiway-family longitudinal and transverse law."""

    longitudinal: CodeTable
    transverse: CodeTable
    transverse_min: float
    width_m: CodeTable | None = None   # pavement width by letter (2026-09-06t)


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
    corridor_length_m: CodeTable | None = None


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
    eat: EatSurface | None = None
    key: str = ""


@_dc.dataclass(frozen=True)
class CommonLaw:
    """Authority-independent caps."""

    roles: _t.Mapping[str, RoleCap]
    #: THE 5 % CEILING (owner RULINGS 2026-09-09b (4)): the hard maximum
    #: grade of EVERY pavement class, and of a free road; the per-class
    #: letter caps stay targets under it (``constraints/ceiling.py``)
    pavement_max_grade: float
    road_max_grade: float
    apron_fan_ramp_max: float
    road_transverse_axis_min_deg: float
    runway_crown_transverse: float
    vertical_curve_k_grade_unit: float     # vertical_curve_k_m is metres per THIS much grade
    #: THE END-AROUND TAXIWAY's recognition constants (spec §36)
    eat: EatRecognition


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
    groundside_cutback_m: float
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
    #: spec §26: the ``tunnel`` values that seed a bore (default ``["yes"]``);
    #: every other value — ``building_passage``, ``culvert``,
    #: ``avalanche_protector``, ``flooded``, ``no`` — never seeds a structure.
    admitted_values: tuple[str, ...]
    ramp_max_grade: float
    mouth_standoff_m: float   # spec §29 (1): cover ⊕ this = where a mouth may stand
    ramp_cuts_runway_family: bool
    ramp_crosses_pad: bool
    wall_band_width_m: float
    lane_width_m: float
    default_lanes: int
    ramp_width_source: tuple[str, ...]      # 2026-09-06b (2): ["pavement", "lanes"]
    ramp_pavement_max_offset_m: float
    dual_carriageway_max_separation_m: float
    max_ramp_length_m: float
    #: spec §34 (2): the largest turn the approach walk may take at a
    #: node it HOPS across (a way's own nodes are never a hop).
    approach_turn_max_deg: float
    #: spec §34 (5): an ``aeroway`` ``bridge=yes`` way at or above this
    #: ``layer`` states a crossing; a road under its deck ribbon for at
    #: least ``underpass_min_span_m`` is bored.
    underpass_min_layer: int
    underpass_min_span_m: float
    object: TunnelObject


@_dc.dataclass(frozen=True)
class Bridge:
    """Bridge deck law (RULINGS 2026-08-28; memory othh-bridge-deck-datum-r12)."""

    clearance_m: float
    clearance_minimum_m: float
    #: spec §34 (6): how far past a terrain deck's mapped end the governed
    #: cell that end MEETS may stand (OSM stops a service road at the
    #: apron's edge, not on it).
    deck_end_reach_m: float
    deck_datum: str
    mapped_deck_cuttable: bool
    terrain_deck_without_object: bool
    # the deck signature by geometry (04k; M6b)
    deck_plate_normal_y_min: float
    deck_plane_bin_m: float
    deck_plane_area_tie: float
    deck_min_area_m2: float
    deck_min_span_m: float
    deck_min_elevation_m: float
    deck_close_m: float
    deck_profile_bin_m: float
    deck_way_cover_min: float
    deck_way_carried_area_min: float
    pavement_deck_families: tuple[str, ...]   # 2026-09-06f: pavement cells of these role families spanning a corridor are decks
    deck_spanning_evidence: tuple[str, ...]
    abutment_sample_step_m: float
    abutment_walk_max_m: float
    abutment_min_land_samples: int
    deck_stations: int
    deck_plate_connected_min: float
    deck_pier_footprint_max: float
    deck_pier_close_m: float
    deck_min_clearance_under_m: float


@_dc.dataclass(frozen=True)
class BuildingPad:
    """Building pad law (RULINGS 2026-09-01g/i)."""

    weld_to_touching_pavement: bool
    footprint_outside_pad_m: float
    groundside_cutback_m: float
    min_area_m2: float
    in_basin_sits_at_floor: bool
    step_exemption_pad_to_pad: bool
    frontage_near_miss_m: float
    frontage_soft_roles: tuple[str, ...]


@_dc.dataclass(frozen=True)
class Skirt:
    """FOUNDATION-SKIRT law (owner RULINGS 2026-09-10af/10ag; spec §22).
    A skirted building needs no pad and seats at its low-side foot."""

    perimeter_fraction: float
    depth_tolerance_m: float
    min_depth_m: float
    edge_tolerance_m: float
    pad_cover_fraction: float
    drops_pad: bool
    seat_low_side: bool


@_dc.dataclass(frozen=True)
class RetainingWall:
    """Where a wall may exist at all (RULINGS 2026-08-07, 2026-08-21d)."""

    allowed_outside_carves: bool
    in_runway_strip: bool


@_dc.dataclass(frozen=True)
class LoadLaw:
    """§42 OBJECT-BASED PAVEMENT (owner RULINGS 2026-09-13cv): which of a
    pack's DRAPED OBJ8 ground polygons are pavement SOURCE geometry.
    ``airport/object_pavement.py`` carries the measurement behind each
    key."""

    #: a draped vertex further than this off Y = 0 is not a ground polygon
    draped_y_tol_m: float
    #: the object's whole draped footprint must reach this
    object_pavement_min_m2: float
    #: ``ATTR_layer_group_draped`` groups that are PAVEMENT (v1's ruled
    #: gate, ``dsf_reader._PAVEMENT_OBJECT_LAYER_GROUPS``); an object
    #: declaring none, or declaring ``markings``, is a shadow or a decal
    object_pavement_layer_groups: tuple[str, ...]
    #: ...at no greater draw offset: +2 is painted ON the pavement
    object_pavement_max_layer_offset: int
    #: basename tokens that veto a page whatever it declares
    object_pavement_skip_tokens: tuple[str, ...]


@_dc.dataclass(frozen=True)
class Structures:
    """structures.toml."""

    tunnel: Tunnel
    bridge: Bridge
    building_pad: BuildingPad
    skirt: Skirt
    basin: Basin
    cutout: Cutout
    retaining_wall: RetainingWall
    rebake: Rebake
    placement: Placement
    load: LoadLaw


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
    weld_spacing_m: float
    dsf_pavement_admission_m: float

@_dc.dataclass(frozen=True)
class Materiality:
    """Residual floors and the step threshold."""

    elevation_m: float
    grade: float
    step_m: float


@_dc.dataclass(frozen=True)
class NoStep:
    """Airside no-step pairs (RULINGS 2026-08-27; 2026-09-04o/04q: the window
    and K are ROUTE distances).  ``metric`` = ``"route"`` (along the taxi
    network; a chord metric is the refuted 08-27 reading)."""

    window_m: float
    k: int
    metric: str


@_dc.dataclass(frozen=True)
class Transect:
    """The transect walk (owner 2026-08-21): station / reach / span."""

    step_m: float
    half_width_m: float
    min_width_m: float
    max_gap_m: float


@_dc.dataclass(frozen=True)
class WithinShape:
    """Which ring pairs the within-shape law prices."""

    apron_body_chord_max_m: float
    runway_station_cluster_m: float
    #: RULINGS 2026-09-04t-2 (edge portion): a shared apron run at least
    #: this many face-widths long is a LONG EDGE (apron cap along it); a
    #: shorter run is a MOUTH (the face's own cap).
    apron_edge_portion_min_width_ratio: float
    #: RULINGS 2026-09-04y: roles whose bodies are priced by their triangle
    #: mesh (ring edges, common-stretch pairs, mesh edges), never all-pairs.
    junction_mesh_roles: tuple[str, ...]
    #: RULINGS 2026-09-06p (3): the oracle's withdrawn-chord stamp applies
    #: only to taxi-family chords at least this long (m); shorter ones are
    #: priced.
    withdrawn_chord_min_m: float
    #: RULINGS 2026-09-05f, kept when ``[relaxation]`` was deleted (08t): a
    #: rigid pad is ONE level, so its emitted plane may slope at most this
    #: (m/m); above it ``verify/pads.py`` reads a ``pad_flat`` DEFECT.  The
    #: plane's own residual tolerance is ``materiality.elevation_m``.
    pad_slope_max: float

    #: RULINGS 2026-09-14au: THE PAD'S SKIRT YIELDS, THE AIRSIDE NEVER
    #: DOES.  v2settle's stage-2 feasibility CERTIFICATE proved a welded
    #: pad's 1 % ceiling and a fixed apron rim mutually infeasible (KCLT
    #: 143 ``building_pad airside skirt`` rows, 26.4 m over 179 columns,
    #: all at 35.2097, −80.9327).  The SKIRT BAND's pairs — those with an
    #: airside end, ``constraints/pads._pad_rows`` — are therefore priced
    #: at THIS ceiling instead of ``pad_slope_max``: a slope, never a
    #: step.  The pad's CORE keeps the cap-0 plate and the 1 % ceiling.
    #: At or below ``pad_slope_max`` the relaxation is disarmed.


@_dc.dataclass(frozen=True)
class Instrument:
    """The census's encoding envelope (a reader's forgiveness, never a
    solve budget)."""

    rounding_noise_m: float
    coarse_noise_m: float
    coarse_noise_roles: tuple[str, ...]
    strip_edge_noise_m: float
    step_contact_tol_m: float
    edge_search_m: float
    tile_seam_zone_m: float


@_dc.dataclass(frozen=True)
class Seam:
    """The tile-seam cut (user 2026-05-10): the graticule band no face
    covers, ``half_width_m`` each side of an integer lat/lon line."""

    half_width_m: float


@_dc.dataclass(frozen=True)
class LateralContiguity:
    """The road station walk (owner 2026-08-02 clause 2; 2026-08-28
    Amendment 2): station spacing, probe reach, run tolerances."""

    station_step_m: float
    probe_m: float
    gap_tol_m: float
    min_member_m: float


@_dc.dataclass(frozen=True)
class RoadProfile:
    """The core's road clamp constants (RULINGS 2026-09-04t-4; ``airport/road_profile.py``)."""

    station_m: float
    lane_width_m: float
    answer_radius_lane_widths: float


@_dc.dataclass(frozen=True)
class RoadContact:
    """§37 (10) THE AIRSIDE CONTACT SET AND THE GEOMETRIC ROUTE PAIR
    (Fable 2026-09-13; owner RULINGS 2026-09-13cs items 3/4/5)."""

    #: (1) a road that ENDS this far from an airside face's edge without
    #: touching it takes a contact at the nearest edge point
    contact_reach_m: float
    #: (2) two routes whose frames place vertices this close laterally...
    pair_lateral_m: float
    #: ... over at least this much arc are ONE carriageway
    pair_overlap_m: float
    #: contact roles BESIDE the airside value roles (apron, pad, the taxi
    #: family, the runway family with §40's shoulder): §37 (10)'s LOT,
    #: which precedence.toml partitions groundside but which is hard
    #: surface a road meets at a stated level
    extra_roles: tuple[str, ...] = ()


@_dc.dataclass(frozen=True)
class EmitLaw:
    """emit.toml."""

    chords: Chords
    identity: Identity
    materiality: Materiality
    no_step: NoStep
    transect: Transect
    within_shape: WithinShape
    instrument: Instrument
    #: [cockpit]: THE READING RULE for every bar (2026-09-12x/12y, §31)
    cockpit: Cockpit
    seam: Seam
    lateral_contiguity: LateralContiguity
    road_profile: RoadProfile
    #: [road_contact]: §37 (10) (RULINGS 2026-09-13cs)
    road_contact: RoadContact
    terrace: Terrace
    #: [design]: THE DESIGN SURFACE's objective weights (RULINGS 2026-09-08t) —
    #: replaces [relaxation] and [yield], deleted with the tier / IIS /
    #: relaxation / yield machinery they priced.
    design: Design


# ── precedence.toml / families.toml ──────────────────────────────────────

@_dc.dataclass(frozen=True)
class RoleSpec:
    """One emitted role.  ``rigid``: one flat value per face, levelled by
    its contact (RULINGS 2026-09-03h)."""

    family: str
    side: str
    value: bool
    aeroway: str
    rigid: bool = False
    #: The role name the v1 census oracle judges this role under (None =
    #: its own name); the emitter writes ``class=<role>`` beside it.
    oracle_role: str | None = None
    #: A STRUCTURE role: its values are a structure generator's datum
    #: (tunnel floor / ramp / wall crest / basin floor), never a site-wide
    #: preference's — the flat datum rows skip every vertex such a face
    #: touches (RULINGS 2026-09-05k-2 amendment: OTHH ramp lifted 3.7 m).
    structure: bool = False
    #: The v1 grade LAW the oracle prices the alias under (``o4_grade_law``:
    #: ``ROLE_GRADE_LIMITS[<law>]``) when the alias caps tighter than this
    #: role (a door ramp under ``tunnel_ramp``, spec othh-terminal-ramps §4).
    oracle_law: str | None = None
    #: The cap the ORACLE prices this role's pairs at (``o4_grade_law_cap``),
    #: in place of the role's own face cap — the pair frame reads a ramp's
    #: ring diagonals, which the face's longitudinal law does not bound.
    #: RULINGS 2026-09-08u (2): both structure ramps are read at the ramp
    #: law's ceiling ``cutout.wall_corridor.max_ramp_grade`` 0.10.
    oracle_cap: float | None = None


@_dc.dataclass(frozen=True)
class Authority:
    """The total order of value authority (lower index wins)."""

    order: tuple[str, ...]


@_dc.dataclass(frozen=True)
class RoleGroup:
    """A named group of roles a family may address as one word."""

    members: tuple[str, ...]


@_dc.dataclass(frozen=True)
class StructureDatums:
    """Which structure's datum a vertex shared by two structures keeps
    (lane v2hecalemd, 2026-09-05): ``Source.inputs`` prefixes, senior first."""

    datum_order: tuple[str, ...]


@_dc.dataclass(frozen=True)
class Precedence:
    """precedence.toml — the total authority order and the role register."""

    authority: Authority
    roles: _t.Mapping[str, RoleSpec]
    structures: StructureDatums
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
    #: §31 (6)'s class (``cockpit_schema.COCKPIT_CLASSES``); REQUIRED
    cockpit: str
    key: str = ""


@_dc.dataclass(frozen=True)
class LawTables:
    """Everything the eight files hold, validated."""

    resolution: Resolution
    common: CommonLaw
    rulesets: _t.Mapping[str, Ruleset]
    zones: Zones
    structures: Structures
    emit: EmitLaw
    precedence: Precedence
    families: _t.Mapping[str, Family]
    flat_site: FlatSite
    #: airports.toml, keyed by upper-case ICAO (may be empty)
    airports: _t.Mapping[str, Affordances] = _dc.field(default_factory=dict)


# ── the loader ───────────────────────────────────────────────────────────

_ROLE_FAMILIES = ("runway", "taxi", "common", "none")
_SIDES = ("airside", "groundside")
_PAIRS = ("within", "cross", "steps")
_SOLVERS = ("edge", "pin", "flat", "band", "offset", "construction",
            "diagnostic")
_DATUMS = {"beyond_zone2": ("dem",), "crest": ("dem",),
           "plate_datum": ("ground",), "mouth_depth": ("floor_slab", "wall_bottom"),
           "ramp_end": ("wall_end",), "trench": ("inner_walls",),
           "mouth_end": ("bore",),
           "deck_datum": ("deck_top",), "floor": ("deepest_solid",),
           "rim": ("ground",)}


def _num(path: str, name: str, raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise LawError(f"{path}.{name}: expected a number, got {raw!r}")
    _sane(path, name, float(raw), LawError)
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
    if tp is RoleCap:
        return _role_cap_schema(path, name, raw, _build, RoleCap, LawError)
    if tp is float:
        return _num(path, name, raw)
    if tp is int:
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise LawError(f"{path}.{name}: expected an integer")
        _sane(path, name, float(raw), LawError)
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
        raise LawError(f"{path}: unknown key(s) {sorted(unknown)} (allowed: {sorted(fields)})")
    kw: dict[str, object] = {}
    for name, f in fields.items():
        optional, inner = _is_optional(hints[name])
        if name not in data:
            if f.default is _dc.MISSING and f.default_factory is _dc.MISSING:  # type: ignore[misc]
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
    _check_terrace(t.emit.terrace, roles, LawError)
    # §31: thresholds ordered, range real, EVERY family classed
    _check_cockpit(t.emit.cockpit, t.families, LawError, t)
    # THE PROFILE WINDOW IS THE SCALE OF THE K LAW (spec §21.2 (1)): the
    # largest ``vertical_curve_k_m`` any loaded ruleset states, handed to
    # the design schema (which imports nothing from v2).
    ks: list[float] = []
    for rs in t.rulesets.values():
        ct = rs.runway.vertical_curve_k_m
        ks += [float(v) for v in (ct.by_code or {}).values()]
        ks += [float(v) for v in (ct.by_letter or {}).values()]
        if ct.default is not None:
            ks.append(float(ct.default))
    _check_design(t.emit.design, LawError, max(ks) if ks else None)
    # §38 (3)/13an (e) THE SLIT IS NOT CLOSED BY A COINCIDENCE (owner
    # RULINGS 2026-09-13an).  Until 13an the 2 x ``seam.half_width_m`` gap
    # between two tile pieces was closed only because ``design.
    # bank_min_width_m`` (5.0) happened to EQUAL ``seam.half_width_m``
    # (5.0) — two independently typed constants — and the two collars'
    # 1.6 mm miss was the SPLP texture tear.  ``emit/bank.py`` now unions
    # the band into the coverage EXPLICITLY, so the closure no longer
    # depends on this; the relation is asserted anyway, by name, so a
    # future edit that would put the collar back in charge is refused at
    # law load instead of being discovered in a mesh.
    if t.emit.seam.half_width_m > 0.0 and (
            t.emit.design.bank_min_width_m < t.emit.seam.half_width_m):
        raise LawError(
            f"emit.design.bank_min_width_m {t.emit.design.bank_min_width_m} < "
            f"emit.seam.half_width_m {t.emit.seam.half_width_m}: the bank's "
            "minimum-width collar must at least reach the tile-seam band's "
            "half width (RULINGS 2026-09-13an; the band is unioned into the "
            "coverage at emit/bank.py, and this keeps the two readings of "
            "the seam from drifting apart)")
    if len(set(t.precedence.order)) != len(t.precedence.order):
        raise LawError("precedence.authority.order: duplicate role")
    so = t.precedence.structures.datum_order
    if len(set(so)) != len(so) or not set(so) <= {"tunnel", "basin"}:
        raise LawError(f"precedence.structures.datum_order: {so!r} must list "
                       f"'tunnel' / 'basin' once each")
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
        if spec.oracle_role is not None:
            alias = t.precedence.roles.get(spec.oracle_role)
            if alias is None or alias.oracle_role is not None:
                raise LawError(f"precedence.roles.{r}.oracle_role: "
                               f"{spec.oracle_role!r} is not a registered "
                               "un-aliased role")
            if alias.side != spec.side:
                raise LawError(f"precedence.roles.{r}.oracle_role: side differs")
        if spec.oracle_cap is not None and (spec.oracle_role is None or spec.oracle_cap <= 0.0):
            raise LawError(f"precedence.roles.{r}.oracle_cap: a positive cap, "
                           "and only on an aliased role")
    # RULINGS 2026-09-08u (2): the oracle reads BOTH structure ramps at the
    # ramp law's ceiling — ONE number, ``cutout.wall_corridor.max_ramp_grade``
    for r in ("door_ramp", "wall_corridor_ramp"):
        spec = t.precedence.roles.get(r)
        if spec is not None and spec.oracle_cap != t.structures.cutout.wall_corridor.max_ramp_grade:
            raise LawError(f"precedence.roles.{r}.oracle_cap {spec.oracle_cap} is not "
                           "structures.cutout.wall_corridor.max_ramp_grade "
                           f"{t.structures.cutout.wall_corridor.max_ramp_grade} (08u (2))")
    for r in t.common.roles:
        if r not in roles:
            raise LawError(f"rulesets.common.roles.{r}: not a registered role")
    # RULINGS 2026-09-12m: the ramp is BUILT at structures.tunnel.ramp_max_grade
    # and JUDGED at the tunnel_ramp role cap (rulesets.common.roles, the number
    # the census reads through v1 ROLE_GRADE_LIMITS).  Building steeper than the
    # judged cap would mint a violation by construction.
    ramp_role_cap = t.common.roles.get("tunnel_ramp")
    if ramp_role_cap is not None and \
            t.structures.tunnel.ramp_max_grade > ramp_role_cap.longitudinal + 1e-12:
        raise LawError(
            f"structures.tunnel.ramp_max_grade {t.structures.tunnel.ramp_max_grade} "
            f"exceeds the tunnel_ramp role's longitudinal cap "
            f"{ramp_role_cap.longitudinal} (RULINGS 2026-09-12m)")
    door_cap = t.common.roles.get("door_ramp")
    wc_cap = t.common.roles.get("wall_corridor_ramp")
    gr_cap = t.common.roles.get("garage_ramp")
    _check_cutout(t.structures.cutout, None if door_cap is None else door_cap.longitudinal,
                  LawError, None if wc_cap is None else wc_cap.longitudinal,
                  None if gr_cap is None else gr_cap.longitudinal)
    for grp in (t.precedence.taxi_family.members,
                t.precedence.runway_family.members):
        for r in grp:
            if r not in roles:
                raise LawError(f"precedence family member {r!r} unknown")
    if t.resolution.default not in t.rulesets:
        raise LawError(f"rulesets.resolution.default {t.resolution.default!r}"
                       " is not a ruleset")
    _check_flat_site(t.flat_site, LawError)
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
    """Load and validate the eight tables under ``law_dir``."""
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
    # airports.toml — the per-airport affordances (RULINGS 2026-09-10ap)
    airports = _load_airports(_read(d, "airports.toml"), LawError, _build)
    tables = LawTables(
        resolution=resolution, common=common, rulesets=rulesets,
        zones=_build(Zones, _read(d, "zones.toml"), "zones"),
        structures=_build(Structures, _read(d, "structures.toml"),
                          "structures"),
        emit=_build(EmitLaw, _read(d, "emit.toml"), "emit"),
        precedence=_build(Precedence, _read(d, "precedence.toml"),
                          "precedence"),
        families=families,
        flat_site=_build(FlatSite, _read(d, "flat_site.toml"), "flat_site"),
        airports=airports)
    _check_cross_refs(tables)
    return tables


# ── the Law bound to one airport ─────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Law:
    """The tables plus the ruleset that governs ONE airport.  Every
    consumer (constraint generators, emit, verify) reads through this."""

    tables: LawTables
    ruleset_key: str
    #: the airport this law is bound to, upper-case ("" = none: the law
    #: without an airport takes NO affordance — RULINGS 2026-09-10ap)
    icao: str = ""

    @property
    def ruleset(self) -> Ruleset:
        """The governing authority's tables."""
        return self.tables.rulesets[self.ruleset_key]

    @property
    def affordances(self) -> Affordances:
        """The airport's opt-in laws (``airports_schema``, 2026-09-10ap);
        an unnamed airport takes :data:`NO_AFFORDANCES`."""
        return self.tables.airports.get(self.icao, NO_AFFORDANCES)

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
        return cls(tables=tables, ruleset_key=key,
                   icao=str(icao or "").strip().upper())
