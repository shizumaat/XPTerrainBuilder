# Pavement scoring classifier v2 — evidence-fusion spec

Status: **APPROVED scope** (owner decisions 2026-07-27): full 4-class scope,
shadow-first rollout, legacy verdict as the development fallback. Explicit
end goal: **retire the repair-chain classifier once the scorer matches or
exceeds it** ("we want to retire and eliminate that messy, convoluted chain
if possible").

## 1. Problem

A shape's role today is the product of one geometric fallback decision
(`pavement/global_slice.classify_faces`, apron = "we don't know") plus ~16
ordered repair passes, each patching the previous one's errors, each
calibrated on per-airport anecdotes. Semantic data that directly answers the
question — apt.dat row-110 `name`/`surface_code`, OSM `aeroway` polygons and
lines, road-feed tags — is either ignored or consulted only as
after-the-fact veto evidence. Measured consequence at HECA (2026-07-26):
251/318 apron shapes (32.1 % of apron area) were landside. Owner verdict
2026-07-27: classification is still terribly inaccurate.

## 2. Goal

One scoring pass in which every pavement shape **accumulates weighted points
per class** from every available evidence layer; the class with the highest
score wins. Certainty is explicit (score margin), logged per shape, and
tunable per airport by data quality — because completeness varies: one
airport has rich OSM and poor apt.dat, the next the reverse.

Classes (the 4-way decision the owner named):

| Class | Enacted role(s) | Grade law |
|---|---|---|
| `APRON` | `apron` | 1.5 % all-direction |
| `TAXI` | `junction` (taxiway family) | 1.5 % taxi law |
| `SERVICE` | `service_road` / `service_junction` | axial 4–5 % |
| `GROUNDSIDE` | `groundside_pavement` | DEM-following |

## 3. Non-goals / hard constraints

* **SINGLE SPINE (owner constraint, verbatim intent).** The apt.dat
  1201/1202 route-arc spine remains the ONLY linework that slices pavement
  and carries taxi identity. OSM taxiway/taxilane lines, painted-line 120
  centerlines, discovered lanes etc. are **evidence layers only** —
  buffered coverage fractions. Nothing is ever merged into the spine.
  ("We had trouble merging them and we don't want multiple spines!")
* Slicing itself (`global_slice`), runway roles, buildings, boundary,
  bridges/tunnels, clearance features: unchanged.
* Owner rulings stay HARD LAW, encoded as candidate gates (§6), not weights:
  free-road ruling, R-VETO, wide-residue-stays-one-surface, runway
  touch-chain (with its existing guards).
* Build budget: the shadow pass must stay < 0.6 s/airport (1 % of the 60 s
  budget) or receive the CLAUDE.md-mandated optimization-agent evaluation.

## 4. Stage 0 — per-airport source reliability

Data completeness varies per airport, so raw evidence is scaled by a
per-source reliability factor r ∈ [0, 1] computed once per layout:

| Source | Reliability metric |
|---|---|
| apt.dat 110 names | named-polygon area ÷ total source pavement area |
| OSM aeroway | min(1, aeroway airside area ÷ (0.5 × source pavement area)) blended with min(1, n_ways / 20) |
| road feed | min(1, n road ways / 25) |
| truck routes (1206) | min(1, total truck-route length / 500 m) |
| taxi spine | min(1, spine length ÷ (2 × longest-runway length)) |

An absent source therefore contributes nothing AND its silence is not read
as negative evidence (a shape isn't "not apron" because OSM never mapped
aprons at this airport). Purely geometric features (width, openings,
connectivity) always have r = 1.

## 5. Stage 1 — evidence layers

Extends the existing memoized `pavement_classification.EvidenceSources`
(road corridors, road lines, parking aisles, OSM apron/stand/taxi/airside,
spine union, runway union) with:

* **Name priors** — apt.dat row-110 polygons bucketed by name keyword:
  TWY/TAXI… → taxi-named; APRON/RAMP/STAND/GATE/TERM/PAD… → apron-named;
  ROAD/SVC/SERVICE/PERIM/VEHICLE… → service-named. Requires the pipeline to
  stash per-polygon records (`layout.apt_pavement_records`) — today only
  the anonymous union survives.
* **Truck territory** — buffered 1206 truck-route corridors + raw line
  union (for axis threading).
* **apt.dat-only pavement index** — third-party-DSF provenance = 1 − cover
  by apt.dat-only polygons (`layout.apt_only_pavement_polys`).
* **Surface codes** — recorded per shape for diagnostics; weight 0 in v2.0
  (gravel taxiways exist; tune later from logs).
* **Global-airports cross-reference (owner addition 2026-07-27).** When
  the selected pack is a custom scenery, the DEFAULT Global Airports
  apt.dat for the same ICAO often has BETTER row-110 layout/naming (the
  custom author drew everything with DSF objects — HECA). Its named
  polygons and 1201/1202 network territory join as coverage evidence
  (`alt_name_*`, `alt_taxi_cover`) at half the primary name weights —
  never as spine. Reliability self-discounts by measured alignment:
  r = (alt-pavement ∩ our source pavement)/alt area × informativeness
  (naming coverage + network richness), so "there won't be perfect
  alignment" is priced in rather than assumed away. Cost: one extra
  indexed apt.dat block parse + one union/intersection — measured at
  landing (§10.3 covers it).

All layers use the proven `CoverIndex` STRtree pattern (per-piece,
never pre-merged — the HARD-LAW build-budget idiom).

## 6. Stage 2 — scoring

For shape s: `score(C) = Σ_f  W[f][C] · r_source(f) · x_f(s)`, features
x ∈ [0, 1]. Weight matrix `PAVEMENT_SCORE_WEIGHTS` lives in `config.py`
(env-overridable as JSON via `O4_PAVEMENT_SCORE_WEIGHTS`); initial values:

| feature | APRON | TAXI | SERVICE | GROUNDSIDE | source scale |
|---|---|---|---|---|---|
| name_apron | +3.0 | | | | apt names |
| name_taxi | | +3.0 | | | apt names |
| name_service | | | +3.0 | | apt names |
| osm_apron | +2.5 | | | | OSM aeroway |
| osm_stand | +2.0 | | | | OSM aeroway |
| osm_taxi | | +2.5 | | | OSM aeroway |
| spine_cover | | +2.0 | | | spine |
| spine_thread | | +2.5 | | | spine |
| truck_cover | | | +1.5 | | truck routes |
| truck_thread | | | +2.5 | | truck routes |
| road_cover | | | +0.5 | +2.0 | road feed |
| road_thread | | | +2.0 | | road feed |
| parking_cover | | | | +2.5 | road feed |
| narrow_only (no aircraft opening) | −2.0 | −1.0 | +1.5 | +1.0 | geometry |
| wide_blob (≳50 m everywhere) | +1.5 | | | | geometry |
| runway_connected | +1.0 | +1.0 | | | geometry |
| runway_disconnected (guarded) | | | | +2.0 | geometry |
| enclosed_by_airside | +1.0 | | | | geometry |
| open_perimeter | | | | +0.5 | geometry |
| third_party_source | | | | +0.5 | provenance |
| outside_boundary (fraction outside the OSM `aeroway=aerodrome` polygon; also the G-BOUNDARY gate input) | | | | +2.0 | geometry/OSM |

`*_thread` = shape is corridor-shaped AND that layer's centerline runs most
of its long axis (the existing `_is_road_corridor` semantics, generalized).

## 7. Stage 3 — hard gates (owner law, applied before argmax)

| Gate | Ruling | Effect |
|---|---|---|
| G-FREE-ROAD | free-road ruling + "wide road-only residue stays one surface" | SERVICE eligible only for road-width corridor shapes |
| G-VETO | R-VETO: positive airside evidence keeps pavement airside | airside evidence ≥ 0.25 → SERVICE/GROUNDSIDE removed |
| G-CHAIN | runway touch-chain law (terminal-present guard, truck-route guards preserved) | disconnected → APRON/TAXI removed |
| G-ENCLAVE | owner 2026-07-28: "groundside can never be surrounded by airside pavement unless it has a tunnel or bridge service road to get out" — the airside/groundside partition must be separable by one continuous boundary | fully-surrounded shape (exterior ring covered by the airside∪building union, ≤ `PAVEMENT_SCORE_ENCLAVE_GAP_M` gap, no touching tunnel/bridge/`is_bridge` escape) → GROUNDSIDE removed; survives the G-CONFLICT reopen; sets `airside_enclave` (+1.5 APRON). Applied by the post-enactment enclave sweep (settled roles needed) |
| G-APRON-EDGE | STANDING free-road law (canonical text `groundside.free_road_subsegments`; owner restatement 2026-07-28: "any portion of a defined service road running along the edge of, or through an apron, becomes apron") | road corridor with `apron_edge_bound` ≥ 0.4 (fraction of boundary shared with apron pavement) → SERVICE removed. The same law re-roles adopted/late-minted service pieces to apron (`reclass_building_faces` + scorer-owns adoption upgrade) |
| G-ABUT | owner 2026-07-28 (SPJC #182): "apron should always abut the airside side of buildings" | shape sharing ≥ 5 m edge with a building/terminal AND airside-face evidence (≥ 5 m shared edge with OTHER aircraft pavement, or the shape is itself chain-role) → SERVICE and GROUNDSIDE removed. Fires despite erosion-disconnection when ≥ 95 % of the shape lies in the buildings' clearance shadow (self-shadowing) or its `apron_edge_bound` ≥ 0.4 (apron-wrapped frontage); survives the G-CONFLICT reopen |
| G-TAXI-ONLY | owner 2026-07-28 (CYXY #208 vs #104): "the difference is the service road connections to 104, and no taxiways, while 208 has taxiway and no roads" — access type decides | ≥ 3 m shared edge with OTHER aircraft pavement (never self-counted) AND road_cover < 0.05 AND truck_cover < 0.05 AND no road/truck threading → SERVICE and GROUNDSIDE removed, regardless of the erosion; survives the G-CONFLICT reopen. The #104 lot keeps its landside candidates through its road/truck evidence |
| G-BOUNDARY | owner 2026-07-28 (refined same day): "a shape ENTIRELY outside the airport boundary is guaranteed to be groundside or road. If it crosses the boundary it requires further analysis by the rest of our rules" — contiguous pavement legitimately spans the fence (airside apron + outside lot) | ≥ `PAVEMENT_SCORE_BOUNDARY_OUT_FRAC` (95 %) of area outside the OSM `aeroway=aerodrome` polygon → candidates ∩= {GROUNDSIDE, SERVICE} (guaranteed pair; overrides G-VETO, both gates logged). Crossers get NO gate — `outside_boundary` weighs +2.0 GROUNDSIDE as plain evidence. Inert when no closed aerodrome way is mapped |

Gates remove candidates; scores decide among what remains. If gates leave
one candidate, that's the verdict (reason logged as the gate).

## 8. Stage 4 — verdict & confidence

* winner = argmax over remaining candidates; margin = (s₁ − s₂)/max(s₁, ε).
* Bands: HIGH ≥ 0.35, MED ≥ 0.15, LOW below.
* **Development ruling:** LOW-margin shapes take the LEGACY verdict (and
  are logged with full feature vectors). Once shadow diffs show the scorer
  matching/exceeding the chain, the chain is retired and LOW falls back to
  argmax — the chain is not kept forever.
* Every shape logs: feature vector, per-class scores, gates fired, winner,
  margin, band, legacy role, centroid lat/lon → `layout.pavement_score_decisions`.

## 9. Rollout

* **Phase A (this change): SHADOW.** `O4_PAVEMENT_SCORE_V2=shadow`
  (default). At pipeline end the scorer classifies every final pavement
  shape (apron/junction/taxi-rect/service/groundside roles mapped to the 4
  classes), mutates NOTHING, logs decisions + one summary line, and
  `tools/classify_report.py` prints the legacy-vs-scorer confusion matrix
  per airport with per-shape drill-down (lat/lon for in-sim checks).
* **Phase B: ENACT — LIVE (owner approval 2026-07-28: "turn it on so I
  can test it"; low legacy agreement at HECA is expected — legacy is
  what's being replaced there).** `on` (now the default) runs
  `enact_classify` in the `classify_pavement_v1` slot: HIGH/MED-band
  verdicts become the roles (GROUNDSIDE via `_demote`/DEM re-follow +
  airside separation; SERVICE picks road vs junction by threading);
  LOW-band shapes stay untouched for the remaining legacy passes. One
  post-enactment connectivity recompute re-verdicts shapes orphaned by
  an enacted demotion (the severing cascade). Gated OFF under "on":
  the v1 vote, the first unscoped runway-disconnected pass, and the
  groundside→service corridor promotion (their laws live in the scorer
  as G-CHAIN / the SERVICE verdicts / the `road_narrow` ruling). Still
  running: pre-slot passes (55 m flip, service re-role, road-lots) so
  LOW shapes land where legacy puts them, and the late
  service-adjacency-scoped orphan reruns (hygiene for post-slot
  splits). **Weight ruling 2026-07-28:** `road_narrow` (narrow +
  road-covered) votes SERVICE 2.5 — a vehicle-only shape riding a road
  corridor is a road even when too short to thread.

  **SUPERSEDED same day — PURE SCORER-ONLY (owner: "To test if the new
  system actually works, we need to disable the legacy system").**
  Under `on` the ENTIRE legacy role-deciding chain is now disabled:
  the 55 m junction→apron flip, service-junction re-role, road-only
  lots, both scoped orphan reruns, groundside route corridors,
  apron-enclosed absorption, orphan-junction demotion, both
  SVC-connector re-roles, and the 50 m route-proximity re-role (zone
  cut included). `PAVEMENT_SCORE_PURE=1` (default) additionally enacts
  the argmax on LOW margins, so nothing falls through. The scorer's
  verdicts are the classification, full stop — no-winner shapes keep
  their born role, sub-50 m² fragments keep the slice's role. What
  still runs is shape-making (slice, free-road carve, neck split as
  geometry) and geometry hygiene (welds, deconfliction, merges,
  airside/groundside separation). Hybrid dev behavior:
  `O4_PAVEMENT_SCORE_PURE=0`; full legacy: `O4_PAVEMENT_SCORE_V2=off`.
* **Phase B addendum — SEVERANCE (owner ruling 2026-07-28, round 4:
  "we need to sever landside from airside so we can classify
  correctly").** Before scoring, `sever_unreachable` CUTS any
  apron/junction shape straddling the aircraft-reachability contour:
  `reachable_part = shape ∩ dilate(reach core, half-width + standoff)`;
  unreachable remainder pieces ≥ `PAVEMENT_SCORE_SEVER_MIN_AREA_M2`
  split off, and every piece scores against its OWN connectivity (one
  side airside, one groundside/service).  Route-touch applies per
  piece — a remainder the authored 1201/1202 network touches stays
  welded (it would re-score connected anyway).  Cut pieces snap onto
  the parent ring (weld hygiene) and carry `from_severance_cut` +
  `from_route_proximity_cut`.  The post-enactment ENCLAVE sweep is the
  dual rule: shapes this round demoted to groundside that end up fully
  surrounded by airside re-verdict through G-ENCLAVE (§7).
* **Phase C: RETIRE** the legacy passes' code once in-sim verification at
  HECA/SPJC/CYXY/KCLT passes and compare-target fixtures are re-cut.

## 10. Acceptance criteria

1. Shadow agreement with legacy ≥ 95 % by area on shapes where legacy is
   believed correct (fixture airports), AND the scorer flips a clear
   majority of the known-wrong inventory (HECA landside blobs, curbside).
2. Suite green (standing known-red classes excepted).
3. Shadow cost < 0.6 s/airport measured cold at HECA (largest evidence
   volume); build-time impact statement recorded in this spec at landing.

   **Impact statement (measured 2026-07-28, in-session).** Shadow pass
   cost after two optimization rounds (bulk dwithin connectivity,
   sampled flank, deduped erosions + bbox short-circuit, batched
   per-layer `cover_fractions`, indexed thread-cuts): HECA (972 shapes)
   **1.39 s** (was 2.37 s), SPJC (388) **0.82 s**, CYXY (142) ~0.2 s.
   Verdicts stable across all rounds (HECA agree 515→516/972). Both
   HECA (341 s baseline) and SPJC (77 s) are already over the 60 s
   budget, so a ≥0.6 s default-on regression requires explicit owner
   approval per the HARD LAW. **Pending that approval the committed
   default is `O4_PAVEMENT_SCORE_V2=off`**; `tools/classify_report.py`
   forces shadow for its own runs, so tuning is unaffected. Owner
   options: (i) approve default-shadow for the tuning phase (cost
   removed/offset at Phase B when the subsumed legacy passes retire);
   (ii) keep default-off (shadow data comes from report runs only);
   (iii) approve with an area floor / shape cap. Remaining cost is
   dominated by genuinely-overlapping coverage overlays; further cuts
   would trade evidence fidelity.

   **Severance + enclave + boundary impact (measured 2026-07-28,
   in-session).** SPJC enact-slot seconds: 1.23 s without severance
   (`O4_PAVEMENT_SCORE_SEVER_MIN_AREA_M2=1e18`) vs 1.39 s with the full
   round-5 additions (27 shapes severed) — a ~0.16 s delta, under the
   0.6 s optimization-agent threshold (single-run in-process timer,
   both sides same session; the reach-core erosion is shared with
   connectivity via `_reach_zone`, so severance adds one dilation +
   prepared-covers sweep + differences for straddlers only).  The
   aerodrome-boundary feature costs one prepared-covers per shape
   (fully-inside fast path) and the enclave sweep runs only when a
   shape was demoted that round.
4. No layout mutation in shadow mode — byte-identical emitted patch.

## 11. Files

* `src/auto_patch/pavement_scoring.py` — the scorer (new).
* `src/auto_patch/config.py` — `PAVEMENT_SCORE_V2`, `PAVEMENT_SCORE_WEIGHTS`,
  reliability + gate/band constants.
* `src/auto_patch/pipeline.py` — stash `apt_pavement_records` /
  `apt_only_pavement_polys`; shadow hook at pipeline end.
* `src/auto_patch/layout.py` — the two new stash fields.
* `tools/classify_report.py` — per-airport diff report.
* `tests/test_pavement_scoring.py` — headless unit tests (synthetic
  layouts; no network, no X-Plane install).
