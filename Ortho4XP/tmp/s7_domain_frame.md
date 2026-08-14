# S7 — the ROUND'S COMPARISON FRAME (domain-restored, §B3 landside half retired)

Lane `lane/s7domain`. Every number comes from `tools/harness/census.py
--no-cache` over the FROZEN 1.0.245 artifacts (`baselines/1.0.245/*.osm.gz`
+ their `.axes.json` sidecars, gunzipped byte-for-byte; MANIFEST body
hashes untouched). No build was run.

**Scope note (owner 2026-08-14, RULINGS "DRAINAGE RULING SCOPE
CLARIFIED").** The retirement is NARROW: what retires is *"ADDING
drainage curvature (crown / minimum-slope requirements) to TAXIWAY and
ROAD pavement surfaces"*. NOT retired — and untouched by this lane — the
drainage SPINE in enclosed areas, the drainage slope on ADJACENT GROUND
beside runways and taxiways, the runway crown, and **the APRON half of
§B3** (FAA §5.9.1.1's cited 0.5 %). An earlier revision of this frame
retired the apron half too; that was over-broad and was reverted.

Three frames, one patch set, three trees, the harness census on each:

| frame | tree | what it is |
|---|---|---|
| **blind** | `8345bf8` (main) | the SHIPPED census the round has been quoting |
| **restored** | `aba74b7` (S7 half 1) | + service_road/service_junction back in the §B3 walk |
| **retired** | S7 half 2 (this lane) | + §B3's LANDSIDE half withdrawn by law |

**The `retired` column is the round's frame from here on.** The blind
frozen censuses are void for delta adjudication: they read a domain that
silently shrank when the corridor round re-roled pavement.

## 1. Headline

| airport | ruleset | blind | restored | **retired** | ADJUDICATED (all three) | airside (all three) |
|---|---|---:|---:|---:|---:|---:|
| CYXY | icao | 388 | 899 | **245** | 245 | 67 |
| HECA | icao | 8306 | 12249 | **7416** | 7416 | 1720 |
| KCLT | faa | 2424 | 4451 | **2050** | 1080 | 1074 |
| KSTJ | faa | 446 | 527 | **390** | 54 | 377 |
| OTHH | icao | 7283 | 12653 | **5906** | 5906 | 5670 |

**ADJUDICATED is identical in all three frames at every airport, and so
is AIRSIDE.** Both halves of S7 move only `drainage_minimum`, a
version-deferred family the acceptance verdict never counted. No
acceptance number in this round changes because of S7.

## 2. The blindness was never an OTHH story (S3's deferred question)

`drainage_minimum` rows, blind vs restored domain — rows the walk stopped
reading when `groundside_pavement` became `service_junction` /
`service_road`:

| airport | blind | restored | UNREAD | share of the family unread |
|---|---:|---:|---:|---:|
| CYXY | 143 | 654 | **+511** | 78 % |
| HECA | 890 | 4833 | **+3943** | 82 % |
| KCLT | 1344 | 3371 | **+2027** | 60 % |
| KSTJ | 392 | 473 | **+81** | 17 % |
| OTHH | 1377 | 6747 | **+5370** | 80 % |
| **battery** | **4146** | **16078** | **+11932** | 74 % |

All five were blind, KSTJ least (+81), OTHH most (+5370). The −639 OTHH
headline was one airport's slice of an 11,932-row instrument defect.

## 3. What the retirement then removed

| airport | ruleset | restored | retired | withdrawn by law | what survives |
|---|---|---:|---:|---:|---|
| CYXY | icao | 654 | **0** | −654 | nothing — ICAO states no apron minimum |
| HECA | icao | 4833 | **0** | −4833 | nothing — ICAO states no apron minimum |
| KCLT | faa | 3371 | **970** | −2401 | apron rows (FAA §5.9.1.1) |
| KSTJ | faa | 473 | **336** | −137 | apron rows (FAA §5.9.1.1) |
| OTHH | icao | 6747 | **0** | −6747 | nothing — ICAO states no apron minimum |

The family did NOT go away: it is still registered, still version-deferred
(RULINGS d48bc0a), and still walks aprons. At the two FAA airports it
still reports — KCLT 970, KSTJ 336 — and those rows are AIRSIDE, which is
why airside is invariant across all three frames.

## 4. The domain-invariant table (per airport, per family)

`—` = the family reported zero. Only families with a non-zero reading
somewhere are listed; the census walks all 22 at every airport in every
frame.

### CYXY — ruleset `icao`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 70 | 70 | **70** |
| plane_gradient | 1 | 1 | **1** |
| runway_end_skirt | 3 | 3 | **3** |
| transverse | 169 | 169 | **169** |
| strip_longitudinal | 1 | 1 | **1** |
| strip_arc | 1 | 1 | **1** |
| drainage_minimum | 143 | 654 | **—** |
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
| drainage_minimum | 890 | 4833 | **—** |
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
| drainage_minimum | 1344 | 3371 | **970** |
| frontage_near_miss | 7 | 7 | **7** |
| vertex_to_edge_step | 2 | 2 | **2** |
| mid_edge_step | 18 | 18 | **18** |
| **TOTAL** | 2424 | 4451 | **2050** |
| — airside | 1074 | 1074 | **1074** |
| — groundside | 1343 | 3370 | **969** |
| — mixed | 7 | 7 | **7** |

### KSTJ — ruleset `faa`

| family | blind | restored | **retired (the frame)** |
|---|---:|---:|---:|
| within_shape | 23 | 23 | **23** |
| strip_seam_tear | 3 | 3 | **3** |
| transverse | 26 | 26 | **26** |
| lateral_contiguity | 2 | 2 | **2** |
| drainage_minimum | 392 | 473 | **336** |
| **TOTAL** | 446 | 527 | **390** |
| — airside | 377 | 377 | **377** |
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
| drainage_minimum | 1377 | 6747 | **—** |
| vertex_to_edge_step | 1068 | 1068 | **1068** |
| mid_edge_step | 4558 | 4558 | **4558** |
| **TOTAL** | 7283 | 12653 | **5906** |
| — airside | 5670 | 5670 | **5670** |
| — groundside | 1613 | 6983 | **236** |
| — mixed | 0 | 0 | **0** |

## 5. What moved, and what provably did not

* **Every family except `drainage_minimum` reads IDENTICALLY in all three
  frames at all five airports** — within_shape, transverse, the strip and
  RESA families, drainage_spine, adjacent_ground_tear, strip_seam_tear,
  lateral_contiguity, frontage, both step families. Measured, not argued:
  the restoration widened exactly one walk and the retirement narrowed
  exactly the same one.
* **The two laws the clarification KEPT are visibly intact in the frame**:
  `drainage_spine` (KCLT 14, OTHH 2) and `adjacent_ground_tear` (KCLT 1)
  read the same in all three frames.
* **AIRSIDE is invariant across all three frames at all five airports.**
  No S1 coupling is implicated; there is nothing here for S1 to adjudicate.
* **No ADJUDICATED number moves**, so no acceptance verdict moves.

## 6. Reading the frame

* Quote the **retired** column. A delta against a blind frozen census is
  void (RULINGS 2026-08-13b: "The −639 must never be quoted as a delta").
* A `drainage_minimum` zero at an ICAO airport now means three different
  things stacked: no ICAO apron minimum exists, the landside half is
  retired, and nothing else was ever in the walk. It does NOT mean the
  surface drains. `check_grade.RETIRED_LAWS` records which surfaces left
  by law; `tests/test_harness.py` asserts they really left the walk.
* OPEN ITEM for the round: **the runway crown law has no census reader.**
  A runway emitted dead flat against a declared 0.30 m crown drop censuses
  ZERO rows — the within-shape crown check judges deviation from the
  DESIGNED crown against the runway's own transverse cap allowance, and a
  1 % crown sits inside a 1.5 % cap by construction. The minimum is bound
  only where it is generated (`tests/test_crown_minimum_bound.py`).
  Building the reader is a new law family: spec work, not this lane's.

## 7. Provenance

| frame | JSON (in this lane) |
|---|---|
| blind | `tmp/s7/frame1_blind.json` — censused in the main tree at 8345bf8 |
| restored | `tmp/s7/frame2_restored.json` — censused in worktree `s7frame2` at aba74b7 |
| retired | `tmp/s7/frame3_retired.json` — this lane |

Regenerate:

    venv/bin/python tools/harness/census.py tmp/s7/frozen/consol3*.osm \
        --no-cache --json OUT.json

(`tmp/s7/frozen/` is `baselines/1.0.245/*.osm.gz` gunzipped beside its
sidecar. `--no-cache` is mandatory across frames: a census cached on the
patch would be reused across two different law frames.)
