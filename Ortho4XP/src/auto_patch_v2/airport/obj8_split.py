"""THE OBJ8 SPLIT WRITER (spec ``object-placement-spec.md`` §4; owner
RULINGS 2026-09-11b).

One authored placement is ONE object with ONE anchor.  X-Plane drapes an
``OBJECT`` (AGL) placement by sampling the terrain UNDER THAT ANCHOR, so a
mega-object whose components stand kilometres apart renders every one of
them on the ground of a single point (Aerosoft LEMD: 302 members under 31
anchors, 32 m of relief across them).  The cure is not a seat: it is to
cut the file into its RIGID BODIES — the very bodies ``emit/clusters``
already forms — and give each its own placement and its own anchor (§6).

WHAT THIS MODULE IS
-------------------

:func:`split_obj8` reads the PRISTINE OBJ8 (``.anchor_bak`` when one
exists — restore-before-read), walks its command stream ONCE, and returns
one :class:`SplitFile` per body: the body's ``TRIS`` / ``LINES`` /
``LIGHTS`` with a freshly re-indexed ``VT`` / ``VLINE`` / ``VLIGHT`` /
``IDX`` table of its own, the ``ATTR_*`` STATE in force re-emitted at the
body's first command, every ``ATTR_LOD`` bracket the body has geometry in
replayed, each top-level ``ANIM`` block kept WHOLE, ``POINT_COUNTS``
recomputed and a provenance comment after the header.  The original file
is never touched and nothing here writes anything: the caller decides
where the files land.

THE FOUR RULES THE WALK OBEYS
-----------------------------

1. **Attribute state is re-emitted, never inherited.**  A ``TRIS`` renders
   under whatever ``ATTR_*`` state the stream left standing, and a cut
   file starts with none of it.  The walk therefore tracks the state by
   GROUP (``ATTR_no_blend`` replaces ``ATTR_blend``; ``ATTR_hard``,
   ``ATTR_hard_deck`` and ``ATTR_no_hard`` are one group) and, before each
   command it emits into a body, writes the lines of every group whose
   value differs from what that body's file already carries.  At the
   body's FIRST command that is the whole state in force — §4.2's words —
   and thereafter it is exactly the changes, so the cut file replays the
   original's attribute history over its own geometry.

2. **``ATTR_LOD`` is a bracket, and a body appears in every bracket it has
   geometry in** (§4.4).  The bracket line is replayed ahead of the body's
   first command inside it.

3. **A top-level ``ANIM_begin … ANIM_end`` block moves as one** (§4.4, v1
   invariant I-11: baking half an animation bends its pivot).  The block's
   triangles are counted per body and the WHOLE block — every line of it,
   at every nesting depth — goes to the body owning most of them.

4. **The translation never bends an animation.**  Every vertex a body uses
   OUTSIDE an animation is written translated by ``-offset`` (§4.3: the
   body's new anchor becomes its origin).  A vertex used INSIDE a block is
   written UNTRANSLATED into the same table, and the block's own
   ``ANIM_begin`` is followed by a static compensating
   ``ANIM_trans -dx -dy -dz -dx -dy -dz 0 0 none``.  That is the only
   rewrite that is algebraically right: the rendered point must be
   ``T(v) - o`` where ``T`` is the block's accumulated transform, and
   ``Trans(-o)·T`` gives exactly that, while translating the vertices and
   leaving the block's own ``ANIM_trans`` pivots alone would displace the
   pivot by ``+o`` and swing the door through the wall.  A vertex used
   both inside and outside a block is simply written TWICE (the tables
   are rebuilt per body anyway), so nothing straddles by accident.

5. **A SEAT TILT is baked into the vertices, and so are the normals**
   (owner RULINGS 2026-10-01k Q1; base-profile spec §8a Q1).  A DSF
   ``OBJECT`` row carries HEADING only, so a post-feet body that must
   stand on a graded apron can only be seated by rotating the model
   itself.  :attr:`BodyCut.tilt` names that rotation as the two authored
   gradients the body's own feet fitted, and every vertex a body keeps is
   written ``R · (v − offset)`` with ``R`` from :func:`tilt_matrix` —
   the translation first, so the rotation is about the body's NEW origin,
   which is the point X-Plane drapes.  A ``VT`` row's NORMAL triple is
   rotated with its position (a tilted body whose normals stayed put
   lights as though it were still level), and ``LIGHT_*`` / ``SMOKE_*``
   positions rotate too.  Nothing here decides WHETHER a body tilts or by
   how much — that is ``airport/placement_seat_tilt.py``, which fits the
   gradients on the design surface under the feet and caps them.

   A body that owns an ``ANIM`` block is NEVER tilted: rule 4's
   compensation is a translation and there is no ``ANIM`` command that
   pre-rotates a block's accumulated frame, so baking the rotation would
   swing the animated part out of its pivot.  Such a body is written
   UNTILTED and counted (``counts["tilt_refused_anim"]``) — reported,
   never silently bent.

WHEN A PLACEMENT IS KEPT WHOLE
------------------------------

:attr:`SplitResult.kept_whole` names the reason and :attr:`files` is then
empty — the caller leaves the placement exactly as authored (§2 ``kept``):

``one_body``     the cut would produce a single file: the object already IS
                 one body (the overwhelming majority of a pack).  §14 (1)
                 gives that case a reason to be WRITTEN anyway — a
                 FOOTLESS placement carried onto another body's anchor is
                 one body and must move, and so is a one-body placement
                 whose authored row reads different terrain from its own
                 anchor — so the caller asks for it with
                 ``allow_single=True`` and gets its one translated file.
``no_bodies``    no body was handed in, or none of them owns any geometry.
``anim``         a body's triangles lie inside a block another body owns,
                 so cutting at block granularity would still tear it.
``unparsable``   the file carries no ``VT`` table this reader can find.

Nothing numeric and nothing about WHERE a body's anchor goes lives here —
that is ``airport/anchor_rule.py`` (§6), which computes the ``offset``
this writer applies.
"""
from __future__ import annotations

