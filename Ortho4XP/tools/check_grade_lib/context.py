"""THE SIDECAR LAW CONTEXT: the metre frame a patch is read in and the
law keywords its ``.axes.json`` declares — ``law_context_from_sidecar``,
the one reader the CLI, the census and the pytest fixtures share.  Moved
verbatim from ``check_grade.py`` (issue #857), which re-exports it."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: The sidecar key that carries the BUILDER's projection anchor WHEN THE
#: PATCH HAS ONE.  v1 wrote it; v2's register
#: (``auto_patch_v2.emit.osm_adapter.SIDECAR_KEYS``) deliberately does
#: NOT — so a reader that SUBSCRIPTS it dies with ``KeyError: 'anchor'``
#: on every current patch, which is what both read tools did (issue #147
#: for ``lattice_overlap_read``, RULINGS 2026-09-13cs for
#: ``role_overlap_read``).  Read through :func:`sidecar_anchor`, never
#: spelled again.
SIDECAR_ANCHOR_KEY = "anchor"

#: The two metre frames a patch can be read in, NAMED — so a reader can
#: print the frame in force and two reads are never quoted across frames
#: (the x-scale differs by ``cos(lat0)``: millimetres over a chord, which
#: is enough to flip an epsilon contact predicate).
FRAME_BUILDER_ANCHOR = "builder anchor"
FRAME_MEAN_OF_NODES = "mean-of-nodes"
#: The frame a patch that declares no ``anchor`` is read in: the origin
#: taken from the patch's own SIDECAR-DECLARED geometry
#: (:data:`SIDECAR_FRAME_DATUM_KEYS`) rather than from its node multiset.
#: Issue #215 — see :func:`_sidecar_frame_datum`.
FRAME_SIDECAR_DATUM = "sidecar law datum"

#: THE FRAME DATUM KEYS (issue #215), in the order they are read.  A
#: patch that declares no ``anchor`` takes its metre-frame origin from
#: the first of these its sidecar carries.  Every one is a BUILD
#: DECLARATION — ``runway_axes`` is ``[ref, lat_a, lon_a, lat_b, lon_b,
#: half_m]`` off the apt.dat ends and width (never a fit to the emitted
#: rings), ``axes`` / ``axes_exact`` are the published centrelines,
#: ``seam_pins`` the tile cut — so each is a function of what the BUILD
#: declared and NOT of how many vertices the emitted patch happens to
#: carry.  That is the whole point: see :func:`_sidecar_frame_datum`.
SIDECAR_FRAME_DATUM_KEYS: Tuple[str, ...] = (
    "runway_axes", "axes_exact", "axes", "seam_pins")


def _frame_datum_points(key: str, value) -> "List[Tuple[float, float]]":
    """Every ``(lat, lon)`` the sidecar key ``key`` declares, by that
    key's OWN published shape — explicit per key, never a guessing walk
    over nested lists (a walker that mistook a cap for a latitude would
    put the frame origin in the Gulf of Guinea and every metre would
    still read plausibly)."""
    out: "List[Tuple[float, float]]" = []
    if key == "runway_axes":
        # ``[ref, lat_a, lon_a, lat_b, lon_b, half_m]`` (§40 (2))
        for r in value or ():
            if isinstance(r, (list, tuple)) and len(r) >= 5:
                out.append((float(r[1]), float(r[2])))
                out.append((float(r[3]), float(r[4])))
    elif key in ("axes_exact", "axes"):
        # ``[[[lat, lon], ...], cL, cT, ordinal, is_service]`` per axis
        for e in value or ():
            if not (isinstance(e, (list, tuple)) and e):
                continue
            pts = e[0]
            if not isinstance(pts, (list, tuple)):
                continue
            for q in pts:
                if isinstance(q, (list, tuple)) and len(q) >= 2:
                    out.append((float(q[0]), float(q[1])))
    elif key == "seam_pins":
        for q in value or ():
            if isinstance(q, (list, tuple)) and len(q) >= 2:
                out.append((float(q[0]), float(q[1])))
    return out


def _sidecar_frame_datum(sidecar: "Optional[Dict[str, Any]]"
                         ) -> "Optional[Tuple[float, float]]":
    """A POPULATION-INDEPENDENT frame origin from the patch's own
    sidecar, or ``None`` when it declares no geometry to take one from.

    THE DEFECT THIS CLOSES (issue #215).  A census verdict may depend
    only on the geometry it judges and the sidecar law context — never on
    the patch's node POPULATION.  ``_ll_to_m_factory``'s fallback origin
    is the MEAN OF NODES, so adding or removing a vertex anywhere moves
    the frame; and because the frame's x scale is ``cos(lat0)``, moving
    ``lat0`` rescales every projected x.  v2's sidecar register
    (``auto_patch_v2.emit.osm_adapter.SIDECAR_KEYS``) deliberately
    publishes no ``anchor``, so EVERY current patch is censused in that
    moving frame.

    Measured on this repo's own synthetic twin
    (``tests/test_census_frame_population.py``): 400 unrelated apron
    nodes 40 km away, not one strip or runway coordinate touched, moved
    the derived runway length 1200.975 m -> 1198.982 m.  Across
    ``config.runway_code_number``'s 1200 m step that is aerodrome code 3
    against code 2, which is ``ruleset_strip_half_width_m`` 75 m against
    40 m and ``grade_law.strip_longitudinal_law`` 1.75 % against 1.5 % —
    the strip footprint itself changed by 35 m and the ``strip_arc``
    reading went 1 row / 198 stations to 0 rows / 99 stations.  That is
    the #215 signature (``sw1003_HECA`` 0 rows, ``sw1004b_HECA`` 1) with
    the mechanism in the open.

    The origin is the ``min()`` over every point the chosen key declares,
    so the key's own LIST ORDER cannot move the frame either (the
    ``_strip_chain_start`` lesson: a canonical choice, not the first
    element of an array whose order is an emitter detail).

    NOT closed here: ``grade_law.runway_axis_and_width`` is
    vertex-count-weighted (issue #190, ``needs-owner``), so the derived
    length still drifts with the RUNWAY's own vertex multiset and the
    code tables remain a knife edge under it.  #215 is the FRAME; #190 is
    the fit.  Fixing the frame removes the whole-patch coupling and
    leaves #190's runway-ring coupling exactly where its issue puts it.
    """
    side = sidecar or {}
    for key in SIDECAR_FRAME_DATUM_KEYS:
        if key not in side:
            continue
        try:
            pts = _frame_datum_points(key, side[key])
        except (TypeError, ValueError, IndexError):
            continue
        if pts:
            return min(pts)
    return None


def sidecar_anchor(sidecar: "Optional[Dict[str, Any]]"
                   ) -> "Optional[Tuple[float, float]]":
    """The patch's POPULATION-INDEPENDENT metre-frame origin: the
    builder's projection anchor a ``.axes.json`` DECLARES, else one
    derived from the sidecar's own declared geometry
    (:func:`_sidecar_frame_datum`), else ``None`` when it carries
    neither.

    THE one read of :data:`SIDECAR_ANCHOR_KEY` and the one derivation
    site for the frame origin, so a tool and the census never disagree
    about which frame a patch is read in.  ``None`` now means the
    sidecar declares NO frame at all — the caller then falls back to
    ``_ll_to_m_factory``'s mean of nodes, which is population-DEPENDENT
    (issue #215) and is named :data:`FRAME_MEAN_OF_NODES` so no report
    can mistake it for a declared frame.
    """
    a = (sidecar or {}).get(SIDECAR_ANCHOR_KEY)
    if a:
        return (float(a[0]), float(a[1]))
    return _sidecar_frame_datum(sidecar)


def sidecar_frame_name(sidecar: "Optional[Dict[str, Any]]") -> str:
    """Which of the three frames :func:`sidecar_anchor` just handed back,
    for the report — THE one naming site, so two tools cannot print two
    names for one frame."""
    if (sidecar or {}).get(SIDECAR_ANCHOR_KEY):
        return FRAME_BUILDER_ANCHOR
    if _sidecar_frame_datum(sidecar) is not None:
        return FRAME_SIDECAR_DATUM
    return FRAME_MEAN_OF_NODES


#: Sidecar key -> ``run_checks`` keyword.  THE contract between an emitted
#: patch and every reader of it.  ``law_context_from_sidecar`` is the only
#: implementation; the CLI, ``tools/harness/census.py`` and the pytest
#: fixtures all go through it, so a new sidecar key is wired in ONE place.
#: (``axes``/``routes`` are the legacy pre-exact spelling and are used only
#: when ``axes_exact`` is absent — see ``law_context_from_sidecar``.)
SIDECAR_LAW_KEYS: Dict[str, str] = {
    "axes_exact": "taxi_axes_ll",
    "routes_exact": "routes_ll",
    "anchor": "anchor",
    "seam_pins": "seam_pins_ll",
    # §16g (10) (12) (2): the airside nodes the pad stage minted/deleted
    "pad_airside_renode": "pad_airside_renode_ll",
    # jetway-strip spec §2 (6): the strips, their levels, vertices, clamps
    "jetway_strips": "jetway_strips_ll",
    # unit-platform spec §4 (5): the platforms, their planes and relief
    "platforms": "platforms_ll",
    # flat-pad spec v2 §5a: the hard rows the feasibility LP relaxed
    "hard_conflict": "hard_conflict_ll",
    # §38 (3)/(5): the band's own half width, so ``bank_across_seam``
    # reads "inside the band" from the law the BUILD ran under
    "seam_half_width_m": "seam_half_width_m",
    # §39 (1)/(2) THE HAIRLINE LAW: the FOREIGN water edges the emitter's
    # shore weld ran against — so ``hairline_pair`` prices the population
    # the law ran on and never a second water witness
    "shore_edges": "shore_edges_ll",
    # §37 (11) (7) (owner RULINGS 2026-09-27a (7)): the natural-shore
    # wedges — the runway-edge tie reads the bank-slope fall inside them
    "natural_shore": "natural_shore_ll",
    # OWNER RULINGS 2026-10-02ag (2): the strip tie withdrawn under a ribbon
    "road_cap_governs": "road_cap_governs_ll",
    # RULINGS 2026-10-15j: a non-runway pavement's own lip in an end area
    "end_profile_yields": "end_profile_yields_ll",
    # §33 (6): the object cuts the emitted patch must answer to
    "object_cuts": "object_cuts_ll",
    "mesh_edges": "mesh_edges_ll",
    # RULINGS 2026-09-05ae(1): a soft face's holes by ``shapeID`` — an apron
    # chord crossing one is no pair (``grade_graph._visibility_predicate``)
    "face_holes": "face_holes_ll",
    "crown_drops": "crown_drops_ll",
    # §40 (2) as amended: the runway/shoulder line and the shoulder cap
    "runway_axes": "runway_axes_ll",
    "shoulder_transverse_max": "shoulder_transverse_max",
    # RULINGS 2026-10-16a (i): the shoulder vertices a taxi route crosses
    # (the taxiway's law governs them, not the shoulder's)
    "shoulder_taxi_crossings": "shoulder_taxi_crossings_ll",
    # §50.1 (4) THE RUNWAY'S EFFECTIVE LONGITUDINAL CAP (owner RULINGS
    # 2026-09-18d (3), answered 18f): one record per runway — the code,
    # the ruleset, the TABLE's cap and the cap the build actually priced
    # it at (yielded to its own hard pins where they demand more).  LAW
    # INPUT: this file's own table is a flat 1.5 % for every runway, which
    # 18f makes wrong in BOTH directions (2 % code 1/2, 1.25 % code 4),
    # and a yielded runway is judged under a law its build refused.  A
    # patch with no key reads exactly as before.
    "runway_caps": "runway_caps",
    # THE PAD'S RELIEF TARGET (owner RULINGS 2026-09-11j; ratified 11l (2);
    # spec ``object-placement-spec.md`` §11a (2)/(4)): per pad vertex, the
    # metres the emitted terrain stands ABOVE the pad's own LEVEL.  LAW
    # INPUT, and of the strongest kind: the solve PRICED the pad flat on
    # its level plane (``constraints/pad_relief``, ``Diff.rel``) and the
    # in-build verify reads it there (``verify/pads.relief_offsets``), so
    # a census without this key judges a law the build never ran under and
    # reports every relief pad's designed steps as ``within_shape`` /
    # ``plane_gradient`` rows.  A patch with no key reads exactly as before.
    "pad_relief": "pad_relief_ll",
    # §37 (7) THE ROAD PAIR LAW'S ROUTE FRAME (owner RULINGS 2026-09-13av;
    # ``_road_frame_by_nid``): LAW INPUT — the road's pairs are priced over
    # the ROUTE, so a census without it judges the chord law the ruling
    # withdrew.  A patch with no key reads exactly as before.
    "road_route_frame": "road_route_frame_ll",
    # §37 (9) (RULINGS 2026-09-13be): the core ribbon's altitude at each
    # coverage exit — LAW INPUT, the value the solve PINNED.
    "road_coverage_join": "road_coverage_join_ll",
    # issue #623 THE GROUND ENVELOPE: ``[lowest, highest]`` lawful elevation
    # of the map (``auto_patch_v2/solve/ground_band.py``) — LAW INPUT for
    # ``sentinel_elevation``.  A patch with no key is read against its own
    # robust band, as before.
    "ground_envelope": "ground_envelope",
    "crown_centerline": "crown_centerline_ll",
    "pair_caps": "pair_caps_ll",
    # TAXIWAY STRETCHES (RULINGS 2026-09-04t-3 / 04y): the v2 emitter's
    # per-stretch centrelines with their letter caps.  LAW INPUT for the
    # JUNCTION STRETCH CAPS reading (``_junction_stretch_caps``): a
    # junction body pair priced at the body cap takes the cap of the
    # stretch nearest its midpoint — the reading v2 solved to.
    "stretches": "stretches_ll",
    # THE PER-STATION CAP VECTOR (owner 2026-08-29, Amendment 9).  LAW
    # INPUT: the cap authority lives at the STATION, and this is the ONE
    # derivation the emitter's three readers price with.  Without it the
    # census prices every station at the way-level tag and a
    # lawfully-per-station road over-reports (5j: +100 rows at CYXY AND
    # SPJC).  Registered here so the harness twins cover it and an old
    # patch degrades loudly rather than silently.
    "station_caps": "station_caps_ll",
    "terrace_joints": "terrace_joints_ll",
    "fan_ramp_zones": "fan_ramp_zones_ll",
    # THE APRON INTERIOR LATTICE's own law edges (spec
    # heca-apron-round2 Amendment 1 section 1b, Amendment 2 clause 3).
    # LAW INPUT, and the only possible kind: a lattice edge joins two
    # INTERIOR nodes that lie on no ring, so no ring-adjacency rule can
    # discover it and no cap table can re-derive its budget.  The solve
    # priced each edge through classify_pair at the apron's own cap and
    # publishes the pair WITH that budget, so the family below checks
    # the emitted membrane against the law the solver actually built to
    # — one law, one number, no second opinion.
    "apron_lattice_edges": "apron_lattice_edges_ll",
    # THE AIRSIDE NO-STEP LAW's direct-distance law edges (owner ruling
    # RULINGS 2026-08-27; spec ``airside-no-step-law-spec.md`` §1.6).
    # LAW INPUT of the same kind and for a stronger reason: the pair may
    # cross a SHAPE BOUNDARY, so no within-shape rule can rediscover it,
    # and its cap came out of the pair's own frontage / corridor /
    # back-edge / strip context.  The solve publishes the pair with the
    # budget it built to; the family below prices EXACTLY that list.
    "airside_no_step_edges": "airside_no_step_edges_ll",
    # THE BACK-EDGE ZONES the apron 5 % class was priced with (owner
    # ruling RULINGS 2026-08-24).  LAW INPUT: the census reaches
    # ``grade_law.is_apron_interior`` through the SAME context field the
    # bake filled, so a census without this key would price every
    # back-edge pair strict and invent violations the law never had.
    "interior_zones": "interior_zones_ll",
    "disconnected_rings": "disconnected_rings_ll",
    # THE DECLARED BASIN FACILITIES (spec docs/specs/
    # tunnel-trench-law-and-basin-floor-spec.md §1).  LAW INPUT since this
    # round — it was EVIDENCE while nothing read it, and the census then
    # priced every by-law trench wall as a step (LEMD 11,110 rows of
    # 12,253, OTHH 5,616 of 5,871).  The floor→rim drop each facility
    # declares is the allowance its own contacts are judged against, and
    # its two bottom instruments are the ``basin_floor_declaration``
    # family — so a census without this key would judge a law the build
    # never ran under, in both directions.
    "basin_facilities": "basin_facilities",
    # THE OPEN CHANNELS (spec §45; owner RULINGS 2026-09-15i).  LAW
    # INPUT: the floor datum a channel declares is what its own floor is
    # judged against, and no patch carries it — the record does.
    "channel_facilities": "channel_facilities",
    # THE ACCEPTED END-AROUND TAXIWAY RECTS (spec §36; owner RULINGS
    # 2026-09-13j item 2).  LAW INPUT: recognition needs the apt.dat route
    # network and the runway ends, which no patch carries, so the rects the
    # solve accepted — with the regulation value each was pinned at — are
    # declared here and the ``eat_ceiling`` family prices exactly them.  A
    # patch with no key (v1's own output, or a v2 patch predating §36)
    # reports nothing in that family, as it did before.
    "eat_rects": "eat_rects",
    # §16g (10) (3) THE DECLARED PAD<->CLUSTER DEFECT SET (owner RULINGS
    # 2026-09-14x).  LAW INPUT: a cluster is a relation between the
    # emitted pads and the PACK's footprint outlines, which no patch
    # carries, so the build declares the records and the
    # ``pad_cluster_mismatch`` family prices exactly them.
    "pad_cluster_mismatch": "pad_cluster_mismatch",
    "ruleset": "ruleset",
    # THE TIERED APRON LAW the build priced (owner RULINGS 2026-09-06w):
    # ``{preferred, max, fan}`` as fractions, published by v2
    # (``pipeline.publication.apron_tier``).  LAW INPUT: an apron-law pair
    # (an ``apron`` / ``building`` way, a 04t-2 portion pair) is judged at
    # ``max`` (1.5 %), and the rows above ``preferred`` (1 %) are the
    # REPORT FIGURE ``apron_over_preference`` (``_APRON_PREF_STATS``),
    # never a violation.  A v1 patch has no key and reads exactly as before.
    "apron_tier": "apron_tier",
    # THE LAST RESORT's relaxed rows (RULINGS 2026-09-04t(1); spawner
    # ruling 04x-2, 2026-09-04): the rows v2's IIS-scoped relaxation gave
    # a slack, with their relaxed caps.  LAW INPUT: a row relaxed under
    # 04t(1) is a LAWFUL last resort — the census prices it at its
    # RELAXED cap and reports it under the ``relaxed_by_04t1`` heading,
    # never as a violation; an airport with only relaxed rows is at zero.
    "relaxed_rows": "relaxed_rows",
    # THE YIELDED ROWS (RULINGS 2026-09-08d (2)): the rows the yielding
    # families hold above their cap, with their built grade.  LAW INPUT:
    # priced at the built grade and reported under ``yielded_by_08d``;
    # the law-true count of the same rows is the family's own.
    "yielded_rows": "yielded_rows",
    # THE BOUND TRANSECTS (owner ruling 2026-08-21; spec section 11 +
    # AMENDMENT A1 section 8b).  LAW INPUT, not evidence: the census
    # re-walks the emitted ring and joins these to report priced / bound /
    # unbound / broken_by_emit, which is this round's measurement.
    "xsection_spans": "xsection_spans",
    # THE LAST STAGE's own record (spec §55 (15) rule B): ``{"floor_m",
    # "followers"}`` — the floor it widened its all-unknown ceilings by and
    # the follower ribbons' refs.  LAW INPUT: the census prices a pair of
    # two last-stage unknowns at ``cap·d + floor_m`` in ``within_shape``,
    # ``pavement_over_road_cap`` and ``cross_shape``
    # (``late_stage_unknown_nodes``).  Absent on a build with no last
    # stage, and the census is then exactly the old one.
    "late_stage": "late_stage",
}

#: Sidecar keys that are EVIDENCE, not law input: they are reported by the
#: census but never passed to ``run_checks``.  Every key an emitted sidecar
#: carries must appear here or in ``SIDECAR_LAW_KEYS`` (twin-asserted), so a
#: newly emitted key can never be silently ignored by every reader.
SIDECAR_EVIDENCE_KEYS: Tuple[str, ...] = (
    # #1028: a SLID tunnel mouth's own depth over its floor (the road's
    # profile, ``pipeline/publication.tunnel_mouth_depths``).  EVIDENCE: v2
    # verify's ``tunnel_mouth_canonical`` reads it off the publication.
    "tunnel_mouth_depths",
    # §34 (9) THE PINCHED RAMP (owner RULINGS 2026-09-14ak/14am, sidecar
    # ``lifted_caps``): ``[shapeID, corridor, road ref, span m, designed
    # grade]`` per ramp face whose within-shape LONGITUDINAL cap is LIFTED
    # — the record §34 (9) (3) reports by name.  EVIDENCE: the LIFT itself
    # rides on the way as ``o4_grade_law_cap_lifted``
    # (:data:`LIFTED_CAP_TAG`, read per pair in ``_check_within_shape``),
    # so this list prices nothing and a reader that lost it would still
    # adjudicate identically.
    "lifted_caps",
    # 30ah (1) TAXIWAYS YIELD WITH THEIR RUNWAY (owner RULINGS 2026-09-30ah
    # (1), issue #135): per tied taxi-family face ``{shape, cap, table,
    # ref, runway_cap}``.  EVIDENCE here: the yield rides on the way as
    # ``o4_grade_law_cap_taxi_yield`` (:data:`TAXI_YIELD_CAP_TAG`, read per
    # pair in ``_check_within_shape``); v2 verify reads this list.
    "taxi_yield_caps",
    # THE DESIGN SURFACE's residual per family (RULINGS 2026-09-08t, sidecar
    # ``design``, replacing ``law_tiers``): rounds, unknowns, rows, the hard
    # runway rows and per family how many targets were missed and by how
    # much.  EVIDENCE: nothing here re-prices a row — under the design
    # surface every law but the runway family's is a TARGET, and a missed
    # target IS a census row, counted law-true in its own family.
    "design",
    # THE MISSED TARGETS (RULINGS 2026-09-08t/v, sidecar ``design_target``):
    # one record per row the surface did not reach — ``family``, ``miss_m``
    # and the vertices' ``ll``.  EVIDENCE for the same reason, and the
    # population ``design_target_summary`` reports under one census heading
    # so the owner can see WHICH law the surface is buying its smoothness
    # from.  It never changes an adjudication.
    "design_target",
    # THE APRON PREFERENCE FIGURE (RULINGS 2026-09-06w (2)): the generator-
    # side reading of the built surface against the 1 % preference, per
    # face (``constraints.apron.apron_preference_report``).  EVIDENCE: the
    # oracle computes its own from ``apron_tier`` (``_APRON_PREF_STATS``).
    "apron_over_preference",
    # THE TAXI ROUTE PAIRS (RULINGS 2026-09-05ab/ac): the v2 verify's own
    # population — every taxi-family pair priced over its centreline
    # route.  EVIDENCE here: ``run_checks`` never consumes it (the oracle
    # prices the chord law the owner withdrew for the taxi family);
    # ``harness/census.py`` reads its PRESENCE to stamp the oracle's taxi
    # chord rows ``WITHDRAWN_TAXI_CHORD_OUT_OF_SCOPE``.
    "taxi_route_pairs",
    # THE LAW-BAND CONTRADICTION LEDGER (spec unified-law-band Amendment
    # 1, owner ruling "3", 2026-08-27).  EVIDENCE, deliberately: a row
    # here is a site where the narrowed band admitted NO elevation at all
    # — two laws contradicting each other — which is a defect in the DATA
    # or the LAW, not surface debt, so it is reported beside the census
    # and never adjudicated as a law family.  Pre-ship the build CONTINUES
    # at those nodes on their pre-band interval; promotion of
    # ``O4_BAND_LAW_REFUSE`` to a hard refusal is a ship-gate ruling made
    # on exactly this accumulated ledger, which is why it has to be
    # visible in every census rather than only in a build log.
    "law_band_contradictions",
    # THE PACK-GROUP SPLIT LEDGER (spec pads-as-band-variables §1.3/§1.7;
    # owner ruling RULINGS 2026-08-27 late, "GRADE LAW OUTRANKS
    # SHARED-DATUM PRESERVATION").  EVIDENCE, by the spec's own word —
    # "no new family: the existing frontage / no-step / within-shape
    # families adjudicate the result; ``pack_group_splits`` is evidence".
    # A split is not a violation and must never be counted as one; it is
    # a SHEAR of authored pack geometry that the owner reviews site by
    # site, and it doubles as a bad-pack detector.
    "pack_group_splits",
    # THE ROAD BRIDGE DECK LEDGER (RULINGS 2026-08-30c §6: "refused ...
    # with a named log line and sidecar evidence").  EVIDENCE, not a law
    # family: a refused deck is a bridge that was NOT built, so the
    # surface it left behind is judged by the ordinary families exactly
    # as it was before the law existed — there is nothing new to
    # adjudicate.  What the rows carry is WHY: the §4 deck value and the
    # highest emitted surface beneath the span, and per abutment the
    # receiving value, the run available and the run the road cap
    # requires.  That makes a refusal re-derivable from the patch alone,
    # which is what the owner rules on when a site does not get its
    # bridge.
    "road_bridge_decks",
    # PER-PAD PROVENANCE (spec pads-as-band-variables §1.6): the domain
    # each pad's flat variable lives in, the solved value, and the ring
    # vertex binding each side — published into the SAME container the
    # binding-route capture uses, because "why is this pad here" must
    # stay ONE file read (extend the near-fit, never fork: RULINGS
    # 7e90032).  Evidence, adjudicated by nothing.
    "pad_binding_routes",
    "axes",                       # legacy per-size-split axes
    "routes",                     # legacy chained routes
    "triangle_plane_unresolved",  # count of unresolved triangle vertices
    # THE PAD-SEAT FEASIBILITY GATE (owner ruling RULINGS 2026-08-24c):
    # pad seats that cannot reach their governing centerline anchor within
    # 1 % x chord.  EVIDENCE, deliberately: a seat defect is caught at
    # SEATING time and is not surface debt, so it is reported beside the
    # census and never adjudicated as a law family — which is also what
    # keeps this round's acceptance counts comparable with the last.
    # THE BAND AT PAD FRONTAGE POINTS (lead order 2026-08-24) — evidence
    # for the seat adjudication, reported and never adjudicated.
    "frontage_band",
    "pad_seat_infeasible",
    # THE ALTERNATION INSTRUMENT (owner ruling RULINGS 2026-08-25h, spec
    # ``service-road-apron-spine-spec.md`` §3.2).  EVIDENCE, deliberately
    # and by the spec's own word ("report-first"): a shared apron/road
    # edge should carry ONE solved value series, and this counts the
    # adjacent station pairs whose authorship alternates past the
    # tolerance.  It is watched, never adjudicated — making it a law
    # family would re-found the acceptance bar, which is the owner's call
    # and not this round's.
    "edge_alternation",
    # How many service sub-segments were recognised as APRON SPINES in
    # this build (§1).  Evidence for reading the line above: an
    # alternation count means something different at 0 spines than at 200.
    "apron_spine_segments",
    "apron_seniority",            # the apron staged solve's SENIOR/INTERIOR
                                  # partition per apron ring node (spec
                                  # apron-staged-solve-spec.md section 3):
                                  # evidence about the SOLVE, so the census
                                  # can say whether a senior node moved in
                                  # the interior pass without re-deriving
                                  # the partition it did not run.
    "band_clamp_nodes",           # the writeback band clamp's own sites +
                                  # deltas: evidence about the SOLVE, which
                                  # the census reports and never re-judges
    "terrace_certificates",       # the panelization evidence chain
    # FINAL BAND EXCESS (cycle-5 item 7): the build's own post-solve band
    # MEMBERSHIP report.  EVIDENCE, not law input — the census does not
    # re-judge it (route_band lives in-memory, on the solver's graph); it is
    # here so "did this patch ship with vertices outside their band?" is
    # answerable from the artifacts instead of only from a pytest run.
    "band_excess",
    # spec §55 (4) THE GAP PIECES' PARTS (owner RULINGS 2026-10-04u / 06d,
    # ``pipeline/publication.gap_pieces``): per part of a cut gap piece its
    # ref, kind, area, level groups, stations by class and the stations the
    # floors merged.  EVIDENCE: the census judges the emitted parts by the
    # ordinary families; a part-aware reader names a merged-sliver step
    # from this record instead of re-deriving the cut.
    "gap_pieces",
    # spec §63 (3) Rule T (owner RULINGS 2026-10-09j, sidecar ``pad_touch``,
    # ``pipeline/publication.pad_touch``): per pad the groundside cells
    # that TOUCH it in the source geometry and the GAPPED ones with their
    # gap.  EVIDENCE: ``tools/pad_edge_read.py --source`` classes by it;
    # the census prices nothing from it.
    "pad_touch",
    # (``basin_facilities`` was here — an EVIDENCE key nothing read —
    # until the tunnel-trench declared-step law made it LAW INPUT; it now
    # lives in ``SIDECAR_LAW_KEYS`` above.  Its own spec is
    # basin-rim-flush-seating-spec.md section 2.1e item E2.)
    # SERVICE-CORRIDOR FREE-END DEM TIES (corridor-joins round, spec
    # ``docs/specs/corridor-joins-round-spec.md`` rulings 3 + 4(b)).  One
    # record per anchored corridor terminus: its lat/lon, the AMBIENT DEM
    # the build read there, the target it was anchored at (clamped into the
    # road cap's reach where terrain is out of reach) and the terminal
    # cross-section's node count.  EVIDENCE, never law input — the census
    # judges the emitted road by the ordinary grade families; this exists so
    # "did the road reach GROUND?" is answerable from the artifacts, in the
    # BUILD's own DEM frame, which an offline DEM read cannot reproduce
    # (warm-vs-cold has moved terrain 12 m).  Read by
    # ``tools/corridor_axis_coverage.py --free-ends``.
    "svc_free_ends",
    # THE ROAD-OWNERSHIP DECLARATION (linear-transport redesign spec
    # §3.4, the census MIGRATION GUARD MIRROR).  auto_patch mints
    # CONTACT STUBS only — the general road course is the core's
    # ``include_roads`` (RULINGS 2026-08-31b) — so EVERY road-family law
    # population in this census is smaller than it was, by construction
    # and not by accident.  These are the numbers that make that
    # provable: the centerline length offered to the mint, the length
    # kept inside the 25 m contact / bridge-tunnel scope, and the length
    # RELEASED to the core.  EVIDENCE, never law input: the released
    # roads are priced by ``tools/road_terrain_conformance.py
    # --levelled-roads`` off the tile's own clamp sidecar, which is the
    # only instrument that can see them at all (census #91).
    "road_ownership",
    # THE FLAT-SITE EVIDENCE RECORD (spec docs/specs/
    # flat-site-detector-spec.md section 2).  The detector's four
    # signals + verdict, measured at the build's DEM-in-hand point:
    # CIFP threshold consensus, DEM relief vs its own SOURCE CLASS's
    # noise floor over the pavement+boundary+margin extent, the
    # DEM-vs-instrument offset, and the pack-object consensus.
    # REPORT-ONLY — nothing in the law reads it, and the census
    # re-judges none of it; it is here so "did this patch ship from a
    # site whose DEM was pure noise?" is answerable from the artifact.
    "site_class",
    # THE TUNNEL REFUSAL REGISTER (spec docs/specs/
    # tunnel-integrity-round-spec.md section T3.2).  One record per bore
    # the tunnel pass declined to model: the adjacent-road veto (the
    # blocking road, whether it CROSSED, its distance, and whether the
    # own-bore exemption applied) and R10-1's covered-at-grade
    # passthrough refusals.  EVIDENCE, never law input — the census
    # counts them and re-judges nothing.  A vetoed bore emits NO
    # geometry, so it contributes no rows to any family table below; a
    # census that does not print this number cannot distinguish "this
    # airport has no tunnels" from "this airport's tunnels were all
    # refused" (measured LEMD: 37 ways in one veto).
    "tunnel_vetoes",
    # THE DECK-CLEARANCE CORRIDOR THAT YIELDED (spec docs/specs/
    # tunnel-integrity-round-spec.md section T1.1).  One record per
    # object-bridge trench / causeway piece suppressed because a MAPPED
    # bore already owns that ground.  EVIDENCE, never law input — the
    # census counts them and re-judges nothing; a suppressed corridor
    # emits no shape, so like a refused bore it can appear in no family
    # table, and without this line its absence is unattributable.
    "object_corridor_suppressions",
    # THE NODELESS-INTERIOR INSTRUMENT (spec docs/specs/
    # heca-apron-round2-spec.md section 2).  One record per apron-role
    # polygon carrying an interior disk of radius >
    # ``config.APRON_NODELESS_RADIUS_M`` with ZERO emitted vertices.
    # EVIDENCE, and the most important kind: this is the census's own
    # BLIND SPOT reported by the build.  The census prices PAIRS OF
    # EMITTED NODES, so a region with no nodes yields no rows and reads
    # as compliant however wrong it is — HECA's 215 x 430 m void passed
    # three rounds of censuses at 1,679 while carrying a visible cliff.
    # Printed at ZERO too (zero-of-zero is not a pass).
    "nodeless_interiors",
    # THE GAP-BRIDGING SPINE's provenance (same spec, section 1.2): one
    # record per synthesized bridging centerline — the two route ends it
    # joins (apt.dat 1201 node ids where nameable), its length and its
    # inherited size letter.  EVIDENCE: the census judges the bridge's
    # emitted pavement by the ordinary grade families like any other
    # route; this exists so a reader can NAME a centerline that is in
    # the patch but in no upstream feed.
    "gap_spine_bridges",
    # THE STAND-DOWN (gap-spine-bridge-stand-down-spec Amendment 1): one
    # record when this patch is the bridge-free RETRY of a build the
    # post-solve band law refused with bridges minted.  EVIDENCE — a
    # stand-down is not a defect row; it says the surface in this patch
    # was adjudicated by an interventional re-run, and which refusal it
    # answered.  Counted, never re-judged.
    "gap_spine_stand_down",
    # THE PAD BINDING ROUTES (spec docs/specs/pad-binding-routes-spec.md
    # §1.4/§1.5).  EVIDENCE, deliberately: per pad, the recorded route
    # that bound its seat on each side — anchor, anchor value, route
    # budget, plan length, hop chain.  The census REPORTS it and
    # adjudicates nothing from it; the surface those seats produced is
    # judged by the ordinary law families, exactly as before.  It is here
    # so an emitted patch answers "which route bound this pad?" without a
    # rebuild (``tools/trace_reach_route.py --from-sidecar``).
    "pad_binding_routes",
    # THE AIRSIDE-SCOPED CERTIFICATE (air7; RULINGS 2026-09-01l/r): the
    # build's OWN law-graph verdict on the owner's zero-airside beta bar
    # — CERTIFIED-AIRSIDE iff every airside-scoped law edge (row-side
    # partition; mixed counts against airside) was within cap plus the
    # ratified quantization allowance at the run's last exit reading.
    # EVIDENCE, deliberately: the census's own families adjudicate the
    # EMITTED surface; this is the solve's constraint-graph reading,
    # taken in a different population (law edges, not emitted pairs), so
    # counting it as a family would be two instruments over one claim.
    # The census prints it beside its counts so the beta claim can cite
    # both numbers from one artifact.
    "airside_certificate",
)


#: The label a user-edited patch's census carries (spec
#: patch-editor-20261015 §1.3, owner A5: "violations are reported, never
#: fail the build, result labelled 'user-edited'").
USER_EDITED_LABEL = "user-edited"


class UserEditedPatchUnjudged(FileNotFoundError):
    """A user-edited patch (``o4_user_edited="1"``) with no law frame of its
    own: the patch editor writes no sidecar, and grade checking of edits is
    ruled out (owner A3) — the census REPORTS it under
    :data:`USER_EDITED_LABEL` instead of refusing.  A subclass of
    ``FileNotFoundError`` so every other caller still refuses a
    context-free run exactly as before."""


def user_edited_label(osm_path) -> Optional[str]:
    """:data:`USER_EDITED_LABEL` when the patch's root carries
    ``o4_user_edited="1"`` (the patch editor's mark), else ``None`` — the
    ONE predicate the census and the build log read
    (``auto_patch.build_support.is_user_edited_patch``)."""
    from auto_patch.build_support import is_user_edited_patch
    return USER_EDITED_LABEL if is_user_edited_patch(str(osm_path)) else None


def law_context_from_sidecar(osm_path, *, announce: bool = False) -> dict:
    """Read the patch's ``.axes.json`` sidecar and return the ``run_checks``
    law keywords it declares — THE single sidecar reader.

    The sidecar is the CONTRACT: it carries the axes/routes the solver
    graded to, the projection anchor, the seam pins, the solver's junction
    mesh, the crown field, the baked pair caps, the declared apron-terrace
    joints and the REGION RULESET the build actually ran under.  A reader
    that drops any one of them silently judges a different law than the
    build ran (both known frame errors in this repo were exactly that).

    Raises ``FileNotFoundError`` when there is no sidecar: a context-free
    check overcounts by construction and must never be mistaken for a
    census (memory ``check-grade-needs-law-true-frame``).  Callers that
    genuinely want the bare frame call ``run_checks`` with no law kwargs.
    """
    import json as _json
    side = Path(str(osm_path) + ".axes.json")
    if not side.exists() and user_edited_label(osm_path):
        raise UserEditedPatchUnjudged(
            f"{osm_path} is a user-edited patch (o4_user_edited=1) with no "
            f"law frame — its grade law is not judged (owner A3); it is "
            f"reported, never failed (A5).")
    if not side.exists():
        raise FileNotFoundError(
            f"no axes sidecar for {osm_path} — refusing a context-free run. "
            f"Every emit writes one (the config.LOG_VERBOSITY gate was "
            f"removed 2026-08-05), so a missing sidecar means the patch was "
            f"not emitted by this tree — rebuild through "
            f"tools/harness/build_airport.py.")
    data = _json.loads(side.read_text())
    ctx: dict = {}
    exact = data.get("axes_exact") or None
    if exact:
        # exact build_context mirror: (pts, seg_caps, route_ordinal,
        # is_service).  The 5th slot of the reader's tuple carries the
        # SERVICE flag through to the centerline rebuild — a truck route is
        # not an aircraft spine (grade_graph._reads_service_spines), and the
        # solver and this reader must agree on that or they judge two
        # different laws.  Sidecars written before the flag existed carry
        # 3-element entries and read as all-taxi, which is how they were
        # graded.
        ctx["taxi_axes_ll"] = [
            (e[0], e[1], None, e[2], bool(e[3]) if len(e) > 3 else False)
            for e in exact]
        ctx["routes_ll"] = data.get("routes_exact") or None
    else:
        ctx["taxi_axes_ll"] = data.get("axes") or None
        ctx["routes_ll"] = data.get("routes") or None
    ctx["anchor"] = sidecar_anchor(data)
    ctx["seam_pins_ll"] = data.get("seam_pins")
    # §16g (10) (12) (2): the re-node witness list (absent on any patch
    # written before 2026-09-16, which then reports nothing)
    ctx["pad_airside_renode_ll"] = data.get("pad_airside_renode")
    # jetway-strip spec §2 (6) (absent before the strip law: nothing)
    ctx["jetway_strips_ll"] = data.get("jetway_strips") or None
    # unit-platform spec §4 (5) (absent before the platform: nothing)
    ctx["platforms_ll"] = data.get("platforms") or None
    # flat-pad spec v2 §5a (absent before the feasibility check: nothing)
    ctx["hard_conflict_ll"] = data.get("hard_conflict") or None
    ctx["seam_half_width_m"] = data.get("seam_half_width_m")
    # §39 (1)/(2): the emitter's own foreign-water population
    ctx["shore_edges_ll"] = data.get("shore_edges") or None
    ctx["natural_shore_ll"] = data.get("natural_shore") or None
    ctx["road_cap_governs_ll"] = data.get("road_cap_governs") or None
    ctx["end_profile_yields_ll"] = data.get("end_profile_yields") or None
    # §33 (6) (owner RULINGS 2026-09-15e/15g): the object cuts
    ctx["object_cuts_ll"] = data.get("object_cuts") or None
    ctx["mesh_edges_ll"] = data.get("mesh_edges") or None
    ctx["face_holes_ll"] = data.get("face_holes") or None
    ctx["crown_drops_ll"] = data.get("crown_drops") or None
    # §40 (2) as amended (owner RULINGS 2026-09-13dd)
    ctx["runway_axes_ll"] = data.get("runway_axes") or None
    ctx["shoulder_transverse_max"] = data.get("shoulder_transverse_max")
    ctx["shoulder_taxi_crossings_ll"] = data.get("shoulder_taxi_crossings") or None
    # §50.1 (4) (owner RULINGS 2026-09-18d (3) / 18f)
    ctx["runway_caps"] = data.get("runway_caps") or None
    # THE PAD'S RELIEF TARGET (11l (2)): absent on any patch built before
    # 11j, which reads exactly as it did then.
    ctx["pad_relief_ll"] = data.get("pad_relief") or None
    # §37 (7): absent on any patch built before it (the chord law)
    ctx["road_route_frame_ll"] = data.get("road_route_frame") or None
    ctx["road_coverage_join_ll"] = data.get("road_coverage_join") or None
    ctx["ground_envelope"] = data.get("ground_envelope") or None
    ctx["crown_centerline_ll"] = data.get("crown_centerline") or None
    ctx["pair_caps_ll"] = data.get("pair_caps") or None
    ctx["stretches_ll"] = data.get("stretches") or None
    # THE PER-STATION CAP VECTOR (Amendment 9) — the census's own read of
    # the one derivation.  ``None`` when the patch predates the key, which
    # ``_check_lateral_contiguity`` announces before falling back.
    ctx["station_caps_ll"] = data.get("station_caps") or None
    ctx["xsection_spans"] = data.get("xsection_spans") or None
    ctx["terrace_joints_ll"] = data.get("terrace_joints") or None
    ctx["fan_ramp_zones_ll"] = data.get("fan_ramp_zones") or None
    ctx["apron_lattice_edges_ll"] = data.get("apron_lattice_edges") or None
    ctx["airside_no_step_edges_ll"] = (
        data.get("airside_no_step_edges") or None)
    ctx["interior_zones_ll"] = data.get("interior_zones") or None
    ctx["disconnected_rings_ll"] = data.get("disconnected_rings") or None
    ctx["basin_facilities"] = data.get("basin_facilities") or None
    ctx["channel_facilities"] = data.get("channel_facilities") or None
    ctx["eat_rects"] = data.get("eat_rects") or None
    ctx["pad_cluster_mismatch"] = data.get("pad_cluster_mismatch") or None
    ctx["ruleset"] = data.get("ruleset") or None
    ctx["relaxed_rows"] = data.get("relaxed_rows") or None
    ctx["late_stage"] = data.get("late_stage") or None
    ctx["yielded_rows"] = data.get("yielded_rows") or None
    ctx["apron_tier"] = data.get("apron_tier") or None
    if announce:
        print(f"  (axes sidecar loaded: {len(ctx['taxi_axes_ll'] or [])} axes"
              + (" [exact]" if exact else "")
              + f", {len(ctx['routes_ll'] or [])} routes"
              + (f", {sidecar_frame_name(data)} frame"
                 if ctx["anchor"] else ", NO declared frame (mean of "
                 "nodes — population-dependent, issue #215)")
              + (f", {len(ctx['seam_pins_ll'])} seam pins"
                 if ctx["seam_pins_ll"] is not None else "")
              + (f", {len(ctx['mesh_edges_ll'])} solver mesh edges"
                 if ctx["mesh_edges_ll"] else "")
              + (f", {len(ctx['crown_drops_ll'])} crown drops"
                 if ctx["crown_drops_ll"] else "")
              + (f", {len(ctx['pad_relief_ll'])} pad relief vertices"
                 if ctx["pad_relief_ll"] else "")
              + (f", {len(ctx['terrace_joints_ll'])} terrace joints"
                 if ctx["terrace_joints_ll"] else "")
              + (f", {len(ctx['fan_ramp_zones_ll'])} fan-ramp zones"
                 if ctx["fan_ramp_zones_ll"] else "")
              + (f", {len(ctx['interior_zones_ll'])} back-edge zones"
                 if ctx["interior_zones_ll"] else "")
              + (f", {len(ctx['disconnected_rings_ll'])} disconnected "
                 f"groundside ring(s)"
                 if ctx["disconnected_rings_ll"] else "")
              + (f", {len(ctx['basin_facilities'])} declared basin "
                 f"facility(ies)" if ctx["basin_facilities"] else "")
              + (f", {len(ctx['eat_rects'])} end-around-taxiway rect(s)"
                 if ctx["eat_rects"] else "")
              + f", ruleset={ctx['ruleset']!r}"
              + (f", {len(ctx['relaxed_rows'])} relaxed row(s) [04t(1)]"
                 if ctx["relaxed_rows"] else "")
              + (f", {len(ctx['yielded_rows'])} yielded row(s) [08d]"
                 if ctx["yielded_rows"] else "")
              + " — law-true check)")
    return ctx


#: The heading the census reports the missed design targets under
#: (RULINGS 2026-09-08t: the census reports, never blocks).
DESIGN_TARGET_HEADING = "design_target"
DESIGN_TARGET_RULING = "08t"


def design_target_summary(osm_path) -> dict:
    """THE DESIGN-TARGET READING (sidecar ``design_target``, RULINGS
    2026-09-08t/v): per family the number of law rows the design surface
    missed and the worst miss in metres.  The rows themselves are counted
    law-true in their families by ``run_checks`` — this is the heading that
    names them, not a re-pricing."""
    import json as _json
    side = Path(str(osm_path) + ".axes.json")
    if not side.exists():
        return {}
    try:
        data = _json.loads(side.read_text())
    except (ValueError, OSError):
        return {}
    out: Dict[str, dict] = {}
    for rec in (data.get("design_target") or []):
        fam = str(rec.get("family", "?"))
        f = out.setdefault(fam, {"rows": 0, "max_miss_m": 0.0})
        f["rows"] += 1
        try:
            f["max_miss_m"] = max(f["max_miss_m"], float(rec.get("miss_m") or 0.0))
        except (TypeError, ValueError):
            pass
    return out


def sidecar_evidence(osm_path) -> dict:
    """The sidecar's non-law EVIDENCE fields (see ``SIDECAR_EVIDENCE_KEYS``)
    plus ``unknown_keys`` — any key this build of the reader does not know.
    A non-empty ``unknown_keys`` means the emitter grew a field no reader
    consumes: report it, never ignore it."""
    import json as _json
    side = Path(str(osm_path) + ".axes.json")
    if not side.exists():
        return {}
    data = _json.loads(side.read_text())
    known = set(SIDECAR_LAW_KEYS) | set(SIDECAR_EVIDENCE_KEYS)
    out = {}
    for k in SIDECAR_EVIDENCE_KEYS:
        if k not in data:
            continue
        v = data[k]
        if k == "band_excess":
            # ALREADY a summary (counts + the worst ten), and its whole point
            # is to be readable from the artifact — collapsing it to
            # "<N entries>" would re-hide exactly what item 7 surfaced.  The
            # worst-row list is dropped; the numbers are kept.
            out[k] = (None if not isinstance(v, dict) else
                      {kk: vv for kk, vv in v.items() if kk != "worst"})
            continue
        if k == "law_band_contradictions":
            # SUMMARISED HERE, printed in full by the census: the count
            # plus the worst site's arithmetic, which is what a reader
            # needs to know whether to open the sidecar.  Never collapsed
            # to "<N entries>" — a ledger the ship gate is adjudicated on
            # must carry a number in every report that mentions it.
            rows = v if isinstance(v, list) else []
            out[k] = {"sites": len(rows)}
            # THE LEDGER HAS TWO PRODUCERS since the pads-as-band-variables
            # round (spec §1.4): a NODE whose two band directions crossed,
            # and a PAD whose flatness admits no level at every ring vertex
            # (``source: "pad_domain"``).  Counted apart so a reader is
            # never told a pad row's absent anchor arithmetic is a missing
            # measurement — the pad rows have no anchors by construction.
            out[k]["pad_domain_sites"] = sum(
                1 for r in rows
                if isinstance(r, dict) and r.get("source") == "pad_domain")
            if rows:
                w = rows[0]
                out[k].update({
                    "worst_source": w.get("source") or "band_node",
                    "worst_pad": w.get("pad"),
                    "worst_deficit_m": w.get("deficit_m"),
                    "worst_ll": w.get("ll"),
                    "worst_ceil_anchor_value": w.get("ceil_anchor_value"),
                    "worst_floor_anchor_value": w.get("floor_anchor_value"),
                    "worst_ceil_budget_m": w.get("ceil_budget_m"),
                    "worst_floor_budget_m": w.get("floor_budget_m"),
                })
            continue
        if k == "pack_group_splits":
            # SUMMARISED HERE, printed by the census (spec
            # pads-as-band-variables §1.3/§1.7).  Never collapsed to
            # "<N entries>": a split SHEARS authored pack geometry and the
            # owner reviews each one, so the count and the worst site have
            # to survive into every report that mentions the ledger.
            rows = v if isinstance(v, list) else []
            rows = sorted(rows, key=lambda r: -float(r.get("worst_m") or 0.0))
            # THE DENOMINATOR travels in the pad_binding_routes container
            # (one evidence container for the pads, never a second key);
            # resolved into this summary below, after both are read.
            out[k] = {"groups_split": len(rows)}
            if rows:
                w = rows[0]
                out[k].update({
                    "worst_group": w.get("group"),
                    "worst_m": w.get("worst_m"),
                    "worst_stage": w.get("stage"),
                    "worst_members": len(w.get("members") or []),
                    "worst_pieces": len(w.get("pieces") or []),
                })
            continue
        if k == "pad_binding_routes":
            # SUMMARISED: the container is per-pad provenance (domains,
            # solved values, binding vertices, and — where the route
            # capture is present — the recorded routes).  The census needs
            # to know it RAN and over how many pads; the detail is a file
            # read away, which is the whole point of the key.
            rec = v if isinstance(v, dict) else {}
            rows = rec.get("records") or []
            out[k] = {
                "nodespace": rec.get("nodespace"),
                "pads": len(rows),
                "pad_variables": sum(
                    1 for r in rows
                    if isinstance(r, dict) and r.get("pad_variable")),
                "on_domain_bound": sum(
                    1 for r in rows
                    if isinstance(r, dict)
                    and ((r.get("binding") or {}).get("at_ceiling")
                         or (r.get("binding") or {}).get("at_floor"))),
                "pack_groups_declared": rec.get("pack_groups_declared"),
            }
            continue
        if k == "airside_certificate":
            # SUMMARISED HERE, printed by the census: the decision-grade
            # verdict plus each reading's headline numbers.  Never
            # collapsed to "<N entries>" — the beta bar is adjudicated on
            # exactly this record, so the verdict has to survive into
            # every report that mentions the key.  ``{}`` (the solve
            # never took a reading) passes through as ``{}`` so a
            # geometry-only patch is distinguishable from a pre-law one.
            rec = v if isinstance(v, dict) else {}
            out[k] = {"verdict": rec.get("verdict"),
                      "readings": {
                          t: {kk: r.get(kk) for kk in
                              ("certified", "n_edges_scoped", "n_over",
                               "n_over_mixed", "n_both_hard_over",
                               "worst_excess_m", "partition")}
                          for t, r in (rec.get("readings") or {}).items()
                          if isinstance(r, dict)}}
            continue
        if k == "site_class":
            # ALREADY a flat record of scalars (four signals + verdict),
            # and its whole point is to be readable from the artifact —
            # collapsing it to "<N entries>" would hide exactly the
            # numbers it exists to carry.  Passed through verbatim.
            out[k] = v
            continue
        # SUMMARISE, never embed: the legacy ``axes``/``routes`` arrays are
        # megabytes of geometry, and a report that inlines them is a report
        # nobody reads.  Scalars pass through.
        out[k] = f"<{len(v)} entries>" if isinstance(v, (list, dict)) else v
    # ZERO OF ZERO IS NOT A PASS (RULINGS 2026-08-06): join the pack-group
    # DENOMINATOR onto the split summary so "0 split" can never be read as
    # "every declared group accommodated" when none was declared.
    if isinstance(out.get("pack_group_splits"), dict):
        out["pack_group_splits"]["groups_declared"] = (
            (out.get("pad_binding_routes") or {}).get("pack_groups_declared")
            if isinstance(out.get("pad_binding_routes"), dict) else None)
    out["unknown_keys"] = sorted(set(data) - known)
    out["seam_pin_count"] = len(data.get("seam_pins") or [])
    out["terrace_joint_count"] = len(data.get("terrace_joints") or [])
    out["terrace_certificate_count"] = len(data.get("terrace_certificates")
                                           or [])
    # LAW-KEY COUNTS beside the evidence (the ``seam_pin_count`` /
    # ``terrace_joint_count`` idiom): the KEY is law input, but how big its
    # declared population was is what a reader needs to judge the counts
    # above — ZERO OF ZERO IS NOT A PASS (RULINGS 2026-08-06, binding
    # point 2).  A patch with no basin declares nothing and exempts
    # nothing, and this is where that is visible.
    out["basin_facility_count"] = len(data.get("basin_facilities") or [])
    # THE CENSUS'S OWN BLIND SPOT, counted (spec heca-apron-round2 §2).
    # A nodeless apron interior contributes ZERO census rows however
    # wrong its surface is, so this count is the only thing standing
    # between "no violations" and "no evidence".  Reported at zero.
    out["nodeless_interior_count"] = len(
        data.get("nodeless_interiors") or [])
    out["gap_spine_bridge_count"] = len(data.get("gap_spine_bridges")
                                        or [])
    # A STAND-DOWN IS NOT A DEFECT ROW (spec Amendment 1 §2 register):
    # the census reports the COUNT so a reader can tell a surface that
    # was adjudicated by the bridge-free re-run from one that never had
    # bridges at all.  Reported at zero — zero-of-zero is not a pass.
    out["gap_spine_stand_down_count"] = len(
        data.get("gap_spine_stand_down") or [])
    # THE TUNNEL REFUSAL REGISTER, counted and split by reason (spec
    # tunnel-integrity-round §T3.2).  A refused bore emits nothing, so
    # it is invisible to every family table; without this line "0 tunnel
    # rows" reads the same on an airport with no tunnels and on one
    # whose 37 tunnel ways were vetoed in a single pass.  Reported at
    # zero — zero-of-zero is not a pass.
    from collections import Counter as _CounterTV
    _tv = data.get("tunnel_vetoes")
    out["tunnel_veto_count"] = (None if _tv is None else len(_tv or []))
    out["tunnel_veto_reasons"] = (
        None if _tv is None else dict(sorted(_CounterTV(
            str((r or {}).get("refused_because") or "unknown")
            for r in (_tv or []) if isinstance(r, dict)).items())))
    # THE YIELDED DECK-CLEARANCE CORRIDORS, counted (section T1.1).
    _cs = data.get("object_corridor_suppressions")
    out["object_corridor_suppression_count"] = (
        None if _cs is None else len(_cs or []))
    return out
