# Terrace flip readiness V2: the lockstep frame, the two real defects

Fable spec (designer-authored, lead-approved with the §3(d) ruling below) V2, 2026-08-05. Supersedes terrace-flip-readiness-
spec.md (WITHDRAWN at preflight, canon verdict 00e90db appended there;
evidence scratchpad terrace2/FLIP-EVIDENCE.md; zero builds spent).
Lines against 56866b1. BINDING: docs/RULINGS.md (airside-first; law
compliance not instrument-zero; single-solve/single-pass;
runway-edge/strip law; owner terrace ruling; timing SUSPENDED).
Premise chain, stated so no round re-litigates it: V1's §3 premises
were NON-LAW-TRUE — the flip lane's census instrument
(flipadj/census.py) never passed `terrace_joints_ll` to `run_checks`,
so every terrace-arm row was judged by the bare cap while production
law-true (`tests/test_pavement_grade.py:291`) consumes the sidecar.
Preflight refuted §3(d) (0/35 riser rows joint-adjacent) and §3(e)
(the 378.1 m carrier crosses 1 declared joint; LAWFUL; the 3.98→4.89
"worsening" exists only in the joint-blind reader).

## The corrected evidence base (lockstep frame; terrace2/, zero builds)

Single-gate A/B (FLIP5 vs F5_NO_TERRACE), r1=r2 body-hash determinism
at all three airports. AIRSIDE rows, control → terrace, full lockstep:
HEAZ 98 → 77 (**−21**); HECA 8224 → 5978 (**−2246**); KCLT 2376 → 2237
(**−139** — V1's "+52 regression" was the instrument artifact).
Groundside: HECA −97, KCLT −6, HEAZ 0. V1's bands 1/2 are therefore
met BEFORE this round's work; terrace is a larger airside improver
than the flip adjudication knew. COMPOSED-WORLD NOTE (no re-measure):
every terrace-bearing composed number recorded by the flip lane is
likely an UNDER-counted improvement for the same reason — stated here
once; do not rebuild those arms to prove it.

The two REAL law defects (found offline, both invisible to V1):
D1 **Unfaced declared joints grant unbacked relief.**
   `emit_terrace_joint_faces` skips a face (flank Δ ≤ 0.05 m, or strip
   keepout) but the joint stays in `plan.joints` → the sidecar → grants
   `_terrace_step_allowance` to every crossing chord. HECA 17/118
   (steps to 1.889 m), KCLT 5/17 (to 1.740 m). The S1 in-strip joint
   is one of these — its face was keepout-dropped, its allowance lived.
D2 **Actual step exceeds declared.** 10 HECA faces at 2.14–5.52 m
   actual `|panel_hi − panel_lo|` vs 1.767–1.994 m declared vs the
   2.0 m `APRON_TERRACE_MAX_STEP_M`. Nothing generation-side bounds
   the settled flank delta, and the validator reads the DECLARED step
   — blind by construction.

## §1 S1 — strip fence structural + frame congruence (CARRIED, unchanged)

Carried verbatim from V1 §1: `corridor_cover` gains the runway-strip
footprint via `adjacent_ground.runway_strip_wall_keepout(layout,
require_gate=False)` — the ONE law function
(`grade_law.runway_strip_wall_keepout_rings`) — buffered by
`APRON_TERRACE_JOINT_CLEARANCE_M` (2.0 m); a joint inside ANY strip is
impossible by construction. Geometry read regardless of
`O4_STRIP_PRECEDENCE` and `O4_RUNWAY_STRIP_WALL_LAW` state. The
validator-side open-ring dedupe (rsa amendment 4: endpoints 0.27–0.98 m,
width to 1.19 m) folds in; the 2.0 m buffer covers residual drift.
Twins: synthetic strip-overlap apron; the KCLT 1.53 m site as the named
regression (joint_in_strip = 0 AND wall_in_strip = 0, hard). Updated
evidence note: KCLT `wall_in_strip` already reads 0 (the emitter's
defense-in-depth drop worked); §1 removes the JOINT, and §3(a) below
guarantees the drop class can never again leave an allowance behind.

## §2 — certificate replaces the area guard (CARRIED, unchanged)

Carried verbatim from V1 §2: (a) CERTIFICATE REQUIRED, hard zero — an
apron panelizes only with the recorded chain (raw DEM-infeasible edges
> 0, envelope excess ≥ floor, steep-truth signature), written into the
sidecar (`certificates` key) so the twin audits from the patch alone;
(b) fire bounded by evidence — joints per apron ≤ ceil(certified
relief / max step); (c) area DEMOTED to report — `is_overfire()` and
`APRON_TERRACE_OVERFIRE_AREA_FRAC` retired, the fraction quoted
honestly (HECA ≥ 70 %, HEAZ ≥ 50 % expected — high BY LAW, and said
so). Owner look-for (never a blocker): do HECA's terraced big ramps
read as plausible graded aprons? Acceptable ⇒ ratified; over-terraced
⇒ he names the bound.

## §3 — the re-aim: declaration ↔ face ↔ allowance are ONE fact

### (a) Faced-or-no-relief lockstep (D1)

A joint's admissibility is decided ONCE, at PLAN time, by geometry
that needs no solve: both candidate retreat bands (either side — the
low side is unknown pre-solve) are tested against every keepout. A
joint that could not face on EITHER side is STILLBORN — never in
`plan.joints`, never a solver budget, never a sidecar row. RULING on
the coordinator's question (keepout-dropped joints must also lose
their solver budget): with §1 landed the keepout class is empty by
construction (strip footprint + 2.0 m clearance > 0.6 m retreat), and
plan-time admissibility makes the rule self-enforcing for every OTHER
keepout the wall machinery ever grows — the budget cannot outlive the
face because both are minted from the same plan-time fact. A face
drop at emit time for keepout reasons becomes a LOUD counter that
must read 0 (its firing means the plan-time predicate and the emit
predicate diverged — a frame bug, STOP).

