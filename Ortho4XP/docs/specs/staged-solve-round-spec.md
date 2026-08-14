# Staged-solve round (Fable, 2026-08-13)

Runs AFTER the performance phase (owner ruling "PERFORMANCE PHASE
OPENED") on the fast iteration loop: every lane iterates on
`solve_cut.py` replays (all of this round lives in phases [5]+[6]),
never whole builds, and acceptance arms follow PRE-SHIP-AMENDED law
(attribution A/Bs + ONE measured acceptance arm per lane; consolidated
acceptance is lead-owned). Dev-model v2 throughout.

THE GATE: this round CHANGES emitted bytes on purpose. Its gate is the
frozen-baseline row-by-row explained delta — every census delta vs the
frozen 1.0.245 censuses is attributed to a named mechanism of this
round; a delta a lane cannot attribute is a STOP. Known imperfections
are never silently "improved".

## Evidence base (author-verified today against STATUS/RULINGS and code)

Three independent measured instances of GROUNDSIDE SPINE VARIABLES
PULLING THE AIRSIDE SOLVE — the architecture defect this round retires:
1. Service corridors ON moved HECA airside +130 adjudicated rows with
   solve-stage values on UNCHANGED rings (apron −11906 worst
   0.86→5.69 m) + one 1.21 m seam tear (ship ruling 1.0.244).
2. Rim pockets (knoll fix, mesh 106.3→93.72) put 1,238/1,330 airside
   rows off-face at HECA, median 63 m — parked DEFAULT-OFF
   (`O4_GAP_FILL_RIM_POCKETS`, config.py:5658, verified default 0).
3. OTHH absorption closed interim by POST-SOLVE-ONLY posture
   (`O4_RIM_PRESOLVE_ABSORB`, config.py:5677, default 0; airside 29→9
   kept behind the gate).

KCLT residual (the round's other charter): the two refused
stacked-conflict wall sites. Corridor-joins ruling 2 wired the
corridor keepout into both wall passes; the fallback on intersect is a
bare `continue` — face dropped, nothing grades the abandoned step
(verified: adjacent_ground.py:3075-3078 and :3845-3846). Result:
strip_seam_tear +22 vs frozen (8/26 at the two refused walls, worst
7.18 m). Corridor-joins item 4 ("where the wall exclusion removes a
wall, a graded transition must replace it") is the unpaid law.

HECA corridor profile (re-opened disposition, STATUS 20260812b): plan
straight, defect vertical — 6.18 m cap-ridden hump (crest
30.11268,31.40684, no anchor within 60 m), ±8% cap-riding flanks,
−25%/−19% discharge pockets = break-region/quarantine blend residue;
judged unlawful under RULINGS (quarantine UNAUTHORIZED,
accepted-residue retired, feasibility-is-guaranteed).

OTHH −639 "within" census delta from the corridor round is
UNATTRIBUTED with census-blindness suspicion (R19 precedent: the
census was once blind to whole edge families).

## The law this round lands

**STAGED SOLVE (airside-is-king, executable).** Stage A: the airside
system contains ONLY airside variables — groundside variables
(corridor chains and their rods, groundside terraces, rim-pocket
constructs, absorption) are ABSENT from stage A's constraint system,
not down-weighted. Stage B: groundside solves with stage-A values as
IMMUTABLE boundary data — corridor mouths read welded airside values
(landed law), surfaces the free-road ruling assigns to the apron are
stage-A. Nothing in stage B may write, re-project, or re-blend a
stage-A row (the §7 anti-re-drag memory and writeback band read
stage-A output as fixed).

**WHOLE-RUN CORRIDOR PROFILE.** One corridor = one law object
end-to-end (landed ruling). Its vertical profile is solved as a 1-D
constrained problem over the whole run: mouth endpoints = welded
airside values; free ends = hard DEM ties (landed); interior grade
under the road cap (config's ROAD/SERVICE_ROAD limit — the existing
constant, no new number); the profile is the smoothest lawful path,
never a cap-riding bang-bang trace (the hump/pockets are exactly what
pointwise capping without a whole-run objective produces). Band-lawful
displacement trumps DEM in the interior. The corridor profile then
enters stage B as ONE band consumed by seats/endpoints (ONE-band law).
SCOPING (Fable ruling 2026-08-14, resolving S2's STOP 1): the 1-D
profile HOLDS on the corridor's LINEAR RUNS only — the station
domains where the corridor is genuinely one-dimensional. A 2-D
service surface (junction yard, service apron) is never held to a
line: it solves as a surface with the profile's values as BOUNDARY
SEEDS at its mouths — the same weld posture corridor mouths take at
airside. This is a scoping of the one band, not a second band: the
band carries the held profile along runs and the yard's solved
surface through yards. S2 measured why (KCLT: holding the line over
2-D yards made within-shape pairs unsatisfiable, +157 rows;
releasing them is the fix, not a relaxation).

**GRADED TRANSITION REPLACES A REFUSED WALL.** At a wall face dropped
by the corridor-course keepout, the elevation delta the wall would
have carried is instead graded ALONG the corridor run: an integral
constraint — the step's rise must be absorbed over available run
length under the road cap, entering the corridor's whole-run profile
as an interior constraint, not emitted as a bare step. If the
available run cannot lawfully absorb the rise, that is a REPORTED law
conflict with numbers (feasibility-is-guaranteed: a real airport +
real thresholds has a lawful surface; find what mints the conflict) —
never a quarantine, never a silent step. There is NO wall fallback
behind this mechanism (weld-or-gap ruling): the whole-run profile IS
the resolution.

**WELD OR GAP (owner ruling 2026-08-13, RULINGS "TRANSITION MACHINERY
RETIRES").** The interior adjacency law: touching patch surfaces
AGREE at shared nodes; surfaces that must not couple are separated by
an ambient-DEM gap the mesh drapes; an interior shared-edge
disagreement is ALWAYS a defect. Patch↔DEM transitions belong to
Ortho4XP's own drape. Stacked-conflict walls, groundside terrace
walls, feathers and blend shapes retire AS the conflict classes that
demanded them close; SEAWALLS are the sole survivor (VHHH +
connected-island rulings stand). S5's pad emission simplifies under
the same law: the pad CORE welds to touching pavement and meets the
building base; the blend annulus retires — the gap to ambient DEM is
the mesh's.

**S6 — transition-machinery retirement (sequenced AFTER S1+S2
acceptance).** Retire the interior wall/terrace/feather/blend
emitters (emit_stacked_conflict_walls, emit_groundside_terrace_walls,
the feather and blend paths — enumerate by sweep, seawall paths
exempted by their gate, never by geometry guesswork), measure the
five-airport censuses under weld-or-gap, and route every site whose
step SURVIVES retirement back to its minting mechanism (a surviving
step is a solve defect by definition now, never a re-wall candidate).
Acceptance: censuses adjudicated row-by-row; the owner's in-sim pass
judges the visual result, VHHH's coast explicitly on the list.

## Lanes

**S1 — stage-boundary architecture (solver).** Partition the solve's
variable set airside/groundside; make stage A structurally free of
groundside variables; stage B consumes stage-A output read-only.
Step 1 is attribution: enumerate every coupling by which corridor/rim/
absorption variables currently reach airside rows (the solver
dependency register from the corridor round is the starting
instrument). S1 also owns the REPETITION architecture question (owner
2026-08-13, the single-pass principle made executable for the solve):
the solve builds its unified graph SIX times and runs five seed
passes per run — restaging must state which constructions are
inherently per-stage and collapse the rest to build-once-read-many;
the dupcensus instrument's per-build duplicate table is the measure
that adjudicates it.

THE GEOMETRY FREEZE (owner direction 2026-08-13): all plan geometry
the solve consumes is COMPLETED before any elevation solving — a
named freeze point after which no construction may add, move, or
split solve-consumed geometry. The apron-terrace panel split, the
gap-fill spine admission and the adjacent-ground construct geometry
move BEFORE the freeze (S1 step-1 hypothesis, verified not assumed:
none of them reads a solved value — any that does is a STOP with the
read site named); then ONE node list + ONE unified graph serves the
presolve envelopes, the bands, the groundside probe and the solve.
Elevation-DEPENDENT geometry (conflict walls, terraces, feathers,
blends) stays post-solve and ADDITIVE-ONLY — emitted conforming to
the solved field, never feeding back into it. Post-solve refinement
(tile cuts, conformance welds, densify) becomes VALUE-PRESERVING
(values carried through cuts/welds by interpolation, not
re-projection), which is what lets the mid/late double projection
(owner ruling 2026-07-18, mid-off measured OTHH −64 s under the old
law) collapse to one projection BY CONSTRUCTION rather than by
re-ruling. Not byte-preservable — one graph instead of five is a
different float path by design; the gate is the round's row-by-row
census adjudication, and the dupcensus + solve_cut instruments are
the before/after measures. Acceptance arm (HECA replay): airside rows byte-equal to
the PRE-CORRIDOR airside state on unchanged rings — the +130 rows
return, apron −11906 worst returns ≤0.86 m, the 1.21 m seam tear
gone; every remaining delta row-attributed. CYXY control replay.

**S2 — whole-run corridor profile + KCLT graded transitions.** The
1-D profile solve over each corridor chain (HECA spines A/B the named
sites) and the refused-wall transition constraint (KCLT the named
site). Acceptance arms: HECA replay — hump ≤ materiality over the
smoothed lawful path, zero cap-riding flank runs, zero discharge
pockets beyond cap, corridor_axis_coverage --free-ends clean, seam-weld
tables quoted (row-absence is never evidence); KCLT replay —
strip_seam_tear — CLAUSE SUPERSEDED (Fable 2026-08-14, on S2's
measured refutation): the "+22 refused-wall tears" premise does not
reproduce in the restored frame (control 27 vs frozen 26), and the
worst tear (7.18 m, 35.2201431,-80.9635580) is PRE-EXISTING in the
frozen baseline — a STRIP↔STRIP shared-edge disagreement, not a
corridor defect. Under weld-or-gap an interior shared-edge
disagreement is always a defect: the site routes to S6, resolved by
weld or attributed to its minting mechanism. S2's KCLT acceptance
reduces to: no NEW seam tears attributable to the profile (the
arm's 27→28 resolves in S2b), and the +23 new-violation class
continuing to shrink or attribute.

**S3 — OTHH attribution (measure-first, no fix).** Attribute the −639
within delta row-by-row (frozen census vs corridor census, canonical
identity join — never proximity). First test census DOMAIN coverage
(the R19 blindness class). Then rule: real improvement (mechanism
named) vs blindness (restore domain, re-census). Also proves where
absorption belongs under staging: post-solve-only posture becomes a
stage-B step or retires; the kept airside 29→9 must survive S1's
boundary or be given up (report which).

**S4 — rim-pocket re-enable (sequenced AFTER S1 merges).** Flip
`O4_GAP_FILL_RIM_POCKETS=1` in a lane arm: acceptance = knoll fix
retained (mesh 106.3→93.72 class) AND zero airside off-face rows (the
1,238/1,330 channel gone). If pockets still write airside geometry
under staging, the construct itself is the writer — park it again and
name the write site.

**S5 — object pads in the one solve, RELATIVE COUPLING (owner rulings
2026-08-13 + 2026-08-13b).** MECHANISM SUPERSEDED by the premise test
(lane/s5pads 3065e51): objects render at MESH-under-anchor + AGL +
authored base_y — zero absolute placements exist in either battery
pack, and mesh−DEM at anchors (p50 0.82 m / p90 7.26 m, HECA) is
dominated by our own solved surface, so a pre-solve absolute seat is
infeasible. THE RULED DESIGN: the pad enters the one solve as a
RELATIVE coupling — pad_level − ground_level(anchor) = base_y, a
rigid constraint between two in-solve nodes — terrain meets the base
exactly wherever the solve lawfully puts the anchor's ground.
Grade-law-infeasible couplings fall back to the y-bake path. All
other clauses of the original S5 stand verbatim: the convergence
read-back retires, the sidecar becomes write-only audit at most,
core-only emission under weld-or-gap, and the acceptance arms (a)
determinism tile pair PASSING, (b) pack pristine for coupled objects,
(c) the faster-than-y-bake gate, (d) unchanged check_object_pads law,
(e) row-attributed census deltas. Original charter follows for
context: The next-build convergence
design is RETIRED: the perfbake arm measured its §5.2 fixed-point
promise false (object_pad 689→723→736, sidecar sha still moving after
run 3), and the owner rules no convergence and no multi-build anything.
The replacement: per structure, compute the deviation of the object
base from DEM PRE-SOLVE — the footprint evidence read already runs
before step 1 and the base elevations are pristine pack data
(`.anchor_bak` law) — and where the pad seat can reach the object base
WITHIN THE FEASIBILITY BAND, that adjusted elevation enters the one
solve as the seat's target (the existing building-seat family; seats
consume reach_band_unified per the ONE-band law; no new role, no new
constant — the band itself is the within-reach criterion, which
subsumes the owner's ~1 m motivating class). An object the band cannot
reach keeps the existing rigid-reseat (y-bake) path. RETIRES: the
`o4_object_foot_pads.json` READ-BACK (`config.py` consumer gate region
~4010, `flat_site.py:587`, `object_pads`' request consumption and
`emitted`-record persistence); the sidecar may remain a write-only
audit product of its own build (its pre-consumer posture, which was
byte-identical builds by construction). Acceptance arms: (a)
DETERMINISM — a build→build HECA tile pair byte-identical (the
perfbake arm's criterion 3, now required to PASS; worktree and
artifacts are still up); (b) PACK PRISTINE — zero `.obj` rewrites for
every within-band object (run 1 baked 171 today; quote the count
before/after); (c) THE OWNER'S BUILD-TIME GATE — the in-solve pad path
must cost no more than the y-bake work it eliminates (`--count` +
recorded phases, exclusive pair at close; if it costs MORE, the
feature is not useful — STOP and report, do not land); (d) pads meet
bases under the unchanged `check_object_pads` law (one-solve
doctrine); (e) every census delta row-attributed vs frozen. Premise
with a pre-registered test: the retired design measured seats
POST-MESH — if attribution shows a mesh-vs-patch residual above
materiality at real sites (something pre-solve genuinely cannot see),
quantify it and STOP for the owner; the expectation is it lives under
`DSF_OBJECT_FOOT_PAD_RESIDUAL_M`.

**S1b — the stage partition (Fable design ruling 2026-08-13b, on top
of lane/s1freeze, which stays UNMERGED until this lands).** S1's
phase-1 findings bind: 21 couplings inventoried
(tmp/s1_attribution.md in the s1freeze worktree); the §7 premise was
STALE — the live §10 rod interval reaches final projection as
family="rod_interval" with NO role key, so a partition keyed on
sc["role"] is structurally blind to it. THE KEY DESIGN: stage
membership is a FIRST-CLASS TAG stamped where each constraint entry
is MINTED — shapes from the lawful-airside partition of their role
(the vouching fixpoint, not the raw role literal), rod intervals
inheriting the stage of the rod's owning chain, seats from their
host surface, the S5 pad coupling from its anchor's surface — and
every entry reaching the solve or any projection MUST carry the tag
(an untagged entry is a constructor defect and a twin failure, the
same never-silent posture as the axes sidecar). Stage A solves with
only airside-tagged entries and variables; stage B fixes stage-A
values read-only. MERGE CRITERION, RESTATED IN LAW TERMS (owner 2026-08-14: the law is
BINARY — a row is within grade or it is not; magnitude drift inside a
persisting violation row is NOT a defect metric, per the standing
band-lawful-displacement ruling — and metre-scale wiggles are
imperceptible in-sim): the S1 chain merges when every airside row
that FLIPS INTO VIOLATION vs the pre-corridor reference (ledger
9713491f, body 7bf9038e93f7-class join per S1c) is either gone or
row-attributed to a named lawful mechanism. Magnitude changes at
sites whose violation state is unchanged (the 11.33→11.49 mega-apron
residue class) are recorded as context, never blockers. The original
"apron −11906 worst ≤0.86 m" clause is RETIRED — S1c measured that
site closed by corridor-joins before the freeze; no such site exists.
Seam tear: gone (paid by the freeze). Open at S1c close: net +23
new-violation rows, all in corridor-changed rings — owned by S2's
+152-class work. S1's independent law-defect fix (stations
frozen onto later-decimated rings) and the assert_frozen rail ride
in with it.

**S7 — census domain restoration + drainage retirement (instrument
lane, dispatchable immediately).** Per the S3 blindness verdict and
the 2026-08-13b drainage ruling: service_road/service_junction return
to every family walk the role migration removed them from
(grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES and any sibling domain
list — sweep for the class, including the three never-emitted role
literals S3 flagged); the drainage_minimum family RETIRES for
non-runway surfaces (only runways crown — remove the family or gate
it to runway surfaces per its existing structure; twins prove the
restored roles are READ by the surviving families and that
drainage_minimum reports zero BY LAW). Re-census OTHH + the four
battery airports; the domain-invariant deltas become the round's
comparison frame. S3's absorption finding executes here or in S4:
O4_RIM_PRESOLVE_ABSORB retires (measured inert in production).

## Pre-delegated decisions

- S1 finds a coupling that is emitted GEOMETRY, not a solver variable
  (e.g., a wall polygon feeding airside constraints) → cut it at the
  stage boundary the same way; report the family.
- S2's integral constraint infeasible at a real site → report with
  numbers (rise, run, cap); no quarantine; owner rules only on a
  genuine conflict of laws.
- S3 finds blindness → restore domain FIRST (R19 precedent), re-census,
  then judge; an improvement claim from a blind census is void.
- S4 still off-face → park, name writer, close round without pockets.
- Any airside delta a lane cannot attribute → STOP (identity-mismatch
  law: clean-worktree control first).
- Materiality: 0.01 m elevation classes; seam tears per existing seam
  law threshold; attempt cap 2 per site; heartbeats per convergence law.

## Order and acceptance

S1 ∥ S3 ∥ S5 first (S2 may start on the profile solve against captures
but its acceptance arms re-run on S1's merged boundary; S5's seat
family rides wherever S1's partition puts building seats, so the two
lanes coordinate on that one interface); S4 strictly after S1. Lead-owned consolidated acceptance: one build per baseline airport
on the merged tree; every census delta vs frozen 1.0.245 attributed
row-by-row; disclosed-regression rows (HECA +130 family) must CLOSE,
not persist. Then the owner in-sim pass judges HECA per the ship
ruling.
