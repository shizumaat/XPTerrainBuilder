# Pad-inside-basin floor seating (Fable spec, 2026-08-25; RULINGS
# 2026-08-25f — the building8 disposition: the LEMD cut emits)

Evidence: the basinpool round's finding 1. LEMD's basin is confined to
the owner bbox (12,251 m², floor 584.5, 8.53 m drop) but NO terrain cut
emits: pack shape `building8` (way -10008, 33,447 m², flat pad at
600.28 m) covers 100% of the facility footprint; the facility floor is
differenced against every earlier-born shape (`_owned_near` /
`_TUNNEL_FLOOR_OWNED_CLEARANCE_M`) and erased, and R13's pit cut only
cuts pavement, never a building pad. Owner: "building8 should be below
apron grade." Second finding: the emitter is SILENT when
`body_floor_born == 0`.

## §1 The seating rule (RULINGS 2026-08-25f)

1. A building pad whose footprint lies within a basin facility's
   footprint (coverage ≥ `BASIN_PAD_COVERAGE_MIN = 0.8` of the PAD's
   area) SEATS AT THE FACILITY FLOOR: its flat level is the facility's
   floor elevation, not the surrounding grade; downstream consumers
   (seats, chords, strip adoption) see the floor value.
2. The facility floor is NOT differenced against such a pad — the cut
   emits through it (extend the `_owned_near` exclusion test; R13's
   cut applies within the facility footprint regardless of the pad).
   Partial-coverage pads (< 0.8) keep today's behaviour and are
   REPORTED (named line) — a pad straddling a basin rim is a real
   design case, not this rule's.
3. Flag `O4_BASIN_PAD_FLOOR_SEAT`, default ON; OFF byte-identical.

## §2 The silence dies (the 25e named-line class)

1. When a facility's `body_floor_born == 0`, the emitter logs a LOUD
   line naming the facility, its floor elevation, and each shape the
   floor was differenced against (with area and role). Ungated —
   instrument is law.
2. Twin: synthetic facility fully covered by a pad → §1 ON: floor
   emits + pad seats at floor; §1 OFF: zero plates + the named line.

## Twins

(a) Pad 100% inside facility → seated at floor; cut emits; walls at
    the facility rim.
(b) Pad outside → untouched. Pad at 50% coverage → untouched +
    reported.
(c) OTHH: byte-identical unless a pad genuinely sits inside a
    facility there — any newly-seated OTHH pad is reported with
    location BEFORE acceptance is claimed (expected: none; its pool
    members are structures, not covering pads).
(d) Flag OFF byte-identical.

## Acceptance (ONE LEMD build + ONE OTHH control)

- LEMD: floor plates > 0 at the owner bbox; emitted cut ≈ the bbox at
  ~7-8.5 m below surrounding grade; building8's pad level ≈ the floor
  (report both numbers); census delta reported vs 894 (the cut's new
  walls/steps are declared geometry under the trench law — expect the
  declared-step exemption to absorb them; report the class table).
- OTHH: byte-identical body sha, or every delta named per twin (c).
- HECA/SPJC/CYXY: artifact re-census unchanged (no basins).
- Attempt cap 2, materiality 0.01 m, STOP on second miss. No
  shared-repo writes, no timing claims.
