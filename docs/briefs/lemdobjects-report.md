# Scout `lemdobjects` — LEMD 1.0.348, items 4 (T4 components below the apron) and 5 (Bridge2 edge walls)

Read-only. No build, no edit, no worktree. All numbers read verbatim out of the
1.0.348 products written 2026-09-17 19:35–19:37 (engine `1.50.1794`, law digest
`b2ebc2a4…`):
`/Users/noah/XPTerrainBuilderData/Patches/+40-010/+40-004/{LEMD.graded.json,
o4_v2_placement_LEMD.json, o4_v2_rebake_LEMD.json}` and the PRISTINE DSF dump
`/Users/noah/XPTerrainBuilderData/Airport_mod_cache/Aerosoft - LEMD Madrid - 1 - Airport/+40-004.dsf.anchor_bak.747ee558.text`.
Session tree at `91c9adde` (brief base `ab879322`).

## THE HEADLINE

**Item 4 is ONE mechanism with ONE number.** 45 bodies of Terminal 4 are bound
into footprint unit `fu:25:983@cluster_pad` and every one of them is seated with
its zero plane at **614.77 m**, the *single lowest vertex* of pad `building45`,
which lies at **40.4914444, −3.5929523 — 590 m south-west of the owner's point**.
The graded airside apron `pav12` under the owner's three coordinates runs
**615.16 … 616.62**. The unit's own anchor reasons already state the error per
body: *"own ground +0.42 … +2.24 m"* — **all 45 positive**, median **+1.26 m**
(`ground_off`, the §16a mis-anchor read over each body's own feet: 0.88 / 1.68 /
2.34 m min/median/max). Nothing in the law brings the unit back up to the apron.

**Item 5 is the absence of a law.** `Bridge2.obj` has `deck_kind = ""`,
`deck_top_y = None`, `plate_y = None` (`o4_v2_rebake_LEMD.json`, unit 7 member 0).
LEMD's whole pack has `deck_members = 0`, `signature_decks = 0`, `deck_families = 0`,
`bridge_deck_footprints = 0`. §16e's datum branch
(`anchor_rule.py:658`, `datum_of` `anchor_rule.py:324`) therefore returns `None`
and never runs. The bridge deck at this site is an **engine-emitted design-surface
face**, `service_road bridge_deck:-6288` (shape 803, groundside, z 605.60..609.47) —
and **the object stage reads only two graded regions**: `building` faces (pads)
and `structure_rim` breaklines (`placement_read.py:51-52`). There is **no consumer
of a `bridge_deck:*` face anywhere in `src/auto_patch_v2/airport/`**. So the
parapets seat from the terrain under their own footprints, which at this crossing
ranges from the trench floor 599.30 to the ramp 611.5 — three seats for one wall.

---

## Q1 — ITEM 4 CENSUS: submersion per body

