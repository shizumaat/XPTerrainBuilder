"""§16g (10) (12) THE PAD-ADMISSION EVIDENCE — v1's two gates, ported
(issue #101; owner RULINGS 2026-10-02v (3), verbatim: *"We definitely
don't want a flat pad under the whole train at HECA"*).

WHAT v1 REFUSED AND v2 ADMITTED.  v1's object-footprint reader measured
every welded structure of a pack before it could seed a building pad, and
TWO gates refused the classes that are not buildings
(``src/auto_patch/object_footprints.py::structure_ring``,
``src/auto_patch/config.py`` :3734-3790,
``dsf_reader.read_dsf_object_building_evidence``):

* **TALL-BASE FILL** (``DSF_OBJECT_MIN_TALL_BASE_FILL`` 0.002,
  ``DSF_OBJECT_TALL_MEMBER_MIN_EXTENT_M`` 2.5).  A building's TALL member
  covers its OWN footprint.  A 0.3 m ground plate welded to a 28 m
  floodlight mast defeats the height gate (the mast supplies the extent)
  and the hull-fill gate (the plate supplies the base area), and is still
  street furniture on a slab.  Fill = Σ base area of members whose own
  vertical extent reaches the tall floor ÷ the footprint HULL's area: a
  real terminal reads ~1.0, the plate+mast weld ~0.002.  HECA's elevated
  train is the same composition at 31,220 m2 — a deck and its masts over
  a long thin hull.
* **BUILDING EVIDENCE** (R18-2, owner ruling 2026-08-11b;
  ``DSF_OBJECT_BUILDING_EVIDENCE``, ``DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M``
  6.0, ``DSF_OBJECT_EVIDENCE_MIN_COVERAGE`` 0.0).  A footprint ring seeds
  a pad ONLY with evidence a BUILDING is there, never on solid reach
  alone — either (a) an intersecting OSM building / terminal / hangar
  footprint, or (b) a VERTICAL-STRUCTURE test on the object's own solid
  geometry.  It closed four HECA pads 11-18 m below their own ground
  whose footprints were apron slabs, jersey barriers and buses.

THE FLOOR IS DELIBERATELY LOW AND MUST NOT BE RAISED (v1's own
calibration comment, measured HECA 2026-07-27): the plate+mast weld class
and sparse street furniture measure < 0.002 (670 of 813 skip events;
phantom building124 at ~0.0015), while THIN-WALL terminal shells —
material-split wall objects whose 1.5 m footing band projects as thin
strips — measure ~0.002-0.01 and are REAL buildings that need their pads.
Raising it toward 0.05 culled ~140 thin-wall shells (buildings 498 -> 90).

WHY THIS MODULE IS IN ``geom``.  Two layers that may not import each
other need the SAME measurement: ``airport/placement_family.plan_clusters``
MEASURES it (one derivation, carried on ``PlanCluster.evidence`` like
every other cluster scalar) and ``geom/cluster_outline.cluster_outlines``
JUDGES it — where the MINT (``classify/evidence._pads``) and the CENSUS
(``constraints/cluster_pad``) both read it, so the two cannot disagree
about which footprint got a pad.  A second spelling of "is this a
building" is the census-wrapper defect in geometry (CLAUDE.md, RULINGS
2026-08-30l).

No law value is read here — the caller passes the ``[placement]`` keys.
No model type, no I/O: ``geom``'s own rule.
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import os as _os
import typing as _t

from shapely.geometry import MultiPoint

__all__ = ["MemberRow", "PadEvidence", "member_row", "resource_rows",
           "ring_area",
           "tall_base_fill", "tall_member_coverage", "tallest_extent_m",
           "has_vertical_structure_evidence", "evidence_name_vouches",
           "wide_path_name_vouches", "pad_evidence",
           "BUILDING_NAME_TOKENS"]

#: One evidence row per COMPONENT of a cluster's member bodies —
#: ``(resource, total_extent_m, above_grade_extent_m, footprint_area_m2)``.
#: v1's row is per member RESOURCE
#: (``object_footprints.StructureMemberEvidence``); v2's unit of solid
#: geometry is the welded ``model.rebake.Part``, which carries its own
#: ``height_m`` (the authored y extent) and its own footprint ``rings``,
#: so the row is per component and the two gates read exactly the
#: quantities v1 read.
MemberRow = tuple[str, float, float, float]

#: v1 ``object_footprints._BUILDING_NAME_TOKENS``: a resource whose own
#: BASENAME (or stock-library virtual path) NAMES it a building is
#: definitionally one — the owner's CYXY ruling 2026-07-28 (a missing
#: hangar at 60.706235,-135.0696776, whose arched shell projects ~0.001 of
#: its hull, below the 0.002 floor).
BUILDING_NAME_TOKENS = ("hangar", "term_building", "terminal")


@_dc.dataclass(frozen=True)
class PadEvidence:
    """What the two gates measured for ONE cluster, admitted or refused —
    v1's ``evidence_out`` record (``object_footprints.structure_ring``),
    carried on the cluster so the refusal can be LISTED with its ref, its
    gate and its measured value (owner RULINGS 2026-10-02v (3)).

    ``length_m`` / ``width_m`` are the footprint hull's minimum rotated
    rectangle: the refusal record carries them for issue #229 (2026-10-02v
    (3b), a refused pack object that REPRESENTS A ROAD grades as a road),
    which is NOT implemented here — this module only leaves the numbers
    #229 will read."""

    #: Σ footprint area of components whose OWN vertical extent reaches
    #: ``tall_member_min_extent_m``, ÷ the hull's area.  v1 sums the
    #: component areas rather than unioning them, and the double count
    #: over an overlap can only ever KEEP a real building.
    tall_base_fill: float
    #: the tallest component's own ABOVE-GRADE extent (v1's A11 clamp: a
    #: 3.9 m drainage pit and a 3.9 m wall are not the same evidence)
    tallest_extent_m: float
    #: fraction of the hull covered by components reaching
    #: ``evidence_min_height_m`` — the evidence gate's coverage term
    evidence_coverage: float
    #: the footprint HULL (v1's ``MultiPoint(base_points).convex_hull``)
    hull_area_m2: float
    #: the WIDE path vouch — the tall-base gate's, v1
    #: ``_wide_path_name_vouches`` (shipped; ``DSF_OBJECT_NAME_VOUCH_SCOPED``
    #: is parked OFF in v1 and the substitution stays parked here)
    name_vouched: bool
    #: the SCOPED vouch — the evidence gate's, v1 ``evidence_name_vouches``
    evidence_name_vouched: bool
    #: the hull's minimum rotated rectangle, long side first (issue #229)
    length_m: float
    width_m: float
    #: how many components the rows were measured over
    components: int
    #: the rows themselves (:data:`MemberRow` per component).  They travel
    #: with the measurement so the GATE can re-run v1's real test at the
    #: law's own thresholds (``geom/cluster_outline._vertical_evidence``)
    #: instead of carrying a verdict taken at thresholds the law may no
    #: longer read — a cached cluster must never carry a stale verdict.
    #: They are small beside the footprint rings the cluster already
    #: carries (four floats per component).
    rows: tuple[MemberRow, ...] = ()

    def line(self) -> str:
        return (f"tall_base_fill {self.tall_base_fill:.4f}, tallest "
                f"{self.tallest_extent_m:.2f} m, hull "
                f"{self.hull_area_m2:,.0f} m2 ({self.length_m:.0f} x "
                f"{self.width_m:.0f} m), {self.components} component(s)"
                + (", name-vouched" if self.name_vouched else ""))


