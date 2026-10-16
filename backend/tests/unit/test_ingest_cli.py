import runpy
import sys

import pytest

from app.ingest import pipeline


@pytest.fixture
def cli(monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "run_ingest", lambda source, log=print: calls.append(("ingest", source)))
    monkeypatch.setattr(pipeline, "write_messages", lambda msgs, path: calls.append(("write", len(msgs), path)))
    monkeypatch.setattr("app.ingest.parse.parse_export", lambda folder: [{"id": 1, "text": "x"}])

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["app.ingest", *args])
        sys.modules.pop("app.ingest.__main__", None)
        runpy.run_module("app.ingest", run_name="__main__")
        return calls
    return run


def test_seed(cli):
    assert cli("--seed") == [("ingest", pipeline.SEED_FILE)]


def test_folder(cli, tmp_path):
    assert cli(str(tmp_path)) == [("ingest", tmp_path)]


def test_write_seed(cli, tmp_path, capsys):
    assert cli("--write-seed", str(tmp_path)) == [("write", 1, pipeline.SEED_FILE)]
    assert "wrote 1 messages" in capsys.readouterr().out


def test_usage(cli):
    with pytest.raises(SystemExit) as e:
        cli("--bogus")
    assert "python -m app.ingest" in str(e.value)


def test_jsonl_round_trip_and_empty_source(tmp_path):
    path = tmp_path / "m.jsonl"
    pipeline.write_messages([{"id": 1, "text": "mail me at a@b.co"}], path)
    assert pipeline.load_messages(path)[0]["text"] == "mail me at [email removed]"
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="no messages found"):
        pipeline.load_messages(tmp_path / "empty")
