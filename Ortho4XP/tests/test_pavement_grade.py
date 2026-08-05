"""End-to-end grade validation for the pavement builder.

Skipped automatically unless an X-Plane install is available (the
builder needs CIFP + DEM tiles).  When run, it builds SPJC + SPLP,
writes the output OSM, then invokes ``tools.check_grade.run_checks``
to assert:

* No cross-shape proximity violations (shared corners agree on elev).
* No vertex-to-edge steps > 0.5 m (no visible drops between
  adjacent shapes — the user-reported "1 m drop" regression).
* Within-shape grade violations stay below a soft cap (the long-
  thin-apron-triangle case is a known limitation documented for
  follow-up; this test guards against new regressions).

SCOPE (``O4_TEST_AIRPORTS``).  **The FULL battery is the acceptance
frame** — a claim about this gate means the whole airport set, and
nothing less.  ``O4_TEST_AIRPORTS=ICAO[,ICAO…]`` narrows the
parametrisation to exactly those airports; that is an ITERATION tool
(SPLP alone is ~25 s against the battery's ~712 s), never the evidence
a change is green.  Scoped runs key the run ledger on the env, so they
are recorded as distinct entries and can never be mistaken for a full
run.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from conftest import baseline_airports, airports_under_test

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def _xplane_root() -> str:
    return os.environ.get("XPLANE_ROOT", "/Users/noah/X-Plane 12")


def _xplane_available() -> bool:
    root = _xplane_root()
    return (Path(root).is_dir()
            and (Path(root) / "Custom Data" / "CIFP").is_dir())


pytestmark = pytest.mark.skipif(
    not _xplane_available(),
    reason="X-Plane install not found (set XPLANE_ROOT to override)",
)


# Grade thresholds are UNIVERSAL and ZERO — no per-airport caps, no
# baselines, no soft exceptions (user 2026-05-31).  A within-shape
# vertex pair > 1.5 %, a cross-shape elevation disagreement, or a
# mid-edge step > 0.5 m means the elevation solver / source geometry
# produced a non-compliant surface; the fix is there, not in the
# threshold.  Any airport with residual violations FAILS until fixed.
WITHIN_SHAPE_CAP = 0
MID_EDGE_CAP = 0


# ══════════════════════════════════════════════════════════════════════
# ADJUDICATED RED, 2026-08-04 (test-maintenance lane) — REAL DEFECT
# WITNESSES, DELIBERATELY NOT MARKED.
#
# Five of the suite's standing reds live in this module:
# ``test_pavement_grade`` for SPJC / SPLP / CYXY / HECA, and
# ``test_runway_longitudinal_grade[HECA]``.
#
# RE-PINNED 2026-08-05 to the RELEASE TIP (f607018, the P2 flip batch:
# O4_SEAT_STAMP_GUARD + O4_STRIP_HEAL_LAW default ON).  Measured at
# f607018, full battery, law-true frame — these numbers ARE the
# instrument's current reading, not an expectation:
#   CYXY   cross=0  steps=0    within=149
#   SPLP   cross=0  steps=26   within=44    (worst step 5.79 m)
#   SPJC   cross=0  steps=0    within=1377
#   HECA   cross=0  steps=126  within=8865  (worst step 3.47 m)
#   HECA runway 05C/23C longitudinal 2.45% against the 1.50% cap
#     @ 30.10458,31.40419
# These reconcile with the RELEASE census minted at the f607018 tip
# (SPJC 1382, SPLP 27, CYXY 149, HECA 8865, KCLT 2643), i.e. this gate
# and the census are measuring the same population.  The SPJC / SPLP
# offsets (1377 vs 1382, 44 vs 27) are the standing frame difference:
# this gate grades the PER-TILE cut geometry the way Ortho4XP ships it
# (``_airport_tiles`` above), the census grades the whole-airport patch.
#
# PREVIOUS PIN, for the delta (c48ce36 tip, 2026-08-04): CYXY 155,
# SPLP 44/26, SPJC 1361, HECA 9125/131; census SPJC 1366, SPLP 27,
# CYXY 155, HECA 9125, KCLT 2643.  The movement is attributed
# interventionally at the P3 tip, one gate at a time, same tree:
# the seat-stamp guard owns HECA -236 within / -5 steps and SPJC +16
# (an AIRSIDE regression, lead-ratification item); the strip-heal law
# owns HECA seam 28->4 (-24 within) and CYXY seam 6->0 (-6 within),
# and is census-inert at SPJC / KCLT / SPLP / HEAZ.
#
# They are NOT stale expectations and NOT broken tests: the caps above
# are the universal zero the owner set (2026-05-31), and this module is
# the campaign's own acceptance instrument for the five-airport
# law-compliance goal.
#
# WHY NO ``xfail(strict=True)`` DRAIN-LEDGER MARKER.  The drain ledger
# exists to keep a known defect VISIBLE while the suite goes green
# around it.  These five are already maximally visible — they are the
# number the campaign is driving to zero.  Marking them would (a)
# manufacture a green suite that asserts nothing about the goal, and
# (b) break the instrument, since a strict xfail turns every partial
# win into a suite failure.  A smaller honest red set beats a fake
# green: these stay RED until the surface is lawful, which is the
# definition of done.
# ══════════════════════════════════════════════════════════════════════


def _airport_tiles(icao: str, root: str):
    """Integer ``(lat, lon)`` tiles the airport's pavement occupies.

    A cheap geometry-only build (``compute_elevations=False`` skips the
    elevation / runway-segmenter / seam / tile_cut pipeline) gives the
    footprint without paying for the full build.  The grade audit then
    builds each of these tiles the way Ortho4XP SHIPS them — per-tile,
    with that tile's DEM and ``current_tile_lat/lon`` — so we grade the
    final cut-and-adjusted geometry, not the pre-cut whole-airport
    superset (user 2026-05-23).
    """
    import math
    # Shared session cache (conftest) — geometry-only footprint build.
    from conftest import cached_airport_layout
    layout = cached_airport_layout(icao, compute_elevations=False)
    lats: list = []
    lons: list = []
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        for (x, y) in s.polygon.exterior.coords:
            lat, lon = layout.m_to_ll(x, y)
            lats.append(lat)
            lons.append(lon)
    if not lats:
        return []
    tiles = []
    for la in range(int(math.floor(min(lats))),
                    int(math.floor(max(lats))) + 1):
        for lo in range(int(math.floor(min(lons))),
                        int(math.floor(max(lons))) + 1):
            tiles.append((la, lo))
    return tiles


# HECA is grade-checked here even though it is NOT in the global
# ``baseline_airports()`` invariant set (adding it there would pull HECA into
# every geometry invariant at once).  Scoping it to the GRADE gate makes the
# real within-shape / cross-shape violations the Ortho4XP-window WARN already
# reports become CI-visible — closing the runtime-vs-test gap where HECA's
# grade was never asserted (terminal-8 apron ramp, steep stub/cross_connector
# rects, a shared-corner step).  This gate is RED until the solver pulls
# apron-bridged terminals to a grade-compatible level (see the T8 investigation
# in docs/presolve_geometry_refactor.md / memory); it turns GREEN when the
# violations are fixed, proving the fix.
def _grade_test_airports() -> list:
    """The airport set this module parametrises over.

    * ``O4_TEST_AIRPORTS`` UNSET (or empty) → the FULL BATTERY: the
      baseline invariant set, plus HECA, plus anything ``O4_TEST_TILE``
      discovery adds.  Unchanged from before this helper existed — the
      union semantics for the tile-discovery path are deliberate.
    * ``O4_TEST_AIRPORTS=ICAO[,ICAO…]`` → EXACTLY those airports.

    Before this, the env list was UNIONED in, so a scoped request still
    paid for the whole battery (~712 s) and the scoping variable did
    nothing here.
    """
    scoped = set(airports_under_test())
    if os.environ.get("O4_TEST_AIRPORTS", "").strip():
        return sorted(scoped)
    return sorted(set(baseline_airports()) | {"HECA"} | scoped)


_GRADE_TEST_AIRPORTS = _grade_test_airports()


@pytest.mark.parametrize("icao", _GRADE_TEST_AIRPORTS)
def test_pavement_grade(tmp_path, icao):
    import check_grade

    tiles = _airport_tiles(icao, _xplane_root())
    assert tiles, f"{icao}: no pavement footprint tiles discovered"

    # Audit each shipped per-tile patch; aggregate violations.
    within: list = []
    cross: list = []
    steps: list = []
    # All builds go through the shared cache (conftest.cached_airport_layout),
    # which uses the SMOOTHED (apt_smoothing_pix=8) DEM production ships.
    # Single-tile airport: no integer line crosses the footprint, so
    # tile_cut is a no-op and the per-tile build is bit-identical to the
    # whole-airport cached layout — reuse it directly (no current_tile).
    # Multi-tile (e.g. SPLP): build per tile, but via the SAME cache key
    # (icao, tile) the compare_target / tile_cut tests use, so the tile is
    # built ONCE per run instead of once per consuming test.
    from conftest import cached_airport_layout
    single_tile = len(tiles) == 1
    for (tlat, tlon) in tiles:
        if single_tile:
            layout = cached_airport_layout(icao)
        else:
            layout = cached_airport_layout(
                icao, tile_lat=tlat, tile_lon=tlon)
        if not layout.shapes:
            continue  # airport doesn't reach this corner tile
        out = tmp_path / f"{icao}_tile{tlat:+d}{tlon:+d}.osm"
        layout.to_osm(str(out))

        # LAW-TRUE frame (2026-07-05): mirror EXACTLY what ``layout.to_osm``'s
        # ``_write_axes_sidecar`` exports for ``tools/check_grade.py`` — the
        # EXACT-AXES mirror of ``grade_graph.build_context``
        # (``verification.taxi_axes_exact_ll``: unsplit polylines, per-SEGMENT
        # caps, route ordinal), the builder's projection ANCHOR, and the
        # tile-seam PIN vertices — so this test measures through the SAME
        # frame as the standalone CLI and cannot drift from the solver's law
        # reading.  NEVER re-derive centerlines from the OSM.
        from auto_patch.verification import (taxi_axes_exact_ll,
                                             junction_mesh_edges_ll)
        from auto_patch.elevation_per_surface.route_profile.apron_terrace \
            import terrace_joints_sidecar as _terrace_joints_sidecar
        axes_exact, routes_exact = taxi_axes_exact_ll(layout)
        # EXACT-MESH sidecar mirror: the solver's junction mesh, consumed
        # 1:1 (emit-time ring repairs otherwise make the validator's
        # Delaunay differ from the solver's — the cm-noise junction class).
        mesh_edges_ll = junction_mesh_edges_ll(layout) or None
        # Same 4-tuple shape check_grade's sidecar loader passes to
        # run_checks: (latlon_pts, seg_caps, None, route_ordinal).
        taxi_axes_ll = [(pts, caps, None, ridx)
                        for (pts, caps, ridx) in axes_exact]
        seam_pins_ll = [[round(la, 7), round(lo, 7)]
                        for (la, lo) in
                        (getattr(layout, "_seam_pin_ll", None) or [])]
        # THE BREAK-REGION QUARANTINE IS DELETED (spec ``docs/specs/
        # kill-half-spec.md`` §2, 2026-08-04): ``run_checks`` no longer
        # takes ``break_nodes_ll`` and no longer splits any pair out of
        # the actionable count.  This test is therefore FULL-CENSUS, which
        # is what docs/RULINGS.md requires ("all counts are full-census,
        # never quarantine-excluded").
        # SPINE CROWN drop field (part 30), exactly like the sidecar: the
        # within-shape law re-centres each pair on the designed crown
        # offset the solver built to (grade_law.crown_pair_offset).
        crown_drops_ll = [[la, lo, c] for (la, lo, c) in
                          (getattr(layout, "_crown_drop_ll", None) or [])]
        # CROWN CENTERLINE nodes (Phase 0 hotfix): the runway ridge vertices
        # the interior cross-edge crown inserted, exempt from the runway
        # within-shape all-pairs plane law (spine-profile governed).
        crown_centerline_ll = [[la, lo] for (la, lo) in
                               (getattr(layout, "_crown_centerline_ll", None)
                                or [])]

        # proximity_m = the solver's weld tolerance (one definition of
        # "same point" everywhere — canonical registry, pre-solve weld,
        # and this check).  Vertices farther apart are INDEPENDENT
        # solver nodes whose relationship the vertex-to-edge/mid-edge
        # step checks govern; a wider radius double-counts that class
        # (the years-old "HECA fails in suite, never standalone"
        # mystery was exactly this: the CLI defaults to 0.5, this call
        # hardcoded 1.0).
        from auto_patch.layout import SHARED_VERTEX_TOL_M
        w, c, s = check_grade.run_checks(
            out,
            max_grade_pct=1.5,
            proximity_m=SHARED_VERTEX_TOL_M,
            edge_search_m=5.0,
            edge_step_m=0.5,
            top_n=5,
            taxi_axes_ll=taxi_axes_ll,
            routes_ll=routes_exact,
            anchor=(tuple(layout.anchor)
                    if layout.anchor is not None else None),
            seam_pins_ll=seam_pins_ll,
            mesh_edges_ll=mesh_edges_ll,
            crown_drops_ll=crown_drops_ll,
            crown_centerline_ll=crown_centerline_ll,
            # WITHIN-SHAPE baked pair caps (2026-07-17): the exact pair
            # selection + metre budgets the final projection enforced,
            # frozen on the layout — same lockstep as the sidecar's
            # ``pair_caps`` (see verification.lockstep_pair_caps_ll).
            pair_caps_ll=getattr(layout, "_lockstep_pair_caps_ll", None),
            # APRON TERRACE JOINTS (owner 2026-08-04): the same declared
            # joints the sidecar carries, from the same builder call, so
            # the law-true suite count and the standalone CLI read one
            # law.  Empty list with the gate off.
            terrace_joints_ll=_terrace_joints_sidecar(layout),
        )
        within += w
        cross += c
        steps += s

    # ── EVERY SECTION IS REPORTED (spec kill-half §4d, 2026-08-04) ──
    # These were three sequential asserts, so the FIRST failing section
    # masked the other two — a drain list that reads "cross-shape: 1" when
    # the same build also has 900 within-shape rows is a measurement
    # instrument that hides its own population.  Each section is now
    # evaluated, collected, and reported together.
    failures = []

    # Cross-shape continuity must be perfect.
    if cross:
        failures.append(
            f"{icao}: {len(cross)} cross-shape proximity violations "
            f"(shared corners disagree on elevation).  Worst: "
            f"{max(v.de_m for v in cross):.2f} m step.")
    # Soft cap on vertex-to-edge + mid-edge steps combined.  Vertex
    # continuity at shared boundaries should be ~perfect; mid-edge
    # discontinuities (sliver triangles whose plane tilts away from
    # neighbouring triangles' surfaces) are the known background.
    # BUILDING↔BUILDING steps are exempt (user 2026-06-20): two adjacent
    # terminal/hangar pads are independent FLAT surfaces and may legitimately
    # sit at different floor levels with a facade/wall between them (SPJC
    # building16 @30.9 abuts building30 @29.5 = a 1.4 m terminal-to-terminal
    # step, correct in X-Plane).  A pad-vs-pavement step is still gated.
    def _both_buildings(s):
        return (s.way_v.tags.get("role") == "building"
                and s.way_e.tags.get("role") == "building")
    steps = [s for s in steps if not _both_buildings(s)]
    step_cap = MID_EDGE_CAP
    if len(steps) > step_cap:
        failures.append(
            f"{icao}: {len(steps)} edge/mid-edge steps > 0.5 m exceeds "
            f"cap {step_cap}.  Worst: {max(s.step_m for s in steps):.2f} "
            f"m step.")
    # Within-shape grade violations indicate an infeasible elevation
    # field; fix the solver / geometry, not the threshold.
    cap = WITHIN_SHAPE_CAP
    if len(within) > cap:
        within.sort(key=lambda v: -v.grade_pct)
        worst = "\n  ".join(
            f"{check_grade._label(v.way_a)} -> "
            f"{check_grade._label(v.way_b)}: {v.grade_pct:.2f}% over "
            f"{v.distance_m:.1f} m ({v.elev_a:.1f} -> {v.elev_b:.1f})"
            for v in within[:5])
        failures.append(
            f"{icao}: {len(within)} within-shape grade/plane "
            f"violations (cap {cap}).  Worst:\n  {worst}")
    if failures:
        pytest.fail(
            f"{icao}: {len(failures)} of 3 law sections over cap "
            f"(cross={len(cross)}, steps={len(steps)}/{step_cap}, "
            f"within={len(within)}/{cap}):\n"
            + "\n".join(failures))


@pytest.mark.xdist_group("CYXY")   # reuse CYXY's already-built layout
# DRAIN LEDGER ITEM CLOSED 2026-08-04 (spec ref-pull-interim §1).  This
# carried ``xfail(strict=True)`` for the CYXY apron pair at (-291,343),
# which graded 1.9 % against a 1.5 % cap — a real ADJUDICATED defect
# exposed by the kill-half §4b defaults flip.  Lowering the reference-rod
# proximal weight (``O4_YIELD_REF_WEIGHT`` 0.2 -> 0.02) restores the
# projection budget the pull was truncating, and the pair grades in
# bounds: the test XPASSed on the very first battery run of the new
# default and again on a targeted re-run.  The strict marker existed
# precisely so this could not "silently start passing", so it is REMOVED
# rather than relaxed — the invariant is now a live guard.
def test_cyxy_spine_zero_no_bowl():
    """THE single-graph invariant (user 2026-06-24): the taxi SPINE must be
    grade-compliant (0 within-shape spine violations on the unified grade graph)
    AND no building bowled — building reach and spine grade come from ONE graph
    (``building_feasibility.reach_band_unified``), so they agree by construction.

    Guards the absorbed-runway-end anchor fix (``_CONNECT_TOL_M`` 20→25): before
    it, the CYXY ~U11/taxiway-A corridor back to the absorbed runway-02 end was
    credited via a far detour anchor and the spine seated a ~3.3% ramp (16 spine
    violations); the dense-graph attempt fixed the spine but bowled building16 to
    ~702 (should be ≥706).  This asserts BOTH halves stay fixed."""
    from auto_patch.grade_graph_validate import within_violations
    from auto_patch.layout import ROLE_BUILDING
    from conftest import cached_airport_layout
    import math

    layout = cached_airport_layout("CYXY")
    assert layout.shapes, "CYXY: no shapes built"

    # (1) SPINE: zero taxi-route within-shape grade violations.
    spine = [v for v in within_violations(layout) if v[4]]
    assert not spine, (
        f"CYXY: {len(spine)} taxi-spine within-grade violation(s) "
        f"(expected 0).  Worst: {spine[0][0]:.1f}% (cap {spine[0][1]:.1f}%) "
        f"{spine[0][3]} @({spine[0][5]:.0f},{spine[0][6]:.0f}).")

    # (2) NO BOWL: building16 / building19 must sit near their route-feasible
    # level, not dragged metres below it.  Identified by centroid (refs renumber
    # when the building set changes).  b16 ~708 (working model) / ~712 (default);
    # the dense-graph bowl drove it to ~702 — the floor below catches that.
    def _emit_level(lat, lon):
        px, py = layout.ll_to_m(lat, lon)
        b = min((s for s in layout.shapes
                 if s.role == ROLE_BUILDING and s.polygon is not None
                 and not s.polygon.is_empty and s.node_altitudes),
                key=lambda s: math.hypot(s.polygon.centroid.x - px,
                                         s.polygon.centroid.y - py))
        na = [v for v in b.node_altitudes if v is not None]
        return sum(na) / len(na)

    b16 = _emit_level(60.707982, -135.075708)
    b19 = _emit_level(60.714189, -135.076256)
    # b16 floor re-pinned 706.0 → 702.5 (production-DEM parity, owner
    # ruling 2026-07-19): the old floor was calibrated on the base-DEM
    # test world (~708 local ground).  The PRODUCTION surface (lidar
    # inset) reads 703.4-704.1 there and production has always emitted
    # b16 at ~702.9 — a normal pad seat, never flagged in-sim.  The
    # floor still guards against genuine future bowling (the dense-graph
    # bowl class would read ~698 on this surface).
    assert b16 >= 702.5, f"CYXY building16 bowled to {b16:.1f} (expected >=702.5)"
    # building19 floor re-pinned 697.7 → 696.4 (production-DEM parity
    # v2, 2026-07-19): a FRESH production rebuild at HEAD
    # (tools/production_airport_patch.py) emits b19 at 696.65 —
    # centimetre-identical to the harness build, so parity holds and
    # the old 697.7 floor was pinned to a STALE production patch
    # (~2026-07-17 code; the in-sim-accepted 697.8).  The level moved
    # 697.8 → 696.65 across the sanctioned 2026-07-18/19 merges (seam
    # blend, connector split, trench v3) in BOTH worlds — flag for the
    # next in-sim pass, but it is not a harness artifact.  The floor
    # still guards the BOWL class (dense-graph bowls read ~metres
    # lower, ~692 on this surface).
    assert b19 >= 696.4, f"CYXY building19 bowled to {b19:.1f} (expected >=696.4)"


def _fmt_rwy(vios) -> str:
    out = []
    for kind, ref, val, cap, ll in vios[:6]:
        if kind == "grade":
            out.append(f"{ref}: {val * 100:.2f}% > {cap * 100:.2f}% @ {ll}")
        else:
            out.append(
                f"{ref}: |Δg|={val:.5f}/m > {cap:.5f}/m @ {ll} (kink)")
    return "\n  ".join(out)


@pytest.mark.parametrize("icao", _GRADE_TEST_AIRPORTS)
def test_runway_longitudinal_grade(icao):
    """The emitted runway centerline profile must not exceed the uniform
    ``RUNWAY_MAX_GRADE`` (1.5%) longitudinal cap anywhere — the binding
    longitudinal limit the runway solver + runway-flex enforce today.  Guards
    against a runway-flex MOVE (or any solver change) pulling a runway steeper
    than 1.5% along its axis.  Reconstructs the profile from the whole-airport
    layout (a runway is continuous; not per-tile).

    ★ Owner ruling 2026-07-26 (``config.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS``):
    "ALL nodes along the seam MUST be at exact DEM and anchored BEFORE the
    solve, then the solver can grade between them and its other anchors to
    maintain grade."  A segment between two tile-seam cut-back nodes is a
    terrain reading, not a solver choice — ``check_runway_profile`` reports
    those separately (see ``test_runway_seam_dem_steps_are_reported``) and
    this assertion covers the profile the solver actually owns."""
    from conftest import cached_airport_layout
    from auto_patch.verification import check_runway_profile

    layout = cached_airport_layout(icao)
    if not any((s.role or "") == "runway" for s in layout.shapes):
        pytest.skip(f"{icao}: no runway shapes")
    vios = check_runway_profile(
        layout, end_grade_cap=None, check_curvature=False)
    assert not vios, (
        f"{icao}: {len(vios)} runway longitudinal-grade violation(s) "
        f"> {1.5:.1f}%.  Worst:\n  {_fmt_rwy(vios)}")


def test_runway_seam_dem_steps_are_reported():
    """★ Owner ruling 2026-07-26: the DEM anchor wins at every seam node and
    the grade the solver must step through between two of them is REPORTED.

    SPLP's RW02/20 crosses the -77 tile line at 18 degrees over terrain that
    rises ~2 m across the contact, so at least one adjacent cut-back pair is
    steeper than the 1.5% runway law.  It must appear in the seam-step report
    (with its grade) and NOT in the profile violations."""
    from conftest import cached_airport_layout
    from auto_patch import config as CFG
    from auto_patch.verification import check_runway_profile

    if not CFG.RUNWAY_SEAM_CUTBACK_DEM_ANCHORS:
        pytest.skip("O4_RUNWAY_SEAM_CUTBACK_DEM=0: pre-ruling behaviour")
    layout = cached_airport_layout("SPLP", tile_lat=-13, tile_lon=-77)
    vios = check_runway_profile(
        layout, end_grade_cap=None, check_curvature=False)
    steps = getattr(layout, "_runway_seam_grade_steps", None)
    assert steps is not None, "the seam-step report must always be published"
    assert steps, (
        "SPLP's oblique seam contact must produce at least one over-cap "
        "seam-DEM step to report")
    for kind, _ref, grade, cap, _ll in steps:
        assert kind == "seam_dem_step"
        assert grade > cap, "only over-cap steps are worth reporting"
    # ...and none of them is counted as a profile violation.
    assert not [v for v in vios if v[0] == "grade"], (
        f"seam-DEM steps leaked into the profile violations: {vios[:3]}")


@pytest.mark.xfail(
    reason="runway vertical-curve smoothing (STATUS item D) not built + the "
           "0.8% end-grade cap is opt-in, so runways emit as plane rects with "
           "sharp kinks at extrema and 1.5% end zones — RED until those land; "
           "flips to XPASS when a runway becomes fully compliant.",
    strict=False)
@pytest.mark.parametrize("icao", _GRADE_TEST_AIRPORTS)
def test_runway_vertical_curve(icao):
    """The emitted runway profile must also obey the EASA 0.8% end-grade cap and
    the FAA vertical-curve rate-of-grade-change limit
    (``RUNWAY_MAX_GRADE_CHANGE_PER_M``).  This is the runway counterpart of the
    taxiway vertical-curve smoothing (STATUS item D): currently RED on every
    airport because plane rects meet at sharp kinks at terrain extrema.  Kept as
    an ``xfail`` tracking target — it turns XPASS per airport as the smoothing /
    end-grade enforcement lands."""
    from conftest import cached_airport_layout
    from auto_patch.verification import check_runway_profile

    layout = cached_airport_layout(icao)
    if not any((s.role or "") == "runway" for s in layout.shapes):
        pytest.skip(f"{icao}: no runway shapes")
    vios = check_runway_profile(layout)
    assert not vios, (
        f"{icao}: {len(vios)} runway end-grade/vertical-curve violation(s).  "
        f"Worst:\n  {_fmt_rwy(vios)}")


def _synthetic_clipped_runway_layout(displace_station=None, displace_dz=0.0):
    """A synthetic single-poly runway ring that reproduces the SPLP failure
    shape, for a pure-geometry unit test of ``check_runway_profile``'s
    edge-aware reconstruction.

    A tilted rectangle (heading 25°, 850 m usable, 45 m wide) with:

    * densification vertices on EVERY edge (~20 m spacing);
    * a normal flat cross-cap at the high end; and
    * an OBLIQUE tile-clipped cap at the low end that spans ~150 m of station
      — LONGER than the runway is wide — with vertices sweeping across the
      centerline (exactly the SPLP 02/20 clipped end).

    Per-vertex altitudes follow a compliant 0.5 % along-axis slope.  When
    ``displace_station`` is given, that plus-rail vertex's altitude is shifted
    by ``displace_dz`` to inject a REAL mid-edge profile defect.  Returned as a
    lightweight layout stand-in (``check_runway_profile`` only needs
    ``shapes`` + the per-shape ``polygon``/``ref``/``role``/``node_altitudes``/
    ``from_single_poly`` fields; ``_ll`` degrades to ``"?,?"`` without
    ``m_to_ll``)."""
    import math
    from types import SimpleNamespace
    from shapely.geometry import Polygon

    theta = math.radians(25.0)
    ux, uy = math.cos(theta), math.sin(theta)
    vx, vy = -uy, ux
    half_w = 22.5
    slope = 0.005           # 0.5 % along-axis — well under the 1.5 % cap
    base = 100.0
    spacing = 20.0
    clip = 150.0            # plus rail starts here (low end clipped off)
    top = 1000.0

    ring = []               # (x, y)
    alt = []                # per-vertex altitude

    def add(station, lateral):
        ring.append((station * ux + lateral * vx, station * uy + lateral * vy))
        z = base + slope * station
        if (displace_station is not None
                and abs(station - displace_station) < 1e-6
                and abs(lateral - half_w) < 1e-6):
            z += displace_dz
        alt.append(z)

    station = clip                       # plus rail, low -> high
    while station < top - 1e-6:
        add(station, +half_w)
        station += spacing
    add(top, +half_w)
    for lateral in (11.0, 0.0, -11.0):   # normal cross-cap (densified)
        add(top, lateral)
    add(top, -half_w)
    station = top - spacing              # minus rail, high -> low
    while station > 1e-6:
        add(station, -half_w)
        station -= spacing
    add(0.0, -half_w)
    add(50.0, -7.5)                      # oblique clipped cap (sweeps center)
    add(100.0, +7.5)

    shape = SimpleNamespace(
        role="runway", ref="09/27", polygon=Polygon(ring),
        node_altitudes=list(alt), altitude=None, from_single_poly=True)
    return SimpleNamespace(shapes=[shape])


def test_runway_profile_edge_aware_oblique_clip():
    """The edge-aware single-poly reconstruction must (a) NOT fabricate a
    phantom violation from an oblique tile-clipped end-cap (the cap edges are
    excluded from the longitudinal profile), yet (b) still catch a REAL
    mid-edge profile defect — edge-awareness must not blind the checker.

    Pure geometry, no build required (guards the reconstruction itself)."""
    from auto_patch.verification import check_runway_profile

    compliant = check_runway_profile(
        _synthetic_clipped_runway_layout(),
        end_grade_cap=None, check_curvature=False)
    assert not compliant, (
        f"synthetic compliant runway: {len(compliant)} phantom violation(s) "
        f"(oblique clipped cap must be excluded): {compliant}")

    defect = check_runway_profile(
        _synthetic_clipped_runway_layout(
            displace_station=510.0, displace_dz=0.5),
        end_grade_cap=None, check_curvature=False)
    assert any(kind == "grade" for kind, *_ in defect), (
        "synthetic +0.5 m mid-edge displacement not flagged — edge-awareness "
        f"must still catch real profile defects (got {defect})")
