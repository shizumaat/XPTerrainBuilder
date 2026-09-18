# Scout `deckseat` — consumer census for §49 (a parapet takes the emitted DECK face as its datum)

Repo `/Users/noah/XPTerrainBuilder`, base main **`390c3282`**, read-only, no builds, no worktree.
Frame read: the shipped LEMD products in the shared data repo —
`/Users/noah/XPTerrainBuilderData/Patches/+40-010/+40-004/LEMD.graded.json` (2026-09-17 19:36),
`o4_v2_placement_LEMD.json` (19:37), `o4_v2_rebake_LEMD.json` (19:36); provenance engine
`1.50.1794`, law digest `b2ebc2a4…488a8`, `counts.bodies 2840 / files 2836 / kept 4 (all one_body) / anim 0`.
Corpus sweep over every `*.graded.json` + `o4_v2_placement_*.json` under
`/Users/noah/XPTerrainBuilderData/Patches`.

---

## THE HEADLINE (four facts that shape the spec)

1. **The region is tiny and it is LEMD's alone.** `bridge_deck:*` faces exist at 5 of 41 emitted
   airports — LEMD 7, KCLT 3, HEAZ 2, LGMG 1, KJQF 1 = **14 faces corpus-wide**; every one is role
   `service_road`, side `groundside`. **OTHH, VHHH, HECA, LGAV, KPHX (×2), KSDL, SPJC, NZQN, NZVL
   publish ZERO.** Of the airports that also have a placement product, only **LEMD has any body
   touching a deck face — 22 bodies** (KCLT 3 deck faces / **0** bodies).
2. **DECK ∩ PAD = ∅, DECK ∩ RIM = 8–9 nodes per deck.** Not one `building` pad ring's bbox even
   overlaps a deck face at LEMD, and no deck node is a pad node. Every deck face shares 8–9 of its
   14–39 ring nodes with `tunnel_wall@*` `structure_rim` breaklines — 13r's "the deck ring's
   vertices ARE the corridor rim's". So the whole `pads` consumer arm is **inert** and the whole
   `rims` arm **must ignore**.
3. **The surface already knows the deck's z. The rule reads the wrong statistic.** The deck's
   vertices are emitted vertices, so `surface(lat,lon)` inside the deck reads 605.6…609.5 today.
   `placement_boxes.ground_under` (`:194-202`) takes the **median** of the foot-box samples, and
   half of Bridge2 b3/b4's foot boxes sit on the `tunnel_ramp` face at a flat 599.30 — so the
   median lands on the trench. A DECK REGION is needed for **selection**, not for elevation.
4. **The datum is pre-empted three times, and that is measurable on main today.** `Bridge4.obj`
   is LEMD's ONLY member with a live crest-plate datum (`plate_y 2.016`, **72** `plate_stations`)
   and BOTH its bodies are written `datum=false` with reason `line segment 1/2 · 2/2: mid-foot`
   — **§10's station cut already throws §16e's datum away** (`placement_body.py:143-163` mints
   `segment_anchor` and `continue`s without ever calling `_ar.datum_of`). Whatever §49 does must
   pass that gate, `placement_carrier.is_elevated` and `placement_plan._own_ground_file`.

---

## Q1 — THE REGION CENSUS

### Where graded geometry enters the object stage (three doors, no more)

