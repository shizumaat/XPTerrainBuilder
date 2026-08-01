# The reach envelope uses THE graph — not a pavement-pair closure

Owner ruling 2026-07-30: "Feasibility and reach must only follow actual
taxi route centerlines… We already have the graph, use it, don't
duplicate it.  Why would we need to rebuild the envelope on the
centerline graph, can't we just use the centerline graph?"

This is the 2026-06-27 ruling ("stop building the same thing in
different ways") applied to the one component that never got it.

## 1. Defect

`one_solve.feasibility_project` decides which nodes are infeasible by
transitive closure over the within-shape pavement PAIR graph
(`edge_lim` / `joint_edges`), seeded from **every hard node**.  That
answers a reach-shaped question with pavement adjacency:

* its argmin "binding path" is 119 nodes / 5,349 m with a role mix of
  junction 61, apron 49, service_junction 6, building 1 — pavement
  vertices, not route segments.  The owner, shown two KML renderings:
  "Neither represents any sort of route an aircraft could take."
* it crosses 14 rigid-flat building pads (3,461 m of span) at ZERO
  budget, because a pad collapses to one node (48 zero-budget edges
  airport-wide, up to 617 m, 12,073 m total).
* it constrains exactly the points `grade_law.
  building_requires_full_frontage` declares NOT runway-reach-
  constrained ("its non-central frontage and the apron stepping up to
  it grade FROM the pad, not from the runway route").

Meanwhile `building_feasibility.reach_band_unified` — route-metric,
service-excluded, seeded from `G.runway_anchor`, already consumed by
`build_building_seats` and `route_band_violations` — is the graph the
owner's law means.

## 2. Measured (replay, one patch-neutral HECA build 2026-07-30)

Sourcing the break declaration from the existing band:

| pass | broken now | band-sourced | break pairs now → band |
|---|---|---|---|
| fp#8 | 13,428 | **0** | 111,888 → 0 |
| final #1 | 9,991 | **0** | 69,804 → 0 |
| final #2 | 7,634 | **0** | 59,941 → 0 |

Zero band inversions at HECA; zero nodes newly broken.  The owner's two
runway anchors compose **≥ 48.886 m** on the centerline route (exact
bound from `ceil_B ≤ z_A + budget(A,B)`) against **48.120 m** needed —
FEASIBLE — where the pair closure composes 20.892 m.

Attribution: the band seeds `G.runway_anchor` only; the closure seeds
every hard node, so `gs_pin` (on one side of 90.3 % of breaks),
`pad_detached_dem` and terrain pins can all declare airside infeasible.
They are not band anchors, so most of the quarantine cannot exist on
the centerline graph by construction.

Corroboration that today's behaviour is already wrong against the band
it claims to honour: **11,109 band-feasible fp#8 nodes emit BELOW their
band floor and 2,907 ABOVE their band ceiling** (final #2: 338 / 4,321).

## 3. Semantics (fixed)

**Feasibility is read from THE graph.**  A node's `[floor, ceiling]`
comes from `reach_band_unified` — no second closure, no new structure,
no re-derivation (`single-pass-principle`).  A node is BROKEN only
where the band inverts (`floor > ceiling`).

**Off-net ⇒ NOT broken.**  Where the band has no value (32.9 % of
non-hard nodes at fp#8, but only 372 of the currently broken), the
local within-shape law governs — the tree's own documented contract in
`reach_band_unified`, `one_profile_solve.node_band` and
`route_band_violations`.  Measured: the opposite default triples the
quarantine (42,008 nodes).

**★ The clamp moves with the declaration.**  `one_solve.py:1780`'s
non-broken branch is `elev[i] = min(max(elev[i], lo), hi)` using the
SAME closure interval; for the 13,056 nodes the band frees that
interval is still empty and the clamp collapses to `hi`, pinning them
anyway.  Break declaration AND clamp must be re-sourced in one edit —
"change only what declares a break" is NOT isolable.

**Unchanged — this is a bound on FEASIBILITY, not on the surface
law.**  Every pair constraint still enforces in the sweeps and in the
final RAW-budget tally (`one_solve.py:2561-2583` never reads `broken`).
Local apron 1 % / taxi 1.5 % / visible-geodesic behaviour is untouched.
What changes is which nodes are frozen and what value is written there.

## 4. Scope

`one_solve.py` (envelope source, clamp source, off-net default) and
whatever thin plumbing hands the band in from `solve.py`.  Do NOT touch
`grade_graph.py`, `pavement_scoring.py`, the terracing/crown work, or
Track 1's reference machinery.  Gate `O4_ENVELOPE_FROM_BAND`, default
ON, gate-off byte-identity proven.

## 5. Acceptance

Measured on the EMITTED patch, law-true frame.  **Nothing here is
predicted** — the replay measured the break declaration only; the
emitted surface is unmeasured (`mechanism-before-fix`).

* Report broken nodes, break pairs, within-shape, mid-edge and
  vertex-to-edge steps, strip tears, spine kinks — HECA and all three
  flat fixtures, gate OFF vs ON.
* HECA seam site stays in the 106-109 class; building199 weld ≤ 0.2 m
  at the ≤0.6 m weld tolerance (NOT a 5 m probe radius — that
  conflates a break blend with a weld).
* Flat fixtures: step and tear sections stay ZERO.
* `test_single_graph_acceptance` 4/4; report `test_pavement_grade` and
  `test_spine_taut_string_heca` on merit.
* If the emitted surface gets WORSE, report it plainly with
  attribution — do not tune to hide it.
* Mandatory build-time statement (`check_build_time --run --runs 3`).
  Note the accumulated stack already owes one.

## 6. Constraints

Main tree `/Users/noah/XPTerrainBuilder/Ortho4XP`, `venv/bin/python`
from that cwd; `git log --oneline -1 && git status --short` before AND
after every measurement; never commit/stash/revert; no KCLT; one
airport build per process; output to files, never pipes;
PID/artifact-verified waits with timeout arms.  Hash patch BODIES
(`tail -n +3`) — the `o4_provenance_built` header defeats whole-file
hashing; never baseline a session's FIRST build; prove gate identity
with a copied `src/` tree (`/tmp/gsw/build_alt_src.py`,
`/tmp/pathtrace2/base.bodyhash`), never by mutating the shared tree.
Replay dumps and scripts: `/tmp/bandq/`.  STATUS/memory documentation
stays with the parent session.
