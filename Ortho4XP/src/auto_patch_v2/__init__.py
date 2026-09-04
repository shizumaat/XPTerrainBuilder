"""auto_patch_v2 — the ground-up graded-surface engine (RULINGS
2026-09-03d; plan ``docs/specs/auto-patch-v2-plan.md``).

Packages, in dependency order (each imports only those before it):
``law`` -> ``model`` -> ``solve`` -> ``emit``.  M1 adds the producers
(``airport`` loaders, ``classify``, ``planar`` builder) between ``model``
and ``solve``; M2 adds ``constraints`` generators and ``verify``.
Nothing is imported from ``auto_patch`` (v1).
"""
__version__ = "0.0.M0"
