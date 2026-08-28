# HECA round 4 — membrane coverage + do-no-harm relaxation, adoption
# freeze narrowed, road-evidence severance, junction carve-lip profile
# (Fable spec, 2026-08-28; RULINGS 2026-08-28b items 1/2/3/5,
# attribution lane/hecar2 843137cb — every mechanism measured there)

## §0 Measured frame (patch /tmp/harness/hecar2_corrected.osm ==
## padvars_on byte-identical; census ledgered; owner surgery reference
## Ortho4XP/tmp/owner_surgery/HECA_owner_surgery_20260828.osm)

- Item 1: 787 of 2,202 lattice endpoints (36 %) carry NO pair_caps and
  NO airside_no_step edge; the measured void pair (lattice 76.43 ↔
  ring 79.15, 18.51 m, 14.7 % vs 1.5 %) is priced by NOTHING. The 80 m
  threshold governs both lattice firing and void reporting, so 35 m
  interstitial cells are structurally invisible.
- Item 2: the T-site rows are own-law residuals 0.0001–0.0012 pp over
  cap (worst |de| 0.70 m over 46.7 m) — the exact class the no-step
  spec Amendment 3 §2 chartered the DO-NO-HARM RELAXATION for, "IF
  the owner's sim read still shows the dip". It does. ACTIVATED.
- Item 3: the owner's reference surgery removes 49,652 m² (17.7 %) of
  apron 582 whose ground the builder excavates −12.71 m median below
  DEM (worst −15.17). Source: two Tai-pack apt.dat pavements unioned
  into the blob; OSM carries NO apron there but 5+ service roads. The
  scorer's ONLY severance is the aeroway-evidence cut (osm_taxi AND
  osm_apron ≥ 0.2 mix) — shape 605 has osm_taxi 0.0, and NO
  road/service-evidence severance exists at all (road_cover 0.174 ≈
  the cut fraction, unused).
- Item 5(a): the Amendment-2 docket is DISCHARGED — apron −10258 is
  lawfully graded (+0.54 m over DEM, 106/141 edges at its own
  budget); the mis-valued authority is JUNCTION −10250: +6.99 m over
  its own DEM, and 8.20 % on ITS OWN RING at the road-carve lips
  (nodes −3531/−3532 at 109.03–109.06 vs −3533/−3535 at 108.37–108.44,
  8 m apart) — five census rows, all junction|junction no-step.
- Item 5(b): the crossing-adoption freeze covers vertices shared with
  ANY non-road shape; at −10774 the graded_strip-shared pair freezes
  at 106.74/106.87 beside the airside-shared pair at 108.41/108.48 →
  123.11 % on the road ring. Patch-wide: 290 road-family rows ≥1.0 m,
  313 ≥20 % — the owner's "disconnected roads with cliffs" class.
  This is the measured site road-crossing Amendment 2 §3 said would
  reopen the strip-freeze question.

## §H1 EVERY MEMBRANE NODE CARRIES LAW, AND PASS 2 MAY SMOOTH
## (no-step spec Amendment 4, enacted here)

1. COVERAGE GUARANTEE: the no-step enumeration gains a per-membrane-
   node floor — every lattice/station node carries at least one
   direct-distance edge to its nearest ring-or-senior node within the
   window (k-NN sector selection may not orphan a node; the 36 %
   orphan population goes to 0, twin-asserted as a structural
   invariant: zero membrane nodes with no priced neighbour).
2. DO-NO-HARM RELAXATION (the Amendment-3 charter, activated): in
   pass 2, each own-law budget is raised to AT LEAST its pass-1
   residual — pass 2 may then repair no-step/membrane rows without
   being blocked by pre-existing hair-over-cap own-law rows it cannot
   lawfully touch. Do-no-harm is the invariant (no own-law row grows
   beyond its pass-1 residual; twin).
3. Acceptance: item-1 void pair priced and repaired (≤1.5 % over its
   18.5 m); item-2 T-site rows report improved or explained;
   nearest-pair tables at both sites; census honest A/B.

## §H2 THE ADOPTION FREEZE IS AIRSIDE-ONLY (road-crossing spec
## Amendment 4, the ruling Amendment 2 §3 promised)

1. `adopt_road_airside_crossing_values` freezes only vertices shared
   with AIRSIDE shapes (enclaves register). A vertex shared with a
   graded_strip/adjacent-ground RECEIVER is ADOPTABLE — the strip is
   a conforming product, not an authority; after adoption the landed
   taut-strip fairing re-fairs it (no new welding machinery — the
   existing mechanism runs on the adopted values).
2. Acceptance: item-5(b) site — the −10774 ring's four-vertex span
   reads continuous at ≤ its cap; the patch-wide road-family cliff
   class (290 rows ≥1.0 m / 313 ≥20 %) shrinks materially (report
   the numbers); airside byte-identity preserved (the freeze narrows
   — airside-shared vertices stay frozen).

## §H3 ROAD-EVIDENCE SEVERANCE (the scorer's missing cut)

1. The aeroway-evidence severance extends to ROAD/SERVICE evidence
   (extend the ONE existing cutter, never a second): a shape ≥ the
   standing min-area whose road/service cover exceeds the standing
   mix fraction on a coherent sub-region is SEVERED there and the
   pieces re-scored on their own evidence — the mapped service-road
   zone inside blob 605 gets its own GROUNDSIDE verdict instead of
   being outvoted by the airside 82 %.
2. Acceptance: apron 582's emitted extent within the owner's
   reference surgery envelope (IoU of the retained region vs the
   reference ≥ 0.9, report the number); the cut area emits as
   groundside; the 12.7 m drop emits as a LAWFUL TERRACE (groundside
   terrace law — assert it is NOT flattened); the 13 over-cap rows at
   the site die; SPJC/CYXY/LEMD non-regression (severance is
   evidence-gated — report every shape it fires on, expect few).

## §H4 THE TRANSVERSE PROFILE OBEYS NO-STEP ON ITS OWN RING
## (the senior-round's first concrete law; item 5(a))

1. A taxiway-family shape's transverse writeback may not mint a
   direct-distance violation between its OWN ring vertices: the
   writeback clamps ring-vertex pairs within the window to cap ×
   direct distance (the carve-lip class: two lips of one ring 8 m
   apart may not differ by 0.66 m). Junction −10250's +6.99 m DEM
   standoff is bounded by its neighbours through those same pairs.
2. Acceptance: the five junction|junction rows at the item-5(a) site
   die; the road's adopted descent (already at its ceiling) now meets
   a lawful junction face — re-read the crossing line; tier2↔tier2
   no-step rows patch-wide report the delta (this law repairs the
   subset that is WITHIN one ring; cross-shape senior pairs remain
   census-priced dockets).

## §Shared

Flags `O4_MEMBRANE_LAW_FLOOR`, `O4_PASS2_RELAXATION`,
`O4_ADOPT_FREEZE_AIRSIDE_ONLY`, `O4_ROAD_EVIDENCE_SEVER`,
`O4_TRANSVERSE_NO_STEP`, default ON, OFF byte-identical each; twins
per section incl. the preserved priors (strip fairing unchanged
mechanism; aeroway severance unchanged where it fired before).
Acceptance builds: ONE HECA (all four sections read there) +
SPJC/CYXY controls + LEMD for §H3 non-regression. Convergence guards
standard; no shared-repo writes; no timing claims; build-time
statement. The hecar2 lane's `way_authority_read.py` promotes into
`tools/apron_pull_attrib.py` as a `--way`/`--site` scope (second use,
RULINGS 7e90032).
