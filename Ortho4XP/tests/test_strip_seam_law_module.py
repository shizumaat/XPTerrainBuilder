"""Unit twins for the ONE strip-seam law home (spec seam-continuity-v2 §1).

The v1 seam-continuity round died because two unrelated notions of "seam"
lived under one word: the STRIP seam (tears between two ``graded_strip``
shapes) and the TILE seam (the graticule tile-cut corridor).  §1 gives the
strip seam a single home in ``src`` so a generation-binding law and the
census validator read ONE definition (docs/RULINGS.md, grade-law
completeness standard: emitter and validator lockstep, never two copies).

These are SOURCE-INSPECTION twins in the ``test_reference_honesty`` idiom:
the properties they defend are structural (who owns a constant, how many
copies of a name exist), so inspecting the source is the direct test — a
behavioural test would pass just as well with a silently re-introduced
second copy.

Properties, one test each:

* every strip-seam constant ``check_grade`` exposes IS the law module's
  object (identity, not equality — an equal-but-separate copy fails);
* ``check_grade`` defines NO strip-seam constant of its own (the move is
  a move, not a fork);
* the strip-seam predicates ``check_grade`` uses come from the law module;
* the law module is import-light (stdlib only) — a law that can fail to
  import is not a law, and the standalone validator must keep running;
* the TILE-seam constants are named ``TILE_SEAM_*`` at BOTH sites and
  agree in value (the two-site-agreement idiom);
* a bare ``_SEAM_LL_TOL_DEG`` / ``_SEAM_ZONE_M`` survives nowhere (the
  banned bare-"seam" spelling for the tile corridor).

THIRD-COPY ABSORPTION (spec seam-continuity-v3 §1) extends the same three
properties to the EMITTER half of the law,
``adjacent_ground.blend_cross_strip_seam_steps``, which carried a third
equal-valued copy of the radius and step floor under bare-"seam" names:

* the healer's thresholds ARE the law module's objects (identity);
* ``adjacent_ground`` declares no strip-seam constant of its own (AST);
* the retired bare spellings survive nowhere (regex, both sites).

TWO HOMES SINCE SEAM S4 (v1 retirement round 1, 2026-09-17; RULINGS
2026-09-13aw session ruling (d)).  ``tools/check_grade.py`` may no longer
import the v1 tree at all — ``tests/test_v1_retired.py`` holds that line —
so the census reads the law from its own copy,
``tools/harness/law_support/strip_seam.py``, and the v1 EMITTER
(``auto_patch.adjacent_ground``) still reads ``auto_patch.strip_seam_law``.
The identity properties below are therefore asserted WITHIN each half, and
the two halves are held together by (a) VALUE agreement, asserted here, and
(b) TEXTUAL identity of the copy against its source, asserted in
``tests/test_law_support.py`` while the v1 tree is still on disk.  Nothing
weakened: "no second copy anyone can drift" became "one copy per half, and
both are checked against the other".
"""
from __future__ import annotations

import ast
import inspect
import os
import re
import sys
from pathlib import Path

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "tools"), os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade  # noqa: E402


def test_check_grade_defines_no_strip_seam_constant_of_its_own():
    src = Path(inspect.getsourcefile(check_grade)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    assigned = {
        t.id
        for node in tree.body if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    }
    strayed = sorted(n for n in assigned if n.startswith("STRIP_SEAM"))
    assert not strayed, (
        f"check_grade re-declares strip-seam constant(s) {strayed} — they "
        f"belong to auto_patch.strip_seam_law and must only be imported")


