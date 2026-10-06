"""THE ARM TABLE of ``tools/v2_solve_replay.py`` (issue #321): which arm
flag takes effect in which run, and the refusal for every other pairing.

An ARM FLAG changes the problem a run measures (a law key, a weight, a
dropped generator, a corpus input).  The tool dispatches on a MODE
(``--capture``, ``--replay --from STAGE``, ``--why-from`` ...) and each
mode hands only SOME flags on, so a flag given to a mode that never reads
it used to be dropped without a word: ``--replay PKL --from classify
--rule apron.arm_reread_factor=0.0 --emit OUT`` printed no arm line, no
refusal, and emitted the UNARMED result (lane ``mouth314``).  A reading
taken on such a run is attributed to an arm that was never applied.

ONE TABLE decides it, read by ``main()`` before any pickle is opened:

* a flag whose mode reads it prints ``<MODE> ARM --flag value`` (one line
  per flag, whatever the consumer prints beside it), and
* a flag whose mode cannot read it REFUSES BY NAME, saying where it does
  take effect.

``--workers`` is NOT in the table: it pins the work pool, which changes
seconds and never a product (its own ``REPLAY ARM [pool]`` line stands).

Pure: no engine import, no file read.  Twin:
``tests/test_v2_solve_replay_arms.py``.
"""
from __future__ import annotations

__all__ = ["ARM_FLAGS", "CONTEXTS", "EFFECT", "PSEUDO_GENERATORS", "arm_gate",
           "context_of", "drop_gate", "given_arms", "takes_effect"]

#: every run the tool can make, in ``main()``'s own dispatch order
#: (the first that matches wins): ``mode`` or ``mode/<--from stage>``
STAGES = ("classify", "planar", "shapes", "constraints")
CONTEXTS: tuple[str, ...] = (
    "stage1-diff",
    *(f"stage1-dump/{s}" for s in STAGES), "stage1-dump/why-from",
    "probe-site", "bank-from", "capture", "reclassify", "why-from",
    *(f"pad-read/{s}" for s in STAGES),
    *(f"replay/{s}" for s in STAGES),
)

_REPLAY = tuple(f"replay/{s}" for s in STAGES)
_DUMP = tuple(f"stage1-dump/{s}" for s in STAGES)
#: the resumes that RE-RUN the arrangement (classify / planar)
_ARRANGE = tuple(f"{m}/{s}" for m in ("replay", "pad-read", "stage1-dump")
                 for s in ("classify", "planar"))

#: flag -> (contexts it takes effect in, why it is inert everywhere else)
EFFECT: dict[str, tuple[tuple[str, ...], str]] = {
    "--rule": (("capture", "reclassify"),
               "a classify/rules.toml key is read upstream of the capture, "
               "which HOLDS the classification and the flat site derived "
               "from it; a matched pair is two --capture arms, or the dry "
               "--reclassify read"),
    "--placement": (("capture", *_ARRANGE),
                    "a [placement] key is read at classify / planar; a "
                    "later resume or a solved pickle re-uses the captured "
                    "arrangement and cannot see the key"),
    "--cifp-dir": (("capture",), "CIFP is read by the LOAD stage, which "
                                 "only --capture runs"),
    "--data-overlay": (("capture",), "the corpus is read by the LOAD stage, "
                                     "which only --capture runs; a replay "
                                     "re-announces the overlay its capture "
                                     "recorded"),
    "--mod-cache-root": (("capture",), "the airport mod cache is read by "
                                       "the LOAD stage, which only --capture "
                                       "runs"),
    "--design-weight": ((*_REPLAY, *_DUMP, "stage1-dump/why-from"),
                        "a [design] override is applied where the design "
                        "problem is assembled: --replay and --stage1-dump "
                        "(--probe-site takes --probe-arm)"),
    "--drop-generator": ((*_REPLAY, *_DUMP, "stage1-dump/why-from"),
                         "rows are dropped where the constraint set is "
                         "assembled: --replay and --stage1-dump"),
    "--chord-fill": (_REPLAY, "the chord-fill target is published by the "
                              "solving --replay alone"),
    "--method": (_REPLAY, "the linear solver is chosen by the solving "
                          "--replay alone"),
    "--probe-arm": (("probe-site",), "a probe arm is a [design] override of "
                                     "--probe-site's own re-solve"),
    "--late-from": (_REPLAY, "the last stage (spec §53 (9)) is solved by "
                             "the solving --replay alone; a --why-from on "
                             "its --solved-out re-solves it from the pickle"),
}
ARM_FLAGS: tuple[str, ...] = tuple(EFFECT)

