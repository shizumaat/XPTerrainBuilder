# Brief pack — lane `v2drapedbind`

Base: main `98c94f86` · generated 2026-09-15 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Bind _draped_components: the LGAV object-stage crash

## The brief

# THE DEFECT (observed, owner's LGAV tile build 2026-09-14 23:14, engine 1.50.1785; still on main 98c94f86)

    [v2 rebake] LGAV: placement failed ('_LineCutter' object has no attribute '_draped_components'); continuing

The whole OBJECT STAGE was skipped at LGAV (no unit placed, no re-bake) — the build "continued" and exited 0.

Mechanism (read, not guessed): `Ortho4XP/src/auto_patch_v2/airport/placement_geom.py` holds the §16d (1) readings
that were MOVED out of `placement_cut._LineCutter` (module comment at :103). Three of the four are re-bound as
methods in `placement_cut.py` (:647–:659: `written_components`, `part_tris`, `plan_box_of_tris` each delegate
to `_pg.<name>(self, …)`). The fourth, `_draped_components(self, drp)` (:202), is NOT bound — yet
`written_components` (:157) calls it as `self._draped_components(drp)`. Any placement whose written geometry
carries DRAPED triangles beside solid ones reaches that line and raises. The campaign suite is 1,570 green with
this bug in it: no twin drives `written_components` through a draped+solid fixture.

# THE FIX (one mechanism)

1. Bind or call directly — prefer the direct module call `_pg._draped_components(self, drp)` at :157 (the
   other three readings are called through `_pg.` from the class; a private helper needs no method identity),
   OR add the fourth delegate beside :647–:659. Pick one; say which and why in the commit.
2. Twin in `Ortho4XP/tests/auto_patch_v2/test_v2objsplit.py` (the file already builds `_CUT._LineCutter(...)`
   fixtures at :2519, :2557, :3283): a fixture whose OBJ8 has one solid body AND a draped page (ATTR_draped
   triangles at Y=0), then `written_components()` returns the solid body and the draped components without
   raising; assert the draped components are welded on the millimetre key the docstring names.
3. Grep `placement_geom.py` for every other `^def name(self` and prove each is reachable from the class
   (bound or called with an explicit `self`); list them in the commit message.

# WHAT NOT TO DO
- No tile build. No airport build is needed for this fix: the closing test is the twin plus the offline
  object-stage read of LGAV IF an instrument exists (`tools/docq.py index site_read`); if none replays the
  rebake plan offline, the twin is the closing test and you SAY SO.
- Do not touch the law, the loader, or the trench/pavement questions (the session owns those; separate briefs).
- File cap: `placement_geom.py` / `placement_cut.py` line counts stay under the 1,000-line guideline.

