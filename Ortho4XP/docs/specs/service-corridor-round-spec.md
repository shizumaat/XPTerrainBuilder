# Service-corridor round (Fable spec, 2026-08-12b)

Owner rulings (RULINGS.md 2026-08-12b, recorded from the in-sim session):
service roads ENABLED AND BUILT; apt.dat truck routes are an authoritative
corridor source, one corridor = ONE continuous law object; a road's own
course is never terraced — free ends grade to DEM under the road cap; the
HECA svc_break residue dispositions are re-opened. PRE-SHIP DEV MODE and
all standing lane mechanics apply. Deviations STOP-and-report to this
spec's author.

## Evidence base (all measured this session)

- KCLT ramp corridor (35.2136167,-80.9422409 → 35.2140148,-80.940769 →
  35.213515,-80.9403524): OSM ways -12868/-12869 (highway=service,
  node-shared, contiguous) exist and are read; NO apt.dat 1206 coverage
  (nearest edge 20.4 m off-corridor). ~30 m pavement gap from ramp top
  (214.04) to taxiway (218.7); R20-2's second clause unpaid.
- KCLT lot road (35.2069238,-80.93057 → 35.2077303,-80.9290869): R20-3
  site; NO 1206 coverage (143 m). The 263 m ribbon -11671 (mean width
  11.6 m) fails road_corridor because ONE ≥25 m widening at the lot
  entrance (blobs at 35.2068789,-80.9312496 / 35.2071122,-80.9302925)
  denies the whole shape; SCORER_SERVICE_ADJ ships OFF; terrace wall
  -12626 crosses the road at the third coordinate (+5.56 m hang; ring
  grade reads to 11.44%).
- HECA corridor A (30.1121738,31.4062992 → 30.115711,31.4112487) and
  corridor B (30.1118558,31.4066355 → 30.1149222,31.4107135): BOTH
  CONTINUOUS in apt.dat 1206 (5 edges/607.7 m and 6 edges/508.0 m, zero
  internal gaps, name 'N', max lateral deviation 9.0/1.8 m). Emitted
  state: corridor A covered by FOUR disjoint 2-node axes with axis-free
  gaps s97-254 and s269-593; 6.18 m cap-ridden hump at
  (30.1126780,31.4068387) with ±8% flanks and −25%/−19% discharge
  pockets in -13274/-12237; corridor B has ZERO road representation
  (imagery on mega-apron -10629). No seat/pad anchor within 60 m of the
  hump; terrace/fan structures empty in the sidecar.
- Machinery: build_service_road_network (pavement/service_roads.py:113-231,
  gated by ENABLE_SERVICE_ROADS=False at config.py:2136) mints
  service_road/service_junction rects (6.0 m width, 25 m min, 1.0 m
  pavement-clear, junction fill); callsite pipeline.py:3662 unions
  apt_service_centerlines (1206, via apt_dat_reader.py:2093-2155
  name-grouped linemerge) + OSM small roads clipped to pav_union 25 m
  buffer, NO source dedupe. SERVICE_ROAD_CARVE (default ON) already
  registers 1206 routes as service TaxiCenterlines; since cycle 9 the
  grade graph reads layout._slice_service_subsegments INSTEAD of the
  unscoped originals (grade_graph.py:447-452 — one-road-two-spines
  hazard). Grade law: SERVICE_ROAD_MAX_GRADE=0.080 is THE number;
  service_roads.py docstring says 4%, grade_graph.py:25 says 5% — both
  stale.

## Rulings (design decisions, mine)

1. **Sources and precedence.** apt.dat 1206 routes are authoritative
   where present; OSM small roads complement. DEDUPE AT CENTERLINE
   LEVEL, before minting: an OSM small-road line whose 6 m corridor
   overlaps a 1206 route's corridor by more than half its own length is
   suppressed (the 1206 spelling wins). The existing downstream
   rect-overlap skip stays as belt.
2. **Minting.** ENABLE_SERVICE_ROADS flips to a config var default ON
   (keep an O4_ env kill switch, recorded in gates_on). The minter runs
   as today (rects + junction fill, pavement-clear), so pavement is
   minted ONLY where none exists — existing ribbons/aprons are not
   double-paved. Stale docstrings/annotations fixed: ONE grade number
   (SERVICE_ROAD_MAX_GRADE), TaxiCenterline type spelled correctly
   (layout.py:766, service_roads.py:114).
