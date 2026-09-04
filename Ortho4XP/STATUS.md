# ══════════════════════════════════════════════════════════════════
# 20260903b — OWNER SIM READ (OTHH tunnels) RULED + FIXED + MERGED;
#   +40-004 abort ATTRIBUTED (teardown wedge, hardened); ZERO-AIRSIDE
#   R1.1 MERGED, R1.2 IN FLIGHT. Main = 7c0513cf..dd025e05 (+ R1.2).
# TUNNEL WALLS (RULINGS 2026-09-03b, spec tunnel-wall-crest-dem-spec.md,
#   merged 7c0513cf lane/wallcrest): the crest is the DEM all round the
#   ramp (5.1 m above the mouth node by construction); the R5 transition
#   law that graded it DOWN to the ramp is DELETED at both derivation
#   sites (bridges._CrestProfile emit + finalize apply_below_grade_
#   transition — retaining_wall out of TRANSITION_ROLES; walled ramps
#   no longer below-grade sources); service-road hosts taken WHOLE
#   alongside the run (partition at the far-end line, no tolerance);
#   finalize.deconflict_road_features clip now NN-resamples (was
#   nulling wall lists, masked by the re-grade). OTHH closing build
#   e936a0cb6ab2: owner wall node −1.10 → 4.00 vs ramp −1.12; ribbon
#   −10051 GONE; census 1,620 → 1,528 (airside 1,202 = 1,202,
#   groundside 282 → 190); acceptance actionable_sites 32 → 17.
#   OWED: SW fork-crumb class (ramp_wall_gap 23 = 23, wall_top_flat
#   3.45 on a 0.47 m² crumb, mouth 25.2537652,51.6032373 non-canonical
#   before and after); owner eyeball of L4 removal service_road #48
#   (1,157 m², SW fork). osm_site prints alt=[None,None] for flat
#   way-level walls — display, not loss.
# +40-004 (RULINGS 2026-09-03c, merged 0fabfce7 lane/tilewedge): NOT a
#   failure line — the tile child finished LEMD (13:58:32) then never
#   ran the results loop; owner's Stop labelled it failed. 3 harness
#   rebuilds rc=0 (not reproduced). Hardened: bounded pool/Manager
#   teardown naming stragglers, cancelling child = "stopped", step
#   tracebacks logged. Chip filed: per-tile Stop never escalates SIGTERM.
# ZERO-AIRSIDE R1: R1.1 attribution MERGED 7de9f88b (docs/specs/r1-
#   attribution-20260903.md): HECA 2,167 = 803 inherited from the solve
#   exit / 716 FGP rebuilt graph / 648 FGP projection; 1,361 rows have an
#   endpoint RE-SEEDED pre-FGP (decimate_emit_nodes 1,205, _quant_pre
#   316, emit_terrain_transition 300, _grade_limit_gs_chords 205,
#   _enf_pre 101) — a channel the plan lacks; S1+S2+S3 ON grows apron
#   690 → 1,073. New instruments: who_wrote --cert-attrib/--vertex-dump,
#   O4_AIRSIDE_CERT_DUMP. R1.2 lane/r1solve IN FLIGHT: arm A hold-
#   release-only, arm B solve-side membrane_conform certify — DONE,
#   PARKED at lane/r1solve 6acef114 (docs/specs/r1-solve-20260903.md):
#   arm A closes 653 cert rows (2,167 → 1,514; entry both-hard 1,602 →
#   166; apron/junction/tns unchanged) but mints +22 census rows at two
#   shared-vertex apron sites (-10270 @30.11056,31.39529; -10165/-10749
#   @30.1108,31.3984) → strict rule PARKS it; gate-OFF byte-identical
#   (CYXY + HECA replay = control). Arm B: pass-2 membrane_conform pin
#   set PROVEN INFEASIBLE (L>U, 1,368/4,498 nodes, max gap 19.64 m,
#   carrier (2379,24595) budget 3.76 vs dz 20.64) → STOP, no forcing.
#   decimate_emit_nodes = ring re-mapping (0 value changes); the value-
#   changing re-seeders are _grade_limit_groundside_chords 881, _quant_pre
#   198, emit_terrain_transition 113. R1.3 (lane r1pins) IN FLIGHT:
#   attribute WHO MINTED the infeasible pass-2 pins (who_wrote --at on
#   the carriers + the -10270 site; ONE instrumented HECA) so the owner
#   can rule which senior yields (R5 if a runway datum, else R4).
# V2 DIRECTION (owner 2026-09-03 evening): build `auto_patch_v2` from
#   the ground up SIDE BY SIDE with v1 — fully law-compliant patches,
#   simpler, faster to build and to apply to the mesh (NOT byte-identity);
#   files ≤ 1,000 lines; format-agnostic GradedSurface with osm + S2
#   adapters (X-Plane Next-Gen S2 tile engine, late 2026). PLAN:
#   docs/specs/auto-patch-v2-plan.md (1eadc802); week review that led to
#   it: docs/specs/review-20260903-week.md (27ce5590; artifact link
#   inside). Lanes/scouts default to OPUS (CLAUDE.md Lanes; the hook
#   .claude/hooks/agent_guard.py still needs the owner's one-line edit).
# V2 M0 MERGED 1c053226: src/auto_patch_v2/ — law as TOML (rulesets,
#   families, precedence, zones, structures, emit; 239 constants cross-
#   checked = v1; owner 03e: editable without code), frozen interfaces
#   (model/airport, planar, constraints; solve/api; emit/surface, osm,
#   s2), m0-interfaces.md carries the M1 CYXY brief. NEXT: M1 planar map
#   for CYXY — lane v2m1 IN FLIGHT (Fable; owner 03h: Fable implements).
#   Solver decided (03g): scipy/HiGHS LP, real objective (150k in 5.3 s);
#   OSQP refused. OWNER 03h: PADS YIELD to aprons (apron relief charter)
#   — v1 R4 ARM 1 PARKED (lane/r4padyield c0eccc76): pads freed only at
#   pass-2/fp#8/FGP → airside 1,069 → 1,182 on the replay (pass-2 rows
#   1,510 → 682 but apron rings absorb the drop as within_shape); the
#   seat is MINTED in phases A/B (hard |= building_seats, spine seat
#   stamps, body-fill anchors). ARM 2 IN FLIGHT (r4padyield2): attached
#   pads leave the A/B hard set (premise change; 03i: ungoverned yields).
# R1.3 MERGED e4c568c6: the pass-2 "infeasible" pins are PHANTOM — non-
#   ring membrane nodes (stations/lattice) backfilled with the nearest
#   CIFP runway-corner elevation (116.5 m vs DEM 98) by
#   _seed_elevations(readonly) → nearest_hard_backfill; 977/1,362 rows.
#   R1.4 MERGED 754322ac (RULINGS 03f): stations/lattice/gap spines carry
#   the solve's own values; HECA adjudicated airside 1,094 -> 1,069, CYXY
#   74 -> 71, runway movers 0, pass-2 max gap 19.64 -> 4.34 m. RESIDUAL =
#   apron|apron over ~10 m REAL relief (1,058 pass-2 rows; owner: apron
#   relief charter, plan R4). Zone rows + non-pavement rings still
#   backfilled (follow-up).
# APP 1.0.276 / engine 1.50.1719 BUILT (b6f264d2; embedded==dist, fixes
#   verified inside the PYZ). NEXT: owner rebuilds +25+051 and sim-reads
#   OTHH sites 25.2715296,51.6022683 / 25.2556192,51.6080938; merge R1.2
#   on its report; five-airport sweep at the app build (29f).
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260903a — BETA ABORT ROOT-CAUSED + FIXED; app 1.0.275 / engine
#   1.50.1718 (embedded==dist). PLAN TO ZERO AIRSIDE written:
#   docs/specs/zero-airside-plan-20260903.md (READ THAT NEXT).
# THE ABORT: the 13:24 PT build of +30+031/+25+051/+40-004 on 1.0.274
#   died in every tile after 8-14 min: H1 (c1c5cccb) made every
#   build-stage failure fatal and swept in the pre-existing
#   "No apt.dat found for HECP/OTBT/LECU/LECV" raise (CIFP-listed,
#   no enabled pack). Pre-H1 that was logged + skipped. FIX 459125a0:
#   apt.dat selected in the main process before queuing; None = level-0
#   skip, never in tasks, manifest owes nothing. Twins in
#   test_auto_patch_freshness.py. First tile build on 1.0.275 rebuilds
#   every patch (engine stamp moved) — HECA ~14 min.
# MERGED: chip step-loop rc=0 (run_tile_steps over 31d imagery-optional,
#   b5f9ba3c; 292 harness tests pass). Chip road-band-seal restore =
#   SUPERSEDED on main (9ac3441c/184ee9b4), dropped.
# OWNER DECISIONS (data in the plan §2): OD-3 FGP/solve round scope;
#   OD-1 air3 sign-off (-31 net, 21 NEW); OD-2 split-level un-hold;
#   OD-8 pad-law bar vs 08-08 apron relief. OD-4/OD-5 parked to perf.
# NEXT: owner sim read of 1.0.275 → R1 attribution build (no decision
#   needed) → R1 solve round per the plan.
# LANE PROTOCOL (owner 2026-09-03, f9553e8b): subagents = Fable 5.1
#   MODERATE effort via .claude/agents/{lane,scout}.md; agent_guard.py
#   refuses any other model/type; definitions load at SESSION START —
#   a fresh session is required before dispatching R1. Root CLAUDE.md
#   "Lanes" section is the brief template's law.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260902a — BETA CANDIDATE 1.0.274 BUILT (Wed 03:30 PT); owner tests
#   Thu 12:00 PT. READ FIRST: docs/SIM-GUIDE-20260901.md (top section =
#   the candidate guide), RULINGS 2026-09-01a..w + 2026-09-02a.
# APP: dist.nosync/XPTerrainBuilder.app 1.0.274 (engine 1.50.1717,
#   embedded==dist verified). A/B: XPTerrainBuilder-1.0.272-roads-only.
# MAIN = the candidate tree. Suite 9,161 pass; red = the 5-airport
#   ACCEPTANCE MODULE only (owner: green-except-acceptance). Sweep:
#   HECA 2,838 KCLT 2,174 SPJC 686 CYXY 153 SPLP 35. Perf exclusive:
#   HECA 756.7 s (−11.9% wk) OTHH 434.0 SPJC 166.9 KCLT 499.7 CYXY 41.4
#   SPLP 9.5 LEMD 573.9 (baseline RECORDED df02d536).
# MERGED THIS WEEK: H1 silent-tile-death (6 paths, protocol 1.7 both
#   sides) · H2/H4/H5/H6/H8 red-zero (17+8+2+5+5 reds; grade_graph crash
#   + census-cache caveat drop + runway_segments midpoint fixes; 08-25
#   c-h rulings reconstructed) · H7 HECA RUNWAY REGRESSION (7786ff0e,
#   writeback preserve; all 5 airports pass longitudinal) · Batch 3
#   tunnels (foot RETIRED 01c, gap 0.6 01e, per-body walls 01j, clip 01h)
#   · Batch 4a ownership + annulus · building split (2b616f73) · air1
#   quantization allowance (01m, moves the metric — STATED) · air6/air7
#   certificate + both-hard instrument · ovfix emit-frame self-overlap
#   (01w, REVEALED double-covers) · weldov re-clip (02a) · FGP S1+S2+S3
#   merged GATE-OFF byte-identical (01v).
# PARKED (branches, unmerged): lane/bldround (full pad law: close
#   retired + frontage + contact weld — blocked on the 08-08 relief
#   class, 01f/01g/01i) · lane/air2 (profile-law ingestion, correct at
#   CYXY, blocked on FGP) · lane/air3 (pass-2 LP, −31 net, 21 NEW —
#   OWNER SIGN-OFF) · lane/air4 evidence merged, mechanism deleted.
# OWNER DECISIONS THURSDAY: (1) air3 sign-off; (2) split-level-seat
#   UN-HOLD (b168 evidence, 01o); (3) post-beta FGP round scope
#   (fgp-single-authority-spec.md — root: the solve's exit does not
#   satisfy the law FGP imposes, 01v); (4) bless-or-remove the
#   +60-136 airport_small_roads cold-cache write (slipped the H3 guard);
#   (5) whole-tile 300 s budget unmeetable while LEMD patch = 574 s.
# CHIPS the owner started (cloud sessions, merge on return): restore
#   road-band-seal spec (task_8b4cf3da); silent mesh-step rc=0 failure
#   (task_9165e4dc).
# OWED: registry-pollution channels (02a, 30l census first); LEMD emit
#   bisect (+25.7 s wk); HEAZ perf; tile-store CLI writer; 231 lane
#   branches + worktrees cleanup; three more phantom specs (25f/g/h).
# LAW THIS WEEK: 31a sim gate/anchored tripwire/redesign threshold;
#   30l consumer census; 01e standoffs-never-on-a-tolerance; 01l zero
#   airside; Fable 5.1 medium for lanes (proved: ~1/3 tokens, same rigor).
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260901a — AWAY-PERIOD CAMPAIGN CLOSED; RETURN PACKAGE READY.
# READ FIRST: docs/SIM-GUIDE-20260901.md (per-site guide + the FOUR
# owner decisions) + RULINGS 31a-31m.
# APPS in dist.nosync/: XPTerrainBuilder-1.0.272-roads-only.app
#   (main: Batches 1+2) and XPTerrainBuilder.app 1.0.273
#   (staging/return: + tunnels/bridges rework, face ownership,
#   annulus fix, building isthmus split). A/B by swapping apps and
#   rebuilding a tile.
# MERGED ON MAIN: Batches 1+2 (core clamp roads, contact model, FRP
#   retired) — sim-adjudicated good (31c) + roads redesign complete.
# PARKED (unmerged, integrated in staging/return only): lane/ltbatch3
#   (tunnels/bridges, 8-9/10 mouths canonical, 31k), lane/ltbatch4a
#   (face ownership -98.4% far rings, annulus closed, 31l),
#   lane/bldround (building100 isthmus split, 31m). Merge on owner
#   sign-off after sim.
# SWEEP (staging, adjudicated): SPJC 1051= SPLP 83= CYXY 176(-23)
#   HECA 3774(-41%) KCLT 3036(-35%, zero KCLT-specific work).
# PERF (exclusive, vs committed d787464 baselines): Batch 2 clawed
#   back 64-73% of the accretion; HECA x2.48, SPJC BELOW baseline;
#   residual scales with road/tunnel population (bisect list in
#   DEFERRED). All airports over the 60s ship-gate budget still.
# OWNER DECISIONS WAITING (evidence in RULINGS): (1) fork pinch wall
#   vs R10-2; (2) BUILDING_OUTLINE_FILL_R 110m closing radius;
#   (3) freed-ground strip meets: terrace or weld; (4) merge
#   sign-offs for the three parked lanes.
# PROCESS: postmortem laws 31a (sim gate, anchored tripwire,
#   redesign threshold) + 30l consumer census are in CLAUDE.md;
#   ledger hash fix means ALL pre-08-31 keys stale (miss = re-run).
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260830b — SIM-READ MEGA-ROUND CLOSED (all lanes merged; owner
# adjudicated ~20 rulings live, RULINGS 29g..30n).
# MERGED TO MAIN this session: chip sweep (4 single-graph reds green);
#   HECA r6/6b/6c + building79 structure-walls + dup-ref fix (cliff law
#   band-cuts-groundside, airside-frozen ramp up-build, sliver width
#   test, gap-fill groundside blocker + veto fix, 8-pad split);
#   LEMD basin twin canyons + building1-7 demotion + T4S ring setback
#   (163 fallout rows -> 0) + ROAD BRIDGE DECK (10 rounds, RULINGS
#   30c/30d/30f/30i/30m/30n; road_bridge_deck.py, 86 twins; span paved
#   by road at 1.9%, bore datum to the deck, census 1758->1723);
#   OTHH canonical mouths + walls-follow-ramp; ledger empty-index
#   hash fix (docs commits no longer poison keys — ALL OLD KEYS STALE,
#   first rerun of each command is a miss).
# NEW LAW: consumer-census before cross-cutting geometry law
#   (RULINGS 30l + CLAUDE.md) — from the 8-round bridge retrospective.
# OWED: five-airport sweep at next app build (29f); item-3 road class
#   + item-4 level + apron-adjacent duplicate walls + OTHH mid_edge
#   density effect + spine-on-groundside 2,492 m2 + roads-annulus
#   class — ALL deferred to owner sim read; G post-mesh re-read;
#   split-producer attribution (elevation phase); ~90 worktrees.
# NEXT: owner builds app, sim-reads HECA/LEMD/OTHH; residuals above
#   adjudicated there.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260830a — HANDOVER (session close mid-round; app 1.0.269 shipped,
# owner testing; HECA round 6 lane IN FLIGHT).
# COLLECT FIRST (this session's notifications die with it):
#   * HECA ROUND 6 — NOT STARTED (owner killed the lane at launch
#     for the session handoff; no branch content): DISPATCH FRESH from
#     spec 70216a48 heca-round6-groundside-classification. 6 owner
#     items — A: groundside classification
#     (shapeID 3151 scorer-v2 severed slivers; 2837/2838 mis-roled
#     aprons + overlaps; taxiway-edge cliff at 30.1125699,31.4053664 —
#     owner asked for the adjacent-ground LAW TEXT confirmation;
#     item-3 road-vs-groundside at 30.1118886,31.4064793); B:
#     building79 one-ring-five-buildings split; C: item-4 ramp level
#     residue. All probes are in the spec; brief per the CLAUDE.md
#     BUILD ECONOMY section.
#   * TWO CHIP SESSIONS the owner started (single-graph reds):
#     same-nodes/spine-step (curved-road rects, attributed 516bba14)
#     and spine-zero/edge-budgets (cross-section law, 3ccd470d).
#     Their fixes land on claude/* branches — MERGE them when done
#     (4 reds in tests/test_single_graph_acceptance are the check).
# STATE: main at app 1.0.269 (engine 1.50.1713, osr warning silenced);
#   test_harness.py fully GREEN (standing red fixed via chip sweep);
#   review-round merges all in (runway strict-claim §1/§2 census OWED,
#   rampsites final site numbers OWED, scorer-v2 in, tunnels in).
# LAW ADDED THIS SESSION (all in CLAUDE.md + RULINGS 29a-f): build
#   economy (synthetic-first, ONE airport, ledger controls), gates are
#   the exception, refuted code DELETED, site-first reporting,
#   below-bar needs owner sign-off, chip branches merge same-day and
#   THE SPAWNER OWNS THE MERGE, no chip-from-chip spawning.
# OWED: retired-code deletion sweep (§H3, 5e-5i freezes, trench arms);
#   3 conflicted chip cherry-picks (6d7a2c0c trace, 5f05f1ca solve_cut,
#   2aa4dd72 dump-guard); rod-clamp f9953d0c review; HEAZ held question
#   4d96a043; 84-row tunnel attribution residue; five-airport sweep at
#   next merged batch; ~90 worktrees cleanup.
# NEXT SESSION: read this block + RULINGS 29a-f + CLAUDE.md BUILD
#   ECONOMY section; collect hecar6 + chips; owner sim read of 1.0.269
#   drives the next round.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260829b (OWNER REVIEW ROUND MERGED; app 1.0.268, engine 1.50.1711,
# embedded==dist verified. Owner-ordered merges with verification cut
# short by spend limits — THE SIM PASS ADJUDICATES.)
# PROCESS LAW (in CLAUDE.md now, 60386e2a+11265a5): 29e gates-are-the-
#   exception (ungated fixes, git revert rollback, refuted code
#   DELETED) + 29f build economy (synthetic-first, ONE representative
#   airport, ledger-shared controls) + invalid-brief clause.
# MERGED: tunneldockets (owner sign-off +164: B2 mouth PASS, drops 0,
#   coverage 90%, foot ON annulus 56->44, 853% cliffs gone);
#   scorerv2 (owner sign-off +14: face-local class-change cuts —
#   back edge 25,900->180 m² airside behind wall, ITEM-4 ROAD CLIFF
#   CLOSES 93->100.2-102.8; CYXY -17, SPJC byte-identical; global
#   dissolve refused at 17,410 m cut line); strictclaim (§1 CAP + §2
#   VALUE at the runway crossing — site fix confirmed on valid frame,
#   census PENDING); rampsites (weld-outranks-cap per-span, road chord
#   both directions, cumulative cap-distance ON; item-4 post-resolve
#   exemption named but OFF on measured regression; refuted arms
#   deleted). 118 merged twins pass.
# RULINGS 29c contact=value (canon); 29d scorer-v2 approved.
# OWED: strictclaim census; rampsites guard-blocked-write attribution
#   + site numbers in final config; scorerv2 repro_cut fixtures +
#   build-time; retired-code deletion sweep (§H3, 5e-5i freezes,
#   trench arms); 84-row tunnel attribution residue; five-airport
#   sweep AT THIS APP BUILD (29f) not run — owner ordered build now.
# NEXT: owner sim pass on 1.0.268 (runway pit, ramps at per-span law,
#   apron back edge, tunnels); Opus spend limit resets Aug 31 9am PT.
# 20260725 — DSF ENCODER: PREMISE CORRECTED + WRITE LOOPS VECTORIZED
# ══════════════════════════════════════════════════════════════════
# (branch claude/hopeful-liskov-9b8713)

## Premise correction (evidence: XPTerrainBuilderData/Ortho4XP.log,
## ~/.ortho4xp/tile_build_times/+30+031.json)
The "build_dsf takes ~16 min on +30+031" claim was a MISATTRIBUTION.
 * Step 3 (all of build_dsf) took 24 s / 27 s in both full Cairo app
   builds on 2026-07-25 (09:51, 15:34). From source with warm caches,
   build_dsf on the real (Step-1-stage, 356 k-node) mesh is ~4.6 s.
 * The 906–922 s (~15.4 min) single-thread step is the MESH step; that
   is what "16 min at 99 % CPU" was. Auto-patch vector was 515–700 s.
 * The 35 MB DSF = GEOD 19.4 MB + CMDS 15.8 MB (~1.3 M nodes), no DEMS
   raster. The "20× per byte vs synthetic" figure died with the 16-min
   number.
 * Cold-cache caveat: first build_dsf after an OSM-cache flush spends
   ~30 s in ensure_bathymetry_band (network + pyosmium) even for a
   no-shoreline tile.
 * CONSEQUENCE for the <5 min/tile budget: the targets are Step 2
   (mesh) and auto-patch, NOT the DSF encoder. Plan item (C)
   (triangle-loop constant factors, worth ~1–2 s) dropped.

## Landed: (B) vectorized GEOD pool + CMDS PATCH-TRIANGLE writes
 * src/O4_DSF_Utils.py: per-word struct.pack loops replaced by numpy
   views (`_patch_triangle_commands`, pool column writes, cross-pool
   remap LUT). Encode-write section 0.68 s → 0.06 s at 356 k nodes
   (~11×; ~2.5 s saved at full 1.3 M-node scale).
 * BYTE-IDENTICAL verified three ways: real +30+031 A/B (cmp, stock
   c2c46a2 vs edited, 8,886,288 B), synthetic-tile A/B vs pinned
   c2c46a2, and a chunk-boundary property test vs a struct reference
   (tests/test_dsf_encoding_vectorized.py, 25 tests). Full DSF suite:
   131 passed, 3 pre-existing skips.
 * NOTE: tests/test_dsf_texture_modes.py::test_full_ortho_byte_identical_
   to_base has been silently SKIPPING everywhere — its pinned commit
   26ea8ee does not exist in this repo and its `git show` path lacks
   the Ortho4XP/ prefix. Not touched here (it pins a different
   feature's baseline); worth a follow-up.

# ══════════════════════════════════════════════════════════════════
# 20260725 — RUNWAY-END + POCKET + OLS ROUND: HANDOFF
# ══════════════════════════════════════════════════════════════════
# Everything is UNCOMMITTED in the working tree. Six gates are default ON
# by owner ruling ("Turn them all on now, I will test in X-Plane").
# BOTH BLOCKERS RESOLVED 2026-07-25 PM (supervised session, Fable lead +
# Opus implementers) — owner is UNBLOCKED for in-sim testing.

## THE TWO BLOCKERS — BOTH FIXED (details below, originals kept for record)

### B1 FIXED — collared pockets now stand the adjacent-ground bands down
Ruling taken: candidate (a), via the CROSSING-INFLUENCE-ZONE pattern (a
published non-shape zone), NOT by unioning the pocket into `static_union`
(which would have fed `_split_zone_rows_off_static` and evicted zone rows).
 * `gap_fill.collared_pocket_zone_union/_prepared` — union of
   `pocket_collars` pockets whose rings ACTUALLY emitted (`chains > 0`;
   an economy-skipped collar keeps its bands — verified `chains` is the
   faithful emission key).
 * `adjacent_ground`: station-level stand-down in `_station_reference_ex`
   (reason "collared_pocket", ALL families, not taxiway-only like the
   crossing zone) + ZERO-buffer polygon clip block (weld ruling: exact
   geometry, no standoff groove). Per-part bbox pre-filter keeps the cost
   at ~35 ms/airport (raw predicate measured 450 ms — 75 % of the 1 %
   HARD-LAW threshold; the guard is semantically exact and test-pinned).
 * `verification`: MIRROR 4 in `_adjacent_ground_stations` (lockstep) +
   NEW invariant `check_collar_ring_band_overlap` (STRtree, band eroded
   1 cm; counts key `collar_ring_in_band`) — the check that would have
   caught B1; there was previously NO collar×band assertion anywhere, and
   MIRROR 3 actively hid the symptom.
 * Emit ordering was already sufficient: collar (pipeline ~6666) runs
   before bands (~6717); with shipped gates the emitter RE-MARCHES inline,
   so the zone is visible. The presolve construct march CANNOT see the
   collar (needs solved pavement altitudes) — the clip block is what
   protects the frozen-footprint gate state.
 * SPJC end-to-end: 2 pockets → 364,240 m² zone, 1,026 stations stood
   down, overlap invariant = 0 findings. +13 tests.
 * No new gate: collar off ⇒ no zone ⇒ bands byte-identical.

### B2 FIXED — weld-inserted T-vertices now bounded by the cut law
HYPOTHESIS REFUTED (there is no `_build_cut_bands`; the emitter is
LAWFUL — all 24 SPJC RESA vertices at min(ceiling, DEM) at emission).
Real mechanism, proven by per-pass attribution: the final epsilon-wedge
weld `enforce_conformance` (pipeline ~6811) inserted T-vertices (n=24→32)
valued by PLAIN LERP (conformance.py "3. plain lerp"); on the RESA
outer/daylight row both hosts are ceiling-limited so the lerp IS the
analytic ceiling, floating +2.12/+2.22 m over a DEM depression between
stations. Donor-adopt and overlay-donor paths both structurally
unreachable for this ref.
 * FIX: `enforce_conformance(dem=, tile_lat=, tile_lon=)` (same trio the
   clearance/OLS emitters consume; DEM parity verified — `_projection_*`
   at the call site are the exact objects handed to the emitters). Inserts
   into CUT-ONLY receivers (`ref runway_end_resa`, roles
   `runway_clearance`/`ols_cut`; fill-only ref `runway_end_skirt` VETOES)
   are bounded min(value, DEM) as a FINAL bound after any valuation path —
   the receiver's OWN law re-applied, so the coincident-adopt
   value-authority guard stands. Gate `O4_CONFORMANCE_CUT_CLAMP` default
   ON, off ⇒ byte-identical. ~0.5 µs/insert. +8 tests
   (tests/test_conformance_cut_clamp.py).
 * ★ KNOWN LIMITATION LEFT ON RECORD: the RESA outer-row SURFACE between
   stations still floats above terrain where daylight distances jump
   (SPJC 16R: chords +2.65 m / +2.28 m worst over ~60 m spans at
   140→120→60→6 m daylight steps) — the vertex clamp cannot fix polygon
   interiors. If the owner sees a floating wedge near 16R in-sim, the fix
   is densifying the outer daylight row in `_build_graded_strips` (the
   flank discontinuity-split pattern at clearance.py ~3205) — touches
   every graded strip, needs build-time evaluation. Do NOT lift the outer
   row to max(ceiling, DEM) — part 30f tried and reverted it.
 * Separate defect spawned as chip: the weld can insert DUPLICATE
   T-vertices at identical coords (SPJC #26/#27, zero-length edge).

## LANDED THIS ROUND (all uncommitted, all in the working tree)

Origin: two owner in-sim defects at SPJC.
 * 16R end had NO RESA anywhere — Pass C has not run since the B4 flip
   (2026-07-15) gated the legacy clearance chain off; the skirt is
   FILL-only by ruling; `adjacent_ground_envelope` declines runway ends.
   Measured: 138/1829 corridor samples breach the 5 % ramp, worst +6.76 m.
 * Five owner coordinates were ring vertices of ONE 158,651 m² flat
   `gap_pit_floor` plateau standing ~3 m proud of the taxiways on an 8 m
   axis-aligned sample staircase.

ARC A (runway ends)
 A1 `grade_law.runway_end_envelope` — ONE law, BOTH bounds (skirt floor +
    RESA ceiling). `runway_end_corridor_half_width_m`. Two pure lockstep
    helpers: `adjacent_ground_end_pin_flags`, `runway_strip_band_width_m`.
    `verification.check_runway_end_skirt` now two-sided (`end_rise`).
 A2 RESA cut inside `clearance.emit_runway_end_skirts` (NOT by reviving
    the legacy chain), ref `runway_end_resa`, cut-only `min(ceiling,DEM)`.
    SPJC 16R: 1 shape, 5652 m². CYXY 3/12226 m². HECA 1/37329 m².
    SPLP correctly silent.
 A3 end-skip bench pin — the 16R west wing no longer collapses
    diagonally; depth over the last 60 m went 57.5/52.5/120.5/60.4 ->
    206.9/226.8/246.0/229.6.
 A4 runway strip width from the CENTERLINE. NOTE: A4 clamps the **FILL
    ONLY**. Clamping the cut erased zone 3 (ICAO §3.4.16 governs the
    ungraded strip out to the FULL strip edge) — that was a functional
    regression, since corrected.
 + `Runway.published_width_m` / `.declared_width_m` (UNGATED): `pipeline`
    overwrites `width_m` with runway+shoulders (SPJC 45->81 m) and that
    was feeding Annex 14 §3.5.3's "twice the runway width". Corridor now
    sizes 75 m not 81 m. **The only ungated behaviour change this round.**

ARC B (enclosed pockets)
 B1 collar rings for width-skipped pockets (`O4_POCKET_COLLAR_RINGS`).
 B2 pit floor v2 — local ring-2 reference, sloped, daylight rim, welds.
 + OWNER RULING 2026-07-24: `GAP_FILL_INTERIOR_FLOOR_ENABLED` **default
   OFF** — "once we're past the grade law zones on a large infield, we
   want to blend back into DEM". This RESTORES the round-8 design ("Terrain
   INSIDE ring 2 stays open-floor"). It DELETED the planned pit-clip-truth
   slice (no pit ⇒ no pit rim ⇒ no pit-rim/collar-chain slivers) and more
   than doubled drainage-rim coverage (weighted mean 8.6 % -> 18.3 %,
   bands 244 -> 300). HECA's artifact pits now ride raw DEM; if that
   matters the answer is an ENCLOSURE test, not flipping the gate back.

OLS ARC (docs/specs/obstacle-limitation-surfaces-spec.md, new)
 Law + constants + STANDARDS rows; new `src/auto_patch/ols.py` (vectorized
 raster pre-scan, island labelling, mountain refusal, banded cut emission);
 `verification.check_ols_surfaces`; pipeline wiring; snap + decimation;
 cross-tile seam determinism (boundary-touching islands refused whole).
 Scope ruling: ONLY transitional + approach-first-section, cut-only.
 Inner-horizontal/conical REFUSED as cuts (they decapitate every hill
 within 4 km above +45 m — at SPLP a mountain range).
 ★ ROAD/RAIL/WATER MASK ADDED 2026-07-25 (owner report): `ols.py` had NO
   infrastructure handling — the only terrain law in the subsystem that
   ignored it. Now masks `clearance._surface_road_corridors`, the skirt's
   own source. WHY IT CANNOT BE DEM-DETECTED: the airport-smoothed DEM
   does not CONTAIN the road cut — a transect across a cutting 210 m off
   the 16R end reads 12.91-13.26 m FLAT over ±80 m. The law lawfully cut
   13.19 -> 9.60 m, which sits above the real deck and reads as a fill.
   Sampling harder cannot fix it; only the vector corridor knows.

ARC R (owner ruling: the end envelope is law the SOLVER enforces)
 RESA cut admitted to the terrain graph as a one-sided interval edge.
 Measurement that settled it: the anchor is NOT the CIFP threshold, it is
 the pavement-EXIT elevation, and it MOVES — 212 reads, 106 numeric ones
 drifted median 0.110 / p90 0.150 / max 0.164 m, 88/106 over 0.05 m; the
 other 106 returned None pre-solve. Crown is the 0.15 m mode.
 Also fixed a REAL pre-existing bug: `_fair_ring_edges` faired cut rings
 and dragged a shared pavement node 2.1 m.
 ★ STOP CONDITION HIT AND RESOLVED: CYXY end 1 moved +1.68..+7.47 m —
   NOT coupling; a degenerate end whose outward march never exits pavement
   (`pavement_beyond_end` 297 m, governed 0). Lead added a no-pavement-exit
   guard: no exit ⇒ no end zone ⇒ no cut, matching the fill which already
   vanishes there by law.

OPT-1 (from the mandatory Fable-5 build-time review)
 `gap_fill._point_interval`/`_spine_interval`/`_freeze_spine_parent_specs`
 brute-force airside scans -> STRtree prefilter + hoisted exteriors +
 radius doubling. Byte-identical (6/6 empty diffs). HECA gap passes
 15.9 -> 2.4 s gate-off, 21.7 -> 3.0 s gate-on. The collar's marginal cost
 went +5.8 s -> +0.6 s, and the SHIPPED path gained 13.4 s at HECA.

## TEST STATE
Pre-flip baseline: 8 failed / 3170 passed / 36 skipped / 7 xfailed.
The 8 are long-standing: test_msfs_xplane_pack dsftool round-trip,
test_compare_target SPLP+SPJC, test_pavement_grade ×4, no_self_overlap[CYXY].
GATES-ON run: 16 failed. Lead has since fixed:
 * `ols_cut` added to `verification._NON_SOURCE_PAVEMENT_ROLES` (a new
   role must be enumerated at EVERY role-keyed site — it was wired into
   SOFT_RECEIVER_ROLES/AEROWAY_FOR_ROLE/ROLE_GRADE_LIMITS and not there).
 * `tests/test_terrain_role_admission.py` now drives from a complete
   `_SUBGATES` list + `test_subgate_list_is_complete` guard.
REMAINING gates-ON failure to fix: B2 above. **RE-RUN THE FULL SUITE** —
it has not been run since those fixes.
★ RESOLVED 2026-07-25 PM: full suite run TWICE through the ledger.
Pre-fix gates-ON baseline: 9 failed / 3172 passed (the 8 long-standing +
B2). Post-fix: **8 failed / 3196 passed / 34 skipped / 7 xfailed** — the
8 long-standing only; +21 new tests green, B2's envelope test green.

## QUEUED, NOT APPLIED
Fable ruling on `_fair_ring_edges._SKIP_ROLES` (full text in the session
transcript): ENDORSE the role-level skip — add ROLE_RUNWAY_CLEARANCE,
ROLE_GRADED_STRIP, ROLE_OLS_CUT to `_SKIP_ROLES`, KEEP the node-level
`skip_nodes` (they cover different classes), no gate. Measured 9 fairing
executions × 3 airports, 35,000+ candidate triples, ZERO accepted,
counterfactual delta 0.0 m on every node — a model correction, not a
behaviour fix. Landing protocol wants a byte-level A/B across CYXY, SPJC,
HECA, SPLP, KCLT, MMOX + one `O4_LEGACY_SURFACE_CLEARANCE=1` CYXY run;
**a diff anywhere is a live pavement-drag defect in HEAD, not a
regression of the change.** Not applied because the owner is mid-test.

## OTHER OPEN ITEMS
 * ★ RESOLVED 2026-07-25 PM: SPJC (76.97 s) + HECA (341.42 s) baselines
   recorded in tools/build_time_baselines.json (clean 2-run pairs, spreads
   0.7/0.6 s; checker PASS — SPJC under the existing 90 s approval
   ceiling). HECA's morning 409-487 s store records were contended junk.
 * ★ RESOLVED 2026-07-25 PM — OLS forced re-bake TRIANGLE CHECK run at
   tile -13-078 (SPJC+SPLP), O4_OLS_CUT A/B + byte-identical control:
   +146 tris tile-wide (+0.068 %), +168 in the SPJC bbox, all on the OLS
   fans, densest cells identical, no sliver/epsilon class. PASS — not a
   gate. Side effect: Tiles/zOrtho4XP_-13-078 + Patches are now a FRESH
   gates-on forced re-bake (the 08:17 artefacts predated the flip).
   Pre-flip mesh/patch preserved in the session scratchpad.
 * ★ OLS BUILD-TIME (HARD-LAW Fable-5 review, 2026-07-25 PM): an initial
   contended A/B suggested +7-8 s at SPJC — CONTAMINATED (the ON runs paid
   an ~8 s stale pavement-pack sidecar-cache rebuild the OFF run didn't,
   inside a 2-worker tile build). Clean interleaved fresh-interpreter A/B:
   OLS-on delta +0.2-0.5 s at SPJC (median 77.13 -> 77.56), ~0.0 at HECA
   (zero admitted penetrations — pre-scan exits in ms). UNDER the 0.6 s
   trigger; gate stays ON as shipped. Profile: 0.20 s in-pipeline, ~0.12 s
   of it rebuilding `clearance._surface_road_corridors` (built 3×/build —
   skirt ×2 + OLS ×1). QUEUED NEXT OPTIMIZATION ROUND: memoize the road
   corridor union per layout (~0.24 s back, OPT-1-class duplicate-work
   win). MEASUREMENT LESSON for the file: sidecar-cache staleness books
   ~8 s into "Assembling pavement" and reads as a feature regression —
   check the cache STALE/read log lines before attributing any phase-2
   delta.
 * SPJC builds are NOT run-to-run deterministic — two gates-off builds in
   one session, same DEM state, gave 906 vs 911 shapes and moved a finding
   0.115 m. Any cross-build A/B needs a control build. This undermines
   several of this round's A/B deltas.
 * `driver.py` calls `verify_and_log(source_runways=None)`; the lead added
   `layout.apt_runways` + a fallback so the caps mirror measures the real
   centreline. Threading `source_runways` properly is still cleaner.
 * Emitter snapshots gates into module locals at import
   (`AG._END_PIN` etc.) while the validator reads config at call time —
   equivalent in production, but a test must flip BOTH. Worth unifying.
 * `emit_decimate` collinear-span split: two independent sessions produced
   fixes. The MAIN-tree one (split at the arc-length MIDPOINT) was kept
   and the greedy worktree one REMOVED, because greedy-from-one-end is not
   orientation-independent: on a span whose length does not divide evenly
   it keeps 7 nodes but two abutting rings tracing it in opposite
   directions disagree, and the unanimity vote keeps the UNION — 24 nodes
   vs the midpoint version's 18, plus broken chain identity.

## GATE STATE (all six flipped ON 2026-07-25 by owner ruling)
 O4_RUNWAY_END_RESA, O4_ADJACENT_GROUND_END_PIN,
 O4_STRIP_WIDTH_FROM_CENTERLINE, O4_POCKET_COLLAR_RINGS, O4_OLS_CUT,
 O4_ONE_SOLVE_TERRAIN_RUNWAY_END_RESA.
 Every arc was proven byte-identical gate-off at landing, so setting any
 ONE env var to 0 isolates that arc cleanly.
 + SEVENTH GATE added 2026-07-25 PM: O4_CONFORMANCE_CUT_CLAMP (B2 fix,
 default ON, off ⇒ byte-identical pre-fix weld). The B1 fix carries NO
 gate of its own — O4_POCKET_COLLAR_RINGS=0 removes the collar AND the
 zone together (byte-identical bands).
 DELIBERATELY OFF: O4_GAP_FILL_INTERIOR_FLOOR (owner ruling, above).

## BUILD ARTEFACTS
 ★★ CURRENT: App 1.0.200 / engine 1.50.1640 at
 dist.nosync/XPTerrainBuilder.app — the ROUND IS COMMITTED (3cdc8a3 on
 main, 45 files) plus the three chip fixes: conformance insert dedupe
 (_radius_index, was already swept into 3cdc8a3 — the chip edited the
 main checkout), the _resolve_yielding_tjunctions/_resolve_edge_crossings
 dedupe guards (same), and the _surface_road_corridors per-layout memo
 (merge 1b117a0 — all 4 call sites incl. OLS hit the cache, ~0.24 s/
 airport back). Post-merge suite: 8 failed / 3202 passed (the 8
 long-standing only). Freshness VERIFIED (auto_patch.ols in the frozen
 module table, engine version bumped) + direct-exec launch OK. All gates
 at defaults (the O4_POCKET_COLLAR_RINGS=0 workaround is OBSOLETE).
 (Prior stamp: 1.0.199 / 1.50.1639, uncommitted-tree build, superseded.)
 (Superseded stamp for the record: 1.0.198 / 1.50.1638 predated the
 fixes. Rebuild procedure, unchanged:)
   scripts/make_engine.sh   (redirect, NEVER pipe — pipefail + an early
                             closing pipe kills it silently at exit 141)
   scripts/make_app.sh release
 Verify freshness: `auto_patch.ols` must appear in the frozen module table
 (`strings`/`grep -a` the Engine binary). A plain grep of the bundle for
 source symbols proves NOTHING — the modules are in a compressed archive;
 a control with pre-existing symbols comes back absent too.
 macOS: direct-exec Contents/MacOS/XPTerrainBuilder first — the first
 `open` of a fresh bundle can hang in LaunchServices.

# ══════════════════════════════════════════════════════════════════
# 20260718 PM — ≤60 s PROGRAM RETROSPECTIVE + TRACK BOARD OPENED
# docs/build_time_program_board.md = cross-session continuation point
# (measured state, 4-audit retrospective condensed, track table T0-T7,
# verification discipline).  Headlines: ★store UNDERCOUNTS ~40 s
# (record_build before late FGP — fix in flight, chip session; OTHH
# true ≈382 s); ★late FGP defers ~nothing because snapshot never
# recaptured post-mid (T1a in flight); ★wave-2c coloring recomputed
# 9-12×/build + quadratic at hubs, ~32 s overhead (T2a in flight,
# byte-identical); ★wave 3 = 1 lever of 4 at 1 site, Θ(n²) intact
# (T3a in flight); ★Tier 2 structurally NEVER fires at OTHH → owner
# ruling needed (T7); ★remaining planned work alone lands 150-180 s,
# NOT 60 — T4 pair-generation collapse + T5 never-planned emitters
# required.  Profiler phase-boundary drift fixed (b1315e0).
# ══════════════════════════════════════════════════════════════════
# 20260718 — BUILD-TIME BASELINES REFRESHED POST WAVES 2c+3
# tools/build_time_baselines.json re-measured at dev 0834fef (includes
# projection-wave2c + geometry-wave3 merges): CYXY 40.6 s (was 43.4),
# OTHH 343.4 s (was 365.8).  Cold-equivalent per the checker docstring:
# one warm-up full build per airport, then fresh-interpreter measured
# run via check_build_time.py --run --update-baselines.  Preconditions
# verified (no concurrent builds; OSM regional extracts + Elevation_data
# present).  tests/test_check_build_time.py 27 green; standalone
# check_build_time.py PASS.  OTHH remains over the 60 s airport budget
# (approvals file still empty — pre-existing state, improved this round).
# ══════════════════════════════════════════════════════════════════
# 20260718 EARLY AM — TWO SUPERVISED AGENT LANDINGS INTEGRATED
# (same session as the EGGW tunnel fixes below; all uncommitted):
# 1. RIGID-SEAT SPAN LIMIT (EGGW floating buildings FIXED):
#    DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M=3.0 — a Phase-2 structure whose
#    ground span exceeds it (and has no anchored feet) is LEFT AT
#    AUTHORED ELEVATIONS (skip_reason "…rigid-seat limit…"); its
#    buildings ride their Phase-1 pads.  ★Stale-bake restore already
#    existed (object_rebake reversion pass un-bakes undecided
#    resources vs .anchor_bak) — skips route through it.  EGGW: both
#    mega components skip; EGLL: only 4 new skips, all >3 m.  LEAD
#    RULINGS: A3 bake-and-flag SUPERSEDED (test renamed/flipped);
#    KCLT end-to-end allows span-reason skips (3/220, spans
#    3.46-4.22 m — USER: spot-check KCLT terminal in-sim).
#    tests/test_object_bake_span_limit.py (7) + object suite 183 green.
# 2. FEATURE A TUNNEL CARVES (W-T) BUILT — GATE DEFAULTED **ON**
#    (user ruling 2026-07-18; also ruled: trench depth authority =
#    the OBJECT'S OWN GEOMETRY, author mesh was oracle-only).  230
#    object tests + compare-target green at ON; ★rebuild +43-080
#    with O4_AUTO_PATCH_REBUILD=1 to get the CYYZ cut (freshness
#    gate ignores code changes).  Chips running in cloud sessions:
#    node_altitudes loss root-cause; flat-fast-path refusal role.
#    (O4_OBJECT_TUNNEL_TERRAIN): whole-body trench pans (A1) + rim
#    collars born at layout from classification.tunnels; pavement wins
#    (R2/R8, yielded area logged); ROLE_TUNNEL_TRENCH = LAW weld tier
#    + decimation exemption + force_per_node.  ★MEASURED DEVIATION
#    FROM R12 (lead-accepted): trench pins must NOT join solver
#    PAVEMENT_ROLES — coupling dragged 30% of EGLL airside pavement
#    down (max 8.3 m); shipped decoupled (pavement neutrality 0.004 m
#    mean).  EGLL oracle: substantial tunnels within ~±1 m of the
#    author mesh (−0.5 m by design); tunnel 5 under pavement → not cut;
#    9/12 shallow (OBJECT under-specifies author — open Q1).  EGGW
#    byte-neutral.  CYYZ: taxiway tunnels = Feature-B BRIDGES; one
#    Feature-A cut (Terminal-1, 2.46 m = expected).  BEFORE DEFAULT-ON:
#    rule open Q1 (object-vs-author depth); verification.py lockstep
#    validator; rule enclosed-terminal parts (A vs C/R10);
#    ROLE_TUNNEL_TRENCH into flat_airport_fast_path refusal roles.
#    tests/test_object_tunnel_terrain.py (15).
# ALSO: EGWN int64 solver fix cherry-picked (d89b155c, user's cloud
# session).  ★Pre-existing red: test_contracts::
# test_object_geometry_fields (another session's draped_layer_group
# field in obj8_reader — not ours).
# ══════════════════════════════════════════════════════════════════
# 20260717 EVENING — EGGW TUNNEL FIXES (separate session; BUILT +
# mesh-verified at EGGW, uncommitted):
# 1. `unclassified` added to HW_TUNNEL_TYPES (bridges.py) — EGGW's
#    airside tunnel (ways -232502/-22713, highway=unclassified
#    tunnel=yes) was invisible while service/residential qualified.
#    ★_load_tunnel_road_network ALREADY merges small_roads (KPHL);
#    the class filter was the real gate, and mapped unclassified
#    tunnels keep their MAPPED ends (re-split set = major classes).
# 2. DEM-CUT PORTAL MODE (user ruling: what a tunnel ramp needs
#    DEPENDS ON THE MESH): with a lidar inset the bare-earth DTM
#    already carves the approach ramps AND strips the structure over
#    the bore (open trench under the taxiway).  Detection = median
#    CROSS-ROAD relief (deck beside the walk minus walk) ≥ 3 m over
#    the first 60 m — ★never absolute-vs-apt_elev (its mid-field
#    fallback samples the trench floor itself: measured apt_elev ==
#    cut_min at EGGW) and ★never DEM-vs-surroundings (false-fires on
#    hillside bores, KPHL class).  Cut mode emits ONLY: flat cap at
#    the measured cross-road deck grade, 6 m mouth plate at the DEM's
#    own road grade (crisp face wall), and a GRADED roof-quad chain
#    (4-corner sloped rects, ramp-chain corner convention) from
#    face-top grade up to the pavement-seam deck — NO synthetic
#    ramps/walls/throat ("no tunnel ramp around the parking garage").
#    Flat-DEM airports keep the legacy path byte-identically; env
#    gate O4_TUNNEL_DEM_CUT.  ★★Post-solve plates: way-level altitude
#    and 4-corner altitude_high/low reach the mesh; per-vertex
#    node_altitudes measurably LOSE most values en route to the
#    written patch (mechanism un-root-caused — chip spawned; owner
#    prefers per-corner once fixed).  ★Roof chains truncate at the
#    bore MIDPOINT (a full-bore plate put the partner cluster inside
#    "an emitted portal's exclusion zone" — silent drop), emit ONLY
#    from the clear-line piece CONTAINING the member's own face
#    (nearest-piece fallback wandered onto the taxiway mid-body),
#    and the mouth plate = cluster rect MINUS the roof union (roof
#    wins in the twin-carriageway stagger zone).
# 3. PORTAL-FACE records (object_terrain_features.py): single-
#    placement all-SOFT ≤8-tri quads hanging below grade (min y ≤ −2,
#    top ≤ +1, height ≥ 2, rect long side 4-60 m) = the EGGW portal
#    authoring class; finds EXACTLY the 2 real portals in 614 pack
#    objects.  ★A face is NOT ⊥ to the tunnel axis (parallels the
#    crossed taxiway edge) — face pairs test mutual parallelism +
#    segment-crosses-face.  Faces join R4 exclusions always (the
#    y-bake would shove a hanging face up by its height).  Pairs
#    corroborated by a mapped OSM tunnel are SUPPRESSED (OSM owns —
#    fires at EGGW); object-only pairs ride the KBNA portal branch
#    with the ANCHOR-SEAT INVERSION (anchor disk joins the deck-grade
#    crown, never the road-grade mouth).  Cache bumps:
#    _CLASSIFICATION_CACHE_VERSION 3→4, _OBJECT_FOOTPRINT_CACHE 1→2.
# 4. Tests: tests/test_tunnel_dem_cut_portals.py +
#    tests/test_portal_faces.py (25 new, Opus-authored); compare-
#    target fixtures byte-stable; 166 tunnel/bridge tests green.
# 5. MESH-VERIFIED (tile +51-001 vector+mesh rebuilds into repo
#    Tiles/ dir — ★run_tile_mesh_only builds into Tiles/, the user's
#    flyable scenery lives on ThunderBlade): tunnel body graded
#    155→157.7 with face walls at both mouths; approaches track the
#    lidar within 1.5 m (untouched).  Sampler:
#    scratchpad verify_tunnel_mesh.py (session 20260717 evening).
# 6. ALSO: EGGW floating buildings root-caused (NOT fixed): two
#    chained mega components (fences/cars/barriers chain 55+44
#    resources, 3.1/2.6 km) → area backstop kills their pads but
#    Phase 2 still bakes ONE rigid offset → +33 m floats.  Fix
#    direction = fill-aware span gate / connector partition.
#    EGLL: Feature A tunnel EMISSION never built (agent-verified;
#    classification.tunnels feeds one log line; W-T inventory in
#    session report).  EGWN solver int64 crash = pre-existing,
#    spawned as separate task.
# ══════════════════════════════════════════════════════════════════
# 20260717-18 OBJ8 GROUND-PAINT PAVEMENT (separate session — feature
# BUILT; OWNER RULED 2026-07-18: DEFAULT ON for in-sim testing.
# HECA builds now gain +4.05 km2 pavement — expect
# test_pavement_grade[HECA] failure content to shift (pre-existing
# red either way) and HECA compare-target drift until fixtures are
# re-cut after the in-sim verdict):
# Packs like HECA Tai Models draw base pavement as DRAPED-ONLY .obj
# texture pages (asphalt.obj = 31k draped vertices, zero solid tris)
# invisible to both the building path and the .pol pavement reader.
# NEW: obj8_reader parses ATTR_layer_group_draped;
# dsf_reader.read_dsf_object_pavements admits draped-only objects
# declaring layer group runways/taxiways at offset ≤1 (base pavement
# stacks UNDER markings — the pack's own rendering contract is the
# base-vs-decal discriminator), unions their draped triangles into
# patches (all patches, holes honoured), chains them through the ONE
# existing DSF pavement sweep (same gates, third-party marked),
# sidecar-cached (o4_object_pavements_*).  24 tests
# (test_dsf_object_pavement.py) green.  Gate O4_DSF_OBJECT_PAVEMENT
# **DEFAULT OFF pending owner ruling** — suite untouched at OFF.
# HECA law-true A/B (axes-sidecar check_grade): +4.05 km² pavement,
# within-shape 30→3 (fixes 27/30 tracked frontage flags!) BUT
# test_runway_longitudinal_grade[HECA] GREEN→RED (the one genuine
# new regression, un-root-caused; 3 runway-end-skirt violations at
# the low end are the lead), TEAR 0→6, CROSS 0→3, mid-edge 0→55,
# retaining walls 21→332 (perimeter sheets over desert relief).
# OWNER RULED: NO airside/groundside split — object pavement rides
# the same union/slicing as .pol pavement, existing perimeter
# treatment stands.  LONGITUDINAL REGRESSION ROOT-CAUSED + FIXED:
# MID final_grade_projection writeback aliasing — the runway's
# beyond-threshold blast-pad corner (hard 57.56 through the whole
# solve, probed clean) aliases via get_or_add on post-densify
# geometry to the new terrain-pressed junction's soft node and gets
# stamped 55.31 (1.8% end kink); later passes re-seed the corruption
# as hard truth and the LATE run's RUNWAY PROFILE PRESERVE restores
# it verbatim.  FIX = the preserve snapshot/restore made
# UNCONDITIONAL in final_grade_projection (was late-run-only) —
# runway nodes are hard through the projection by design, so the
# only writeback-changeable runway values are aliasing corruptions.
# VERIFIED: gate-ON longitudinal[HECA] RED→GREEN; gate-OFF
# longitudinal[HECA/SPJC/CYXY] all stay GREEN (baseline undisturbed).  ★PROCESS: check_grade CLI
# without <patch>.osm.axes.json (written only at O4_LOG_VERBOSITY>0)
# over-flags 17,092-vs-3 on the same patch — never read grade
# numbers off a sidecar-less run.  ★DEBUG: coordinate-keyed
# class-level BuiltShape.__setattr__ watchpoint with stack capture =
# the tool that found the writer (index-keyed and single-object
# watches both false-negatived).
# ══════════════════════════════════════════════════════════════════
# 20260717 NIGHT ADDENDUM (after the wave-2 section below; three
# further landings, all verified):
# 1. 05L/23R KINK FIX (late-projection WRITEBACK ALIASING): two runway
#    ring vertices under the 0.5 m canonical tolerance alias to ONE
#    grade-graph node; the late projection holds it hard but its
#    _writeback re-stamps BOTH ring vertices with the one value
#    (60.46→60.70, a 3.7% profile kink at HECA).  Fix = RUNWAY PROFILE
#    PRESERVE (solve.py): late run snapshots runway/runway_crossing
#    altitude fields pre-projection, restores post-writeback.  HECA
#    longitudinal test GREEN; SPJC all-zero.  ★WATCH: the same
#    writeback aliasing exposure exists for ANY sub-tolerance vertex
#    pair on any shape in the late run — fixture airports empirically
#    clean, runway was the datum-critical case.
# 2. OBJ8 MEGA-PAD FIX (user in-sim reports EGGW/EGLL/HECA — giant
#    building pads + buried EGLL tunnels):  co-baked packs' connector
#    meshes (2.7 km fence, road/rail, NEN ground slabs) chain real
#    buildings into airport-scale components at the contact-epsilon
#    partition; convex hull fills the field.  OSM extracts REFUTED as
#    cause (sane data, DSF-preferred wins).  SHIPPED:
#    DSF_OBJECT_MAX_FOOTPRINT_AREA_M2 default 0→100000 (area backstop)
#    + sidecar-cache fingerprint now includes the gate constants (was
#    silently serving stale geometry).  EGGW 10→39 buildings, EGLL
#    tunnels un-buried, HECA 1.94M m² pad gone (338→487 buildings),
#    SPJC's own 371k LIMANUEVA mega dropped (55→65 seeds, grades 0).
#    IMPLEMENTED BUT DEFAULT-OFF pending owner ruling: connector
#    pre-filter (span 300/fill 0.20 — texture-page .obj packs defeat
#    the fill heuristic: EGGW 39→6) and structure span gate (500 m —
#    kills SPJC's real 560 m banner-inflated terminal).  Residual
#    sub-backstop spanners: EGLL 88k/1076 m + 87k/654 m, HECA
#    46k/601 m.  OWNER RULED 2026-07-17: option (b) ACCEPTED — ship
#    the backstop alone; fill-aware span gate = designed follow-up.  321 object-pipeline tests green.
# 3. HECA within-shape rose 14→30 WITH the object fix — NOT a
#    regression: 149 newly-revealed real building pads carry the known
#    frontage-flag class (terminal-8); TEAR/CROSS/steps stay 0.
# 4. Compare-target fixtures RE-CUT a second time same day (after the
#    object fix; SPJC building 57→60, total 775; SPLP tiles
#    unchanged); floors updated in test_compare_target.py.
# 5. FINAL SWEEP RESULT (six suites × four airports, -n0,
#    PYTHONHASHSEED=0): ONE red left — test_pavement_grade[HECA]
#    (terminal-8 apron-bridged-terminal class, ~30 building frontage
#    flags after the object fix revealed 149 real pads; TEAR/CROSS/
#    steps 0).  Everything else GREEN or tracked: compare-target green
#    on the fresh fixtures, SPLP route-band XPASS→now gates hard,
#    CYXY building19 floor re-pinned 697.7 (user in-sim acceptance),
#    CYXY route-reach converted to tracked xfail (user acceptance —
#    2.42%/2.12%/1.69% feeder-convergence residuals, sub-visible).
#    USER RULINGS 2026-07-17 recorded: span-gate option (b) accepted;
#    CYXY accepted as-is; user reviewing HECA/SPJC/SPLP in-sim next.
# 6. EGLL TUNNEL-PAD EXCLUSION (user in-sim: "building36" bulging
#    south over two tunnel objects): the pad WAS a pure tunnel
#    (shell+deck pair welded correctly, mis-emitted as a building).
#    Fix: the Feature-B classifier (object_terrain_features, pure
#    placements+geometry) now runs at building-extraction time in
#    dsf_reader.read_dsf_object_buildings; classified tunnel/bridge/
#    deck resources are dropped pre-pooling (gate OBJECT_BRIDGE_
#    TERRAIN, failure-safe fallback, cache-fingerprinted).  EGLL
#    tunnel pads 10→0 — INCLUDING both ruling-(b) residual spanners
#    (they were tunnels); EGGW 39 / HECA 487 exact; SPJC all-zero;
#    391 object tests green (+2 new).  Only residual spanner left
#    anywhere: HECA 46k/601 m.
# 7. WHOLE-SUITE REGRESSION: 2058 passed / 10 failed — 1 = the known
#    HECA terminal-8 red; 9 are the CONCURRENT session's in-flight
#    areas (6 build-time estimates, 2 texture modes, 1 provider
#    registry custom_url; plus their obj8_reader draped_layer_group
#    breaks test_contracts::test_object_geometry_fields).  Zero
#    regressions from this session's work.
#    NEXT SESSION CANDIDATES: terminal-8 solver project (THE red),
#    fill-aware span gate (only HECA's 46k/601 m spanner left),
#    solved_store_missing_shape root-cause, writeback-aliasing watch
#    item.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260829a (ROAD-RAMP FAMILY SHIPPED ON OWNER ORDER; app 1.0.267,
# engine 1.50.1710, embedded==dist hash-verified.)
# OWNER ORDERS: 29a law-correction equilibrium accepted; 29b NO
#   BASELINE — value deltas are not acceptance, gate = law violations
#   only + in-sim reads; "skip the ship arm, build the app" — the
#   five-airport ship arm was SKIPPED (Opus spend limit killed lane
#   5k mid-arm; resets Aug 31 9am PT), sim adjudicates.
# FLIPPED DEFAULT-ON (c4b5be0): O4_FREE_ROAD_PROFILE (one-way weld,
#   242 end-on bindings, whole-path 8%, chord-law SELF-PINS),
#   O4_ROAD_PATH_METRIC (path pricing + gap chords, 4 readers incl.
#   census via NEW SIDECAR CAP-VECTOR KEY, 5k merge), per-station cap
#   vector (unconditional since 5d), O4_ROAD_CONTACT_CAP_SCOPE.
# RETIRED-KEPT-GATED (refutation ledgers): 5e blanket freeze, 5f/5g
#   scoped freeze (never fired — SCOPED_FINAL_PROJECTION is PARKED,
#   never un-park), 5h live-store ring criterion, 5i road-blind.
#   Round-5 spec has 10 amendments = the full record.
# KNOWN STATE AT FLIP: CYXY fifth site 0.270 m (was 3.631); HECA
#   items 2/3/4 proven per-mechanism in arms but the COMBINED flip
#   census was never measured at HECA/OTHH/LEMD (owner skipped);
#   watch first sim read + first censuses for the lateral_contiguity
#   fourth-reader arithmetic (CYXY/SPJC +100s must be gone).
# CHIP DONE: lockstep twin re-founded (coordinate-join artifact, NO
#   solver/validator divergence, no contamination).
# NEXT: owner sim pass on 1.0.267 (rebuild +30+031/+60-136 minimum);
#   ship-gate ledger keeps accumulating; solve-partition docket only
#   if sim shows airside harm.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260828d (SIM-READ ROUND 3 on 1.0.265 — LEMD ramp/road fidelity,
# pad carve, HECA drainage+ramps; FIVE lane rounds, app 1.0.266 built
# embedded==dist hash-verified.)
# LEMD (all MERGED): §F1 wall-top station law (humps WERE the wall top;
#   owner wall cross-band 0.80->0.00 m, 21->11 twisted bands; docket =
#   second emitter _emit_low_corridor_connectors); §F4 spelling envelope
#   (ribbon overhang -2.47 -> +0.56 m clear — DSF chain 2.75 m off the
#   OSM line was the centering defect, pair hypothesis refuted); §F5
#   per-way road width (item-3 5.94->13.90 m vs stated 14.0); PAD CARVE
#   default-ON (corridor from ramp object deck, 20/20 stations,
#   building8 flat, census -2) + FOUNDED-DATUM CARRY (pack seats at
#   provenance 600.51 — 596.682 was the 2026-08-27 dev surface,
#   SUPERSEDED; scoped read = drift detector).
# HECA: item-1 ols_road runway-strip stand-down MERGED default-ON
#   (site 680%->102%, strip_seam_tear 5.10->2.32 m, runway 0/66 moved,
#   HECA -191). Items 2/3/4 (ramps): contact-cap scoping + the whole
#   free_road_profile pass (one-way weld, 242 end-on bindings/673
#   refusals published, whole-path 8%) MERGED DEFAULT-OFF — blocked on
#   METRIC COLLISION (census prices road pairs by euclidean chord; a
#   path-lawful U-loop ramp reads 8.33-9.11%; CYXY +120 = 8% x
#   path/chord). RULED Amendment 1: path-metric pricing for road-family
#   within-shape pairs + gap-chord exclusion, ONE implementation in
#   check_grade; moved-airside gate on the SOLVE-OWNED frame. Round 5c
#   lane (hecar5c) implementing; gates flip ON in its arm.
# RULINGS: 28e free-road 8% (confirms SERVICE_ROAD_MAX_GRADE; defect
#   was apron-spine scoping); terrace-vs-grade on wide steep roads
#   docketed; artifact-ledger stale-tree-hash chip out (owner started).
# NEXT: owner sim pass on 1.0.266 (OTHH walls, all LEMD, CYXY, HECA
#   tear; HECA ramps unchanged until 5c -> 1.0.267).
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260828c (OWNER SIM-READ ROUND 2 on 1.0.264 — OTHH tunnels, LEMD
# pit ramp, CYXY terrain; THREE lanes, all closed; app 1.0.265 built
# embedded==dist hash-verified, engine 1.50.1708.)
# OTHH WALLS FIXED (§W1 MERGED 04272e71): walls were BORN by §2.3 then
#   eaten by covered-stretch drop (claim footprints missing from the
#   ruling-4 post-cut union) — adjudication-only subtraction lands;
#   coverage 0%→51%, mouth reach 727.6→5.9 PASS, covered-span guard
#   holds. §W2 landed lawful but the hump attribution was WRONG (host
#   ring authors the 4.00s, outside cut+claims) — SIM ADJUDICATES the
#   walled render. Dockets: 173 hole-ring over-cap rows (instrument Q
#   first), wall-foot R16-2b, site B2 reach 107.9.
# DEPTH RULED (2026-08-28d, 715a44fa): service-bore depth STAYS 5.1 m;
#   shallowness read = missing walls, not dig depth.
# CYXY FIXED (R18-1c MERGED d5b6bf91): my flood-leak spec REFUTED by
#   lane instruments (0/578 seeds, 0/22,923 tris); real owner =
#   R18-1b harmonic domain welded tile-wide through include_roads'
#   shared INTERP_ALT bit. Domain scoped to patch coverage: |mesh-.alt|
#   mean 7.50→0.58 m, >20 m 1,811→0; HECA 867-vertex miniature also
#   cured; leak detector red→green. Coastal seawall control DEFERRED.
# LEMD PIT RAMP UNSHIPPED (both arms retired-kept-gated, 4a407394):
#   arm 1 region-completion moves the one-body reads (floor/rim/pad/G);
#   arm 2 emit plate is geometrically MET but the ramp corridor is
#   INSIDE building8's pad ring — pad flattening authority owns the
#   ground at 600.51. NEXT LEVER = pad authority carve (spec Amendment
#   2, PENDING OWNER; G fork: 8/70 stations on the corridor,
#   596.680 pre-plate vs 596.000 dropped). Stale-sidecar cache v26
#   fix shipped in passing.
# NEXT: owner rebuilds +25+051/+40-004/+60-136 on 1.0.265; pad-carve
#   ruling; then the docket list.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260828b (THE 1.0.263 SIM-READ WAVE MERGED — 17 owner items across
# LEMD/HECA/OTHH, four lanes + two attribution lanes; app 1.0.264.)
# TUNNELS (spec 98ee0a88 + amendments): LEMD portal table 5 PASS /
#   0 FAIL (items 4/5/6/7 — corridor suppression over mapped bores,
#   DEM-cut provenance gate, scoped adjacent-road veto with published
#   refusals, mouth-beats-cap); OTHH covered-span mask 12->0 at mint
#   (item 12 + LEMD 557); claimed corridors footprint-scoped; ramp-
#   wall _g0 gap ships (item 9; foot RETIRED-KEPT-GATED off — the
#   face-inflation docket has its bisect signature); corridor-
#   seniority pre-pass (rule 3) + road-piece ledger (item 8 partial:
#   runway-clip joins fixed; third-world mint-side ledger chartered).
# LEMD RIM/STATIONS (spec bff21887 + 3 amendments): stations weld or
#   stand down (on-edge 144->0 at five airports — KILLS THE NEEDLE
#   LOAD-TIME REGRESSION, p99 aspect 43k class); trench senior to
#   pavement at its rim (338/338); rim re-seats post-solve at the
#   solved neighbour (600.47 level-to-level, walled 12.72 m pit);
#   pad rings stand-down hosts; declared pit wall exempt BY NAME w/
#   carried-span conditional; LEMD census 3205->3028.
# HECA ROUND 4 (spec 357854f4 + Amendment 1): membrane law floor +
#   do-no-harm relaxation ON (+396 at HECA, +252 = un-blinding, ~144
#   docketed); adoption freeze narrowed receiver-plus-lot; transverse
#   no-step on own rings = the round's win (item 5(a) CLOSED; LEMD
#   -530 / SPJC -266 on matched controls); road-evidence severance
#   retired-kept-gated OFF (IoU 0.8221; item 3 -> scorer-v2 docket,
#   interim = split Tai pack pavements #111/#57 in the PACKAGE).
# OWNER ITEM SCOREBOARD: fixed 4,5,6,7,9,12 (tunnels), 1-LEMD/4-HECA
#   (stations), 2/3-LEMD (rim), 5(a)-HECA; partial 8, 1-HECA; honest
#   misses docketed: 2-HECA T-site (sim adjudicates), 5(b) binding
#   unnamed, item-3 scorer docket.
# OPEN DOCKETS: face-inflation (~1.4 m2/wall between emit and final);
#   over-cap tunnel ramps (LEMD 30 w252% / OTHH 220 w337%, standing
#   2026-08-07); §H1.1 ~144 response; item-5(b) binding; scorer-v2;
#   mint-side road ledger; 7 ramps with no wall either arm.
# NEXT: app 1.0.264 owner sim pass -> docket triage by what reads.
# ══════════════════════════════════════════════════════════════════
# ── HANDOVER CODA (20260828b, session close) ──────────────────────
# TREE: main CLEAN at 4fd0813c (app 1.0.264 bump); every wave lane
#   branch MERGED. Unmerged lane/* are OLDER parked lanes (align,
#   c3rework, fixtriage, frontweld) + lane/hecar2 (attribution
#   evidence only — its tool already promoted via hround4).
# APP: dist.nosync/XPTerrainBuilder.app 1.0.264, embedded==dist
#   hash-verified. Owner rebuilds tiles +40-004/+30+031/+25+051 to
#   see the wave; load times should normalize (needle fix).
# CHIP PENDING: osr.UseExceptions FutureWarning at launch
#   (task filed; cause = O4_Proj_Runtime importing osr + GDAL 3.12;
#   benign). Chip sessions for the two red twins (near-miss,
#   pad-law late-projection) ran in their own sessions/branches —
#   check claude/* branches before re-fixing.
# PRESERVED: owner's HECA surgery reference at
#   Ortho4XP/tmp/owner_surgery/HECA_owner_surgery_20260828.osm
#   (dd2bc44d) — the data-repo Patches copy will be overwritten.
# CLEANUP OWED: ~86 worktrees accumulated (standing queue item);
#   .claude/worktrees/basecheck holds untracked engine caches
#   (lane_worktree.sh down basecheck --force is safe).
# NEW SESSION: read this block + RULINGS 2026-08-28/28b/28c + the
#   three wave specs' amendment histories; owner sim pass on 1.0.264
#   triages the docket list above.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260828a (PADS AS BAND-BOUNDED VARIABLES MERGED 85febb99 + the
# pad_binding_routes chip branch 9ec11e15 + composition fix; app
# 1.0.263 built embedded==dist for the owner sim pass.)
# PADS: 53/54 HECA pads are one flat variable in the ring-domain
#   intersection of the narrowed band (median 6.19 m; 33 LAW-placed at
#   a bound); ring-median seat pass retired (O4_PADS_BAND_VARIABLES,
#   OFF byte-identical measured); building25 domain 2.105 m reproduces
#   82.320; building146 lawful 0.812 m domain. HECA 6,543->6,516;
#   CYXY/HEAZ byte-identical; SPJC -1, LEMD -6; 0 empty domains, 0
#   contradictions anywhere.
# GROUP accommodate-else-split machinery ARMED but 0-of-0 declared:
#   docket-B groups are post-mesh; the pad-frame declaration is an
#   open design docket (recon chip out; Fable ruling to follow).
#   LEMD note for the owner: building8+building24 rigid unit seats at
#   599.393 (building8's domain floor) inside building24's domain.
# PROVENANCE: pad_binding_routes carries routes + domains, merged by
#   pad ref (one container, two producers); pass-identity composition
#   ruled — foreign band publishes neither, capture-degraded
#   suppresses routes only.
# reds on main: near-miss twin (chip session out), pad-law
#   late-projection twin (source-inspection drift, chip filed).
# NEXT: owner sim pass on 1.0.263; pack-group declaration ruling from
#   the recon; ship-gate ledgers keep accumulating.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260827b (UNIFIED LAW BAND MERGED 16889bc9: the reach band is the
# projection of the FULL law graph — frontage chords + membrane +
# no-step enumeration, ONE shared list — narrowed BEFORE seating and
# the solve; owner rulings "REFINE THE BAND FIRST" + report-first
# contradictions + grade-law-outranks-shared-datum.)
# MEASURED: building25 frontage band 28.6->6.3 m, seat hard against
#   its frontage ceiling, both over-cap rows GONE; HECA census
#   6,927->6,543 (-384); 32/51 HECA pads re-seat (worst -11.3 m,
#   drifted-high class); SPJC/CYXY/HEAZ pads 0 moved; OFF arm
#   byte-identical; band phase +2.38 s at HECA (~4% — statement in
#   the lane report, gates suspended).
# CONTRADICTION LEDGER (report-first pre-ship, O4_BAND_LAW_REFUSE=1 =
#   ship-gate arm): law_band_contradictions in every sidecar, census
#   prints it; 0 sites on shipped HECA/CYXY/HEAZ arms. The HEAZ pair
#   (runways 81.10 vs 86.14 over a 4.38 m chain) lives ONLY in the
#   bridge-carrying arm — the band now names the bridge disease
#   PRE-solve; docket joined to the bridge docket in DEFERRED.
# SEAT ANCHORS OFF BY MEASUREMENT (+4,069 rows ON at SPJC — post-hoc
#   narrowing vs committed rigid seats): the founding evidence for the
#   NEXT ROUND, pads as band-bounded variables (owner-ruled direction
#   + group-split ruling: grade law outranks shared-datum, groups
#   split loudly when accommodation would violate grade).
# ALSO: pad_binding_routes sidecar publication + --from-sidecar render
#   (c32fceaa, chip session); trace_building_frontage repaired
#   (6d7a2c0c, chip session); band-gate twin chip in flight.
# NEXT: pads-as-band-bounded-variables spec + lane; owner sim pass on
#   the fresh app; conform-pass retirement question stays open (not
#   approaching no-op: 583 residual at HECA post-repair).
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260827a (OWNER SIM-READ ROUND, RULINGS 2026-08-26b: five HECA
# items from the 1.0.260 pass. Two lanes, both MERGED on branch
# round3-integration — main merge held: main's tree carries the LEMD
# session's UNCOMMITTED basin round, owner decides how it lands.)
# ITEM 1 lattice-overlap FIXED: per-segment clip, 7 seg/89.6 m -> 0
#   (station class 1 seg/1.1 m accepted). tools/lattice_overlap_read
#   .py promoted (INDEX row + 11 twins).
# ITEM 2 road-crossing cliff: crossing-conformance law landed
#   (source-frame crossings-only detection, POST-SOLVE ADOPTION onto
#   frozen-boundary road vertices — 0 MOVED airside rows everywhere).
#   Owner site 3.44 -> 2.73 m: road at its 8% cap ceiling; residual
#   ruled AIRSIDE-vs-AIRSIDE (apron -10258 at 103.2 vs junction
#   -10250 at 108.9 over ~35 m) — needs its own attribution docket if
#   the owner's sim still reads it. Widening kept (Amendment 3:
#   177-row lateral_contiguity value vs 13 marginal-row cost).
# ITEMS 3+5 (dip + disconnected "T"): ONE defect — the taxi ROUTE was
#   never cut; the 84.2 m owner line had ZERO interior stations.
#   APRON SPINE STATIONS landed (apron_spine_stations.py): interior
#   stations on every aircraft axis crossing an apron, valued as
#   INTERPOLANTS of the un-densified phase-A profile (chain
#   byte-identical to stations-OFF — three amendments to get there:
#   symmetric edges dragged junctions DOWN 0.22 m, chain membership
#   re-solved the profile, unstrung axes valued from route endpoint
#   anchors). 62/62 HECA stations valued; line-T station steps
#   lawful; junction "T" pieces unmoved. DIP RESIDUAL STANDS
#   (~1.5 m proud ridge): membrane within every law budget as
#   written; the low nodes sit 130-137 m from the nearest station,
#   outside the 75 m §3 join radius. OWNER QUESTION: widen the join /
#   membrane tautness term (DEM-last says plane-flatness beats DEM in
#   the lawful range) — or accept in sim.
# ITEM 4 necessity: MEASURED — stations alone leave 8 HECA aprons
#   with >80 m empty disks (worst 169.5 m): the lattice is NOT
#   subsumed; stays ON.
# COMBINED ACCEPTANCE (integ3, HECA_20260827T021457): adjudicated
#   4652 (airside 999) vs CTL 4697 (915) — +86 airside is the newly
#   PRICED station-pair membrane (un-blinding), rest slightly better;
#   twins 381/1 green (1 = pre-existing near-miss-frontage register
#   drift, chip filed); CYXY 295 adj / SPJC 348 adj compose per-lane.
# PRE-EXISTING MAIN DEFECTS surfaced (chips filed): HEAZ
#   BandInversionError (43/1478, flag-independent) and the red
#   test_the_near_miss_frontage_law_is_one_authority twin.
# NEXT: owner lands the LEMD uncommitted round -> merge
#   round3-integration to main -> app build for owner sim pass
#   (cliff/dip/T re-read in sim) -> dip-residual ruling.
# ══════════════════════════════════════════════════════════════════
# 20260827-basin-dockets (LEMD basin follow-up dockets A+B, both
#   COMMITTED: c446edba founding, 690d0568 group seat; road feed
#   refreshed via ledger 2026-08-27T07:08.)
# DOCKET A (basin-region-founding-spec.md + Amendments 1-2): unmatched
#   below-grade regions found basin records (depth <=-3.0, open sky,
#   tight contributors, no new R4 exclusions); coverage LAZY BY
#   PREMATCH (eager 33.4 s -> lazy 0.63 s at LEMD); gate
#   O4_BASIN_REGION_FOUNDING ON; cache v23/exclusion v9; LEMD inert
#   (0 founded, ON==OFF byte-identical).
# DOCKET B (basin-group-seat-spec.md + Amendments 1-2): one connected
#   body = one facility; seat group = partition structures ∩ body,
#   CLOSED over file<->structure; one datum plane G=R_mesh,
#   delta=G-anchor_ground, ONE instrument; item-6 topology -> delta
#   threshold; provenance records delta+G; run-record v9 + gate lists
#   gain the 4 missing O4_BASIN_* envs; degenerate split components
#   dropped at 1e-6 m2 validity floor (LEMD 1.5e-13 sliver minted a
#   2nd facility, double-seated 42 files); exclusion cache v10.
# ACCEPTANCE: mesh-only +40-004 tile run + rebake replay + offline
#   probe, guard armed, corpus UNCHANGED: ONE facility, ONE
#   G=596.682, 48 files/14,378 structures, 5/5 named T4S objects,
#   relationship invariant worst 0.000000 m over 48 provenance
#   entries (owner's metric), 8.95 m structure-0 seam ABSENT, A3
#   skips 0, clearance +1.38 m, trench unchanged (587.75).
# NOTE pre-existing HEAD failures, NOT this round: test_harness
#   near_miss_frontage SOFT_ROLES; test_contracts obj8_partition
#   signature (drift from 6045e6b6) — concurrent-lane dockets.
# OPEN: owner in-sim read of T4S; final-profiling adjudication of the
#   region/coverage costs; OTHH/battery group-seat regression at ship
#   gate (DEFERRED ledger).
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# 20260826-basin (LEMD T4S basin round — region footprint + solid-
#   witness floor law. Implemented on main, NOT committed; owner
#   in-sim read pending.)
# GROUND TRUTH: the pack's own mesh patch (Aerosoft LEMD - 2 - Mesh
#   .../LEMD.patch.osm): T4S pit ring 87 verts 27,612 m2, rim flush at
#   the pack's flat 594.625 datum, floor datum-18.0 (a ~10.9 m overcut;
#   family's deepest genuine solid is -7.09). All pack placements are
#   draped OBJECT on a flat TIN; T4S = 358 objects on ONE anchor.
# RULINGS 2026-08-26 (docs/RULINGS.md, same-day canon): (1) floor keys
#   on the thickness-gated deepest solid + restored tunnel margins,
#   open pits included (supersedes Amendment 3 deck-face clause,
#   retire-gated O4_BASIN_OPEN_PIT_DECK_KEY); (2) trench senior to
#   pad/building authority inside the region (building8 docket
#   RESOLVED — its footprint CONTAINS the whole pit); (3) cut shape
#   derived region-level from object geometry (independent of the
#   pool/structure partition), pack patches = validation only.
# SPEC: docs/specs/basin-region-footprint-spec.md (incl. post-impl
#   floor-prediction correction: lawful floor 587.75, not 584.44 —
#   R_est moves with the full outline; invariant = clears seated
#   solid bottom 588.95 by 1.20 m).
# LANDED (Opus lane): below_grade_regions() in object_terrain_features
#   (plane-clip below TRENCH_SPINE_MIN_DEPTH_M, MIN_SOLID_PART_
#   THICKNESS_M decal gate, close 2 m), record extension in
#   basin_trench_structures, grade_law margins restored, gates
#   BASIN_REGION_FOOTPRINT (ON) / BASIN_OPEN_PIT_DECK_KEY (OFF),
#   classification cache v22 + exclusion v8 (v21 could hold a
#   poisoned empty-region sidecar), 28 new test cases. DEFECT FIXED
#   EN ROUTE: shapely union_all TopologyException on a walls-only
#   resource (0 m2 clip) was swallowed -> whole ring silently [] —
#   now buffer(0) repair + loud one-at-a-time fallback.
# ACCEPTANCE (one harness LEMD build, degraded-dem frame — road-feed
#   sidecar STALE blocked a shared-repo write, corpus UNCHANGED,
#   KCLT-precedent class; owner may --refresh-data osm_roadfeed):
#   trench 27,346.5 m2 (99.0% of authored; was 11,845.6/36.5%),
#   floor 587.75 law-true, bbox covers authored, building8 authority
#   yield fires over the full ring; 1.8% emit shrink = the lawful
#   0.6 m wall setback. Tests 650 pass / 1 PRE-EXISTING fail
#   (test_harness near_miss_frontage SOFT_ROLES vs ROLE_SERVICE_
#   JUNCTION — byte-identical at HEAD, likely the concurrent HECA
#   lane's docket).
# OPEN: founding basins from unmatched regions (no interface record);
#   shared-anchor rigid group seating (relationship preservation)
#   design; zero-area sliver reaching the NO-FLOOR-PLATE named line
#   (cosmetic); road-feed refresh decision (owner).
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# 20260825c (THIRD SHIP: app 1.0.260, embedded==dist — the round-2
# fixes from the owner's 1.0.259 sim read, all merged to main.)
# IN 1.0.260 (on top of 20260825b): APRON ROUND 2 — interior LATTICE
#   for nodeless apron voids (HECA cliff: 247 m nodeless run -> 12
#   stations, monotone; nodeless_interiors 10->0; census un-blinded
#   +523/-87; new family apron_lattice_membrane), gap-spine bridge
#   (inert at HECA — the "feed gap" was a 2.2x detour, premise
#   corrected), taut strip where band-authored. ROADS — cross-section
#   law (25g, transverse road pairs at the cross-section limit; owner
#   site worst lateral 7.68%->2.11%), late-limiter repair confirmed,
#   BuildingClaim one-notion consolidation, and SERVICE-ROAD APRON
#   SPINES (25h): free-road scoping was DROPPING the contact
#   stretches entirely — restored as 1% spines; HECA airside
#   2,177->918 on the post-lattice frame, alternation class 0.
#   LEMD BASIN — open-pit floor at authored depth (586.01, no tunnel
#   margins), authority clip (no pad severing/seating; building8+18
#   unmoved), per-part wall allowance (926/930 rows retire; +4 honest
#   rim-rim rows); OTHH bowls to authored depth (+1.5-1.8 m — likely
#   closes the owner's deferred "drainage too low" item; bores keep
#   margins).
# DEFERRED (pre-ship ledger, owner-pending): CYXY spine-zero gate
#   FAILS at 3 rows (14.6/14.6/10.2% vs 8% longitudinal, induced by
#   cross-section constraining pinned junction neighbours — the
#   joint-caps ruling); site-B single ~6.3 m step (apron -10582)
#   = the apron-chain docket; HECA groundside transverse +454
#   residue; the frontage-pin BuildingClaim machinery kept
#   (law-correct, doesn't fix site B).
# ALL RULINGS 2026-08-25 a-h in RULINGS.md; all specs amended with
#   measured dispositions. LEMD day arc: fatal assert -> 894 ->
#   (lattice/basin re-frame) -> current frame in the specs.
# NEXT: owner sim pass on 1.0.260 (HECA cliff/ripples/roads, OTHH
#   basins+tunnels+inset ruling, LEMD hole) -> joint-caps + apron
#   -10582 rulings -> bar re-founding -> battery + SPLP/KAFW/KDFW ->
#   worktree cleanup (apronfix/roads/tunattr/othhtun/eatscope/
#   kdfwfix/eatctl/backedge standing) -> deferred OTHH round-2 sites.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260825b (SECOND SHIP OF THE DAY: app 1.0.259, embedded==dist.
# Six lanes merged on top of the 20260825 block's work.)
# IN 1.0.259 (all owner-ruled, all twinned): road band-seal scoped
#   airside-only + road-apron edge conformance as pricing+seeding
#   (RULINGS 25b; HECA 1,679 / SPJC 174; owner road site = continuous
#   <=8% descent, was 201.5% step); EAT recognition v2 (RULINGS 25c/d:
#   routed wrap + vacuous bound + 600 m cap + cut-only pin — LEMD
#   builds, zero pins, KCLT byte-identical); tunnel-trench declared-
#   step law + basin floor integrity (OTHH census 5,871->255 — 96%
#   was the missing law entry; LEMD floor 545.5->588.5); basin pool
#   scoping (thin parts cannot SEED a pit — LEMD 7,331->894, basin
#   confined to the owner bbox at 8.53 m; VOR decals were the
#   seeders, LEMD03 exonerated); portal corridor claim (RULINGS 25e:
#   per-piece named refusals ungated, bore-depth stand-down guard,
#   claim fields RIDE the shape + drift audit — OTHH mouth D emits at
#   -0.90 m, was 727.6 m of nothing); KDFW GEOS fix (safe_difference
#   precision-grid retry — valid inputs, invalid GEOS output class).
#   Node book stays v1 (nine-arm ledger on lane/tunnelfix: findings
#   2-5 — retreat face XOR shared key; carriers outside every
#   publishable region; owner disposition pending, accept-v1
#   recommended; residual = 3 walls + 1.03 m lot half).
# LEMD DAY ARC: fatal assert -> 12,252 -> 894 (airside 155).
# OWNER RULINGS PENDING: (1) node-book disposition (accept v1 vs
#   reopen road-chord-limiter seeding); (2) building8 vs the basin
#   cut (a 33,447 m2 pack pad covers the real sunken tower circle;
#   R13 cuts pavement never pads — does the cutout pierce it?);
#   (3) R16-2b ramp-wall inset (owner checks in-sim first).
# DOCKETS RECORDED: emit-authority at claimed-corridor shared nodes;
#   silent emitter when body_floor_born==0 (25e class); post-limiter
#   road authors (roadseal §1.3 audit: 4 passes); spain5m integer
#   quantization (WCS refetch as Float32?); OTHH mouth A site_reach
#   89.8 vs 60 bar; 229 post-projection weld insertions; §2 DEM-last
#   spine-only-anchors design; HECA bar re-founding; sites 2/3 OTHH
#   pre-existing tickets; battery + SPLP arms + worktree cleanup.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260825 (RULINGS ROUND: apron chord anchor targets + DEM-last;
# tunnel-corridor fix; LEMD attribution; app 1.0.258 / engine
# 1.50.1701 SHIPPED for owner sim test, embedded==dist hash-verified)
# TWO OWNER RULINGS (RULINGS.md 2026-08-25): (1) apron ring vertices
#   chord to NEAREST VISIBLE anchor — pad OR centerline, closer wins,
#   apron-only visibility; frontage chords unchanged; (2) DEM LAST
#   priority — straight planes between anchors, never drape.
# MERGED TO MAIN: §1 chord-anchor law (spec apron-chord-anchor-target,
#   grade_graph nearest-anchor enumeration, flag
#   O4_APRON_CHORD_ANCHOR_TARGET ON) — HECA 1,964→1,735 new frame
#   (old bar 1,487 NOT re-founded, owner's call), SPJC 175, CYXY 31,
#   drape all better, median vs DEM 0.400→-0.474 (cutting). The
#   2026-08-21f pad-INTERCEPT clause superseded (kept behind flag-off);
#   _pad_intercept was census-blind (asymmetry removed). Tunnel fix v1
#   (per-RING corridor exclusion from the road chord limiter's node
#   book, spec tunnel-corridor-node-book-exclusion + owner
#   disposition): OTHH site-1 ramp EXACT, walls 7/10, adjudicated +30.
# PARKED OFF (measured-regressing, mechanisms in lane history — do
#   not re-arm without a new design): O4_PAD_SEAT_CONSISTENCY
#   (frontage-subset interval, HECA +285), O4_DEM_LAST_SEAT_BIAS
#   (anchor-neighborhood seat bias, HECA +237/SPJC +265 both attempts;
#   solved-anchor filter proved regression is population not values;
#   candidate next design = SPINE-ONLY senior anchors — pad anchors
#   are other pads' provisional seats, circular under creation-order).
# TUNNEL LEDGER (lane/tunnelfix, v2 d83379a8 + v3 b9ef30c9 unmerged):
#   per-NODE keys REFUTED (two-step carrier: road→out-of-cut weld→own
#   chord law→bore); precedence-exemption REFUTED (clamp carries what
#   precedence doesn't); FINDING 2 (structural): a retreat face and a
#   shared key are MUTUALLY EXCLUSIVE — faces need disagreement.
#   QUEUED option A (owner-gated): claim-touching ROAD rings leave
#   _CHORD_LIMIT_ROLES for the pass. OTHH sites 2
#   (25.2791543,51.5997351 mapped-mouth D never emitted) + 3
#   (25.2760974,51.5920871 ramp-wall no-inset) PRE-EXISTING tickets.
#   Separate standing defect: 229 post-projection nid-weld insertions
#   (weld-before-projection spec requires 0) — real, not the author of
#   the owner sites.
# LEMD (new fixture, fails final-band inversion): NOT the 5m-PNOA
#   data (identical on both DEM arms); 4 flat pack-baked datum lines
#   (624.2/620.8/610.9/603.8, no DEM matches, all CIFP thresholds
#   <=608.1) at La Munoza campus (40.492-40.500N 3.584-3.591W) descend
#   ~2.3-2.6% vs 1.5% routes; leading hypothesis deck/crossing-rect
#   pins (Aerosoft Bridge3.obj placements sit between anchor lines;
#   deck-vs-deck contradiction UNGUARDED — KDFW guard is deck-vs-
#   senior only). CONFIRMATION OWED: one harness LEMD build grepping
#   pin-registration lines for the four values.
# NEXT: owner sim read (HECA aprons + OTHH tunnels) -> re-found HECA
#   bar -> tunnel option A on owner go -> §2 spine-only design if
#   aprons still read wrong at pads -> LEMD confirmation build ->
#   battery + SPLP/KAFW/KDFW arms + worktree cleanup still owed.
# OWNER BACKLOG (2026-08-25 in-sim, deferred behind the current bug
#   list on owner's own call): (1) further OTHH tunnel issues beyond
#   the v1-restored site-1 (unspecified — collect sites at next sim
#   pass); (2) DRAINAGE OBJECTS set too low (new class, no sites yet).
# LEMD GROUND TRUTH (owner 2026-08-25): the airport REALLY HAS several
#   tunnel mouths AND a large open sunken circle ~5+ m below the
#   surrounding apron with the CONTROL TOWER inside it — the object-
#   basin machinery is modelling a real feature; the POOLING docket's
#   acceptance shape is that circle (post-fix depth ~8.5 m is
#   plausible; the 1.56M m2 / 4 km extent is the pooling defect).
#   OWNER BBOX for the circle: 40.4910364,-3.5681856 to
#   40.4923786,-3.5703743. Pack probe: T4STower_(c)_Sim-wings-SWbaume
#   .obj base_y -6.99..-4.04 (134 parts in-box) + Ground-FSX-LEMD36/
#   37/85 floor pieces at -7.0 = the REAL basin members (~7 m deep);
#   Ground-FSX-LEMD03 (the -6.75 decal-chain culprit) touches the box
#   with ONE part — the bridge the pool escaped through. OWNER: a
#   road+ramp legitimately leads UP out of the MOSTLY-RECTANGULAR
#   cutout to apron level, so a connection out of the hole is real
#   geometry (the -3.3/-2.8 LEMD37 pieces are that exit ramp) — the
#   pooling chain-break must key on RETURNING TO GRADE, not bare
#   adjacency. OWNER SIMPLIFICATION: the pack objects most likely
#   model the ramp themselves — the terrain owes only a SIMPLE
#   RECTANGULAR CUT ~= this bbox at ~7 m; no ramp modelling in the
#   terrain. Pooling spec acceptance: that cut, nothing more.
#   LEMD's mouths will exercise the portal-corridor-claim law
#   (RULINGS 2026-08-25e) beyond OTHH.
# IN-FLIGHT at session close of this block: LEMD confirmation build;
#   HECA roads attribution (missing spines + floor-clamp author +
#   exit_over_budget, site 30.102344,31.3951157); HECA apron
#   attribution (cut-centerline cliff 30.1289374,31.4052385 ->
#   30.1311876,31.4048029 owner-hypothesis stand-route end clipping;
#   back-edge ripples 30.1274109,31.3970477 + 30.1141206,31.4095574 —
#   possibly 24c DEM-soft-seed vs the DEM-last ruling).
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260824 (APRON MEMBRANE ROUND — owner in-sim review + JOSM ground
# truth drove five ruling cycles; the conclusion is a SPEC'D BUT
# UNIMPLEMENTED seat-consistency fix. READ
# docs/findings/apron-membrane-findings-20260824.md FIRST — it holds
# every number and every refuted mechanism; then
# docs/specs/pad-seat-consistency-spec.md is the work order.)
# THE FINDING: the reach band seats pads in a FEASIBILITY interval
#   7-34 m wide; the chord law then judges them against the SOLVED
#   corridor at 0.13-1.06 m budgets. 100% of HECA's violating pads
#   are lawfully INSIDE their band — the band is right but NOT
#   BINDING. Fix: seat interval = band ∩ [corridor_solved ± cap x
#   route_dist] (creation-order seniority; DEM still chooses within).
#   REFUTED on the way (do not retry; findings §2): plateau framing,
#   interior-cap tuning (5% never priced a row anywhere), hidden DEM
#   attractor (projection honours seeds, median +0.01 m), scaffold-
#   derived seats (v4: 22/22 CYXY pads down 9 m, reverted 46c27cf),
#   route-vs-euclid band mismatch (route==euclid 300/300), seat
#   edge-clamping (810/810 mid-interval), the lead's 295-row
#   parallel-structure claim (classification error).
# RULINGS this round (2026-08-24, 24b, 24c in RULINGS.md): 5% only at
#   back-edge zones (fan geometry, live-computed); tiny pads (<250 m2)
#   fold into parent; NO plateaus — continuous membrane on the
#   centerline scaffold; interior corridor-region chords at 1.5%;
#   stand scope = pad-anchored at 1%; taut membrane anchors =
#   centerline profiles + seated pads, NO DEM attraction on interiors,
#   pad-less edges soft-seed DEM but never hard-anchor; PAD-SEAT
#   FEASIBILITY GATE (report-first; 1 finding: HECA building60 0.5 m).
# LANE lane/backedge (worktree .claude/worktrees/backedge, ~12
#   commits, tips: 41cb44e narrowing, a9d9c88 frontage_band export):
#   DONE+verified: back-edge zone rescope, tiny-pad fold (56/19/2),
#   strip-exclusion WIRED (was unimplemented!), 24b corridor chain,
#   scaffold seed (honoured), pad-seat gate, frontage_band sidecar,
#   apron_drape_read tool, cliff metric pinned (B: shape-pair sites;
#   old "145" retired unreproducible). Numbers (bars 75/189/1,487):
#   CYXY 19, SPJC 167 (PASSES since v2), HECA 1,964 — HECA waits on
#   the seat spec. Parked branch lane/backedge-seatsrc = the refuted
#   seat-source experiment (keep for reference, never merge).
# ALSO THIS SESSION (already ON MAIN, app 1.0.257 / engine
#   1.50.1700): WCS explicit-size inset fix e295455 — the IGN GetCov
#   grid drifts ~1/800 vs DescribeCoverage; grid refusals now
#   TRANSIENT never no-coverage; +40-004's 13 airports (LEMD!)
#   refetched at 5 m PNOA (corpus verified; ledger stamp still owed:
#   the --break-stale-lock re-run needs the OWNER, command in the
#   transcript ~2026-08-24); HECA visual attribution (trouble_osm
#   --visual, Previews/trouble/HECA_visual.osm) — roads verdict:
#   pre-existing and improving, band-clamp class 121 records is the
#   road round's target (owner site 30.102297,31.3951639 = +5.05 m
#   floor clamp, "clamp is EVIDENCE of a solver defect upstream").
# NEXT SESSION, in order: (1) review findings doc; (2) implement
#   pad-seat-consistency-spec.md on lane/backedge (HECA first);
#   (3) whole-apron Dirichlet interpolator (only after seats are off
#   the terrain); (4) merge decision + SPLP/KAFW/KDFW + battery +
#   ledger; (5) roads/band-clamp round; (6) chord-origin reader spec.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260821b (WAVE-3 SECOND PASS — the APRON LAW round, one Mac
# session with the owner interactive in JOSM; lane/compose MERGED
# c2a00d2 ON OWNER ORDER; app 1.0.256 / engine 1.50.1699 shipped for
# sim test; CYXY 16 / HECA 1,116 PASS their bars, SPJC 207 (+18,
# seat/weld dimples — the solver-convergence round's target))
# SIX OWNER RULINGS this pass (RULINGS 2026-08-21 a-f; full text
#   there): transverse enforced IN THE SOLVE (option 2); apron
#   within-shape population = MOVEMENT SURFACES not all pairs (ii);
#   interior apron pairs = LAW at the 5% fan-ramp cap; strict chord =
#   vertex -> nearest VISIBLE spine node, pad in path INTERCEPTS
#   (prices to the pad); runway-strip area NEVER apron population;
#   CREATION-ORDER SENIORITY (later-minted geometry defers — the
#   generalisation of airside-is-king).
# MERGED MECHANISMS (all default-ON unless noted): transverse 4-node
#   hyper rows bound pre-emit w/ vertex-snap guard + step cap;
#   apron staged solve (A1 senior incl. BOTH-SENIOR interior pairs,
#   A2 interior movers only — A2 both-hard 315/78 -> ~0 everywhere);
#   one partition input runtime==sidecar; weld inserts (nid +
#   epsilon-wedge) PRE-projection, post passes verify-only with loud
#   POST-PROJECTION WELD RESIDUE lines; conforming_mint implemented
#   but GATED OFF (its 22-row justification was a JOIN ARTIFACT —
#   pair_caps was 7dp, half-ulp 5.6mm; now 11dp canonical identity);
#   kernel reporting (excluded_both_hard named, a2 both-hard docket,
#   all-hard hyper rows can't hold any_active); O4_SWEEP_BUDGET_SCALE.
# NUMBERS (bars 75 / 189 / 1,487 from the 2026-08-21 battery):
#   CYXY 16, SPJC 207, HECA 1,116. Nothing prices at the 5% interior
#   cap — 7+ arms, 3 airports: the interior law mints nothing.
#   HECA within_shape by chord: <=60m 642ish, >200m 27 (spine pairs
#   way -10256 ~500m @1.54% — owner spine-gate question OPEN).
# SPJC'S +18: 25 sub-5m seat/weld rows (17 at the -12.021394,
#   -77.110990 cluster where -10113/-10162/-10698/-10699 meet) —
#   PROVEN solver fixed-point dimples (all baked, all strict, kernel
#   at bit-identical plateau, not locally repairable) — the
#   SOLVER-CONVERGENCE round (SM3/certified-exit docket) owns them.
# OPEN OWNER ITEMS: (1) chord-less vertices (no visible centerline in
#   reach, ~1 in 6): (a) interior 5% as now / (b) fallback nearest
#   visible pad / (c) any visible movement surface — SPJC nearly free
#   (6 rows), HECA load-bearing (312/935 rows touch one, all still
#   bound by other strict clauses); (2) long spine pairs >60m gate
#   (the 27 HECA rows); (3) -12251 mis-roling -> scorer-v2 docket;
#   (4) 2026-08-21 wave-3 Q2-Q6 still open (RAOA-3, adaptive snap,
#   A2 cutback, KDFW in-sim, KAFW N-classes).
# DEBT ELSEWHERE: SPLP/KAFW/KDFW have NO arm under this tree — full
#   battery + ledger refresh owed next session; RM (lane/routemetric
#   fec3b34) is MOOT on the new population — re-evaluate then park;
#   adaptive snap 31909dc + C3 ae4a6d5 still held; census frame: line
#   reports census-time tree not build tree (harness fix owed);
#   near_miss_frontage twin still fails on main (pre-existing).
# APP 1.0.256 / engine 1.50.1699 from 034eed6, embedded==dist —
#   SIM-TEST bundle (SPJC +18 disclosed), owner-ordered merge.
#   JOSM trouble maps: tools/trouble_osm.py (Previews/trouble/).
# WORKTREES: compose is the merged lane (tear down after sim OK);
#   cyxy20/chordlim/c3rework/resid/fixtriage/eatseed/apronpop +
#   apronpopctl controls still standing; ~50 older ones — cleanup
#   session owed.
# NEXT: owner sim test -> solver-convergence round (SPJC 18) ->
#   chord-less + spine-gate rulings -> SPLP/KAFW/KDFW arms -> full
#   battery + ledger -> RM disposition -> merge-round close.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260821 (WAVE 3, first pass — Mac session, 6 Opus lanes; FOUR
# MERGES, composed battery PASS all six: 9,350/2,211 -> 6,121/1,999;
# app 1.0.254 on engine 1.50.1697 shipped to dist.nosync, embedded==
# dist; RM/C3/SM3 HELD on a NEW owner question; RULINGS 2026-08-20/21
# has the lead adjudications + six owner questions)
# MERGED (in order): F3c graded handoff 47e83ed (HECA drainage_spine
#   64->35, the 34-row crater-vs-dam class GONE, all else byte-ident);
#   crown fix e55f98d (undeclared crown endpoint = UNKNOWN interval,
#   not ridge; HECA ws::runway 3->1, 0 new rows anywhere; new reporter
#   CROWN DECLARATION GAP HECA 215/CYXY 29/SPLP 27); ROAD CHORD
#   LIMITER 1590f75 (service_road+service_junction in the finalize
#   clamp, stricter cap at shared nodes, AIRSIDE PINNED AS DATA at the
#   seed entry — CYXY 336->206, SPJC 482->407, HECA 7,548->4,844 on
#   its base; airside values moved vs control CYXY 0/SPJC 2@0.01/HECA
#   1@0.12 m; new [airside-value-audit] line); EAT RECT-LEVEL REFUSAL
#   4540c29 (the brief's "refused pin seeds" premise was WRONG — the
#   contradiction envelope reached 3 of 19 KDFW pins, the 16 UNJUDGED
#   kept authority; now a contradiction on any pin condemns the whole
#   flat rect; KDFW 284a->150a, 134 gone/0 new, CYXY byte-ident). Also
#   on main: triage dossier docs/triage/KAFW-KDFW-20260820.md
#   (c7caea3), ledger refresh d570fe0, RULINGS 1872e16,
#   tools/airside_value_delta.py (+twin, INDEX) — the instrument that
#   sees airside value drift the census cannot.
# BATTERY 2026-08-21 (composed main 4540c29/1872e16, all rc=0, ledger
#   d570fe0): CYXY 206/75a, SPLP 36/34a, SPJC 397/189a, KAFW 259/64a,
#   HECA 4,812/1,487a, KDFW 411/150a = 6,121/1,999. Per-airport
#   airside <= 08-16 bar EVERYWHERE. HECA -29 proven = F3c emitter.
# HELD: lane/routemetric fec3b34 (REBASED on main, MERGE-READY: bake-
#   hash stale-refusal landed per the lead condition, ring-adjacency
#   one predicate, sm_decompose promoted; CYXY on this base 286/90a);
#   lane/c3rework ae4a6d5 (airside-frozen C3: worst pull 58.5->1.11 m,
#   HECA gs -703; STOP — see owner Q1); lane/resid 31909dc adaptive
#   join_snap_t (clean test record; buys ONE row for 415/353 churn —
#   owner Q3); A2 cutback default-OFF (pre-solve channel, owner Q4);
#   C2 lawpair + SM3 NOT re-measured this wave (blocked on RM).
# OWNER QUESTIONS (full text RULINGS 2026-08-20/21): Q1 C3 CANNOT PAY
#   RM's relocated AIRSIDE debt (those rows are taxi-pass pairs; the
#   taxi-pass aligned-partner completion O4_XSECTION_VERTEX_HITS was
#   previously REFUSED) — extend C3 onto the taxi pass, or park RM?
#   RM+SM3 wait on this. Q2 RAOA-3 (CYXY -10406 1.68 m/0.45 m survive).
#   Q3 adaptive snap merge/drop. Q4 A2 spec revision. Q5 KDFW in-sim
#   (refused inset 220.obj + KMCI/KDEN y-bakes; EAT: KSTJ rect now
#   refuses whole, ~70% KDFW pins unjudged). Q6 KAFW N-1: road
#   transverse 2-8% is OVER the cross-section cap, UNDER the 8% chord
#   cap; the limiter DEPOSITS flattened chord debt into that band (KAFW
#   148->170, HECA +218) — now the largest groundside class; which cap
#   is the law?
# DOCKET: HECA limiter residual node 30.12927761885,31.41320440005
#   0.12 m; pre-existing final-projection airside channel (HECA 6,085
#   nodes worst 16.9 m, control too); test_the_near_miss_frontage_law_
#   is_one_authority FAILS ON MAIN (NEAR_MISS_FRONTAGE_SOFT_ROLES lacks
#   service_junction vs its twin — pre-existing); blast.py misses
#   conftest-fixture reach (test_pavement_grade) — task chip spawned;
#   sm_decompose needs route_pair_legs (RM-lane only) until RM merges;
#   the nine pre-existing pytest failures (DEFERRED_VERIFICATION) are
#   unchanged across every arm (3-arm md5-identical).
# APP: 1.0.254 from 7588def, engine 1.50.1697 frozen fresh (verified:
#   grade_law carries drainage_spine_interval + crown interval;
#   groundside carries _airside_claimed_keys), embedded binary cmp-
#   identical to dist. NOT absolute-zero (6,121 remain) — this is the
#   owner-queued wave-3 bundle, not an acceptance bundle. make_engine
#   now prunes tmp/ (lane cache root re-tripped the iCloud conflict
#   glob on the SPJC "3.0 Nueva Terminal" pack name).
# WORKTREES: lanes chordlim, cyxy20 (lane/routemetric), c3rework,
#   resid, fixtriage, eatseed stand; controls residctl/residA/c3ctl/
#   c3pre/r5base/sm3base torn down. ~50 older worktrees remain — a
#   cleanup session is overdue.
# NEXT: owner answers Q1-Q6 -> RM merge (fec3b34, re-run acceptance
#   composed) -> SM3 + C2 on that base -> A2/N-1 per Q4/Q6 -> ledger.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260818 (REMOTE INTERVIEW SESSION — ALL SIX PENDING OWNER RULINGS
# CLOSED; wave 3 re-ordered under them; no builds — remote container)
# RULINGS 2026-08-18 (canon in RULINGS.md, full text there):
#  RM (a) TRANSVERSE STAYS EUCLIDEAN — relocated +963 paid by C3
#    mechanism, never re-priced. RM (b) "airside strictly improves"
#    is PER-AIRPORT — CYXY +20 BLOCKS lane/routemetric; attribution
#    brief docs/specs/rm-cyxy-plus20-attribution-brief.md is the
#    merge gate (pre-delegated tree: relocated-transverse → C3 pays,
#    newly-legible → lead adjudication, lockstep fork → lane fix,
#    else STOP). KDFW bounds PROVISIONAL PENDING IN-SIM (bridgeguard
#    stays merged+ON; ratify after owner eyeballs KDFW + 10 y-baked
#    KMCI/KDEN records). CRATER-VS-DAM = GRADED HANDOFF (spec:
#    gap-conformance-spec.md F3c — monotone descent floor→ceiling on
#    disjoint intervals, supersedes nearer-parent fallback; 34/70
#    HECA survivors). join_snap_t ADAPTIVE (scales with station
#    spacing; residual-sweep lane, with the diagonal-pair fix). SM3
#    both rulings DEFERRED to the RM-base re-measure (probe stays a
#    lane flag).
# NEW SPECS: road-chord-limiter-spec.md (wave-3 step 1: extend
#    _grade_limit_groundside_chords to service_road/service_junction,
#    stricter cap at shared nodes, corridor-coherent unification,
#    tunnel_ramp excluded, A2 re-arm in the same lane) + F3c
#    amendment + RM owner-answers amendment + CYXY+20 brief.
# WAVE 3 RE-ORDERED under the per-airport ruling: (1) chord limiter;
#    (2) CYXY+20 attribution → (likely) C3 airside-frozen rework →
#    RM re-acceptance on that base; (3) C2 fixpoint; (4) SM3 on RM
#    base + its deferred rulings; (5) residual sweep (now owns F3c
#    graded handoff + adaptive join_snap_t + R8's 2 rows + C2's 8);
#    (6) KAFW/KDFW triage; (7) ledger re-refresh + app 1.0.254
#    (make_app + embedded==dist). In-sim list for the owner: KDFW +
#    KMCI/KDEN y-baked records (gates the bounds ratification).
# NOTE: held lanes (routemetric c009239, align 671d1cb, sm3solve
#    e1fadad, lawpair) + control worktrees live ONLY on the Mac —
#    unpushed; push them if any remote session should see them. This
#    session found main itself unpushed for 2 days (20260815g work
#    reached GitHub 2026-08-18 only after owner pushed mid-session):
#    CLOSE RITUAL GAINS: git push IS part of session close.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260815g FINAL (ZERO-DEBT ROUND CLOSED FOR HANDOVER: all lanes
# finished+adjudicated; F3, R8, BRIDGEGUARD, FRONTAGE merged; RM/C3/
# SM3/C2 HELD with owner questions; six-airport battery on composed
# main ALL rc=0 — KAFW+KDFW first-ever builds)
# BATTERY (composed main, 2026-08-16 morning, ledger addendum has the
# table): CYXY 336/75a, SPLP 43/35a, SPJC 482/199a, KAFW 365/89a,
# HECA 7,548/1,522a, KDFW 576/291a — total 9,350 adjudicated / 2,211
# airside. NOT zero: the road-face chord-limiter gap (frontage's
# honest exposure, +892 HECA gs), the held lanes' populations, and
# the new fixtures' fresh debt are wave 3.
# MERGES this stretch beyond F3+R8: BRIDGEGUARD 3796168 (KDFW builds
# with the feature ON; OTHH viaducts value-identical; girder gate
# requires a MEASURED line — lead-approved disambiguation; refusal
# bounds PROVISIONAL for owner ratification: len>1000/w>60/area>40k,
# +clearance gate — blast radius 6 KMCI + 4 KDEN cosmetic records;
# refused structures return to y-bake = in-sim acceptance item) and
# FRONTAGE 95e4374 (A1 POSITIVE landside term — HECA builds, guards
# pass, sink site 62 rows->1 worst 0.39 m; A2 cutback DEFAULT-OFF by
# lead adjudication — bought neither witness, +286 HECA via the
# road-chord gap; re-arms when the road chord limiter lands).
# RM VERDICT (lane/routemetric c009239, HELD): the ruling is RIGHT
# for SM1/SM2 (827+219 rows -> ~0 in both arms) but the chord law was
# ALSO holding cross-corridor flatness — debt RELOCATES to transverse
# (HECA within -1,152 / transverse +963); CYXY (zero within-debt)
# pays +20. Ring-adjacent chord exclusion (attempt 2) nets HECA
# airside -194. TWO OWNER QUESTIONS: (a) does transverse follow the
# route metric too, (b) is "airside strictly improves" per-airport or
# campaign-net. Also: groundside_pavement/tunnel_ramp have no solver
# pair bake — pricing them census-only would fork the lockstep
# (interpretation flagged). C1-proxy lat/lon bug corrected in the
# lane's SM script (scratchpad rm/sm_decompose.py — promote on 2nd
# use); tools/INDEX.md vs README.md ritual check discrepancy noted.
# WAVE 3 (next session): (1) road chord limiter (roads-like-taxiways
# ruling implements it; unlocks A2 re-arm + prices frontage's exposed
# faces); (2) RM per owner's two answers; (3) C3 rework airside-
# frozen; (4) C2 fixpoint + non-contact-survivor frame; (5) SM3 on
# RM base + its rulings (204-node population; probe flag); (6)
# residual sweep (R8's 2 rows, F3's 70 + trench cone, C2's 8, C3
# cliffs); (7) KAFW/KDFW new-fixture triage (365/576); (8) ledger
# re-refresh + app 1.0.254 (engine 1.50.1696 frozen; run make_app,
# verify embedded==dist). OWNER RULINGS PENDING (full list): RM (a)
# (b); crater-floor-vs-dam-ceiling clause (F3's 70); KDFW refusal
# bounds; join_snap_t radius; refused-structure y-bake in-sim accept.
# Control worktrees to tear down --force when done: r5base, sm3base,
# kafwctl, frontagebase, kafwbase.
# ORIGINAL 20260815g DRAFT (pre-lane-completion) FOLLOWS:
# Owner mandate: complete every ledger category, all adjudicated -> 0,
# app bundle LAST. TWO NEW RULINGS in canon: within-shape budget is
# ROUTE-METRIC for the apron family (the C1 keystone — SM1's 1,007
# rows retire by construction); string-bend RETIRED.
# MERGED to main this stretch: F3+F3b complete (located author =
# reclamp_gap_spines re-applying the superseded terrain floor LAST;
# one staged-law evaluator both authors; HECA drainage_spine
# 1,323->70 ~ control 66, CYXY->0; all owner sites verified; two
# STOPs docketed: trench cone floor inert pending validator-side
# conformance population; 70 survivors = empty-intersection fallback
# class, crater-floor-vs-dam-ceiling OWNER RULING PENDING) and R8
# both attempts (KAFW BUILDS rc=0; SPLP 57->42/34a ws::runway 9;
# HECA airside-acc 1,821->1,526; 2 sub-metre HECA ws::runway
# residuals docketed: diagonal-pair blind spot in the minting test +
# join_snap_t sliver — snap radius is an owner knob).
# C1 ATTRIBUTION (the dossier that changed everything): 1,502 apron
# rows = SM1 1,007 (route-vs-euclid metric gap) + SM2 232 (long-chord
# relief; terrace trigger fires ZERO joints — anchor-envelope licensed,
# nobody asks) + SM3 263 (solver exits still-descending @2,632/250k
# sweeps; 2,061 empty polytopes midpointed). DEMAND CENSUS histogram
# measured EMPTY both arms (SM3 lane) — envelope never fires at HECA.
# KDFW ATTRIBUTION: the 183.286 plateau = Aerosoft inset mesh (5 obj,
# ONE DSF anchor, 2.85x0.82 km) misclassified DECK_CARRIED via
# deck_profile_fallback; datum = anchor DEM + 8m; 193 hard pins ->
# band inversion. Interventionally proven (O4_OBJECT_BRIDGE_TERRAIN=0
# arm rc=0). NOT the KAFW family.
# IN FLIGHT (background agents; harvest via lane worktrees +
# .progress if the session ends): lane/routemetric (RM keystone spec
# docs/specs/rm-route-metric-within-shape-spec.md — one shared law
# function, SM decomposition re-run required); lane/bridgeguard
# (docs/specs/kdfw-bridge-refusal-spec.md — refusal bounds PROVISIONAL
# length>1000/width>60/area>40k m² NEED OWNER RATIFICATION; OTHH
# viaducts must survive); lane/frontage continuation (amendments
# A1-A3 in r6r7-frontage-lot-spec.md — POSITIVE landside term, ruled
# clause-3 cutback mechanism, corrected sink attribution; prior
# commits bff8f2b/70a49dd/5a52e1c KEPT; HECA guard + build are the
# gates).
# HELD FOR WAVE 3 (committed lanes, kill switches, re-measure on RM
# base): lane/align C3 671d1cb (transverse HECA 1,684->1,135 but
# pair-binding PULLS AIRSIDE worst 58.5m — rework under the
# rim-pocket/airside-frozen posture C2 already implements; its
# survivors list = the genuine junction cliffs, 351 rows >=20%);
# lane/sm3solve e1fadad (certified exit + refuse-not-midpoint; HECA
# refuses on a PRE-EXISTING 204-node population: spine_floor pinned
# AT band ceiling vs neighbour cap slab — likely dissolved by RM;
# rulings pending: population disposition, O4_SM3_EMPTY_INTERVAL_
# PROBE keep/delete); lane/lawpair (C2: seam tears 45->8, adjacent_
# ground_tear 0, CYXY 313/74, R5c sliver closed; needs fixpoint
# re-enumeration over minted stations + RM re-pricing; 8 survivors
# are NON-CONTACT pairs 1.6-5.6m — outside the law-pair predicate by
# construction, need their own frame).
# WAVE 3 QUEUE (after RM/bridgeguard/frontage land): (1) re-measure
# SM3+C2+C3 on RM base, rework C3 pair-binding airside-frozen,
# C2 fixpoint; (2) merge order RM -> bridgeguard -> frontage ->
# reworked C3/C2/SM3; (3) full battery composed censuses (CYXY HECA
# SPJC SPLP + KAFW KDFW as new fixtures); (4) residual sweep:
# R8's 2 rows, F3's 70 + trench, C2's 8, C3 cliffs, SM2 survivors;
# owner rulings then: crater-vs-dam clause, KDFW bounds, snap
# radius, C1-model revisit; (5) Grade Debt Ledger REFRESH (current
# one is pre-F3/R8 numbers) + final report; (6) app 1.0.254+ build
# (engine 1.50.1696 frozen; make_app was refused while app ran —
# re-run make_app + verify embedded==dist). Standing docket: F5
# OLS-road joint (H1), HECA H2 verify post-C3/R6, r5base/sm3base/
# kafwctl control worktrees to tear down --force when done.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260815f (R5c MERGED, F3 HELD AT CAP, GRADE DEBT LEDGER published)
# R5c reviewed+adjudicated by the lead: PASS (CYXY 333/74 airside,
# HECA 6,955/1,733 — both better, airside byte-stable; the stale
# T203504 arm was mid-implementation; honest arm T210728). Merged to
# main; composed-main builds CONFIRM lane numbers (T214510/T214605);
# covering twins pass. F3+F3b: solve refusal fixed (ceiling-only
# stage — a (0,0) pin had inverted 677 nodes uniformly 1.8009 m),
# validator staged (cones from CONFORMED ends only; MIN_FALL kept
# provisional per charter; 262 twins), but 1,323 airside
# drainage_spine rows (worst 25.6, median 76 m from parents) are an
# UNLOCATED EMITTER POPULATION — HELD at the attempt cap on
# lane/gapconform; next: rows->way-ids->emitter attribution.
# KAFW BISECT VERDICT (owner's seam frame refuted too): NOT a
# regression (identical to d787464), NOT the seam (877 m away,
# healthy) — the runway DEM-follow band is per-runway longitudinal;
# parallel runways seat 2.333 m apart across a 136 m connector
# (budget 2.046) -> 0.287 deficit -> refusal. R8 direction: route-
# feasible seeding (or join contacts at taxi crossings, seated
# through faa_joint_solve). KDFW = DIFFERENT family (hard-seed
# plateau 183.286 vs 176.470, 6.8 m, 650 nodes) — unattributed, the
# larger +32-098 blocker. Artifacts Ortho4XP/tmp/kafwbisect/.
# GRADE DEBT LEDGER published (docs/grade-debt-ledger-20260815.md +
# artifact): 8 root-cause categories, priorities C7 (withheld
# patches) > C4 (R6/R7 groundside bulk) > C5 (F3 last pass) > C3
# (owner transverse-cap ruling re-adjudicates ~1,700) > C1/C2
# (airside end-game, gated on the two open K1b rulings).
# App 1.0.254: engine 1.50.1696 FROZEN; make_app REFUSED (owner is
# running the app) — quit + rerun make_app, verify embedded==dist.
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# 20260815e (HANDOVER — F3/R5c LANES BUILT+HELD, THREE NEW OWNER
# RULINGS, KAFW SEAM BISECT QUEUED; agents died at the account
# monthly SPEND LIMIT — no subagents until raised)
# Post-1.0.253 owner in-sim rounds, all attributed:
# LOT-OVER-ROAD DOSSIER (CYXY 377): DSF .pol pavement arrives as one
#   blob; free-road test is WIDTH-ONLY (no landside term) so lots
#   absorb public roads (82-93% stations dropped; HECA 142/160
#   groundside shapes contain roads); no production path can split.
# SINK DOSSIER: groundside = min(terrain, 8% cone from perimeter
#   welds) — CUT-ONLY; lot 377's low weld inherited from building
#   25's pad datum (5.03m gap → 92.8% cut, 40k m³); predates ALL
#   2026-08-15 rounds (every arm within 0.11m); apron 42 mirror =
#   99.6% fill. Owner's 3.2m step = lot spans the min() branch
#   switch between two road faces on one chain (axis 182).
# THREE NEW RULINGS (canon updated): (1) roads carry spines like
#   taxiways, OSM ways as source, spines PASS THROUGH pavement
#   (lots/aprons consume spine stations — taxiway-through-apron
#   precedent); (2) roads weld to aprons at MOUTHS ONLY, never to
#   buildings; parallel frontage >1.5x width cuts back to DEM
#   (multi-level terminal frontage is real — CYXY 2nd-story road);
#   (3) groundside lots CUT AND FILL (two-sided projection
#   supersedes cut-only). Together = the R7 frontage/lot round
#   (spec next session; composes with, does not conflict with,
#   F3/R5c). Also RULED: gap rings conform near pavement + eroded-
#   pocket interior + spines never below terrain (= spec F3,
#   docs/specs/gap-conformance-spec.md).
# LANES (agents died at spend limit; work PRESERVED, NOT merged):
#   lane/gapconform (F3) 46f4630: CYXY acceptance PASSED (agent-
#   verified, committed); HECA arm built by lead post-mortem
#   (HECA_20260815T203509, cf79ec64d773) — censuses 8,315 vs 6,998:
#   +1,332 ALL ONE FAMILY airside drainage_spine (instrument-vs-law:
#   the family flags spines at-or-above pavement edge; F3 spines
#   START at conformed pavement value BY the new ruling) + gs
#   transverse +429 (needs eyes). ADJUDICATION OPEN: re-found the
#   drainage_spine family under the new law (harness law change,
#   twins) before judging F3; all other airside families +0.
#   lane/roadchar (R5c) 84df5ee: lead PRESERVATION commit of the
#   dead agent's uncommitted tree (reversal suppression + corridor
#   co-level + twins) — NOT reviewed, NOT adjudicated; its arms are
#   built (CYXY_20260815T203504, r5checa rc=0) awaiting census +
#   lead diff review.
# KAFW ("KAFL" resolved): straddles lat 33; +33 sliver patched OK,
#   +32 main REFUSED 20:16 — FINAL band INVERTED 9/994 nodes. OWNER
#   CORRECTED the clip hypothesis: seam-through-runway is a HANDLED
#   class (seam edge = DEM anchor; SPLP fixture; twins exist) — a
#   2026-08-15 round broke the seam-anchor interaction. BISECT
#   queued: KAFW +32 arm at dd6473f vs merged main; suspects
#   mouthweld prox anchors / R2/R3 / R5 pegs.
# ALSO: airport-index "gone" scare = intact (engine+cache+Swift all
#   verified; fresh-signature TCC re-prompt clears the map via the
#   "none" reply — owner chip task_053c0752 fixes the erase); a
#   second repo-root docs/RULINGS.md was created in error and
#   merged back (one canon only).
# NEXT SESSION: (1) drainage_spine family re-found → adjudicate F3;
#   (2) review+adjudicate R5c; (3) merge what passes → app 1.0.254;
#   (4) KAFW bisect; (5) R7 spec (three rulings above); (6) HECA
#   H1/H2 residuals (F5 OLS-road joint; substrate). Standing queue
#   unchanged. r5base lane needs re-mount or down --force.
# ══════════════════════════════════════════════════════════════════
# 20260815d (R5 TERRAIN-TRACKING ROADS MERGED — app 1.0.253, owner
# in-sim pending; R5b refuted)
# Owner in-sim on 1.0.252: CYXY terrain FIXED (warm-start retirement
# holds); 8 new road/groundside sites, all attributed to FIVE
# families: F1 taut-chord (roads strung straight between mouths —
# CYXY causeway 30.71/-135.073 +5.2m over a dip, canyon complex
# 60.7016/-135.0674 flat 706 under 718-722 HRDEM, HECA plateau;
# who_wrote-confirmed the solve ingests the held chord), F2
# pointwise-jagged (no/1-peg runs post-R4 on rough DEM; HECA
# 30.1091/31.4080 7m swings), F3 stamped-low flats (gap_drainage_
# spine flat 695.8 = 7.7m BELOW terrain at CYXY 60.7124/-135.0802;
# HECA plateau's 94.9 side), F4 = F2 sibling (HECA 30.1048/31.3980),
# F5 OLS-cut-through-road (real ols_cut/ols_transitional shapes
# 3381/3382 at HECA H1; cut slices road without a joint).
# R5 (spec + R5b + refutation in service-road-law-spec.md, owner-
# ratified w/ longitudinal-cap + lateral-flat conditions):
# track_dem_profile = cap-Lipschitz least-deviation tracker of
# low-passed station DEM (provably sup-norm minimal), service-road
# runs only, taut string stays airside; R4 span rule kept; unpegged
# stretches tracked as SEEDS. MEASURED (Opus lane, matched control):
# road 349 dips -0.32..+0.84m vs HRDEM (was +5.2 causeway),
# junction-190 rises 710.7-720.7 (was flat 706), HECA -11585 stays
# ambient, AIRSIDE BYTE-IDENTICAL both airports both arms. Census
# CYXY 303->377 / HECA 6,700->6,998 — ALL groundside, transverse
# rows more-but-milder (p90 excess 2.46->1.60m): pricing real
# cross-corridor relief a chord hid. R5b (tracker HOLDS) REFUTED:
# sites unchanged, transverse flat, +211 HECA via ONE-SIDED
# WELD-OR-GAP (frozen 1-D profile vs welded 2-D neighbours); the
# over-cap-emitted-segment instrument reads RELIEF not roughening
# (chord has none by construction). Seeds arm d7e3435 merged;
# 7919c3e NOT merged (lane keeps it). Twins 136+1 pre-existing.
# App 1.0.253 / engine 1.50.1695, embedded==dist verified.
# TILE-SEAM CHECK (owner report "KAFL" + SPLP): round touched ZERO
# tile-cut/mesh code; SPLP seam envelope BYTE-IDENTICAL pre/post
# round (lon min -76.99995, 0 nodes on -77 meridian, both eras;
# ledger artifact s6_before); 58 seam/tile-cut twins pass. KAFL not
# in any apt.dat (closest PAFL, mid-tile) — ICAO/latlon requested
# from owner. HYPOTHESIS: mixed-version tile seams — tiles built on
# 1.0.249-251 carry warm-start-flattened terrain (up to 22.7m at
# range, largest at tile edges); seam vs differently-built neighbor
# = uneven ground; remedy is rebuilding both tiles on 1.0.253.
# DOCKET adds: one-sided weld-or-gap class (joins node-vs-edge
# mouth law pair — law-paired boundaries, never a frozen side);
# CYXY weld site 60.69699,-135.05965 (0.76/0.61m steps, dossiered);
# service_road -10368 plane sliver; F3 stamped-low flats lane; F5
# OLS-road joint lane; F2 no-substrate road population; r5base lane
# needs re-mount (up r5base 32e6cc3) or down --force (control
# patches CYXYBASE/HECABASE.osm intact in /tmp/harness).
# OWNER QUEUE: in-sim 1.0.253 (the road-terrain round's acceptance);
# KAFL identity; R5/R5b rulings ratified-by-conditions, refutation
# recorded. STANDING QUEUE unchanged from 20260815c.
# ══════════════════════════════════════════════════════════════════
# 20260815c (SERVICE-ROAD ROUND MERGED — app 1.0.252 built, owner
# in-sim pending)
# All three 20260815b blockers cleared and svcround MERGED to main
# (162c22c, on top of the concurrent session's dd6473f airport-index
# commit; DEFERRED_VERIFICATION union-resolved).
# (B1) ATTRIBUTED + FIXED — R4 spec amendment (service-road-law-spec):
#   the whole-run corridor string held values BEYOND its pegged span.
#   Run (46,0): 2,364.6 m, 265 stations, pegs ONLY at s=0/3.0/7.2 m
#   (south mouth welds ≈127.21) → strung FLAT end to end, stamping
#   -11585 37.6 m over ambient. Interventional chain: R1-off arm
#   erupts identically (R1 EXONERATED); O4_SVC_SPINE_DEBUG_LL station
#   dump = WHOLE-RUN tgt 127.2132 over DEM 89.7; peg dump (temporary
#   probe) showed the one-sided pegs. Far-end DEM tie REFUSED as the
#   fix — it re-draws the run as a km-scale chord (~8 m census-
#   invisible mid-corridor ridge, the warm-start in-sim-only class).
#   Fix `_r4_pegged_span` (anchors.py): string [first..last peg] only;
#   <=1-peg runs entirely pointwise (retires the caller's synthetic
#   both-end DEM tie — same chord class); outside-span stations keep
#   spine-first DEM-follow. 5 twins. Eruption gone (ring 89.6–89.7).
#   HECA 6,908→6,700 (within_shape −216, transverse +24 honest ≤ old
#   worst, no new family); CYXY 294→303 (+9 all groundside, new rows
#   ≤0.36 m, worst unchanged — the composed 294 partly rode the
#   retired unlawful mechanism). R4 amendment awaits OWNER
#   RATIFICATION (recorded in the spec).
# (B2) ADJUDICATED: apron within_shape +21 / transverse +9 / strip_arc
#   +5 / strip_long +1 = honest pricing (distributions identical,
#   worst 11.35→11.36, p50 0.90→0.89; headline 8.55/6.15 tears are
#   PRE-EXISTING sites renumbered). ONE real regression site
#   30.1110,31.4283: 44 airside rows ≤2.59 m (38 strip_seam_tear + 4
#   adjacent_ground_tear + 2 within_shape) where service roads thread
#   between graded strips — strips re-conform unevenly to moved road
#   values; net site 13→52 rows though 5 groundside fixed. DOCKETED
#   (joins the node-vs-edge mouth law pair docket — one owner per
#   seam). (B3) ADJUDICATED: 8 rows, ONE spine (way -13304) at
#   30.107010,31.401492, ≤1.348 m — gapstop's own held item, the
#   concave-notch class already docketed; accepted as named residual.
# Twins on merged main: the 7 covering files 173 pass + the SAME
# pre-existing test_lateral_cross_section::test_the_solve_ingests...
# failure (stale twin, docketed). App 1.0.252 (engine 1.50.1694,
# embedded == dist freeze ef3949953110) — THE FIRST HONEST TERRAIN
# BUILD (1.0.251 still had the retired warm-start flattener); owner
# in-sim on 1.0.252 is the round's acceptance. TCC note: fresh app
# signature will re-prompt volume access (0% CPU at solve start =
# pending prompt; tccutil reset + killall tccd if stuck).
# OWNER QUEUE: ratify R4; rule on B2-site docket + B3 residual;
# in-sim verdict on 1.0.252 (terrain character at CYXY range
# especially — the warm-start class detector is in-sim only).
# DOCKET UNCHANGED from 20260815b (node-vs-edge law pair, gap spine
# clip-to-face, late-roled faces, apt.dat SVC carve, _svc_dup_block,
# stale lateral twin) + STANDING QUEUE (2026-08-12a triage, deletion
# sweep, task_898e3c75; rwy-flexed/string-bend rulings).
# ══════════════════════════════════════════════════════════════════
# 20260815b (HANDOVER — SERVICE-ROAD ROUND: 4 LANES COMPOSED, ONE
# ERUPTION BLOCKS THE MERGE)
# Owner bug reports (all root-caused, all lanes implemented+committed):
# lane/luneix (curved-road chord rects: _split_at_bends chord-deviation
# break at half-width; CYXY 114/133 class; apt.dat SVC carve site
# DOCKETED), lane/gapstop (spines/drainage stop at service roads:
# _enclave_exempt never-exempts service roles + construct mirrors the
# emitter's subdivision; owner site FIXED; residuals docketed: 6 spines
# whose AXIS CHORD cuts a concave notch (33 m), 20 late-roled-road
# faces), lane/mouthweld (proximity mouth anchors, airside-pavement-
# only edges, svc_mouth HELD keyset + emission-time re-seat before the
# final projection; owner cliff 8.246->0.000; in-tolerance sites
# 25->9; the 7-site residual is STRUCTURAL — pavement moves INSIDE the
# final projection — the NODE-VS-EDGE LAW PAIR in the one graph is the
# docketed true fix), lane/roadlaw (spec service-road-law-spec.md:
# R1 releases unlawfully-held profile stations (HECA 1,146/288 runs;
# they were emitted at up to 80.49% vs the 8% cap and FROZEN), R2
# lateral pass reads all 816 registered chains (feet 492->36k), R3
# nearest-route transverse cap (7,999 pairs)).
# COMPOSED on the svcround worktree (branch tip 'Merge lane/mouthweld',
# all 4 lanes merged clean; twins 168 pass + 1 PRE-EXISTING main
# failure test_lateral_cross_section::test_the_solve_ingests...).
# COMPOSED RESULTS: CYXY 294 adjudicated vs 313 baseline (BETTER, the
# per-lane +57 transverse composed away); HECA 6,908 vs 7,196,
# transverse 2,796->1,391 HALVED. THREE MERGE BLOCKERS:
# (B1) NEW 40.34 m ERUPTION: service_junction -11585 (shapeID 1585) —
#   its whole 20-node ring stamped 127.21 where baseline is 89.61, NO
#   airside pavement within 25 m; groundside ring -12838 + 2 gap faces
#   tear against it (40 rows @ 30.10937,31.38545). PROVEN NOT a mouth
#   seat (svc_mouth dump: 129 seats, none at 127.21). Suspects: an
#   R1-RELEASED station falling into the DEM-follow break-blend, or a
#   wrong station value in R2's densified substrate. Artifacts: dump-
#   arm patch HECA_20260815T1537-ish + svcround tmp/svcround_heca_
#   dump.log (O4_STEP_DEBUG=1) + /tmp/harness/svc_mouth_dump.json +
#   composed patch HECA_20260815T1509 (de3432a27a79).
# (B2) AIRSIDE ACCEPTANCE 1,729->1,821 (+92): strip_seam_tear 9->45,
#   graded_strip|graded_strip +45, frontage_near_miss +26, apron +38 —
#   strips re-conform to moved road/groundside values; adjudicate
#   real-regression vs honest-pricing per class (roadlaw's own +7/+7
#   was the single-lane reading).
# (B3) drainage_spine 0->8 (ONE new spine, way -13304, host apron
#   -12275, values to 1.348 m at-or-above pavement edge; gapstop's
#   held item; survives composition; bounded one-site attribution).
# NEXT SESSION: attribute B1 (lane-bisect gates: O4_SVC_MOUTH_PROX_
# ANCHOR=0 exists; R1 has no gate — bisect by reverting _profile_law_
# release in the worktree, or read the step-debug log's station
# report for -11585's nodes -24120/-24121), adjudicate B2/B3, then
# merge svcround -> main, run the covering twins once, build app
# 1.0.252 (make_engine trap: park Ortho4XP/tmp/engine_caches to
# .engine_caches_parked/ first, restore after; verify embedded ==
# dist freeze). ⚠ APP 1.0.251 PRE-DATES THE WARM-START RETIREMENT
# (b166906e): it still flattens terrain km-scale — owner must not
# judge terrain in it; 1.0.252 is the first honest terrain build.
# DOCKET (this round's residuals): node-vs-edge mouth law pair; gap
# spine clip-to-face; late-roled road population (20 faces); apt.dat
# SVC carve chord rects; pipeline _svc_dup_block staleness (feed-vs-
# feed dupes never tested); stale test_lateral_cross_section twin;
# harness minute-collision fix (owner runs task_fcc5c569 separately).
# STANDING QUEUE UNCHANGED: 2026-08-12a ratification triage, deletion
# sweep, o4_schema_snapshot chip (task_898e3c75), owner rulings open:
# groundside_pavement as gap blocker?, rwy-flexed/string-bend classes.
# ══════════════════════════════════════════════════════════════════
