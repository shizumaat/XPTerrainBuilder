"""Hand-set pavement roles (capability "patch_roles", #1697): ``patch_role_set``
stores a user edit beside the patch keyed by the pavement's ring identity,
the loader resolves it, and the classifier gives every pavement cell of
that pavement the hand-set role on every rebuild."""
from __future__ import annotations

import dataclasses as dc
import json
import os
from types import SimpleNamespace as NS

import O4_File_Names as FNAMES
import pytest
from auto_patch_v2.airport import user_roles as UR
from o4_engine import patch_roles as PR

TILE = "+45-123"
RING = ((-122.9, 45.1), (-122.8, 45.1), (-122.8, 45.2), (-122.9, 45.2))


def _identity(icao, lat, lon, source):
    if source.startswith("dsf:"):
        return "", "sig-a", ""
    return UR.ring_key(RING, 11), "", "Apron 3"


def test_ring_key_is_start_and_winding_free_and_canonical():
    k = UR.ring_key(RING, 11)
    assert UR.ring_key(RING[2:] + RING[:2], 11) == k
    assert UR.ring_key(tuple(reversed(RING)), 11) == k
    # a move below the 11th place is the same vertex; one above is not
    assert UR.ring_key(((-122.9 + 1e-13, 45.1),) + RING[1:], 11) == k
    assert UR.ring_key(((-122.9 + 1e-9, 45.1),) + RING[1:], 11) != k


def test_source_of_names_only_pack_pavements():
    assert UR.source_of("pav131") == "pav131"
    assert UR.source_of("pav54#2") == "pav54"
    assert UR.source_of("pav54#plateau:building70") == "pav54"
    assert UR.source_of("dsf:pol267") == "dsf:pol267"
    assert UR.source_of("dsf:objpav3#1") == "dsf:objpav3"
    for ref in ("adjacent_ground", "route8", "building3", "", None, "xpav1", "dsf:fac2",
                "dsf:agp1"):
        assert UR.source_of(ref) is None


def test_resolve_honours_only_the_same_ring():
    pavs = [NS(index=7, rings=(RING,)), NS(index=8, rings=(RING[:3],))]
    rows = [UR.RoleOverride("pav7", UR.ring_key(RING, 11), "apron"),
            UR.RoleOverride("pav8", UR.ring_key(RING, 11), "apron"),     # pack changed
            UR.RoleOverride("pav9", "x", "apron")]                       # gone
    taken, refused = UR.resolve(rows, pavs, 11)
    assert taken == (("pav7", "apron"),)
    assert len(refused) == 2 and all("pack has changed" in r for r in refused)


def test_a_dsf_pavement_is_held_by_its_pack():
    rows = [UR.RoleOverride("dsf:pol267", "", "primary_parallel", pack="sig-a"),
            UR.RoleOverride("dsf:pol268", "", "apron", pack="sig-old"),
            UR.RoleOverride("pav7", UR.ring_key(RING, 11), "apron", pack="sig-old")]
    asked = []
    kept, dropped = UR.for_pack(rows, lambda: asked.append(1) or "sig-a")
    assert [o.source for o in kept] == ["dsf:pol267", "pav7"]    # a ring outlives the pack
    assert len(dropped) == 1 and "dsf:pol268" in dropped[0] and asked == [1]
    assert UR.for_pack(rows[2:], lambda: 1 / 0) == (tuple(rows[2:]), ())   # never asked
    taken, refused = UR.resolve(kept, [NS(index=7, rings=(RING,))], 11,
                                {"pav7", "dsf:pol267"})
    assert taken == (("dsf:pol267", "primary_parallel"), ("pav7", "apron")) and not refused
    taken, refused = UR.resolve(kept[:1], [], 11, {"dsf:pol1"})
    assert taken == () and len(refused) == 1


@dc.dataclass(frozen=True)
class _Cell:
    ref: str
    role: str
    side: str = "airside"
    evidence: dict = dc.field(default_factory=dict)


def test_apply_changes_pavement_cells_of_the_source_only():
    cells = [_Cell("pav7", "junction"), _Cell("pav7#1", "stub"), _Cell("pav7", "runway"),
             _Cell("pav8", "junction"), _Cell("adjacent_ground", "graded_strip")]
    out, n = UR.apply(cells, (("pav7", "parking_lot"),), lambda r: "groundside")
    assert n == 2
    assert [c.role for c in out] == ["parking_lot", "parking_lot", "runway", "junction",
                                     "graded_strip"]
    assert out[0].side == "groundside" and out[0].evidence["classified_as"] == "junction"


