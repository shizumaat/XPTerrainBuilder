# The airside beside a flat-built terminal group is held at the group's level (spec, round 1: picture before code)

Owner ruling Q370 (#1717; RULINGS 2026-11-03b, the two-level model), Noah,
2026-11-03T10:47:23Z, chose **(a)**: "Next to a terminal whose pack is built
flat, should the airside be: a) held flat at the terminal's own level, as in
your patch, so the lower level stays 7 m under it and the terminal's objects
stay seated".

Status: SPEC + dry A/B + pictures. No engine code (owner Q347: section views
first, code after his yes). Lane flatA, base origin/main 0702f0e7b.

## 0. Summary

- **The defect (attributed by lane attr-land).** The LFPG T2 pack is authored
  flat: the stand-side walls of 2A to 2F have feet at y -0.5 to 0.0 and the
  lower storey at y -7.07, across the whole terminal. The object stage seats
  the group at ONE zero, 104.79 m, read off the 2A-2D stands (RULINGS 23e).
  The airside, though, follows the survey. East of lon 2.585 it lies at
  about 100.3 m, 4.5 m under the zero, so the 2E/2F objects float. The lower
  level is tied to the zero (23f), which is why the step shrinks from 7.5 m
  to 1.5 m at building64/p3.
  - Mechanism: `constraints/group_level.py:102,162-164` and
    `planar/low_extent.py:164` hold the lower level at the zero.
  - But `constraints/platform.datum_groups` gives each of T2's held blocks
    its own datum (at LFPG today there is one datum group, of 2 blocks).
  - Each block's datum follows its own apron
    (`constraints/platform.py:599`, `no_step.hold_interval`).
- **The rule.** The held blocks of a flat-built terminal group take ONE
  datum, and their fronting apron is held at it. This extends the existing
  law "one connected complex, one level" (RULINGS 2026-10-10n (1),
  2026-10-12l (1)) to the object stage's one-zero group. There is one
  derivation site, `constraints/platform.datum_groups`.
- **The finding the owner must see.** Holding T2 at today's zero (104.79)
  breaks grade law.
  - South of 2E/2F, runway 08R/26L lies at 96.96 m, 315-342 m from the held
    zone.
  - Reaching 104.79 from it takes a 2.3 % climb, over the 1.5 % apron and
    taxiway cap. Runway first (Q311) means the runway does not move.
  - The highest lawful level for the whole group is **101.67 m** with the
    whole fronting apron held, or 102.09 m with only the stand zones held.
    That is 3.1 m under today's zero and 1.3 m under the owner's 103.
- **Where else it fires.** Of the six registered captures, the rule fires at
  LFPG T2 (58 held blocks) and at KATL's international terminal F (7 blocks,
  today 299.3 / 302.3). It does not fire at KBNA, EGLL, KPHX or KBWI.

## 1. The witness: a flat-built group (no airport literal)

A **group** is the object stage's one-zero group, read at planar time.
- It is the pack partition's grounded parts, from every unit, with line and
  scatter parts left out.
- The parts are chained by footprint ring within `[placement] touch_m`
  (1 m). This is the 22o relation `open_frame_seat` applies, and it also
  covers 23e's cross-unit merge.
- A held block belongs to the group whose chained footprints overlap its pad
  most.

The group is **flat-built** when its stand-side walled feet meet all three
tests below. These are the feet the object stage reads the zero on
(`airside_group_seat.airside_zeros`): on or within 1 m of rolled-on
pavement, within `STAND_M` (60 m) of an apt.dat stand or jetway, and
walled.

1. There are at least `PLANE_MIN_FEET` (20) of them.
2. More than 90 % of them lie within `PLANE_BAND_M` (1.0 m) of their
   `floor_plane`. This is 20x's "greater than 90 % at one level", read on
   the group's own frontage.
3. The survey under them has real relief: p95 - p5 over the DEM class's
   `flat_site.detector.relief_floor_m` (2.0 m on lidar). This is the same
   relief gate as `airport/flat_pack`; on flat ground there is nothing to
   do.

Every constant above already exists. No new law value is added.

How this relates to the whole-pack verdict (RULINGS 20ad, "whole pack"):
- LFPG's pack reads `follows_terrain`: 62.8 % of objects stand at one level,
  under the 90 % bar.
- The group witness is deliberately narrower. 20ad decided terracing, which
  is a groundside matter.
