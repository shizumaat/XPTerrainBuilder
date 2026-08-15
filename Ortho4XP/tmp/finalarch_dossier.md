# FINALARCH — the five S1f architecture items, implemented and adjudicated (lane `lane/finalarch`)

Tree: worktree at `cacae39` (main, single projection landed), branch
`lane/finalarch`.  Every number below is measured on the SHARED corpus
through the harness entries; shared repo UNCHANGED on every arm
(full-surface before/after snapshot, all arms).

CONTROL IDENTITY FIRST (identity-mismatch law).  `cacae39` had never
been built at HECA (the R17 guard merge landed after the S1f arms), so
the control was built: `fa_0_heca` = **3ab5a8dfae80** — S1e's own
mid-only body, proving the R17 merge byte-inert.  The commit-A
(items 2+3) arms then read CYXY **5dd542654f0c**, OTHH **271f5e2df731**
— byte-identical to the S1e bodies — and HECA **ed040ecb0e65**, NOT
identical, which forced the item-2 adjudication below.  After it,
`fa_B_heca` (items 2+3 as landed) = **3ab5a8dfae80**: items 2+3 are
byte-preserving at all three airports.

## ITEM 1a — BETWEEN-RING SEATING WELD: LANDED

`_SeatedWeldBook` (groundside.py): both seat passes record every
shipped ring value by the emitter's node identity
(nearest-within-`SHARED_VERTEX_TOL_M`, the `law_anchor_key` rule,
first-writer-wins, pre-seeded with solve-authored vertices so the
solve outranks any seat); a later ring PINS its shared vertices to the
recorded value and absorbs the level change over its own run
(`_grade_limit_ring`, existing cap, no new constant) — weld-or-gap at
the seat, the S6 routing's losing-lot law.  MEASURED (fa_G vs the
cacae39 control frame): the between-shape step families CLOSE — HECA
`mid_edge_step` 9→1 GONE-dominated, `vertex_to_edge_step` −2,
`plane_gradient` −1; OTHH `mid_edge_step` −6, `vertex_to_edge_step`
−1.  The conform cost surfaces as groundside transverse/within rows
(OTHH +33 NEW all groundside; HECA groundside net −20) — the known,
named cost class of a weld (RULINGS S6 routing).  Twin: two seated
rings agree at shared nodes (fails on the old tree).

## ITEM 1b — BAND-SEAL AUTHORSHIP: GRADE ARM REFUTED, STANDS ATTRIBUTED

Both docket arms were exercised.  The FOLLOWING-GRADE arm was built
and measured (commit 5c2ad4b, arm fa_F): it moved 74 airside
survivors at HECA seam 26 (seam-ledger TOTAL RE-PROJECTION CLASS
18 → 91) and flipped +24 `within_shape::apron` rows INTO violation at
OTHH (ways −10387/−10388) — new last-seam airside authorship, the
exact class the ledger refuses, and a smoothing of the step that is
the upstream out-of-band author's visible signature
(no-degradation-shield law).  REVERTED (d2e7da3); the refutation is
the finding.  RULED (Fable, recorded in RULINGS): the authorship
STANDS — the band is the last authority (R17-1b structural), the
clamp is confined to the vertices the band clamped (twin), and every
clamp is a counted, sited finding routed to the stage-B/solve docket
that owns the out-of-band author.  fa_G seam 26 reads exactly S1f's
class 2 (the 0.0104 m apron/junction pair; the ~9.2–9.3 m
service_junction cluster is stage-B seating, excluded by the
instrument's own partition).

## ITEM 2 — FREEZE-GRAPH REUSE: KEY FIXED; OBJECT REUSE REJECTED ON MEASUREMENT

The per-ctx memo re-keyed from `(id(polygon), role, ring_only)` to
CONTENT (`grade_graph._sc_ctx_key`) — the recycled-id class that
served one shape another shape's pairs is structurally closed (twins:
recycled id cannot collide; content hits across ids; flag
sensitivity).  The ctx-OBJECT reuse the docket anticipated was then
measured: byte-identical at CYXY/OTHH, but HECA moved — 72,418
changed lines, +20 emitted nodes, a node-id renumbering cascade
(fa_A **ed040ecb0e65** vs control **3ab5a8dfae80**).  MECHANISM:
`build_context` INTERNS canonical points (`get_or_add`) while
building its building-key set; the solve-time call's interning side
effect is part of the canonical node space the patch is spelled in —
skipping it changes which later points intern together (the
`law_anchor_key` warning, measured).  RULED: the frozen ctx object is
identity-bearing and not reusable; the freeze→solve pair-generation
duplication is collapsed by the LAYOUT-SCOPED RUN MEMO (full value
key, spans the gap by construction); `build_context`'s own rebuild is
cheap (dupcensus 0.0 s) and REQUIRED.  The repetition-charter item
closes: collapsed where lawful, residual rebuild adjudicated
identity-bearing.

## ITEM 3 — CAPTURE DEM LEAK: CLOSED, QUARANTINE LIFTS