# CLOSING
Run `cd Ortho4XP && venv/bin/pytest tests/auto_patch_v2 tests/test_harness.py -x -q` and quote the FAILED lines
(or "0 failed") verbatim. Commit on branch `claude/v2drapedbind`; the session merges.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/placement_geom.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_cut.py`, `Ortho4XP/tests/auto_patch_v2/test_v2objsplit.py`

## Spec (object-placement) §16d

## §16d THE PLAN BOXES WHAT THE WRITER WRITES (Fable 2026-09-13; RULINGS 2026-09-13h) — lane `v2unboxed`

Owner (13d items 3, 4): a dark plate ~15 m over the T4 apron; roofs still floating at
the cargo hangars. Scout `v2lemd325o` on the 1.0.325 written frame: the DSF has no
polygon with an elevation (every one of its 1,609 `.pol`/`.lin` is draped) — the
plate is an OBJECT: the FS2XPlane 10 × 10 m shadow quad every source object carries
at its origin, y = −5, normal down (`North_FSX-LEMD80.obj` is nothing else). Aerosoft
LEMD is a shared-datum pack — 2,035 of 2,109 bodies sit on two placement rows 18 m
from the owner's point — so seven such quads stack at that spot, and four ride zeros
chosen kilometres away: `Terminal4_green-T4BJO__b0` +16.37 m, `Terminal4_yellow-
LEMD16__b0` +15.90 (its box is the T4 terminal 2.27 km west), `Cargo-LEMD63__b6`
+7.13, `OldTerminal_FSX-LEMD43__b0` +2.22. At the cargo hangars `Cargo-TEJ1__b0`'s
roof plate stands +3.71 m over `NEWCO__b9`'s roof (76 of its 105 vertices lie 694 m
outside its own `geom_box`; on `NEWCO__b9`'s zero it lands 0.03 m from the roof top);
`Cargo-TEJ3__b1` the same. THE MECHANISM: `geom_box` is the hull of the ADMITTED
parts (`placement_plan.py:230`, `:298`) while the writer emits the source object's
triangles regardless — a zero-thickness one-sided quad is not admitted (`no_solid_
admitted 25`), a roof plate over another hangar was never boxed — so the geometry
rides a zero the body chose elsewhere and NO instrument reads it (§15, §16a, §16b
read the box; §7 reads feet; the quad has neither). Class: 397 of 2,109 bodies carry
geometry > 1 m outside their own box (202 > 10 m, 65 > 100 m, 8 > 1 km; 91 of them
carried/bound). Two instrument defects beside it: the cockpit block's worst
coordinate for §15/§16a/§16b rows is the PLACEMENT ROW (`placement_cockpit.py:42-60`)
— at a shared-datum pack that is one of two points for 96.5 % of bodies (12ak's
"LEMD03__b33 at 40.4928202" was that artefact); and the `nearest footed body of the
unit` fallback (`placement_carrier.py:833-843`) has no distance cap (35 binds, 19 over
100 m, one 3,323 m).

1. **EVERY WRITTEN TRIANGLE BELONGS TO A BODY WHOSE BOX CONTAINS IT.** At the split,
   a connected component — admitted as a part or not — whose plan distance from
   the body's part hull exceeds `coarsen_reach_m` (100 m) is not that body's: it is
   its own body, footless, anchored on its own ground at its authored offset
   (§16 (3)). The FS2XPlane origin plate (a one-sided, zero-thickness quad at the
   object origin below y = 0) is such a body: written on its own ground at −5 m, it
   is buried as the pack authored it. `geom_box` is the hull of what the file will
   contain, and §16b's span bar reads it.
2. **THE NEAREST-FOOTED FALLBACK IS CAPPED** at `coarsen_reach_m`; beyond it a
   footless body takes its own ground (§16 (3)).
3. **THE COCKPIT COORDINATE IS THE BODY'S**: the worst row's coordinate is the
   centre of the body's written geometry (or its worst foot), never the placement
   row.
4. **BARS (1.0.325 written frame, matched arms)**: the four plates gone from the sky
   (each on its own ground at −5 m); `Cargo-TEJ1__b0` on `NEWCO__b9` (roof base within
   0.3 m of 605.04); `TEJ3__b1` likewise; bodies with geometry > 1 m outside their
   box 397 → 0 (twin); the nearest-footed fallback beyond 100 m 19 → 0; the 11at/12h/
   12o/12z/12aq/12ar sites held; torn seams 0; §15 carried float 0; files quoted;
   plan stage LEMD ≤ 10.3 s; OTHH the same under the guard; the cockpit block's
   worst coordinates verified against the bodies' geometry (twin); suite. No build;
   the app after.

### §16d (1)–(3) MEASURED (lane `v2unboxed`, 2026-09-13; branch `claude/v2unboxed`)

Implemented in `airport/placement_orphan.py` (NEW: §16d (1)'s whole law — the
components the plan's bodies do not own, placed), `airport/placement_cut.py`
(`_LineCutter.written_components` / `plan_box_of_tris` / `_draped_components`),
`airport/placement_plan.py` (the pass between §15's candidates and §15's search;
`_geom_hull`, `Staged.geom_boxes`), `airport/placement_carrier.py` (§16d (2)'s
cap), `airport/placement_cockpit.py` (§16d (3)) and `airport/placement_seams.py`
(`census_outside_box`, §16d (1)'s bar instrument, printed by `--write-pack` and
`--torn-seams`).  Two files moved for the 1,000-line law: `_footless_targets` /
`_carrier_pieces` into `placement_body.py`, `group_at_zero` into
`placement_boxes.py`; both re-exported where every caller reads them.

* **ATTRIBUTION FIRST — the dry arm is NOT the app's arm.**  `obj8_split_report`
  on the 1.0.325 rebake plan does not reproduce the app's written carriers, and
  the cause is THE SURFACE, not the population: the app hands `build_splits`
  the built MESH sampler (`engine_v2._placement_surface(mesh_sample)`) while the
  tool hands it a `LinearNDInterpolator` over `LEMD.graded.json`'s emitted
  vertices (`surface_from_graded`).  Everything else matches — identical
  `bodies_uncoarsened` 11,135 and `line_segments` 849, identical law keys, the
  same `--admit-skipped` population — while the SURFACE-driven readings do not:
  `anchor_off_surface` 0 (app) vs 6 (dry), `carrier_refused_zero_off_ground`
  105 vs 221, `carrier_refused_far_from_carried_ground` 179 vs 274,
  `unit_clusters` 206 vs 202.  Those refusals are exactly what pushes a search
  down to the fallback rules, which is where `Terminal4-LEMD01__b0` sits
  (`elect__b0 (838 m)` written, `SENRG__b233 (512 m)` dry).  **Every bar below
  is therefore read on MATCHED DRY ARMS** — main `59790e5f` into pack copy A,
  this branch into pack copy B, the same rebake plan, the same graded surface,
  APFS clones of the live pack, the guard armed (both runs print `shared repo
  UNCHANGED`).  The app's own figures are quoted beside them where they exist.

* **THE INSTRUMENT (§16d (1)'s bar).** `census_outside_box` opens the WRITTEN
  files and asks whether every `VT` row lies inside the `geom_box` the plan
  published for that body.  On the app's live 1.0.325 pack it reads **378** of
  2,109 bodies over 1 m (the scout's 397 under its own fixed metres-per-degree;
  same population, same 8 over a kilometre, worst `Munoza-LEMD80__b0` 3,682 m).

  | bar (matched dry arms) | A (main) | B (branch) |
  |---|---|---|
  | §16d bodies with geometry > 1 m outside their box | 390 | **0** (0 even over 1 cm) |
  | nearest-footed fallback binds / over 100 m | 49 / 29 | **21 / 0** |
  | §16c torn seams outside line/arc pieces | 0 | **0** |
  | §16c single-component resources in ≥ 2 files | 0 | **0** |
  | §15 carried body floating over its carrier | 0 | **0** |
  | duplicate rows of a split placement surviving | 0 | **0** |
  | DSF round trip / new `OBJECT_DEF`s read back | OK 2,141 | **OK 2,279** |
  | files | 2,141 | **2,279** |

* **THE FOUR PLATES (§16d (4)).**  Each is now its own footless body on its own
  ground with its authored y kept, so it renders 5 m UNDER the ground the pack
  put it over — buried, as authored:

  | plate | A: render − ground | B |
  |---|---|---|
  | `Terminal4_green-T4BJO` | **+15.94** | −5.00 (ground 595.81) |
  | `Terminal4_yellow-LEMD16` | **+15.73** | −5.00 |
  | `Cargo-LEMD63` | **+5.77** | −5.00 |
  | `OldTerminal_FSX-LEMD43` | **+1.72** | −5.00 (ground 595.82) |

  (the app's own frame read +16.37 / +15.90 / +7.13 / +2.22 — the same four
  plates, the surface difference above.)

* **THE CARGO ROOFS.**  `Cargo-TEJ1`'s roof plates are no longer one carried
  body riding a zero chosen elsewhere: each component finds the hangar it stands
  over.  The piece over `NEWCO__b9` has its roof base at **604.95** — 0.09 m
  from the hangar's authored roof top 605.04, inside the 0.3 m bar; the piece
  over `NEWCO__b10` reads 604.72 on its own hangar.  `Cargo-TEJ3` likewise
  (ten pieces on `CNTRL`, `FBRIK__b0/b1`, `NEWCO__b0/b3/b5/b8/b11/b12`, `TNT__b3`).

* **THE NAMED SITES HELD** (11at/12h/12o/12z/12aq/12ar; base planes per
  resource, arm A → arm B): `Terminal4_green-TEJ3` 610.41–617.17 → identical;
  `Terminal4SAT_green-TEJ3` 589.47–597.26 → identical; `HANG3` 605.73–606.06 →
  identical; `LEMD47` one body 603.53 → identical; `Bridge2` 598.73–607.03 →
  identical; `TABOX` spread 0.01 → identical; `T2NBG` 602.81–607.24 → identical;
  `green-PKT4` and `Terminal4_green-TEJ1` identical; `Terminal4_48` one body,
  spread 0.00 → identical.  `green-STRT4` gains 5 files (19 → 24) at the SAME
  base range 597.54–617.71: the orphan components now have files of their own
  inside the range, not outside it.

* **A LATENT WRITER DEFECT FOUND AND FIXED.**  `obj8_split` named a body's file
  by its index in the LIVE list (`body_resource_name(rel, k)`) while the plan
  spells it `body_resource_name(resource, body_id)` and the DSF row is written
  on the plan's name.  A body the cut leaves with NO triangle (its geometry
  inside an ANIM block another body owns) therefore shifted every later body's
  file one name down — the row carried the NEXT body's geometry at this body's
  zero.  Measured at LEMD: `OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s
  object, 254 m from `b0`'s own box.  The file is now named by its body, and a
  body with no file is dropped from the plan's rows (`bodies_without_a_file`) so
  no `OBJECT_DEF` points at a file nothing wrote.

