# Bounded Yield + Reference Rods — yields stay in the box AND cost
# displacement from their reference

Owner rulings 2026-07-29 (burial-triage session):

1. **"Any yield absolutely needs to stay within the feasibility box."**
2. **Reference-rod model** (same day, follow-up): *"the seats should
   definitely be the target rod for the buildings, and then the next
   priority the rod is pulling toward is essentially straight line
   between the buildings and the anchors: tile seams, runway
   crossings, and CIFP runway thresholds, flexed to be within grade
   cap and feasibility band."*

§2-§6 implement ruling 1 (the clamp).  §7 implements ruling 2 (the
reference term) — the clamp alone is measured insufficient when the
band box is wide: the projection's alternating cap sweeps have no
displacement cost, so healthy in-box nodes drift with the correction
waves (building199: seated 101.13, feasible against a 117 ceiling,
parked at 87.94; path-dependent drift accumulates across the four fp
passes because each re-anchors to the previous wave's drifted state).

## 1. Problem (measured 2026-07-29, HECA)

The movable-pads yield (fp#8, `route_profile/solve.py` ~1040-1090)
frees building pads (as rigid flat groups) and apron seats from the
hard set, then projects the joint system with **no bounds and no
altitude preference**. Two measured failure modes:

* **Unbounded drag** (pads movable, the default): building199 —
  seated flat at 101.13 m by the reach band, local DEM 103-105 —
  was parked at **87.94 m** by the projection, dragging the welded
  south-terminal fabric to ~86 (owner seam site 30.11211,31.40562:
  86.88 emitted vs ~106 healthy). The old chord-metric pair web made
  this drag *lawful*; the spine-frame pair law (landed same day)
  fixed the web's ceiling (91 → 117 at the seam), but the projection
  still has nothing holding a freed seat near its seat.
* **Blunt hard-hold** (`O4_YIELD_MOVABLE_PADS=0`): recovers the seam
  (100.35) but pushes the genuine conflicts into everything that can
  still move: 9 runway longitudinal-grade violations (05C/23C 63 %,
  22.8 % at 30.1034,31.4027), 135 edge/mid-edge steps (cap 0, worst
  4.14 m), corridor sag 2.54 m. The yield exists for real reasons —
  its all-or-nothing form is what is wrong.

## 2. The law

Every value the solver releases from the hard set retains its
**feasibility box** — the reach-band interval computed when it was
seated — as a hard clamp:

* A **pad flat group** may translate only within the intersection of
  its member seats' boxes (the `[lo, hi]` its seat was chosen from,
  `anchors.build_building_seats` — the `pads` list already carries
  `(shape, ring, target_level, lo, hi)`).
* A **freed non-pad seat** (the `O4_YIELD_FREE_APRON_SEATS` set:
  nobuild-apron tilt seats, contact seats, seat nodes off any pad
  ring) clamps to its own band interval at its coordinate
  (`band(x, y)`, de-crowned frame — the same lookup that seated it).
* A node with **no box** (band unreachable / never seated) keeps
  today's behavior — the clamp is a refinement of the yield, not a
  new hold.
* Seam pins, runway nodes, and every other hard-set member are
  untouched (they never yield at all).

Conflicts that exceed a box now surface as remaining over-cap edges /
solver-declared break regions — the existing quarantine machinery —
instead of being resolved by burying seated structures.

## 3. Design

1. **Persist the boxes.** `build_building_seats` returns (or stashes
   on the layout, keyed by canonical node index) each seat's
   `(lo, hi)` alongside the level it already returns. Non-pad seats:
   evaluate `band(x, y)` at seat time and stash the interval the same
   way. One source: whatever seated the node also records its box.
   (`layout._seat_boxes: dict[node_idx, (lo, hi)]` or equivalent.)
2. **Clamp inside the projection.** `one_solve.feasibility_project`
   gains optional bounds:
   * `group_bounds`: per flat group `(lo, hi)` — the group's level
     update clamps to the interval (intersection of member boxes,
     computed at the call site).
   * `node_bounds`: per freed node `(lo, hi)` — per-node update
     clamps after each sweep step.
   Bounds default to `None` (today's behavior, byte-identical).
3. **Call site (fp#8).** Build `group_bounds` from the pad groups'
   member boxes and `node_bounds` for the freed seat set; pass them.
   Gate: `O4_BOUNDED_YIELD` default **ON**; `0` restores the current
   unbounded yield byte-identically (A/B lever).
4. **Out of scope** (companion items, do not implement here): the
   taut-string rod's canonical-key carry (~47 % at HECA — dropped
   keys let the corridor sag independent of seats); the KCLT OOM.

## 4. Validation order (cheap first)

1. **Offline replay (~1 s, no build):** the probe kit
   (`tools/probes_heca_burial_20260729/`) has
   `heca_spineframe_state.pkl` — a pre-fp#8 dump from the
   spine-frame-law tree. `rod_attribution.py --fp8` runs fp#8 offline;
   extend it (or copy it) to pass the new bounds (the dump carries
   `node_band` per node) and confirm the corridor/seam profile holds
   near the seats instead of sinking. The burial reproduces offline;
   so must the fix.
2. **Unit:** scoring/grade suites (`-k "grade_graph or grade_law or
   taut or pavement_scoring"`) stay green; add a
   `feasibility_project` bounds unit test (group clamps at box edge;
   `None` bounds byte-identical).
3. **Full builds** (main tree `Ortho4XP/` cwd — worktrees silently
   no-op; one build per process; wall times are contention-noisy,
   counts are not):
   `venv/bin/python tools/full_airport_build.py <ICAO> <suffix>`.

## 5. Acceptance

Measured on the **emitted patch** (never the dump — it precedes fp#8):

* HECA seam site (30.11211,31.40562 / 30.11195,31.40578): emitted
  values in the seat-lawful class (~100-106; seats around it sit at
  101.1-108.6; was 86.88). `seam_site_probe.py` on the emitted OSM.
* `O4_TEST_AIRPORTS=HECA venv/bin/python -m pytest
  tests/test_spine_taut_string_heca.py tests/test_pavement_grade.py
  -k HECA -n0 -s` — the edge-step cap-0 assertion and the runway
  longitudinal-grade assertion must not regress vs the DEFAULT-tree
  baseline (measure both arms same-tree; the blunt-hold arm's 63 %
  runway kinks are the anti-goal). Corridor sag: target ≤ 0.5 m
  below-chord class; if residual sag traces to rod-key carry, report
  it against the companion item rather than forcing it here.
* Flat fixtures unchanged-or-better vs the post-spine-frame-law
  values (within-shape law-true: CYXY 2, SPJC 9, SPLP 0 + break 24;
  no new step/tear classes; the SPJC 1.9 m strip-tear pair at #728
  ideally disappears as it did under the blunt hold).
* `O4_BOUNDED_YIELD=0` is byte-identical to today's default tree
  (hash the emitted OSM).

## 7. Reference rods (ruling 2 — the displacement term)

The yield solves **"minimum total displacement from the reference
field, subject to the caps and the boxes"** — not "any feasible
point."  Mechanically: every freed node carries a reference value
`z_ref`; each projection sweep adds a proximal pull of the node toward
`z_ref` (weight small vs the cap projections, so the law always wins
locally), and convergence means nodes with no binding conflict return
to `z_ref` exactly while conflicted nodes settle at the least
displacement the law permits, never leaving their box.  This is the
taut-string model generalized off the spine.

The reference field, by priority:

1. **Anchors (immovable, never yield — unchanged):** tile-seam pins,
   runway geometry/crossings and spine↔runway joins, CIFP runway
   thresholds.  These are the string endpoints.
2. **Building pads: `z_ref` = the seat** (`build_building_seats`
   level).  The seat *is* the rod for the pad.
3. **Fabric between buildings and anchors — and between ADJACENT
   buildings (terminal rows):** `z_ref` = the taut string between the
   flanking references (straight chord, DRAPED over terrain the way
   the existing spine taut-string lifts over its floor — a chord must
   never tunnel through rising ground), flexed only as the caps and
   boxes demand.
4. **Service corridors:** `z_ref` = their authoritative DEM-followed
   shape (`apply_service_road_dem_follow` output, snapshotted at
   yield entry exactly like the §10 rod Δ — the phase-A-end snapshot
   minted 8.95 % service mints at CYXY; do not repeat).
5. **Groundside:** unchanged (DEM-following, solve-independent;
   terraces at pad↔groundside boundaries stay lawful).

**Two flexes — only the first is ever free (owner clarification
2026-07-29, closing the dip loophole):**

* Flex in CONSTRUCTING the string: the chord is bent exactly as much
  as caps, terrain floors, and the band demand — deterministic,
  minimal, computed once.  This is "flexed to be within grade cap and
  feasibility band."
* Flex of the solved surface AWAY from the string: never free.
  Spine corridors already make it a hard interval law (the §10 rod,
  ±ε = 2 cm — the mechanism that killed the round-7 dip class); pads
  and fabric make it cost displacement (§7 proximal term).  "Within
  the caps" is NOT a licence to wander — cap-lawful sag below the
  string (the round-7 dip: 6.3 m under the ceiling at lawful wall
  grades) is exactly the answer this model forbids.  The surface
  leaves its string only where a binding constraint forces it, by the
  minimum amount, inside the box.

Conflict semantics: when caps + boxes cannot reconcile a region even
at minimum displacement, the conflict surfaces as the existing
break-region quarantine — it must NOT resolve by burying a seated
structure (the free-seats failure) nor by landing on a runway (the
hard-seats failure: 05C 63 %).

Bookkeeping constraints (measured traps): references live in the same
crown-lifted z′ space as the solver values (`crown_pair_offset` /
`_crown_of` — comparing spaces has faked measurements); and the §10
rod's canonical-key carry (~47 % at HECA — dropped position-bucket
keys after weld moves) must be raised so spine strings survive into
the rebuilt final-projection space — that carry loss is the measured
cause of the 2.54 m corridor sag and is IN SCOPE for this spec as the
spine instance of the same reference machinery.

Phasing: land §2-§6 (clamp) first — it is independently correct and
already implemented; §7 builds on it.  Validation order for §7 is the
same cheap-first ladder (§4): offline replay against
`heca_spineframe_state.pkl` with the reference term active must hold
the corridor/seam near the seats BEFORE any full build.

## 8. Files

* `src/auto_patch/elevation_per_surface/route_profile/anchors.py` —
  box persistence (`build_building_seats`, non-pad seat sites).
* `src/auto_patch/elevation_per_surface/route_profile/solve.py` —
  fp#8 call site (~1040-1090).
* `src/auto_patch/elevation_per_surface/route_profile/one_solve.py`
  — `feasibility_project` bounds.
* `tools/probes_heca_burial_20260729/` — offline validation.
* Context: STATUS.md 20260729 burial-triage block (full measurement
  trail); memory `heca-burial-composed-apron-law`.
