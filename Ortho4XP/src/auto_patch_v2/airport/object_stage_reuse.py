"""THE OBJECT STAGE'S REUSE (issue #879): one airport's placement after the
mesh is served from its record when nothing it reads has changed.

ONE RECORD PER AIRPORT AND TILE in the pack's mod-cache folder, in the v2
stage cache's store (``airport/stage_cache``: temp + ``os.replace``, a
record that does not parse or names another key is REFUSED, never
repaired).  The KEY (:meth:`StageReuse.recipe`) is:

* ``plan``         the airport's rebake plan, as the stage holds it;
* ``mesh``         the WHOLE tile mesh's sha256.  The stage samples the
                   mesh inside the plan's bounds, but #660 measured a
                   graded face regrouping bodies 800 m away, so the read
                   set is not narrowed here (a follow-up gated on the
                   corpus measurement);
* ``graded``       the graded surface beside the patch;
* ``pristine_dsf`` the pack DSF the placement starts from;
* ``objects``      the pack OBJ sources the plan names;
* ``params``       the write mode, the art omission, the law tables and
                   the engine version;
* ``code``         the stage's import closure (``object_stage_code``);
* ``env``          the interpreter and geometry libraries (``xplat``).

THE WITNESS, checked before a record is served: every file the stage
opened for reading (``file_witness.FileRecorder``) and every file it
WROTE re-hash to the sha256 the record holds.  The digests are taken when
the whole stage is over (:meth:`StageReuse.finish`), so an airport whose
pack DSF a sibling airport rewrote later in the same stage (#25's
composition) holds what the stage left on disk.  A pack file the user, a
stopped build's restore or another tool changed is a re-run, never a
wrong hit.

The switch is ``O4_OBJECT_STAGE_REUSE`` (``0`` = off; a run-environment
variable, ``provenance_env``).  Every airport says ``reused`` or ``ran:
<the first input that differs>`` with its wall time.
"""
from __future__ import annotations

import glob
import os
import time
import typing as _t

from . import file_witness as _fw
from . import stage_cache as _sc
from .file_hash import sha256_file_or_none

__all__ = ["ENV_SWITCH", "INPUTS", "enabled", "StageReuse"]

#: ``0`` turns the reuse off (every airport runs, no record is written).
ENV_SWITCH = "O4_OBJECT_STAGE_REUSE"

#: The key's inputs, in the order a miss names the first that differs.
INPUTS: tuple[str, ...] = ("plan", "mesh", "graded", "pristine_dsf",
                           "objects", "params")


def enabled(env: _t.Mapping[str, str] | None = None) -> bool:
    """Whether the reuse is on (default on)."""
    env = os.environ if env is None else env
    return str(env.get(ENV_SWITCH, "1")).strip() != "0"


class _Entry(_t.NamedTuple):
    icao: str
    path: str
    key: str
    recipe: dict
    payload: _t.Any
    reads: tuple[str, ...]
    outputs: tuple[str, ...]
    stored: "dict | None"          # the witness served (a reuse), else None


