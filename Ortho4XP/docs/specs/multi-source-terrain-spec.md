# Multi-source airport terrain — spec (#1359, RULINGS 2026-10-26q / Q172)

Lane `ltriang`, 2026-10-26, base `origin/main` 59fa7241d (the spec). The
numbers in §0 are hand probes on the shared corpus; §8.1 is the measured
prototype run on captures (lane `ltriang2`, 2026-10-26).

**State (lane `ltriang2`, #1359):** the owner ruled §9 (RULINGS 2026-10-26v,
26w, 26x, 26y, 26z, 27a). Landed: the §8 prototype (`v2_solve_replay
--witness`, the label sets, the measured bars, §8.1); **Q1/Q2 at its
derivation site** (26v: `airport/runway_end_witness`, called by
`airport/load` before `end_pins.verify`); **26y** (the airport's own photos
are fetched before the patches and stamped `o4_imagery`). NOT landed: **Q4
on coarse DEM** (26w/26z/27a) — its §8 bar was missed (§8.1), so the rule is
coded (`airport/graded_edge_witness.decide_edges`) and printed by
`--witness`, not wired into `planar/zones`; **Q5/Q6** (bar missed, §8.1);
**Q3** (no stale region on the five, no synthetic twin yet).

**The ruling (RULINGS 2026-10-26q, Noah, 2026-10-27T00:47:57Z, verbatim):**
"I think both are worth exploring. Lidar is not always available or up to
date, so it would be ideal to be able to "triangulate" the optimal solution
by cross referencing lidar, CIFP, currently installed airport layout, and the
imagery that's being built so the terrain matches the best. It's not uncommon
for airports to undergo expansions that substantially change terrain to build
new or extend existing runways for example, so one data source might have the
old info, while others might have a newer one. We want to tailor the terrain
to the imagery being used, and what fits more realistically with the airport
pavement/layout. I suggest spinning off a feature branch session to explore
the airport terrain image model, and fold it in if it produces good results,
while proceeding with a multi-pronged approach as I've outlined."

What this spec settles:

1. Four sources are read for every airport: the **DEM** (lidar or coarse,
   with its survey date where the provider states one), **CIFP** thresholds
   (with the 25a / 26a / 26j / 26m checks already in law), the **installed
   layout** (apt.dat and the pack's pavement and objects), and the
   **imagery being built** (the orthophotos this tile build textures the
   airport with).
2. Each terrain QUESTION (§3) is answered by a **vote** (§4). No source is
   trusted alone, and a source that disagrees with the others yields, so a
   source that is stale after an expansion loses.
3. The answer enters the solve at that question's **one existing derivation
   site** (§5) as a pin value, a region, or an admission. It never becomes a
   new authority over airside law (airside is king).
4. The **image method is pluggable** (§7.3). The classic edge finder ships
   first; the learned model the side branch is exploring plugs into the same
   interface and is folded in only if it measures better on the §8 labels.

---

## 0. Site numbers first (hand probes, 2026-10-26)

Probes: bilinear samples of the airport inset (`Elevation_data/<tile>/…_airport_insets/`)
and of the built textures. "Built texture" is the owner's built tile
`Custom Scenery/zOrtho4XP_<tile>/textures/*.dds` (read-only), or the orthophoto
cache `Orthophotos/<tile>/<provider>_<zl>/*.jpg`. Lidar "depth" is the median
of a 40–60 m ring minus the minimum within 15 m. Lane scratch scripts, not
committed: `scratchpad/ltriang/{kdij_axis,kdij_trans,cutprobe,cropdds}.py`.

### 0.1 KDIJ (#1358): the CIFP is the stale source

| question | apt.dat | CIFP | lidar (3DEP 1 m, 2020 survey) | imagery (profiles: BI ZL18 cache; markings: the USA2 ZL18 built texture) |
|---|---|---|---|---|
| where is the 04 end? | 43.7360349, −111.1070718 | 593 m further NE, mid-runway | the graded runway profile (0.7–1.5 %, smooth) starts here | **piano keys and the "4" are at the apt.dat end**; the CIFP 04 point shows plain centreline dashes, no threshold marking |
| where is the 22 end? | 2,224 m from the 04 end | 2,818 m (594 m beyond) | the graded profile stops at 2,224 m; flat ±0.4 % to 2,280 m, then natural 1–2 % | **pavement ends at about 2,215–2,224 m**; the CIFP 22 point lies in a crop field |
| how far does the graded RSA run beyond the 04 end? | — | — | uniform 1.3–1.9 % grade to about −310/−330 m, then irregular | light mowed band to about −330 m |
| where is the RSA's side edge (the owner's "lighter mowed grass")? | — | — | slope break at +60 m (s = −150 m), +60…+70 m (s = −250 m), −72 m (s = −150 m) | luminance step at +60 m, +60…+70 m and −80 m — **within 0–10 m of the lidar break** |

Along the axis the asphalt reads about 90–105 (luminance, 0–255) and the
grass beside it 150–180. The contrast is about 55 levels at 0.4–0.6 m per pixel.

Three of the four sources agree on where the runway is (apt.dat, lidar,
imagery). CIFP disagrees by 594 m at both ends, which is the
KDIJ "shifted runway" of #1358 (2). Its heights still match the lidar at its
own points (+0.12 m and +0.74 m): those points are ground, not thresholds. The
current main code (lane lrwypin) pins RW04's CIFP height mid-runway, as if it
were a displaced threshold, and pins RW22 on the CIFP line. The built ends then
sit −0.14 m and +0.50 m against the lidar. Under §4, CIFP loses the
**position** vote and so has no **height** vote here, and both ends follow the
lidar by the 26e rule (owner question Q-A).

Without a band, the strongest edge on a cross-profile is an unrelated feature
at 2 of the 4 side crossings for the imagery (a bright strip at −136 m, a dark
patch at +130 m) and at 1 of 4 for the lidar (a bank at +148 m). In the ±20 m band around the law's zone-2 edge, three of
the four agree and the fourth (s = −250 m, right side) shows no clean edge in
either source, so it abstains. **So the band is required, and a source must be
allowed to abstain.**

