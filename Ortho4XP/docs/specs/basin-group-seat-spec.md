# Basin group seat — rigid facility-group seating for shared-datum packs

**Status:** APPROVED (owner 2026-08-26: "spec and implement the follow-up
dockets"). Fable-authored. Docket B of the basin-region round; amends
`docs/specs/basin-rim-flush-seating-spec.md` §2.2/§item-6 and builds on
`basin-region-footprint-spec.md` + `basin-region-founding-spec.md`.
Reconnaissance basis: the 2026-08-26 recon report (facts cited inline as
R§n / trap Tn; file:line refs verified there).

## 1. Problem — the authored relationships are being torn today

LEMD T4S: 203 placements / 184 resources drape on ONE datum (a second
datum of 98 sits 6.2 m away). In the pack's world all of them sit on a
flat mesh, so every authored inter-object vertical relationship is
carried by the shared drape. On our sloping mesh the machinery today
splits that family across at least five fates (R§2, T5): one member
seated by the `basin_rim_flush` law at anchor ground 595.97, its
neighbours generically cluster-seated at anchor ground 597.52 (**1.544 m
two-instrument gap at one identical point**, T7), four structures
A3-skipped, ~19 placements I-4-skipped, 78 resources never baked — and a
recorded **8.95 m cut seam between clusters inside structure idx 0**, the
very complex whose below-grade decks must stay −2/−3/−7 relative to the
terminal. The relationship the owner ruled must survive is destroyed
before any trench question arises.

The codebase already contains the correct shape: R12-2's bridge seat —
"ONE BRIDGE, ONE RIGID SEAT … neither the per-structure grounds nor the
per-member anchor grounds enter the arithmetic — which is precisely why
the family cannot tear across either of them" (`post_mesh.py:2354-2368`).
This spec is that law for basin facilities.

## 2. Design

### 2.1 Facility identity: one connected body = one facility (grouping fix)

`basin_rim_flush_facilities` today groups records by
`(terrain_feature, anchor×1e5, anchor×1e5)` (`object_terrain_assembly.py:2126-2131`),
so in a shared-datum pack EVERY below-grade structure lands in ONE
facility whose `body` unions geographically unrelated pits, and
`anchor_inside_body` is judged against that union (R§3 — this is how the
T4S facility "contained" an anchor 406 m outside the ring). New law: after
unioning the grouped records' parts, **split the facility per connected
body component** — one `BasinRimFlushFacility` per connected part
(members = records whose footprint touches that part; `solid_minimum_y_m`
min over those members). The anchor stays the records' shared datum. The
emitter's trench grouping is untouched (it already cuts per-part rings);
only the facility/seating records split.

**Amendment 2 (Fable ruling, 2026-08-27 — degenerate components are
noise, not facilities).** Measured at LEMD: the body union split into the
real 27,806 m² T4S ring AND a 1.6e-13 m² sliver, which became a second
facility with its own `G` 3.705 m away and double-seated 42 files (last
writer wins) with a spurious clearance FINDING. Split components pass
through the region round's polygon-repair idiom, and a component below
1e-6 m² is DROPPED as degenerate numerical noise with a log line — a
geometric-validity floor, not a design threshold. The implementer's
conservative overlap refusal (a group sharing resources with an earlier
facility's group refuses loudly) is RATIFIED and stays as the backstop.

**Amendment 1 (Fable ruling, 2026-08-27 — the seat group is CLOSED over
the file↔structure relation).** §2.3's delta is per resource FILE
(`delta_by_resource_and_vertex`), so a file spanning structures inside
and outside the footprint-intersection seed cannot take two deltas: the
group closes over "same file" and "same structure" until fixed (LEMD:
seed 26 structures / 46 files → closure 14,378 structures / 48 files).
Closure widens only the CLAIM set — every closed-in file takes the same
`G` it would have anyway — and the relationship invariant is asserted
over the closed group.

### 2.2 The seat group: structures intersecting the body

For each facility, the SEAT GROUP is every partition structure
(`_cached_partition_structures`, the same partition the bake walks) whose
horizontal footprint intersects the facility body — NOT the interface's
`object_resources` list. At T4S this pulls in structure idx 0 (the
81,204 m² fused complex: Ground-FSX 03/13/14/37/85, Terminal4SAT parts,
T4STower), the Terminal4sBlue structures, and the R4-excluded LEMD36 —
the whole local complex, and nothing 2 km away (Cargo/Munoza structures
not touching a body stay on the generic path). This is the owner's "the
seatable rigid unit is the structure group, not the whole pack family",
made literal.

Widening rule (T1, the LSGG law): the group is widened into SEATED and
withheld-from-generic **in the same step** — every seat-group structure is
routed to this law and removed from the generic pass's population (both
its cluster seating and its A3 guard; mirror of rim-flush item 5). No new
R4 exclusions.

### 2.3 The seat: one datum ground per facility, one law formula

Rendered elevation of a draped member is `mesh(anchor) + y + delta`.
Authored relationships are preserved iff every member of the group ends on
one common datum plane `G`:

    delta(member) = G − anchor_ground(member's anchor)
    G = R_mesh   (the §2.2 rim-band built-mesh median, unchanged)

This is the existing rim-flush formula — the amendments are:

1. **One instrument (T7 fix):** all `anchor_ground` values for a
   facility's seat group are computed by THE facility pass's sampler in
   one pass; the generic pass's ground for those anchors is never
   consulted. OBJECT_AGL folds in as today (A18,
   `post_mesh.py:1235-1239`).
2. **Item 6 retires topology for a threshold:** instead of
   "anchor-outside facilities do not bake", every facility group bakes
   with the formula; where `|delta| < DSF_OBJECT_BAKE_MIN_DELTA_M` (1.0,
   the existing constant) for ALL group anchors, the bake is a recorded
   no-op — which reproduces the OTHH anchor-outside measurement (drape
   was ≤0.4 m correct there, i.e. delta ≈ 0) while fixing LEMD, where
   drape-at-datum vs rim differs by ~1.5 m. The old topological skip is
   retire-kept-gated with the feature gate (§2.6).
3. **Decision kind `basin_group_seat`** (new constant beside
   `BASIN_RIM_FLUSH_DECISION_KIND`), stamped per resource as today.
4. **Floor lockstep unchanged:** the emit-time floor law stands; the §2.2
   clearance check now uses the group's `G` (same check, wider
   membership), still a loud FINDING on violation.

### 2.4 Member fates inside the group (T5)

- A resource with >1 draped placement keeps its I-4 skip but gains a loud
  per-resource line naming the facility (today it's silent to the
  facility).
- The reach-floor drop's bare `continue` (`post_mesh.py:930-943`) gains
  the missing skip line (defect noted in recon; in scope, one line).
- Foot-anchored and inheritance logic never run for seat-group members
  (the group delta is total).

### 2.5 Provenance + run record (T3, T6 fixes — required, not optional)

- Provenance entries for `basin_group_seat` bakes record the applied
  `delta` and the facility's `G` (today no delta survives a restore —
  the LEMD offsets are already unrecoverable). Add to the entry dict;
  bump `RUN_RECORD_VERSION`.