The remaining drop reason — flanks settled level (Δ ≤ 0.05 m) — is
only knowable post-solve. Those joints emit no face and are DEMOTED
IN THE SIDECAR: `step_m` := the ACTUAL settled step (0 for the level
class), so the validator grants exactly what the surface expresses.
No second solve is needed, and demotion mints no unbacked-relief
rows once (b) holds, by algebra: a crossing chord a→b decomposes as
|z_a − z_b| ≤ cap·d_a + actual_step + cap·d_b through the flank pair,
so with the actual step constrained and within-panel law intact, the
chord is lawful under the demoted allowance. The twin states exactly
this: after (a)+(b), a lockstep census re-read of the arms shows zero
rows minted by demotion.

### (b) Actual step bounded by declared (D2) — generation + honest reader

GENERATION-BINDING: each declared joint contributes JOINT-STEP PAIR
CONSTRAINTS to the ONE solve — flanking node pairs (the emitter's
nearest-flank populations, identified at plan time from positions
alone) get `|z_m − z_n| ≤ step_m + cap·planar(m,n)`. The solve can
then never settle a flank delta past the declared step: D2's
2.14–5.52 m class is impossible by construction, and `step_m ≤
APRON_TERRACE_MAX_STEP_M` (existing) transitively bounds the surface.
Single-pass: constraints added to the one solve; no re-derivation —
the plan-time flank populations are handed to both the solver binding
and the face emitter (one computation, two consumers).

VALIDATOR TWIN (the honest instrument — the preflight's caveat is
binding): a new check reads the ACTUAL emitted delta per declared
joint as nearest STRADDLING VERTEX PAIRS — for emitted vertex pairs
(m, n) on opposite sides of the joint line within a short planar
window, `|Δz| ≤ step_m + cap·planar(m,n) + quant noise` — NEVER
flank-window means (a long window folds lawful cap-graded relief into
the number; `panel_lo/hi` stay as report fields only, recomputed as
`actual_step_m` at emit for the census, never trusted by the check).
The validator recomputes actual from the patch + sidecar joint lines;
it does not read the sidecar's actual.

### (c) The undeclared panel-boundary class — joints are interior-only

The HECA specimen: panelized apron `-10519`'s panel leveling
propagated to its OUTER boundary against non-panelized `-10520`
0.72–0.89 m away — 0.57/0.72 m undeclared steps, no joint (nearest
24.3 m), no face. RULING: panel outer boundaries against
non-panelized neighbours keep FULL law; the terrace law owns apron
INTERIORS only, and the lateral-contiguity family governs the outer
ring. Binding, three parts:
1. EXCLUSION: no terrace budget rewrite on any edge with an endpoint
   on a FACING boundary run — a stretch of the apron's exterior ring
   within the step checks' own proximity of another pavement shape.
   Facing-run nodes are held to full apron law against the interior.
