# Basin facilities: rim-flush seating, no anchor pillar — spec (2026-08-09, v2 EXPERIMENT-FIRST)

Author: lead session (Fable). Status: **v2 — §2.1 (emitter) FROZEN for
implementation as Phase E, the owner's experiment; §2.2 (post-mesh
bake) DEFERRED pending the owner's in-sim verdict.** Owner 2026-08-09
(second ruling, verbatim): "If the object placement is in the middle,
maybe it's tied to the bottom of the object, so placing it at the
bottom of the trench will already seat the top at the ground level?
Let's try cutting the trench, but don't modify the objects so I can
see how it looks." The measurement on record (recon §1) says the
placement origin is the RIM (authored solids −3.816…+0.056, y = 0 at
the top), so the predicted Phase E result is rims ~4.3 m below grade
(13.5 m at Dewatering_01) — but the sim adjudicates, not the
prediction; both outcomes are recorded either way. SEQUENCED: the lane
starts only after lane/objpads lands (shared file: grade_law.py);
lane/seatgate has landed. Charter: owner 2026-08-09 (OTHH bug report,
verbatim):
"Drainage areas, like open tunnel ramps that have objects, need to have
the trench cut enough to expose the interior (bottom and sides) faces
of the objects, we don't want any terrain poking up in the middle —
currently we're emitting an 'object_basin_anchor_seat' which protrudes
up through the bottom of the object, and the drainage objects are still
be seated down too low, they need to be seated so their primary top
surface is flush with the terrain, not below it."

Siblings: `docs/specs/object-reseat-threshold-spec.md` (the ≥ 1 m
reseat law this class rides on), `docs/specs/feature-c-pit-emitter-spec.md`
(closed; emitter exists), `docs/object_terrain_features_spec.md` (R4
interlock — amended below), prior art
`docs/specs/below-grade-cutouts-and-deck-flush-plan.md` W2f (predicted
this pillar). Rulings canon: `docs/RULINGS.md`.

## 1. Measured state (recon 2026-08-09; cite, don't re-derive)

* OTHH has 8 basin facilities (6 Drainage bowls, `cuts_pavement=True`;
  2 Dewatering TRENCH_SPINE pools). All placements are draped `OBJECT`,
  AGL 0; every shell's primary top surface is authored at y ≈ 0
  (+0.056 m lip on the `_001` shells) — so the y = 0 plane IS the rim
  reference.
* Six facilities' anchors lie INSIDE their own cut; each gets a 3×3 m
  `object_basin_anchor_seat` pinned at the pre-solve DEM datum — a
  pillar standing `body_depth + 0.5` above the trench floor (4.31 m;
  13.50 m at Dewatering_01), covering 7.4–9.0 m² of the object's own
  interior floor faces. The trench floor's 17.64 m² keep-out hole
  emits as an UNVALUED `shape_interior_ring` way. Two facilities
  (Drainage_06, Dewatering_02 pool) have anchors OUTSIDE the body and
  no seat; they drape on adjacent terrain, off-flush by ≤ 0.4 m.
* Top-vs-surrounding-surface error today: −1.65 … +0.79 m, sign
  flipping, from three mechanisms: (1) the datum is a point DEM sample
  at `placements[0]`, an arbitrary point (Dewatering_01: datum 0.80
  against a rim-band DEM range 0.71…2.96); (2) the neighbour the rim
  must match is the SOLVED surface, not DEM (Drainage_04: DEM 3.41 vs
  solved apron 2.62); (3) the rim band's emitted values are per-part
  DEM samples (`object_terrain_assembly.py:1842-1854`), the law value
  `tunnel_trench_rim_elevation_m` being only a nodata fallback — and
  the facility log line prints the law value, not what was emitted.
* THE COUPLING TRAP: floor and seat key on the SAME datum
  (`floor = datum + deck_reference_y − 0.5`). Re-keying the seat to
  rim-flush without re-keying the floor buries Drainage_04/05's floors
  through their modelled bottoms (−0.29 / −0.07 m clearance).
* `basin_trench_structures` sets `solid_minimum_y_m` to the
  largest-perimeter-share below-grade level, NOT the deepest solid:
  Drainage_06's true min −4.201 vs floor key −3.859 leaves 0.158 m of
  the promised 0.5 m clearance.
* Interior exposure is otherwise already correct: outside the seat
  keep-out, un-cut terrain under interior floor faces is only the
  0.6 m wall-setback collar (1.3–5.0 %), which is the designed
  flush-wall batter and stays.

