"""The airport INPUTS — plain dataclasses in ONE local metric frame
(plan §1 row 1).  Loaders (M1, ``airport/``) produce these from apt.dat,
CIFP, OSM, the DEM + insets, DSF objects and the scenery pack; nothing
downstream reads a source file.

Every coordinate is ``(x, y)`` metres in :class:`~.frame.Frame`; every
elevation is metres above the ellipsoid-corrected geoid the DEM uses.
Identity: apt.dat and OSM ids are kept as given so a constraint's
``source`` can name the input row.  No shapely / numpy here.
"""
from __future__ import annotations

import dataclasses as _dc
import enum
import typing as _t

from .frame import LL, XY, Frame

Ring = tuple[XY, ...]
"""A closed ring: first vertex NOT repeated; orientation as loaded."""

__all__ = [
    "Ring", "Surface", "RunwayEnd", "Runway", "Pavement", "LinearFeature",
    "TaxiNode", "TaxiEdge", "GroundRoute", "Boundary", "Startup",
    "OsmWay", "Building", "FacadeEdge", "FacadeRead", "DemSample", "DsfObject", "SceneryPack",
    "FlatVerdict", "FlatPackVerdict", "Airport", "GAP_SHEET_PREFIX",
]

#: the id prefix of a GAP SHEET body (``Airport.gap_sheets``; owner RULINGS
#: 2026-10-04o (a)) — ``dsf:gapsheet<k>``
GAP_SHEET_PREFIX = "dsf:gapsheet"


class Surface(enum.IntEnum):
    """apt.dat surface codes (1100/1200 spec)."""

    ASPHALT = 1
    CONCRETE = 2
    TURF = 3
    DIRT = 4
    GRAVEL = 5
    DRY_LAKEBED = 12
    WATER = 13
    SNOW = 14
    TRANSPARENT = 15


#: ``RunwayEnd.pin_flags`` of an end whose CIFP record the installed layout
#: and the imagery outvoted (#1359, owner RULINGS 2026-10-26v,
#: ``airport/runway_end_witness``): the record is dropped, and the end
#: follows the lidar (``constraints/runway_profile.end_pin_cases``).
PIN_OUTVOTED = "q1"


@_dc.dataclass(frozen=True)
class RunwayEnd:
    """One end of a runway (apt.dat row 100, one half).

    ``threshold_elev_m`` is the CIFP threshold elevation, ABSOLUTE and
    pinned (RULINGS :511-516); ``None`` when CIFP has no record for the
    end (the loader reports it — the profile then has one pin fewer,
    never an invented one, plan §2)."""

    name: str
    xy: XY
    ll: LL
    displaced_m: float
    overrun_m: float
    threshold_elev_m: float | None
    cifp_source: str
    #: THE END'S APPROACH CLASS (owner RULINGS 2026-10-15m (2) / 15n;
    #: ``airport/approach.end_approach``): ``visual`` / ``npa`` / ``apv`` /
    #: ``pa`` (``law.reference_code``).  The RAOA binds before a ``pa`` end.
    approach: str = "visual"
    #: Cat II/III: apt.dat ALSF-II / Calvert II lighting with touchdown-zone
    #: lights at a precision end (15m (2))
    cat_ii_iii: bool = False
    #: THE PIN'S STATION (issue #1358, ``airport/end_pins``): how far along
    #: the runway from THIS end the height pin sits — the joined CIFP
    #: record's own landing threshold projected onto the axis; ``None`` =
    #: the apt.dat landing threshold (``displaced_m``).  Read through
    #: :meth:`pin_along`, never directly.
    pin_along_m: float | None = None
    #: THE PIN'S ORIGIN (owner RULINGS 2026-10-25a / 26a / 26e;
    #: ``airport/end_pins``): ``cifp`` (verified), a cross-check source name
    #: (``ourairports`` …: ``threshold_elev_m`` is ITS value), ``dem`` (a
    #: flagged CIFP end the DEM decides, ``threshold_elev_m`` = None), or
    #: ``""`` (no CIFP record: the apt.dat datum / 22a DEM end).
    pin_source: str = ""
    #: the CIFP elevation AS READ, kept when verification replaced it
    cifp_elev_m: float | None = None
    #: the verification flags that fired on this end's runway (``a``,
    #: ``b``, ``c``), comma-joined; ``""`` = none; :data:`PIN_OUTVOTED` when
    #: the terrain witness dropped the end's CIFP record (#1359, 26v)
    pin_flags: str = ""

    def pin_along(self) -> float:
        """Metres from this end to its pin's station (``pin_along_m``,
        else the apt.dat displaced length)."""
        return float(self.displaced_m if self.pin_along_m is None else self.pin_along_m)


