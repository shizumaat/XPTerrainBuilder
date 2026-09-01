# Road band-seal scope + road↔apron edge conformance

> **RECONSTRUCTED 2026-09-01 (beta hardening, H2).** This document was
> cited by five files across `src/`, `tools/` and `tests/` but was **never
> committed** — `git log -- docs/specs/road-band-seal-scope-spec.md` is
> empty and there is no archived copy. The law itself is live and has
> been shipping since 2026-08-25; only the spec was missing.
>
> It is reconstructed **from the implementation and its twins**, not from
> memory, and every clause below names the code or test that carries it.
> Treat those as authoritative where this text and the code disagree, and
> correct this file rather than the code. The section numbers are the ones
> the citing files already use (§1, §1.2, §1.3, Amendment 1), so existing
> references resolve.
>
> Per `docs/specs/README.md`, this directory is **historical record, not
> guidance**: the living law is `docs/RULINGS.md` (see the 2026-08-25b
> entry) and the living behaviour is the code and its twins. This file
> exists so the five citations resolve to the evidence and the measured
> numbers behind them — cite it as history, with its date.
>
> Sources used, all of which cite this spec:
> * `src/auto_patch/elevation_per_surface/solver_primitives.py`
>   (`seal_role_scope`, `seal_pavement_to_band`)
> * `src/auto_patch/elevation_per_surface/raster_reach_band.py`
>   (`band_domain_roles`)
> * `src/auto_patch/mutation_seam_audit.py` (the §1.3 ordering audit)
> * `src/auto_patch/groundside.py` (`apply_lateral_contiguity_law`) and
>   `src/auto_patch/lateral_contiguity.py` (`_edge_conformance_on`)
> * `tools/band_clamp_attrib.py` (the attribution instrument)
> * `tests/test_road_band_seal_scope.py` (the twins), plus
>   `tests/test_kill_prep_round.py`, `tests/test_membership_round.py`,
>   `tests/test_classification_round.py`

**Owner rulings.** The seal-scope half is owner-approved **option (a)**
(2026-08-25). The contact half is **RULINGS 2026-08-25b**: *a road sharing
an edge with an apron conforms to the strictest grade — it becomes part of
the apron.* Amendment 1 (below) settles what "becomes part of" means in
the layout, against measurement.

---

## §1 — The seal seals only what the band legislates

### §1.1 The defect

`solver_primitives.seal_pavement_to_band` is the pipeline's **last
elevation author** (round 17, §R17-1(b)): it runs after every emitter and
both final projections and confines the *emitted* altitudes to the **band
of record**.

The band of record is the **aircraft-reachability** band. The road family
is absent from it three times over:

* its propagation domain (`raster_reach_band._domain_geom`) is built from
  `band_domain_roles()`, which contains no road role;
* the leg-cost grid (`_local_cap_grids`) never paints the road cap — it
  skips `is_service`;
* an off-mask road point is priced at `APRON_MAX_GRADE` × straight-line
  offset with a hard **30 m** horizon.

So clamping a road to that interval applied an interval **computed under a
law the road is not under** — and, because the seal runs after
`pipeline._grade_limit_groundside_chords`, it did so as the *last* author,
overwriting the road's own lawful result.

**Measured (2026-08-25 HECA roads round, `tools/band_clamp_attrib.py
--clamps`):** 110 band-clamp records, of which **92 were road-family**.
Every floor-side road clamp lay inside the raster band's 30 m off-net
radius and none outside it. The owner's site at
`30.102344, 31.3951157` shipped as a **+5.05 m step**.

### §1.2 The law

The seal clamps **exactly the roles the band states a law for**.

* The scope is `solver_primitives.seal_role_scope()`, derived from
  `raster_reach_band.band_domain_roles()` — **one source**. A second
  hand-written role list is the census-wrapper defect the root
  `CLAUDE.md` names; the twin in §3(d) forbids it.