Capture v2 (`solve_capture.py`): the composed airport DEM rides the
capture (forced warm through `_load_airport_dem`, the same entry
phases 5-6 use, so build and capture share ONE object; only the
airport's own tile keys, never a process-wide snapshot) and is
installed into `elevation._DEM_CACHE` at replay;
`flat_site_mode.set_build_xplane_root` restores the build's root so
flat-site/sea-exclusion products reconstruct byte-equal;
`CAPTURE_VERSION` 1→2, every v1 capture refuses.  ACCEPTANCE:
**OTHH capture→replay REPRODUCES its own build byte-for-byte**
(fa_F `d4b97ca68f2a…809a45` both sides; fa_G replay verdict in the
acceptance table) — the "OTHH replays are NOT quotable" quarantine
LIFTS.  HECA replay likewise (table).  Twins: missing `dem_cache`
refuses; replay installs the captured DEM + root; version ≥ 2.

## ITEM 4 — STATION-PATH FALLBACKS: THE NEIGHBOUR TERM, LANDED

The two fallback clamps (station fallback, legacy per-vertex) seeded
`min(max(de, lo), c)` — a band clamp with no neighbour term.  Landed:
one multi-source Dijkstra computes the largest cap-Lipschitz minorant
of the fallback field over the `e_cap·d` metric `_reach` already
prices (no new constant); fallback STATIONS move as one cross-section
(spine-first law, contracted groups); anchors, free-end ties, held
profile members, released yards and break-blend nodes are sources
only.  D is fully Lipschitz by the inf-convolution triangle
inequality; only the upper side of an over-cap pair moves (DEM
deviation is not a reported consideration — owner 2026-08-14).  Twin:
a crest-vs-pit fallback pair (128 % against the 8 % cap, both ends
band-satisfied) ships capped; fails on the old tree.

## ITEM 5 — INVERTED TUBES: STAGE-AWARE ANCHORS, LANDED

Anchors carry their mint-time stage (`solve_stage` tags; airside wins
a shared node).  Stage A's envelope is computed first from stage-A
anchors alone; a stage-B authority whose value lies outside it is
RECORDED (`layout._svc_cross_stage_conform`, lat/lon sited) and its
propagation conforms to the envelope — the corridor-mouth weld
posture (2026-08-14 rim-pocket ruling).  The anchor's own held value
is untouched (the mint stays visible to the census).  Residual
inversions are now within-regime and attributable.  Twin: a
groundside authority 100 m from an airside weld at a value the cap
metric cannot reconcile conforms, is recorded, and renders no break
blend; the all-airside case reproduces the free-end law exactly.

## THE ACCEPTANCE TABLE

| item | state | evidence |
|---|---|---|
| tests once, ledgered | GREEN | blast-selected 82 files, `O4_ROUND_TAG=finalarch`: 1,774 passed / 2 failed — both reproduced on UNCHANGED cacae39 sources (matched control): pre-existing |
| twins fail on the old tree | GREEN | 6 defect-class twins checked out against cacae39 sources: all fail there, all pass here |
| items 2+3 byte-preserving | GREEN | fa_B_heca `3ab5a8dfae80` = control; CYXY `5dd542654f0c`, OTHH `271f5e2df731` = S1e bodies |
| CYXY vs `round_close_cyxy` | GREEN | 328→323, NET **−5**, all `transverse::service_junction` groundside; zero airside deltas |
| OTHH vs `round_close_othh` | GREEN | 5874→5876, NET **+2** (= −11 pre-existing S1e + **+13 this lane**, 33 NEW all groundside = weld conform cost; step families −7; ZERO airside deltas vs control; one 3-vertex role-less `shape_interior_ring` articulation way no longer emitted, 2238→2237) |
| HECA vs `round_close_heca` | GREEN, attributed | 7139→7198, NET **+59** (= +60 pre-existing merged-main [S1e single projection, S1f-adjudicated] **−1 this lane**).  Lane frame (vs cacae39 control): 215 NEW / 216 GONE; groundside net −20 with the step families closing; airside 69 NEW / 54 GONE — the near-cap tail of the standing 7,139-row projection residual (worst NEW apron rows 1.006–1.035 % against the ICAO 1.0 % apron cap) breathing under lawful groundside re-values in the coupled solve — the S1f-adjudicated population, no new mechanism |
| re-projection class | GREEN, one groundside row over | fa_G HECA TOTAL **19** vs S1f's 18: 09 planarize 5 (=), 20 pad-host 8 (=), 26 band seal 2 (=); seam 22 3→4 where the +1 is a `service_junction` (groundside) densify insert 0.171 m off-lerp minted by the seat-weld value change — the class's airside content did not grow |
| ONE projection | GREEN | `CALL #1`/`final#1` only in every arm's log; AST twin untouched |
| stage rails | GREEN | `test_solve_stage.py` in the ledgered selection, passing |
| shared repo UNCHANGED | GREEN | every arm's harness snapshot line |
| OTHH capture→replay reproduces | GREEN | fa_G replay `aaf3ce394d01` REPRODUCED (and fa_F `d4b97ca68f2a…809a45` byte-equal) — the quarantine lifts |
| HECA capture→replay reproduces | GREEN | fa_G replay body `3053349c0b26` = its own build, REPRODUCED |
| HECA tile pair byte-identical | see report | sequential `--tile 30 31 --no-ledger` pair |

## HASHES

control (cacae39): HECA `3ab5a8dfae80` · CYXY `5dd542654f0c` · OTHH `271f5e2df731`
final (d2e7da3): HECA `3053349c0b26` · CYXY `2c3331baccb1` · OTHH `aaf3ce394d01`
references (round_close): HECA `3c084a212d0f` · CYXY `a4aa1654431a` · OTHH `a1a2e8f024fb`
refuted arms: fa_A_heca `ed040ecb0e65` (ctx reuse) · fa_F_heca `5d9f97397a2b` / fa_F_othh `d4b97ca68f2a` (1b grade arm)