Method: a body's world zero plane is `surface_z − y_zero` (the rule sets
`y_zero = best_foot_surface − datum`, `footprint_unit.py:707`), so that is the
plane the model is drawn from. "Submersion" = graded design-surface z over the
body's own `foot_boxes` **minus** that plane (positive = body below ground).
Graded z by barycentric interpolation inside the containing face, 7×7 samples per
foot box. Scratchpad reader:
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/03d6658a-30ff-4e68-8bf7-8c84d900b14f/scratchpad/sub2.py`.

### 40.4967429, −3.5912949 (r = 15 m; graded face = `apron pav12`, airside, shape 141, 615.16..616.62, med 615.97, n=146)

| sub(med) | sub(max) | body zero | graded [min,med,max] | class | unit | body | seat reason (verbatim) |
|---|---|---|---|---|---|---|---|
| **+1.66** | +1.68 | 614.77 | 616.41/616.43/616.45 | other | – | `…green-LEMD20.obj` b2 | `carried by …green-KIOSK__b2… (rests on it …)` |
| **+1.66** | +1.68 | 614.77 | 616.41/616.43/616.45 | skirted | fu:25:983 | `…green-KIOSK.obj` b2 | `§16g unit fu:25:983@cluster_pad of 8 member(s) on pad building45 at 614.77 (own ground +2.19 m)` |
| **+1.63** | +1.66 | 614.77 | 616.37/616.40/616.43 | other | fu:25:983 | `…yellow-LEMD14.obj` b3 | `§16g unit … at 614.77 (own ground +1.51 m)` |
| **+1.52** | +1.61 | 614.77 | 616.19/616.29/616.38 | other | – | `…green-LEMD16.obj` b0 | `carried by …yellow-LEMD13__b5… (§16c (7) bound by contact into the unit's rigid cluster)` |
| **+1.30** | +1.66 | 614.77 | 615.81/616.07/616.43 | skirted | fu:25:983 | `…yellow-LEMD13.obj` b5 | `§16g unit … at 614.77 (own ground +1.51 m)` |
| **+1.11** | +1.31 | 614.77 | 615.38/615.88/616.08 | other | – | `Terminal4/…_48.obj` b4 | `carried by Terminal4/…_05__b3… (§16c (7) bound by contact …)` |
| +0.20 | +0.95 | 615.61 | 615.17/615.82/616.57 | other | – | `…Terminal4-LEMD01.obj` b1 | `carried by …green-STRT4__b3… (rests on it …)` |
| −0.51 | −0.42 | 616.79 | – | line_segment | – | `…green-LEMD17/18.obj` b17 | `carried by …green-TRIPU__b0… (nearest footed body of the unit (28 m))` |
| −0.91 | −0.41 | 616.79 | – | line_segment | – | `…green-LEMD15.obj` b20 | same carrier, 31 m |
| −1.49 | −0.01 | 616.26 | 609.24/614.77/616.25 | other | – | `AESlite-LEMD-VOR-25-T4-1.obj` b0 | `footless_own_ground: no carrier the law accepts — the ground under its own footprint, authored y kept` |
| −1.59 | −0.06 | 616.27 | 608.70/614.68/616.21 | other | – | `AESlite-LEMD-VOR-25-T4-2.obj` b0 | same |

### 40.4967396, −3.5899271 (r = 15 m, 4 bodies)

| **+1.29** | +1.40 | 614.77 | 615.75/616.06/616.17 | other | – | `…green-LEMD20.obj` b3 | carried by `…green-KIOSK__b3…` |
| **+1.21** | +1.40 | 614.77 | 615.75/615.98/616.17 | skirted | fu:25:983 | `…green-KIOSK.obj` b3 | `§16g unit … at 614.77 (own ground +1.45 m)` |
| −1.49/−1.59 | | 616.26/616.27 | | other | – | the two `AESlite-…T4-1/2` | `footless_own_ground …` |

### 40.4964709, −3.5910008 (r = 15 m, 28 bodies) — the spread is 2.37 m inside ONE building

Submerged (all at zero plane 614.77 unless noted):
`…yellow-LEMD13` b0 **+1.53** (unit, "own ground +1.00"), `…green-LEMD16` b0 **+1.52**
(carried), `…yellow-LEMD4` b0 **+1.31** (carried), `…yellow-LEMD13` b5 **+1.30** (unit),
`Terminal4/…_05` b9 **+1.27** (unit, "own ground +1.97"), `Terminal4/…_48` b4 **+1.11**,
`…yellow-LEMD11` b1 **+1.06**, `…yellow-LEMD10` b0 **+1.04**, `…Terminal4-LEMD01` b1 +0.20
(zero 615.61).

Floating on the same footprint: `Terminal4/…_56.obj` b0 **−0.95** (zero 616.96,
`surface at the body's zero`), `Terminal4/…_05.obj` b5 **−1.12** (zero 616.96,
`surface at the body's zero`), `…yellow-LEMD19.obj` b8 **−1.10** (zero 616.97,
`median foot: every foot on rolled-on pavement (§17, motion; terrain spread 2.08 m)`),
`…green-T4BJO.obj` b7 **−1.29** (zero 617.14, `line segment 3/3: mid-foot`),
`…green-TRIPU.obj` b0 −0.52, `…yellow-LEMD21.obj` b0 −0.63 (`footless_own_ground`),
`D066-D0066.obj` b0 −0.22 (`footless_own_ground`).

**Note the second disease at this point:** `Terminal4/LEMD_OBJ-Airport_Terminal4_05.obj`
bodies b0–b4 and b9 are IN the unit at 614.77, while **b5 of the same resource** is
NOT (`unit_of = None`, `surface at the body's zero`) at 616.96 — the same file,
**2.19 m apart**.

### Which are "the owner's components seated too low"

**Every body whose zero plane is 614.77** — the 45 members of
`fu:25:983@cluster_pad` plus the 19 further bodies carried by them
(`family_of = fu:25:983@cluster_pad` = 64 bodies in total). The rules:

| seat reason | rule | file:line |
|---|---|---|
| `§16g unit fu:25:983@cluster_pad of 8 member(s) on pad building45 at 614.77 (own ground +X m)` | §16g (1)/(2) plan-wide seat; the datum comes from `plan_unit_datums`, the low-side branch | `airport/footprint_unit.py:682` (`_seat`), reason string `:711`; datum `:528` / **`:589` `(min(p.z) if low_side else _median(list(p.z)))`** |
| `carried by … (rests on it / §16c (7) bound by contact into the unit's rigid cluster / nearest footed body of the unit (N m))` | §16c (7)–(9) — a carried body inherits its carrier's zero, so it inherits 614.77 | `airport/placement_carrier.py` (carrier search), reasons consumed in `placement_plan.py` |
| `footless_own_ground: no carrier the law accepts — the ground under its own footprint, authored y kept` | §16 (3) | `airport/placement_plan.py:296` (`OWN_GROUND`), `:299` `_own_ground_file`, reason `:324`; ground = median over `foot_boxes` (`placement_boxes.py:194` `ground_under`) |
| `surface at the body's zero` (the "skirted at its own zero" bodies) | generic rule, residual ≤ `split_tol_m` | `airport/anchor_rule.py:749-750` |
| `median foot: every foot on rolled-on pavement (§17, motion; terrain spread 2.08 m)` | §17 (2) | `airport/anchor_rule.py:736-740` |
| `line segment N/M: mid-foot` | §16d line stations | `airport/placement_cut.py:727` `segment_anchor`, reason `:740` |

`footless_own_ground` is **not** submerging anything here: the two `AESlite-…T4`
bodies the owner's first two coordinates land on read 616.26/616.27, i.e. 0.3 m
**above** the apron median. The skirted "body's zero" bodies are 0.95–1.12 m
**above** it. Only the pad-datum population is below.

## Q2 — ITEM 4 THE PAD

**What `building45` is.** FIVE emitted `building` faces share the ref
(`LEMD.graded.json`): face 160 (36.2 m², 615.58..615.64), face 161 (38.1 m²,
615.55..615.63), **face 162 (25,928.4 m², 614.77..615.72, median 615.17)**,
face 1035 (72,620.0 m², 615.18..615.50), face 1036 (4,416.6 m², 615.17..615.21).
Combined extent lat 40.4883369..40.4943438, lon −3.5954779..−3.5928177 — i.e. the
T4 **main terminal block, 250–600 m south-west of all three owner coordinates**.
156 ring vertices, z min 614.77 / median 615.22 / max 615.72.

**How 614.77 is derived.** `plan_unit_datums` picks the pad holding the plurality
of the unit's part-centres (`placement_family.py:521` `pad_plurality`) and then takes
**`min(p.z)`** — `footprint_unit.py:589`, armed by `[placement] pad_between_aprons`
(`law/structures.toml:790 = true`, schema `law/rebake_schema.py:195`) under
§16g (10) (9) (2) "THE BUILDING SEATS AT THE LOW SIDE". 614.77 is the **single
lowest vertex of face 162, at 40.4914444, −3.5929523**.

**Was it the pad losing to the apron?** No. The pad is welded to its aprons and
agrees with them: `building45` shares **19 ring vertices with `apron pav3`**
(614.77..615.57 — the 614.77 vertex IS one of them) and 8 with `apron pav12`
(615.37..615.72). §16g (10) (9) (2) is doing exactly what it says *at the pad*.
The defect is that **the unit is 1,216 m × 516 m** (bound-body bbox lat
40.48577188..40.49677192, lon −3.59543989..−3.58934052) while the pad it takes its
one plane from is 600 m of that span away, over a different apron 1.0–1.9 m higher.
The code comment at `footprint_unit.py:577-587` already names the deviation
("the law says the lowest SHARED-EDGE level and `PadRing` carries no per-vertex
airside flag at this layer … what is read is the pad plane's own LOW SIDE").

**A second, latent hazard at the same line.** `pad_plurality` keys its hit table
by `p.ref` but **stores the last `PadRing` matched** (`placement_family.py:543`;
the identical shape in `anchor_rule.py:266` for `pad_majority`). `building45` is
five separate `PadRing` objects, so `min(p.z)` is the low vertex of **whichever
face happened to be stored last**, not of the pad. Here it was face 162 (614.77);
face 1035 would have given 615.18 — a 0.41 m swing decided by iteration order.

**"Only 8 members".** `8 member(s)` is `len(mems)` = the count of distinct plan
**members** (resources), not bodies: `footprint_unit.py:712`. The eight are
`green-KIOSK`, `green-VRDCH`, `green-PKT4`, `yellow-LEMD12`, `yellow-LEMD13`,
`yellow-LEMD14`, `yellow-LEMD19`, `Terminal4/…_05`. They carry **45 bodies**
(`unit_of`), and 19 further bodies hang off them (`family_of` = 64). The rest of
Terminal 4 — `Terminal4_56`, `Terminal4_48`, `green-TRIPU`, `green-T4BJO`,
`green-STRT4`, `yellow-LEMD10/11/21`, `green-LEMD03/15/16/17/18/20/23` and
`Terminal4_05` **b5** — has `unit_of = None`, because `_bind_plan_wide` only seats
a candidate whose **pids name a plan-wide unit** and which has ground contacts in
that pass (`footprint_unit.py:596-679`); the rest keeps its §16c seat.

**Same class as HECA T3?** Related, not identical — cite scout `hecat3split`
(`docs/briefs/hecat3split.md`), do not redo it. At HECA the terminal's 99 bodies
are **outside** any unit (89 `None` carried bodies + six separately seated shells)
and spread over nine datums 97.54..100.16 = 2.6 m. At LEMD T4 the unit **did**
form, and the failure is that its ONE datum is 1.0–1.9 m too low across a 1,216 m
span **and** the rest of the terminal (`Terminal4_56` at 616.96, `Terminal4_05` b5
at 616.96, `T4BJO` b7 at 617.14) stayed outside it — a 2.37 m spread inside one
building at 40.4964709,−3.5910008. So LEMD shows **both** halves: HECA's
"terminal never became one unit" *and* a new one, "the unit that did form took a
plane from 600 m away".

## Q3 — ITEM 4, WHAT THE PACK AUTHORED

The pristine dump `+40-004.dsf.anchor_bak.747ee558.text` holds **3,021 `OBJECT`
rows, 0 `OBJECT_MSL`, 0 `OBJECT_AGL`** (415 `OBJECT_DEF`). The plan agrees:
`counts.conversions_msl = 0`, `conversions_agl = 0`, `msl_seats = 0`
(`o4_v2_placement_LEMD.json` `counts`).

**Every Terminal 4 resource is authored on ONE shared row** —
`lon = −3.564788376, lat = 40.492764363, heading 0.000, no elevation` — including
`Terminal4/LEMD_OBJ-Airport_Terminal4_05.obj`, `…_56.obj`,
`…Terminal4_yellow-LEMD12/13/14/19.obj`, `…green-KIOSK/PKT4/VRDCH/LEMD50/LEMD65.obj`.
That is the shared-datum pack class (memory `shared-datum-pack-authoring`, LSGG
class): the pack authors **no elevation at all**; all geometry rides authored
offsets inside the `.obj`, and 100 % of the height in the sim is the engine's.
`AESlite-LEMD-VOR-25-T4-1/2.obj` and `D066-D0066.obj` are separate plain `OBJECT`
rows near the sites (e.g. `D066-D0066.obj` at 40.4965152,−3.5909018).

**The Aerosoft basin ground truth is irrelevant here — stated explicitly.** The
614.77 datum is the min vertex of an emitted `building` pad ring at
40.4914444,−3.5929523; it is not derived from the T4 pit. The only members
carrying a plate in this build are `objects/Bridges/Bridge4/Bridge4.obj`
(`plate_y = 2.016`, 72 stations) and `objects/LEMD_OBJ-Ground-FSX-LEMD37.obj`
(`plate_y = −7.048`, 113 stations) — `plate_members = 2`, `plate_objects = 2`.
Nothing in the T4 unit's datum path touches the basin floor 587.75 or G = 596.682.

## Q4 — ITEM 5, THE WALL

**Authored:** `objects/Bridges/Bridge2/Bridge2.obj`, ONE plain `OBJECT` row,
`lon = −3.581320096, lat = 40.483770600, heading 0.000, no elevation`
(pristine dump; plan `placement.index = 2938`).
`objects/LEMD_OBJ-Airport_Terminal4_green-LEMD50.obj` is on the T4 shared row
(−3.564788376, 40.492764363, hdg 0). `…green-LEMDzaun.obj` likewise.
No MSL, no AGL, no authored elevation anywhere.

**The deck.** `LEMD.graded.json` face 803, `service_road bridge_deck:-6288`,
groundside, 15 vertices, lat 40.4835045..40.483743, lon −3.5808891..−3.5798808,
z 605.60..609.47. **Both owner coordinates are ring vertices of it**:
40.483716,−3.5803761 → **606.98** (north edge) and 40.4835314,−3.5803938 → **606.19**
(south edge). They are 20.4 m apart — the parapet pair span RULINGS 2026-09-15ax
records as `-6288` "centred on Bridge2's pair (span 20.6 vs inner 20.37 m)".

**Bridge2 is five bodies out of three components — the slice is real and it is
the ELEVATED/FOOTED split, not the line-station cut:**

| body | comp | feet | class | zero plane | vs deck at that station | seat reason (verbatim) |
|---|---|---|---|---|---|---|
| b0 | 0 | 50 | line_segment | **611.52** | **+4.54 m over 606.98** | `line segment 1/2: mid-foot` |
| b2 | **0** | 0 | line_segment | **605.96** | −1.02 m under 606.98 | `footless_own_ground: no carrier the law accepts — the ground under its own footprint, authored y kept` |
| b1 | 2 | 4 | line_segment | 599.29 | −7.69 m | `low-side foot (no point within 0.3 m of the body's zero plane: terrain spread 7.34 m)` |
| b3 | 1 | 0 | line_segment | **599.33** | **−6.86 m under 606.19** | `footless_own_ground: …` |
| b4 | **1** | 0 | line_segment | **599.31** | **−6.88 m under 606.19** | `footless_own_ground: …` |
| `…green-LEMD50.obj` b0 | – | 0 | line_segment | 606.22 | +0.03 m | `footless_own_ground: …` |
| `…green-LEMD50.obj` b1 | – | 0 | line_segment | 599.63 | (off the deck) | `footless_own_ground: …` |
| `…green-LEMDzaun.obj` b35 | – | 60 | line_segment | 609.23 | (box 40.4837440..40.4846043; contains neither owner point) | `line segment 3/3: mid-foot` |

Plan boxes (`o4_v2_placement_LEMD.json`): b0 lat 40.4836834..40.4837886 (11.6 × 125.5 m,
**contains the north point**); b2 lat 40.4834989..40.4837721 (30.2 × 137.1 m,
**contains BOTH points**); b3 lat 40.4834584..40.4835593 (11.2 × 99.7 m, south point);
b4 lat 40.4834876..40.4835593 (7.9 × 84.5 m, south point); b1 lat 40.4837272..40.4842653
(neither).

So the owner's "sliced" north wall is **component 0 split into a FOOTED piece
(b0, 50 feet, station-cut into 2, seated at its mid-foot on the tunnel ramp at
611.52) and an ELEVATED footless remainder (b2, seated on the median ground under
its own footprint at 605.96)** — the same connected component, 5.56 m apart, with
b0's 125 m box running west onto the `tunnel_ramp` face that climbs to 611. The
"sunk" south wall is **component 1 split into b3 + b4, both footless, both taking
the median ground under boxes that straddle the deck and the trench** — where the
graded `tunnel_ramp` face reads a flat **599.30**.

**Which law SHOULD seat it, and where each reason pre-empts §16e:**

- §16e's datum is read FIRST — `anchor_rule.py:658`
  (`if datum is not None and datum.stations:`), the datum built by `datum_of`
  (`anchor_rule.py:324`, plate branch `:359-364`, deck branch `:365-372`). For
  `Bridge2.obj` it returns `None`: `plate_y = None`, `deck_top_y = None`,
  `deck_datum_z = None`, `deck_kind = ""` (`o4_v2_rebake_LEMD.json` unit 7 member 0).
  §16e (3)'s name family cannot help either — a stem with no deck member falls back
  to §16c, and every `bridge_of` on these bodies is `None`.
- **`footless_own_ground` (b2, b3, b4, LEMD50 b0/b1) never reaches `anchor_of` at
  all.** It is a separate Body constructor, `placement_plan.py:299 _own_ground_file`,
  reason `:324`; the datum branch at `anchor_rule.py:658` is not on its path. This
  is the strongest pre-emption of the three.
- **`line segment N/M: mid-foot` (b0, LEMDzaun b35) likewise bypasses it**:
  `placement_cut.py:727 segment_anchor`, reason `:740` — its own `Anchor`, no datum
  argument.
- **`low-side foot (… terrain spread 7.34 m)` (b1) IS inside `anchor_of`**
  (`anchor_rule.py:742-747`) and is reached only because the datum was `None`.

The law that *should* apply does not exist: the object stage's only graded inputs
are `PAD_FACE_ROLE = "building"` and `RIM_BREAKLINE_KIND = "structure_rim"`
(`placement_read.py:51-52`, `pads_rims_from_graded_doc` `:55-78`). `grep bridge_deck
src/auto_patch_v2/airport/` returns only comments (`road_ramp.py:97/105/107`,
`deck_signature.py:155`) and the counter `placement_plan.py:541` — **no seat rule
reads an emitted deck face.** §16e is written entirely against the OBJECT's own
plate/deck-top geometry; §16d's line stations and §17's motion reading both read
the surface under the feet, which here is the trench.

## Q5 — ITEM 5, THE OTHER SIDE (the sunk wall)

b3 and b4 are **not** outside the deck polygon — their boxes straddle it. Sampling
9×9 over each plan box against the graded faces: b3 → `tunnel_ramp` 24 samples,
`bridge_deck:-6288` 19, none 38; b4 → `bridge_deck:-6288` 28, `tunnel_ramp` 19,
none 34. The `tunnel_ramp` face reads a flat **599.30** everywhere under them,
and `ground_under` takes the **MEDIAN** over the body's foot boxes
(`placement_boxes.py:194-202` — "one part hanging over a ditch is not the ground
the body stands on"). With roughly half the footprint over a 599.30 trench and
half over a 606–609 deck, the median lands on the trench side: 599.33 / 599.31.
A material fraction of both footprints (34–38 of 81 samples) stands over **no
graded face at all** — the raw DEM — so the design surface does not even cover
the wall there.

**The crest plate says nothing here.** `Bridge2.obj` has `plate_y = None`,
`plate_stations = []`, `plate_clearance_m = 0.0`. LEMD's only plate members are
`Bridge4.obj` (2.016) and `LEMD_OBJ-Ground-FSX-LEMD37.obj` (−7.048);
`plate_members = 2`. §16e (1) keys on `plate_y` (`anchor_rule.py:359`), so the
crest-plate branch is dead at this bridge.

## Q6 — HISTORY

**Not verifiable by measurement.** The shared patch dir holds exactly ONE
`o4_v2_placement_LEMD.json` (written 2026-09-17 19:37). No earlier placement
record survives anywhere under `/Users/noah/XPTerrainBuilder`, `/tmp/harness` or
the session scratchpads, and `tools/harness/frames.py list LEMD` has **no
object-stage LEMD capture that is not `[MISSING]`** — the only live LEMD frames
are lane `v2wallface`'s §47 `structures.json` dry pair at base main `31b7ad1b`
(`/tmp/harness/v2wallface/{base,lane}_LEMD/structures.json`), which is the
structure stage, not the object stage.

From RULINGS text (`Ortho4XP/docs/RULINGS.md`), the same bodies have been read
three times before and never re-seated:

- **2026-09-12d** (1.0.320, scout `v2lemd320`): "`Bridge2` (3 → 8, seam 11.7 m)" —
  the three-component split is at least that old.
- **2026-09-13r** (lane `v2wallplate`, MERGED `a16431b9`): "**`Bridge2.obj` /
  `LEMD50.obj` are DRAPED object plates (their top an offset over the solved
  ground, not a datum) — RULED: a draped deck plate rides the terrain deck the
  mesh gives it; the terrain deck is what must be right (item 9), no object
  re-seat.**" This is the standing ruling that says the parapets take no datum.
- **2026-09-15h** (1.0.340): "the pack's parapets Bridge2 b3/b4 (S, 0.92 m) and
  b0/b2 (N, 0.93 m), 25.6 m apart, are REFUSED as walls at the 1.5 m skirt gate
  (13r: draped plates)" — the **same body ids and the same N/S pairing** as the
  1.0.348 plan, so the five-body split and the b0-vs-b2 north slice are unchanged
  since at least 1.0.340.
- **2026-09-15ax / v2vmmcshore r7** moved the DECK: `-6288` is now "centred on
  Bridge2's pair (span 20.6 vs inner 20.37 m, 0.23 ≤ 0.3)" — the deck was ~8–9 m
  off the parapets at 1.0.340 (15h) and is centred now. **The deck was fixed; the
  walls were never re-seated**, which is why the owner sees the gap now.
- **2026-09-11ae** names `Bridge2` only as a nearby non-building at 40.4845169,
  −3.5828313 (item 2, UNVERIFIED).

I found **no earlier ruling on the T4 `fu:25:983` unit or on pad `building45`'s
low-side datum**; `building45` appears in the frames registry (v2padqp closing
build, base `2117c48c`) only as the pad that captures the owner's T4 garage at
40.4892214,−3.5944287 — i.e. at the pad's own location, where it reads correctly.

## Q7 — THE SMALLEST FIX SHAPES (described, NOT implemented)

**(A) Item 4, one line. The low-side datum must be read where the body stands, not
over the whole pad.** `footprint_unit.py:589` takes `min(p.z)` over the *entire*
ring of one pad face. The smallest correct-shaped change is to read the low side
**locally** — per seated body, the minimum over the pad ring vertices within some
reach of that body's own contacts (or, as the code comment at `:577-587` already
proposes, publish the pad's SHARED-EDGE vertex subset and take the lowest of
those). Amends **§16g (10) (9) (2)** (owner RULINGS 2026-09-14az) and touches
`footprint_unit.py` only. Blast (`tools/blast.py`): imported by 3 src
(`placement_plan.py`, `placement_record.py`, `placement_write.py`), 3 tests
(`test_v2connector.py`, `test_v2leafframe.py`, `test_v2objsplit.py`), 17 tests via
the conftest fixtures; co-change `test_v2connector.py` 83 %.

**(B) Item 4, the floor. A unit member never seats below the graded AIRSIDE
surface under its own footprint.** The evidence is already computed and printed
in every reason string — `own ground +X m` — and 45 of 45 are positive. A clamp
`zero_body = max(unit_datum, own_ground − ε)` at `footprint_unit.py:705-707`
(`best[3] - zero`) converts "the pad is king everywhere" into "the apron is king
where the body actually stands" (memory `airside-is-king`). This BREAKS the §16g
rigidity invariant (a unit would no longer be one plane), so it is an **owner
intent question**, not a mechanism: *does a 1,216 m footprint unit stay one rigid
plane when its members are 2 m apart in ground?* Amends **§16g (2)** and
**§16g (10) (11)**.

**(C) Item 4, the latent one. `pad_plurality` must fold all faces of a ref.**
`placement_family.py:543` (and the twin `anchor_rule.py:266`) stores the LAST
`PadRing` per ref; `building45` is five faces whose minima differ by 0.41 m. Fold
z over every face sharing the ref before `min`/`median`. Pure defect, no spec
amendment. Blast for `anchor_rule.py`: 21 importers (17 src), co-change
`test_v2objsplit.py` 87 %, `placement_plan.py` 73 % — this is the widest-radius
file of the four and should be touched last.

**(D) Item 5. A body whose footprint touches an emitted `service_road
bridge_deck:*` face takes that face's z at its own station as its datum, before
any foot, own-ground or line-station reading.** Structurally this means extending
`placement_read.pads_rims_from_graded_doc` (`:55-78`) to publish a third region —
DECK faces — and giving `datum_of` (`anchor_rule.py:324`) a branch that reads it,
so the datum is live at `anchor_rule.py:658` *and* so `_own_ground_file`
(`placement_plan.py:299`) and `segment_anchor` (`placement_cut.py:727`) consult it
before minting their own anchors. **This is a new region entering the object
stage, so under the consumer-census ruling (RULINGS 2026-08-30l) it starts at spec
time with a census of every pass that reads the graded faces, in ONE table.** It
also collides head-on with **RULINGS 2026-09-13r** ("no object re-seat" for
`Bridge2`/`LEMD50` as draped plates) — an **owner intent question**: 13r ruled the
DECK PLATE rides the terrain; it did not rule the PARAPETS. Amends **§16e** (the
datum is presently object-derived only) and needs 13r disambiguated.

**(E) Item 5, cheaper and narrower. An elevated footless remainder of a component
whose footed sibling exists takes the sibling's zero.** b2 is component 0's
elevated remainder and b0 is component 0's footed piece; they are 5.56 m apart.
`_own_ground_file` (`placement_plan.py:299`) is reached only after the carrier
search refuses (`carrier_refused_*` = 1,606 / 1,622 / 681 / 371 in this build's
counts); the narrow shape is to make the body's OWN component's footed sibling an
accepted carrier of last resort before §16 (3). Amends **§16 (3) / §16c (7)**.
Does not fix the sunk south wall (component 1 has no footed body at all), so it is
a partial fix only.

**Fastest object-stage replay to measure any of them.** `tools/obj8_split_report.py`
(INDEX row: "THE OBJ8 SPLIT, DRY-RUN … reads only a build's own two products — the
re-seat plan `<ICAO>.rebake.json` and the emitted design surface `<ICAO>.graded.json`
… never builds anything"), run against the shipped 1.0.348 pair
`/Users/noah/XPTerrainBuilderData/Patches/+40-010/+40-004/o4_v2_rebake_LEMD.json`
+ `…/LEMD.graded.json` — **no mesh, no tile**. The mesh-carrying alternative is
`tools/v2_rebake_replay.py plan PLAN.json MESH --graded G.json` (INDEX: "the
synthetic-first instrument for the post-mesh half", runs inside
`harness/shared_repo_guard`); the only LEMD mesh on disk is
`Ortho4XP/Tiles/zOrtho4XP_+40-004/Data+40-004.mesh` dated **2026-08-27**, which is
NOT matched to the 1.0.348 vector run — any arm using it must say so, and a
matched base arm must be cut with `git archive <sha> src | tar -x` (the
`--src`-at-a-live-checkout trap in the INDEX row). `tools/site_read.py` is the
per-coordinate reader used throughout this report.

**Base sha for a lane:** there is **no registered object-stage LEMD capture** to
replay against (`frames.py list LEMD`: every `capture` row is `[MISSING]`). A lane
must either register a fresh one or work from the shipped 1.0.348 products above,
whose provenance is engine `1.50.1794`, law digest
`b2ebc2a4f0b3a2002529206d206c4a87bdb0f8bd9d6fde1837a82a5d047488a8`.

## Q8 — SOURCES I COULD NOT VERIFY

1. **The 1.0.336 / 1.0.341 seats (Q6).** No archived `o4_v2_placement_LEMD.json`
   or `LEMD.graded.json` from those builds exists on disk, and every LEMD
   `capture`/`patch`/`graded`/`rebake` row in `tools/harness/frames.py list LEMD`
   older than 2026-09-17 is `[MISSING]`. The history in Q6 is read from RULINGS
   prose only; the body-id match (b0/b2 north, b3/b4 south) in RULINGS 2026-09-15h
   is the strongest evidence and is NOT a measurement I made.
2. **Why component 0's second line station is absent.** b0 reads `line segment
   1/2: mid-foot` but no sibling `2/2` exists in the plan for `Bridge2.obj`; b2 is
   the same component under `footless_own_ground`. I did not attribute how the
   segmentation count and the elevated split interact
   (`counts.line_bodies_segmented = 257`, `line_segments = 849`,
   `placements_coarsened = 120`, `groups_re_cut = 100`). Stated as observed, not
   explained.
3. **Which `building45` face `pad_plurality` actually stored.** Inferred from
   `min = 614.77` matching face 162 uniquely; the iteration order itself is not
   observable in the products.
4. **The graded z over a footprint is my own sampling**, not an engine product:
   7×7 (Q1) / 9×9 (Q5) samples per foot box, barycentric inside the containing
   face, fan-triangulated. It will differ slightly from the engine's own
   `surface()` on non-convex faces. The engine's own numbers (`surface_z`,
   `y_zero`, the `own ground +X m` in the reason strings, `ground_off`) are quoted
   verbatim and are the load-bearing ones.
5. **The `foot_boxes` granularity.** Bodies in this plan publish a single foot box
   each, while `_own_ground_file` samples `_pc.foot_boxes(part_boxes)` — the
   per-PART boxes. So my footprint samples are coarser than the rule's, which is
   why my box median for b4 (606.27) differs from its recorded `surface_z`
   (599.31). The recorded values are the truth; my medians are context.
6. **`tools/INDEX.md` does not exist** at the path CLAUDE.md names; the tool index
   is `Ortho4XP/tools/README.md` plus `tools/docq.py index`. Both were consulted.
   Reported as an instruction/source mismatch.
7. **No build, no census run** — per the brief. Every defect-count claim here is a
   read of one build's products, not a `harness/census.py` number.