import dataclasses as _dc
import hashlib
import math
import os
import struct
import typing as _t

import numpy as np

from . import obj8 as _obj8

__all__ = ["BodyCut", "SplitFile", "SplitResult", "split_obj8",
           "body_resource_name", "offset_tag", "tilt_matrix", "NO_TILT",
           "SEAT_OWNED_DIRECTIVES", "is_seat_owned", "strip_seat_owned",
           "seat_owned_in_file", "SEAT_HEADER_BYTES"]

#: :attr:`BodyCut.tilt` for a body that is NOT tilted — the identity, and
#: the value every caller that knows nothing of the seat tilt passes.
NO_TILT: "tuple[float, float]" = (0.0, 0.0)

#: THE SEAT IS THE STAGE'S (issue #232; #162, #163).  These two OBJ8
#: header directives hand the seat to X-PLANE: ``TILTED`` rotates the
#: whole object to the terrain normal sampled under its own DSF anchor,
#: and ``SLOPE_LIMIT`` is the band it does that in.  Every file THIS
#: writer mints is already seated by the stage — its vertices carry the
#: body's own offset and, under 10-01k Q1, the fitted seat rotation — so
#: replaying either directive asks X-Plane to seat it a SECOND time, on a
#: normal the stage never read:
#:
#: * the bodies of ONE building sit at DIFFERENT anchors (that is what a
#:   split is), so each tilts to its own patch of terrain and the parts
#:   come apart — KASE's fire station, 6 placements cut into 14 bodies
#:   at 9 anchors, rigid plan (seat spread 0.000 m), 3.91 m apart at the
#:   owner's point;
#: * a body whose seat tilt the stage BAKED is tilted again on top of the
#:   bake — KASE's shelters, one body, 0.75 deg baked within tolerance,
#:   then the anchor's 1.46 % slope applied over it: 284 of 292 feet
#:   float, p50 +1.39 m, max +2.95 m.
#:
#: So a written file carries NEITHER, wherever the authored file spelled
#: it.  An AUTHORED file this stage does not write keeps what it was
#: authored with — stripping a directive out of the user's own object is
#: not this writer's act — and the kept-whole census counts those
#: (``placement_plan``'s ``tilted_kept_whole``) for the owner to rule on.
SEAT_OWNED_DIRECTIVES: frozenset = frozenset({"TILTED", "SLOPE_LIMIT"})


def is_seat_owned(line: str) -> bool:
    """Whether ``line`` is one of :data:`SEAT_OWNED_DIRECTIVES` — the
    ONE test, so the header writer and the command replay cannot drift
    apart about what a written file may carry."""
    s = line.strip()
    if not s:
        return False
    return s.split(None, 1)[0] in SEAT_OWNED_DIRECTIVES


def strip_seat_owned(lines: "_t.Iterable[str]") -> "list[str]":
    """``lines`` without the seat directives, every other line kept in
    order (:data:`SEAT_OWNED_DIRECTIVES`)."""
    return [ln for ln in lines if not is_seat_owned(ln)]


#: How far into a file the seat directives are looked for.  Both are OBJ8
#: HEADER directives, so they stand before ``POINT_COUNTS`` and therefore
#: before the first ``VT``; ``object_pavement.header_facts`` reads the
#: same header under the same budget.
SEAT_HEADER_BYTES = 8192


def seat_owned_in_file(path: str) -> "tuple[str, ...]":
    """The seat directives the file at ``path`` SPELLS, in the order it
    spells them (``()`` where it spells none, or where the file cannot be
    read — a census, never a refusal).

    This is the KEPT-WHOLE reading (#232): the placement stage does not
    write such a file, so what it carries is the author's and is reported,
    not changed.  It reads :data:`SEAT_HEADER_BYTES` and stops at the
    vertex table, so a file whose body happens to contain the word is not
    counted.
    """
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as fh:
            head = fh.read(SEAT_HEADER_BYTES)
    except OSError:
        return ()
    found: list[str] = []
    for ln in head.split("\n"):
        s = ln.strip()
        kw = s.split(None, 1)[0] if s else ""
        if kw in ("VT", "VLINE", "VLIGHT") or kw.startswith("IDX"):
            break
        if kw in SEAT_OWNED_DIRECTIVES:
            found.append(kw)
    return tuple(found)

#: The commands that carry a POSITION in the authored frame and must be
#: translated with the vertices: keyword -> index of the first of the
#: three coordinate tokens (the token index counts the keyword as 0).
_POSITIONAL: dict[str, int] = {
    "LIGHT_NAMED": 2, "LIGHT_PARAM": 2, "LIGHT_CUSTOM": 1, "LIGHT_SPILL_CUSTOM": 1,
    "LIGHT": 1, "SMOKE_BLACK": 1, "SMOKE_WHITE": 1,
}

