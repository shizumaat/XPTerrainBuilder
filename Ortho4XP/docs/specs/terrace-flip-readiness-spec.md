# Terrace flip readiness: the three STOPs designed away

Fable spec, 2026-08-05 (designer-authored, lead-approved). Lines against 56866b1 (release tip).
BINDING: docs/RULINGS.md (airside-first release priority; law compliance
not instrument-zero; feasibility-is-guaranteed; single-pass;
single-solve; runway-edge law — walls NEVER lawful in a strip; owner
terrace ruling 2026-08-04; timing SUSPENDED — ledger tripwire only).
Parent spec: apron-terrace-law-spec.md with ALL adjudication tails
(768cded deviations 1–4). This round's goal IS the flip:
`O4_APRON_TERRACE_LAW` is the single biggest measured HECA airside
improver — **−771 airside rows** in the flip lane's composed arm
(flipadj side-split, 8224→7453; groundside −70 besides), and it owns
the HECA `within_pair::apron|apron` 6,156-row family (OFF census) —
and it was HELD at the release flip on exactly three STOPs. Each gets
a structural fix, not a retune.

## The three STOPs (measured, flipadj/ + terrace_impl/)

S1 **KCLT in-strip joint.** FLIP5 arm: 1 `apron_terrace_joint` sidecar
   vertex inside a runway-strip footprint, declared step 1.53 m
   (KCLT_FLIP5_r1.log:644). The panelizer's no-cross set has NO strip
   fence — only the FACE emitter consults the keepout, so the joint
   (line + step budget + sidecar row) is minted in the strip anyway.
S2 **Over-fire.** Band-6 area guard (>20 %,
   `APRON_TERRACE_OVERFIRE_AREA_FRAC`) trips at HECA (75 %, 28–32
   aprons / 102–118 joints across arms) AND HEAZ (55.2 %, 2 aprons /
   3 joints). The fix population IS the big aprons.
S3 **Panel-size-vs-coverage** (deferred at 768cded). HEAZ band-3
   final-projection over-cap edges 944→855→828→**730** vs ≤700 — a
   second miss on the pre-registered target; the 378.1 m carrier
   (0,163) worst |de| worsens 3.98→4.89 under FLIP5; ONE new
   `transverse::apron` row at 1.9642 m (≤ the 2.0 m max step —
   suggestive, unadjudicated); KCLT airside +52 under terrace
   (apron +152 / junction −111); HECA `step_mid::apron|apron` 3→5 and
   `adj_edge` 1→2 small rises, unadjudicated.

## §1 S1 fix — the strip footprint joins the no-cross set (structural)

`corridor_cover` (apron_terrace.py:414) gains the runway-strip
footprint: union in `adjacent_ground.runway_strip_wall_keepout(layout,
require_gate=False)` — the ONE law function
(`grade_law.runway_strip_wall_keepout_rings`) both the wall emitters and
check_grade already build from — buffered by
`APRON_TERRACE_JOINT_CLEARANCE_M` (2.0 m). A joint inside ANY strip
footprint is then impossible by construction, exactly as joints-
crossing-routes already are: `(terrace line ∩ apron) − cover` can never
yield a piece in a strip.

