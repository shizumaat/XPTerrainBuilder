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
# flat_pack.toml's schema likewise (owner direction 2026-10-20, answers 59-66)
from .flat_pack_schema import (FlatPack, FlatPackDetector,  # noqa: F401
                               check_flat_pack as _check_flat_pack)
# runway_ends.toml's schema likewise (owner RULINGS 2026-10-25a / 26a / 26e)
from .runway_ends_schema import (ByDemClass, RunwayEnds,  # noqa: F401
                                 check_runway_ends as _check_runway_ends)
# terrain_witness.toml's schema likewise (#1359, RULINGS 2026-10-26q/v/w/x/y/z, 27a)
from .terrain_witness_schema import (TerrainWitness,  # noqa: F401
                                     check_terrain_witness as _check_terrain_witness)
# the [rebake] schema (06g: the contact-cluster law's keys) likewise
from .rebake_schema import Deck, Placement, Rebake, Scatter  # noqa: F401
# the [cutout] schema (06b (1), 09-08a; the door / sunken-road ramp laws 09-08b/c)
from .cutout_schema import Cutout, check_cutout as _check_cutout  # noqa: F401
# the [basin] schema (the below-grade facility law; 11t §24) likewise
from .basin_schema import Basin  # noqa: F401
# the [base_profile] schema (the building base profile; base-profile spec
# §1) likewise lives beside the other per-table schemas
from .base_profile_schema import BaseProfileLaw  # noqa: F401
from .walled_plate_schema import WalledPlateLaw  # noqa: F401
# the [tunnel.object] schema (05k-1/05n/06c/06f/09w; the THIN-PLATE wall
# class of spec §33 (2)) likewise — the 1,000-line file law
from .tunnel_object_schema import TunnelObject  # noqa: F401
# the unit-sanity register (grades are fractions; RULINGS 2026-09-08n bound)
from .units import sane as _sane  # noqa: F401
from .model_types import ApproachSurface, CodeTable, Rate, RoleCap  # noqa: F401
from .role_cap_schema import role_cap_from_table as _role_cap_schema  # noqa: F401
# the END-AROUND TAXIWAY schema (spec §36) likewise beside this module
from .eat_schema import EatRecognition, EatSurface  # noqa: F401
# the runway witnesses' table (regulation-conformance spec §3) likewise
from .reference_code import ReferenceCode  # noqa: F401
from .terrace_schema import Terrace, check_terrace as _check_terrace  # noqa: F401
from .design_schema import Design, check_design as _check_design  # noqa: F401
from .cockpit_schema import COCKPIT_CLASSES, Cockpit, check_cockpit as _check_cockpit  # noqa: E501,F401  the [cockpit] frame, 12x/12y
# the ruleset resolution by identifier class likewise
from .airports_schema import Resolution, resolve_ruleset  # noqa: F401

__all__ = ["LawError", "CodeTable", "Rate", "RoleCap", "RunwayLaw", "TaxiLaw", "StripLaw",
    "EndSkirtLaw", "ResaLaw", "RaoaLaw", "DrainageLaw", "EatSurface", "EatRecognition", "ReferenceCode",
    "Ruleset", "CommonLaw", "Resolution",
    "ZoneClass", "AdjacentGround", "Pockets", "Zones", "Tunnel", "TunnelObject", "Bridge",
    "BuildingPad", "Skirt", "Basin", "RetainingWall", "Rebake", "Placement",
    "Structures", "ReliefFloor", "Scatter",
    "FlatDetector", "FlatDatum", "Declared", "FlatSite", "Chords", "Identity", "Materiality", "Verify",
    "NoStep", "Transect", "WithinShape", "Instrument", "Cockpit", "Terrace", "Design",
    "EmitLaw", "RoleSpec", "Authority", "RoleGroup", "Precedence", "Family", "LawTables",
    "Law", "TABLE_FILES", "load_tables",
    "COCKPIT_CLASSES"]