- Add the new gate to `_GATE_NAMES` AND `_GATE_ENVIRONMENT_NAMES`
  (`object_rebake.py:167-241`), **and fix the standing gap found in
  recon:** `O4_BASIN_REGION_FOOTPRINT`, `O4_BASIN_REGION_FOUNDING`,
  `O4_BASIN_OPEN_PIT_DECK_KEY`, `O4_BASIN_POOL_SCOPING` are absent from
  `_GATE_ENVIRONMENT_NAMES`, so a pre-region run record can short-circuit
  a post-region decision. Add all four.

### 2.6 Gate

`config.BASIN_GROUP_SEAT` (env `O4_BASIN_GROUP_SEAT`, default ON). OFF →
the pre-amendment rim-flush behavior (anchor-keyed grouping, topological
item 6, interface-member seating) byte-identical. Salt into the
classification cache key AND the run-record gate lists.

## 3. Tests (headless, synthetic; extend `tests/test_object_basin_trench.py` or a new `tests/test_basin_group_seat.py`)

1. **Relationship invariant (the owner's metric):** synthetic facility —
   flat-datum family of an at-grade "terminal" + below-grade members at
   authored −3/−7, sloping mesh. After the decision, every group member's
   delta satisfies `mesh(anchor)+delta == G` exactly → pairwise rendered
   relationships equal authored (0 relative shift), including across two
   anchors 6 m apart.
2. **Grouping split:** two disjoint pits under one shared datum → TWO
   facilities, each with its own `G`; the distant pit's seat unaffected
   by the near pit's rim.
3. **Seat-group membership:** a structure overlapping the body joins the
   group and leaves the generic pass in the same decision; a structure
   2 km away at the same datum does not.
4. **Threshold no-op:** anchor ground ≈ R_mesh (OTHH pattern) → recorded
   no-op, no .obj rewrite.
5. **Provenance:** the entry carries `delta` and `G`; gate lists contain
   the five env names (§2.5).
6. **Gate off:** old behavior byte-identical on the synthetic fixture.

Run once (ledger): the new/extended test file plus
`tests/test_object_basin_trench.py`, `tests/test_object_tunnel_terrain.py`,
`tests/test_object_bridge_terrain.py`, `tests/test_harness.py`
(near-miss-frontage failure is pre-existing, not yours).

## 4. Acceptance — ONE mesh-only LEMD tile run

The rebake runs on tile builds only (R§1), so acceptance uses
`tools/run_tile_mesh_only.py` for +40−004 (it arms the shared-repo guard;
verify it reaches `rebake_dsf_objects`, else fall back to ONE
`build_airport.py LEMD --tile 40 -4`-class run — never more than one
tile-scale run). On the run's provenance/run record:

* ONE `basin_group_seat` decision covers the T4S seat group, including
  ALL FIVE named objects' structures (`Ground-FSX-LEMD36/37/85/03`,
  `Terminal4sBlue-LEMD35`);
* for every pair of group members, `mesh(anchor)+delta` agree (one `G`) —
  relative shift 0.000 m (materiality 0.01 m);
* the structure-0 intra-family cut seam (8.95 m recorded in the last run)
  is absent from `cluster_seams` for seat-group structures;
* no A3 skip lines for seat-group structures; the I-4 and reach-drop
  lines appear where applicable (loud, named).

Attempt cap 2 per target; second miss STOP-and-report. Build-time: the
group intersection is one STRtree pass over partition footprints per
facility (~ms); the seat itself replaces per-cluster work for those
structures. Suspended timing law — ledger tripwire only; tile budget
adjudicated at the final profiling round.

## 5. Out of scope

* Seating for shared-datum families with NO basin facility (pure
  above-grade packs) — the generic cluster law stands there.
* Multi-placement (I-4) member baking.
* Any change to trench emit geometry, floor arithmetic, or the region
  instrument.
