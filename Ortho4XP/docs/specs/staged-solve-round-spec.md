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

**GRADED TRANSITION REPLACES A REFUSED WALL.** At a wall face dropped
by the corridor-course keepout, the elevation delta the wall would
have carried is instead graded ALONG the corridor run: an integral
constraint — the step's rise must be absorbed over available run
length under the road cap, entering the corridor's whole-run profile
as an interior constraint, not emitted as a bare step. If the
available run cannot lawfully absorb the rise, that is a REPORTED law
conflict with numbers (feasibility-is-guaranteed: a real airport +
real thresholds has a lawful surface; find what mints the conflict) —
never a quarantine, never a silent step.

## Lanes

**S1 — stage-boundary architecture (solver).** Partition the solve's
variable set airside/groundside; make stage A structurally free of
groundside variables; stage B consumes stage-A output read-only.
Step 1 is attribution: enumerate every coupling by which corridor/rim/
absorption variables currently reach airside rows (the solver
dependency register from the corridor round is the starting
instrument). Acceptance arm (HECA replay): airside rows byte-equal to
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
strip_seam_tear returns to frozen-baseline count (the +22 gone or
each survivor row-attributed), the two refused-wall sites show graded
transitions (quote the transition profiles), worst tear at those
sites under the existing seam-law threshold (read it from seam
law code; no new constant).

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

S1 ∥ S3 first (S2 may start on the profile solve against captures but
its acceptance arms re-run on S1's merged boundary); S4 strictly after
S1. Lead-owned consolidated acceptance: one build per baseline airport
on the merged tree; every census delta vs frozen 1.0.245 attributed
row-by-row; disclosed-regression rows (HECA +130 family) must CLOSE,
not persist. Then the owner in-sim pass judges HECA per the ship
ruling.
