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
import os
import typing as _t

import numpy as np

from . import obj8 as _obj8

__all__ = ["BodyCut", "SplitFile", "SplitResult", "split_obj8",
           "body_resource_name", "offset_tag"]

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


@_dc.dataclass(frozen=True)
class SplitResult:
    source: str
    files: tuple[SplitFile, ...]
    kept_whole: str
    counts: _t.Mapping[str, int]


def offset_tag(offset: _t.Sequence[float]) -> str:
    """THE BAKED OFFSET, AS EIGHT HEX CHARACTERS (RULINGS 2026-09-14at).

    The tag is a pure function of the three doubles the cut SUBTRACTS
    from every vertex it keeps — ``blake2s`` over their IEEE-754 bytes —
    and of nothing else.  That is the whole reason it is a hash and not
    "the index of this offset among the resource's distinct offsets":
    an index is a function of the POPULATION, so adding or removing an
    unrelated placement of the same resource renames another
    placement's file, and the previous write's own body files (the ones
    ``o4_placement_provenance.json`` names) then go stale in the pack.
    The hash renames a file only when the file's own contents move.
    """
    import hashlib
    import struct
    x, y, z = (float(v) for v in offset)
    return hashlib.blake2s(struct.pack("<3d", x, y, z),
                           digest_size=4).hexdigest()


def body_resource_name(resource: str, k: int,
                       offset: "_t.Sequence[float] | None" = None) -> str:
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
    return f"{stem}__b{k}_{offset_tag(offset)}.obj"


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


def _retok(line: str, first: int, delta: tuple[float, float, float]) -> str:
    """``line`` with its three coordinate tokens at ``first`` shifted by
    ``-delta``, printed to the millimetre (the authored files' own
    precision)."""
    t = line.split()
    try:
        for j in range(3):
            t[first + j] = f"{float(t[first + j]) - delta[j]:.3f}"
    except (IndexError, ValueError):
        return line
    return "\t".join(t)


# ── the cut ──────────────────────────────────────────────────────────────

def split_obj8(pristine_path: str, bodies: _t.Sequence[BodyCut],
               resource: str = "", *, allow_single: bool = False) -> SplitResult:
    """Cut ``pristine_path`` into one file per body (module doc).  Reads
    the file and returns text; writes nothing.  ``resource`` is the
    pack-relative spelling the new names are derived from (defaults to
    the file's own basename under ``objects/``)."""
    counts: dict[str, int] = {"bodies": len(bodies), "tris": 0, "assigned": 0,
                              "nearest": 0, "anim_blocks": 0, "lod_brackets": 0}
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

    def vt_index(body: int, v: int, in_anim: bool) -> int:
        key = (v, in_anim)
        hit = vmap[body].get(key)
        if hit is not None:
            return hit
        row = src.vt[v] if 0 <= v < len(src.vt) else src.vt[0]
        vt_out[body].append(row if in_anim else _retok(row, 1, offset_of[body]))
        vmap[body][key] = len(vt_out[body]) - 1
        return len(vt_out[body]) - 1

    def vline_index(body: int, v: int, in_anim: bool) -> int:
        key = (v, in_anim)
        hit = lmap[body].get(key)
        if hit is not None:
            return hit
        row = src.vline[v] if 0 <= v < len(src.vline) else src.vline[0]
        vline_out[body].append(row if in_anim else _retok(row, 1, offset_of[body]))
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
                    vlight_out[body].append(_retok(src.vlight[v], 1, offset_of[body]))
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
            out[body].append(_retok(ln, first, offset_of[body]))
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
    files: list[SplitFile] = []
    for b in live:
        bid = b.body_id
        head = [h for j, h in enumerate(src.header) if j != src.point_counts_at]
        body_text: list[str] = list(head)
        body_text.append(f"POINT_COUNTS\t{len(vt_out[bid])} {len(vline_out[bid])} "
                         f"{len(vlight_out[bid])} {len(idx_out[bid])}")
        body_text.append(f"# o4 split of {stem} body {k} offset "
                         f"{b.offset[0]:.3f} {b.offset[1]:.3f} {b.offset[2]:.3f}")
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
        files.append(SplitFile(bid, body_resource_name(rel, bid, b.offset),
                               "\n".join(body_text) + "\n",
                               len(vt_out[bid]), tri_count[bid], b.offset,
                               tuple(lods_seen[bid]), anim_count[bid]))
    return SplitResult(pristine_path, tuple(files), "", counts)