- The master should confirm that a group verdict is not barred by 20ad
  (O-F3).

## 2. What it holds

- **(H1) One datum.** Every held block of a flat-built group goes into ONE
  `datum_groups` entry, through the existing hard tie
  `datum_group_rows: z[dv_b] - z[dv_lead] = 0`.
  - Each block's existing welds, plateau and flat-pad rows then put the
    whole group's frontage on one level.
  - The lead is the block carrying the most stand-side feet (23e's winner).
- **(H2) The fronting apron.** Each block's plateau (the stand zone, spec
  v2 §3) is held at the datum, as today.
  - A flat-built group also holds the rest of every apron body its plateaus
    were cut from: `reg.plateaus[b]["apron_refs"]`, read where
    `planar/pad_cut.plateau_cut` publishes it.
  - The owner's patch holds the whole T2 apron flat, and this is that
    reading.
  - Holding the plateaus alone leaves the apron between the stands on the
    survey. West of 2.570 that means drops of 2-4 m to the stands (the
    plateau-only variant in §4).
- **(H3) The level.** The datum is a free column (2026-10-02ah (1)).
  - Its soft preference is the lead block's own frontage level, which is
    the group's zero.
  - The hard caps bound it: 12l (1), "pads are seated so the aprons can
    reach them within grade law".
  - Where the zero lies outside the lawful interval, the solve lands at the
    interval's nearest end. Welds and caps stay feasible, so no weld is
    relaxed.
  - No new mechanism is needed. The member blocks' own preference Bands are
    dropped and they follow the lead (23e: "every other share takes it").
- **(H4) Beyond the held zone.** The existing laws apply, and nothing new:
  - apron 1.5 % hard, 1 % preferred (06w);
  - the taxiway caps, and 30 m of curve per 1 % of change (10-15l);
  - runway first (Q311);
  - the 5 % pavement ceiling.
- **(H5) The lower level.** It stays at the group's zero + `y_feet` (23f,
  `constraints/group_level`). That is now the flat level - 7.07 m, a
  vertical step at its riser (Q341 a). No change.
- **(H6) The objects.** The object stage reads the zero off the now-flat
  frontage. Every stand-side foot reads the same plane, so the group sits
  at the held level. No change to `airside_group_seat`.

## 3. Consumer census (RULINGS 2026-08-30l): every pass that reads a held block's datum, plateau or group zero

| # | pass | reads | ruling |
|---|---|---|---|
| 1 | `constraints/platform.datum_groups` | plane entries of `cluster_pad.plane_groups` | **THE ONE EDIT SITE**: add the flat-built group (§1) as a second plane-entry source, and its lead |
| 2 | `constraints/platform.datum_group_rows` | groups -> hard ties | unchanged |
| 3 | `constraints/no_step.hold_interval` | per-block D preference Band, reach Bands, misfit/widened | the members' preference Bands are dropped (lead only); reach Bands per block as today; report `flat_group` per block |
| 4 | `constraints/platform.frontage_hold_rows` / `hold_row` | welds to D | unchanged |
| 5 | `planar/pad_cut.plateau_cut` | stand zone | unchanged; already publishes `apron_refs` |
| 6 | the plateau rows / `model/platform.plateau_vertices` | plateau vertices held at D | for a flat-built group, extended to the vertices of its fronting apron bodies (H2); still ONE accessor |
| 7 | `constraints/group_level` (rows + rewrite) | the witnesses' `airside z - y` | unchanged; on a flat frontage every witness reads the held level |
| 8 | `planar/low_extent.extend_levels` | the host's group zero | unchanged; see D-p3 (§5) |
| 9 | `airport/airside_group_seat.airside_zeros`, `open_frame_seat.unchained_links` | the solved airside | unchanged; winner and members now read one plane |
| 10 | `constraints/door_pad`, road terrace (10-03b), between-levels road (29x), reach seed (27a (11)), `road_ramp` | the bordering pavement level | unchanged; groundside adapts (23e) |
| 11 | deck bridges (H1/H2 forecourt, H8-H14 taxiway decks), 30a flush | the taxi surface at the end lines | unchanged; a deck stays flush to what it lands on |
| 12 | tunnels / mouths / level B (11-03b ladder; b2lvl S2 not on main) | level A beside | unchanged; read after the solve |
| 13 | runway projection (09y), runway first (Q311) | runway columns | unchanged; this is the binding constraint (§4) |
| 14 | `constraints/flat_site` (flat-site datum Z0) | the flat-site region | not active where a group is flat-built (relief over the floor rules out `flat_candidate`); no interaction on the six captures |
| 15 | `airport/flat_pack` (phase 1, report only) | the whole-pack verdict | unchanged; the group verdict is reported beside it on the `[flat-pack]` line |
| 16 | census: `airside_no_step`, `frontage_near_miss`, `pad_flat`, apron and taxi caps; 23d's "< 1 m airside movement" | the graded surface | the hold moves airside 1-6 m by ruling (Q370 a); 23d's bar does not apply to a ruled hold, and the report names it |