* `ROLE_RUNWAY` is additionally never clamped (CIFP-hard; "airside is
  king").
* The write-back form is preserved per shape, and every material clamp
  stays a counted, logged finding on `layout.band_clamp_findings` — a
  clamp is evidence, never silence.

The road family keeps **its own** authorities, which are the ones that
actually legislate it: the mouth-fed `groundside_reach_band` seating, and
the road chord limiter at the road cap.

Gate `O4_SEAL_AIRSIDE_ONLY`, **default ON**;
`O4_SEAL_AIRSIDE_ONLY=0` restores the pre-ruling behaviour exactly.

### §1.3 The ordering obligation

Removing the road roles from the seal raises a second question the seal
used to mask: *what else can move a road node after
`_grade_limit_groundside_chords`?* A post-limiter road author would be
the same defect shape the seal was.

That question is answered **by measurement, never by reading the
source**: `src/auto_patch/mutation_seam_audit.py`, armed with
`O4_MUTATION_SEAM_AUDIT=1`, records road-ring altitudes at the seams the
pipeline already marks. Its `ROAD_FAMILY_ROLES` is spelled as literals
(the module deliberately imports nothing from `auto_patch.layout`); the
two spellings are twinned so they cannot drift. `|dz|` below
`SEAM_MOVE_MATERIALITY_M` (0.01 m, the convergence guards' elevation
floor) is not a move.

---

## §2 — Road↔apron edge conformance (RULINGS 2026-08-25b)

### §2.1 Contact is canonical identity, never proximity

Two rings **share an edge** exactly when they share an ordered pair of
consecutive node IDs, in either orientation. `layout.to_osm` deduplicates
emitted nodes by their 11-decimal lat/lon spelling, so edge-sharing is an
identity fact about the emitted graph — not a distance test. This is the
project's standing canonical-identity rule, and it is the ruling's own
boundary.

Rings that come *close* to airside pavement without sharing an edge are
the **near-miss class**. They are reported separately by
`band_clamp_attrib.py --contact-rings` (`--near-miss-m`) and are
**never folded in**: the owner rules on that class separately.

### §2.2 Amendment 1 — conformance is PRICING, never POPULATION

**Attempt 1 routed edge-sharing rings into clause (4) of the lateral-
contiguity law — absorption — and it was measured wrong:**

| arm | HECA airside | SPJC |
|---|---|---|
| control | 1,735 | 175 |
| absorbing contact rings | **1,948** | **178** |

Absorption added **+53,530 m² of new apron** and minted new 6 m
apron|junction steps at ways `-12160` / `-12167`. That is the
airside-contamination direction **"airside is king" forbids**.

**The amended law:** a ring sharing an edge with an apron **CONFORMS to
the apron's law — it does not become the apron.**

Concretely, in `groundside.apply_lateral_contiguity_law`:

* the ring is stamped `apron_contact` and held to the **cap path**;
* it carries the apron's cap **end to end** (`station_caps` folds the
  apron into every station's class set) and seeds from the apron datum;
* **no absorption, no mouth cut, no role change** — its rows stay in the
  groundside families, and the conformance shows up as a tighter cap;
* the `apron_contact` and `absorbed` counters can therefore never count
  the same ring.

Gate `O4_ROAD_APRON_EDGE_CONFORM`, **default ON** (read at *call* time by
`lateral_contiguity._edge_conformance_on`, so a twin can flip it without
a module reload); `=0` restores the pre-ruling absorption exactly.

The owner's sentence — *"five ring roads touching one apron are one
apron-grade surface"* — is delivered as **grade**, which is what it says.
Pinned by
`tests/test_classification_round.py::TestLateralContiguityEmitter::
test_ring_roads_touching_one_apron_are_one_apron_GRADE_surface`.

### §2.3 Scope note — later widening

**RULINGS 2026-08-26b item 2** (spec
`road-airside-crossing-conformance-spec.md` §1.1) widened the contact
term from the apron to **every airside neighbour**, which removed the
last airside-hosted merge from the absorption path altogether. Read that
spec alongside this one; the mechanism here is unchanged, its neighbour
set is larger.

**RULINGS 2026-08-28e** further scoped the contact term: contact is a
**value** law, so it no longer folds into the cap for a road that meets
airside only at a **face** — such a road keeps its free-road class beyond
the contact. The lateral walk still reads an apron a road stands *inside
or alongside*, which is 25b's substance.

---

## §3 — Acceptance (the twins)

`tests/test_road_band_seal_scope.py`, headless — hand-built layouts and
polygons, an explicit band closure, no DEM and no build:

* **(a)** A road ring beyond the band's off-net radius with a lawful
  descent: flag ON, it is not sealed and the descent survives; flag OFF,
  the historic clamp reproduces.
* **(b)** **AIRSIDE sealing is byte-identical** between the two flag
  states — the change removes roles from the scope and touches nothing
  else.
* **(c)** An edge-sharing road ring **conforms without reclassification**:
  apron cap end to end, apron-datum seeding, still road-family
  population. A free road 2 m away takes neither (canonical identity,
  never proximity).
* **(d)** The two spellings each half needs — the seal's scope against
  the band engine's own domain, and the seam audit's road-family literals
  against `auto_patch.layout` — **cannot drift**.

Related twins that turn on this law:
`tests/test_kill_prep_round.py` (the strictest cap still decides the
host, now by conformance), `tests/test_membership_round.py` (the apron
left the absorption path), `tests/test_classification_round.py` (§2.2's
headline).