2. CONFORMANCE: facing-run nodes gain generation-side cross-shape
   step constraints to the neighbour's nearest ring geometry, with
   the step readers' OWN budget (one shared function — lockstep; the
   same one-fact discipline as (a)/(b)). The boundary then cannot
   drift from the neighbour in the solve, instead of being caught
   drifting by the validator.
3. CLEARANCE: joint lines keep `APRON_TERRACE_JOINT_CLEARANCE_M`
   from facing boundary runs, so no joint discharges its step at a
   neighbour's face.
Twin: synthetic panelized apron 0.8 m from a plain apron — boundary
pairs within step budget, joints repelled from the facing run; the
HECA `-10519`/`-10520` pair is the named regression
(`step_mid::apron|apron` returns to the control count 3; the +2 rows
die).

## §4 The instrument — frame of record + the one-line fix (deliverable)

`scratchpad/flipadj/census.py` gains `terrace_joints_ll=
d.get("terrace_joints") or None` in its `run_checks` call (one line;
terrace2/census_lockstep.py is the model) — delivered as a patch so
no future round repeats the frame error. Frame-of-record statement
for every band below: the LOCKSTEP census (sidecar joints passed),
airside split via side.py; the bare frame is quoted beside it, never
gated on. OFFLINE AUDIT (before any code): the HEAZ band-3
final-projection counter (944→730) predates the sidecar — count how
many of the 730 cross declared joints; the band-3 target from the
parent spec is RETIRED as a gate pending that audit (its residue, if
law-true, is attribution material for a future round — V1's
refinement machinery is OUT of V2, its motivating numbers having been
frame artifacts).

## Pre-registered outcomes (lockstep frame; stress HECA + KCLT,
## HEAZ ride-along, sentinel CYXY)

1. HARD ZEROS, all arms: `joint_in_strip` = 0; `wall_in_strip` = 0;
   joint ∩ `routes_exact` = 0; sidecar joints with `step_m > 0` and
   no emitted face = 0 (D1: HECA 17/118 → 0, KCLT 5/17 → 0); actual-
   step-over-declared rows = 0 (D2: HECA 10 → 0); certificate-free
   panelizations = 0; §3(a) keepout face-drop counter = 0.
2. HECA: airside delta ≤ −1800 success / ≤ −1400 partial (baseline
   −2246; (a)'s demotions, (b)'s step binding and (c)'s boundary law
   re-tighten honestly and may surrender some rows — terrace must
   remain the dominant airside improver); `step_mid::apron|apron` = 3
   (control; the two boundary rows die); the new 1.04 m
   `adj_edge` band tear (179 m from any joint — second-order field)
   adjudicated: count not above control, or attributed by name.
3. KCLT: airside delta ≤ −100 success / ≤ −50 partial (baseline
   −139); joint count falls (in-strip stillborn + 5 unfaced die) —
   reported, not banded.
4. HEAZ: airside delta ≤ −15 success / ≤ −10 partial (baseline −21);
   the 378.1 m carrier row stays absent-or-lawful in lockstep; the
   1.9642 m `transverse::apron` row (581 m from any joint, way
   `-10007`, no joint on it) is pre-registered as NOT a terrace law
   defect — ordinary second-order residue for the release-residue
   lane, quoted honestly, no exemption built for it.
5. CYXY sentinel: zero-trigger — gate-on byte-identical to gate-off.
6. Second-order: demoted (settled-level) joints counted and quoted;
   retaining-wall counts quoted, never netted; runway vertices
   byte-identical; healer never averages across a terrace joint
   (wall-site registration twin carried from V1 §3(d)'s surviving
   half — the `strip_wall_site_index` extension is kept; the READER
   exemptions V1 hung on it are NOT, having been refuted).

## Acceptance

