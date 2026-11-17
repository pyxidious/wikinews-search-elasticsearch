"""Test della riga di comando."""
import pytest

from wikinews_search.cli import download, main

from .conftest import ES_URL


def test_download_from_file_url_and_skip_existing(sample_dump, tmp_path, capsys):
    dest = tmp_path / "dump.json.tar.gz"
    download(sample_dump.as_uri(), dest)
    assert dest.read_bytes() == sample_dump.read_bytes()
    assert not dest.with_suffix(dest.suffix + ".part").exists()
    download(sample_dump.as_uri(), dest)
    assert "gia' presente" in capsys.readouterr().out


def test_force_download_replaces_existing_file_on_windows(sample_dump, tmp_path):
    dest = tmp_path / "dump.json.tar.gz"
    dest.write_bytes(b"versione precedente")
    download(sample_dump.as_uri(), dest, force=True)
    assert dest.read_bytes() == sample_dump.read_bytes()


@pytest.mark.elasticsearch
def test_index_then_stats(es, sample_dump, capsys):
    name = "itwikinews_test_cli"
    try:
        main(["index", "--dump", str(sample_dump), "--es-url", ES_URL, "--index-name", name])
        main(["stats", "--es-url", ES_URL, "--index-name", name])
        out = capsys.readouterr().out
        assert "Indicizzati 11 articoli" in out and "11 documenti indicizzati" in out
    finally:
        es.indices.delete(index=name, ignore_unavailable=True)
