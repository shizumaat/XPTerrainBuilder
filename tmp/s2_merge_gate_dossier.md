# S1/S2 STACK MERGE-GATE DOSSIER — the 22 airside rows

Row-by-row adjudication of the airside rows gating the merge of
`lane/s1freeze → lane/s1stage → lane/s2profile` (tip `4d1fded`).

**Measure-only.** No source changed, no build ran, shared repo UNCHANGED.
Every row is read verbatim out of a `census.py --rows-json` dump already
present in this lane; every polygon out of the patch that census was run
on. The only new artefacts are joins, and each is labelled with its frame.

---

## 0. Frame and identity

| | |
|---|---|
| Frame | S8, `main 1fc73e6` (ancestor of current `main`) |
| Worktree | `/Users/noah/XPTerrainBuilder/.claude/worktrees/s2profile` |
| Arm | `tmp/arm/HECA_s2d.osm`, body `a9496e142bff928c…` (S2b, 3895 shapes) |
| Reference | `tmp/ref/corrHECAoff.osm`, artifact-ledger key `9713491f3bbb29aa…` |
| Instruments | `tools/harness/census.py` dumps (`tmp/cens8/*.rows.json`); `tools/census_rows_diff.py` |

**Identity correction.** The brief cites the reference body as
`7bf9038e93f7…`. That is not this reference: `7bf9038e93f7` is the FROZEN
KCLT baseline body from the 2026-08-13 performance-phase ruling. The
served pre-corridor HECA reference is body **`7fbe7c26d7e3ddbd…`** —
confirmed three ways: the ledger entry `9713491f`, the lane's own
`corrHECAoff.result.json`, and `tail -n +3 corrHECAoff.osm | shasum -a 256`
recomputed here. The S1c commit message states the same value. The ledger
entry id in the brief is correct, so this is a transcription slip in the
spec text (`staged-solve-round-spec.md` line 272 carries it too), not a
frame mismatch. **No STOP.** The spec line should be corrected.

Reference env confirms it is genuinely pre-corridor:
`O4_ENABLE_SERVICE_ROADS=0`, `O4_SERVICE_CORRIDOR_CHAINS=0`,
`O4_SERVICE_CORRIDOR_FREE_END=0`, `O4_SCORER_CORRIDOR_WIDTH=0`.

### The headline reproduced

`census_rows_diff ref.rows.json heca_armd.rows.json --tol 0.0 --side airside`:

```
EXACT 1305   MOVED 0   GONE 348   NEW 370   NET +22
```

Exactly the S2b close-out numbers.

---

## 1. The join at tol 0.0 counts re-vertexing as new violations

At `--tol 0.0` `MOVED` is 0 **by construction**, so every row whose vertex
moved by even a millimetre is forced into NEW/GONE. The tool's own
docstring calls two tolerances "the honest way to show the join is not
doing the work". The ladder:

| tol | EXACT | MOVED | GONE | NEW | NET |
|---|---|---|---|---|---|
| 0.0 m | 1305 | 0 | 348 | 370 | +22 |
| 0.5 m | 1305 | 2 | 346 | 368 | +22 |
| 2.0 m | 1305 | 13 | 335 | 357 | +22 |
| 5.0 m | 1305 | 36 | 312 | 334 | +22 |

The net is tolerance-invariant (good — the join is not inventing the +22),
but NEW/GONE stay large at every tolerance because the corridor weld
**re-partitioned the airside rings entirely**: the same physical apron
carries way `-10629` in the reference and `-10577` in the arm. A
coordinate join cannot follow that; a way-identity join must.

### The controlling law

`staged-solve-round-spec.md`, MERGE CRITERION (owner 2026-08-14):

> the law is BINARY — a row is within grade or it is not; magnitude drift
> inside a persisting violation row is NOT a defect metric … Magnitude
> changes at sites whose violation state is unchanged … are recorded as
> context, never blockers.

So the criterion asks about **sites flipping into violation**, not about
vertex identity. Two independent site-level instruments follow.

---

## 2. Instrument A — surface provenance (way-identity join)

Each arm way carrying a NEW row was matched to the reference way with the
largest area overlap (shapely, layout-local metre frame), then asked
whether that reference twin also lost rows.

| n | surface provenance | reading |
|---|---|---|
| 304 | reference twin ALSO carried GONE rows | re-vertexed, state unchanged |
| 65 | pre-existing surface, twin lost nothing | candidate flip |
| 1 | no pre-corridor pavement underneath | genuinely corridor-created |

## 3. Instrument B — site-level violation state

For every NEW row, the distance to the nearest **reference** row of the
**same family + roles + side**:

| n | nearest same-class reference row |
|---|---|
| 21 | ≤ 0.5 m (the census's own `proximity_m`) |
| 149 | ≤ 5 m (the census's own `edge_search_m`) |
| 92 | ≤ 25 m |
| **108** | **> 25 m — no nearby reference row of this class** |

262 of 370 NEW rows sit where the reference was already violating in the
same class. Their site's violation state is unchanged; under the binary-law
clause they are context, not blockers.

## 4. Instrument C — ring class (S1c's frame, ring-level)

A ring "the reference also carries" = every one of its canonical 11-decimal
node spellings exists in the reference patch (canonical-identity join law;
never a proximity join). 2253 of 4224 arm ways qualify.

| ring class | NEW | GONE | net |
|---|---|---|---|
| reference-carried | 51 | 45 | +6 |
| corridor-changed | 319 | 303 | +16 |
| **total** | **370** | **348** | **+22** |

*Deviation noted:* S1c reported −129 / +152 for the same split. S1c
classified by whether a row's **nodes** were shared; this classifies by
whether the whole **ring** is unchanged, so a large apron with one corridor
weld lands wholly in "corridor-changed" here. Both totals agree (370/348);
only the split differs. This is a frame difference, not a contradiction —
stated so no later reader treats it as one.

---

## 5. Which increment minted what — the decisive table

All six states censused in the same S8 frame by the same `census.py`.
Class counts are immune to re-vertexing; exact-key origin tests are not
(a moved row reads as "minted"), so **the class table is the instrument**.

| airside class | ref | frozen 1.0.245 | ctl (S1c) | armd (S2b) | corridor | S1 | S2 |
|---|---|---|---|---|---|---|---|
| within_shape::building\|building | 9 | **52** | 52 | 52 | **+43** | 0 | 0 |
| within_shape::apron\|apron | 1384 | 1401 | 1368 | 1367 | +17 | −33 | −1 |
| within_shape::junction\|junction | 95 | 103 | 100 | 101 | +8 | −3 | +1 |
| transverse::junction\|junction | 76 | 72 | 68 | 67 | −4 | −4 | −1 |
| strip_arc::graded_strip | 46 | 50 | 50 | 50 | +4 | 0 | 0 |
| strip_seam_tear::graded_strip | 0 | 2 | 1 | 1 | +2 | −1 | 0 |
| transverse::apron\|apron | 21 | 21 | 22 | 22 | 0 | +1 | 0 |
| mid_edge_step::apron\|building | 8 | 7 | 5 | 5 | −1 | −2 | 0 |
| mid_edge_step::building\|junction | 1 | 0 | 0 | 0 | −1 | 0 | 0 |
| frontage_near_miss::apron\|building | 5 | 2 | 3 | 3 | −3 | +1 | 0 |
| frontage_near_miss::building\|junction | 2 | 3 | 2 | 2 | +1 | −1 | 0 |
| vertex_to_edge_step::apron\|building | 1 | 1 | 0 | 0 | 0 | −1 | 0 |
| strip_longitudinal::graded_strip | 2 | 3 | 2 | 2 | +1 | −1 | 0 |
| **AIRSIDE TOTAL** | **1653** | **1720** | **1676** | **1675** | **+67** | **−44** | **−1** |

**The +22 is +67 (corridor ship) − 44 (S1) − 1 (S2).**

The S1/S2 stack is **−45 airside against the frozen baseline** and worsens
exactly **two** classes by one row each (`transverse::apron|apron` +1,
`frontage_near_miss::apron|building` +1, both S1). Every other class the
stack improves or leaves flat.

---

## 6. THE +43 — the class that is the merge gate

`within_shape::building|building`, 9 → 52. Flat at 52 across frozen, ctl,
armb, armc, armd: **minted by the corridor feature's ship, untouched by
the S1/S2 stack.** All 43 rows carry `out_of_scope = null`. They sit on
exactly three ways.

### Pad `-10187` — 21 rows, ~(30.11623, 31.38670)

| | reference | arm |
|---|---|---|
| nodes with `alt_abs` | 12 of 21 | 23 of 23 |
| levels | 75.01 (×11), 75.04 (×1) | 72.28 (×22), 75.04 (×1) |
| internal spread | **0.03 m — lawful** | **2.76 m — 21 violating pairs** |

The single vertex left behind is node `-33562` @
`30.11622295360,31.38693302951`, `alt_abs = 75.04` — **byte-identical to
the reference**, and **shared with the aerodrome ring** (`-13398` in the
arm, `-12798` in the reference). The pad body followed the corridor-changed
solved ground down ~2.73 m; the vertex welded to the aerodrome ring did
not follow. The pad's own surface absorbs the whole disagreement.

### Pad `-10189` (14 rows) + new ring `-13851` (8 rows), ~(30.1213, 31.4077)

| | reference | arm |
|---|---|---|
| pad `-10189` | 85.63 uniform, spread **0.00 m** | 85.47 (×8) + 88.51 (×2), spread **3.04 m** |
| ring `-13851` | **absent** | 85.46/85.47 (×5) + 88.51 (×2) |

The two high vertices are `-1903` @ `30.12139538933,31.40766419809` and
`-1904` @ `30.12130251402,31.40769830240`, both `alt_abs = 88.51`. **Neither
spelling exists anywhere in the reference patch.** Both are shared between
`-10189` and the newly-created overlapping ring `-13851`. A second pad ring
was welded into an existing building ring at a level 3.04 m off it.

### Verdict — DEFECT (43 rows)

Not lawful-new: a building pad is a level plate, and the pre-corridor
geometry carried these same pads lawfully (spreads 0.03 m and 0.00 m). The
mechanism is a pad seat that does not track the ground its host ring now
sits on, plus a shared vertex holding a stale level.

**Owner: S5**, under *OBJECT PADS: EMISSION-TIME RELATIVE* (owner
2026-08-14) — "pad target = the patch's own evaluated ground at the datum +
`base_y`, computed in-run downstream of the one solve". A pad welded to a
neighbour's stale level is precisely the failure that ruling replaces; the
S5 mechanism, correctly applied here, resolves all three pads.
**Shared-vertex half: S6**, under *TRANSITION MACHINERY RETIRES — WELD OR
GAP* (owner 2026-08-13): the pad and the aerodrome ring agree at the shared
node while the pad's interior does not, which is the disagreement the
weld-or-gap sweep owns.

*Not chargeable to this merge:* the class is identical in the control
(`ctl` 52 = `armd` 52). Merging or not merging the S1/S2 stack does not
move a single one of these 43 rows.

---

## 7. Verdict table — all 370 NEW airside rows

| verdict | rows | basis |
|---|---|---|
| **LAWFUL-NEW** | **324** | 262 rows whose site the reference was already violating in the same class (binary-law clause: state unchanged, vertex moved) + 60 rows > 25 m from any same-class reference row but on **corridor-changed rings** — surfaces the corridor created or re-welded, which the pre-corridor geometry did not have + 2 threshold-marginal rows on way `-12173`, whose reference twin also lost rows |
| **RETIRED / OUT-OF-SCOPE** | **1** | `strip_seam_tear::graded_strip` — routed to **S6** under *WELD OR GAP* |
| **DEFECT** | **44** | 43 building-pad rows (owner **S5**, weld half **S6**) + 1 `frontage_near_miss::apron\|building` (owner **S1**) |
| **UNATTRIBUTABLE** | **1** | one `within_shape::junction\|junction` row, see §9 |
| total | 370 | |

### The 60 LAWFUL-NEW corridor-changed rows, by class

28 `within_shape::apron|apron`, 20 `within_shape::junction|junction`,
5 `transverse::junction|junction`, 4 `strip_arc::graded_strip`,
2 `transverse::apron|apron`, 1 `frontage_near_miss::building|junction`.
All on rings whose node spellings the reference does not carry — the
corridor welded new pavement into these airside rings, so a within-shape or
transverse pair exists there that had no pre-corridor counterpart. These
are paid for many times over by the 348 GONE rows and by the stack's −45.

### The seam tear (RETIRED → S6)

`strip_seam_tear::graded_strip|graded_strip`, ways `-13012|-13014`,
@ `30.110467,31.409006`, grade 188.521 %, `out_of_scope = null`. Reference
carries **zero** rows of this class anywhere. Corridor ship minted 2, the
S1 freeze paid 1, one survives at ctl/armb/armc/armd.

**The spec premise "Seam tear: gone (paid by the freeze)" is REFUTED — one
survives.** It is a real grade-law violation, not a nothing; it adjudicates
out of *this* gate only because *WELD OR GAP* (owner 2026-08-13) charters
the whole shared-edge-disagreement class to the S6 sweep, whose retirement
"follows the closure that makes it safe". Flagged for the spec text.

---

## 8. The one S1-owned DEFECT

| field | value |
|---|---|
| family / roles | `frontage_near_miss` / `apron\|building` |
| side | airside |
| location | `30.12549863051857, 31.416252111633572` |
| ways | `-10257` (apron) \| `-10022` (building) |
| grade | 7.9429 % |
| separation | 0.629 m |
| `out_of_scope` | null |
| ring class | **reference-carried** — the corridor changed no spelling on it |
| nearest same-class reference row | **943.8 m** |
| increment | class 5 → 2 (frozen) → **3 (ctl)** → 3 (armd): minted by **S1** |

A new airside frontage near-miss on a ring the corridor never touched,
nearly a kilometre from any comparable reference row. This is the only row
in the whole set that the S1/S2 stack itself put into violation on
unchanged geometry.

**Owner: S1d.** It belongs with the S1d docket the spec already opens
(`staged-solve-round-spec.md` "S1d docket (accumulating)"), alongside the
inverted-tube conflicts and the free-end outlier.

---

## 9. The UNATTRIBUTABLE row

| field | value |
|---|---|
| family / roles | `within_shape` / `junction\|junction` |
| location | `30.13129526916, 31.39656795869` |
| way | `-11890` (taxiway), ring class **reference-carried** |
| grade | 1.8423 % (cap 1.5 %) |
| nearest same-class reference row | 27.873 m |

**What was looked at:** the class table (ref 95 → frozen 103 → ctl 100 →
armc 101), which places the mint in S2b, not S1; the way-provenance join
(`-11890` → reference `-11600`, which lost no rows); the site test (27.9 m,
just outside the 25 m band, so it is threshold-sensitive — at a 30 m band
it reads as churn on an already-violating junction). **What was not
established:** which S2b mechanism moved this vertex. The row sits on a
taxiway junction ring the corridor did not re-spell, so the whole-run
profile should not reach it; the free-end station peg and the 1-D validity
release are the two S2b mechanisms that write outside the run, and neither
was traced to this coordinate from existing artefacts.

This is **one row of 370**, at 1.84 % against a 1.5 % cap, and is reported
as UNATTRIBUTABLE rather than laundered into the churn bucket. Resolving it
needs a `solve_cut` replay probe at this coordinate against the armb arm —
cheap (captures exist in `tmp/cap/HECA`), but it is an S2b question, not a
merge-gate one.

---

## 10. Recommendation

**The merge criterion is NOT met as literally written, and the reason has
nothing to do with the S1/S2 stack.**

- 325 of 370 NEW rows adjudicate away (324 LAWFUL-NEW + 1 S6-routed).
- 44 are DEFECT. **43 of those 44 were minted by the corridor feature's own
  ship and are byte-identical in the control** — the stack neither creates
  nor removes them, and they are owned by S5 and S6, both already chartered.
- The stack's own footprint is **−45 airside rows against the frozen
  1.0.245 baseline**, with exactly two classes worsened by one row each, of
  which one (§8) is a genuine defect for the S1d docket and one (§9) is
  unattributed.

Blocking the merge on the +43 would hold a −45 improvement hostage to a
regression it does not contain and cannot fix — the pad class needs S5's
emission-time-relative mechanism, which is a different lane's work. The
merge-criterion clause "gone or row-attributed to a named lawful mechanism"
was written before the pad and weld-or-gap rulings existed; the +43 is now
row-attributed to a named mechanism and a named owner, but that mechanism
is a **defect**, not a lawful one, so the clause as written still bites.

**Recommended to the owner — merge, with three conditions:**

1. The 43 building-pad rows transfer to **S5** as named acceptance sites
   (pads `-10187`, `-10189`, `-13851` at HECA), with the weld half to
   **S6**. The stack's merge does not discharge them.
2. The `frontage_near_miss` row at `30.12549863051857,31.416252111633572`
   (§8) joins the **S1d docket** as this stack's one genuine minted defect.
3. The spec is corrected on two refuted premises: the reference body is
   `7fbe7c26d7e3` (not `7bf9038e93f7`), and "Seam tear: gone (paid by the
   freeze)" is false — one survives at `30.110467,31.409006`.

This is an owner/lead decision, not a lane's: the criterion's own words are
not satisfied, and only the owner can rule that a pre-existing,
other-lane-owned class does not gate a strictly-improving merge.

---

### Reproduction

```
cd .claude/worktrees/s2profile/Ortho4XP
venv/bin/python tools/census_rows_diff.py \
    tmp/cens8/ref.rows.json tmp/cens8/heca_armd.rows.json \
    --tol 0.0 --side airside
```

Analysis scripts (scratchpad, measure-only): `map_ways.py` (surface
provenance), `sites.py` (site-level violation state), `origin.py`
(increment origin), `rings.py` (ring class), `pads.py` / `stuck.py` (the
three pads). No source changed; shared repo UNCHANGED; no build ran.
