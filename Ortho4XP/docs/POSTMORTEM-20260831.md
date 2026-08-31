# Post-mortem — 2026-08-30 sim-read mega-round (owner-reviewed 2026-08-31)

Verdict from the owner's sim read of app 1.0.271: none of the reported
bugs visibly fixed; roads WORSE (capped at a low grade, cutting through
hills instead of following terrain up to 8 %); tunnels a tangled mess;
app builds 62–75 % slower (owner ledger: HECA 2,129→3,452 s, LEMD
1,323→2,313 s, OTHH →1,823 s). ~25 merges landed that day.

## Failure modes

1. ACCEPTANCE PROXY: every merge adjudicated on censuses/site probes;
   the standing law says the owner's in-sim pass is acceptance, but no
   sim checkpoint ran between ~25 merges. Censuses count law rows and
   cannot see a road in a cutting; several fixes were census-real and
   visually insufficient or harmful.
2. TRIPWIRE UNASSIGNED: the ~2x build-time tripwire fired in the
   owner's own recorded app-build ledger and no one was tasked with
   reading it; per-change timing gates are suspended, so nothing else
   could catch it.
3. BATCH SIZE: four cross-cutting laws in one day destroyed
   attributability — the regression now needs a measurement pass to
   name its cause.
4. LAW-BY-INCREMENT ON A BROKEN FOUNDATION: the bridge consumed 10
   rounds / ~7 rulings (float model ratified before an emitability
   check; consumers discovered serially — since codified as RULINGS
   30l). Deeper: the day deepened investment in the `tunnel_road`
   claim class instead of questioning it. Owner verdict: the pre-claim
   model (mouths, ramps, retaining walls) worked; the claim class is
   the defect. The 25e "explain, don't fix" → supersession → five-
   consumer fight was the tell.
5. RULING FIREHOSE: ~20 owner rulings in a day is design-by-committee
   at merge speed; a troubled subsystem needs one ratified redesign.

## Owner road law (restated 2026-08-31, canonical)

Roads follow terrain UP TO 8 % (`SERVICE_ROAD_MAX_GRADE`) and are
pinned ONLY where they meet airside pavement. A road capped below 8 %
into a cutting through a hill is a defect.

## Owner bridge/crossing policy (restated — matches RULINGS 30c/30d/30f)

OSM carries crossing levels: `layer=*`, `bridge=*`, `tunnel=*`; shared
nodes = same-level intersection (our road feed preserves these —
measured `bridge=yes layer=1` at the LEMD crossing). Scenery pack
provides a bridge object → cut the road trench, the object bridges it.
No object → grade the "bridge" (deck at grade) and create the lower
road cuts on either side, cuts at minimum depth for clearance under
the bridge = `BRIDGE_ROAD_CLEARANCE_M` (5.1 m). Site exemplar:
40.4834432,-3.5805328 (LEMD).

## Plan (approved 2026-08-31)

- Phase 0 — attribution, no fixes: (a) roads grade-cap mechanism via
  single-suspect off-arms; (b) slowdown via recorded phase-time ledger
  diff; (c) sim-divergence read: the flown tile patches vs harness
  arms at owner sites. Spec: `docs/specs/phase0-attribution-spec.md`.
- Phase 1 — revert-by-ruling per family; keep the verified-orthogonal
  set (ledger hash fix, instruments/twins, basin twin-canyon fix, T4S
  setback, building1–7 demotion, dup-ref fix).
- Phase 2 — ONE tunnel redesign spec: retire the `tunnel_road` claim;
  mouths/ramps/walls + OSM-level crossing classifier + the bridge
  policy above; consumer-census table and heightfield-emitability
  check inside the spec; ratified once.
- Phase 3 — implement under the sim-checkpoint gate.

## Task C findings (2026-08-31, appended)

* **HECA WAS NEVER REBUILT — the owner flew Aug-29 geometry.** The app
  tile build died silently at 22:38:40 (engine's last log line, mid
  "Decimating emitted geometry"); phase times were recorded but no
  patch was written (two racing +30+031 builds + X-Plane running;
  worker likely killed). Every HECA "not fixed" read is VOID; the
  round-6 family was not in the scenery. NEW DEFECT: a tile build
  that dies between phase-time write and patch write fails SILENTLY —
  the app surfaced no error and stale scenery flew.
* **LEMD + OTHH: the fixes WERE flown** — flown patches site-identical
  (basin byte-identical) to the harness closing arms. "Not fixed"
  re-scopes to CENSUS-REAL, VISUALLY INSUFFICIENT — direct support
  for the tunnel_road retirement verdict.
* **Correction to this document's Phase-0 plan text:** the LEMD bridge
  branch WAS merged (13c9351b) before the app build and was flown;
  the deck emits as ordinary road pavement (no deck role exists). The
  flown span shows road 600.83–603.18 over the 598.45 ramp —
  the 30n-accepted 2.4–4.6 m separation, sub-5.1 by design at this
  site.