Gate reconciliation (the brief's named hazard): `require_gate=False` is
the whole answer — the footprint GEOMETRY is read regardless of
`O4_STRIP_PRECEDENCE` (default OFF; that gate governs corridor LAW, not
where strips ARE) and regardless of `O4_RUNWAY_STRIP_WALL_LAW` (its "0"
escape is archaeology; the owner's walls-never-lawful ruling is not
gate-shaped). The existing call in `emit_terrace_joint_faces` already
uses this pattern; it STAYS as defense-in-depth but becomes LOUD: after
§1 a face drop at the keepout means the panelizer fence failed —
counted, reported, and a STOP in this round's arms.

Frame asymmetry folded in (rsa-law amendment 4, QUEUED → lands here):
the emitter derives the footprint from layout rings via `_open_coords`;
check_grade's `_runway_strip_groups` feeds way points WITH the closing
duplicate into the axis fit — endpoints shift 0.27–0.98 m, ring width
up to 1.19 m. One-line fix on the validator side (dedupe the closing
vertex, the transverse checker's own `nids[:-1]` pattern) so the two
footprints are congruent; the 2.0 m buffer in the panelizer covers any
residual drift (> the measured 1.19 m bound). This round owns the
strip-number re-read on its stress airports that the amendment promised.

Twin: synthetic apron overlapping a strip footprint → zero joint
vertices inside footprint+margin; the KCLT 1.53 m site is the named
regression twin (stress arm: `joint_in_strip` = 0 AND `wall_in_strip`
= 0, hard). Footprint-congruence twin: panelizer keepout ⊇ validator
rings on a synthetic runway, both open- and closed-ring input.

## §2 S2 ruling — demand-justification replaces the area instrument

DESIGN RULING (this round is the adjudication venue 768cded named): the
area-share guard is the WRONG INSTRUMENT for the owner's intent. The
guard exists to prevent panelizing LAWFUL aprons (band 6's own words:
"panels only on infeasible-component aprons"). The owner's ruling
targets "LONG aprons on genuinely steep ground" — the target population
IS the large-area family, so an area-share STOP fires precisely when
the law works as ruled and can only be cleared by refusing lawful
terraces: instrument-zero thinking, which the owner has rejected
(census instruments REPORT, the law ADJUDICATES). Measured: HECA
panelizes 31 of 205 candidates (15 % by count, 75 % by area) and every
one carries the raw-DEM steep certificate; the area number is dominated
by exactly the DOSSIER-named carriers.

Re-expression, generation-binding + twin:
(a) CERTIFICATE REQUIRED (hard zero): an apron panelizes only with the
    full recorded chain — `dem_infeasible_edges > 0` (raw,
    instrument-independent), envelope excess ≥ floor, steep-truth
    signature (DEM drop > cap allowance on the witness path). Already
    structural in `plan_apron_terraces`; becomes an INVARIANT: the
    per-apron certificate row is written into the `terrace_joints`
    sidecar (new `certificates` key) so the twin can audit
    joints-without-certificate = 0 from the patch alone.
(b) FIRE BOUNDED BY EVIDENCE: joints per apron ≤
    ceil(certified relief / `APRON_TERRACE_MAX_STEP_M`) + §3
    refinement joints, each refinement joint carrying its own
    per-panel certificate. Steps ≤ max step (unchanged).
(c) AREA DEMOTED TO REPORT: `apron_area_panelized %` is quoted per
    airport, per arm, with the full per-verdict candidate breakdown —
    no STOP power. `is_overfire()` and the band-6 STOP die;
    `APRON_TERRACE_OVERFIRE_AREA_FRAC` is retired (constant deleted,
    census keeps the raw fraction).
OWNER LOOK-FOR (not a blocker — he flies this morning): do HECA's big
terraced ramps read as plausible graded aprons in the sim? Acceptable ⇒
this re-expression stands ratified; over-terraced ⇒ he names the bound
he wants and a follow-up designs under it.

## §3 S3 fix — certificate-driven refinement, the lap surgery, reader lockstep

(a) INTERIOR REFINEMENT (finer panels only where the certificate
    demands). After initial panelization, per PANEL (the
    `_panel_components` groups): re-run the DEM-infeasible prefilter on
    panel-internal edges under their post-rewrite budgets; a panel
    still carrying infeasible edges takes further interior terrace
    lines sized from ITS OWN plane-fit demand (spec §2 of the parent
    already authorizes this; it was never implemented — the 17 %
    straddle-only coverage is the measured gap). ONE refinement pass
    (attempt-cap discipline); per-apron joint total bounded by §2(b);
    demanded-vs-delivered relief recorded per apron (`lost_relief_m`),
    loud, never silent.
(b) LOST LINES RE-PLACED: a terrace line whose pieces all die to the
    cover or the length floor (HECA: 31 lost lines) is re-tried at
    ±¼ and ±½ spacing before being recorded lost — silent capacity
    loss is what starves the carriers the panelization was for.
(c) LOWER-PANEL POLYGON SPLIT (owed since 768cded deviation 3 — "not a
    license to skip it"): the lower panel's apron polygon retreats by
    the wall band (`STACKED_WALL_RETREAT_M`): subtract each settled
    `wall_poly` from the lower panel's apron surface at face-emit time;
    the apron ring adopts the wall's lower-edge vertices (shared
    identity, canonical join — no naked step, no doubled surface).
    Clears the HECA 6,222 m² lap. Twin: apron ∩ wall area = 0; shared
    boundary vertices byte-equal. SIM-LOOK DEPENDENCY (informative
    only): whether the 0.6 m lap band is visible tonight orders
    severity; the surgery lands regardless.
(d) READER LOCKSTEP — joint-adjacent steps are lawful steps in EVERY
    reader, not just within-pair. `_check_transverse_grade` gains the
    same `_terrace_step_allowance` on cross-sections crossing a
    declared joint (sound because joints are outside every corridor by
    §1's construction, and the joint∩route check loudly owns the
    converse). The step readers and the adjacent-ground tear readers
    get the straddle exemption via the SAME machinery seam v4 built:
    terrace joint lines register in `strip_wall_site_index` (one
    shared predicate — the healer then splits clusters at terrace
    joints instead of averaging across them, the
    emit-consensus-mints-violations class fenced by construction) and
    the census straddle exemption covers the faces. ADJUDICATION FIRST,
    offline, zero builds: `jointstraddle.py` on the existing flipadj
    FLIP5 patches — pre-registered: the HEAZ 1.9642 m transverse row
    and the HECA step_mid/adj_edge risers sit within straddle tolerance
    of a declared joint with |de| ≤ declared step + quant noise ⇒
    lawful; ANY of them not joint-adjacent ⇒ real defect ⇒
    STOP-and-attribute before any code lands.
(e) THE 378.1 m CARRIER (HEAZ (0,163), 3.98→4.89): pre-registered
    attribution (offline from the FLIP5 sidecar first): the chord's
    crossing joints were lost/trimmed or its endpoints share a panel
    still infeasible — exactly the (a)/(b) population. After (a)+(b)
    the chord crosses ≥1 joint or its panel certifies feasible.

## Pre-registered outcomes (bands; both frames; airside split via side.py)

1. KCLT (stress; the in-strip twin lives here): `joint_in_strip` = 0,
   `wall_in_strip` = 0, joint∩`routes_exact` = 0 — hard zeros. KCLT
   airside law-true delta (terrace-on vs tip default): ≤ 0 success /
   ≤ +25 partial (measured composed baseline +52; §1 removes the
   strip-adjacent panelization, §3(d) re-judges the joint-adjacent
   share of the apron +152; residue adjudicated per-row).
2. HECA (stress; the fix population): airside law-true delta ≤ −600
   success / ≤ −400 partial (measured −771 composed; the fence and the
   guard change must not silently cost the win); `apron|apron` family
   falls, `apron.cliff` does not rise; hard zeros as (1).
3. HEAZ (band-3 owner; ~40 s, shares HECA's tile): final-projection
   over-cap edges ≤ 550 success / ≤ 700 partial from 730 — ONE fresh
   attempt under the NEW mechanism (§3a/b); a miss is
   STOP-with-attribution, never a retune. Worst within-pair law-true
   EXCESS at (0,163) ≤ its OFF excess (band-lawful displacement
   adjudicates in excess terms, not bare |de|); zero unadjudicated
   `transverse::apron` rows.
4. Certificates: joints-without-certificate = 0 at every airport
   (hard); per-apron joints ≤ evidence bound (hard); area share quoted
   honestly per airport as REPORT (expect HECA still ≥ 70 %, HEAZ
   ≥ 50 % — high BY LAW, and said so).
5. CYXY sentinel: zero-trigger — gate-on byte-identical to gate-off
   (5b7a1912-class precedent from terrace_impl).
6. Second-order: no new `wall_in_strip` anywhere; face-drop counter
   reads 0 (§1 defense-in-depth never fires); retaining-wall counts
   quoted, never netted; runway vertices byte-identical; healer never
   averages across a terrace joint (twin).

## Acceptance

Same gate `O4_APRON_TERRACE_LAW`, still default "0" in this round's
tree — the FLIP EVIDENCE is the deliverable, the flip itself lands via
the next train's anchor-minting lane (never mint anchors twice).
Gate-off byte identity 2× at HECA + KCLT + CYXY, anchors RE-PINNED at
dispatch from the run ledger against the current tip (9863a7e re-pinned
release census; quote what the ledger says, assume nothing). Suite:
same reds vs matched pristine control on an identical selection; new
twins T1 strip-fence synthetic + KCLT-site regression, T2 footprint
congruence (open/closed), T3 certificate invariant + evidence bound,
T4 refinement mints-and-bounds, T5 transverse step-law lockstep (and
joint∩route still ERROR), T6 polygon split (zero lap, shared vertices),
T7 wall-site registration / healer split, T8 sidecar round-trip with
certificates. Offline adjudications (§3d/§3e preflight on existing
flipadj patches) run BEFORE any build. Build budget (honest total):
offline + unit twins first; gate-on arms HECA + KCLT + HEAZ ×(≤2
attempts) + identity runs not answerable from the ledger ≈ 1.5–2 h
foreground, WORKTREE (venv/OSM_data symlinked), no commit. Timing
suspended — no wall-clock claims; ledger tripwire only. Convergence
guards: 0.01 m materiality, 2 attempts, `.progress` heartbeat.

FLIP EVIDENCE DELIVERABLE (end of round, scratchpad FLIP-EVIDENCE.md):
per-airport airside/groundside delta table (side.py frame), the three
STOP clearances each with its measured zero/band, worst-row
adjudications, certificate census, identity hashes, suite result — and
the airside-first verdict line for the lead to fold
`O4_APRON_TERRACE_LAW` into the next train's flip batch.

## STOP rules

Any joint or wall inside a strip footprint (frame-drift recurrence:
name the emitter-vs-validator footprint delta before anything else);
any joint crossing `routes_exact`; §1 face-drop counter > 0; any
certificate-free panelization; §3(d) preflight finds a
non-joint-adjacent riser (attribute before landing the exemption);
band-3 miss after the one fresh attempt; KCLT partial miss; net
airside law-true rise at any arm airport; identity mismatch
(clean-control first, per standing law); second miss on any target.

## Out of scope

The flip commit itself and anchor minting (train tip, lead/owner);
`O4_STRIP_PRECEDENCE`'s own flip (rsa lane; only its footprint
GEOMETRY is consumed here); consensus retirement; split-level seats;
string gates (owner pause); service-spine relaxation (conservative
no-cross stands; the intent question stays queued, nothing here
depends on it); groundside lots; the cut-piece floor.

## Owner look-fors (formulated for this morning's flight, never blockers)

1. HECA big ramps: do the long contour terrace walls read as plausible
   graded aprons? (ratifies §2's guard re-expression, or names the
   bound a follow-up designs under)
2. Terrace joints up close: any doubled-surface/z-fighting band along
   joint lines (the 0.6 m lap, pre-§3c)? (orders the surgery's
   severity; it lands either way)
3. Step scale: do ~1.5–2 m terrace steps at apron edges read
   acceptably? (ratifies provisional `APRON_TERRACE_MAX_STEP_M` = 2.0)
