# gapspec2 summary — §55 revised on the SOLVE (Fable, 2026-10-07)

Design and review only; no engine code touched. The section is
`design-surface-spec.md` §55 (`tools/docq.py spec '§55'`): (2) 4 and 5,
(3) 4, (5) the ceiling row, (7) the measured line, (11) the changed plan,
and the new probe record §55 (14). Founded on gaps6's STOP
(`docs/briefs/gaps6-notes.md`, `feature/pavement-gaps` `af918152`).

THE LOOP. gaps6's offline re-solve of the arm's pickle (~20 s) extended to
`<scratch>/gapspec2/resolve2.py` + `tools/v2_late_read.py` (bars + the
three sites): ~90 s a variant, 14 variants, every ruling cites the one that
decided it. The cut is recomputed from `gaps5/cl.pkl` + `gaps6/BASE` in
1.6 s and reproduces ARM1's 93 / 48 / 66.

THE RULE NOW (one configuration, SEEN on HECA — P12):
1. Q-D YES: a pavement-fallback pair across a declared knife is a step, not
   a grade (the knife's fourth law) — generator + census copy skip it by ONE
   predicate in `model.planar`. 111 rows; relaxed 235 → 186.
2. Q-E YES: a part's vertex follows only rings whose nearest station is the
   part's own (`Part.stations`, station level); relaxed 186 → 141; the 64
   removed bounds are DECLARED misses the reader must class so.
3. Q-F NO as a tier, YES as the widened row: a hard ceiling between two
   last-stage unknowns carries the pair test's own inequality
   `|dz| <= cap d + floor` (bounded by construction). A sixth tier demoted
   207 ceilings, 22 of them over the floor (worst 3.49 m) — unbounded.
   Relaxed 141 → 89; own-group follow misses 68 → 45.
4. Q-G NARROWED: lot rows only on a lot part whose own stations are roads
   and aprons alone; 214 rows on 5 parts (from 5,509); own-group misses
   240 → 45; relaxed lot rows 9, all at merged stations or under the floor.
   Refused: nearest-station-is-a-road (8.3 % at #430), a plane through the
   road stations (0.86 m under the road), the terrain-datum lever (no
   effect at the site).

P12 MEASURED (offline; the S3′ replay re-measures, ±10 % is the STOP):
movers 0; relaxed 89 (follow 32, ceilings 21 / 5 over the floor, ramp
ceiling 15 pre-existing, lot 9, constant-end 9, cross-section 3); follow
misses 43 declared + 45 own-group (34 under the floor; worst 2.05 m);
stepping pairs 82 / 65 on big pieces — the big ones are merged-sliver steps
at sunken pads (8.35 / 4.55 / 4.41 / 3.43 m, coordinates in §55 (14)); knives
46, worst 7.94 m (declared). Sites: #430 `gap:7/lot` 97.46, 2.0 % across
from the road 17 m away, 3.5 % along, ramp continuous 0.06 m — the lot
follows a road that climbs 4 m along it and its own cap to the up-road rim
holds it at the top of the 2 % window (why-vertex: no hard chord tight;
`lot_fit` pulls down; the datum is not the cause); #292 `gap:7/ramp0`
97.56, 7.8 % to `pav37`, no knife; #358 `gap:0/s4/lot` 90.24, 0.02 m to the
apron, 0.18 m to `building26`, 9.9 % inside (the floor weld).

BARS NOT MET BY P12: "follow misses only on merged stations" (45 own-group,
34 under the floor); stepping pairs above gaps4's arm (population grew
147 → 202 with ribbons as rings; residual 3 now visible).

RESIDUALS, named with coordinates in §55 (14): (1) the gap:8 interleave
(lot rows 10.78 / 9.12 m); (2) ribbon terrain floors (`building133`
2.04 m, `building147` 1.6–1.8 m; 15 of 45); (3) merged-sliver steps at
sunken pads (five pairs); (4) `gap:34 | pav39` 2.05 m, `gap:37/lot` 1.21 m;
(5) 132 contour joints — HYPOTHESIS: `planar/shapes` earns joints from the
DEM the sheet refused (read at S5′); (6) the census that did not finish —
profile before anything changes.

STEP PLAN (§55 (11) table "as changed"): S1 stays; S2′ Q-D (1 h);
S2″ Q-E (1 h); S2‴ Q-F widening at `late_constraints` (0.5 h); S3′ Q-G
narrowing + ONE replay + sites (1 replay + 1 h); S4′ reader classes
DECLARED / OWN-GROUP (1 h); S5′ census profile + contour-joint read
(1–2 h); S6 stays; S7 after S9 if short; S8/S9 one HECA build. The
smallest shippable subset IS S2′+S2″+S2‴+S3′ — nothing optional in it,
nothing beyond it this round.

OWNER QUESTIONS (new): Q5 the lot follows a climbing road along and rises
≤ 2 % across (recommend yes — Q2 with the mechanism named); Q6 a sunken pad
inside a lot keeps its step at the pad's foot for Beta 2 (recommend yes;
five coordinates for the sim read).
