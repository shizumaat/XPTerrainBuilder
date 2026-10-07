# padspec REVIEW — the pad / platform / collar / block machinery under a terminal (Fable, 2026-10-07)

Owner RULINGS 2026-10-07a (6) / 07b (4), issue #452. Design and review only;
no engine code touched. The new spec is `design-surface-spec.md` **§56**
(`tools/docq.py spec '§56'`); the lane summary is `docs/briefs/padspec-summary.md`.
Numbers below come from the sweep artefacts `/tmp/harness/swg_{OTHH,HECA,KCLT}.*`
(main `798702f2`-era builds), the registered captures `perfA362/OTHH.pkl`,
`gaps3/HECA.pkl`, `onelevel318/KCLT.pkl`, and two read-only scratch probes
(`<scratch>/padspec/outline_probe.py`, `road_probe.py`; logs beside them).

## 1. What stands at the owner's site today (OTHH 25.259994, 51.6104872, r = 150 m)

57 emitted faces / 2,375 ring vertices: `building6#collar` **12 faces / 844 vertices**
(one 44,352 m² annulus of 345 vertices + 3 holes, and ELEVEN slivers of 1–96 m²,
0.2–3.7 m wide, 3–25 vertices each), `building6` platform 1 / 552, apron 2 / 457,
`service_road` **29 / 192** (`route41`–`route55`, `small_roads:-97xx`), 5 block
faces / 61, tunnel_trench 5 / 83, junction 82, secondary_parallel 95, parking 9.
Airport-wide OTHH carries **99 collar faces / 2,589 vertices**. The unit's closed
outline (`geom.cluster_outlines`, rule 2) is **1,717 vertices with 34 holes**
over 472,471 m²; HECA T3 `unit:43#6330/0` 1,476 / 7 holes / 169,383 m²; KCLT
`unit:31#0/0` 990 / 36 holes / 115,538 m².

## 2. The pieces — why each exists, what it buys, what it costs

