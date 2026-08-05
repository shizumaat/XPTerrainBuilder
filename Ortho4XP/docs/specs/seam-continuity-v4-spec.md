# Seam continuity v4: the healer obeys the census's own law

Fable spec, 2026-08-04, assignment 6 V4 (designer-authored, lead-approved) — the FINAL seam design.
Premise chain: v1 (wrong nodes) → v2 (wrong authority) → v3 (owner
question) → bounds attribution (2ed59bf; scratchpad bounds/): the
question is WITHDRAWN — the inverted guard bounds carry NO two-law
tension (both sides the SAME constant quoted against two excluded
neighbours; inverted iff they differ >1.90 m), and the residual
"genuine tension" class is pavement-bench level changes already ruled
(2026-07-19: a genuine level change is horizontal WALL geometry;
single-authority doctrine; the emit-consensus precedent — the healer
was AVERAGING disagreeing weld authorities into unlawful middles, the
CLAMPED nodes being the lawful ones). Both v3 §3 branches die unbuilt.
Lines against the tip (bd1c8a7-era healer, adjacent_ground.py:1662ff;
re-verify at dispatch). BINDING: docs/RULINGS.md
(feasibility-is-guaranteed; single-pass; law compliance; convergence
guards). Timing is SUSPENDED per the lead — no build-time statements
this round; ledger tripwire only.

## §1 Grade-aware guard (mechanism 1; absorbs the FOURTH copy)

The non-worsening guard's per-neighbour allowance (today
`±(STRIP_SEAM_TEAR_MIN_STEP_M − 0.05)`, adjacent_ground.py:~2040-2050)
becomes IDENTICAL to the census pair predicate:
`max(STRIP_SEAM_TEAR_MIN_STEP_M, STRIP_SEAM_TEAR_MIN_GRADE ·
planar(m,n)) − 0.05` per outside neighbour n. The healer's local
`SEAM_STEP_MIN_GRADE = 0.5` (:1683 — the file itself flags it as the
un-absorbed FOURTH copy, deferred to exactly this round's authority)
is deleted in favour of `strip_seam_law.STRIP_SEAM_TEAR_MIN_GRADE`;
the identity-not-equality twins extend to it. Effect (bounds probe,
arithmetic on the hash-verified tip patches): the inverted-bounds
class empties at the measured sites — the inversion-creating
neighbours are drapes the healer's own cliff test already declared
lawful, so the census-identical allowance admits them. Static
predictions, taken as pre-registration ANCHORS not proofs (the
probe's own caveat — statics cannot see cascades from newly-permitted
moves): CYXY 6→0, HECA 28→~11.

## §2 Authority-split clusters (mechanism 2) — THE ORDERING RULING

The healer must NEVER average across disagreeing weld authorities or
a declared/stacked wall. Design: cluster membership SPLITS at
authority boundaries (the rod-chains-split-at-branches shape) — a
boundary is (a) a pair of weld anchors whose values disagree beyond
the §1 allowance, or (b) a stacked-wall SITE. Each sub-cluster takes
a single lawful target: its own agreeing anchors' level (a mean over
a population that pairwise agrees UNDER the census predicate cannot
mint a row — that is the only condition under which the healer may
ever average, stated as law). An authority JOINT is not healed — it
is deferred to the wall machinery with a named forensics record
(report rows == deferred joints, the existing loudness channel
extended).

**RULED: wall-AWARE healer via one shared predicate — NOT wall passes
reordered before the healer.** Grounds: (i) the existing ORDER
CONTRACT is measured law — heal-before-retreat, because healing after
a retreat drops the unshared retreated vertex and springs the strip
edge back across the wall band (pipeline.py:6236-6241, the CYXY
2.16 m² overlap); wholesale reordering re-opens that defect. (ii)
Single-pass is satisfied by hoisting the wall-SITE predicate (which
strip vertices coincide with designed-split authority corners beyond
`VERTEX_ALT_MERGE_TOL_M` — derivable from layout state before any
wall is emitted) into ONE shared function that the healer consults
and `emit_stacked_conflict_walls` consumes when it runs after —
evaluated once, passed to both; one code path, no second derivation.
(iii) The deferred joints then get their declared wall in the
existing pass order, and the census's straddle exemption
(`STRIP_SEAM_WALL_STRADDLE_TOL_M`, shared module) covers them —
lockstep end to end. A joint the wall pass does NOT pick up is a loud
record and a pre-registered zero.

## §3 Cluster-level guard (mechanism 3 — the radius fix)

Per-node clamping dies. The guard computes ONE feasible interval for
the whole (sub-)cluster: the intersection of every member's
per-neighbour §1 allowances, where the neighbour set is every
non-member within `STRIP_SEAM_TEAR_RADIUS_M` of ANY member — a bound
applies to the CLUSTER, not to whichever mates happen to sit within
radius of one mover. The sub-cluster moves as one level to the
clamped target (no intra-cluster divergence — the 4.26 m
cliff-between-mates-1.5 m-apart class is impossible by construction).
An empty cluster interval AFTER §1+§2 is a loud guarded record with
the lawful-assignment check attached (feasibility-is-guaranteed: the
bounds probe proved a lawful assignment computable at every measured
inverted site — a survivor is attribution, not tolerance).

## §4 Post-healer minting — the instrumented arm (folded in)