def test_set_read_clear_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    monkeypatch.setattr(PR, "_identity", _identity)
    r = PR.patch_role_set(TILE, "zzzz", "pav7#2", "parking_lot", was="junction")
    assert r == {"source": "pav7", "role": "parking_lot", "previous_role": None,
                 "description": "Apron 3", "path": "o4_user_roles_ZZZZ.json"}
    path = UR.roles_path(PR._patch_dir(TILE)[0], "ZZZZ")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert doc["roles"][0]["ring"] == UR.ring_key(RING, 11)
    assert doc["roles"][0]["was"] == "junction"
    # a second change keeps the classifier's verdict as the evidence
    r = PR.patch_role_set(TILE, "ZZZZ", "pav7", "apron", was="parking_lot")
    assert r["previous_role"] == "parking_lot"
    assert UR.read(PR._patch_dir(TILE)[0], "ZZZZ")["pav7"].was == "junction"
    listed = PR.patch_roles(TILE, "ZZZZ")
    assert [o["role"] for o in listed["overrides"]] == ["apron"]
    assert "ring" not in listed["overrides"][0]
    assert {c["role"] for c in listed["choices"]} == {r for r, _ in UR.CHOOSABLE}
    # clearing (the Undo of the first set) removes the file
    r = PR.patch_role_set(TILE, "ZZZZ", "pav7", None)
    assert r["previous_role"] == "apron" and not os.path.exists(path)
    # a DSF pavement is keyed by the pack's signature
    PR.patch_role_set(TILE, "ZZZZ", "dsf:pol267#3", "primary_parallel", was="apron")
    row = UR.read(PR._patch_dir(TILE)[0], "ZZZZ")["dsf:pol267"]
    assert (row.ring, row.pack, row.was) == ("", "sig-a", "apron")


def test_patch_role_set_refuses_what_is_not_a_pack_pavement(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    with pytest.raises(ValueError, match="not one of the pack's pavements"):
        PR.patch_role_set(TILE, "ZZZZ", "adjacent_ground", "apron")
    with pytest.raises(ValueError, match="not a pavement role"):
        PR.patch_role_set(TILE, "ZZZZ", "pav7", "runway")


def test_every_choosable_role_is_registered():
    from auto_patch_v2.law import Law
    roles = Law.for_airport("SYNT").tables.precedence.roles
    assert all(r in roles for r, _label in UR.CHOOSABLE)


def _evidence(tmp_path) -> list[dict]:
    with open(tmp_path / UR.EVIDENCE_FILENAME, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def test_every_change_is_a_line_of_classifier_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    monkeypatch.setattr(PR, "_identity", _identity)
    PR.patch_role_set(TILE, "ZZZZ", "pav7", "primary_parallel", was="apron")
    PR.patch_role_set(TILE, "ZZZZ", "pav7", None)
    lines = _evidence(tmp_path)
    assert [(ln["action"], ln["role"], ln["classified_as"]) for ln in lines] == [
        ("set", "primary_parallel", "apron"), ("cleared", None, "apron")]
    assert lines[0]["ring"] == UR.ring_key(RING, 11) and lines[0]["icao"] == "ZZZZ"


def test_digest_names_what_the_solve_reads(tmp_path):
    d = str(tmp_path)
    assert UR.digest(d, "ZZZZ") == "none"
    row = UR.RoleOverride("pav7", "r", "apron", was="junction", set_at="t1")
    UR.set_role(d, "ZZZZ", row, source="pav7")
    one = UR.digest(d, "ZZZZ")
    UR.set_role(d, "ZZZZ", dc.replace(row, set_at="t2", description="x"), source="pav7")
    assert UR.digest(d, "ZZZZ") == one != "none"        # when/why is not an input
    UR.set_role(d, "ZZZZ", dc.replace(row, role="stub"), source="pav7")
    assert UR.digest(d, "ZZZZ") != one
    with open(UR.roles_path(d, "ZZZZ"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{"version": 99}')
    assert UR.digest(d, "ZZZZ") == "unreadable"


def test_a_role_change_makes_the_patch_stale(tmp_path, monkeypatch):
    from auto_patch import provenance as P
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path))
    tile = NS(lat=45, lon=-123)
    assert "o4_user_roles" in P.FRESHNESS_COMPARED_KEYS
    before = P.user_roles_identity(tile, "ZZZZ")
    UR.set_role(FNAMES.patch_dir(45, -123), "ZZZZ", UR.RoleOverride("pav7", "r", "apron"),
                source="pav7")
    after = P.user_roles_identity(tile, "ZZZZ")
    assert before == "none" != after
    assert P.freshness_mismatches({"o4_user_roles": before}, {"o4_user_roles": after}) \
        .count("o4_user_roles") == 1
    assert P.user_roles_identity(None, "ZZZZ") == "none"


def test_library_rows_are_laid_only_where_the_user_has_none(tmp_path):
    d = str(tmp_path)
    rows = [UR.RoleOverride("pav7", "r", "apron", was="junction").to_dict(),
            {"source": "pav8", "ring": "r", "role": "runway"}]          # not choosable
    assert UR.lay_rows(d, "ZZZZ", rows) == 1
    assert set(UR.read(d, "ZZZZ")) == {"pav7"}
    assert UR.lay_rows(d, "ZZZZ", [dict(rows[0], role="stub")]) == 0  # the user's stay
    assert UR.read(d, "ZZZZ")["pav7"].role == "apron"