_LABEL = {"capture": "CAPTURE", "reclassify": "RECLASSIFY"}


def takes_effect(flag: str, context: str) -> bool:
    """The table's cell: does ``flag`` change what ``context`` measures?"""
    return context in EFFECT[flag][0]


def context_of(a) -> str:
    """The run ``main()`` will make of the parsed arguments ``a`` — its
    dispatch order, first match wins."""
    if a.stage1_diff:
        return "stage1-diff"
    if a.stage1_dump:
        return ("stage1-dump/why-from" if a.why_from
                else f"stage1-dump/{a.resume}")
    if a.probe_site:
        return "probe-site"
    if a.bank_from:
        return "bank-from"
    if a.capture:
        return "capture"
    if a.reclassify:
        return "reclassify"
    if a.why_from:
        return "why-from"
    if a.pad_read or a.rim_diagnostics:
        return f"pad-read/{a.resume}"
    return f"replay/{a.resume}"


def given_arms(a) -> dict[str, str]:
    """The arm flags the command line carries, with their values as typed
    (``--method`` only when it is not the default)."""
    raw = {"--rule": a.rule, "--placement": a.placement,
           "--cifp-dir": a.cifp_dir, "--data-overlay": a.data_overlay,
           "--mod-cache-root": a.mod_cache_root,
           "--design-weight": a.design_weight,
           "--drop-generator": a.drop_generator,
           "--chord-fill": a.chord_fill,
           "--method": None if a.method == "normal" else a.method,
           "--probe-arm": a.probe_arm,
           "--late-from": a.late_from}
    out = {}
    for flag, v in raw.items():
        if v is None or v == [] or v == "":
            continue
        out[flag] = " ".join(map(str, v)) if isinstance(v, list) else str(v)
    return out


def arm_gate(context: str, arms: dict[str, str]) -> list[str]:
    """The arm lines of a run in ``context`` carrying ``arms`` — or a
    ``SystemExit`` REFUSAL naming every flag the run cannot apply and
    where each one does take effect.  Nothing is printed here."""
    inert = [f for f in arms if not takes_effect(f, context)]
    if inert:
        raise SystemExit("REFUSED: " + "; ".join(
            f"{f} {arms[f]} cannot take effect at {context} — "
            f"{EFFECT[f][1]} (takes effect at: {', '.join(EFFECT[f][0])})"
            for f in inert))
    label = _LABEL.get(context, "REPLAY")
    return [f"{label} ARM {f} {v} (takes effect at {context})"
            for f, v in arms.items()]


#: ``--drop-generator`` names that are no row's generator: a CHANNEL EDIT
#: the replay drops by name before the solve (the EAT's §36 (5) trend
#: withdrawal; ``eat_anchor_rect`` is the EAT rows' own generator)
PSEUDO_GENERATORS: tuple[str, ...] = ("eat_ramp_reach",)


def drop_gate(drop, generators, heads) -> None:
    """REFUSE a ``--drop-generator`` name that is no known generator, no
    ruling head and no pseudo-generator (issue #420): such a name dropped
    NOTHING and said nothing, so the run was reported under an arm that
    was never applied.  ``generators`` / ``heads`` are the names the
    caller's constraint set (and generator register) can drop by; the
    refusal lists them.  Nothing is printed here."""
    gens = set(generators) | set(PSEUDO_GENERATORS)
    heads = set(heads)
    unknown = [d for d in drop if d not in gens and d not in heads]
    if unknown:
        raise SystemExit(
            f"REFUSED: --drop-generator {' '.join(unknown)} names no "
            f"generator and no ruling head — it would drop nothing.  "
            f"Known generators: {', '.join(sorted(gens))}.  "
            f"Known ruling heads: {', '.join(sorted(heads)) or '-'}")
