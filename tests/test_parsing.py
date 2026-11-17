"""Test unitari: lettura del dump e pulizia dei record."""
import gzip
import json

from wikinews_search.dump import iter_records
from wikinews_search.parsing import clean_categories, html_to_text, parse_date, record_to_article

from .conftest import write_ndjson
from .sample_data import RECORDS, rec


def test_html_to_text_removes_noise_and_keeps_paragraphs():
    html = ("<html><head><title>T</title></head><body><p>Primo <b>paragrafo</b>, ok.</p>"
            "<sup>[1]</sup><script>x()</script><style>p{}</style><p>Secondo</p></body></html>")
    assert html_to_text(html) == "Primo paragrafo, ok.\nSecondo"


def test_html_entities_are_decoded():
    assert html_to_text("<p>3 &lt; 5 &amp; 7</p>") == "3 < 5 & 7"


def test_parse_date_variants():
    assert parse_date("2024-06-10T08:00:00Z").year == 2024
    assert parse_date("2024-06-10T08:00:00+02:00").tzinfo is None
    assert parse_date("non una data") is None
    assert parse_date(None) is None


def test_clean_categories():
    raw = [{"name": "Categoria:Disastri_e_incidenti"}, {"name": "Categoria:Pubblicati"},
           {"name": "Categoria:Italia"}, {"name": "Categoria:Italia"}, {"name": "A, B"}]
    assert clean_categories(raw) == ["Disastri e incidenti", "Italia", "A B"]


def test_clean_categories_drops_maintenance_and_date_categories():
    raw = [{"name": "Categoria:Politica"}, {"name": "Categoria:Articoli archiviati"},
           {"name": "Categoria:Articoli da controllare per l'archiviazione"},
           {"name": "Categoria:Notizie per Wikivoyage scadute"}, {"name": "Categoria:3 aprile 2008"},
           {"name": "Categoria:Elezioni politiche italiane 2008"}, {"name": "Categoria:Italia"}]
    assert clean_categories(raw) == ["Politica", "Elezioni politiche italiane 2008", "Italia"]


def test_record_to_article_ok():
    article = record_to_article(RECORDS[0])
    assert article.id == "1001"
    assert article.title.startswith("Elezioni comunali")
    assert "[1]" not in article.body
    assert article.categories == ["Politica", "Italia", "Roma"]
    assert article.date.year == 2024


def test_record_to_article_discards_invalid_records():
    assert record_to_article(rec(1, "Vuota", "2020-01-01T00:00:00Z", [], "")) is None
    assert record_to_article(rec(2, "Redirect", "2020-01-01T00:00:00Z", [], "<p>Redirect</p>")) is None
    long = "<p>Testo abbastanza lungo da superare la soglia minima di caratteri.</p>"
    assert record_to_article(rec(3, "Altro namespace", "2020-01-01T00:00:00Z", [], long, namespace=1)) is None
    assert record_to_article({"identifier": 4, "article_body": {"html": long}}) is None  # senza titolo


def test_iter_records_reads_tar_gz(sample_dump):
    assert len(list(iter_records(sample_dump))) == len(RECORDS)


def test_iter_records_plain_and_gzip_and_bad_lines(tmp_path):
    plain = tmp_path / "a.ndjson"
    write_ndjson(plain, RECORDS[:3])
    assert len(list(iter_records(plain))) == 3

    zipped = tmp_path / "a.ndjson.gz"
    with gzip.open(zipped, "wt", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in RECORDS[:2]))
    assert len(list(iter_records(zipped))) == 2

    broken = tmp_path / "b.ndjson"
    broken.write_text(json.dumps(RECORDS[0]) + "\n{non json\n\n" + json.dumps(RECORDS[1]) + "\n", encoding="utf-8")
    assert len(list(iter_records(broken))) == 2
