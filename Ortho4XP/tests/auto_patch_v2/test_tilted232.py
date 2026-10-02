"""A WRITTEN OBJ8 BODY NEVER CARRIES THE SEAT (issue #232; #162, #163).

``TILTED`` makes X-Plane rotate a whole object to the terrain normal it
samples under that object's own DSF anchor, and ``SLOPE_LIMIT`` is the
band it does it in.  Before this lane the split writer replayed the
source header verbatim into every body file, so both survived into files
the stage had ALREADY seated:

* the bodies of one building stand at DIFFERENT anchors — that is what a
  split is — so each tilted to its own patch of terrain and the parts
  came apart (KASE's fire station: 6 placements cut into 14 bodies at 9
  anchors, a rigid plan at seat spread 0.000 m, 3.91 m apart at the
  owner's point);
* a body whose seat tilt 10-01k Q1 had BAKED into its vertices was then
  tilted a second time on top of the bake (KASE's shelters: 0.75 deg
  baked within tolerance, then the anchor's 1.46 % slope over it — 284 of
  292 feet floating, p50 +1.39 m, max +2.95 m).

The twins are synthetic and hermetic, on the two-box source
``test_v2objsplit`` already builds (ONE fixture builder, not a second
copy of it): a TILTED source loses both directives in every written body
and keeps every other header line in order; a source that never spelled
them is written BYTE-IDENTICALLY to the pre-fix writer; and the restore
path puts the AUTHORED header — directives and all — back over the pack,
because a file the stage does not write is the author's.
"""
from __future__ import annotations

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import obj8_split as OS
from auto_patch_v2.airport import placement_write as PW

# ONE fixture builder (CLAUDE.md's census-wrapper precedent): the boxes,
# the writer and the cuts are ``test_v2objsplit``'s own.
from test_v2objsplit import _cuts, _two_boxes  # noqa: E402

#: The directives a TILTED source spells, in the order a pack authors
#: them (X-Plane reads both from the header, before ``POINT_COUNTS``).
TILTED_LINES = ("TILTED", "SLOPE_LIMIT\t-5.0 5.0 -5.0 5.0")

#: The two body offsets the twins cut at — DIFFERENT anchors, which is
#: the whole mechanism of #163 (one building, two patches of terrain).
OFFSETS = ((1.0, 2.0, 3.0), (-5.0, 0.0, 7.0))


def _with_lines(path, lines, *, after_tables: bool = False):
    """``path``'s text with ``lines`` inserted — in the HEADER (right
    after ``TEXTURE``, where a pack authors them) or, for the awkward
    case, AFTER the vertex tables where the reader files them under the
    command stream instead."""
    rows = path.read_text(encoding="latin-1").split("\n")
    if after_tables:
        at = len(rows) - 1 if rows[-1] == "" else len(rows)
    else:
        at = next(i for i, r in enumerate(rows)
                  if r.startswith("TEXTURE")) + 1
    rows[at:at] = list(lines)
    out = path.with_name(path.stem + "_tilted" + path.suffix)
    out.write_text("\n".join(rows), encoding="latin-1", newline="")
    return out


def _header_of(text):
    """The written file's header: every line before the first vertex
    row, which is where X-Plane reads a global directive."""
    head = []
    for ln in text.split("\n"):
        kw = ln.strip().split(None, 1)[0] if ln.strip() else ""
        if kw in ("VT", "VLINE", "VLIGHT") or kw.startswith("IDX"):
            break
        head.append(ln)
    return head


# ── the rule ─────────────────────────────────────────────────────────────

def test_a_tilted_source_writes_two_bodies_that_carry_neither(tmp_path):
    """#232: two body files, and NEITHER spells ``TILTED`` or
    ``SLOPE_LIMIT`` — anywhere in the file, not just in the header."""
    p, total = _two_boxes(tmp_path)
    cuts = _cuts(p, OFFSETS)
    src = _with_lines(p, TILTED_LINES)
    assert "TILTED" in src.read_text(encoding="latin-1")

    res = OS.split_obj8(str(src), cuts, "objects/twobox.obj")
    assert res.kept_whole == "", res.kept_whole
    assert len(res.files) == 2
    for f in res.files:
        for line in f.text.split("\n"):
            assert not OS.is_seat_owned(line), (f.resource, line)
        assert "TILTED" not in f.text and "SLOPE_LIMIT" not in f.text
    # both lines of ONE source, counted once (every body loses the same two)
    assert res.counts["seat_owned_dropped"] == len(TILTED_LINES)
    # and the files still parse through the engine's own reader
    for f in res.files:
        q = tmp_path / f.resource.replace("/", "_")
        q.write_text(f.text, encoding="latin-1", newline="")
        assert obj8.parse_obj8(str(q)).solid.shape[0] == f.tris
    assert sum(f.tris for f in res.files) == total


