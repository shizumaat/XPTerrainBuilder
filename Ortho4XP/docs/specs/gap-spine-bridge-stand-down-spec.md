# Gap-spine bridge stand-down (Fable spec, 2026-08-27; owner ruling
# "2" on the HELD question — RULINGS 2026-08-27, HEAZ build refusal)

## §0 Measured frame (attribution commit 4d96a043, lane heazbisect;
## memory heaz-band-inversion-attributed)

HEAZ refuses to build on main since c6a85e9c
(`assert_no_final_band_inversion`, 43 of 1,478 nodes). Interventional
split: `O4_GAP_SPINE_BRIDGE=0` → clean; taut-strip off → same refusal.
Every inverted node is a station of the synthesized bridge chain: the
bridge mints a 286–331 m route at the 1.5 % taxiway cap (budgets
4.30–4.97 m) between runway 18/36 anchors (85.52–86.14) and runway
04/22 anchors (81.10–81.16) — spread 4.42–5.03 m, shortfall up to
0.66 m. The runway profiles were seated before the route existed;
feasibility-is-guaranteed holds (CIFP windows fit), the LAW question
was who yields. Owner: THE BRIDGE.

## §1 THE LAW — the stand-down guard

1. At bridge-candidate acceptance time (`gap_spine_bridge`, before any
   station is minted), compute the governing anchor values at the two
   route ends — the SAME values the band would carry for those ends
   (reuse the band/anchor machinery the refusal itself reads; never a
   second notion of "the end's value"). If |spread| > cap ×
   bridge-route-length, the candidate is REFUSED: a named log line
   (`[gap-spine] ICAO: bridge X–Y stands down: spread S over budget B`)
   and a sidecar evidence record (`gap_spine_stand_down` list), and
   the nodeless region stays unfilled — round-3 spine stations and the
   lattice are the anchor mechanism there, not synthesized routes.
2. No re-seat, no new cap class, no new constants: the cap and route
   length are the candidate's own existing budget inputs.
3. The existing flag `O4_GAP_SPINE_BRIDGE` is unchanged (0 still
   removes the mechanism entirely).

## §2 Twins

- Synthetic: two anchor groups spread > cap × route → candidate
  refused, loud line, sidecar record, no stations minted; spread
  within budget → bridge byte-identical to today.
- Register: the sidecar key joins the evidence keys the census prints
  (count only; a stand-down is not a defect row).

## §3 Acceptance

- HEAZ builds rc=0 on the lane tree; surface byte-identical to the
  `O4_GAP_SPINE_BRIDGE=0` arm at HEAZ (c6a85e9c's own contract: the
  bridge was HEAZ's only firing).
- HECA byte-identical (the bridge is inert there — Amendment 1 of the
  round-2 spec measured the premise refuted).
- Census recorded for HEAZ (its first main-tip census since c6a85e9c);
  SPJC/CYXY untouched (no bridge fires — assert via the log line).
- Convergence guards: materiality 0.01 m, attempt cap 2, heartbeat;
  no shared-repo writes, no timing claims; build-time impact statement
  (expect ~zero: one spread check per candidate).
