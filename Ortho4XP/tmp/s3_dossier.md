# S3 — OTHH −639 attribution dossier (measure-first, no fix)

Lane `lane/s3othh`, worktree `.claude/worktrees/s3othh/Ortho4XP`, tree
`200598d`. Every defect count below comes from
`tools/harness/census.py`; every EXAMINED-population count comes from
`check_grade`'s own printed domain counters via `run_checks_law_true`
(the harness library, one code path — `tmp/s3/domain_probe.py`,
lane-local, never lands). Nothing was built: all three arms are
recorded artifacts in `/tmp/harness`.

## VERDICT: **BLINDNESS**, essentially total.

The −639 is not an improvement. Judged over a domain-invariant
population the same change is **+1,718 within rows** — a regression.

## 1. Arm identification (the −639's two sides)

| tag | file | shapes | body sha | posture |
|---|---|---|---|---|
| PRE-corridor | `/tmp/harness/padseat_othh_off.osm` | 4675 | `4ecaaa5ac1be` | corridors OFF (= `t10_fix_OTHH`, same sha) |
| POST-corridor | `/tmp/harness/consol2othh.osm` | 5053 | `444f769141b8` | consolidated-2, corridors ON |
| FROZEN 1.0.245 | `/tmp/harness/consol3othh.osm` | 5052 | `75594bc8773a` | + corridor-joins; `baselines/1.0.245` |

All three carry anchor `[25.27577459, 51.617808335]`, ruleset `icao`
from sidecar, identical law-true knobs. The pre-arm censuses at
**within = 2312** and the post-arm at **within = 1673** under today's
census — the STATUS headline reproduces exactly, so the comparison is
one law frame, two patches.

## 2. The −639 decomposed (shipped census domain)

| family | pre | consol2 | frozen c3 | pre→c3 | adjudicated? |
|---|---:|---:|---:|---:|---|
| drainage_minimum | 2127 | 1407 | 1377 | **−750** | NO — VERSION-DEFERRED (RULINGS `d48bc0a`) |
| within_shape | 148 | 166 | 189 | +41 | yes (airside 29→51) |
| transverse | 33 | 94 | 85 | +52 | yes |
| lateral_contiguity | 1 | 3 | 3 | +2 | yes |
| drainage_spine | 2 | 2 | 2 | 0 | yes |
| strip_arc | 1 | 1 | 1 | 0 | yes |
| **within total** | **2312** | **1673** | **1657** | **−655** | |

pre→consol2 is exactly −639 (−720 / +18 / +61 / +2). **92 % of the
pre-arm "within" bucket is one non-adjudicated family**, and the whole
headline delta is that family moving. Every ADJUDICATED within family
went UP.

## 3. The domain test — the census stopped looking

`check_grade._check_drainage_minimum` walks only ways whose role is in
`_DRAINAGE_MIN_ROLES`, derived from
`grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES = {groundside,
groundside_pavement, parking, lot, curbside}` (+ apron roles, a no-op
under ICAO). It reads consecutive ring pairs ≥ 5 m
(`_DRAINAGE_MIN_RUN_M`).