def test_every_other_header_line_survives_in_order(tmp_path):
    """The strip is SURGICAL: the written header is the source's header
    minus exactly the seat directives (and ``POINT_COUNTS``, which the
    writer recomputes), every other line in its authored order."""
    p, _ = _two_boxes(tmp_path)
    cuts = _cuts(p, OFFSETS)
    plain = OS.split_obj8(str(p), cuts, "objects/twobox.obj")
    tilted = OS.split_obj8(str(_with_lines(p, TILTED_LINES)), cuts,
                           "objects/twobox.obj")
    for a, b in zip(plain.files, tilted.files):
        assert _header_of(a.text) == _header_of(b.text), a.resource
    # the source's own header, as authored, is what that equals
    src_head = [ln for ln in _header_of(p.read_text(encoding="latin-1"))
                if not ln.startswith("POINT_COUNTS")]
    for f in tilted.files:
        assert _header_of(f.text)[:len(src_head)] == src_head, f.resource


def test_a_source_without_the_directives_is_byte_identical_to_today(tmp_path):
    """The fix is a NO-OP on every object that never spelled them: the
    written bytes are the pre-fix writer's, exactly."""
    p, _ = _two_boxes(tmp_path)
    cuts = _cuts(p, OFFSETS)
    res = OS.split_obj8(str(p), cuts, "objects/twobox.obj")
    assert res.counts["seat_owned_dropped"] == 0
    # the pre-fix writer IS this one with the strip removed, so on a
    # source it would not have changed, the strip changes nothing
    for f in res.files:
        head = _header_of(f.text)
        assert OS.strip_seat_owned(head) == head, f.resource
    # ... and the names, which key the pack's files, do not move either
    assert [f.resource for f in res.files] == [
        OS.body_resource_name("objects/twobox.obj", 0, OFFSETS[0]),
        OS.body_resource_name("objects/twobox.obj", 1, OFFSETS[1])]


def test_a_directive_after_the_vertex_tables_goes_too(tmp_path):
    """``_read`` files a line after the tables under the COMMAND stream,
    whose catch-all replays it into EVERY body.  It is the same directive
    in the same file, so it goes the same way."""
    p, _ = _two_boxes(tmp_path)
    cuts = _cuts(p, OFFSETS)
    res = OS.split_obj8(str(_with_lines(p, TILTED_LINES, after_tables=True)),
                        cuts, "objects/twobox.obj")
    assert len(res.files) == 2
    for f in res.files:
        assert "TILTED" not in f.text and "SLOPE_LIMIT" not in f.text
    assert res.counts["seat_owned_dropped"] == len(TILTED_LINES)


# ── the kept-whole reading (REPORTED, not decided) ───────────────────────

def test_the_kept_whole_reader_names_the_directives_it_finds(tmp_path):
    """#232's own open question: a placement kept WHOLE is not written,
    so its authored directives stand.  They are CENSUSED, in the order
    the file spells them, for the owner to rule on."""
    p, _ = _two_boxes(tmp_path)
    assert OS.seat_owned_in_file(str(p)) == ()
    src = _with_lines(p, TILTED_LINES)
    assert OS.seat_owned_in_file(str(src)) == ("TILTED", "SLOPE_LIMIT")
    # a file that does not exist is a census miss, never a refusal
    assert OS.seat_owned_in_file(str(tmp_path / "nope.obj")) == ()
    # and the word AFTER the vertex table is not a header directive
    body = tmp_path / "body.obj"
    body.write_text(p.read_text(encoding="latin-1") + "\nTILTED\n",
                    encoding="latin-1", newline="")
    assert OS.seat_owned_in_file(str(body)) == ()


# ── the restore (a file the stage does not write is the author's) ────────

def test_the_restore_puts_the_authored_header_back(tmp_path):
    """11f (1): ``<obj>.anchor_bak`` is a BYTE copy back over the pack.
    The authored header — ``TILTED`` and all — is what it restores: the
    strip is this WRITER's act on a file it mints, never an edit of the
    user's own object."""
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    live = pack / "objects" / "a.obj"
    # §12a's y-only WITNESS, as ``test_v2objsplit`` spells it: the live
    # file is v1's bake of the backup — the same bytes but for one VT y.
    head = "I\n800\nOBJ\nTEXTURE\tt.dds\nTILTED\nSLOPE_LIMIT\t-5 5 -5 5\n"
    authored = head + "VT\t0 0.0 0\t0 1 0\t0 0\n"
    live.write_text(head + "VT\t0 -7.5 0\t0 1 0\t0 0\n",
                    encoding="latin-1", newline="")        # v1's stale bake
    (pack / "objects" / "a.obj.anchor_bak").write_text(
        authored, encoding="latin-1", newline="")
    res = PW.restore_pack_objects(str(pack))
    assert str(live) in res.restored, res
    assert live.read_text(encoding="latin-1") == authored
    assert OS.seat_owned_in_file(str(live)) == ("TILTED", "SLOPE_LIMIT")