#: The eight files a law directory must contain (owner amendment
#: 2026-09-03; ``flat_site.toml`` per RULINGS 2026-09-05k-2;
#: ``flat_pack.toml`` per the owner's 2026-10-20 flat-pack direction;
#: ``runway_ends.toml`` per RULINGS 2026-10-25a / 26a / 26e; ``terrain_witness.toml``
#: per RULINGS 2026-10-26q, #1359).  None names
#: an airport (RULINGS 2026-10-05e; ``tests/test_no_airport_specific_code``).
TABLE_FILES: tuple[str, ...] = ("rulesets.toml", "zones.toml", "structures.toml", "emit.toml",
                                "precedence.toml", "families.toml", "flat_site.toml",
                                "flat_pack.toml", "runway_ends.toml", "terrain_witness.toml")


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
    #: THE MEAN RUNWAY SLOPE (Annex 14 §3.1.13): (max - min) / length;
    #: ``None`` = the authority states none
    mean_slope_max: CodeTable | None = None
    #: the station spacing its rows are stated at (spec §4)
    mean_slope_station_m: float | None = None
    #: the shoulder's minimum fall (FAA Table 3-6 S-2), RECORDED
    shoulder_transverse_min: float | None = None
    #: the largest grade change inside an END ZONE (FAA §3.16.1 C-E std 2:
    #: none); ``None`` = the curve bound applies there too
    end_zone_max_grade_change: CodeTable | None = None


@_dc.dataclass(frozen=True)
class TaxiLaw:
    """Taxiway-family longitudinal and transverse law."""

    longitudinal: CodeTable
    transverse: CodeTable
    transverse_min: float
    width_m: CodeTable | None = None   # pavement width by letter (2026-09-06t)
    #: metres of vertical curve per ``common.vertical_curve_k_grade_unit``
    #: of grade change, by letter (Annex 14 §3.9.9 / AC §4.14.1 (3)(b))
    curve_k_m: CodeTable | None = None


@_dc.dataclass(frozen=True)
class StripLaw:
    """Graded runway strip: abeam slope and its rate of change."""

    longitudinal: CodeTable
    arc_rate: Rate
    arc_rate_provisional: bool
    #: How far the STRIP runs beyond each runway end (owner RULINGS
    #: 2026-10-12q (1) (a)): the strip's longitudinal cap governs the
    #: ground over this length, the end skirt's down-grade beyond it.
    #: ``None`` = the authority states no strip beyond the end (FAA: the
    #: RSA near-end rule, ``EndSkirtLaw.near_zone_m``, governs instead).
    end_length_m: CodeTable | None = None
    #: ... on an INSTRUMENT runway (owner RULINGS 2026-10-15k (1); Annex 14
    #: §3.4.2: 60 m at every code), where the authority states a separate
    #: figure; ``None`` = the instrument runway reads ``end_length_m``
    end_length_instrument_m: CodeTable | None = None


@_dc.dataclass(frozen=True)
class EndSkirtLaw:
    """Ground beyond the runway end (one profile with the strip's end
    length and the take-off climb surface: ``tables.runway_end_profile``)."""

    max_down_grade: float
    rate: Rate
    rate_provisional: bool
    near_zone_m: float | None = None
    near_max_down_grade: float | None = None
    corridor_length_m: CodeTable | None = None
    #: THE RSA LENGTH beyond each runway end, measured from the runway END
    #: with the blast pad inside it (owner RULINGS 2026-10-15c (2)): the FAA
    #: states it by design group (AC 150/5300-13B App. G dim R); ``None``
    #: = the authority builds it from the strip end length + the RESA
    #: (``tables.runway_safety_area_length_m``)
    rsa_length_m: CodeTable | None = None
    #: the RESA on an INSTRUMENT runway (owner RULINGS 2026-10-15k (1);
    #: Annex 14 §3.5.2-3.5.4); ``None`` = it reads ``corridor_length_m``
    corridor_length_instrument_m: CodeTable | None = None
    #: the RSA length on a PRECISION runway (#811, audit row 7; AC
    #: 150/5300-13B App. G Tables G-2 / G-4 "Lower than 3/4 mile"); ``None``
    #: = it reads ``rsa_length_m``
    rsa_length_precision_m: CodeTable | None = None
    #: THE APPROACH SURFACES beyond an end by the end's approach class
    #: (owner RULINGS 2026-10-15m (1); AC 150/5300-13B Tables 3-2 to 3-4);
    #: ``None`` = the authority reads the climb surface alone (ICAO)
    approach_surface: _t.Mapping[str, tuple[ApproachSurface, ...]] | None = None


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
    #: OWNER RULINGS 2026-10-27s (Q197): A PUBLIC ROAD'S JOINT AT A JUNCTION
    #: (town-street values, ~30 km/h): a grade change up to this needs no
    #: curve (``airport/road_joint``)
    road_joint_free_grade_change: float
    #: ... and a bigger change is spread over at least this many metres of
    #: road per 1 % (``vertical_curve_k_grade_unit``) of change: K
    road_joint_k_m_per_pct: float
    apron_fan_ramp_max: float
    road_transverse_axis_min_deg: float
    runway_crown_transverse: float
    vertical_curve_k_grade_unit: float     # vertical_curve_k_m is metres per THIS much grade
    #: THE END-AROUND TAXIWAY's recognition constants (spec §36)
    eat: EatRecognition
    #: THE RUNWAY CODE NUMBER / LETTER classifier's table (regulation-
    #: conformance spec §3.1/§3.2; ``reference_code``)
    reference_code: ReferenceCode


