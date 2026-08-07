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
        --adjudicated-delta-max -24 --actionable-sites-max 82

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
    when the road cache is not reachable (the check then SKIPS)."""
    if not profile.bore_osm_relpath or osm_data_dir is None:
        return None
    path = Path(osm_data_dir) / profile.bore_osm_relpath
    if not path.exists():
        return None
    from shapely.geometry import LineString
    opener = bz2.open if path.suffix == ".bz2" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        root = ET.parse(fh).getroot()
    nn = {n.get("id"): to_m(float(n.get("lat")), float(n.get("lon")))
          for n in root.findall("node")}
    out = {}
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
def _check_site_reach(patch: Patch, profile: Profile, thr: Thresholds
                      ) -> List[Check]:
    """A ``tunnel_ramp`` surface within reach of every named site, and a
    ramp VERTEX within ``mouth_max_m`` of the mouth (the first site)."""
    from shapely.geometry import LineString, Point
    if not profile.sites:
        return [Check("site_reach", SKIP, None, None,
                      "no sites: pass --profile or --site NAME=LAT,LON")]
    geoms = []
    for w in patch.role_ways("tunnel_ramp"):
        pts = patch.pts(w)
        if len(pts) >= 2:
            geoms.append((w.wid, LineString(pts)))
    if not geoms:
        return [Check("site_reach", FAIL, 0, len(profile.sites),
                      "the patch emitted no tunnel_ramp geometry at all")]
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
        f"{len(profile.sites)} site(s)"))
    mouth = next(iter(profile.sites.items()))
    mp = Point(patch.ll_to_m(*mouth[1]))
    vd = min((mp.distance(Point(v)) for _wid, g in geoms
              for v in g.coords), default=float("inf"))
    checks.append(Check(
        "mouth_vertex_reach", PASS if vd <= thr.mouth_max_m else FAIL,
        round(vd, 1), thr.mouth_max_m,
        f"nearest ramp VERTEX to {mouth[0]!r}"))
    return checks


def _check_covered_span(patch: Patch, profile: Profile, bores) -> List[Check]:
    """No emitted vertex below grade over the bore's COVERED span — a
    roofed stretch has no open trench."""
    from shapely.geometry import Point
    from shapely.ops import substring, unary_union
    if not bores:
        return [Check("covered_span_clean", SKIP, None, 0,
                      "mapped-bore road cache not reachable "
                      "(--osm-data-dir / --bore-osm)")]
    lo, hi = profile.covered_span_m
    worst = 0
    detail = []
    for half in profile.covered_half_widths_m:
        corridor = unary_union(
            [substring(g, lo, hi) for g in bores.values()]).buffer(half)
        bad = 0
        for w in patch.ways:
            for n, e in zip(w.nids, w.elevs):
                if e is not None and e < 0.0 and n in patch.nodes:
                    if corridor.contains(Point(patch.ll_to_m(
                            *patch.nodes[n]))):
                        bad += 1
        worst = max(worst, bad)
        detail.append(f"half-width {half:.0f} m: {bad}")
    return [Check("covered_span_clean", PASS if worst == 0 else FAIL,
                  worst, 0,
                  f"below-grade vertices over s∈[{lo:.0f},{hi:.0f}] — "
                  + ", ".join(detail))]


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
    checks += _check_covered_span(patch, profile, bores)
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
    p.add_argument("--osm-data-dir", default=str(ROOT / "OSM_data"),
                   help="OSM_data root for the mapped-bore cache")
    p.add_argument("--json", help="write the results to this path")
    for name, default in (("mouth-max-m", 15.0), ("site-max-m", 60.0),
                          ("needle-spread-m", 8.0), ("drift-floor-m", 0.5),
                          ("retreat-wall-radius-m", 2.0)):
        p.add_argument(f"--{name}", type=float, default=default)
    for name in ("drift-max", "retreat-wall-max", "over-cap-ramp-max",
                 "actionable-sites-max"):
        p.add_argument(f"--{name}", type=int, default=None)
    p.add_argument("--adjudicated-delta-max", type=float, default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    profile = (SITE_PROFILES[args.profile] if args.profile
               else Profile(name="(cli)"))
    sites = _parse_sites(args.site)
    if sites:
        profile = Profile(**{**asdict(profile), "sites": sites})
    thr = Thresholds(
        mouth_max_m=args.mouth_max_m, site_max_m=args.site_max_m,
        needle_spread_m=args.needle_spread_m, drift_max=args.drift_max,
        drift_floor_m=args.drift_floor_m,
        retreat_wall_max=args.retreat_wall_max,
        retreat_wall_radius_m=args.retreat_wall_radius_m,
        over_cap_ramp_max=args.over_cap_ramp_max,
        adjudicated_delta_max=args.adjudicated_delta_max,
        actionable_sites_max=args.actionable_sites_max)
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