#: Attribute keywords whose state group is not simply their own name with a
#: leading ``no_`` stripped (the convention every other ``ATTR_`` follows).
_ATTR_GROUP: dict[str, str] = {
    "ATTR_hard": "hard", "ATTR_hard_deck": "hard", "ATTR_no_hard": "hard",
    "ATTR_shadow_blend": "blend", "ATTR_blend": "blend", "ATTR_no_blend": "blend",
    "ATTR_cockpit_region": "cockpit", "ATTR_cockpit": "cockpit",
    "ATTR_no_cockpit": "cockpit",
    "ATTR_light_level_reset": "light_level", "ATTR_light_level": "light_level",
    "ATTR_manip_none": "manip",
}


def _attr_group(kw: str) -> str:
    """The STATE GROUP a keyword sets (rule 1).  ``ATTR_manip_*`` is one
    group whatever the manipulator; everything else follows X-Plane's own
    ``ATTR_x`` / ``ATTR_no_x`` naming."""
    if kw in _ATTR_GROUP:
        return _ATTR_GROUP[kw]
    if kw.startswith("ATTR_manip"):
        return "manip"
    body = kw[len("ATTR_"):]
    if body.startswith("no_"):
        body = body[3:]
    return body


@_dc.dataclass(frozen=True)
class BodyCut:
    """One body to cut out: its component indices into
    ``obj8.solid_components`` of the SAME pristine file, and the authored
    offset (§4.3 / §6) subtracted from every vertex it keeps.

    A body is NOT always a set of components (owner RULINGS 2026-09-11f
    (2); spec §10): a LINE OBJECT authored as one component is cut into
    SEGMENTS, and a segment is a set of TRIANGLES of that component.
    ``tris`` names them as authored vertex triples — the same triples the
    ``IDX`` table spells — and, where it is given, it is SENIOR to the
    vertex vote: a triangle named here belongs to this body whatever its
    vertices are shared with (two segments share the vertices of the
    panel they meet at, and a vote cannot separate them)."""

    body_id: int
    comps: tuple[int, ...]
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    #: authored vertex triples this body owns outright (a SEGMENT)
    tris: tuple[tuple[int, int, int], ...] = ()
    #: THE SEAT TILT (rule 5; owner RULINGS 2026-10-01k Q1): the two
    #: AUTHORED-frame gradients ``(dy/dx, dy/dz)`` of the plane the body's
    #: own feet fitted on the design surface, as
    #: ``placement_seat_tilt.fit`` decided them.  :data:`NO_TILT` — the
    #: default, and what every body with a floor plane keeps — writes
    #: exactly the pre-tilt bytes.  The rotation itself is
    #: :func:`tilt_matrix`; this names it in ONE place so the fit's
    #: residual check and the writer cannot disagree about what was baked.
    tilt: tuple[float, float] = NO_TILT


@_dc.dataclass(frozen=True)
class SplitFile:
    """One body's file: ``resource`` is the pack-relative name (§4.5),
    ``text`` its whole content.  The counts are what the caller reports
    and the twins assert."""

    body_id: int
    resource: str
    text: str
    vertices: int
    tris: int
    offset: tuple[float, float, float]
    lods: tuple[str, ...]
    anim_blocks: int
    #: rule 5: the seat tilt THIS FILE ACTUALLY BAKED — :data:`NO_TILT`
    #: where the body was not tilted, or where it owns an ANIM block and
    #: the writer refused the tilt.  The plan's ``seat`` record says what
    #: was ASKED FOR; this says what was written, and the two differ
    #: exactly on the refusal the counts name.
    tilt: tuple[float, float] = NO_TILT


@_dc.dataclass(frozen=True)
class SplitResult:
    source: str
    files: tuple[SplitFile, ...]
    kept_whole: str
    counts: _t.Mapping[str, int]


def tilt_matrix(tilt: _t.Sequence[float]) -> np.ndarray:
    """THE SEAT ROTATION, DERIVED ONCE (rule 5; owner RULINGS 2026-10-01k
    Q1).

    ``tilt`` is the pair of AUTHORED-frame gradients ``(gx, gz)`` of the
    plane the feet fitted: the plane ``y = gx·x + gz·z`` through the
    body's own origin.  The matrix returned is the MINIMAL rotation that
    carries the authored up axis onto that plane's normal — Rodrigues
    about ``ŷ × n``, so no third degree of freedom (a yaw) is invented
    and the body's HEADING, which is the one thing the DSF row still
    carries, is untouched.

    It is a rotation, not a shear: ``RᵀR = I``, so the model is seated
    without being stretched, and ``(R·(1,0,0))ᵧ = gx/√(1+|g|²)`` — the
    authored ``+x`` end rises by the fitted gradient (exactly, to the
    cosine the rotation costs), and ``+z`` by ``gz``.
    :data:`NO_TILT` returns the identity, which is why an untilted body's
    file is byte-identical to the pre-tilt writer's.
    """
    gx, gz = float(tilt[0]), float(tilt[1])
    g = math.hypot(gx, gz)
    if g == 0.0:
        return np.eye(3)
    theta = math.atan(g)
    kx, ky, kz = -gz / g, 0.0, gx / g
    K = np.asarray([[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]])
    return np.eye(3) + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)


