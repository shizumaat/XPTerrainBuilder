# HECA apron round 3 — SPINE-FIRST MEMBRANE (Fable spec, 2026-08-26;
# owner sim read of 1.0.260, RULINGS 2026-08-26b items 1/3/4/5)

Owner directive (RULINGS 2026-08-26b item 4): if an apron lattice exists
it JOINS the taxiway centerline spines seamlessly — the whole apron must
be perfectly smooth for aircraft movement — and the lattice's own
necessity is IN DOUBT ("which I'm not convinced is necessary").

## §0 Measured frame (this session; patch `/tmp/harness/HECA_20260826T213425.osm`,
## body 8437a8bf, tree 97b38bffa614 at cb4749b9-dirty, census ledgered)

- Owner line T `30.129106,31.4059601 → 30.1293042,31.4068041` (84.2 m):
  ZERO interior stations — emitted vertices only at stations 0.00
  (74.02) and 84.22 (74.55). The taxi ROUTE is not cut: sidecar axes
  656→663→662→212→210/215 chain straight across the apron, every piece
  cap 0.015. What is cut is the ANCHORED SURFACE along the crossing.
- The owner's "disconnected T + two arcs": junction pieces -12810
  (73.87–74.34) / -12660 etc., anchored by the centerline profile,
  standing 0.7–1.2 m PROUD of the lattice membrane beside them
  (73.12–73.61, way -14534/-14514).
- Dip site `30.1290177,31.4055841`: same mechanism seen from below —
  lattice way -14514 runs 73.61→70.11 coupled only to its own ring;
  ring anchors span 61–74 on the giant apron -10659, so the taut seed
  and the solve pull the interior DOWN past the crossing spine's 74.
- Census (frame of record): `apron_lattice_membrane` 144 rows, worst
  2.750 m — the membrane violates its own family.
- Lattice overlap (owner item 1): 226 lattice ways / 970 segments;
  7 segments leave the apron footprint entirely, 89.5 m total —
  28.1 m through building shapeID 157 at `30.1111480,31.4041528`,
  23.5 + 8.2 m through junctions 2775/2776 at `30.1099666,31.4017001`,
  and graded_strips 3260 / 3422 / 3247. Mechanism:
  `apron_lattice._rows_and_columns` joins consecutive grid points into
  straight polylines with only per-POINT containment, so a segment
  between two lawful points bridges holes and concavities.

## §1 CENTERLINE STATIONS THROUGH APRONS — the spine is never cut

