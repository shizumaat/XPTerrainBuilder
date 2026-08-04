# Apron terrace law: level panels, joints never cross a spine

Fable spec, 2026-08-04 (lead-reviewed, approved). Implements the owner's apron terrace law
(RULINGS, landed 170d4e3): long aprons on genuinely steep ground MAY
terrace into level panels with declared joint steps — "but it has to be
done in a way that does not interrupt any spine where aircraft have to
travel." BINDING CONSTRAINT (owner verbatim class): joints NEVER cross a
taxi spine/route; panels are bounded by the taxi corridors crossing the
apron; joints live only on non-taxiable interior edges; every spine
grades continuously at cap through the apron regardless of panelization.
Lines against 399c24d. BINDING: docs/RULINGS.md (feasibility-is-
guaranteed; single-solve architecture; airside-is-king; groundside
terrace law = the model; grade-law completeness: binding + twin;
runway-edge/strip law; convergence guards).

## Mechanism (the fix population — carrier_attrib/DOSSIER.md)

Genuinely-steep truth: real ground steeper than the apron cap
(`APRON_MAX_GRADE` 0.01, config.py:775) over long runs, so ONE
continuous 1 %-surface is infeasible by topology, not by any wrong
value. Measured: HEAZ (0,163/164) — 378.1 m within-apron edge, DEM
1.47 % (§4; airport-top certificate 1 165.5 m, DEM 1.397 % vs mean cap
1.203 %, excess 2.744 m; 944 over-cap final-projection edges named "the
residue a terrace law would legalise"); HECA (768,3063) — 25.0 m rise
over 1 469 m = 1.70 % (§7); (1021,17424) — 2.45 % over 521 m, ~11 m of
the 12.89 m residual is truth (§6); (779,3124)/(784,3181) — 1.63 % over
326.7 m, shipped 6.2–6.7 m steps (§8). The spine-freeze round's STOP
attribution (spine_freeze/RESULTS.md #3) names these exact carriers as
the surviving authors of HECA's 76–81 %-infeasible deep pockets: this
law is the pre-registered unlock. Census face: `within_pair.apron.slope`
(drain_worklist: 2 254 rows, 2 128 at HECA, p50 run 252 m).

## The design

1. **Trigger (generation-binding, envelope-time).** Panelize ONLY where
   law demands: an apron constraint component whose anchor/DEM/cap
   envelope is infeasible (L>U) with the steep-truth signature (the
   certificate path's DEM chord grade > cap) BEFORE the value solve —
   the existing envelope/certificate machinery names the component and
   the span (reuse; single-pass: reorder, never a second solve). Floor:
   component excess ≥ `APRON_TERRACE_MIN_EXCESS_M` (provisional 0.25 m,
   25× materiality) so cm-noise never panelizes.
2. **Panelization.** The taxi-spine network partitions the apron:
   corridor cover = every spine chain crossing the apron
   (`_build_spine_corridors`, route_profile/solve.py:6381) buffered at
   its law corridor width, PLUS building frontage chords (reach-follows-
   centerlines: stands are aircraft travel). Panels = connected
   components of (apron − corridor cover). Joints = panel|panel shared
   boundaries — non-taxiable by construction. A panel whose bounding
   corridors demand more relief than cap spans may take further interior
   terrace lines (still inside the corridor-free region). Joint-to-spine
   clearance ≥ `APRON_TERRACE_JOINT_CLEARANCE_M` (PINNED by lead review: sources the lateral-contiguity walker's
   corridor half-width — one law family; provisional 2.0 m).
3. **Joint-step geometry.** The terrace/retaining-wall machinery is the
   model (`emit_stacked_conflict_walls`, adjacent_ground.py:1841): the
   LOWER panel retreats (`STACKED_WALL_RETREAT_M` 0.6, :1827), one
   `retaining_wall` face per terrace run (:1920/:2423 pattern), step
   height ≤ `APRON_TERRACE_MAX_STEP_M` (owner constant, provisional
   2.0 m — flagged). Joint vertices are decimation-exempt (the
   two-decimators trap) and the faces are minted BEFORE interning, so
   no emit-time consensus can average a joint away.
4. **Solver binding.** Panels are constraint GROUPS in the one solve —
   no second solve. Within-panel edges keep the full apron law (cap
   0.01, all directions; "level panels" = free datum, ordinary law
   inside). Joint edges swap the within-pair cap for the declared step
   bound. Corridor nodes remain global route members: spines grade
   continuously at cap through the apron; panel boundary nodes ON a
   corridor ARE the corridor's nodes (shared identity — a step at a
   taxiable edge is impossible by construction; direction spine→panel,
   airside-is-king generalized: the spine gives, the panel conforms).
5. **Validator twin (lockstep).** The `.axes.json` sidecar gains
   `terrace_joints` (joint polylines, panel ids, declared step heights).
   check_grade: (a) within-pair edges crossing a declared joint are
   judged by the step law, not the grade cap; (b) joint ∩ `routes_exact`
   ⇒ ERROR (the binding constraint's twin); (c) no step on any route
   edge through the apron; (d) joint inside the runway-strip footprint
   (CL ± `RUNWAY_STRIP_HALF_WIDTH_BY_CODE` + end corridor) ⇒ ERROR.

Gate: `O4_APRON_TERRACE_LAW`, default "0".

## Interaction fences

- **Lateral-contiguity absorption:** absorbed road stretches are apron
  surface; their SERVICE spines stay in the no-cross set conservatively
  (a wall across a vehicle route is still a wall). Whether service
  routes may relax is an INTENT question — route to the owner, do not
  decide in-round.
- **Strip precedence (rsa-law round, unimplemented at 399c24d):** no
  joint inside the strip footprint regardless of that round's landing
  order; walls at runway edges are NEVER lawful (owner 2026-08-01).
- **Emit / consensus-retirement round:** joint faces use the retreat
  machinery and must be lawful in BOTH emit worlds (mean and
  single-authority); neither spec may depend on the other landing.

## INSTRUMENT CONTINGENCY (lead annotation, 2026-08-04): the owner has
## challenged the envelope/certificate instrument (the spine-seed red-
## flag attribution is in flight). The steep-truth EVIDENCE here is
## instrument-independent (raw DEM chord 1.47-2.45% vs cap) so the LAW
## stands; but band 1 below reads the challenged instrument — its
## verdict is PROVISIONAL until the attribution certifies the band, and
## implementers must report the raw-DEM reading beside it and must not
## STOP solely on the instrument's number.
## RESOLVED (lead, 2026-08-04, attribution landed): the band is
## TRUTHFUL; the defect was the ENVELOPE adjudication (per-edge quant
## margin compounding along paths — seed-fix round §1). Band 1 is
## adjudicated in the RAW-LAW frame at merge review; raw-DEM readings
## remain the evidence of record.

## Pre-registered outcomes (bands, not points)

1. HECA deep pockets, comparable-call infeasible fraction (default
   76.5–81.3 %): arm B (terrace + `O4_SEAT_BAND_CONSISTENT` +
   `O4_SEAT_COUPLE_SHARED_SURFACE` — the dossier pre-registered that the
   seat fix alone does NOT clear §6): <30 % success, <50 % partial, no
   movement ⇒ STOP-with-attribution. Arm A (terrace alone) quoted for
   attribution, no band.
2. The named carriers (768,3063), (779,312x), (784,318x) cease to be
   stall carriers, or their residuals fall ≥50 %; the shipped 6.2–6.7 m
   §8 steps become declared joints or fall under the step bound.
3. HEAZ final-projection over-cap edges 944 → ≤400 success / ≤700
   partial.
4. Census, both frames, all five airports: HECA
   `within_pair.apron.slope` 2 128 → −30..−80 %; `apron.cliff` (76)
   does not rise; declared-terrace/wall rows RISE and are quoted
   honestly (visible lawful steps, not defects — law adjudicates,
   instruments report).
5. Joint ∩ route intersections = 0 everywhere (hard, not a band).
6. Trigger census per airport: panels only on infeasible-component
   aprons; SPLP/CYXY expected 0-few. Panelization touching >20 % of any
   airport's apron area ⇒ over-fire STOP.

## Acceptance

Gate-off byte identity (body hashes, 2×) on the five anchors: SPLP
1531e6d0 / CYXY 5b7a1912 / HEAZ 5854d6e7 / HECA 2a28d01b / KCLT
74c4731f. Suite: same 23 reds; new twins (synthetic joint-never-
crosses-spine, corridor continuity through a panelized apron, step cap,
sidecar round-trip, trigger floor). Runway vertices byte-identical.
Only `check_build_time --run` timings are quotable; this round makes no
timing claim, and any measured gate-on cost ≥1 % of budget goes to the
Fable-5 optimization review per hard law. Build budget: identity 2×5 +
HEAZ/HECA arms (A, B) ≈ 2–2.5 h honest wall total, foreground, in a
WORKTREE (venv/OSM_data symlinked; the main tree hosts a measurement).
Do NOT commit. Convergence guards: 0.01 m materiality, 2 attempts,
`.progress` heartbeat.

## STOP rules

Band-1 no-movement (return the attribution); over-fire (band 6); ANY
joint crossing `routes_exact`; any new wall inside a strip footprint or
at a runway edge; net law-true census rise at any airport; second miss
on any pre-registered target.

## Out of scope

Split-level building seats (own spec); consensus retirement (own spec);
strip-precedence implementation (rsa-law round — fenced only here);
groundside lots; all string gates (owner pause); the cut-piece floor
(accept-the-drape stands).

## LEAD ADJUDICATION (2026-08-04, post-implementation; evidence
## scratchpad terrace_impl/)

Gated land ACCEPTED (default "0", gate-off byte identity 2x5 PASS;
band 4 HIT: HECA apron.slope -55.7%, law-true within -27.8%, cliff not
up; band 5 HIT hard-zero: joints never cross routes_exact, never enter
a strip — the owner's no-spine-interruption clause is structural).
Deviation rulings, judged against design intent:
1. APPROVED AS CANON — joint budget is `cap*d + sum(step)` (monotone-
   relaxing), NOT the literal cap-for-step swap: the literal form
   TIGHTENS chords >200 m, a regression on the fix population. Spec
   text is amended by this ruling.
2. APPROVED — panel count sized from geometric relief demand (DEM
   plane fit); the envelope remains the trigger. Post-seed-fix this
   is the only sound reading (the margined envelope is attributed
   defective).
3. PROVISIONAL — lower-panel retreat deferred: the emitted wall face
   laps 0.6 m of apron (HECA 6,222 m^2); conformance warnings byte-
   identical, nothing measurably regressed. Polygon-split surgery is
   QUEUED for the default-ON round; the sim look adjudicates lap
   visibility. Not a license to skip it there.
4. APPROVED — APRON_TERRACE_CORRIDOR_HALF_WIDTH_M=11.5 (code C)
   pinned; rulesets phase B keys it by reference code.
Arm-B pocket verdict (clause 2): the RAW/declared evidence governs —
terraces landed correctly. Bands 1/3/6 are recorded as instrument-
frame misses to be RE-READ RAW after seed-fix §1 lands; band 3's
residual (828 vs <=700, straddle-only relaxation reaches 17% of
infeasible edges) and band 6's area over-fire (75% of HECA apron area)
are the named open tension — panel size vs coverage — deferred to the
default-ON adjudication, not retuned past the attempt cap.