def offset_tag(offset: _t.Sequence[float],
               tilt: _t.Sequence[float] = NO_TILT) -> str:
    """THE BAKED TRANSFORM, AS EIGHT HEX CHARACTERS (RULINGS 2026-09-14at;
    the seat tilt added by 2026-10-01k Q1).

    The tag is a pure function of what the cut BAKES into the vertices it
    keeps — ``blake2s`` over the IEEE-754 bytes of the three offset
    doubles, and of the two tilt gradients where the body is tilted — and
    of nothing else.  That is the whole reason it is a hash and not
    "the index of this offset among the resource's distinct offsets":
    an index is a function of the POPULATION, so adding or removing an
    unrelated placement of the same resource renames another
    placement's file, and the previous write's own body files (the ones
    ``o4_placement_provenance.json`` names) then go stale in the pack.
    The hash renames a file only when the file's own contents move.

    THE TILT IS IN THE TAG for the same reason the offset is (14at's
    OTHH ``tunnel1``, 38.7 m): two placements of one resource over two
    aprons fit two different gradients, and a name blind to the tilt
    would give the second placement the first one's seated geometry.  An
    UNTILTED body hashes exactly the three doubles 14at hashed, so every
    file a pre-tilt write named keeps its name and no pack churns.
    """
    x, y, z = (float(v) for v in offset)
    gx, gz = float(tilt[0]), float(tilt[1])
    if (gx, gz) == (0.0, 0.0):
        return hashlib.blake2s(struct.pack("<3d", x, y, z),
                               digest_size=4).hexdigest()
    return hashlib.blake2s(struct.pack("<5d", x, y, z, gx, gz),
                           digest_size=4).hexdigest()


def body_resource_name(resource: str, k: int,
                       offset: "_t.Sequence[float] | None" = None,
                       tilt: _t.Sequence[float] = NO_TILT) -> str:
    """``objects/<stem>__b<k>_<tag>.obj`` beside the original (§4.5).

    THE FILE IS KEYED ON WHAT IT CONTAINS (owner RULINGS 2026-09-14at;
    the owner's missing OTHH tunnel wall at 25.2697569, 51.6055534).
    ``resource`` and ``body_id`` name a body SLOT — a member's k-th
    group — but ``authored_offset`` is per PLACEMENT, and a pack may
    place one resource twice: OTHH's ``tunnels/tunnel1.obj`` stands at
    two anchors 38.7 m apart, both placements wrote
    ``tunnels/tunnel1__b0.obj``, the file baked the FIRST placement's
    offset and the second wall rendered 38.7 m from its own DSF row.
    The offset therefore belongs in the name: two placements whose
    bodies bake different offsets get two files, and two that bake the
    SAME offset still share one (the tag is equal, so nothing is
    duplicated).

    ``offset`` None spells the UNTAGGED name — a body SLOT's id, used
    where no file is being named (a carrier candidate before pass 3 has
    replaced its anchor, and the prose that quotes it).  Every caller
    that names a FILE passes the offset the cut will bake.
    """
    stem, _ext = os.path.splitext(resource)
    if offset is None:
        return f"{stem}__b{k}.obj"
    return f"{stem}__b{k}_{offset_tag(offset, tilt)}.obj"


# ── the file, as text ────────────────────────────────────────────────────

@_dc.dataclass
class _Source:
    header: list[str]
    vt: list[str]
    vline: list[str]
    vlight: list[str]
    idx: np.ndarray
    commands: list[str]
    point_counts_at: int


def _read(path: str) -> _Source | None:
    """Split the file into header / vertex tables / index table / command
    stream.  ``latin-1`` round-trips every byte, so a comment in any
    encoding survives untouched."""
    with open(path, "rb") as fh:
        raw = fh.read()
    lines = raw.decode("latin-1").split("\n")
    header: list[str] = []
    vt: list[str] = []
    vline: list[str] = []
    vlight: list[str] = []
    idx: list[int] = []
    commands: list[str] = []
    pc_at = -1
    seen_table = False
    for ln in lines:
        s = ln.strip()
        kw = s.split(None, 1)[0] if s else ""
        if kw == "VT":
            seen_table = True; vt.append(s); continue
        if kw == "VLINE":
            seen_table = True; vline.append(s); continue
        if kw == "VLIGHT":
            seen_table = True; vlight.append(s); continue
        if kw.startswith("IDX"):
            seen_table = True
            idx.extend(int(t) for t in s.split()[1:] if _is_int(t))
            continue
        if kw == "POINT_COUNTS":
            pc_at = len(header); header.append(s); continue
        if not seen_table:
            header.append(ln.rstrip("\r"))
        elif s:
            commands.append(s)
    if not vt:
        return None
    return _Source(header, vt, vline, vlight,
                   np.asarray(idx, dtype=np.int64), commands, pc_at)


def _is_int(tok: str) -> bool:
    try:
        int(tok)
    except ValueError:
        return False
    return True


def _coords(rows: list[str], n_lead: int) -> np.ndarray:
    """The first three floats after the keyword of each row."""
    out = np.zeros((len(rows), 3))
    for i, r in enumerate(rows):
        t = r.split()
        try:
            out[i] = [float(t[n_lead]), float(t[n_lead + 1]), float(t[n_lead + 2])]
        except (IndexError, ValueError):
            pass
    return out


