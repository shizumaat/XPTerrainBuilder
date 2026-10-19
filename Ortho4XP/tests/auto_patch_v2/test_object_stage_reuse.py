"""issue #879 — THE OBJECT STAGE AFTER THE MESH REUSES AN AIRPORT'S WORK
WHEN NOTHING IT READS HAS CHANGED (``airport/object_stage_reuse``).

Synthetic twins, no corpus: a stand-in placement that reads a pack OBJ and
the graded surface and writes a body file (temp + ``os.replace``) and a
"DSF" — the shape of ``object_stage._place_objects``'s reads and writes.

* unchanged inputs: served, the pack byte-identical to a fresh run's;
* every key input changed: the airport runs and names that input;
* the mesh, a read file or an output changed after the record: runs;
* the switch off: runs, no record;
* a sibling airport's later write in the same stage is re-witnessed.
"""
from __future__ import annotations

import os
import types

import pytest

from auto_patch_v2.airport import file_witness as FW
from auto_patch_v2.airport import object_stage_reuse as R
from auto_patch_v2.airport import stage_cache as SC


class _World:
    def __init__(self, root):
        self.root = root
        self.pack = root / "pack"
        (self.pack / "objects").mkdir(parents=True)
        self.cache = root / "cache" / "pack"
        self.cache.mkdir(parents=True)
        self.mesh = root / "tile.mesh"
        self.obj = self.pack / "objects" / "hangar.obj"
        self.graded = root / "graded.json"
        self.dsf = self.pack / "tile.dsf"
        self.pristine = self.pack / "tile.dsf.anchor_bak"
        self.extra = self.pack / "library.txt"      # read, not keyed
        for path, text in ((self.mesh, "mesh 1"), (self.obj, "OBJ 1"),
                           (self.graded, "graded 1"), (self.pristine, "DSF 0"),
                           (self.extra, "lib 1")):
            path.write_text(text, encoding="utf-8", newline="\n")
        self.calls = 0
        self.said: list[str] = []
        self.plan = {"icao": "XAAA", "units": [1, 2]}
        self.params = {"write_enabled": True, "measure_only": False}

    def place(self, tag="XAAA"):
        """The stand-in placement: deterministic in what it reads."""
        self.calls += 1
        src = "".join(p.read_text(encoding="utf-8") for p in (
            self.obj, self.graded, self.pristine, self.extra))
        body = self.pack / "objects" / f"{tag}_b0.obj"
        with open(str(body) + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("body of " + src)
        os.replace(str(body) + ".tmp", body)
        with open(self.dsf, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"DSF with {src}, last written for {tag}")
        return {"bodies": 1, "packs_written": 1}

    def stage(self, *, on=True, airports=("XAAA",)):
        reuse = R.StageReuse("+10+020", str(self.mesh), code="c" * 64,
                             env={"python": "3"}, cache_root=str(self.cache.parent),
                             on=on, say=self.said.append)
        out = []
        for icao in airports:
            recipe = reuse.recipe(dict(self.plan, icao=icao), graded_path=str(self.graded),
                                  pristine_path=str(self.pristine), objects=[str(self.obj)],
                                  params=self.params)
            out.append(reuse.run(icao, str(self.cache), recipe,
                                 lambda icao=icao: self.place(icao)))
        reuse.finish()
        return out

    def pack_bytes(self):
        return {p.name: p.read_bytes() for p in self.pack.rglob("*") if p.is_file()}

    def last(self):
        return self.said[-1]


@pytest.fixture
def world(tmp_path):
    return _World(tmp_path)


def test_unchanged_inputs_are_served_and_equal_a_fresh_run(world, tmp_path):
    first = world.stage()
    assert world.calls == 1 and "ran: no record" in world.last()
    after_first = world.pack_bytes()
    second = world.stage()
    assert world.calls == 1, "the second stage must be served"
    assert "object stage reused" in world.last()
    assert second == first
    assert world.pack_bytes() == after_first
    fresh = world.stage(on=False)                    # a fresh run, reuse off
    assert world.calls == 2 and "reuse off" in world.last()
    assert fresh == second and world.pack_bytes() == after_first


@pytest.mark.parametrize("change, named", [
    (lambda w: w.plan.update(units=[1, 2, 3]), "plan"),
    (lambda w: w.mesh.write_text("mesh 2", encoding="utf-8", newline="\n"), "mesh"),
    (lambda w: w.graded.write_text("graded 2", encoding="utf-8", newline="\n"), "graded"),
    (lambda w: w.pristine.write_text("DSF 9", encoding="utf-8", newline="\n"),
     "pristine_dsf"),
    (lambda w: w.obj.write_text("OBJ 2", encoding="utf-8", newline="\n"), "objects"),
    (lambda w: w.params.update(measure_only=True), "params.measure_only"),
])
def test_each_key_input_changed_reruns_and_is_named(world, change, named):
    world.stage()
    change(world)
    world.stage()
    assert world.calls == 2
    assert f"ran: {named} " in world.last()
    world.stage()                                    # and the new record holds
    assert world.calls == 2


def test_the_code_and_the_environment_are_in_the_key(world):
    world.stage()
    reuse = R.StageReuse("+10+020", str(world.mesh), code="d" * 64, env={"python": "3"},
                         say=world.said.append)
    recipe = reuse.recipe(world.plan, graded_path=str(world.graded),
                          pristine_path=str(world.pristine), objects=[str(world.obj)],
                          params=world.params)
    reuse.run("XAAA", str(world.cache), recipe, world.place)
    assert world.calls == 2 and "ran: code " in world.last()
    reuse = R.StageReuse("+10+020", str(world.mesh), code="c" * 64, env={"python": "4"},
                         say=world.said.append)
    recipe["env"] = reuse.env
    recipe["code"] = "c" * 64
    reuse.run("XAAA", str(world.cache), recipe, world.place)
    assert world.calls == 3 and "ran: env " in world.last()


def test_a_read_file_or_an_output_changed_after_the_record_refuses_it(world):
    world.stage()
    # read, never keyed
    world.extra.write_text("lib 2", encoding="utf-8", newline="\n")
    world.stage()
    assert world.calls == 2 and f"ran: file:{world.extra}" in world.last()
    # an output
    world.dsf.write_text("the user's own DSF", encoding="utf-8", newline="\n")
    world.stage()
    assert world.calls == 3 and f"ran: output:{world.dsf}" in world.last()
    world.stage()
    assert world.calls == 3


def test_a_record_names_another_key_or_is_torn_is_refused(world):
    world.stage()
    (rec,) = list(world.cache.glob("o4_stage_XAAA_objects+10+020_*.cache"))
    rec.write_bytes(rec.read_bytes()[:-3])           # torn payload
    world.stage()
    assert world.calls == 2 and "record refused" in world.last()
    assert len(list(world.cache.glob("o4_stage_XAAA_*.cache"))) == 1


def test_the_switch_off_runs_and_writes_no_record(world, monkeypatch):
    from auto_patch import object_stage as STAGE
    monkeypatch.delenv(R.ENV_SWITCH, raising=False)
    assert STAGE.reuse_enabled()
    monkeypatch.setenv(R.ENV_SWITCH, "0")
    assert not STAGE.reuse_enabled()
    tile = types.SimpleNamespace(lat=10, lon=20, build_dir=str(world.root))
    reuse = STAGE._stage_reuse(tile, str(world.mesh))
    assert reuse is not None and not reuse.on
    world.stage(on=STAGE.reuse_enabled())
    world.stage(on=STAGE.reuse_enabled())
    assert world.calls == 2
    assert not list(world.cache.glob("o4_stage_*"))


def test_no_code_digest_never_reuses(world):
    reuse = R.StageReuse("+10+020", str(world.mesh), code=None, env={},
                         say=world.said.append)
    recipe = reuse.recipe(world.plan, graded_path=str(world.graded),
                          pristine_path=str(world.pristine), objects=[], params={})
    reuse.run("XAAA", str(world.cache), recipe, world.place)
    assert reuse.finish() == 0 and "no code digest" in world.last()


def test_a_sibling_rewriting_the_shared_dsf_later_is_rewitnessed(world):
    """#25's composition: two airports, one pack DSF.  The second's write
    changes the first's output; both are served next time."""
    world.stage(airports=("XAAA", "XBBB"))
    assert world.calls == 2
    assert world.dsf.read_text(encoding="utf-8").endswith("for XBBB")
    world.stage(airports=("XAAA", "XBBB"))
    assert world.calls == 2, world.said


def test_the_recorder_keeps_what_was_written(tmp_path):
    rec = FW.FileRecorder(writes=True)
    out = tmp_path / "out.txt"
    src = tmp_path / "in.txt"
    src.write_text("x", encoding="utf-8", newline="\n")
    rec.recording(True)
    try:
        src.read_text(encoding="utf-8")
        with open(str(out) + ".tmp", "w", encoding="utf-8", newline="\n") as fh:
            fh.write("y")
        os.replace(str(out) + ".tmp", out)
        (tmp_path / "o4_stage_own.cache").write_text("z", encoding="utf-8", newline="\n")
    finally:
        rec.recording(False)
    assert rec.written() == [os.path.abspath(out)]
    assert os.path.abspath(src) in rec.record()
    assert FW.FileRecorder().written() == []


def test_records_use_the_stage_cache_store(world):
    world.stage()
    (rec,) = list(world.cache.glob("o4_stage_*.cache"))
    head = SC.read_header(str(rec))
    assert head["stage"] == "objects+10+020" and head["version"] == SC.CACHE_VERSION
    assert set(head["recipe"]["inputs"]) == set(R.INPUTS)
