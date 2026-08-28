# LEMD ramp/road fidelity round (owner sim read of 1.0.265, 2026-08-28)

Owner items 1 and 3 from the 1.0.265 LEMD pass (RULINGS context: tunnel
walls now emit after §W1; these are fidelity defects on the emitted ramps
and roads themselves).

## Item 1 — tunnel ramp at 40.4984622,-3.5850476

Owner: "not centered on the road, a little too narrow, up-and-down humps
and valleys in the ramp, and the top of the retaining wall is not flat —
interior nodes at a different elevation than the outer nodes."

Measured on the owner's patch (built 11:25:04, `+40-010/+40-004`):

- Ramp fan rects -11982/-11983 (`tunnel_ramp`, 5-node sloped rects,
  603.29→606.1) + wall -11986 (`tunnel_wall`, 22 nodes, alt 603.4–610.6).
- WALL-TOP DEFECT CONFIRMED: -11986 is ONE ring carrying BOTH wall bands
  (west band lon ≈ -3.58506, east ≈ -3.58495, ~9.3 m apart). Across each
  ~1–1.5 m band the paired nodes differ 0.5–1.6 m (e.g. 610.6/610.1,
  608.3/607.7, 606.2/605.4) — each node samples the DEM at its own
  position, so the wall top renders as a twisted, jagged ribbon
  (owner screenshot 1's crumpled white band).
- WIDTH/CENTERING: the two wall bands stand ~9.3 m apart around the
  corridor. The tile has NO OSM small-roads extract and big_roads is
  empty at both sites — LEMD road corridors derive from the X-Plane DSF
  ROAD-NETWORK cache (`Airport_mod_cache/zOrtho4XP_+40-004/
  o4_dsf_road_network_+40-004.cache`). ATTRIBUTION HYPOTHESIS (measure
  first): a dual carriageway is a PAIR of one-way chains there; deriving
  the corridor from one chain gives exactly a half-width, off-center cut.
  Measure which chains cross the portal, what width each carries, and
  what the sim renders (the road ribbon in the cut sits right of center).

## Item 3 — road at 40.4836395,-3.5813233 up to the bridge at
   40.4836357,-3.5808828

Owner: "a 4-lane dual carriageway and our road is about half the width,
and again very bumpy output instead of a smooth road up to the edge of
the bridge over the tunnel ramp."

Measured: `service_road` -10293 (shapeID 292, 12 nodes, 600.84–605.65)
and `service_junction` -10529 (41 nodes, 600.72–609.78 — a 9 m range)
both under the probe; ramp fan + walls 16–26 m east. Same width-derivation
root as item 1(c) expected; the bumps class needs its own attribution
(junction/road seam vs fan-rect tops vs DEM between pieces — prior art:
OTHH §W2 round, where the pins were the HOST RING's own authored values).

## Laws

1. WALL TOP IS FLAT ACROSS ITS WIDTH: at every station the band's inner
   and outer top nodes carry ONE value; along its run the top follows the
   wall's own law (ambient at the cut top), monotone where the ambient is
   monotone — no per-node independent DEM sampling across the band.
2. CORRIDOR WIDTH AND CENTER COME FROM THE WHOLE CROSSING ROAD: where the
   road source (DSF network or OSM) carries a carriageway PAIR or an
   explicit width, the bore corridor, ramp fan, and wall bands take the
   pair's combined envelope, centered on it. No invented default width
   where the source states one.
3. THE RAMP DESCENDS MONOTONICALLY between grade and portal: fan-rect
   tops, the road ribbon, and the ground between pieces conform to one
   profile (attribute the humps interventionally BEFORE fixing — the OTHH
   round proved these attributions wrong twice).

## Acceptance

- Item-1 site: wall-top cross-band deltas 0 (per-station single value);
  corridor centered on the crossing road's envelope, width covering it;
  ramp profile monotone portal→grade (no interior local maxima beyond the
  materiality floor 0.01 m).
- Item-3 site: emitted road covers the mapped/DSF carriageway envelope;
  profile up to the bridge edge smooth under the 5% law with no
  over-cap rows minted at the seam.
- `tunnel_portal_acceptance --profile LEMD` not worsened anywhere;
  LEMD census not worsened; OTHH/HECA controls byte-identical or every
  delta attributed.

## AMENDMENT 1 (Fable, 2026-08-28, on lane/lemdfidelity's report)

MEASURED CORRECTIONS to this spec:
- The humps (item 1) are the WALL BAND'S OWN TOP (ring-order
  transition-law run down one band and back the other), not the ramp fan
  (monotone at 3%). §F1 (crest = function of station) is the fix — RATIFIED.
- The carriageway-PAIR hypothesis (law 2) is REFUTED: one chain, one
  road, lanes=2, corridor 7.03 m is correct. The centering defect is TWO
  SPELLINGS OF ONE ROAD — emitted centre 0.3 m off the OSM/feed line but
  2.75 m off the DSF chain X-Plane draws, so the ribbon hugs one wall.

RULINGS on the three stopped deviations:
1. AUTHORISED — corridor centre/width at a portal takes the ENVELOPE OF
   EVERY SPELLING of the crossing road (DSF chain + feed/OSM line,
   matched within a small radius): the cut exists to cover what the sim
   RENDERS plus what we emit; one spelling's centre is never authority
   over the other's ribbon.
2. AUTHORISED — a per-way width channel in the service-road minter
   (pavement/service_roads.build_service_road_network), width from the
   way's own lanes/width tags, DEFAULT UNCHANGED (6.0) so untagged
   networks are byte-identical; lanes=4 -> 14.0 at the item-3 site.
   Controls must show untagged airports byte-identical.
3. §F2/§F3 KEPT as landed (real classes, interventionally proven,
   positive-control attributed) even though neither is an owner-site
   lever.

DOCKETED: second wall emitter `bridges._emit_low_corridor_connectors`
(~line 5910) still samples DEM per node — owns the residual 0.34/0.24/
0.20 m twisted bands (-11960/-11930/-11961); follow-up round. OTHH §F1
family shifts (airside_no_step 132->140, road_cross_section 82->85
against three families improving) recorded for the ship gate.
