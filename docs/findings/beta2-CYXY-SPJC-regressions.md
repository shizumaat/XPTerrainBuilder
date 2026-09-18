# Beta 2 regressions — CYXY-1/2/3, SPJC-1/3 (ATTRIBUTION ONLY)

Lane: diagnose-only, 2026-09-18. **No builds, no code edits, no git writes.**

> **This document is ATTRIBUTION, not an interventional measurement.**
> Project law (memory `mechanism-before-fix`): attribution reads are not
> causal. Every hypothesis below names a commit and a mechanism; none has
> been demonstrated by an A/B arm. A fix lane MUST reproduce the site with
> `tools/v2_solve_replay.py --capture/--replay --probe-site LAT,LON` and
> measure the arm before editing.

Rows: CYXY-1, CYXY-2, CYXY-3, SPJC-1, SPJC-3 of
`/Users/noah/XPTerrainBuilder/docs/BETA2-BLOCKERS.md`.

## Evidence inventory (patches / sidecars found)

(filled in below as discovered)

### CYXY patch generations (md5 of `Patches/+60-140/+60-136/CYXY_auto.patch.osm`)

Worktree copies are seeded by `lane_worktree.sh`, so their mtime is a COPY
date; the content is whatever main's tree held at that moment. Three distinct
bodies exist on this machine:

| gen | md5 | ways | seen from → | vocabulary |
|-----|-----|------|-------------|-----------|
| A | `21c45d0622873d589e530e4a1f703136` | – | ≤ 2026-08-28 | v1 |
| B | `c5f49b4ea2de22aa2dbdeed6492e137c` | 480 | 2026-09-03 … 2026-09-15 07:10 | **v1** (`service_junction`, `gap_fill_spine`, `ref=groundside`) |
| C | `21088aa754fb3258f0595b1671dd3f91` | 274 | 2026-09-15 12:41 → now (incl. `Ortho4XP/dist/.../Ortho4XP_Data/Patches`, the frozen engine seed) | **v2** (`ref=dsf:polNNN`, `pav9`, `route6`, `o4_grade_law_cap_t`) |

Newest body C: `/Users/noah/XPTerrainBuilder/Ortho4XP/Patches/+60-140/+60-136/CYXY_auto.patch.osm`
(2026-09-15 12:41). Oldest "was before" body B (last copy):
`/Users/noah/XPTerrainBuilder/.claude/worktrees/kind-wiles-54dadf/Ortho4XP/Patches/+60-140/+60-136/CYXY_auto.patch.osm`.

**The CYXY bracket is the v1 → v2 engine cutover, not a one-line commit.**
Every "was previously" CYXY state below is a *v1-engine* state.

## CYXY-1 — 60.7125349, -135.0753244

**Now (gen C).** The point is INSIDE way `-10106`
`{aeroway=apron, ref=dsf:pol123, role=apron, shapeID=101}`, area ~5,074 m².
The only service-road geometry near it is two slivers —
way `-10219` `{ref=route6, role=service_road, shapeID=212}` ~5 m² at 3.1 m and
way `-10218` `{ref=route4, role=service_road, shapeID=211}` ~10 m² at 13.5 m.
That is verbatim the owner's "two road slivers, rest apron".
Nearest groundside is way `-10088` `{ref=dsf:pol118, role=groundside_pavement,
class=parking_lot, o4_grade_law_cap=0.05, shapeID=83}` at 21 m.

**Before (gen B, v1).** The point was INSIDE way `-10286`
`{ref=groundside, role=groundside_pavement, shapeID=285}`, area ~12,147 m²,
with a real service road way `-10254` `{role=service_road, shapeID=253}`
(160 m², i.e. 16-32x the gen-C slivers) at 10.4 m, and the apron
(way `-10034`, 112,447 m²) 35.6 m away.

So: one ~12,000 m² groundside slab + a 160 m² road became a 5,074 m² **apron**
polygon carrying `ref=dsf:pol123` + two ≤10 m² road slivers.