| # | site | what it reads | with a third DECK region |
|---|---|---|---|
| E1 | `airport/placement_read.pads_rims_from_graded_doc` **:55-78** (`PAD_FACE_ROLE="building"` :51, `RIM_BREAKLINE_KIND="structure_rim"` :52) | `d["vertices"]` (lat/lon/**z**), `d["faces"]` role==building → `PadRing(ref,ring,z)`, `d["breaklines"]` kind==structure_rim → `RimRing` | **MUST CONSULT — this is the derivation site.** File is 87 lines, room for a third reader. Callers: `engine_v2.py:678`, `obj8_split_report.py:219`, `v2_rebake_replay.py:291` (re-exported through `placement_plan.py:83-89`) |
| E2 | `airport/placement_boxes.graded_roles_from_doc` **:502-518** / `GradedRoles` **:380-500** | ALL faces + roles, senior by `precedence.toml` authority rank, 55 m grid | **MUST CONSULT.** It ALREADY resolves "which face is under this point" and already sees the deck as `service_road`. A second point-in-deck index would be the census-wrapper defect — §49 should ask `GradedRoles` for the face, not re-derive containment. (`roles_many` :464 returns ROLE only; the REF is not published — that is the one missing field.) |
| E3 | the SURFACE sampler — app: `engine_v2._placement_surface(mesh_sample)` (`engine_v2.py:661`); dry: `obj8_split_report.surface_from_graded` **:86** (Delaunay over graded vertices) | z at a point | **INERT.** The deck's z is already in it. §49 adds no sampler. |

`pipeline/` is **not a reader**: `pipeline/build.py:956` calls `emit.graded.graded_surface` — it
WRITES the document; `pipeline/publication.py`'s `pads` / `cluster_pads` (:251, :426) are PLANAR
faces, a different population. `pipeline/why.py:256` is a colour table. **INERT, all of it.**

### The consumers, one table

*(verdicts: **INERT** = the new region cannot reach it; **CONSULT** = §49 must edit or read it;
**IGNORE** = it must be explicitly told the deck is not its region, or it will mis-fire)*

| # | pass (file:line) | what it reads today | DECK verdict | why / measured |
|---|---|---|---|---|
| **PADS arm** |
| 1 | `anchor_rule._pad_of` :201 · `_pad_boxes` :223 · `pad_majority` :236-272 | pads | **INERT** | 0 pad bbox overlaps any LEMD deck face (measured) |
| 2 | `anchor_rule.anchor_for` **:697-701** (§16d (6) on-pad restriction) | pads | **CONSULT** | This is *the exact shape* §49's restriction takes: `cands = [c for c in cands if _inside(pad.ring, …)]`. Substitute the deck face and the existing low-side / median branches deliver Q6's fallback unchanged |
| 3 | `placement_body._whole_body` **:517** and **:383** → `anchor_rule.classify_body` :556 (`has_pad=`) | `_pad_of(pads,…)` | **IGNORE** | A deck is not a pad. Feeding it here would class a parapet `BUILDING` and change §6 class, file naming and every census population |
| 4 | `placement_family.pad_plurality` :521-548 · `cluster_plane` :614-642 · `_bind_cluster` :644 · `bind_families` :726-974 | pads + their z | **INERT** | **0 of the 22** deck-touching bodies carries a `family_of` (measured, all `None`) |
| 5 | `footprint_unit.plan_unit_datums` :528-597 (`pad_plurality` :567, `min(p.z)` :589) · `plan_wide_seats` :778-870 · `bind_footprint_units` :68-242 | pads | **INERT today, IGNORE by rule** | **0 of the 22** carries a `unit_of` or `connector_of`. But 17x (1) has just made "the graded AIRSIDE surface a FLOOR under every unit member" — a deck is **groundside** `service_road`, so §49 must say in words that a deck face is *not* that floor, or the two laws will collide the first time a parapet lands in a unit |
| 6 | `footprint_unit.msl_seats_for_dump` :898-1016, **`src == "deck"` :998-1000** (`msl_base_deck`) | the unit seats | **CONSULT** | `src=="deck"` here is the OBJECT deck (`_is_deck_member` :56-66). If §49 seats a body off a graded deck face, the `OBJECT_MSL` writer must know which base to print. LEMD `msl_seats = 0` today, so nothing moves yet |
| **RIMS arm** |
| 7 | `placement_body._raw_bodies` **:182** (`rim_of`), **:196** (`body_rims = rims if is_basin else ()`) | rims | **IGNORE** | A deck shares 8–9 nodes with `tunnel_wall` rims. If the deck were published as a rim-like ring, parapets would classify BASIN and take §14 (2)'s single rim point |
| 8 | `anchor_rule._basin_rim_anchor` :753-792 (via `anchor_for` :670-673) | rims | **IGNORE / EXCLUDE** | A BASIN body's zero IS its rim. `LEMD60__b8` (`basin rim (tunnel_wall@850)`, 10/81 samples inside deck `-11828`) and `Bridge3.obj__b0` (`basin rim (tunnel_wall@827)`) are exactly this class and must be excluded by construction |
| 9 | `placement_cut._rim_of` :879-892 · `_rim_ring_of` :869-877 · `_basin_floor_member` :857 | rims | **INERT** | keyed on `RimRing` only |
| 10 | `basin_ring.arcs_of` :132 · `ring_bar` :324 · `ring_arcs` :447 · `arc_anchor` :543 | `RimRing.z` | **INERT** | ditto |
| 11 | `placement_census.census_v14` :67-232 (**`for r in rims` :188**, §14a ring bar) | rims | **CONSULT (census only)** | §49 needs its own bar line beside §14a's, not inside it |
| **SURFACE / GROUND arm — where the wrong z comes from** |
| 12 | `placement_boxes.ground_under` **:194-202** (MEDIAN of `ground_samples`) | surface at each foot-box centre | **CONSULT — the defect site** | b3 → 599.33, b4 → 599.31 because half their foot boxes stand on `tunnel_ramp` 599.30 and half on the deck 606.2. The median picks the trench |
| 13 | `placement_boxes.ground_at_box` :147-163 · `ground_samples` :166-190 · `anchor_ground_off` :213 · `contact_ground` :298 | same family | **CONSULT** | one sampler, one rule — a deck-aware restriction must land here or not at all |
| 14 | `placement_cut._LineCutter.terrain_groups` :197 · `foot_groups` :335 · `carrier_groups` :487 | surface under the body's own triangles | **IGNORE, by ruling** | §16b cuts a body by the ground under it. A parapet straddling deck (606) and trench (599) is **cut in two before §49 ever sees it** — that is how Bridge2's component 1 became b3 **and** b4. §49 must either run before this cut or declare a deck-straddling body uncuttable |
| 15 | `placement_cut.segment_anchor` **:727-741** (`line segment N/M: mid-foot`) | one segment's feet | **CONSULT — pre-emption 1** | Mints its own `Anchor`, takes no `datum`, no `pads`, no `rims`. Bridge2 b0, LEMDzaun b34 **and both Bridge4 bodies** (the only live crest-plate datum at LEMD) come out here |
| 16 | `placement_carrier.is_elevated` **:73-106** (`if anchor.datum: return False` :99-102) | the anchor | **CONSULT — pre-emption 2** | A parapet on a deck has its lowest authored vertex above `elevated_base_m` 0.5 (`structures.toml:626`) → ELEVATED → handed to PASS 3. The `anchor.datum` escape already exists and is the hook |
| 17 | `placement_plan._own_ground_file` **:299-330** (`ground_under` at **:323**, reason `OWN_GROUND` :296) | surface under its own footprint | **CONSULT — pre-emption 3** | Never calls `anchor_for`, so `anchor_rule`'s datum branch is not on its path. b2/b3/b4 and `LEMD50__b0/b1` all land here. `counts.footless_own_ground = 414` at LEMD |
| 18 | `placement_plan._carried_file` :235-291 | the carrier's anchor | **IGNORE** | **9 of the 22** hits are `carried by …`. §49 must apply to the CARRIER, never to the carried body, or a roof will be seated on a bridge |
| 19 | `placement_orphan.place_orphans` :47-165 (+ `_append` :204) | surface under an orphan component | **CONSULT** | §16d (1)'s orphans get their ground the same way |
| 20 | `placement_carrier.carriers_for` :585-886 (`Candidate.ground_off`, `_ok` :697, `_near_carried` :723) | candidate bodies + surface | **IGNORE** | A graded face is not a body, so a deck can never be a carrier. But `carrier_refused_far_from_carried_ground` must not refuse a body whose ground IS the deck |
| 21 | `placement_atom.bind_unit` :597 · `unit_rigid` :365 · `unit_clusters` :256 | zeros + contact graph | **IGNORE** | A deck-seated body must not be dragged to a cluster senior's zero. 0 of the 22 is bound today |
| 22 | `anchor_rule.datum_of` **:324-372** (plate :359-364, deck :365-372) | the MEMBER record (`plate_y`, `plate_stations`, `deck_top_y`, `deck_datum_z`, `deck_kind`, `deck_ends`) | **CONSULT** | Today it is member-level and object-derived. §49's datum is **per-body and region-derived** — a different signature |
| 23 | `anchor_rule.keep_off_row` **:376-390** (`if anchor.datum: return True`) | anchor + row z | **CONSULT** | A deck-seated one-body placement must be WRITTEN, not kept on its authored row |
| 24 | `anchor_rule._all_on_rolled` :590-615 + the §17 median-foot branch :731-742 | `surface.roles`, `surface.rolled_on` | **INERT** | `service_road` is groundside → not in `law.tables.rolled_on_roles` (`law/tables.py:541-559`). A deck foot is never rolled-on; the bar is `visual_m` |
| 25 | `placement_motion.census_motion` :108-348 | `GradedRoles` per foot | **INERT (bar)**, reports the role | groundside role, judged at `visual_m` 0.5 (`law/emit.toml:117`), never `motion_step_m` 0.05 (:116) |
| 26 | `placement_cockpit.cockpit_block` (via `placement_census`) | the §15/§16a/§16b/§16c rows | **CONSULT (census)** | This is where a parapet's residual is priced, at `visual_m` 0.5 |
| 27 | `placement_seams.census_torn_seams` :93 · `census_outside_box` | written files | **INERT** |  |
| 28 | `bridge_family.deck_prints` :250-290 → `Body.bridge_of`; `placement_plan.py:540-541` `counts["bridge_deck_footprints"]` | the OBJECT deck member's mesh | **INERT AND NAMED** | This is §16e (3)'s object-derived footprint, **not** the graded region. LEMD reads `bridge_deck_footprints: 0`; all 22 hits have `bridge_of: None` |
| 29 | `footprint_unit._is_deck_member` :56-66 · `_deck_lending` :347 | `deck_kind` / `deck_ring` on the member | **INERT** | object deck again |
| 30 | `airport/road_ramp.deck_refs` **:94-110** | `pm.structures[*].decks[*].ref` | **NOT an object-stage reader — but the precedent** | It is the existing "deck region" in `airport/`, and its docstring is explicit: *"read off the map's own structure records — never off the ref string"*. The object stage has no `PlanarMap`; it has only `graded.json`, whose only deck handle IS the ref string. **§49 must state and accept that inversion.** |

### The three tensions the table exposes (for the spec author)

* **(a) The deck ref is not published as data.** `GradedRoles.roles_many` (:464) returns the ROLE,
  not the REF. A deck face is indistinguishable from any other `service_road` face by role alone.
  §49 needs either a ref-carrying reader (E1's shape) or a `refs_many` beside `roles_many` (E2's).
* **(b) `bridge_deck:` is minted by one site and its ROLE is not fixed.**
  `planar/structure_deck.py:648` (`dref = f"bridge_deck:{w.id}"`) is the single derivation.
  A MAPPED bridge deck gets role `service_road` (:669); a **PAVEMENT** deck keeps the pavement's
  own role (`deck_roles.append(w.role if pav else "service_road")`, :669) — so an `apron`-role
  `bridge_deck:` face is possible and once existed (SPJC's four jetway decks, narrowed away by
  `deck_signature.is_bridge_way` :147-164 / RULINGS 13bm item 1). §49 must say whether a
  pavement deck is in the region. **Today the corpus has 14 deck faces and all 14 are
  `service_road`** — so the choice is free of collateral right now.
* **(c) `object_deck:` never reaches a face.** `structure_deck.py:687-688` appends
  `Deck(f"object_deck:{oid}", …)` to `decks` but **not** to `deck_polys`/`deck_roles` — object
  bridges are "recorded, never severing". Confirmed: **zero `object_deck:` refs in any
  `graded.json` in the corpus.** So the region is `bridge_deck:*` and nothing else; there is no
  `pavement_decks` or viaduct ref family in the emitted product.

---

## Q2 — THE DATUM PATH AND THE ORDER

### The order the seat rules actually run in (`placement_plan.build_splits` :408-983)

| order | site | what it can set |
|---|---|---|
| 0 | `_fu.plan_wide_seats` **:543** (§16g (1)) | unit datums, before any body exists |
| 1 | **PASS 1** `:550` → `_raw_bodies` (`placement_body.py:45`) | the body's first anchor. Three branches: **(1a)** partless datum member `:89`; **(1b)** the SEGMENT branch `:143-163` → `segment_anchor`, `continue` — **no datum argument at all**; **(1c)** terrain/foot/carrier groups `:388-394` and `_whole_body` `:522-527` → `anchor_for(..., datum=datum_of(m))` |
| 2 | **PASS 2** `:608` | `coarsen` → `bind_plan_overlaps` → `re_cut_by_terrain`; the group takes the SENIOR body's anchor |
| 3 | `_orphan.place_orphans` `:703` (§16d (1)) | orphan components get their own anchors |
| 4 | `_atom.bind_unit` `:712` (§16c (7)) | the cluster senior's zero replaces the member's |
| 5 | `_fu.bind_footprint_units` `:719` (§16f/§16g) | the family/unit plane replaces a FOOTED body's zero |
| 6 | **PASS 3** `:724` | elevated/footless bodies: `carriers_for` → `_carried_file` `:235` **or** `_own_ground_file` `:299` |
| 7 | **PASS 4** `:874` | the cut and the write |

### Which reading pre-empts the deck if it were added to `anchor_for` only

Adding a deck branch to `anchor_for` / `datum_of` would reach **1 of the 5 Bridge2 bodies** (b1,
`low-side foot`). It is pre-empted for the other four, and the pre-emption is ordered:

1. **`placement_body.py:143-163` — the SEGMENT branch.** `pieces = cutter.segments(parts)`; if
   non-empty it appends `segment_anchor(feet, surface, si, len(pieces))` and `continue`s.
   `anchor_for` is never called, `datum_of` is never called. **Catches Bridge2 b0,
   `Terminal4_green-LEMDzaun__b34`, and both `Bridge4.obj` bodies.**
   *This is not hypothetical:* `Bridge4.obj` carries `plate_y 2.016` with **72 plate stations** —
   the only live §16e (1) crest-plate datum at LEMD — and the shipped plan writes both its bodies
   `datum: false` with reasons `line segment 1/2: mid-foot` (z 589.15) and `2/2` (591.89).
   **§10 is already eating §16e's datum on main.**
2. **`placement_carrier.is_elevated` :73-106.** A parapet on a deck has its lowest authored vertex
   above `elevated_base_m` 0.5 → ELEVATED → PASS 3. The escape `if anchor.datum: return False`
   (:99-102) exists *because* §16e hit this same wall at OTHH, and it only fires if the anchor
   already carries a datum — i.e. only if pre-emption 1 was passed first.
3. **`placement_plan._own_ground_file` :299-330.** A separate `Body` constructor that builds its
   own `_ar.Anchor` at `:322-325` from `ground_under` at `:323`. `anchor_for` is not on its path.
   **Catches Bridge2 b2/b3/b4, `Terminal4_green-LEMD50__b0/b1`.** (`counts.footless_own_ground`
   = 414 airport-wide.)

### The single derivation site I would choose

**`airport/placement_read.py` (a `decks_from_graded_doc` beside `pads_rims_from_graded_doc`,
returning a `DeckFace(ref, ring, z)` exactly parallel to `PadRing`), consumed by ONE new
`anchor_rule.deck_datum_of(box_or_feet, decks) -> Datum | None` that the three anchor mints call.**

Reasons, in order of weight:
* `placement_read.py` is the file the law already names as "the graded document's own rings", it
  is 87 lines (the 1,000-line law is not near), it has exactly two production callers plus the two
  tools, and its docstring already says "NO LAW CONSTANT LIVES HERE" — the region constant
  (`DECK_REF_PREFIX = "bridge_deck:"`) belongs beside `PAD_FACE_ROLE` / `RIM_BREAKLINE_KIND` at
  `:51-52`, which is where the census-wrapper precedent it records says to put it.
* `PadRing` already carries per-vertex **z** (`anchor_rule.py:99-109`, added by §14a/§16f (4)) —
  a `DeckFace` needs no new plumbing to answer "the deck's z at this station".
* The alternative — a deck-aware `surface()` wrapper — is **refuted before it is tried**: it
  would move every reading of every body over a deck (carriers, terrain cuts, §17 motion,
  §16b's ground bound), i.e. 22 bodies' worth of intent spread over ~15 consumers.
* **What it does NOT solve, and must be ruled:** three mints must each be edited to call it
  (`segment_anchor`, `_own_ground_file`, `anchor_for`). If the spec wants literally one edited
  site, the only shape that gives it is a **late override pass in `build_splits` between step 6
  and PASS 4**, in the position `bind_footprint_units` occupies — it sees every body's final
  anchor and can replace it. That is the shape I would recommend if "one site" is the hard
  constraint, with the caveat in Q3 that a late override cannot create stations.
  Note `placement_plan.py` is **1,035 lines** — already over the 1,000-line law; a lane adding a
  pass there must move something out first.

---

## Q3 — THE SLOPE

### Where the seat is baked (file:line), and is it a pure translation?

**Yes — a pure translation, at four call sites of one function.**

* `airport/obj8_split.py:300-311` `_retok(line, first, delta)` — "``line`` with its three
  coordinate tokens at ``first`` shifted by ``-delta``", `for j in range(3)`. **A constant
  subtraction.**
* Applied at `:498` (`vt_index`, the `VT` rows), `:508` (`vline_index`), `:629` (`LIGHTS`) and
  `:641` (the `_POSITIONAL` commands `LIGHT_NAMED`/`LIGHT_PARAM`/`LIGHT_CUSTOM`/`LIGHT`/
  `SMOKE_*`, `:104-107`). `offset_of = {b.body_id: b.offset}` at `:490`.
* The offset itself: `placement_plan.authored_offset` **:94-109** —
  `return (e*c - n*s, y_zero, -e*s - n*c)`: the anchor point's authored (x, z) and the body's
  `y_zero`. `Anchor.offset` is declared at `anchor_rule.py:123`.

### Would a SHEAR be a one-site change there?

**Mechanically yes for the vertex positions; no in three named respects.**

1. **Positions: one site.** `_retok` already parses the three coordinates, so replacing the
   constant `delta` with a callable `delta(x, y, z)` (y += g · along-axis station) covers all
   four call sites at once.
2. **NORMALS ARE NOT SHEARED, and the same line must do it.** An OBJ8 `VT` row is
   `VT x y z nx ny nz s t`; `_retok(row, 1, …)` edits tokens 1-3 only. A shear is not a rigid
   motion, so `nx ny nz` must be transformed by the inverse-transpose or every lit surface on the
   parapet is wrong. Same function, second edit — still one site, but a real correctness item the
   spec must name.
3. **AN ANIMATED BODY CANNOT BE SHEARED AT ALL.** Vertices inside an `ANIM` block are written
   **untranslated** (`row if in_anim else _retok(...)`, `:498`/`:508`); the offset is instead
   injected as an `ANIM_trans` node (`obj8_split.py:575-580`,
   `ANIM_trans\t{-dx} {-dy} {-dz}\t{-dx} {-dy} {-dz}\t0 0\tnone`). **OBJ8 has no shear
   animation node.** So a sheared body with an ANIM block has no representation. At LEMD this is
   free — `counts.anim = 0` and `kept = 4, all one_body` — but it is a hard limit of the format
   and must be a refusal in the spec, not a silent wrong render.
4. A **small pitch rotation** is expressible (`ANIM_rotate` exists, and a rotation preserves
   normals up to the same rotation) but it rotates the parapet's *whole* section — the wall would
   lean. A shear keeps posts vertical. The owner's words ("match the slope angle") read as the
   shear.

### What §16d / §10's line-station cut gives for free — and the exact numbers

The deck faces, with their least-squares grade along their own principal plan axis (my
measurement, `LEMD.graded.json`):

| deck face | ref | axis length | z range | rise | **grade along axis** | off-axis residual (crossfall) |
|---|---|---|---|---|---|---|
| 789 | `bridge_deck:-6288` (**Bridge2's**) | 84.9 m | 605.60…609.47 | 3.87 m | **+4.12 %** | 1.39 m |
| 843 | `bridge_deck:-15293` | 72.7 m | 629.61…632.89 | 3.28 | +4.28 % | 0.63 |
| 817 | `bridge_deck:-14230` | 48.7 m | 633.56…637.56 | 4.00 | −7.31 % | 0.77 |
| 839 | `bridge_deck:-5305` | 35.1 m | 607.79…609.34 | 1.55 | −2.76 % | 0.44 |
| 840 | `bridge_deck:-1378` | 46.7 m | 611.61…612.92 | 1.31 | +2.10 % | 0.37 |
| 818 | `bridge_deck:-516` | 460.9 m | 633.00…635.14 | 2.14 | −0.21 % | 1.16 |
| 812 | `bridge_deck:-11828` | 83.1 m | 601.25…603.38 | 2.13 | −0.52 % | 1.25 |

**Station spacing.** `[placement] line_segment_m = 100.0` (`law/structures.toml:689`, pinned equal
to `[rebake] body_feet_span_m` :630); `line_object_stations_max = 64` (:636).
`_LineCutter.segments` (`placement_cut.py:155-194`) returns `[]` when
`span <= self.segment_m` — so:

* **Bridge2 b0**: plan box **125.6 m** → `line segment 1/2`, ~**63 m per station**.
* **Bridge2 b3 (99.8 m) and b4 (84.6 m) are both UNDER 100 m → NO station cut at all.** One seat
  for the whole run.
* On `-6288`'s **+4.12 %**, the step between adjacent station seats is
  **100 m × 0.0412 = 4.12 m** at the shipped key, **~2.6 m** at b0's actual 63 m stations, and
  **±1.94 m about the mid-foot** for a body seated once across the deck's own 84.9 m.

**Is that step visible? Yes, by a factor of 8.** The judging bar for a `service_road` (groundside,
therefore **not** in `law.tables.rolled_on_roles`, `law/tables.py:541-559`) face is
`[cockpit] visual_m = 0.5 m` — `law/emit.toml:117`, the §17 CRITICAL VISUAL threshold
(`motion_step_m = 0.05`, :116, does not apply here). To hold 0.5 m on a 4.12 % deck the stations
must be **≤ 12.1 m** — about **1/8 of `line_segment_m`**. That key cannot simply be lowered: it is
pinned to `[rebake] body_feet_span_m` and LEMD's 5,157 m perimeter fence would need ~430 stations
against the 64 cap. **So the station cut gives §49 nothing usable for free; a deck-local station
rule (or the shear) is required.**

### Is `LEMDzaun.obj` the same class?

**Partly, and the brief's figures need one correction from the shipped plan.**
`LEMD_OBJ-Airport_Terminal4_green-LEMDzaun.obj` publishes **36 bodies**. The body that touches
deck `-6288` is **`__b34`**, `line segment 2/3: mid-foot`, **27 feet**, z 605.00, `y_zero` −0.20,
box 74.4 × 48.3 m — 6/81 samples inside the deck ring, **−2.00 m** below the deck at its station.
Its siblings are `b33` (1/3, 18 feet, 608.65) and `b35` (3/3, **60 feet**, 609.02) — the brief's
"60 feet, 3 stations" is `b35`, which does **not** overlap `-6288`. So: **yes, same class** — a
`line_segment` body cut by `segment_anchor`, pre-empted at the same site — but the one on the deck
is `b34`, not `b35`.

---

## Q4 — THE POPULATION

### Corpus-wide (every `*.graded.json` + `o4_v2_placement_*.json` under `/Users/noah/XPTerrainBuilderData/Patches`)

| airport | graded written | deck faces | placement product | **bodies touching a deck** |
|---|---|---|---|---|
| **LEMD** | 2026-09-17 19:36 | **7** | 19:37 | **22** |
| KCLT | 2026-09-13 19:51 | 3 | 19:54 | **0** |
| HEAZ | 2026-09-17 19:30 | 2 | — | n/a |
| LGMG | 2026-09-16 16:54 | 1 | — | n/a |
| KJQF | 2026-09-13 19:45 | 1 | — | n/a |
| OTHH / VHHH / HECA / LGAV / KPHX(×2) / KSDL / SPJC / NZQN / NZVL | — | **0** | yes | **0** |
| CYXY + 25 others | — | 0 | none | n/a |

**OTHH has no deck face at all** — its whole bridge law (§16e) runs off the OBJECT's `deck_top_y` /
`plate_y`, not off a graded face. So §49 and §16e are two disjoint regions at two disjoint
airports, and §49 is **testable only at LEMD** (KCLT gives a zero-collateral control).

### The 22 LEMD bodies, by deck, with z vs the deck at their own station

*"in" = of an 81-point grid over the body's plan box, how many fall inside the deck ring; "deck z"
= the deck ring vertex nearest the body's in-deck centroid; `d` = body z − deck z.*

**`bridge_deck:-6288` (Bridge2's deck, the owner's site) — 7 bodies**

| resource | body | class | feet | elev | in/81 | z | deck z | **d** | anchor reason (verbatim) |
|---|---|---|---|---|---|---|---|---|---|
| `Bridges/Bridge2/Bridge2.obj` | b0 | line_segment | 50 | F | 14 | 611.52 | 606.98 | **+4.54** | `line segment 1/2: mid-foot` |
| " | b1 | line_segment | 4 | F | 1 | 599.30 | 608.87 | −9.57 | `low-side foot (… terrain spread 7.34 m)` |
| " | b2 | line_segment | 0 | T | 26 | 605.96 | 606.19 | **−0.23** | `footless_own_ground: …` |
| " | b3 | line_segment | 0 | T | 19 | 599.33 | 606.20 | **−6.87** | `footless_own_ground: …` |
| " | b4 | line_segment | 0 | T | 28 | 599.31 | 606.19 | **−6.88** | `footless_own_ground: …` |
| `…Terminal4_green-LEMD50.obj` | b0 | line_segment | 0 | T | 22 | 606.22 | 606.19 | **+0.03** | `footless_own_ground: …` |
| `…Terminal4_green-LEMDzaun.obj` | b34 | line_segment | 27 | F | 6 | 605.00 | 607.00 | **−2.00** | `line segment 2/3: mid-foot` |

**`bridge_deck:-11828` (T2/OldTerminal, service road over the tunnel) — 15 bodies**

| resource | body | class | feet | elev | in/81 | z | deck z | d | reason |
|---|---|---|---|---|---|---|---|---|---|
| `…OldTerminal_FSX-LEMD60.obj` | b8 | **basin** | 8 | F | 10 | 601.64 | 601.44 | +0.20 | `basin rim (tunnel_wall@850)` |
| " | b11 | other | 8 | F | 9 | 602.75 | 601.72 | +1.03 | `surface at the body's zero` |
| " | b12 | other | 8 | F | 18 | 602.28 | 602.16 | +0.12 | `low-side foot (…)` |
| `…OldTerminal_FSX-LEMD38.obj` | b76 | other | 10 | F | 0 (31 deck vtx inside its box) | 602.45 | 603.18 | −0.73 | `median foot: every foot on rolled-on pavement (§17)` |
| `…OldTerminal_FSX-ZAUN.obj` | b6 | line_segment | 0 | T | 26 | 601.64 | 601.44 | +0.20 | `carried by …LEMD60__b8` |
| " | b7 | line_segment | 0 | T | 1 | 602.75 | 601.96 | +0.79 | `carried by …LEMD60__b11` |
| " | b9 | line_segment | 0 | T | 3 | 601.72 | 601.84 | −0.12 | `carried by …LEMD60__b10` |
| `…-TEJ3.obj` b0 · `…-VRDCH.obj` b23 · `…-LEMD84.obj` b11 · `…-T2CSG.obj` b1 · `…-LEMD41.obj` b12 · `…-STRT1.obj` b0 · `…-tej2_teilb.obj` b0 | | other | 0 | T | 0–1 | 601.87…602.83 | 601.58…602.63 | +0.01…+0.87 | all `carried by …` |
| `AESlite-LEMD-VOR-40-T1.obj` | b0 | other | 0 | T | 0 (31 deck vtx inside its box) | 603.14 | 603.38 | −0.24 | `footless_own_ground: …` |

The other five LEMD decks (`-14230`, `-516`, `-5305`, `-1378`, `-15293`) have **no body at all**.

### Which must be EXCLUDED by construction

| exclusion | count in the 22 | evidence |
|---|---|---|
| **a body already on a DATUM** (`Anchor.datum`) | **0** | every one of the 22 reads `datum: false`. (Corpus-wide there is exactly **one** member with a live datum at LEMD — `Bridge4.obj`, `plate_y 2.016`, 72 stations — and it is **not** on a deck, and its datum is already lost to §10. Name it in the spec anyway: `if anchor.datum: …` must stay senior) |
| **a BASIN body** (§14 (2): its zero IS its rim) | **1** — `LEMD60__b8` (`basin rim (tunnel_wall@850)`); plus `Bridges/Bridge2/Bridge3.obj__b0` (`basin rim (tunnel_wall@827)`, 354 × 25 m) just outside the box test | `anchor_rule.anchor_for :670-673` → `_basin_rim_anchor :753`. Every deck face shares 8–9 nodes with a `tunnel_wall` rim, so this collision is structural, not incidental |
| **a CARRIED body** (§15: takes its carrier's anchor) | **9** (`merged_into` set: ZAUN b6/b7/b9, TEJ3 b0, VRDCH b23, LEMD84 b11, T2CSG b1, LEMD41 b12, STRT1 b0, tej2_teilb b0 — 10 rows, 9 distinct carriers) | `placement_plan._carried_file :235-291`. §49 must move the CARRIER; moving a carried body breaks §15 (3)'s `zero − zero_beneath` bar |
| **a DECK-class body** (the object's own deck plate) | **0 at LEMD** | no member has `deck_kind` in `("flag","signature")`: the plan reads `{'candidate': 39, '': 288}`. §16e (2)'s deck-top datum is **dead at LEMD** |
| **a PIER / a body BELOW the deck** | not separable from this product | `Bridge2__b1` (z 599.30, 1/81 inside, −9.57 m) is the candidate — it stands in the trench, not on the deck. §49 needs an above/below test the plan does not publish (`Part.height_m` exists since 14bo; the body's top-y does not reach the placement record) |
| a body in a **footprint unit / object family / connector** | **0** | all 22 read `family_of: null`, `unit_of: null`, `connector_of: null`, `bridge_of: null` |

**`Bridge4.obj`'s plate**, asked for by name: two bodies, `b0` `line segment 1/2: mid-foot`
z 589.15 and `b1` `2/2` z 591.89, both `datum: false`, boxes 75.6 × 64.0 m and 80.7 × 34.8 m —
**not on any deck face** and therefore outside §49's population, but it is the live proof of
pre-emption 1. **`othh-bridge-deck-datum-r12`'s class is absent from this region entirely**: OTHH
emits no deck face, and its bridges are handled by §16e (2)'s object-derived deck top.
**Light poles / road furniture on decks: none found** — the only non-parapet bodies on a deck are
the 15 around `-11828`, which are terminal fabric and fence stations, not deck furniture.

---

## Q5 — RULINGS 2026-09-13r, quoted, and exactly what it ruled

`tools/docq.py ruling 13r` (`Ortho4XP/docs/RULINGS.md`), the operative sentence, verbatim:

> `Bridge2.obj` / `LEMD50.obj` are DRAPED object plates (their top an offset over the solved
> ground, not a datum) — RULED: a draped deck plate rides the terrain deck the mesh gives it; the
> terrain deck is what must be right (item 9), no object re-seat.

And, two sentences earlier in the same entry, the reason the parapets are not in it:

> ITEM 9 MISSED: the decks went from 2.77 m BELOW the apron to 2.0–2.1 m ABOVE it … **THE DECK
> RING'S VERTICES ARE THE CORRIDOR RIM'S (one node carries both ways)** …

**What it ruled, and what it did not.** The subject of 13r is "a draped deck **plate**" — the
object's own horizontal top surface, whose top is "an offset over the solved ground". The remedy
it names is entirely on the TERRAIN side ("the terrain deck is what must be right (item 9)"), and
the two refinements it owes (`v2rampwalk`'s route reading; the rim/deck vertex coupling) are both
terrain refinements. **"No object re-seat" is the plate's disposition, not the parapets'.**

The measurement agrees with that reading. If 13r had bound the parapets, the parapets would be
draped at "an offset over the solved ground" — i.e. within a plate thickness of the deck. They are
not: **b3 −6.87 m and b4 −6.88 m** below the deck at their stations, **b0 +4.54 m** above it. The
only two bodies actually behaving as 13r describes are `Bridge2__b2` (−0.23 m) and
`Terminal4_green-LEMD50__b0` (+0.03 m) — and `LEMD50.obj` is the other resource 13r names. So 13r
is descriptively true of the **plate** bodies it names and descriptively false of the walls.
RULINGS 2026-09-15h corroborates: the parapets "are REFUSED as walls at the 1.5 m skirt gate
(13r: draped plates)" — i.e. 13r was already being applied to the parapets as a *screening*
decision, never as a seat.

**Answer: 13r bound the PLATE. The parapets were never adjudicated.** Owner ruling 17x (2) reads
it the same way ("13r is read as the deck PLATE (rides the terrain), not the parapets"), so §49
amends §16e without overturning 13r — but the spec should say so in one line, because
`Bridge2.obj` is named in both.

---

## Q6 — THE FALLBACK: "seat at the LOW end and let it disappear into the deck"

**It is deliverable with the existing rules and ONE new region — no new anchor rule.**

The reading that delivers it is `anchor_rule.anchor_for`'s **existing low-side branch**,
`:740-747`:

```
low = min(cands, key=lambda c: (c[3], c[2], c[0], c[1]))     # c[3] = surface(foot)
return Anchor(body_class, low[0], low[1], low[2],
              f"low-side foot (no point within {tol_m:g} m of the body's "
              f"zero plane: terrain spread {residual:.2f} m)" + on_pad, low[3])
```

`min` is keyed on `c[3]`, **the design surface at the foot** — so the low-side foot IS the foot at
the lowest end of whatever surface the candidate set is restricted to. The restriction machinery
is also already there, three lines above at **`:697-701`** (§16d (6)'s `pad_majority`):

```
_pad = pad_majority(cands, pads)
if _pad is not None:
    _on = [c for c in cands if _inside(_pad.ring, c[0], c[1])]
    if _on: cands = _on; on_pad = f" on pad {_pad.ref}"
```

**Substitute the deck face for the pad and the fallback is complete**: the candidate set becomes
the feet standing on the deck, `zero` becomes their median, the residual becomes the deck's own
rise, `residual > tol_m` (0.3) fires, and the body is seated at the **low end of the deck**, its
base buried into the deck rising away from it. That is the owner's sentence, in the code that is
already there.

**Which station.** For `bridge_deck:-6288` the low end is **z 605.60** and the high end
**609.47**: a parapet seated at the low end is **buried up to 3.87 m** at the high end and
**floats 0.00 m** anywhere — which is the trade the owner named ("better than leaving an end
floating"). Per body, the move from today:

| body | today | seated at `-6288`'s low end (605.60) | change |
|---|---|---|---|
| Bridge2 b0 | 611.52 | 605.60 | **−5.92 m** (it stops standing 4.54 m proud) |
| Bridge2 b2 | 605.96 | 605.60 | −0.36 |
| Bridge2 b3 | 599.33 | 605.60 | **+6.27 m** |
| Bridge2 b4 | 599.31 | 605.60 | **+6.29 m** |
| LEMD50 b0 | 606.22 | 605.60 | −0.62 |
| LEMDzaun b34 | 605.00 | 605.60 | +0.60 |

**Two things the fallback does NOT get for free, and they must be in the spec:**
* **The three pre-emptions of Q2 still apply.** `anchor_for` is reached by **1 of the 7** bodies on
  `-6288` (b1). b0/b34 come from `segment_anchor`, b2/b3/b4/LEMD50-b0 from `_own_ground_file`.
  So even the "free" fallback needs the deck consulted at those two extra mints — or the late
  override pass of Q2.
* **For the footless bodies there are no feet to take the `min` of.** `_own_ground_file` uses
  `ground_under` (`placement_boxes.py:194-202`), the **median** of foot-box samples. The fallback
  there is `min` instead of the median, over the samples **restricted to the deck face** — same
  one-line shape, a different function.

---

## Q7 — SOURCES I COULD NOT VERIFY

1. **How many bodies carry an `ANIM` block internally.** The `ANIM`-shear impossibility
   (Q3 item 3) is read off the code (`obj8_split.py:498/:508/:575-580`) and off
   `counts.anim = 0` in the shipped plan — but that counter is the *kept-whole-for-anim* reason,
   not a count of ANIM blocks inside written bodies. `obj8_split` tracks `anim_count[body]`
   (`:488`) and does not publish it. **Unmeasured.** Measuring it needs
   `obj8_split_report.py --write-into DIR` on the shipped rebake plan, or a new published count.
2. **Whether `Bridge2__b2` is literally station 2/2 of `b0`'s segmentation.** The code path is
   consistent with it (`placement_body.py:160-163` marks each segment `is_elevated(min foot y,
   sa, elevated_base_m)`; an elevated segment goes to PASS 3 and `_own_ground_file` overwrites the
   `2/2` reason) and b0/b2 are both component 0 with adjacent boxes — but the shipped product
   publishes neither the segment index of an overwritten body nor the triangle sets, so I cannot
   close it. **Stated as the most likely mechanism, not measured.** (Same open item as scout
   `lemdobjects` Q8 #2.)
3. **The above/below test for piers.** `Bridge2__b1` (599.30, 1/81 inside the deck) is almost
   certainly *under* the deck, not on it, but the placement record publishes no body top-y —
   only `plan_box`, `geom_box`, `foot_boxes`, `surface_z`, `y_zero`. I could not separate
   "pier under the deck" from "parapet on the deck" from the product. **A §49 exclusion for piers
   needs a field the plan does not currently carry.**
4. **KCLT's 3 deck faces against a matched placement product.** KCLT's `graded.json` (09-13 19:51)
   and `o4_v2_placement_KCLT.json` (09-13 19:54) are from the same run, so the 0 is sound — but
   both are four days older than main `390c3282` and predate §16g's later rounds. The zero is
   reported at that base, not at HEAD.
5. **HEAZ / LGMG / KJQF.** Deck faces measured (2 / 1 / 1) but **no placement product exists**
   for any of them, so I cannot say whether a body would touch them. §49's collateral at those
   three airports is **unmeasured**.
6. **The mesh sampler vs the graded Delaunay.** Every z I quote is read verbatim out of the
   emitted `LEMD.graded.json` and `o4_v2_placement_LEMD.json`. I did **not** run any sampler.
   `obj8_split_report`'s own MEASURED block (§16d) records that the app's mesh sampler and the
   tool's Delaunay disagree on every surface-driven refusal, so any lane arm must be dry-to-dry.
   The only LEMD mesh on disk is dated 2026-08-27 (unmatched to this 09-17 frame).
7. **Historical seats.** `tools/harness/frames.py list LEMD` has **no live object-stage LEMD
   capture** — every `capture` row is `[MISSING]`; the only live LEMD frames are lane
   `v2wallface`'s and `v2doorwellperf`'s **structures**-stage `structures.json` dry pairs at base
   main `31b7ad1b` (`/tmp/harness/v2wallface/{base,lane}_LEMD/`). I could not compare against any
   earlier placement product.
8. **`counts` in the shipped placement product are the summary only** (8 keys: bodies 2836,
   splits 323, kept 4, …). The rich plan-stage counters I quote
   (`footless_own_ground 414`, `footless_no_carrier 33`, `bridge_deck_footprints 0`,
   `elevated_own_files 0`, `anim 0`) come from `provenance.counts` in the same file, which is the
   writer's own block — verified present, not independently derived.

---

## Instrument note (tool discipline, RULINGS `7e90032`)

My sweep is a scratchpad script,
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/03d6658a-30ff-4e68-8bf7-8c84d900b14f/scratchpad/decks.py`
— **first use**, so not promoted. `tools/INDEX.md` **does** exist at the repo root (343 KB; the
`lemdobjects` report's "instruction mismatch" is stale — note it is dirty in `git status`).
The near-fits I checked before writing it: `tools/site_read.py` answers ONE coordinate;
`tools/obj8_split_report.py --rows-near LAT,LON[,R]` answers bodies near a POINT; neither can be
asked about a REGION. **On a second use the right move is to extend `obj8_split_report.py`** (a
`--rows-on-ref PREFIX` projection of the same census pass, in the shape `--rows-near` already
took), never to fork this script.
