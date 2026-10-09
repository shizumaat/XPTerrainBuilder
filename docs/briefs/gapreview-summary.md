# gapreview — the gap-piece apron rule (§59) as BUILT: review, spec amendment, sweep

Lane `gapreview` (Fable, spec author / reviewer; edits NO engine code), 2026-10-08.
Subject: branch `claude/gapapron` `edb9483a` (PR #485, lanes gapapron → gapapron4),
owner RULINGS 2026-10-08c (6), 08g, 09b; spec §59. Review branch
`claude/gapreview` (= `claude/gapapron` + §59 amended in place + this file).
Scratch `<scratch>/gapreview/` (the probe scripts `weld_check.py`,
`site_probe.py`, `pair_probe.py`, `band_probe.py`: one-off patch reads, no tool).

## Part 1 — the five deviations, ruled (§59 carries each as **AS BUILT (Dn)**)

| # | deviation | ruling | evidence |
|---|---|---|---|
| D1 | rim closure = morphological closing of part ∪ apron at `weld_m`, less the mint's knife, bodies reaching both rims only — not §59 (2) 4's `part ∪ (buffer ∩ buffer)` | **ACCEPT, REPLACES the formula** | the literal formula was measured to grow a 1 m ear at every contact end and leave slits where the gap is 1–2 m (1.26 m gap at 30.1278346, 31.4046247; the band absorbed stood 0.13 m off each rim). The closing is what the words meant ("within weld_m of BOTH"). Arm B's emitted patch: 30 gapapron\|apron contacts, all welded at shared nodes (2–23 each); 2 residual unwelded rim pairs under the weld spacing, both under the 0.05 m motion floor, one vertex each — `gapapron:1`\|`pav6` 0.044 m across 0.73 m at 30.1040989, 31.3966508 (a tangent pass between two shared runs) and `gapapron:4`\|`pav1#plateau:building4` 0.024 m across 0.86 m at 30.1069224, 31.3966555 (a pad plateau ring, minted at planar after the mint). The spec's sliver site 30.1278259, 31.4046286 lies 0.60 m inside `gapapron:7`; the census's apron\|apron row there is gone (CRITICAL motion 3 → 2). |
| D2 | no road evidence ⇒ apron even where §27 would not flip (`flipped or not evidenced`) | **ACCEPT** | the owner's sentence has two classes; §27's exemptions (sliver radius, mouth) are about roads and emit artefacts. No new floor is needed: the mint keeps a part only at ≥ `structures.load.object_pavement_min_m2` (200 m²) with a non-empty erosion at half `emit.road_profile.lane_width_m` (1.75 m), BEFORE the judgement — no hairline can be minted apron. HECA has no such part. |
| D3 | `gap:<k>` keeps its ordinal (holes where a part became apron); `gapapron:<j>`; `gap_ref` records the old ref | **ACCEPT** | no consumer reads `gap:` ordinals densely: late stage, `gap_terrace`, `gap_follow`, `census_class`, `check_grade` read the prefix and the `/s<n>/lot` path; the only `int(ref.split(":")[1])` on the branch is the frame twin's. Sites and class tables keep today's refs. |
| D4 | the keep-out: ground in a standing cell's stand-off or the band envelope is not absorbed (gap:24: 14 m² of band-envelope ground stays) | **ACCEPT — it is the law (§53 (12)), not an exception** | an apron part may not claim zone ground or a stand-off even to close its own rim; the step across such ground is the band's / stand-off's lawful terrace. On the emitted patch the ground beside `gapapron:6` is the pre-existing raw ground next to `route21`, 3.8 m wide in arm A (gap:24) and B alike — not this rule's. |
| D5 | zone-claim trim: a gap-apron cell is left out of the zone claim; cut out of a band only where it reaches one (replaces §59 (4) row 10 "none") | **ACCEPT**; the general cure is its OWN change, before #337's sweep | the claim's `unary_union` is input-chaotic: all 11 cells in → a 1,689 m × 0.8 mm hairline of runway 05C/23C's own lip passes the 1 m² area floor, +143 runway vertices, 74 nodes 0.05 m; each piece alone 0, either half 0. The cell never reaches a band (the mint's band knife), so the trim changes no zone. CURE: a WIDTH floor on zone parts at the same line as the 1 m² area floor — a part thinner than `emit.identity.min_distinct_spacing_m` (0.5 m; `g.buffer(-0.25).is_empty`) cannot hold two distinct vertices and is unmeshable (§39 (2)). #337 adds 122 standing bodies at OTHH and grows two HECA pieces — every one a new polygon in the same union, so the same hairline class can pop beside any runway there and nothing in §59 would catch it. One read settles it: `zone_regions` on the OTHH capture with / without the 122 bodies, counting runway-ring vertices (`docs/briefs/gapapron3/planar_arms.py`, minutes, no solve). |

The 2 contour joints at `gapapron:1` | `dsf:objpav106#2`: LAWFUL. Both `apron_terrace`,
declared = actual (sidecar `terrace_joints`, shapes 25 | 38): 0.051 m over 7.0 m
(0.7 %) across one `graded_strip` face at 30.1046581, 31.3957662; 0.050 m over
3.1 m across one `service_road` face at 30.1045342, 31.3966481. Two apron bodies
bridged by non-apron faces; no contour lies inside an apron face, so 02v (2)
withdraws nothing. Not owed work.

The pull, for the sim (30.1047, 31.3965): `gapapron:1` (gap:15, 3,040 m²) lies on
the slope between the small apron `pav6` (100.8 m, low) and `dsf:objpav106#2` (up
to 106.8 m); as a late road piece it ramped 3.7 m across at the road cap, and as
APRON it must hold 1.5 % across itself and both neighbours, so the merged body
re-levels: `pav6` rises 2.47 m (100.80 → 103.27), connector `pav111` welded to it
follows 1.38 m, `objpav106#2`'s low end 0.7 m, the strip beside 1.79 m — one
continuous apron grade where there was a short steep ramp between two aprons.

Late stage A → B (`late_{A,B}.txt`): fewer pieces (38 → 27) and parts (82 → 67)
because 11 left the stage; follow misses 84 → 70 (DECLARED 44 → 40, OWN-GROUP
40 → 30, worst 2.04 → 2.03 m), stepping pairs 82 → 61 (56 on pieces ≥ 1,000 m²,
15 merged), knives 33 = 33 worst 7.93 m (gap:5/s1 | gap:5/s3 — untouched by the
rule), movers 0 of 34,737, foreign 0, ribbons grown 9 = 9. Every change is a
piece leaving; no bar worsens.

## Part 2 — the sweep (branch head `edb9483a`, this worktree, tags `swga_*`)

| airport | branch body | main (`sw6_*`/`svg_*`) | rebake plan | wall s (branch / sw6) |
|---|---|---|---|---|
| CYXY | cf8e9e89ec62 | cf8e9e89ec62 | = | 25.8 / 26.8 |
| SPJC | 61f66f149737 | 61f66f149737 | = | 73.8 / 81.3 |
| KCLT | 0b1566de77d5 | 0b1566de77d5 | = | 258.0 / 248.8 |
| KASE | f9b157158a39 | f9b157158a39 | = | 37.2 / 36.3 |
| NLWF | 45ec40e74dcb | 45ec40e74dcb | = | 6.7 / 7.1 |
| OTHH | 73676fda6914 | 73676fda6914 | = | 646.0 / 619.8 |

All six byte-identical (bodies and `*.rebake.json`); `rebake.screen.json` differs
only in its cache key (tree path, partition fingerprint, code digest). NLWF: its
one object-pavement body (1,505 m²) is a pavement SOURCE, not `gap_only`
(`airport/object_pavement`: a sheet is minted only from a page refused per
triangle), so `airport.gap_sheets` is empty and `mint_gap_pieces` returns before
`judge` / `close_rim` are reached. The sweep ran with other lanes' work about
(correctness only; not a timing).

HECA timing pair — ONE run each, branch (`swga_HECA`, this worktree) then main
`e77d20e9` (`swga_HECA_main`, the main checkout), back to back, `--no-ledger`,
nice 0, no other build / replay / suite on the machine (load 4 → 9 under the
build itself). A single-run pair swings ±25 %; stated as such, not a gate read.

| phase (s) | branch | main | Δ | `sw6_HECA` (main, 2026-10-08) |
|---|---|---|---|---|
| load | 6.2 | 6.1 | +0.1 | 6.4 |
| partition | 47.5 | 46.6 | +0.9 | 48.4 |
| classify | 24.1 | 23.1 | +1.0 | 24.9 |
| planar | 34.6 | 32.1 | +2.5 | 34.0 |
| constraints | 40.8 | 38.3 | +2.5 | 39.0 |
| solve (stage 1 + 2) | 221.7 | 196.7 | +25.0 | 197.3 |
| late_stage | 117.0 | 108.4 | +8.6 | 108.6 |
| emit | 8.3 | 7.9 | +0.4 | 8.0 |
| verify | 15.8 | 14.3 | +1.5 | 14.3 |
| **wall** | **525.9** | **483.1** | **+42.8 (+8.9 %)** | 490.6 |

Bodies: branch `ad4ef9685c5f` (= the lane's closing build and arm B), main
`50d64a8b4fbe` (= `sw6_HECA` / `svg_HECA`). Both under the 600 s bar. The one
phase that carries the mechanism is the solve (+25 s, +12.7 %: 11 apron parts in
stage 1, +154 unknowns, +0.8 % hard rows — §59 (3) expected "± 0", this reads
larger than the noise of the untouched phases, which sit within ±2.5 s); the
late stage is +8.6 s with 11 FEWER pieces, which is noise or the shared
machine, not the rule. The lane's 769.5 s was a loaded-machine reading.

## Not done

* The zone-part width floor (D5's cure) — reported, not built (no engine edits in this lane).
* The two sub-floor rim pairs of D1 — read on the emitted patch only; the
  classify-vs-planar attribution is one read on `cl_dump.py`'s pickle, not taken.
* No census of the sweep builds (bodies identical to main's: nothing to count).
