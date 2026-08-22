from unittest.mock import patch

from corrective_rag.ingestion.cli import main
from corrective_rag.ingestion.pipeline import IngestionResult
from corrective_rag.ingestion.wikipedia_client import WikipediaFetchError


def _articles_file(tmp_path):
    path = tmp_path / "articles.txt"
    path.write_text("Apollo 11\nVoyager 1\n")
    return str(path)


def test_missing_api_key_exits_nonzero_without_calling_run_ingestion(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("corrective_rag.ingestion.cli.run_ingestion") as mock_run:
        exit_code = main(["--articles", _articles_file(tmp_path)])

    assert exit_code == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    mock_run.assert_not_called()


def test_successful_run_prints_summary_and_exits_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("corrective_rag.ingestion.cli.run_ingestion") as mock_run:
        mock_run.return_value = IngestionResult(
            corpus_version="20260822-deadbeef", chunk_count=3, chunk_ids=["a", "b", "c"]
        )
        exit_code = main(["--articles", _articles_file(tmp_path)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "corpus_version=20260822-deadbeef" in out
    assert "chunks=3" in out


def test_wikipedia_fetch_error_exits_nonzero_and_names_the_article(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("corrective_rag.ingestion.cli.run_ingestion") as mock_run:
        mock_run.side_effect = WikipediaFetchError("Apollo 11", "not found")
        exit_code = main(["--articles", _articles_file(tmp_path)])

    assert exit_code == 1
    assert "Apollo 11" in capsys.readouterr().err
