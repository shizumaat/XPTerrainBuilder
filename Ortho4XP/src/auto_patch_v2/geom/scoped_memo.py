"""A MEMO THAT LIVES FOR ONE BLOCK: the scope two module memos open around
one call -- ``airport/obj8_memo`` (one parse per OBJ8 file version while
the placement plan is built, #412) and ``solve/assembly_memo`` (the sheet's
geometry once per staged solve, #2206).  Outside a scope :attr:`memo` is
``None`` and every caller computes; a nested scope shares the outer one's
memo; the memo dies when the outermost block exits."""
from __future__ import annotations

import contextlib
import functools
import typing as _t

__all__ = ["ScopedMemo"]


class ScopedMemo:
    """One module's scoped memo (module docstring)."""

    def __init__(self) -> None:
        #: the open scope's memo, or ``None`` (no scope: every call computes)
        self.memo: "dict | None" = None

    @contextlib.contextmanager
    def scope(self) -> _t.Iterator[None]:
        """Memoise until the block exits (nested scopes share the outer
        one's memo)."""
        if self.memo is not None:
            yield
            return
        self.memo = {}
        try:
            yield
        finally:
            self.memo = None

    def scoped(self, fn: _t.Callable) -> _t.Callable:
        """``fn`` run inside :meth:`scope` (its signature kept: ``inspect``
        reads the wrapped one)."""
        @functools.wraps(fn)
        def run(*args: _t.Any, **kwargs: _t.Any) -> _t.Any:
            with self.scope():
                return fn(*args, **kwargs)
        return run