@_dc.dataclass(frozen=True)
class ZoneClass:
    """Zone-2 geometry for one pavement family."""

    half_width_m: CodeTable
    band_min_down: float
    band_max_down: CodeTable
    half_width_faa_m: CodeTable | None = None
    #: the half-width BY INSTRUMENT STATUS (#811, audit rows 7 / 12;
    #: ``tables.zone2_half_width_m``): ICAO on an instrument runway (Annex 14
    #: §3.4.8), FAA on a precision runway (App. G "Lower than 3/4 mile");
    #: ``None`` = the status reads the table above
    half_width_instrument_m: CodeTable | None = None
    half_width_faa_precision_m: CodeTable | None = None
    #: the zone-2 band's maximum fall under the FAA ruleset, by the AAC's
    #: runway-width letter proxy (RULINGS 2026-10-15l (2), AC 150/5300-13B
    #: Table 3-6 S-3); ``None`` = the ``band_max_down`` table everywhere
    band_max_down_faa: CodeTable | None = None
    #: the zone-2 band's maximum RISE where the authority bounds the
    #: transverse slope in MAGNITUDE only (RULINGS 2026-10-15l (4), ICAO
    #: Annex 14 §3.4.15: no minimum fall beyond the lip); ``None`` = the band
    #: falls by at least ``band_min_down``
    band_max_up: CodeTable | None = None
    #: the zone-1 lip under the FAA ruleset where it differs (AC §4.14.2
    #: item 4, the taxiway: 5 +/- 0.5 %); ``None`` = ``adjacent_ground``'s
    lip_min_down_faa: float | None = None
    lip_max_down_faa: float | None = None