## 2. The design

One coordinated correction per basin facility, replacing the pillar:
the TERRAIN cuts the full interior, and the OBJECT is reseated so its
y = 0 plane lands on the surrounding built surface. R4's interlock
("terrain-to-object and object-to-terrain corrections must never
stack") is AMENDED for the basin class only: this is one correction
defined jointly, not two stacked — the bake target is defined relative
to the post-cut built mesh, so neither side double-counts. Record the
amendment note in `docs/object_terrain_features_spec.md` §R4 in the
landing commit.

### 2.1 Emitter (object_terrain_assembly.py) — basin facilities only
(`terrain_feature == TERRAIN_FEATURE_BASIN`; tunnel facilities keep
today's behaviour verbatim — no OTHH fixture exercises them and the
EGLL class must not move; the shared-mechanism follow-up is an open
item, not this spec)

1. **No anchor seat.** The seat emission (`:1687-1734`) and its
   keep-out are skipped for basin facilities. The floor covers the
   anchor; no interior ring, no pillar.
2. **The rim reference replaces the point datum.** New law input
   `R_est` = median of DEM samples along the facility body outline
   (`body.exterior`, sampled every ≤ 10 m; multi-part bodies pool all
   parts' samples). `tunnel_trench_rim_elevation_m` and
   `tunnel_trench_floor_elevation_m` take `R_est` for basins where
   they took `datum`.
3. **The floor keys on the TRUE deepest solid, with a seat-estimate
   margin.** `basin_trench_structures` carries the structure's true
   minimum solid y (new field or corrected `solid_minimum_y_m` —
   whichever the record contract allows without breaking tunnel
   consumers; if ambiguous, STOP and report). Floor law for basins:

       floor = R_est + y_true_min − TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
                     − TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M

   New constant `TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M` default **1.0**
   (config.py, env `O4_TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M`): covers
   |built-mesh rim − R_est| estimate error (measured DEM-vs-solved
   gaps at OTHH reach 0.79 m). The extra depth sits under the
   modelled bottom, invisible from above.
4. **Instrumentation:** the facility log line reports the EMITTED rim
   band range alongside the law value (closes the gap recon named).

### 2.1e Phase E additions (the experiment arm — implement WITH §2.1)

E1. **No basin member is baked, by construction.** Every basin
    facility member resource joins `exclusion_set_for_dsf`
    (`object_terrain_assembly.py:888`) — VERIFY current coverage
    first: the 2026-08-08 pad-request corpus shows Dewatering pool
    shells raising cluster requests (−13.6 m deltas), i.e. at least
    the pool members are NOT excluded today; extend the set so all 8
    facilities' members are. The pack stays byte-authored through a
    tile pass; assert it (live == `.anchor_bak` for every member
    resource after the pass).
E2. The experiment tile build is the owner's viewing artifact: cut
    trenches per §2.1 (no seat, R_est/true-min/margin floor), objects
    draped as authored. Record per facility, in the report the owner
    reads: predicted vs built rim elevation (mesh-sampled at the
    object outline), and the drape elevation X-Plane will use
    (mesh at the anchor point).
E3. §2.2 below is implemented ONLY if the owner, after looking,
    rejects the draped result. Its text stays frozen design.

### 2.2 Post-mesh basin seat law — ACTIVATED (owner in-sim verdict 2026-08-09)
(object_anchor / post_mesh / object_rebake)

> **VERDICT ON RECORD (owner, 2026-08-09, build 1.0.226 in-sim):** the
> anchor-outside facilities (Drainage_06, Dewatering_02) "look just
> right"; the anchor-inside facilities (Drainage_04, _05, _01, _02,
> Dewatering_01 named; Drainage_03 same class) are "sunk below the
> bottom of their trench" — the predicted drape-on-floor outcome, and
> the §2.1e E3 condition for implementing this section. Scope is
> unchanged: item 6 already limits the bake to anchor-inside
> facilities; the anchor-outside class stays untouched (measured
> correct in-sim). Prerequisite fix folded in: the sidecar's
> `solid_minimum_y_m` for Drainage_06 still carries the interface
> floor key (−3.859) not the true deepest solid (−4.201) — the
> true-min plumbing must be verified per-facility BEFORE the bake
> targets are computed (it feeds the §2.2 item 7 clearance check).

5. Basin facility member resources (the `TunnelStructure
   .object_resources` — pool siblings whose anchors lie outside the
   cut are NOT members and keep the generic law) leave the
   excluded-from-bake set and take a dedicated bake law, decision kind
   `basin_rim_flush`:

       R_mesh = median built-mesh elevation on the ring offset
                OUTWARD from the body by
                (_TUNNEL_RIM_BAND_WIDTH_M + 1.0) m   [first terrain
                outside our plates], sampled every ≤ 10 m
       delta  = R_mesh − mesh_at_anchor        (mesh_at_anchor = the
                trench floor the object drapes on)

   applied whole-facility-rigidly (all member resources, one delta
   family via the existing per-resource anchor-ground arithmetic).
   Generic median/A3/threshold arithmetic does not run for this class;
   the delta is by construction ≥ 1 m here, consistent with the
   reseat-threshold law's "≥ 1 m units reseat".
6. **Anchor-outside facilities do not bake.** A basin facility whose
   anchor lies outside its body (Drainage_06, Dewatering_02 pool)
   drapes on neighbour terrain; its flush error is neighbour-local
   (≤ 0.4 m measured) and stays under the reseat threshold — leave
   draped, generic law untouched.
7. **Clearance verification, not hope:** after seating, assert
   `R_mesh + y_true_min ≥ floor + TUNNEL_FLOOR_BELOW_OBJECT_DECK_M −
   0.01`; a violation is a loud per-facility FINDING naming the
   measured `R_mesh − R_est` (it means the margin constant is too
   small for this airport — report, never silently re-derive).
8. Idempotence: authored space from `.anchor_bak` (I-15); the new
   constants and the basin law join `_gate_digest`; the reversion pass
   needs no change (basin bakes revert like any other).

## 3. Constraints (standing; violations are STOP-and-report)

1. Basin plates stay `ROLE_TUNNEL_TRENCH` with the existing name
   prefixes minus the seat; NO new role literal.
2. Zero airside effect; the R13 pavement cut set is untouched.
3. Battery inertness: no battery airport classifies a basin
   (feature-c spec) — battery patches must be byte-identical; prove,
   don't assume.
4. Build-time HARD LAW: the R_est/R_mesh medians are O(perimeter/10)
   DEM/mesh samples per facility (~tens) — state the impact (~zero),
   tripwire only.

## 4. Tests (extend tests/test_object_basin_trench.py conventions;
headless, tmp_path)