@_dc.dataclass(frozen=True)
class Runway:
    """apt.dat row 100."""

    id: str
    width_m: float
    surface: Surface
    ends: tuple[RunwayEnd, RunwayEnd]
    code_number: int | None
    code_letter: str | None
    #: THE INSTRUMENT STATUS (owner RULINGS 2026-10-15k (3), 15m (2), 15n):
    #: either END has an approach (``RunwayEnd.approach`` other than
    #: ``visual``); none -> non-instrument.  The law tables read the RESA
    #: and the strip's end length by it.
    instrument: bool = False
    #: THE SHOULDER WIDTH beyond each runway edge, metres, from the apt.dat
    #: row-100 shoulder code (``airport.apt_dat.shoulder_width_m``; owner
    #: RULINGS 2026-10-20n): the runway's graded band reads it as its §40
    #: shoulder where no pavement already covers it
    #: (``classify/apt_shoulder``).  0 where the row states no width.
    shoulder_m: float = 0.0

    @property
    def length_m(self) -> float:
        """Centreline length between the two end points."""
        (ax, ay), (bx, by) = self.ends[0].xy, self.ends[1].xy
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    @property
    def slab_corners(self) -> tuple[XY, XY, XY, XY]:
        """THE RUNWAY SLAB's four corners in the frame: physical end to
        physical end (the apt.dat ends plus each end's blast pad /
        overrun) at the declared width.  The ONE derivation of the slab's
        geometry: ``classify.evidence.runway_rectangle`` polygonises it
        and ``constraints.strips.runway_groups`` fits the strip footprint
        to it (§40 (1) — the strip axis is the RUNWAY's, never a fit to
        whatever else carries the runway role, e.g. a shoulder)."""
        (ax, ay), (bx, by) = self.ends[0].xy, self.ends[1].xy
        L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 or 1.0
        ux, uy = (bx - ax) / L, (by - ay) / L
        ax, ay = ax - ux * self.ends[0].overrun_m, ay - uy * self.ends[0].overrun_m
        bx, by = bx + ux * self.ends[1].overrun_m, by + uy * self.ends[1].overrun_m
        px, py = -uy * self.width_m / 2, ux * self.width_m / 2
        return ((ax + px, ay + py), (bx + px, by + py),
                (bx - px, by - py), (ax - px, ay - py))


@_dc.dataclass(frozen=True)
class Pavement:
    """apt.dat row 110 (taxiway / apron polygon), beziers flattened.

    ``source`` is ``""`` for the pack's own row and
    ``"global_airports"`` for a row §44's PAVEMENT BORROW appended
    (``airport/borrow.py``); it carries no role and no privilege — it
    says where the record came from."""

    id: str
    surface: Surface
    outer: Ring
    holes: tuple[Ring, ...]
    description: str = ""
    source: str = ""


@_dc.dataclass(frozen=True)
class LinearFeature:
    """apt.dat row 120: painted line (taxi centreline etc.) — a
    smoothing refinement only, never a surface authority (RULINGS
    :45-50)."""

    id: str
    line_type: int
    points: tuple[XY, ...]
    closed: bool


@_dc.dataclass(frozen=True)
class TaxiNode:
    """apt.dat row 1201."""

    id: int
    xy: XY
    usage: str


@_dc.dataclass(frozen=True)
class TaxiEdge:
    """apt.dat row 1202 (aircraft) — the reach follows these only
    (memory ``reach-follows-centerlines``)."""

    a: int
    b: int
    name: str
    one_way: bool
    is_runway: bool
    width_class: str | None


@_dc.dataclass(frozen=True)
class GroundRoute:
    """apt.dat row 1206 (ground-vehicle route edge) — authoritative
    service-road routing (RULINGS free-road :28-30)."""

    a: int
    b: int
    name: str
    one_way: bool


@_dc.dataclass(frozen=True)
class Boundary:
    """apt.dat row 130.  ``source`` as on :class:`Pavement` (§44 (3): the
    Global boundary is borrowed ONLY when the pack authored none)."""

    id: str
    outer: Ring
    holes: tuple[Ring, ...]
    source: str = ""