* **THE COST, REPORTED NOT HIDDEN.**  LEMD plan stage **13.6 → 17.8 s** (wall
  16.81 → 21.08 s, medians of 3 foreground runs each; the branch's own
  `plan stage` line is new and reads 17.6–18.2 s, the baseline's inferred from
  the same fixed 3.2 s of tool overhead).  §16d (4)'s `LEMD ≤ 10.3 s` is
  **MISSED on BOTH arms in this frame** — the 10.3 s figure was read without
  `--admit-skipped`, which this replay needs.  OTHH plan stage **≈ 83 → 86.1 s**
  (wall 86.99 → 89.89, +3 %), the ≤ 60 s bar missed on both arms as it was at
  12ap.  The cost is the POPULATION: LEMD now places 27,737 components the plan
  never saw (19,905 joined to a body within the reach, 7,832 their own bodies),
  OTHH 143,950 (98,776 / 45,174), and 7,786 more carrier searches run at LEMD.
  Three optimisations already took most of it back and are part of the change:
  `written_components` hands back numpy arrays and the caller builds Python
  triples only for what it places; the joined components of one group are ONE
  append, not one per component; `group_at_zero` memoises each group's zero and
  ground range on its length (29.6 M inner steps, 9 s of the profiled stage).
  A further reduction is a new question, not this lane's.

