# padspec4 summary — §56 (3) re-written for the landed seat (Fable, 2026-10-08)

Branch `claude/pads56` (PR #463). Spec `tools/docq.py spec '§56'`. Design only; no engine code touched.
Probe: `docs/briefs/padspec-scratch/padspec4/platforms_probe.py SIDECAR.axes.json …` (one read, no replay).

## The seat decision (STOP 3)

The S1–S4 ladder is WITHDRAWN. On main since RULINGS 2026-10-02ag/ah (`constraints/no_step.py:534-612`)
the datum is a free solve column with one soft Band at the frontage median, every weld is a hard row,
and a weld is released only by the elastic LP (`solve/feasibility.py`, tiers runway > taxi caps >
apron cap > pad hold — the relaxation lands on the PAD's hold, never an apron cap), read after the
solve in `constraints/platform._datum_record`. That solve IS the owner's seat (07c (6)) and the
release IS the "cannot be solved" verdict. NO new seat machinery for Beta 2:

- the collar is deleted (4C); the seat is the free datum + hard welds (landed);
- the WARNING (4B) is built from the post-solve record: `released > 0` and `released_max_m >
  frontage_hold_margin_m` (0.3 m) → `session.log_warning` with the fixed copy; sidecar `warned` /
  `warning`; no `seat` key;
- the TILT (S3) is NOT built: follow-up `tilted-pad-seat`, design (b) (free gradient columns) if ever
  opened, triggered only by a miss on §56 (8) 3 (a)/(b).

Evidence (`heca_4a` replay sidecar + `sw1045_*`): at EVERY collared pad with a released weld
`rim_relief_max_m == released_max_m` to the mm (HECA `building147` 0.415/0.415, `141` 0.261/0.261,
`132`/`158`/`150` 0.043, `165` 0.043, `157` 0.039) — the collar carries exactly the release the solve
already made, so deleting it changes neither WHICH welds release nor by how much; the step moves from
the collar's inner ring to the pad's rim. The conforming pads (no collar) are the post-4C case already
running: `building101` 0.328 (would warn), `105` 0.269, `141` 0.261 (held), `186`/`138`/`193` ≈ 0.02;
KASE `building1` 0.629 (warns). Every other live collar: 0 released, relief 0.000–0.002 (KCLT
`building49` 0.23/0.48 is a groundside-rim terrace case, no weld released).

## The warning copy (verbatim, §56 (3))

> Building pad {unit} at {lat:.5f}, {lon:.5f} ({area:,.0f} m²): the apron cannot be welded to it along
> its whole frontage within the grade caps. The pad is seated flat at {datum:.2f} m, the apron's own
> level there; {n_rel} of {n_contacts} frontage contacts are released, the worst by {de:.2f} m at
> {wlat:.5f}, {wlon:.5f}. Why: {why}. The apron keeps its caps; the pad's rim steps there; the building
> is not moved.

`{why}` by `reach_isect_empty`: "no single level is within the apron's reach of every frontage contact
from the fixed taxiways and runways: the lowest contact can be reached only up to {r_hi:.2f} m and the
highest only down to {r_lo:.2f} m" / "a common level within reach exists ({r_lo:.2f}–{r_hi:.2f} m),
but the apron around those contacts cannot blend to it under its caps and the fixed airside"; suffix
"; the unit reads one level, so it is not split into blocks" when `blocks` == 1 and `needs_split`.
The padspec3 anchor sentences (kind / id / distance) are withdrawn: `reach_lo/hi_binding` are in no
sidecar record today.

## STOPs 1 and 2, deviations 1–6

- STOP 1: keep rule 8's clip; bars RESTATED from the clipped code — `building6` cell 1,111 ± 5 % /
  7 holes, HECA `building3` 1,096, site ring vertices ≤ 1,900 (1,390 + ≈ 500 the clip returns). The
  131 rim vertices are the apron's own ring the pad shares at the weld; re-straightening would cut the
  apron and move airside vertices (bar 2). Straight chords are delivered on the groundside / road sides.
- STOP 2: OTHH 34 into 4 ACCEPTED; the six roads at `building14/15/17/20` whose only join is over apron
  stay roads (`pad_not_one_polygon`) — apron stands between, not "right next to the building".
- Deviations: 1 (clip the growth only) ACCEPTED, rule 8 text corrected; 2 (`connector_step_max_m`
  4.95) ACCEPTED; 3 (`pad_base_ref`, pad family only) ACCEPTED; 4 (`#collar` bank in 4A, flip in 4C)
  ACCEPTED; 5 (per-road one-polygon test, detached scrap → ground, `over_airside_or_deck_shade`)
  ACCEPTED and written into rule 8; 6 (`building3` absorbs 1 road; 92 → 91 not `route24`) ACCEPTED —
  the implementer names the pad and road ref in the lane summary.

## 4B–4E as re-written (§56 (8))

| step | what | acceptance |
|---|---|---|
| 4B | the warning only, at the one `_datum_record` read site; `families.toml` text; `check_grade` rows; twins (0.45 → text in both `{why}` variants + suffix, byte-asserted; 0.25 → silent) | HECA `gaps3` `--from constraints --verify` vs the 4A arm: z byte-identical; WARNED = `building101` only; `pad_frontage_infeasible` rows 6 each with `warned`; OTHH 0 |
| 4C | the deletion core as before + `#collar` → `#strip` flip + drop `rim_relief_*` / `over_collar_max` | bar 3 (a)–(e) vs the 4A arm: same released set (± the 3 erosion-refused pads, quoted), no `released_max_m` grows > 0.05 m, `hard_conflict` runway/taxi/apron tiers count-identical, `datum == datum_median`, HECA WARNED ≤ 3 with copy, OTHH 0; collar faces 0; bars 2, 5; feet bar 4 |
| 4D | dead-code removal, byte-identical to 4C | as before |
| 4E | allow-list + schema snapshot for dropped keys; object readers | `--placement` bar 4 |

A miss on 3 (a) or (b) is a STOP → follow-up `tilted-pad-seat`, option (b).

## The owner's site after 4C (25.259994, 51.6104872)

≈ 22 faces / ≈ 1,900 ring vertices: building **1** (6 today), collar **0** (4), apron ≈ 10 (the
stand-zone plateau cut + the pieces the trenches and `pav32` leave — the apron's own tiling; a later
emit rule "same-plane apron pieces across a cut merge" could take it to ≈ 3, with its own consumer
census), tunnel_trench 5 (inherent), `pav32` / junction / parking_lot 1 each (inherent), service_road
≤ 3 (passing roads, inherent under (2) 4).

## Owner questions

None new. Q4 (tilt ≤ 1 %) is MOOT for Beta 2 — the tilt is deferred; cost of not building it: one
warning at HECA (`building147` 0.415 / `building101` 0.328 by frame) and one at KASE (`building1`
0.629). Q5 (0.3 m bar) recommendation unchanged: YES.