class StageReuse:
    """The object stage's records for ONE tile's stage run."""

    def __init__(self, tile_name: str, mesh_path: str, *, code: str | None,
                 env: _t.Any, exclude_dirs: _t.Sequence[str] = (),
                 cache_root: str | None = None, on: bool | None = None,
                 say: _t.Callable[..., _t.Any] | None = None) -> None:
        self.stage = "objects" + tile_name
        self.mesh_path = os.path.abspath(mesh_path)
        self.code = code
        self.env = _sc.canonical_digest(env)
        self.on = enabled() if on is None else bool(on)
        self.cache_root = cache_root
        self._exclude = tuple(os.path.abspath(d) + os.sep for d in exclude_dirs)
        self._say = say or (lambda *a: None)
        self._mesh: str | None = None
        self._memo: dict[tuple, str | None] = {}
        self._entries: list[_Entry] = []
        self.reused = self.ran = 0

    # ── digests ─────────────────────────────────────────────────────────
    def digest(self, path: str) -> str | None:
        """sha256 of the file at ``path`` (``None`` when unreadable),
        memoised on its stat."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        stamp = (path, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino)
        if stamp not in self._memo:
            self._memo[stamp] = sha256_file_or_none(path)
        return self._memo[stamp]

    def mesh_digest(self) -> str | None:
        if self._mesh is None:
            self._mesh = self.digest(self.mesh_path)
        return self._mesh

    def recipe(self, plan_doc: _t.Any, *, graded_path: str, pristine_path: str,
               objects: _t.Iterable[str], params: _t.Mapping[str, _t.Any]) -> dict:
        """The key's recipe for one airport (module doc)."""
        return {"inputs": {
            "plan": _sc.canonical_digest(plan_doc),
            "mesh": self.mesh_digest(),
            "graded": self.digest(graded_path),
            "pristine_dsf": self.digest(pristine_path),
            "objects": _sc.canonical_digest(
                sorted((p, self.digest(p)) for p in set(objects))),
            "params": dict(params),
        }, "code": self.code, "env": self.env}

    # ── the run ─────────────────────────────────────────────────────────
    def run(self, icao: str, folder: str, recipe: dict,
            compute: _t.Callable[[], _t.Any]) -> _t.Any:
        """``compute()``'s result for ``icao``, or its record's when that
        holds; says which, and how long it took."""
        t0 = time.monotonic()
        key = _sc.key_of(self.stage, recipe)
        path = _sc.entry_path(folder, icao, self.stage, key)
        if not self.on:
            reason = f"reuse off ({ENV_SWITCH}=0)"
        elif not self.code:
            reason = "no code digest"
        else:
            served, reason = self._serve(path, key, folder, icao, recipe)
            if reason is None:
                payload, stored = served
                self._entries.append(_Entry(icao, path, key, recipe, payload,
                                            tuple(stored["reads"]),
                                            tuple(stored["outputs"]), stored))
                self.reused += 1
                self._say(f"  [v2 rebake] {icao}: object stage reused "
                          f"({time.monotonic() - t0:.1f} s)")
                return payload
        rec = _fw.FileRecorder(writes=True)
        rec.recording(True)
        try:
            payload = compute()
        finally:
            rec.recording(False)
        self.ran += 1
        if self.on and self.code:
            reads = tuple(p for p in rec.record() if self._kept(p))
            outputs = tuple(p for p in rec.written() if self._kept(p))
            self._entries.append(_Entry(icao, path, key, recipe, payload,
                                        reads, outputs, None))
        self._say(f"  [v2 rebake] {icao}: object stage ran: {reason} "
                  f"({time.monotonic() - t0:.1f} s)")
        return payload

    def _kept(self, path: str) -> bool:
        return path != self.mesh_path and not path.startswith(self._exclude)

    def _serve(self, path: str, key: str, folder: str, icao: str,
               recipe: dict) -> tuple[_t.Any, str | None]:
        try:
            _head, wit, load = _sc.read(path, key)
        except FileNotFoundError:
            return None, self._first_difference(folder, icao, recipe)
        except (_sc.Refused, OSError, ValueError) as exc:
            return None, f"record refused ({exc})"
        if not (isinstance(wit, dict) and wit.get("mesh") == self.mesh_digest()
                and isinstance(wit.get("reads"), dict)
                and isinstance(wit.get("outputs"), dict)):
            return None, "record refused (witness)"
        for kind, name in (("outputs", "output"), ("reads", "file")):
            for p, sha in wit[kind].items():
                if self.digest(p) != sha:
                    return None, f"{name}:{p}"
        try:
            return (load(), wit), None
        except Exception as exc:                     # a Refused payload too
            return None, f"record refused ({exc})"

    def _records(self, folder: str, icao: str) -> list[str]:
        """Every record of ``icao``'s stage on this tile in ``folder``."""
        name = os.path.basename(_sc.entry_path(folder, icao, self.stage, ""))
        return glob.glob(os.path.join(glob.escape(folder),
                                      glob.escape(name[:-len(".cache")]) + "*.cache"))

    def _first_difference(self, folder: str, icao: str, recipe: dict) -> str:
        """The first key input that differs from the airport's last record."""
        heads = [(os.path.getmtime(p), _sc.read_header(p))
                 for p in self._records(folder, icao)]
        heads = [h for _m, h in sorted(heads, key=lambda t: t[0]) if h]
        if not heads:
            return "no record"
        prev = heads[-1].get("recipe") or {}
        before, now = prev.get("inputs") or {}, recipe["inputs"]
        for name in INPUTS:
            if name == "params" and before.get(name) != now[name]:
                diff = sorted(k for k in set(now[name]) | set(before.get(name) or {})
                              if now[name].get(k) != (before.get(name) or {}).get(k))
                return "params." + (diff[0] if diff else "?")
            if before.get(name) != now[name]:
                return name
        for name in ("code", "env"):
            if prev.get(name) != recipe[name]:
                return name
        return "record refused (key)"

    # ── the records ─────────────────────────────────────────────────────
    def finish(self) -> int:
        """Write the record of every airport that ran, and re-witness every
        airport served, against what the whole stage left on disk.
        Returns how many records were written.  Never raises."""
        self._memo.clear()
        written = 0
        for e in self._entries:
            try:
                written += self._store(e)
            except Exception:
                continue
        self._entries.clear()
        if written and self.cache_root:
            _sc.sweep(self.cache_root)
        return written

    def _store(self, e: _Entry) -> int:
        reads = {p: d for p in e.reads if (d := self.digest(p)) is not None}
        outputs = {p: d for p in e.outputs if (d := self.digest(p)) is not None}
        wit = {"mesh": self.mesh_digest(), "reads": reads, "outputs": outputs}
        if e.stored is not None and wit == e.stored:
            return 0
        blob, out_digest = _sc.encode(e.payload)
        header = {"stage": self.stage, "key": e.key, "recipe": e.recipe,
                  "version": _sc.CACHE_VERSION, "output_digest": out_digest,
                  "created": time.time(), "bytes": len(blob)}
        if not _sc.write(e.path, header, wit, blob):
            return 0
        for old in self._records(os.path.dirname(e.path), e.icao):
            if os.path.abspath(old) != os.path.abspath(e.path):
                try:
                    os.remove(old)
                except OSError:
                    pass
        return 1
