"""A memo that lives only while a scope is open (shared by the per-stage
memos: ``airport.obj8_memo``, ``solve.assembly_memo``).

``memo`` is the open scope's dict, or ``None`` outside any scope (callers
then compute every time).  A nested scope shares the outer one's memo."""

from __future__ import annotations

import contextlib
import functools
import typing as _t

__all__ = ["MemoScope"]


class MemoScope:
    """One module's scoped memo."""

    def __init__(self) -> None:
        self.memo: "dict | None" = None

    @contextlib.contextmanager
    def open(self) -> _t.Iterator[None]:
        """Memoise until the block exits (a nested scope shares the outer)."""
        if self.memo is not None:
            yield
            return
        self.memo = {}
        try:
            yield
        finally:
            self.memo = None

    def scoped(self, fn: _t.Callable) -> _t.Callable:
        """``fn`` run inside :meth:`open` (signature kept for ``inspect``)."""
        @functools.wraps(fn)
        def run(*args: _t.Any, **kwargs: _t.Any) -> _t.Any:
            with self.open():
                return fn(*args, **kwargs)
        return run
