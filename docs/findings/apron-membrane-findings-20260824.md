# The apron membrane investigation — data and reasoning (2026-08-24)

Audience: the next session, before implementing
`docs/specs/pad-seat-consistency-spec.md`. Everything here is measured;
arm artifacts live in the lane/backedge worktree, `/tmp/harness/`, and
the artifact ledger. Rulings referenced: RULINGS.md 2026-08-21b-f,
2026-08-24, 24b, 24c (+ addendum in lane commit messages).

## 0. The owner's model (the target)

Aprons are graded like taxiways and runways — never a DEM drape. Anchors
are the taxi-centerline profiles and the seated building pads; the ideal
surface is a taut membrane between them, < 1 % in every direction, 1.5 %
along corridor bands, small 5 % ramps only at back edges / between
adjacent buildings; steps only at pavement gaps; pad-less apron edges may
seed at DEM but are NEVER hard anchors (cut/fill to the scaffold).

## 1. Arm ladder (all HECA unless noted; one corpus, one DEM frame)

| arm | what | apron airside rows | notes |
|---|---|---|---|
| Aug-12 patch | pre-wave-3 reference | (1,519a total) | apron median height-above-DEM −0.18 m — see §6 |
| merged main (A5) | apron law A1-A5 | 1,116a total | drape complaint arm (owner in-sim) |
| backedge v1 | +back-edge 5 % rescope, pad fold, strip wiring | 2,138a | strict 1 % returned to ≤60 m interior |
| v2 | +24b corridor 1.5 % chain | 1,922a | corridor class → 1 row |
| v3 | +24c scaffold seed, pad-anchored scope | 1,964a | seed honoured, drape unchanged |
| v4 (KILLED) | scaffold-derived seats | CYXY only: 38a, pads −9 m | reverted 46c27cf; branch lane/backedge-seatsrc |
| v5 | frontage-only narrowing + frontage_band export | 1,964a (0 rows moved) | the evidence arm |

SPJC across the same ladder: 207 → 164 → 167 → 167 (bar 189 — PASSES since
v2). CYXY: 16-19 (bar 75). SPJC/CYXY carry almost none of the HECA classes.

## 2. What was refuted, in order (do not retry)

1. **"Plateau authority" framing** — owner: no plateaus, no cliffs; the
   membrane is continuous on the scaffold.
2. **Interior-cap value as the lever** — across EVERY arm and airport,
   not one violation was ever priced at the 5 % cap. The interior cap
   governs movement, it does not mint rows.
3. **"Something pulls the seeded membrane back to DEM"** — dead: the
   projection honours the scaffold seed (median emitted−seed +0.01 m).
   The membrane sits on the terrain because ITS ANCHORS do (corridor
   +0.15 m, pads −0.23 m median above DEM).
4. **Scaffold-derived seat source** — catastrophic (v4: 22/22 CYXY pads
   down mean 9.07 m). The band must stay the seat authority.
5. **Route-vs-euclid mismatch between band and chord law** — dead:
   route ≡ euclid on 300/300 sampled violating chords (the enforced
   graph contains the chord edge).
6. **Seat edge-clamping (zero margin)** — dead: 810/810 violating rows
   sit on pads seated INSIDE their band interval (8-99 % up, clustering
   mid-interval). No clamping.
7. **The lead's "295 rows price a pad-less vertex" claim** — a
   classification error (either endpoint may be the frontage vertex);
   879/882 have one. The frontage-only narrowing (41cb44e) was verified
   a 0-row no-op (v5: 1,964 EXACT/0/0/0).
8. **"Cap-budget reach" in the scaffold interpolation** — a misreading;
   the membrane is a boundary-value interpolation with no reach concept
   (owner: cut/fill covers any distance). NOTE: the whole-apron
   Dirichlet interpolator is still UNWRITTEN — sequenced after the seat
   fix because interpolating from terrain-level anchors is pointless.
9. **The "2.9 m proud a week ago" drape target** — cross-instrument
   artifact; not reproducible from any patch in the tree. Acceptance is
   now RELATIVE (apron vs its own corridor), findings §5.
10. **The old cliff count "145"** — not reproducible under either pinned
    definition; retired. Metric (B) (shape-pair sites) is the proposal:
    Aug-12 2,213 → v3 532.

## 3. What was established