* **MOVING THE WRONG WAY, NAMED.**  §16b's two counts rise because the
  population they read grew: `carried piece float over its OWN ground > 0.5 m`
  120 → 151 and `body wider than its terrain group` 1,037 → 1,116 (both already
  over their bar 0 on main).  The rise is the components that previously stood
  in some other body's file where NO instrument read them; they are now bodies
  with their own ground reading.  `§16 CARRIED bodies whose carrier's zero is
  over 1 m from the ground under their own geometry` 62 → 81 (information only),
  and COCKPIT CRITICAL visual 459 → 494 for the same reason.

* **SUITE** `tests/auto_patch_v2 tests/test_harness.py
  tests/test_role_edge_census.py tests/test_mesh_sampler*.py
  tests/test_post_mesh.py tests/test_object_rebake.py`: **1,234 passed, 1
  skipped**, twice.  Twins: `test_16d_1_a_component_beyond_the_reach_is_its_own_body`,
  `test_16d_1_every_written_triangle_lies_inside_its_body_box` (the bar as a
  property), `test_16d_2_the_nearest_footed_fallback_is_capped`,
  `test_16d_3_the_cockpit_coordinate_is_the_bodys_not_the_row`.
  `coarsen_reach_m <= 0` DISARMS the reach (the convention every other
  plan-contiguity key takes): the component then joins the nearest body.


### §16d (4)–(6) Carried components group by carrier; the ground bound is member-agnostic; a body anchors on the pad it stands on (Fable 2026-09-13; RULINGS 2026-09-13m)

