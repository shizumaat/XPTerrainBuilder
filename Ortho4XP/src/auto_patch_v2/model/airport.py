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
    "OsmWay", "Building", "DemSample", "DsfObject", "SceneryPack",
    "FlatVerdict", "Airport",
]


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


@_dc.dataclass(frozen=True)
class Runway:
    """apt.dat row 100."""

    id: str
    width_m: float
    surface: Surface
    ends: tuple[RunwayEnd, RunwayEnd]
    code_number: int | None
    code_letter: str | None

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
    #: beside the groups — the design surface gives each ONE pad and
    #: flattens the apron within ``[design] cluster_apron_reach_m`` of it.
    #: ``constraints`` may not import ``planar``, so the relation travels
    #: here.  Same ``None`` / empty rule as ``groups``.
    clusters: _t.Any = None
