#!/usr/bin/env python3
"""TUNNEL PORTAL ACCEPTANCE — the emitted-patch assertions a tunnel round
is accepted on, as one instrument.

Promoted 2026-08-07 from the lane scratchpad ``accept_othh.py`` on its
second use (RULINGS ``7e90032``: "The second use of a lane scratchpad
script is the signal to promote it into ``tools/`` with an index entry
and a twin").  Two rounds asked the same questions of an OTHH patch —
tunnel-portal-fidelity §4.3 and tunnel-ramp-cut-boundaries §6.3 — and the
second round had to re-derive one of them under a DIFFERENT identity
predicate than the first, which is exactly the two-instruments trap
(memory ``two-instruments-one-assumed-population``: the parent's 148 and
this reader's 164 were never the same population).  One instrument, one
population, stated thresholds.

WHAT IT IS NOT: a defect counter.  Every ROW COUNT here comes from
``tools/harness/census.py``'s ``census_one`` — which is itself
``check_grade.run_checks_law_true`` — and every geometry read goes
through ``check_grade._parse_osm``.  There is no private parse of the
patch and no private re-count of a law family; a census wrapper is the
defect this repo has already paid for twice.

USAGE

    venv/bin/python tools/tunnel_portal_acceptance.py PATCH.osm \
        [--control CONTROL.osm] [--profile OTHH] [--json OUT.json]

    # thresholds are arguments, never literals in the checks
    ... --mouth-max-m 15 --site-max-m 60 --needle-spread-m 8 \
        --drift-max 10 --retreat-wall-max 5 --over-cap-ramp-max 2 \
        --adjudicated-delta-max -24 --actionable-sites-max 82 \
        --claim-wall-cover-min 0.8

    # an airport with no shipped profile supplies its own sites
    ... --site "A=25.271935,51.6022729" --site "B1=25.2758817,51.6139664"

Every check reports MEASURED / THRESHOLD / verdict, and a check whose
inputs are absent reports SKIPPED — never PASS.  Exit code 1 if any check
FAILED, 0 otherwise (SKIPPED does not fail the run; it is reported).

LIBRARY ENTRY: :func:`run_acceptance` returns the same ``list[Check]``
the CLI prints — the CLI is a formatter over it, and
``tests/test_tunnel_portal_acceptance.py`` twin-asserts that.
"""
from __future__ import annotations

import argparse
import bz2
import importlib.util
import json
import math
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIPPED"


# ──────────────────────────────────────────────────────────────────
# The ONE law/census code path (never a private copy)
# ──────────────────────────────────────────────────────────────────
def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_census():
    """``tools/harness/census.py`` from THIS tree — the only sanctioned
    producer of defect counts.  It brings ``check_grade`` with it
    (``census.load_check_grade``), so there is exactly one law reader in
    the process."""
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    return _load("tpa_census", ROOT / "tools" / "harness" / "census.py")


# ──────────────────────────────────────────────────────────────────
# Profiles — a named site set, never a literal inside a check
# ──────────────────────────────────────────────────────────────────
@dataclass
class Profile:
    """One airport's acceptance inputs.  Everything a check needs that is
    not a threshold: WHERE to look."""
    name: str
    #: display name → (lat, lon).  The FIRST entry is the tunnel MOUTH
    #: (the ``--mouth-max-m`` check); every entry takes ``--site-max-m``.
    sites: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    #: OSM road-cache path RELATIVE to the OSM_data dir, and the way ids
    #: of the mapped bore(s) inside it.
    bore_osm_relpath: Optional[str] = None
    bore_way_ids: Tuple[str, ...] = ()
    #: arc-length window of the bore that is COVERED (roofed): no
    #: emitted vertex may sit below grade over it.
    covered_span_m: Tuple[float, float] = (0.0, 0.0)
    #: half-widths (m) the covered-span corridor is tested at.
    covered_half_widths_m: Tuple[float, ...] = (15.0, 25.0)
    #: a CONTROL way id whose footprint the "needle" check searches.
    needle_control_way: Optional[str] = None
    #: ``ref`` of a building pad that must be FLAT.
    flat_pad_ref: Optional[str] = None
    #: roles whose sub-grade node counts must not exceed the control's.
    subgrade_roles: Tuple[str, ...] = (
        "building", "service_junction", "service_road", "junction", "apron")


#: Shipped profiles.  A profile is DATA — adding one must never require
#: editing a check.
SITE_PROFILES: Dict[str, Profile] = {
    "OTHH": Profile(
        name="OTHH",
        sites={
            "D (mapped mouth)": (25.2789456, 51.5994543),
            "A": (25.271935, 51.6022729),
            "B1": (25.2758817, 51.6139664),
            "B2": (25.2558032, 51.6079424),
            "B3": (25.2540818, 51.6036435),
        },
        bore_osm_relpath="+20+050/+25+051/+25+051_big_roads.osm.bz2",
        bore_way_ids=("-917", "-918"),
        covered_span_m=(70.0, 740.0),
        needle_control_way="-11724",
        flat_pad_ref="building1",
    ),
    # §T8.2 — THE LEMD PROFILE.  The four sites are RULINGS 2026-08-28
    # items 4-7 (the owner's in-sim reads at 1.0.263), in the ruling's
    # own order: item 4 first, so it is the ``--mouth-max-m`` mouth.
    # The bores are the mapped ways the road feed carries; LEMD has no
    # ``*_big_roads`` tunnel extract at all, which is why this profile
    # names the ROAD-FEED CACHE (see ``_bore_lines``).  NO COVERED SPAN
    # is declared: these bores are 224-2 615 m ways and one (lo,hi)
    # window cannot describe the roofed stretch of all five, so
    # ``covered_span_clean`` reports SKIPPED here rather than PASSing
    # over a span nobody named.  Declare one per run with
    # ``--covered-span``.
    "LEMD": Profile(
        name="LEMD",
        sites={
            "item 4 (entrance, way -2070)": (40.4980435, -3.5849427),
            "item 5 (mouth, no ramp)": (40.4960151, -3.5849926),
            "item 6 (mouth, ways -1872/-257)": (40.4944689, -3.5546245),
            "item 7 (mouth, way -2119)": (40.4901623, -3.5593036),
        },
        bore_osm_relpath="_airport_road_feed/LEMD_road_feed.cache",
        bore_way_ids=("-2070", "-1872", "-257", "-2085", "-2119"),
    ),
}


@dataclass
class Thresholds:
    mouth_max_m: float = 15.0
    site_max_m: float = 60.0
    needle_spread_m: float = 8.0
    drift_max: Optional[int] = None
    drift_floor_m: float = 0.5
    retreat_wall_max: Optional[int] = None
    retreat_wall_radius_m: float = 2.0
    over_cap_ramp_max: Optional[int] = None
    adjudicated_delta_max: Optional[float] = None
    actionable_sites_max: Optional[int] = None
    pad_flat_tol_m: float = 0.005
    #: THE CANONICAL MOUTH (RULINGS 2026-08-30).  How close a ramp must
    #: come to a mouth plate to be "reaching the mouth line", and how far
    #: around a mouth its own wall band / end cap is looked for.
    mouth_reach_m: float = 1.0
    mouth_radius_m: float = 25.0
    #: Two tunnel road surfaces sharing at least this much ground are a
    #: DUPLICATE corridor — the class R14-1's claim minted beside the
    #: synthetic ramp.  The claim's own "cover, do not graze" floor.
    dup_overlap_m2: float = 2.0
    #: A wall/foot piece smaller than this is a FRAGMENT, not a wall.
    wall_fragment_m2: float = 1.0
    #: arm the canonical bar (0 non-canonical mouths); otherwise REPORT
    mouth_canonical: bool = False
    #: A bore surface answers a mouth only where it is BELOW GRADE by
    #: this much — it must carry a bore, not merely be a tunnel piece.
    claimed_bore_max_m: float = 0.0
    #: §T8.1 covered-span datum.  How far outside the corridor the LOCAL
    #: grade is sampled, how many samples the median needs before it is
    #: a datum at all, and how far under it a vertex must sit to count as
    #: below grade (emit quantisation is 0.1 m; 0.50 m is well clear).
    datum_ring_m: float = 25.0
    datum_min_samples: int = 8
    below_grade_m: float = 0.50
    #: §T6.1 bar: minimum MEDIAN face coverage of the below-grade claimed
    #: corridors.  ``None`` makes the check a REPORT, which is how the
    #: attribution arms read it.
    claim_wall_cover_min: Optional[float] = None
    #: §T5: the emitter's wall gap, the width of the annulus the FOOT
    #: must own (``config.TUNNEL_WALL_GAP_M``'s value, stated once here
    #: rather than re-derived inside a check).
    wall_gap_m: float = 0.6
    #: §T4.2: how near a road neighbour must be for an isolated rect to
    #: read as a LOST FILL rather than a lawful lone rect.
    isolated_neighbour_m: float = 10.0
    #: …and the bar on that count.  ``None`` makes it a REPORT.
    isolated_rects_max: Optional[int] = None
    #: §T4.2's population is CORRIDOR-WIDTH pieces (the synthesised
    #: 6.00 m rects), not any road surface that touches nothing.
    corridor_width_max_m: float = 8.0
    #: §F1 (LEMD ramp/road fidelity spec law 1): two ``tunnel_wall``
    #: vertices closer than this in PLAN are ACROSS THE BAND, not along
    #: its run — a band is ~1 m wide and its stations stand tens of
    #: metres apart, so this separates the two frames without needing
    #: the walled body the patch does not carry.
    wall_band_span_m: float = 2.0
    #: …and the bar on the worst such delta.  ``None`` makes the check a
    #: REPORT, which is how the attribution arms read it and how every
    #: pre-§F1 profile keeps reading.
    wall_top_delta_max: Optional[float] = None


