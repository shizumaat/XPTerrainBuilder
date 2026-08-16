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