3. **One law object per corridor.** Each 1206 name-group (and each
   surviving OSM chain) becomes ONE corridor chain end-to-end in the
   grade graph: axis coverage with NO axis-free gaps, junctions are
   interior nodes. Rod-degree≥3 splitting stays for TAXIWAY rods; a
   service corridor's own through-run does not split at minor service
   branches (a branch grafts, the trunk continues). The corridor
   profile solves as one chain under the road cap; break-region
   discharge on a corridor is UNLAWFUL (re-opened residue) — an
   infeasibility must surface as a named refusal, not a −25% pocket.
4. **Free-end law.** A corridor end not terminating on pavement ties to
   ambient DEM (the R20-2 walk generalized): the profile reaches DEM
   within the cap. The groundside terrace-wall emitter gains the
   corridor exclusion: no wall may cross a corridor's course (the ruled
   KCLT -12626 case dies by construction, not by special-case).
5. **Classification.** SCORER_SERVICE_ADJ flips ON (the RULINGS:128
   corollary goes live). The road_corridor width read becomes
   corridor-aware: free_road_subsegments-style decomposition first;
   the corridor-width part of a shape classifies as service road even
   when a contiguous widening (lot entrance) exists — the widening
   itself stays groundside pavement. A widening never vetoes the
   ribbon (the measured buffer(-12.5) blobs at the KCLT lot entrance
   are the twin fixture).
6. **Solver integration.** Minted corridor pavement joins the SAME
   spine/one-band machinery as carved service roads (slice subsegments
   composed into the corridor chain of ruling 3 — never two spines for
   one road; grade_graph.py:447-452's invariant is preserved by
   construction: the corridor chain REPLACES, not duplicates, its
   slices).

## Implementation plan (ONE Opus lane — coupled change-set)

1. blast.py on every touched file first; ledgered tests once.
2. Sources: centerline dedupe (ruling 1); enable + env kill switch
   (ruling 2); docstring/type/grade-number cleanup.
3. Corridor chains (ruling 3): compose slice subsegments + minted-rect
   spines into per-corridor chains; register end-to-end; verify HECA
   corridor A axis coverage has NO gap (the s97-254 / s269-593 gaps
   close), corridor B gains a chain.
4. Free-end tie + wall exclusion (ruling 4).
5. Scorer: SCORER_SERVICE_ADJ default ON + corridor-aware width read
   (ruling 5); KCLT ribbon fixture twin.
6. Twins: minter (rect/junction/pavement-clear on a synthetic layout);
   dedupe (1206+OSM coincident → one corridor); corridor chain
   continuity (no axis-free gap on a synthetic 3-branch corridor);
   free-end DEM tie; wall-course exclusion; width-read decomposition
   (entrance-widening fixture); grade-number single-source.
7. Acceptance arms — per the owner-artifact ruling, attribution reads
   against the shipped patches; ONE measured arm per airport at close:
   - KCLT (--patch-only): ramp corridor SURFACED end-to-end (all three
     owner coords covered by road-family pavement, profile within the
     ramp/road datum law, no gap); lot ribbon classified service road,
     wall -12626 gone, profile reaches DEM within 8% at
     35.2077303,-80.9290869 (no cliff); census before/after quoted +
     row-class table (expect the +129-class and hang rows to move).
   - HECA (--patch-only): corridors A and B each ONE chain, axis
     coverage gapless; every span within ±8.0%; the −25%/−19% pockets
     GONE; the 6.18 m hump pulled to the terrain-demanded profile
     (quote profile-vs-chord before/after); corridor B carries road
     representation. Census quoted.
   - CYXY or KSTJ control: byte-identical expected where no corridors
     exist near pavement gaps — quote body hashes.
8. Build-time impact statement REQUIRED (minting + corridor chains run
   per build; expect >0.6 s — quote it, profiling round adjudicates).

Convergence: materiality 0.01 m; attempt cap 2 per named target;
`.progress` heartbeat; shared repo UNCHANGED; commit on the lane branch;
no merge; report with the acceptance table.

## Out of scope

Relief-round items (mega-apron -10629's 15.89 m spread; groundside
grade-to-DEM beyond corridor free ends); the #11 band remedy; taxiway
rod-chain law changes; KCLT tunnel portal machinery (R14 claim law
untouched — corridors mint plain road pavement per R20-2's clause).
