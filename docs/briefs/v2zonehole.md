# Brief pack — lane `v2zonehole`

Base: main `93a2a3d2` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§41: a face inside a pavement face is a hole; zones clipped out of pavement; zone_on_pavement census; role_overlap_read repaired

## The brief

Frame: the owner's 1.0.329 HECA products — data repo `Patches/+30+040/+30+031/HECA_auto.patch.osm` (+ `.axes.json` sidecar), `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+30+031/HECA/` (report.json, graded), the shipped `zOrtho4XP_+30+031` tile — ALL READ-ONLY. `auto_patch_v2 explain --shape N --patch <that patch> HECA` (pass `--patch`; the engine-tree default is a Sep 9 patch with different shapeIDs; `--shape` goes BEFORE the ICAO). Scout `v2heca329`'s numbers are in RULINGS 13cs; its declared reader `heca_probe.py` (xref/samp/line) is in the session scratchpad `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/` — reuse via `tools/mesh_region_tris.py --z-xref` and `tools/osm_site.py` where they fit. Dry arm on the 1.0.329 products first; ONE HECA build through `tools/harness/build_airport.py HECA` as the closing test; other airports dry from registered frames (`frames.py list`). Lanes running beside you: `v2bankfoot` (O4_Vector_Map / O4_Mesh_Utils / emit/bank.py — do not touch), `v2connector` (airport/footprint_unit.py), `v2gradecache` (planar cost).
Implement §41: (1) in the planar stage (`Ortho4XP/src/auto_patch_v2/planar/` — find where zone strips (`adjacent_ground:taxi:*:zoneN`) are derived and where cross-connector faces are admitted), a pavement face ≥ 95 % inside another pavement face is a HOLE of the outer (no rows of its own; outer law governs); (2) zone strips CLIPPED out of every pavement body before emission; (3) census family `zone_on_pavement` (CRITICAL when > 0.5 m² overlap) registered in `tools/check_grade.py` LAW_FAMILIES with its twin (`tests/test_harness.py` will refuse an unregistered family); (4) repair `Ortho4XP/tools/role_overlap_read.py:106` (`KeyError: 'anchor'` on the 1.0.329 sidecar — read the sidecar's actual keys) and make it report the containment census per airport. Site: 30.1312203, 31.3983896 — station inside `primary_parallel:pav73` + `graded_strip:adjacent_ground:taxi:F:zone2#7` + `cross_connector:pav77` (892 m², 100 % inside pav73). Consumer census first (every reader of the zone strips / face list). Twins for (1)–(3).

## Bars

- HECA site 30.1312203, 31.3983896: `zone_on_pavement` 0 after (today zone2#7 over pav73); pav77 a hole of pav73; the taxiway profile ±100 m through the site monotone within the 1.5 % cap (today 66.83 → 65.49 → 67.68, 8.6 % climb-out).
- Containment census (`role_overlap_read.py`, repaired) before → after on HECA and the registered frames.
- The family twin: an unregistered `zone_on_pavement` fails `test_harness.py`; the census counts the site on the 1.0.329 patch.
- Suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/tools/role_overlap_read.py`, `Ortho4XP/tools/check_grade.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/classify/roles.py`, `Ortho4XP/src/auto_patch_v2/constraints/road_ramp.py`, `Ortho4XP/src/auto_patch_v2/emit/bank.py`

## Spec (design-surface) §41

## §41 A FACE INSIDE A PAVEMENT FACE IS A HOLE OF IT; ZONES ARE CLIPPED OUT OF PAVEMENT (owner RULINGS 2026-09-13co item 2; Fable 2026-09-13; RULINGS 2026-09-13cs) — lane `v2zonehole`

**THE DEFECT.**  At 30.1312203, 31.3983896 (HECA) the taxiway station is inside
`primary_parallel:pav73` AND inside `graded_strip:adjacent_ground:taxi:F:zone2#7`
(stations 0–60 m) AND inside `cross_connector:pav77` (892 m², 100 % within
pav73's ring).  Three surfaces over one point; the mesh takes the union and
the taxiway dips 66.83 → 65.49 → 67.68 over 87 m (8.6 % climb-out against a
1.5 % cap); verify has 0 rows within 40 m because each face is lawful on its
own.

1. A pavement face lying wholly (≥ 95 % of its area) inside another pavement
   face is a HOLE of the outer face for the purpose of the design surface: it
   contributes no rows of its own; the outer face's law governs every vertex
   in it.  (A cross-connector inside a parallel is the parallel.)
2. Adjacent-ground zone strips are CLIPPED out of every pavement body before
   emission: a zone vertex standing on pavement is a defect the census names
   (`zone_on_pavement`, CRITICAL when > 0.5 m² of overlap).
3. `role_overlap_read.py` is repaired (it crashes on the 1.0.329 sidecar:
   `KeyError: 'anchor'`) and reports the containment census per airport.

BARS: HECA the 1.0.329 frame: `zone_on_pavement` 0 after (today: zone2#7 over
pav73 at the site), pav77 a hole of pav73; the taxiway profile through the site
monotone within the 1.5 % cap; the five-airport containment census before →
after; suite twice.

## RULINGS

## 2026-09-13cs HECA eight items attributed (scout `v2heca329`): none is the 13cp mesh regression; §40, §41, §37 (10) written; lanes `v2roles`, `v2zonehole`, `v2roadcontact`

Scout on the owner's 1.0.329 +30+031 tile, read-only. Tile-wide node→mesh
cross-reference: PATCH_RING 27,673 vertices 0 off; road ribbons 271,698, 2
off (both ~100 km from HECA); at every owner site mesh = patch to 0.000 m.
The 13cp condition IS present (128 open `bank_foot` ways vs 9 closed;
annulus seeds 252 → 3, valued vertices 84,631 → 0, INTERP_ALT 629,054 →
369,060, harmonic "kept own" 374) but landed on no authored HECA vertex.

| # | class | ruling |
|---|---|---|
| 1 shape 44 | PATCH-ROLE: 585 m along runway 05L/23R, 73 % apron cover, still a corridor (no rung refuses it) | §40 (1) runway shoulder joins the runway body; §40 (2) apron cover refuses the corridor kind |
| 2 dip | PATCH-SOLVE: zone2#7 strip and `cross_connector:pav77` (100 % inside pav73) emitted over the taxiway; 8.6 % climb-out, verify blind | §41: inner face = hole; zones clipped out of pavement; `zone_on_pavement` census; `role_overlap_read.py` repaired |
| 3 hill | PATCH-SOLVE: route7 holds the DEM 1.5 m above the cut ground beside pav131 | §37 (10) (1) contact within reach |
| 4 road step | PATCH-SOLVE: two route frames on one ribbon → `NOT_A_PAIR`, 42.6 % never priced | §37 (10) (2) pairs by geometry |
| 5 cliff | PATCH-SOLVE: taxiway not in the contact set → road targets the DEM, 33 % step | §37 (10) (1) taxiways are airside contacts |
| 6 shape 93/478 | PATCH-ROLE: corridor (width 27.8, apron 13 %); 478 is its zone strip | §40 (2)/(3) |
| 7 floating building | OBJECT, NOT REPRODUCED: pad 88.88–88.98 = mesh 88.955; `T3_60.obj` in `unit:41` (36 members, anchor 1.7 km away, 19.47 m higher) but no seating row > 0.5 m within 70 m | owner asked for the object / a screenshot; standing HECA object debt noted: +19.70 m at 30.120503,31.402651 (`feet:20`, 1,144 m diameter), `Airport/T23` median −4.04 worst −11.71, 83 of 359 over 0.5 m |
| 8 missing apron | MISSING-SOURCE: 0 rings; nearest OSM apron 60.5 m, apt.dat pavement 110.6 m; the pavement seen is the pack's draped `.pol` page; the "feeder" is `apron:pav132` | INTENT QUESTION to the owner: admit the pack's DSF draped-pavement pages as source polygons (`dsf_pavements` admits one today)? |

* Lanes: `v2roles` (§40, `classify/roles.py` + `rules.toml`), `v2zonehole`
  (§41, planar zones + `role_overlap_read.py`), `v2roadcontact` (§37 (10),
  `constraints/road_ramp.py`, `airport/road_ramp.py`). HECA is the closing
  airport for each; dry arms first on the 1.0.329 products.
* Chips: `role_overlap_read.py` `KeyError: 'anchor'`; `auto_patch_v2 explain`
  defaults to the engine-tree patch (Sep 9) — must take `--patch`, and
  `--shape` only before the ICAO.
* Not verified: item 7; the `apron_named=1` token on cells 58/191 (source
  description matches no token — untraced); no registered HECA frame.

## 2026-09-13co Owner read of 1.0.329 — HECA ("mostly … close to the best we've built so far"), six items — scout `v2heca329`

Owner, verbatim: "HECA is mostly looking close to the best we've built so
far. Some issues: 1. shapeID 44 is a taxiway role, but taxiway cannot run
adjacent to a runway, that portion should have been absorbed into the runway
itself 2. Around here: 30.1312203, 31.3983896 I can't tell if there's a gap
with no coverage, or just a problem, but in the sim their's a bit dip in the
taxiway that aircraft could not drive through. 3. This taxiway has too much
lateral slope: 30.1114112, 31.4063353. Really we just need this area
30.1116052, 31.4066985 to be lowered so we don't have so much of a hill
right there, then the road, taxiway, and apron can all meet more smoothly.
4. This is the edge of a road: 30.1096746, 31.4048466, the center of the
road here: 30.1096476, 31.4048517 is lower creating a sharp lateral slope in
the road 5. Road here: 30.1077666, 31.4031555 is ending in a cliff above the
taxiway, it should join the taxiway edge smoothly with no gap and at the
same elevation. 6. This large area 30.1082777, 31.4022695 is apron, not all
taxiway, and shapeID 478 should be part of it, not adjacent ground"

* Earlier in the same read (LEMD): "There's nothing in the patch, it seems
  like both LEMD and HECA the terrain looks different, did anything change
  with the DEM? … a road that now appears in a deep canyon: 40.465414,
  -3.5531888". Checked: NO DEM refresh since 2026-09-08 (refresh ledger), no
  elevation file newer than the 1.0.329 app. Mesh-path commits since
  1.0.327: b6ad4309 / 0523aec5 / 95579a99 / d1fd6242 (§39 shore weld,
  vector-map weld OFF, pre-flight). Scout `v2lemd329` redirected: coverage
  test at the coordinate, mesh profile vs DEM, diff of every code path
  touching non-patch terrain.
* Scout `v2heca329` dispatched on the six HECA items: (1) shape 44's role
  and its runway adjacency — the §29 (7) lateral band / role scorer; (2)
  coverage at 30.1312203, 31.3983896 and the dip's profile; (3)/(4) the
  cross-slope at the two sites against §37 (8) (road cross-section is LAW)
  and the taxiway lateral cap; (5) the road end vs the taxiway edge — §37
  (9) coverage-edge join; (6) shape 478's role and the apron/taxiway
  partition at 30.1082777, 31.4022695.

## Tool: role_overlap_read

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). `--pad M` grows the ON union before the read and `--beyond` reports the COMPLEMENT — the OVER ways that do NOT reach it, totalled and split by ref: the OWNERSHIP read RULINGS 31b is stated in ("within SERVICE_ROAD_PAVEMENT_NEAR_M of aircraft pavement"), which is how Batch 4a priced HECA's far road-family population off the merged-main control (`service_junction` beyond 25 m of the airside roles: 1,526 of 1,777 rings / 473,248 m², of which 1,325 ref-less / 435,882 m²). `--site LAT,LON` (repeatable) answers a named place in the OVER class's own terms — which way covers it, its ref and area, and the distance from both point and ring to the ON class. Several patches are reported separately — the arm-to-arm read; quote it on identical options. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, the `--pad`/`--beyond` complement, the `--site` read, and this index row). |

| `Ortho4XP/tools/role_overlap_read.py` | The question is WHAT STANDS ON WHAT — *how many square metres of one emitted role/ref class lie on another class's footprint* — which is the single number a ruling of the form "the gap-fill spine must STOP at groundside pavement" (RULINGS 2026-08-30 ruling 4) is accepted or refused on. No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a face lying flat on a lot breaks no grade law and reports ZERO rows; `osm_site.py` answers one coordinate and `arm_site_read.py` one named place; `void_census.py` asks enclave TOPOLOGY; `lattice_overlap_read.py` asks CONTAINMENT of the two role-less membrane classes by LENGTH. This is the AREA sweep: `--over ROLE[:REF] --on ROLE[:REF],...` reports the populations, how many OVER ways stand on the ON union, the total m², and per stacked way its own area, the area over, the fraction and the ON shapes it stands on, largest first. **It measures no law and counts no defects** — geometry, the metre frame about the sidecar's own anchor and the role-carrying rings come from the harness library (`check_grade._parse_osm` / `_ll_to_m_factory`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. A patch with NO `.axes.json` sidecar is REFUSED (no anchor, no metre frame — an area in the wrong frame looks right and is not). `--min-area` (default 1.0 m²) is emit rounding, not a law threshold. Measured basis (HECA round 6b/6c): on the round-6b closing arm `graded_strip:gap_fill_spine` over `groundside_pavement` = 18 strips / 26,780 m², two faces carrying 24,288 m² of it (3190 over lot 2813 by 13,657 m², 70 %; 3192 over 2814 by 10,631 m², 63 %), while the same read over `service_road,service_junction` — 34 strips / 25,073 m² — said the annulus class was not one ruling's alone. Promoted 2026-08-30 from the HECA round-6b lane's scratchpad on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. Twin: `tests/test_role_overlap_read.py` (the area IS the intersection, the ROLE:REF selector is exact, the floor both ways, prices-no-law, the no-sidecar refusal, and this index row). |

## Tool: osm_site

| `Ortho4XP/tools/osm_site.py` | You have a coordinate and the question is WHAT IS THERE — which ways carry that spot, how they are tagged and roled, how many nodes they have, what altitudes those nodes carry — or you want one way's node chain dumped in order. Reads BOTH OSM dialects this repo produces (the emitted patch's single-quoted attributes with per-node `alt_abs`, and the Ortho4XP road feeds' double-quoted ones, plain or `.bz2`), so a patch and the feed it was built from can be read side by side in one process, at one probe point, in one projection. Several files are reported separately — that is the arm-vs-arm read (an owner artifact against a lane build) an attribution starts from. `--role` scopes to one emitted role, `--dump WAY` prints the chain with per-node altitude and distance, `--json` writes what the report printed. **It measures nothing and derives no law**: every value is read verbatim out of the file, and defect counts come from `harness/census.py` and nowhere else — a private re-count is the census-wrapper defect. A node with no `alt_abs` reports `None`, never 0.0 (no authority claimed it is a real state), and a dangling `nd` ref is reported, never dropped. Promoted 2026-08-12 from the round-20 lane's `kclt_site.py` (patches) and `osmfeed.py` (bz2 feeds) on their SECOND use (RULINGS `7e90032`, promote-on-reuse): two copies of one question asked of two formats, already drifted — one could read `alt_abs`, the other could read bz2, neither could read the other's quoting. **`--contains` is the SECOND question, and it is not the first one** (added 2026-08-28, spec `docs/specs/lemd-pad-authority-carve-spec.md` Acceptance): `--at` reports the distance to a way's nearest NODE, so a point deep inside a large ring reads tens of metres away and NEVER 0.00 m — a lane quoted "1.20 m / 11.60 m outside" off exactly that and a containment read then put both owner probes 9.87 m and 3.88 m INSIDE the pad (`lemd-basin-trench-ramp-extension` Amendment 2). `--contains` asks WHICH RINGS COVER THIS POINT: geometry comes from the harness library's own parser (`check_grade._parse_osm`), imported and never re-spelled, and rings are grouped by `(role, ref)` and decided EVEN-ODD inside each group — a point in a hole ring is OUTSIDE its own pad, not inside two ways. **`--line LAT,LON:LAT,LON [--step M]` is that same containment answered along a SEGMENT, station by station** — the reading a "the plate covers the whole ramp" acceptance is stated in (the carve spec samples the deck line at ~2 m); both ends are always stations, and a run of stations INSIDE NOTHING is itself the finding. Neither prices a law nor counts a defect. **THE THIRD ROAD SOURCE (2026-08-28, LEMD ramp/road fidelity round):** a `.cache` file is the X-Plane DSF VECTOR ROAD NETWORK sidecar (`Airport_mod_cache/<pack>/o4_dsf_road_network_<tile>.cache`), unpickled through the engine's OWN record types (`auto_patch.dsf_road_network`) — never a second DSF parser — and presented as ways so `--at` / `--dump` / `--json` work on it unchanged. Reach for it where the OSM sources are EMPTY and the corridors still come from somewhere: at LEMD the tile carries no small-roads extract and `big_roads` is empty at both tunnel sites, so this sidecar is the only thing that can say how many chains cross a portal, what subtype each carries and whether it drapes (level 0) or flies (level 1+). A node reports NO altitude: the network's third column is a draping LEVEL FLAG, not metres, and it is reported as the `level` / `draped` tags it is. TWO SELECTION FRAMES, and the one in force is printed on every report and carried in the JSON (`selection_frame`): the nearest NODE (the default, the frame every pre-2026-08-28 caller reads in) or the closest approach to the POLYLINE (`--by-line`, the default for a `.cache`, because a DSF segment's shape points stand tens of metres apart while the road passes right over the probe — measured at LEMD item 1: nearest node 34.54 m, line 0.66 m). Both distances are always reported, so the two frames can never be mixed unnoticed. **`--relate` is the FOURTH question, and it is the DUPLICATION one** (added 2026-08-30, spec `docs/specs/othh-tunnel-mouth-canonical-spec.md`): `--at` says WHICH shapes are at a coordinate, `--contains` says which COVER it — neither says HOW THEY SIT AGAINST ONE ANOTHER, which is the whole of a "is this one corridor emitted twice?" question. It reports, per touching pair among the ways `--at` selected, the two areas, the OVERLAP AREA, the SHARED-BOUNDARY LENGTH and the containment verdict — same rings, same metre frame and the same harness-library parser (`check_grade._parse_osm`) as `--contains`, imported and never re-spelled. The shared-edge column is the discriminator the other modes cannot give: two surfaces that TILE (0 m² overlap, a long shared edge) are one surface emitted as two, which reads identically to two neighbours under `--at`. Measured basis (OTHH item 1, owner patch 2026-08-29): service_road -10051 vs tunnel_road -12306 — overlap 0.0 m², shared edge 211.22 m, union area == sum of parts, i.e. one road corridor cut into three shapes. It prices no law and counts no defects. Twin: `tests/test_osm_site.py` (both dialects, both containers, absent-altitude-is-None, radius/role selection, nearest-first order, dump order, dangling refs, the CLI's JSON IS the library's result, the refusals, the nearest-node-is-not-containment trap, the hole ring, the role filter, both-ends stations, the DSF cache source with its two selection frames, `--relate` reporting a tiling pair as 0 m² overlap with a long shared edge and an overlapping pair as overlap, and this index row). **`--relate` reads the FEATURE rings too and the rim's stand-off** (2026-09-08a, lane `v2trenchgap`): the role-less `o4_feature` ways the census skips (`structure_rim`, `gap_interior_ring`) join the ring set as role `feature:<name>`, and each pair carries `boundary_gap_m` (the smallest vertex-to-other-exterior distance over the vertices not on it) with `a_off_b_median_m` / `b_off_a_median_m` (each direction's median) — `gap_m` reads 0 for a rim around its ramp, and the question there is how far the rim's vertices stand off the ramp edge (the mesh wall band's width: OTHH tunnel sites read 1.77 / 1.12 m under 06b's `rim_gap_m`). Quote the median for the side stand-off; the minimum is a corner's. |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. |