### 0.2 Portals: lidar answers where it is fresh lidar; imagery answers where it is not

| site | what the map minted | lidar depth / floor | imagery | the right answer |
|---|---|---|---|---|
| KBUF site 1, 42.943562651, −78.726619628 (#1343) | pack portal; production patch had no cut | **6.47 m**, floor 212.32; wall slopes >150 % | a road runs into a dark, shadowed opening | a portal; lane lpackcut round 2's floor 212.43 is **0.11 m** off the lidar floor |
| KBUF site 2, 42.935047080, −78.724917302 | production: service road at grade, 210.3–211.7 | **4.87 m**; the lidar at the point is 207.99 | the head of a walled ramp descending between the parking rows, its wall's shadow along one side | a cut; production was 2.3–3.7 m above the lidar |
| KBUF site 3, 42.935452165, −78.725199037 | production ramp 204.1–208.7 ("too deep") | 5.92 m, floor **207.44** | a walled ramp ending in a dark, shadowed portal | a cut; production's bottom was 3.3 m under the lidar floor |
| NZWN −41.328982258, 174.813874159 (#1337) | phantom `tunnel_ramp`, 7.2 m design depth | **1.34 m** (kerbs and noise) | golf-course grass, no road, no opening | **no tunnel** (owner) |
| NZWN −41.329986226, 174.813713002 | phantom `tunnel_ramp` | **0.63 m** | grass | **no tunnel** (owner) |
| LGAV 37.943947839, 23.951564905 (#1331) | pack trench under the taxiway, floor 73.73 | 1.27 m: **undecided** (Copernicus GLO-30 is a 30 m DSM; the trench is about 40 m wide) | **the taxiway continues as a deck over a divided road**, with a shadow band about 10 m wide on its NE edge | an underpass: the cut is real, and the taxiway stays on top (RULINGS 26d) |

These three sources (lidar, imagery, the map) would have refused both NZWN
phantoms by 2–1, admitted all three KBUF cuts by 3–0, and kept LGAV's trench
with the taxiway on top by 2–0 with the lidar abstaining. That is every owner
site in the five issues that names a portal.

### 0.3 What the corpus holds for the five airports

| airport | DEM inset (provider, pixel, survey date as recorded today) | orthophoto cache | built textures (owner's tile) | capture (`frames.py list`) |
|---|---|---|---|---|
| KDIJ | USGS 3DEP 1 m; titles `ID_2020TetonCounty…`, `WY_North_Converse_2020…` | BI 16/18 | USA2 ZL18 (280), BI ZL18 (21) | lrwypin `KDIJ.pkl` (base 9a021461b) |
| KBUF | USGS 3DEP 1 m; title `NY_3County_2019_A19` | none | USA2 ZL18 (198) | lpackcut `KBUF.pkl` (base 77e3a13e4) |
| LGAV | Copernicus GLO-30 (30 m DSM, building-masked); no per-cell date | Arc 16/18 | Arc ZL18 (42) | none registered (lramp took one, unregistered) |
| NZWN | LINZ 1 m; **no date recorded** | none | BI ZL18 (21) | none (lbed registered a mesh only) |
| LFLL | IGN RGE ALTI 1 m (+ GLO-30); **no date recorded** | BI 16 | BI ZL18 (1,110) | none |

Survey dates today: USGS states the project in its title and gives a
`publication_date`; the other providers' sidecars carry only `fetch_date`. §2.1
adds the field.

---

## 1. Why a vote, not a ranking

Today's law ranks the sources per question. For runway-end heights the order
is CIFP → NASR → openAIP → OurAirports → lidar (25a / 26a / 26m), and pack
portals outrank OSM bores (lpackcut). A ranking breaks when the senior source
is the stale one: KDIJ's CIFP ends sit 594 m off the runway in the imagery,
NZWN's OSM bore has no hole in the lidar or the imagery, and lidar flown
before an extension shows the old ground under new pavement. The owner's
words name the fix: cross-reference, and let the terrain match the imagery and
the pavement.

The existing runway-end rule (`airport/end_pins.verify`) is already a small
vote: CIFP's value is tested against the DEM's grade and against a
cross-check source, and it yields when it loses (26m). This spec generalises
that rule to every terrain question and adds two voters, the layout and the
imagery.

---

## 2. The four sources

| source | what it is in this build | resolution / σ (law table, §7.2) | how it goes stale | abstains when |
|---|---|---|---|---|
| **DEM** | the airport inset if any (lidar, national 1–2 m, GLO-30), else the base tile DEM; read through `airport/dem` | lidar: σz 0.15 m, σxy 1 m; GLO-30: σz 2 m, σxy 30 m (a surface model, buildings masked at fetch) | flown before an expansion: shows old ground under new pavement | no coverage, a void, or a pixel coarser than the feature (GLO-30 cannot see a 40 m trench) |
| **CIFP** | `airport/cifp` threshold records joined by `airport/load.join_cifp` | σz 0.15 m (whole-foot heights), σxy 1 m | records for a moved or relocated runway (KDIJ), placeholders (25a (a), 26j), grade errors (25a (b)) | no record, or a placeholder flagged by `end_pins.verify` |
| **layout** | apt.dat runways and pavement, the pack's pavement (§42 object pavement, §44 borrow), the pack's placed objects (portals, trenches, walls); OSM ways where the pack has none | apt.dat ends σxy 3 m; pack geometry as authored | a pack authored before an expansion; OSM tags that do not match the ground (NZWN's covered lane) | no pack and no apt.dat geometry for the feature |
| **imagery** | the orthophotos **this build textures the airport with**: the provider and zoom `O4_DSF_Utils.zone_list_to_ortho_dico` assigns, airport cover at `cover_zl` when `cover_airports_with_highres` is set; read as the cached JPEG (the same pixels as the DDS before conversion) | σxy = max(2 px, 3 m registration): ZL18 about 3 m, ZL16 about 5 m | imagery older than the layout (pavement drawn in apt.dat that is not yet in the photo) | texture mode `default_xplane`, a combined provider with a mask layer over the feature, cloud or haze (contrast below the floor), shadow on the probe, or the texture absent at read time (§7.4) |

### 2.1 Survey date (a tie-break and a log line, never a vote)

`SourceEpoch(source, year | None, whence)` is read once at load:

- **USGS 3DEP:** the year token in `project_titles` (`NY_3County_2019` → 2019),
  and else `publication_date`.
- **GLO-30:** the product's stated range (no per-cell date).
- **LINZ STAC, IGN, other national lidar:** the date the provider states, where
  it states one. Today the fetch records none. The inset fetch adds
  `survey_date` beside `fetch_date` in the inset sidecar (a field in
  `elevation_access`, no new download).
- **Imagery:** unknown unless the provider states it. No provider call is added
  for it.

The epoch never casts a vote. The owner's target is the imagery being used,
whatever its date. It does two things: it breaks a tie between two
equal-seniority clusters (the newer wins), and it goes on the loud line
("lidar 2019 vs layout: pavement not in lidar").

---

## 3. The questions, and the cheapest witness for each

A **question** is asked at a **site**: a runway end, a station on a graded
edge, a mapped mouth, or a pavement polygon. Each source either votes
(value ± σ) or abstains with a named reason. The cheapest method comes first
in each cell, and nothing in this table reads the whole raster (see the
measured cost, §7.5).

| # | question (site) | DEM | CIFP | layout | imagery |
|---|---|---|---|---|---|
| Q1 | **Where is the runway end / landing threshold?** (each runway end) | end of the graded longitudinal profile along the axis: the last station of the planar run (residual of a 60 m moving line fit < bar) before a break | the record's point projected on the axis (`end_pins.cifp_station`) | apt.dat end and displaced length | along-axis luminance profile: the pavement / non-pavement step and the threshold-marking signature (a bright periodic run across ≥ 60 % of the width) |
| Q2 | **How high is the runway end?** (each end, once Q1 is answered) | median of centreline samples in `dem_window_m` (`end_pins._dem_at`, unchanged) | the threshold height **if the record won Q1**, with the cross-check sources of 26a | the 30z (2) apt.dat datum where nothing else answers | abstains (no heights) |
| Q3 | **Is the DEM under this pavement current?** (each layout pavement polygon) | graded test: residual of the polygon's samples against the planar fit of its own centreline profile (runway, taxiway) or plane (apron) | abstains | the pavement is drawn (it always votes "pavement here") | pavement score: mean in-polygon luminance and texture variance against a 20 m outside ring; asphalt and concrete read uniform, grass and fields read textured |
| Q4 | **Where does the graded ground meet natural ground?** (stations every 20 m on each zone-2 / RSA outer edge, in a band ± `band_half_m`) | max \|curvature\| of the smoothed normal profile in the band, with a minimum slope change | abstains | the law's edge (zones.toml offsets): the band's centre, not a vote | max \|d luminance / dn\| of the along-track median profile in the band, with a minimum step |
| Q5 | **Is there an open cut or portal here?** (each mapped mouth: OSM bore end, pack portal, pack trench open end, wall-corridor mouth) | depth = ring median (40–60 m) − min (≤ 15 m) ≥ `portal_depth_min_m`, with a wall-slope check | abstains | the proposer: the mapped feature votes "yes" | dark-opening score in the mouth window against the approach road, plus a shadow-line detector (a dark band beside a bright edge, across the road axis) |
| Q6 | **How deep is the floor at the mouth?** (each mouth Q5 admitted) | min within the mouth window (fresh lidar only) | abstains | the pack's authored portal floor (`portal_objects`), else the design depth (`structures.toml`) | abstains |
| Q7 *(later)* | where are the retaining walls and terrace edges? | slope > 45° chains | — | pack walls | linear shadow lines |

Q7 is listed so the interface carries it. It is not in the prototype: VNLK's
terraces wait for the owner's video (26n).

---

## 4. The vote (one rule for every question)

For question *q* at site *x*, each source *s* gives `Abstain(reason)` or
`Vote(value, σ_s)`. σ comes from the source's class in the law table (§7.2).

1. **Agreement.** Two votes agree when |v_s − v_t| ≤ `k`·√(σ_s² + σ_t²), with
   `k` = 2 by default. Q5 is yes/no: two votes agree when they say the same
   thing. The votes are grouped into clusters, each built around its most
   senior member (most senior first, then the agreeing votes join it).
2. **Majority.** The cluster with the most votes wins, if it has at least two
   members and more than any other cluster. The answer is the value of its
   **most senior member** (§4.1), so a survey is never averaged with a coarse
   DEM. The other members only corroborate it.
3. **Tie** (1–1, or 2–2). The question's seniority list decides (§4.1). Where
   seniority is equal, the newer epoch decides (§2.1). Two DEMs never vote
   twice: the inset and the base tile are one source.
4. **One vote only** (every other source abstained): **uncorroborated**. It is
   used only where today's law already takes that source alone (the lidar for
   an apt.dat-only end, 26e; a CIFP threshold that passed verification,
   09-18d (3); a mapped bore where no witness can see). It is published with
   the flag. "No source is trusted alone" means no single source ever
   overrides the others. It does not mean a build stops when only one source
   can see the site.
5. **No votes.** Today's law and today's code path stand, unchanged.
6. **Yield, loudly.** Every source that loses says one line with all values
   (`[witness] KDIJ RW22 Q1: CIFP 2818 m yields to apt.dat 2224 / lidar 2224 /
   imagery 2219`) and one record in the sidecar's `witness_votes` (§7.2).
7. **Deterministic.** Votes are computed from the inputs alone: no time-outs
   that change an answer between two builds of the same inputs (§7.4).

### 4.1 Seniority per question (law table; a tie-break, never a veto)

| question | most senior → least | why |
|---|---|---|
| Q1 position | layout → imagery → DEM → CIFP | the pavement is what the sim draws (the owner: "fits … the airport pavement/layout"); the imagery is what the pilot sees; a CIFP point is only a threshold if it lies on that pavement |
| Q2 height | **not this table**: Q2 is `end_pins.verify`'s decision table as ruled (25a, 26a, 26e, 26j, 26m), unchanged | its own tests (placeholder, grade, cross-check) already settle CIFP against the DEM; a 1–1 tie there is never decided by seniority (25a (b) case C) |
| Q3 DEM current | imagery → DEM | layout always says "pavement"; the question is whether the photo shows it built and the DEM shows it graded |
| Q4 graded edge | DEM (lidar class) → imagery → DEM (coarse) | fresh lidar measures the fill; on a coarse DEM the image edge is the only line |
| Q5 portal | layout (pack object) → imagery → DEM → layout (OSM) | a pack object is authored where the modeller saw the portal; an OSM tag is the weakest |
| Q6 floor | pack authored floor → DEM (lidar class) → design depth | the pack object is drawn at its authored floor and must sit on the cut (#1343, 26p); the lidar corroborates it (KBUF site 1: 0.11 m apart) and pins where there is no pack portal |

The invariant the ruling states: **a source that disagrees with the imagery
and the layout yields.** In Q1 the imagery and the layout outnumber a
dissenting CIFP or DEM 2–1 by rule 2, before seniority is read. In Q5 an OSM
tag that the imagery and the DEM both contradict yields the same way (NZWN).

---

## 5. How an answer enters the solve: one derivation site per question

The witness never writes a surface value outside law. It sets pin values,
regions and admissions that law already reads, at the single site where each
is derived today.

| Q | derivation site (today) | what the answer changes there | what it never does |
|---|---|---|---|
| Q1, Q2 | `airport/end_pins.py` (`verify`, `shifted_ends`, `cifp_station`) at load | a CIFP record that loses Q1 is not joined as this end's threshold (no pin from it). The end is then an apt.dat-only end and takes the 26e lidar rule, or the 30z (2) datum where there is no lidar. Q2 runs the existing 25a / 26a / 26m / 26j rule on the remaining votes | move an apt.dat end; invent a threshold |
| Q3 | **new**: `airport/dem_trust.py`, wrapping `Airport.dem` once at load (the sampler every planar and constraint reader already takes) | inside a **stale region** (layout + imagery say pavement, the DEM shows natural ground), the sampler answers from a fill of the region's rim (the one rule: harmonic, as `O4_Mesh_Utils.interpolate_free_interior_altitudes` does for the mesh), so every DEM reader inherits it at once; the raw DEM stays `Airport.dem_raw` for the witness and the census | override a CIFP or cross-check pin (the pins stand; the fill only replaces the DEM); touch a seam pin (26b: the seam outranks everything) |
| Q4 | `planar/zones.py` (zone-2 / RSA rings from `law/zones.toml` offsets) | **coarse DEM only** (26w): the ring's outer edge moves to the observed toe where ≥ 70 % of an edge's stations agree. It moves OUT freely and IN (narrower or shorter, 26z) only down to the standard width and length — the FAA RSA or ICAO strip for that runway (27a); every place the imagery shows less is logged with how much and where, by landmark. On lidar-class DEM the answer is a **check** (§6, `verify`) | narrow or shorten below the standard RSA / strip (27a); grade beyond the probe band |
| Q5 | `planar/structures.build_structures` admission (OSM mouths via `structure_approach.mouths` / `structure_mouth`), `airport/portal_objects.read_portals`, `airport/object_cut` shells | an **OSM-only** mouth that loses Q5 (DEM and imagery both say no, NZWN) is refused by name (`#1359 witness`); one that wins stays admitted by today's rules. A **pack** portal or trench that loses is kept and published as a disagreement: the sim draws the object, and an object the sim draws is never left floating | create a cut no map source names (Q-C) |
| Q6 | `airport/portal_objects` (pack portal floor pins), `planar/structure_mouth.portal_mouth` | the floor pin takes the winning value: the pack's authored floor where a pack portal exists (today's rule), the fresh-lidar floor at an OSM-only mouth in place of the design depth; a pack floor more than `k`σ from fresh lidar is published as a disagreement | lower airside pavement (a mouth under a taxiway is a deck, RULINGS 26d, 26p) |

Airside is king, and these rules hold everywhere: a witness never lowers
airside pavement, never removes a law zone, and never opens a strip keep-out
that law keeps shut. The 26k pack-portal exception stays exactly as ruled.

---

## 6. Consumer census (RULINGS 2026-08-30l)

Every pass that reads the geometry or values the witness changes, ruled once.
"Inherits" means the reader takes the new value through the accessor it
already uses, and its code is unchanged.

### 6.1 Runway-end pins (Q1, Q2)

The pin's value and location are still set at one site, `airport/end_pins`,
so the reader table of `docs/findings/lrwypin-runway-end-pins.md` §2 applies
row for row. Its readers are `runway_profile.runway_profile` / `datum_pins` /
`threshold_pins`, `runway_chord`, `runway_yield`, `threshold_seam`,
`no_step.reach_band_values`, `model/threshold_datum`, `flat_site` (left raw, as
there), and the sidecar `runways` and `runway_end_pins`. One change: a CIFP
record that loses Q1 reaches `datum_pins` as an end with no CIFP
(`threshold_elev_m = None`, `pin_source = "dem"` per 26e). That is a case it
already values, so **all inherit**. `flat_site_prep` reads raw CIFP in DEM
prep, before load and without the imagery, so a Q1 loser still enters its S1
spread. It is **left raw**, as lrwypin left it; §8 prints the flat-site
verdict of each airport with and without the losers, and a verdict that
changes is a finding for the master, never a silent fix.

### 6.2 The trusted DEM (Q3)

| reader | reads | ruling |
|---|---|---|
| `planar/build._sample` → `Vertex.dem_z` (I7), and every constraint and solve reader of `dem_z` (`solve/design_ground`, `design_assemble`, `rows`, `ground_band`; `constraints/runway_chord`, `water`, `eat`, `pad_*`, `road_ramp`, `ramp_runout`, `apron_shelf`) | the sampler | **inherits**: it is the one site |
| planar samplers calling `dem_z_many` directly (`structure_approach`, `structure_mouth`, `structure_deck`, `structures`, `channel*`, `covered_ground`, `shore`, `terrain_edge`, `unframed_ramp`; `airport/wall_class`) | `Airport.dem` | **inherits** (same wrapper) |
| `airport/end_pins._dem_at` (Q2's DEM vote) | must see the **raw** DEM (a vote on the fill would vote twice) | **reads `dem_raw`**: the one reader changed |
| `airport/flat_site_prep` (DEM prep's flat decision, #932) | runs in DEM prep, before load | **left raw**: the flat-site class must see the real relief; a stale region on a flat site is flat fill anyway |
| `constraints/threshold_seam` / §38 seam pins | the tile DEM at the seam | **raw, by ruling** (26b): a stale region never moves a seam pin; a region touching the seam is clipped `q3.seam_clear_m` (50 m) short of it |
| the mesh outside the patch (`O4_Mesh_Utils`) | the tile DEM | **untouched**: stale regions lie under patch pavement, which the patch values |
| census (`tools/harness/census.py`, `verify/*`) DEM-departure reads | the published surface vs DEM | **reads `dem_raw` plus the published `stale_dem_regions`**, so a departure inside a stale region is reported as such, not as a defect |

### 6.3 Graded-area edges (Q4)

| reader of the zone-2 / RSA ring | ruling |
|---|---|
| `planar/zones.py` (derivation) | **the one site**: coarse-DEM widening only (§5) |
| `planar/overlay.dissolve_sliver_zones`, `planar/strip_keepout`, `planar/pad_blocks`, `planar/structures`, `planar/road_yield`, `planar/terrain_edge` | inherit (they read the ring) |
| `constraints/zones` (`zone_bands`, `strip_transverse`), `constraints/strips`, `constraints/end_lip`, `constraints/geometry`, `constraints/runway_chord`, `constraints/road_ramp`, `constraints/water` | inherit: the widened band is zone 2 with zone 2's law; `strip_transverse` ties every ring vertex as today |
| `solve/design_ground` (`ground_roles`, the bend class), `solve/design_assemble`, `solve/design_report` | inherit |
| `classify/roles`, `classify/ribbon_mint` (zone-2 half-width readers via `law/tables.zone2_half_width_m`) | **unchanged**: they read the law width for classification, not the ring, so the widening is a ring change only (the implementing lane confirms this with `blast.py` before the edit) |
| `airport/road_ramp`, `pipeline/band_road_wall`, `model/end_area` | inherit |
| `verify/strips`, `emit/osm_adapter` (the `graded_strip` role) | inherit; **new** report-only family `graded_edge` in `verify/` (observed toe vs built toe, lidar-class airports), priced by no gate |

### 6.4 Structures (Q5, Q6)

| reader | ruling |
|---|---|
| `planar/structure_approach.mouths`, `structure_mouth.mouth_at_pavement` / `road_end_after_slide` (#1337 rule) | **the admission site**: a Q5 loss refuses the corridor by name here, before the slide |
| `airport/portal_objects.read_portals` / `portal_of` | the Q6 floor value is set here |
| `airport/object_cut`, `airport/tunnel_objects.read_corridors`, `airport/wall_corridors` | Q5 is asked of their open ends; a pack trench under airside pavement keeps 26d (cut stays, deck on the solved taxiway) |
| `planar/structures.build_structures` and its readers (`channel*`, `structure_deck`, `structure_service`, `door_ramps`, `wall_corridor_ramps`, `structure_overlap`) | inherit (they read admitted structures) |
| `tunnel_ramp` role readers (`law/precedence.toml` emit tag; `constraints/structures`, `constraints/groundside`, `constraints/channel`, `constraints/foot_rows`; `verify/keepout.portal_cut_regions`, `verify/within`, `verify/structures`, `verify/channel`; `emit/graded`, `emit/osm_adapter`; `classify/airside_edge`; `pipeline/publication`, `pipeline/build`) | inherit: fewer ramps (refused) or a different floor pin; no new role |

### 6.5 Freshness and caches

| reader | ruling |
|---|---|
| auto-patch freshness (26o fingerprint) and the v2 stage cache (`airport/stage_cache` keys) | **amended** (landed): `o4_imagery` (`auto_patch/provenance.imagery_identity`: each airport texture's name and byte size) is a compared freshness stamp, schema "7"; the front half keys on the airport, which carries the witness's answer. The provider's `name@version` is in the patch code key (its module is in the closure). **Owner question (§9 Q-E):** the tile step reuse (#615, owner 2026-10-12: an imagery-only change rebuilds "just the DSF") still does not count the imagery as a vector-step input, so a provider switch alone keeps the patch until the vector step runs again |
| the object stage (`placement_*`, `rebake_*`) | inherits (reads the solved surface) |

No reader takes a second derivation. Every answer is set at one site.

---

## 7. Interfaces

### 7.1 Modules (each a new file in its package; `blast.py --find` showed no edge, break or imagery witness in `auto_patch_v2`)

| module | package | one responsibility |
|---|---|---|
| `airport/witness_vote.py` | airport | `Vote`, `Abstain`, `WitnessVote`; the §4 rule as one pure function `decide(question, votes, law)` |
| `airport/source_epoch.py` | airport | `SourceEpoch` per source (§2.1) |
| `airport/imagery_read.py` | airport | the build's airport textures: which (provider, zoom, texture) cover a point (`O4_DSF_Utils.zone_list_to_ortho_dico` rules), JPEG windows into the local frame as `ImagePatch`; decoded lazily, only under probes |
| `airport/image_provider.py` | airport | the `ImagePatch` / `Probes` / `ImageEvidence` types, the `ImageProvider` protocol and its registry (§7.3) |
| `airport/image_edges_classic.py` | airport | the classic band edge and opening finder (numpy + scipy.ndimage + PIL, all already bundled; no OpenCV) |
| `airport/lidar_breaks.py` | airport | normal-profile slope and curvature breaks, planar-run residuals, cut depth, all vectorised over the probes in one `map_coordinates` call |
| `airport/dem_trust.py` | airport | the stale-region test (Q3) and the wrapped sampler (`Airport.dem` / `dem_raw`) |
| `law/witness.toml` | law | σ per source class, `k`, band and contrast floors, depth minimum, seniority lists (§7.2) |

All of these sit in `airport` (layer 4 of `tools/ratchets.py LAYER_ORDER`),
which `planar` and `constraints` already import. No layer edge is added, and
no subpackage either. Each new module joins `auto_patch/provenance_code.PATCH_CODE_MODULES`
and `O4_Step_Code` (the closure twins), and imports its third-party modules at
the top of the file (memory `frozen-engine-lazy-imports`: a function-level
import is invisible to the freeze).

### 7.2 Law keys and published records

The table landed as `law/terrain_witness.toml` (schema
`law/terrain_witness_schema.py`; `law/witness.py` is the stage cache's law
recorder). Its `[q1]` gained `search_after_max_m` 300, `search_past_threshold_m`
150, `marking_inset_m` 6 (the markings begin 6 m inside the threshold) and
`marking_sigma_m` 4; `[q4]` `band_half_m` is 40 (26z: the probe reaches in and
out, no 20 m cap). The starting block below is kept for the record:

```toml
[vote]
k = 2.0                         # agreement: |a - b| <= k * sqrt(sa^2 + sb^2)

[sigma]                         # metres
lidar_z = 0.15
lidar_xy = 1.0
coarse_z = 2.0
coarse_xy = 30.0
cifp_z = 0.15
cifp_xy = 1.0
aptdat_xy = 3.0
image_xy_px = 2.0
image_registration_m = 3.0

[q1]
marking_width_frac = 0.6
pavement_step_min = 25          # luminance levels (0-255)

[q3]
graded_residual_max_m = 0.15
window_m = 60.0
pavement_score_min = 0.6
seam_clear_m = 50.0

[q4]
band_half_m = 20.0
station_m = 20.0
slope_change_min_pct = 1.5
lum_step_min_per_m = 2.5
edge_agree_frac = 0.7

[q5]
portal_depth_min_m = 2.0
ring_m = [40.0, 60.0]
core_m = 15.0

[seniority]                     # Q2 has none: it is end_pins.verify as ruled
q1 = ["layout", "imagery", "dem", "cifp"]
q3 = ["imagery", "dem"]
q4 = ["dem_lidar", "imagery", "dem_coarse"]
q5 = ["pack", "imagery", "dem", "osm"]
q6 = ["pack", "dem_lidar", "design"]

[image]
provider = "classic_edges"
```

Sidecar (REPORT keys; no census family prices them):
`witness_votes` (one record per site: question, site, every source's vote or
abstain reason, the answer, the winners, the yielders, and the uncorroborated
flag), `stale_dem_regions` (polygons and reasons), and `source_epochs`.

### 7.3 The image-provider interface (where the learned model plugs in)

```python
@dataclass(frozen=True)
class ImagePatch:            # what every provider sees, and nothing else
    rgb: np.ndarray          # uint8 H×W×3, north-up, resampled to the airport frame
    m_per_px: float
    origin_xy: tuple[float, float]   # airport-frame metres of pixel (0, 0)
    source: str              # "BI@18", "USA2@18", …: the build's own texture

@dataclass(frozen=True)
class Probes:                # line probes: N stations × M samples along normals
    xy: np.ndarray           # N×2 station points (airport frame)
    normal: np.ndarray       # N×2 unit normals
    offsets_m: np.ndarray    # M signed offsets (the band)

@dataclass(frozen=True)
class ImageEvidence:
    offset_m: float | None   # edge position along the normal; None = no edge
    strength: float          # calibrated 0..1
    label: str               # "pavement_edge" | "graded_edge" | "portal_opening" | "shadow_line" | "none"

class ImageProvider(Protocol):
    name: str                # registry key (law `[image] provider`)
    version: str             # joins the patch freshness fingerprint (§6.5)
    def edges(self, patch: ImagePatch, probes: Probes, kind: str) -> list[ImageEvidence]: ...
    def presence(self, patch: ImagePatch, window_xy: np.ndarray, kind: str) -> ImageEvidence: ...
```

The vote reads only `ImageEvidence`. A strength below the question's floor is
an abstain. A provider never opens files, never sees a source other than the
imagery, and never knows which airport it is on (RULINGS 05e). The learned
model is one more file in the family, `airport/image_edges_<name>.py`,
registered under its own key. The side branch needs nothing else from this
lane. The conditions it must meet to be folded in:

- It measures better on the §8 label set: precision and recall each at least
  the classic provider's, and one strictly better.
- It runs on CPU on macOS, Windows and Linux, inside the frozen engine
  (`scripts/make_engine.sh`), with no GPU path that changes results.
- Its inference is deterministic (fixed threads and seed). Patch bodies are
  hashed for A/B (memory `patch-ab-integrity`).
- Its weights and training data are open (owner, 25a: "stick to open data"),
  their licence is recorded beside the weights, and its size is stated (the
  owner rules on the bundle size).

### 7.4 Imagery before the solve

The patch is solved in the vector step, before the mesh. The imagery step
downloads after the mesh, so the witness must have its textures first. The
airport-cover texture set is **pre-mesh**: `zone_list_to_ortho_dico` derives it
from the airport boundary's bounds, `cover_extent` and `cover_zl`, with no
triangles. (Without airport cover it is the base-zoom grid over the boundary.)
These are textures the imagery step downloads anyway. The witness:

1. puts that list at the **front** of `O4_Imagery_Prefetch.candidates` (the
   prefetch already runs alongside the vector step, one texture in flight,
   with the imagery step's per-provider limits);
2. waits for that set before Q1/Q3–Q5 are asked (Q-D (a)), or abstains on
   every imagery vote when the set is incomplete (Q-D (b)).

A texture mode with no orthophoto (`default_xplane`), or a combined provider
whose mask layer covers the probe, abstains by name. The JPEG cache is the
source (the DDS is the same pixels after colour harmonization). The witness
reads pixels and writes nothing.

### 7.5 Cost (measured, this Mac, 2026-10-26)

| step | measured | per airport |
|---|---|---|
| decode one 4096² ZL18 JPEG | 0.065 s | 6–20 textures under the probes: 0.4–1.3 s; decoded in the pack pool workers (`airport/pool`), and only textures a probe touches |
| gaussian + sobel over a **whole** texture | 1.09 s | **not used**: probes only |
| slope + curvature over the whole KDIJ inset (6053 × 7163) | 1.62 s | **not used**: probes only (the inset is already read by the build) |
| probes (about 1,000 stations × 160 samples, one `map_coordinates` per raster) | estimated ≤ 50 ms per question family | measured in §8 |

The image decode can pass the 0.6 s line (1 % of the 60 s per-airport budget,
`Ortho4XP/CLAUDE.md` HARD LAW 6). The final-profile round adjudicates it (the
per-change timing gates are suspended, RULINGS "Per-change timing gates
SUSPENDED"), and the build-time statement of the implementing brief carries
the §8 measurement.

---

## 8. Prototype (offline, on captures; no airport build)

**Tool:** extend `tools/v2_solve_replay.py` with `--witness [--witness-labels
FILE.json]`. No new script, per the tool discipline: it is the capture
tool's near-fit, and it lands with its `tools/INDEX.md` row change. On a
`--replay X.pkl --from planar`, it builds the probes from the replayed Airport
and planar map. It reads the DEM from the capture and the imagery from the
orthophoto cache, or the built tile's textures with `--imagery-dir`
(read-only). It prints one line per site with every vote, abstain and answer,
and writes `witness_votes.json`. With labels, it prints precision and recall
per question and per source.

**Captures:** reuse KDIJ (lrwypin) and KBUF (lpackcut). Take LGAV, NZWN and
LFLL once (`--capture`, the owner's Custom Scenery as shipped) and register
them (`frames.py register`). Imagery: the owner's built textures for all five
(§0.3, read-only), so the prototype reads **the imagery the owner's build
used** and downloads nothing.

**Label sets** (`docs/specs/multi-source-terrain/labels/<ICAO>.json`, one record per site: question, site, truth, whence):

| airport | Q | labels and where they come from |
|---|---|---|
| KDIJ | Q1 | 2 ends: pavement extent and markings read from the built texture (§0.1); CIFP 04/22 points as negatives |
| KDIJ | Q4 | every 20 m on the RSA and zone-2 rings of 4/22: truth = the lidar break where its slope change ≥ 3 % (fresh 2020 lidar), so the imagery is scored against the lidar |
| KBUF | Q5, Q6 | owner sites 1–3 (positives, lidar floors in §0.2) plus every pack `Road_Tunnel.obj` portal; every OSM bore end not under a pack portal, labelled from the texture |
| NZWN | Q5 | owner sites (negatives) plus all 12 production `tunnel_ramp` mouths, labelled from the texture and the lidar |
| LGAV | Q5, Q6 | the trench and the 12 production ramps, labelled from the texture and the pack's authored trench walls (Copernicus abstains: this is the imagery-only airport) |
| LFLL | Q4, Q5 | the rail cut past the station (#1333 (2)) every 20 m: lidar break vs image edge; every mapped bridge and tunnel mouth in the pack (#1333 (3)) |
| all | Q3 | every layout pavement polygon: truth = in the imagery and graded in the lidar (expected all "current" on these five; a **synthetic twin** paints an extension, a lidar patch of natural ground under a new apt.dat runway end, to test the stale path, since none of the five shows one) |

**Bars (pre-registered):**

- Q5: precision ≥ 0.95 and recall ≥ 0.9 over all mouths, with the three
  witnesses voting. Every owner site in §0.2 answered right.
- Q1: every labelled end right. KDIJ: CIFP yields both ends.
- Q4: on lidar airports, the image edge within 10 m of the lidar break at ≥ 70 %
  of the stations it does not abstain on, and an abstain rate ≤ 40 %.
- Q6: at KBUF, each portal's answer and its lidar floor are listed. A gap
  over 0.3 m is a finding for the master (pack floor vs the real ground),
  not a bar.
- Cost: the §7.5 rows measured per airport (`--witness` prints them).

Convergence guards: materiality floor 0.3 m (floors) and 5 m (edges); at most
two threshold iterations per bar. A second miss is a stop-and-report to the
master, never a third try.

**Closing test (after the owner rules and the implementing lane lands):** ONE
build, of the airport carrying an owner site. Recommended: **KDIJ**.
It carries Q1, Q2 and Q4 at once. Its site bar is both runway ends within
0.15 m of the lidar (today −0.14 m and +0.50 m), with the RSA runout
reaching the DEM at the mowed edge. KBUF is the portal control if the master wants
a second one in the batch sweep.

### 8.1 Measured (lane `ltriang2`, 2026-10-26; `v2_solve_replay --witness`)

Captures: KDIJ (lrwypin), KBUF (lpackcut), NZWN / LGAV / LFLL (taken by
this lane, registered in `frames.py`). Imagery: the owner's built tiles
(live textures named by `terrain/*.ter`). Labels:
`docs/specs/multi-source-terrain/labels/<ICAO>.json` (read off the built
textures and the lidar by this lane; owner sites from the issues).

| bar | measured | verdict |
|---|---|---|
| **Q1** every labelled end right; KDIJ CIFP yields both ends | **14 / 14** (KDIJ 2 dropped; KBUF 4, LGAV 4, LFLL 4 kept, the markings confirming the CIFP displaced thresholds within 0.5–4 m). NZWN 16/34 labelled *neither* (threshold bars about 130 m / 108 m in; apt.dat 150 / 156, CIFP 66.5 / 36): the vote keeps CIFP (layout and imagery disagree) — a finding, not scored | **MET** |
| Q1 on the 81 shifted runways (lrwypin's test set) | 162 ends, 76 with an owner-built texture, 8 with an imagery vote: **2 drops (KDIJ 4, 22), both right**; 4 ends where the markings confirm CIFP over a stale apt.dat (KAEG 17/35, KVCB 2/20), kept; 2 false marking reads, both ties, no action | **MET** |
| **Q4** image edge within 10 m of the lidar break at ≥ 70 % of non-abstaining stations, abstain ≤ 40 % (lidar airports) | KDIJ 33 %, KBUF 70 %, LFLL 42 %, NZWN no truth (every probe crosses pavement); **pooled 48 %**, abstain 30 % — after two iterations (stations crossing pavement abstain; a coherent-line mode over 9 stations) | **MISSED** — step 4 stops (§5 Q4 not wired) |
| **Q5** precision ≥ 0.95, recall ≥ 0.9, three witnesses | 60 labelled mouths: **precision 0.52, recall 0.94**. The lidar alone: 21 / 21 positives and no false yes (P = R = 1.0); the classic imagery alone P 0.40, R 0.76 (dark roofs and building shadows read as openings) | **MISSED** (no iteration spent: the fix is a seniority change — §9 Q-F) |
| Q6 KBUF floors (finding, not a bar) | lidar core minimum at the pack-pinned mouths: way −756 ends 208.08 / 208.72 against pack floors 205.54 / 206.28; −709 212.28 against 210.38; −766 212.22 / 214.21 against 212.94 — gaps 0.7–2.5 m, over the 0.3 m floor | finding for the master |
| cost per airport (this Mac, under sibling load) | Q1 0.2–0.6 s; Q4 0.8–11 s (unwired); Q5 0.04–0.3 s | Q1 is about 1 % of the 60 s budget (final-profile round) |

---

## 9. Owner questions (ruled: RULINGS 2026-10-26v, 26w, 26x, 26y, 26z, 27a)

**Q-A. A CIFP threshold that is not on the runway in the imagery.**
At KDIJ, the CIFP records for runways 4 and 22 both sit 594 m north-east of
the runway the photo shows. The runway 22 record lies in a crop field past the
22 end, and the runway 4 record is mid-runway with no threshold marking. Today
we still pin runway 4's CIFP height there, as if it were a displaced
threshold. (a) When the layout and the imagery agree on where the runway end
is and CIFP disagrees, the CIFP record is dropped for that end (position and
height), and the end follows the lidar like any runway without CIFP (26e);
(b) keep using the CIFP height at its own point (today's rule).
**RULED (a): RULINGS 2026-10-26v (Q177), "A".** Implemented at the end-pin
derivation site (`airport/runway_end_witness`, §8.1).
The CIFP points are ground beside an old or moved runway,
not thresholds. Their heights only agree with the lidar because the lidar
there is ground. With (a), the 22 end (now +0.50 m) is expected to sit on the
lidar; §8 measures it. The 81 shifted runways lane lrwypin counted are the
cases (a) would be tested on.

**Q-B. Where the graded ground meets natural ground (the KDIJ mowed edge).**
(a) Where the elevation data is coarse (no lidar), the edge seen in the
imagery sets the outer edge of the graded zone around runways and taxiways.
It can widen the zone by up to 20 m and never narrows it below the law's
width. Where the lidar is fresh, the edge is only a check, because the lidar
already holds the real fill. (b) The imagery edge is only ever a check.
**RULED (a): RULINGS 2026-10-26w (Q178), "A"; amended by 2026-10-26z (the
edge may also narrow or shorten the zone; the 20 m widen-only cap dropped)
and 2026-10-27a (Q181: never below the standard width — the FAA RSA or
ICAO strip for that runway — and every place the imagery shows less is
logged).** Not wired: the §8 Q4 bar was missed (§8.1).
On lidar the two agree (KDIJ, within 0–10 m), so nothing
moves. On coarse data it is the only witness of where the fill stops, and it
fits the terrain to the imagery as 26q asks.

**Q-C. A cut the imagery and lidar show but no map source names.**
(a) The witnesses only confirm, refuse, place and set the depth of cuts that
OSM or the pack names. A cut with no map source is a log line and a finding.
(b) Where the lidar and the imagery both show a cut, the build cuts it even
with no map source. **RULED (a): RULINGS 2026-10-26x (Q179), "A"** (the
prototype reads mapped mouths only, `portal_witness.mapped_mouths`).
Without a map source there is no road
to seat, no axis and no width. Both owner reports of a missing cut (KBUF sites
1 and 2) had a pack portal object, which (a) covers.

**Q-D. Waiting for the airport photos before the patch is solved.**
The patch is solved before the photos normally download. (a) The build
downloads the airport's own photos first (the ones it downloads later anyway)
and the patch waits for them. The first build of a tile is slower by that
download, and every build of the same inputs gives the same patch. (b) The
patch never waits. When a photo is not there yet, the imagery's votes abstain,
so the first and second builds of a tile can differ. **RULED (a): RULINGS
2026-10-26y (Q180), "A".** Implemented: the session hands the vector step
`O4_Imagery_Prefetch.fetch_airport_imagery`, which downloads the airport's
own textures (`zone_list_to_ortho_dico`'s assignment over the boundary +
500 m) before the patches build; the background prefetch puts the highest
zoom first and shares its download lock. A
patch that changes between two builds of the same inputs breaks the A/B
measurement and confuses a sim read. The download is not extra work, only
moved earlier.

**Q-E (new, for the owner). Does an imagery-only change rebuild the airport
patches?** Owner 2026-10-12 (#615): a rebuild whose only change is the
imagery rebuilds "just the DSF" — the vector step and its patches are
reused. 26q / 26y fit the patch to the imagery, so a provider switch now
changes what the patch should be. Today: the patch stamps `o4_imagery`, so
the next time the vector step runs it refits; an imagery-only rebuild keeps
the old patch.

**Q-F (new, for the owner). At a mapped tunnel mouth, should fresh lidar
outrank the photo?** Measured (§8.1): the lidar alone answers all 21
positives and every negative right; the classic photo method reads dark roofs
and shadows as openings, and with the map's own "yes" it outvotes the lidar
2–1 (precision 0.52). (a) On fresh lidar the lidar decides and the photo is
a check; the photo votes only where the elevation data is coarse (LGAV).
(b) Keep the vote as ruled and wait for the image model branch.

---

## 10. Not in this spec

- **The learned model itself**: the side branch builds it against §7.3.
- **Q7** (retaining walls, terraces): VNLK waits for the owner's video (26n).
- **Imagery dates**: no provider metadata call is added (§2.1).
- **New pavement from imagery**: the witness never draws pavement the layout
  lacks. Pavement in the photo with no layout is a log line.
- **Engine code, tests, the `--witness` flag and the label files**: the
  implementing lane, after the owner rules Q-A to Q-D.
- **Precision and recall on the six airports** (#1359's deliverable): §0 is
  hand probes on owner sites only; the numbers are §8's output. EGGW and EGLL
  (#1298) are not in this round's five; they join the label set when their
  captures exist.