@_dc.dataclass(frozen=True)
class Startup:
    """apt.dat row 1300."""

    name: str
    xy: XY
    heading_deg: float
    kind: str


@_dc.dataclass(frozen=True)
class OsmWay:
    """An OSM way with the TAGS OF INTEREST only: ``highway``,
    ``bridge``, ``tunnel``, ``layer``, ``aeroway``, ``building``,
    ``service``, ``access``, ``name``.  Roads (big/small feeds) and
    airport-area ways share this type; ``kind`` says which feed."""

    id: int
    kind: str
    points: tuple[XY, ...]
    closed: bool
    tags: _t.Mapping[str, str]


@_dc.dataclass(frozen=True)
class FacadeEdge:
    """One wall edge of a placed facade that ATTACHES something: ``a`` ->
    ``b`` in the frame, the widest outward reach of its attachments and
    the object that sets it (``airport/facade.py``, spec §52)."""

    a: XY
    b: XY
    reach_m: float
    wall: str
    obj: str
    vehicle: bool


@_dc.dataclass(frozen=True)
class FacadeRead:
    """What the ``.fac`` FILE says of a placed facade (spec §52): its
    class (``line`` / ``roofed`` / ``lot`` / ``parking_structure``), the
    attaching edges, and how many edges had NO decidable wall (a polygon
    with no DSF wall index whose fitting walls differ)."""

    def_path: str
    cls: str
    edges: tuple[FacadeEdge, ...] = ()
    undecided: int = 0


@_dc.dataclass(frozen=True)
class Building:
    """A building footprint (OSM ``building=*`` or a DSF object's
    footprint) with its pad law inputs (RULINGS 2026-09-01g/i)."""

    id: str
    outer: Ring
    holes: tuple[Ring, ...]
    source: str
    height_m: float | None
    levels: int | None
    dsf_object: "DsfObject | None" = None
    #: the facade file's own reading, for a ``dsf:fac`` / ``dsf:lot:fac``
    #: footprint (``None``: not a facade, unresolved, or a capture older
    #: than the reader)
    facade: "FacadeRead | None" = None


class DemSample(_t.Protocol):
    """The DEM + insets sampler interface.  ``z(x, y)`` is the terrain
    elevation at a frame point (bilinear over the effective raster —
    Ortho4XP's smoothed tile DEM with the airport insets applied);
    ``provenance`` names the rasters (recorded in ``frame.json``).
    v2 never mutates the DEM; a vertex with no sample is an error at
    planar-map build (plan §2)."""

    provenance: _t.Mapping[str, str]

    def z(self, x: float, y: float) -> float: ...

    def bounds(self) -> tuple[float, float, float, float]:
        """``(xmin, ymin, xmax, ymax)`` of valid samples in the frame."""
        ...


@_dc.dataclass(frozen=True)
class DsfObject:
    """A placed DSF object.  ``resolved_path`` is the OBJ8 file the
    placement resolves to (pack-relative first, then the library index;
    ``None`` = unresolved, reported) — the structure pass reads the
    geometry from it (``airport/obj8.py``, M4b): hard-deck footprint and
    deck TOP (memory ``othh-bridge-deck-datum-r12``), below-grade solids.
    ``y_offset_m`` is the ``OBJECT_AGL`` offset or the ``OBJECT_MSL``
    elevation (0 for a plain ``OBJECT``); ``kind`` names the row."""

    id: str
    path: str
    xy: XY
    heading_deg: float
    footprint: Ring | None
    hard_deck: bool
    deck_top_m: float | None
    y_offset_m: float
    resolved_path: str | None = None
    kind: str = "OBJECT"


