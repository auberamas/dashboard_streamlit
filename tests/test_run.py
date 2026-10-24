"""Tests of the launcher: the dashboard must start whatever happens during the update"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run  # noqa: E402
from utils import datagouv, state  # noqa: E402

OLD_DATE = "2026-07-06T10:51:07.978000+00:00"
NEW_DATE = "2026-11-02T08:00:00+00:00"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Temporary data folder and every slow or network call replaced by a recorder"""
    calls = []

    monkeypatch.setattr(run, "RAW_CSV", tmp_path / "effectifs.csv")
    monkeypatch.setattr(run, "CLEAN_CSV", tmp_path / "effectifs_clean.csv")
    monkeypatch.setattr(run, "TABLES", tmp_path / "tables.pkl")
    monkeypatch.setattr(state, "STATE_FILE", tmp_path / "state.json")

    import cleaning_analysis.clean as clean
    import utils.tables as tables

    monkeypatch.setattr(tables, "build_tables", lambda *a, **k: calls.append("build_tables"))
    monkeypatch.setattr(clean, "run", lambda *a, **k: calls.append("clean"))

    resource = {"resource_id": "abc", "url": "https://example.invalid/f.csv", "last_modified": OLD_DATE}
    monkeypatch.setattr(datagouv, "fetch_resource", lambda: dict(resource))

    def fake_download(url, target, **kwargs):
        calls.append("download")
        Path(target).write_bytes(b"x" * 10)
        return 10

    monkeypatch.setattr(datagouv, "download", fake_download)

    monkeypatch.setattr(run, "launch", lambda port, browser=True: calls.append("launch") or 0)

    class Env:
        pass

    holder = Env()
    holder.calls = calls
    holder.resource = resource
    holder.dir = tmp_path
    return holder


# ** STEP 1 DATA TO SHOW **

def test_tables_present_means_nothing_to_do(env):
    run.TABLES.write_bytes(b"x")
    run.prepare()
    assert env.calls == []


def test_missing_tables_are_rebuilt_from_the_clean_csv(env):
    run.CLEAN_CSV.write_bytes(b"x")
    run.prepare()
    assert env.calls == ["build_tables"]


def test_missing_clean_csv_is_rebuilt_from_the_raw_csv(env):
    run.RAW_CSV.write_bytes(b"x")
    run.prepare()
    assert env.calls == ["clean"]


def test_no_local_data_downloads_the_raw_file(env):
    run.prepare()
    assert env.calls == ["download", "clean"]


# ** STEP 2 UPDATE **

def test_first_launch_keeps_the_local_file(env):
    """No state file yet but a csv is there: nothing is downloaded"""
    run.RAW_CSV.write_bytes(b"x" * 5)
    message = run.refresh()
    assert env.calls == []
    assert "conservee" in message
    assert state.read_state()["remote_last_modified"] == OLD_DATE


def test_up_to_date_does_nothing(env):
    run.RAW_CSV.write_bytes(b"x")
    state.write_state({"remote_last_modified": OLD_DATE, "downloaded_at": None,
                       "size_bytes": 1, "resource_id": None})
    assert "a jour" in run.refresh()
    assert env.calls == []


def test_newer_remote_downloads_cleans_then_remembers(env):
    run.RAW_CSV.write_bytes(b"x")
    state.write_state({"remote_last_modified": OLD_DATE, "downloaded_at": None,
                       "size_bytes": 1, "resource_id": None})
    env.resource["last_modified"] = NEW_DATE

    run.refresh()

    assert env.calls == ["download", "clean"]
    assert state.read_state()["remote_last_modified"] == NEW_DATE


# ** THE DASHBOARD ALWAYS STARTS **

def test_dashboard_starts_when_data_gouv_is_down(env, monkeypatch):
    run.TABLES.write_bytes(b"x")
    run.RAW_CSV.write_bytes(b"x")

    def down():
        raise datagouv.DataGouvError("injoignable")

    monkeypatch.setattr(datagouv, "fetch_resource", down)

    assert run.main(["--no-browser"]) == 0
    assert env.calls == ["launch"]


def test_failed_cleaning_keeps_the_old_state_and_still_starts(env, monkeypatch):
    run.TABLES.write_bytes(b"x")
    run.RAW_CSV.write_bytes(b"x")
    state.write_state({"remote_last_modified": OLD_DATE, "downloaded_at": None,
                       "size_bytes": 1, "resource_id": None})
    env.resource["last_modified"] = NEW_DATE

    import cleaning_analysis.clean as clean

    def broken(*args, **kwargs):
        raise ValueError("colonne manquante")

    monkeypatch.setattr(clean, "run", broken)

    assert run.main(["--no-browser"]) == 0
    assert "launch" in env.calls
    # not remembered so the next launch tries again
    assert state.read_state()["remote_last_modified"] == OLD_DATE


def test_skip_update_never_calls_data_gouv(env, monkeypatch):
    run.TABLES.write_bytes(b"x")

    def forbidden():
        raise AssertionError("data.gouv ne doit pas etre appele")

    monkeypatch.setattr(datagouv, "fetch_resource", forbidden)

    assert run.main(["--skip-update", "--no-browser"]) == 0
    assert env.calls == ["launch"]


def test_no_data_and_no_network_stops_with_a_clear_code(env, monkeypatch):
    """The only case where the launcher refuses to start: there is nothing to show"""
    def down():
        raise datagouv.DataGouvError("injoignable")

    monkeypatch.setattr(datagouv, "fetch_resource", down)

    assert run.main(["--no-browser"]) == 1
    assert "launch" not in env.calls
