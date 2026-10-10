# kclt546 — lane notes (KCLT owner sim read of 1.0.387: #546, #547, #548)

Branch `claude/kclt546` off main 66bc72f92. Read build: `tunnel522_KCLT` (body f1b26887fcc3).
Replays: capture `frames/pads67/KCLT.pkl`.

## Finding 1 (#546) — tiny apron shapes nested in apron shapes: ATTRIBUTED

Site 35.2202043, -80.946664 (`osm_site --at … --relate` on `tunnel522_KCLT.osm`): three ways
`-10231` (1.50 m2, 5 nodes), `-10232` (3.01 m2), `-10233` (0.38 m2), role `apron`, ref
`pav14#plateau:building81` (shapeID 223/224/225), every one wholly inside way `-10201`
(same role, SAME ref, 42,419 m2). Levels 221.51–221.62 m against the host's 220.86–221.75:
the apron's own surface, no level of its own.

- What they are: SURPLUS PAD SCRAPS. The stand-zone plateau cut leaves thin pieces of the
  building pad standing in holes of the plateau apron face; `planar/pad_sliver.
  rerole_plateau_scraps` (spec §56 (10) R-F) re-roles each as the plateau it borders but
  keeps it a FACE OF ITS OWN ("LAST, so no merge above reads the new region and no vertex
  leaves the arrangement", `planar/ribbons.py:200`). Emitted, each is a ring inside its host.
- Measured on a planar re-run of the capture (scratch `planar_dump.py` / `pl3.py`):
  `plateau_cut` returns 56 plateau pieces, 1 nested; the finished arrangement has 93
  plateau faces, 35 nested, every one with 0 % of its area inside a cut plateau piece and
  100 % of its perimeter along ONE face of its own ref. `pad_scraps_reroled` = 36 / 203.4 m2.
- Census (apron ways <= 60 m2 wholly inside a larger way; scratch `nested.py`):
  KCLT sw10 14 (1 same-ref) -> sw11 49 (34 same-ref + 1 same-base) = tunnel522 49;
  HECA sw12 6 (3 same-ref plateau); OTHH basins526 8 (2 same-ref plateau);
  KASE 1 (a gap ring, other class); CYXY / NLWF / SPJC 0.
- Purpose: none as faces of their own. They add ring vertices inside the plateau (levels
  the plateau's own), nothing else.
