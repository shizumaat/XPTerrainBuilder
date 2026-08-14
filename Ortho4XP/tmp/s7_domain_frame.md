# S7 — the ROUND'S COMPARISON FRAME (domain-restored, drainage retired)

Lane `lane/s7domain`. Every number below comes from
`tools/harness/census.py --no-cache` over the FROZEN 1.0.245 artifacts
(`baselines/1.0.245/*.osm.gz` + their `.axes.json` sidecars, unpacked
byte-for-byte; MANIFEST body hashes unchanged). No build was run.

Three frames, one patch set, three trees — each census is the harness
census on that tree, never a wrapper:

| frame | tree | what it is |
|---|---|---|
| **blind** | `8345bf8` (main) | the SHIPPED census the round has been quoting |
| **restored** | `aba74b7` (S7 half 1) | + service_road/service_junction back in the §B3 walk |
| **retired** | S7 half 2 (this lane) | + the drainage_minimum family RETIRED (owner 2026-08-13b) |

**The `retired` column is the round's frame from here on.** The blind
frozen censuses are void for delta adjudication: they read a domain that
silently shrank when the corridor round re-roled pavement.

## 1. The headline: what each half moved

| airport | ruleset | total blind | total restored | total retired | ADJUDICATED (all three) |
|---|---|---:|---:|---:|---:|
| CYXY | icao | 388 | 899 | 245 | 245 |
| HECA | icao | 8306 | 12249 | 7416 | 7416 |
| KCLT | faa | 2424 | 4451 | 1080 | 1080 |
| KSTJ | faa | 446 | 527 | 54 | 54 |
| OTHH | icao | 7283 | 12653 | 5906 | 5906 |

**The ADJUDICATED verdict is identical in all three frames, at every
airport.** Both halves move only the version-deferred `drainage_minimum`
family, which the acceptance verdict never counted. No acceptance number
in this round changes because of S7.

## 2. The blindness was NOT an OTHH story (S3's deferred question, answered)

`drainage_minimum` rows, blind vs restored domain — the rows the walk
stopped reading when `groundside_pavement` became `service_junction` /
`service_road`:

| airport | blind | restored | UNREAD rows | share of the family unread |
|---|---:|---:|---:|---:|
| CYXY | 143 | 654 | **+511** | 78 % |
| HECA | 890 | 4833 | **+3943** | 82 % |
| KCLT | 1344 | 3371 | **+2027** | 60 % |
| KSTJ | 392 | 473 | **+81** | 17 % |
| OTHH | 1377 | 6747 | **+5370** | 80 % |
| **battery** | **4146** | **16078** | **+11932** | 74 % |

Every one of the five was blind, KSTJ least (+81) and OTHH most (+5370).
The −639 OTHH headline was one airport's slice of an 11,932-row instrument
defect.

## 3. The domain-invariant table (per airport, per family)

`—` = the family reported zero. `GONE` = the family no longer exists.
Only families with a non-zero reading somewhere are listed; the census
walks all 22 (21 after the retirement) at every airport.

### CYXY — ruleset `icao`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 70 | 70 | **70** |
| plane_gradient | 1 | 1 | **1** |
| runway_end_skirt | 3 | 3 | **3** |
| transverse | 169 | 169 | **169** |
| strip_longitudinal | 1 | 1 | **1** |
| strip_arc | 1 | 1 | **1** |
| drainage_minimum | 143 | 654 | GONE |
| **TOTAL** | 388 | 899 | **245** |
| — airside | 67 | 67 | **67** |
| — groundside | 321 | 832 | **178** |
| — mixed | 0 | 0 | **0** |

### HECA — ruleset `icao`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 3764 | 3764 | **3764** |
| plane_gradient | 6 | 6 | **6** |
| strip_seam_tear | 2 | 2 | **2** |
| transverse | 3289 | 3289 | **3289** |
| lateral_contiguity | 3 | 3 | **3** |
| strip_longitudinal | 3 | 3 | **3** |
| strip_arc | 50 | 50 | **50** |
| raoa | 1 | 1 | **1** |
| drainage_minimum | 890 | 4833 | GONE |
| frontage_near_miss | 72 | 72 | **72** |
| vertex_to_edge_step | 37 | 37 | **37** |
| mid_edge_step | 189 | 189 | **189** |
| **TOTAL** | 8306 | 12249 | **7416** |
| — airside | 1720 | 1720 | **1720** |
| — groundside | 6519 | 10462 | **5629** |
| — mixed | 67 | 67 | **67** |