Key signal: in gen C the polygon is identified by `dsf:pol123` — it is a
polygon read out of the **airport pack DSF**, not an OSM groundside union.
The v2 classifier assigned it `role=apron` while its neighbour `dsf:pol118`
(21 m away) got `groundside_pavement / class=parking_lot`. The regression is
therefore a **v2 DSF-polygon role decision**, not loss of the road feature:
the road survives (route4/route6) but is cut down to slivers because the
surrounding slab is apron rather than groundside.

### CYXY-1 adjacency (gen C, measured from the emitted rings)

Polygon-to-polygon shared boundary (not point distance):

| face | shares with | metres |
|------|-------------|--------|
| `dsf:pol123` (shapeID 101, **apron**) | `pav9` shapeID 84, **apron** 94,045 m² | **8.1** |
| | `route4` shapeID 211 service_road (10 m²) | 47.5 |
| | `route6` shapeID 212 service_road (5 m²) | 20.3 |
| | `dsf:pol20` shapeID 213 **apron** (809 m²) | 116.1 |
| | `dsf:pol17` shapeID 214 **apron** (6,571 m²) | 22.2 |
| `dsf:pol20` (213) | **only** `dsf:pol123` | 116.1 |
| `dsf:pol17` (214) | **only** `dsf:pol123` | 22.2 |

`dsf:pol17 + dsf:pol20 + dsf:pol123` = 6,571 + 809 + 5,074 = **12,454 m²** —
the same three pages, and the same ~12,466 m², that owner ruling
**2026-09-04u** names verbatim in
`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/classify/open_default.py:11`:

> "Measured CYXY (04u): dsf:pol17 + pol20 + pol123 (12,466 m², no taxi, no
> startup, no apron name) defaulted to APRON, airside, while they are the
> parking lots 1206 route 50 climbs to from the apron."

04u exists precisely to make these three groundside, and `default_open_role
= "groundside_pavement"` (rules.toml:81) still says so. They are apron
again. So the 04u default is being **overridden downstream**, and there is
exactly one pass that overrides it.

### CYXY-1 — hypothesis (ATTRIBUTION, not measured)

**§27 the airside-edge flip, iterated to a fixpoint.**
`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/classify/airside_edge.py`, `airside_edge_flip()`. Its own docstring:

> "Flips PROPAGATE — a lot beside a road that became apron is beside apron —
> so the pass iterates to a FIXPOINT".

Named commits (both on main, both 2026-09-12):

- `05ea3bbf` — "§27: an airside edge makes a lot (and a road) airside —
  RULINGS 2026-09-12c/12e/12f" (introduces the pass)
- `a1daa7d5` — "§27 round 2: the class widens to **groundside_pavement**;
  the tunnel-ramp regression is refuted (RULINGS 2026-09-12i)"
  — this is the commit that put 04u's own default role
  (`groundside_pavement`) into `_AIRSIDE_EDGE_CANDIDATES`, i.e. that made
  the 04u verdict itself flippable.

Mechanism as read from the code (each step still to be measured):

1. `dsf:pol123` is a §27 candidate (role `groundside_pavement` or
   `parking_lot` after 04u).
2. Its lateral airside contact with `pav9` reads **8.1 m exact** in the
   emitted rings — *below* `lot.airside_edge_min_m = 10.0` (rules.toml:69).
   But `_lateral_airside_m` measures **weld-tolerant**: it buffers each
   airside boundary by `emit.identity.weld_spacing_m` and unions the
   contacts, deliberately over-reading the exact figure (its own comment:
   "exact boundary coincidence under-reads ... by ~30 %"). The two road
   slivers `route4` (47.5 m shared) and `route6` (20.3 m) lie ON that same
   pol123/pav9 edge; under a weld buffer they do not break the run. **The
   8.1 m → ≥10 m crossing is the thing to measure first.**
3. pol123 flips to `apron`. On the NEXT fixpoint round `dsf:pol20`
   (116.1 m of shared edge with it) and `dsf:pol17` (22.2 m) flip too —
   neither touches any other airside face at all, so they can only have
   flipped off pol123. That is the cascade the owner sees as "rest apron".
