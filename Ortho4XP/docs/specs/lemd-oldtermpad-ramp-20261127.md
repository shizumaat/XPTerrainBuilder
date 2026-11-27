# LEMD OLDTERMPAD road step: a short bore left with one mouth (one-miss review, 2026-11-27)

Scout review under RULINGS 2026-11-11c after two Opus rounds missed:
`l588fix` 02e308358 and `llemd2` 9a6cd25ad. No issue number; site
40.4652, -3.5700 (LEMD old terminal, landside frontage roads).
Read-only: nothing here was built. Every number is from the gate JSONs of
the integration tile build or from replays of the registered capture.

## 0. Summary

- The 3.33 m step is the mouth face of **the other end of the same tunnel**.
  `llemd2` refused end `tunnel:-1501@0` (north-east, on road -1503). End
  `tunnel:-1501@1` (south-west, on road -1518) was never refused. It is
  built in the replay and in the tile alike: a 264 m ramp, 7.50 m deep at
  its mouth, along the old terminal frontage road.
- The replay never said that end was gone. `llemd2` read its replay at
  40.466748, -3.570098, which is end @0's site. The step is at
  40.466139, -3.571018, 100 m away, at end @1's mouth.
- Nothing in the tile path differs from the replay (no stage-cache,
  pack-copy or rebake effect): the tile's ramp and the replay's ramp have
  the same mouth nodes and the same floor, 593.97 m.