@_dc.dataclass(frozen=True)
class AdjacentGround:
    """The two graded zones and the DEM beyond (RULINGS 2026-08-01)."""

    beyond_zone2: str
    lip_width_m: float
    lip_min_down: float
    lip_max_down: float
    ungraded_max_up: float
    #: beyond a taxi corridor's outer edge, the reach of the
    #: ``ungraded_max_up`` ceiling (``constraints/zones._beyond_graded_ceiling``)
    ungraded_rise_reach_m: float
    #: the blend width of a zone reference across a nearest-edge switch
    #: along one pavement (``constraints/zones._blend_partner``)
    reference_blend_m: float
    groundside_cutback_m: float
    #: §37 (11) THE SHORE DECISION (owner RULINGS 2026-09-29a (4)): the
    #: terrain profile across the last ``shore_profile_run_m`` before the
    #: water line reads a BUILT edge where it drops at least
    #: ``shore_profile_drop_m`` there (``planar/shore``).  Fields below.
    #: (RULINGS 2026-09-29h: the drop calibrated 2.0 -> 3.5 m; the values
    #: live in ``zones.toml`` ONLY — no numeric default here, the law-python
    #: literal twin forbids it)
    shore_profile_drop_m: float
    shore_profile_run_m: float
    runway: ZoneClass
    taxi: ZoneClass
    #: THE END AREA STOPS AT THE TOP OF A DROP (owner RULINGS 2026-10-15g
    #: (C); ``model/end_area``): the raw ground along the extended
    #: centreline stands ``emit.design.edge_min_drop_m`` below the end
    #: profile's lawful fall AND falls steeper than this over
    #: ``emit.design.edge_probe_m`` — PROPOSED, for the owner's ratification
    end_drop_min_grade: float
    #: 19ad THE BAND HOLDS ITS GRADE BESIDE A ROAD THROUGH ZONE 2 (owner
    #: RULINGS 2026-10-20c, 39; ``planar/road_shadow``): a band vertex within
    #: the probe of a road's axis reads the DEM at the probe — the road's
    #: half-width, the stand-off and this many DEM postings past them
    road_shadow_dem_cells: float
    #: THE SERVICE ROAD IN A SAFETY AREA SITS AT GRADE (owner RULINGS
    #: 2026-10-28p (1), #1201): a road of one of these ``highway`` classes
    #: through a RUNWAY band's zone 2 is not cut out of it (20c (39) is
    #: for public roads) — it grades with the safety area
    rsa_at_grade_highways: tuple[str, ...]


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

    #: THE MOUTH DEPTH AS ITS COMPOSITION (owner RULINGS 2026-10-14f (1)):
    #: the road's vertical clearance, the signs / fans over it, the roof
    #: slab and the cover on the roof.  Their sum is :attr:`mouth_depth_m`.
    clearance_m: float
    equipment_m: float
    roof_m: float
    cover_m: float
    wall_gap_m: float
    crest: str
    #: spec §26: the ``tunnel`` values that seed a bore (default ``["yes"]``);
    #: every other value — ``building_passage``, ``culvert``,
    #: ``avalanche_protector``, ``flooded``, ``no`` — never seeds a structure.
    admitted_values: tuple[str, ...]
    ramp_max_grade: float
    #: THE DESIGN GRADE of a ramp no object frames (owner RULINGS
    #: 2026-10-08c (1)): what it is BUILT at; ``ramp_max_grade`` is the
    #: ceiling it steepens toward only where this one cannot top out.
    ramp_grade: float
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
    #: §34 (12) (5) (owner RULINGS 2026-09-16d): A TERRAIN TUNNEL PASSES
    #: UNDER SOMETHING AT GRADE.  The four witnesses a bore with an
    #: on-field mouth is admitted by (``planar/structure_service.
    #: terrain_tunnel_witness``) and (a)'s enclosure class.
    terrain_cover_min_m: float
    terrain_crossing_min_m: float
    terrain_rise_m: float
    terrain_layer_max: int
    enclosure_parking_values: tuple[str, ...]
    object: TunnelObject
    #: §34 (13) (4) (Fable 2026-09-15; RULINGS 2026-09-15y): how far a
    #: mapped road's END may stand from a structure MOUTH and still be
    #: the ROAD BETWEEN TWO MOUTHS (`planar/structure_road`).
    mouth_pair_m: float
    #: THE GROUND OVER A COVERED ROAD (issue #714, ``planar/covered_ground``):
    #: past the covered footprint's edge, how far the ground BESIDE the
    #: cover is read (its highest DEM sample) on each side of a bore.
    covered_side_probe_m: float
    #: ... the cut's RIM is where the DEM first climbs this fraction of
    #: the way from the floor to the highest ground within the search.
    covered_rim_rise_frac: float
    covered_rim_search_m: float
    #: #971 (owner RULINGS 2026-10-19e/n/o): the farthest a mapped mouth
    #: slides out along its approach to stand clear of the pavement it may
    #: not cut (``planar/structure_mouth.clear_mouth``); beyond, the bore
    #: is refused by name.
    mouth_slide_max_m: float

    @property
    def mouth_depth_m(self) -> float:
        """THE MOUTH DEPTH (owner RULINGS 2026-10-14f; supersedes the clearance-only
        ``bore_datum_m`` of 2026-09-03b / 09-08l): the road surface at the
        portal face stands this far under the GROUND above it — clearance +
        equipment + roof + cover.  The one derivation every reader takes."""
        return float(self.clearance_m + self.equipment_m + self.roof_m + self.cover_m)