## Registered frames: HECA

(none registered)

## Registered frames: KCLT

KCLT  capture  base ec8723e9   lane v2eat            2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2eat/cap  — captures of KCLT/HECA/OTHH/SPJC by lane v2eat; base predates the 13ak pad-law break — valid
KCLT  rebake   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.rebake.json  — v2familyKCLTframe build (rc 0, 389.3 s, body_sha bb022a77f067) on main 864e7577 — POST 13ak pad-law fix; the build was CONTAMINATED (one Airport_mod_cache dump, chip 13ao) so it carries no ledger key
KCLT  graded   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.graded.json  — the design surface of the same v2familyKCLTframe build
KCLT  capture  base 70646dc8   lane v2roadramp       2026-09-13T12:44:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/KCLT.pkl
KCLT  rebake   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.rebake.json  — v2clusterpadKCLT2 build (rc 0, 477.2 s, body_sha 9f056cce3dc3, shared repo UNCHANGED) on claude/v2clusterpad over main 0c86fe2c — the FIRST KCLT frame carrying the §30 (4) CLUSTER PAD and its apron reach; no ledger key (the tree moved between key and store time)
KCLT  graded   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.graded.json  — the design surface of the same v2clusterpadKCLT2 build: building80+building91 are ONE plane (union spread 4.43 -> 1.46 m) and 38 of 90 apron vertices within 60 m sit at the pad's level
KCLT  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/KCLT_20260913T172152.osm  — closing build of claude/v2zonebank cde84e27 (rc 0, 492.4 s, body_sha 9113da337600, ledger 6486660716cc, shared repo UNCHANGED) — §37 (3) as amended: bank 134 rings / 1,311 foot nodes, bank_foot at both owner sites (38.3 m and 10.2 m) and at the 13ax lip; census law-true 13,416
KCLT  graded   base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/zonebank/KCLT.solved.pkl  — v2_solve_replay --solved-out off cap/KCLT.pkl on BASE ce203b29 — the fixed upstream for 'v2_solve_replay --bank-from PKL --bank-walk' (2.5 s per bank-stage arm)
KCLT  graded   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.graded.json  — v2cpKCLTr2 (rc 0, 493.0 s, 5fb560ae50d0) — the CLUSTER arm of the matched pair; its DISARM twin (cluster_pad_min_m2=0, cluster_apron_reach_m=0) is v2cpKCLTdisarm at .../disarmOUT/v2cpKCLTdisarm.v2/
KCLT  rebake   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.rebake.json  — the rebake plan of the same v2cpKCLTr2 build
KCLT  graded   base 952924e9   lane v2clusterpad     2026-09-13T18:15:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/c3/v2cpKCLTc3.v2/KCLT.graded.json  — round-3 CLUSTER arm (13cc reach: population minus no-step-coupled apron, priced at apron_trend); its matched DISARM twin is .../d3/v2cpKCLTd3.v2 and the PAD-ONLY attribution arm .../padonly/ is BYTE-IDENTICAL to the disarm
KCLT  patch    base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_arm.osm  — §39 ARM patch (harness tag v2hairline_kclt_patch): shore weld dropped 2 bank nodes, worst 0.0198 mm at 35.2031709,-80.9454997 (the 723,015-sliver site)
KCLT  graded   base e88ed84b   lane v2clusterpad     2026-09-13T18:41:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p5/v2cpKCLTp5.v2/KCLT.graded.json  — round-4 PAD-ONLY arm (reach 0, merge EFFECTIVE: building91 221.52, union spread 1.07); its matched DISARM twin is .../d4/v2cpKCLTd4.v2 (bde3f0aff32e). Taxi family 2,406 moved worst 2.07 m between the two — the merge's own, the reach is off in both
KCLT  graded   base 8841c106   lane v2clusterpad     2026-09-13T18:58:24  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p6/v2cpKCLTp6.v2/KCLT.graded.json  — round-5 PAD-ONLY arm under the §30 (4) (5) GATE — BYTE-IDENTICAL to its DISARM twin .../d4/v2cpKCLTd4.v2 (both bde3f0aff32e): building91 yields (65.81 m from the terminal, a part-box artefact), taxi family 0 moved
KCLT  patch    base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_r2.osm  — §39 round 2 arm patch: hairline_pair adjudicated 0, emitted sub-spacing segments 799 -> 11 (all the deliberate triangle floor)

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

