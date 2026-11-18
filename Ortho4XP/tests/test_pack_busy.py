"""#2168: a pack-row action waits only for a run writing that pack."""

from o4_engine import pack_busy


def test_only_a_run_on_the_packs_tiles_holds_it(monkeypatch):
    from auto_patch import object_rebake

    monkeypatch.setattr(object_rebake, "pack_tiles",
                        lambda root: {"+39-107"})
    assert pack_busy.busy_reason("/CS/KASE", set()) == ""
    assert pack_busy.busy_reason("/CS/KASE", {"+48+002", "+49+002"}) == ""
    reason = pack_busy.busy_reason("/CS/KASE", {"+39-107", "+48+002"})
    assert "+39-107" in reason and "+48+002" not in reason


def test_the_session_refuses_a_write_with_the_reason(monkeypatch):
    from o4_engine.session import EngineSession as Session

    session = Session.__new__(Session)
    monkeypatch.setattr(Session, "pack_busy_reason",
                        lambda self, root: "the current run is building +39-107")
    warnings = []
    monkeypatch.setattr(Session, "log_warning",
                        lambda self, text: warnings.append(text))
    ran = []
    reply = session._pack_choice_worker(
        "t", lambda *a: ran.append(a), "/CS/KASE", "undo", None, None)
    assert reply == {"status": "refused",
                     "reason": "the current run is building +39-107"}
    assert ran == [] and "+39-107" in warnings[0]