def _retok(line: str, first: int, delta: tuple[float, float, float],
           rot: "np.ndarray | None" = None, normal_at: int = -1) -> str:
    """``line`` with its three coordinate tokens at ``first`` moved into
    the body's own frame — shifted by ``-delta`` and then, where ``rot``
    is given, ROTATED about the new origin (rule 5) — printed to the
    millimetre (the authored files' own precision).

    ``normal_at`` names a second triple on the same row that is a
    DIRECTION, not a position: a ``VT`` row's normal, which is rotated by
    the same ``rot`` and never translated.  It is written to six decimals,
    the unit-vector precision the exporters use; a zero or unparsable
    normal is left exactly as authored.
    """
    t = line.split()
    try:
        p = [float(t[first + j]) - delta[j] for j in range(3)]
    except (IndexError, ValueError):
        return line
    if rot is not None:
        p = [float(rot[r][0] * p[0] + rot[r][1] * p[1] + rot[r][2] * p[2])
             for r in range(3)]
    for j in range(3):
        t[first + j] = f"{p[j]:.3f}"
    if rot is not None and normal_at >= 0:
        try:
            n = [float(t[normal_at + j]) for j in range(3)]
        except (IndexError, ValueError):
            return "\t".join(t)
        if n[0] or n[1] or n[2]:
            n = [float(rot[r][0] * n[0] + rot[r][1] * n[1] + rot[r][2] * n[2])
                 for r in range(3)]
            for j in range(3):
                t[normal_at + j] = f"{n[j]:.6f}"
    return "\t".join(t)


# ── the cut ──────────────────────────────────────────────────────────────