## 4. Dry A/B and the lawful level (no engine code)

Method. The scripts are in `/private/tmp/claude-501/flatA/`.
- `dryab2.py` reads each registered capture's pack partition, planar map
  and stands, and forms the §1 groups and witness.
- `export.py` / `export2.py` export T2's pads, plateaus, lower levels and
  fronting apron.
- `plan.py` is a raster prototype on the master's 4 m LFPG grids (b2lvl
  scratch: the owner patch, 1.0.454, and "today" = the main 5544d9568
  control replay of `lfpg6/LFPG.pkl`).
  - It holds the zone at Z0.
  - It blends the airside beyond along the cone `clip(today, Z0 +/- 1.5 % * d)`.
  - It holds the runways, and sets the lower levels at Z0 + `y_feet`.
- The lawful interval of one flat level is
  `[max(rw - 1.5 % d), min(rw + 1.5 % d)]` over the runway cells.

**Witness on six captures.**

| airport (capture) | groups with 2 or more held blocks | flat-built | plane share / relief | today's block datums |
|---|---|---|---|---|
| LFPG (lfpg6) | 2 | **1: T2, 58 blocks, 481 stand-side feet** | 0.992 / 4.56 m | 100.15 - 106.1 |
| KATL (b1661) | 7 | **1: terminal F (lon -84.418), 7 blocks, 229 feet** | 0.991 / 4.02 m | 299.33 (building46) - 302.33 (building39) |
| KBNA (ldeck5) | 1 | 0 | 0.992 / 0.54 m (flat ground) | - |
| EGLL (lpackcut EGLL_r3) | 4 | 0 | 0.93-1.0 / 0.67-1.30 m | - |
| KPHX (b2lvl) | 1 | 0 | 1.0 / 0.58 m | - |
| KBWI (b1742) | 2 | 0 | 0.199 (two planes, y -6.15 and -0.28) / 3.23 m | - |

KATL's concourses T to E are one pack frame, but each concourse is its own
group: they are not chained within 1 m. The rule therefore leaves them at
their own levels, 308.95 down to 305.23, as today. Reading by frame instead
of by group would tie them across 3.7 m, so that reading is refused.

**LFPG T2, three variants.**

| variant | held | lawful interval | level | held surface moved > 0.5 m | blend beyond | fill / cut | runway cells breached |
|---|---|---|---|---|---|---|---|
| as asked: zero 104.79, whole fronting apron | 154 ha | [98.72, 101.67] | 104.79 | - | 7.1 m max, 391 m reach | 3.9 / 0.6 Mm3 | **2,934 (08R/26L, lat 48.9973-48.9984, lon 2.585-2.599)** |
| **PLANNED: whole fronting apron (H2)** | 154 ha | [98.72, 101.67] | **101.67** | 130 ha (-6.2 to +4.4 m) | 6.2 m max, 333 m reach | 0.6 / 4.2 Mm3 | 0 |
| stand zones only (plateaus) | 62 ha | [96.91, 102.09] | 102.09 | 44 ha (-4.3 to +4.8 m) | 5.1 m max, 372 m reach | 0.6 / 2.2 Mm3 | 0 |

- The binding cell is runway 08R/26L at 48.9981, 2.5942 (z 96.96), 315 m
  from the held zone.
- West of lon 2.583 alone, the lawful interval reaches 106.21. Only the
  2E/2F side binds, at 102.09 m or less.
- The owner's own patch breaks the same cap there. His 103 apron edge at
  49.0011 meets the unpatched taxiway (97.3 m) about 70 m to the south.

**Site numbers.**