@dataclass
class Check:
    name: str
    verdict: str
    measured: Any
    threshold: Any = None
    detail: str = ""

    def line(self) -> str:
        mark = {PASS: "PASS ", FAIL: "FAIL ", SKIP: "SKIP "}[self.verdict]
        thr = "" if self.threshold is None else f"  (bar {self.threshold})"
        return (f"  [{mark}] {self.name:<28} measured={self.measured}{thr}"
                + (f"\n           {self.detail}" if self.detail else ""))


# ──────────────────────────────────────────────────────────────────
# Patch reading — through the law library's parser only
# ──────────────────────────────────────────────────────────────────
class Patch:
    """A parsed patch in the law library's own frame."""

    def __init__(self, path: Path, cg):
        self.path = Path(path)
        self.features: Dict[str, list] = {}
        self.nodes, self.ways = cg._parse_osm(self.path,
                                              feature_out=self.features)
        ctx = cg.law_context_from_sidecar(self.path, announce=False)
        self.anchor = ctx.get("anchor")
        self.ll_to_m = cg._ll_to_m_factory(self.nodes, anchor=self.anchor)
        self.by_wid = {w.wid: w for w in self.ways}
        self.owners: Dict[str, set] = defaultdict(set)
        for w in self.ways:
            for n in w.nids:
                self.owners[n].add(w.wid)

    # -- geometry helpers ------------------------------------------
    def pts(self, w) -> list:
        return [self.ll_to_m(*self.nodes[n]) for n in w.nids
                if n in self.nodes]

    def role_ways(self, role: str) -> list:
        return [w for w in self.ways if w.role == role]

    def ref_ways(self, ref: str) -> list:
        return [w for w in self.ways if w.ref == ref]

    def spell(self, nid: str) -> Tuple[str, str]:
        """The canonical 11-decimal identity of a node (memory
        ``canonical-identity-join``; a proximity join is not identity)."""
        la, lo = self.nodes[nid]
        return (f"{la:.11f}", f"{lo:.11f}")

    def coordset(self, w) -> frozenset:
        return frozenset(self.spell(n) for n in w.nids if n in self.nodes)

    def altvec(self, w) -> Dict[Tuple[str, str], Optional[float]]:
        return {self.spell(n): e for n, e in zip(w.nids, w.elevs)
                if n in self.nodes}


def _bore_lines(profile: Profile, osm_data_dir: Optional[Path], to_m):
    """``{way id: LineString}`` for the profile's mapped bores, or None
    when the road cache is not reachable (the check then SKIPS).

    TWO SOURCES, one reader (§T8.2).  ``bore_osm_relpath`` may name an
    OSM XML extract (``*.osm`` / ``*.osm.bz2`` — a ``big_roads`` file)
    OR an ``_airport_road_feed/*.cache`` road-feed pickle, which is
    where an airport whose bores were never in a ``big_roads`` extract
    actually has them.  Which source an airport uses is PROFILE DATA,
    never a branch in a check.  A path that is already absolute is used
    as given, so ``--bore-osm`` can point anywhere.
    """
    if not profile.bore_osm_relpath:
        return None
    rel = Path(profile.bore_osm_relpath)
    if rel.is_absolute():
        path = rel
    elif osm_data_dir is None:
        return None
    else:
        path = Path(osm_data_dir) / rel
    if not path.exists():
        return None
    from shapely.geometry import LineString
    out = {}
    if path.suffix == ".cache":
        # The road feed is a pickle of ``auto_patch.osm_load
        # .AirportRoadNetwork``; ``load_census`` has already put ``src``
        # on ``sys.path`` (the ONE law/census code path), so unpickling
        # resolves without a second import policy here.
        import pickle
        with open(path, "rb") as fh:
            record = pickle.load(fh)
        network = record.get("network") if isinstance(record, dict) \
            else record
        nodes = getattr(network, "nodes", None) or {}
        for way in (getattr(network, "ways", None) or ()):
            wid, refs = str(way[0]), way[1]
            if wid not in profile.bore_way_ids:
                continue
            pts = [to_m(*nodes[n]) for n in refs if n in nodes]
            if len(pts) >= 2:
                out[wid] = LineString(pts)
        return out or None
    opener = bz2.open if path.suffix == ".bz2" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        root = ET.parse(fh).getroot()
    nn = {n.get("id"): to_m(float(n.get("lat")), float(n.get("lon")))
          for n in root.findall("node")}
    for w in root.findall("way"):
        wid = w.get("id")
        if wid not in profile.bore_way_ids:
            continue
        pts = [nn[nd.get("ref")] for nd in w.findall("nd")
               if nd.get("ref") in nn]
        if len(pts) >= 2:
            out[wid] = LineString(pts)
    return out or None


# ──────────────────────────────────────────────────────────────────
# The checks
# ──────────────────────────────────────────────────────────────────
#: The refs that ARE a bore's face — the perimeter band (rising face and
#: its §T5 foot), the roof and the cap.  A claimed corridor is bore
#: geometry only if one of these stands along it.
FACE_REFS = ("tunnel_wall", "tunnel_wall_foot", "tunnel_roof",
             "tunnel_cap")
#: How near a face must stand to a corridor edge to answer for it — the
#: emitter's own graze clearance plus the wall gap the §T5 foot occupies.
FACE_REACH_M = 2.5


