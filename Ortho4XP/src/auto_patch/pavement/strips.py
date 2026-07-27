"""Pavement role vocabulary — the five canonical role-string constants.

``layout.py`` re-exports these (``ROLE_PRIMARY_PARALLEL`` …
``ROLE_APRON``) and the rest of ``auto_patch`` consumes them from
there.  Do not inline the literals elsewhere: role *values* are a
silent-rename hazard (see ``tools/blast.py`` at the repo root, which
resolves this alias hop when indexing role literals).

History (owner rulings, 2026-07-26): this module once held the
geometric pavement *decomposition* front-end — ``decompose_pavement``
with its MRR / Voronoi-skeleton / trunk-extraction helpers and the
``taxiway_skeleton`` module — plus the ``Shape``/``Adjacency``
classifiers built on it.  Production never routed through any of it
(the pipeline builds taxi/apron geometry in ``pavement/rects.py`` and
friends); the sole callers were this module's own tests.  All of it
was deleted.  Recover from git history if ever needed.
"""
from __future__ import annotations

# Role labels for classified pavement shapes.  layout.py aliases these
# as its own ROLE_* constants; the string VALUES are load-bearing.
ROLE_PRIMARY_PARALLEL = "primary_parallel"
ROLE_STUB = "stub"
ROLE_SECONDARY_PARALLEL = "secondary_parallel"
ROLE_CROSS_CONNECTOR = "cross_connector"
ROLE_APRON = "apron"
