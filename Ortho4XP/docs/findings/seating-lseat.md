# Pack-object seating: one connected group (#1146, #1288, #1252) — lane lseat

Lane lseat, 2026-10-26, base `origin/main` 2184b16df. Instrument: the object stage
replayed offline (`tools/v2_rebake_replay.py plan`) on the owner's own rebake
plans and meshes — KLAX from the app build of 2026-10-20 (1.0.409, the build
the owner read for #1146), KMCI from 2026-10-24 (1.0.424). The KMCI replay at
main reproduces the owner's plan (4,819 bodies, zero diff on every body's zero;
2 extra bodies). Geometry probes read the authored OBJ8 files directly
(vertex-to-triangle distance, the same row-wise test `contact.py` uses).

## 1. #1146 KLAX elevated rail — attribution

The rail is ONE placement, `Misc/People_Mover/Tracks.obj` (index 5809): 261
solid components, 3.1 km x 0.7 km, a FLAG hard deck (`deck_top_y` +19.35),
FOOTLESS (no geometry at its ground band).

**In the owner's 1.0.409 plan** it was written as 32 bodies: 30 at
`footless_own_ground` (each on the ground under its own footprint, zeros
30.01 ... 32.55) and 2 `footless_carried_by_unit` (32.72 on pad building61,
31.30 on fu:146:2275/host). Adjacent pieces therefore stood up to 2.5 m apart —
the owner's "seated at slightly different levels ... look broken".