@_dc.dataclass(frozen=True)
class Channel:
    """THE OPEN CHANNEL (spec §45; owner RULINGS 2026-09-15i) — a road /
    rail corridor under a STATED CROSSING that keeps its own floor
    through the field.  Its identification, its merge and its default
    bank; the depth comes from ``[tunnel] bridge.clearance_m`` and the
    grade from ``[tunnel] ramp_max_grade`` — a channel invents no second
    copy of either."""

    #: §45 (1): the road/rail ways sharing the corridor within this are
    #: ONE channel.  Ruled EQUAL to ``dual_carriageway_max_separation_m``
    #: (40 m) — stated here so the two can be read apart if they ever part.
    merge_m: float
    #: §45 (5): the default bank where no witness states its shape —
    #: 1:2, i.e. rise/run = 0.5.
    bank_slope: float
    #: §45 (1) (b): a paved NECK of the pavement union across the
    #: corridor is a deck only while it is plausibly a crossing and not
    #: the field itself — a run longer than this along the road is
    #: pavement the road runs UNDER for its whole length, not a deck.
    deck_max_width_m: float
    #: §45 (1): a neck whose UNPAVED flank on either side is shorter than
    #: this is a road crossing a taxiway, not a deck over a channel.
    corridor_min_length_m: float
    #: §45 (1), the lane's MEASURED DEVIATION (reported, never decided):
    #: the corridor never reaches wider than this from the axis.  The
    #: TOML comment carries the measurement.
    corridor_max_half_width_m: float
    #: §45 (12): a channel witnessed by a NECK alone, whose floor comes
    #: from (3) (iii), needs this many crossings — one neck is a
    #: crossing, not a channel.  The TOML comment carries the site.
    min_decks_without_depth: int
    #: The station spacing the floor profile and the banks are sampled at.
    station_m: float
    #: §45 (1) (c): a pack solid whose plan runs along the axis and whose
    #: deepest genuine solid stands at least this far under the corridor's
    #: crest is a WALL/FLOOR witness (the 05k-1 authority: seat = floor).
    object_min_depth_m: float
    #: §45 (3) (ii): the DTM floor is read as the MINIMUM over a window
    #: this wide across the axis at each station (the bank toes are in the
    #: corridor; the floor is what lies between them).
    lidar_floor_window_m: float
    toe_rise_m: float
    toe_confirm_m: float


@_dc.dataclass(frozen=True)
class Bridge:
    """Bridge deck law (RULINGS 2026-08-28; memory othh-bridge-deck-datum-r12)."""

    clearance_m: float
    clearance_minimum_m: float
    #: spec §34 (6): how far past a terrain deck's mapped end the governed
    #: cell that end MEETS may stand (OSM stops a service road at the
    #: apron's edge, not on it).
    deck_end_reach_m: float
    #: §34 (12) (4) (owner RULINGS 2026-09-15ap): the DEM drop under a
    #: deck's span, against the mean of its abutments, that witnesses a
    #: cutting; and how far along the deck an abutment is sampled.
    deck_cut_witness_m: float
    deck_abutment_m: float
    deck_group_gap_max_m: float
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
    #: THE LANDING BANK'S WIDTH (owner RULINGS 2026-10-03e, #290): the 1:3
    #: bank around a viaduct ramp landing (``planar/landing``).  The unit
    #: platform's collar it was first written for is deleted (spec §56 (3))
    platform_collar_max_m: float
    #: flat-pad spec §1 / §6 Q5 (owner RULINGS 2026-09-30f): the platform's
    #: welded frontage is HELD at its block datum in stage 1 (false = 29s)
    frontage_hold: bool
    #: flat-pad spec §2 (1): the DEM proxy's allowance in the mint-time test
    frontage_hold_margin_m: float
    #: flat-pad spec §2 (4) (e) / §6 Q4: a unit needing more blocks STOPS
    frontage_blocks_max: int
    #: owner RULINGS 2026-10-19ai (#809): a held block's unit whose parts
    #: stand at least this far under its frontage level carries a LOWER
    #: level (``planar/low_level``); ``0`` disarms it
    low_level_min_step_m: float = 0.0
    #: THE TERMINAL PAD TAKES ITS JETWAYS (owner RULINGS 2026-10-16b (1);
    #: ``airport/jetways.py``): ``None`` = no expansion
    jetway_root_reach_m: float | None = None
    jetway_half_width_m: float | None = None
    jetway_cab_m: float | None = None
    jetway_token: str | None = None
    #: RULINGS 2026-10-20d (spec ``road-edge-drop-spec.md`` R2): a pad fill
    #: that cannot bank down takes the ground to every road strip within
    #: this; ``0`` disarms it (WORKING VALUE, awaiting the owner)
    fill_road_reach_m: float = 0.0


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
    #: §42 (1b) THE HARD GROUND PLANE (lane ``nlwf``, issue #20): a
    #: resource declaring NO draped layer group whose EVERY triangle stands
    #: within ``draped_y_tol_m`` of Y = 0 and which carries ``ATTR_hard``
    #: is a pavement too — X-Plane rolls aircraft on it (NLWF
    #: ``pavement/vele_apron.obj``, 1,499 m2, the pack's whole apron)
    object_pavement_hard_planes: bool
    #: THE GAP SHEET (owner RULINGS 2026-10-04o (a)): a pavement page is
    #: judged flat PER TRIANGLE; it is kept, as GAP PIECES ONLY, when the
    #: off-plane triangles' share of its plan area is at most this
    #: (HECA ``ground/asphalt.obj``: 458 of 1,645,011 m2 = 0.00028).
    #: 0 = off (the whole-page refusal).
    gap_sheet_offplane_max_share: float
    #: §44 (2) THE PAVEMENT BORROW (owner RULINGS 2026-09-15f): a custom
    #: pack whose row-110 union covers LESS than this fraction of the
    #: Global Airports block's borrows Global's pavement (and its row-130
    #: boundary when it has none) — ``airport/borrow.py``.  0 = off,
    #: 1 = always where a Global block exists.
    pavement_borrow_coverage_max: float