def _face_union(patch: Patch):
    """The union of every face piece in the patch, or ``None``."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = []
    for ref in FACE_REFS:
        for w in patch.ref_ways(ref):
            pts = patch.pts(w)
            if len(pts) >= 3:
                try:
                    p = Polygon(pts)
                    if not p.is_valid:
                        p = p.buffer(0)
                    if not p.is_empty:
                        polys.append(p)
                except Exception:                        # pragma: no cover
                    continue
    if not polys:
        return None
    try:
        return unary_union(polys)
    except Exception:                                    # pragma: no cover
        return None


def bore_face_coverage(patch: Patch, way, faces) -> float:
    """Fraction of ``way``'s perimeter that a face piece answers for.

    §T6/§2.3's acceptance number, RE-KEYED to ramp/mouth geometry
    (redesign spec §5.4, census #40) now that the ``tunnel_road`` claim
    class is retired.  One definition, used by both the ``site_reach``
    admission and the coverage table, so the two can never be different
    populations (memory ``two-instruments-one-assumed-population``).
    """
    from shapely.geometry import Polygon
    pts = patch.pts(way)
    if len(pts) < 3 or faces is None:
        return 0.0
    try:
        ring = Polygon(pts).exterior
        total = ring.length
        if total <= 0.0:
            return 0.0
        open_len = ring.difference(faces.buffer(FACE_REACH_M)).length
        return max(0.0, min(1.0, 1.0 - open_len / total))
    except Exception:                                    # pragma: no cover
        return 0.0


def _check_site_reach(patch: Patch, profile: Profile, thr: Thresholds
                      ) -> List[Check]:
    """BORE GEOMETRY within reach of every named site, and a vertex of it
    within ``mouth_max_m`` of the mouth (the first site).

    "Bore geometry" is the portal walk's OWN emitted road surface — a
    ``tunnel_ramp`` shape or a ``tunnel_mouth`` piece (both carry
    ``ROLE_TUNNEL_RAMP``).  RE-KEYED (redesign spec §5.4, census #40):
    the check used to admit a BELOW-GRADE CLAIMED CORRIDOR
    (``ref=tunnel_road``) as well, because R14-1's law was "the paved
    area IS the corridor".  That claim class is retired (RULINGS
    2026-08-31b) and mapped road pavement is never re-profiled in place,
    so the only object that can answer a mouth is the ramp reaching it —
    which is the canonical-mouth law (RULINGS 2026-08-30) stated as a
    measurement.  Re-keyed IN THE SAME BATCH as the retirement so this
    battery cannot silently go SKIP against a patch with no claims left.
    """
    from shapely.geometry import LineString, Point
    if not profile.sites:
        return [Check("site_reach", SKIP, None, None,
                      "no sites: pass --profile or --site NAME=LAT,LON")]
    geoms = []
    for w in patch.role_ways("tunnel_ramp"):
        pts = patch.pts(w)
        if len(pts) >= 2:
            geoms.append((w.wid, LineString(pts)))
    n_ramp = len(geoms)
    faces = _face_union(patch)
    n_faceless = 0
    for w in patch.ref_ways("tunnel_mouth"):
        if any(w.wid == _wid for _wid, _g in geoms):
            continue
        pts = patch.pts(w)
        if len(pts) < 2:
            continue
        # §T6.3, unchanged in kind: A FACELESS BELOW-GRADE SURFACE IS
        # NOT BORE GEOMETRY.  A surface may be dug and still be a hole in
        # the ground with no wall — the owner's ground read of exactly
        # that ring (RULINGS 2026-08-28c item 3: "no ramp, no walls").
        if bore_face_coverage(patch, w, faces) <= 0.0:
            n_faceless += 1
            continue
        geoms.append((w.wid, LineString(pts)))
    n_mouth = len(geoms) - n_ramp
    if not geoms:
        return [Check("site_reach", FAIL, 0, len(profile.sites),
                      "the patch emitted no tunnel_ramp geometry at all"
                      + (f" ({n_faceless} tunnel_mouth piece(s) "
                         f"REJECTED: no face)"
                         if n_faceless else ""))]
    checks: List[Check] = []
    worst_name, worst_d = None, -1.0
    for name, (lat, lon) in profile.sites.items():
        p = Point(patch.ll_to_m(lat, lon))
        d, wid = min((g.distance(p), w) for w, g in geoms)
        if d > worst_d:
            worst_name, worst_d = name, d
    checks.append(Check(
        "site_reach", PASS if worst_d <= thr.site_max_m else FAIL,
        round(worst_d, 1), thr.site_max_m,
        f"worst site {worst_name!r} at {worst_d:.1f} m over "
        f"{len(profile.sites)} site(s) — bore geometry: {n_ramp} "
        f"tunnel_ramp + {n_mouth} tunnel_mouth piece(s) with a "
        f"face ({n_faceless} faceless one(s) rejected)"))
    mouth = next(iter(profile.sites.items()))
    mp = Point(patch.ll_to_m(*mouth[1]))
    vd = min((mp.distance(Point(v)) for _wid, g in geoms
              for v in g.coords), default=float("inf"))
    checks.append(Check(
        "mouth_vertex_reach", PASS if vd <= thr.mouth_max_m else FAIL,
        round(vd, 1), thr.mouth_max_m,
        f"nearest BORE VERTEX to {mouth[0]!r} (ramp or mouth)"))
    return checks


def _check_covered_span(patch: Patch, profile: Profile, bores,
                        thr: Optional["Thresholds"] = None) -> List[Check]:
    """No emitted vertex below grade over the bore's COVERED span — a
    roofed stretch has no open trench.

    §T8.1 — THE DATUM IS LOCAL, NEVER ABSOLUTE 0.0.  The predicate was
    ``e < 0.0``: true only of a field near sea level, and STRUCTURALLY
    VACUOUS on a field 561-617 m up — no emitted vertex there is ever
    below zero, so the check reported PASS over a span it had not
    examined.  The datum is now measured from the patch itself:
    the median elevation of the emitted vertices in the ANNULUS just
    outside the corridor (the surrounding grade at this bore, in the
    build's own frame), and a vertex is below grade when it sits
    ``below_grade_m`` under that.  A corridor with no annulus evidence
    reports SKIPPED — never PASS.
    """
    from shapely.geometry import Point
    from shapely.ops import substring, unary_union
    thr = thr or Thresholds()
    if not bores:
        return [Check("covered_span_clean", SKIP, None, 0,
                      "mapped-bore road cache not reachable "
                      "(--osm-data-dir / --bore-osm)")]
    lo, hi = profile.covered_span_m
    if hi <= lo:
        # NOT DECLARED.  ``substring(g, 0, 0)`` is a POINT: buffering it
        # gave a disc that contained nothing and the check reported a
        # clean PASS over a span the profile never named.
        return [Check("covered_span_clean", SKIP, None, 0,
                      "no covered span declared (--covered-span LO,HI "
                      "or a profile that names one)")]
    # Every emitted vertex once, in layout metres, with its altitude.
    pts: List[Tuple[Any, float]] = []
    for w in patch.ways:
        for n, e in zip(w.nids, w.elevs):
            if e is not None and n in patch.nodes:
                pts.append((Point(patch.ll_to_m(*patch.nodes[n])),
                            float(e)))
    worst = 0
    detail = []
    datums = []
    for half in profile.covered_half_widths_m:
        axis = unary_union([substring(g, lo, hi) for g in bores.values()])
        corridor = axis.buffer(half)
        annulus = axis.buffer(half + thr.datum_ring_m).difference(corridor)
        ring = sorted(e for p, e in pts if annulus.contains(p))
        if len(ring) < thr.datum_min_samples:
            detail.append(f"half-width {half:.0f} m: no datum "
                          f"({len(ring)} annulus vertex/vertices)")
            continue
        datum = ring[len(ring) // 2]
        datums.append(round(datum, 2))
        bad = sum(1 for p, e in pts
                  if e < datum - thr.below_grade_m and corridor.contains(p))
        worst = max(worst, bad)
        detail.append(f"half-width {half:.0f} m: {bad} "
                      f"(datum {datum:.2f} m)")
    if not datums:
        return [Check("covered_span_clean", SKIP, None, 0,
                      f"no LOCAL DATUM measurable beside the corridor "
                      f"(needs ≥{thr.datum_min_samples} emitted vertices "
                      f"in the {thr.datum_ring_m:.0f} m annulus) — "
                      + ", ".join(detail))]
    return [Check("covered_span_clean", PASS if worst == 0 else FAIL,
                  worst, 0,
                  f"vertices ≥{thr.below_grade_m:.2f} m below the LOCAL "
                  f"grade datum over s∈[{lo:.0f},{hi:.0f}] — "
                  + ", ".join(detail))]


def _check_bore_corridor_walls(patch: Patch, thr: Thresholds
                               ) -> List[Check]:
    """A BELOW-GRADE BORE SURFACE WALLS ITSELF, both sides.

    RE-KEYED (redesign spec §5.4, census #40).  The check measured the
    MEDIAN face coverage of R14-1's below-grade CLAIMED corridors against
    the synthetic path's own measured class (82 %); with the claim class
    retired (RULINGS 2026-08-31b) that population is empty and the check
    would report SKIP forever — the silent-skip failure the redesign's
    §5.4 exists to prevent.  The population is now the portal walk's own
    below-grade surfaces (``tunnel_ramp`` + ``tunnel_mouth``), which is
    the canonical-mouth law's own subject: no ramp, no walls.
    """
    faces = _face_union(patch)
    bore = [w for w in patch.role_ways("tunnel_ramp")
            if any(e is not None and e < thr.claimed_bore_max_m
                   for e in (w.elevs or ()))]
    ramps = patch.role_ways("tunnel_ramp")
    if not bore:
        return [Check("bore_corridor_walls", SKIP, None,
                      thr.claim_wall_cover_min,
                      "no below-grade bore surface in this patch")]
    cc = sorted(bore_face_coverage(patch, w, faces) for w in bore)
    sc = sorted(bore_face_coverage(patch, w, faces) for w in ramps)

    def _median(xs):
        return xs[len(xs) // 2] if xs else 0.0

    med = _median(cc)
    bar = thr.claim_wall_cover_min
    verdict = SKIP if bar is None else (PASS if med >= bar else FAIL)
    return [Check("bore_corridor_walls", verdict, round(med, 3), bar,
                  f"{len(bore)} below-grade bore surface(s): "
                  f"median face coverage {med:.0%} "
                  f"(min {cc[0]:.0%}, max {cc[-1]:.0%}); "
                  f"{len(ramps)} tunnel_ramp(s) measured the "
                  f"same way: median {_median(sc):.0%}")]


def _mouth_axis(mouth_poly, ramp_geoms):
    """``(cx, cy, ax, ay)`` — the mouth's centroid and the CORRIDOR
    direction there: the unit vector from the nearest ramp's centroid to
    the mouth's.  ``None`` when no ramp answers this mouth, which is
    itself a canonical failure the caller reports.

    The axis is what makes "one wall per SIDE" measurable: a wall's side
    is the sign of the cross product of the axis with the offset from
    the mouth centroid to the wall's.  No new geometric notion of a
    corridor is invented here — the ramp IS the corridor.
    """
    c = mouth_poly.centroid
    best = None
    for _wid, g in ramp_geoms:
        try:
            d = g.distance(mouth_poly)
        except Exception:                                # pragma: no cover
            continue
        if best is None or d < best[0]:
            best = (d, g)
    if best is None:
        return None
    rc = best[1].centroid
    ax, ay = c.x - rc.x, c.y - rc.y
    n = math.hypot(ax, ay)
    if n <= 1e-9:
        return None
    return (c.x, c.y, ax / n, ay / n)


def _check_mouth_inventory(patch: Patch, thr: Thresholds) -> List[Check]:
    """THE CANONICAL TUNNEL MOUTH, enumerated (RULINGS 2026-08-30).

        At a tunnel mouth the emitted set is exactly: ONE ramp surface
        descending the corridor centre to the mouth line, ONE retaining
        wall (wall + foot) per side, ONE straight end cap.  The ramp
        reaches the mouth line.  No second road shape may share the
        corridor.  Nested wall rings and wall fragments are defects.

    Six counts per mouth, all from the emitted patch and all through the
    instrument's own parser: the ramps reaching it, the walls and feet
    per SIDE, the end caps, the DUPLICATE corridor surfaces (two tunnel
    road surfaces overlapping — the class the retired ``tunnel_road``
    claim minted), and the NESTED/FRAGMENT wall pieces.

    Added 2026-08-31 for the redesign's Batch-3 acceptance, EXTENDING
    this instrument rather than forking a second one (RULINGS
    ``7e90032``): the site profile, the parser and the identity spelling
    stay single-sourced, and the mouth population is the same
    ``ref == "tunnel_mouth"`` set the R10-2 walling finding uses.

    With no ``--mouth-canonical`` it REPORTS (SKIPPED) — the full
    inventory is printed either way, because "quote every mouth" is the
    acceptance, not a single number.
    """
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union

    def _poly(w):
        pts = patch.pts(w)
        if len(pts) < 4:
            return None
        try:
            g = Polygon(pts)
            if not g.is_valid:
                g = g.buffer(0)
            return None if g.is_empty else g
        except Exception:                                # pragma: no cover
            return None

    mouths = [(w.wid, _poly(w)) for w in patch.ref_ways("tunnel_mouth")]
    mouths = [(wid, g) for wid, g in mouths if g is not None]
    if not mouths:
        return [Check("mouth_inventory", SKIP, None, None,
                      "no tunnel_mouth piece in this patch")]
    mouth_wids = {wid for wid, _g in mouths}
    ramps = [(w.wid, _poly(w)) for w in patch.role_ways("tunnel_ramp")
             if w.wid not in mouth_wids]
    ramps = [(wid, g) for wid, g in ramps if g is not None]
    walls = [(w.wid, _poly(w)) for w in patch.ref_ways("tunnel_wall")]
    feet = [(w.wid, _poly(w))
            for w in patch.ref_ways("tunnel_wall_foot")]
    caps = [(w.wid, _poly(w)) for w in patch.ref_ways("tunnel_cap")]
    walls = [(wid, g) for wid, g in walls if g is not None]
    feet = [(wid, g) for wid, g in feet if g is not None]
    caps = [(wid, g) for wid, g in caps if g is not None]
    # every tunnel ROAD surface, for the duplicate test
    corridor = list(ramps) + list(mouths)
    for w in patch.ref_ways("tunnel_corridor"):
        g = _poly(w)
        if g is not None:
            corridor.append((w.wid, g))

    def _near(items, poly, radius):
        out = []
        for wid, g in items:
            try:
                if g.distance(poly) <= radius:
                    out.append((wid, g))
            except Exception:                            # pragma: no cover
                continue
        return out

    def _sides(items, axis):
        cx, cy, ax, ay = axis
        left, right = [], []
        for wid, g in items:
            c = g.centroid
            cross = ax * (c.y - cy) - ay * (c.x - cx)
            (left if cross >= 0.0 else right).append(wid)
        return left, right

    lines: List[str] = []
    bad = 0
    totals = Counter()
    for wid, mg in sorted(mouths, key=lambda t: str(t[0])):
        near_ramps = _near(ramps, mg, thr.mouth_reach_m)
        near_walls = _near(walls, mg, thr.mouth_radius_m)
        near_feet = _near(feet, mg, thr.mouth_radius_m)
        near_caps = _near(caps, mg, thr.mouth_radius_m)
        near_corr = _near(corridor, mg, thr.mouth_radius_m)
        axis = _mouth_axis(mg, near_ramps or ramps)
        if axis is None:
            wl = wr = fl = fr = None
        else:
            _l, _r = _sides(near_walls, axis)
            wl, wr = len(_l), len(_r)
            _l, _r = _sides(near_feet, axis)
            fl, fr = len(_l), len(_r)
        # DUPLICATE CORRIDOR SURFACES: two tunnel road surfaces sharing
        # ground.  This is the class R14-1's claim minted beside the
        # synthetic ramp and the stand-down existed to remove.
        dup = 0
        for i in range(len(near_corr)):
            for j in range(i + 1, len(near_corr)):
                try:
                    if near_corr[i][1].intersection(
                            near_corr[j][1]).area >= thr.dup_overlap_m2:
                        dup += 1
                except Exception:                        # pragma: no cover
                    continue
        # NESTED / FRAGMENT WALL PIECES: a wall ring inside another, or a
        # piece too small to be a wall at all.
        band = near_walls + near_feet
        nested = 0
        for i in range(len(band)):
            for j in range(len(band)):
                if i == j:
                    continue
                try:
                    if band[j][1].covers(band[i][1]):
                        nested += 1
                        break
                except Exception:                        # pragma: no cover
                    continue
        frag = sum(1 for _w, g in band if g.area < thr.wall_fragment_m2)
        canonical = (len(near_ramps) == 1 and wl == 1 and wr == 1
                     and fl == 1 and fr == 1 and len(near_caps) == 1
                     and dup == 0 and nested == 0 and frag == 0)
        if not canonical:
            bad += 1
        totals["mouths"] += 1
        totals["ramps"] += len(near_ramps)
        totals["walls"] += len(near_walls)
        totals["feet"] += len(near_feet)
        totals["caps"] += len(near_caps)
        totals["duplicate_corridor_surfaces"] += dup
        totals["nested_wall_pieces"] += nested
        totals["wall_fragments"] += frag
        lines.append(
            f"    mouth {wid}: ramp={len(near_ramps)} "
            f"wall L/R={wl}/{wr} foot L/R={fl}/{fr} "
            f"cap={len(near_caps)} dup={dup} nested={nested} "
            f"frag={frag}  {'CANONICAL' if canonical else 'NOT CANONICAL'}")
    bar = 0 if thr.mouth_canonical else None
    verdict = SKIP if bar is None else (PASS if bad == 0 else FAIL)
    head = (f"{totals['mouths']} tunnel mouth(s), {bad} NOT canonical "
            f"(law: 1 ramp reaching the mouth, 1 wall + 1 foot per side, "
            f"1 end cap, 0 duplicate corridor surfaces, 0 nested/fragment "
            f"walls) — totals: " +
            ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
    return [Check("mouth_inventory", verdict, bad, bar,
                  "\n           ".join([head] + lines))]


def _check_ramp_wall_gap(patch: Patch, thr: Thresholds) -> List[Check]:
    """§T5 / RULINGS 2026-08-28c item 1: the ramp is not welded to the
    rising wall, and the annulus between them is still OWNED.

    Two numbers, because the law has two halves and fixing one by
    breaking the other is exactly what R16-2b and this ruling each
    guard.  Measured before the round: 84 shared node ids over 22 pairs
    at 0.0000 m, and every wall band's inner ring on the ramp boundary.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    ramps = patch.role_ways("tunnel_ramp")
    walls = patch.ref_ways("tunnel_wall")
    if not ramps or not walls:
        return [Check("ramp_wall_gap", SKIP, None, 0,
                      "no ramp/wall pair in this patch")]
    shared = 0
    for r in ramps:
        rc = patch.coordset(r)
        for w in walls:
            shared += len(rc & patch.coordset(w))
    checks = [Check("ramp_wall_gap", PASS if shared == 0 else FAIL,
                    shared, 0,
                    f"node ids shared between {len(ramps)} tunnel_ramp "
                    f"and {len(walls)} tunnel_wall way(s) — the weld the "
                    f"owner read as a broken ramp")]
    # …and the annulus is still owned: no ramp edge faces open ground
    # inside the wall gap.  The FOOT is what owns it after §T5.
    # THE OWNER IS THE WALL STRUCTURE, in either arm.  Measuring the
    # annulus against the FOOT alone makes this check SKIP on a
    # pre-§T5 patch, and a check that cannot read the control arm
    # cannot tell a regression from a pre-existing condition — the
    # question "did §T5 unown anything" is only answerable if both arms
    # are measured the same way.  Before §T5 the rising wall owned the
    # annulus; after it, the foot does; the LAW is that SOMETHING in the
    # wall structure does.
    feet = (patch.ref_ways("tunnel_wall_foot")
            + patch.ref_ways("tunnel_wall"))
    def _polys(ways):
        out = []
        for w in ways:
            pts = patch.pts(w)
            if len(pts) >= 3:
                try:
                    p = Polygon(pts)
                    out.append(p if p.is_valid else p.buffer(0))
                except Exception:                        # pragma: no cover
                    continue
        return out
    fp = _polys(feet)
    rp = _polys(ramps)
    if not fp:
        checks.append(Check("ramp_wall_annulus_owned", SKIP, None, None,
                            "no wall structure emitted at all"))
        return checks
    try:
        foot_u = unary_union(fp)
        unowned = 0
        for p in rp:
            gap = p.boundary.buffer(thr.wall_gap_m).difference(p)
            if not gap.is_empty and gap.difference(foot_u).area > \
                    0.5 * gap.area:
                unowned += 1
    except Exception:                                    # pragma: no cover
        return checks
    checks.append(Check(
        "ramp_wall_annulus_owned", PASS if unowned == 0 else FAIL,
        unowned, 0,
        f"of {len(rp)} ramp(s), those whose {thr.wall_gap_m:g} m "
        f"annulus is mostly unowned by the wall STRUCTURE "
        f"(R16-2b, measurable in both arms)"))
    return checks


def _check_wall_top_flat(patch: Patch, thr: Thresholds) -> List[Check]:
    """§F1 (LEMD ramp/road fidelity spec law 1): THE WALL TOP IS FLAT
    ACROSS ITS WIDTH — at every station the band's inner and outer top
    nodes carry ONE value.

    THE FRAME, and why it needs nothing but the patch.  A ``tunnel_wall``
    band is ~1 m across and its stations stand tens of metres apart, so
    two of its own vertices closer than ``--wall-band-span-m`` in PLAN
    are ACROSS the band by construction, never along its run.  The
    reported number is the worst ``|Δalt|`` over every such pair — the
    read the owner made by hand on the 1.0.265 patch (610.6/610.1,
    608.3/607.7, 606.2/605.4).

    Measured on the LEMD control before the round: worst 0.80 m over the
    portal band at 40.4984622,-3.5850476.  With no ``--wall-top-delta-max``
    this REPORTS rather than adjudicating, which is how the attribution
    arms read it.
    """
    walls = patch.ref_ways("tunnel_wall") + patch.ref_ways(
        "tunnel_wall_foot")
    if not walls:
        return [Check("wall_top_flat", SKIP, None, thr.wall_top_delta_max,
                      "no wall band in this patch")]
    span = float(thr.wall_band_span_m)
    # ── THE FRAME IS THE CREST RING (ruling 2026-08-29) ──────────────
    # THIS MEASURES TWIST, NOT HEIGHT.  Before §T5 shipped its foot the
    # whole band WAS the wall top, so every vertex pair across it was a
    # cross-band pair and the reading was unambiguous.  With the foot
    # the band is a PARTITION: the ``tunnel_wall_foot`` shelf sits at
    # ramp level and the ``tunnel_wall`` face legitimately RISES from
    # the shelf's top to the crest, so a face-inner-vs-face-outer pair
    # is the wall's HEIGHT and reporting it as a twist made the §F1 bar
    # unsatisfiable at the same time as R16-2b's owned annulus.
    #
    # The crest members are the band vertices the SHELF does not carry:
    # foot and face share their common boundary node-for-node (one
    # boolean partition of one polygon), so a face vertex whose
    # canonical spelling a ``tunnel_wall_foot`` way also carries is the
    # face's INNER edge — the foot's top — and belongs to the shelf, not
    # to the crest.  A patch with NO foot way has an empty shelf set and
    # reads EXACTLY as it did before this frame existed, which is what
    # keeps every pre-§T5 number comparable.
    shelf = set()
    for w in patch.ref_ways("tunnel_wall_foot"):
        for nid in w.nids:
            if nid in patch.nodes:
                shelf.add(patch.spell(nid))
    n_shelf_excluded = 0
    worst = 0.0
    worst_at = None
    pairs = 0
    over = 0
    bar = thr.wall_top_delta_max
    for w in walls:
        # ONE VERTEX PER NODE.  A ring closes on its first node, and a
        # repeated coordinate is the same vertex, not a pair: counting it
        # would put a guaranteed 0.00 into the population and let a check
        # PASS on a band it never examined.  The canonical 11-decimal
        # spelling is the identity (memory ``canonical-identity-join``).
        seen: set = set()
        rows = []
        for nid, elev in zip(w.nids, w.elevs):
            if elev is None or nid not in patch.nodes:
                continue
            key = patch.spell(nid)
            if key in seen:
                continue
            seen.add(key)
            if key in shelf and w.ref != "tunnel_wall_foot":
                # the face's inner edge — the SHELF's top, not the crest
                n_shelf_excluded += 1
                continue
            rows.append((patch.ll_to_m(*patch.nodes[nid]), elev))
        for i in range(len(rows)):
            (ax, ay), ae = rows[i]
            for j in range(i + 1, len(rows)):
                (bx, by), be = rows[j]
                if abs(ax - bx) > span or abs(ay - by) > span:
                    continue
                if math.hypot(ax - bx, ay - by) > span:
                    continue
                pairs += 1
                delta = abs(float(ae) - float(be))
                if bar is not None and delta > bar:
                    over += 1
                if delta > worst:
                    worst = delta
                    worst_at = (w.wid, round(float(ae), 2),
                                round(float(be), 2))
    if not pairs:
        return [Check("wall_top_flat", SKIP, None, bar,
                      f"no cross-band CREST pair within {span:g} m — "
                      f"nothing to measure ({n_shelf_excluded} shelf "
                      f"node(s) excluded)")]
    detail = (f"CREST-ONLY frame: {pairs} cross-band pair(s) over "
              f"{len(walls)} band way(s), {n_shelf_excluded} shelf "
              f"node(s) excluded ({len(shelf)} shelf node id(s) from "
              f"{len(patch.ref_ways('tunnel_wall_foot'))} tunnel_wall_"
              f"foot way(s))"
              + (f"; worst on way {worst_at[0]}: "
                 f"{worst_at[1]} vs {worst_at[2]}" if worst_at else ""))
    if bar is None:
        return [Check("wall_top_flat", SKIP, round(worst, 3), None,
                      detail + " (REPORT: no --wall-top-delta-max given)")]
    return [Check("wall_top_flat", PASS if worst <= bar else FAIL,
                  round(worst, 3), bar,
                  detail + f"; {over} pair(s) over the bar")]


def _check_isolated_road_rects(patch: Patch, thr: Thresholds
                               ) -> List[Check]:
    """§T4.2: NO ROAD-CORRIDOR PIECE IS EVER LOST SILENTLY.

    A road rect is ISOLATED when no other road-family surface touches
    it, and the defect the owner read in the sim is the SUBSET of those
    that have a road neighbour within ``isolated_neighbour_m`` — a
    corridor cut in two by a lost junction fill, emitting as two
    disconnected rectangles at different levels.  A genuinely isolated
    rect far from everything is lawful and reported separately.

    The road family is roles, not refs: a rect the scorer re-roled is
    still the corridor's own pavement and still connects it.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    ROAD_ROLES = ("service_road", "service_junction", "junction",
                  "groundside_pavement", "apron")
    rects, family = [], []
    for w in patch.ways:
        pts = patch.pts(w)
        if len(pts) < 3:
            continue
        try:
            p = Polygon(pts)
            if not p.is_valid:
                p = p.buffer(0)
        except Exception:                                # pragma: no cover
            continue
        if p.is_empty:
            continue
        if w.role in ROAD_ROLES:
            family.append((w, p))
        if w.role == "service_road":
            rects.append((w, p))
    if not rects:
        return [Check("isolated_road_rects", SKIP, None,
                      thr.isolated_rects_max,
                      "no service_road rect in this patch")]
    try:
        from shapely.strtree import STRtree
        tree = STRtree([p for _w, p in family])
    except Exception:                                    # pragma: no cover
        tree = None
    def _corridor_width(poly) -> float:
        """The SHORT side of the piece's minimum rotated rectangle — a
        synthesised corridor rect is one corridor wide, and that is what
        separates §T4.2's population from a large carved road surface
        that merely happens to touch nothing."""
        try:
            mrr = poly.minimum_rotated_rectangle
            xy = list(mrr.exterior.coords)[:-1]
            if len(xy) != 4:
                return float("inf")
            import math as _m
            sides = [_m.dist(xy[i], xy[(i + 1) % 4]) for i in range(4)]
            return min(sides)
        except Exception:                                # pragma: no cover
            return float("inf")

    lonely, with_neighbour, sites = 0, 0, []
    narrow_hits = 0
    for w, p in rects:
        near = []
        idxs = (range(len(family)) if tree is None
                else tree.query(p.buffer(thr.isolated_neighbour_m)))
        for i in idxs:
            other_w, other = family[int(i)]
            if other_w.wid == w.wid:
                continue
            d = p.distance(other)
            near.append(d)
        if not near or min(near) > 1e-6:
            lonely += 1
            if near and min(near) <= thr.isolated_neighbour_m:
                with_neighbour += 1
                # §T4.2's OWN population: a CORRIDOR-WIDTH piece whose
                # void is a rect-trim gap.  A large carved road surface
                # standing off a groundside ring by the clearance
                # tolerance is a different mechanism and must not be
                # counted here — measured at LEMD, way -10318 is
                # 2,186 m² beside a 7,893 m² groundside ring, and
                # counting it made the two populations one number.
                cw = _corridor_width(p)
                if cw <= thr.corridor_width_max_m:
                    narrow_hits += 1
                    if len(sites) < 6:
                        sites.append(
                            f"way {w.wid} (gap {min(near):.1f} m, "
                            f"width {cw:.1f} m)")
    verdict = (SKIP if thr.isolated_rects_max is None
               else (PASS if narrow_hits <= thr.isolated_rects_max
                     else FAIL))
    return [Check("isolated_road_rects", verdict, narrow_hits,
                  thr.isolated_rects_max,
                  f"{narrow_hits} CORRIDOR-WIDTH (<= "
                  f"{thr.corridor_width_max_m:.0f} m) isolated rect(s) "
                  f"with a road neighbour within "
                  f"{thr.isolated_neighbour_m:.0f} m — §T4.2's LOST-FILL "
                  f"class; {with_neighbour} of {lonely} isolated rect(s) "
                  f"have such a neighbour at ANY width, out of "
                  f"{len(rects)} service_road rect(s)"
                  + (" — e.g. " + ", ".join(sites) if sites else ""))]


def _check_no_low_connector(patch: Patch) -> List[Check]:
    n = len(patch.ref_ways("tunnel_low_connector"))
    return [Check("no_low_connector", PASS if n == 0 else FAIL, n, 0,
                  "a mapped bore's interior is roofed by definition")]


def _check_needle(patch: Patch, control: Optional[Patch],
                  profile: Profile, thr: Thresholds) -> List[Check]:
    """No way mixing altitudes ≥ ``needle_spread_m`` apart inside the
    footprint the control's needle way occupied."""
    from shapely.geometry import LineString
    if control is None or not profile.needle_control_way:
        return [Check("no_needle", SKIP, None, 0,
                      "needs --control and a profile needle way")]
    cw = control.by_wid.get(profile.needle_control_way)
    if cw is None:
        return [Check("no_needle", SKIP, None, 0,
                      f"control way {profile.needle_control_way} absent")]
    cpts = control.pts(cw)
    if len(cpts) < 3:
        return [Check("no_needle", SKIP, None, 0, "degenerate footprint")]
    foot = LineString(cpts).convex_hull.buffer(1.0)
    hits = []
    for w in patch.ways:
        pts = patch.pts(w)
        a = [e for e in w.elevs if e is not None]
        if len(pts) < 2 or len(a) < 2:
            continue
        if max(a) - min(a) >= thr.needle_spread_m \
                and LineString(pts).intersects(foot):
            hits.append((w.wid, w.ref, round(max(a) - min(a), 2)))
    return [Check("no_needle", PASS if not hits else FAIL, len(hits), 0,
                  f"ways with a ≥{thr.needle_spread_m:.0f} m altitude "
                  f"spread in the control needle footprint: {hits[:5]}")]


def _check_flat_pad(patch: Patch, control: Optional[Patch],
                    profile: Profile, thr: Thresholds) -> List[Check]:
    if not profile.flat_pad_ref:
        return [Check("pad_flat", SKIP, None, None, "no pad in the profile")]
    hits = patch.ref_ways(profile.flat_pad_ref)
    if not hits:
        return [Check("pad_flat", SKIP, None, None,
                      f"no way with ref={profile.flat_pad_ref!r}")]
    vals = [e for e in hits[0].elevs if e is not None]
    if not vals:
        return [Check("pad_flat", SKIP, None, None, "pad carries no values")]
    spread = max(vals) - min(vals)
    ctl = ""
    if control is not None:
        cw = control.ref_ways(profile.flat_pad_ref)
        if cw:
            cv = [e for e in cw[0].elevs if e is not None]
            if cv:
                ctl = (f"; control [{min(cv):.2f},{max(cv):.2f}] "
                       f"Δ{abs(vals[0] - cv[0]):.2f} m")
    return [Check("pad_flat", PASS if spread <= thr.pad_flat_tol_m else FAIL,
                  round(spread, 3), thr.pad_flat_tol_m,
                  f"{profile.flat_pad_ref} = "
                  f"[{min(vals):.2f},{max(vals):.2f}]{ctl}")]


def _subgrade_by_role(patch: Patch, roles) -> Dict[str, int]:
    tally: Counter = Counter()
    seen = set()
    for w in patch.ways:
        if w.role not in roles:
            continue
        for n, e in zip(w.nids, w.elevs):
            if e is not None and e < 0.0 and (w.role, n) not in seen:
                seen.add((w.role, n))
                tally[w.role] += 1
    return {r: tally.get(r, 0) for r in roles}


def _check_subgrade(patch: Patch, control: Optional[Patch],
                    profile: Profile) -> List[Check]:
    """No pavement role may be dragged below grade beyond what the
    control already had."""
    mine = _subgrade_by_role(patch, profile.subgrade_roles)
    if control is None:
        return [Check("subgrade_by_role", SKIP, mine, None,
                      "needs --control for the comparison")]
    theirs = _subgrade_by_role(control, profile.subgrade_roles)
    over = {r: (mine[r], theirs[r]) for r in profile.subgrade_roles
            if mine[r] > theirs[r]}
    return [Check("subgrade_by_role", PASS if not over else FAIL,
                  mine, theirs,
                  "role: patch/control — "
                  + ", ".join(f"{r} {mine[r]}/{theirs[r]}"
                              for r in profile.subgrade_roles)
                  + (f"   OVER: {over}" if over else ""))]


def _check_geometry_drift(patch: Patch, control: Optional[Patch],
                          thr: Thresholds) -> List[Check]:
    """Ways BYTE-IDENTICAL in geometry to a control twin whose altitudes
    moved.  ONE identity predicate, stated: the canonical 11-decimal
    coordinate SET, joined to the control way sharing the most of it, and
    required to match exactly.  (Two rounds measured this class with two
    different predicates and got 148 and 164 for the same population —
    memory ``two-instruments-one-assumed-population``.)"""
    if control is None:
        return [Check("geometry_drift", SKIP, None, thr.drift_max,
                      "needs --control")]
    csets = {w.wid: control.coordset(w) for w in control.ways}
    calts = {w.wid: control.altvec(w) for w in control.ways}
    bycoord: Dict[Tuple[str, str], set] = defaultdict(set)
    for wid, cs in csets.items():
        for c in cs:
            bycoord[c].add(wid)
    same, drift = 0, []
    for w in patch.ways:
        cs = patch.coordset(w)
        if len(cs) < 3:
            continue
        cand: Counter = Counter()
        for c in cs:
            for wid in bycoord.get(c, ()):
                cand[wid] += 1
        if not cand:
            continue
        # MOST-SHARED wins, ties broken by way id.  ``most_common`` alone
        # breaks a tie by insertion order, which here comes from set
        # iteration and therefore from PYTHONHASHSEED — two runs of the
        # same instrument on the same bytes read 8 and 9.  A join that
        # depends on iteration order is not a measurement
        # (``check_grade.resolve_feature_hosts`` carries the same rule).
        best = sorted(cand.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0]
        if csets[best] != cs:
            continue
        same += 1
        fa, ca = patch.altvec(w), calts[best]
        worst = max((abs(v - ca[k]) for k, v in fa.items()
                     if v is not None and ca.get(k) is not None),
                    default=0.0)
        if worst >= thr.drift_floor_m:
            drift.append((round(worst, 3), w.wid, w.role))
    drift.sort(reverse=True)
    verdict = (SKIP if thr.drift_max is None
               else (PASS if len(drift) <= thr.drift_max else FAIL))
    return [Check("geometry_drift", verdict, len(drift), thr.drift_max,
                  f"{same} same-geometry ways; {len(drift)} drifted "
                  f"≥{thr.drift_floor_m:.2f} m; worst "
                  f"{[d[:3] for d in drift[:6]]}")]


def _check_retreat_walls(patch: Patch, thr: Thresholds) -> List[Check]:
    """``authority_retreat_wall`` improvising at a ramp edge means the
    tunnel machinery is not walling its own cut."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    ramps = [LineString(p) for p in
             (patch.pts(w) for w in patch.role_ways("tunnel_ramp"))
             if len(p) >= 2]
    walls = [(w.wid, LineString(patch.pts(w)))
             for w in patch.ref_ways("authority_retreat_wall")
             if len(patch.pts(w)) >= 2]
    if not ramps:
        return [Check("retreat_walls_near_ramps", SKIP, None,
                      thr.retreat_wall_max, "no tunnel_ramp geometry")]
    ru = unary_union(ramps)
    near = [wid for wid, g in walls
            if g.distance(ru) <= thr.retreat_wall_radius_m]
    verdict = (SKIP if thr.retreat_wall_max is None
               else (PASS if len(near) <= thr.retreat_wall_max else FAIL))
    return [Check("retreat_walls_near_ramps", verdict, len(near),
                  thr.retreat_wall_max,
                  f"{len(walls)} retreat wall(s) in the patch; "
                  f"{len(near)} within {thr.retreat_wall_radius_m:.0f} m "
                  f"of a tunnel_ramp ring")]


# ── row-level checks: every count comes from the census ────────────
def _census_rows(osm: Path, census, cg, want_sites: bool = True) -> dict:
    """``census_one``'s own itemised rows + report for one patch.  The
    ONLY row source in this file."""
    with tempfile.TemporaryDirectory(prefix="tpa_rows_") as td:
        rows_out = Path(td) / "rows.json"
        rep = census.census_one(Path(osm), cg, top=0, rows_out=rows_out,
                                want_sites=want_sites)
        rows = json.loads(rows_out.read_text())["rows"]
    return {"report": rep, "rows": rows}


def _check_over_cap_ramp_rows(rows: list, thr: Thresholds) -> List[Check]:
    over = [r for r in rows
            if r.get("family") == "within_shape"
            and "tunnel_ramp" in (r.get("roles") or "")
            and (r.get("grade_pct") or 0.0) > (r.get("cap_pct") or 0.0)]
    ways = Counter((r.get("way_a"), r.get("way_b")) for r in over)
    verdict = (SKIP if thr.over_cap_ramp_max is None
               else (PASS if len(over) <= thr.over_cap_ramp_max else FAIL))
    worst = max((r.get("grade_pct") or 0.0 for r in over), default=0.0)
    return [Check("over_cap_ramp_rows", verdict, len(over),
                  thr.over_cap_ramp_max,
                  f"worst grade {worst:.2f}% ; by way {ways.most_common(6)}")]


def _check_role_less_ring_rows(patch: Patch, rows: list) -> List[Check]:
    """Rows minted by a ROLE-LESS interior ring.  Under the host-cap law
    a ring is judged at its host's role, so a row still naming one must
    read with a real role pair — never ``?``/``<none>``."""
    rings = {w.wid for w in patch.ways
             if not w.tags.get("role")
             and w.tags.get("o4_feature") in ("shape_interior_ring",
                                              "gap_interior_ring")}
    hit = [r for r in rows
           if str(r.get("way_a")) in rings or str(r.get("way_b")) in rings]
    roleless = [r for r in hit
                if "?" in (r.get("roles") or "")
                or "<none>" in (r.get("roles") or "")]
    classes = Counter("{}::{}".format(r.get("family"), r.get("roles"))
                      for r in hit)
    return [Check("role_less_ring_rows", PASS if not roleless else FAIL,
                  len(roleless), 0,
                  f"{len(rings)} interior-ring way(s); {len(hit)} row(s) "
                  f"name one; classes {dict(classes)}")]


def _adjudicated(rep: dict) -> Optional[int]:
    """The census's OWN adjudicated total (never recomputed here)."""
    adj = rep.get("adjudication") or {}
    if isinstance(adj.get("adjudicated_total"), int):
        return adj["adjudicated_total"]
    # Fallback ONLY if the census renames its own field: law-true minus
    # the two REPORTED-never-dropped classes, exactly the census's note.
    lt = rep.get("lawtrue")
    total = lt.get("total") if isinstance(lt, dict) else lt
    deferred = adj.get("deferred_total")
    oos = adj.get("out_of_scope_total")
    if all(isinstance(v, int) for v in (total, deferred, oos)):
        return total - deferred - oos
    return None


def _check_census_deltas(mine: dict, theirs: Optional[dict],
                         thr: Thresholds) -> List[Check]:
    checks: List[Check] = []
    a_mine = _adjudicated(mine["report"])
    sites_mine = ((mine["report"].get("sites") or {})
                  .get("sites_actionable"))
    if theirs is None:
        checks.append(Check("adjudicated_delta", SKIP, a_mine,
                            thr.adjudicated_delta_max, "needs --control"))
    else:
        a_ctl = _adjudicated(theirs["report"])
        if a_mine is None or a_ctl is None:
            checks.append(Check("adjudicated_delta", SKIP, None,
                                thr.adjudicated_delta_max,
                                "census report carries no adjudicated total"))
        else:
            delta = a_mine - a_ctl
            verdict = (SKIP if thr.adjudicated_delta_max is None
                       else (PASS if delta <= thr.adjudicated_delta_max
                             else FAIL))
            checks.append(Check("adjudicated_delta", verdict, delta,
                                thr.adjudicated_delta_max,
                                f"patch {a_mine} vs control {a_ctl}"))
    verdict = (SKIP if (thr.actionable_sites_max is None
                        or sites_mine is None)
               else (PASS if sites_mine <= thr.actionable_sites_max
                     else FAIL))
    ctl_sites = (None if theirs is None
                 else (theirs["report"].get("sites") or {})
                 .get("sites_actionable"))
    checks.append(Check("actionable_sites", verdict, sites_mine,
                        thr.actionable_sites_max,
                        f"control {ctl_sites}"))
    return checks


# ──────────────────────────────────────────────────────────────────
# The library entry — the CLI is a formatter over THIS
# ──────────────────────────────────────────────────────────────────
def run_acceptance(patch_path, control_path=None, *,
                   profile: Optional[Profile] = None,
                   thresholds: Optional[Thresholds] = None,
                   osm_data_dir=None,
                   census=None) -> List[Check]:
    """Run every acceptance check and return the results.

    ``census`` (the loaded ``tools/harness/census.py`` module) is injected
    so a caller — and the twin test — runs the SAME code path the CLI
    does; when omitted it is loaded here.
    """
    census = census or load_census()
    cg = census.load_check_grade()
    profile = profile or Profile(name="(none)")
    thr = thresholds or Thresholds()

    patch = Patch(Path(patch_path), cg)
    control = Patch(Path(control_path), cg) if control_path else None
    bores = _bore_lines(profile, osm_data_dir, patch.ll_to_m)

    checks: List[Check] = []
    checks += _check_site_reach(patch, profile, thr)
    checks += _check_covered_span(patch, profile, bores, thr)
    checks += _check_covered_span(patch, profile, bores)
    checks += _check_isolated_road_rects(patch, thr)
    checks += _check_mouth_inventory(patch, thr)
    checks += _check_bore_corridor_walls(patch, thr)
    checks += _check_ramp_wall_gap(patch, thr)
    checks += _check_wall_top_flat(patch, thr)
    checks += _check_no_low_connector(patch)
    checks += _check_needle(patch, control, profile, thr)
    checks += _check_flat_pad(patch, control, profile, thr)
    checks += _check_subgrade(patch, control, profile)
    checks += _check_geometry_drift(patch, control, thr)
    checks += _check_retreat_walls(patch, thr)

    mine = _census_rows(Path(patch_path), census, cg)
    theirs = (_census_rows(Path(control_path), census, cg)
              if control_path else None)
    checks += _check_over_cap_ramp_rows(mine["rows"], thr)
    checks += _check_role_less_ring_rows(patch, mine["rows"])
    checks += _check_census_deltas(mine, theirs, thr)
    return checks


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────
def _parse_sites(values) -> Dict[str, Tuple[float, float]]:
    out: Dict[str, Tuple[float, float]] = {}
    for raw in values or ():
        name, _, coords = raw.partition("=")
        lat, _, lon = coords.partition(",")
        out[name.strip()] = (float(lat), float(lon))
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tunnel_portal_acceptance",
        description=__doc__.split("\n\n")[0])
    p.add_argument("patch", help="the emitted patch under test (.osm)")
    p.add_argument("--control", help="a control patch for the A/B checks")
    p.add_argument("--profile", choices=sorted(SITE_PROFILES),
                   help="a shipped site profile")
    p.add_argument("--site", action="append",
                   help="NAME=LAT,LON (repeatable; the FIRST is the mouth)")
    # §T8.2: --site mode gains the bore inputs, so an ad-hoc run can
    # execute the covered-span and claim checks instead of SKIPPING them.
    p.add_argument("--bore-osm",
                   help="mapped-bore source: an OSM extract (.osm/.osm.bz2) "
                        "or a road-feed .cache, relative to --osm-data-dir "
                        "or absolute")
    p.add_argument("--bore-ways",
                   help="comma-separated mapped-bore way ids in --bore-osm")
    p.add_argument("--covered-span",
                   help="LO,HI arc-length metres of the bore that is "
                        "ROOFED (the covered-span check's window)")
    p.add_argument("--osm-data-dir", default=str(ROOT / "OSM_data"),
                   help="OSM_data root for the mapped-bore cache")
    p.add_argument("--json", help="write the results to this path")
    for name, default in (("mouth-max-m", 15.0), ("site-max-m", 60.0),
                          ("needle-spread-m", 8.0), ("drift-floor-m", 0.5),
                          ("retreat-wall-radius-m", 2.0),
                          ("claimed-bore-max-m", 0.0),
                          ("datum-ring-m", 25.0),
                          ("below-grade-m", 0.50),
                          ("wall-gap-m", 0.6),
                          ("isolated-neighbour-m", 10.0),
                          ("corridor-width-max-m", 8.0),
                          ("wall-band-span-m", 2.0)):
        p.add_argument(f"--{name}", type=float, default=default)
    p.add_argument("--datum-min-samples", type=int, default=8)
    for name, default in (("mouth-reach-m", 1.0),
                          ("mouth-radius-m", 25.0),
                          ("dup-overlap-m2", 2.0),
                          ("wall-fragment-m2", 1.0)):
        p.add_argument(f"--{name}", type=float, default=default)
    p.add_argument("--mouth-canonical", action="store_true",
                   help="RULINGS 2026-08-30: FAIL unless EVERY tunnel "
                        "mouth is canonical (default: report the full "
                        "inventory, verdict SKIPPED)")
    p.add_argument("--claim-wall-cover-min", type=float, default=None,
                   help="§T6.1 bar: median face coverage of the "
                        "below-grade bore surfaces (0-1)")
    for name in ("drift-max", "retreat-wall-max", "over-cap-ramp-max",
                 "actionable-sites-max",
                 "isolated-rects-max"):
        p.add_argument(f"--{name}", type=int, default=None)
    p.add_argument("--adjudicated-delta-max", type=float, default=None)
    p.add_argument("--wall-top-delta-max", type=float, default=None,
                   help="§F1 bar: worst |Δalt| between two tunnel_wall "
                        "vertices ACROSS the band (default: REPORT only)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    profile = (SITE_PROFILES[args.profile] if args.profile
               else Profile(name="(cli)"))
    sites = _parse_sites(args.site)
    _over: Dict[str, Any] = {}
    if sites:
        _over["sites"] = sites
    if args.bore_osm:
        _over["bore_osm_relpath"] = args.bore_osm
    if args.bore_ways:
        _over["bore_way_ids"] = tuple(
            w.strip() for w in args.bore_ways.split(",") if w.strip())
    if args.covered_span:
        _lo, _, _hi = args.covered_span.partition(",")
        _over["covered_span_m"] = (float(_lo), float(_hi))
    if _over:
        profile = Profile(**{**asdict(profile), **_over})
    thr = Thresholds(
        mouth_max_m=args.mouth_max_m, site_max_m=args.site_max_m,
        needle_spread_m=args.needle_spread_m, drift_max=args.drift_max,
        drift_floor_m=args.drift_floor_m,
        retreat_wall_max=args.retreat_wall_max,
        retreat_wall_radius_m=args.retreat_wall_radius_m,
        over_cap_ramp_max=args.over_cap_ramp_max,
        adjudicated_delta_max=args.adjudicated_delta_max,
        actionable_sites_max=args.actionable_sites_max,
        claimed_bore_max_m=args.claimed_bore_max_m,
        datum_ring_m=args.datum_ring_m,
        datum_min_samples=args.datum_min_samples,
        below_grade_m=args.below_grade_m,
        claim_wall_cover_min=args.claim_wall_cover_min,
        wall_gap_m=args.wall_gap_m,
        isolated_neighbour_m=args.isolated_neighbour_m,
        isolated_rects_max=args.isolated_rects_max,
        corridor_width_max_m=args.corridor_width_max_m,
        wall_band_span_m=args.wall_band_span_m,
        wall_top_delta_max=args.wall_top_delta_max,
        mouth_reach_m=args.mouth_reach_m,
        mouth_radius_m=args.mouth_radius_m,
        dup_overlap_m2=args.dup_overlap_m2,
        wall_fragment_m2=args.wall_fragment_m2,
        mouth_canonical=bool(args.mouth_canonical))
    checks = run_acceptance(args.patch, args.control, profile=profile,
                            thresholds=thr, osm_data_dir=args.osm_data_dir)
    print(f"=== TUNNEL PORTAL ACCEPTANCE — {args.patch} ===")
    print(f"  control={args.control}  profile={profile.name}")
    for c in checks:
        print(c.line())
    n_fail = sum(1 for c in checks if c.verdict == FAIL)
    n_skip = sum(1 for c in checks if c.verdict == SKIP)
    print(f"  --> {len(checks) - n_fail - n_skip} PASS, {n_fail} FAIL, "
          f"{n_skip} SKIPPED")
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"patch": args.patch, "control": args.control,
             "profile": profile.name,
             "checks": [asdict(c) for c in checks]}, indent=1))
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