@_dc.dataclass(frozen=True)
class SceneryPack:
    """The scenery signature: apt.dat + DSF ONLY (RULINGS :75).

    §44 (4) (owner RULINGS 2026-09-15f): ``borrowed_apt_dat_path`` /
    ``borrowed_block_sha256`` name the GLOBAL AIRPORTS block this pack
    borrowed its pavement from (both ``""`` when nothing was borrowed) —
    the signature carries them, so a Global Airports update invalidates
    every cache keyed on it."""

    name: str
    apt_dat_path: str
    apt_dat_sha256: str
    dsf_paths: tuple[str, ...]
    dsf_sha256: tuple[str, ...]
    borrowed_apt_dat_path: str = ""
    borrowed_block_sha256: str = ""
    #: the airport block's ``1302 flatten 1`` metadata: the author asked
    #: X-Plane to flatten the airport (owner answer 65, 2026-10-20: "a
    #: strong clue the author was not planning for terrain")
    flatten_declared: bool = False
    #: the pack's folder when it is not the one holding ``apt_dat_path``
    #: (an objects-only COMPANION, ``airport/companion``; an OBJECT PACK
    #: serving a Global Airports block, ``airport/object_pack``, #1630);
    #: ``""`` = the folder two levels above ``apt_dat_path``
    root: str = ""

    @property
    def pack_root(self) -> str:
        """The folder the pack's DSF and objects resolve in: ``root``, else
        the folder two levels above ``apt_dat_path`` (``""`` with neither)."""
        if self.root or not self.apt_dat_path:
            return self.root
        import os
        return os.path.dirname(os.path.dirname(self.apt_dat_path))


@_dc.dataclass(frozen=True)
class FlatVerdict:
    """The FLAT-SITE verdict (RULINGS 2026-09-05k-2; ``airport/flat_site.py``
    measures it, ``constraints/flat_site.py`` prices it).  ``verdict`` ∈
    ``flat_candidate | not_flat | lidar_credible | no_data |
    flat_declared``; ``auto_verdict`` is what the detector measured even
    when a ``[declared]`` entry overrode it (v1's audit); ``z0_m`` the
    datum (``None`` when there is none to grade to); ``source`` names it
    (``cifp`` | ``pack_seats`` | ``metres``); ``region`` is pavement ∪
    boundary ⊕ margin as ``(outer, holes)`` rings in the frame — the
    preference's extent; ``signals`` the S1..S4 evidence (plain values,
    reported verbatim)."""

    verdict: str
    auto_verdict: str
    z0_m: float | None
    source: str
    region: tuple[tuple[Ring, tuple[Ring, ...]], ...]
    signals: _t.Mapping[str, _t.Any]

    @property
    def substitutes(self) -> bool:
        """Whether the datum is priced: a flat candidate or a declared
        site with a datum to grade to."""
        return self.z0_m is not None and self.verdict in (
            "flat_candidate", "flat_declared")


@_dc.dataclass(frozen=True)
class FlatPackVerdict:
    """THE FLAT-PACK WITNESS (owner direction 2026-10-20, answers 59-66;
    ``airport/flat_pack.py`` measures it at load, spec
    ``flat-pack-terracing-spec.md`` §1).  ``verdict`` ∈ ``flat_assumed |
    follows_terrain | no_data``; ``witness`` names what decided it
    (``seats``, ``flatten_flag``, both joined by ``+``, or ``""``);
    ``level_share`` the share of the pack's grounded objects at ONE level,
    ``level_m`` that level, ``relief_m`` the p95 − p5 of the ground under
    them; ``signals`` the rest of the evidence (plain values, reported
    verbatim).  A REPORT in phase 1: nothing grades by it."""

    verdict: str
    witness: str
    level_share: float | None
    level_m: float | None
    relief_m: float | None
    signals: _t.Mapping[str, _t.Any]


