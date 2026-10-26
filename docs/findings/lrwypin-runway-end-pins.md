# lrwypin — where a runway end's height pin comes from, and when it is trusted (#1342, #1358, #1394)

Lane `lrwypin`, base `origin/main` 77e3a13e4 with PR #1385 (#1346, `threshold_seam`)
merged in, because the closing check needs PANC verify-clean with the #1346 seam rule
in place. Rulings: 2026-10-22a, 2026-10-25a, 2026-10-26a, 2026-10-26b (#1346),
2026-10-26e, and 2026-09-30z (2) as 22a and 26e amend it.

## 1. The sites, numbers first

The before and after numbers for each closing build are in §7. These are the inputs, read
through v2's own readers (`read_apt` and `join_cifp`; probe
`scratchpad/lrwypin/probe_ends.py`):

| airport | runway | CIFP ends | apt.dat field | what goes wrong today |
|---|---|---|---|---|
| VNLK | 06/24, 541 m | 2845.92 / 2845.92 m (9337 ft both) | 9100 ft (custom pack) | both ends pinned flat; DEM relief 32 m, 12.6 % |
| CBR2 | 07/25, 1168 m | 717.50 / 717.50 m (2354 ft both) | 2354 ft (= CIFP) | both ends pinned flat; lidar falls 17.3 m (1.45 %) 07 → 25 |
| KDIJ | 4/22, 2224 m | RW04 1878.79 m, 593.5 m in from the apt.dat 04 end; RW22 refused (#994), 594.5 m beyond the 22 end | — | the RW04 height pinned at the apt.dat 04 end, 5.28 m over the lidar |
| PAAQ | 16S/34S, 476 m | none | 242 ft | both ends on the apt.dat datum, 0.9 to 1.7 m under the lidar |
| PANC | 15/33 | RW15 0 m in (apt.dat says 61 m); RW33 145.8 m in (apt.dat says 270 m) | — | regression check (#1346): the pins move to the CIFP points |

## 2. Consumer census: every reader of a runway-end pin

Each reader takes the pin through one of three accessors. `RunwayEnd.threshold_elev_m`
is the value. `runway_profile._end_vertex` is the location. `runway_profile.threshold_pins`
and `datum_pins` give the vertex → z map. The table rules each reader once.

| reader | what it reads | how this change reaches it | ruling |
|---|---|---|---|
| `constraints/runway_profile.runway_profile` (the `Pin` rows) | `threshold_elev_m`, `_end_vertex` | the value is the resolved one (CIFP, or a cross-check source); the vertex is the CIFP point's station | inherits; the `Source` names the pin's origin |
| `runway_profile.datum_pins` (the apt.dat datum, the 22a DEM end) | `threshold_elev_m is None` ends | THE ONE SITE that values a DEM-following end: 22a (unchanged), a flagged CIFP end (#1342), and an apt.dat-only end the lidar outvotes (#1394) | extended here |
| `runway_profile.threshold_pins` | both of the above | unchanged code; it merges them | inherits |
| `constraints/runway_chord` (the §21 trend target, the crossing pins) | `threshold_pins` | the trend is shifted through the pins wherever they now sit; a mid-runway pin (KDIJ 04) carries the trend past itself to the end | inherits |
| `constraints/runway_yield` (`_pin_sources`, `derive`) and `runway_mean_slope` | `threshold_pins`, `datum_pins` | the caps yield to the new pins exactly as to CIFP pins (09-18d (3)); a DEM-valued pin is a hard pin like any other | inherits |
| `constraints/threshold_seam` (#1346) | `threshold_elev_m`, `_end_vertex` | a flagged end resolved to the DEM has `threshold_elev_m = None`, so it is not a seam conflict (it stands on the DEM); a cross-check value is a threshold like a CIFP one; the location is the CIFP point's station | inherits; PANC re-checked (§7) |
| `constraints/no_step.reach_band_values` (route reach bands) | `threshold_pins` less the seam-yield set | anchors on the resolved pins | inherits |
| `model/threshold_datum.threshold_datums` (the approach surface's datum, sidecar slots 20/21) | `threshold_elev_m`, `displaced_m` | the grade through the two pins now runs over the PIN stations (`pin_along_m`); the datum is still stated at the apt.dat displaced threshold, where the approach surface starts | amended (one line) |
| `airport/flat_site.detect` S1 / Z0 | `threshold_elev_m` | the build reads DEM prep's record (#932) and does not re-measure. DEM prep (`flat_site_prep.site_inputs`) reads raw CIFP | **left raw, on purpose**: a flag by rule (a) or (b) needs DEM relief beyond the tier's noise, which already fails S2. Note in §8 |
| the sidecar `runways` row (slots 17/18 displaced, 20/21 datum) | `displaced_m`, `threshold_datums` | slot 17/18 stays apt.dat's displaced length (the approach surface's own input) | inherits |
| the sidecar (new) `runway_end_pins` | — | one record per end: source, CIFP, field, DEM, cross-check, flags, pinned value and station | new REPORT key; no census family prices it |
| `tools/rwy_profile.py`, `tools/v2_solve_replay.py` (line overlays) | `threshold_elev_m` | instruments; they read the resolved values | inherit |

No reader takes a second derivation. The value and the location are set once at load
(`airport/end_pins.py`). A DEM-following value is set once in `datum_pins`, because it
needs the §21 ridge trend that only the planar map carries, and 22a's rule already lives
there.

## 3. The decision table, per end

`s` is the station along the apt.dat axis. "Hard" means a `Pin` row. The caps yield to it
(09-18d (3)).

| case | when | pin at | pin value | ruling |
|---|---|---|---|---|
| A | CIFP joined, verification passes | the CIFP point projected onto the axis (`pin_along_m`) | CIFP | :511-516 / 09-18d (3); **#1358** |
| B | CIFP joined, flagged; a cross-check source agrees with the DEM | the CIFP point | the source's end value (NASR → openAIP → OurAirports, first that agrees) | **25a, 26a** |
| C | CIFP joined, flagged; no source agrees | the CIFP point | the DEM: §21 trend at the station, else the vertex DEM; **no cap clamp** (the caps yield) | **25a** with the 22a DEM rule |
| A′ | no CIFP joined here because the record lies BEYOND this end on the axis, while the other end's CIFP sits the same distance INSIDE its end (a shifted runway, #1358 (2)) | the apt.dat landing threshold | the straight line through the two CIFP thresholds; then verified as a CIFP pair | #1358 (2) |
| D | no CIFP at this end; the other end is pinned A, A′ or B | the apt.dat landing threshold | the DEM, pulled toward the surveyed pin within the cap | 22a, unchanged |
| D′ | no CIFP at this end; the other end is C | the apt.dat landing threshold | the DEM, no pull (a DEM pin is not a survey) | 25a + 22a |
| E | no CIFP on the runway; credible lidar; `|datum − DEM| > noise(lidar)` | the apt.dat landing threshold | the DEM | **26e** |
| F | no CIFP on the runway, otherwise | the apt.dat landing threshold | the apt.dat datum line | 30z (2), unchanged |

The location rule (A, B, C) is #1358. A CIFP `RWY:` record's coordinate IS its landing
threshold (ARINC 424 LTP), so the pin goes there, never at the apt.dat end advanced by
apt.dat's displaced length. 22a already joins a record anywhere on its own half of the
runway, so the join and the pin now agree. A pin projecting short of the end, inside the
join tolerance, is clamped to station 0.

### Verification (#1342, 25a): when a runway's CIFP is flagged

DEM per pin: the median of production-DEM samples on the centreline within
`dem_window_m` / 2 of the pin station (a window clamped to the runway). Δ is end b minus
end a. The DEM class comes from `law/inset_class.dem_source_class` (lidar / fine / coarse;
unknown reads coarse).

- **(a) placeholder.** The runway has two CIFP ends, equal to each other within
  `placeholder_spread_ft`, both within `field_equal_ft` of the apt.dat field elevation,
  and `|Δdem| > dem_noise_m[class]`. (CBR2: 0 against 17.3 m on lidar. VNLK's custom pack
  says the field is 9100 ft, so (a) does not fire there; (b) does.)
- **(b) grade.** The runway has two CIFP ends and `|Δcifp − Δdem| > grade_disagree_m[class]`.
  This compares differences, so a constant vertical-datum offset (geoid against MSL)
  cancels.
- **(c) cross-check.** A cached source carries this end, and
  `|cifp − source| > crosscheck_tol_ft`. An end whose CIFP or source threshold is displaced
  is skipped: the CIFP value belongs to the displaced point, the source's to the end.

A flag is per RUNWAY: every CIFP end of a flagged runway is resolved B or C.

**Resolution.** Each source in order, with this runway's two ends:
`|Δsource − Δdem| ≤ grade_disagree_m[class]` accepts it. A source with only one end can
resolve a one-CIFP-end runway, and is accepted when `|source − dem| ≤ grade_disagree_m`.
Nothing accepted gives C. CIFP is not a candidate once it is flagged (25a: "is not taken as
truth"). Every flag logs one loud line with all the values (CIFP, field, DEM, each
source), and the sidecar and the report publish the record.

**No cache, no network.** The sources are read only from an explicit, hash-stamped cache
(`--refresh-data runway_refs`, §5). With no cache, (c) cannot fire, and resolution goes
from (a) or (b) straight to C. No build ever fetches.

### Thresholds (`law/runway_ends.toml`; census in §6)

| key | value | why |
|---|---|---|
| `field_equal_ft` | 3 | "equals the field elevation": CIFP is whole feet, and an apt.dat field from another cycle differs by a foot or two |
| `placeholder_spread_ft` | 1 | the ends are the SAME number |
| `dem_noise_m` | lidar 0.5, fine 2.0, coarse 8.0 | fine and coarse are flat-site S2's own relief floors; lidar is the 3DEP/HRDEM DTM's metre-scale noise. Also case E's bar |
| `grade_disagree_m` | lidar 1.5, fine 4.0, coarse 12.0 | (b) and the resolution's agreement test: three times the noise on lidar, two on fine, 1.5 on coarse (a 1-arcsec DSM's canopy and edge error over two windows) |
| `crosscheck_tol_ft` | 3 | 26a: "more than a few feet" |
| `dem_window_m` | 60 | two runway widths of centreline per pin |

## 4. What the rule does to the closing airports

- **VNLK**: (b) fires (Δcifp 0, Δdem about +31 m on Copernicus GLO-30). No cache, so case C:
  both ends follow the DEM, and the code-1 caps yield to the DEM pins.
- **CBR2**: (a) and (b) fire on lidar. Case C: the 07 end at about 731.9 m, the 25 end at
  about 714.6 m.
- **KDIJ**: a shifted runway. Both CIFP thresholds lie 593.5 m and 594.5 m north-east of
  the apt.dat ones. RW04 is case A, pinned at its own point 593.5 m in. RW22 is case A′,
  pinned on the CIFP line at 1899.56 m. As first implemented, RW22 fell to case D: the 22a
  pull toward the RW04 pin within the 0.8 % end-zone cap left the 22 end 7.27 m under the
  lidar, because moving the RW04 pin 594 m in shortened the reach. That measurement is why
  case A′ exists. The pair passes (b) on lidar.
- **PAAQ 16S/34S**: case E: both ends on the lidar.
- **PANC**: the pins move to the CIFP points (RW15 from 61 m to 0 m, RW33 from 270 m to
  145.8 m). The #1346 seam rule judges the new location.

## 5. Cross-check data: what landed and what did not

- **OurAirports** (`runways.csv`, public domain, <https://davidmegginson.github.io/ourairports-data/runways.csv>):
  reader `airport/runway_refs/ourairports.py`. The cache is
  `Airport_mod_cache/_runway_refs/ourairports/runways.csv` with a `.json` stamp (URL,
  sha256, bytes, fetched time, licence line). It is filled only by the harness scope
  `--refresh-data runway_refs`, which takes the scope lock, snapshots, records the change in
  the refresh ledger, and is the only caller of the module's `refresh()`. The build reads
  the cache and nothing else.
  Attribution line: "Runway end elevations cross-checked against OurAirports data
  (public domain), ourairports.com".
- **FAA NASR** and **openAIP**: NOT implemented this round (follow-ups, §9). The provider
  interface (`runway_refs.lookup` → per-designator end records, `ORDER`) takes each one as
  a new file in `airport/runway_refs/`. openAIP's licence text and access method (API key
  or bulk export) are still to be confirmed and recorded in that provider's entry, as 26a
  asks.

## 6. Census over the CIFP airports (for the owner, before the rule ships)

`venv/bin/python tools/runway_end_census.py --json …` at cf6afddf3 + the void guard: 175 s,
read-only. 17,104 CIFP airports. 12,411 join a Global Airports apt.dat block with runways.
6,727 have a DEM tile in the shared corpus, and those give 8,229 runways with CIFP, 7,867 of
them with CIFP at both ends. With no cross-check cache, rule (c) is n/a.

| DEM class | airports | runways judged | flagged | (a) | (b) |
|---|---|---|---|---|---|
| lidar | 403 | 625 | **64** (10.2 %) | 43 | 44 |
| fine | 42 | 66 | **5** | 2 | 5 |
| coarse | 6,282 | 7,538 | **227** (3.0 %) | 130 | 163 |
| **all** | 6,727 | 8,229 | **296** (3.6 %) | 175 | 212 |

What a flag does: **lidar** flags put the runway on the lidar, which is the real ground, so a
borderline lidar flag costs little. **Coarse** flags put it on a 1-arcsec DSM trend, which is
where a false flag could hurt. That is why the coarse tolerance is the widest.

**How sensitive (b) and (a) are to their tolerances.** These are runways with two CIFP ends
and DEM reads at both. "(b) at t" counts `|Δcifp − Δdem| > t`. "(a) at n" counts the
placeholder-pattern runways with `|Δdem| > n`.

| class | n | (b) at 1 / 1.5 / 2 / 3 / 4 / 6 / 8 / 12 / 15 / 20 m | placeholder pattern | (a) at 0.25 / 0.5 / 1 / 2 / 4 / 8 / 12 m |
|---|---|---|---|---|
| lidar | 611 | 62 / **44** / 36 / 19 / 14 / 10 / 7 / 5 / 5 / 1 | 66 | 46 / **41** / 30 / 18 / 6 / 3 / 2 |
| fine | 51 | 18 / 11 / 8 / 7 / **5** / 2 / 2 / 1 / 0 / 0 | 11 | 7 / 6 / 5 / **1** / 1 / 1 / 0 |
| coarse | 7,146 | 3,574 / 2,703 / 2,050 / 1,317 / 897 / 517 / 333 / **163** / 89 / 49 | 1,031 | 844 / 774 / 608 / 456 / 282 / **128** / 65 |

The shipped tolerances are in bold. The owner may move any of them (`law/runway_ends.toml`,
no code change).

**Without a DEM**, the placeholder pattern (both CIFP ends the same number and at the field
elevation) shows on **1,134** of the 7,867 two-CIFP runways. They are mostly small US fields.
(a) flags only the ones whose DEM shows relief beyond the tier's noise.

Examples the rule catches. CBR2 07/25 and VNLK 06/24 are the closing sites. Also: 25U 17/35
(lidar: CIFP flat at 2044.6 m, lidar +15.4 m), 1S9, 1U4. 92 runways carry CIFP **0 ft at
both ends**, like 08VA 09/27 (DEM 311.7 / 296.7 m) and 0GA9, 0PA3. (b) catches these only
where the DEM also shows relief; see F6.

**#1358, the location rule.** 1,054 CIFP ends at 783 airports sit more than the 30 m join
radius from the apt.dat landing threshold, so their pin moves to the CIFP point (median
82 m, p90 234 m, max 959 m). For 256 of them the CIFP threshold is nearer the end than
apt.dat says (LFOM 06: apt.dat displaces it 960 m, CIFP puts it at the end); for the rest it
is further in (KPAE 16R: 921 m in, apt.dat 0). **81 shifted runways** (the KDIJ class) get
their refused end pinned on the CIFP line.

## 7. Closing builds (harness, branch `claude/lrwypin-runway-ends`)

The "after" builds are harness builds tagged `<ICAO>_20261026T133309` (`/tmp/harness/`).
The "before" figures are a capture-and-replay (`--from constraints --emit --verify`) at the
base 9a021461b (origin/main 77e3a13e4 plus #1385), in the `lrwypin-base` worktree. "Built"
is the nearest runway node's `alt_abs`, and "DEM" is the inset sampled bilinearly at the
point. Probe: `scratchpad/lrwypin/ends_vs_dem.py`.

| site | point | DEM (inset) | before built − DEM | after built − DEM |
|---|---|---|---|---|
| CBR2 (HRDEM lidar) | 07 end | 731.83 | **−14.33** | **+0.07** |
| | 25 end | 714.72 | +2.78 | −0.02 |
| KDIJ (3DEP lidar) | 04 end | 1873.50 | **+5.29** | **−0.14** |
| | 04 CIFP threshold | 1878.66 | +3.30 | +0.13 |
| | 22 end | 1899.06 | −2.48 | +0.50 |
| PAAQ (3DEP lidar) | 16S end | 72.64 | **−1.69** | **+0.01** |
| | 34S end | 70.38 | −1.72 | −0.02 |
| | 16 / 34 / 10 / 28 (CIFP, verified) | — | −0.04 / +0.10 / −0.06 / +0.20 | unchanged |
| VNLK (Copernicus GLO-30, coarse) | 06 end | 2782.91 | **+63.01** | **+0.61** |
| | 24 end | 2862.39 | −16.47 | −5.87 (the §21 trend at the end; OurAirports, once cached, says 2845.0) |

VNLK's runway is now built at 13.5 % (the cap yields, 09-18d). The trend puts the 24 end
5.9 m under the Copernicus DSM at that point, and OurAirports says it is 17 m under the
DSM. With the cache filled, the resolution would take OurAirports' 2784.0 / 2845.0 m: its
end-to-end difference of 61 m agrees with the DEM's 71 m within the 12 m coarse tolerance.

Census (`tools/harness/census.py`), ADJUDICATED (airside), before → after:

| site | before | after | what moved |
|---|---|---|---|
| PAAQ | 399 (363) | **110 (74)** | `within_shape` 276 → 67 (face-10's 16S/34S step); `airside_no_step` 129 → 5 |
| KDIJ | 442 (352) | **246 (202)** | `airside_no_step` 120 → 5 … 29; `taxi_box` 89 → 16; `strip_transverse` 26 → 9; `hard_conflict` 14 → 35 (24 airside, worst 0.75 m, down from 5.67 m) |
| CBR2 | 21 (11) | 31 (26) | `strip_transverse` 0 → 10, `strip_longitudinal` 1 → 9: the strip now grades beside a 1.45 % runway (worst 1.58 m) |
| VNLK | 152 (152) | **985 (985)** | `taxi_box` 439, `airside_no_step` 219, `hard_conflict` 107 (102 relaxed hard rows: pavement and road ceilings), 3 CRITICAL motion `strip_transverse` junction / runway cliffs (worst 1.50 m over 3.98 m). This is the junction and apron pavement meeting a runway that now climbs 13.5 %. It needs an owner read (§9 F7) |

`verify` DEFECT families (`runway_transverse`, `runway_vertical_curve`, `runway_step`,
`sentinel_elevation`) are ALL ZERO on every build.

**PANC (#1346 regression), verify-clean.** Harness `PANC_20261026T133438` (both tiles, 180 s,
body `2530719a3bc4`). The pins move to the CIFP points: RW15 from 61.0 m to 0.0 m, RW33 from
270.0 m to 145.8 m. RW33 still yields to the lon −150 seam (26b) at its new place, CIFP
36.881 → built 36.798 m (−0.082 m), 53.6 m from the seam. Before, it was 36.294 m at the
270 m station. The census shows CRITICAL motion 0, `seam_residual` 3 (worst 0.177 m, the
same as #1346's closing patch) and no runway-step, transverse or vertical-curve rows.
ADJUDICATED is 460 (395 airside), against 772 (707) on #1346's registered closing patch
`l1346_PANC2.osm`. That is a different base tree, so the figure is indicative, not an A/B.

## 8. Notes

- DEM prep's flat-site decision (`flat_site_prep.site_inputs`) reads raw CIFP. A runway
  flagged by (a) or (b) carries DEM relief beyond the tier's noise, which S2 refuses
  anyway. A runway flagged only by (c) on a flat site would keep a raw-CIFP Z0 in DEM prep.
  That is recorded as follow-up F4, not changed here.
- The DEM's class is read for the whole airport (`dem_source_class`), not per end. Insets
  are fetched to the airport's extent, so they cover the runway ends.

## 9. Follow-ups (not done this round)

- F1: an FAA NASR provider (`APT_RWY_END.csv`; use the elevations, not the gradient fields).
- F2: an openAIP provider, with its licence text and access recorded.
- F3: an app-side action that fills the `runway_refs` cache (the engine's `refresh()` is
  ready; the harness scope is the only caller today).
- F4: DEM prep's flat-site S1 reads the resolved values.
- F6 (owner question): a CIFP end of **0 ft** at a field whose DEM is hundreds of metres up
  (92 runways, all with both ends at 0) is not caught when the runway is flat. (a) needs the
  field elevation, and (b) compares only differences. An absolute rule, (d) `|cifp − DEM|`
  beyond a generous per-class bound, would catch it. That is a new verification rule, so it is
  not shipped here.
- F7 (owner read): VNLK. The runway now climbs 13.5 % as the ground does, but the junction
  stubs and apron that join it are held by their own caps, so the census counts rise
  152 → 985 (taxi_box, airside_no_step, 102 relaxed pavement and road ceilings). A
  steep-runway airport probably needs the #135 taxi yield to follow a yielded runway. That is
  not changed here.
- F8: KDIJ's N–S road (#1358 comment) was not re-read separately. The 04 end moved
  5.29 → −0.14 m, and graded-strip off-DEM went from 6.53 to 4.53 m max. A sim read is owed.
- F5: the cache was not filled in this lane (it is a download the master or owner
  authorises: `build_airport.py ICAO --refresh-data runway_refs --refresh-only`). Rule (c)
  and the source-backed resolution are tested on fixtures only.
