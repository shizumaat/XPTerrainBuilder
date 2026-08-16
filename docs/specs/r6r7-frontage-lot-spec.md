# R6/R7 — Roads through pavement; mouths-only welds; cut-and-fill lots
# (Fable, 2026-08-15 late; all three laws OWNER-RULED, RULINGS.md)
Evidence: lot-over-road dossier + sink dossier (STATUS 20260815e/f).

R6 — SPINES THROUGH PAVEMENT: every road carries a spine; OSM road ways
are the source where no better chain exists (closes the no-substrate
population, HECA H1). A road spine does NOT stop at pavement: it
continues through lots/aprons/junction faces and the crossed pavement
CONSUMES its station values in the corridor band (the taxiway-through-
apron mechanism, reused not re-implemented). One corridor chain through
two faces valued apart (CYXY axis 182 / lot 377, 3.2 m) becomes
impossible.
R7a — THE FREE-ROAD KNIFE GAINS ITS LANDSIDE TERM: in
`groundside.free_road_subsegments`, a wide cross-section with NO
airside evidence (no OSM aeroway backing, outside the lawful airside
closure) is NOT "inside an apron" — the station stays a knife. Roads
through landside become their own faces and score `service_road`.
GUARD the two airside classes the width test was built for (SPJC east
terminal phantom junctions; HECA svc junctions 4→76): both are airside
and must be preserved by construction — measure both.
R7b — MOUTHS-ONLY WELDS: a road welds to an apron only at a MOUTH
(matches apron elevation, grades away under its own cap). A road NEVER
welds to a building (pad datums stay on their footprints). A road
parallel to an apron for > 1.5× its width takes the standard groundside
cutback and stays AT DEM (multi-level frontage is real — CYXY 2nd-story
road). R7c — LOTS CUT AND FILL: groundside lot surface = terrain
clamped into the weld-reachable band [weld − cap·d, weld + cap·d]
(supersedes min(terrain, cone)).
Acceptance: CYXY lot 377 tracks its terrain (median |dz| < 0.5 m; the
40 k m³ hollow gone); the owner's 3.2 m step site flat; HECA groundside
within_shape and steps fall by the dossier's attribution (report per
family); airside byte-identical at CYXY/HECA; SPJC + HECA guard
measurements; twins per clause. Materiality 0.01; attempt cap 2;
deviations STOP to the lead.

## AMENDMENTS (Fable, 2026-08-15 late, adjudicating the lane's 3 STOPs)
A1 — R7a's landside term becomes POSITIVE (the negative test is
refuted at DSF-pack airports where genuine apron carries no OSM/apt
evidence): a station reads LANDSIDE only on positive evidence — the
road-corridor / _PARKING_SERVICE / parking-aisle layer
pavement_classification already builds, OR outside the runway-touch
connectivity chain. Guard measurements (SPJC east terminal, HECA
junction counts) must PASS this time; HECA must build.
A2 — R7b clause 3's mechanism (ruled by the spec author): the cutback
is GEOMETRIC, via the existing groundside._separate_groundside_from_
airside machinery (its buffer + mouth-window + DEM-refollow) — a road
face edge-sharing or within GROUNDSIDE_CLEARANCE_M of an apron for a
contiguous span > 1.5× the road's own carriageway width is separated
(mouth windows exempt) and DEM-refollows. The 1.5× span measures the
road's edge-contact run against that apron.
A3 — the sink note: the building-pad channels stay closed (the law
stands) but the hollow's fix is R7c + the ruled route-metric law +
mouths-only welds acting on the junction network's own low values —
quote it that way, never as the pad fix.
