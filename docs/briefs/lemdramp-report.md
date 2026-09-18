# Scout `lemdramp` — LEMD 1.0.348 items 2–3

Read-only. Base main `ab879322`. Products read: the shipped tile's patch
`/Users/noah/XPTerrainBuilderData/Patches/+40-010/+40-004/LEMD_auto.patch.osm`
(+ `.axes.json`), `/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+40-004/LEMD/LEMD.report.json`,
the registered dry structure arm `/tmp/harness/v2wallface/base_LEMD/structures.json`
(main `31b7ad1b`, 2026-09-17 19:20 — 15 min before the shipped build; see §6),
apt.dat `/Users/noah/X-Plane 12/Custom Scenery/Aerosoft - LEMD Madrid - 1 - Airport/Earth nav data/apt.dat`,
the OSM feeds under `Ortho4XP/OSM_data/+40-010/+40-004/`, and two dry
`python -m auto_patch_v2 explain LEMD` runs (classification only, no tile build,
lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR`; shared repo not written).

## Headline

Both owner items are ONE site: the **F-6 taxiway-bridge underpass** (§34 (5)),
its third owner read in a row (14bl item 1, 15e item 7, now 17q item 2).

* −10863 is **an OSM bore's north mouth ramp**, not an object corridor, door ramp
  or channel: `tunnel:-5821+-5820@1`, the north half of the dual-carriageway
  service-road pair bored under `aeroway=taxiway bridge=yes layer=1` way −1230 (F-6).
* The mouth's position is **not** set by §34 (8) (that rule only runs for WALL
  corridors). It is set by §34 (5) (a)+(b): the deck CELL's kerbs across the axis
  **plus its graded strip**, eroded by 2.1 m. F-6's OSM centreline runs **0.15 m**
  from `pav157`'s north kerb, so the code-E strip (19.0 m) is added almost entirely
  on the north side: mouth = 0.15 + 19.0 − 2.1 ≈ **17.0 m north of the centreline**,
  ~16.9 m past the taxiway cell's own north edge and 14.5 m inside `pav188`.
* `pav188`'s `apron` role is **NOT** what let the mouth sit there. §34 (12) (3) —
  "a corridor never cuts airside pavement" — already covers `apron`, and would
  equally cover `junction`; the mouth escapes it through the explicit
  *portal's-own-pavement* exclusion at `structure_service.py:283-284`.
  **Re-classifying `pav188` as taxiway would not move this mouth at all.**

---

## 1. WHICH CORRIDOR is −10863

**An OSM bore's mouth ramp under a §34 (5) underpass.** Ruled out:

| candidate | evidence |
|---|---|
| §34 object corridor (`object_corridors`) | LEMD has exactly **1** (`report.json /planar/structures/object_corridors = 1`); the sidecar's only `tunnel_objects` record is `tunnel-object:Bridge4.obj@0`, axis at 40.4866,−3.5667 — 2.9 km away (`LEMD_auto.patch.osm.axes.json`, key `tunnel_objects`) |
| door ramp | `/planar/structures/door_ramps = 0` |
| §45 channel | `/planar/structures/channels = 3`; none at this site (`structures.json` `channels`; RULINGS 2026-09-15aa/`docs/RULINGS.md:7470` — F-6's `−5821/−5820` were *taken back* from the channel pass) |
| wall corridor / sunken road | `wall_corridors = 0`, `sunken_roads = 0` |

**The record** (`/tmp/harness/v2wallface/base_LEMD/structures.json`, `tunnels[]`):

```
id            tunnel:-5821+-5820@1     source osm
mouth_ll      40.4613118, -3.5446744   top_ll  40.4620682, -3.5446807
mouth_z       564.9    mouth_dem_z 570.0
top_s         84.0 m   climb_from_s 0.0   design_grade 0.08
notes         "stations collapsed 8 -> 3 (§34 (7))"
              "dual carriageway of 2 bores (2026-08-31h)"
              "underpass under aeroway -1230"
rim_ll        9 vertices, 40.4612929..40.4620764, -3.5445451..-3.5448103
```

The sibling `tunnel:-5821+-5820@0` (south mouth, `mouth_ll` 40.460868,−3.5446729,
`top_s` 108.0) is the emitted ramp −10862.

**The ways that state it.** `OSM_data/+40-010/+40-004/+40-004_airport_small_roads.osm.bz2`
ways **−5821** (62 nodes) and **−5820** (64 nodes), both `{"highway":"service","lanes":"2"}`
— **no `tunnel` tag**; the crossing is minted by §34 (5) from
`+40-004_airports.osm.bz2` way **−1230** `{"aeroway":"taxiway","bridge":"yes","layer":"1","ref":"F-6"}`
(2 nodes, 40.4611577,−3.5449608 → 40.4611609,−3.5443945, 48.0 m).

**Emitted geometry** (way −10863, shapeID 916, `role=tunnel_ramp ref=tunnel_ramp`,
11 nodes, 1,532.5 m²; ring extent 84.72 m N–S × 17.9 m E–W):

```
-18617 40.461310980 -3.544781021 alt=571.52   <- south end, AT the mouth
-18616 40.461310950 -3.544568798 alt=571.52
-18615 40.461635148 -3.544568720 alt=571.0
-18614 40.461959345 -3.544568641 alt=570.5
-18613 40.462071914 -3.544574509 alt=570.0    <- north end (the top)
...
```

**The mouth rule that placed the south end at 40.461311** — `planar/structure_underpass.py:166-277`:

* `underpass_bores` clips each road to a ribbon built from the **deck cell's own
  two kerbs per station** (`_deck_cell`, `structure_underpass.py:373-478`), **plus
  the cell's graded strip** (§34 (5) (b), `strip_half_width_m`, `structure_underpass.py:58-82`),
  **eroded** by `rim_off + grid` where `rim_off = wall_gap_m 0.6 + wall_band_width_m 1.0`
  (`law/structures.toml:9,16`) → the shipped note's **2.1 m**.
* The shipped run's own note (`report.json /planar/structures/underpasses[0]`):
  `underpass taxiway -1230 (layer 1, deck half-width 7.7 m, clip the deck CELL's
  footprint across the axis PLUS its graded strip (§34 (5) (b)) eroded by 2.1 m
  (2186 m2 over 50 station(s), §34 (5) (a)), cell 50 read / 0 refused over 4x
  carriageway): 2 road(s) bored`.
* **Measured on the shipped patch**: the deck cell at the bore's longitude is
  `junction:pav157` (way −10277, shapeID 271, `code_letter=E`); its **north kerb is
  0.09–0.22 m from way −1230's axis** and its south kerb 14.9–16.4 m. Code-E taxi
  zone-2 half width = **19.0 m** (`law/zones.toml:29`). So the northern clip lands
  at 0.15 + 19.0 − 2.1 = **17.05 m** north of the centreline → lat
  40.4611590 + 17.05/111320 = **40.4613122**; the record's mouth is **40.4613118**.
  The ramp ring's south edge sits exactly on it (40.461310980) and the rim stands
  2.00 m beyond (rim south edge 40.4612930).
* `ramp_grade`: `design_grade = 0.08` = `[tunnel] ramp_max_grade = 0.080`
  (`law/structures.toml:12`, the role cap `common.roles.tunnel_ramp`).

**One unexplained asymmetry, reported not resolved.** The record's `mouth_z` is
**564.9** for BOTH mouths, and the south ramp −10862 honours it
(nodes 564.9 → 567.28 → 569.64 → 572.39 → 572.7, i.e. 7.9 %/8 % over 108 m).
The emitted **north** ramp −10863 never reaches it: its lowest node is **570.0**
(= `mouth_dem_z`) and its mouth node is **571.52**, i.e. 6.62 m ABOVE the record's
floor, running **−1.79 %** over 84.7 m. No `tunnel_trench` face is emitted between
the two mouths (correct for an underpass — the taxi cell `pav157` is the deck), but
the road surface therefore steps from 564.9 at the south mouth to 571.52 at the
north mouth. This is consistent with the owner's 1.0.336 observation that the north
side's "DEM is already low there" (`docs/RULINGS.md:6325`), i.e. the north "ramp" is
really a shallow cut into the taxiway's shoulder — the "hole in the taxiway".
I could not verify whether the shipped build's own structures record still says
564.9 (§6).

---

## 2. THE TAXIWAY: what shape 294 is, and why `apron`

### apt.dat says
`pav188` = the **189th parsed `110` pavement** (`airport/load.py:277-282`
mints `pav{p.index}`; `airport/apt_dat.py:363` numbers by parse order;
197 `110` rows, 197 parsed):

```
apt.dat:13317   110 37 0.25 0.0 plain.pol
```

* surface **37**, smoothness 0.25, orientation 0.0, description **`plain.pol`** —
  a draped-polygon name, **no taxiway name, no designator**. 70 nodes, one ring,
  54,432 m².
* Its shape: a NW blob plus a **44.5 m wide, ~570 m long east–west BAND**
  (south edge lat 40.46100–40.46104 from lon −3.53944 to −3.54546; north edge
  lat 40.46144 from lon −3.53941 to −3.54616; nodes 20–26 of the ring). That band
  is the wide pavement the owner is pointing at, and F-6 crosses it.
* **No `120` linear feature within 460 m** (nearest apt.dat line is 467.8 m away)
  and **no `1201/1202` taxi-route edge within 461 m** of either owner point —
  so neither a painted edge line nor the pack's routing network says anything here.

### what classify made of it
`python -m auto_patch_v2 explain LEMD --at 40.4614416,-3.5452585`:

```
cell 471: role=apron side=airside kind=apron ref=pav188 area=46,764 m2
  evidence: area_m2=59,364, n_taxi=2, shared_m=558, width_m=106,
            route_territory_frac=0.242, kind=apron,
            shoulder_beyond_band=1, shoulder_band_of=14R/32L,
            territory_frac=0.754, apron_remainder_m2=4,101, near_route=0,
            apron_evidence=taxi centreline touches the face
  centrelines: taxi ['taxi614/osm:-1230', 'taxi765/osm:-149']; 1206 -;
               OSM roads ['osm1132','osm1134','osm1135','osm1155']
```

The ladder, rung by rung, with the number each rung read:

| rung | site | number | verdict |
|---|---|---|---|
| corridor? | `classify/roles.py:1216-1219` | width = area/shared = 59,364/558 = **106 m** vs `corridor.max_width_m` **50.0** (`classify/rules.toml:19`) | no |
| tight junction? | `roles.py:1220-1222` | area **59,364 m²** vs `junction.max_area_m2` **2500.0** (`rules.toml:27`) | no |
| route territory? | `roles.py:1223-1229` | `route_territory_frac` **0.242** vs `junction.route_territory_min_fraction` **0.55** (`rules.toml:29`) | no → **kind = apron** (`roles.py:1231-1233`) |
| §43 (1) neck cut | `roles.py:409-413` | **no `neck_cut` / `neck_new_apron` mark on cell 471** in the `--roles` census (5 neck cells and 40 "apron beyond" cells at LEMD, none `pav188`) — the 44.5 m arm is under `neck_width_m` **45.0** (`rules.toml:35`) but it **dead-ends**, so there are not two wide lobes either side of it | not cut |
| §40 (2) apron-cover refusal | `roles.py:387-399` | not marked (kind was already apron) | — |
| 04z-1 taxi-name | `roles.py:435-447` | needs `named_src.taxi_name`; the source description is `'plain.pol'` — LEMD has **0** `taxi by name` cells | no |
| route-proximity cut | `roles.py:449-484` | split off the **junction** cell (way −10301, shapeID 295, 12,385 m², `near_route=1`) over the eastern 570 m where the two chains' 25 m territory reaches; the rest stayed apron with `near_route=0` | partial |
| 04u open default | `classify/open_default.py:32-51`, called at `roles.py:517-520` | `n_taxi=2 > 0` → `apron_evidence = "taxi centreline touches the face"` → **apron kept** (without it the cell would have become `parking_lot`/`groundside_pavement`) | **apron** |

### does a centreline run through pav188 at 40.4614416,−3.5452585?
**No.** The only two taxi chains touching the whole 46,764 m² cell are
`osm:-1230` (the bridge, lon −3.5449608…−3.5443945) and `osm:-149`
(F-6 east, lon −3.5443945…−3.5386238). **OSM's F-6 stops at lon −3.54496**;
the owner's point is at lon −3.54526, ~25 m further west, and the pack's band runs
another ~540 m west of that with no centreline of any kind (OSM or apt.dat 1202).

**The rule that would choose taxiway.** Three candidates, none of which fires today:
(a) a taxi centreline over the western arm (`_kind`, `roles.py:1204`) — OSM does not
map one; (b) §43 (1)'s neck (`roles.py:409-413`, `classify/neck.py`) — the arm is
45 m-ish but has only ONE wide lobe; (c) 04z-1's taxi name (`roles.py:435-447`) —
the pack's description is `plain.pol`. The cheapest true statement is (b) generalised:
*a narrow arm of an apron cell that leaves one wide lobe and dead-ends is still a
taxiway* — i.e. admit a single-lobe neck.

---

## 3. THE RAMP'S END vs THE PAVEMENT

### does the ramp lie inside pav188?
**No overlap — but it notches it.** `osm_site.py --relate` at the site:

```
-10863 (tunnel_ramp, 1,532.54 m2) vs -11018 (structure_rim:tunnel_wall, 1,913.95 m2)
        overlap 1,530.29 m2
-10300 (apron:pav188, 46,440.11 m2) vs -11018   overlap 0.0 m2  shared_edge 55.05 m
        (no -10863 / -10300 pair at all: overlap 0.000 m2)
```

The apron way was **cut around the rim**: `pav188`'s emitted ring dives from
lat 40.4614415 (its own north edge) south down the rim's east side to
40.4612929, across the rim's foot, and back up the west side to 40.4614416 —
a **22.0 m wide × 16.5 m deep slot, ≈324 m² of pavement removed**
(classify cell 471 = 46,764 m²; emitted apron way = 46,440 m²). The **source**
apt.dat `pav188` contains the ramp's south node 14.48 m inside its own boundary,
so the pack authored continuous pavement there.

### how much would the owner's point shorten it?
* owner's end **40.4613855,−3.5447716** vs the ramp's south-end node
  **40.461310980,−3.544781021**: **8.331 m** apart; the owner's point is
  **0.796 m** off the ramp's own (west) edge, **2.794 m** from `pav188`'s
  emitted boundary (the current node is **1.999 m** from it), inside both the ramp
  ring and the rim, **25.22 m** north of way −1230's centreline and **6.19 m**
  south of apt.dat `pav188`'s authored north edge (lat 40.4614411).
  It is **0.22 m** in latitude from the north edge of `pav188`'s *junction* cell
  (way −10301's north boundary, lat 40.4613875) — the only law-shaped line
  anywhere near it, and that line is 32 m east.
* **Shortening**: the run from the mouth to the top is `top_s` **84.0 m**; ending
  8.331 m later leaves **75.67 m**. Keeping the record's climb (564.9 → 564.9 +
  0.08×84 = 571.62, a rise of 6.72 m) over 75.67 m needs **8.88 %**, over the
  `[tunnel] ramp_max_grade` **8.0 %** cap (`law/structures.toml:12`) — so a pure
  truncation is unlawful; the §34 (8)-AMENDED shape (move the mouth, lengthen the
  covered trench by 8.33 m, keep the cap, carry the top north with it) is the
  lawful form.
* **The emitted shape's own numbers**: z interpolates to **571.40** at the owner's
  point; from there to the top's 570.0 over the remaining 76.4 m is **−1.83 %**
  (today's ring is −1.79 % over 84.7 m). i.e. truncating the *emitted* ramp costs
  nothing in grade — the emitted north ramp is nowhere near the cap (see §1's
  unexplained asymmetry).

### which law places a mouth relative to airside pavement
1. **§34 (5) (a) + (b)** — `planar/structure_underpass.py:166-277`. This is the rule
   that placed 40.4613118, and its comment says so in as many words:
   *"THE MOUTH STANDS INSIDE THE DECK (spec §34 (5) as amended, RULINGS 2026-09-13ai):
   the clip ribbon is the deck's own half-width LESS the rim stand-off and one
   identity step, so the corridor's end cap — the rim — lands ON the taxi cell"*
   (`structure_underpass.py:222-228`).
2. **§34 (12) (3)** — *a corridor never cuts airside pavement* — `structure_service.py:247-288`,
   armed for OSM bores at `structures.py:580-583` and applied in the truncation loop
   at `structures.py:596-628`. `airside_cut_roles` (`structure_service.py:224-244`)
   **does include `apron`** (every airside value role bar `building`), so the role is
   not the gate. The gate is:
   ```python
   if any(p.dwithin(q, grid) for q in mouth_pts):
       continue                      # the portal's own pavement
   ```
   (`structure_service.py:283-284`) — the mouth stands *inside* `pav188`, so `pav188`
   is struck from the stop list as "the portal's own pavement". `pav157` is struck too,
   as this corridor's own deck (`structure_service.py:285-286`). And the loop only
   ever drops the **last** station (`structures.py:626-627`) — it shortens the ramp's
   **top**, never its mouth end; here the top (40.462072) points away from the taxiway.
3. **§34 (8) / (8) AMENDED / §34 (9)** — **do not apply.** `stop_and_steepen` is
   called only under `if c is not None and g.kind == WALL_KIND` (`structures.py:618-620`,
   implementation `planar/wall_corridor_ramps.py:314`). An OSM bore is neither.

### would a `taxiway` role on pav188 already move the mouth?
**No.** Three independent reasons, all measured:
1. The mouth is governed by **`pav157`**, not `pav188`: `_deck_cell` reads the cell
   that *contains each axis station*, and 3 of the 5 stations I probed (25/50/75/100 %
   of way −1230) stand in `junction:pav157`; only the 0 % station stands in `pav188`.
   `pav157` is **already** `junction`, code E → the strip is already 19.0 m.
2. §34 (12) (3) already protects `apron` (`airside_cut_roles`); re-roling it to
   `junction` changes nothing, because the exclusion that frees it is the
   *portal's-own-pavement* clause, which is role-blind.
3. If anything it would move the mouth **further out**: `strip_half_width_m`
   (`structure_underpass.py:58-82`) returns the **lip, 3.0 m** (`law/zones.toml:14`)
   for a cell that is neither runway nor TAXI family, and would return the
   **default 12.5 m** (`law/zones.toml:29`, no code letter on that cell) for a taxi
   cell — widening the 0 % station's ribbon by 9.5 m.

Measured with the classify capture (`explain LEMD --at …`, two dry runs) and the
shipped patch; no replay was needed for (1)–(3). A `v2_solve_replay --from planar`
or a dry `planar --stage structures` arm would be needed to *confirm* the moved
mouth's coordinates for any candidate fix.

---

## 4. HISTORY — this is the third owner read of this underpass

| when | what the owner said | what landed |
|---|---|---|
| **2026-09-13i** (`RULINGS.md:3670`) | item 1: "no bore — the roads under taxiway bridge F-6 carry no `tunnel` tag; the DEM's 7.5 m cutting is unmodelled; the taxi surface bathtubs 2.66 m at 5.3 %" | §34 (5) A BRIDGE STATES THE CROSSING |
| **2026-09-13ai** (`RULINGS.md:3744`) | — | §34 (5) implemented: *"LEMD F-6 way −1230 … deck half-width 7.6 m off its taxi cell, both service roads bored, **mouths at 40.4610903 / 40.4612284, −3.54467**, floor 564.90"*. The north mouth then stood **7.7 m** north of the centreline. |
| **2026-09-13ax** (`RULINGS.md:3795`) | — | §34 (5) ARMED and merged |
| **2026-09-14bl item 1** (`RULINGS.md:6325`) | *"There's a tunnel mouth here: 40.4614416, −3.5447633 that we are **not** emitting, but looks correct **because the DEM is already low there**… However the otherside where we do create a tunnel ramp **it's cutting deep into the taxiway and also distorting it**. The mouth should stop back about here: 40.4609913, −3.5445335"* | §34 (5) (a): the clip becomes the deck **cell's** footprint across the axis (`RULINGS.md:6455`) |
| **2026-09-14bt** (`RULINGS.md:6600-6630`) | — | *"F-6: the ramp's **north extent back 7.5 m** (rim 40.4611264 → 40.4610588), the taxiway `pav157` never cut in either arm"*; and the caveat that is now the whole story: *"the OSM centreline sits **0.25 m from the north kerb** so the eroded cell still reaches ~14 m south"* |
| **2026-09-15e item 7** (`RULINGS.md:6941`) | *"the lateral slope and **hole in the taxiway** here: 40.4611623, −3.5444804. It's better, but still not fixed."* (14bl item 1 residual) | **§34 (5) (b)** ruled (`RULINGS.md` 2026-09-15h): *"the trench (face 993, 572.42) opens 12.8–15.5 m from the kerb (577.80) inside zone 1 — a 5.38 m unbanked face; junction pav157 shares the runway's nodes → RULED §34 (5) (b)"* — the covered extent gains the **graded strip** |
| **now, 1.0.348 item 2** | *"The tunnel ramp here: 40.461311,−3.544781 must stop short of the taxiway"* | — |

**The ramp was NOT identical at 1.0.336.** The north mouth moved
**40.4612284 → 40.4613118 = +9.3 m further north** between 13ai and today, and the
cause is §34 (5) (b): adding the code-E 19.0 m strip to a cell whose north kerb is
0.15 m from the centreline pushes the north mouth 19 m past the taxiway's north
edge — out of `pav157` (which the 14bt bar protected) and into `pav188`, which no
bar named. The cure for 15e item 7 is the cause of 17q item 2.

---

## 5. THE SMALLEST FIX SHAPES (described, not implemented)

### (a) classification — `pav188` → taxiway
* **Rule**: extend **§43 (1)** (`classify/neck.py`, offered at `classify/roles.py:409-413`,
  `classify/rules.toml:35` `neck_width_m = 45.0`) so a sub-`neck_width_m` arm that
  leaves ONE wide lobe and **dead-ends** is still cut out of the apron and kinded by
  the corridor ladder. `pav188`'s band reads 44.5 m authored width — inside the knob.
  Alternative and narrower: a rung that re-kinds an apron cell **collinear with and
  continuous from a taxi-kinded neighbour** (`pav188`'s own junction cell −10301 is
  end-to-end with the arm).
* **Blast radius** (`tools/blast.py Ortho4XP/src/auto_patch_v2/classify/roles.py`):
  imported by **84 files** (13 src, 70 tests, 1 tool); hot symbols `Cell` (70),
  `Classification` (69), `TAXI_FAMILY` (4); 70 direct test importers plus 16 via
  conftest fixtures; co-changed with `test_classify.py` (80 %) and `rules.toml` (79 %).
  **This is the widest of the three shapes.**
* **What else flips — NOT COUNTED.** A role change re-prices the whole airside/
  groundside split (taxi law carries more slope than apron law — the owner's own
  words in `rules.toml:35`). The counting instrument is the **dry classify arm**, no
  tile build: `PYTHONPATH=src venv/bin/python -m auto_patch_v2 explain LEMD --roles`
  before/after (~4 min per arm; it prints cells + area per role and every re-kinded
  cell with its evidence), and `tools/classify_report.py --from-json` for the
  legacy-vs-scorer confusion matrix. Today's LEMD baseline from that instrument:
  apron 73 cells / 3,361,427 m²; junction 76 / 953,642; cross_connector 186 /
  1,510,808; 5 §43 neck cells and 40 "apron beyond" cells; 0 taxi-by-name; 0 open-default.
* **It does not fix item 2** (see §3's three reasons).

### (b) the mouth rule — end the climb N m short of ANY airside pavement
This is the one that actually fixes item 2. Two sub-shapes:
1. **Narrow §34 (5) (b)'s strip to the side the pavement is on.** The strip term was
   ruled to stop a trench opening *inside zone 1* (15h item 7). Where the deck cell's
   kerb on one side is under a metre from the centreline, the strip on that side is
   added to *someone else's* pavement. Site: `structure_underpass.strip_half_width_m`
   (`structure_underpass.py:58-82`) / `_deck_cell`'s `offs.append((s, best[1] + strip,
   best[2] + strip))` (`structure_underpass.py:472-473`). Smallest form: **clip each
   station's offset at the first airside cell boundary beyond the deck cell's own
   kerb** — the strip covers ground, not a neighbour's pavement.
2. **Withdraw the portal's-own-pavement exclusion when the mouth is not at the
   pavement's edge.** `structure_service.py:283-284` exempts the whole cell the mouth
   stands in. §34 (12) (3)'s own reasoning ("a corridor whose mouth stands on an
   apron does not cross it, it ENDS in it") holds for a mouth *at* a pavement's edge;
   here the mouth is 14.5 m inside a 44.5 m band and the rim has notched 324 m² out
   of it. Smallest form: exempt only the part of the cell **within the rim's own
   footprint plus the stand-off**, so the truncation loop still stops the ramp short
   of the rest.
* Amends **§34 (5) (b)** (Fable 2026-09-15; RULINGS 2026-09-15h) and/or
  **§34 (12) (3) as amended** (RULINGS 2026-09-15w).
* **Blast radius**: `structure_underpass.py` — 7 importers (3 src: `channel.py`,
  `channel_claims.py`, `structures.py`; 4 tests: `test_v2channel.py`,
  `test_v2lemdstruct.py`, `test_v2rampwalk.py`, `test_harness.py`) + 16 conftest-fixture
  tests. `structure_service.py` — 4 importers (`structure_approach.py`, `structures.py`;
  tests `test_v2objcut.py`, `test_v2vmmcshore.py`) + 17 fixture tests; co-changes with
  `structures.py` 89 %. **Much narrower than (a).**
* **Fastest replay**: a dry `python -m auto_patch_v2 planar LEMD --stage structures`
  pair (base arm via `git archive`, lane arm on the branch) — ~180–195 s per arm on
  this Mac (the two v2wallface arms at `/tmp/harness/v2wallface/{base,lane}_LEMD/`
  took 193 s and 183 s). Read `tunnels[]` for `tunnel:-5821+-5820@0/@1`'s `mouth_ll`
  and `rim_ll`, and the `underpasses[]` note's ribbon area (today 2,186 m² / 50
  stations). Then `tools/osm_site.py --relate` on the emitted patch for the notch,
  and `--deck-witness structures.json` for the deck table. KCLT taxiway U (−1560) and
  VMMC are the standing controls for any §34 (5)/(12) change.
* **Bars I would write**: north mouth within 1 m of 40.4613855,−3.5447716; the
  `pav188` notch area 324 m² → ≤ ~160 m² (or 0); `pav157` still never cut; the south
  mouth unchanged at 40.460868; KCLT taxiway U's two mouths byte-identical;
  the F-6 ramp profile monotone and under the 8 % cap.

### (c) an owner-authored override
A per-site `mouth_ll` / `covered_end` override keyed by tunnel id. There is no such
table today (I found no site-keyed override register for tunnels; `frames.py` and
`refresh_ledger.jsonl` are the only site registries). It would amend §34 (5) with a
new authored-exception clause, and the tool-discipline ruling (`7e90032`) means it
would need an INDEX row and a twin. **I would not recommend it**: the mechanism in
(b) is fully attributed and general, and the site has already been ruled on three times.

---

## 6. Sources I could NOT verify

1. **The shipped build's own structures record.** `LEMD.report.json` carries only
   *counts* under `/planar/structures` (`tunnels 47`, `object_corridors 1`,
   `underpasses[1]`); the per-tunnel rows (`mouth_z`, `top_s`, `design_grade`,
   `rim_ll`) come from `/tmp/harness/v2wallface/base_LEMD/structures.json`, a dry arm
   on main **`31b7ad1b`** at 19:20, **15 minutes before** the 19:35 tile build, and
   I could not establish which sha the 1.0.348 engine was frozen at. The rim ring
   matches the emitted rim −11018 vertex for vertex and the mouth matches the emitted
   ramp's south edge to 0.4 mm, so the identification is safe; the **z values**
   (`mouth_z 564.9`) are the part I am quoting across that gap.
2. **Why the emitted north ramp stands 6.62 m above the record's `mouth_z`** (§1).
   Resolving it needs a `v2_solve_replay --why-vertex` / `--from planar` arm; I ran
   no replay.
3. **The owner's 40.4613855 has no law-shaped derivation I could find.** It is
   0.796 m off the ramp's own west edge, 8.331 m north of the current mouth and
   6.19 m south of the authored pavement's north edge. Nearest law line: the
   `pav188` *junction* cell's north boundary, same latitude to 0.22 m but 32 m east.
   I read it as a sim-read judgement ("about 8 m back"), not a derived point.
4. **The LEMD-wide (and cross-airport) collateral of fix (a)** — not counted; needs
   the dry classify arms named above.
5. **`surface 37`** in the apt.dat row is not a standard X-Plane surface code
   (1–15); I did not chase what the Aerosoft pack means by it, and nothing in this
   report depends on it.
6. **No registered LEMD classify capture exists** (`frames.py list LEMD` returns
   patch / mesh / capture / rebake / graded rows only, and every pre-2026-09-17 path
   is `[MISSING]`), so §2's verdicts come from two live `explain` runs rather than a
   registered frame. I did not register a frame (read-only lane).
