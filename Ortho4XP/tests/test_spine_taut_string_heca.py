"""HECA taut-string corridor regression (spec §8.2).

``docs/specs/taut-string-spine-profile-spec.md`` §1 measured a ~3.6 m V-dip
on the taxi corridor between (30.1105599, 31.4087103) and
(30.1137307, 31.4129164) — a corridor whose reach-band ceiling sits 6+ m
ABOVE the solved profile and whose end-to-end straight chord is feasible at
every node.  The dip is therefore not law-forced: it is the harmonic /
POCS objective having no altitude preference, plus interior seat pins
turning the sag into a V.  This module is the acceptance gate for the
taut-string profile (spec §8.2 / §9 task D).

WHY THIS MEASURES THE EMITTED PATCH (audit finding, do not "simplify")
---------------------------------------------------------------------
The §7 audit proved the ``O4_DUMP_SOLVE_STATE`` snapshot is taken BEFORE
the dominant drag wave (the movable-pads / free-seats yield projection at
``route_profile/solve.py`` ~:1095 pulls the corridor a further −7.9 m and
frees a 106.48 seat pin to 98.60), and before ``final_grade_projection``
re-solves in a REBUILT node space with no spine concept.  A dump-based
assertion would PASS while the surface X-Plane renders still dips.  So
this test reads the **emitted patch**: it writes ``layout.to_osm(...)``
into ``tmp_path`` and parses the per-vertex altitudes back out — the same
bytes Ortho4XP bakes into the mesh.

HOW PER-VERTEX ALTITUDE IS EMITTED (parsing notes)
--------------------------------------------------
``layout.to_osm`` does NOT use one uniform encoding; a corridor mixes all
three of these, so the patch must be decoded, never regex-scraped:

* per-node ``<tag k='alt_abs' v='...'/>`` children — the current
  per-vertex form, and the one that OVERRIDES the way-level value;
* a way-level ``node_altitudes='z0,z1,...'`` tag (legacy per-vertex form,
  one value per closed-ring nid);
* ``altitude_high`` / ``altitude_low`` on a 5-nid sloped rect (X-Plane's
  complex-way form: nids ``[hi, lo, lo, hi, hi]``) — most taxi rects on
  this corridor are emitted this way, so a naive ``altitude``-only reader
  sees NOTHING here;
* plain ``altitude`` for flat shapes.

``tools/check_grade.py`` already owns that decode
(``_parse_osm`` + ``_derive_per_vertex_elevations``) and is already
imported from ``tests/`` by ``test_pavement_grade.py``, so it is reused
verbatim rather than reimplemented.  Its ``_ll_to_m_factory(nodes,
anchor=layout.anchor)`` is likewise reused so the corridor projection is
the BUILDER's frame (``auto_patch.layout._projection``) to float
precision, not an independent equirectangular guess.

MEASURED SHAPE OF THIS CORRIDOR (2026-07-28 emitted HECA patch)
---------------------------------------------------------------
Two facts the selection depends on, both verified against the emitted
patch rather than assumed:

* **The whole corridor emits with ``role='junction'``** — 98 of the 117
  band vertices; the rest are ``apron`` (16) and ``graded_strip`` (3).
  There is not one ``primary_parallel`` / ``stub`` / ``cross_connector``
  rect in the band: HECA's terminal-area taxi network is junction-filled
  here.  Drop ``junction`` from ``CORRIDOR_ROLES`` and this test measures
  NOTHING, which is exactly what guard (c) exists to catch.
* **The emitted patch has no "spine node" concept**, so a 25 m
  perpendicular band is NOT the emitted equivalent of the audit's 56
  solver spine nodes.  The emitted spine is a **centerline chain at
  perpendicular offset |d| < 1 m**, ~46 m apart (the 60 m emit-decimation
  chord rule).  The 25 m band around it additionally contains (i) the
  rails, ~25 m out and 1.0-1.3 m below the crown BY DESIGN where a
  junction fan slopes off toward the neighbouring apron, and (ii) at the
  P1 mouth a junction vertex 6-7 m below its own polygon's neighbours
  (way -12037 / graded_strip -13278 at 30.1102807, 31.4087303 — 31 m from
  the P1-P2 segment, admitted only because the selection rectangle's
  corner reaches further than its sides).  Measuring "how far is this
  vertex below the corridor chord" over the whole band therefore reports
  designed cross-slope and an unrelated lateral cliff as corridor sag: it
  flagged 6 vertices with a 6.47 m "worst sag" on a corridor whose spine
  was in fact straight to 0.24 m.
  **So the profile law (a)+(b) is measured on the centerline chain**, the
  emitted object the spec's longitudinal profile actually governs, and
  the 25 m band is kept for the selection guard (c).  Verified
  discriminating, same code, two emitted HECA patches an hour apart:
  pre-fix 11 of 21 centerline vertices deep, worst sag **3.08 m**, with
  three −1.81 / −1.83 / −1.85 % dip walls between s=163 and s=279;
  post-fix worst sag **0.24 m**, worst station grade 1.22 %, zero
  over-cap stations.

Crown note: emitted spine centerline vertices are crown-LIFTED relative
to the projection space (see ``crown.py`` and the crown-z′ memory).  Both
the chord's end values and the profile being tested come from the SAME
crown-lifted chain, so the crown cancels out of the comparison.

Cost / opt-in: gated on ``HECA`` appearing in ``O4_TEST_AIRPORTS`` (the
suite-wide convention, ``conftest.airports_under_test``), so the default
suite pays ZERO for it.  When selected it reuses the session-cached HECA
layout (``conftest.cached_airport_layout``) that the HECA grade tests
already build, pinned to the same xdist worker via ``xdist_group("HECA")``
— so it adds no second build.  No pipeline cost whatsoever (test-only).

Run it with::

    O4_TEST_AIRPORTS=HECA venv/bin/python -m pytest \\
        tests/test_spine_taut_string_heca.py -q -n0
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

from conftest import airports_under_test

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def _xplane_root() -> str:
    return os.environ.get("XPLANE_ROOT", "/Users/noah/X-Plane 12")


def _xplane_available() -> bool:
    root = Path(_xplane_root())
    return root.is_dir() and (root / "Custom Data" / "CIFP").is_dir()


pytestmark = [
    pytest.mark.skipif(
        not _xplane_available(),
        reason="X-Plane install not found (set XPLANE_ROOT to override)"),
    pytest.mark.skipif(
        "HECA" not in set(airports_under_test()),
        reason="airport-scale opt-in test: set O4_TEST_AIRPORTS=HECA"),
]

# ── The diagnosed corridor (spec §1) ──────────────────────────────
P1 = (30.1105599, 31.4087103)
P2 = (30.1137307, 31.4129164)

#: Half-width of the corridor selection band, metres.  Wide enough to take
#: both rails of a code-E taxi rect plus its junction fill, narrow enough to
#: exclude the parallel taxiway and the aprons either side.
CORRIDOR_HALF_WIDTH_M = 25.0
#: Allowed overshoot past each endpoint along the P1→P2 axis.
CORRIDOR_OVERSHOOT_M = 30.0
#: Window at each end whose mean altitude defines the corridor END VALUE
#: the taut-string chord is drawn between.
END_WINDOW_M = 30.0
#: Perpendicular band that isolates the emitted spine CENTERLINE chain
#: (measured |d| < 1 m) from the rails and junction-fan vertices (nearest
#: 3.7 m, rails ~25 m).  The profile assertions run on this chain — see
#: the module docstring for why the full 25 m band cannot carry them.
CENTERLINE_BAND_M = 2.0
#: Slack on the corridor's own endpoints for the grade walk: the emitted
#: P2 spine node lands 0.008 m past the computed chord length, and losing
#: the corridor's last station to a rounding sliver would be silly.
ENDPOINT_TOL_M = 2.0
#: Station bucket for the grade walk.  Averaging a bucket suppresses the
#: residual spread where the mouth junctions emit two centerline vertices
#: within a metre of each other.
STATION_M = 5.0

#: Spec §8.2: no interior node more than 0.5 m BELOW the end-to-end chord.
MAX_SAG_M = 0.5
#: 1.5 % taxi cap (``config.ROLE_GRADE_LIMITS``) + emit-quantisation slack.
MAX_GRADE_PCT = 1.6

#: Airside taxi-like roles only.  ``apron`` is out (phase-B body fill, spec
#: §3 OUT list) and boundary / clearance / groundside / graded_strip /
#: service shapes trace terrain by design and carry no taxi grade rule at
#: all (``config.ROLE_GRADE_LIMITS`` maps several of them to ``None``).
#: ``junction`` is IN and is not optional here: the junction polygons ARE
#: this corridor's emitted surface, and the spine profile governs them
#: (see the measured note in the module docstring).
CORRIDOR_ROLES = frozenset({
    "primary_parallel",
    "secondary_parallel",
    "stub",
    "cross_connector",
    "taxiway",
    "junction",
})


def _corridor_frame(ll_to_m):
    """Return ``(origin, unit_along, length)`` for the P1→P2 axis in the
    builder's local-metre frame."""
    ax, ay = ll_to_m(*P1)
    bx, by = ll_to_m(*P2)
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    assert length > 1.0, "degenerate corridor definition"
    return (ax, ay), (dx / length, dy / length), length


