# Apron relief law: fan ramps first, terrace panels as fallback, nothing touches a movement surface

## Revision history

- **r2, 2026-08-05 (this text).** Fable revision to CURRENT law — the
  cycle-4 design debt (checkpoint `ab00777` item 5). Replaces the r1 text
  and the "PARTIALLY SUPERSEDED" banner `b538ba4` carried over it.
  Incorporates: the trigger re-keying to anchor-envelope infeasibility
  (RULINGS `4cbed92`, code `db4d823`), THE FAN-RAMP LAW (RULINGS
  `21f0980`, code `3850c92` + `b538ba4` + `d316e65`), the pre-solve panel
  boundary (`8c6e047`), the 0.6 m slot items (`fe06dbf`), and the parked
  fan-activation design (lane/fix3b `d9ce0e6`/`de2132e`/`bfa79d1`,
  pending merge). Supersessions and ratifications are in §10–§11.
- **r1, 2026-08-04.** "Apron terrace law: level panels, joints never
  cross a spine" (original Fable spec, owner ruling `170d4e3`; lead
  adjudication `768cded`). Its binding constraint, certificate
  discipline and validator lockstep survive into this text; its trigger,
  relief-form exclusivity, gate, and acceptance regime are dead (§10).

**Status: BINDING.** Mode: BUILD-COMPLETE-THEN-DEBUG (RULINGS
`12320bd`) — no gates, no terrace-off arm, deviations decide-and-note.
BINDING context: docs/RULINGS.md end-to-end, especially
no-lawful-infeasible-ground (`5578b6a`), single-solve architecture
(2026-08-03), airside-is-king, flat-worlds-first + CORRECTION
(`4cbed92`), the fan-ramp law (`21f0980`), the HECA central-U model,
drainage scope (`d48bc0a`), real-DEM gated on flat-green (`e56d40c`).
Consistency partner: docs/specs/cycle4-projection-ingestion-spec.md
(the terrace/fan law is a carried-context INPUT to it — §7).

## 1. The law in one paragraph

An apron whose anchor envelope no single capped panel can span takes
RELIEF. The relief trigger is ANCHOR-ENVELOPE INFEASIBILITY — hard
values + caps + geometry — never DEM steepness; it fires identically in
flat and real worlds. The relief answer, in precedence order: in
frontage-backed apron zones, a FAN RAMP first — a continuous zone at the
groundside-pavement cap (5 %) fanning between adjacent buildings' seat
levels along the back apron edge; then, for the shortfall 5 % cannot
span within the zone, and as the only form for non-frontage aprons,
LEVEL TERRACE PANELS with declared joint steps (retaining walls). No
ramp, joint, or wall may touch any aircraft-movement surface — spine
corridors, frontage chords, stand entries — and every spine grades
continuously at its cap through the apron regardless of panelization.
Panels and zones exist BEFORE the solve as shapes; the ONE solve is
handed their caps and step budgets as ordinary law; emitters emit,
never grade; no post-solve authority mints or overrides a terrace or
fan value.

## 2. The trigger: anchor-envelope infeasibility (never DEM)

Owner law (RULINGS `4cbed92`): "triggers derive from ANCHOR-ENVELOPE
INFEASIBILITY (hard values + caps + geometry), identical in flat and
real worlds." Any DEM-steepness-keyed trigger is incorrect law,
verdict (c). Landed: `db4d823` (`apron_terrace._envelope_demand`,
`presolve_anchor_envelope`).

- The envelope is the interval the projection enforces at every point:
  `floor(p) = max over anchors (v_a − route budget a→p)`,
  `ceiling(p) = min over anchors (v_a + route budget a→p)` — the same
  two fields `building_feasibility.spine_value_fields` computes and the
  FINAL band assert judges. It is built PRE-SOLVE
  (`presolve_anchor_envelope`: `reach_band_unified` on the unified
  grade graph), a pure function of geometry + CIFP anchors — no solved
  value can launder a value defect into a terrace (`5578b6a` stands).
