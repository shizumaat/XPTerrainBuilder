# Frontage weld authority — the seat IS the weld — spec

Author: lead (Fable), 2026-08-08. Charter: the 2026-08-08 owner
ruling "Apron welds to building frontage; the seat IS the weld"
(RULINGS — read the verbatim). This spec REPLACES the planned
"pad-frontage round" (retrospective structure #1): for fronting
buildings there is no chord to price; the detached remainder belongs
to the relief/feather round, not here.

## The design (small by construction)

1. **Fronting buildings**: where a building fronts an apron (the
   existing frontage-identification machinery decides "fronting" —
   do not invent a new predicate; report which machinery you bound
   to), the apron pavement extends/welds to the building face and
   the building's seat value := the welded apron value at the face.
   The independent band-derived seat for fronting buildings RETIRES
   — measure first (Job 1) how often it currently disagrees with the
   welded value; every disagreement is the defect population this
   spec exists to kill. Apron cap governs to the face; no steps, no
   feather on the apron side.
2. **Detached pads are OUT OF SCOPE** here: their band seat stands
   (ONE-graph law); their surrounding ground is the relief round's
   feather territory (two pads' feathers meet in the middle — that
   geometry belongs to the relief spec).
3. **No new solve machinery.** The frontage strip joins the apron's
   own within-shape law population. `frontage_near_miss` self-retires
   for fronting buildings (seat == edge by construction) — keep the
   family for detached pads; its fronting subpopulation must read 0.

## Jobs

- **Job 1 (measure first, offline where possible)**: on the current
  tip and corpus, split the old ~1,870-row frontage class: how many
  rows/sites belong to FRONTING buildings vs DETACHED pads (the
  numbers were minted pre-road-feed/pre-floor/pre-enclave — re-count,
  never quote the stale figure). Quote the per-airport table.
- **Job 2 (implement)**: the weld authority for fronting buildings
  per (1). Blast radius expectation: building_feasibility seat path +
  the apron/frontage emit weld; NO solver changes.
- **Job 3 (acceptance)**: the fronting subclass dies (per-airport
  before/after, every moved row attributed); detached subclass
  UNCHANGED (it is another round's population); adjudicated airside
  Δ ≤ 0 both worlds at HECA (any positive is a STOP with the class
  table); battery matched controls; twins (fronting seat == welded
  value; detached seat untouched; near-miss fronting subpopulation
  == 0), registered per the lockstep rule.

## Budget

Job 1: 0 builds (offline on existing arms if they suffice; else it
rides Job 3's control). Jobs 2–3: 3 builds, hard cap 5. Frames
labelled (post-re-bake corpus, post-matfloor adjudication).
Deviations: STOP-and-report for Fable review.
