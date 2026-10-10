# level549 — summary (spec author, #549 / #519: KCLT garage group; design only)

Spec: `Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` **§64** (design-surface spec, not the object
spec: the defect and the rule are in the pad outline / plane group / pad seat; the object stage is unchanged).
Notes: `docs/briefs/level549-notes.md`. Probes + arm: `<scratchpad>/level549/` (p1–p11, `arm_group.py`).
Frames registered under lane `level549`: base replay patch + arm G patch (both `frames/valley2/KCLT.pkl --from classify`).

## 1 Attribution (owner's 1.0.387 frame; plan sw11 v13; DEM off frames/valley2/KCLT.pkl)
* The garages are BODIES of the terminal's 20 object files at ONE `OBJECT` anchor (35.221229591, -80.943372339,
  plan `unit:31`; 0 MSL rows in the pack). Grounded walled bodies on building88 / 90 / 86 / 92 / 84 / 75: authored
  base y 0.000 +- 0.034 m. PREMISE TRUE: one rigid level by construction = the terminal's own ground (DEM 220.15
  at the anchor), not a constant.
* Today: building88 (hourly deck, 22,027 m2) 223.21 over DEM 218.0-219.3 (rim z-DEM +3.9..+5.2, 28/28 over 1 m);
  building90 218.99 (DEM 218.1-222.1, the 3.1 m hole on its uphill rim); building86 218.11 at its ground;
  building92 223.67 HELD by the pav14 plateau (`--why-at`: pad_frontage_level + platform_plane bind) over a
  hillside 222.3-228.9; the ground BETWEEN 86/88/90 (2.42 ha) is raw DEM 218.03 / 218.23 / 219.22.
* Object stage: `fu:31:2809@cluster_pad` seats all 14 bodies at ONE zero = building88's 223.21; 10 of them stand
  over building90 / 86 / raw ground (`ground_off` 3.15-5.13) = the owner's floats (6.27 / 5.76 / 5.56 m sites
  are `paredes_10` b3 / b8 / b5). The toll plaza and the `vidrios_*` glass are kept-whole / alone-seated files
  (lane kclt546, #519) — not members of the unit; they compose by construction once re-cut.
* WHAT HOLDS building88 AT 223.21 (`--why-from base.solved.pkl --why-at 35.2242287,-80.9428688`): no hard row —
  "the objective holds it". It is NOT the terminal's plane: `plane_groups` lists the three garages as three
  PIECES of ONE cluster `cluster:unit:31#1117/0,/2,/4` (the design cluster = the object unit), each piece its own
  pad and plane (`geom/cluster_outline` rule 2 `still_in_pieces`, §16g (10) (5)); removing the three per-piece
  entries (arm G) drops the deck to 218.5. WHICH soft term carries the 223.21 is UNPROVEN (candidate: the §9b mean
  over a mis-indexed rim — the entry's 29 rim ids are not face 1009's ring; §20 fronting excluded, nearest apron
  180 m > 50 m reach).

## 2 Witness (population at 7 airports; p6/p8/p8b/p10)
* W1 "one anchor family + equal authored base": TRUE of every big pack (KCLT unit:3 66 pads over 22.5 m relief,
  HECA unit:41 72 pads over 45 m) -> REFUTED as a level witness (the LSGG class; §16c/§16g re-cut by law).
* W2/W3 plan-chain at gap <= D: fires on {86,88,90} at D = 10 m and on 10-20 HECA chains per D (spreads 1-7 m)
  -> over-fires; D is a tuned number.
* W4 THE §16g UNIT / §30 (4) CLUSTER ITSELF, landside (no piece fronts airside, none Rule-L fixed) and in PIECES
  or with bodies off the pad: KCLT exactly one (`fu:31:2809`, worst 5.13 m); HECA 21 / OTHH 18 / KASE 17 units
  have a body > 2 m off its zero on the OBJECT side (T3 landings, viaducts, mountainside pairs) but "landside AND
  in pieces" is read only at KCLT — step 1's replays name the rest.

## 3 Rule (§64 (3)) — smallest narrowing of what exists, no new class, no new law value
(a) the pieces of a LANDSIDE cluster stay ONE plane-group entry (narrow §16g (10) (5) / `_split_blocks`);
(b) the pad covers the whole unit: grounded leaf/thin bodies (|base_y - unit base| <= floor_split_m, with feet)
    enter rule 2's union before the 0.5 m close (elevated plates still link nothing — HECA T3 twin kept);
(c) level: held piece -> §30 (4) as today; else the group's §9b DEM datum (10a (2), §63 Rule S) — NOT a touching
    road (09j: pad senior), NOT an authored absolute (none stated), NOT a cut/fill optimum (the datum is one);
(d) edge: 09d (1) bare = raw DEM, touching pavement welds (§63 W), gapped road free; (e) objects unchanged
    (§16g (2) reads the one pad); (f) composes with kclt546 by construction. Consumer table: 16 rows, §64 (4).

## 4 Probe — arm G on frames/valley2/KCLT.pkl (per-piece entries withdrawn; rule (a)+(c), no minted between)
building88 223.21 -> 218.52-218.57 (rim z-DEM +3.9..+5.2 -> -0.8..+0.6, 0/28 over 1 m); building90 -> 218.41-218.89
(uphill rim -3.6 m cut remains: a garage on sloping ground); building86 -> 218.40-218.78; spread of the three
5.10 -> 0.48 m; AIRSIDE MOVERS 0 of 14,894; solve optimal; verify families identical except pad_flat 66 -> 68,
defects {}; hard relaxed 309 = 309. Unit zero (dry, plan numbers - 4.66): the 10 off-pad bodies 3.15-5.13 ->
-1.51..+0.47 (over 0.5 m: 10 -> 1, worst 5.13 -> 1.51, the one in building90's cut). The between stays raw DEM,
within 0.8 m of the level (step 3's change at KCLT <= 0.8 m). seat_feet window census (per split body vs its own
anchor — not the unit-zero instrument): 23 -> 19 over 0.5 m; the three > 1 m are roadway-spanning bodies
(kclt546's class). The witness fires nowhere else among the seven on the design side (nearest misses listed).

## 5 Implementation (§64 (6)): 1 one plane for a landside cluster's pieces (3 h) -> 2 VERIFY the §9b rim index
space (1-3 h) -> 3 grounded leaves in the outline, new capture (6 h) -> 4 records (2 h) -> 5 KCLT once + sweep.

## 6 Owner questions (§64 (8))
Q1 LEVEL: the ground's DEM datum (~218.5; recommend YES) vs the terminal's level as an authored absolute (222.4+,
   4.6-5.2 m of fill under ~5 ha; would also bind unit:3's 66 pads / HECA's 72 — already ruled the other way).
Q2 BETWEEN: mint the ground between to the group level (step 3; recommend YES, after steps 1-2 are sim-read).

## Not done
No engine code (design lane); the soft term holding piece /2 not named (step 2 reads it); no plan rebuild (the
dry ground_off arithmetic stands in); no second-airport arm (the witness fires nowhere else on the design side —
HECA's `fu:42:944` etc. are read on the object side only); no airport build; map PNG not rendered (no matplotlib).
