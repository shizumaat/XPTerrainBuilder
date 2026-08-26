# Portal corridor claim + per-piece named refusals (Fable spec,
# 2026-08-25; implements RULINGS 2026-08-25e — the mouth-D fix)

Evidence: the 2026-08-25 tunnel attribution, class 2. OTHH mouth D
(25.2789456, 51.5994543; ways r+25+051:-6785/-6786) is ADMITTED and
EMITTED (`[tunnel-cover-bore] admitted on cover (pavement=0.993)`,
cluster at (-1840,350)), then every piece is removed by three
aggregate-logging passes (`dropped N under pavement (covered
stretch)`, graze-clip, R14-1 stand-down) — 4 of 8 OTHH portal
clusters lose every ramp this way, and no remover names what it
deletes. `tunnel_portal_acceptance` FAILs the mouth at 806.1 m and
cannot see more, because absence is all there is to see.

## §1 The instrument FIRST (mandatory, lands before or with §2)

1. Every post-emit tunnel-piece remover (the covered-stretch drop,
   the graze-clip, the wall/roof/cap clip, `_stand_down_synthetic_
   over_claimed`, and any sibling found by grep) logs ONE line PER
   PIECE removed: `[tunnel-remove] <predicate>: ref=<ref>
   way=<id> @<lat,lon> coverage=<frac> cluster=<centroid>`.
   Aggregate counts may remain as summaries; the per-piece lines are
   the law. Verbosity: vprint(1).
2. Twin: a synthetic covered piece removed → the line carries the
   piece's identity; the summary count equals the line count.

## §2 The corridor claim (RULINGS 2026-08-25e option (a))

1. Where a mapped mouth's outward approach corridor lands on pavement
   that the walk today can neither cut nor claim (the mouth-D class:
   admitted, emitted, then removed for pavement coverage), the ramp
   CLAIMS the corridor's own footprint — the ramp-width strip of its
   walk — and lowers it to the bore profile. The claim extends the
   EXISTING R14-1 claim machinery (`_claim_road_pavement` /
   `tunnel_open_cut_claim_polys` and the stand-down predicate): one
   claim authority, never a parallel one.
2. Scope: the corridor FOOTPRINT only, never the host shape whole. A
   673,901 m² apron crossed by an 8 m ramp cedes the 8 m strip.
3. The host pavement around the claim grades to the lowered
   corridor's EDGES under its own law: the trench walls / retaining
   walls emit through the host exactly as at any bore (the R2
   node-split wall class); steps only at pavement gaps; the host's
   remaining area keeps its role, its law and its census population.
4. The three removers stop deleting pieces the claim now covers; a
   piece still removed (outside any claim, genuinely covered at
   grade) is removed WITH its §1 named line. No silent path remains.
5. Gate `O4_PORTAL_CORRIDOR_CLAIM`, default ON; OFF = today (silent
   removal becomes named removal via §1, which is ungated — the
   instrument is law, not behaviour).

## Twins

(a) Synthetic mouth whose approach crosses a pavement ring: ON — the
    corridor strip is claimed, the ramp emits at bore depth, walls
    emit at the strip edges, the host ring survives with its role;
    OFF — the pieces are removed with named lines.
(b) A genuinely covered-at-grade stretch (no mapped mouth) is still
    removed, with named lines, both flag states.
(c) The claim is corridor-footprint-scoped: host area outside the
    strip is untouched (geometry + role + caps).
(d) R14-1's existing stand-down still fires for synthetic rects over
    ALREADY-claimed pavement (one claim authority, no regression).

## Acceptance (ONE OTHH build)

- Mouth D EMITS: tunnel_ramp/tunnel_wall pieces within 80 m of
  25.2789456, 51.5994543; `tunnel_portal_acceptance` mouth-D distance
  collapses from 806.1 m (report the number).
- The other three ramp-less clusters from the attribution ((-1556,
  -470), (-1422,-2412), (-983,-2234)) re-read: emitted, or removed
  WITH named lines — zero unnamed removals patch-wide (grep the log).
- Site-1 (25.27158, 51.60244) unchanged vs the Amendment-4 arm (this
  spec must not disturb the node-book round; build on the SAME lane
  after Amendment 4 lands, so one arm carries both).
- OTHH airside byte-stable; adjudicated delta reported honestly (the
  new walls/trench through the host will move groundside counts —
  report the class table; no bar yet for the new class).
- Attempt cap 2, materiality 0.01 m; STOP on second miss. No
  shared-repo writes, no timing claims.

## Amendment 1 (Fable, 2026-08-25 — the stand-down requires a
## bore-depth claimant; resolves the mouth-D fork)

Measured (lane/tunnelmerge): with the phantom whole-shape claim fixed
to corridor footprints, mouth D's claimant is legitimate at share
~0.62 — but R14-1's own line reads "0 levelled at bore depth": the
level pass claims nothing at OTHH, so no claimed surface ever carries
the corridor, and the stand-down was deleting the ONLY below-grade
geometry (the synthetic ramp).

1. `_stand_down_synthetic_over_claimed` may stand a below-grade piece
   down ONLY when its claimant CARRIES BORE DEPTH — the claimed
   surface was actually levelled below grade at that footprint. An
   at-grade claimant never stands down a below-grade piece; the
   synthetic ramp IS the bore geometry there, exactly the case the
   stand-down exists to avoid duplicating, not deleting.
2. The refusal/keep decision is per-piece and named (§1's line gains
   the claimant's bore-depth verdict).
3. Twin: at-grade claimant + synthetic ramp → ramp survives, line
   names the keep; bore-depth claimant → stand-down fires as today.
4. Acceptance: mouth D EMITS (ramp pieces within 80 m of 25.2789456,
   51.5994543; portal-acceptance distance collapses from 806.1 m —
   report the number); the other stood-down clusters re-read; no
   double geometry where a claimant genuinely carries bore depth;
   site-1 and airside byte-stable vs the branch's current arm.

## Amendment 2 (Fable, 2026-08-25 — the claimed corridor's authored
## fields survive to emit; completes 25e's "claim and lower")

Measured (lane/tunnelmerge b656f3a9): mouth D's claimant way -12170
(19,325 m²) is lowered to -0.92 m and marked tunnel_road by R14-1 —
and ships as role=groundside_pavement ref=groundside with alt_abs on
0 of 66 nodes. A downstream groundside pass re-creates or
re-classifies the claimed shape and drops both the ref and every
authored altitude, so the corridor the stand-down lawfully trusted is
never written.

1. ATTRIBUTE the dropping pass (which rebuild/re-classification
   consumes the claimed shape and loses its fields), then fix AT
   SOURCE: a shape carrying an R14-1 claim verdict keeps its claimed
   ref and its authored corridor altitudes through every downstream
   rebuild to to_osm. No post-hoc re-stamping pass — the fields ride
   the shape.
2. Twin: a claimed-and-lowered shape survives a downstream rebuild
   with ref + altitudes intact; an unclaimed groundside shape is
   untouched.
3. Acceptance: mouth D's corridor emits below grade (portal-acceptance
   distance collapses from 727.6 m — report the number); the other
   claimed roads' emitted altitudes match their claim depths; site-1
   and airside byte-stable. Attempt cap 2 under this amendment.