- The demand: `excess = max over ordered pairs (L_k − U_m −
  allowance_km)`. The allowance is `cap·d_km` (strict apron cap), or
  the ZONE cap over in-zone pairs (§3 — precedence lives in the
  trigger). The shortfall IS the relief the declared steps discharge.
  Terrace lines run along the ENVELOPE contour (perpendicular to the
  worst pair's axis), the role the DEM gradient used to play.
- Fire floor: `APRON_TERRACE_MIN_EXCESS_M` (0.25 m) — cm-noise never
  panelizes. No envelope ⇒ no licensed terrace (a build that cannot
  compute the demand must not invent one).
- AN INVERTED BAND IS A DEFECT REPORT, NEVER A LICENCE. `floor >
  ceiling` at one point means two anchors contradict through the route
  between them; a terrace cannot add budget to a route it may not
  cross. The loud `BandInversionError` rolls its nodes up by anchor
  pair (provenance `layout._band_anchor_provenance`), so "3,169 nodes
  inverted" reads as two anchors, one route budget, one shortfall.
- THE DEMAND CENSUS: `candidates_demanded` / `candidates_under_floor` /
  `demand_total_m` / `demand_worst_m` — "0 joints" must distinguish
  no-apron-asked from asked-and-nothing-fired.
- The DEM plane reading survives ONLY as report-only certificate
  provenance (`dem_plane_slope`, `dem_geom_excess_m`). Anchor evidence
  (the pair, values, route budgets, chord, allowance, shortfall) is in
  the certificate; the sidecar stays auditable.

## 3. Relief precedence: fan ramp first, wall as fallback

Owner law (RULINGS `21f0980`, four clarifications answered): ramp cap
**5 % — the groundside-pavement class, no new constant family**
(`FAN_RAMP_CAP = GROUNDSIDE_MAX_GRADE`, 0.050); **ramps FIRST**, the
declared wall/step is the ruled FALLBACK only for the relief 5 % cannot
span within the zone; GENERAL scope — every apron with building
frontage; the HECA central U (between 05C/23C and 05L/23R) is the
acceptance exemplar.

Precedence is IN THE TRIGGER, not a second pass (`3850c92`): the zone
cap enters `_envelope_demand` as the pair allowance, so the shortfall
the wall law then sees is exactly what 5 % could not discharge. Two
predicates, deliberately distinct: the SOLVER prices one straight edge,
so a chord that leaves the zone keeps the strict apron cap (pair_cap);
the TRIGGER asks whether a ramp can discharge relief along the ground,
and a zone polygon is connected, so both endpoints inside suffice
(endpoints_cap).

Non-frontage aprons: the terrace panel/wall form (§5–§6) remains the
one relief answer. The fan is not drawn anywhere: zone-interior pairs
enter the ONE solve at the zone cap as ordinary law edges, and a
surface fanning between the two seat levels is what that system solves
to.

## 4. The fan-ramp zone (geometry)

Landed derivation (`3850c92`, indexed `b538ba4`,
`apron_terrace.plan_fan_ramp_zones`): one zone per ADJACENT PAIR of
buildings. For pads A, B with gap ≤ `_FAN_PAIR_MAX_GAP_M` (250 m,
provisional): reach = `hull(A ∪ B)` grown by the gap it must fan across
(depth capped `_FAN_ZONE_MAX_DEPTH_M` 120 m), cut back to the pair's own
extent along the axis joining them; the zone is
**reach ∩ apron − corridor cover**:

- ∩ APRON — the law grades apron, nothing else;
- − COVER — `corridor_cover` already carries every spine corridor,
  frontage chord, stand entry and pad, each buffered by the standard
  clearance, so "clear of every aircraft-movement surface" is inherited
  STRUCTURALLY, not checked after;
- ∩ REACH — bounded by the two buildings it fans between: the back-edge
  wedge, never the whole apron. Both bounds were forced by measurement
  (an unbounded cut wrapped 77,142 m² of a 120,000 m² fixture apron
  through the strip behind the pads; the axis cut closes the sideways
  spill).

A third pad between A and B is in the cover and splits the zone by
construction — "adjacent" needs no separate test. Components under
`_FAN_MIN_AREA_M2` (200 m²) or touching fewer than 2 pads are dropped.
The `_FAN_*` bounds are implementation-provisional (owner-adjustable),
not owner constants; the ruled bound they encode is "adjacent frontage
chords + back apron edge + spine clearance".

## 5. Structural constraints (the binding clause)

Owner verbatim class (`170d4e3`): relief "has to be done in a way that
does not interrupt any spine where aircraft have to travel." These hold
for ramps, joints, steps and walls alike:

1. A joint is born as `(terrace line ∩ apron) − corridor cover`; a zone
   is born minus the same cover. Cover = every taxi/route centerline at
   `APRON_TERRACE_CORRIDOR_HALF_WIDTH_M` (11.5, code C) +
   `APRON_TERRACE_JOINT_CLEARANCE_M` (2.0), plus frontage chords, stand
   entries and pads at standard clearance. Never-touch is BY
   CONSTRUCTION — no later pass shortens anything; the validator twin
   (§8) is the instrument, not the enforcement.
2. Every spine grades continuously at its cap through the apron:
   corridor nodes remain global route members; panel-boundary nodes on
   a corridor ARE the corridor's nodes (shared identity — a step at a
   taxiable edge is impossible by construction; direction spine→panel:
   the spine gives, the panel conforms — airside-is-king generalized).
