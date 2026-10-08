# jetspec summary — §57 THE JETWAY-TERMINAL PAD: THE BAYS ARE THE PLATEAU (Fable `jetspec`, 2026-10-08, design only)

Spec: `tools/docq.py spec '§57'` (design-surface-spec.md, appended; §56 (1) / (2) / (11) carry a
SUPERSEDED-IN-SCOPE note). Owner RULINGS 2026-10-08a / 08b. Probes `docs/briefs/padspec-scratch/jetspec/`
(`jet_probe.py` witness + shape candidates, `gate_probe.py` the gate witness, `pocket_census.py` what each
bay holds, `bl_check.py` centrelines vs pads, `replay_bays.py` + `arms.sh` the replay arm, `arm_read.py`);
logs `<scratch>/jetspec/`. Captures: `perfB362/OTHH.pkl`, `gaps3/HECA.pkl`, `<scratch>/sweepwalls/base/{KCLT,
SPJC,KASE,CYXY}.pkl`, `conc333/NLWF_main28500ecf.pkl`; surfaces `/tmp/harness/p60_*` / `swg_*`.

## The design in three sentences

The owner's E → rectangle already exists in the engine as the stand-zone PLATEAU (flat-pad v2 §3): apron pieces
held HARD at the pad's datum, role `apron`, taxi/runway vertices excluded. §57 extends its REGION to every hull
pocket of a terminal's outline that holds an apt.dat `gate` startup (the name-free witness; riders are refuted
as a witness). The pad face keeps its footprint and its pinned frontage (no weld-row change → no airside
motion), the bay is coplanar with it, nothing is re-roled; rule 2b, the near-road absorption and the R-W pin of
PR #463 are DELETED under 08a (1) ("every other building keeps its outline"); the collar deletion, the warning,
4F, the landing band, the scrap re-role and the per-vertex census survive.

## Who qualifies (gates within 60 m of the rule-2 outline; a BAY = a hull pocket holding a gate)

| airport | qualifying units (gates; bays; bay m²) | refused, rightly | notes |
|---|---|---|---|
| OTHH | `unit:28#8/0` 74 gates, 5 bays, 963,621 m²; six 100 m² root pieces 2–5 gates; `unit:16#0/2` 3, `unit:20#6` 4, `unit:80#0` 3 (tiny pockets) | the 177k m² landside forecourt pocket (0 gates, 1,253 riders) | every OTHH startup is authored `gate` (345/345) |
| HECA | T3 `unit:43#6330/0` 42 gates, 5 bays, 316,745 m² | T2 `unit:42#46` 0 gates / 3 tie-downs / 0 riders; the 49.6k landside pocket | T2 does NOT qualify |
| KCLT | `unit:31#0/0` 54, `/2` 32, `/1` 22, `unit:30#0` 11 | every hangar (0 gates; tugs are riders) | KCLT jetways read 3–11.5 m half-extent, tugs ≥ 12: extent is no witness |
| SPJC | `unit:1#0` 62 gates (2 bays, 120k m²), `unit:5#0` 11 | the 75.7k landside pocket (135 riders, 0 gates) | no jetway OBJECT in the pack — qualifies on gates (Q3) |
| KASE | none (12 tie-down, 12 misc) | | no jetways |
| CYXY / NLWF | no cluster unit | | |

## What the bays hold (pocket census, graded roles)

OTHH terminal: apron 513k, cross_connector 214k, junction 104k, strip 10k (taxi/runway family: excluded by
construction), service_road 14k (joins the plateau as the apron's road), tunnel_ramp 5.5k (structure pass cuts
it after), 83 stands, 4.4 km of taxi centreline (flat → every centreline row met). HECA T3: apron 219k, junction
25k, strip 1k, groundside pavement 35k (the landside half of a mixed pocket, untouched). KCLT: apron 109k,
junction 16k. Today 0 taxi-centreline vertices lie strictly inside a pad face at OTHH / HECA / KCLT.

## Flatness on sloping ground (today's plateau, graded z vs datum)

OTHH `building6` 1,223 / 1,223 vertices on 3.962. HECA T3 `building3`: 340 of 576 within 0.02 m, 403 within
0.3, extremes −0.96 / +0.98 (the vertices a taxi / runway face carries: `foreign`, the taxiway's). KCLT
`building77` 220 / 404, ±0.8. The whole-bay region changes nothing in kind: own vertices hold, taxiway-edge
vertices stay the taxiway's; no new warning, no tilt.

## Replay arms (`replay_bays.py`, --from planar --emit --verify, base = same tree unpatched; UPPER BOUND: every
pocket touching a block's stand-zone parts, gate or not)

| airport | plateau m² base → bays (terminal) | vertices on datum | runway | solve-owned movers @0.02 | taxi-tier hard_conflict | pad-tier | WARNED |
|---|---|---|---|---|---|---|---|
| OTHH `building6` | 140,628 → **351,650** | 1,043 / 1,043 | 0 | **0** (row-side 1 trench vertex 0.020) | 0 = 0 | 1 → 2 | 0 = 0 |
| HECA `building3` | (running at hand-back — `<scratch>/jetspec/arm_*_HECA`) | | | | | | |
| KCLT `building77` | (running at hand-back) | | | | | | |

OTHH owner's site r 150 m: 56 faces → 56 (building 17 → 12, plateau 1 → 6, roads 29 = 29); every face but the
five trenches is at 3.96 in BOTH arms — at a flat airport the surface there is one plane already (Q4).

## Owner questions (yes / no, recommendation)
Q1 the bay is the plateau, not a re-roled pad — YES. Q2 taxiways crossing a bay keep their level — YES.
Q3 SPJC qualifies on gates alone — YES. Q4 what is read at OTHH: terrain or the preview's cells? — build J2 +
J3, read HECA T3 in the sim first.

## Not settled here
HECA / KCLT arm numbers (running); the gate rule vs the arm's "touches the stand zone" (the arm over-fills; the
rule's exact m² per bay is in `pockets.log`); whether the plateau should also take the groundside pavement half
of a mixed pocket (HECA 35k m²: NO by default — it is landside); the same-plane emit face merge (Q4).
