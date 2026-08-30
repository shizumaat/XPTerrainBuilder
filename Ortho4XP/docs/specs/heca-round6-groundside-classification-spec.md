# HECA round 6 — groundside classification + building merge + ramp residue
# (owner sim read of 1.0.269, 2026-08-30)

Six owner items, probed on the owner's patch (engine 1.50.1713, built
23:27). Three families. SITE-FIRST: each item closes at its coordinate
or shapeID, quoted first, current configuration.

## Family A — groundside/apron classification (items 2, 3, 5, 6)

- Item 5: shapeID 3151 (way -13146, 668 nodes, the scorer-v2 severed
  groundside piece) "should not be there at all" where it forms a THIN
  STRIP between taxiway and gap_interior_ring, minting bumps. The
  class-change cut severed correctly at the back edge but its severed
  piece includes slivers along airside edges. LAW: a severed groundside
  piece thinner than a service-road width along an airside edge is not
  a groundside surface — it merges into the adjacent airside grading
  (the adjacent-ground band), never a separate shape. Attribute which
  cut edges minted the slivers before fixing.
- Item 6: shapeIDs 2837/2838 (ways -12832/-12833) are mis-roled
  groundside_pavement — the owner reads them as APRON — with
  overlapping shapes present. Attribute the scorer decision (own-side
  evidence read) and the overlap; re-role and dedupe.
- Item 2: 30.1125699,31.4053664 — groundside shape 2836 sits several
  metres below the immediately adjacent taxiway junction (-10586,
  103.84-106.45): a cliff at a taxiway edge. LAW CONFIRMATION the owner
  asked for: taxiway adjacent-ground requirements (the graded-area
  zones law, adjacent_ground) must state a cliff cannot abut a taxiway
  — zones 1-2 grade FROM THE TAXIWAY regardless of which shape owns
  the ground (a shape boundary is not an exemption). Verify the law
  text, then close the gap that let a neighbour shape carry 93 m
  against a 104-106 m taxiway.
- Item 3: 30.1118886,31.4064793 — a service road area carried by the
  giant groundside shape 2836 drops 7 m from apron 585; it should be a
  ROAD ramping smoothly to 30.1123727,31.4059687. Classification first
  (is there road evidence there?), then the free-road ramp law (round-5
  family, already merged) applies once it is a road.

## Family B — building merge (item 1)

building79 (way -10079, shapeID 78): ONE flat ring at 97.85 spanning
~530x490 m — it encompasses FIVE buildings and their surrounding
pavement. Attribute the merge (building sources: "199 DSF + 27 OSM ->
215 seeds; 11 DSF clusters absorbed into OSM ways" — an OSM compound
way treated as one building, or hull-fill). LAW: a building pad is one
building's footprint; five buildings are five pads with the pavement
between them scored as pavement. Split per the source's own building
outlines.

## Family C — ramp residue (item 4, round-5 continuation)

30.1055367,31.3994026 "still seems low, should be a couple metres
higher", road climbing smoothly to taxiway at 30.1052593,31.3990067.
Probed: service_road 2822 (104.22-107.24) + service_junction 756
(104.1-108.3) — the climb exists in the span but the LEVEL is low and
the junction contact (junction 2675 at 107.89-109.64) still steps.
Under weld-outranks-cap (merged): attribute why the weld end is not at
the junction value and why the level sits low; fix within the merged
law, no new law expected.

## Acceptance

Each item at its coordinate/shapeID quoted first; HECA law-true census
not worsened beyond attributed re-roling; iterate on repro_cut/solve_cut
fixtures; ONE closing HECA build; controls via artifact ledger.
Below-bar = STOP with residual quoted.