@_dc.dataclass(frozen=True)
class Airport:
    """Everything the producers need, loaded ONCE."""

    icao: str
    name: str
    frame: Frame
    elevation_m: float
    runways: tuple[Runway, ...]
    pavements: tuple[Pavement, ...]
    linear_features: tuple[LinearFeature, ...]
    taxi_nodes: _t.Mapping[int, TaxiNode]
    taxi_edges: tuple[TaxiEdge, ...]
    ground_routes: tuple[GroundRoute, ...]
    boundaries: tuple[Boundary, ...]
    startups: tuple[Startup, ...]
    osm_ways: tuple[OsmWay, ...]
    buildings: tuple[Building, ...]
    dsf_objects: tuple[DsfObject, ...]
    pack: SceneryPack
    dem: DemSample
    ruleset_key: str
    #: The flat-site verdict, measured after the load (``pipeline`` sets it
    #: through ``dataclasses.replace``); ``None`` before the detector ran.
    flat_site: FlatVerdict | None = None
    #: THE FLAT-PACK WITNESS, measured at load once the pack partition is
    #: read (``airport/flat_pack.detect``); ``None`` before it ran.  A
    #: report in phase 1 (``law/flat_pack.toml`` ``terrace = false``).
    flat_pack: FlatPackVerdict | None = None
    #: THE PACK PARTITION, read ONCE at load (owner RULINGS 2026-09-11j;
    #: spec §11a (3)) — ``airport.pack_partition.PackPartition``.  The
    #: pack is a load-stage input like the DEM, and the pad law needs its
    #: BODIES and ABUTMENTS before ``classify`` runs.  ``None`` where the
    #: caller never read a pack (fixtures, ``explain``).  Typed loosely:
    #: ``model`` stays importable without the airport package.
    partition: _t.Any = None
    #: THE CANOPY-AND-BUILDING GROUPS derived from it (``planar/group.py``
    #: ``GroupSet``, owner RULINGS 2026-09-11i) — the ONE derivation, read
    #: by the pad law and by the placement plan.  Same ``None`` rule.
    groups: _t.Any = None
    #: §16g / §30 (4) THE FOOTPRINT UNITS large enough to be TERMINAL
    #: CLUSTERS (``planar/cluster.py`` ``PlanCluster``, owner RULINGS
    #: 2026-09-13bj item 1 / 13bo), derived from the partition at load
    #: beside the groups — the design surface gives each ONE pad (and the
    #: JETWAY STRIP levels the apron at its rider edges, jetway-strip spec).
    #: ``constraints`` may not import ``planar``, so the relation travels
    #: here.  Same ``None`` / empty rule as ``groups``.
    clusters: _t.Any = None
    #: issue #516 THE SUNKEN RAMPS' GROUND (``airport/sunken_ramp``,
    #: owner RULINGS 2026-09-13bi / 13cm): the planar-frame union of the
    #: ground under a unit member's sloped deck where it rises through the
    #: natural ground, which leaves the cluster pads like a deck shade.
    #: Derived at load beside the clusters; the pad MINT (``classify``) and
    #: its CENSUS (``constraints``, which may not import ``airport``) both
    #: read THIS.  ``None`` = not derived (a capture written before it).
    sunken_ramps: _t.Any = None
    #: issue #1633 THE RETAINING WALLS' FOOTPRINTS (``airport/wall_shade``):
    #: a wall that retains its own height is a step between two levels,
    #: never a flat pad, so its footprint leaves every pad outline like a
    #: deck shade.  Same reader rule as ``sunken_ramps``; ``None`` = none,
    #: or not derived (a capture written before it).
    wall_shade: _t.Any = None
    #: issue #1633 round 3 THE RETAINING WALLS READ AS TWO LEVELS
    #: (``airport/wall_sides.WallSides``: footprint, upper and lower side
    #: bands, smear, the object's top): a road is never on both sides of
    #: one, and nothing answers, merges or grades across it.  Derived with
    #: ``wall_shade``; empty = none, or not derived.
    retaining_walls: tuple = ()
    #: owner RULINGS 2026-10-27t/u (#1201): THE RUNWAY-END WALLED PLATES
    #: (``model.walled_plate.WalledPlate``, recognised on the pack reading by
    #: ``airport/walled_plate``): the end area stops at each one's inner edge
    #: (``model/end_area``), the ground under it stays below it
    #: (``constraints/walled_plate``).  Empty = none (or a capture written
    #: before them).
    walled_plates: tuple = ()
    #: THE FEET OF THE PACK'S OBJECT RAMPS (issue #669; owner RULINGS
    #: 2026-10-14c (5); ``airport/ramp_feet``): derived at load beside the
    #: sunken ramps on the build's ``ResourceCache``; the run-out mint
    #: (``classify/ramp_runout``) reads THIS.  ``None`` = not derived.
    ramp_feet: _t.Any = None
    #: THE GAP SHEETS (owner RULINGS 2026-10-04o (a); issues #292, #358): the
    #: bodies of a pack's draped pavement page admitted by the PER-TRIANGLE
    #: flatness read (``airport/object_pavement.gap_sheet_footprint``).
    #: NEVER a pavement source — they are not in ``pavements`` — only their
    #: remainder after every pavement the engine already knows is ground.
    gap_sheets: tuple[Pavement, ...] = ()
    #: RULINGS 2026-10-27n THE JUNCTION WITNESS (``airport/junction_witness``):
    #: pavement id -> whether the build's imagery shows it PAVED where it
    #: meets a runway; ``None`` = no imagery (every junction stands, the vote
    #: abstains), an absent id = no contact read (its junction stands)
    paved_joins: _t.Mapping[str, bool] | None = None