@_dc.dataclass(frozen=True)
class Structures:
    """structures.toml."""

    tunnel: Tunnel
    channel: Channel
    bridge: Bridge
    building_pad: BuildingPad
    skirt: Skirt
    basin: Basin
    cutout: Cutout
    retaining_wall: RetainingWall
    rebake: Rebake
    placement: Placement
    load: LoadLaw
    #: §49: the deck-face datum (``[deck]``); defaulted so a law dir
    #: without the table still loads
    deck: Deck = _dc.field(default_factory=Deck)
    #: THE SCATTER CLASS (``[scatter]``, spec pack-read-once-fast §B.2):
    #: the predicate's two thresholds.  NOTHING CONSULTS IT YET — slice
    #: S5a landed the predicate and the dry census only.  Defaulted like
    #: ``deck``.
    scatter: Scatter = _dc.field(default_factory=Scatter)
    #: THE BUILDING BASE PROFILE (``[base_profile]``, base-profile spec
    #: §1; owner RULINGS 2026-10-01f/k): the four numbers the base read
    #: needs.  Defaulted like ``deck`` / ``scatter``, so a law dir
    #: without the table still loads and the read falls back to its
    #: measured defaults.
    base_profile: BaseProfileLaw = _dc.field(default_factory=BaseProfileLaw)
    #: A WALLED PLATE CAPS A RUNWAY'S SAFETY AREA (``[walled_plate]``, owner
    #: RULINGS 2026-10-27t/u, #1201): the recognition's numbers.  Defaulted
    #: like ``base_profile``.
    walled_plate: WalledPlateLaw = _dc.field(default_factory=WalledPlateLaw)


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
    #: §46 (4): the grid every INPUT coordinate is snapped to at entry to
    #: the airport's metric frame.  Not an identity parameter — the
    #: identity is ``coordinate_dp`` and does not move — but it lives here
    #: because it is the other half of "what a coordinate IS" in v2.
    input_quantum_m: float
    min_distinct_spacing_m: float
    weld_spacing_m: float
    dsf_pavement_admission_m: float
    #: #119: the CIFP COORDINATE JOIN's radius — an apt.dat end whose
    #: designator matches no CIFP record takes the one record whose landing
    #: threshold lies within this of its own (``airport/cifp.match_threshold``)
    cifp_threshold_join_m: float

@_dc.dataclass(frozen=True)
class Materiality:
    """Residual floors and the step threshold."""

    elevation_m: float
    grade: float
    step_m: float
    runway_step_m: float