Two sites are minted AFTER the healer (wall emitters + late writers,
no reconciliation). The (−100,31) attribution arm is FOLDED into
v4's verification, not a separate probe: ONE instrumented HECA build
with write-only order markers at both suspects —
`final_grade_projection`'s zone writeback vs `to_osm`'s donor-weld
consensus — which doubles as pre-flight parts 2/3 (below). Contingent
fixes, named now: if the zone writeback → extend the
`O4_STRIP_RESOLVE_LAST` reordering precedent (the reconcile unit
already moved once, for exactly this class); if the to_osm consensus
→ the site is the CONSENSUS-RETIREMENT round's named territory —
recorded and fenced there, not patched here.

## §0 Pre-flight (PERMANENT, three-part) applied to v4

Population: the §1-§3 rules bind the healer's cluster population —
join proven against the 34 census rows offline (the guard/decline
records already name them). Authority + ordering: v4's binding site
is INSIDE the healer, so the proof needed is that the healer's output
SURVIVES TO EMIT at the 8 sites — the §4 instrumented arm proves
exactly that (who writes those vertices after the healer, in order),
and it runs FIRST, before any fix arm.

## Pre-registered outcomes (bands; stress HECA, sentinel CYXY,
## battery at the next tip)

0. §4/§0 instrumented arm: healer-output survival proven at ≥6 of 8
   sites; the (−100,31) minter named. Survival failing at the healed
   sites = the v2 lesson repeated ⇒ STOP-and-attribute.
1. v4 arm (gate on, tip defaults): CYXY `seam::seam` 6 → 0-1; HECA
   28 → ≤14 success / ≤20 partial (static anchor ~11); inverted
   (BLOCKED) guard records → 0-2, each surviving one carrying its
   lawful-assignment attribution.
2. SECOND-ORDER (the probe's caveat, promoted to a band): newly
   minted `seam::seam` rows at previously-clean sites = 0 unadjudicated
   (any minted row must trace to a loud record; the guard "actively
   minted" a row once — that class must read zero); pavement vertices
   byte-identical (the healer binds strips only — hard); stacked-wall
   face count changes quoted (deferred authority joints may RAISE it —
   declared lawful geometry, reported not netted).
3. Kill-hold arm (v4 + `O4_YIELD_REF_WEIGHT=0`): the strip class
   HOLDS — HECA ≤ band-1 level + 4, CYXY ≤ 1, against the MEASURED
   kill-control 34 → 109 (battery-2). This is the proof v4's law is
   the load-bearer the pull was. The +74 four-class HECA item
   (junction +48, building +26, transverse +5, step_mid +2 vs net
   −672) remains the recorded KILL-GATING attribution item — out of
   v4's scope, never netted, adjudicated before the kill lands.
4. Loudness invariants: report rows == deferred joints + guarded
   survivors + declined clusters; zero silent exits (hard).
5. Gate-off byte identity 2× on the tip anchors (re-pinned at
   dispatch PRE_REG from refpull_interim/RESULTS.md).

## Acceptance

Gate `O4_STRIP_HEAL_LAW`, default "0", covering §1-§3 as one law (they
interlock: census-identical allowances, split targets, cluster-level
clamping); §4's contingent fix gated separately once attributed.
Suite: same reds vs matched pristine control, identical selection; new
twins (fourth-copy identity, the census-predicate-equality twin — the
guard allowance and `_check_strip_seam_tears` computed from ONE
function; split-at-disagreement membership; cluster-rigid move; the
deferred-joint record; a synthetic of the CYXY inverted site healing
lawfully). Timing suspended — no wall-clock statements; ledger
tripwire only. Build budget: instrumented HECA ×1, v4 arm HECA+CYXY,
kill-hold arm HECA+CYXY, identity 2×5 — foreground, WORKTREE, no
commit; the kill itself remains the lead/owner ANCHOR-MINTING
decision, excluded from this round's authority. Convergence guards:
0.01 m materiality, 2 attempts, `.progress`.

## STOP rules

Band-0 survival miss (binding site wrong again — attribute, never
build the fix arms); any unadjudicated second-order minted row; band-1
miss after one attempt; a deferred joint the wall pass does not pick
up (loud record + attribution, not silent tolerance); kill-hold miss
(v4 is not the load-bearer — re-attribute before any kill talk);
second miss on any target.

## Out of scope

The kill's landing and the +74 kill-gating adjudication (lead/owner);
the to_osm donor-weld consensus if §4 attributes there (consensus
round); the pinch healer `_heal_emitted_band_tears` (untouched); tile
seams; both dead v3 branches; the band-writer single-solve ingestion.

## LEAD VERDICT (2026-08-04 23:30, landed 80a1ec9)

Bands 0/1/2/4/5 PASS (band 1 exceeded: HECA 28→4, CYXY 6→0; zero
unadjudicated minted rows; pavement byte-identical; 10/10 identity).
**O4_STRIP_HEAL_LAW is FLIP-ELIGIBLE for the 06:00 train on this
lane's own evidence** (its stress+sentinel arms ARE the flip arms;
KCLT/SPJC/SPLP ride the tip) — the lead folds it into the P2 flip
batch directly; the flip lane's composed arm predates it. Residue
accepted-with-attribution: the 4 surviving HECA rows are the two
post-healer sites (consensus territory, fenced) + the 1.58 m
unpicked-joint row. STOP 1 (wall pass cannot see 2.1-2.5 m authority
joints — coincidence predicates only) is the NEXT-TRAIN wall-site
redesign item. STOP 2 (kill-hold: a new 48-row region at w=0 — the
guard interval no longer contains the target in the rougher pull-dead
field) keeps THE KILL BLOCKED pending re-attribution; not a release
item. Sixth seam-vocabulary observation: the healer/census predicate
is now ONE function — the lockstep end state the v1 spec wanted,
reached three premises later.