1. Every AIRCRAFT taxi axis (the `centerline_specs` aircraft
   population — the same enumeration the sidecar's `axes_exact`
   publishes; never a second notion) whose span crosses the INTERIOR of
   an apron-role polygon gains emitted stations along the axis inside
   the apron, at the standing pavement-node spacing (the 60 m emit
   rule's constant; reuse it, no new number).
2. The stations are CENTERLINE nodes: they join the phase-A scaffold
   anchor set and take the route profile's solved value exactly as
   junction-ring centerline nodes do — no new authority, the axis's
   own. Canonical-registry interned; sidecar provenance
   `apron_spine_station`.
3. Each station gains within-shape law edges to its nearest apron
   ring/lattice neighbours through `_grade_graph_edges`/`classify_pair`
   (the apron's own caps — the lattice precedent, one law). This is
   what makes the membrane CONFORM UP to the spine: the proud-T and the
   dip are the two sides of the missing coupling.
4. Flag `O4_APRON_SPINE_STATIONS`, default ON; OFF byte-identical.
5. Twin: synthetic apron crossed by one axis with ring anchors 2 m
   below the axis profile → stations minted at spacing, membrane
   conforms within cap, no proud ridge (station-to-neighbour deltas
   lawful); axis not crossing any apron → byte-identical.

## §2 LATTICE SEGMENTS CLIP TO THEIR APRON

1. A lattice polyline SEGMENT must lie inside the apron polygon
   (interior holes respected) buffered by the standing
   `LATTICE_RING_MARGIN_M`. `_rows_and_columns` output is filtered
   per segment (`prepared.contains(LineString(a, b))`); a violating
   segment is DROPPED and its run splits; sub-runs shorter than 2
   points die.
2. No new constants; the margin is the one the points already honour.
3. Twin: L-shaped apron whose two arms hold grid points → no segment
   across the notch; apron with a hole (carved building) → no segment
   across the hole; convex apron → byte-identical output.

## §3 LATTICE JOINS THE SPINES + the necessity measurement

1. Lattice law edges gain the §1 stations as neighbours: each lattice
   point within 1.5× `APRON_LATTICE_SPACING_M` of a §1 station gains a
   law edge to it (same `_grade_graph_edges` path, apron caps). One
   membrane, one law — the owner's "join seamlessly".
2. NECESSITY ARM (report-first, owner decides): with §1 landed, run the
   §2 empty-disk instrument on a lattice-OFF arm
   (`O4_APRON_INTERIOR_LATTICE=0`) of the SAME tree. Report per apron
   whether any >80 m empty disk survives once spine stations exist. If
   none does, the recommendation to the owner is to retire the lattice
   (spine stations subsume it); DO NOT gate it off unilaterally.

## §4 Acceptance (ONE HECA build; A/B census vs the §0 frame)

- Owner line T: interior stations exist; profile lawful; no station
  pair over the apron cap (report the profile).
- Dip site + T site: membrane-to-junction-piece deltas within the
  apron law (no ≥0.5 m bowl or proud ridge; report before/after).
- Lattice overlap read: 0 segments leaving the apron footprint
  (re-run the §0 instrument, same options).
- Census: `apron_lattice_membrane` 144 → report honestly (rows may
  MOVE to the new station pairs — un-blinding, not regression);
  airside delta explained row-for-row at the named sites.
- SPJC/CYXY non-regression (no new nodeless interiors, no lattice
  regressions; CYXY has no latticed apron — expect byte-identical
  there unless an axis crosses an apron).
- Convergence guards: materiality 0.01 m, attempt cap 2, STOP on
  second miss, progress heartbeat. No shared-repo writes, no timing
  claims (ledger tripwire only); build-time impact statement in the
  implementation report.

## Amendment 1 (Fable, 2026-08-27 — rulings on the lane's STOP items;
## attempt cap RESETS for the amended §1/§3 targets, cap 2)

Measured (lane/round3spine, arms CTL/B/C/A3, single tree): §2 clip
COMPLETE (lattice overlap 7 → 0). §1/§3 landed but the coupling is
SYMMETRIC: at the dip site the lattice did not move and the junction
pieces came DOWN 0.22 m; the line-T ring vertex fell 74.02 → 73.43;
ring-to-station steps 2.50–4.05 % against the 1.5 % cap;
`apron_lattice_membrane` 144 → 422. The projection satisfies the new
edges by lowering the anchored side — the opposite of "conform UP to
the spine" and of airside-is-king. Rulings:

1. **STATION VALUES ARE PHASE-A OUTPUT — CONSTANTS IN THE MEMBRANE
   SOLVE.** A station is valued by the route profile (the spine's own
   solve, where it is a legitimate collinear interior point of the
   chain — this is NOT a mid-taxiway hard anchor: the value is the
   profile's own, not an external pin). In the membrane/POCS solve the
   station is NOT a free variable: station-touching law edges
   constrain the NON-station side only (one-sided interval against a
   constant), exactly the adoption-not-constraint principle the
   road-crossing Amendment 1 §3 established. No term of the spine or
   junction solve may reference lattice/ring membrane variables
   through these edges. If the one-solve graph cannot express the
   one-sidedness, fix the station values between the spine pass and
   the membrane pass (the staged precedent), never post-hoc.
2. **ACCEPTANCE RESTATED for §1/§3:** junction pieces and centerline
   values at the T/dip sites within materiality (0.01 m) of the
   stations-OFF arm (the anchored side yields NOTHING); the membrane
   RISES toward the stations (dip-site proud ridge shrinks by the
   membrane moving up, junction unmoved); line-T ring-to-station steps
   lawful OR attributed to the ring's own pre-existing profile;
   membrane family reported honestly (rows may remain — un-blinding).
3. **Approved deviations:** the ≥3-station minimum (parse-contract
   forced, densify-only) and the station-chord clip stand. The 1.1 m
   station-class overlap residual through junction −12393 is ACCEPTED
   this round (report it; the polyline-following refinement is a
   later round if the owner's sim read ever sees it).
4. **The overlap instrument PROMOTES** (RULINGS `7e90032`, ~8 uses):
   land it as `tools/lattice_overlap_read.py` with an INDEX.md row and
   a twin, reading through the patch's own parser conventions; note in
   the row that `check_grade._parse_osm` drops <3-node ways, so the
   tool parses features directly.
5. **Necessity arm stands as the owner's answer:** with stations
   alone, 8 HECA aprons still carry a >80 m empty disk (worst 169.5 m)
   — the lattice remains necessary on this instrument; not gated off.
   The CYXY "byte-identical" premise in §4 is corrected: CYXY has a
   latticed apron and lawfully gains stations.

## Amendment 2 (Fable, 2026-08-27 — ruling on the §1.2 reading;
## supersedes the chain-membership wording; completion allowed)

Measured (A3↔A4 interventional pair): one-sided edges fixed the
membrane direction (dip ridge 1.48 → 1.20 m, lattice rises) but the
anchored side still moves (dip-site junctions to −0.500 m) through the
stations' membership in the phase-A chain itself — 62 interleaved
collinear points change the profile solve, and the yielding junctions
settle elsewhere. Ruling:

1. **READING (b) IS THE LAW: STATION VALUES ARE INTERPOLANTS OF THE
   PHASE-A PROFILE AS SOLVED WITHOUT THEM.** The chain is NOT
   densified; a station is not a chain variable. Its value is the
   solved profile of its axis, interpolated at the station's arc
   position — still "the profile's own value", now with the chain
   (and every junction, ring and centerline value) BYTE-IDENTICAL to
   the stations-OFF arm by construction. §1.2's "join the phase-A
   scaffold anchor set … exactly as junction-ring centerline nodes do"
   is superseded: the intent was the spine's VALUE at that point,
   never a re-solve of the spine. Everything else from Amendment 1
   stands (constants in the membrane solve, one-sided edges,
   preservation membership).
2. **Acceptance:** gate 2a becomes structural — assert the junction/
   centerline population byte-identical (or within 0.01 m) vs the
   stations-OFF arm; membrane rises toward the stations; line-T
   ring-to-station steps re-read under the interpolated values
   (expected lawful: the CTL profile itself ran 0.63 %); station-class
   overlap residual stays accepted. Report the same tables.