### KCLT — ruleset `faa`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 466 | 466 | **466** |
| plane_gradient | 13 | 13 | **13** |
| adjacent_ground_tear | 1 | 1 | **1** |
| strip_seam_tear | 26 | 26 | **26** |
| transverse | 508 | 508 | **508** |
| drainage_spine | 14 | 14 | **14** |
| lateral_contiguity | 10 | 10 | **10** |
| strip_longitudinal | 5 | 5 | **5** |
| strip_arc | 10 | 10 | **10** |
| drainage_minimum | 1344 | 3371 | GONE |
| frontage_near_miss | 7 | 7 | **7** |
| vertex_to_edge_step | 2 | 2 | **2** |
| mid_edge_step | 18 | 18 | **18** |
| **TOTAL** | 2424 | 4451 | **1080** |
| — airside | 1074 | 1074 | **104** |
| — groundside | 1343 | 3370 | **969** |
| — mixed | 7 | 7 | **7** |

### KSTJ — ruleset `faa`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 23 | 23 | **23** |
| strip_seam_tear | 3 | 3 | **3** |
| transverse | 26 | 26 | **26** |
| lateral_contiguity | 2 | 2 | **2** |
| drainage_minimum | 392 | 473 | GONE |
| **TOTAL** | 446 | 527 | **54** |
| — airside | 377 | 377 | **41** |
| — groundside | 69 | 150 | **13** |
| — mixed | 0 | 0 | **0** |

### OTHH — ruleset `icao`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 189 | 189 | **189** |
| transverse | 85 | 85 | **85** |
| drainage_spine | 2 | 2 | **2** |
| lateral_contiguity | 3 | 3 | **3** |
| strip_arc | 1 | 1 | **1** |
| drainage_minimum | 1377 | 6747 | GONE |
| vertex_to_edge_step | 1068 | 1068 | **1068** |
| mid_edge_step | 4558 | 4558 | **4558** |
| **TOTAL** | 7283 | 12653 | **5906** |
| — airside | 5670 | 5670 | **5670** |
| — groundside | 1613 | 6983 | **236** |
| — mixed | 0 | 0 | **0** |

## 4. What moved, and what provably did not

**Every family except `drainage_minimum` reads IDENTICALLY in all three
frames, at all five airports** — within_shape, transverse, the strip and
RESA families, the step families, frontage, spine, lateral contiguity, all
of them, row for row. That is the domain-invariance claim, measured rather
than argued: the restoration widened exactly one walk and the retirement
removed exactly one family.

**AIRSIDE is untouched by the RESTORATION** at every airport (blind ==
restored airside, five for five). No S1 coupling is implicated and there
is nothing here for S1 to adjudicate.

**AIRSIDE moves under the RETIREMENT at the two FAA airports, and only
there**: KCLT 1074 -> 104, KSTJ 377 -> 41. Those are apron rows. FAA
§5.9.1.1's 0.5 % apron gradient was the one half of §B3 that bound on a
real authority's number, and aprons are airside; ICAO states no apron
minimum, so the three ICAO airports show no airside change at all. This is
the ruling being applied ("only runways get a crown, the rest can be flat
for the sim"), not a coupling — and the rows were version-deferred, so no
adjudicated airside number moves.

## 5. Reading the frame

* Quote the **retired** column. A delta against a blind frozen census is
  void (RULINGS 2026-08-13b: "The −639 must never be quoted as a delta").
* `drainage_minimum` no longer exists as a family. A report that shows it
  as `0` is reading a stale frame, not a compliant surface —
  `check_grade.RETIRED_FAMILIES` is where the family went.
* The deferral register `VERSION_DEFERRED_FAMILIES` is now EMPTY, so
  law-true TOTAL and ADJUDICATED are the same number in this frame at
  every airport. They were not before, and reports that carried both
  numbers to keep the deferral honest can now carry one.

## 6. Provenance

| frame | JSON |
|---|---|
| blind | `Ortho4XP/tmp/s7/frame1_blind.json` (main tree, 8345bf8) |
| restored | worktree `s7frame2` `tmp/s7/frame2_restored.json` (aba74b7) |
| retired | `tmp/s7/frame3_retired.json` (this lane) |

Regenerate any of them with:

    venv/bin/python tools/harness/census.py tmp/s7/frozen/consol3*.osm \
        --no-cache --json OUT.json

(`tmp/s7/frozen/` is `baselines/1.0.245/*.osm.gz` gunzipped beside its
sidecar; `--no-cache` is mandatory across frames — a cached census keyed
on the patch would be reused across two different law frames.)