3. No joint or wall inside a runway-strip footprint; retaining walls
   are NEVER lawful at a runway edge (owner 2026-08-01).
4. "Level panels" = free datum, ordinary apron law (1 % cap, all
   directions) inside each panel — not literal flatness. Interior
   drainage-minimum grading of panels is VERSION-DEFERRED (`d48bc0a`);
   the census reports the family under its own heading.

## 6. The pre-solve form: geometry refinement, one solve

Terracing and fan zones are GEOMETRY REFINEMENT under the single-solve
architecture (ingest → geometry → ONE solve → emit verbatim). The panel
boundary and the fan zone exist BEFORE the solve as shapes; the solve is
HANDED their caps; no post-solve authority mints terrace/fan values.

**6a. Panel boundary pre-solve (LANDED, `8c6e047`).**
`construct_apron_terrace_presolve` panelizes every triggered apron and
SPLITS its polygon at the joints before the solve. The joint's two
station rows — the line itself, and the same stations retreated one
`STACKED_WALL_RETREAT_M` to the low side — become ordinary apron RING
vertices, therefore solve VARIABLES, with no special case downstream.
The apron's `BuiltShape` is kept and re-pointed at the largest panel
(identity survives for earlier captors); siblings append as new apron
shapes with the same ref. A joint expressible only as an interior hole
is STILLBORN (every shape stays simply connected). This is the root fix
for every residue r1 carried: D2's 6.0 m faces, the post-solve split's
minted defects, the 2,479 m² face lap, SPLP's 8.48 m² self-overlap —
one defect (boundary created after the surface settled), now
structurally impossible.

**6b. Joint binding and emission (LANDED, `8c6e047`).**
`plan_apron_terraces` is the BINDER: it resolves the declaration into
the solve's index space by canonical join, re-resolved after any
node-list rebuild (the rod-key lesson), and decides nothing.
`terrace_station_edges` binds `|z_hi − z_lo| ≤ step + cap·retreat` — the
declared step is BOUND, not merely reported. `apply_terrace_budgets`:
a within-apron law edge whose chord crosses k declared joints gets
`cap·d + Σ step` (monotone-relaxing; canon per r1 adjudication ruling 1
— the literal cap-for-step swap TIGHTENS long chords); every other
edge, including every edge on or through a corridor, keeps full apron
law. Steps: `step_m = min(APRON_TERRACE_MAX_STEP_M, excess/joints)`
(2.0 m, owner-adjustable provisional). `emit_terrace_joint_faces` mints
one `retaining_wall` face per settled joint PER STATION, reading the
two panels' FINAL settled ring values BY IDENTITY (it runs after the
late final grade projection — standing owner ruling 2026-08-05 — so it
reads what actually settled); the station table is one computation with
two consumers (binder and emitter speak about identical ground). Faces
are minted before interning so no emit-time consensus can average a
joint away. The r1 flank window / first-order fit / cap-clamped walk-in
are DELETED.