4. `route4` / `route6` are STRIP-class (born road), so §37 (2)
   (`road_airside_edge_frac = 0.2` of perimeter, commit `c632622d`) spares
   them — they survive as `service_road`, at 5 and 10 m². **The "two road
   slivers" are the §37 (2) exemption working; the apron around them is the
   §27 cascade.**

Why the owner's "was before" has no §27: gen B is v1-engine output.
`airside_edge_flip`'s docstring records that v1 had the first half of this
rule as the AIRSIDE-ADJACENCY VETO
(`auto_patch/junction_repair.py:2752-2789`, owner 2026-07-27) — v1 had the
veto but **no fixpoint propagation**. The regression is the propagation
plus the widened candidate class.

**Interventional test a fix lane must run (no build needed):**
`tools/v2_solve_replay.py --capture CYXY --out DIR` then
`--replay DIR/CYXY.pkl --from classify --probe-site 60.7125349,-135.0753244`,
and the classify explainer added in `01968aca` (`--by-ref` / `--why-at`) on
`dsf:pol123`. The flip records its own evidence keys —
`airside_edge_m`, `airside_edge_round`, `airside_edge_was`,
`airside_edge_flip` — set in `airside_edge.py`. (They are NOT written to
the `.axes.json` sidecar: checked, zero occurrences. Only a replay shows
them.)

Cheap falsification: if `airside_edge_round` is 1 for pol20/pol17 too, the
cascade story is wrong and something gives all three faces direct apron
evidence (`open_default.apron_evidence`, e.g. `lot.apron_cover_fraction =
0.1`, touched by `57cf0d74` / `f02bb08f`, both 2026-09-11) instead.

