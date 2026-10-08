# padspec2 summary (Fable, 2026-10-07) — §56 revised after PR #461's report

Branch `claude/padspec2` (= `origin/claude/cloudpadspec` + main `318efe5b`). Design only;
no engine code touched. Spec: `tools/docq.py spec '§56'`. Probes:
`docs/briefs/padspec-scratch/padspec2/` (run on `perfA362/OTHH.pkl`, `gaps3/HECA.pkl`,
`onelevel318/KCLT.pkl` and the `swg_*` sweep sidecars / graded surfaces).

## Rulings

1. **Step 2 (jetway rider rings): DELETED as machinery.** A rider has no geometry, the
   host is decided after planar, and the measurement says nothing is missing: every
   jetway anchor at HECA (51) and KCLT (67) stands on APRON, 68 of OTHH's 127 too; 4 m
   out from the face 95 / 51 / 67 are over apron, 8 m out 124 / 51 / 67. The close moves
   0 anchors across the outline at any airport. The rest at OTHH stand on un-minted
   ground between pad and apron (45) or over a trench (22 at 4 m) — the road absorption
   and the structure cut own those. Jetways are in the footprint BY HOSTING (127 / 51 /
   67 hosted today). Bar: anchors over ground / service_road at the site = 0.
2. **Step 3 (road absorption site): ONE call at the END of `roles.classify`**, after
   `mint_osm_ribbons` and before `mint_gap_pieces`, by ROLE over the cells list (routes
   and ribbons alike); the 0.6 m set-back does not apply to an absorbed face (the
   stand-off fills by the close) and is re-applied for CHANGED pads only, so A nodes are
   identical where nothing is absorbed. roadweld100's order is untouched. Never absorbed:
   a road over a structure footprint / keep-out, a wall-extended route, a ramp role.
   Counts: OTHH site 26 of 29 (20 route + 6 ribbons); airport-wide OTHH 75 / HECA 18
   (T3 0 of 2) / KCLT 24.
3. **The seat without the collar (owner 07c (6)):** ladder S1 flat interval (today) →
   S2 split (today, stepped base only) → S3 TILT ≤ 1 % (NEW: a 3-variable LP in
   `hold_interval`, gradient columns on the datum) → S4 residual: released contacts
   priced, the pad's plane row priced at them (the row that gives), a warp at the rim,
   reported in `pad_frontage_infeasible`, WARNED above 0.3 m through the existing
   `Log(level="warning")` path with fixed copy. Probe: HECA building147 0.416 → 0.191 at
   0.24 % tilt, building105 0.271 → 0.165, building157 seated by tilt. Expected warned:
   HECA 0–1, KASE 0–1, others 0, + 0–2 of the 21 pads today refused by erosion
   (those become held pads). KCLT building49's 0.23 / 0.48 collar relief is groundside
   rim → §28/§37 terrace, not a seat question.
4. **Step-1 deviations: all three ACCEPTED** (union + simplify(0); the mouth dimple;
   the concave fillet); bar 7 re-worded. NEW finding the implementer could not see:
   pads HECA 82 → 74, OTHH 56 → 52, KCLT 38 → 38 — pieces JOINED by the close and
   slivers dropped, every change named; the bar is "every change named", not "count
   unchanged".
5. **Plan**: steps 1 (landed, corpus proof owed), 3 (2 h), 4 (3–4 h), 5 seat + warning
   (3 h), 6 (1 h), 7 closing build (1 h) ≈ 11–12 h. Land 1+3+4+5+6 as ONE batch for ONE
   sim read; PR #461 may merge alone as code once its corpus proof is quoted, no
   release / sim read on it.

## Owner questions (new)
- Q4 tilted seat ≤ 1 % before warning — recommend YES.
- Q5 warning bar 0.3 m (`frontage_hold_margin_m`) — recommend YES.

## Not done
- No new capture taken; no frames registered (the probes read registered captures and
  the swg sweep products). No engine replay run (every number is pure geometry on the
  captures or a read of the emitted surface); the seat probe is a SUFFICIENCY reading of
  the solved surface, not a re-solve — step 5's HECA `--from constraints` replay settles
  building147's real S3 residual.
- The step-1 corpus proof (replay OTHH `--from classify`) is left to the implementer.