def _collect_corridor_vertices(osm_path: Path, anchor):
    """Emitted corridor vertices as
    ``[(s, d, lat, lon, alt, role, ref), …]`` ordered by arclength ``s``
    along P1→P2 (``d`` = signed perpendicular offset).

    Returns ``(vertices, chord_length_m)``.
    """
    import check_grade

    nodes, ways = check_grade._parse_osm(osm_path)
    ll_to_m = check_grade._ll_to_m_factory(nodes, anchor=anchor)
    (ox, oy), (ux, uy), chord_len = _corridor_frame(ll_to_m)

    out = []
    seen = set()
    for w in ways:
        if w.role not in CORRIDOR_ROLES:
            continue
        ring = w.nids
        # Skip the closing repeat so a shared corner is not double-counted.
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]
        for k, nid in enumerate(ring):
            if nid not in nodes:
                continue
            alt = w.elevs[k] if k < len(w.elevs) else None
            if alt is None:
                continue
            lat, lon = nodes[nid]
            x, y = ll_to_m(lat, lon)
            rx, ry = x - ox, y - oy
            s = rx * ux + ry * uy
            d = -rx * uy + ry * ux
            if abs(d) > CORRIDOR_HALF_WIDTH_M:
                continue
            if not (-CORRIDOR_OVERSHOOT_M <= s
                    <= chord_len + CORRIDOR_OVERSHOOT_M):
                continue
            # One entry per emitted node id + altitude claim: the same OSM
            # node is referenced by every shape sharing that corner.
            key = (nid, round(float(alt), 3))
            if key in seen:
                continue
            seen.add(key)
            out.append((s, d, lat, lon, float(alt), w.role, w.ref))
    out.sort(key=lambda v: v[0])
    return out, chord_len