**Caveat on the bracket:** gen C was emitted 2026-09-15 12:41; beta 1 is
build 350 (2026-09-18). Two later classify commits are inside that window
and could have moved CYXY again: `5340dcd7` (2026-09-14, §43 apron neck
cut) is before gen C, but `dabbda82` (2026-09-17, "§43 (1) AMENDED: a
pavement arm that follows a path and is under 50 m wide is a taxiway") is
AFTER it. gen C is the closest available proxy for what the owner flew, not
a copy of it.

## SPJC — the evidence limit (read this before trusting anything below)

**Every `SPJC_auto.patch.osm` on this machine is the SAME body**,
md5 `377b0e971de3fd7ce96f251aaaf6c8d9`, oldest copy 2026-07-25 17:37
(`/Users/noah/XPTerrainBuilder/.claude/worktrees/build-kill/Ortho4XP/Patches/-20-080/-13-078/SPJC_auto.patch.osm`);
every later worktree copy, and the frozen-engine seed under
`Ortho4XP/dist/Ortho4XP/_internal/Ortho4XP_Data/Patches/`, is byte-identical.
It is a **v1-engine** patch. SPJC has not been rebuilt in this tree since
2026-07-25.

Consequence: for SPJC-1 and SPJC-3 I can measure the "**was before**" state
exactly, and the "**now**" state **not at all**. The now-state attribution
below is code-reading only. A fix lane must capture SPJC first
(`tools/v2_solve_replay.py --capture SPJC`) — that capture does not exist
either (`tools/harness/frames.py list SPJC`).

### SPJC-3 — tunnel mouths, the "before" state (v1 patch, measured)

Both owner coordinates sit on emitted tunnel geometry:

- `-12.0326702, -77.115129`: way `-10532` `{ref=tunnel_wall,
  role=retaining_wall, shapeID=531}` at 1.3 m, way `-10524`
  `{ref=tunnel_ramp, role=tunnel_ramp, shapeID=523}` (151 m²) at 3.0 m.
- `-12.0325443, -77.1148715`: way `-10523` `{ref=tunnel_wall,
  role=retaining_wall, shapeID=522}` (315 m²) at 0.5 m, way `-10513`
  `{ref=tunnel_ramp, role=tunnel_ramp, shapeID=512}` (148 m²) at 2.2 m.

So the "were emitted" claim is confirmed: a `tunnel_ramp` + `tunnel_wall`
pair per mouth, ~150 m² and ~230-315 m². The four ramps 512/513/523/524 and
two walls 522/531 form the two mouths of one tunnel.

### SPJC-1 — building13, the "before" state (v1 patch, measured)

`-12.0256285, -77.1076771` is INSIDE way `-10032`
`{aeroway=building, ref=building32, role=building, shapeID=31}`, area
**48,488 m²** — one single footprint covering the whole terminal, nearest
apron 30.9 m away. The owner now sees `building13` as "one tiny end of a
terminal". So the regression is **one 48,488 m² body becoming many bodies,
of which only a small one carries a pad** — a v2 body/cluster split, not a
lost building.

### SPJC-3 — hypothesis (ATTRIBUTION, not measured)

The v2 tunnel pass refuses bores, by name, with a reason string. The whole
attribution surface is `stats.refused` in
`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/planar/structures.py`
(published as `tunnels_refused`, structures.py:994) — a replay prints the
exact sentence that killed SPJC's tunnel. **Do that before believing any of
the below.**

Three gates landed between the v1 patch (2026-07-25) and beta 1
(build 350, 2026-09-18) that can delete BOTH mouths at once. In likelihood
order:

1. **`eab1a904` (2026-09-16) — §34 (12) (5), owner RULINGS 2026-09-16d:
   "a bore that enters a building or passes under nothing at grade is not a
   terrain tunnel".** Implemented as `terrain_tunnel_witness()` in
   `/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/planar/structure_service.py:43`.
   A bore is now built only on one of four witnesses — classified cover for
   `terrain_cover_min_m`, a road/railway crossing its interior AT GRADE,
   the DEM standing `terrain_rise_m` (0.5 m, `law/structures.toml:61`) over
   it, or `layer <= terrain_layer_max`. It was written for VMMC's car-park
   ramps ("There should be no tunnels cut at VMMC…", owner 2026-09-16). Its
   refusal sentence is literally `"bore … PASSES UNDER NOTHING AT GRADE"`.
   **This is the newest gate, it is in build 350, and it is the only one of
   the three whose whole purpose is to delete tunnels the previous code
   built.** If SPJC's bore is an unlayered service/road bore whose cover is
   a pavement the v2 classifier no longer calls cover, it dies here.
2. **`eae06307` (2026-09-15) — §34 (12) (1)/(3) "a tunnel serves the field
   or is not built; a corridor never cuts airside pavement".** The
   admission-by-mouth region (`field_region_for`, structures.py:196) plus
   the airside role set a corridor may not cut
   (`structure_service.py:225-294`). Kills a bore whose mouths fall outside
   the field region, or whose ramp would cut airside pavement.
3. **The amplifier that explains why the owner sees BOTH mouths gone
   rather than one:** structures.py:896-904 — "A LEVEL CORRIDOR IS BUILT
   WHOLE OR NOT AT ALL (Law C, spec §6a row 15)": a half whose sibling was
   refused is refused too. In the v1 patch the two mouths are exactly such
   a pair (ramps 512/513 at one mouth, 523/524 at the other; walls 522 and
   531). **One gate firing on one half removes the whole tunnel** — which
   is what "tunnel mouths gone" (plural, both coordinates) looks like.

Note the sibling row is also why SPJC-3 and blocker **OTHH-1** ("no tunnel
exists at 25.2575296, 51.6120308; extra tunnels emitted around the
groundside") are probably NOT one mechanism: OTHH-1 is over-admission,
SPJC-3 is refusal. They meet only in the §34 (12) (5) witness set (too
loose at OTHH, too tight at SPJC). A fix lane should read both from the
same `stats.refused` / witness-reason dump.

## CYXY-2 and CYXY-3 — the owner's two sites are NAMED IN THE LAW FILE

This is the strongest result in this document.

Measured in gen C, the face containing each site and its neighbours:

- **CYXY-2** `60.7141907, -135.0766528` → way `-10081`
  `{ref=pav4, role=groundside_pavement, class=parking_lot,
  o4_grade_law_cap=0.05, shapeID=79}`, 4,981 m²; `building9` (shapeID 103,
  4,471 m²) 0.39 m away; service roads `pav0` (7.4 m shared) and
  `dsf:pol23` (86.3 m shared).
- **CYXY-3** `60.7155636, -135.0792452` → way `-10090`
  `{ref=dsf:pol129, role=groundside_pavement, shapeID=85}`, 1,542 m²;
  `building10` (shapeID 104, 749 m²) 0.74 m away. **It touches nothing
  else at all.**

Those are exactly the two pairs in the §28 (6) law table,
`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/law/emit.toml:530-547`:

```
#   CYXY  building9  -> pav4         +3.76   DISARM (the owner's 13l item 1:
#   CYXY  building10 -> dsf:pol129   +3.43   DISARM   cut into the hillside,
#                                                     the lot a storey up)
#   LEMD  building4  -> pav124       +3.00   ARMED
...
frontage_step_max_m = 3.2
```

So the mechanism is **§28 THE GROUNDSIDE FRONTAGE TAKES THE PAD'S EDGE
LEVEL** (`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/constraints/pad_frontage_gs.py`),
landed `fe0299dd` (2026-09-12, RULINGS 2026-09-12r "grade frontages only"),
and its **§28 (6) hillside-terrace exemption**, `b973d8d3` + `37dac595`
(both 2026-09-13) — whose own commit subject is
*"§28 (6) MEASURED: CYXY's two hillside lots back on the DEM"*.
**The owner is reporting that CYXY's two hillside lots are NOT back on the
DEM.** `pad_frontage_gs.py:216` states the intent verbatim: grading these
lots to the pads "made `dsf:pol129` a 3.4 m excavation it can never climb
out of at its 8 % cap".

The exemption is a per-pair bound on the MEDIAN DEM STEP between the face's
frontage vertices and **the pad footprint's own median `dem_z`**, and
`3.2` sits in a 3.00-3.43 gap — 0.23 m wide. Two things can put these pairs
back under it:

1. **The pad footprint changed.** The §28 (6) numbers were measured
   2026-09-13, on the footprint-cache pad. The **§16g (10) cluster-pad
   campaign landed AFTER** — `f71fca86` "THE PAD IS THE CLUSTER" and
   `ad8b5120` "LEAVES GET NO PAD" (2026-09-14), `01724ef4` "only a WALLED
   body chains" (2026-09-14), `c61da98e` / `59dd0aed` (2026-09-15),
   `dba32406` (2026-09-16). A pad derived from a CLUSTER covers different
   ground from `building9` / `building10`'s own footprint, so its **own
   median `dem_z` is a different number**, and the step it is compared
   against moves. A pad extending downhill lowers the pad median and drops
   the step under 3.2 → the pair arms → the lot is pulled to the pad. The
   pad in turn follows the apron under §20, which is why the owner sees the
   lot "flat with the apron" rather than flat with the building.
2. **The DEM frame.** emit.toml:541-545 warns the same pairs read
   **+4.5 / +4.7** on an emitted patch versus +3.76 / +3.43 in the engine's
   own frame, because the production DEM is smoothed (CYXY inset HRDEM 1 m,
   radius 1 px) — "quote the frame with the number". Any change to the
   CYXY inset, its smoothing, or `--allow-degraded-dem` moves both pairs
   across a 0.23 m gap. The owner's "DEM ~2 m higher" is the residual, not
   the step.

`pairs_held_as_terrace` is published in `STATS["groundside_frontage_level"]`.
**The whole diagnosis is one replay away and needs no build:** capture CYXY,
replay from the constraint stage, read `pairs_held_as_terrace` and the two
pairs' measured `pair_dem_step_m`. If `building9 -> pav4` and
`building10 -> dsf:pol129` are no longer ~+3.76 / +3.43, hypothesis 1 or 2
is confirmed by which input moved. CYXY-2 and CYXY-3 are **one mechanism**,
as the blocker row guessed.

Note CYXY-3's face `dsf:pol129` carries **no** `o4_grade_law_cap` tag while
CYXY-2's `pav4` carries `0.05` — worth a second look (the 8 % cap the
comment cites is not on the emitted face), but it is a separate question
from what pulls it.

## SPJC-1 — hypothesis (ATTRIBUTION, not measured)

"Was built before" = the v1 patch's single `building32` ring, **48,488 m²**
(measured above). The v2 pad is no longer a footprint: **THE PAD IS THE
CLUSTER** (`f71fca86`, 2026-09-14, §16g (9)-(10)), derived in
`/Users/noah/XPTerrainBuilder/Ortho4XP/src/auto_patch_v2/geom/cluster_outline.py`.
That function has five ways to give a terminal "one tiny end" of a pad, each
with its own counter in the `counts` dict it returns (cluster_outline.py:122):

- `leaf_dropped` — §16g (10) (7) **LEAVES GET NO PAD** (`ad8b5120`,
  2026-09-14): a pad is minted only for a WALLED cluster, one holding a body
  whose solid height reaches `chain_min_height_m`. Measured at HECA:
  **359,152 m² in 1,518 pads are LEAVES**. A terminal read as slabs/decks/
  canopies plus one walled end mints a pad for the walled end ONLY — which
  is exactly "one tiny end of a terminal".
- `over_another` — rule 3: clusters take ground LOWEST FLOOR FIRST and each
  one's overlap with ground already taken is SUBTRACTED; a cluster left with
  nothing mints no pad.
- `on_airside` — rule 4 (§16g (10) (5), `01724ef4`): airside is subtracted
  from every outline. SPJC's terminal stands 30.9 m from a 73,025 m² apron
  in v1, so this is a live candidate for the lost area.
- `under_min_m2` — `cluster_pad_min_m2`.
- `still_in_pieces` / `clipped`.

Plus `01724ef4` "only a WALLED body chains": the chaining rule decides
whether the terminal is ONE cluster or many. If the terminal's parts do not
chain, each part is its own cluster and the owner gets per-component pads at
different levels — which is **blocker SPJC-2** (central terminal, "components
seated at different levels, float") at the same airport. **SPJC-1 and SPJC-2
are very likely one mechanism**, and both are the same family as HECA-1
(nested building20's) and HECA-2.

Instruments (no build): the `counts` dict above, and the sidecar keys
`cluster_pads` + `pad_cluster_mismatch` which are already published in
`*.axes.json` (both present in the CYXY sidecar — confirmed). A fix lane
captures SPJC, replays the planar stage, and reads which counter absorbed
the terminal's 48,488 m².

## Summary of named commits (all ATTRIBUTION)

| row | mechanism | commit(s) | date |
|-----|-----------|-----------|------|
| CYXY-1 | §27 airside-edge flip, iterated to a FIXPOINT; candidate class widened to `groundside_pavement` so the 04u open default is itself flippable; cascade pol123 → pol20 → pol17 | `05ea3bbf`, **`a1daa7d5`** | 2026-09-12 |
| CYXY-2, CYXY-3 | §28 (6) hillside-terrace exemption no longer holding the two pairs the law file names by name (`building9 -> pav4`, `building10 -> dsf:pol129`), most likely because the §16g cluster pad changed the pad median the 0.23 m-wide bound is measured against | §28: `fe0299dd`; §28 (6): `b973d8d3`, `37dac595`; pads: **`f71fca86`, `ad8b5120`, `01724ef4`, `c61da98e`, `59dd0aed`, `dba32406`** | 09-12 … 09-16 |
| SPJC-1 (and SPJC-2) | pad = cluster; LEAVES GET NO PAD / `over_another` / `on_airside` leave one walled end of the terminal padded | **`f71fca86`, `ad8b5120`**, `01724ef4` | 2026-09-14 |
| SPJC-3 | §34 (12) (5) terrain-tunnel witness refuses a bore that "passes under nothing at grade"; Law C then takes the sibling half, so both mouths vanish together | **`eab1a904`** (09-16), `eae06307` (09-15); amplifier `structures.py:896-904` | 09-15 … 09-16 |

None of these is an interventional measurement. Each row names the counter
or evidence key that settles it in a single `v2_solve_replay` replay.