| site | owner | today | PLANNED 101.67 | as asked 104.79 |
|---|---|---|---|---|
| 2E/2F south apron (49.0022, 2.5920) | 103.00 | 100.27 | 101.67 | 104.79 |
| 2E/2F north apron (49.0070, 2.5920) | 103.00 | 101.31 | 101.67 | 104.79 |
| 2A-2D apron (49.0020, 2.5750) | 103.00 | 104.80 | 101.67 | 104.79 |
| T2 corridor west (49.0040, 2.5650) | 96.00 | 106.20 | 101.67 | 104.79 |
| building64/p3 lower level (49.00554, 2.59827) | 96.00 | 100.86 | 94.60 | 97.72 |
| taxiway south of 2E (49.0004, 2.5900) | - (mesh) | 97.74 | 101.18 | 103.72 (over cap) |
| runway 08R/26L (48.9981, 2.5942) | - | 96.96 | 96.96 | 96.96 |

Wherever the lower level fronts T2's own held apron, the planned step from
level A is 7.07 m.

The T2 window (lon 2.540-2.605, lat 48.996-49.016), measured against the
terminal level:

| surface | at level (within 0.5 m) | 0.5-5 m under | lower (5 m or more under) | above |
|---|---|---|---|---|
| owner | 56 % | 3 % | 35 % | 7 % |
| today | 11 % | 41 % | 19 % | 30 % |
| PLANNED | 39 % | 17 % | 7 % | 37 % |

The owner's remaining lower level (the central corridor, Roissypole and
north 2E/2F) belongs to the regions round (the two-level-regions spec,
S1/O1), not to this rule.

## 5. Where the rule and the owner's patch disagree

- **D-level.** Planned T2 stands at 101.67, against the owner's 103 and
  today's zero of 104.79.
  - The 2A-2D halls and their objects drop 3.1 m, with up to 6.2 m of cut
    where the survey stands at 107.
  - 2E/2F rise by up to 4.4 m.
  - Under grade law and runway first, the group cannot stand any higher.
    The owner's patch reaches 103 only by breaking the 1.5 % cap south of
    2E/2F.
- **D-p3.** building64/p3 (49.00554, 2.59827) is a `low_extent` extent of
  building64, but it stands beside the 2G apron. That apron belongs to
  unit 7, a separate frame and group at 100.3, which this rule does not
  hold.
  - Its planned step is 4.9 m (94.6 under 99.5), not 7.07.
  - The extent is tied to T2's zero while it stands beside another group's
    airside. This is how today's `extend_levels` reads it, and it needs a
    ruling (O-F2).
- **D-depth.** Today's solve does not hold some lower levels at their depth:
  building64/p3 reads 100.86 against an intended 97.72. This is the b2lvl
  PR's "Not in this PR (1)".
  - The planned lines draw the INTENDED level, zero + `y_feet`.
  - This rule does not fix that shortfall, and it may or may not remove it.

## 6. Emittability

- Each held zone is one flat polygon set at one height. The existing
  plateau and flat-pad faces already emit that way.
- The blend is ordinary graded apron.
- The lower-level step is the existing riser strip, vertical.
- There is no new shape class, no new face kind and no overlap. Every face
  is a heightfield.

## 7. Owner questions this raises (for the master to number)

- **O-F1 (D-level).** T2 cannot be held at its objects' current level,
  104.79, without breaking the 1.5 % airside cap toward runway 08R/26L. One
  flat T2 is lawful at 101.67 m at most. Should T2 be:
  - (a) held flat at the highest lawful level, 101.67 (recommended)? The
    whole group and its objects move down 3.1 m, and the lower level stays
    7 m under it, at 94.6.
  - (b) held at 104.79, with runway 08R/26L's east part raised about 2.5 m?
    That exceeds Q311's "a little" bend.
  - (c) held at 104.79, with the airside south of 2E/2F allowed up to 2.3 %,
    over the apron and taxi cap, as in the owner's patch?
- **O-F2 (D-p3).** Where a lower-level extent of one group stands beside
  another group's airside, should it sit:
  - (a) 7 m under its own group's level (one level B per group, today's
    tie)?
  - (b) 7 m under the airside it stands beside?
- **O-F3.** Is a per-group flat-built test (this spec) acceptable beside
  20ad's whole-pack verdict? LFPG's pack reads `follows_terrain`, so a
  whole-pack gate would never fire there.
- **O-F4 (KATL).** The rule also ties KATL terminal F's two held blocks,
  today at 299.33 and 302.33, to one level. A section view at KATL F is owed
  before code.

## 8. Not done in this round

