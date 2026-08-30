# OTHH round — canonical tunnel-mouth assembly (three owner sites)
# (owner sim read of 1.0.269, 2026-08-30)

Three owner items, probed on the owner's patch
(`XPTerrainBuilderData/Patches/+20+050/+25+051/OTHH_auto.patch.osm`,
engine 1.50.1713, built 2026-08-29 23:07). One family: the tunnel-mouth
assembly emits tangled, duplicated ramp/wall/road shapes where the
owner expects ONE canonical mouth: a simple straight end cap at the
tunnel mouth, a single wall along each side, and a single ramp down
the middle. SITE-FIRST.

## Item 1 — service_road wraps and edge-shares a tunnel_road; ramp stops
## short of the mouth

Site: 25.2557909,51.6083778. Probed: service_road shapeID 50 (way
-10051, 51 nodes) and tunnel_road 2309 (way -12306, 13 nodes) BOTH at
0.00 m with IDENTICAL alt span [-1.1,5.47] — two shapes carrying the
same corridor, edge-sharing/wrapped. Second tunnel_road 2308
(-1.08–4.01) and wall pieces 2303/2357/2358 lace around them.

Owner law read: a service_road must not wrap around and share edges
with a tunnel_road — the corridor is ONE surface. The tunnel ramp must
extend all the way DOWN to a tunnel mouth at 25.255673,51.6080375
(probed: the ramp/road pair passes 2.57 m away; nearest wall 7.06 m —
no walls AT the mouth), with retaining walls around it.

## Item 2 — other end of the same tunnel: dual adjacent ramps

Site: 25.2539129,51.6031915. Probed: within 10 m — dual service_road
tunnel_roads 2306 (0.52–2.48) and 2307 (-1.14–2.3) beside plain
service_roads 47 (-1.14–2.44) and 2304 (0.52–2.67); groundside
tunnel_road shapes 2323/2324 (aprons, 0.8–4.0); wall rings
2332/2333/2334/2335/2336/2367 interleaved. Owner: it should be a
SINGLE ramp down, not dual adjacent ones.

## Item 3 — walls within walls, multiple road segments

Site: 25.2715775,51.6023886. Probed: TEN retaining_wall ways within
12 m (2261/2344/2345 at 0.00 m; 2263/2340/2343/2371/2373/2374/2378
within 12 m — tunnel_wall and tunnel_wall_foot rings nested inside one
another, including flat 4.0 fragments 2373/2378 of 5 nodes), plus
three tunnel_road service_junctions (2314/2315/2317) and plain
junction 732 overlapping. Owner: a simple straight end cap at the
tunnel mouth, single walls along each side, a single ramp down the
middle.

## Law (the canonical mouth)

At a tunnel mouth the emitted set is exactly: ONE ramp surface
descending the corridor centre to the mouth line, ONE retaining wall
per side (wall + foot as the law family defines them), ONE straight
end cap at the mouth. No second road shape sharing the corridor
(service_road vs tunnel_road duplication is one surface twice), no
nested wall rings, no wall fragments. The ramp reaches the mouth line
— it does not stop short of it.

## Attribution first

The tunnel emitter family lives in bridges.py (standing attribution:
all six earlier OTHH defect classes were in the emitter, and the OSM
refresh is NOT the lever — do not touch the shared OSM data). The
tunneldockets round merged owner-signed mouth work (B2 mouth PASS,
foot-on-annulus, covered-stretch handling) — read that spec and the
round-2 wall-survival record (specs aed29ba4, docket work on
lane/tunwall2) BEFORE proposing mechanisms; a mechanism refuted there
stays refuted. Attribute per site: which emitter path minted each
duplicate/nested shape (wrap vs dual-carriageway split vs wall-ring
nesting vs mouth-cap absence), demonstrate on a cut fixture, then fix
in the emitter so the canonical set above is what emits.

## Acceptance

Each item closes at its coordinate, quoted first: item 1 — one
corridor surface, ramp reaching 25.255673,51.6080375, walls present
around the mouth; item 2 — single ramp; item 3 — end cap + one wall
per side + one centre ramp, nested/fragment walls gone. Synthetic-first
(repro_cut/solve_cut); ONE closing OTHH build via the harness; controls
via the artifact ledger; OTHH law-true census not worsened beyond
attributed dedupe. Below-bar = STOP with residual quoted.
