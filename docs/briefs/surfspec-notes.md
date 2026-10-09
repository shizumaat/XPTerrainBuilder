# surfspec — notes (spec §60: SURFACE-admitted `.pol` as gap sheets; #337, #333; RULINGS 2026-10-09a)

Lane `surfspec` (Fable, design only), branch `claude/surfspec` off main `7cc787ee`.
Probes in `docs/briefs/surfspec/` (`admit_probe.py`, `overlay_probe.py`,
`aptclip_probe.py`, `structures_probe.py`); outputs under `<scratch>/surfspec/`
(`*.json`, `*.log`). No engine code edited. Updated after each finding.

## Captures read (all registered, none taken)

| ICAO | capture | tree | why this one |
|---|---|---|---|
| HECA | `frames/gapapron3/HECA.pkl` | main d0b2f0f4 + gapapron (walls merged) | the only HECA capture carrying today's 23 gap-sheet bodies |
| OTHH | `frames/surface337/OTHH_main900727f2.pkl` | main 900727f2 (2026-10-04) | the surface337 control; OTHH has no object gap sheet on any tree (sw1041 report: `object_pavements.resources_admitted 0`, 70 `dsf:pol` pages) |
| SPJC | `frames/fac334/SPJC_r4.pkl` (#333 gate in) + `frames/conc333/SPJC_main28500ecf.pkl` / `SPJC_arm_ee610d1a.pkl` | 6d2eaa77 / 28500ecf / ee610d1a | the #333 pair |
| KCLT, KASE, CYXY, NLWF | `frames/conc333/<ICAO>_main28500ecf.pkl` | main 28500ecf | sweep controls |

The dump is resolved through `airport/dsf.find_text_dump` on the SHARED mod
cache (the captures' `inputs.dsf_dump_path` points at dead lane trees).

## F1 — THE INTAKE TODAY (main 7cc787ee)

* A GAP SHEET is populated at ONE site, `airport/load.py:605-619`, from ONE
  witness: `airport/object_pavement.read_object_pavements` marks an OBJ8
  draped page `gap_only` when `draped_footprint` refuses it and
  `gap_sheet_footprint` (per-triangle flatness, off-plane share ≤
  `gap_sheet_offplane_max_share` 0.01) admits it (`object_pavement.py:431-438`).
  Id `dsf:gapsheet<k>` (`model/airport.GAP_SHEET_PREFIX`). HECA
  `Airport/ground/asphalt.obj` is the only known case (23 bodies, 1.65 M m²).
* A `.pol` page NEVER becomes a gap sheet today. `load.py:489-507`: the
  name gate `dsf.pavement_gate` → `is_pavement_def` (stock namespace minus
  `PAVEMENT_SKIP`; `MATERIAL_TOKENS` minus `THIRD_PARTY_SKIP`; the 04d (2)
  `conc` word confirmed/refused by `pol_surface`) admits as `dsf:pol<i>`
  PAVEMENT SOURCE; everything else is ignored (facades/lots aside).
* The classify-side gate on a `dsf:pol` source: `classify/evidence._dsf_pavements`
  (boundary + 50 m; ≥ 80 % on apt.dat = OVERLAY → only remainder parts ≥ 50 m²
  as `dsf:pol<i>#<k>` SOURCES; < 80 % joins `ev.pavement_union` WHOLE).
* The mint: `classify/gap_mint.mint_gap_pieces` (called LAST by
  `roles.classify:670`): union of sheets, simplified at half the identity
  spacing, MINUS every standing cell (apron/ribbon flush; everything else
  stood off `standoff_m` 1.45 m) MINUS the runway/taxi band envelope
  (`ribbon_mint.ribbon_extent`, stood off); parts ≥ `object_pavement_min_m2`
  200 holding a 2 m disc; a part along a runway/taxi face touching no
  apron is NOT minted (listed). So a sheet over standing airside pavement
  mints NOTHING there BY CONSTRUCTION — confirmed by the probe (F2: OTHH
  712,279 m² of admitted page on runway cells → 0 m² in pieces).

## F2 — THE POPULATION (`admit_probe.py`, branch gate 3936fd94 ported verbatim vs main's gate, over the cached dumps)

SURFACE-ONLY = admitted by the branch gate, refused by main's. Clipped to the
classify gate (boundary + 50 m).

| ICAO | `.pol` polygons name / SURFACE-only / refused | SURFACE-only m² (clipped) | on every pavement source | on runway / taxi / apron cells | on pads | on standing cells | on today's sheets | FREE of standing cells + pads |
|---|---|---|---|---|---|---|---|---|
| OTHH | 70 / **281** / 8,446 | 5,303,656 (ASPH1 4,380,947; ASPH3 627,736; Stone_Tiles1 145,574; ASPH2 116,367; Stone_Tiles2 18,431; ASPH1_upper 14,600) | 3,394,812 | 712,279 / 1,880,707 / 822,710 | 654,023 | 3,480,339 | 0 | **1,417,955** |
| HECA | 1 / **2** / 0 | 63,173 (`Asphalt_1_NOLINE.pol`) | 169 | 0 / 0 / 169 | 16,743 | 1,182 | **15,346** | **45,248** |
| SPJC | 107 / 0 / 284 | 0 | — | — | — | — | — | 0 |
| KCLT | 101 / 0 / 1,858 | 0 | | | | | | 0 |
| CYXY | 44 / 0 / 20 | 0 | | | | | | 0 |
| KASE | 9 / 0 / 25 | 0 | | | | | | 0 |
| NLWF | 0 / 0 / 2 | 0 | | | | | | 0 |

Refused-though-hard-surface at the five no-op airports: every one is a
`LAYER_GROUP markings` file (SPJC `objectfede/lines/red_grid.pol` 46,
`lib/airport/lines/safety_area_*` 46; OTHH `lib/airport/markings/*` 1,556 +
`Ground/Markings/safe_area_*` 240) or OTHH `Ground/Poly/Grass3.pol` (3, soft
name word). The branch's 9 tests describe exactly this population.

THE MINT on the probe (the real `mint_gap_pieces`, today's standing cells, control = today's sheets, arm = + the SURFACE-only polygons as sheets):

| ICAO | control pieces / m² | arm pieces / m² | new / grown | apron-touching (mint's `touches_apron`) | under floor | band trim m² | rim total |
|---|---|---|---|---|---|---|---|
| OTHH | 0 / 0 | **122 / 671,706** (min 207, p25 645, median 1,467, p75 3,592, max 154,272) | 122 new | 39 / 393,728 | 318 | 619,500 | 133,071 m |
| HECA | 38 / 1,001,549 | 38 / 1,031,194 | 0 new; **2 grown**: `gap:0` 709,935 → 729,034, `gap:1` 53,392 → 63,939 (+29,646) | 19 / 861,812 (same 19) | 75 → 76 | 14,006 | 120,697 m (122,271) |
| others | 0 | 0 | — | — | — | — | — |

So HECA is NOT a no-op: 15,346 m² of `Asphalt_1_NOLINE` lies on today's
`asphalt.obj` sheet (coincident), 16,743 m² on pads, and the 45,248 m² free
part grows two existing pieces by 29,646 m² (the rest is stand-off / band
trim / under-floor).

## F3 — OTHH SCALE

* 1,417,955 m² free → 671,706 m² in 122 pieces after the stand-off, the band
  envelope (619,500 m² — the ASPH pages shoulder every taxiway) and the floors
  (318 parts < 200 m² / no 2 m disc).
* §59 class ESTIMATE on the 39 apron-touching pieces (the §59 readers
  approximated: OSM highway inside, 1206 route within 1 m, road face within
  stand-off + weld; share = apron_shared / rim; the same estimator reproduces
  HECA's §59 table to within one piece — 12 apron vs the measured 11):
  **road by evidence 9 / 329,259 m²; APRON by share ≥ 20 % 24 / 56,774 m²;
  APRON, no road evidence 6 / 7,695 m²** → ~30 stage-1 apron parts / 64,469 m².
  The remaining 83 pieces (277,978 m²) touch no apron: late road pieces.
* Structures (`structures_probe.py` against the sw1041 OTHH sidecar): 7
  pieces (gap:14, 22, 37, 51, 29, 55, 87; 24,326 m²) overlie the
  tunnel-object wall corridors of `tunnel1.obj` / `tunnel south west 2.obj`
  (sunken roads), one (gap:50, 290 m²) a wall corridor; 0 on basin ramp
  rings, 0 on the six stand-zone plateaus, 0 within 5 m of a terrace joint.
  `planar/structure_approach.standing_cover` sets gap pieces aside and
  `cut_gap_cells` cuts them by the structure footprints + stand-off LAST
  (§53 (18)) — confirmed in code (`structure_approach.py:427-451`).
* TIME: sw1041 OTHH warm 448.1 s build (phase ledger: solve 267 s, emit 129 s,
  no late stage). HECA's late stage is 120.1 s (swg) / 146.8 s (sww, under
  load) for 38 pieces → 83 parts, 2,834 stations, 122 km of rim. OTHH's arm
  has 122 pieces and 133 km of rim with many more small parts → late stage
  estimate 130–180 s → **580–630 s against the 600 s bar: at or over it.**
  ONE replay settles it (not run: a sweepwalls KCLT replay held the machine,
  load 4–6, disk at 16 GB free — the OTHH capture is 1.1 GB and a sheet-
  injected copy would need writing).

## F4 — #333 (SPJC), MECHANISM BY INTERVENTION (dry classify on this tree, seconds)

* Today's tree, control capture (147 pavements) vs #333 arm capture (158):
  ROLE CHANGES 5,252 m²: `pav6` junction → apron **1,450 m² at -12.0159033,
  -77.1147723** (450 m south of the owner's site, which is `pav6` junction in
  BOTH arms); `route10/11/12/9` service_road → apron 2,759 m² (the free-road
  absorption once the page made them inside-apron); `small_roads` →
  `dsf:pol50#12` / `#13` apron 972 m² (3.1 m slivers flipped by §27, 7.8 m
  from site 2).
* `aptclip_probe.py` (every page clipped to its OFF-apt.dat part at the
  evidence gate): 9 m² of role change — the ON-apt.dat part of a page is
  NOT the mechanism. Clipping is refuted.
* `conc_3` routed as a GAP SHEET (10 overlay polygons ≥ 80 % on apt.dat;
  `dsf:pol195` at 74 % stays a source): role changes vs the source arm
  5,758 m² = the EXACT inverse (pav6 junction back, routes back, slivers
  gone) + ONE gap piece `gap:0` 505 m² (17 parts under floor, 550 m² band
  trim). Routing the partial page alone: 0 m², no piece. **The overlay
  remainders are the whole of #333.**
* Population of overlay remainders (`overlay_probe.py`): SPJC 13 pieces /
  7,877 m² (cells today: apron 1,679, service_road 520, groundside_pavement
  285, parking_lot 64); KASE 4 / 311; OTHH 8 / 812 (cells parking_lot 389,
  groundside_pavement 159); KCLT 0 (2 + 2 remainder cells from an older
  tree, 1,857 m²); CYXY, HECA, NLWF 0.

## F5 — CONSUMERS (see §60 (5))

`gap_sheets` readers: `gap_mint.py:89` only (+ `load.py` writer, model,
two tests). `is_pavement_def` / `pavement_gate` / `pol_surface` /
`pavement_surface_code`: `load.py:465/489/501/615` + tests. `airport.dsf`
IS in `partition_code.CODE_MODULES` → editing it changes the partition
cache code digest (one cold partition read per airport after the merge).
`pipeline/xplat._load_items` does not read `gap_sheets` (load digest
unchanged); the classify digest changes with the cells.

## Open / not settled

* The OTHH late-stage wall time (estimate only).
* The pull of ~30 apron parts on OTHH's standing apron/taxi (needs §59 merged
  + one OTHH replay pair; the runway is 0 by the mint's construction, the
  §59 zone-claim hairline is gapapron3's to attribute).