- **The centerline scaffold is lawful**: corridor profiles never exceed
  their cap (the owner's acceptance test) — 47-55 corridor-family rows
  of ~1,950, none longitudinal-profile violations.
- **The corridor-region membrane conforms at 1.5 %** (24b chain): that
  class fell to 1-2 rows.
- **The projection is faithful**: seeds are honoured; there is no hidden
  DEM attractor in the solve.
- **Seats are lawful under the band** — the defect is that the band is a
  FEASIBILITY interval (7-34 m wide) while the law applied afterwards is
  a CONSISTENCY question (0.13-1.06 m budget to the solved corridor).
  The interval never sees where the corridor solved.

## 4. The evidence table (v5 HECA; frontage_band sidecar, a9d9c88)

813 violating stand-class chords sit on 29 large pads; top 8 by rows:

| pad | area m² | rows | seat | band floor | band ceil | seat pos | med drop | med budget |
|---|---|---|---|---|---|---|---|---|
| building70 | 15,298 | 274 | 87.91 | 84.19 | 91.03 | 54 % | 3.28 | 1.06 |
| building76 | 13,351 | 104 | 90.65 | 84.18 | 96.72 | 52 % | 1.26 | 0.49 |
| building157 | 36,905 | 82 | 97.62 | 94.80 | 127.24 | 9 % | 2.25 | 0.43 |
| building150 | 12,651 | 63 | 101.94 | 97.99 | 125.62 | 14 % | 1.03 | 0.33 |
| building67 | 4,896 | 45 | 102.36 | 96.98 | 102.39 | 99 % | 1.12 | 0.71 |
| building68 | 53,175 | 37 | 96.63 | 89.53 | 98.41 | 80 % | 3.22 | 0.85 |
| building81 | 2,104 | 30 | 86.32 | 78.50 | 90.36 | 66 % | 2.20 | 0.91 |
| building156 | 11,486 | 29 | 77.87 | 73.83 | 85.47 | 35 % | 1.53 | 0.13 |

Class distribution of the 882 violating chords: LARGE-building frontage
(2026-08-08 class) 525 · either-end frontage misc 295 (see §2.7) ·
small/detached pads (2026-08-06 class) 62. Route attachments 1.7-6.0 m.

## 5. Current acceptance frame (re-founded)

Per-airport airside bars 75 / 189 / 1,487 (2026-08-21 battery). PLUS
relative drape: apron median height within ±0.5 m of ITS OWN corridor
(v3 read: −1.3 m gap); pads within their frontage interval; ring
relief / amp50 not worse than the Aug-12 patch (1.44 / 0.47 on
`tools/apron_drape_read.py` — the pinned instrument, 6c6c94e); cliff
metric (B) not worse than 532; owner sites (30.1290177,31.4055841
apron; 30.1123069,31.4015122 tiny pad) read smooth.

## 6. Instrument lessons (they bit repeatedly)

- `pair_caps` was exported at 7 dp (half-ulp 5.6 mm) — a proximity join
  at that scale minted a phantom 26/22 class earlier in the session; now
  11 dp. NEVER pair-join below the export quantum.
- The census `frame:` line reports the CENSUS-TIME tree, not the build
  tree — check the patch's env.json (harness fix still owed).
- `apron_drape_read`'s definitions are NOT any older instrument's;
  cross-instrument comparisons of drape numbers are void (§2.9).
- The band was not exported until a9d9c88 (`frontage_band`); adjudicate
  seats ONLY against that export, never a replay.

## 7. Open items handed to the next session

1. IMPLEMENT `pad-seat-consistency-spec.md` (the main event).
2. Then the whole-apron Dirichlet interpolator (24c, §2.8 note).
3. Chord-origin awareness for the stand population (small reader spec;
   §2.7's structural note).
4. Roads/band-clamp round (owner site 30.102297,31.3951639 — 5 m jump,
   pre-existing; writeback-band floor clamp, 121 records; plus the
   2,432 transect exit_over_budget convergence class).
5. Tiny-pad fold + strip wiring + back-edge zones are DONE on
   lane/backedge (verified firing); merge decision rides on the seat
   spec's acceptance.
6. SPLP/KAFW/KDFW have no arm under lane/backedge; full battery +
   ledger refresh owed at merge time.
7. Pad-seat feasibility gate: 1 finding total (HECA building60,
   0.5 m over ceiling) — no fix policy needed yet.
