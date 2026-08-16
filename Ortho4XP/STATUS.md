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