def ring_area(ring: _t.Sequence[_t.Sequence[float]],
              ml: float, mo: float) -> float:
    """A ``(lat, lon)`` ring's plan area in m2 — the shoelace
    ``placement_family.draws_outline`` already takes, at the same
    ``ml``/``mo`` (metres per degree of latitude / longitude)."""
    if len(ring) < 3:
        return 0.0
    xs = [float(lo) * mo for _la, lo in ring]
    ys = [float(la) * ml for la, _lo in ring]
    n = len(xs)
    return 0.5 * abs(sum(xs[i] * ys[(i + 1) % n] - xs[(i + 1) % n] * ys[i]
                         for i in range(n)))


def member_row(part: _t.Any, resource: str, ml: float, mo: float) -> MemberRow:
    """One :data:`MemberRow` for a ``model.rebake.Part``.

    ``total_extent_m`` is ``Part.height_m`` — the component's own authored
    y extent, which is exactly v1's ``_res_max_y - _res_min_y`` and what
    its TALL-BASE accumulator tests.  ``above_grade_extent_m`` CLAMPS BOTH
    ENDS AT GRADE (v1's A11 amendment, owner defect 2026-07-30, OTHH
    ``Buildings/Dewatering Drainage/*``): the drainage basins there are
    open pits authored −3.82 .. +0.06, every millimetre below grade, and
    the raw extent read a 3.87 m HOLE as a 3.87 m building.  Authored
    ``y = 0`` is the object's own grade in both engines, so the clamp
    ports unchanged and leaves every at-or-above-grade component's extent
    as it was."""
    base = float(getattr(part, "base_y", 0.0) or 0.0)
    extent = float(getattr(part, "height_m", 0.0) or 0.0)
    above = max(base + extent, 0.0) - max(base, 0.0)
    area = sum(ring_area(r, ml, mo)
               for r in (getattr(part, "rings", ()) or ()))
    return (str(resource), extent, above, area)