def _centerline_profile(verts):
    """The emitted spine chain: band vertices with ``|d| <= 2 m``, in ``s``
    order.  This is the longitudinal profile the spec's law governs."""
    return [v for v in verts if abs(v[1]) <= CENTERLINE_BAND_M]


def _end_value(profile, *, at_start: bool) -> float:
    """Mean altitude over the first (or last) ``END_WINDOW_M`` of the
    profile — the corridor END VALUE the taut string is pinned to."""
    s0, s1 = profile[0][0], profile[-1][0]
    if at_start:
        window = [v for v in profile if v[0] <= s0 + END_WINDOW_M]
    else:
        window = [v for v in profile if v[0] >= s1 - END_WINDOW_M]
    assert window, "empty corridor end window"
    return sum(v[4] for v in window) / len(window)


def _stations(profile, chord_len: float):
    """Mean ``(s, alt)`` per ``STATION_M`` bucket over the corridor proper,
    endpoints included (spec §8.2 grades the corridor, not the junction
    fans out in the endpoint overshoot), ordered by ``s``."""
    lo = -ENDPOINT_TOL_M
    hi = chord_len + ENDPOINT_TOL_M
    core = [v for v in profile if lo <= v[0] <= hi]
    if not core:
        return []
    s0 = core[0][0]
    buckets: dict = {}
    for v in core:
        buckets.setdefault(int((v[0] - s0) // STATION_M), []).append(
            (v[0], v[4]))
    return [
        (sum(p[0] for p in vals) / len(vals),
         sum(p[1] for p in vals) / len(vals))
        for _b, vals in sorted(buckets.items())
    ]


@pytest.mark.xdist_group("HECA")   # reuse HECA's already-built layout
def test_heca_corridor_taut_string_profile(tmp_path):
    """The emitted HECA corridor must hang like a taut string.

    (a) no emitted centerline vertex more than 0.5 m BELOW the chord drawn
        between the corridor's two end values (spec §8.2 — the V-dip
        class);
    (b) no over-cap longitudinal grade between consecutive 5 m stations;
    (c) the selection itself is non-empty and spans the real corridor, so
        the test can never pass by measuring nothing.
    """
    from conftest import cached_airport_layout

    # Same cache key the HECA grade tests use → exactly one build per run.
    layout = cached_airport_layout("HECA")
    assert layout.shapes, "HECA: no shapes built"

    # EMITTED surface: post final_grade_projection, as written to the patch.
    out = tmp_path / "HECA_corridor.osm"
    layout.to_osm(str(out))

    anchor = (tuple(layout.anchor) if layout.anchor is not None else None)
    verts, chord_len = _collect_corridor_vertices(out, anchor)

    # ── (c) selection sanity — must run BEFORE the real assertions ──
    assert len(verts) >= 20, (
        f"HECA corridor selection collapsed: only {len(verts)} emitted "
        f"vertices with altitudes within {CORRIDOR_HALF_WIDTH_M:.0f} m of "
        f"the P1-P2 line (roles {sorted(CORRIDOR_ROLES)}).  The test cannot "
        f"prove anything about a corridor it did not find — check the role "
        f"vocabulary and the emitted altitude encoding, not the threshold.")
    profile = _centerline_profile(verts)
    assert len(profile) >= 10, (
        f"only {len(profile)} of {len(verts)} band vertices lie on the "
        f"centerline (|d| <= {CENTERLINE_BAND_M:.0f} m) — the emitted spine "
        f"chain was not found, so both profile assertions would be vacuous.")
    span = profile[-1][0] - profile[0][0]
    assert 450.0 <= span <= 620.0, (
        f"HECA corridor span {span:.1f} m outside [450, 620] "
        f"(P1-P2 chord {chord_len:.1f} m) — the selection is not the "
        f"diagnosed corridor.")
    stations = _stations(profile, chord_len)
    assert len(stations) >= 10, (
        f"only {len(stations)} station bucket(s) on the centerline chain "
        f"— too sparse to walk a profile; the grade half of this test "
        f"would be vacuous.")

    z_start = _end_value(profile, at_start=True)
    z_end = _end_value(profile, at_start=False)
    s0, s1 = profile[0][0], profile[-1][0]

    def chord_z(s: float) -> float:
        return z_start + (z_end - z_start) * (s - s0) / (s1 - s0)

    # ── (a) sag against the end-to-end chord ───────────────────────
    worst = max(profile, key=lambda v: chord_z(v[0]) - v[4])
    worst_sag = chord_z(worst[0]) - worst[4]
    deep = [v for v in profile if chord_z(v[0]) - v[4] > MAX_SAG_M]
    assert not deep, (
        f"HECA corridor sags below the taut-string chord: {len(deep)} of "
        f"{len(profile)} emitted centerline vertices more than "
        f"{MAX_SAG_M:.2f} m below the chord {z_start:.2f} m -> "
        f"{z_end:.2f} m over {span:.1f} m.\n"
        f"  worst: s={worst[0]:.1f} m (lat {worst[2]:.7f}, lon "
        f"{worst[3]:.7f}) alt={worst[4]:.2f} m, "
        f"chord={chord_z(worst[0]):.2f} m, sag={worst_sag:.2f} m "
        f"[role={worst[5]!r} ref={worst[6]!r} d={worst[1]:+.1f} m]")

    # ── (b) longitudinal grade along the station profile ───────────
    over = []
    for (sa, za), (sb, zb) in zip(stations, stations[1:]):
        ds = sb - sa
        if ds < 1e-6:
            continue
        pct = abs(zb - za) / ds * 100.0
        if pct > MAX_GRADE_PCT:
            over.append((pct, sa, sb, za, zb))
    over.sort(reverse=True)
    assert not over, (
        f"HECA corridor has {len(over)} consecutive-station grade(s) over "
        f"{MAX_GRADE_PCT:.1f}% (cap 1.5% + emit slack).  Worst:\n  "
        + "\n  ".join(
            f"{pct:.2f}% between s={sa:.1f} and s={sb:.1f} m "
            f"({za:.2f} -> {zb:.2f} m)"
            for pct, sa, sb, za, zb in over[:5]))