* Basin facility → NO `*_anchor_seat` plate, no interior ring, floor
  covers the anchor point.
* Floor law: `R_est`-keyed, true-min-keyed, margin applied (synthetic
  fixture where point-datum and rim median differ — assert the floor
  uses the median).
* Post-mesh: synthetic mesh → `basin_rim_flush` delta seats y = 0 at
  R_mesh; whole-facility rigidity; pool sibling keeps generic law;
  anchor-outside facility not baked; clearance finding fires when
  R_mesh is forced below R_est − margin.
* Tunnel facility (non-basin) → byte-identical behaviour to HEAD
  (regression pin for the scope boundary).

## 5. Acceptance

1. Unit tests + blast-radius suites green (ledger).
2. OTHH patch build (harness, lane): zero `object_basin_anchor_seat`
   plates; zero basin `shape_interior_ring` ways; floor/rim values
   reproduce the §2.1 law to ±0.01 m; report per-facility floor, rim
   range, R_est.
3. OTHH tile pass (JOINT with the reseat-threshold integration —
   budget one shared pass, lead-coordinated): per facility, measured
   in the built mesh + rebaked pack: top surface within ±0.10 m of
   R_mesh (report all eight); clearance assertion green; census vs
   control — zero NEW airside rows, groundside deltas attributed.
4. Battery: byte-identity spot-check (HECA or KCLT patch body hash)
   proving basin-scoped changes are inert off-OTHH.
5. Build-time impact statement.

## 6. Convergence guards (mandatory)

Materiality 0.01 m (the ±0.10 m in-mesh tolerance is the acceptance
bound, not an iteration target); attempt cap 2 then STOP-and-report;
`.progress` heartbeat. Honest budget: ledger suite + 1 OTHH patch
build; the tile pass rides the integration round's budget. Hard cap 2
OTHH patch builds.

## 7. Open items (owner / follow-up)

* The pillar class exists for TUNNEL facilities too (W2f predicted it
  at Bridge_01); this spec scopes to basins — a follow-up decides the
  tunnel-side treatment with an airport that exercises it.
* The +0.056 m lip: y = 0 is the flush reference (the `_000` shells'
  top); the lip rides 5.6 cm proud by authoring — accepted, sub-floor.