- No engine code and no solve of the rule. The planned surface is a raster
  prototype. The real solve may sit lower than 101.67 if a hard row the cone
  ignores binds: a deck, a tunnel mouth, or the vertical-curve rate.
- No KATL section view and no build.
- The groundside roads that meet the moved apron (10-03b terrace, door pads)
  are drawn as they are today.
- Pictures: `/private/tmp/claude-501/flatA/lfpg-flatA-sections.png` and
  `lfpg-flatA-levelmap.png` (lane scratch).

## 9. Owner answers (2026-11-03T13:58:37Z) and round 2 as built: STOPPED at LFPG

Owner, verbatim: "LFPG, recommendations accepted, goals is most accurate
airside with necessary accommodations for poorly modeled airports that
retains correct runways, grade laws, and looks authentic from a pilots
view." Accepted: O-F1 (a), O-F2 (a), and O-F3 (master, per group).

**Built (branch `claude/flatA-spec`).**
- `planar/flat_group.flat_groups` is the §1 witness. It writes
  `held[b]["flat_group"] = {lead, group, feet, share, relief_m, y_plane}`.
- In `planar/pad_cut.plateau_cut`, a flat-built group's blocks hold every
  apron body that they alone touch as a whole plateau (H2).
- `constraints/platform.datum_groups` adds the flat group as an entry,
  keyed by its lead (H1). `skip_flat` withdraws it.
- `constraints/platform.flat_group_level` is the highest lawful level (H3).
  It is the intersection, over the group's blocks, of each block's
  pair-graph interval `I0` and reach intersection. Blocks whose own
  admissible set is empty are left out. The lead's frontage level is
  clamped into it. No new constant.
- `constraints/no_step.hold_interval` sets every member's datum preference
  to that level. A group that no lawful level serves is not tied, and its
  blocks keep their own levels. `_flat_binding` reports the anchor that
  closes each side. Report field `stats.interval.flat_groups`; held field
  `flat_group_level`.

**The engine's own reading at LFPG contradicts §4's raster.** Replay of
`lfpg6/LFPG.pkl` from the planar stage, branch against main 7c18b338b:
- T2 group: 58 blocks, 26 with welds.
- Lawful interval: **[106.08, 100.14], EMPTY**.
- So the tie is withdrawn, and T2's levels stay as they are today:
  0.9 ha moved by more than 0.5 m, from the whole-body plateaus at each
  block's own datum.

The interval closes on two anchors that §4's runway-only cone did not
model:
- **Low side, 106.94 m.** The 2A–2C contact at 49.00331, 2.56468 is one
  hop from a `cutout.sunken_road` pin at 49.00357, 2.56444. This is the
  pinned plate floor of a pack sunken road under the hall (Law B), and its
  height is fixed at planar time. It is a pack object of the T2 group, but
  it does not follow the group's level. This is a consumer the §3 census
  missed: row 17, pack plate-floor pins.
- **High side, 100.14 m.** The 2E/2F south apron contact at 49.00108,
  2.59098 is seven hops from a **tile seam DEM pin** at 49.00007, 2.59008.
  The 49° N tile edge crosses LFPG about 110 m south of the 2E/2F apron.
  The patch has to meet the neighbouring tile's mesh there.

KATL terminal F (replay of `b1661/KATL.pkl`, branch against main):
- Flat group of 7 blocks, lead `building29`. Zero 301.54 m. Lawful
  interval [294.68, 305.36], bound by runway columns on both sides.
- Tied at 301.54. The solved terminal F level moves from 300.80 to
  300.88 m, about 0.1 m. Datum-group rows go from 6 to 16. Aprons beside it
  move −0.10 and −0.15 m.
- Control already held terminal F at one level, through its cluster datum
  group.

Owner questions this raises:
- **O-F5.** With the 49° N tile seam pinned to the survey 110 m south of
  2E/2F, T2 can be one flat level only at 100.1 m or less. That is 4.7 m
  under the objects' level today, and up to 7 m of cut into the 107 m
  survey at 2A–2D.
  - (a) Accept ≤ 100.1. This also needs the pack plate-floor pins to follow
    the group's level (census row 17).
  - (b) Keep T2 as it is today: a flat level where lawful, the rest
    following the survey, and 2E/2F objects about 4.5 m above their apron.
  - (c) Let the patch's tile-seam pin give way inside the aerodrome
    boundary. That is a new seam law, and the mesh must still close at the
    seam.