def resource_rows(rows: _t.Sequence[MemberRow],
                  span: "tuple[float, float] | None") -> list[MemberRow]:
    """``rows`` with the ABOVE-GRADE extent read per member RESOURCE over
    its welded structure, which is what v1's evidence row IS
    (``object_footprints.structure_ring``: ``max(_res_max_y, 0) -
    max(_res_min_y, 0)`` over every triangle the resource contributes to
    the structure) — lane ``padgates101b``, issue #101.

    ``span`` is the resource's authored ``(lowest base y, highest top y)``
    over the welded chain.  v2's unit of solid geometry is the welded
    COMPONENT, and a material-split pack stacks many components of one
    resource into one wall: MEASURED HECA (sweep sw1008b), cluster
    ``unit:43#807`` — 10,006 m2 of ``Hangar_Tower/T3_32.obj``, 210
    components, the tallest 5.15 m — was refused under the 6.0 m evidence
    height although v1's own cache vouches the same ground (role
    ``object``, 9,423 m2 of overlap).  The per-component reading can only
    ever UNDER-read v1's, so the fold can only ever KEEP a building.

    The TOTAL extent (the tall-base accumulator's term) stays the
    component's own: there the per-component reading is the
    discriminator — a deck-on-piers weld's tall members are its piers,
    not its deck (PR #242 deviation 3)."""
    if span is None:
        return list(rows)
    above = max(float(span[1]), 0.0) - max(float(span[0]), 0.0)
    return [(r[0], r[1], max(r[2], above), r[3]) for r in rows]


def tall_member_coverage(rows: _t.Sequence[MemberRow], hull_area_m2: float,
                         minimum_extent_m: float,
                         above_grade: bool = True) -> float:
    """Fraction of the footprint hull covered by the components whose own
    vertical extent reaches ``minimum_extent_m``.

    THE one definition — v1's ``object_footprints.tall_member_coverage``,
    which both of its gates, its twins and
    ``tools/object_pad_evidence_report.py`` call for the same reason.
    ``above_grade`` picks which extent the row is read at: the EVIDENCE
    gate asks for the above-grade one (v1's R18-2 rows), the TALL-BASE
    accumulator for the total (v1's ``_res_extent``).  The area sum may
    double-count an overlap, which can only ever KEEP a structure.
    Returns 0.0 for a degenerate hull."""
    if hull_area_m2 <= 0.0:
        return 0.0
    k = 2 if above_grade else 1
    covered = sum(row[3] for row in rows
                  if minimum_extent_m <= 0.0 or row[k] >= minimum_extent_m)
    return covered / hull_area_m2


def tall_base_fill(rows: _t.Sequence[MemberRow], hull_area_m2: float,
                   tall_member_min_extent_m: float) -> float:
    """v1's TALL-BASE FILL: Σ footprint area of components whose own TOTAL
    vertical extent reaches ``tall_member_min_extent_m`` ÷ the hull's
    area.  ``tall_member_min_extent_m <= 0`` reads every component as
    tall, which is v1's own degradation and why that floor is its OWN
    constant: ``chain_min_height_m`` is a separately owned gate (tests and
    users legitimately zero it) and the tall-base discriminator must not
    silently become "everything is tall" when they do."""
    return tall_member_coverage(rows, hull_area_m2, tall_member_min_extent_m,
                                above_grade=False)


def tallest_extent_m(rows: _t.Sequence[MemberRow]) -> float:
    """The tallest ABOVE-GRADE extent among a cluster's components — the
    vertical evidence test's primary reading (v1
    ``object_footprints.tallest_member_extent``)."""
    return max((row[2] for row in rows), default=0.0)


def has_vertical_structure_evidence(
        rows: _t.Sequence[MemberRow], hull_area_m2: float,
        evidence_min_height_m: float, evidence_min_coverage: float,
        name_vouched: bool = False) -> tuple[bool, float]:
    """``(verdict, coverage)`` for the VERTICAL half of R18-2 — v1
    ``object_footprints.has_vertical_structure_evidence``, value for
    value.

    THE TEST: some component of the cluster stands at least
    ``evidence_min_height_m`` above grade on its own, and the tall
    components cover at least ``evidence_min_coverage`` of the hull.  The
    coverage term is ARMED AT 0 BY MEASUREMENT and the measurement is the
    point (HECA 2026-08-11): a material-split pack authors a terminal
    shell as thin per-material wall strips whose tall members cover
    0.000-0.02 of the fused hull — the SAME range as the phantom slab
    class — so no coverage floor separates them.  HEIGHT does, cleanly,
    and the coverage-shaped defence is already carried upstream, as a
    REFUSAL, by the tall-base fill."""
    coverage = tall_member_coverage(rows, hull_area_m2, evidence_min_height_m)
    if name_vouched:
        return True, coverage
    if (evidence_min_height_m > 0.0
            and tallest_extent_m(rows) < evidence_min_height_m):
        return False, coverage
    return coverage >= evidence_min_coverage, coverage


