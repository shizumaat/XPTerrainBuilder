"""THE CLUSTER'S COMPOSED BASE PROFILE (base-profile spec §1 (3)/(4)) — one
body group's member profiles composed into ONE frame, as a JOB any process
can run.

The read is split where its cost is (issue #362; owner RULINGS 2026-10-04x
(4)).  MEASURED on the pack stage's own partition: OTHH spends 48.9 s of
its 69.8 s of cluster derivation here, 45.8 s of it in ONE unit
(``unit:28``, 16,609 clusters; its largest group 3.6 s, forty-odd single
bodies ~1 s each) and HECA 4.4 of 9.1 s, 3.5 s of it in ``unit:43`` — so
the work that divides is the GROUP, never the unit:

* :func:`profile_job` — the cheap half, in the caller's process: which
  members, their offsets into the unit frame, the group's feet.  ``None``
  is §1 (3)'s cheap exit (no member carries a base plane).
* :func:`compose_job` — the whole composition, a pure function of the job
  (plain floats, the members' published profile dicts and one array), so a
  worker's answer is the caller's own, bit for bit.
* :func:`compose_jobs` — every job of a plan, IN JOB ORDER, on a work pool
  where one answers and here where none does.

:func:`cluster_base_profile` is the two halves joined: the one spelling
``plan_clusters`` and ``tools/obj8_split_report`` both read.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from . import obj8_grade as _og
from .placement_contact import m_per_deg_exact

__all__ = ["ProfileLaw", "cluster_base_profile", "profile_job",
           "compose_job", "compose_jobs"]


#: base-profile spec §1 (3): THE SIX LAW NUMBERS the composed read needs,
#: each at its OWN existing key at the caller (``planar/cluster.clusters``
#: holds the ``Law``; this module holds no law number, as
#: ``obj8_grade.base_profile`` holds none).  Passing them as one record
#: rather than five keywords keeps ``plan_clusters``'s signature from
#: growing a tail an insertion can shift (``pack_partition``'s own
#: "EVERY OPTIONAL FIELD IS PASSED BY NAME" lesson).
@_dc.dataclass(frozen=True)
class ProfileLaw:
    """``[terrace] pad_terrace_floor_m`` (the riser weld floor), ``[seam]
    pad_frontage_m`` (the adjacency reach), ``[base_profile]
    roof_support_fraction`` (the support-hull share that makes a ROOF),
    ``[basin] contact_band_m`` (how far below a plane a support counts)
    ``[identity] min_distinct_spacing_m`` (the polygon erosion) and
    ``emit.identity.input_quantum_m`` (§51's entry snap, read through
    ``frame_entry.quantum`` — the composition places polygons, so it goes
    through §51 (2)'s one entry site and needs that site's quantum)."""

    pad_terrace_floor_m: float
    pad_frontage_m: float
    roof_support_fraction: float
    contact_band_m: float
    min_distinct_spacing_m: float
    input_quantum_m: float = 0.0


def profile_job(unit: _t.Any, member_ix: _t.Sequence[int], law: ProfileLaw,
                pids: "_t.AbstractSet[int] | None" = None) -> "tuple | None":
    """What :func:`compose_job` needs for one body group, or ``None`` —
    §1 (3)'s cheap exit: no member carries a base plane, nothing is
    composed and nothing is published (every FEET cluster takes it; HECA
    4,565 of 6,151, OTHH 22,233 of 24,521).

    THE FRAME is metres east/north about the UNIT's own anchor.  Each
    member's base polygons are AUTHORED ``(x, z)``; they are rotated by
    that member's ``heading_deg`` and translated to its ``Member.origin``
    (``obj8_grade._place``, the ``placement_affine`` matrix).  The
    composed lower geometry the roof test needs is every PART FOOT of
    the group (``Part.feet`` — the components' own ground-contact
    vertices, ``(lat, lon, authored y)``, RULINGS 2026-09-09s (2)), which
    is exactly the "solid vertices of the UNIT lying contact_band_m or
    more below" a hall floor stands on.

    VERTICALLY NOTHING IS OFFSET.  A unit carries ONE ``agl_m``, so every
    member's authored ``y`` is already in one frame (it is why
    ``PlanCluster.floors`` compares members' ``base_y`` directly, §16g
    (10) (1)).

    A member whose plan ``origin`` is absent (a plan before version 12)
    makes the whole group's read the VERTICAL-ONLY upper bound — never a
    composed answer from a half-placed set."""
    seen: list[int] = []
    for mi in member_ix:
        if mi not in seen:
            seen.append(mi)
    mems = [unit.members[mi] for mi in seen]
    if not any((m.base_profile or {}).get("planes") for m in mems):
        return None
    lat0, lon0 = float(unit.anchor[0]), float(unit.anchor[1])
    ml, mo = m_per_deg_exact(lat0)
    placed = all(getattr(m, "origin", None) is not None for m in mems)
    rows = []
    for m in mems:
        if placed:
            o = m.origin
            dE = (float(o[1]) - lon0) * mo
            dN = (float(o[0]) - lat0) * ml
            rows.append((m.base_profile, (dE, 0.0, dN), float(m.heading_deg)))
        else:
            rows.append((m.base_profile, (0.0, 0.0, 0.0), 0.0))
    lower = None
    if placed:
        pts = [((float(lo) - lon0) * mo, float(y), (float(la) - lat0) * ml)
               for m in mems for q in m.parts
               if pids is None or q.pid in pids
               for (la, lo, y) in q.feet]
        if pts:
            lower = np.asarray(pts, dtype=float)
    return (rows, lower, placed, law)


def compose_job(job: tuple) -> "tuple[dict, str]":
    """One :func:`profile_job` composed: ``(the profile as its publication
    dict, the composition label)`` — ``"composed"``, or ``"vertical_only"``
    where the plan carried no origins (the per-member upper bound).

    THE PROBLEM THIS SOLVES, measured (base-profile spec §0 fact 10, §5
    A5, §6's STOP): a member's OWN base read cannot see supports that
    live in a SIBLING member, so HECA's T3 complex (``unit:43``) reads
    STEPPED with **113 planes** at the per-member upper bound — the halls'
    upper floors, whose walls are other members' geometry.  §1 (3)
    composes the members into ONE frame and RE-RUNS the roof test there,
    and those floors read ROOF.  A plane pad minted for one of them is
    §6's "a plane pad whose polygon contains lower geometry of its unit
    after composition (a roof pad)"."""
    rows, lower, placed, law = job
    comp = _og.compose_profiles(
        [(_og.profile_from_json(d), off, hdg) for d, off, hdg in rows],
        pad_terrace_floor_m=law.pad_terrace_floor_m,
        pad_frontage_m=law.pad_frontage_m,
        roof_support_fraction=(law.roof_support_fraction if lower is not None
                               else 0.0),
        lower_pts=lower, contact_band_m=law.contact_band_m,
        min_distinct_spacing_m=law.min_distinct_spacing_m,
        input_quantum_m=law.input_quantum_m)
    return (_og.profile_to_json(comp), "composed" if placed else "vertical_only")


def cluster_base_profile(unit: _t.Any, member_ix: _t.Sequence[int],
                         law: ProfileLaw,
                         pids: "_t.AbstractSet[int] | None" = None,
                         ) -> "tuple[dict, str]":
    """§1 (3) THE COMPOSED-UNIT PROFILE of one body group — ``({}, "")``
    where no member carries a base plane (today's law exactly), else
    :func:`compose_job` of its :func:`profile_job`."""
    job = profile_job(unit, member_ix, law, pids=pids)
    return ({}, "") if job is None else compose_job(job)


def _weight(job: tuple) -> float:
    """How heavy a job is to compose: its planes times its feet."""
    rows, lower, _placed, _law = job
    planes = sum(len(d.get("planes") or ()) for d, _o, _h in rows if d)
    return float(planes) * float(1 + (0 if lower is None else lower.shape[0]))


def _compose_task(_state: _t.Any, job: tuple) -> "tuple[dict, str]":
    """:func:`compose_job` as a work-pool task (the worker state is unused:
    a job carries its own law)."""
    return compose_job(job)


def compose_jobs(jobs: _t.Sequence[tuple], pool: _t.Any = None
                 ) -> "list[tuple[dict, str]]":
    """``[compose_job(j) for j in jobs]`` — computed by ``pool``'s workers
    (``airport/pool.WorkPool``) where one answers, here where none does;
    the same function either way, the answers in JOB order."""
    jobs = list(jobs)
    if pool is not None and len(jobs) > 1:
        got = pool.try_map(_compose_task, jobs, weights=[_weight(j) for j in jobs],
                           what="terminal clusters: base profiles", unit="clusters")
        if got is not None:
            return got
    return [compose_job(j) for j in jobs]