- The law that fits is already ruled: **2026-11-16h** (a one-mouthed short
  bore is a road at grade) with **2026-09-13bm (ii)** ("a tunnel with one
  mouth is never right"). Its implementation was narrowed on 11-16 to a
  far end refused at a building pad. Today's two refusals (l588, llemd2)
  create a second kind of far end at grade, and 16h does not yet see it.
- Fix: a far end refused by the l588 / llemd2 refusal counts for 16h as a
  pad-refused end does. About 25 source lines in two files.
- LEMD replay with the law applied (monkeypatch, no source edit): two ends
  are withdrawn, `tunnel:-1501@1` and `tunnel:-2487@0`. No tunnel face is
  left within 300 m of the site. Predicted road step within 80 m of the
  site: 0.20 m (the installed control reads the same 0.20 m there).
- **Warning for the gate.** The 300 m OLDTERMPAD site will still read
  FAIL after this fix, at about 0.94 m. That is a different mechanism
  (the rim of pad `building49`, absent from the installed control). The
  gate prints only the worst step per site, so the 3.33 m hid it. See
  §6.3.

## 1. Evidence used

| what | where |
|---|---|
| integration | `origin/claude/project-thread-ddpu46` c0e91ad4f. The tile was built at 21cea197a (`/tmp/harness/l591_LEMD.env.json`). The two differ by 2 lines in `Ortho4XP/tests/test_elevation_ladder_fallthrough.py`: same engine. |
| drawn gate, automatic | `/tmp/harness/l591_LEMD.drawn.json`, `/tmp/harness/l591_LEMD.result.json` |
| drawn gate, with sites | master's run `arm.txt` / `arm.json` in the session scratchpad (`--against` the installed control `ctl.json`) |
| capture | `/Users/noah/XPTerrainBuilderData/.harness/frames/l588fix/LEMD.pkl` (base c91ccefb0, which already holds lpads 6cf8cfd04) |
| replays (this review) | scratch `git archive` of c0e91ad4f, `tools/v2_solve_replay.py --replay … --from planar --emit`: control (`scout/out/ctl.log`, `scout/out/emit_ctl/`) and the law arm (`scout/out/arm.log`, `scout/out/emit_arm/`) |
| mapped roads | `OSM_data` road feed `airport_small_roads`, tile +40-004 (the feed the gate's road layer reads) |

Paths that start `scout/` are under the session scratchpad
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-recursing-brattain-3c19a5/6e5e195e-57b0-4b69-95e2-5b2be3524724/scratchpad/`
(not durable; nothing was registered in `frames.py`).

Not available: the tile's own products. `/tmp/harness/tile_l591_LEMD`, the
l591 worktree's `Patches/` and the pack copy were already deleted, so the
drawn mesh could not be sampled again. "Drawn" below means the gate JSONs.

## 2. Mechanism (question 1)

### 2.1 The mapped road

Way -1501 is `highway=tertiary, lanes=1, layer=-1, tunnel=yes`, 29 m long,
three nodes:

| node | lat, lon | joins |
|---|---|---|
| end 0 (NE) | 40.466223, -3.570719 | tertiary -1503 (113 m, runs NE to apron `pav92`) |
| mid | 40.466165, -3.570891 | |
| end 1 (SW) | 40.466135, -3.571039 | tertiary -1518 (145 m, runs W along the terminal front) |

No mapped bridge crosses it. Tertiary -531 (lanes 1, no bridge or layer
tag) crosses it at mid-length and climbs 600.8 → 605.1 m in the patch: the
map reads as an upper road going over on a bank and the lower road
passing under it level. It is a 29 m underpass, not a tunnel in the
ground. The owner named this place on
2026-09-11 ("Still see a tunnel here: 40.4661521, -3.5708203 where there
should be no tunnel", RULINGS 2026-09-11ao); that point lies on way -1501.

### 2.2 What each round did

1. Before lpads, LEMD's five AESlite sheets were read as trench objects at
   76 of 78 tunnel ends (6cf8cfd04 message). One acted as a pack portal at
   end @0 and refused it (9a6cd25ad message). The installed control (app
   1.0.585) has no tunnel face at either end and reads 0.21 m.
2. lpads 6cf8cfd04 stopped that. Both ends of -1501 opened as plain mapped
   mouths at the 7.50 m ladder depth with 5 % ramps.
3. l589's gate read 4.34 m on -1503 at 40.466703, -3.570135: end @0's ramp,
   clipped 72 m out by apron `pav92`.
4. `llemd2` 9a6cd25ad refused end @0 ("cannot top out before the airside
   pavement pav92 … its mapped road runs on past it",
   `planar/structures.py:1408-1431`). Its replay evidence was read on
   road -1503, at end @0's site (40.466748, -3.570098). End @1 was not
   looked at.
5. End @1 stands. With @0 gone it is the only mouth of a 29 m bore.

### 2.3 Proof that the tile's step is end @1's mouth face

| reading | tile build (gate JSON) | replay at c0e91ad4f (this review) |
|---|---|---|
| ramp face | `tunnel_ramp -11406` at 40.466121, -3.571038 | `tunnel_ramp` way -11399, mouth nodes 40.466121, -3.571038 and 40.466152, -3.571038 |
| ramp floor at the mouth | 593.97 (patch), 594.01 (drawn mesh) | 593.97 |
| ramp relief | 12.89 m | 593.97 → 606.86 = 12.89 m, top at 40.465346, -3.573786 |
| the step point 40.466139, -3.571018 | road step 3.33 m, [600.28, 596.95], way -1501 | planar face 1392, role `retaining_wall`, ref `tunnel_wall`, 1,071 m² (`ctl.log` "PAD READ site"); patch-surface road read 4.67 m at 40.466143, -3.570997, [602.84, 598.17], way -1501 |
| end @0's site 40.466748, -3.570098 | not the worst step | roles apron / building / service_road, step 0.0 m |
| structure lines | (not kept) | `tunnel:-1501@0` refused; no line for `@1`: built. Census: mouth 40.466135, -3.571040, depth 7.50 m, ramp top 264 m out |

- Way ids of patch faces are minted per emit (-11406 in the tile, -11399 in
  the replay). The OSM way id -1501 and the tunnel ids are stable. There is
  no renumbering effect.
- The tile's patch → drawn layer passed at the site run (0 of 53,791 nodes
  over the bars, `arm.txt`), and the drawn mesh reads 594.01 against the
  patch's 593.97 at the ramp's low node. The drawn step is the patch.
- The 3.33 m (drawn) and 4.67 m (patch surface) are the same face read on
  two triangulations: 1 m samples across a wall band about 2 m wide that
  drops from the rim (600.8–603.2) to the floor (593.97).
- The gate's road layer exempts a mouth face only for a mouth a pack
  portal claims (`tools/harness/drawn_roads.py:66-85`). A plain mapped
  mouth's face on its own tunnel way is judged. So this site cannot pass
  while any plain mouth of -1501 stands, one-mouthed or not.

The visible defect is larger than the step: a trench 264 m long, one lane
wide, up to 8.6 m under its rim (rim 602.6, floor 593.97 at the mouth),
along the old terminal's frontage road, and a road that enters it and
comes out at grade 29 m later.

### 2.4 The same defect elsewhere in the same tile

`tunnel:-2487@1` was refused by l588 (crossing road -2490, 60 m out). Its
other end `tunnel:-2487@0` stands: a **10 m** bore (tertiary, layer -1),
mouth 40.469631, -3.573440, 7.50 m deep, ramp 108 m. The tile's gate JSON
lists it as `tunnel_ramp -10961` at 40.469623, -3.573421, floor 598.94.
No judged site covers it. The replay's patch-surface road read there is
4.10 m on way -2487.

## 3. The law (question 2)

Question: a mapped tunnel's ramp cannot reach its road's grade within the
cap before a stop. Refuse the end, extend the ramp past the stop, or lift
or close the mouth?

| option | verdict | rulings |
|---|---|---|
| extend the ramp past the stop | refused | 2026-10-19e (a mouth never cuts pavement), 19o (a rim never trims pavement it runs beside), owner Q32 2026-10-20 ("they definitely shouldn't cross a pavement edge or go through another road", `Ortho4XP/docs/specs/tunnel-ramp-road-and-pack-ramps-1028.md:5`), 2026-08-07 ramp-cut ruling 3 (never across a pad edge) |
| steepen | already exhausted | 2026-10-08c (1), 08d (1), 14j: 5 % design, 10 % is the cap; the refusal fires only when no grade up to the cap fits |
| lift the mouth (shallower floor) | refused | depth has one ladder (2026-11-03b (5); 2026-09-08l): object, flat deck, credible lidar, else 7.5 m. No ruling lets the ramp length choose the depth |
| refuse the end | right, and already done | Q32: "either there isn't really a tunnel there, or it's steeper, or the shape is wrong" |
| **and then the rest of the bore** | **missing** | 2026-09-13bm (ii): "a tunnel with one mouth is never right". 2026-11-16h: "a mapped bore too short to climb from its mouth floor to an unopened end at the ramp cap (length × ramp_max_grade < mouth depth, and a mapped road leaves the unopened end at grade) is not built: no cut, no ramp; the road stays at grade" |

**The law (general, no airport named):**

> A bore end whose ramp is refused because no grade up to the cap tops out
> before a crossing road or airside pavement, while its mapped road runs
> on past that stop, is an end at grade. Where the bore is too short to
> climb from its other mouth's floor to that end at the ramp cap, and a
> mapped road leaves that end at grade, the bore is not built at either
> end: no cut, no ramp, the road stays at grade (2026-11-16h).
> A bore long enough to climb out keeps its other mouth, as today.

Why this is inside 16h and not a new rule:

- 16h's ruled text has no building in it. The master narrowed the
  *implementation* on 11-16 to far ends refused at a building pad, after
  the broad form withdrew 31 tunnels at 17 airports (master handoff
  11-16, 20:0xZ). This spec adds one far-end class to that narrow form.
- The new class cannot reach a tunnel anyone has accepted. It exists only
  where l588 or llemd2 refuse an end, and both landed today. Where they
  refuse nothing, this law changes nothing (census, §5).
- The evidence that the far end is at grade is stronger than a pad's: the
  engine has shown that the road must be at grade at a mapped crossing or
  pavement edge within reach, and it leaves the end uncut.

Arithmetic at the site: 29 m × 10 % = 2.9 m against a 7.50 m mouth; the
bore would need 25.9 %. At -2487: 10 m, 75.9 %.

The master records this as an application of 16h (RULINGS entry, master's
to write). If the master reads it as a change to 16h's 11-16 narrowing
that needs the owner, the question is one line: "A short tunnel whose
other end we already refuse because its ramp would hit a road or apron:
drop the whole tunnel and keep the road flat? (LEMD old terminal, 29 m
underpass.)"

## 4. Implementation

Two files, one behaviour. Frozen: every existing signature; the pad
class's refusal text (RJTT's line must not change).

1. `Ortho4XP/src/auto_patch_v2/planar/structures.py`
   - beside `pad_ends` (line 572): `stop_ends: dict[tuple[int, int],
     tuple[str, str]] = {}` — bore ends refused by the stop refusal.
   - in the l588 / llemd2 refusal block (lines 1408-1431), before
     `continue`: `stop_ends.update({bore_end(m): ("crossing road" if
     crossed else "airside pavement", str(clipped_by)) for m in members})`.
     Same pattern as line 1360.
   - at the `short_bore_refusal` call (line 1871): pass
     `stop_ends=stop_ends`.
2. `Ortho4XP/src/auto_patch_v2/planar/short_bore.py`
   - `short_bore_refusal(…, pad_ends=None, stop_ends=None)`: one new
     keyword, last, default `None`. Not a new public symbol.
   - at lines 127-129: read both maps for `(id(b), far_i)`; return `None`
     only when neither holds the far end.
   - the text: the pad class keeps "under building pad {pad}, where road
     {road} leaves at grade" and its closing words. The stop class says
     "whose ramp no grade up to the cap tops out before {kind} {ref},
     where road {road} leaves at grade" and closes "the road stays at
     grade (owner RULINGS 2026-11-16h, #2079; #1028 Q32)". Keep
     `ONE-MOUTHED SHORT BORE` and `2026-11-16h` in both.
   - docstrings: the module's and the function's narrowing paragraph name
     the second class.
3. Tests (run only these two files, once):
   - `tests/auto_patch_v2/test_short_bore2079.py`: a stop far end
     withdraws a short bore and names the stop and the road; a bore that
     can climb out stands; a stop recorded at the near end does nothing;
     `test_an_end_under_no_building_stands` keeps passing unchanged.
   - `tests/auto_patch_v2/test_mouth_profile1028.py`: in the l588 and
     llemd2 twins (lines 212-266) assert on the *west* mouth too. With a
     bore shorter than `depth / ramp_max_grade` both ends are gone and the
     refusal list carries `ONE-MOUTHED SHORT BORE`; with a longer bore the
     west mouth stands. Read law values from the tables.
4. No law table change, no new `O4_` variable, no new module, no wire or
   sidecar change. Build-time impact: none measurable (one dict, one
   lookup per built tunnel).

Estimate: +25 / -5 source lines, +50 test lines, 0 new public symbols.

Consumers (RULINGS 2026-08-30l): none new. The withdrawal goes through
16h's existing path (`keep[i] = False` in the built-whole-or-not loop,
`structures.py:1856-1876`; cells, footprints and keep-outs dropped at
1900-1904). No new region or exemption is minted.

## 5. Census (question 3)

Planar stage only, c0e91ad4f code, each capture's latest registered frame.
"Stop refusals" are l588 / llemd2 refusals. "This law" is the number of
tunnel ends it withdraws. "Broad 16h" is what 16h would withdraw with no
far-end class at all (reported for the master; not proposed).

| airport | capture | structures built | stop refusals | 16h today | **this law** | broad 16h |
|---|---|---|---|---|---|---|
| LEMD | `l588fix/LEMD.pkl` | 27 → 25 | 4 (-4927@0, -4927@1, -2487@1, -1501@0) | 0 | **2**: `-1501@1`, `-2487@0` | see note |
| KEGE | `lkege3/KEGE.pkl` | 0 | 0 | 0 | **0** | 0 |
| BIKF | `l2203/BIKF.pkl` | 0 | 0 | 0 | **0** | 0 |
| OMDB | `l2203/OMDB.pkl` | 22 | 0 | 0 | **0** | 0 |
| LGAV | `l2203/LGAV.pkl` | 9 | 0 | 0 | **0** | 1: `-133@1` |
| CYYZ | `lcyyz/CYYZ.pkl` | 10 | 0 | 0 | **0** | 0 |
| KATL | `lvec/KATL.pkl` | 4 | 1 (-10200@0) | 0 | **0** | 0 |
| RJTT | `lpackobj/RJTT.pkl` | 25 | 2 (-6965@1, -6906@0) | 1: `-6785+-6784@1` (pad class) | **0** more (the same 1) | 2: adds `-7726@0` |

- LGAV `tunnel:-133@1` (54 m bore, 7.20 m mouth, 13.3 %) is one-mouthed
  because `-133@0` is refused "the road leaves the corridor 12 m out"
  (#1028 Q32's first half). That class is **not** in this law. LGAV is a
  certified airport; this law leaves it untouched.
- KATL `tunnel:-10200@0` is refused by l588's own rule (crossing road
  -1202, 12 m out); its other end has no portal witness (2026-11-03b (6)),
  so the bore builds nothing and this law adds nothing. l588's census
  (KEGE, BIKF, OMDB, LGAV, KDEN, CYYZ) did not include KATL: that end is
  an l588 effect no census has listed until now.
- RJTT: l588 / llemd2 refuse two ends there (`-6965@1`, crossing road
  -7479, 72 m out; `-6906@0`, airside pavement `dsf:netpage44`, 36 m out).
  Neither lane's census included RJTT. `-6965@0` stands (mouth
  35.552489, 139.750990, 7.50 m, ramp 168 m): its bore is long enough to
  climb out at the cap, so 16h and this law both keep it. `-6906`'s other
  end goes on underground and has no mouth. The broad form would also
  take `-7726@0` (60 m, 12.4 %), through the "road leaves the corridor"
  class; not proposed.
- LEMD note: the broad column was not measured on the LEMD run (a probe
  defect in the first run, fixed before the others).
- LEMD arm against the control replay, emitted patches: 9 nodes move more
  than 0.1 m, all within 300 m of the two mouths, none on an airside-role
  node; worst 0.51 m near -1501 and 7.67 m at -2487's mouth (a rim node
  back at grade). 131 nodes only in the control (the two ramps and rims),
  29 only in the arm.

## 6. Bars and drawn-gate sites

### 6.1 Lane bars (replay; the lane stops here, RULINGS 2026-11-17r)

`tools/v2_solve_replay.py --replay <l588fix/LEMD.pkl> --from planar --emit DIR`:

1. Structure lines: `tunnel:-1501@1` and `tunnel:-2487@0` each refused
   `ONE-MOUTHED SHORT BORE`; `-1501@0`, `-2487@1`, `-4927@0/@1` refused as
   today; no other tunnel line changes (25 structures built, 27 on the
   control).
2. `--site 40.466139,-3.571018`: roles `service_road` only; no
   `tunnel_ramp` / `retaining_wall`.
3. The emitted patch has no `tunnel_ramp` or `tunnel_wall` face within
   300 m of 40.466139, -3.571018, nor within 120 m of
   40.469631, -3.573440.
4. Movers against a control replay of the same capture on the lane's
   base: none over 0.1 m farther than 300 m from the two mouths; none on
   an airside role.
5. Census replays (planar stage) on KEGE, BIKF, OMDB, LGAV, CYYZ, KATL,
   RJTT: no structure line changes. RJTT's -6785 / -6784 refusal text is
   byte-identical.

Measured with the law applied by monkeypatch in this review: bars 1-4
hold (`scout/out/arm.log`, `scout/out/emit_arm/`).

### 6.2 Drawn gate at integration (one LEMD tile build, `--pack-copy`)

    drawn_gate.py LEMD --tag T --against <installed control json>
      --site OLD1501=40.466139,-3.571018,80
      --site OLDS=40.466748,-3.570098,60
      --site OLDTERM=40.463344,-3.571491,80
      --site T2487=40.469631,-3.573440,60

All values are patch-surface road reads (predicted, not drawn):

| site | what it judges | law applied | replay control (c0e91ad4f) | installed 1.0.585 |
|---|---|---|---|---|
| OLD1501, 80 m | end @1's mouth and the first 80 m of its ramp | 0.20 m (way -531, 40.466211, -3.571040) | 4.67 m (way -1501) | 0.20 m, same place |
| OLDS, 60 m | end @0 (llemd2's site) | 0.10 m | 0.10 m | 0.09 m |
| OLDTERM, 80 m | l588's site (-4927) | 0.07 m | 0.07 m (tile l591 drew 0.06 m) | — |
| T2487, 60 m | -2487's mouth | 0.29 m | 4.10 m (way -2487) | 0.29 m |

Bar: roads PASS at these four sites, no MOVED against the control.

### 6.3 What the 300 m OLDTERMPAD site will still show

Not this law's. Pad `building49` (29,637 m², 40.467512–40.469372,
-3.573232–-3.569818, 603.54–604.95 m) stands in the replay at c0e91ad4f.
The installed control has road faces there and no pad. lpads 6cf8cfd04
raised LEMD's arrangement pads 46 → 76 and is the likely source; that was
not attributed here. Three mapped roads enter the pad and step at its
rim. Patch-surface road reads, same in the control replay and the arm:

| road | at | patch surface | step on 1 m samples |
|---|---|---|---|
| service -2501 | 40.467644, -3.570643 | pad 604.83 → road 605.77 | 0.94 m |
| service -2507 | 40.467644, -3.570832 | road 605.91 → pad 604.82 | 0.59 m (1.09 m across the stand-off) |
| tertiary -1092 | 40.469178, -3.572457 | road 606.13 → pad 604.43 | 1.44 m |

The first two are inside OLDTERMPAD's 300 m circle (277 m and 281 m from
its centre); the third is 97 m from -2487's mouth (hence T2487 at 60 m
above). Expect
`OLDTERMPAD … max step ≈ 0.9 m … way -2501` and a MOVED line (0.21 →
≈ 0.9) after this fix. Whether the drawn mesh shows exactly these values
needs the tile build; the patch surface is a prediction.

This is a pad-to-road weld question (2026-10-08c (4), 08d (2), 16i), for
the lpads / #2302 thread. It needs its own attribution; none was done
here.

## 7. Out of scope, noted

- The road layer judges the face of any mouth no pack portal claims
  (`drawn_roads.claimed_mouths`). A lawful two-mouthed mapped tunnel with
  no portal object therefore fails any site that covers it. The master's
  11-16 owner question ("is a bare engine mouth with no portal object
  acceptable?") is still open; branch `claude/lrjtt2` c2e727df8 holds the
  gate half. After this fix no plain mouth stands within 300 m of the
  site, so it does not arise here.
- The "road leaves the corridor" refusal (#1028 Q32's first half) leaves
  the same kind of one-mouthed short bore (LGAV `-133@1`). Adding that
  class would change a certified airport: owner's call, not proposed.
- The survey rule 2026-10-28k (232 a) ("the credible survey shows no
  cut", which refuses BIKF's -410+-415 at both ends) decided nothing at
  LEMD: none of the control replay's 45 structure lines cites the survey.
  Whether LEMD's inset counts as credible lidar was not read here.

## 8. Sources not verified

- The drawn mesh, the tile's patch and the pack copy of `l591_LEMD`
  (deleted before this review). §2.3's "tile" column is the gate JSONs.
- The 11-16 census "31 tunnels at 17 airports" is the master's handoff
  note only; its split by far-end class is not on file.
- Owner Q32's words are quoted from the #1028 spec; they are not a
  RULINGS entry.
- `tools/harness/frames.py list LEMD` on branch `claude/lpackobj` does not
  show the l588fix row; it is in `docs/frames.jsonl` at c0e91ad4f and the
  file exists.
- The patch-surface road read (`tools/patch_faces.PatchFaces` under
  `drawn_roads.road_layer`) was checked once against a drawn result: the
  installed control reads 0.20 m here, the gate drew 0.21 m.

## 9. Process

- Both rounds verified at one end's site with a tight radius. A tunnel
  fix needs both mouths in its bar: list every `tunnel:<ways>@k` of the
  bore and read each mouth.
- The gate prints one worst step per site. A 300 m site with a 3 m defect
  hides every 1 m defect behind it. `arm.json` keeps only the worst too.
  Printing every way over the bar would have shown `building49` on the
  l589 read.
- Scratch tools of this review (second use → promote): `scout/bin/
  roadstep.py` (the road layer on a patch surface, every way over the
  bar), `scout/bin/census_driver.py` (planar-only structure census with a
  monkeypatched law).
