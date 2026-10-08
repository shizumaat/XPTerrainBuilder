# padreview summary — review of the built 4B–4E on PR #463 (Fable `padreview`, 2026-10-08)

Spec: §56 (10) (`tools/docq.py spec '§56'`), amended in place; the "pending spec-author review"
marks of §56 (3) and §56 (8) 3 are resolved there. Read on `/tmp/harness/p59c_OTHH`, `p59c_HECA`
(frames `frames/pads59/`) against main's `swg_*`; probes in `docs/briefs/padspec-scratch/padreview/`
(sidecar / graded reads only; no replay, no build; one pack read of two deck objects' authored y).

## The six rulings, numbers first

1. **Landings — RIGHT in kind, gated by one witness.** Main `swg_HECA` carries 0 landings at the #290
   ruling's own site (`T23/T3_road.obj`): the eroded one-block region made `landing._key` find no block.
   HECA's five (`building3/landing0..4`, 101.66–101.87 m on datum 101.874; `T3_road.obj` authored y
   −0.23..16.83 = origin at the ramp foot) are the ruled picture (2026-10-03e). OTHH `landing2/3` at
   −1.74 / −1.89 m are pier footings (`OTHH_Bridge_01_LOD0_002/_003`, lowest y −0.80 / −2.34) — the
   solve carries 27 landing `hard_conflict` rows, ten of 9.8–10.1 m. RULE: `y_land ≥ −BAND_M` (0.5) or
   no landing. Expected OTHH 4 → 2, HECA 5 → 5.
2. **#112 site 100.38 → 93.04 m — WRONG.** `unit:43#6330/1` (92.03) + `/2` (100.38), T3's own
   bodiless ramp pieces, were joined by rule 2b into one 12,685 m² pad with `welded 0`, so no block plan
   ran and one §20 plate seated the whole at 93.04 — a 7.3 m pit under the upper piece. RULE: every pad
   with `outline_joined_from` non-empty goes through `plan_blocks`, welded or not. After: 100.38 / 92.03
   ± 0.5 with a `#strip`. The deck is unmoved (03e); the feet on the pad are what #112 measures.
3. **Eight building faces at the OTHH site.** `building6` 194,424 m² + a 4,060 m² part cut by the §20
   stand-zone plateau apron (inherent, allowed by §56 (8) 1) + six same-plane scraps 0.2–105 m² bordered
   only by that plateau. RULE: a same-plane surplus piece under the rule-6 floor bordered only by airside
   is re-roled as that airside face (`pad_sliver`). After: building faces 2, site faces 19.
4. **Datum column — YES, no `apron_trend` / `detached` row** (its own step 4F, own sweep). Bars 3
   (c)/(d) restated against the measured noise floor (taxi/apron ±3 rows, no new row > 0.2 m; datum
   ≤ 0.15 m, every pad over 0.05 named). FINDING F1: a null change moves 231 junction vertices up to
   0.57 m (`<scratch>/pads59/heca_4a_dvlast`) — a flat optimum in the SW taxi region; owed to a solve lane.
5. **R1–R3 ACCEPTED; D1–D5 ACCEPTED** (D3 with the R-J amendment). §56 (6) corrected: a flat row at a
   ramp top is satisfiable by seating the pad at the structure (the first OTHH build did: 3.962 → 2.611);
   `596e62c2` is the rule. OTHH's 37 terminal rows (23 ceiling + 14 plane, median 0.61 m) lawful; the
   27 landing rows owed (go with ruling 1).
6. **The 4.65 m gap is PRE-EXISTING ON MAIN** (same datums at the same centroids, 22 of 35 within
   0.05 m); `datum_median` = pass-1a `z1a` without the hold rows. Discriminating read named (20 min,
   `--stage1-dump` at `building85`'s contacts vs graded z at the same 11-dp lat/lon). Not §56's.

## Accepted / replaced

| item | verdict |
|---|---|
| R1 copy without `{why}` | ACCEPTED |
| R2 one-level suffix | ACCEPTED |
| R3 bar (d) `≤ 0.05 m` | REPLACED by the restated (c)/(d) (§56 (8) 3) until 4F lands, then 0.05 again |
| R4 landings keep collar machinery | ACCEPTED; `_unit_collar` deleted |
| D1 structure vertex not flat / not datum | ACCEPTED, spec corrected |
| D2 near-miss endpoint joins the hold set | ACCEPTED |
| D3 no plan → conforming-held | ACCEPTED, a joined pad is always planned |
| D4 test helper semantics | ACCEPTED |
| D5 no OTHH replay | ACCEPTED (closing build stood in) |

## Fix list (ordered, each its own commit) — §56 (10) table

1. landing gate `y_land ≥ −BAND_M` + `_unit_collar` deleted (0.5 h) — OTHH landings 4 → 2, landing rows
   27 → ≤ 2, max `s_m` ≤ 0.5; HECA 5 → 5.
2. `pad_sliver` re-roles same-plane surplus pieces (0.5 h) — OTHH site building faces 8 → 2, z identical.
3. `plan_blocks` on every joined pad (1.5 h) — #112 site 100.38 / 92.03 ± 0.5 with `#strip`.
4. step 4F datum column out of `apron_trend` / `detached` (0.5 h + its own sweep) — bar 3 (d) at 0.05.
5. re-measure: `obj8_split_report --feet-in` at #96 / #111 / #112 / #10; jetways hosted ≥ 127, anchors
   over ground 0; `harness/census.py` both arms; KASE / KCLT if captures exist.

## After the fixes

OTHH owner site: 1 pad + 1 plateau remnant, 19 faces, ≈ 1,090 ring vertices (this instrument), roads 3,
collar 0, landings 2 (feet +0.30 / +0.38 m), `hard_conflict` ≈ 37 pad-tier (terminal ramp tops).
HECA #112 site: two blocks at ≈ 100.4 / 92.0 with a strip; T3 landings 5, lots banking to 101.8 m —
flagged to the owner's sim read as the change he asked for in 03e.

## Owner questions

None new. Q5 (warn above 0.3 m) open, YES default; HECA warns once (`building101` 0.33 m, 3 of 16).

## Not settled

F1 (the 0.57 m null-change response) and F2 (the pre-existing datum gap) are findings for a solve lane,
not this section's; the T3 landing banks are a sim-read item, not a spec question.
