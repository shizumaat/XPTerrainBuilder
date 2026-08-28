# Claimed-corridor wall survival + ramp profile conformance (OTHH round 2)

Owner sim read of app 1.0.264, 2026-08-28 (OTHH, site 25.25591,51.6086926 and
patch-wide). Three read items, all attributed on the owner's own emitted patch
(`XPTerrainBuilderData/Patches/+20+050/+25+051/OTHH_auto.patch.osm`, built
07:00:43) plus a ledgered harness OTHH build (identical code):

1. "Emitting stuff with no walls; tunnel_ramp joining a tunnel_road and the
   tunnel_road wrapped by a service_road."
2. "Many tunnel ramps have humps in them instead of descending smoothly."
3. "Tunnels don't appear deep enough" — OPEN OWNER QUESTION (§Q), no
   implementation in this round without a ruling.

The role composite itself is the mouth-D claim design (RULINGS 2026-08-25e,
option (a)): claim = corridor footprint, host keeps its role. NOT a defect.
The missing walls and the humps are.

## Evidence (all reproduced this session)

- `tunnel_portal_acceptance --profile OTHH` on the owner patch:
  `claimed_corridor_walls` median face coverage **0%** over 15 below-grade
  claimed corridors (synthetic ramps median 4%); `ramp_wall_annulus_owned`
  **56/56** ramps' 0.6 m annulus unowned; `ramp_wall_gap` 21 welded node ids;
  `over_cap_ramp_rows` **225**, worst 853%, 173 of them on ONE
  `shape_interior_ring` (way -13104 @25.25353,51.62135) — the bare rim-to-
  floor cliff of an unwalled claim, i.e. the over-cap docket and the wall
  docket are one root cause.
- Harness build log (scratchpad othh_build.log of session 2026-08-28c):
  `§2.3 claimed-corridor walls: 15 bodies walled (20 pieces)` — the walls ARE
  born — followed by the removal ledger deleting them:
  `[tunnel-remove] covered-stretch drop: ref=tunnel_wall way=2291
  @25.2559488,51.6086658 coverage=0.743 area=319.4m2` (the owner's exact
  site), plus ways 2330/2341/2342 same portal at 0.948/0.964/0.985, ~20
  dropped + 12 graze-clipped to slivers patch-wide.

## §W1 — a wall follows its CLAIM as it follows its ramp

Mechanism: the covered-vs-graze discriminator (bridges.py ~6180-6280) judges
`tunnel_wall`/`tunnel_roof` against `_post_gate_u`, the airside gate union
AFTER `_tunnel_ramp_pavement_cut` — ruling 4's "a wall follows its ramp: it
must not be dropped for overlapping pavement its own ramp has removed". But
only synthetic RAMP footprints are cut. A claimed corridor lowers its host
without cutting it, so its §2.3 walls overlap host pavement 50-100% and drop
whole as "covered stretch".

Law: for wall/roof adjudication, the post-cut union additionally subtracts
every CLAIMED corridor footprint (the `_CLAIMED_BORE_REGISTER` population)
plus the wall band's own annulus — the claim variant of ruling 4's cut. The
mouth-D ruling's "walls/trench emit through the host as at any bore" becomes
true in the emitted patch, not only at mint.

Scope guard: subtract for ADJUDICATION only — the host shape's geometry is
untouched; genuinely roofed spans (the item-12 covered-span mask population,
e.g. under the terminal bridge) still drop their walls: a claim stretch that
is ALSO in the covered-span mask stays covered.

## §W2 — the claim edge takes the corridor profile (humps)

At the site, corridor descent is lawful (~4.5% < 5% cap) but its EDGE
vertices shared with senior grade-level neighbours stay pinned at grade
mid-descent: nodes -965/-968 pinned at 4.00 by `authority_retreat_wall`
-12605 crossing the ramp; -995/-996 by an apron seam (-12303); -977/-978 the
host ring popping to grade at the claim's deep end (where the mouth face
stands). Emitted as tents/humps in the descent.

Law: on the claim boundary, between the claim's mouths, the corridor profile
is senior — a crossing grade-level authority (retreat-wall stub, apron seam,
gap-fill spine) either takes the corridor's interpolated altitude at shared
nodes or stands down over the claim footprint (splits, as the corridor-
seniority pre-pass already does for pavement). A retreat wall crossing a
descending claim is itself a mis-scoped stub — it retreats around the claim,
never across it. Interventional twin required per mechanism-before-fix.

## Acceptance (the standing instrument, no new wrappers)

`tunnel_portal_acceptance --profile OTHH` on a rebuilt OTHH patch:
- `claimed_corridor_walls` median face coverage rises from 0% to the §2.3
  target (both sides, wrapped ends, minus genuinely covered spans).
- `over_cap_ramp_rows` 225 → the residue attributable to real geometry only
  (way -13104's 173 cliff rows gone).
- `site_reach`/`mouth_vertex_reach` site D 727.6 m → within bars (60/15 m).
- covered_span_clean stays 0 (the §W1 scope guard's twin).
- LEMD/HECA/CYXY control arms byte-identical or attributed.
- The removal ledger still names every deletion (no silent aggregate lines).

## §Q — OPEN OWNER QUESTION: bore depth

Current: service-road bores dig to `BRIDGE_ROAD_CLEARANCE_M = 5.1` m below
grade (config.py:5203; OTHH floor -1.1 vs flat-site datum 3.96);
`tunnel_depth_m = 8.0` is only the no-evidence fallback. Owner read:
"tunnels don't appear deep enough". Options: keep 5.1 / raise to 8 / other.
Note: at the 5% ramp cap each extra metre of depth adds ~20 m of ramp run.
NO change ships in this round without the ruling.
