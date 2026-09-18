"""THE CENSUS'S OWN LAW MACHINERY — engine-neutral BY IMPLEMENTATION.

`tools/check_grade.py` is the harness library every defect count comes from.
It prices v2 patches, but until 2026-09-17 it read its pair law, its constraint
generator, its seam law, its role vocabulary and its lateral machinery out of
ELEVEN modules of the retired v1 engine (`layout`, `grade_law`, `grade_graph`,
`strip_seam_law`, `lateral_contiguity`, `lateral_spine_nodes`, `enclaves`,
`gap_fill`, `adjacent_ground`, `transect_walk`, and `route_profile.apron_terrace`
through the constraint generator) — seam S4 of the stage-B inventory
(RULINGS 2026-09-13aw), and the reason the census could not survive the
deletion.

Session ruling (d) of the lane brief: *what it actually USES moves into a small
keep module owned by the harness, copied ONCE with its tests — never a second
spelling of a v2 law value (where a value exists in `law/*.toml`, read it from
there)*.  That is exactly what this package is:

    roles.py        the role vocabulary + the authority order  (layout, strips)
    strip_seam.py   the strip-seam / tear law                  (strip_seam_law)
    grade_law.py    the pair law, the envelopes, the budgets    (grade_law)
    grade_graph.py  the constraint generator                   (grade_graph)
    contiguity.py   lateral contiguity, priced axes, enclaves  (lateral_*,
                                                                enclaves,
                                                                gap_fill,
                                                                adjacent_ground)
    corridor.py     the apron spine corridor cover             (apron_terrace)
    transect.py     the transect walk                          (transect_walk)

WHAT IS *NOT* COPIED
    Every law VALUE.  `auto_patch/config.py` is a KEEP module and the numbers
    are imported from it exactly as before; the v2 tables in
    `auto_patch_v2/law/*.toml` are read where check_grade already read them.
    Nothing here re-spells a threshold.

THE ONE DELIBERATE CHANGE, and it is not a behaviour change at default
environment: the four `fabric_flags.on(...)` reads inside the adjacent-ground
envelope are collapsed to their arm.  Every flag in that registry is
DEFAULT-ON and its OFF arm is the pre-W2 v1 behaviour, which dies with v1;
v2's engine reads none of them.  A lane that had set `O4_FABRIC_W2_*=0` would
have seen the harness follow it before and will not now — that is the retirement,
recorded here rather than left as a silent divergence.

ACCEPTANCE: a census A/B over the SAME patch bytes (the registered HECA frame
`/tmp/harness/xq_base_heca.osm`) before and after the re-point, every family,
every side and the cockpit block IDENTICAL.  Twin: `tests/test_law_support.py`
(each copied symbol IS the v1 symbol while v1 is still on disk; the role tags
are v2's `precedence.toml` names).
"""