Scout `v2kclt1o` on KCLT (Nimbus, native XP12: master models per material — `paredes_N`
walls, `techos_N` roofs, `vidrios` glazing — each on ONE placement row; 34 rows carry 71
split placements, bodies up to 1,628 m from their row): (a) hangar wall `005_ALB__b9`
5.04 m into its pad — a SAME-MEMBER §16c (7)/(8) bind to a body 500 m away on the
apron; 12ap's 0.5 m ground bound tests only `member != top.member`, so it was skipped
(the cluster spans 714 m at one zero; the airport's worst §17 row +5.96 m); (b) roof
plates `001_ALB__b5/b6/b11/b18/b28/b29` float +2.5 … +7.4 m — elevated bodies of 3–12
components spanning 154–1,774 m carried at ONE zero (`carried_bodies_uncut` 5,295 vs
3 cut by carrier), the walls under them correctly seated; (c) the terminal: one pad
`building80` (1.19 m of relief); 213 bodies overlap it, zeros 210.5–223.7 — the 80
whose ANCHOR POINT lands on the pad agree with it to 1.13 m, the 133 whose anchor
point lands on apron/adjacent ground (213.8–224.6) do not; clusters by contact are 272
separate things at one zero each; 12 rest-on carriers with authored gaps to −9.9 m;
a wall carried by GLAZING; a 20-vertex z = 0.00 crater in apron face 661 (`dsf:pol31`)
— design surface, not object law (RULINGS 13m, lane `v2zerocrater`).

4. **A CARRIED BODY'S COMPONENTS GROUP BY CARRIER.** Each connected component of a
   carried (elevated / footless) body finds the footed body IT stands over (§15's
   overlap at the component); components over different carriers are different
   pieces, each at its carrier's zero; a component over none anchors on its own
   ground (§16 (3)). §16a (1)'s "cut where the carrier is cut" and (1)'s reach are
   read per component. A roof resource of twelve plates over twelve buildings is
   twelve pieces.
5. **THE GROUND BOUND IS MEMBER-AGNOSTIC**: §16c (7)'s bind holds only while the
   bound body's own-ground zero is within `visual_m` 0.5 of the senior's, same
   member or not (12ap (A) applied everywhere); a cluster's zero-plane span obeys it.
6. **A BODY ANCHORS ON THE PAD IT STANDS ON.** Where a footed body's written
   geometry lies mostly on a `building` pad, its anchor point is chosen on that pad
   (the low-side foot that lies on the pad, else the pad's level under the body's
   centroid) — never on the apron or ground it happens to spill onto. The pad's own
   relief (§20: 1.19 m over 900 m at KCLT's terminal) is a §20/§28 reading, reported.
7. **BARS (KCLT 1.0.324 frame + LEMD 1.0.325 frame, matched arms)**: `005_ALB__b9` on
   its pad (−5.04 → within 0.5); the six `001_ALB` roof bodies on their walls (each
   piece within 0.5 m of the wall top beneath it); terminal bodies anchoring off
   every pad 133 → 0, the complex's zero spread 13.2 m → the pad's relief; the
   glazing carrier named and, if glazing is footless by authoring, excluded by the
   existing solid test (report, do not name-match); the LEMD sites held; seams 0;
   §16b carried-own-ground bar at KCLT 32 → quoted; files; plan stage; suite.

### §16d (4)–(6) MEASURED (lane `v2unboxed`, 2026-09-13; branch `claude/v2unboxed`)

Implemented in `airport/placement_body.py` (§16d (4): `_atom_targets`, one carried
target per ATOM, and `CARRIED_ATOMS_MAX`), `airport/placement_plan.py` (the split
before §15's search, carrying the SOURCE group so §16c (7)'s cluster membership
survives it), `airport/placement_atom.py` (§16d (5): the `member != top.member`
clause deleted) and `airport/anchor_rule.py` (§16d (6): `pad_majority`, and the
`pads` argument WIRED at last).  `placement_geom.py` took `written_components` /
`part_tris` / `plan_box_of_tris` for the 1,000-line law.

* **THE ATOM, NOT THE BARE COMPONENT.**  §16d (4) says "each connected component";
  the division here is by §16c (1)'s ATOM (`_comp_blocks`) — the component, or the
  CLUSTER §16c (6)/(7) bound it into.  Dividing a rigid cluster would undo that law,
  and the two readings are the same wherever no cluster exists.  **Reported as a
  deviation from the sentence, held to be its intent.**

* **BARS (KCLT 1.0.324 frame, matched dry arms; the write half into an APFS clone,
  guard armed, `shared repo UNCHANGED` on every run).**

  | bar | before (this branch after §16d (1)–(3)) | after |
  |---|---|---|
  | `005_ALB__b9` vs its `building` pad | **−5.04** (12ap's frame) / −5.85 here (zero 210.46, pad 216.31) | **+0.02** (zero 215.51, pad `building26` 215.49–215.51) |
  | widest RETAINED cluster zero-plane span | 5.69 m | **0.64 m** |
  | binds refused for ground | 14 | **22** |
  | carried bodies divided by ATOM | 0 | **473** |
  | footed bodies anchored ON their pad (§16d (6)) | 0 | **61** |
  | §15 carried body floating over its carrier | 0 | **0** (bar 0) |
  | §16d written geometry outside its own box | — | **0** (bar 0) |
  | §16c torn seams outside line/arc pieces | 0 | **1**, step **+0.16 m**, `paredes_9_charlotte` b1↔b6, ONE shared vertex — under the 0.3 m census tolerance and under `visual_m`; NAMED, bar missed |
  | files | 473 | **477** |
  | DSF round trip / defs read back | — | **OK, 477/477** |
  | plan stage (dry, 3 runs) | 8.65 s | **8.3–8.5 s** |

  The `001_ALB` roof bodies the owner's read names are now cut per atom and each
  rides the wall body IT stands over (`b5` → `006_ALB__b0` 219.56 vs 219.94 ground,
  `b6` → `008_ALB__b1` 221.39 vs pad `building59` 221.38–221.41, `b11` →
  `004_ALB__b0` 217.51 vs pad 217.59, `b29` → `004_ALB__b25` 216.93 vs pad
  216.93–216.96) where before they were ONE carried body per resource at one zero
  (217.51 under 223.75 m of ground, 208.81 under 221.89).  §15's own carried bar —
  `zero − zero_beneath`, which IS "within 0.5 m of the wall beneath" — is **0 on
  both arms**.

* **THE TERMINAL, REPORTED NOT CLOSED.**  Over `building80` (1.19 m of relief,
  865-node ring) the ON-PAD set's zero spread is **1.03 m** on both arms — the pad's
  own relief, as §16d (6) predicts.  The count of bodies whose anchor lands OFF the
  pad moves only 71 → 65 (footed 26 → 24) in this frame, NOT 133 → 0: the 133 was
  read on the app's 1.0.324 WRITTEN frame, and the residue here is bodies whose
  ground contacts are MOSTLY off the pad (the rule's own majority test declines
  them) plus carried bodies, which take their carrier's anchor by §15 and not their
  own.  Named, not closed.

* **A DEFECT §16d (4) EXPOSED AND FIXED.**  A target group holding BOTH a cut piece
  (its own `tris`) and a raw the cut never touched (its parts' whole components) was
  read for its `tris` alone, so the rest of the group's triangles were claimed by no
  body and `obj8_split` handed them to the nearest one: measured at KCLT, 9
  placements left 990–3,280 triangles unclaimed and `001_ALB__b32`'s file reached
  207 m outside its own box.  The audit (every placement's solid triangles against
  the union of its bodies' `tris` and `cut_components`) reads **0 of 103** after.

* **THE COST — OVER BUDGET, AND NAMED.**  Plan stage, dry, this machine: LEMD
  13.6 (main) → 17.8 (§16d (1)–(3)) → **25.0 / 28.6 / 46.0 s** over three runs;
  OTHH ≈83 → 86.1 → **136.5 s**; KCLT 8.65 → **8.3–8.5 s**.  The LEMD run-to-run
  swing is the standing ±25 % and worse; the OTHH figure is one run.  §16d (4) asks
  a carrier search PER ATOM, and OTHH's clutter members publish thousands of them.
  Three narrowings are already in: a body narrower than `coarsen_reach_m` is not
  divided (§16a (1) already cuts those against the carriers the search returns),
  `CARRIED_ATOMS_MAX` 64 bounds a body's pieces, each piece carries only ITS OWN
  parts (so §15's contact fallback reads its own neighbours, not the whole body's),
  and that fallback now counts by set intersection instead of scanning the unit's
  neighbour list once per candidate.  **This takes an airport that was already over
  the 60 s per-airport budget further over it: it needs the owner's approval and a
  Fable-5 whole-pipeline optimisation review before it ships** (`Ortho4XP/CLAUDE.md`
  HARD LAW).  No further reduction was attempted in this lane.

* **THE LEMD SITES HELD** on the same 1.0.325 frame, written arm: the four shadow
  plates still −5.00 on their own ground; `Cargo-TEJ1` on `NEWCO__b9` at 604.95;
  §16d outside-box 0; seams 0; §15 carried float 0; round trip OK 2,435/2,435;
  every named site's base range identical to §16d (1)–(3)'s except
  `Terminal4_green-TEJ1` (spread 4.01 → **1.28**) and `T2NBG` (4.44 → **4.28**).
  §16b's carried-piece own-ground count rises again with the population it reads
  (LEMD 151 → 154, KCLT 41 → 41), already over its bar 0 on every arm.

* **SUITE**: **1,237 passed, 1 skipped**.  Twins:
  `test_16d_4_each_atom_of_a_carried_body_finds_its_own_carrier`,
  `test_16d_5_the_ground_bound_holds_inside_one_member_too`,
  `test_16d_6_a_body_anchors_on_the_pad_it_stands_on`.  Four existing twins were
  re-read against the new law and are marked with the ruling that changed them: the
  two §16a (1) roof twins now assert the OUTCOME and the atom count, §14 (1)'s
  footless twin reads two atoms as two own-ground bodies, and 12ap's bind twin
  asserts the refusal INSIDE one member.

* **NOT DONE.** The KCLT z = 0 crater in apron face 661 (`dsf:pol31`) is lane
  `v2zerocrater`'s and no bar here excludes or names its bodies — the terminal
  figures above are quoted whole.  The glazing carrier is not separately attributed.
  No airport was built.

## RULINGS

## 2026-09-13m — ATTRIBUTED (scout `v2kclt1o`) and RULED (Fable, §16d (4)–(6)): KCLT (Nimbus, native XP12, no FS2XPlane quad; master models per material on 34 rows for 71 placements). Item 4: hangar wall `005_ALB__b9` 5.04 m INTO its level pad by a SAME-MEMBER §16c bind to an apron body 500 m away — 12ap's ground bound tests only across members; roofs `001_ALB__b6` +5.87, `002_ALB__b42/b45` +4.1/+3.8: elevated multi-component bodies (154–1,774 m) at one carrier's zero, never re-cut (`carried_bodies_uncut` 5,295 vs 3). Item 6: the same roof resource `001_ALB` (31 bodies, all elevated plates) +3.0 … +7.4 over correctly seated walls. Item 9: one pad `building80` (1.19 m relief); 213 bodies, zeros 210.5–223.7: the 80 anchored ON the pad within 1.13 m, the 133 whose anchor point fell on apron/ground spread 10 m; 272 contact clusters, each one zero; 12 rest-on carriers with authored gaps to −9.9 m; a wall carried by glazing (`vidrios`); FOUR bodies at zero 0.00 — a 20-vertex z = 0.00 CRATER in apron face 661 (`dsf:pol31`), a 90 × 65 m mesh pit to sea level with a 130 m skirt: DESIGN SURFACE, not object law. KCLT-wide: 136 bodies outside their box (§16d), 4 nearest-footed fallbacks > 100 m, seams 0, §16b carried-own-ground 32 (bar 0 violated), the cockpit coordinate = the one placement row for every critical line (§16d (3) confirmed). LAW: §16d (4) carried components group by carrier; (5) the ground bound is member-agnostic; (6) a body anchors on the pad it stands on. Lane `v2unboxed` (running) takes (4)–(6) as round 2; lane `v2zerocrater` (design surface) attributes and fixes the z = 0 apron vertices — a sentinel/no-data leak into the graded surface is a CRITICAL defect at any airport it touches.

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join. |

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