@_dc.dataclass(frozen=True)
class NoStep:
    """Airside no-step pairs (RULINGS 2026-08-27; 2026-09-04o/04q: the window
    and K are ROUTE distances).  ``metric`` = ``"route"`` (along the taxi
    network; a chord metric is the refuted 08-27 reading)."""

    window_m: float
    k: int
    metric: str
    #: the turn beyond which a ring triple is not a travel profile (the
    #: taxiway curve rate's reach; ``tables.airside_rate_per_m``)
    rate_profile_turn_max_deg: float | None = None


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
    covers, ``half_width_m`` each side of an integer lat/lon line — and
    ``ask_reach_m``, how far past its own apt.dat airside the airport may
    still emit airside geometry (the boundary dialog's reach, spec
    ``insets-follow-patch-set-spec.md`` §C.1)."""

    half_width_m: float
    ask_reach_m: float


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
    #: §2-SUPPLEMENT S.1 (3): the run-out, in arclength along the way,
    #: from the nearest in-band station
    runout_m: float
    #: S.3: the deviation budget the class cap yields to
    budget_m: float
    #: S.3: nothing above this is a road any class drives
    cap_ceiling: float
    #: S.3: the per-class longitudinal caps (OSM ``highway`` value, else
    #: ``railway:<value>``).  A class absent here takes the core's
    #: ``road_grade_limit``.
    class_caps: _t.Mapping[str, float]
    #: OWNER RULINGS 2026-10-22h: the PUBLIC classes (``highway`` values)
    #: whose in-band segments follow the terrain up to ``cap_ceiling``
    #: (``O4_Vector_Utils.road_inside_cap``); every other class keeps the
    #: patch's ``road_grade_limit``
    public_classes: tuple[str, ...] = ()


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
    #: THE DESIGN GRADE of the ramp a groundside road leaves its airside
    #: contact on (§37 (6); owner RULINGS 2026-10-09c (2b)): what it is
    #: BUILT at; the road role's longitudinal cap is the ceiling it
    #: steepens toward only where the run cannot fit this
    ramp_grade: float
    #: THE MOST A PAD MOVES FOR ITS ROAD (owner RULINGS 2026-10-13d "road
    #: ramps first, pad takes the remainder, capped"): where no ramp inside
    #: the road cap fits between a pad and its road's other standing end,
    #: the pad takes the remainder up to this, as one rigid pad; beyond it
    #: the road ends at a step (``constraints/pad_road_reach``)
    pad_shift_max_m: float
    #: contact roles BESIDE the airside value roles (apron, pad, the taxi
    #: family, the runway family with §40's shoulder): §37 (10)'s LOT,
    #: which precedence.toml partitions groundside but which is hard
    #: surface a road meets at a stated level
    extra_roles: tuple[str, ...] = ()


@_dc.dataclass(frozen=True)
class Verify:
    """``emit.toml [verify]``: how the VERIFY stage's structural-DEFECT
    gate reads a row (owner RULINGS 2026-09-14bx)."""

    #: THE DEFECT MATERIALITY FLOOR: a DEFECT row whose EXCESS beyond its
    #: own cap over its own span is under this many metres stays a census
    #: violation and is NAMED in the engine log, but never aborts the
    #: tile.  0.15 pp over 30 m -- the LEMD row that killed the +40-004
    #: tile on 1.0.339 -- is 4.6 cm.
    defect_min_excess_m: float


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
    #: [verify]: the structural-DEFECT gate's materiality floor (14bx)
    verify: Verify
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
    #: RULINGS 2026-09-08u (2): both structure ramps are read at the road
    #: ramp law ``tunnel.ramp_max_grade`` — the pairs the object-framed
    #: lift (2026-10-07e) does not take: the ramp's seams with its
    #: neighbours.
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
    flat_pack: FlatPack
    #: THE RUNWAY-END PIN RULE (RULINGS 2026-10-25a / 26a / 26e)
    runway_ends: RunwayEnds
    #: THE TERRAIN WITNESS (#1359, RULINGS 2026-10-26q)
    terrain_witness: TerrainWitness


# ── the loader ───────────────────────────────────────────────────────────

_ROLE_FAMILIES = ("runway", "taxi", "common", "none")
_SIDES = ("airside", "groundside")
_PAIRS = ("within", "cross", "steps")
_SOLVERS = ("edge", "pin", "flat", "band", "offset", "construction",
            "diagnostic")
#: ``crest`` gains ``"design"`` (spec §45 (5); owner RULINGS 2026-09-15i):
#: a CHANNEL's wall crest is the SOLVED surface of the governed cell at the
#: corridor edge, never ``DEM(x, y)`` — which at LGAV stands 2–4 m under the
#: real rim.  Bores keep ``"dem"`` (09-03b, no change to any tunnel).
_DATUMS = {"beyond_zone2": ("dem",), "crest": ("dem", "design"),
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
    # §44 (2) (owner RULINGS 2026-09-15f): the borrow key is a COVERAGE
    # FRACTION — 0 turns the borrow off, 1 fires it wherever a Global
    # Airports block exists; anything outside is not a coverage.
    cbm = t.structures.load.pavement_borrow_coverage_max
    if not (0.0 <= cbm <= 1.0):
        raise LawError(f"load.pavement_borrow_coverage_max {cbm} is not a "
                       "coverage fraction in [0, 1] (§44 (2))")
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
    # RULINGS 2026-09-08u (2), 2026-10-07d/07e: an object-framed ramp's own
    # grade is uncapped (the lift); what the oracle still prices on BOTH
    # structure ramps — their seams — it prices at the road ramp law, ONE
    # number, ``structures.tunnel.ramp_max_grade``
    for r in ("door_ramp", "wall_corridor_ramp"):
        spec = t.precedence.roles.get(r)
        if spec is not None and spec.oracle_cap != t.structures.tunnel.ramp_max_grade:
            raise LawError(f"precedence.roles.{r}.oracle_cap {spec.oracle_cap} is not "
                           "structures.tunnel.ramp_max_grade "
                           f"{t.structures.tunnel.ramp_max_grade} (08u (2); 07d)")
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
    # RULINGS 2026-10-08c (1): the cap is a ceiling, never the grade a ramp is
    # built at — the design grade stands at or under it
    if not 0.0 < t.structures.tunnel.ramp_grade <= t.structures.tunnel.ramp_max_grade + 1e-12:
        raise LawError(
            f"structures.tunnel.ramp_grade {t.structures.tunnel.ramp_grade} is not in "
            f"(0, ramp_max_grade {t.structures.tunnel.ramp_max_grade}] (RULINGS 2026-10-08c (1))")
    # RULINGS 2026-10-09c (2b): the same law for the groundside road's ramp —
    # its design grade stands at or under every road role's own cap
    road_caps = [t.common.roles[r].longitudinal
                 for r in t.families["road_cross_section"].roles if r in t.common.roles]
    rg = t.emit.road_contact.ramp_grade
    if not 0.0 < rg <= min(road_caps, default=rg) + 1e-12:
        raise LawError(
            f"emit.road_contact.ramp_grade {rg} is not in (0, the road cap "
            f"{min(road_caps, default=rg)}] (RULINGS 2026-10-08c (1), 2026-10-09c (2b))")
    gr_cap = t.common.roles.get("garage_ramp")
    _check_cutout(t.structures.cutout, LawError,
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
    _check_flat_pack(t.flat_pack, LawError)
    _check_runway_ends(t.runway_ends, LawError)
    _check_terrain_witness(t.terrain_witness, LawError)
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
        flat_pack=_build(FlatPack, _read(d, "flat_pack.toml"), "flat_pack"),
        runway_ends=_build(RunwayEnds, _read(d, "runway_ends.toml"), "runway_ends"),
        terrain_witness=_build(TerrainWitness, _read(d, "terrain_witness.toml"),
                               "terrain_witness"))
    _check_cross_refs(tables)
    return tables


# ── the Law bound to one airport ─────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Law:
    """The tables plus the ruleset that governs ONE airport.  Every
    consumer (constraint generators, emit, verify) reads through this."""

    tables: LawTables
    ruleset_key: str
    #: the airport this law is bound to, upper-case ("" = none) — for the
    #: ruleset resolution (a rule by identifier CLASS), the owner's flat-
    #: site declaration and report lines; NO law table is keyed by it
    #: (RULINGS 2026-10-05e)
    icao: str = ""

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
        return cls(tables=tables, ruleset_key=key,
                   icao=str(icao or "").strip().upper())