Gate `O4_APRON_TERRACE_LAW`, default "0" in this round's tree; the
FLIP EVIDENCE is the deliverable and the flip lands via the next
train's anchor-minting lane. Gate-off byte identity 2× at HECA +
KCLT + CYXY — pins of record are the reltip lane's own 2× hashes
(HECA `a1ade8bd`, KCLT `307c3fcc`, CYXY `fd43f616`; the run ledger
does NOT carry them — terrace2 verified; re-pin from reltip logs or
fresh 2× at dispatch, assume nothing). Suite: same reds vs matched
pristine control, identical selection; twins T1 strip-fence synthetic
+ KCLT-site regression, T2 footprint congruence (open/closed), T3
certificate invariant + evidence bound, T4 plan-time admissibility
(stillborn joint: no budget, no sidecar row) + demotion algebra
(zero minted rows), T5 joint-step pair constraint (actual ≤ declared
by construction) + the straddling-pair validator on a synthetic
over-step, T6 facing-boundary exclusion/conformance/clearance + the
HECA pair regression, T7 wall-site registration / healer split, T8
sidecar round-trip (certificates + actual_step_m). Offline first:
the §4 band-3 audit + re-verification of the D1/D2 populations on
the existing flipadj patches (scripts exist in terrace2/). Build
budget (honest total): offline + unit twins; gate-on arms HECA +
KCLT + HEAZ ×(≤2 attempts); identity 2×3 ≈ 1.5–2 h foreground,
WORKTREE (venv/OSM_data symlinked), no commit. Timing suspended —
ledger tripwire only. Convergence guards: 0.01 m materiality, 2
attempts, `.progress`.

FLIP EVIDENCE DELIVERABLE (end of round, scratchpad
FLIP-EVIDENCE.md): per-airport lockstep airside/groundside table;
the hard zeros; D1/D2 clearance with before/after populations; the
§4 instrument patch; identity hashes; suite result; the
airside-first verdict line for the lead to fold
`O4_APRON_TERRACE_LAW` into the next train's flip batch.

## STOP rules

Any joint or wall inside a strip footprint (name the emitter-vs-
validator footprint delta first); any joint crossing `routes_exact`;
any sidecar allowance without an emitted face; any actual step past
its declared step; §3(a) keepout face-drop counter > 0 (plan/emit
predicate divergence — frame bug); certificate-free panelization;
demotion mints an unadjudicated row (the (a)+(b) algebra failed —
attribute, don't tolerate); band miss after one attempt on any of
2–4; net airside law-true rise at any arm airport (lockstep frame);
identity mismatch (clean-control first); second miss on any target.

## Out of scope

The flip commit and anchor minting (train tip, lead/owner);
`O4_STRIP_PRECEDENCE`'s own flip (only its footprint geometry is
consumed); V1's refinement/coverage machinery and its band-3 target
(retired pending the §4 audit; frame-artifact motivation); consensus
retirement; split-level seats; string gates; service-spine
relaxation (conservative no-cross stands); groundside lots; the
cut-piece floor; the SPJC emit-amplification corner class (7f6464a,
owed before next flip — a different lane).

OPEN SCOPE ITEM (coordinator decision, flagged not decided): the
lower-panel POLYGON SPLIT (768cded deviation 3 — "queued for the
default-ON round... not a license to skip it") is absent from the V2
brief's §3 re-aim. If this round's flip evidence is the default-ON
event, the adjudication tail says the split rides with it; V2 as
drafted does NOT carry it (the re-aim is the two law defects + the
boundary class). Either the coordinator confirms the split moves to
a named follow-up that lands BEFORE the flip commit, or V2 §3 gains
it back as (d) — the look-for on lap visibility informs severity
either way.

## Owner look-fors (carried from V1; never blockers)

1. HECA big ramps: plausible graded aprons? (ratifies §2)
2. Joint lines up close: doubled-surface/z-fighting along the 0.6 m
   lap band? (orders the polygon-split's severity — NOTE: the split
   itself, V1 §3(c), is NOT in V2's scope; it remains queued from
   768cded deviation 3 and lands with the default-ON round unless
   the look-for escalates it)
3. Step scale: do ~1.5–2 m steps read acceptably? (ratifies
   `APRON_TERRACE_MAX_STEP_M` = 2.0 — note D2's fix makes the
   constant BINDING for the first time; before it, the sim showed
   steps up to 5.5 m that the constant never governed)


## LEAD RULING ON THE OPEN SCOPE ITEM (2026-08-05 04:00): §3 GAINS (d)
## — the polygon split rides this round

768cded deviation 3's obligation ("queued for the default-ON round —
not a license to skip it") binds HERE: this round's flip evidence IS
the default-ON event. §3(d) = the v1 design carried: the lower
panel's apron polygon retreats by the settled wall band (subtract
each wall_poly at face-emit; the ring adopts the wall's lower-edge
vertices by canonical join — no lap, no naked step). Twin: apron ∩
wall area = 0; shared vertices byte-equal. The owner's lap-visibility
look-for orders severity narrative only; the surgery lands
regardless.