| piece | created by | what it buys | what it costs (evidence) | verdict |
|---|---|---|---|---|
| **Cluster pad outline** (`geom/cluster_outline.cluster_outlines`, minted in `classify/evidence._pads`) | §16g (10) (2), owner 14x "pads must match building clusters exactly"; rules 2–10 from 14ah (airside never taken), 14aj (leaves), #7/#8 (wall lines), #14 (deck shades), #73 (post bridges), #101 (v1 admission gates) | ONE pad per building unit from the pack's true footprints; every seat/frontage/hold reader keys on it | The outline is the UNION OF EVERY PART RING of every walled body, closed only at `footprint_touch_m` 0.5 m and simplified at 0.05 m — so every crenelation, door recess, column line and canopy edge of the pack is a rim vertex: 1,717 vertices / 34 holes at OTHH. Each rim vertex is a planar vertex, a weld candidate, a constraint column, a census subject | **LOAD-BEARING, TRIM AT THIS SITE** (§56 (1)): one simplification rule after rule 2 — probed 1,717 → **650** at OTHH, 1,476 → **472** HECA, 990 → **305** KCLT, with +0.4–1.2 % of area |
| **Pad / apron weld + airside clip** (`planar/pad_cut.apron_cut_to_pads`, `airside_clip`, `airside_vertex_snap`; 09-01g, 23a, 14ah/14as) | contact = value; the apron never tiers into the terminal; a derived pad never takes airside ground | none that the owner named; the weld IS "welded to the surrounding apron" | **KEEP, unchanged** |
| **Frontage level / hard hold** (§20 LS plane, RULINGS 30f + flat-pad v2 §2/§5: hold rows `constraints/platform.py:492`, interval `no_step.hold_interval`, blocks `planar/pad_blocks`) | the flat pad LEADS its frontage; the apron conforms within hard caps; #96/#111 (HECA T2/T3 sunk/floating) are served by exactly this | none specific to shape; it is what makes the rim relief ≈ 0 (next row) | **KEEP, unchanged** (the follower set becomes the single pad face) |
| **Platform + collar** (`planar/platform.platform_split`, `constraints/platform.platform_collar_rows`, `[building_pad] platform_collar`/`platform_collar_max_m`; unit-platform spec §1, RULINGS 28a (1), 10-02v (5), 10-02z) | designed for a world where the rim is airside-led and the interior one plane: a 1:3 bank INSIDE the footprint carrying up to ≈5 m of rim relief (unit-platform §0: HECA T3 +4.68 / −1.74 m) | (a) **It carries nothing now.** Sidecar `platforms` on the sweep builds: every live collar reads `rim_relief_max_m` **0.000–0.002 m** at OTHH (10/10) and KCLT (8/10; the two `building49` blocks 0.23 / 0.48), HECA 0.000–0.043 on 7 of 8 and **0.415 m** on `building147` — while minted **5–15 m wide** (`collar_why` `cap`/`area`/`floor`). The hard hold (30f) moved the relief out of the rim before the collar could carry it. (b) **It mints the slivers**: 11 of the 12 collar faces at the site are 1–96 m² fragments of a 15 m erosion of a crenellated ring — the hairline class §39 exists to kill. (c) **It doubles the rim**: the inner ring is a second ring of ≈ the pad's vertex count (unit-platform §1 (4): +≈2 k vertices at HECA); 2,589 collar vertices airport-wide at OTHH. (d) **It is a second shape class 23 consumers special-case** (`collar-cap-census-20261002.md`; `#collar` literals in `constraints/platform.py:157`, `model/platform.py:164`, `check_grade.py:7031`; `_collars_as_platform` is "THE ONE SITE the object stage learns of the platform"). (e) Refusals: OTHH 2, HECA 5, KCLT 11 `platform_refused` rows — pads that exist only to be reported | **DELETE** (§56 (3)); the landing bank (#290, `landing<k>#collar`) is a different thing and keeps its rows |
| **Block cut** (`planar/pad_blocks.plan_blocks`, `_mint_blocks`, `<unit>/b<k>`; RULINGS 29s A2 / 30f "the pad SPLITS per rigid block"; `frontage_blocks_max` 5) | a unit whose relief the caps cannot absorb becomes N flat blocks with a declared terrace strip at each cut | 5 block faces / 61 vertices at the site; the strip half-width `bank_min_width_m` | **KEEP** — it is 30f's own fallback and the only lawful place for relief that a one-plane pad cannot hold; the block's `/b<k>#collar` goes with the collar |
| **Road ribbons beside the pad** (`classify/ribbon_mint`, `planar/ribbons`; §37, free-road ruling 2026-07-27 for aprons) | a service road keeps its own longitudinal law | 29 faces / 192 vertices at the site; probed: **26 of 29 lie wholly within 10 m of the outline** (2,436 m²), 2 are split by it (`route42`), 1 passes by. Each is a face the pad welds to and §28 (1) grades to the pad's level anyway | **ABSORB the near ones** (§56 (2)): the free-road ruling's own logic ("inside or edge-sharing an apron ARE the apron") read for the pad |
| **Jetway strip / riders** (`constraints/jetway_strip`, `airport/riders`; jetway-strip spec; `[design] jetway_strip_m` 40) | an apron plateau under the jetways; riders hosted on the face under them | not a shape at the site; flat-pad v2 §3 already disarms it on held blocks | **UNCHANGED** here (flat-pad v2 owns its deletion) |
| **Census families** `pad_airside_weld`, `pad_cluster_mismatch`, `pad_airside_renode`, `pad_frontage_hold/_infeasible`, `platform_rim_relief`, `platform_refused` (`check_grade.py`, `families.toml`) | the instruments | `_is_platform_collar` exemptions in three families; `platform_rim_relief` / `platform_refused` measure a region that will not exist | first four **KEEP**; the two platform families stay registered and read 0 (never deleted from `LAW_FAMILIES` — `test_harness` twin) |

## 3. The "more problems" the owner suspects — named

1. **Hairlines**: eleven 1–96 m² collar slivers at one site (0.2–3.7 m wide); a 1 m²
   3-vertex cell is a §39 subject by construction.
2. **Vertex budget**: 1,717 rim + ≈ the same again for the inner ring + 192 road
   vertices, for a surface that is ONE plane. Every one is an arrangement vertex,
   a solve column and a `within_shape` / `pad_flat` pair.
3. **A bank that carries 0.00 m**: a 15 m 1:3 terrace minted under the building
   for relief the hold already removed — invisible, but it is a second ring the
   object stage must be told about (`_collars_as_platform`) and that `islands`,
   `pavement_cap`, `verify/within`, `verify/pads`, `check_grade` each exempt.
4. **Roads beside the building** become 29 faces graded to the pad's level by
   §28 — the owner's exact words: they "have to be graded like the pad anyway".
5. **Refused platforms** (18 across the three airports) are pads that exist only
   to print `platform_refused`.

## 4. What a simplified outline makes unnecessary, and what it does not

Unnecessary: the collar (every row of it), `_collars_as_platform`, the three
`#collar` exemptions, `platform_rim_relief` / `platform_refused` as live
instruments, the collar's inner ring, the 26 near-road faces at the site.
Still load-bearing and untouched by this spec: the cluster-pad admission rules
2–10, the airside clip and weld, the §20 plane, the 30f hard hold and interval,
the block cut and its terrace strip, the landing bank (#290), the jetway strip,
the §55 gap stage. The one-plane pad with its rim ON the plane is exactly the §20
pad CYXY already builds (flat-pad v2 §4 "no regression by construction"); the
unit pad simply joins that class with a simpler rim.