Why the pieces were asked one at a time: §16d (4) `_atom_targets` cuts a
carried body into its ATOMS (`placement_atom.comp_blocks`), and an atom is a
component or a §16c (6)/(7) cluster. The cluster test is VERTEX to vertex
(`contact_eps_m` 0.002 m), and the §16c (7) reach is not asked of a member with
more than 64 components. The rails lie ON the beams' top faces with no shared
vertex: measured on the authored file, vertex-to-vertex at 0.002 / 0.05 / 0.3
/ 1.0 m gives 261 / 261 / 240 / 105 clusters, vertex-to-FACE gives 256 / 5
(239 + 17 + 3 + 1 + 1) / 2 / 2. The atoms are touching pieces of one rigid
object, but each asked its own carrier and fell to its own ground. 22o
("connected objects stay as one group ... that touch or even come within a
meter ... must always move together") was implemented between §16g UNITS and
for unchained PARTS; an own-ground ATOM holds no part (#610: "an atom made only
of components the plan holds no part for has NO parts"), so neither the unit
chain, `unchained_links` (part rings) nor the #127 weld (part ids) can see it.

**At main (2184b16df) the same plan replays differently**: all 38 bodies at
ONE zero, 14.39 — `airside_deck_seat` (RULINGS 2026-10-22n, class A) reads the
rail as an airside hard-deck BRIDGE (path 2: no emitted deck face, 4 of the
ring's 80 vertices on airside faces, `deck_datum_z` 36.41) and seats its deck
top FLUSH with the solved airside at its "end lines" 36.29 / 31.20. The rail's
deck top lands at 33.74 over ground 30.0-32.6: the elevated track is lowered
16.4 m, its beams (authored y +8.9) about 7.5 m under the ground. This is a
separate defect from #1146's (it is one zero, but the wrong one) and it is
LIVE in every build since 22n. See §5 for why this lane does not fix it.

## 2. Rule R1 (implemented) — an own-ground piece moves with what it touches

Reading of RULINGS 2026-10-22o on the pieces of ONE placement; no new constant
(`open_frame_seat.TOUCH_M`, 1 m, is 22o's metre).

For every placement record, after the group passes (`rigid_open`,
`group_zero`) and before the deck cut:

1. The pieces are the record's bodies; a piece's authored geometry is its own
   triangles (`Body.tris`, else its whole components'). A piece with neither is
   not read.
2. Two pieces TOUCH when a vertex of one comes within `TOUCH_M` of a triangle
   of the other (vertex-to-face, both directions; authored frame, so the test
   is exact and independent of the seat).
3. An OWN-GROUND piece (`footless_own_ground`: "no carrier the law accepts")
   takes the zero of the piece it is connected to — through touching own-ground
   pieces, transitively. The zero is that of the connected NON-own-ground piece
   with the most triangles (a carried, unit-carried, deck-seated or footed piece:
   the law found it a seat); with none, of the own-ground piece with the most
   triangles (its own ground). Pieces of the component already within
   `tol_m` (0.05 m) of the zero are left as they are.
4. Only own-ground pieces move. A carried or unit-carried piece keeps its
   carrier's zero (a material file's pieces on two buildings stay on their two
   buildings — KMCI's Nghia/Thong trimsheets touch across buildings).
5. Counted: `own_ground_welded_bodies`, `own_ground_weld_groups`.

Asked only of a record with at least one own-ground piece and two zeros more
than `tol_m` apart (at the replayed KLAX plan: 1 placement; KMCI: placements
listed in §6).

Acceptance (#1146): replay of the owner's 1.0.409 KLAX plan through R1 with
class A as it stood then (or with class A refused for the rail): every
Tracks.obj own-ground piece at one zero; the residual step named (a piece
carried by a unit at another zero is not moved — 4).

## 3. #1288 KMCI garage ramp/bridge island — attribution (STOP: needs the owner)

Measured on the owner's 1.0.424 plan, frame `Airport/TerminalC-E/*` (one anchor
39.296474, -94.716002, heading 192.70, plain OBJECT rows):

* island unit fu:16:6934 — 13 bodies, 28 components (KCMO-Trimsheet-22/23,
  betong, line, concrete-6, Streetsign-1, brown) at 307.25: a concrete ramp
  (betong c0, y 0 ... 6.50), pillars (concrete-6, y -1.9 ... 4.7), stair towers
  (Trimsheet-23); its walls' feet are AUTHORED at y -0.65 / -1.79;
* garage unit fu:16:6923 — 31 bodies at 306.61, feet at y 0;
* both stand on the SAME flat pad building12 (306.60). Each is seated on its own
  feet on that pad, so the island stands 0.64 m higher than the author drew it
  relative to the garage (same frame, so the authored relation is exact).

**No authored geometry joins them.** Vertex-to-face over every component of the
frame: the nearest island-to-garage structure is 4.28 m (betong ramp to the
garage); nothing else in the frame (1,684 other components) comes within 5 m of
the island except one Trimsheet-23 b1 piece (1.91 m, itself at 307.25). The ONE
sub-metre link is a STREET SIGN: its pole (brown.obj c2, on the island deck,
y 5.71 ... 10.98) and its plate (Streetsign-1.obj c450, y 10.27 ... 10.80) are
0.19 m apart, the pole in the island group and the plate bound into the
garage's Streetsign-1 b1 — so the plate is written 0.64 m below where its pole
holds it (39.29525, -94.71457). Nothing within 15 m of the owner's site
(39.294641, -94.713640) is at the island's zero: the site is ON the garage roof
(carpark-roof-dark, darkconcretetile at y 12.3 ... 13.1, all at 306.61).

So 22o's connected-group rule does not reach the island and must not: 22o
splits "objects that are clearly at least a couple meters apart with no above
ground connecting shape", and 4.28 m with no connecting shape is that case.
R1 does not change it (the island is not own-ground; the sign straddles two
PLACEMENTS). What would change it is a PAD-LEVEL rule — "units of one frame
standing on one pad keep the frame's authored relative heights" — which puts
the island's feet 0.64 m into pad building12 (or needs a 0.64 m step in the
pad there, the 23f lower-level mechanism). That is a law choice for the owner.

Sim read needed (owner), at the KMCI Terminal C/E parking garage:
1. North of the garage, the concrete ramp with pillars and stair towers (the
   "bridge island", ~40-130 m north of your 39.294641, -94.713640 point, the
   garage's north face at ~40 m): what joins it to the garage — a deck, a
   walkway, a road — and where? Our files show a ~4 m gap with nothing in it.
2. Does the island look too high (0.64 m) against the garage, or is the
   garage too low?
3. On the island deck near its west stair tower (39.29525, -94.71457): a street
   sign whose plate sits 0.64 m below its pole top.

## 4. #1252 sibling packs' OBJECT_MSL rows — not implemented here

The scoping study on the issue stands (rule: every enabled non-library pack
with a DSF on the tile and at least one OBJECT_MSL row, or a non-zero-elevation
network/polygon node, inside the apt.dat 130 boundary; reseat only those rows;
KDFW 2 packs, KMCI / LFPG / KATL 0). It is a write-side feature on the user's
OTHER packs — backup, provenance, journal, restore on airport removal, freshness
— estimated by the study at 1-2 lane rounds, and neither closing airport of
this lane (KLAX, KMCI) has a sibling row to exercise it (KMCI 0). It needs its
own lane with KDFW as the test case.

## 5. Open for the owner (this lane stops here)

Q-a (#1146, the rail at main): an elevated rail / road viaduct is read as a
22n class-A taxiway bridge and seated with its deck top on the apron. 22n says
"a taxiway or runway carried over a road on a pack hard deck: its deck top
meets the solved airside surface where the taxiway drives onto it". No witness
on the plan separates the rail from LFPG's H18/H19 (deck top +13, flush zero
13 m under the ground at their anchors) or ELLX's Bridge_2 (1 of 13 ring
vertices airside) without a tuned threshold. Candidates, each measured:
(a) the deck must be flush at BOTH end lines within a bound — the two end-line
zeros differ by 5.09 m on the rail, at most 1.74 m on LFPG (H2), 0.95 m ELLX;
(b) only a deck the planar stage emitted a bridge_deck face for is class A —
no airport in the owner's current plans has one (KLAX, YSSY, ELLX, LFPG all
take the ring-role path), so (b) would end class A everywhere;
(c) a deck whose authored top stands more than N m over its authored ground is
never driven onto — LFPG H18r is +13.11, the rail +19.35;
(d) the airside must reach the deck along a share of its edge — of the ring's
5 m perimeter stations, airside outside: rail 46 / 1,490 (3.1 %), lowest
genuine decks ELLX Bridge_2.003 10 / 94 (10.6 %) and LFPG H16 9 / 60 (15 %).
Each of (a), (c), (d) separates the rail only by a threshold chosen between
the rail and one named airport's deck — the tuning RULINGS 05e forbids without
the owner's rule.
Until ruled, KLAX's APM track is lowered 16.4 m at main.

Q-b (#1288): pad-level rule (§3) or the owner's witness of the connection.