def evidence_name_vouches(resource_paths: _t.Iterable[str]) -> bool:
    """The SCOPED vouch (v1 ``object_footprints.evidence_name_vouches``):
    the token must be in the resource's own BASENAME, or the path must be
    a stock-library virtual path.

    The owner's CYXY subject is a LIBRARY resource whose virtual path
    (``lib/airport/…/hangars/…``) is a semantic statement by the library
    author.  A payware pack's directory layout is not: HECA's Tai Models
    pack files its whole airport — jet-blast fences, apron slabs,
    barriers — under ``Airport/Hangar_Tower/`` and ``Airport/Hangar/``,
    and a path-anywhere match vouched 667 of its 817 rings, the phantom
    pads included (measured 2026-08-11)."""
    for resource_path in resource_paths:
        lowered = str(resource_path).lower().replace("\\", "/")
        basename = _os.path.basename(lowered)
        if any(token in basename for token in BUILDING_NAME_TOKENS):
            return True
        if (lowered.startswith("lib/") or "/lib/" in lowered) and any(
                token in lowered for token in BUILDING_NAME_TOKENS):
            return True
    return False


def wide_path_name_vouches(resource_paths: _t.Iterable[str]) -> bool:
    """The WIDE vouch — a token ANYWHERE in the resource path (v1
    ``object_footprints._wide_path_name_vouches``).

    This is the predicate v1's two HULL FLOORS actually ship with, because
    ``DSF_OBJECT_NAME_VOUCH_SCOPED`` is PARKED OFF there: the scoped
    substitution was measured right on population (HECA 817 -> 210 rings,
    215 -> 73 building pads) and made the HECA build refuse the band
    inversion law, whose remedy was measured outside that file.  Porting
    the SHIPPED predicate is porting the gate the owner read; when v1's
    park is lifted this function goes with it and
    :func:`evidence_name_vouches` is the only implementation."""
    for resource_path in resource_paths:
        lowered = str(resource_path).lower()
        if ("hangar" in lowered or "term_building" in lowered
                or "/terminal" in lowered):
            return True
    return False


def _hull(points: _t.Sequence[tuple[float, float]]):
    try:
        hull = MultiPoint(list(points)).convex_hull
    except Exception:
        return None
    return None if hull.is_empty or hull.geom_type != "Polygon" else hull


def pad_evidence(rows: _t.Sequence[MemberRow],
                 hull_points: _t.Sequence[tuple[float, float]],
                 ml: float, mo: float,
                 tall_member_min_extent_m: float,
                 evidence_min_height_m: float,
                 evidence_min_coverage: float) -> "PadEvidence | None":
    """Measure one cluster — ``None`` where there is no footprint to
    measure (v1's ``degenerate`` / ``hull_failed`` verdicts), which the
    gate reads as "not measured" and never as a refusal.

    ``hull_points`` are ``(lat, lon)`` vertices of EVERY component of the
    cluster, posts and flat lines included: v1's hull is over every base
    vertex of the structure, and the discriminator is precisely that the
    MAST is in the hull while its base is not in the numerator.  The hull
    is v1's convex hull, not the pad outline's union — a plate+mast weld's
    union is solid and only the hull exposes the weld."""
    if len(hull_points) < 3:
        return None
    hull = _hull([(float(lo) * mo, float(la) * ml) for la, lo in hull_points])
    if hull is None:
        return None
    hull_area_m2 = float(hull.area)
    if hull_area_m2 <= 0.0:
        return None
    try:
        box = hull.minimum_rotated_rectangle
        xy = list(box.exterior.coords)[:-1] if box.geom_type == "Polygon" else []
        sides = sorted(_math.dist(xy[i], xy[(i + 1) % len(xy)])
                       for i in range(len(xy))) if len(xy) >= 4 else []
        length_m = float(sides[-1]) if sides else 0.0
        width_m = float(sides[0]) if sides else 0.0
    except Exception:                                   # a degenerate hull
        length_m = width_m = 0.0
    paths = {row[0] for row in rows}
    _vertical, coverage = has_vertical_structure_evidence(
        rows, hull_area_m2, evidence_min_height_m, evidence_min_coverage,
        evidence_name_vouches(paths))
    return PadEvidence(
        tall_base_fill=tall_base_fill(rows, hull_area_m2,
                                      tall_member_min_extent_m),
        tallest_extent_m=tallest_extent_m(rows),
        evidence_coverage=coverage,
        hull_area_m2=hull_area_m2,
        name_vouched=wide_path_name_vouches(paths),
        evidence_name_vouched=evidence_name_vouches(paths),
        length_m=length_m, width_m=width_m, components=len(rows),
        rows=tuple(rows))