EXAMINED population (check_grade's own counter):

| arm | drainage pairs censused | surfaces | rows | hit rate |
|---|---:|---:|---:|---:|
| pre | 2192 | 85 | 2127 | 97.0 % |
| consol2 | 1462 | 96 | 1407 | 96.2 % |
| frozen c3 | 1447 | 86 | 1377 | 95.2 % |

**−745 examined pairs against −750 rows.** The defect RATE on OTHH
landside pavement is invariant at ~96 %; the row count tracks the
examined population one-for-one. Nothing about the surface improved.

### The family the domain lost: the corridor ROAD family

Role inventory of the emitted patches (way count / ring perimeter m /
ring edges ≥ 5 m):

| role | pre | consol2 | frozen c3 |
|---|---|---|---|
| groundside_pavement | 85 / 46 737 / 2239 | 98 / 31 433 / 1524 | 87 / 31 280 / **1507** |
| service_junction | 523 / 84 663 / 3381 | 850 / 147 726 / 5751 | 854 / 148 136 / **5769** |
| service_road | 4 / 1 064 / 46 | 44 / 13 976 / 295 | 44 / 13 983 / **294** |

The corridor round re-roled ~15 500 m of landside pavement perimeter
out of `groundside_pavement` and into `service_junction` /
`service_road`. Those two roles are groundside in the law's own
partition (`check_grade._GROUNDSIDE_ROLES` — their rows are reported
`side=groundside` in every other family) but they are **not** in the
drainage-minimum role set, so the walk no longer reads them.

Canonical identity join (11-decimal lat/lon spelling; no proximity),
pre drainage-minimum surfaces → frozen roles, per way in
`tmp/s3/table_drainmin_surface_fate.csv`. Aggregate over the 3 967
pre-arm nodes that carried the 2 127 rows:

| frozen role at the same coordinate | nodes | ~rows carried |
|---|---:|---:|
| still groundside_pavement | 2276 | ~1178 |
| service_junction | 1113 | ~611 |
| service_road | 29 | ~10 |
| absent from frozen patch | 548 | ~328 |
| other | 1 | ~0 |

This is the R19 class recurring by role migration instead of by typo —
and the same defect this very check already carries a comment about
("it used to be a hand-typed tuple, and it was wrong … the GROUNDSIDE
HALF OF §B3 NEVER FIRED … structurally silent: an empty walk and a
compliant walk report the same zero", `tools/check_grade.py:2610`).

## 4. Restore-domain arm — the TRUE delta

Lane-local, reverted, never lands: `service_road` and
`service_junction` added to `grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES`;
re-censused via `tools/harness/census.py --no-cache`
(`tmp/s3/census_restored.txt`).

| | pre | consol2 | frozen c3 | pre→c3 |
|---|---:|---:|---:|---:|
| drainage pairs EXAMINED | 5271 | — | 6926 | +1655 |
| drainage_minimum rows | 5124 | 6744 | 6747 | **+1623** |
| within TOTAL | **5309** | 7010 | **7027** | **+1718** |
| hit rate | 97.2 % | — | 97.4 % | flat |

**An improvement claim from the shipped census is void: the same
change reads −639 blind and +1718 sighted.** The restore also exposes
a PRE-EXISTING blind spot of 2 997 rows at OTHH (the 523
`service_junction` ways that were never read before the corridor round
either), so restore-domain is not corridor-round cleanup — it is a
standing instrument defect the round should pay.

Caveat the round must rule, not this lane: the restored arm applies the
PROVISIONAL 1.0 % `GROUNDSIDE_MIN_DRAINAGE_GRADE` (owner question 3) to
road-family surfaces. Whether the landside drainage minimum binds on a
service road is a LAW question. The arm's purpose is a domain-invariant
comparison, not a law claim — and either answer leaves the shipped
domain wrong: if the minimum binds, 6 747 rows are unreported; if it
does not, then `groundside_pavement` pavement that became a road did
not improve, it left the law's scope, and the −639 must not be quoted
as a delta at all.

## 5. The real (adjudicated) movement: a regression

Canonical identity join on the adjudicated within families
(`tmp/s3/table_adjudicated_within_rows.csv`, 339 rows), pre → frozen:
**115 SHARED, 64 GONE, 160 NEW**, net +95 (= within_shape +41 +
transverse +52 + lateral_contiguity +2).

NEW rows by family / role pair:

| family | roles | new | side |
|---|---|---:|---|
| transverse | service_junction\|service_junction | 72 | groundside |
| within_shape | groundside_pavement\|groundside_pavement | 46 | groundside |
| within_shape | apron\|apron | 28 | **airside** |
| within_shape | service_junction\|service_junction | 10 | groundside |
| lateral_contiguity | service_junction\|service_junction | 2 | groundside |
| within_shape | service_road / junction | 2 | mixed |

GONE: 31 groundside_pavement within_shape, 20 service_junction
transverse, 7 airside, 6 other.

Mechanism, named: the corridor round's new/re-roled service pavement
(`service_junction` +327 ways, +63 km perimeter) carries its own
cross-corridor grade defects (transverse +52 net, 72 new rows all on
`service_junction`), and the airside `apron|apron` within_shape
population moved 29 → 51 (+22 net; 28 new, 6 gone) — the same
groundside-pulls-airside channel S1 is chartered to close, here on
OTHH's aprons rather than HECA's.

## 6. ABSORPTION HOME (evidence-based recommendation)

Measured, `tmp/s3/census_padseat.txt` (three padseat arms, one tree,
one variable):

| arm | rim pockets | presolve absorb | within_shape AIRSIDE | within total |
|---|---|---|---:|---:|
| `padseat_othh_off` | OFF | n/a | **29** | 2312 |
| `padseat_othh_on` | ON | ON | **47** | 2329 |
| `padseat_othh_nopresolve` | ON | OFF (post-solve only) | **9** | 2290 |

The 29 → 9 is real and it is worth 20 airside rows. **But it is not in
production.** `gap_fill._rim_pocket_polys` returns `[]` when
`GAP_FILL_RIM_POCKETS_ENABLED` is false (`gap_fill.py:2551`), which is
the shipped default (`config.py:5658`, `O4_GAP_FILL_RIM_POCKETS=0`), so
`rim_ids` is empty and the `RIM_PRESOLVE_ABSORB` branch at
`gap_fill.py:2842` **never executes in a production build**. The
shipped OTHH airside is the 29 arm, and the frozen 1.0.245 patch reads
51 — the corridor round moved it, not absorption.

Recommendation:

1. **The gate RETIRES; it does not become a stage-B step.** It is a
   per-construct opt-out of one groundside family from the one solve —
   exactly the ad-hoc form S1's partition replaces. Under staging,
   rim-pocket spines are groundside variables and are ABSENT from stage
   A by construction; no flag is needed to keep them out, and keeping
   one would be a second, weaker boundary that can disagree with the
   real one.
2. **The 29 → 9 must be re-earned by S1's boundary, not carried.** It
   was never shipped, so nothing regresses if it is not; the honest
   posture is to give up the number as a kept claim and re-measure it
   as an S4 acceptance criterion (S4 already owns the pockets-ON arm).
   If S1's boundary is real, pockets-ON under staging should read ≤ 9
   airside with the knoll fix retained; if it reads 47, the pocket
   construct itself writes airside geometry and S4's pre-delegated
   ruling (park it, name the writer) applies.
3. **Emission is unaffected either way** — the comment at
   `gap_fill.py:2836` is accurate: rim-pocket spines are emitted like
   any other gap's; only their solver admission is at issue.

## 7. DEFERRED / not done

- No build was run (budget: three recorded artifacts served every arm).
  No `--base-arm` fetch was needed.
- The restore-domain fix is NOT landed (measure-first lane); the
  lane-local edit was reverted, tree clean.
- Not measured: whether the same role-migration blindness moved the
  other four baseline airports' `drainage_minimum` counts (KCLT/HECA
  gained corridor pavement too). One census pair each on recorded
  artifacts would answer it; DEFERRED to the round.
- `_DRAINAGE_MIN_GROUNDSIDE_ROLES` also names three roles this engine
  never emits (`groundside`, `parking`, `lot`, `curbside`); not audited
  here beyond noting it. DEFERRED.

## Artifacts

- `tmp/s3/census3.txt` / `.json` — shipped-domain census, 3 arms, sites
- `tmp/s3/census_restored.txt` / `.json` — restore-domain census, 3 arms
- `tmp/s3/census_padseat.txt` / `.json` — the two absorption arms
- `tmp/s3/rows.*.json` — every law-true row, 3 arms (the join input).
  9 MB, NOT committed; regenerate with
  `census.py /tmp/harness/{padseat_othh_off,consol2othh,consol3othh}.osm
  --rows-json tmp/s3/rows.json --sites --sites-json tmp/s3/sites.json`
- `tmp/s3/table_adjudicated_within_rows.csv` — 339 rows, GONE/NEW/SHARED
- `tmp/s3/table_drainmin_surface_fate.csv` — per-way canonical fate
- `tmp/s3/domain.txt`, `tmp/s3/domain_probe.py` — the domain instrument
