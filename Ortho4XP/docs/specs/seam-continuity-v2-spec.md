# Seam continuity v2: strip-fabric law, then the kill

Fable spec, 2026-08-04, assignment 6 V2 (designer-authored, lead-approved) — after the v1 premise
falsification (canon verdict appended at 77ee283; evidence
seam_lane/RESULTS.md; tip frame refpull_interim/RESULTS.md). The
owner's endgame authorization STANDS: delete the pull, re-express as
law — v1 aimed the law at the wrong population. Lines against the tip
(9324cad at writing; the kill inventory is anchored at 47d7904 —
RESULTS.md §6 — and MUST be re-verified by blast.py at dispatch: both
inventories have already drifted once, and `_fp_node_refs` now has TWO
seeding sites, solve.py:6013 and :6112, the second added by the flex
lane). BINDING: docs/RULINGS.md (single-solve architecture;
adjacent-ground zone law; groundside terrace law; law compliance;
convergence guards).

## §0 The falsification, institutionalized

v1 boxed tile-cut vertices; the census class its band 1 quoted
(`seam::seam` = `_check_strip_seam_tears`) counts ADJACENT-GROUND
strip|strip fabric 11–14 km from any graticule line. Tile-cut vertices
exist only at SPLP (36 nodes; seam 0 both arms) — the box bound ZERO
nodes wherever the regression lives. Rule, permanent for this lane:
**POPULATION PRE-FLIGHT** — before any arm is built, an offline join
must prove the law-bound population intersects the census population
it is pre-registered against (here: box-bound nodes cover HECA's 7
seam sites and CYXY's 1). A free check; v1 died for lack of it.

## §1 One vocabulary, one home (brief item 2)

Two "seam" notions coexist: the STRIP seam (tears at the graded-strip
fabric; constants `STRIP_SEAM_TEAR_MIN_STEP_M` 1.0,
`STRIP_SEAM_WALL_STRADDLE_TOL_M` 0.5,
`STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M` 15.0, `STRIP_SEAM_GRADED_ROLES` +
the straddle/open-boundary predicates — today ONLY in
tools/check_grade.py:1589-1662, reached from src only via
verification.py:148's lash `import check_grade`) and the TILE seam
(graticule; `_SEAM_LL_TOL_DEG` 1e-4, `_SEAM_ZONE_M` 400, duplicated by
comment-mirror in grade_graph_validate.py:415-435).

Design: new module **`src/auto_patch/strip_seam_law.py`** — the strip
constants + the straddle and open-boundary predicates move there;
tools/check_grade.py and grade_graph_validate.py import it (the
comment-mirror dies); the solve's new law (§3) reads the SAME module
(lockstep, grade-law completeness). Tile-seam constants stay where
they are but are renamed `TILE_SEAM_*` in place; bare "seam" is banned
in new identifiers. The census row key `seam::seam` is NOT renamed
(baseline continuity — every historical matrix quotes it); its
docstring and the class registry say strip_seam. Byte-inert move,
proven on the tip anchors, landed direct with source-inspection twins
(the two-site-agreement idiom from test_reference_honesty.py).

## §2 The architecture ruling (brief item 1 — ruled, with grounds)

**Ruling A — solve-side box, as the FIRST INSTALMENT of the scheduled
adjacent-ground ingestion, not an alternative to it.** The RULINGS
single-solve entry schedules "adjacent-ground band values" for
ingestion into the solve. A box carried by the final projections IS
that ingestion for the strip fabric: the value-writer's output stops
being defended by a memory (the pull) and becomes a solve-time
CONSTRAINT the projection cannot violate. The writer is not a second
authority under this shape — it supplies the DATUM once (single-pass),
and the box direction is one-way: the datum gives, the projection
conforms. Ingesting the writer wholesale (zones 1-2 value production
inside the solve) remains its own scheduled round; nothing here
pre-empts it, and the box population/datum transfer to it verbatim.

**Ruling B — no global law replaces the pull.** solve.py:6013/:6112
seed `_fp_node_refs` with every non-hard node: the pull is a GLOBAL
anti-re-drag memory. The s7 w=0 census is the evidence base on what
that memory actually protects: every class IMPROVED at w=0 except the
adjacent-ground strip family (`seam::seam` 12→93 at HECA, `adj_edge`
worst 1.05→2.60 — both strip-fabric classes; HECA within fell
9 952→8 511, HEAZ 118→63). The memory is a damping shield that also
holds lawful improvement hostage (~1 400 battery rows at the old
weight). Ruling: the strip fabric is the only casualty that gets a
law; no other population gets a replacement memory. The guard against
an unmeasured second casualty is pre-registration #1 (the kill-control
arm) plus the cross-class STOP — a new regressing class post-kill is a
STOP-with-attribution and gets ITS OWN law, never a revived pull.
HONESTY: the w=0 evidence is from the 0.2-era frame; the tip default
is already (0.02, ref=0), so the remaining 0.02→0 exposure is
UNMEASURED — the control arm measures it before anything is banded.

## §3 The strip-fabric law

Population: graded-strip fabric nodes in the final projections'
graphs, EXCLUDING (a) nodes weld-shared with pavement (soft receivers
adopt pavement by weld law — the box must not fight the weld) and
(b) sites where the straddle or open-boundary predicate (shared
module) exempts — lawful terraces stay steppable. Datum: the node's
adjacent-ground ZONE-LAW value — the writer's lawful value in zones
1-2, raw DEM beyond zone 2 (a law-tier datum that already exists; no
new authority invented). Box: `[datum − tol, datum + tol]`,
tol = `STRIP_SEAM_TEAR_MIN_STEP_M` from the shared module, carried on
the existing `node_box` channel (exact, certifiable — the categorical
difference from the pull that v1 got right). Validator twin: already
exists (`_check_strip_seam_tears` reads the same constants once §1
lands) — this is the rare round where the twin PRECEDES the binding
half. Gate: `O4_STRIP_FABRIC_LAW`, default "0".

## §4 The kill (phase C — the owner's endgame)

Inventory per seam_lane/RESULTS.md §6 (anchored 47d7904, re-verify at
dispatch): `_ref_pull_weight`/`O4_YIELD_REF_WEIGHT` (one_solve.py:367/
:388, default now "0.02"), `_node_ref_arrays` (:357), pull sites
(:463-465, :1265-1267), the `ref_prev` equilibrium break family
(:1365-1512), `O4_CORRIDOR_REF_STRING` (solve.py:2717/:2998, default
"0" both sites — retired by owner ruling, path deleted here),
`_fp_node_refs`/`_fp_group_refs` + the fp call (solve.py:5856-6008,
:6212 — PLUS the :6112 `_field_fp` site added since),
`node_refs=_spine_refs` (six sites), `_yield_group_refs`/
`_yield_node_refs` (:2943-2959). Dies with the path, enumerated: the
two corridor-ref source twins and the §2 equilibrium report/tests
(refpull_interim RESULTS — rewrite to assert the post-kill contract:
no refs channel exists; every exit certifies or stalls loudly). The
kill is the NEXT ANCHOR-MINTING EVENT: it changes default bytes
everywhere; landing it is a deliberate lead/owner decision, not this
round's — this spec delivers it built, measured, and gated-off.

## Phase 0 — standing fact, cost carried honestly (brief item 3)

Rod composition is LANDED default "1" at 53e1156 and verified
(dropped-by-decimation 1313→0, ledger closes exactly both ways). Its
measured cost: HEAZ +14 law-true rows (within_pair::junction 15 vs 8,
transverse::junction 23 vs 20) against worst transverse 2.2456→1.3017
m. RULED HERE: yes, that trade gets its OWN adjudication line in the
flip/campaign ledger — per law-compliance-not-instrument-zero the 14
rows must be adjudicated (violation vs below-materiality vs lawful),
not netted silently against the severity win; HEAZ is a bonus fixture
outside the campaign five, so the line informs but does not move the
campaign gate. The 2.54 m corridor-sag figure is NOT re-quoted (no
instrument in tools/; it belongs to 53e1156's round).

## Baselines and verification protocol (brief item 4 — tip frame)

Baselines = the tip battery (refpull_interim/RESULTS.md): HEAZ
100/604 s=0, CYXY 155 s=6, HECA 9 125 seam 28 (7 sites), SPLP 27 s=0,
KCLT 2 643 s=0, SPJC 1 366 s=0; campaign five 13 316, seam 34.
Campaign anchors = the tip table (HECA 122708ac…, etc.), cited from
that file, 2× verified there. Streamlined verification: STRESS = HECA
(the only airport with a real strip-seam population), SENTINEL = CYXY
(6 rows, one pair); the other four ride the next tip battery.
Arms: (1) tip default; (2) KILL-CONTROL — `O4_YIELD_REF_WEIGHT=0`
(the solver equivalent of the kill), measuring the true 0.02→0
exposure; (3) control + `O4_STRIP_FABRIC_LAW=1`.

## Pre-registered outcomes (bands)

0. POPULATION PRE-FLIGHT (offline, before any arm): box-bound strip
   nodes cover ≥6 of HECA's 7 seam sites and CYXY's pair; a miss is a
   STOP before any build.
1. Arm 2 control (quoted, not banded — the exposure is unmeasured):
   HECA seam expected to rise from 28 toward the old-frame 93-class;
   any NEW regressing class outside the strip family is recorded and
   is a STOP for Ruling B (that class needs its own law first).
2. Arm 3: HECA seam ≤ 28 success (below 28 = the law also legalises
   existing tears — quoted as a win), ≤ 40 partial; CYXY seam ≤ 6;
   `adj_edge` worst ≤ its tip value at both.
3. The banked win holds: HECA law-true ≤ 9 125 at arm 3; no new
   over-cap class outside the strip family; worst-|de| severity not
   up at HECA/CYXY.
4. Equilibrium exits at arm 3 = 0 (refs inert at w=0); post-kill the
   machinery is gone and the suite's rewritten twins assert absence.
5. §1 module move byte-inert on the tip anchors (2×, hard).

## Acceptance

Phases §1 (direct, byte-inert) and §3 (gated "0") are
identity-preserving against the TIP anchors 2× (cited symbolically —
the anchor set is the refpull tip table at dispatch). Suite: same 23
reds vs a matched pristine control on an identical selection
(the refpull idiom); new twins (module lockstep two-site inspection,
box population/exemption membership, datum selection zone-vs-DEM, the
HECA-site synthetic, weld-shared exclusion). Timing: gates SUSPENDED
(RULINGS defer+tripwire) — ledger tripwire only, no timing claim (the
refpull observation that ref=0 runs shorter stays unquoted). Build
budget: pre-flight offline +
HECA ×3 + CYXY ×3 + suite ≈ 1.5–2 h honest wall; foreground; WORKTREE;
phase-C commit only on lead/owner sign-off. Convergence guards: 0.01 m
materiality, 2 attempts, `.progress`.

## STOP rules

Pre-flight population miss (re-attribute, do not build); a second
casualty class at the kill-control (Ruling B falsified for that class
— it gets its own law before the kill proceeds); band-2 miss (the
strip law is not the load-bearer); any phase-C landing without the
owner's explicit decision; second miss on any target.

## Out of scope

The full adjacent-ground band-writer ingestion (scheduled, own round —
§2 Ruling A is its first instalment only); the consensus-retirement
round (the 0.16 m shared-weld class is ITS territory, adjudicated at
3eab8fe); tile-seam law (SPLP's 36 nodes are real but measured
defect-free — nothing to fix); emit decimation; the census row-key
rename (deliberately declined, §1).