def split_obj8(pristine_path: str, bodies: _t.Sequence[BodyCut],
               resource: str = "", *, allow_single: bool = False) -> SplitResult:
    """Cut ``pristine_path`` into one file per body (module doc).  Reads
    the file and returns text; writes nothing.  ``resource`` is the
    pack-relative spelling the new names are derived from (defaults to
    the file's own basename under ``objects/``)."""
    counts: dict[str, int] = {"bodies": len(bodies), "tris": 0, "assigned": 0,
                              "nearest": 0, "anim_blocks": 0, "lod_brackets": 0,
                              # #232: the seat directives this writer
                              # dropped out of the SOURCE (once per source,
                              # not once per body — every body's file loses
                              # the same lines)
                              "seat_owned_dropped": 0}
    src = _read(pristine_path)
    if src is None:
        return SplitResult(pristine_path, (), "unparsable", counts)
    if not bodies:
        return SplitResult(pristine_path, (), "no_bodies", counts)
    geom = _obj8.parse_obj8(pristine_path)
    comps = _obj8.solid_components(geom)
    verts = _coords(src.vt, 1)
    # vertex -> body, from the bodies' own components
    body_of_vertex: dict[int, int] = {}
    centroid: dict[int, np.ndarray] = {}
    #: the SEGMENT map (11f (2)): an authored triangle this body owns
    #: outright, senior to every vote below
    tri_owner: dict[tuple[int, int, int], int] = {}
    #: §16c (1): THE COMPONENT IS THE ATOM.  The authored triangle (as
    #: its sorted vertex triple) -> its component index, and the body
    #: that owns each component.  No triangle is ever assigned to a body
    #: that does not own its component (owner RULINGS 2026-09-12d).
    comp_of_tri: dict[tuple[int, int, int], int] = {}
    for ci, c in enumerate(comps):
        for row in np.asarray(c.tris).tolist():
            comp_of_tri[tuple(sorted(int(q) for q in row))] = ci
    body_of_comp: dict[int, int] = {}
    comp_tri_keys: dict[int, list[tuple[int, int, int]]] = {}
    for k, ci in comp_of_tri.items():
        comp_tri_keys.setdefault(ci, []).append(k)
    for b in bodies:
        pts: list[np.ndarray] = []
        for ci in b.comps:
            if 0 <= ci < len(comps):
                body_of_comp[ci] = b.body_id
                vi = np.unique(np.asarray(comps[ci].tris).reshape(-1))
                for v in vi.tolist():
                    body_of_vertex[int(v)] = b.body_id
                pts.append(verts[vi[vi < verts.shape[0]]])
        if b.tris:
            t = np.asarray(b.tris, dtype=np.int64).reshape(-1, 3)
            for row in t.tolist():
                tri_owner[tuple(sorted(row))] = b.body_id
            vi = np.unique(t.reshape(-1))
            for v in vi.tolist():
                body_of_vertex[int(v)] = b.body_id
            pts.append(verts[vi[vi < verts.shape[0]]])
        centroid[b.body_id] = (np.concatenate(pts).mean(axis=0) if pts
                               else np.zeros(3))
    if not body_of_vertex:
        return SplitResult(pristine_path, (), "no_bodies", counts)
    ids = [b.body_id for b in bodies]
    cen = np.asarray([centroid[i] for i in ids])

    def nearest(p: np.ndarray) -> int:
        d = (cen[:, 0] - p[0]) ** 2 + (cen[:, 2] - p[2]) ** 2
        return ids[int(np.argmin(d))]

    n_idx = int(src.idx.shape[0])
    nv = verts.shape[0]

    #: §16c (1): the body a component with NO owner falls to, decided
    #: ONCE for the whole component (its plan centroid) — never per
    #: triangle, which is what tore the vault.
    comp_fallback: dict[int, int] = {}

    def _fallback(ci: int, among: "list[int] | None" = None) -> int:
        hit = comp_fallback.get(ci)
        if hit is not None and among is None:
            return hit
        pts = verts[np.unique(np.asarray(comps[ci].tris).reshape(-1))
                    ] if 0 <= ci < len(comps) else np.zeros((1, 3))
        p = pts.mean(axis=0) if pts.size else np.zeros(3)
        if among:
            # the component is already divided by a LAWFUL station cut
            # (§10's segment, §14a's arc): its unclaimed triangles stay
            # inside the component, with the nearest of ITS OWN pieces
            sel = min(among, key=lambda bid: float(
                (centroid[bid][0] - p[0]) ** 2 + (centroid[bid][2] - p[2]) ** 2))
            return sel
        comp_fallback[ci] = nearest(p)
        return comp_fallback[ci]

    def tri_body(a: int, b: int, c: int) -> int:
        """The body of one triangle (§16c (1): NO CUT CROSSES A CONNECTED
        COMPONENT).

        The SEGMENT or ARC that names the triangle outright (§10 / §14a,
        the only lawful station cuts) is senior; otherwise the triangle
        goes to the body that owns ITS COMPONENT, and a component no
        body owns goes WHOLE to the nearest body.  The vertex vote and
        the per-triangle nearest fallback are DELETED: a boundary drawn
        between two triangles of one welded solid writes its halves at
        two zeros, which is the mechanism behind every one of the
        owner's 1.0.320 sites (RULINGS 2026-09-12d)."""
        key = (a, b, c) if a <= b <= c else tuple(sorted((a, b, c)))
        if tri_owner:
            hit = tri_owner.get(key)
            if hit is not None:
                counts["segment"] = counts.get("segment", 0) + 1
                return hit
        ci = comp_of_tri.get(key, -1)
        if ci >= 0:
            own = body_of_comp.get(ci)
            if own is not None:
                counts["assigned"] += 1
                return own
            counts["nearest"] += 1
            # a component a STATION cut already divided keeps its own
            # pieces; one no body claims at all goes whole to the nearest
            share = sorted({tri_owner[k] for k in comp_tri_keys.get(ci, ())
                            if k in tri_owner}) if tri_owner else []
            return _fallback(ci, share or None)
        # a triangle in no solid component at all (a thin sheet, an
        # exporter's ground paint): it is its own atom
        counts["nearest"] += 1
        p = verts[[i for i in (a, b, c) if 0 <= i < nv]] if nv else np.zeros((1, 3))
        return nearest(p.mean(axis=0) if p.size else np.zeros(3))

    # ── pass 1: the ANIM blocks, and who owns each ──────────────────────
    #: index into ``src.commands`` -> (block id) for every line of a block
    block_of_line: dict[int, int] = {}
    blocks: list[dict[str, _t.Any]] = []
    depth = 0
    cur: dict[str, _t.Any] | None = None
    for i, ln in enumerate(src.commands):
        kw = ln.split(None, 1)[0]
        if kw == "ANIM_begin":
            if depth == 0:
                cur = {"id": len(blocks), "lines": [], "votes": {}}
                blocks.append(cur)
            depth += 1
        if cur is not None:
            block_of_line[i] = cur["id"]
            cur["lines"].append(i)
        if kw == "ANIM_end":
            depth = max(0, depth - 1)
            if depth == 0:
                cur = None
    counts["anim_blocks"] = len(blocks)
    for blk in blocks:
        for i in blk["lines"]:
            t = src.commands[i].split()
            if t[0] != "TRIS" or len(t) < 3:
                continue
            off, cnt = int(t[1]), int(t[2])
            for k in range(off, min(off + cnt, n_idx) - 2, 3):
                bid = tri_body(int(src.idx[k]), int(src.idx[k + 1]), int(src.idx[k + 2]))
                blk["votes"][bid] = blk["votes"].get(bid, 0) + 1
        blk["owner"] = (max(blk["votes"].items(), key=lambda kv: (kv[1], -kv[0]))[0]
                        if blk["votes"] else None)

    # a body whose triangles fall inside a block another body owns would
    # still be torn at block granularity (§4.4): keep the placement whole
    for blk in blocks:
        if blk["owner"] is not None and len(blk["votes"]) > 1:
            return SplitResult(pristine_path, (), "anim", counts)

    # ── pass 2: the walk ────────────────────────────────────────────────
    out: dict[int, list[str]] = {b.body_id: [] for b in bodies}
    idx_out: dict[int, list[int]] = {b.body_id: [] for b in bodies}
    vt_out: dict[int, list[str]] = {b.body_id: [] for b in bodies}
    vline_out: dict[int, list[str]] = {b.body_id: [] for b in bodies}
    vlight_out: dict[int, list[str]] = {b.body_id: [] for b in bodies}
    vmap: dict[int, dict[tuple[int, bool], int]] = {b.body_id: {} for b in bodies}
    lmap: dict[int, dict[tuple[int, bool], int]] = {b.body_id: {} for b in bodies}
    written_state: dict[int, dict[str, str]] = {b.body_id: {} for b in bodies}
    written_lod: dict[int, str] = {b.body_id: "\0" for b in bodies}
    lods_seen: dict[int, list[str]] = {b.body_id: [] for b in bodies}
    anim_count: dict[int, int] = {b.body_id: 0 for b in bodies}
    tri_count: dict[int, int] = {b.body_id: 0 for b in bodies}
    offset_of = {b.body_id: b.offset for b in bodies}
    # rule 5: the body's own seat rotation, or None where it is not
    # tilted (then every row below takes the pre-tilt path exactly)
    tilt_of: dict[int, "np.ndarray | None"] = {
        b.body_id: (None if tuple(b.tilt) == NO_TILT else tilt_matrix(b.tilt))
        for b in bodies}
    #: rule 5: a body that OWNS an ANIM block is written untilted — the
    #: compensation of rule 4 is a translation and no ANIM command
    #: pre-rotates a block's frame, so the rotation would swing the
    #: animated part out of its pivot.  Counted, never silent.
    for blk in blocks:
        _bid = blk.get("owner")
        if _bid is not None and tilt_of.get(_bid) is not None:
            tilt_of[_bid] = None
            counts["tilt_refused_anim"] = counts.get("tilt_refused_anim", 0) + 1
    counts["tilted"] = sum(1 for v in tilt_of.values() if v is not None)

    def vt_index(body: int, v: int, in_anim: bool) -> int:
        key = (v, in_anim)
        hit = vmap[body].get(key)
        if hit is not None:
            return hit
        row = src.vt[v] if 0 <= v < len(src.vt) else src.vt[0]
        # a ``VT`` row is ``VT x y z nx ny nz s t``: the normal at token 4
        # rotates with the position (rule 5)
        vt_out[body].append(row if in_anim else
                            _retok(row, 1, offset_of[body], tilt_of[body], 4))
        vmap[body][key] = len(vt_out[body]) - 1
        return len(vt_out[body]) - 1

    def vline_index(body: int, v: int, in_anim: bool) -> int:
        key = (v, in_anim)
        hit = lmap[body].get(key)
        if hit is not None:
            return hit
        row = src.vline[v] if 0 <= v < len(src.vline) else src.vline[0]
        vline_out[body].append(row if in_anim else
                               _retok(row, 1, offset_of[body], tilt_of[body]))
        lmap[body][key] = len(vline_out[body]) - 1
        return len(vline_out[body]) - 1

    state: dict[str, str] = {}
    lod: str = ""

    def sync(body: int) -> None:
        """Rule 1 and rule 2: bring ``body``'s file up to the state and the
        LOD bracket standing here."""
        if written_lod[body] != lod:
            if lod:
                out[body].append(lod)
                lods_seen[body].append(lod)
                counts["lod_brackets"] += 1
            written_lod[body] = lod
            written_state[body] = {}        # a bracket restarts the state
        for g, line in state.items():
            if written_state[body].get(g) != line:
                out[body].append(line)
                written_state[body][g] = line

    def emit_tris(body: int, tris: list[tuple[int, int, int]], in_anim: bool) -> None:
        start = len(idx_out[body])
        for a, b_, c in tris:
            idx_out[body].extend((vt_index(body, a, in_anim),
                                  vt_index(body, b_, in_anim),
                                  vt_index(body, c, in_anim)))
        out[body].append(f"TRIS\t{start} {len(tris) * 3}")
        tri_count[body] += len(tris)

    i = 0
    n_cmd = len(src.commands)
    while i < n_cmd:
        ln = src.commands[i]
        t = ln.split()
        kw = t[0]
        bid_block = block_of_line.get(i)
        if bid_block is not None:
            # rule 3: the whole block, at once, to its owner
            blk = blocks[bid_block]
            owner = blk["owner"]
            if owner is None:
                owner = nearest(np.zeros(3))
            sync(owner)
            anim_count[owner] += 1
            dx, dy, dz = offset_of[owner]
            for j in blk["lines"]:
                bl = src.commands[j]
                bt = bl.split()
                if bt[0] == "TRIS" and len(bt) >= 3:
                    off, cnt = int(bt[1]), int(bt[2])
                    tris = [(int(src.idx[k]), int(src.idx[k + 1]), int(src.idx[k + 2]))
                            for k in range(off, min(off + cnt, n_idx) - 2, 3)]
                    counts["tris"] += len(tris)
                    emit_tris(owner, tris, True)
                    continue
                if bt[0] == "LINES" and len(bt) >= 3:
                    off, cnt = int(bt[1]), int(bt[2])
                    start = len(idx_out[owner])
                    got = 0
                    for k in range(off, min(off + cnt, n_idx)):
                        idx_out[owner].append(vline_index(owner, int(src.idx[k]), True))
                        got += 1
                    out[owner].append(f"LINES\t{start} {got}")
                    continue
                out[owner].append(bl)
                if bt[0] == "ANIM_begin" and j == blk["lines"][0] \
                        and (dx or dy or dz):
                    # rule 4: the block's own frame, compensated
                    out[owner].append(
                        f"ANIM_trans\t{-dx:.3f} {-dy:.3f} {-dz:.3f}\t"
                        f"{-dx:.3f} {-dy:.3f} {-dz:.3f}\t0 0\tnone")
            i = blk["lines"][-1] + 1
            continue
        if kw == "ATTR_LOD":
            lod = ln
            i += 1
            continue
        if kw.startswith("ATTR_"):
            state[_attr_group(kw)] = ln
            i += 1
            continue
        if kw == "TRIS" and len(t) >= 3:
            off, cnt = int(t[1]), int(t[2])
            per: dict[int, list[tuple[int, int, int]]] = {}
            for k in range(off, min(off + cnt, n_idx) - 2, 3):
                a, b_, c = int(src.idx[k]), int(src.idx[k + 1]), int(src.idx[k + 2])
                per.setdefault(tri_body(a, b_, c), []).append((a, b_, c))
                counts["tris"] += 1
            for body in sorted(per):
                sync(body)
                emit_tris(body, per[body], False)
            i += 1
            continue
        if kw == "LINES" and len(t) >= 3:
            off, cnt = int(t[1]), int(t[2])
            lv = _coords(src.vline, 1) if src.vline else np.zeros((0, 3))
            per_l: dict[int, list[int]] = {}
            for k in range(off, min(off + cnt, n_idx)):
                v = int(src.idx[k])
                p = lv[v] if 0 <= v < lv.shape[0] else np.zeros(3)
                per_l.setdefault(nearest(p), []).append(v)
            for body in sorted(per_l):
                sync(body)
                start = len(idx_out[body])
                for v in per_l[body]:
                    idx_out[body].append(vline_index(body, v, False))
                out[body].append(f"LINES\t{start} {len(per_l[body])}")
            i += 1
            continue
        if kw == "LIGHTS" and len(t) >= 3:
            off, cnt = int(t[1]), int(t[2])
            gv = _coords(src.vlight, 1) if src.vlight else np.zeros((0, 3))
            rows = [v for v in range(off, min(off + cnt, gv.shape[0]))]
            if rows:
                p = gv[rows].mean(axis=0)
                body = nearest(p)
                sync(body)
                start = len(vlight_out[body])
                for v in rows:
                    vlight_out[body].append(
                        _retok(src.vlight[v], 1, offset_of[body], tilt_of[body]))
                out[body].append(f"LIGHTS\t{start} {len(rows)}")
            i += 1
            continue
        if kw in _POSITIONAL:
            first = _POSITIONAL[kw]
            try:
                p = np.asarray([float(t[first]), float(t[first + 1]), float(t[first + 2])])
            except (IndexError, ValueError):
                p = np.zeros(3)
            body = nearest(p)
            sync(body)
            out[body].append(_retok(ln, first, offset_of[body], tilt_of[body]))
            i += 1
            continue
        if is_seat_owned(ln):
            # #232: a seat directive AFTER the vertex tables is the same
            # directive in the same file — ``_read`` only files it under
            # the header when it is spelled before them.  The stage owns
            # the seat wherever the authored file put it.
            counts["seat_owned_dropped"] += 1
            i += 1
            continue
        # every other command (ANIM_hide, a bare keyword, a comment) goes
        # to every body: it is state, not geometry, and dropping it would
        # change what the bodies that inherit it render
        for body in out:
            out[body].append(ln)
        i += 1

    live = [b for b in bodies if tri_count[b.body_id] or idx_out[b.body_id]
            or vlight_out[b.body_id]]
    if len(live) < 2 and not (allow_single and live):
        return SplitResult(pristine_path, (), "one_body", counts)

    rel = resource or os.path.join("objects", os.path.basename(pristine_path))
    if rel.endswith(".anchor_bak"):
        rel = rel[: -len(".anchor_bak")]
    stem = os.path.splitext(os.path.basename(rel))[0]
    # THE ONE HEADER THIS WRITER MINTS (#232).  Taken once — every body's
    # file carries the same header lines — with ``POINT_COUNTS`` dropped
    # (recomputed per body below) and the SEAT DIRECTIVES dropped because
    # the stage, not X-Plane, seats a file it writes
    # (:data:`SEAT_OWNED_DIRECTIVES`).
    _head_src = [h for j, h in enumerate(src.header) if j != src.point_counts_at]
    head = strip_seat_owned(_head_src)
    counts["seat_owned_dropped"] += len(_head_src) - len(head)
    files: list[SplitFile] = []
    for b in live:
        bid = b.body_id
        body_text: list[str] = list(head)
        body_text.append(f"POINT_COUNTS\t{len(vt_out[bid])} {len(vline_out[bid])} "
                         f"{len(vlight_out[bid])} {len(idx_out[bid])}")
        _tl = tilt_of[bid]
        body_text.append(f"# o4 split of {stem} body {k} offset "
                         f"{b.offset[0]:.3f} {b.offset[1]:.3f} {b.offset[2]:.3f}"
                         + ("" if _tl is None else
                            f" tilt {b.tilt[0]:.6f} {b.tilt[1]:.6f}"))
        body_text.append("")
        body_text.extend(vt_out[bid])
        body_text.extend(vline_out[bid])
        body_text.extend(vlight_out[bid])
        body_text.append("")
        # ``IDX10`` carries exactly ten indices and ``IDX`` exactly one —
        # a short ``IDX`` row with several is not OBJ8 and X-Plane drops
        # the object silently
        row = idx_out[bid]
        for j in range(0, len(row) - len(row) % 10, 10):
            body_text.append("IDX10\t" + " ".join(str(x) for x in row[j:j + 10]))
        for x in row[len(row) - len(row) % 10:]:
            body_text.append(f"IDX\t{x}")
        body_text.append("")
        body_text.extend(out[bid])
        body_text.append("")
        # §16d (1): THE FILE IS NAMED BY ITS BODY, never by its position
        # in the live list.  The plan spells a body's file
        # ``body_resource_name(resource, body_id)`` and the DSF row is
        # written on that name, so a body the cut left with NO triangle
        # (its geometry inside an ANIM block another body owns) used to
        # shift every later body's file one name down — the row then
        # carried the NEXT body's geometry at this body's zero.  Measured
        # at LEMD: `OldTerminal_FSX-DCNEUN`, whose ``__b0`` row held
        # ``b1``'s object 254 m from ``b0``'s own box.
        # 14at: ...and the file is keyed on the OFFSET IT BAKES beside
        # its body id, so two placements of one resource at two anchors
        # write two files instead of one that holds the first
        # placement's translation (OTHH's ``tunnel1``, 38.7 m).
        _baked = NO_TILT if _tl is None else (float(b.tilt[0]), float(b.tilt[1]))
        files.append(SplitFile(bid,
                               body_resource_name(rel, bid, b.offset, _baked),
                               "\n".join(body_text) + "\n",
                               len(vt_out[bid]), tri_count[bid], b.offset,
                               tuple(lods_seen[bid]), anim_count[bid],
                               _baked))
    return SplitResult(pristine_path, tuple(files), "", counts)