**6c. The 0.6 m slot (LANDED, `fe06dbf`).** The pre-solve split cuts a
`STACKED_WALL_RETREAT_M` band from the apron per joint; until the face
mints at build end, that band is ground no shape covers. Law:
- the reservation is published at plan time as
  `layout.apron_terrace_wall_bands` = **band ∩ host** (the ground the
  split actually removed — the raw band's overhang was never apron);
- `emit_adjacent_ground_bands` unions the reservation into its static
  block: ground that is spoken for is not marchable;
- a joint whose flanks settled LEVEL emits a COVER: `faced` stays
  False, step and allowance stay 0 (no relief), but the cut band is
  closed — a hole is not the absence of relief (ratified, §11);
- unreadable joints are counted loudly (`slots_uncovered`).
NORMATIVE (this revision, promoting `fe06dbf`'s named remedy): joint
END stations are placed where the joint line MEETS the apron boundary,
so the end corners are readable ring vertices and the face reaches the
boundary (closes the measured 67.93 m² end-station-overhang residue).
Note honestly: station positions feed `_band_polygon` and the CUT, so
this changes panel rings, node counts and the solve at every panelized
airport — land it as its own debug-cycle change, never a fix-forward
edit inside another lane.

**6d. Fan zone as a SHAPE (PENDING MERGE: lane/fix3b `d9ce0e6`,
hardened `bfa79d1`).** The landed cap-on-edges form (`3850c92`: in-zone
pairs raised to the zone cap in BOTH edge sets — `shape_constraints`
and the unified graph, since relief granted in one is taken straight
back by the other) is correct and measured INERT: an apron's solve
variables are its ring vertices, and a zone is interior ground by
construction — at HECA plateau only 16 of 10,255 within-apron rows had
an endpoint in any zone. So the zone becomes a shape, the terrace law's
own answer: `split_aprons_at_fan_zones` cuts each apron at its zones'
union components pre-solve; the ramp piece keeps `role == apron` and
carries `fan_ramp_zone`; its cap resolves through ONE function
(`config.fan_ramp_law_cap`) on both the solver side (GradeShape flag,
set at BOTH memoized GradeShape sites — the memo trap) and the census
side (the emitted `o4_grade_law='fan_ramp'` tag maps back to the same
field); both reach the cap through `grade_graph._body_cap_unbounded`.
Hardening (`bfa79d1`): each zone component is subtracted from EVERY
panel (not a chosen host), and the ramp piece is defined as
**apron − panels** — the ground the cut actually removed — so
`ramp ∪ panels == apron` and `ramp ∩ panels == ∅` by construction.
Stillborn interior-ring components are dropped from the DECLARATION as
well as the layout, so solver, trigger and census read one set. The
zone-split census flag (`census.py --zone-split`, `592ec01`) is the
harness reader. These commits are pending-merge DESIGN FACTS: lane/fix3b
is parked UNMERGED behind cycle-4 target #1 (§7) plus its own
downstream ramp↔non-ramp overlap defect (§12); merge order is ruled in
checkpoint `ab00777`.

## 7. Carried law context (cycle-4 consistency)

Per docs/specs/cycle4-projection-ingestion-spec.md, every law input the
solve consumed is captured ONCE at solve time as carried context on the
layout, and `final_grade_projection` consumes it VERBATIM. This law is
therefore SHAPED as carried context:

- the terrace plan (joints, steps, station tables, panel identities) is
  carried and re-bound by SHAPE IDENTITY and GEOMETRY, never node index
  (the pattern the binder already implements — the ingestion spec names
  it as the pattern to extend);
- fan-zone caps travel as handed budgets (with 6d, as shape-carried
  caps) — the projection may not re-derive an apron's cap from raw
  role where re-derivation can disagree with what the solve was handed;
- the sidecar keys (§8) are the emit-side carriage of the same context.

The evidence this clause exists for: with the solve handed a 5 % zone
cap, `final_grade_projection` re-derived constraints without the handed
budgets and re-projected the zones into median-10.24 % surfaces
(fix3b's flat-world specimen, twin `de2132e`) — the fan acceptance
failure that parked the lane. A projection exit at a DERIVED sweep
budget is not exhaustion (`bc53f2f`): the polytope is empty — a law,
anchor, or instrument defect under the closed verdict vocabulary
(`5578b6a`) — or the graph is pathological; never a property of the
ground.

## 8. Validator lockstep (one reader)

- Sidecar keys in `<patch>.axes.json`: `terrace_joints` (joint
  polylines, panel ids, declared steps, per-station bounds) and
  `fan_ramp_zones` (zone rings, cap, buildings, area) —
  `layout.py:2814/:2832`.
- ONE READER: check_grade / the harness census / the pytest fixtures
  share one code path (`check_grade.py` is the harness library;
  `LAW_FAMILIES` registration; `test_harness.py` twin-asserts). The
  census judges a within-apron pair at the zone cap when inside a
  declared zone (the solver's predicate VERBATIM), at
  `cap·d + Σ step` when its chord crosses declared joints, and at the
  strict apron cap otherwise. The precedent this pattern exists for: a
  private census wrapper that dropped `terrace_joints_ll` reported
  lawful declared terraces as violations.
- Hard errors (twins): joint ∩ `routes_exact` ⇒ ERROR; any step on a
  route edge through the apron ⇒ ERROR; joint inside a runway-strip
  footprint ⇒ ERROR. With 6d, the emitted-tag ⇒ GradeShape-field
  round-trip is itself twinned so a tag rename cannot desync the
  readers.
- Instruments report, the law adjudicates: declared-terrace/wall/fan
  rows are lawful structure, quoted honestly, never defects.

## 9. Landed vs pending merge

| Design element | State | Commit(s) |
|---|---|---|
| Anchor-envelope trigger, pre-solve band, inversion guard, demand census | LANDED | `db4d823` |
| Fan-ramp law: zones, precedence-in-trigger, both edge sets, sidecar + census reader | LANDED | `3850c92`, perf `b538ba4`, fix `d316e65` |
| Panel boundary pre-solve; stations as solve variables; flank-window emitter deleted; interior rings emit | LANDED | `8c6e047` |
| Slot reservation ∩ host; march exclusion; level-joint covers | LANDED | `fe06dbf` |
| Derived sweep budget (uncertified-exit verdict) | LANDED | `bc53f2f` |
| Fan zone as SHAPE (pre-solve split, one-function cap lockstep) | PENDING MERGE: lane/fix3b | `d9ce0e6` |
| Zone-split census flag | PENDING MERGE: lane/fix3b | `592ec01` |
| Solve-is-handed-the-cap twin | PENDING MERGE: lane/fix3b | `de2132e` |
| Subtract-from-every-panel; ramp = ground removed | PENDING MERGE: lane/fix3b | `bfa79d1` |
| Joint end stations at the apron boundary (6c) | NORMATIVE, UNBUILT | this revision |
| `final_grade_projection` ingestion (the merge gate for fix3b) | IN FLIGHT, other lane | cycle4-projection-ingestion-spec.md |

## 10. Supersessions (what in r1 is dead, and why)

1. **r1 §Trigger (design item 1) — DEAD.** The steep-truth DEM
   signature ("DEM chord grade > cap", the plane fit) is incorrect law,
   owner verdict (c) (RULINGS `4cbed92`): flat worlds carry the full
   CIFP anchor spread and fired ZERO terraces under it. Replaced by §2
   (`db4d823`). The interim "DEM + geometry only" reading (`8c6e047`
   decided-note 1) was superseded the same day. The component envelope
   read at solve time is equally dead — the band is pre-solve.
2. **r1 relief-form exclusivity — DEAD.** The wall/step is no longer
   the only or the first answer (RULINGS `21f0980`): fan ramps first in
   frontage-backed zones; walls are the fallback and the non-frontage
   form (§3).
3. **r1 gate `O4_APRON_TERRACE_LAW` default "0" — DEAD.** No gates, no
   terrace-off arm (RULINGS `12320bd`).
4. **r1 emit-time joint geometry (design item 3) — SUPERSEDED.** The
   flank window / first-order fit / walk-in are deleted; the emit-time
   §3(d) split was measured to MINT defects and is removed; the
   boundary is pre-solve (§6a–b, `8c6e047`). r1-adjudication item 3
   (face lap deferral, `768cded`) is RESOLVED: with the pre-solve cut
   there is no lap to close; `_split_lower_panels` is RETIRED, its
   reach-line give-back surviving at plan time.
5. **r1 acceptance regime — HISTORY.** Gate-off byte-identity anchors,
   pre-registered bands 1–6, STOP rules, the INSTRUMENT CONTINGENCY
   block, and the 2026-08-04 lead adjudication are historical record
   (adjudicated then; the band-3/band-6 "panel size vs coverage"
   tension is dissolved by §6a/§6d — the boundary and zones are now
   shapes, not post-solve area heuristics). The current regime is
   build-complete-then-debug (`12320bd`): flat worlds to zero first
   (`e56d40c` gates real DEM), the constant-DEM oracle as the standing
   synthetic twin, composed builds as testing.
6. **r1 "Mechanism" DEM percentages — demoted.** The HEAZ/HECA DEM
   readings (1.47–2.45 %) remain honest historical evidence but are
   report-only certificate provenance now, never the trigger.
7. **r1 interaction fences — largely stand.** Strip precedence and
   walls-never-at-runway-edges: unchanged (§5.3). Lateral-contiguity:
   absorbed road stretches are apron surface and their service spines
   stay in the no-cross set conservatively; relaxing service routes
   remains an owner INTENT question. The emit/consensus fence is
   superseded in direction: single-authority emission is the ruled end
   state (single-solve architecture); faces minted before interning
   remains the mechanism.

## 11. Ratifications (spec-author acts, judged against design intent)

1. `fe06dbf` level-joint COVER: RATIFIED. r1's "no face ⇒ no relief"
   governed RELIEF (step 0, faced False, allowance 0 — all untouched);
   closing the cut band is geometry, and a hole was never the design's
   intent.
2. `8c6e047` decided-notes 2–4: RATIFIED — stillborn-on-hole (simply
   connected shapes are a solver invariant); `_split_lower_panels`
   retired, not revived; sibling panels of one declaration are governed
   by their joint's step edge, not the facing law. Note 1 (trigger):
   MOOT — superseded by `db4d823` (§10.1).
3. `3850c92` deviation (the fan census reader added in the law lane
   though instruments were the other lane's territory): RATIFIED as
   necessity — without it every lawful fan grade censused as a
   violation. Promoting a fan-specific FAMILY row remains owed to the
   instruments lane.
4. §6c end-station placement: promoted from `fe06dbf`'s named remedy to
   NORMATIVE, with its blast radius stated (panel rings change at every
   panelized airport).

## 12. Known open defects (named; defects, not law)

- **`final_grade_projection` is a second author** (cycle-4 target #1,
  in flight): overrides handed 5 % fan budgets into median-10.24 %
  surfaces and owns ~10k of HECA plateau's adjudicated rows. THE merge
  gate for lane/fix3b. Its fix spec is the consistency partner (§7).
- **Ramp↔non-ramp overlap growth** (lane/fix3b, `bfa79d1`, at attempt
  cap): the pre-solve split emits a clean partition (144 aprons, 0
  overlaps) and a downstream pass grows ramp pieces into neighbouring
  aprons (3 pairs, worst 0.9477 m² at pipeline end). Proven NOT in the
  cut; parked with the lane.
- **Slot residue at HEAZ** (`fe06dbf`, attributed to the metre):
  28.84 m² unreadable joints (counted as `slots_uncovered`) + 67.93 m²
  end-station overhang — the latter closed by §6c when it lands.

## Out of scope

Split-level building seats (own spec); seam-continuity law (own spec);
groundside lots; drainage-minimum shaping beyond the §5.4 deferral note
(version scope `d48bc0a`); the strings feature (parked, owner).
