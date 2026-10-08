# pads57 notes — hand-back at the 4A boundary (Opus implementer, 2026-10-07)

Branch `claude/pads56` (PR #463). Spec `tools/docq.py spec '§56'`. Done: the items owed on steps 1 and
3, and step 4A. STOPPED before 4B on a spec/code mismatch (below); 4C–4E, the closing builds and the
site bars after 4C are NOT started (the spec orders 4B before 4C).

Probe (the spec author's, kept current): `cd Ortho4XP && venv/bin/python
../docs/briefs/padspec-scratch/padspec3/classify_probe3.py ICAO CAPTURE.pkl --arm today --skip-a
--site LAT LON R`. Captures: `<scratch>/perfA362/cap/OTHH.pkl`,
`/Users/noah/XPTerrainBuilderData/.harness/frames/gaps3/HECA.pkl`. The KCLT capture
(`conc333/KCLT_main28500ecf.pkl`) no longer exists in the scratchpad — KCLT was NOT re-probed.
Logs: `<scratch>/pads57/{othh,heca}_cls4.log` (final code), `heca_s3/`, `heca_4a/` (replays).

## DONE

### Steps 1 + 3 owed (commits `099b7ad6` + the follow-up fix)
- `classify/road_absorb`: `KEPT_WALL` / `wall_extended` DELETED (and the local in `roles.classify`).
- Rule 8: after the re-close, what the close ADDED over an airside cell or a deck shade is clipped
  back (`_growth`). `roles.classify` passes `shades=deck_shades(partition, frame.entry())`, the same
  reading the mint subtracts.
- `ABSORB_GROWTH` → sidecar `cluster_pads[].absorb_growth_m2 {road, shade_clipped, airside_clipped,
  fill}` and `roads_absorbed_m2`; `cluster_outlines(stats=)` → `outline_growth_m2 {join, well, close,
  chord, thin_kept}` (sums to the piece's added area; OTHH `unit:28#8/0` = 0 / 2,870.7 / 672.9 /
  1,443.1 / 0 = the spec's 2,871 / 673 / 1,443).
- Twins: apron tongue, shade notch, per-road keep after the clip, a road under a shade, growth classes.

### Step 4A (commit `3e66b53c`) — byte-identical
- `model/planar`: `STRIP_SUFFIX`, `is_strip_ref`, `is_bank_ref`, `pad_base_ref`; `platform_ref_of`
  strips `#strip` too.
- `constraints/platform`: `_bank_rows` (one body), `platform_collar_rows` (collars + landings) and
  `block_strip_rows` (the `#strip` faces; generator `block_strip` registered right after
  `platform_collar`). No strip face is minted yet — 4C flips `_mint_blocks` to `#strip`.
- Skip readers use `is_bank_ref`: `verify/within`, `verify/pads`, `pavement_cap`, the plate
  (`pads.py:546`), `cluster_pad`, `pad_frontage_gs`, `check_grade._is_platform_collar`.
- `[placement] connector_step_max_m = 4.95`, read by `planar/cluster.py`.
- PROOF: HECA `--replay gaps3/HECA.pkl --from classify --emit`, step-3 arm vs 4A arm: body sha
  `3811547f38240a61…` both, `HECA.graded.json` sha identical. (Both arms ran on an intermediate
  `road_absorb` since corrected, so the proof is relative; the frames are NOT registered.)

## Numbers on the real classify (final code)

| | OTHH | HECA | bar |
|---|---|---|---|
| roads absorbed into pads | 34 into 4 | 36 into 17 | 40 into 7 / 39 into 18 (±10 %) |
| kept | 6 `pad_not_one_polygon` (buildings 14, 15, 17, 20) | 5 `pad_not_one_polygon`, 1 `over_airside_or_deck_shade` | — |
| owner-site road cells | 17 → 2 (`route37`, `small_roads:-8407`) | 2 → 2 | 17 → 2 |
| site pad: road / shade / airside / fill | `building6` 29 roads; 3,844 / 0 / 0 / 2,632 | `building3` 1 road; 47 / 0 / 0 / 261 | 0 airside, 0 shade |
| site pad cell vertices | 954 → 1,111 | 1,020 → 1,096 | 611 ± 5 % / 491 |
| rule-2b `outline_vertices` | 552 (`unit:28#8/0`) | 453 (`unit:43#6330/0`, replay sidecar) | 552 / 453 |
| HECA gap frame twin | — | (91, 48, 64, 6) passes | 91 |

## STOP 1 — the pad-cell vertex bar (611 ± 5 %) cannot be met under rule 8
The 611 was measured on the absorb-all arm WITHOUT the clip. Rule 8 keeps the shade notches and the
airside frontage; their vertices come back with them: OTHH `building6` 954 → 1,111 (131 of them on
the airside cells' own rim; holes 3 → 7), HECA `building3` 1,020 → 1,096. The two readings differ by
678 m² (the 516 airside + 159 shade the clip takes back). The site bar "ring vertices ≤ 1,400 after
4C" was derived from the same un-clipped replay and will read ≈ 500 higher. One attempt made; no
second attempt exists inside the frozen rule (keeping a notch keeps its vertices). The spec author
must choose: keep rule 8 and restate the vertex bars, or let the re-close re-straighten the
frontage and accept the apron cut.

## STOP 2 — the absorbed-road count at OTHH (34 into 4, bar 36–44 into 7)
Two attempts. The roads kept are the ones whose only join to their pad lies over apron (padspec3's
own table: `building14` 136 m² airside, `15` 163, `17` 168, `20` 77): once rule 8 clips the apron
out, the road is off the pad and the union is not one polygon (rule 4 (d)), so it stays a road. The
40 / 7 bar was measured without rule 8. Refinements landed: the one-polygon test is per ROAD (the
others are still absorbed); a scrap of closing fill the clip detaches is ground again; a road the
clip would CUT (over airside or under a deck shade) is kept with `over_airside_or_deck_shade`.
REFUTED and deleted: "a road must lie ≥ 98 % inside the grown pad" as an always-check — the 1 m
straightening shaves small ribbons and it dropped HECA to 15 into 9.

## STOP 3 (BLOCKING for 4B) — the seat ladder is specified against a `hold_interval` that no longer exists
§56 (3) puts S3 "in `no_step.hold_interval` after (ii) finds `I_b` empty" and S4 on the contacts
that pass "released". In the code on main (owner RULINGS 2026-10-02ag / 02ah, round 5,
`constraints/no_step.py:534-612`):
- the datum is a FREE column of the stage-1 solve, pulled by one SOFT zero-width Band to the median
  of the frontage contacts' pass-1a value;
- every weld is a HARD two-way row; `b["residual"] = []`, `b["held"] = True`, `b["eval"] = "i"` for
  every block; step (ii) and the runway budget are gone (`beta = {}`);
- the pair-graph interval is "kept as the REPORT only";
- a weld is released only by the solver's elastic LP, and the residual is read AFTER the solve
  (`constraints/platform._datum_record`: `released`, `released_max_m`, `needs_split`).
So there is no site where "the interval is empty" decides anything, no pre-solve list of released
contacts, and no fixed D to add a gradient to. Fitting S3 means choosing one of: (a) decide
emptiness from the report interval again and fix a gradient by LP before the solve (reverses 02ah's
"report only"); (b) two free gradient columns per block in the stage-1 solve, bounded at
`pad_slope_max` and priced so the least tilt wins (new solver columns that are not vertices);
(c) solve flat, and re-solve tilted only the blocks the elastic LP released (a second pass, which
flat-pad v2 forbids: "no third pass"). Each is a design choice with a ruling behind it — the spec
author's, not the implementer's. S4's "plane row priced at the released contact" has the same
problem (the released set is a solve output). The WARNING half can be built off the post-solve
record under any of the three, but its `{why}` sentences need the anchor's kind, id and distance,
which `reach_lo/hi_binding` do not carry today.
Seen on the HECA replay (gaps3 frame refs, collars still minted): residual `building101`
(conforming) 0.328 m over 3 released contacts — over the 0.3 m bar, it would warn; `building141`
0.261 m over 5 (verdict held, under the bar); `building186` 0.021.

## Deviations from the spec text (for the spec author)
1. Rule 8 clips only the GROWTH (`closed − ((closed − pad) ∩ (shades ∪ airside))`), not the whole
   polygon: the pad cell at classify lawfully overlaps apron cells (OTHH `building6` 78,639 m²; the
   arrangement cuts the apron to the pad, 09-23a) and the literal `g − airside` would remove it.
2. `connector_step_max_m = 4.95`, not 5.0: 15 m × 0.33 is 4.95 and the spec says "no change of value".
3. The hand-spelt `split("#")[0]` joins go through a new `pad_base_ref`, not `platform_ref_of`: the
   two differ on a surplus piece (`building38#1`), and `cluster_pad._base_ref` documents that the
   split spelling is the intended join. Only the pad-family sites were moved (jetway_strip,
   pad_frontage_gs, cluster_pad, constraints/platform, project_strip, landing, model/platform);
   the structure / channel / gap / facade joins and `wall_corridor_ramps.py:235` (walls3's file)
   are untouched.
4. In 4A the block's bank is still minted `<unit>/b<k>#collar`: with the erosion alive the annulus
   share and the strip half are ONE region, and splitting them changes the arrangement. The grammar,
   the rows and the readers are ready; the mint flips in 4C.

## For 4C (reading already done, beyond pads56-notes)
- `_mint_blocks`: `col = Q − keep` becomes the strip (`ref + STRIP_SUFFIX`); the rename passes at
  `planar/platform.py:461-474` and `merge_platform_faces`' keys need the strip ref.
- Still on `is_collar_ref` / the literal and to be re-read then: `pads.py:605` (`platformed`),
  `pads.py:970`, `design_ground.py:140/147`, `placement_read.py:100/131`,
  `model/platform.py:165-166` (`"#collar"` literal), `landing.py:127`.
- `platform_collar_rows` keeps the name; rename to `landing_bank_rows` when only landings are left.

## Merge note
`git merge-tree` against `origin/claude/walls3`: ONE conflict, `tests/auto_patch_v2/test_gap_terrace.py`
(the recorded-counts tuple). `law/structures.toml`, `law/model.py`, `tools/check_grade.py`,
`tools/INDEX.md` and the spec auto-merge.
