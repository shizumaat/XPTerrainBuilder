# HECA apron round 2 — gap-bridging spine + nodeless-interior
# instrument + taut back edge (Fable spec, 2026-08-25; the two apron
# classes the 2026-08-25 attribution named and 1.0.259 confirms
# unfixed: the same-spot cliff and the back-edge ripples)

Evidence: the 2026-08-25 HECA apron attribution. (1) The cliff at
30.1289374, 31.4052385 → 30.1311876, 31.4048029 is a FEED GAP: apt.dat
taxiway J ends at node 462, another route starts at node 470 254 m
north, no edge between, OSM empty there — so the slice cuts no interior
vertices and the patch has a 215 × 430 m NODELESS region whose membrane
is uncontrolled for 233 m (the visible break is the anchor-influence
boundary; the census is structurally blind: no nodes → no rows). The
engine's ramp-lead-in trim fires zero times at HECA — the engine never
had the centerline. (2) The ripples at 30.1274109, 31.3970477 and
30.1141206, 31.4095574: the `graded_strip` B2/B3 encoding is a per-node
DEM clamp with NO coupling and NO fairing (terrain bumps pass through —
24c soft-seed behaviour, superseded by the DEM-last ruling), plus the
identity-adoption ladder (the strip adopts alternating families ~1.6 m
apart at 7% local grade).

## §1 The gap-bridging spine

1. Where two taxi-route ENDS (dead-end 1201/1202 leaf ends or emitted
   axis endpoints) lie unconnected across continuous apron pavement,
   synthesize ONE bridging centerline between them: for each dead end,
   the nearest VISIBLE route end across APRON-ONLY pavement (the §1
   chord-anchor visibility predicate — one notion, never a third)
   within `GAP_SPINE_MAX_M = 300`. Deterministic ties (lower node id).
2. The bridge is a FIRST-CLASS centerline: it enters the slice (cuts
   interior vertices), gets a profile, and the nearest-anchor chords
   price against it. Mark its provenance (`gap_spine_bridge`) in the
   sidecar so the census and readers can name it.
3. Flag `O4_GAP_SPINE_BRIDGE`, default ON; OFF byte-identical.
4. Twin: synthetic two-route apron with a 250 m gap → one bridge, slice
   vertices in the void, chords priced; gap > 300 m → no bridge;
   non-apron pavement between → no bridge.

## §2 The nodeless-interior instrument (ungated, report-first)

1. After emit, any apron-role polygon containing an interior disk of
   radius > `APRON_NODELESS_RADIUS_M = 80` with ZERO emitted vertices
   logs a LOUD line naming the shape, the disk centre (lat/lon) and
   radius, and writes `nodeless_interiors` into the sidecar evidence
   (census prints the count — zero-of-zero visible). Pre-ship this is
   report-first; promotion to refusal is a later ruling.
2. Twin: synthetic apron with an empty 100 m disk → line + sidecar
   count; densely-cut apron → zero.

## §3 The taut back edge (DEM-last applied to the strip)

1. The adjacent-ground `graded_strip` band gains the same second-
   difference LONGITUDINAL FAIRING the gap_fill_spine B2 family already
   has (extend, never fork), plus TRANSVERSE coupling to its host-edge
   anchor — the strip is a plane between its ends, not N independent
   DEM clamps. DEM remains the seed only (DEM-last ruling: anchors
   first, DEM tiebreak).
2. THE ADOPTION LADDER DIES: a strip ring welding two pavement families
   interpolates between its APRON-SIDE anchors along the run; the
   identity-adoption rule ("pavement value wins at a pavement node")
   still holds AT the welded nodes themselves, but between two welded
   nodes of DIFFERENT families the strip fairs monotonically instead of
   sawtoothing (the fairing from §3.1 is the mechanism — no new
   authority).
3. Flag `O4_TAUT_GRADED_STRIP`, default ON; OFF byte-identical.
4. Twin: strip over bumpy DEM between two level anchors → faired plane
   (bump amplitude below materiality); strip welding road (low) and
   apron (high) nodes alternately → monotone between welds, no
   sawtooth; OFF reproduces both.

## Acceptance (ONE HECA build)

- Cliff site: interior vertices exist in the former void; the emitted
  elevation along the owner line has no step > the local law (report
  the station profile); the bridge's own profile is lawful.
- Ripple sites (both): station profiles along the back edge read
  monotone/faired (report amplitude before/after; before: 0.5-1.1 m at
  7%).
- Census: airside not regressed vs 1,679 (new §1 chords may add rows —
  report honestly with the class table); `nodeless_interiors` count
  reported (expect ≥1 before §1, 0 after).
- SPJC/CYXY: non-regression (175 / 31-32 era frames), no new nodeless
  interiors.
- Attempt cap 2, materiality 0.01 m, STOP on second miss. No
  shared-repo writes, no timing claims.
