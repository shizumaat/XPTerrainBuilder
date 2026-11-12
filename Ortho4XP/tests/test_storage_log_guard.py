"""#1881: no test writes ``logs/storage.log`` outside pytest's tmp tree."""
import os

import O4_File_Names as FNAMES
from o4_engine import storage as ST


def test_storage_log_dir_resolves_inside_pytest_tmp(tmp_path_factory):
    base = os.path.realpath(str(tmp_path_factory.getbasetemp()))
    assert FNAMES._data_root_override is None
    assert os.path.realpath(ST._logs_dir()).startswith(base + os.sep)


def test_a_logged_deletion_lands_in_scratch_not_the_data_root(
        tmp_path_factory):
    base = os.path.realpath(str(tmp_path_factory.getbasetemp()))
    real_log = os.path.join(FNAMES.current_data_root(), "logs", ST.LOG_NAME)
    before = os.path.getsize(real_log) if os.path.exists(real_log) else None
    sweep = ST._Sweep.__new__(ST._Sweep)
    sweep._log = None
    sweep._write("guard twin line")
    path = sweep._log.name
    sweep._log.close()
    assert os.path.realpath(path).startswith(base + os.sep)
    after = os.path.getsize(real_log) if os.path.exists(real_log) else None
    assert before == after
